from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT_PDF = ROOT / "figures" / "sparsetreepir_algorithm_stack_figure.pdf"
OUT_PNG = ROOT / "figures" / "sparsetreepir_algorithm_stack_figure.png"


BLUE = "#0b4b8f"
LIGHT_BLUE = "#f0f7ff"
MID_BLUE = "#2f80d0"
ORANGE = "#e66b00"
LIGHT_ORANGE = "#fff3e6"
GREEN = "#1f6b2a"
LIGHT_GREEN = "#f2fbf0"
GRAY = "#667085"
LIGHT_GRAY = "#f8fafc"
RED = "#d62728"
PURPLE = "#7b61d1"


def box(ax, x, y, w, h, text, fc, ec, fontsize=8.5, weight="bold", color="#111827", lw=1.0):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color=color,
        linespacing=1.12,
    )
    return patch


def arrow(ax, x0, y0, x1, y1, color=GRAY, lw=1.0, ms=11):
    ax.add_patch(
        FancyArrowPatch(
            (x0, y0),
            (x1, y1),
            arrowstyle="-|>",
            mutation_scale=ms,
            linewidth=lw,
            color=color,
            shrinkA=2,
            shrinkB=2,
        )
    )


def server_icon(ax, x, y, s=1.0):
    for i, c in enumerate(["#a3e0b1", "#f4a261", "#a3e0b1"]):
        yy = y + (2 - i) * 0.026 * s
        ax.add_patch(
            FancyBboxPatch(
                (x, yy),
                0.055 * s,
                0.020 * s,
                boxstyle="round,pad=0.004,rounding_size=0.004",
                facecolor="#b8c0c8",
                edgecolor="#111827",
                linewidth=0.8,
            )
        )
        ax.add_patch(Circle((x + 0.010 * s, yy + 0.010 * s), 0.0045 * s, facecolor=c, edgecolor="#111827", lw=0.6))
        for j in range(3):
            ax.add_patch(Circle((x + 0.039 * s + 0.006 * j * s, yy + 0.010 * s), 0.002 * s, facecolor="#111827", lw=0))
    ax.add_patch(Rectangle((x + 0.063 * s, y + 0.006 * s), 0.035 * s, 0.052 * s, facecolor="#9cc8e8", edgecolor="#111827", lw=0.8))
    ax.add_patch(Circle((x + 0.0805 * s, y + 0.059 * s), 0.0175 * s, facecolor="#9cc8e8", edgecolor="#111827", lw=0.8))
    ax.plot([x + 0.063 * s, x + 0.098 * s], [y + 0.058 * s, y + 0.058 * s], color="#111827", lw=0.8)


def laptop_icon(ax, x, y, s=1.0):
    ax.add_patch(Rectangle((x, y + 0.025 * s), 0.070 * s, 0.052 * s, facecolor="#f8fafc", edgecolor="#111827", lw=1.0))
    ax.add_patch(Rectangle((x + 0.008 * s, y + 0.033 * s), 0.054 * s, 0.036 * s, facecolor="#e8f2ff", edgecolor="#d0d5dd", lw=0.6))
    shield = Polygon(
        [
            (x + 0.035 * s, y + 0.064 * s),
            (x + 0.052 * s, y + 0.057 * s),
            (x + 0.049 * s, y + 0.041 * s),
            (x + 0.035 * s, y + 0.034 * s),
            (x + 0.021 * s, y + 0.041 * s),
            (x + 0.018 * s, y + 0.057 * s),
        ],
        closed=True,
        facecolor=BLUE,
        edgecolor=BLUE,
    )
    ax.add_patch(shield)
    ax.add_patch(Rectangle((x + 0.031 * s, y + 0.047 * s), 0.008 * s, 0.007 * s, facecolor="white", edgecolor="white", lw=0))
    ax.add_patch(Circle((x + 0.035 * s, y + 0.055 * s), 0.006 * s, facecolor="none", edgecolor="white", lw=1.0))
    ax.add_patch(Rectangle((x - 0.006 * s, y + 0.017 * s), 0.082 * s, 0.007 * s, facecolor="#cbd5e1", edgecolor="#111827", lw=0.8))


def tiny_tree(ax, cx, cy, scale=1.0, active=None, default=None, dashed=False):
    active = set(active or [])
    default = set(default or [])
    nodes = {
        0: (cx, cy + 0.075 * scale),
        1: (cx - 0.035 * scale, cy + 0.045 * scale),
        2: (cx + 0.035 * scale, cy + 0.045 * scale),
        3: (cx - 0.055 * scale, cy + 0.015 * scale),
        4: (cx - 0.015 * scale, cy + 0.015 * scale),
        5: (cx + 0.015 * scale, cy + 0.015 * scale),
        6: (cx + 0.055 * scale, cy + 0.015 * scale),
        7: (cx - 0.065 * scale, cy - 0.015 * scale),
        8: (cx - 0.045 * scale, cy - 0.015 * scale),
        9: (cx - 0.025 * scale, cy - 0.015 * scale),
        10: (cx - 0.005 * scale, cy - 0.015 * scale),
        11: (cx + 0.005 * scale, cy - 0.015 * scale),
        12: (cx + 0.025 * scale, cy - 0.015 * scale),
        13: (cx + 0.045 * scale, cy - 0.015 * scale),
        14: (cx + 0.065 * scale, cy - 0.015 * scale),
    }
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6), (3, 7), (3, 8), (4, 9), (4, 10), (5, 11), (5, 12), (6, 13), (6, 14)]
    for a, b in edges:
        ax.plot([nodes[a][0], nodes[b][0]], [nodes[a][1], nodes[b][1]], color="#b7c0cc", lw=0.65, ls="--" if dashed else "-")
    for i, (xx, yy) in nodes.items():
        if i in active:
            fc, ec = MID_BLUE, BLUE
        elif i in default:
            fc, ec = "#e5e7eb", "#b7c0cc"
        else:
            fc, ec = "white", "#98a2b3"
        ax.add_patch(Circle((xx, yy), 0.0075 * scale, facecolor=fc, edgecolor=ec, lw=0.75))


def interval_icon(ax, x, y, w=0.09, color=MID_BLUE):
    ax.plot([x, x + w], [y, y], color="#111827", lw=0.9)
    for t, lab in [(0, "0"), (0.45, "i"), (0.68, "j"), (1.0, "N")]:
        xx = x + w * t
        ax.plot([xx, xx], [y - 0.006, y + 0.006], color="#111827", lw=0.7)
        ax.text(xx, y + 0.014, lab, ha="center", va="bottom", fontsize=5.5)
    ax.plot([x + w * 0.45, x + w * 0.68], [y - 0.020, y - 0.020], color=color, lw=1.4)
    ax.plot([x + w * 0.45, x + w * 0.45], [y - 0.015, y - 0.020], color=color, lw=1.0)
    ax.plot([x + w * 0.68, x + w * 0.68], [y - 0.015, y - 0.020], color=color, lw=1.0)


def coloring_icon(ax, x, y, w=0.09, h=0.07):
    colors = [RED, MID_BLUE, "#3ca34a", PURPLE]
    xs = [x + i * w / 4 for i in range(5)]
    base = y
    for i in range(4):
        ax.add_patch(Circle((xs[i], base), 0.006, facecolor="white", edgecolor="#111827", lw=0.8))
    ax.text(x + w * 0.82, base + 0.003, "...", fontsize=7, color="#667085")
    for i, col in enumerate(colors):
        ax.add_patch(FancyArrowPatch((xs[i], base + 0.005), (xs[min(i + 1, 3)], base + h * (0.45 + 0.07 * i)), connectionstyle="arc3,rad=0.45", arrowstyle="-", color=col, lw=1.1))
        ax.add_patch(Circle((x + 0.010 + i * 0.018, y - 0.026), 0.006, facecolor=col, edgecolor="#111827", lw=0.4))
        ax.text(x + 0.020 + i * 0.018, y - 0.026, str(i + 1), va="center", fontsize=5.5)


def bars_icon(ax, x, y, w=0.075, h=0.07):
    vals1 = [0.45, 0.90, 0.50, 0.35]
    vals2 = [0.55, 0.58, 0.55, 0.55]
    colors = [RED, MID_BLUE, "#3ca34a", PURPLE]
    bw = w / 10
    ax.text(x, y + h + 0.008, "before", fontsize=5.4, ha="left")
    for i, v in enumerate(vals1):
        ax.add_patch(Rectangle((x + i * bw * 1.5, y), bw, h * v, facecolor=colors[i], edgecolor="#111827", lw=0.35))
    ax.text(x + w * 0.58, y + h * 0.42, "\u2192", fontsize=10, ha="center", va="center")
    x2 = x + w * 0.70
    ax.text(x2, y + h + 0.008, "after", fontsize=5.4, ha="left")
    for i, v in enumerate(vals2):
        ax.add_patch(Rectangle((x2 + i * bw * 1.5, y), bw, h * v, facecolor=colors[i], edgecolor="#111827", lw=0.35))


def query_icon(ax, x, y, w=0.09):
    for i in range(4):
        xx = x + i * w / 3
        ax.add_patch(Rectangle((xx - 0.006, y + 0.020), 0.012, 0.018, facecolor="#f8fafc", edgecolor=BLUE, lw=0.8))
        ax.add_patch(Polygon([(xx + 0.002, y + 0.038), (xx + 0.006, y + 0.034), (xx + 0.006, y + 0.038)], facecolor="#dbeafe", edgecolor=BLUE, lw=0.4))
        real = i in [0, 2, 3]
        ax.add_patch(Circle((xx, y), 0.006, facecolor=MID_BLUE if real else "white", edgecolor=BLUE, lw=0.9, linestyle="-" if real else "--"))
        arrow(ax, xx, y + 0.004, xx, y + 0.018, color="#111827", lw=0.6, ms=6)


def proof_icon(ax, x, y, w=0.055, h=0.10):
    rows = 5
    for i in range(rows):
        yy = y + h * (rows - i - 1) / rows
        fc = "#e8f2ff" if i in [0, 1, 4] else "#f8fafc"
        ax.add_patch(Rectangle((x, yy), w, h / rows, facecolor=fc, edgecolor="#98a2b3", lw=0.55))
        if i in [0, 1, 4]:
            ax.add_patch(Circle((x + w * 0.30, yy + h / rows / 2), 0.0055, facecolor=MID_BLUE, edgecolor=BLUE, lw=0.4))
        else:
            ax.text(x + w * 0.30, yy + h / rows / 2, r"$\Delta$", fontsize=5.5, ha="center", va="center")
    ax.text(x + w + 0.012, y + h * 0.83, "0", fontsize=6)
    ax.text(x + w + 0.012, y + h * 0.51, r"$\cdots$", fontsize=6)
    ax.text(x + w + 0.012, y + h * 0.04, r"$h-1$", fontsize=6)


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, ax = plt.subplots(figsize=(16.0, 8.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.965,
        "SparseTreePIR: Solving the SMT-to-Private-Retrieval Challenge",
        ha="center",
        va="top",
        fontsize=20,
        fontweight="bold",
        color="#111827",
    )

    # Side panels.
    ax.add_patch(
        FancyBboxPatch(
            (0.015, 0.18),
            0.095,
            0.67,
            boxstyle="round,pad=0.010,rounding_size=0.012",
            facecolor="white",
            edgecolor=BLUE,
            linewidth=1.2,
        )
    )
    ax.text(0.062, 0.820, "Ordinary\nSMT proof\nserving", fontsize=10.5, color=BLUE, fontweight="bold", ha="center", va="top")
    server_icon(ax, 0.030, 0.66, s=1.05)
    ax.text(0.062, 0.600, "Server holds\nSMT tree", fontsize=7.5, ha="center", va="top")
    ax.plot([0.03, 0.095], [0.535, 0.535], ls="--", color="#b7c0cc", lw=0.9)
    ax.text(0.062, 0.500, "Return sibling\ndigests for\nknown target", fontsize=7.4, ha="center", va="top")
    tiny_tree(ax, 0.062, 0.310, scale=0.88, active={10, 4, 1})

    ax.add_patch(
        FancyBboxPatch(
            (0.905, 0.18),
            0.080,
            0.67,
            boxstyle="round,pad=0.010,rounding_size=0.012",
            facecolor="white",
            edgecolor=BLUE,
            linewidth=1.2,
        )
    )
    ax.text(0.945, 0.820, "Target-private\nSMT proof\nretrieval", fontsize=9.5, color=BLUE, fontweight="bold", ha="center", va="top")
    laptop_icon(ax, 0.920, 0.660, s=0.96)
    ax.text(0.945, 0.600, "Client receives\ncompleted proof", fontsize=6.9, ha="center", va="top")
    ax.plot([0.918, 0.972], [0.535, 0.535], ls="--", color="#b7c0cc", lw=0.9)
    ax.text(0.945, 0.505, "Target remains\nhidden from\nthe server", fontsize=6.9, ha="center", va="top")
    tiny_tree(ax, 0.945, 0.305, scale=0.78, active={12}, default={10})
    ax.add_patch(Circle((0.958, 0.235), 0.013, facecolor="white", edgecolor=BLUE, lw=1.0, linestyle="--"))
    ax.text(0.958, 0.235, "?", fontsize=9, ha="center", va="center", color=BLUE)

    # Row labels.
    ax.text(0.160, 0.745, "Challenge", fontsize=8.7, color=ORANGE, fontweight="bold", ha="right", va="center")
    ax.text(0.160, 0.515, "Mechanism", fontsize=8.4, color=BLUE, fontweight="bold", ha="right", va="center")
    ax.text(0.160, 0.285, "Result", fontsize=8.7, color=GREEN, fontweight="bold", ha="right", va="center")

    col_x = [0.195, 0.312, 0.429, 0.546, 0.663, 0.780]
    bw = 0.086
    challenge_y, mech_y, result_y = 0.690, 0.385, 0.155
    ch_h, mech_h, res_h = 0.135, 0.210, 0.170

    challenges = [
        "Public default\ncoordinates\nshould not enter\nthe PIR database",
        "Active compaction\nneeds compact\nlookup",
        "A proof must\nbecome a fixed\nbatch workload",
        "Valid coloring\nmay leave one\nlarge bucket",
        "Some colors\nhave no real\nnode",
        "Verifier expects\nordinary\nheight-$h$ proof",
    ]
    mechanisms = [
        ("Active proof\nrecords", lambda x, y: tiny_tree(ax, x + 0.046, y + 0.080, scale=0.95, active={0, 2, 5, 12}, default={1, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14})),
        ("Served\nintervals", lambda x, y: interval_icon(ax, x + 0.014, y + 0.095, w=0.064)),
        ("Active-width\ncoloring", lambda x, y: coloring_icon(ax, x + 0.015, y + 0.080, w=0.064, h=0.065)),
        ("ActiveBalance", lambda x, y: bars_icon(ax, x + 0.016, y + 0.075, w=0.060, h=0.060)),
        ("Real/dummy\nPIR queries", lambda x, y: query_icon(ax, x + 0.018, y + 0.077, w=0.055)),
        ("Default\ncompletion", lambda x, y: proof_icon(ax, x + 0.028, y + 0.038, w=0.030, h=0.100)),
    ]
    results = [
        ("Store only\nnon-default\nproof records", lambda x, y: tiny_tree(ax, x + 0.046, y + 0.037, scale=0.56, active={0, 2, 5, 12})),
        ("Metadata-guided\ntarget lookup", lambda x, y: interval_icon(ax, x + 0.018, y + 0.055, w=0.058, color="#3ca34a")),
        ("At most one\nreal node\nper color", lambda x, y: coloring_icon(ax, x + 0.018, y + 0.050, w=0.055, h=0.050)),
        ("Flatter\ncolor-store loads", lambda x, y: bars_icon(ax, x + 0.019, y + 0.014, w=0.056, h=0.040)),
        ("Fixed transcript\nhides real vs\ndummy", lambda x, y: query_icon(ax, x + 0.020, y + 0.047, w=0.052)),
        ("Recover standard\nSMT proof locally", lambda x, y: proof_icon(ax, x + 0.032, y + 0.007, w=0.024, h=0.076)),
    ]

    for i, x in enumerate(col_x):
        # Number circles.
        ax.add_patch(Circle((x + bw / 2, 0.875), 0.018, facecolor=BLUE, edgecolor=BLUE, lw=1))
        ax.text(x + bw / 2, 0.875, str(i + 1), color="white", fontsize=12, fontweight="bold", ha="center", va="center")
        if i < len(col_x) - 1:
            arrow(ax, x + bw * 0.92, 0.875, col_x[i + 1] + bw * 0.08, 0.875, color="#9aa3ad", lw=1.2, ms=12)

        box(ax, x, challenge_y, bw, ch_h, challenges[i], LIGHT_ORANGE, ORANGE, fontsize=7.8, color="#111827", lw=0.8)
        arrow(ax, x + bw / 2, challenge_y - 0.006, x + bw / 2, mech_y + mech_h + 0.006, color="#111827", lw=0.85, ms=9)

        mech_title, mech_draw = mechanisms[i]
        box(ax, x, mech_y, bw, mech_h, "", LIGHT_BLUE, MID_BLUE, lw=0.8)
        ax.text(x + bw / 2, mech_y + mech_h - 0.020, mech_title, fontsize=7.3, color=BLUE, fontweight="bold", ha="center", va="top")
        mech_draw(x, mech_y)
        arrow(ax, x + bw / 2, mech_y - 0.006, x + bw / 2, result_y + res_h + 0.006, color="#111827", lw=0.85, ms=9)

        result_title, result_draw = results[i]
        box(ax, x, result_y, bw, res_h, "", LIGHT_GREEN, "#7dbb7d", lw=0.8)
        ax.text(x + bw / 2, result_y + res_h - 0.020, result_title, fontsize=6.8, color=GREEN, fontweight="bold", ha="center", va="top")
        result_draw(x, result_y)

    # From left and to right.
    arrow(ax, 0.115, 0.515, 0.185, 0.515, color=BLUE, lw=1.2, ms=12)
    arrow(ax, 0.905, 0.515, 0.875, 0.515, color=BLUE, lw=1.2, ms=12)

    # Footer.
    footer = FancyBboxPatch(
        (0.075, 0.050),
        0.850,
        0.050,
        boxstyle="round,pad=0.010,rounding_size=0.012",
        facecolor="white",
        edgecolor=BLUE,
        linewidth=0.9,
    )
    ax.add_patch(footer)
    footer_items = [
        (0.130, "PIR records: active proof-bearing nodes"),
        (0.405, "Batch width: active width $m$"),
        (0.640, "Proof semantics unchanged: ordinary height-$h$ SMT proof"),
    ]
    for x, text in footer_items:
        ax.add_patch(Circle((x - 0.030, 0.075), 0.017, facecolor=LIGHT_BLUE, edgecolor=BLUE, lw=0.9))
        ax.text(x - 0.030, 0.075, "\u25cf", color=BLUE, fontsize=7, ha="center", va="center")
        ax.text(x, 0.075, text, fontsize=8.0, color="#111827", ha="left", va="center", fontweight="bold")
    for x in [0.355, 0.615]:
        ax.plot([x, x], [0.055, 0.095], color="#d0d5dd", lw=0.9)

    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=220, bbox_inches="tight")


if __name__ == "__main__":
    main()
