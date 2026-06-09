from __future__ import annotations

import argparse
import bisect
import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring, RawNode


COLOR_PALETTE = {
    1: "#e57373",
    2: "#ffb74d",
    3: "#81c784",
    4: "#64b5f6",
    5: "#ba68c8",
    6: "#4db6ac",
    7: "#ffd54f",
    8: "#9575cd",
    9: "#90a4ae",
    10: "#f06292",
}


def heap_leaf_base(tree_height: int) -> int:
    return 1 << tree_height


def heap_leaf_to_slot(leaf_index: int, tree_height: int) -> int:
    return leaf_index - heap_leaf_base(tree_height)


@dataclass
class ProofNode:
    index: int
    depth: int
    interval_left: int
    interval_right: int
    weight: int
    covers_leaves: List[int]
    color: Optional[int] = None
    parent: Optional["ProofNode"] = None
    children: List["ProofNode"] = field(default_factory=list)


def full_leaf_range(node_index: int, tree_height: int) -> Tuple[int, int]:
    depth = node_index.bit_length() - 1
    span = 1 << (tree_height - depth)
    return node_index * span, (node_index + 1) * span - 1


def generate_occupied_leaves(tree_height: int, sparsity: float, seed: int) -> List[int]:
    if not (0.0 <= sparsity <= 1.0):
        raise ValueError("sparsity must be between 0 and 1.")

    total_leaves = 1 << tree_height
    occupied_count = round(total_leaves * (1.0 - sparsity))
    occupied_count = max(1, min(total_leaves, occupied_count))

    rng = random.Random(seed)
    candidates = list(range(1 << tree_height, 1 << (tree_height + 1)))
    occupied = sorted(rng.sample(candidates, occupied_count))
    return occupied


def build_full_proof_nodes(
    raw_nodes: Dict[int, RawNode],
    occupied_leaves: Sequence[int],
    tree_height: int,
) -> List[ProofNode]:
    proof_nodes: List[ProofNode] = []

    for node in raw_nodes.values():
        if node.index == 1 or node.parent is None or node.live_leaf_count == 0:
            continue

        sibling = node.parent.left if node.parent.right is node else node.parent.right
        if sibling is None or sibling.live_leaf_count == 0:
            continue

        sibling_left, sibling_right = full_leaf_range(sibling.index, tree_height)
        left_rank = bisect.bisect_left(occupied_leaves, sibling_left)
        right_rank = bisect.bisect_right(occupied_leaves, sibling_right) - 1
        if left_rank > right_rank:
            continue

        proof_nodes.append(
            ProofNode(
                index=node.index,
                depth=node.depth,
                interval_left=left_rank,
                interval_right=right_rank,
                weight=sibling.live_leaf_count,
                covers_leaves=list(occupied_leaves[left_rank : right_rank + 1]),
            )
        )

    return proof_nodes


def contains(a: ProofNode, b: ProofNode) -> bool:
    return a.interval_left <= b.interval_left and a.interval_right >= b.interval_right


def build_interval_forest(proof_nodes: List[ProofNode]) -> List[ProofNode]:
    ordered = sorted(
        proof_nodes,
        key=lambda item: (
            item.interval_left,
            -(item.interval_right - item.interval_left),
            item.index,
        ),
    )

    roots: List[ProofNode] = []
    stack: List[ProofNode] = []
    for node in ordered:
        node.parent = None
        node.children = []
        while stack and not contains(stack[-1], node):
            stack.pop()
        if stack:
            node.parent = stack[-1]
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def max_chain_length(roots: Sequence[ProofNode]) -> int:
    def depth(node: ProofNode) -> int:
        if not node.children:
            return 1
        return 1 + max(depth(child) for child in node.children)

    return max((depth(root) for root in roots), default=0)


def assign_colors(
    roots: Sequence[ProofNode],
    num_colors: int,
    total_nodes: int,
    rebalance_rounds: int,
) -> Tuple[List[int], List[int]]:
    count_loads = [0] * num_colors
    weight_loads = [0] * num_colors
    base, remainder = divmod(total_nodes, num_colors)
    target_counts = [base + (1 if i < remainder else 0) for i in range(num_colors)]

    def greedy_key(color: int) -> Tuple[int, int, int, int]:
        idx = color - 1
        return (
            weight_loads[idx],
            count_loads[idx],
            abs(count_loads[idx] - target_counts[idx]),
            color,
        )

    def assign(node: ProofNode, color: int) -> None:
        if node.color is not None:
            old_idx = node.color - 1
            count_loads[old_idx] -= 1
            weight_loads[old_idx] -= node.weight
        node.color = color
        new_idx = color - 1
        count_loads[new_idx] += 1
        weight_loads[new_idx] += node.weight

    def greedy(node: ProofNode, ancestor_colors: set[int]) -> None:
        available = [c for c in range(1, num_colors + 1) if c not in ancestor_colors]
        chosen = min(available, key=greedy_key)
        assign(node, chosen)
        next_colors = set(ancestor_colors)
        next_colors.add(chosen)
        children = sorted(node.children, key=lambda item: item.weight, reverse=True)
        for child in children:
            greedy(child, next_colors)

    def can_recolor(node: ProofNode, new_color: int) -> bool:
        current = node.parent
        while current is not None:
            if current.color == new_color:
                return False
            current = current.parent
        stack = list(node.children)
        while stack:
            current = stack.pop()
            if current.color == new_color:
                return False
            stack.extend(current.children)
        return True

    def objective(candidate_weight_loads: List[int], candidate_count_loads: List[int]) -> Tuple[int, int, int, int]:
        return (
            max(candidate_weight_loads) - min(candidate_weight_loads),
            max(candidate_count_loads) - min(candidate_count_loads),
            max(candidate_weight_loads),
            max(candidate_count_loads),
        )

    ordered_roots = sorted(roots, key=lambda item: item.weight, reverse=True)
    for root in ordered_roots:
        greedy(root, set())

    for _ in range(rebalance_rounds):
        current_objective = objective(weight_loads, count_loads)
        best_move: Optional[Tuple[ProofNode, int, Tuple[int, int, int, int]]] = None

        colors_desc = sorted(
            range(1, num_colors + 1),
            key=lambda color: (weight_loads[color - 1], count_loads[color - 1]),
            reverse=True,
        )
        colors_asc = list(reversed(colors_desc))

        for heavy in colors_desc:
            candidates = [node for root in roots for node in traverse(root) if node.color == heavy]
            candidates.sort(key=lambda item: (item.weight, item.depth), reverse=True)
            for node in candidates:
                for light in colors_asc:
                    if light == heavy or not can_recolor(node, light):
                        continue
                    candidate_weight_loads = list(weight_loads)
                    candidate_count_loads = list(count_loads)
                    candidate_weight_loads[heavy - 1] -= node.weight
                    candidate_weight_loads[light - 1] += node.weight
                    candidate_count_loads[heavy - 1] -= 1
                    candidate_count_loads[light - 1] += 1
                    candidate_objective = objective(candidate_weight_loads, candidate_count_loads)
                    if candidate_objective < current_objective:
                        if best_move is None or candidate_objective < best_move[2]:
                            best_move = (node, light, candidate_objective)

        if best_move is None:
            break
        assign(best_move[0], best_move[1])

    return count_loads, weight_loads


def traverse(node: ProofNode) -> Iterable[ProofNode]:
    yield node
    for child in node.children:
        yield from traverse(child)


def verify_coloring(
    roots: Sequence[ProofNode],
    occupied_leaves: Sequence[int],
) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    def dfs(node: ProofNode, path_colors: set[int]) -> None:
        next_colors = set(path_colors)
        if node.color is None:
            issues.append(f"Node {node.index} is uncolored.")
        elif node.color in path_colors:
            issues.append(f"Node {node.index} repeats color {node.color} on a proof chain.")
        else:
            next_colors.add(node.color)
        for child in node.children:
            dfs(child, next_colors)

    for root in roots:
        dfs(root, set())

    by_color: Dict[int, List[ProofNode]] = {}
    for root in roots:
        for node in traverse(root):
            if node.color is None:
                continue
            by_color.setdefault(node.color, []).append(node)

    for color, nodes in by_color.items():
        ordered = sorted(nodes, key=lambda item: (item.interval_left, item.interval_right))
        for left, right in zip(ordered, ordered[1:]):
            if left.interval_right >= right.interval_left:
                issues.append(
                    f"Color {color} has overlapping intervals "
                    f"[{left.interval_left},{left.interval_right}] and [{right.interval_left},{right.interval_right}]."
                )

    leaf_ranks = {leaf: rank for rank, leaf in enumerate(occupied_leaves)}
    for leaf, rank in leaf_ranks.items():
        colors_on_path: List[int] = []
        nodes_on_path: List[int] = []
        for root in roots:
            for node in traverse(root):
                if node.interval_left <= rank <= node.interval_right:
                    if node.color is not None:
                        colors_on_path.append(node.color)
                    nodes_on_path.append(node.index)
        if len(colors_on_path) != len(set(colors_on_path)):
            issues.append(f"Leaf {leaf} hits duplicate colors on proof nodes {nodes_on_path}.")

    return len(issues) == 0, issues


def color_name(color: int) -> str:
    return f"C{color}"


def query_view(proof_nodes: Sequence[ProofNode], occupied_leaves: Sequence[int], leaf: int, num_colors: int) -> List[str]:
    rank = occupied_leaves.index(leaf)
    answer: Dict[int, int] = {}
    for node in proof_nodes:
        if node.color is None:
            continue
        if node.interval_left <= rank <= node.interval_right:
            answer[node.color] = node.index
    return [f"{color_name(color)}->{answer.get(color, 'dummy')}" for color in range(1, num_colors + 1)]


def tree_position(node_index: int, tree_height: int) -> Tuple[float, float]:
    depth = node_index.bit_length() - 1
    level_pos = node_index - (1 << depth)
    span = 1 << (tree_height - depth)
    left_slot = level_pos * span
    right_slot = left_slot + span - 1
    x = (left_slot + right_slot) / 2.0
    y = -depth
    return x, y


def draw_tree(
    tree_height: int,
    occupied_leaves: Sequence[int],
    proof_nodes: Sequence[ProofNode],
    count_loads: Sequence[int],
    weight_loads: Sequence[int],
    output_prefix: Path,
    sample_queries: Sequence[Tuple[int, List[str]]],
) -> None:
    total_leaves = 1 << tree_height
    total_nodes = (1 << (tree_height + 1)) - 1

    proof_color_map = {node.index: node.color for node in proof_nodes if node.color is not None}
    occupied_set = set(occupied_leaves)
    active_set = {index // (1 << (tree_height - (index.bit_length() - 1))) for index in []}
    raw_real_nodes: set[int] = set()
    for leaf in occupied_leaves:
        current = leaf
        while current >= 1:
            raw_real_nodes.add(current)
            current //= 2

    fig = plt.figure(figsize=(24, 12))
    ax_tree = fig.add_axes([0.04, 0.08, 0.68, 0.84])
    ax_info = fig.add_axes([0.75, 0.08, 0.23, 0.84])
    ax_info.axis("off")

    # Draw edges
    for parent in range(1, 1 << tree_height):
        for child in (parent * 2, parent * 2 + 1):
            x1, y1 = tree_position(parent, tree_height)
            x2, y2 = tree_position(child, tree_height)
            ax_tree.plot([x1, x2], [y1, y2], color="#d0d0d0", linewidth=0.18, zorder=1)

    # Default nodes
    default_x: List[float] = []
    default_y: List[float] = []
    real_x: List[float] = []
    real_y: List[float] = []
    occupied_x: List[float] = []
    occupied_y: List[float] = []
    colored_points: Dict[int, Tuple[List[float], List[float]]] = {}

    for node_index in range(1, total_nodes + 1):
        x, y = tree_position(node_index, tree_height)
        if node_index in proof_color_map:
            color = proof_color_map[node_index]
            xs, ys = colored_points.setdefault(color, ([], []))
            xs.append(x)
            ys.append(y)
        elif node_index in occupied_set:
            occupied_x.append(x)
            occupied_y.append(y)
        elif node_index in raw_real_nodes:
            real_x.append(x)
            real_y.append(y)
        else:
            default_x.append(x)
            default_y.append(y)

    ax_tree.scatter(default_x, default_y, s=4, c="#d9d9d9", edgecolors="none", zorder=2)
    ax_tree.scatter(real_x, real_y, s=10, facecolors="white", edgecolors="#777777", linewidths=0.25, zorder=3)
    ax_tree.scatter(occupied_x, occupied_y, s=12, c="#222222", edgecolors="none", zorder=4)

    for color, (xs, ys) in sorted(colored_points.items()):
        ax_tree.scatter(
            xs,
            ys,
            s=24,
            c=COLOR_PALETTE.get(color, "#ff6f61"),
            edgecolors="#111111",
            linewidths=0.35,
            zorder=5,
            label=color_name(color),
        )

    ax_tree.set_title(
        f"Complete Merkle tree (height {tree_height}) with stored proof-bearing nodes highlighted",
        fontsize=14,
    )
    ax_tree.set_xlim(-10, total_leaves + 10)
    ax_tree.set_ylim(-(tree_height + 0.9), 0.8)
    ax_tree.set_xticks([])
    ax_tree.set_yticks([])
    for spine in ax_tree.spines.values():
        spine.set_visible(False)

    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#d9d9d9", markeredgecolor="none", markersize=6, label="default empty node"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor="#777777", markersize=6, label="real but not stored"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#222222", markeredgecolor="none", markersize=6, label="occupied leaf"),
    ]
    for color in sorted(colored_points):
        legend_handles.append(
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=COLOR_PALETTE.get(color, "#ff6f61"),
                markeredgecolor="#111111",
                markersize=7,
                label=f"stored node {color_name(color)}",
            )
        )
    ax_tree.legend(handles=legend_handles, loc="upper left", fontsize=9, frameon=False)

    summary_lines = [
        "Example settings",
        f"height = {tree_height}",
        f"total leaves = {total_leaves}",
        f"occupied leaves = {len(occupied_leaves)}",
        f"bottom-layer slots = {[heap_leaf_to_slot(leaf, tree_height) for leaf in occupied_leaves]}",
        f"sparsity = {(1.0 - len(occupied_leaves) / total_leaves) * 100:.1f}%",
        "",
        "Coloring result",
        f"colors = {len(count_loads)}",
        f"stored proof nodes = {len(proof_nodes)}",
        f"count loads = {list(count_loads)}",
        f"weight loads = {list(weight_loads)}",
        f"count gap = {max(count_loads) - min(count_loads)}",
        f"weight gap = {max(weight_loads) - min(weight_loads)}",
        "",
        "Sample batch-PIR views",
    ]
    for leaf, plan in sample_queries:
        summary_lines.append(
            f"leaf heap={leaf} slot={heap_leaf_to_slot(leaf, tree_height)}: {', '.join(plan)}"
        )

    ax_info.text(
        0.0,
        1.0,
        "\n".join(summary_lines),
        va="top",
        ha="left",
        fontsize=11,
        family="monospace",
    )

    png_path = output_prefix.with_suffix(".png")
    pdf_path = output_prefix.with_suffix(".pdf")
    fig.savefig(png_path, dpi=220, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a full sparse SMT example and figure.")
    parser.add_argument("--height", type=int, default=10, help="Tree height.")
    parser.add_argument(
        "--sparsity",
        type=float,
        default=0.60,
        help="Leaf sparsity. For example, 0.60 means 60%% empty leaves.",
    )
    parser.add_argument("--seed", type=int, default=20260407, help="Random seed for occupied leaves.")
    parser.add_argument("--rounds", type=int, default=400, help="Maximum local rebalance rounds.")
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=Path("height10_sparsity60_full_tree_example"),
        help="Prefix for generated outputs.",
    )
    args = parser.parse_args()

    occupied = generate_occupied_leaves(args.height, args.sparsity, args.seed)
    helper = FixedSparseMerkleColoring(original_height=args.height, occupied_leaves=occupied)

    proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, args.height)
    roots = build_interval_forest(proof_nodes)
    num_colors = max_chain_length(roots)
    count_loads, weight_loads = assign_colors(
        roots=roots,
        num_colors=num_colors,
        total_nodes=len(proof_nodes),
        rebalance_rounds=args.rounds,
    )
    valid, issues = verify_coloring(roots, occupied)

    flat_nodes = sorted(
        proof_nodes,
        key=lambda item: (item.color if item.color is not None else 999, item.depth, item.index),
    )
    sample_leaf_positions = [occupied[0], occupied[len(occupied) // 2], occupied[-1]]
    sample_queries = [(leaf, query_view(flat_nodes, occupied, leaf, num_colors)) for leaf in sample_leaf_positions]

    output_prefix = args.output_prefix
    draw_tree(
        tree_height=args.height,
        occupied_leaves=occupied,
        proof_nodes=flat_nodes,
        count_loads=count_loads,
        weight_loads=weight_loads,
        output_prefix=output_prefix,
        sample_queries=sample_queries,
    )

    json_summary = {
        "height": args.height,
        "sparsity": args.sparsity,
        "seed": args.seed,
        "total_leaves": 1 << args.height,
        "occupied_leaf_count": len(occupied),
        "occupied_leaf_heap_indices": occupied,
        "occupied_leaf_slots_0_based": [heap_leaf_to_slot(leaf, args.height) for leaf in occupied],
        "occupied_leaves": occupied,
        "stored_proof_node_count": len(proof_nodes),
        "num_colors": num_colors,
        "count_loads": count_loads,
        "weight_loads": weight_loads,
        "count_gap": max(count_loads) - min(count_loads),
        "weight_gap": max(weight_loads) - min(weight_loads),
        "valid": valid,
        "issues": issues,
        "sample_queries": [
            {
                "leaf_heap_index": leaf,
                "leaf_slot_0_based": heap_leaf_to_slot(leaf, args.height),
                "plan": plan,
            }
            for leaf, plan in sample_queries
        ],
        "proof_nodes": [
            {
                "index": node.index,
                "depth": node.depth,
                "color": node.color,
                "weight": node.weight,
                "interval_rank": [node.interval_left, node.interval_right],
                "covers_leaves": node.covers_leaves,
            }
            for node in flat_nodes
        ],
    }
    output_prefix.with_suffix(".json").write_text(json.dumps(json_summary, indent=2), encoding="utf-8")

    markdown_lines = [
        f"# Height-{args.height} Sparse SMT Example",
        "",
        f"- `height = {args.height}`",
        f"- `sparsity = {args.sparsity:.2f}` (interpreted as {args.sparsity * 100:.0f}% empty leaves)",
        f"- `seed = {args.seed}`",
        f"- `total leaves = {1 << args.height}`",
        f"- `occupied leaves = {len(occupied)}`",
        f"- `occupied leaf heap indices = {occupied}`",
        f"- `occupied leaf slots (0-based) = {[heap_leaf_to_slot(leaf, args.height) for leaf in occupied]}`",
        f"- `stored proof-bearing nodes = {len(proof_nodes)}`",
        f"- `num colors = {num_colors}`",
        f"- `count loads = {count_loads}`",
        f"- `weight loads = {weight_loads}`",
        f"- `count gap = {max(count_loads) - min(count_loads)}`",
        f"- `weight gap = {max(weight_loads) - min(weight_loads)}`",
        f"- `ancestral property valid = {valid}`",
        "",
        "## Sample batch-PIR views",
        "",
    ]
    for leaf, plan in sample_queries:
        markdown_lines.append(
            f"- `leaf heap={leaf}, slot={heap_leaf_to_slot(leaf, args.height)}`: `{', '.join(plan)}`"
        )

    markdown_lines.extend(
        [
            "",
            "## Output files",
            "",
            f"- `{output_prefix.with_suffix('.png').name}`",
            f"- `{output_prefix.with_suffix('.pdf').name}`",
            f"- `{output_prefix.with_suffix('.json').name}`",
        ]
    )
    output_prefix.with_suffix(".md").write_text("\n".join(markdown_lines), encoding="utf-8")

    print("=== Full Sparse SMT Example ===")
    print(f"height={args.height}")
    print(f"sparsity={args.sparsity:.2f} (empty-leaf ratio)")
    print(f"seed={args.seed}")
    print(f"total_leaves={1 << args.height}")
    print(f"occupied_leaves={len(occupied)}")
    print(f"occupied_leaf_heap_indices={occupied}")
    print(f"occupied_leaf_slots_0_based={[heap_leaf_to_slot(leaf, args.height) for leaf in occupied]}")
    print(f"stored_proof_nodes={len(proof_nodes)}")
    print(f"num_colors={num_colors}")
    print(f"count_loads={count_loads}")
    print(f"weight_loads={weight_loads}")
    print(f"count_gap={max(count_loads) - min(count_loads)}")
    print(f"weight_gap={max(weight_loads) - min(weight_loads)}")
    print(f"ancestral_property_valid={valid}")
    if issues:
        print("issues:")
        for issue in issues[:10]:
            print(f"  - {issue}")
    print("sample_queries:")
    for leaf, plan in sample_queries:
        print(
            f"  leaf_heap_index={leaf}, leaf_slot_0_based={heap_leaf_to_slot(leaf, args.height)}: "
            f"{', '.join(plan)}"
        )
    print("outputs:")
    print(f"  {output_prefix.with_suffix('.png')}")
    print(f"  {output_prefix.with_suffix('.pdf')}")
    print(f"  {output_prefix.with_suffix('.json')}")
    print(f"  {output_prefix.with_suffix('.md')}")


if __name__ == "__main__":
    main()
