from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class RawNode:
    index: int
    depth: int
    left: Optional["RawNode"] = None
    right: Optional["RawNode"] = None
    parent: Optional["RawNode"] = None
    occupied_leaf: bool = False
    live_leaf_count: int = 0


@dataclass
class CompressedNode:
    index: int
    original_depth: int
    left: Optional["CompressedNode"] = None
    right: Optional["CompressedNode"] = None
    parent: Optional["CompressedNode"] = None
    color: Optional[int] = None
    leaf_count: int = 0
    max_path_len: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


class FixedSparseMerkleColoring:
    """
    Offline coloring for a fixed sparse Merkle tree.

    The tree is first compressed by contracting unary paths, which matches
    the discussion in Appendix J of TreePIR. Coloring is then performed on
    the compressed tree.

    The algorithm has two phases:
    1. A topology-aware greedy pass that always picks the least loaded
       available color on the current root-to-node path.
    2. A local rebalancing pass that moves nodes from heavy colors to light
       colors whenever doing so preserves the ancestral property.

    The balancing objective is *weighted*: a node contributes weight equal to
    the number of non-empty leaves in its subtree because that node appears in
    exactly that many membership proofs under a uniform query distribution.
    """

    def __init__(self, original_height: int, occupied_leaves: Iterable[int]):
        self.original_height = original_height
        self.occupied_leaves = sorted(set(occupied_leaves))
        self.raw_nodes: Dict[int, RawNode] = {}
        self.root: Optional[CompressedNode] = None
        self.nodes_in_preorder: List[CompressedNode] = []
        self.num_colors: int = 0
        self.color_weight_loads: List[int] = []
        self.color_count_loads: List[int] = []

        self._validate_leaves()
        self._build_raw_tree()
        self._compress_tree()
        self._refresh_metadata()

    def _validate_leaves(self) -> None:
        low = 2 ** self.original_height
        high = 2 ** (self.original_height + 1)
        for leaf in self.occupied_leaves:
            if leaf < low or leaf >= high:
                raise ValueError(
                    f"Leaf {leaf} is outside the heap-index range "
                    f"[{low}, {high - 1}] for height {self.original_height}."
                )

    def _get_or_create_raw(self, index: int) -> RawNode:
        node = self.raw_nodes.get(index)
        if node is None:
            node = RawNode(index=index, depth=index.bit_length() - 1)
            self.raw_nodes[index] = node
        return node

    def _build_raw_tree(self) -> None:
        if not self.occupied_leaves:
            root = self._get_or_create_raw(1)
            root.live_leaf_count = 0
            return

        for leaf in self.occupied_leaves:
            current = self._get_or_create_raw(leaf)
            current.occupied_leaf = True
            current.live_leaf_count = 1

            while current.index > 1:
                parent_index = current.index // 2
                parent = self._get_or_create_raw(parent_index)
                current.parent = parent
                if current.index % 2 == 0:
                    parent.left = current
                else:
                    parent.right = current
                current = parent

        self._populate_live_leaf_counts(self.raw_nodes[1])

    def _populate_live_leaf_counts(self, node: Optional[RawNode]) -> int:
        if node is None:
            return 0

        if node.occupied_leaf and node.left is None and node.right is None:
            node.live_leaf_count = 1
            return 1

        left_count = self._populate_live_leaf_counts(node.left)
        right_count = self._populate_live_leaf_counts(node.right)
        node.live_leaf_count = left_count + right_count + (
            1 if node.occupied_leaf and node.left is None and node.right is None else 0
        )
        return node.live_leaf_count

    def _compress_tree(self) -> None:
        raw_root = self.raw_nodes.get(1)
        if raw_root is None:
            self.root = None
            return
        self.root = self._compress_subtree(raw_root)

    def _compress_subtree(self, raw: Optional[RawNode]) -> Optional[CompressedNode]:
        if raw is None or raw.live_leaf_count == 0:
            return None

        left = self._compress_subtree(raw.left)
        right = self._compress_subtree(raw.right)

        if left is None and right is None:
            return CompressedNode(index=raw.index, original_depth=raw.depth)

        if left is None:
            return right

        if right is None:
            return left

        node = CompressedNode(index=raw.index, original_depth=raw.depth, left=left, right=right)
        left.parent = node
        right.parent = node
        return node

    def _refresh_metadata(self) -> None:
        self.nodes_in_preorder = []
        if self.root is None:
            self.num_colors = 0
            self.color_weight_loads = []
            self.color_count_loads = []
            return

        self._compute_leaf_counts_and_heights(self.root)
        self._collect_preorder(self.root)
        self.num_colors = max(1, self.root.max_path_len)
        self.color_weight_loads = [0] * self.num_colors
        self.color_count_loads = [0] * self.num_colors

    def _compute_leaf_counts_and_heights(self, node: CompressedNode) -> Tuple[int, int]:
        if node.is_leaf:
            node.leaf_count = 1
            node.max_path_len = 0
            return 1, 0

        left_leaves, left_height = self._compute_leaf_counts_and_heights(node.left)  # type: ignore[arg-type]
        right_leaves, right_height = self._compute_leaf_counts_and_heights(node.right)  # type: ignore[arg-type]
        node.leaf_count = left_leaves + right_leaves
        node.max_path_len = 1 + max(left_height, right_height)
        return node.leaf_count, node.max_path_len

    def _collect_preorder(self, node: CompressedNode) -> None:
        self.nodes_in_preorder.append(node)
        children = [child for child in (node.left, node.right) if child is not None]
        children.sort(key=lambda item: item.leaf_count, reverse=True)
        for child in children:
            self._collect_preorder(child)

    def clear_colors(self) -> None:
        for node in self.nodes_in_preorder:
            node.color = None
        self.color_weight_loads = [0] * self.num_colors
        self.color_count_loads = [0] * self.num_colors

    def color(self, rebalance_rounds: int = 500) -> None:
        if self.root is None:
            return

        self.clear_colors()
        self._initial_weighted_greedy(self.root, ancestor_colors=set())
        self._local_rebalance(max_rounds=rebalance_rounds)

    def _initial_weighted_greedy(
        self, node: CompressedNode, ancestor_colors: Set[int]
    ) -> None:
        if node is not self.root:
            available = [c for c in range(1, self.num_colors + 1) if c not in ancestor_colors]
            if not available:
                raise RuntimeError(
                    f"No available color for node {node.index}; "
                    "increase num_colors or inspect the compressed tree."
                )

            chosen = min(
                available,
                key=lambda color: (
                    self.color_weight_loads[color - 1],
                    self.color_count_loads[color - 1],
                    color,
                ),
            )
            self._assign_color(node, chosen)
            next_ancestor_colors = set(ancestor_colors)
            next_ancestor_colors.add(chosen)
        else:
            next_ancestor_colors = set(ancestor_colors)

        children = [child for child in (node.left, node.right) if child is not None]
        children.sort(key=lambda item: item.leaf_count, reverse=True)
        for child in children:
            self._initial_weighted_greedy(child, next_ancestor_colors)

    def _assign_color(self, node: CompressedNode, color: int) -> None:
        if node.color is not None:
            old = node.color
            self.color_weight_loads[old - 1] -= node.leaf_count
            self.color_count_loads[old - 1] -= 1
        node.color = color
        self.color_weight_loads[color - 1] += node.leaf_count
        self.color_count_loads[color - 1] += 1

    def _local_rebalance(self, max_rounds: int) -> None:
        if self.num_colors <= 1:
            return

        for _ in range(max_rounds):
            move = self._find_best_recolor_move()
            if move is None:
                break
            node, new_color = move
            self._assign_color(node, new_color)

    def _find_best_recolor_move(self) -> Optional[Tuple[CompressedNode, int]]:
        current_objective = self._objective()
        best_move: Optional[Tuple[CompressedNode, int]] = None
        best_objective = current_objective

        color_order_desc = sorted(
            range(1, self.num_colors + 1),
            key=lambda color: (
                self.color_weight_loads[color - 1],
                self.color_count_loads[color - 1],
            ),
            reverse=True,
        )
        color_order_asc = list(reversed(color_order_desc))

        for heavy_color in color_order_desc:
            nodes = [
                node
                for node in self.nodes_in_preorder
                if node is not self.root and node.color == heavy_color
            ]
            nodes.sort(key=lambda item: (item.leaf_count, item.original_depth), reverse=True)

            for node in nodes:
                for light_color in color_order_asc:
                    if light_color == heavy_color:
                        continue
                    if not self._can_recolor(node, light_color):
                        continue

                    candidate = self._objective_after_move(node, light_color)
                    if candidate < best_objective:
                        best_objective = candidate
                        best_move = (node, light_color)

        return best_move

    def _objective(self) -> Tuple[int, int, int, int]:
        return (
            max(self.color_weight_loads) - min(self.color_weight_loads),
            max(self.color_count_loads) - min(self.color_count_loads),
            max(self.color_weight_loads),
            max(self.color_count_loads),
        )

    def _objective_after_move(
        self, node: CompressedNode, new_color: int
    ) -> Tuple[int, int, int, int]:
        old_color = node.color
        if old_color is None:
            raise ValueError("Cannot evaluate recoloring for an uncolored node.")

        weight_loads = list(self.color_weight_loads)
        count_loads = list(self.color_count_loads)
        weight_loads[old_color - 1] -= node.leaf_count
        weight_loads[new_color - 1] += node.leaf_count
        count_loads[old_color - 1] -= 1
        count_loads[new_color - 1] += 1
        return (
            max(weight_loads) - min(weight_loads),
            max(count_loads) - min(count_loads),
            max(weight_loads),
            max(count_loads),
        )

    def _can_recolor(self, node: CompressedNode, new_color: int) -> bool:
        if node.color == new_color:
            return False

        current = node.parent
        while current is not None:
            if current.color == new_color:
                return False
            current = current.parent

        stack = [child for child in (node.left, node.right) if child is not None]
        while stack:
            current = stack.pop()
            if current.color == new_color:
                return False
            if current.left is not None:
                stack.append(current.left)
            if current.right is not None:
                stack.append(current.right)
        return True

    def verify_ancestral_property(self) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        if self.root is None:
            return True, violations

        self._verify_dfs(self.root, set(), violations)
        return len(violations) == 0, violations

    def _verify_dfs(
        self, node: CompressedNode, path_colors: Set[int], violations: List[str]
    ) -> None:
        next_path_colors = set(path_colors)
        if node is not self.root:
            if node.color is None:
                violations.append(f"Node {node.index} is missing a color.")
            elif node.color in path_colors:
                violations.append(
                    f"Ancestor conflict on node {node.index}: color {node.color} repeats on a path."
                )
            else:
                next_path_colors.add(node.color)

        for child in (node.left, node.right):
            if child is not None:
                self._verify_dfs(child, next_path_colors, violations)

    def leaf_paths(self) -> List[List[CompressedNode]]:
        if self.root is None:
            return []
        leaves: List[List[CompressedNode]] = []
        self._collect_leaf_paths(self.root, [], leaves)
        return leaves

    def _collect_leaf_paths(
        self,
        node: CompressedNode,
        prefix: List[CompressedNode],
        leaves: List[List[CompressedNode]],
    ) -> None:
        next_prefix = list(prefix)
        if node is not self.root:
            next_prefix.append(node)

        if node.is_leaf:
            leaves.append(next_prefix)
            return

        for child in (node.left, node.right):
            if child is not None:
                self._collect_leaf_paths(child, next_prefix, leaves)

    def metrics(self) -> Dict[str, object]:
        total_colored_nodes = sum(self.color_count_loads)
        total_weight = sum(self.color_weight_loads)
        target_count = total_colored_nodes / self.num_colors if self.num_colors else 0.0
        target_weight = total_weight / self.num_colors if self.num_colors else 0.0
        path_lengths = [len(path) for path in self.leaf_paths()]

        return {
            "num_colors": self.num_colors,
            "total_colored_nodes": total_colored_nodes,
            "total_weight": total_weight,
            "count_loads": list(self.color_count_loads),
            "weight_loads": list(self.color_weight_loads),
            "count_gap": max(self.color_count_loads) - min(self.color_count_loads)
            if self.color_count_loads
            else 0,
            "weight_gap": max(self.color_weight_loads) - min(self.color_weight_loads)
            if self.color_weight_loads
            else 0,
            "target_count": target_count,
            "target_weight": target_weight,
            "max_path_length": max(path_lengths) if path_lengths else 0,
            "min_path_length": min(path_lengths) if path_lengths else 0,
            "dummy_queries_needed": [
                self.num_colors - path_length for path_length in path_lengths
            ],
        }

    def describe(self) -> str:
        metrics = self.metrics()
        lines = [
            f"Compressed tree colors: {metrics['num_colors']}",
            f"Colored nodes: {metrics['total_colored_nodes']}",
            f"Weight loads: {metrics['weight_loads']}",
            f"Count loads: {metrics['count_loads']}",
            f"Weight gap: {metrics['weight_gap']}",
            f"Count gap: {metrics['count_gap']}",
            f"Proof lengths after compression: min={metrics['min_path_length']}, max={metrics['max_path_length']}",
            f"Dummy queries needed per proof: {metrics['dummy_queries_needed']}",
        ]
        return "\n".join(lines)

    def layer_baseline_metrics(self) -> Dict[str, object]:
        """
        Baseline for comparison: use compressed depth as the color.

        This is valid whenever num_colors equals the maximum compressed proof
        length, but it ignores the asymmetric query weights created by sparsity.
        """
        baseline_weight_loads = [0] * self.num_colors
        baseline_count_loads = [0] * self.num_colors

        def visit(node: CompressedNode, depth: int) -> None:
            if node is not self.root:
                color = depth
                baseline_weight_loads[color - 1] += node.leaf_count
                baseline_count_loads[color - 1] += 1
            for child in (node.left, node.right):
                if child is not None:
                    visit(child, depth + 1)

        if self.root is not None:
            visit(self.root, 0)

        return {
            "weight_loads": baseline_weight_loads,
            "count_loads": baseline_count_loads,
            "weight_gap": max(baseline_weight_loads) - min(baseline_weight_loads)
            if baseline_weight_loads
            else 0,
            "count_gap": max(baseline_count_loads) - min(baseline_count_loads)
            if baseline_count_loads
            else 0,
        }


def demo() -> None:
    # Example adapted from Appendix J of TreePIR.
    occupied = [16, 17, 19, 22, 28]
    coloring = FixedSparseMerkleColoring(original_height=4, occupied_leaves=occupied)
    coloring.color(rebalance_rounds=500)

    ok, violations = coloring.verify_ancestral_property()
    baseline = coloring.layer_baseline_metrics()
    print("=== Fixed Sparse SMT Coloring Demo ===")
    print(f"Occupied leaves: {occupied}")
    print(coloring.describe())
    print(
        "Layer baseline:"
        f" weight_loads={baseline['weight_loads']},"
        f" count_loads={baseline['count_loads']},"
        f" weight_gap={baseline['weight_gap']},"
        f" count_gap={baseline['count_gap']}"
    )
    print(f"Ancestral property valid: {ok}")
    if not ok:
        print("Violations:")
        for violation in violations:
            print(f"  - {violation}")
    print("Leaf paths (node_index:color):")
    for path in coloring.leaf_paths():
        encoded = " -> ".join(f"{node.index}:C{node.color}" for node in path)
        print(f"  {encoded}")


if __name__ == "__main__":
    demo()
