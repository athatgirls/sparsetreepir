from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from generate_full_sparse_smt_example import ProofNode


@dataclass
class CompressedProofNode:
    """
    A super-node obtained by contracting a chain in the interval forest.

    The query interval of the super-node is the interval of the top member.
    Every member keeps its own interval and proof level so that the client can
    decide which hashes from the returned segment are actually written into the
    completed proof.
    """

    members: List[ProofNode]
    interval_left: int
    interval_right: int
    weight: int
    relevant_weight: int
    payload_weight: int
    hash_count: int
    top_depth: int
    bottom_depth: int
    color: Optional[int] = None
    parent: Optional["CompressedProofNode"] = None
    children: List["CompressedProofNode"] = field(default_factory=list)

    @property
    def depth(self) -> int:
        # Reuse the same attribute name expected by the existing coloring code.
        return self.top_depth

    @property
    def support_size(self) -> int:
        return self.interval_right - self.interval_left + 1

    @property
    def top_index(self) -> int:
        return self.members[0].index

    @property
    def bottom_index(self) -> int:
        return self.members[-1].index

    def member_indexes(self) -> List[int]:
        return [node.index for node in self.members]


def same_interval(a: ProofNode, b: ProofNode) -> bool:
    return (
        a.interval_left == b.interval_left
        and a.interval_right == b.interval_right
    )


def _make_compressed_node(
    members: List[ProofNode],
    weight_mode: str,
) -> CompressedProofNode:
    relevant_weight = sum(node.weight for node in members)
    support_size = members[0].interval_right - members[0].interval_left + 1
    payload_weight = support_size * len(members)
    if weight_mode == "payload":
        weight = payload_weight
    elif weight_mode == "relevant":
        weight = relevant_weight
    else:
        raise ValueError("weight_mode must be 'relevant' or 'payload'.")

    return CompressedProofNode(
        members=members,
        interval_left=members[0].interval_left,
        interval_right=members[0].interval_right,
        weight=weight,
        relevant_weight=relevant_weight,
        payload_weight=payload_weight,
        hash_count=len(members),
        top_depth=members[0].depth,
        bottom_depth=members[-1].depth,
    )


def compress_same_interval_forest(
    roots: Sequence[ProofNode],
    weight_mode: str = "relevant",
) -> List[CompressedProofNode]:
    """
    Contract every maximal parent-child chain with identical occupied-rank
    intervals.

    This is the zero-overfetch special case: all leaves hitting the super-node
    need every member hash in the segment.
    """

    def build(start: ProofNode) -> CompressedProofNode:
        members = [start]
        current = start

        while len(current.children) == 1 and same_interval(current, current.children[0]):
            current = current.children[0]
            members.append(current)

        super_node = _make_compressed_node(members, weight_mode=weight_mode)

        for child in current.children:
            if same_interval(current, child):
                # Maximal same-interval chains can only continue through the
                # unique child consumed above. Reaching this branch would mean
                # the forest structure is inconsistent.
                raise ValueError(
                    "Encountered a branching same-interval edge while compressing the forest."
                )
            compressed_child = build(child)
            compressed_child.parent = super_node
            super_node.children.append(compressed_child)

        return super_node

    return [build(root) for root in roots]


def compress_unary_chain_forest(
    roots: Sequence[ProofNode],
    weight_mode: str = "relevant",
) -> List[CompressedProofNode]:
    """
    Contract every maximal unary chain, regardless of whether member intervals
    are equal.

    This is the more aggressive branch-compressed variant. It can reduce the
    active width, but a returned segment may contain member hashes that are not
    used for every leaf in the top interval. That extra cost is tracked by the
    `payload_weight` field.
    """

    def build(start: ProofNode) -> CompressedProofNode:
        members = [start]
        current = start

        while len(current.children) == 1:
            current = current.children[0]
            members.append(current)

        super_node = _make_compressed_node(members, weight_mode=weight_mode)

        for child in current.children:
            compressed_child = build(child)
            compressed_child.parent = super_node
            super_node.children.append(compressed_child)

        return super_node

    return [build(root) for root in roots]


def traverse_compressed(node: CompressedProofNode) -> Iterable[CompressedProofNode]:
    yield node
    for child in node.children:
        yield from traverse_compressed(child)


def flatten_compressed_roots(roots: Sequence[CompressedProofNode]) -> List[CompressedProofNode]:
    nodes: List[CompressedProofNode] = []
    for root in roots:
        nodes.extend(traverse_compressed(root))
    return nodes


def max_compressed_chain_length(roots: Sequence[CompressedProofNode]) -> int:
    def depth(node: CompressedProofNode) -> int:
        if not node.children:
            return 1
        return 1 + max(depth(child) for child in node.children)

    return max((depth(root) for root in roots), default=0)


def per_color_hash_loads(
    nodes: Sequence[CompressedProofNode],
    num_colors: int,
) -> List[int]:
    loads = [0] * num_colors
    for node in nodes:
        if node.color is None:
            continue
        loads[node.color - 1] += node.hash_count
    return loads


def per_color_payload_loads(
    nodes: Sequence[CompressedProofNode],
    num_colors: int,
) -> List[int]:
    loads = [0] * num_colors
    for node in nodes:
        if node.color is None:
            continue
        loads[node.color - 1] += node.payload_weight
    return loads


def verify_compressed_coloring(
    roots: Sequence[CompressedProofNode],
    occupied_leaves: Sequence[int],
) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    def dfs(node: CompressedProofNode, path_colors: set[int]) -> None:
        next_colors = set(path_colors)
        if node.color is None:
            issues.append(f"Compressed node {node.top_index}->{node.bottom_index} is uncolored.")
        elif node.color in path_colors:
            issues.append(
                "Compressed chain "
                f"{node.top_index}->{node.bottom_index} repeats color {node.color} on a proof chain."
            )
        else:
            next_colors.add(node.color)
        for child in node.children:
            dfs(child, next_colors)

    for root in roots:
        dfs(root, set())

    by_color: Dict[int, List[CompressedProofNode]] = {}
    for root in roots:
        for node in traverse_compressed(root):
            if node.color is None:
                continue
            by_color.setdefault(node.color, []).append(node)

    for color, nodes in by_color.items():
        ordered = sorted(nodes, key=lambda item: (item.interval_left, item.interval_right))
        for left, right in zip(ordered, ordered[1:]):
            if left.interval_right >= right.interval_left:
                issues.append(
                    f"Color {color} has overlapping compressed intervals "
                    f"[{left.interval_left},{left.interval_right}] and "
                    f"[{right.interval_left},{right.interval_right}]."
                )

    leaf_ranks = {leaf: rank for rank, leaf in enumerate(occupied_leaves)}
    for leaf, rank in leaf_ranks.items():
        colors_on_path: List[int] = []
        nodes_on_path: List[str] = []
        for root in roots:
            for node in traverse_compressed(root):
                if node.interval_left <= rank <= node.interval_right:
                    if node.color is not None:
                        colors_on_path.append(node.color)
                    nodes_on_path.append(f"{node.top_index}->{node.bottom_index}")
        if len(colors_on_path) != len(set(colors_on_path)):
            issues.append(f"Leaf {leaf} hits duplicate colors on compressed nodes {nodes_on_path}.")

    return len(issues) == 0, issues
