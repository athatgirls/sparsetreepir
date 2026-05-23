from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Dict, List, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring


def heap_leaf_range(node_index: int, original_height: int) -> Tuple[int, int]:
    depth = node_index.bit_length() - 1
    span = 1 << (original_height - depth)
    return node_index * span, (node_index + 1) * span - 1


def parse_leaves(raw: str) -> List[int]:
    leaves = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not leaves:
        raise ValueError("Leaf list cannot be empty.")
    return leaves


def main() -> None:
    parser = argparse.ArgumentParser(description="Show subdatabase contents for a sparse SMT example.")
    parser.add_argument(
        "--height",
        type=int,
        default=4,
        help="Original SMT height.",
    )
    parser.add_argument(
        "--leaves",
        type=str,
        default="16,17,19,22,28",
        help="Comma-separated occupied heap-index leaves.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=500,
        help="Maximum local rebalance rounds.",
    )
    args = parser.parse_args()

    occupied = parse_leaves(args.leaves)
    coloring = FixedSparseMerkleColoring(original_height=args.height, occupied_leaves=occupied)
    coloring.color(rebalance_rounds=args.rounds)
    ok, violations = coloring.verify_ancestral_property()

    print("=== Sparse SMT Subdatabase Example ===")
    print(f"height={args.height}")
    print(f"occupied_leaves={occupied}")
    print(f"num_colors={coloring.num_colors}")
    print(f"weight_loads={coloring.color_weight_loads}")
    print(f"count_loads={coloring.color_count_loads}")
    print(f"ancestral_property_valid={ok}")
    if not ok:
        for violation in violations:
            print(f"  violation={violation}")
    print()

    by_color: Dict[int, List[str]] = defaultdict(list)
    for node in coloring.nodes_in_preorder:
        if node is coloring.root or node.color is None:
            continue
        left, right = heap_leaf_range(node.index, args.height)
        live = [leaf for leaf in occupied if left <= leaf <= right]
        by_color[node.color].append(
            f"node={node.index}, depth={node.original_depth}, "
            f"range=[{left},{right}], live_leaves={live}, weight={node.leaf_count}"
        )

    print("subdatabases:")
    for color in range(1, coloring.num_colors + 1):
        print(f"  C{color}:")
        for entry in by_color[color]:
            print(f"    {entry}")
        if not by_color[color]:
            print("    <empty>")
    print()

    print("batch_pir_view_for_each_live_leaf:")
    sorted_leaves = sorted(occupied)
    leaf_paths = coloring.leaf_paths()
    for leaf, path in zip(sorted_leaves, leaf_paths):
        query = {node.color: node.index for node in path}
        ordered = [f"C{color}->{query.get(color, 'dummy')}" for color in range(1, coloring.num_colors + 1)]
        print(f"  leaf={leaf}: {', '.join(ordered)}")


if __name__ == "__main__":
    main()
