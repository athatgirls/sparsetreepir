from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm


SCHEMES = ["Perfectized", "PBC-active", "Active-only", "SparseTreePIR"]
SHORT_SCHEMES = ["Perfect.", "PBC", "Flat", "Ours"]

PRIVATE_RECORDS = [33_554_430, 50_328, 16_776, 16_776]
BATCH_WIDTH = [24, 26, 17, 17]
LARGEST_SUBDB = [1_398_102, 1_974, 16_776, 992]


def ratio_label(value: float) -> str:
    if value >= 100:
        return f"{value:.0f}x"
    if value >= 10:
        return f"{value:.1f}x"
    if value >= 2:
        return f"{value:.1f}x"
    if value == 1:
        return "1x"
    return f"{value:.2f}x"


def main() -> None:
    out_pdf = Path("figures/sparsetreepir_resource_comparison_figure.pdf")
    out_png = Path("figures/sparsetreepir_resource_comparison_figure.png")

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 6.8,
            "axes.titlesize": 7.3,
            "axes.labelsize": 6.8,
            "xtick.labelsize": 6.2,
            "ytick.labelsize": 6.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    metrics = [
        ("Private records", np.array(PRIVATE_RECORDS, dtype=float) / PRIVATE_RECORDS[-1]),
        ("Batch width", np.array(BATCH_WIDTH, dtype=float) / BATCH_WIDTH[-1]),
        ("Largest subdb.", np.array(LARGEST_SUBDB, dtype=float) / LARGEST_SUBDB[-1]),
    ]
    ratios = np.vstack([values for _, values in metrics])

    fig, ax = plt.subplots(figsize=(3.45, 1.42))
    ax.imshow(
        ratios,
        cmap="YlOrBr",
        norm=LogNorm(vmin=1, vmax=ratios.max()),
        aspect="auto",
    )

    ax.set_xticks(np.arange(len(SHORT_SCHEMES)))
    ax.set_xticklabels(SHORT_SCHEMES)
    ax.set_yticks(np.arange(len(metrics)))
    ax.set_yticklabels([name for name, _ in metrics])
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False, length=0, pad=1)

    for row in range(ratios.shape[0]):
        for col in range(ratios.shape[1]):
            value = float(ratios[row, col])
            text_color = "white" if value >= 100 else "#222222"
            ax.text(
                col,
                row,
                ratio_label(value),
                ha="center",
                va="center",
                fontsize=6.4,
                color=text_color,
                fontweight="bold" if col == len(SHORT_SCHEMES) - 1 else "normal",
            )

    for x in np.arange(-0.5, len(SHORT_SCHEMES), 1):
        ax.axvline(x, color="white", linewidth=0.7)
    for y in np.arange(-0.5, len(metrics), 1):
        ax.axhline(y, color="white", linewidth=0.7)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Resource ratios relative to SparseTreePIR", pad=16)
    ax.set_xlabel("lower is better; darker cells are larger ratios", labelpad=3)
    ax.xaxis.set_label_position("bottom")
    fig.tight_layout(pad=0.25)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    print(f"pdf={out_pdf}")
    print(f"png={out_png}")


if __name__ == "__main__":
    main()
