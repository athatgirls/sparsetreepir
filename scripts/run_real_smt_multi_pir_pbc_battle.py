from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from lwe_pir_backend import (
    average_lwe_metrics,
    execute_lwe_batch_pir,
    random_byte_database,
    setup_lwe_pir_database,
)
from run_lwe_pir_backend_experiment import targets_from_indexes
from run_real_smt_final_experiment_suite import (
    build_instance,
    pbc_width,
    selected_workloads,
)
from run_simplepir_full_backend_experiment import build_pbc_active_indexes


RECORD_BYTES = 32


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_simplepir_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def simplepir_backend_rows(path: Path) -> List[Dict[str, object]]:
    rows = []
    for row in read_simplepir_rows(path):
        if row["scheme"] not in {"pbc_smt_active", "sparsetreepir_activebalance"}:
            continue
        rows.append(
            {
                "backend": "SimplePIR-full-api",
                "dataset": row["dataset"],
                "height": int(row["height"]),
                "scheme": "PBC-SMT" if row["scheme"] == "pbc_smt_active" else "SparseTreePIR",
                "active_records": int(row["active_records"]),
                "width": int(row["width"]),
                "max_bucket": "",
                "query_samples": int(row["query_samples"]),
                "setup_ms": float(row["setup_ms"]),
                "client_query_ms": float(row["client_query_ms"]),
                "server_total_ms": float(row["server_total_ms"]),
                "server_parallel_ms": float(row["server_parallel_ms"]),
                "client_decode_ms": float(row["client_decode_ms"]),
                "online_upload_kb": float(row["online_upload_kb"]),
                "online_download_kb": float(row["online_download_kb"]),
                "online_total_kb": float(row["online_total_kb"]),
                "offline_kb": float(row["offline_kb"]),
                "note": "Measured through the existing SimplePIR Go bridge; 32-byte digest retrieved as eight 32-bit chunks.",
            }
        )
    return rows


def xor_two_server_cost(loads: Sequence[int], width: int) -> Dict[str, float]:
    # Standard two-server XOR/PIR communication shape: two query vectors per
    # subdatabase and two record-size responses. This is an analytic backend
    # model, not a production implementation.
    query_bytes = 0
    response_bytes = 0
    for idx in range(width):
        size = int(loads[idx]) if idx < len(loads) else 0
        padded = max(1, size)
        query_bytes += 2 * math.ceil(padded / 8)
        response_bytes += 2 * RECORD_BYTES
    return {
        "online_upload_kb": query_bytes / 1024.0,
        "online_download_kb": response_bytes / 1024.0,
        "online_total_kb": (query_bytes + response_bytes) / 1024.0,
    }


def loads_from_indexes(indexes: Dict[int, List[Tuple[int, int, int]]], width: int) -> List[int]:
    return [len(indexes.get(color, [])) for color in range(1, width + 1)]


def target_lists_for_sparse(
    indexes: Dict[int, List[Tuple[int, int, int]]],
    occupied: Sequence[int],
    leaves: Sequence[int],
    width: int,
) -> List[List[Optional[int]]]:
    return [targets_from_indexes(indexes, occupied, leaf, width) for leaf in leaves]


def target_lists_for_pbc(width: int, sample_count: int) -> List[List[Optional[int]]]:
    # PBC-SMT is measured as a generic batch layout over replicated active
    # records. Its buckets do not encode served intervals, so every subquery is
    # a valid private backend lookup from a resource-shape point of view.
    return [[None] * width for _ in range(sample_count)]


def lwe_rows_for_instance(
    instance,
    query_samples: int,
    seed: int,
    dimension: int,
) -> List[Dict[str, object]]:
    sampled = [
        instance.occupied_leaves[(seed + idx) % len(instance.occupied_leaves)]
        for idx in range(min(query_samples, len(instance.occupied_leaves)))
    ]
    active_count = len(instance.active_nodes)
    pbc_w = pbc_width(instance.active_width)
    pbc_indexes = build_pbc_active_indexes(active_count, instance.active_width)
    sparse_indexes = instance.color_indexes

    layouts = [
        ("PBC-SMT", pbc_indexes, pbc_w, 3 * active_count, target_lists_for_pbc(pbc_w, len(sampled))),
        (
            "SparseTreePIR",
            sparse_indexes,
            instance.active_width,
            active_count,
            target_lists_for_sparse(sparse_indexes, instance.occupied_leaves, sampled, instance.active_width),
        ),
    ]

    rows: List[Dict[str, object]] = []
    for scheme, indexes, width, stored_records, target_lists in layouts:
        loads = loads_from_indexes(indexes, width)
        tables = random_byte_database(loads, seed=seed * 101 + len(scheme))
        prepared = setup_lwe_pir_database(tables, seed=seed * 103 + len(scheme), dimension=dimension)
        samples = [
            execute_lwe_batch_pir(prepared, targets, seed=seed * 107 + offset + len(scheme))
            for offset, targets in enumerate(target_lists)
        ]
        metrics = average_lwe_metrics(samples)
        rows.append(
            {
                "backend": f"LWE-PIR-prototype-d{dimension}",
                "dataset": instance.spec.label,
                "height": instance.height,
                "scheme": scheme,
                "active_records": active_count,
                "width": width,
                "max_bucket": max(loads) if loads else 0,
                "query_samples": len(sampled),
                "setup_ms": metrics["setup_ms"],
                "client_query_ms": metrics["client_query_ms"],
                "server_total_ms": metrics["server_total_ms"],
                "server_parallel_ms": metrics["server_parallel_ms"],
                "client_decode_ms": metrics["client_extract_ms"],
                "online_upload_kb": metrics["query_bytes"] / 1024.0,
                "online_download_kb": metrics["response_bytes"] / 1024.0,
                "online_total_kb": (metrics["query_bytes"] + metrics["response_bytes"]) / 1024.0,
                "offline_kb": metrics["hint_bytes"] / 1024.0,
                "note": "Executable randomized LWE-style prototype over the same bucket loads; intended as a backend-shape check.",
            }
        )
    return rows


def xor_rows_for_instance(instance, query_samples: int) -> List[Dict[str, object]]:
    active_count = len(instance.active_nodes)
    pbc_w = pbc_width(instance.active_width)
    pbc_indexes = build_pbc_active_indexes(active_count, instance.active_width)
    layouts = [
        ("PBC-SMT", pbc_indexes, pbc_w, 3 * active_count),
        ("SparseTreePIR", instance.color_indexes, instance.active_width, active_count),
    ]
    rows: List[Dict[str, object]] = []
    for scheme, indexes, width, stored_records in layouts:
        loads = loads_from_indexes(indexes, width)
        cost = xor_two_server_cost(loads, width)
        rows.append(
            {
                "backend": "2server-XOR-PIR-model",
                "dataset": instance.spec.label,
                "height": instance.height,
                "scheme": scheme,
                "active_records": active_count,
                "width": width,
                "max_bucket": max(loads) if loads else 0,
                "query_samples": query_samples,
                "setup_ms": 0.0,
                "client_query_ms": 0.0,
                "server_total_ms": float(sum(loads) * RECORD_BYTES) / 1_000_000.0,
                "server_parallel_ms": float((max(loads) if loads else 0) * RECORD_BYTES) / 1_000_000.0,
                "client_decode_ms": 0.0,
                "online_upload_kb": cost["online_upload_kb"],
                "online_download_kb": cost["online_download_kb"],
                "online_total_kb": cost["online_total_kb"],
                "offline_kb": 0.0,
                "note": "Analytic two-server XOR/PIR communication model: two bit-vector queries plus two record responses per bucket.",
            }
        )
    return rows


def summarize_pairs(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str, int], Dict[str, Dict[str, object]]] = {}
    for row in rows:
        key = (str(row["backend"]), str(row["dataset"]), int(row["height"]))
        grouped.setdefault(key, {})[str(row["scheme"])] = row

    summary = []
    for (backend, dataset, height), schemes in sorted(grouped.items()):
        if "PBC-SMT" not in schemes or "SparseTreePIR" not in schemes:
            continue
        pbc = schemes["PBC-SMT"]
        sparse = schemes["SparseTreePIR"]
        summary.append(
            {
                "backend": backend,
                "dataset": dataset,
                "height": height,
                "pbc_width": pbc["width"],
                "sparse_width": sparse["width"],
                "pbc_online_kb": pbc["online_total_kb"],
                "sparse_online_kb": sparse["online_total_kb"],
                "online_reduction": 1.0 - float(sparse["online_total_kb"]) / max(1e-9, float(pbc["online_total_kb"])),
                "pbc_query_ms": pbc["client_query_ms"],
                "sparse_query_ms": sparse["client_query_ms"],
                "query_reduction": 1.0 - float(sparse["client_query_ms"]) / max(1e-9, float(pbc["client_query_ms"])),
                "pbc_parallel_ms": pbc["server_parallel_ms"],
                "sparse_parallel_ms": sparse["server_parallel_ms"],
                "parallel_reduction": 1.0 - float(sparse["server_parallel_ms"]) / max(1e-9, float(pbc["server_parallel_ms"])),
            }
        )
    return summary


def avg(values: Iterable[float]) -> float:
    vals = list(values)
    return mean(vals) if vals else 0.0


def write_note(path: Path, summary_rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_backend: Dict[str, List[Dict[str, object]]] = {}
    for row in summary_rows:
        by_backend.setdefault(str(row["backend"]), []).append(row)

    lines = [
        "# Multi-PIR Backend PBC-SMT Battle",
        "",
        "This experiment compares the same two privacy-preserving organizations on real SMT workloads:",
        "",
        "- `PBC-SMT`: generic probabilistic-batch-code style organization over active SMT proof records.",
        "- `SparseTreePIR`: active-interval color stores after ActiveBalance.",
        "",
        "The point is not that PBC is a PIR backend. PBC is a batch organization. We therefore compare PBC-SMT and SparseTreePIR under the same backend family whenever possible.",
        "",
        "## Backend summary",
        "",
        "| Backend | Avg. online reduction | Avg. query-time reduction | Avg. parallel-server reduction |",
        "|---|---:|---:|---:|",
    ]
    for backend, rows in by_backend.items():
        lines.append(
            f"| {backend} | {100*avg(float(r['online_reduction']) for r in rows):.1f}% | "
            f"{100*avg(float(r['query_reduction']) for r in rows):.1f}% | "
            f"{100*avg(float(r['parallel_reduction']) for r in rows):.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Per-workload summary",
            "",
            "| Backend | Dataset | h | PBC width | Sparse width | PBC KB | Sparse KB | Online red. |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['backend']} | {row['dataset']} | {row['height']} | {row['pbc_width']} | {row['sparse_width']} | "
            f"{float(row['pbc_online_kb']):.2f} | {float(row['sparse_online_kb']):.2f} | "
            f"{100*float(row['online_reduction']):.1f}% |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workloads", default="all")
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--query-samples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=99173)
    parser.add_argument("--hybrid-rounds", type=int, default=200)
    parser.add_argument("--balance-rounds", type=int, default=600)
    parser.add_argument("--lwe-dimension", type=int, default=64)
    parser.add_argument("--simplepir-csv", type=Path, default=Path("examples/real_smt_final_suite_simplepir.csv"))
    parser.add_argument("--output", type=Path, default=Path("examples/real_smt_multi_pir_pbc_battle.csv"))
    parser.add_argument("--summary", type=Path, default=Path("examples/real_smt_multi_pir_pbc_battle_summary.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/real_smt_multi_pir_pbc_battle_note.md"))
    args = parser.parse_args()

    rows: List[Dict[str, object]] = []
    rows.extend(simplepir_backend_rows(args.simplepir_csv))

    for spec in selected_workloads(args.workloads):
        instance = build_instance(
            spec,
            args.height,
            hybrid_rounds=args.hybrid_rounds,
            balance_rounds=args.balance_rounds,
        )
        rows.extend(
            lwe_rows_for_instance(
                instance,
                query_samples=args.query_samples,
                seed=args.seed,
                dimension=args.lwe_dimension,
            )
        )
        rows.extend(xor_rows_for_instance(instance, query_samples=args.query_samples))

    write_csv(args.output, rows)
    summary_rows = summarize_pairs(rows)
    write_csv(args.summary, summary_rows)
    write_note(args.note, summary_rows)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.summary}")
    print(f"Wrote {args.note}")


if __name__ == "__main__":
    main()
