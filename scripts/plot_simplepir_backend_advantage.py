from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCHEMES = ["flat_normal_pir_m", "profile_balanced"]
LABELS = {
    "flat_normal_pir_m": "Uncolored-active PIR",
    "profile_balanced": "Profile-balanced",
}
COLORS = {
    "flat_normal_pir_m": "#8c8c8c",
    "profile_balanced": "#2f7ebc",
}


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sparsity_label(value: float) -> str:
    return f"{value * 100:.3f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot backend advantage relative to uncolored-active PIR.")
    parser.add_argument("--csv", type=Path, default=Path("examples/simplepir_full_backend_results.csv"))
    parser.add_argument("--pdf", type=Path, default=Path("figures/simplepir_backend_advantage.pdf"))
    parser.add_argument("--png", type=Path, default=Path("figures/simplepir_backend_advantage.png"))
    args = parser.parse_args()

    rows = read_rows(args.csv)
    grouped: Dict[Tuple[int, float], Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in rows:
        grouped[(int(row["height"]), float(row["sparsity"]))][row["scheme"]] = row

    keys = sorted(grouped)
    ratios = {scheme: [] for scheme in SCHEMES}
    widths = {scheme: [] for scheme in SCHEMES}
    for key in keys:
        flat_online = float(grouped[key]["flat_normal_pir_m"]["online_total_kb"])
        for scheme in SCHEMES:
            ratios[scheme].append(float(grouped[key][scheme]["online_total_kb"]) / flat_online)
            widths[scheme].append(int(grouped[key][scheme]["width"]))

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 7,
            "axes.titlesize": 8,
            "axes.labelsize": 7,
            "legend.fontsize": 6.5,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(3.45, 2.65))
    x = np.arange(len(keys))
    bar_width = 0.30
    offsets = [-bar_width / 2, bar_width / 2]

    for scheme, offset in zip(SCHEMES, offsets):
        bars = ax.bar(
            x + offset,
            ratios[scheme],
            width=bar_width,
            color=COLORS[scheme],
            edgecolor="#222222",
            linewidth=0.3,
            label=LABELS[scheme],
            zorder=3,
        )
        if scheme != "flat_normal_pir_m":
            for bar, width in zip(bars, widths[scheme]):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.025,
                    f"m={width}",
                    ha="center",
                    va="bottom",
                    rotation=90,
                    fontsize=5.6,
                )

    ax.axhline(1.0, color="#444444", linewidth=0.5, linestyle="--", zorder=1)
    ax.set_ylabel("Online KB / uncolored-active PIR")
    ax.set_xlabel("SMT height and empty-leaf ratio")
    ax.set_xticks(x)
    ax.set_xticklabels([f"h={h}\n{sparsity_label(s)}" for h, s in keys])
    ax.set_ylim(0, 1.16)
    ax.grid(axis="y", color="#dddddd", linewidth=0.5, zorder=0)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False, ncol=1)
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
