from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple


SCHEMES = ["flat_normal_pir_m", "pruned_treepir_h", "profile_balanced"]


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct_reduction(new_value: float, old_value: float) -> float:
    if old_value == 0:
        return 0.0
    return 100.0 * (1.0 - new_value / old_value)


def f(value: float) -> str:
    return f"{value:.2f}"


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_note(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile_flat = [float(row["profile_online_reduction_vs_flat_pct"]) for row in rows]
    profile_pruned = [float(row["profile_online_reduction_vs_pruned_pct"]) for row in rows]
    width_pruned = [float(row["profile_width_reduction_vs_pruned_pct"]) for row in rows]
    query_flat = [float(row["profile_client_query_reduction_vs_flat_pct"]) for row in rows]
    query_pruned = [float(row["profile_client_query_reduction_vs_pruned_pct"]) for row in rows]

    lines = [
        "# Full SimplePIR Comparative Summary",
        "",
        "This note derives comparison-oriented metrics from `examples/simplepir_full_backend_results.csv`.",
        "",
        "## Aggregate takeaways",
        "",
        f"- Profile-balanced online communication reduction vs flat normal PIR: {min(profile_flat):.1f}% to {max(profile_flat):.1f}% (avg {mean(profile_flat):.1f}%).",
        f"- Profile-balanced width reduction vs Pruned-TreePIR-h: {min(width_pruned):.1f}% to {max(width_pruned):.1f}% (avg {mean(width_pruned):.1f}%).",
        f"- Profile-balanced client query time reduction vs flat normal PIR: {min(query_flat):.1f}% to {max(query_flat):.1f}% (avg {mean(query_flat):.1f}%).",
        f"- Profile-balanced client query time reduction vs Pruned-TreePIR-h: {min(query_pruned):.1f}% to {max(query_pruned):.1f}% (avg {mean(query_pruned):.1f}%).",
        f"- Profile-balanced online communication change vs Pruned-TreePIR-h: {min(profile_pruned):.1f}% to {max(profile_pruned):.1f}% (avg {mean(profile_pruned):.1f}%). Negative values are SimplePIR tiering cases where Pruned has lower total bytes.",
        "",
        "## Per-setting comparison",
        "",
        "| h | Empty | m/h | Profile vs flat online | Profile vs pruned online | Profile vs pruned width | Profile vs flat client query | Profile vs pruned client query |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['height']} | {float(row['empty_ratio_pct']):.3f}% | "
            f"{row['profile_width']}/{row['pruned_width']} | "
            f"{float(row['profile_online_reduction_vs_flat_pct']):.1f}% | "
            f"{float(row['profile_online_reduction_vs_pruned_pct']):.1f}% | "
            f"{float(row['profile_width_reduction_vs_pruned_pct']):.1f}% | "
            f"{float(row['profile_client_query_reduction_vs_flat_pct']):.1f}% | "
            f"{float(row['profile_client_query_reduction_vs_pruned_pct']):.1f}% |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize full SimplePIR backend comparisons.")
    parser.add_argument("--input", type=Path, default=Path("examples/simplepir_full_backend_results.csv"))
    parser.add_argument("--csv", type=Path, default=Path("examples/simplepir_comparison_summary.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/simplepir_comparison_summary_note.md"))
    args = parser.parse_args()

    grouped: Dict[Tuple[int, float], Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in read_rows(args.input):
        grouped[(int(row["height"]), float(row["sparsity"]))][row["scheme"]] = row

    summary: List[Dict[str, object]] = []
    for (height, sparsity), schemes in sorted(grouped.items()):
        missing = [scheme for scheme in SCHEMES if scheme not in schemes]
        if missing:
            raise RuntimeError(f"missing schemes for h={height}, sparsity={sparsity}: {missing}")
        flat = schemes["flat_normal_pir_m"]
        pruned = schemes["pruned_treepir_h"]
        profile = schemes["profile_balanced"]

        flat_online = float(flat["online_total_kb"])
        pruned_online = float(pruned["online_total_kb"])
        profile_online = float(profile["online_total_kb"])
        flat_query = float(flat["client_query_ms"])
        pruned_query = float(pruned["client_query_ms"])
        profile_query = float(profile["client_query_ms"])
        pruned_width = int(pruned["width"])
        profile_width = int(profile["width"])

        summary.append(
            {
                "height": height,
                "sparsity": sparsity,
                "empty_ratio_pct": sparsity * 100.0,
                "occupied": int(profile["occupied"]),
                "active_nodes": int(profile["active_nodes"]),
                "profile_width": profile_width,
                "pruned_width": pruned_width,
                "flat_online_kb": flat_online,
                "pruned_online_kb": pruned_online,
                "profile_online_kb": profile_online,
                "profile_online_reduction_vs_flat_pct": pct_reduction(profile_online, flat_online),
                "profile_online_reduction_vs_pruned_pct": pct_reduction(profile_online, pruned_online),
                "profile_width_reduction_vs_pruned_pct": pct_reduction(profile_width, pruned_width),
                "flat_client_query_ms": flat_query,
                "pruned_client_query_ms": pruned_query,
                "profile_client_query_ms": profile_query,
                "profile_client_query_reduction_vs_flat_pct": pct_reduction(profile_query, flat_query),
                "profile_client_query_reduction_vs_pruned_pct": pct_reduction(profile_query, pruned_query),
            }
        )

    write_csv(args.csv, summary)
    write_note(args.note, summary)
    print(f"csv={args.csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
