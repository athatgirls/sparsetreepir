from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from generate_full_sparse_smt_example import ProofNode, traverse
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


@dataclass
class SubtreePermutationResult:
    name: str
    initial_strategy: str
    count_loads: List[int]
    weight_loads: List[int]
    passes: int
    improved_moves: int
    max_bucket: int
    size_gap: int
    objective_signature: Tuple[Tuple[int, ...], Tuple[int, ...]]


def _objective_signature(
    count_loads: Sequence[int],
    weight_loads: Sequence[int],
) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    return (
        tuple(sorted(count_loads, reverse=True)),
        tuple(sorted(weight_loads, reverse=True)),
    )


def _apply_color_loads(nodes: Sequence[ProofNode], num_colors: int) -> Tuple[List[int], List[int]]:
    count_loads = [0] * num_colors
    weight_loads = [0] * num_colors
    for node in nodes:
        if node.color is None:
            continue
        count_loads[node.color - 1] += 1
        weight_loads[node.color - 1] += node.weight
    return count_loads, weight_loads


def _annotate_state(
    roots: Sequence[ProofNode],
    num_colors: int,
) -> Tuple[Dict[int, int], Dict[int, List[int]], Dict[int, List[int]]]:
    ancestor_masks: Dict[int, int] = {}
    subtree_counts: Dict[int, List[int]] = {}
    subtree_weights: Dict[int, List[int]] = {}

    def dfs(node: ProofNode, ancestor_mask: int) -> Tuple[List[int], List[int]]:
        ancestor_masks[id(node)] = ancestor_mask
        counts = [0] * num_colors
        weights = [0] * num_colors
        next_mask = ancestor_mask
        if node.color is not None:
            next_mask |= 1 << (node.color - 1)

        for child in node.children:
            child_counts, child_weights = dfs(child, next_mask)
            for idx in range(num_colors):
                counts[idx] += child_counts[idx]
                weights[idx] += child_weights[idx]

        if node.color is not None:
            counts[node.color - 1] += 1
            weights[node.color - 1] += node.weight

        subtree_counts[id(node)] = counts
        subtree_weights[id(node)] = weights
        return counts, weights

    for root in roots:
        dfs(root, 0)
    return ancestor_masks, subtree_counts, subtree_weights


def _hungarian_assignment(cost_matrix: Sequence[Sequence[float]]) -> List[int]:
    n = len(cost_matrix)
    if n == 0:
        return []
    if any(len(row) != n for row in cost_matrix):
        raise ValueError("Hungarian assignment expects a square cost matrix.")

    # Standard O(n^3) Hungarian algorithm using 1-based arrays.
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        j0 = 0
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    if any(index < 0 for index in assignment):
        raise RuntimeError("Hungarian assignment failed to recover a valid permutation.")
    return assignment


def _best_subtree_mapping(
    available_colors: Sequence[int],
    global_count_loads: Sequence[int],
    global_weight_loads: Sequence[int],
    subtree_counts: Sequence[int],
    subtree_weights: Sequence[int],
    weight_penalty: float,
) -> Dict[int, int]:
    colors = list(available_colors)
    if not colors:
        return {}

    cost_matrix: List[List[float]] = []
    source_colors = list(colors)
    target_colors = list(colors)
    for source in source_colors:
        row: List[float] = []
        src_idx = source - 1
        for target in target_colors:
            tgt_idx = target - 1
            outside_count = global_count_loads[tgt_idx] - subtree_counts[tgt_idx]
            outside_weight = global_weight_loads[tgt_idx] - subtree_weights[tgt_idx]
            candidate_count = outside_count + subtree_counts[src_idx]
            candidate_weight = outside_weight + subtree_weights[src_idx]
            row.append((candidate_count ** 2) + weight_penalty * (candidate_weight ** 2))
        cost_matrix.append(row)

    assignment = _hungarian_assignment(cost_matrix)
    return {
        source_colors[source_idx]: target_colors[target_idx]
        for source_idx, target_idx in enumerate(assignment)
    }


def _candidate_loads_after_mapping(
    mapping: Dict[int, int],
    available_colors: Sequence[int],
    global_count_loads: Sequence[int],
    global_weight_loads: Sequence[int],
    subtree_counts: Sequence[int],
    subtree_weights: Sequence[int],
) -> Tuple[List[int], List[int]]:
    candidate_counts = list(global_count_loads)
    candidate_weights = list(global_weight_loads)

    for color in available_colors:
        idx = color - 1
        candidate_counts[idx] -= subtree_counts[idx]
        candidate_weights[idx] -= subtree_weights[idx]

    for old_color, new_color in mapping.items():
        old_idx = old_color - 1
        new_idx = new_color - 1
        candidate_counts[new_idx] += subtree_counts[old_idx]
        candidate_weights[new_idx] += subtree_weights[old_idx]

    return candidate_counts, candidate_weights


def _apply_mapping_to_subtree(node: ProofNode, mapping: Dict[int, int]) -> None:
    for current in traverse(node):
        if current.color is None:
            continue
        current.color = mapping.get(current.color, current.color)


def subtree_permutation_refine(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    num_colors: int,
    initial_strategy: str = "hybrid",
    initial_rounds: int = 400,
    refine_rounds: int = 200,
    weight_penalty: float = 0.001,
) -> SubtreePermutationResult:
    color_proof_nodes(
        proof_nodes=proof_nodes,
        roots=roots,
        num_colors=num_colors,
        strategy=initial_strategy,
        rebalance_rounds=initial_rounds,
    )
    count_loads, weight_loads = _apply_color_loads(proof_nodes, num_colors)
    current_objective = _objective_signature(count_loads, weight_loads)

    improved_moves = 0
    passes_used = 0
    all_nodes = [node for root in roots for node in traverse(root)]

    for _ in range(refine_rounds):
        passes_used += 1
        ancestor_masks, subtree_counts_by_node, subtree_weights_by_node = _annotate_state(roots, num_colors)
        best_move: Optional[Tuple[ProofNode, Dict[int, int], List[int], List[int], Tuple[Tuple[int, ...], Tuple[int, ...]]]] = None

        for node in all_nodes:
            ancestor_mask = ancestor_masks[id(node)]
            available_colors = [
                color for color in range(1, num_colors + 1) if not (ancestor_mask & (1 << (color - 1)))
            ]
            if len(available_colors) <= 1:
                continue

            subtree_counts = subtree_counts_by_node[id(node)]
            subtree_weights = subtree_weights_by_node[id(node)]
            mapping = _best_subtree_mapping(
                available_colors=available_colors,
                global_count_loads=count_loads,
                global_weight_loads=weight_loads,
                subtree_counts=subtree_counts,
                subtree_weights=subtree_weights,
                weight_penalty=weight_penalty,
            )
            if all(mapping[color] == color for color in available_colors):
                continue

            candidate_counts, candidate_weights = _candidate_loads_after_mapping(
                mapping=mapping,
                available_colors=available_colors,
                global_count_loads=count_loads,
                global_weight_loads=weight_loads,
                subtree_counts=subtree_counts,
                subtree_weights=subtree_weights,
            )
            candidate_objective = _objective_signature(candidate_counts, candidate_weights)
            if candidate_objective < current_objective:
                if best_move is None or candidate_objective < best_move[4]:
                    best_move = (node, mapping, candidate_counts, candidate_weights, candidate_objective)

        if best_move is None:
            break

        node, mapping, count_loads, weight_loads, current_objective = best_move
        _apply_mapping_to_subtree(node, mapping)
        improved_moves += 1

    return SubtreePermutationResult(
        name="profile_balanced",
        initial_strategy=initial_strategy,
        count_loads=list(count_loads),
        weight_loads=list(weight_loads),
        passes=passes_used,
        improved_moves=improved_moves,
        max_bucket=max(count_loads) if count_loads else 0,
        size_gap=max(count_loads) - min(count_loads) if count_loads else 0,
        objective_signature=current_objective,
    )


def best_profile_balanced_coloring(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    num_colors: int,
    initial_strategies: Sequence[str] = ("hybrid", "weighted", "count_balanced"),
    initial_rounds: int = 400,
    refine_rounds: int = 200,
    weight_penalty: float = 0.001,
) -> SubtreePermutationResult:
    best: Optional[SubtreePermutationResult] = None
    best_assignment: Optional[List[Optional[int]]] = None
    for strategy in initial_strategies:
        result = subtree_permutation_refine(
            proof_nodes=proof_nodes,
            roots=roots,
            num_colors=num_colors,
            initial_strategy=strategy,
            initial_rounds=initial_rounds,
            refine_rounds=refine_rounds,
            weight_penalty=weight_penalty,
        )
        if best is None or result.objective_signature < best.objective_signature:
            best = result
            best_assignment = [node.color for node in proof_nodes]

    if best is None or best_assignment is None:
        raise RuntimeError("Failed to produce a profile-balanced coloring.")
    for node, color in zip(proof_nodes, best_assignment):
        node.color = color
    return best
