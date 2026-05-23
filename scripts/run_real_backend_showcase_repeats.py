from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, Iterable, List, Sequence, Tuple


METRIC_COLUMNS = [
    "width_reduction",
    "max_bucket_reduction",
    "online_reduction",
    "query_reduction",
    "setup_reduction",
]


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("seed list cannot be empty")
    return values


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


def run_seed(args: argparse.Namespace, seed: int, seed_index: int) -> Path:
    raw_path = args.output_dir / f"real_backend_showcase_seed{seed_index}_raw.csv"
    summary_path = args.output_dir / f"real_backend_showcase_seed{seed_index}_summary.csv"
    note_path = args.note_dir / f"real_backend_showcase_seed{seed_index}_note.md"
    layout_dir = args.layout_dir / f"seed{seed_index}"
    cmd = [
        sys.executable,
        "scripts/run_real_backend_showcase.py",
        "--workloads",
        args.workloads,
        "--height",
        str(args.height),
        "--backends",
        args.backends,
        "--query-samples",
        str(args.query_samples),
        "--seed",
        str(seed),
        "--hybrid-rounds",
        str(args.hybrid_rounds),
        "--balance-rounds",
        str(args.balance_rounds),
        "--simplepir-timeout",
        str(args.simplepir_timeout),
        "--piano-timeout",
        str(args.piano_timeout),
        "--layout-dir",
        str(layout_dir),
        "--output",
        str(raw_path),
        "--summary",
        str(summary_path),
        "--note",
        str(note_path),
    ]
    if args.piano_repo:
        cmd.extend(["--piano-repo", args.piano_repo])
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    return summary_path


def maybe_float(raw: str) -> float | None:
    if raw == "":
        return None
    return float(raw)


def average(values: Iterable[float]) -> float:
    vals = list(values)
    return mean(vals) if vals else 0.0


def sample_stdev(values: Iterable[float]) -> float:
    vals = list(values)
    return stdev(vals) if len(vals) >= 2 else 0.0


def aggregate(seed_summaries: Sequence[Tuple[int, Path]]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    per_seed_rows: List[Dict[str, object]] = []
    for seed, path in seed_summaries:
        for row in read_csv(path):
            copied: Dict[str, object] = {"seed": seed, **row}
            per_seed_rows.append(copied)

    grouped: Dict[Tuple[str, str, int], List[Dict[str, object]]] = defaultdict(list)
    for row in per_seed_rows:
        grouped[(str(row["backend"]), str(row["dataset"]), int(row["height"]))].append(row)

    aggregate_rows: List[Dict[str, object]] = []
    for (backend, dataset, height), rows in sorted(grouped.items()):
        out: Dict[str, object] = {
            "backend": backend,
            "dataset": dataset,
            "height": height,
            "seeds": len(rows),
            "pbc_width": rows[0]["pbc_width"],
            "sparse_width": rows[0]["sparse_width"],
        }
        for column in METRIC_COLUMNS:
            values = [value for row in rows if (value := maybe_float(str(row.get(column, "")))) is not None]
            if values:
                out[f"{column}_mean"] = average(values)
                out[f"{column}_std"] = sample_stdev(values)
            else:
                out[f"{column}_mean"] = ""
                out[f"{column}_std"] = ""
        aggregate_rows.append(out)
    return per_seed_rows, aggregate_rows


def pct(value: object) -> str:
    if value == "":
        return "n/a"
    return f"{100.0 * float(value):.1f}%"


def write_note(path: Path, aggregate_rows: Sequence[Dict[str, object]], seeds: Sequence[int]) -> None:
    by_backend: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in aggregate_rows:
        by_backend[str(row["backend"])].append(row)

    lines = [
        "# Real Backend Showcase Repeated Runs",
        "",
        f"Seeds: {', '.join(str(seed) for seed in seeds)}",
        "",
        "This note aggregates repeated runs of the real-workload, executable-backend showcase. Means and sample standard deviations are computed over seed-level summary rows.",
        "",
        "## Backend Averages",
        "",
        "| Backend | Workloads | Online mean | Online std | Query mean | Query std | Setup mean | Setup std |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for backend, rows in sorted(by_backend.items()):
        online = [float(row["online_reduction_mean"]) for row in rows if row["online_reduction_mean"] != ""]
        online_std = [float(row["online_reduction_std"]) for row in rows if row["online_reduction_std"] != ""]
        query = [float(row["query_reduction_mean"]) for row in rows if row["query_reduction_mean"] != ""]
        query_std = [float(row["query_reduction_std"]) for row in rows if row["query_reduction_std"] != ""]
        setup = [float(row["setup_reduction_mean"]) for row in rows if row["setup_reduction_mean"] != ""]
        setup_std = [float(row["setup_reduction_std"]) for row in rows if row["setup_reduction_std"] != ""]
        lines.append(
            f"| {backend} | {len(rows)} | {pct(average(online))} | {pct(average(online_std))} | "
            f"{pct(average(query))} | {pct(average(query_std))} | "
            f"{pct(average(setup))} | {pct(average(setup_std))} |"
        )

    lines.extend(
        [
            "",
            "## Per-Workload Means",
            "",
            "| Backend | Dataset | h | Online mean | Online std | Query mean | Setup mean |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in aggregate_rows:
        lines.append(
            f"| {row['backend']} | {row['dataset']} | {row['height']} | "
            f"{pct(row['online_reduction_mean'])} | {pct(row['online_reduction_std'])} | "
            f"{pct(row['query_reduction_mean'])} | {pct(row['setup_reduction_mean'])} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and aggregate repeated real-backend showcase experiments.")
    parser.add_argument("--seeds", default="73000,83000,93000")
    parser.add_argument("--workloads", default="all")
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--backends", default="simplepir,piano")
    parser.add_argument("--query-samples", type=int, default=50)
    parser.add_argument("--hybrid-rounds", type=int, default=60)
    parser.add_argument("--balance-rounds", type=int, default=20)
    parser.add_argument("--simplepir-timeout", type=int, default=1200)
    parser.add_argument("--piano-timeout", type=int, default=300)
    parser.add_argument("--piano-repo", default=".tools/piano-pir-new")
    parser.add_argument("--layout-dir", type=Path, default=Path("examples/real_backend_showcase_repeats_layouts"))
    parser.add_argument("--output-dir", type=Path, default=Path("examples"))
    parser.add_argument("--note-dir", type=Path, default=Path("notes"))
    parser.add_argument("--combined-output", type=Path, default=Path("examples/real_backend_showcase_repeats_seed_rows.csv"))
    parser.add_argument("--aggregate-output", type=Path, default=Path("examples/real_backend_showcase_repeats_summary.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/real_backend_showcase_repeats_note.md"))
    parser.add_argument("--skip-runs", action="store_true", help="Aggregate existing per-seed summaries without running backends.")
    args = parser.parse_args()

    seeds = parse_int_list(args.seeds)
    seed_summaries: List[Tuple[int, Path]] = []
    for index, seed in enumerate(seeds, start=1):
        summary_path = args.output_dir / f"real_backend_showcase_seed{index}_summary.csv"
        if args.skip_runs:
            if not summary_path.exists():
                raise FileNotFoundError(summary_path)
        else:
            summary_path = run_seed(args, seed=seed, seed_index=index)
        seed_summaries.append((seed, summary_path))

    per_seed_rows, aggregate_rows = aggregate(seed_summaries)
    write_csv(args.combined_output, per_seed_rows)
    write_csv(args.aggregate_output, aggregate_rows)
    write_note(args.note, aggregate_rows, seeds)
    print(f"combined={args.combined_output}")
    print(f"aggregate={args.aggregate_output}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
