from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract a focused PBC-active vs SparseTreePIR comparison from the "
            "TreePIR-style comparison matrix. PBC-active is the SMT adaptation "
            "of TreePIR's generic-batch-code foil: three replicated active "
            "records, about 1.5m buckets, and bucket size about 2N/m."
        )
    )
    parser.add_argument(
        "--comparison-csv",
        type=Path,
        default=Path("examples/treepir_style_comparison_results.csv"),
        help="Input comparison matrix produced by build_treepir_style_comparison_table.py.",
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("examples/pbc_active_vs_sparsetreepir_results.csv"),
        help="Output focused comparison CSV.",
    )
    parser.add_argument(
        "--out-note",
        type=Path,
        default=Path("notes/pbc_active_vs_sparsetreepir_note.md"),
        help="Output markdown summary.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def f(row: Dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    return float(raw) if raw != "" else 0.0


def pct_reduction(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def fmt(value: float, digits: int = 1) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.{digits}f}"


def build_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[int, float, int], Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in rows:
        key = (int(float(row["height"])), float(row["sparsity"]), int(float(row["seed"])))
        grouped[key][row["scheme"]] = row

    out: List[Dict[str, Any]] = []
    for (height, sparsity, seed), schemes in sorted(grouped.items()):
        if "pbc_active" not in schemes or "profile_balanced" not in schemes:
            continue

        pbc = schemes["pbc_active"]
        ours = schemes["profile_balanced"]
        active_nodes = int(f(ours, "active_nodes"))
        exact_width = int(f(ours, "exact_width"))

        pbc_stored = int(f(pbc, "stored_records"))
        ours_stored = int(f(ours, "stored_records"))
        pbc_width = int(f(pbc, "width"))
        ours_width = int(f(ours, "width"))
        pbc_max = int(f(pbc, "max_bucket"))
        ours_max = int(f(ours, "max_bucket"))

        # A linear-server-work accounting: PBC-active searches replicated
        # batch-code buckets with three copies; SparseTreePIR searches each
        # active record once across color stores.
        pbc_sequential_records = pbc_stored
        ours_sequential_records = ours_stored

        out.append(
            {
                "height": height,
                "empty_pct": sparsity * 100.0,
                "seed": seed,
                "active_nodes": active_nodes,
                "exact_width_m": exact_width,
                "pbc_stored": pbc_stored,
                "ours_stored": ours_stored,
                "storage_reduction_pct": pct_reduction(ours_stored, pbc_stored),
                "pbc_width": pbc_width,
                "ours_width": ours_width,
                "width_reduction_pct": pct_reduction(ours_width, pbc_width),
                "pbc_max_bucket": pbc_max,
                "ours_max_bucket": ours_max,
                "max_bucket_reduction_pct": pct_reduction(ours_max, pbc_max),
                "pbc_sequential_records": pbc_sequential_records,
                "ours_sequential_records": ours_sequential_records,
                "sequential_record_reduction_pct": pct_reduction(
                    ours_sequential_records, pbc_sequential_records
                ),
            }
        )
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "height",
        "empty_pct",
        "seed",
        "active_nodes",
        "exact_width_m",
        "pbc_stored",
        "ours_stored",
        "storage_reduction_pct",
        "pbc_width",
        "ours_width",
        "width_reduction_pct",
        "pbc_max_bucket",
        "ours_max_bucket",
        "max_bucket_reduction_pct",
        "pbc_sequential_records",
        "ours_sequential_records",
        "sequential_record_reduction_pct",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_note(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    storage = [float(r["storage_reduction_pct"]) for r in rows]
    width = [float(r["width_reduction_pct"]) for r in rows]
    max_bucket = [float(r["max_bucket_reduction_pct"]) for r in rows]
    sequential = [float(r["sequential_record_reduction_pct"]) for r in rows]

    lines: List[str] = []
    lines.append("# PBC-active vs SparseTreePIR on SMT active proof records\n")
    lines.append(
        "This focused experiment compares the generic batch-code adaptation "
        "against the final active-interval organization on the same SMT active "
        "proof objects. PBC-active follows TreePIR's main generic-batch-code "
        "foil at the resource-model level: three replicated active records, "
        "about `1.5m` buckets, and a maximum bucket close to `2N/m`. "
        "SparseTreePIR stores each active proof record once, uses exact active "
        "width `m`, and balances the color stores with ActiveBalance.\n"
    )
    lines.append("| h | Empty | Active N | m | PBC stored | Ours stored | PBC width | Ours width | PBC max bucket | Ours max bucket |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            "| {h} | {empty:.3f}% | {active} | {m} | {pbc_s} | {ours_s} | {pbc_w} | {ours_w} | {pbc_b} | {ours_b} |".format(
                h=row["height"],
                empty=row["empty_pct"],
                active=fmt(float(row["active_nodes"]), 0),
                m=fmt(float(row["exact_width_m"]), 0),
                pbc_s=fmt(float(row["pbc_stored"]), 0),
                ours_s=fmt(float(row["ours_stored"]), 0),
                pbc_w=fmt(float(row["pbc_width"]), 0),
                ours_w=fmt(float(row["ours_width"]), 0),
                pbc_b=fmt(float(row["pbc_max_bucket"]), 0),
                ours_b=fmt(float(row["ours_max_bucket"]), 0),
            )
        )
    lines.append("")
    lines.append("## Aggregate reductions\n")
    lines.append(f"- Storage / linear sequential record work: {fmt(mean(storage))}% mean reduction.")
    lines.append(
        f"- Batch width: {fmt(min(width))}% to {fmt(max(width))}% reduction "
        f"(mean {fmt(mean(width))}%)."
    )
    lines.append(
        f"- Parallel bottleneck bucket: {fmt(min(max_bucket))}% to {fmt(max(max_bucket))}% reduction "
        f"(mean {fmt(mean(max_bucket))}%)."
    )
    lines.append(
        f"- Sequential searched records under a linear cost model: {fmt(mean(sequential))}% mean reduction."
    )
    lines.append("")
    lines.append("## Interpretation\n")
    lines.append(
        "This is not a full PBC implementation. It is the same type of "
        "resource-model PBC baseline used by TreePIR: the question is what "
        "happens if active SMT proof records are treated as an arbitrary batch "
        "rather than as a path-structured interval forest. The result is stable "
        "across the tested SMT settings: generic PBC pays replication, wider "
        "fixed-shape query width, and roughly twice the largest searched bucket. "
        "SparseTreePIR's advantage comes from using the SMT proof structure "
        "after active records have already been identified."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    rows = build_rows(read_csv(args.comparison_csv))
    write_csv(args.out_csv, rows)
    write_note(args.out_note, rows)
    print(f"Wrote {args.out_csv} ({len(rows)} rows)")
    print(f"Wrote {args.out_note}")


if __name__ == "__main__":
    main()
