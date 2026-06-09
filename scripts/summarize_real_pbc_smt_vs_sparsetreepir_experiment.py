from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a PBC-SMT vs SparseTreePIR resource comparison for real "
            "rollup-style SMT workloads from the existing workload summary."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("examples/real_rollup_smt_workload_summary.csv"),
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("examples/real_rollup_pbc_smt_vs_sparsetreepir_resource_summary.csv"),
    )
    parser.add_argument(
        "--out-note",
        type=Path,
        default=Path("notes/real_rollup_pbc_smt_vs_sparsetreepir_experiment_note.md"),
    )
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct_reduction(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def fmt(value: float, digits: int = 1) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.{digits}f}"


def build_rows(rows: List[Dict[str, str]]) -> List[Dict[str, float | str]]:
    out: List[Dict[str, float | str]] = []
    for row in rows:
        workload = row["workload"]
        height = int(float(row["height"]))
        keys = int(float(row["keys"]))
        active_nodes = int(float(row["active_nodes"]))
        active_width = int(float(row["m"]))
        ours_max = int(float(row["profile_max_bucket"]))

        pbc_width = max(1, math.ceil(1.5 * active_width))
        pbc_stored = 3 * active_nodes
        pbc_max = math.ceil(pbc_stored / pbc_width)

        out.append(
            {
                "workload": workload,
                "height": height,
                "keys": keys,
                "active_nodes": active_nodes,
                "active_width_m": active_width,
                "pbc_width": pbc_width,
                "ours_width": active_width,
                "width_reduction_pct": pct_reduction(active_width, pbc_width),
                "pbc_stored_records": pbc_stored,
                "ours_stored_records": active_nodes,
                "storage_reduction_pct": pct_reduction(active_nodes, pbc_stored),
                "pbc_max_bucket": pbc_max,
                "ours_max_bucket": ours_max,
                "max_bucket_reduction_pct": pct_reduction(ours_max, pbc_max),
                "dummy_fraction_pct": float(row["dummy_fraction_percent"]),
            }
        )
    return out


def write_csv(path: Path, rows: List[Dict[str, float | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_note(path: Path, rows: List[Dict[str, float | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width_red = [float(row["width_reduction_pct"]) for row in rows]
    max_red = [float(row["max_bucket_reduction_pct"]) for row in rows]
    lines: List[str] = []
    lines.append("# Real rollup workloads: PBC-SMT vs SparseTreePIR\n")
    lines.append(
        "This experiment applies the same PBC-SMT resource model to real "
        "rollup-style SMT workloads. It is not a full PBC implementation; it "
        "uses the standard generic batch-code accounting: three replicated "
        "copies of each active proof record and about `1.5m` buckets. "
        "SparseTreePIR uses the active width `m`, stores each active proof "
        "record once, and uses the measured ActiveBalance bucket profile.\n"
    )
    lines.append(
        "| Workload | h | Keys | Active N | m | PBC-SMT width | Ours width | PBC-SMT stored | Ours stored | PBC-SMT max bucket | Ours max bucket |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            "| {name} | {h} | {keys} | {active} | {m} | {pbc_w} | {ours_w} | {pbc_s} | {ours_s} | {pbc_b} | {ours_b} |".format(
                name=row["workload"],
                h=int(row["height"]),
                keys=fmt(float(row["keys"]), 0),
                active=fmt(float(row["active_nodes"]), 0),
                m=fmt(float(row["active_width_m"]), 0),
                pbc_w=fmt(float(row["pbc_width"]), 0),
                ours_w=fmt(float(row["ours_width"]), 0),
                pbc_s=fmt(float(row["pbc_stored_records"]), 0),
                ours_s=fmt(float(row["ours_stored_records"]), 0),
                pbc_b=fmt(float(row["pbc_max_bucket"]), 0),
                ours_b=fmt(float(row["ours_max_bucket"]), 0),
            )
        )
    lines.append("")
    lines.append("- Mean storage reduction: 66.7%.")
    lines.append(f"- Mean width reduction: {mean(width_red):.1f}%.")
    lines.append(f"- Mean largest-bucket reduction: {mean(max_red):.1f}%.")
    lines.append(
        "- The h=128 and h=256 rows have the same active skeleton for these "
        "hashed key workloads; the verifier proof height changes, but the "
        "private active retrieval object is governed by the occupied-key "
        "skeleton."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    rows = build_rows(read_rows(args.input))
    write_csv(args.out_csv, rows)
    write_note(args.out_note, rows)
    print(f"csv={args.out_csv} rows={len(rows)}")
    print(f"note={args.out_note}")


if __name__ == "__main__":
    main()
