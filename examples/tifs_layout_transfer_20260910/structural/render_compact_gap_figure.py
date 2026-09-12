"""Render only the frozen 12-row summary; no solver, timing, or source edits."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

out = Path(__file__).resolve().parent
stem = "absolute_gap_distribution_compact"
# Only these new compact draft files are refreshed during visual QA.
# The previously frozen absolute_gap_distribution and ECDF files are never written.
data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
methods = ["First-fit", "AB", "AB + pair", "AB + 3", "AB + 3→4", "Exact OPT"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.labelsize": 8.5,
                     "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
                     "legend.fontsize": 8.5, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42})
fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.65), sharey=True)
fig.subplots_adjust(left=.155, right=.991, bottom=.28, top=.805, wspace=.14)
colors = ["#238b45", "#fdae61", "#f46d43", "#d73027", "#a50026", "#67001f"]
for ax, cohort in zip(axes, ("base", "holdout")):
    rows = [next(r for r in data["methods"] if r["cohort"] == cohort and r["method"] == method) for method in methods]
    y = np.arange(len(methods)); left = np.zeros(len(methods))
    for delta in range(6):
        share = [100 * sum(v for k, v in r["absolute_gap_counts"].items()
                           if int(k) == delta or (delta == 5 and int(k) > 5)) / r["shapes"] for r in rows]
        ax.barh(y, share, height=.66, left=left, color=colors[delta], linewidth=.35, edgecolor="white",
                label=f"Δ = {delta}" if delta < 5 else "Δ ≥ 5")
        left += np.asarray(share)
    for yi, row in enumerate(rows):
        ax.text(103, yi, f"{row['OPT_attained']}/{row['shapes']}", va="center", ha="left", fontsize=8.5)
    ax.text(103, -.84, "OPT hits", fontsize=8.5, weight="bold", ha="left", va="center")
    ax.set_yticks(y, labels=methods)
    ax.set_ylim(5.65, -1.22); ax.set_xlim(0, 141)
    ax.set_xticks([0, 50, 100]); ax.set_xlabel("Share of shapes (%)", labelpad=4)
    ax.set_title(f"{cohort.capitalize()} · {rows[0]['shapes']:,} shapes", fontsize=9.5, weight="bold", pad=10)
    ax.grid(axis="x", color="#dddddd", linewidth=.45); ax.set_axisbelow(True)
    ax.spines["bottom"].set_bounds(0, 100)
    ax.tick_params(axis="y", length=0, pad=5)
axes[1].tick_params(labelleft=False)
fig.suptitle("Exact maximum-bucket gap: Δ = U − OPT", y=.975, fontsize=10.5, weight="bold")
fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(.535, .014),
           ncol=3, frameon=False, columnspacing=1.75, handlelength=1.7, labelspacing=.55)
# Intentionally no bbox_inches='tight': preserve exactly 7.1 inches for predictable typesetting.
fig.savefig(out / (stem + ".pdf"))
fig.savefig(out / (stem + ".png"), dpi=240)
plt.close(fig)
(out / "compact_figure_readme.md").write_text(
    "# Compact figure for final typesetting\n\n"
    "Use absolute_gap_distribution_compact.pdf at width=\\textwidth (7.16 inches). "
    "The PDF is exactly 7.1 × 3.65 inches, so this placement slightly enlarges it. "
    "All tick, method, count, legend and axis-label text is at least 8.5 pt; panel titles are 9.5 pt and the main title 10.5 pt. "
    "It contains the same frozen distribution; gaps ≥5 are grouped only in the figure. "
    "The original PDF/PNG, full ECDF, CSVs, summary and validation files were not altered. "
    "Retain only this figure in the manuscript; the full CSV and ECDF remain in the artifact. "
    "Do not reduce this figure to one column; a one-column version would require another layout.\n",
    encoding="utf-8")
print("Wrote fixed-size compact figure; no measurement or solver work.")
