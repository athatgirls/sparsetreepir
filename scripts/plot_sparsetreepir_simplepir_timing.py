from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCHEME_ORDER = ["flat_normal_pir_m", "pbc_active", "profile_balanced"]
SCHEME_LABELS = {
    "flat_normal_pir_m": "Flat",
    "pbc_active": "PBC-active",
    "profile_balanced": "SparseTreePIR",
}
SCHEME_COLORS = {
    "flat_normal_pir_m": "#8c8c8c",
    "pbc_active": "#b35ba8",
    "profile_balanced": "#2f8477",
}
METRICS = [
    ("setup_ms", "Setup"),
    ("client_query_ms", "QueryGen"),
    ("server_parallel_ms", "Answer"),
    ("client_decode_ms", "Recover"),
]


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot representative SimplePIR timing breakdown.")
    parser.add_argument("--csv", type=Path, default=Path("examples/simplepir_full_backend_results.csv"))
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--sparsity", type=float, default=0.9995)
    parser.add_argument("--pdf", type=Path, default=Path("figures/sparsetreepir_simplepir_timing_figure.pdf"))
    parser.add_argument("--png", type=Path, default=Path("figures/sparsetreepir_simplepir_timing_figure.png"))
    args = parser.parse_args()

    rows = [
        row
        for row in read_rows(args.csv)
        if int(row["height"]) == args.height and abs(float(row["sparsity"]) - args.sparsity) < 1e-12
    ]
    by_scheme = {row["scheme"]: row for row in rows}
    missing = [scheme for scheme in SCHEME_ORDER if scheme not in by_scheme]
    if missing:
        raise RuntimeError(f"missing schemes: {missing}")

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 7,
            "axes.titlesize": 7.6,
            "axes.labelsize": 7,
            "legend.fontsize": 6.6,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    x = np.arange(len(METRICS))
    width = 0.22
    offsets = [-width, 0, width]

    fig, ax = plt.subplots(figsize=(3.45, 2.35))
    for offset, scheme in zip(offsets, SCHEME_ORDER):
        values = [float(by_scheme[scheme][metric]) for metric, _ in METRICS]
        bars = ax.bar(
            x + offset,
            values,
            width=width,
            color=SCHEME_COLORS[scheme],
            edgecolor="#222222",
            linewidth=0.35,
            label=SCHEME_LABELS[scheme],
            zorder=3,
        )
        for bar, value in zip(bars, values):
            if value >= 10:
                label = f"{value:.1f}"
            elif value >= 1:
                label = f"{value:.2f}"
            else:
                label = f"{value:.3f}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.17,
                label,
                ha="center",
                va="bottom",
                fontsize=5.5,
                rotation=90,
            )

    ax.set_yscale("log")
    ax.set_ylabel("Milliseconds (log)")
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in METRICS])
    ax.grid(axis="y", which="major", color="#d0d0d0", linewidth=0.55, zorder=0)
    ax.grid(axis="y", which="minor", color="#eeeeee", linewidth=0.35, zorder=0)
    ax.set_ylim(0.05, 130)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False, ncol=3)
    ax.set_title(r"SimplePIR timing, $h=24$, 99.95\% empty", pad=16)
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
