from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence, Tuple

from run_piano_wsl_backend_from_layouts import run_piano
from run_real_smt_final_experiment_suite import (
    InstanceArtifacts,
    WorkloadSpec,
    build_instance,
    pbc_width,
    selected_workloads,
    simplepir_rows_for_instance,
)
from run_simplepir_full_backend_experiment import (
    build_pbc_active_indexes,
    ensure_subst_drive,
    simplepir_environment,
)


def parse_backend_list(raw: str) -> List[str]:
    if raw.strip().lower() == "none":
        return []
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    allowed = {"simplepir", "piano"}
    bad = sorted(set(values) - allowed)
    if bad:
        raise ValueError(f"unknown backend(s): {bad}. Allowed: {sorted(allowed)}")
    return values


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_reduction(baseline: float, improved: float) -> float:
    return 1.0 - improved / max(1e-9, baseline)


def optional_reduction(baseline: float, improved: float, *, min_baseline: float = 1e-9) -> float | str:
    if abs(baseline) < min_baseline:
        return ""
    return safe_reduction(baseline, improved)


def loads_from_indexes(indexes: Dict[int, List[Tuple[int, int, int]]], width: int) -> List[int]:
    return [len(indexes.get(color, [])) for color in range(1, width + 1)]


def normalize_simplepir_row(row: Dict[str, object]) -> Dict[str, object]:
    scheme = str(row["scheme"])
    if scheme == "pbc_smt_active":
        normalized = "PBC-SMT"
    elif scheme == "sparsetreepir_activebalance":
        normalized = "SparseTreePIR"
    else:
        raise ValueError(f"unexpected SimplePIR scheme: {scheme}")
    return {
        "backend": "SimplePIR-full-api",
        "dataset": row["dataset"],
        "height": row["height"],
        "scheme": normalized,
        "active_records": row["active_records"],
        "width": row["width"],
        "max_bucket": "",
        "query_samples": row["query_samples"],
        "completed_queries": row["query_samples"],
        "setup_ms": row["setup_ms"],
        "client_query_ms": row["client_query_ms"],
        "server_total_ms": row["server_total_ms"],
        "server_parallel_ms": row["server_parallel_ms"],
        "client_decode_ms": row["client_decode_ms"],
        "offline_kb": row["offline_kb"],
        "online_upload_kb": row["online_upload_kb"],
        "online_download_kb": row["online_download_kb"],
        "online_total_kb": row["online_total_kb"],
        "evidence": "full 32-byte digest retrieval through SimplePIR Go API; recovered chunks are verified",
    }


def run_simplepir_showcase(
    instances: Sequence[InstanceArtifacts],
    *,
    query_samples: int,
    seed: int,
    layout_dir: Path,
    simplepir_timeout: int,
    simplepir_drive: str,
) -> List[Dict[str, object]]:
    workspace = Path.cwd()
    workspace_drive = ensure_subst_drive(simplepir_drive, workspace) if os.name == "nt" else workspace.resolve()
    simplepir_root, go_exe, env = simplepir_environment(workspace_drive)
    rows: List[Dict[str, object]] = []
    for offset, instance in enumerate(instances):
        raw_rows = simplepir_rows_for_instance(
            instance,
            query_samples=query_samples,
            seed=seed + offset * 1009 + instance.unique_keys,
            layout_dir=layout_dir,
            workspace=workspace,
            workspace_drive=workspace_drive,
            simplepir_root=simplepir_root,
            go_exe=go_exe,
            env=env,
            timeout=simplepir_timeout,
        )
        for row in raw_rows:
            if row["scheme"] in {"pbc_smt_active", "sparsetreepir_activebalance"}:
                rows.append(normalize_simplepir_row(row))
    return rows


def run_piano_showcase(
    instances: Sequence[InstanceArtifacts],
    *,
    piano_repo: Path,
    query_samples: int,
    seed: int,
    timeout: int,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for offset, instance in enumerate(instances):
        active_count = len(instance.active_nodes)
        pbc_w = pbc_width(instance.active_width)
        pbc_loads = loads_from_indexes(build_pbc_active_indexes(active_count, instance.active_width), pbc_w)
        sparse_loads = loads_from_indexes(instance.color_indexes, instance.active_width)
        layouts = [
            ("PBC-SMT", pbc_loads, 3 * active_count),
            ("SparseTreePIR", sparse_loads, active_count),
        ]
        for scheme, loads, stored_records in layouts:
            metrics = run_piano(
                repo=piano_repo,
                sizes=loads,
                queries=query_samples,
                seed=seed + offset * 7919 + len(scheme),
                timeout=timeout,
            )
            rows.append(
                {
                    "backend": "PIANO-local-runner",
                    "dataset": instance.spec.label,
                    "height": instance.height,
                    "scheme": scheme,
                    "active_records": active_count,
                    "stored_records": stored_records,
                    "width": len(loads),
                    "max_bucket": max(loads) if loads else 0,
                    "query_samples": query_samples,
                    "completed_queries": int(metrics["queries"]),
                    "setup_ms": metrics["setup_ms"],
                    "client_query_ms": metrics["client_query_ms"],
                    "server_total_ms": metrics["server_total_ms"],
                    "server_parallel_ms": metrics["server_parallel_ms"],
                    "client_decode_ms": 0.0,
                    "offline_kb": metrics["offline_kb"],
                    "online_upload_kb": metrics["online_upload_kb"],
                    "online_download_kb": metrics["online_download_kb"],
                    "online_total_kb": metrics["online_total_kb"],
                    "evidence": "PIANO executable runner over the exact real-workload bucket-size vector",
                }
            )
    return rows


def summarize(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str, int], Dict[str, Dict[str, object]]] = {}
    for row in rows:
        key = (str(row["backend"]), str(row["dataset"]), int(row["height"]))
        grouped.setdefault(key, {})[str(row["scheme"])] = row

    out: List[Dict[str, object]] = []
    for (backend, dataset, height), schemes in sorted(grouped.items()):
        if "PBC-SMT" not in schemes or "SparseTreePIR" not in schemes:
            continue
        pbc = schemes["PBC-SMT"]
        sparse = schemes["SparseTreePIR"]
        out.append(
            {
                "backend": backend,
                "dataset": dataset,
                "height": height,
                "pbc_width": pbc["width"],
                "sparse_width": sparse["width"],
                "width_reduction": safe_reduction(float(pbc["width"]), float(sparse["width"])),
                "pbc_max_bucket": pbc.get("max_bucket", ""),
                "sparse_max_bucket": sparse.get("max_bucket", ""),
                "max_bucket_reduction": (
                    ""
                    if pbc.get("max_bucket", "") == ""
                    else safe_reduction(float(pbc["max_bucket"]), float(sparse["max_bucket"]))
                ),
                "pbc_online_kb": pbc["online_total_kb"],
                "sparse_online_kb": sparse["online_total_kb"],
                "online_reduction": safe_reduction(float(pbc["online_total_kb"]), float(sparse["online_total_kb"])),
                "pbc_query_ms": pbc["client_query_ms"],
                "sparse_query_ms": sparse["client_query_ms"],
                "query_reduction": safe_reduction(float(pbc["client_query_ms"]), float(sparse["client_query_ms"])),
                "pbc_setup_ms": pbc["setup_ms"],
                "sparse_setup_ms": sparse["setup_ms"],
                "setup_reduction": safe_reduction(float(pbc["setup_ms"]), float(sparse["setup_ms"])),
                "pbc_server_total_ms": pbc["server_total_ms"],
                "sparse_server_total_ms": sparse["server_total_ms"],
                "server_total_reduction": optional_reduction(
                    float(pbc["server_total_ms"]), float(sparse["server_total_ms"]), min_baseline=0.01
                ),
                "pbc_server_parallel_ms": pbc["server_parallel_ms"],
                "sparse_server_parallel_ms": sparse["server_parallel_ms"],
                "server_parallel_reduction": optional_reduction(
                    float(pbc["server_parallel_ms"]), float(sparse["server_parallel_ms"]), min_baseline=0.01
                ),
            }
        )
    return out


def avg(rows: Sequence[Dict[str, object]], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key, "") != ""]
    return mean(values) if values else 0.0


def pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def write_note(path: Path, raw_rows: Sequence[Dict[str, object]], summary_rows: Sequence[Dict[str, object]]) -> None:
    by_backend: Dict[str, List[Dict[str, object]]] = {}
    for row in summary_rows:
        by_backend.setdefault(str(row["backend"]), []).append(row)

    lines = [
        "# Real Backend Showcase on Real SMT Workloads",
        "",
        "This run is the main executable-backend experiment for the paper: real SMT key sets are converted into SparseTreePIR/PBC-SMT PIR-facing layouts and then measured through concrete backend runners.",
        "",
        "## Backend Evidence",
        "",
        "| Backend | Evidence level |",
        "|---|---|",
        "| SimplePIR-full-api | Full 32-byte digest retrieval through the SimplePIR Go API; recovered chunks are verified. |",
        "| PIANO-local-runner | Executable PIANO runner over the exact bucket-size vectors induced by the real layouts. |",
        "",
        "## Average Effect Against PBC-SMT",
        "",
        "| Backend | Datasets | Width reduction | Max-bucket reduction | Online KB reduction | Query-time reduction | Answer-time reduction | Setup reduction |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for backend, rows in by_backend.items():
        lines.append(
            f"| {backend} | {len(rows)} | {pct(avg(rows, 'width_reduction'))} | "
            f"{pct(avg(rows, 'max_bucket_reduction')) if any(r.get('max_bucket_reduction', '') != '' for r in rows) else 'n/a'} | "
            f"{pct(avg(rows, 'online_reduction'))} | {pct(avg(rows, 'query_reduction'))} | "
            f"{pct(avg(rows, 'server_total_reduction')) if any(r.get('server_total_reduction', '') != '' for r in rows) else 'n/a'} | "
            f"{pct(avg(rows, 'setup_reduction'))} |"
        )

    lines.extend(
        [
            "",
            "## Per-Workload Summary",
            "",
            "| Backend | Dataset | h | PBC width | Sparse width | PBC KB | Sparse KB | Online reduction |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['backend']} | {row['dataset']} | {row['height']} | "
            f"{row['pbc_width']} | {row['sparse_width']} | "
            f"{float(row['pbc_online_kb']):.2f} | {float(row['sparse_online_kb']):.2f} | "
            f"{pct(float(row['online_reduction']))} |"
        )

    lines.extend(
        [
            "",
            "## Scope",
            "",
            "These rows should be presented as real-workload, executable-backend evidence. They do not claim that Spiral, YPIR, or SealPIRplus have already been fully integrated with SparseTreePIR; those remain separate artifact-engineering extensions.",
            "",
            f"Raw rows: {len(raw_rows)}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_instances(workloads: Sequence[WorkloadSpec], height: int, hybrid_rounds: int, balance_rounds: int) -> List[InstanceArtifacts]:
    instances: List[InstanceArtifacts] = []
    for spec in workloads:
        print(f"Building real SMT instance: {spec.label}, h={height}")
        instance = build_instance(spec, height, hybrid_rounds=hybrid_rounds, balance_rounds=balance_rounds)
        print(
            f"  keys={instance.unique_keys}, active={len(instance.active_nodes)}, "
            f"m={instance.active_width}, sparse_max={max(instance.sparse_loads) if instance.sparse_loads else 0}"
        )
        instances.append(instance)
    return instances


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the paper-facing real-workload, real-backend SparseTreePIR showcase."
    )
    parser.add_argument("--workloads", default="all", help="Comma-separated workload labels or 'all'.")
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--backends", default="simplepir,piano", help="Comma-separated subset: simplepir,piano.")
    parser.add_argument("--query-samples", type=int, default=20)
    parser.add_argument("--seed", type=int, default=73000)
    parser.add_argument("--hybrid-rounds", type=int, default=60)
    parser.add_argument("--balance-rounds", type=int, default=20)
    parser.add_argument("--simplepir-timeout", type=int, default=900)
    parser.add_argument("--simplepir-drive", default="X")
    parser.add_argument("--layout-dir", type=Path, default=Path("examples/real_backend_showcase_simplepir_layouts"))
    parser.add_argument("--piano-repo", type=Path, default=Path(".tools/piano-pir-new"))
    parser.add_argument("--piano-timeout", type=int, default=300)
    parser.add_argument("--output", type=Path, default=Path("examples/real_backend_showcase_raw.csv"))
    parser.add_argument("--summary", type=Path, default=Path("examples/real_backend_showcase_summary.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/real_backend_showcase_note.md"))
    args = parser.parse_args()

    workloads = selected_workloads(args.workloads)
    backends = parse_backend_list(args.backends)
    instances = build_instances(
        workloads,
        height=args.height,
        hybrid_rounds=args.hybrid_rounds,
        balance_rounds=args.balance_rounds,
    )

    rows: List[Dict[str, object]] = []
    if "simplepir" in backends:
        print("Running SimplePIR full API backend...")
        rows.extend(
            run_simplepir_showcase(
                instances,
                query_samples=args.query_samples,
                seed=args.seed,
                layout_dir=args.layout_dir,
                simplepir_timeout=args.simplepir_timeout,
                simplepir_drive=args.simplepir_drive,
            )
        )
    if "piano" in backends:
        print("Running PIANO executable runner...")
        rows.extend(
            run_piano_showcase(
                instances,
                piano_repo=args.piano_repo,
                query_samples=args.query_samples,
                seed=args.seed,
                timeout=args.piano_timeout,
            )
        )

    summary_rows = summarize(rows)
    write_csv(args.output, rows)
    write_csv(args.summary, summary_rows)
    write_note(args.note, rows, summary_rows)
    print(f"raw={args.output}")
    print(f"summary={args.summary}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
