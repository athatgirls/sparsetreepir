from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"
EXAMPLES_DIR = ROOT / "examples"


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 7,
            "axes.titlesize": 7.5,
            "axes.labelsize": 7,
            "xtick.labelsize": 6,
            "ytick.labelsize": 6,
            "legend.fontsize": 6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    print(f"wrote figures/{stem}.pdf")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot_distribution_reduction() -> None:
    # Same values as Table "Distribution stress test with 1024 occupied leaves".
    heights = [16, 20, 24]
    data = {
        "uniform": [17.9, 15.6, 17.3],
        "clustered": [16.9, 11.0, 4.8],
        "adversarial": [75.2, 65.5, 65.9],
    }
    colors = {
        "uniform": "#4c78a8",
        "clustered": "#72b7b2",
        "adversarial": "#e45756",
    }

    x = np.arange(len(heights))
    width = 0.24
    fig, ax = plt.subplots(figsize=(3.45, 1.95))
    offsets = [-width, 0.0, width]
    for offset, (label, values) in zip(offsets, data.items()):
        bars = ax.bar(
            x + offset,
            values,
            width,
            label=label,
            color=colors[label],
            edgecolor="#202020",
            linewidth=0.3,
            zorder=3,
        )
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 1.1,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=5.5,
            )

    ax.set_xticks(x)
    ax.set_xticklabels([f"h={height}" for height in heights])
    ax.set_ylabel("largest-bucket reduction (%)")
    ax.set_ylim(0, 84)
    ax.grid(axis="y", color="#dddddd", linewidth=0.45, zorder=0)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.20), frameon=False)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout(pad=0.25)
    save(fig, "sparsetreepir_distribution_reduction_figure")


def plot_height_vs_active_width() -> None:
    rows = read_csv(EXAMPLES_DIR / "height128_256_compressed_smt_profile_balance_results.csv")
    labels = [f"h={int(float(row['height']))}\nn={int(float(row['occupied']))}" for row in rows]
    heights = [float(row["height"]) for row in rows]
    active_widths = [float(row["m"]) for row in rows]

    x = np.arange(len(rows))
    width = 0.36
    fig, ax = plt.subplots(figsize=(3.45, 2.15))
    bars_h = ax.bar(
        x - width / 2,
        heights,
        width,
        label="verification height h",
        color="#8f969f",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    bars_m = ax.bar(
        x + width / 2,
        active_widths,
        width,
        label="active width m",
        color="#2f8477",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_ylabel("levels / PIR subqueries (log)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(axis="y", color="#dddddd", linewidth=0.45, zorder=0, which="both")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, frameon=False)
    for bars, values in [(bars_h, heights), (bars_m, active_widths)]:
        for bar, value in zip(bars, values):
            label = f"{value:.0f}" if value >= 100 else f"{value:.1f}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.12,
                label,
                ha="center",
                va="bottom",
                fontsize=5.7,
            )
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout(pad=0.25)
    save(fig, "sparsetreepir_height_vs_active_width_figure")


def plot_metadata_overhead() -> None:
    rows = read_csv(EXAMPLES_DIR / "metadata_overhead_results.csv")
    # Keep the visually informative height-20/24 rows in the main figure.
    rows = [row for row in rows if int(float(row["height"])) in {20, 24}]
    labels = [f"h={int(float(row['height']))}\n{100 * float(row['sparsity']):.3f}% empty" for row in rows]
    digest = [float(row["digest_kb"]) for row in rows]
    metadata = [float(row["metadata_kb"]) for row in rows]

    x = np.arange(len(rows))
    width = 0.36
    fig, ax = plt.subplots(figsize=(3.45, 2.25))
    bars_digest = ax.bar(
        x - width / 2,
        digest,
        width,
        label="private digests",
        color="#4c78a8",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    bars_meta = ax.bar(
        x + width / 2,
        metadata,
        width,
        label="public metadata",
        color="#f2a541",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_ylabel("setup bytes (KB, log)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.grid(axis="y", color="#dddddd", linewidth=0.45, zorder=0, which="both")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, frameon=False)
    for bars, values in [(bars_digest, digest), (bars_meta, metadata)]:
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value * 1.12,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=5.4,
                rotation=90,
            )
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout(pad=0.25)
    save(fig, "sparsetreepir_metadata_overhead_figure")


def main() -> None:
    configure_matplotlib()
    plot_distribution_reduction()
    plot_height_vs_active_width()
    plot_metadata_overhead()


if __name__ == "__main__":
    main()
