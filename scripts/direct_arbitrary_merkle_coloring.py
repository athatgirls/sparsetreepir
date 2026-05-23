from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class MerkleNode:
    label: str
    left: Optional["MerkleNode"] = None
    right: Optional["MerkleNode"] = None
    parent: Optional["MerkleNode"] = None
    leaf_start: int = 0
    leaf_end: int = -1
    leaf_count: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


@dataclass
class ProofIntervalNode:
    """
    A direct proof-bearing vertex on the original Merkle tree.

    For a non-root node u with sibling s, the node u appears in the Merkle
    proof of exactly the leaves in subtree(s). That set is a contiguous leaf
    interval [l(u), r(u)] in left-to-right order.
    """

    merkle_node: MerkleNode
    interval_left: int
    interval_right: int
    weight: int
    color: Optional[int] = None
    parent: Optional["ProofIntervalNode"] = None
    children: List["ProofIntervalNode"] = field(default_factory=list)


class DirectArbitraryMerkleColoring:
    """
    Direct coloring on the original Merkle tree.

    Core idea:
    - Keep the swapped-tree view only logically.
    - Do not materialize a full swapped/perfect tree.
    - Color only the real proof-bearing nodes directly.
    - Two nodes conflict iff they can appear in the same Merkle proof.
    - A node u appears in the proof of exactly the leaves in sibling(u),
      giving a contiguous interval over the leaf order.
    - Because these intervals form a laminar family, the conflict relation is
      an inclusion forest. Coloring that forest is enough to ensure one real
      node per color per swapped proof path.
    """

    def __init__(self, root: MerkleNode):
        self.root = root
        self.leaf_order: List[MerkleNode] = []
        self.leaf_rank: Dict[str, int] = {}
        self.proof_nodes: List[ProofIntervalNode] = []
        self.interval_roots: List[ProofIntervalNode] = []
        self.num_colors: int = 0
        self.color_weight_loads: List[int] = []
        self.color_count_loads: List[int] = []
        self.target_count_loads: List[int] = []
        self._strategy: str = "weighted"

        self._annotate_leaf_ranges()
        self._build_proof_intervals()
        self._build_interval_forest()
        self._refresh_color_state()

    @staticmethod
    def from_nested(structure: Any) -> "DirectArbitraryMerkleColoring":
        counter = {"internal": 0}

        def build(obj: Any) -> MerkleNode:
            if not isinstance(obj, tuple):
                return MerkleNode(label=str(obj))
            if len(obj) != 2:
                raise ValueError("Each internal node must be a binary tuple of length 2.")
            counter["internal"] += 1
            node = MerkleNode(label=f"I{counter['internal']}")
            node.left = build(obj[0])
            node.right = build(obj[1])
            node.left.parent = node
            node.right.parent = node
            return node

        return DirectArbitraryMerkleColoring(build(structure))

    def _annotate_leaf_ranges(self) -> None:
        self.leaf_order = []
        self.leaf_rank = {}

        def dfs(node: MerkleNode) -> Tuple[int, int, int]:
            if node.is_leaf:
                rank = len(self.leaf_order)
                self.leaf_order.append(node)
                self.leaf_rank[node.label] = rank
                node.leaf_start = rank
                node.leaf_end = rank
                node.leaf_count = 1
                return rank, rank, 1

            if node.left is None or node.right is None:
                raise ValueError(
                    f"Node {node.label} is not binary. This prototype expects a binary Merkle tree."
                )

            left_start, left_end, left_count = dfs(node.left)
            right_start, right_end, right_count = dfs(node.right)
            node.leaf_start = left_start
            node.leaf_end = right_end
            node.leaf_count = left_count + right_count
            return node.leaf_start, node.leaf_end, node.leaf_count

        dfs(self.root)

    def _build_proof_intervals(self) -> None:
        self.proof_nodes = []

        def walk(node: MerkleNode) -> None:
            if node.parent is not None:
                sibling = node.parent.left if node.parent.right is node else node.parent.right
                if sibling is not None:
                    self.proof_nodes.append(
                        ProofIntervalNode(
                            merkle_node=node,
                            interval_left=sibling.leaf_start,
                            interval_right=sibling.leaf_end,
                            weight=sibling.leaf_count,
                        )
                    )
            if node.left is not None:
                walk(node.left)
            if node.right is not None:
                walk(node.right)

        walk(self.root)

    def _build_interval_forest(self) -> None:
        self.interval_roots = []
        for node in self.proof_nodes:
            node.parent = None
            node.children = []

        ordered = sorted(
            self.proof_nodes,
            key=lambda item: (item.interval_left, -(item.interval_right - item.interval_left), item.merkle_node.label),
        )

        stack: List[ProofIntervalNode] = []
        for node in ordered:
            while stack and not self._contains(stack[-1], node):
                stack.pop()

            if stack:
                node.parent = stack[-1]
                stack[-1].children.append(node)
            else:
                self.interval_roots.append(node)

            stack.append(node)

    @staticmethod
    def _contains(a: ProofIntervalNode, b: ProofIntervalNode) -> bool:
        return a.interval_left <= b.interval_left and a.interval_right >= b.interval_right

    def _refresh_color_state(self) -> None:
        self.num_colors = self._max_chain_length()
        self.color_weight_loads = [0] * self.num_colors
        self.color_count_loads = [0] * self.num_colors
        if self.num_colors == 0:
            self.target_count_loads = []
            return
        base, remainder = divmod(len(self.proof_nodes), self.num_colors)
        self.target_count_loads = [
            base + (1 if color_index < remainder else 0)
            for color_index in range(self.num_colors)
        ]

    def _max_chain_length(self) -> int:
        def depth(node: ProofIntervalNode) -> int:
            if not node.children:
                return 1
            return 1 + max(depth(child) for child in node.children)

        if not self.interval_roots:
            return 0
        return max(depth(root) for root in self.interval_roots)

    def clear_colors(self) -> None:
        for node in self.proof_nodes:
            node.color = None
        self.color_weight_loads = [0] * self.num_colors
        self.color_count_loads = [0] * self.num_colors

    def minimum_batch_width(self) -> int:
        return self.num_colors

    def depth_color(self) -> None:
        """
        Assign the exact minimum number of colors by forest depth.

        In the laminar interval forest, every conflict is an ancestor-descendant
        relation. Therefore, coloring every node by its depth in the forest is a
        valid coloring that uses exactly the maximum root-to-leaf chain length.
        """

        self.clear_colors()

        def dfs(node: ProofIntervalNode, depth: int) -> None:
            self._assign_color(node, depth)
            for child in node.children:
                dfs(child, depth + 1)

        for root in self.interval_roots:
            dfs(root, 1)

    def color(self, rebalance_rounds: int = 500, strategy: str = "weighted") -> None:
        if self.num_colors == 0:
            return

        if strategy not in {"weighted", "count_balanced", "hybrid"}:
            raise ValueError("strategy must be 'weighted', 'count_balanced', or 'hybrid'.")

        self._strategy = strategy
        self.clear_colors()
        roots = sorted(self.interval_roots, key=lambda item: item.weight, reverse=True)
        for root in roots:
            self._greedy_color(root, ancestor_colors=set())
        self._local_rebalance(rebalance_rounds)

    def _greedy_color(self, node: ProofIntervalNode, ancestor_colors: set[int]) -> None:
        available = [c for c in range(1, self.num_colors + 1) if c not in ancestor_colors]
        if self._strategy == "hybrid":
            chosen = min(available, key=lambda color: self._hybrid_greedy_key(node, color))
        else:
            chosen = min(available, key=self._greedy_key)
        self._assign_color(node, chosen)

        next_ancestor_colors = set(ancestor_colors)
        next_ancestor_colors.add(chosen)
        children = sorted(node.children, key=lambda item: item.weight, reverse=True)
        for child in children:
            self._greedy_color(child, next_ancestor_colors)

    def _assign_color(self, node: ProofIntervalNode, color: int) -> None:
        if node.color is not None:
            old = node.color
            self.color_weight_loads[old - 1] -= node.weight
            self.color_count_loads[old - 1] -= 1
        node.color = color
        self.color_weight_loads[color - 1] += node.weight
        self.color_count_loads[color - 1] += 1

    def _hybrid_greedy_key(self, node: ProofIntervalNode, color: int) -> Tuple[float, int, int, int, int]:
        color_index = color - 1
        candidate_weight_loads = list(self.color_weight_loads)
        candidate_count_loads = list(self.color_count_loads)
        candidate_weight_loads[color_index] += node.weight
        candidate_count_loads[color_index] += 1
        hybrid_objective = self._objective(candidate_weight_loads, candidate_count_loads)
        return (
            hybrid_objective[0],
            hybrid_objective[1],
            hybrid_objective[2],
            abs(candidate_count_loads[color_index] - self.target_count_loads[color_index]),
            color,
        )

    def _local_rebalance(self, max_rounds: int) -> None:
        for _ in range(max_rounds):
            move = self._best_move()
            if move is None:
                break
            node, new_color = move
            self._assign_color(node, new_color)

    def _greedy_key(self, color: int) -> Tuple[int, int, int, int]:
        color_index = color - 1
        if self._strategy == "count_balanced":
            return (
                self.color_count_loads[color_index] - self.target_count_loads[color_index],
                self.color_count_loads[color_index],
                self.color_weight_loads[color_index],
                color,
            )
        return (
            self.color_weight_loads[color_index],
            self.color_count_loads[color_index],
            abs(self.color_count_loads[color_index] - self.target_count_loads[color_index]),
            color,
        )

    def _hybrid_score(self, weight_loads: List[int], count_loads: List[int]) -> float:
        if not weight_loads or not count_loads:
            return 0.0
        avg_weight = max(1.0, sum(weight_loads) / len(weight_loads))
        avg_count = max(1.0, sum(count_loads) / len(count_loads))
        weight_gap = max(weight_loads) - min(weight_loads)
        count_gap = max(count_loads) - min(count_loads)
        return (weight_gap / avg_weight) + (count_gap / avg_count)

    def hybrid_score_from_loads(self, weight_loads: List[int], count_loads: List[int]) -> float:
        return self._hybrid_score(weight_loads, count_loads)

    def hybrid_score(self) -> float:
        return self._hybrid_score(self.color_weight_loads, self.color_count_loads)

    def universal_lower_bounds(self) -> Dict[str, float]:
        """
        Universal bicriteria lower bounds for any m-color partition.

        These bounds ignore additional ancestral constraints, so they apply a
        fortiori to every valid ancestral coloring.
        """

        if self.num_colors == 0 or not self.proof_nodes:
            return {
                "avg_weight": 0.0,
                "avg_count": 0.0,
                "count_gap_lb": 0.0,
                "weight_gap_lb": 0.0,
                "hybrid_lb": 0.0,
                "total_weight": 0.0,
                "total_count": 0.0,
                "max_node_weight": 0.0,
            }

        total_count = len(self.proof_nodes)
        total_weight = sum(node.weight for node in self.proof_nodes)
        avg_count = total_count / self.num_colors
        avg_weight = total_weight / self.num_colors
        max_node_weight = max(node.weight for node in self.proof_nodes)

        count_gap_lb = 0.0 if total_count % self.num_colors == 0 else 1.0
        weight_gap_lb = float(
            max(math.ceil(total_weight / self.num_colors), max_node_weight)
            - math.floor(total_weight / self.num_colors)
        )
        hybrid_lb = 0.0
        if avg_count > 0:
            hybrid_lb += count_gap_lb / avg_count
        if avg_weight > 0:
            hybrid_lb += weight_gap_lb / avg_weight

        return {
            "avg_weight": float(avg_weight),
            "avg_count": float(avg_count),
            "count_gap_lb": float(count_gap_lb),
            "weight_gap_lb": float(weight_gap_lb),
            "hybrid_lb": float(hybrid_lb),
            "total_weight": float(total_weight),
            "total_count": float(total_count),
            "max_node_weight": float(max_node_weight),
        }

    def _best_move(self) -> Optional[Tuple[ProofIntervalNode, int]]:
        current = self._objective(self.color_weight_loads, self.color_count_loads)
        best_value = current
        best_move: Optional[Tuple[ProofIntervalNode, int]] = None

        colors_desc = sorted(range(1, self.num_colors + 1), key=self._heavy_color_key, reverse=True)
        colors_asc = list(reversed(colors_desc))

        for heavy in colors_desc:
            candidates = [node for node in self.proof_nodes if node.color == heavy]
            candidates.sort(key=self._candidate_move_key)
            for node in candidates:
                for light in colors_asc:
                    if light == heavy or not self._can_recolor(node, light):
                        continue
                    weight_loads = list(self.color_weight_loads)
                    count_loads = list(self.color_count_loads)
                    weight_loads[heavy - 1] -= node.weight
                    weight_loads[light - 1] += node.weight
                    count_loads[heavy - 1] -= 1
                    count_loads[light - 1] += 1
                    value = self._objective(weight_loads, count_loads)
                    if value < best_value:
                        best_value = value
                        best_move = (node, light)

        return best_move

    def _heavy_color_key(self, color: int) -> Tuple[int, int, int]:
        color_index = color - 1
        if self._strategy == "count_balanced":
            return (
                self.color_count_loads[color_index],
                self.color_weight_loads[color_index],
                -color,
            )
        if self._strategy == "hybrid":
            avg_count = max(1.0, sum(self.color_count_loads) / len(self.color_count_loads))
            avg_weight = max(1.0, sum(self.color_weight_loads) / len(self.color_weight_loads))
            return (
                int(
                    1000
                    * (
                        (self.color_count_loads[color_index] / avg_count)
                        + (self.color_weight_loads[color_index] / avg_weight)
                    )
                ),
                self.color_count_loads[color_index],
                self.color_weight_loads[color_index],
            )
        return (
            self.color_weight_loads[color_index],
            self.color_count_loads[color_index],
            -color,
        )

    def _candidate_move_key(self, node: ProofIntervalNode) -> Tuple[int, int, str]:
        if self._strategy == "count_balanced":
            return (node.weight, node.interval_right - node.interval_left, node.merkle_node.label)
        if self._strategy == "hybrid":
            return (
                -(node.weight + 2 * (node.interval_right - node.interval_left + 1)),
                -node.weight,
                node.merkle_node.label,
            )
        return (-node.weight, -(node.interval_right - node.interval_left), node.merkle_node.label)

    def _objective(self, weight_loads: List[int], count_loads: List[int]) -> Tuple[float, int, int, int, int]:
        weight_gap = max(weight_loads) - min(weight_loads)
        count_gap = max(count_loads) - min(count_loads)
        max_weight = max(weight_loads)
        max_count = max(count_loads)
        if self._strategy == "count_balanced":
            return (float(count_gap), count_gap, weight_gap, max_count, max_weight)
        if self._strategy == "hybrid":
            return (
                self._hybrid_score(weight_loads, count_loads),
                count_gap,
                weight_gap,
                max_count,
                max_weight,
            )
        return (float(weight_gap), weight_gap, count_gap, max_weight, max_count)

    def _can_recolor(self, node: ProofIntervalNode, new_color: int) -> bool:
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

    def verify(self) -> Tuple[bool, List[str]]:
        issues: List[str] = []

        def dfs(node: ProofIntervalNode, path_colors: set[int]) -> None:
            next_path = set(path_colors)
            if node.color is None:
                issues.append(f"Node {node.merkle_node.label} is uncolored.")
            elif node.color in path_colors:
                issues.append(
                    f"Conflict at node {node.merkle_node.label}: color {node.color} repeats on a proof chain."
                )
            else:
                next_path.add(node.color)
            for child in node.children:
                dfs(child, next_path)

        for root in self.interval_roots:
            dfs(root, set())

        color_buckets = self.color_indexes()
        for color, entries in color_buckets.items():
            for i in range(1, len(entries)):
                prev = entries[i - 1]
                curr = entries[i]
                if prev[1] >= curr[0]:
                    issues.append(
                        f"Color {color} has overlapping intervals "
                        f"[{prev[0]},{prev[1]}] and [{curr[0]},{curr[1]}]."
                    )

        return len(issues) == 0, issues

    def color_indexes(self) -> Dict[int, List[Tuple[int, int, str]]]:
        buckets: Dict[int, List[Tuple[int, int, str]]] = {c: [] for c in range(1, self.num_colors + 1)}
        for node in self.proof_nodes:
            if node.color is None:
                continue
            buckets[node.color].append((node.interval_left, node.interval_right, node.merkle_node.label))
        for color in buckets:
            buckets[color].sort()
        return buckets

    def query_plan(self, leaf_label: str) -> List[Tuple[int, str, Optional[str]]]:
        if leaf_label not in self.leaf_rank:
            raise KeyError(f"Unknown leaf label: {leaf_label}")

        rank = self.leaf_rank[leaf_label]
        plan: List[Tuple[int, str, Optional[str]]] = []
        for color, entries in self.color_indexes().items():
            left_endpoints = [left for left, _, _ in entries]
            pos = bisect_right(left_endpoints, rank) - 1
            if pos >= 0:
                left, right, label = entries[pos]
                if left <= rank <= right:
                    plan.append((color, "real", label))
                    continue
            plan.append((color, "dummy", None))
        return plan

    def baseline_metrics(self) -> Dict[str, List[int] | int]:
        weights = [0] * self.num_colors
        counts = [0] * self.num_colors

        def dfs(node: ProofIntervalNode, depth: int) -> None:
            color = depth
            weights[color - 1] += node.weight
            counts[color - 1] += 1
            for child in node.children:
                dfs(child, depth + 1)

        for root in self.interval_roots:
            dfs(root, 1)

        return {
            "weight_loads": weights,
            "count_loads": counts,
            "weight_gap": max(weights) - min(weights) if weights else 0,
            "count_gap": max(counts) - min(counts) if counts else 0,
            "hybrid_score": self.hybrid_score_from_loads(weights, counts),
        }

    def summary(self) -> str:
        baseline = self.baseline_metrics()
        return "\n".join(
            [
                f"Leaves: {[leaf.label for leaf in self.leaf_order]}",
                f"Proof nodes: {len(self.proof_nodes)}",
                f"Minimum colors needed: {self.num_colors}",
                f"Minimum active batch width: {self.minimum_batch_width()}",
                f"Strategy: {self._strategy}",
                f"Weighted loads: {self.color_weight_loads}",
                f"Count loads: {self.color_count_loads}",
                f"Weighted gap: {max(self.color_weight_loads) - min(self.color_weight_loads) if self.color_weight_loads else 0}",
                f"Baseline depth-color weighted loads: {baseline['weight_loads']}",
                f"Baseline depth-color weighted gap: {baseline['weight_gap']}",
            ]
        )


def demo() -> None:
    # A deliberately irregular Merkle tree.
    #               root
    #          /             \
    #       /                   \
    #    ((a,b),c)          (d,(e,f))
    coloring = DirectArbitraryMerkleColoring.from_nested((((("a", "b"), "c"), "d"), ("e", "f")))
    coloring.color(rebalance_rounds=400, strategy="weighted")
    ok, issues = coloring.verify()

    print("=== Direct Arbitrary Merkle Coloring Demo ===")
    print(coloring.summary())
    print(f"Valid coloring: {ok}")
    if not ok:
        for issue in issues:
            print(f"  - {issue}")

    print("Per-color interval indexes:")
    for color, entries in coloring.color_indexes().items():
        print(f"  C{color}: {entries}")

    print("Query plans:")
    for leaf in [leaf.label for leaf in coloring.leaf_order]:
        print(f"  leaf={leaf}: {coloring.query_plan(leaf)}")


if __name__ == "__main__":
    demo()
