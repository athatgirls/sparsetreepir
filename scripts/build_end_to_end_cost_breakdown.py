from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, Iterable, List, Sequence, Tuple


SCHEME_TO_LAYOUT = {
    "PBC-SMT": "pbc_smt_active",
    "SparseTreePIR": "sparsetreepir_activebalance",
}

METRICS = [
    "setup_ms",
    "client_query_ms",
    "server_total_ms",
    "server_parallel_ms",
    "client_decode_ms",
    "offline_kb",
    "online_upload_kb",
    "online_download_kb",
    "online_total_kb",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def f(raw: object, default: float = 0.0) -> float:
    text = str(raw)
    if text == "":
        return default
    return float(text)


def maybe_mean(values: Iterable[float]) -> float | str:
    vals = list(values)
    return mean(vals) if vals else ""


def maybe_stdev(values: Iterable[float]) -> float | str:
    vals = list(values)
    return stdev(vals) if len(vals) >= 2 else (0.0 if vals else "")


def ratio_gain(baseline: float, improved: float) -> float | str:
    if baseline <= 0:
        return ""
    return baseline / improved if improved > 0 else ""


def reduction(baseline: float, improved: float) -> float | str:
    if baseline <= 0:
        return ""
    return 1.0 - improved / baseline


def load_raw_rows(raw_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in sorted(raw_dir.glob("real_backend_showcase_seed*_raw.csv")):
        seed = path.stem.split("_seed", 1)[1].split("_", 1)[0]
        for row in read_csv(path):
            copied = dict(row)
            copied["seed_index"] = seed
            rows.append(copied)
    if not rows:
        raise FileNotFoundError(f"no seed raw CSVs found under {raw_dir}")
    return rows


def aggregate_scheme_rows(raw_rows: Sequence[Dict[str, str]]) -> Dict[Tuple[str, str, int, str], Dict[str, object]]:
    grouped: Dict[Tuple[str, str, int, str], List[Dict[str, str]]] = defaultdict(list)
    for row in raw_rows:
        grouped[(row["backend"], row["dataset"], int(row["height"]), row["scheme"])].append(row)

    out: Dict[Tuple[str, str, int, str], Dict[str, object]] = {}
    for key, rows in sorted(grouped.items()):
        backend, dataset, height, scheme = key
        query_samples = sorted({int(float(row.get("query_samples", 0))) for row in rows})
        completed = [int(float(row.get("completed_queries", 0))) for row in rows]
        result: Dict[str, object] = {
            "backend": backend,
            "dataset": dataset,
            "height": height,
            "scheme": scheme,
            "seeds": len({row["seed_index"] for row in rows}),
            "query_samples_per_seed": ",".join(str(value) for value in query_samples),
            "completed_queries_mean": maybe_mean(completed),
        }
        for metric in METRICS:
            values = [f(row.get(metric, "")) for row in rows if row.get(metric, "") != ""]
            result[f"{metric}_mean"] = maybe_mean(values)
            result[f"{metric}_std"] = maybe_stdev(values)
        result["backend_online_latency_ms_mean"] = (
            f(result["client_query_ms_mean"])
            + f(result["server_total_ms_mean"])
            + f(result["client_decode_ms_mean"])
        )
        result["backend_online_latency_ms_std_sum"] = (
            f(result["client_query_ms_std"])
            + f(result["server_total_ms_std"])
            + f(result["client_decode_ms_std"])
        )
        out[key] = result
    return out


def index_layouts(layout_rows: Sequence[Dict[str, str]]) -> Dict[Tuple[str, int, str], Dict[str, str]]:
    indexed: Dict[Tuple[str, int, str], Dict[str, str]] = {}
    for row in layout_rows:
        indexed[(row["dataset"], int(row["height"]), row["scheme"])] = row
    return indexed


def build_breakdown_rows(
    scheme_rows: Dict[Tuple[str, str, int, str], Dict[str, object]],
    layouts: Dict[Tuple[str, int, str], Dict[str, str]],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for (backend, dataset, height, scheme), metrics in sorted(scheme_rows.items()):
        layout = layouts.get((dataset, height, SCHEME_TO_LAYOUT.get(scheme, "")), {})
        instance = layouts.get((dataset, height, "sparsetreepir_activebalance"), layout)
        row: Dict[str, object] = {
            **metrics,
            "dataset_kind": instance.get("dataset_kind", ""),
            "input_records": instance.get("input_records", ""),
            "unique_keys": instance.get("unique_keys", ""),
            "active_records": instance.get("active_records", ""),
            "active_width_m": instance.get("active_width_m", ""),
            "width": layout.get("width", metrics.get("width", "")),
            "stored_records": layout.get("stored_records", ""),
            "max_bucket": layout.get("max_bucket", ""),
            "metadata_kb": instance.get("metadata_kb", ""),
            "digest_payload_kb": instance.get("digest_payload_kb", ""),
            "activebalance_profile_ms": instance.get("profile_runtime_ms", ""),
            "suite_instance_runtime_ms": "",
            "setup_accounting_note": (
                "backend setup/query/answer measured by backend runner; "
                "activebalance_profile_ms is SparseTreePIR layout refinement time from the structural suite"
            ),
        }
        row["sparse_profile_plus_backend_setup_ms_mean"] = (
            f(row["activebalance_profile_ms"]) + f(metrics["setup_ms_mean"])
            if scheme == "SparseTreePIR"
            else ""
        )
        rows.append(row)
    return rows


def build_paired_rows(breakdown_rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str, int], Dict[str, Dict[str, object]]] = defaultdict(dict)
    for row in breakdown_rows:
        grouped[(str(row["backend"]), str(row["dataset"]), int(row["height"]))][str(row["scheme"])] = row

    paired: List[Dict[str, object]] = []
    for (backend, dataset, height), schemes in sorted(grouped.items()):
        if "PBC-SMT" not in schemes or "SparseTreePIR" not in schemes:
            continue
        pbc = schemes["PBC-SMT"]
        sparse = schemes["SparseTreePIR"]
        pbc_online_ms = f(pbc["backend_online_latency_ms_mean"])
        sparse_online_ms = f(sparse["backend_online_latency_ms_mean"])
        pbc_online_kb = f(pbc["online_total_kb_mean"])
        sparse_online_kb = f(sparse["online_total_kb_mean"])
        pbc_setup_ms = f(pbc["setup_ms_mean"])
        sparse_setup_ms = f(sparse["setup_ms_mean"])
        paired.append(
            {
                "backend": backend,
                "dataset": dataset,
                "height": height,
                "seeds": sparse["seeds"],
                "query_samples_per_seed": sparse["query_samples_per_seed"],
                "active_records": sparse["active_records"],
                "metadata_kb": sparse["metadata_kb"],
                "digest_payload_kb": sparse["digest_payload_kb"],
                "activebalance_profile_ms": sparse["activebalance_profile_ms"],
                "pbc_width": pbc["width"],
                "sparse_width": sparse["width"],
                "width_gain": ratio_gain(f(pbc["width"]), f(sparse["width"])),
                "pbc_stored_records": pbc["stored_records"],
                "sparse_stored_records": sparse["stored_records"],
                "stored_record_gain": ratio_gain(f(pbc["stored_records"]), f(sparse["stored_records"])),
                "pbc_max_bucket": pbc["max_bucket"],
                "sparse_max_bucket": sparse["max_bucket"],
                "max_bucket_gain": ratio_gain(f(pbc["max_bucket"]), f(sparse["max_bucket"])),
                "pbc_backend_setup_ms": pbc_setup_ms,
                "sparse_backend_setup_ms": sparse_setup_ms,
                "backend_setup_reduction": reduction(pbc_setup_ms, sparse_setup_ms),
                "sparse_profile_plus_backend_setup_ms": sparse["sparse_profile_plus_backend_setup_ms_mean"],
                "pbc_backend_online_latency_ms": pbc_online_ms,
                "sparse_backend_online_latency_ms": sparse_online_ms,
                "backend_online_latency_reduction": reduction(pbc_online_ms, sparse_online_ms),
                "pbc_online_kb": pbc_online_kb,
                "sparse_online_kb": sparse_online_kb,
                "online_kb_reduction": reduction(pbc_online_kb, sparse_online_kb),
                "pbc_upload_kb": pbc["online_upload_kb_mean"],
                "sparse_upload_kb": sparse["online_upload_kb_mean"],
                "pbc_download_kb": pbc["online_download_kb_mean"],
                "sparse_download_kb": sparse["online_download_kb_mean"],
            }
        )
    return paired


def avg_number(rows: Sequence[Dict[str, object]], key: str) -> float:
    values = [f(row[key]) for row in rows if str(row.get(key, "")) != ""]
    return mean(values) if values else 0.0


def fmt_ms(value: object) -> str:
    if value == "":
        return "n/a"
    return f"{float(value):.2f}"


def fmt_kb(value: object) -> str:
    if value == "":
        return "n/a"
    return f"{float(value):.2f}"


def fmt_gain(value: object) -> str:
    if value == "":
        return "n/a"
    return f"{float(value):.2f}x"


def fmt_pct(value: object) -> str:
    if value == "":
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def write_note(path: Path, paired_rows: Sequence[Dict[str, object]], breakdown_csv: Path, paired_csv: Path) -> None:
    by_backend: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in paired_rows:
        by_backend[str(row["backend"])].append(row)

    lines = [
        "# End-to-End Cost Breakdown",
        "",
        "This note joins the current WSL repeated backend run with the current WSL structural/layout suite. It is an accounting table, not a new PIR primitive result.",
        "",
        f"Scheme-level CSV: `{breakdown_csv}`",
        f"Paired comparison CSV: `{paired_csv}`",
        "",
        "## Backend Averages",
        "",
        "| Backend | Workloads | Setup reduction | Online latency reduction | Online KB reduction | Width gain | Stored-record gain | Max-bucket gain |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for backend, rows in sorted(by_backend.items()):
        lines.append(
            f"| {backend} | {len(rows)} | "
            f"{fmt_pct(avg_number(rows, 'backend_setup_reduction'))} | "
            f"{fmt_pct(avg_number(rows, 'backend_online_latency_reduction'))} | "
            f"{fmt_pct(avg_number(rows, 'online_kb_reduction'))} | "
            f"{fmt_gain(avg_number(rows, 'width_gain'))} | "
            f"{fmt_gain(avg_number(rows, 'stored_record_gain'))} | "
            f"{fmt_gain(avg_number(rows, 'max_bucket_gain'))} |"
        )

    lines.extend(
        [
            "",
            "## Per-Workload Paired Rows",
            "",
            "| Backend | Dataset | m PBC->Sparse | Metadata KB | ActiveBalance ms | Setup ms PBC->Sparse | Online ms PBC->Sparse | Online KB PBC->Sparse |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in paired_rows:
        lines.append(
            f"| {row['backend']} | {row['dataset']} | "
            f"{row['pbc_width']}->{row['sparse_width']} | "
            f"{fmt_kb(row['metadata_kb'])} | "
            f"{fmt_ms(row['activebalance_profile_ms'])} | "
            f"{fmt_ms(row['pbc_backend_setup_ms'])}->{fmt_ms(row['sparse_backend_setup_ms'])} | "
            f"{fmt_ms(row['pbc_backend_online_latency_ms'])}->{fmt_ms(row['sparse_backend_online_latency_ms'])} | "
            f"{fmt_kb(row['pbc_online_kb'])}->{fmt_kb(row['sparse_online_kb'])} |"
        )

    lines.extend(
        [
            "",
            "## Scope Notes",
            "",
            "- Backend setup/query/answer/recovery and communication are measured by the executable backend runners.",
            "- `activebalance_profile_ms` is the SparseTreePIR layout-refinement cost from the structural suite; `suite_instance_runtime_ms` is intentionally not folded into the gain ratio because the suite builds multiple comparison layouts for reporting.",
            "- PIANO answer-time counters are often zero or quantized on these small bucket vectors, so online latency for PIANO should be read mainly as query-side executable-runner evidence plus communication/setup accounting.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an end-to-end cost breakdown from SparseTreePIR experiment CSVs.")
    parser.add_argument("--raw-dir", type=Path, default=Path("examples/wsl_current_final"))
    parser.add_argument("--layouts-csv", type=Path, default=Path("examples/wsl_current_final/real_smt_final_suite_layouts.csv"))
    parser.add_argument("--breakdown-csv", type=Path, default=Path("examples/wsl_current_final/end_to_end_cost_breakdown.csv"))
    parser.add_argument("--paired-csv", type=Path, default=Path("examples/wsl_current_final/end_to_end_paired_comparison.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/wsl_current_final/end_to_end_cost_breakdown_note.md"))
    args = parser.parse_args()

    raw_rows = load_raw_rows(args.raw_dir)
    scheme_rows = aggregate_scheme_rows(raw_rows)
    layouts = index_layouts(read_csv(args.layouts_csv))
    breakdown_rows = build_breakdown_rows(scheme_rows, layouts)
    paired_rows = build_paired_rows(breakdown_rows)

    write_csv(args.breakdown_csv, breakdown_rows)
    write_csv(args.paired_csv, paired_rows)
    write_note(args.note, paired_rows, args.breakdown_csv, args.paired_csv)

    print(f"breakdown={args.breakdown_csv}")
    print(f"paired={args.paired_csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
