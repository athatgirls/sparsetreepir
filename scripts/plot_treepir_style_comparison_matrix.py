from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ORDER = [
    "perfectized_treepir",
    "pbc_active",
    "flat_normal_pir_m",
    "pruned_treepir_h",
    "profile_balanced",
]

LABELS = {
    "perfectized_treepir": "Perfectized",
    "pbc_active": "PBC-active",
    "flat_normal_pir_m": "Flat PIR",
    "pruned_treepir_h": "Pruned-h",
    "profile_balanced": "Profile",
}

COLORS = {
    "perfectized_treepir": "#8a8f98",
    "pbc_active": "#b07aa1",
    "flat_normal_pir_m": "#6574a6",
    "pruned_treepir_h": "#d49a3a",
    "profile_balanced": "#2f7f73",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot a decomposed TreePIR-style comparison matrix."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("examples/treepir_style_comparison_results.csv"),
    )
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--sparsity", type=float, default=0.9995)
    parser.add_argument(
        "--output-pdf",
        type=Path,
        default=Path("figures/treepir_style_comparison_matrix.pdf"),
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=Path("figures/treepir_style_comparison_matrix.png"),
    )
    return parser.parse_args()


def read_rows(path: Path, height: int, sparsity: float) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = [
            row
            for row in csv.DictReader(fh)
            if int(row["height"]) == height
            and abs(float(row["sparsity"]) - sparsity) < 1e-12
        ]
    index = {row["scheme"]: row for row in rows}
    return [index[scheme] for scheme in ORDER if scheme in index]


def value(row: Dict[str, str], key: str) -> float | None:
    raw = row.get(key, "")
    if raw == "":
        return None
    return float(raw)


def annotate_bars(ax: plt.Axes, bars: Any, values: List[float], fmt: str = "{:.0f}") -> None:
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            fmt.format(val),
            ha="center",
            va="bottom",
            fontsize=7,
            rotation=0,
        )


def main() -> None:
    args = parse_args()
    rows = read_rows(args.input, args.height, args.sparsity)
    if not rows:
        raise SystemExit("No rows matched the requested setting.")

    labels = [LABELS[row["scheme"]] for row in rows]
    colors = [COLORS[row["scheme"]] for row in rows]
    x = np.arange(len(rows))

    fig, axes = plt.subplots(2, 2, figsize=(7.1, 4.5))
    fig.subplots_adjust(wspace=0.35, hspace=0.45)

    stored = [value(row, "stored_records") or 0 for row in rows]
    bars = axes[0, 0].bar(x, stored, color=colors, edgecolor="#263238", linewidth=0.5)
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_title("Private records")
    axes[0, 0].set_ylabel("records (log)")
    axes[0, 0].set_xticks(x)
    axes[0, 0].set_xticklabels(labels, rotation=18, ha="right")
    annotate_bars(axes[0, 0], bars, stored, "{:.0f}")

    widths = [value(row, "width") or 0 for row in rows]
    bars = axes[0, 1].bar(x, widths, color=colors, edgecolor="#263238", linewidth=0.5)
    axes[0, 1].set_title("Batch width")
    axes[0, 1].set_ylabel("PIR subqueries")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=18, ha="right")
    annotate_bars(axes[0, 1], bars, widths, "{:.0f}")

    bucket_rows = [row for row in rows if row["max_bucket"] != ""]
    bx = np.arange(len(bucket_rows))
    bucket_labels = [LABELS[row["scheme"]] for row in bucket_rows]
    bucket_colors = [COLORS[row["scheme"]] for row in bucket_rows]
    max_buckets = [value(row, "max_bucket") or 0 for row in bucket_rows]
    bars = axes[1, 0].bar(
        bx, max_buckets, color=bucket_colors, edgecolor="#263238", linewidth=0.5
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_title("Largest queried subdatabase")
    axes[1, 0].set_ylabel("records (log)")
    axes[1, 0].set_xticks(bx)
    axes[1, 0].set_xticklabels(bucket_labels, rotation=18, ha="right")
    annotate_bars(axes[1, 0], bars, max_buckets, "{:.0f}")

    api_rows = [row for row in rows if row["online_total_kb"] != ""]
    ax = np.arange(len(api_rows))
    api_labels = [LABELS[row["scheme"]] for row in api_rows]
    api_colors = [COLORS[row["scheme"]] for row in api_rows]
    online = [value(row, "online_total_kb") or 0 for row in api_rows]
    bars = axes[1, 1].bar(
        ax, online, color=api_colors, edgecolor="#263238", linewidth=0.5
    )
    axes[1, 1].set_title("Full SimplePIR online")
    axes[1, 1].set_ylabel("KB per proof")
    axes[1, 1].set_xticks(ax)
    axes[1, 1].set_xticklabels(api_labels, rotation=18, ha="right")
    annotate_bars(axes[1, 1], bars, online, "{:.1f}")

    fig.suptitle(
        f"TreePIR-style cost decomposition (h={args.height}, empty={args.sparsity*100:.3f}%)",
        fontsize=10,
        y=0.99,
    )
    for ax_i in axes.ravel():
        ax_i.grid(axis="y", linestyle=":", alpha=0.45)
        ax_i.spines["top"].set_visible(False)
        ax_i.spines["right"].set_visible(False)

    args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output_pdf, bbox_inches="tight")
    fig.savefig(args.output_png, dpi=240, bbox_inches="tight")
    print(f"Wrote {args.output_pdf}")
    print(f"Wrote {args.output_png}")


if __name__ == "__main__":
    main()
