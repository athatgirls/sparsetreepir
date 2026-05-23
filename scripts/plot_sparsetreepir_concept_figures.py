from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 6,
            "axes.titlesize": 6.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    print(f"wrote figures/{stem}.pdf")


def add_box(
    ax: plt.Axes,
    xy: tuple[float, float],
    wh: tuple[float, float],
    text: str,
    face: str,
    edge: str,
    fontsize: float = 6.2,
    weight: str = "normal",
    radius: float = 0.06,
) -> FancyBboxPatch:
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.018,rounding_size={radius}",
        linewidth=0.65,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        weight=weight,
        linespacing=1.15,
    )
    return patch


def add_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], color: str = "#333333") -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=8,
            linewidth=0.75,
            color=color,
            shrinkA=2,
            shrinkB=2,
        )
    )


def plot_treepir_vs_smt_object() -> None:
    fig, ax = plt.subplots(figsize=(3.45, 2.10))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.0)

    add_box(
        ax,
        (0.35, 2.95),
        (9.3, 1.35),
        "TreePIR-first adaptation\ncolor full coordinate tree\nthen prune default records\ninterface may remain height-pinned",
        "#f7e6e4",
        "#b66a50",
        fontsize=6.0,
        weight="normal",
        radius=0.08,
    )
    add_box(
        ax,
        (0.35, 1.15),
        (9.3, 1.35),
        "SparseTreePIR organization\nextract active proof intervals first\nthen color active forest\nm queries plus public defaults",
        "#e4f2ee",
        "#2f8477",
        fontsize=6.0,
        weight="normal",
        radius=0.08,
    )

    ax.text(
        5.0,
        0.35,
        "The main question is what object the one-query-per-color principle should color.",
        fontsize=6.1,
        ha="center",
        va="center",
        color="#333333",
    )
    fig.tight_layout(pad=0.12)
    save(fig, "sparsetreepir_treepir_vs_smt_object_figure")


def draw_node(
    ax: plt.Axes,
    x: float,
    y: float,
    label: str,
    face: str,
    edge: str,
    size: float = 0.16,
    fontsize: float = 5.8,
    lw: float = 0.8,
) -> None:
    circle = plt.Circle((x, y), size, facecolor=face, edgecolor=edge, linewidth=lw, zorder=4)
    ax.add_patch(circle)
    ax.text(x, y, label, ha="center", va="center", fontsize=fontsize, zorder=5)


def draw_edge(ax: plt.Axes, a: tuple[float, float], b: tuple[float, float], color: str = "#777777") -> None:
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, linewidth=0.65, zorder=1)


def plot_active_organization() -> None:
    fig, ax = plt.subplots(figsize=(3.45, 2.15))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.0)

    red = "#c85a5a"
    green = "#5ca46a"
    blue = "#4c8ec8"
    grey = "#cfcfcf"

    # Tree coordinates.
    coords = {
        "r": (1.70, 4.45),
        "a": (1.02, 3.48),
        "b": (2.38, 3.48),
        "c": (0.64, 2.52),
        "d": (1.40, 2.52),
        "e": (2.00, 2.52),
        "f": (2.76, 2.52),
        "x0": (0.46, 1.62),
        "x1": (0.82, 1.62),
        "x2": (1.20, 1.62),
        "x3": (1.58, 1.62),
        "x4": (1.82, 1.62),
        "x5": (2.20, 1.62),
        "x6": (2.58, 1.62),
        "x7": (2.94, 1.62),
    }
    for parent, child in [
        ("r", "a"),
        ("r", "b"),
        ("a", "c"),
        ("a", "d"),
        ("b", "e"),
        ("b", "f"),
        ("c", "x0"),
        ("c", "x1"),
        ("d", "x2"),
        ("d", "x3"),
        ("e", "x4"),
        ("e", "x5"),
        ("f", "x6"),
        ("f", "x7"),
    ]:
        draw_edge(ax, coords[parent], coords[child])

    # Active colored nodes and defaults.
    draw_node(ax, *coords["r"], "R", "#ffffff", "#222222", size=0.18, fontsize=5.3, lw=0.8)
    draw_node(ax, *coords["a"], "u1", "#f7dede", red, size=0.17)
    draw_node(ax, *coords["b"], "u2", "#e1f1e3", green, size=0.17)
    draw_node(ax, *coords["c"], "u3", "#dcecf8", blue, size=0.16)
    draw_node(ax, *coords["d"], "u4", "#e1f1e3", green, size=0.16)
    draw_node(ax, *coords["e"], "u5", "#f7dede", red, size=0.16)
    draw_node(ax, *coords["f"], r"$\Delta$", "#eeeeee", "#999999", size=0.16, fontsize=5.5)
    leaves = {
        "x0": ("", "#eeeeee", "#aaaaaa"),
        "x1": ("x1", "#ffffff", "#222222"),
        "x2": ("x2", "#ffffff", "#222222"),
        "x3": ("", "#eeeeee", "#aaaaaa"),
        "x4": ("", "#eeeeee", "#aaaaaa"),
        "x5": ("x5", "#ffffff", "#222222"),
        "x6": ("", "#eeeeee", "#aaaaaa"),
        "x7": ("", "#eeeeee", "#aaaaaa"),
    }
    for node, (label, face, edge) in leaves.items():
        draw_node(ax, *coords[node], label or r"$\Delta$", face, edge, size=0.12, fontsize=4.8)

    ax.text(1.70, 0.92, "full SMT coordinates\npublic defaults stay out of PIR", ha="center", fontsize=5.1)

    # Color subdatabases.
    db_x = 4.05
    db_y = [3.98, 3.02, 2.06]
    db_specs = [
        ("C1", "u1, u5", "#f7dede", red),
        ("C2", "u2, u4", "#e1f1e3", green),
        ("C3", "u3", "#dcecf8", blue),
    ]
    for y, (name, items, face, edge) in zip(db_y, db_specs):
        add_box(ax, (db_x, y - 0.30), (1.78, 0.60), f"{name}: {items}", face, edge, fontsize=5.55, radius=0.04)
    ax.text(db_x + 0.89, 4.63, "color stores", ha="center", fontsize=5.8, weight="bold")

    # Query side.
    add_box(ax, (7.12, 4.08), (2.16, 0.46), "target leaf x2", "#ffffff", "#222222", fontsize=5.7, weight="bold")
    query_specs = [
        (3.42, "PIR(C1, u1)", red),
        (2.66, "PIR(C2, dummy)", green),
        (1.90, "PIR(C3, u3)", blue),
    ]
    for y, text, color in query_specs:
        add_box(ax, (7.12, y - 0.21), (2.16, 0.42), text, "#ffffff", color, fontsize=5.25, radius=0.032)
        add_arrow(ax, (5.84, y), (7.12, y), color)
    add_box(ax, (7.12, 0.86), (2.16, 0.50), "complete with\npublic defaults", "#eeeeee", "#999999", fontsize=5.15)
    ax.text(8.20, 4.72, "one fixed-shape batch", ha="center", fontsize=5.8, weight="bold")

    fig.tight_layout(pad=0.08)
    save(fig, "sparsetreepir_active_organization_figure")


def plot_served_interval_lookup() -> None:
    fig, ax = plt.subplots(figsize=(3.45, 1.95))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.7)

    # Leaf-rank line.
    y = 3.62
    for i in range(6):
        x = 0.72 + i * 0.58
        face = "#e4f2ee" if 1 <= i <= 3 else "#f1f1f1"
        ax.add_patch(Rectangle((x - 0.20, y - 0.20), 0.40, 0.40, facecolor=face, edgecolor="#555555", linewidth=0.55))
        ax.text(x, y, str(i), ha="center", va="center", fontsize=5.9)
    ax.text(0.35, 4.20, "real-leaf ranks", fontsize=5.9, ha="left", weight="bold")
    ax.plot([1.10, 2.25], [3.18, 3.18], color="#2f8477", linewidth=2.0)
    ax.text(1.68, 2.88, r"$I_{\rm srv}(u)=[1,3]$", ha="center", fontsize=5.9, color="#1f6f63")

    add_box(ax, (4.05, 3.18), (1.15, 0.70), "active\nnode u", "#e4f2ee", "#2f8477", fontsize=5.6, weight="bold")
    add_arrow(ax, (2.55, 3.62), (4.05, 3.52), "#2f8477")
    ax.text(3.28, 3.90, "serves", ha="center", fontsize=5.3, color="#1f6f63")

    add_box(ax, (0.40, 1.15), (2.45, 0.78), "public metadata\n(c, j, [1,3], level)", "#fff5df", "#d99a2b", fontsize=5.45)
    add_box(ax, (3.68, 1.20), (1.35, 0.68), "target\nrank 2", "#eaf0fb", "#4c78a8", fontsize=5.45, weight="bold")
    add_box(ax, (6.05, 1.15), (2.35, 0.78), "query compact store\nD_c[j] by PIR", "#e4f2ee", "#2f8477", fontsize=5.45, weight="bold")
    add_arrow(ax, (2.85, 1.54), (3.68, 1.54), "#444444")
    add_arrow(ax, (5.03, 1.54), (6.05, 1.54), "#444444")
    ax.text(3.25, 1.90, "binary search", ha="center", fontsize=4.9)
    ax.text(5.52, 1.90, "hit", ha="center", fontsize=4.9)

    ax.text(0.42, 0.36, "The interval describes target ranks served by u, not u's own subtree span.", fontsize=5.25, color="#333333")
    fig.tight_layout(pad=0.1)
    save(fig, "sparsetreepir_served_interval_lookup_figure")


def plot_leakage_model() -> None:
    fig, ax = plt.subplots(figsize=(3.45, 2.02))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.7)

    add_box(
        ax,
        (0.30, 3.05),
        (2.68, 1.18),
        "public\nsnapshot\nmetadata\ncolor sizes",
        "#f0f0f0",
        "#7f7f7f",
        fontsize=5.15,
        weight="bold",
    )
    add_box(
        ax,
        (3.62, 3.05),
        (2.68, 1.18),
        "hidden\ntarget leaf\nreal/dummy\nsubindices",
        "#f7e6e4",
        "#b66a50",
        fontsize=5.15,
        weight="bold",
    )
    add_box(
        ax,
        (6.92, 3.05),
        (2.78, 1.18),
        "server sees\nQ1, Q2, ..., Qm\nsame shape",
        "#e4f2ee",
        "#2f8477",
        fontsize=5.15,
        weight="bold",
    )

    add_arrow(ax, (2.98, 3.64), (3.62, 3.64), "#555555")
    add_arrow(ax, (6.30, 3.64), (6.92, 3.64), "#555555")

    # Transcript strip.
    labels = [r"$Q_1$", r"$Q_2$", r"$\cdots$", r"$Q_m$"]
    for i, label in enumerate(labels):
        x = 1.78 + i * 1.03
        add_box(ax, (x, 1.55), (0.66, 0.50), label, "#e4f2ee", "#2f8477", fontsize=5.8)
    ax.text(1.78, 2.22, "fixed-shape transcript", ha="left", va="center", fontsize=5.35, weight="bold")
    ax.text(5.80, 1.80, "each item is an ordinary PIR query;\nreal vs dummy is client-local", ha="left", va="center", fontsize=5.25)

    add_box(ax, (1.02, 0.55), (1.40, 0.44), "real", "#e4f2ee", "#2f8477", fontsize=5.25)
    add_box(ax, (2.62, 0.55), (1.40, 0.44), "dummy", "#e4f2ee", "#2f8477", fontsize=5.25)
    ax.text(4.42, 0.77, "same query distribution under the PIR layer", fontsize=5.25, va="center")

    fig.tight_layout(pad=0.1)
    save(fig, "sparsetreepir_leakage_model_figure")


def main() -> None:
    configure_matplotlib()
    plot_active_organization()
    plot_served_interval_lookup()
    plot_leakage_model()


if __name__ == "__main__":
    main()
