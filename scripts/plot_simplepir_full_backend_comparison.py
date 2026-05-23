from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCHEME_ORDER = ["flat_normal_pir_m", "pruned_treepir_h", "profile_balanced"]
SCHEME_LABELS = {
    "flat_normal_pir_m": "Flat normal PIR",
    "pruned_treepir_h": "Pruned-TreePIR-h",
    "profile_balanced": "Profile-balanced",
}
SCHEME_COLORS = {
    "flat_normal_pir_m": "#8c8c8c",
    "pruned_treepir_h": "#d98c2b",
    "profile_balanced": "#2f7ebc",
}


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot the full SimplePIR backend comparison.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("examples/simplepir_full_backend_results.csv"),
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("figures/simplepir_full_backend_comparison.pdf"),
    )
    parser.add_argument(
        "--png",
        type=Path,
        default=Path("figures/simplepir_full_backend_comparison.png"),
    )
    args = parser.parse_args()

    rows = read_rows(args.csv)
    heights = sorted({int(row["height"]) for row in rows})
    values = {
        scheme: [
            float(
                next(
                    row["online_total_kb"]
                    for row in rows
                    if int(row["height"]) == height and row["scheme"] == scheme
                )
            )
            for height in heights
        ]
        for scheme in SCHEME_ORDER
    }
    widths = {
        scheme: [
            int(
                next(
                    row["width"]
                    for row in rows
                    if int(row["height"]) == height and row["scheme"] == scheme
                )
            )
            for height in heights
        ]
        for scheme in SCHEME_ORDER
    }

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8,
            "axes.titlesize": 8,
            "axes.labelsize": 8,
            "legend.fontsize": 7,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(3.45, 2.35))
    x = np.arange(len(heights))
    bar_width = 0.24
    offsets = [-bar_width, 0.0, bar_width]

    for offset, scheme in zip(offsets, SCHEME_ORDER):
        bars = ax.bar(
            x + offset,
            values[scheme],
            width=bar_width,
            color=SCHEME_COLORS[scheme],
            edgecolor="#222222",
            linewidth=0.35,
            label=SCHEME_LABELS[scheme],
            zorder=3,
        )
        for bar, width in zip(bars, widths[scheme]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.07,
                f"w={width}",
                ha="center",
                va="bottom",
                fontsize=6,
                rotation=90,
            )

    ax.set_yscale("log")
    ax.set_ylabel("Online KB/proof (log)")
    ax.set_xlabel("SMT height")
    ax.set_xticks(x)
    ax.set_xticklabels([str(height) for height in heights])
    ax.grid(axis="y", which="major", color="#d0d0d0", linewidth=0.55, zorder=0)
    ax.grid(axis="y", which="minor", color="#eeeeee", linewidth=0.35, zorder=0)
    ax.set_ylim(1.8, max(max(vals) for vals in values.values()) * 1.85)
    ax.legend(loc="upper left", frameon=False, ncol=1)
    ax.set_title("Full SimplePIR API check")

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.35)
    fig.savefig(args.pdf, bbox_inches="tight")
    fig.savefig(args.png, dpi=300, bbox_inches="tight")
    print(f"pdf={args.pdf}")
    print(f"png={args.png}")


if __name__ == "__main__":
    main()
