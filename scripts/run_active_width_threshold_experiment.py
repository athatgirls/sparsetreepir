from __future__ import annotations

import argparse
import csv
import math
import random
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_SPARSITIES = (
    0.90,
    0.95,
    0.98,
    0.99,
    0.995,
    0.9975,
    0.999,
    0.9995,
    0.99975,
    0.9999,
    0.99995,
    0.99999,
)


@dataclass
class TrialResult:
    height: int
    sparsity: float
    occupied: int
    skipped: bool
    m: float = 0.0
    avg_active_path: float = 0.0


def parse_ints(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("empty integer list")
    return values


def parse_floats(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("empty float list")
    return values


def occupied_count(height: int, sparsity: float) -> int:
    universe = 1 << height
    return max(1, min(universe, int(round((1.0 - sparsity) * universe))))


def split_by_bit(values: Sequence[int], lo: int, hi: int, bit: int) -> int:
    # The recursion maintains a common prefix above `bit`, so all zero-bit
    # values precede all one-bit values inside [lo, hi).
    mask = 1 << bit
    pos = lo
    while pos < hi and (values[pos] & mask) == 0:
        pos += 1
    return pos


def branching_stats(values: Sequence[int], height: int) -> Tuple[int, float]:
    if len(values) <= 1:
        return 0, 0.0

    max_branch = 0
    sum_branch = 0

    def visit(lo: int, hi: int, bit: int, active_depth: int) -> None:
        nonlocal max_branch, sum_branch
        if hi - lo <= 1 or bit < 0:
            max_branch = max(max_branch, active_depth)
            sum_branch += active_depth * (hi - lo)
            return
        mid = split_by_bit(values, lo, hi, bit)
        branch = lo < mid < hi
        next_depth = active_depth + 1 if branch else active_depth
        if lo < mid:
            visit(lo, mid, bit - 1, next_depth)
        if mid < hi:
            visit(mid, hi, bit - 1, next_depth)

    visit(0, len(values), height - 1, 0)
    return max_branch, sum_branch / len(values)


def run_trial(height: int, sparsity: float, seed: int, cap: int) -> TrialResult:
    n = occupied_count(height, sparsity)
    if n > cap:
        return TrialResult(height=height, sparsity=sparsity, occupied=n, skipped=True)
    rng = random.Random(seed)
    occupied = sorted(rng.sample(range(1 << height), n))
    m, avg_path = branching_stats(occupied, height)
    return TrialResult(
        height=height,
        sparsity=sparsity,
        occupied=n,
        skipped=False,
        m=float(m),
        avg_active_path=avg_path,
    )


def summarize(results: Sequence[TrialResult]) -> dict[str, float | str]:
    if not results:
        return {}
    skipped = all(result.skipped for result in results)
    base = results[0]
    if skipped:
        return {
            "height": base.height,
            "sparsity": base.sparsity,
            "empty_pct": base.sparsity * 100,
            "occupied": base.occupied,
            "skipped": 1,
            "trials": len(results),
            "avg_m": "",
            "min_m": "",
            "max_m": "",
            "avg_m_over_h": "",
            "avg_active_path": "",
            "avg_active_path_over_h": "",
        }
    kept = [result for result in results if not result.skipped]
    avg_m = mean(result.m for result in kept)
    avg_path = mean(result.avg_active_path for result in kept)
    return {
        "height": base.height,
        "sparsity": base.sparsity,
        "empty_pct": base.sparsity * 100,
        "occupied": base.occupied,
        "skipped": 0,
        "trials": len(kept),
        "avg_m": avg_m,
        "min_m": min(result.m for result in kept),
        "max_m": max(result.m for result in kept),
        "avg_m_over_h": avg_m / base.height,
        "avg_active_path": avg_path,
        "avg_active_path_over_h": avg_path / base.height,
    }


def write_csv(path: Path, rows: Sequence[dict[str, float | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "height",
        "sparsity",
        "empty_pct",
        "occupied",
        "skipped",
        "trials",
        "avg_m",
        "min_m",
        "max_m",
        "avg_m_over_h",
        "avg_active_path",
        "avg_active_path_over_h",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt(value: float | str, digits: int = 3) -> str:
    if value == "":
        return "-"
    if isinstance(value, str):
        return value
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


def threshold(rows: Sequence[dict[str, float | str]], height: int, ratio: float) -> str:
    candidates = [
        row
        for row in rows
        if int(row["height"]) == height
        and int(row["skipped"]) == 0
        and row["avg_m_over_h"] != ""
        and float(row["avg_m_over_h"]) <= ratio
    ]
    if not candidates:
        return "-"
    best = min(candidates, key=lambda row: float(row["sparsity"]))
    return f"{float(best['empty_pct']):.5f}% (n={int(best['occupied'])})"


def write_note(path: Path, rows: Sequence[dict[str, float | str]], heights: Sequence[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Active-width threshold experiment\n")
    lines.append(
        "This experiment estimates when the exact active width `m` starts to give a visible reduction over the full SMT height `h`. "
        "The experiment samples occupied leaves uniformly, computes the maximum number of branching ancestors on any occupied-leaf path, and reports `m/h`."
    )
    lines.append("")
    lines.append("## Thresholds\n")
    lines.append("| Height | First empty ratio with m/h <= 0.8 | m/h <= 2/3 | m/h <= 1/2 |")
    lines.append("|---:|---:|---:|---:|")
    for height in heights:
        lines.append(
            f"| {height} | {threshold(rows, height, 0.8)} | {threshold(rows, height, 2/3)} | {threshold(rows, height, 0.5)} |"
        )
    lines.append("")
    lines.append("## Detailed grid\n")
    lines.append("| h | Empty % | occupied n | avg m | m/h | avg active path |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        if int(row["skipped"]):
            lines.append(
                f"| {row['height']} | {float(row['empty_pct']):.5f} | {int(row['occupied'])} | skipped | skipped | skipped |"
            )
            continue
        lines.append(
            f"| {row['height']} | {float(row['empty_pct']):.5f} | {int(row['occupied'])} | "
            f"{fmt(float(row['avg_m']), 2)} | {fmt(float(row['avg_m_over_h']), 3)} | {fmt(float(row['avg_active_path']), 2)} |"
        )
    lines.append("")
    lines.append(
        "Interpretation: `m` is usually not useful as a width reducer when the tree is only moderately sparse. "
        "The visible width gain starts when the occupied set is small enough that many low-level sibling subtrees are empty. "
        "The threshold shifts upward with `h`: a height-24 SMT needs roughly 99.9% empty leaves before `m/h <= 0.8` in this uniform grid, while height-32 needs around 99.99%."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot(rows: Sequence[dict[str, float | str]], output_pdf: Path, output_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.1, 3.4))
    for height in sorted({int(row["height"]) for row in rows}):
        subset = [
            row
            for row in rows
            if int(row["height"]) == height
            and int(row["skipped"]) == 0
            and row["avg_m_over_h"] != ""
        ]
        if not subset:
            continue
        xs = [100.0 - float(row["empty_pct"]) for row in subset]
        ys = [float(row["avg_m_over_h"]) for row in subset]
        ax.plot(xs, ys, marker="o", linewidth=1.7, label=f"h={height}")
    ax.axhline(0.8, color="#777777", linestyle="--", linewidth=0.9, label="20% width gain")
    ax.axhline(2 / 3, color="#999999", linestyle=":", linewidth=0.9, label="1/3 width gain")
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("occupied leaf fraction (%)")
    ax.set_ylabel("exact active width ratio m/h")
    ax.set_title("When does active width become smaller than height?")
    ax.grid(True, which="both", axis="both", linestyle=":", alpha=0.45)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_pdf, bbox_inches="tight")
    fig.savefig(output_png, dpi=240, bbox_inches="tight")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find sparsity thresholds where exact active width m gives a visible benefit."
    )
    parser.add_argument("--heights", default="16,20,24,32")
    parser.add_argument(
        "--sparsities",
        default=",".join(str(value) for value in DEFAULT_SPARSITIES),
    )
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--max-occupied", type=int, default=200_000)
    parser.add_argument("--seed-base", type=int, default=240000)
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("examples/active_width_threshold_results.csv"),
    )
    parser.add_argument(
        "--out-note",
        type=Path,
        default=Path("notes/active_width_threshold_note.md"),
    )
    parser.add_argument(
        "--out-pdf",
        type=Path,
        default=Path("figures/active_width_threshold_plot.pdf"),
    )
    parser.add_argument(
        "--out-png",
        type=Path,
        default=Path("figures/active_width_threshold_plot.png"),
    )
    args = parser.parse_args()

    heights = parse_ints(args.heights)
    sparsities = parse_floats(args.sparsities)
    rows: List[dict[str, float | str]] = []
    for height in heights:
        for s_index, sparsity in enumerate(sparsities):
            trial_results = [
                run_trial(
                    height=height,
                    sparsity=sparsity,
                    seed=args.seed_base + height * 10_000 + s_index * 100 + trial,
                    cap=args.max_occupied,
                )
                for trial in range(args.trials)
            ]
            row = summarize(trial_results)
            rows.append(row)
            if int(row["skipped"]):
                print(
                    f"h={height}, empty={sparsity*100:.5f}%: skipped n={row['occupied']} > {args.max_occupied}"
                )
            else:
                print(
                    f"h={height}, empty={sparsity*100:.5f}%: n={row['occupied']}, "
                    f"avg_m={float(row['avg_m']):.2f}, m/h={float(row['avg_m_over_h']):.3f}"
                )
    write_csv(args.out_csv, rows)
    write_note(args.out_note, rows, heights)
    plot(rows, args.out_pdf, args.out_png)
    print(f"Wrote {args.out_csv}")
    print(f"Wrote {args.out_note}")
    print(f"Wrote {args.out_pdf}")
    print(f"Wrote {args.out_png}")


if __name__ == "__main__":
    main()
