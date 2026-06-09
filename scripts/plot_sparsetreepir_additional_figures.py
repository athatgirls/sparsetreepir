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


def label_bars(ax: plt.Axes, bars, values: list[float], *, dy: float = 0.04, fontsize: float = 5.6) -> None:
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + dy,
            f"{value:.2f}x",
            ha="center",
            va="bottom",
            fontsize=fontsize,
        )


def plot_gain_summary_xfold() -> None:
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(3.45, 2.18),
        gridspec_kw={"width_ratios": [1.16, 1.24], "wspace": 0.24},
    )

    left_labels = ["queries h=128", "queries h=256", "max store h=128"]
    left_ranges = [(7.53, 14.22), (15.06, 28.44), (1.74, 3.33)]
    left_colors = ["#4c78a8", "#4c78a8", "#72b7b2"]
    ax = axes[0]
    y = np.arange(len(left_labels))
    for yi, (lo, hi), color in zip(y, left_ranges, left_colors):
        ax.hlines(yi, lo, hi, color=color, linewidth=5.5, zorder=3)
        ax.plot([lo, hi], [yi, yi], linestyle="", marker="|", markersize=8, color="#222222", zorder=4)
        ax.text(
            0.98,
            yi,
            f"{lo:.1f}-{hi:.1f}x",
            transform=ax.get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=4.8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 0.25},
            clip_on=True,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(left_labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 30.0)
    ax.set_xlabel("gain (x)")
    ax.set_title("vs pruned TreePIR-h")
    ax.grid(axis="x", color="#dddddd", linewidth=0.45, zorder=0)

    right_labels = ["width", "records", "max bucket", "SimplePIR KB", "PIANO KB"]
    right_values = [1.53, 3.00, 2.11, 2.21, 2.35]
    right_colors = ["#4c78a8", "#f2a541", "#72b7b2", "#9c755f", "#e45756"]
    ax = axes[1]
    y = np.arange(len(right_labels))
    bars = ax.barh(y, right_values, color=right_colors, edgecolor="#222222", linewidth=0.35, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([])
    for yi, label in zip(y, right_labels):
        ax.text(
            0.07,
            yi,
            label,
            ha="left",
            va="center",
            fontsize=5.6,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 0.15},
            zorder=4,
        )
    ax.invert_yaxis()
    ax.set_xlim(0, 3.35)
    ax.set_xlabel("gain (x)")
    ax.set_title("vs PBC")
    ax.grid(axis="x", color="#dddddd", linewidth=0.45, zorder=0)
    for bar, value in zip(bars, right_values):
        ax.text(value + 0.07, bar.get_y() + bar.get_height() / 2, f"{value:.2f}x", va="center", fontsize=5.5)

    for ax in axes:
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
    fig.tight_layout(pad=0.20)
    save(fig, "sparsetreepir_gain_summary_bars")


def plot_workload_xfold() -> None:
    labels = ["Fuel", "Polygon\nrecent", "ZKsync\nsample", "Polygon\nmulti", "Polygon\nbroad", "ZKsync\nbroad"]
    query_gain = [14.22, 11.64, 9.85, 9.14, 7.53, 7.53]
    max_gain = [1.74, 2.40, 2.52, 2.75, 3.33, 3.31]

    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(3.45, 2.15))
    bars_query = ax.bar(
        x - width / 2,
        query_gain,
        width,
        label="queries",
        color="#4c78a8",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    bars_max = ax.bar(
        x + width / 2,
        max_gain,
        width,
        label="max store",
        color="#72b7b2",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_ylabel("pruned TreePIR-h / SparseTreePIR")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_yticks([1, 2, 4, 8, 16])
    ax.set_yticklabels(["1x", "2x", "4x", "8x", "16x"])
    ax.set_ylim(1, 18)
    ax.grid(axis="y", color="#dddddd", linewidth=0.45, zorder=0, which="both")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, frameon=False)
    label_bars(ax, bars_query, query_gain, dy=0.35)
    label_bars(ax, bars_max, max_gain, dy=0.16)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout(pad=0.25)
    save(fig, "sparsetreepir_workload_xfold_figure")


def plot_backend_xfold() -> None:
    metrics = ["online KB", "setup"]
    simplepir = [2.21, 2.50]
    piano = [2.35, 3.29]

    x = np.arange(len(metrics))
    width = 0.34
    fig, ax = plt.subplots(figsize=(3.45, 1.85))
    bars_simple = ax.bar(
        x - width / 2,
        simplepir,
        width,
        label="SimplePIR",
        color="#4c78a8",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    bars_piano = ax.bar(
        x + width / 2,
        piano,
        width,
        label="PIANO",
        color="#e45756",
        edgecolor="#222222",
        linewidth=0.35,
        zorder=3,
    )
    ax.set_ylabel("PBC / SparseTreePIR")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 3.75)
    ax.grid(axis="y", color="#dddddd", linewidth=0.45, zorder=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.18), ncol=2, frameon=False)
    label_bars(ax, bars_simple, simplepir)
    label_bars(ax, bars_piano, piano)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout(pad=0.25)
    save(fig, "sparsetreepir_backend_xfold_figure")


def main() -> None:
    configure_matplotlib()
    plot_distribution_reduction()
    plot_height_vs_active_width()
    plot_metadata_overhead()
    plot_gain_summary_xfold()
    plot_workload_xfold()
    plot_backend_xfold()


if __name__ == "__main__":
    main()
