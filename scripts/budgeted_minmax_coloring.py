from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from generate_full_sparse_smt_example import ProofNode
from run_pir_cost_model_experiment import backend_costs


@dataclass
class FixedBudgetColoringResult:
    num_colors: int
    count_loads: List[int]
    weight_loads: List[int]
    max_bucket: int
    objective_signature: Tuple[Tuple[int, ...], int, Tuple[int, ...]]


@dataclass
class BudgetedColoringResult:
    chosen_colors: int
    score: float
    backend_name: str
    count_loads: List[int]
    weight_loads: List[int]
    max_bucket: int
    query_ms: float
    extract_ms: float
    server_max_ms: float
    candidates: List[Dict[str, float | int | List[int]]]


def clear_colors(proof_nodes: Sequence[ProofNode]) -> None:
    for node in proof_nodes:
        node.color = None


def _count_signature(count_loads: Sequence[int]) -> Tuple[int, ...]:
    return tuple(sorted(count_loads, reverse=True))


def _weight_signature(weight_loads: Sequence[int]) -> Tuple[int, ...]:
    return tuple(sorted(weight_loads, reverse=True))


def _objective_signature(
    count_loads: Sequence[int],
    weight_loads: Sequence[int],
) -> Tuple[Tuple[int, ...], int, Tuple[int, ...]]:
    """
    Lexicographic min-max objective.

    Primary: minimize the full descending count-load profile, which first
    minimizes the largest subdatabase, then the second largest, and so on.
    Secondary: minimize the maximum weighted load.
    Tertiary: minimize the full descending weighted-load profile.
    """

    return (
        _count_signature(count_loads),
        max(weight_loads) if weight_loads else 0,
        _weight_signature(weight_loads),
    )


def _can_recolor(node: ProofNode, new_color: int) -> bool:
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


def color_proof_nodes_min_max_size(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    num_colors: int,
    rebalance_rounds: int,
) -> FixedBudgetColoringResult:
    if num_colors <= 0:
        return FixedBudgetColoringResult(
            num_colors=0,
            count_loads=[],
            weight_loads=[],
            max_bucket=0,
            objective_signature=((), 0, ()),
        )

    def node_order(mode: str, nodes: Sequence[ProofNode]) -> List[ProofNode]:
        if mode == "heavy_desc":
            return sorted(nodes, key=lambda item: (item.weight, len(item.children), -item.depth), reverse=True)
        if mode == "branch_desc":
            return sorted(nodes, key=lambda item: (len(item.children), item.weight, -item.depth), reverse=True)
        if mode == "light_asc":
            return sorted(nodes, key=lambda item: (item.weight, len(item.children), item.depth))
        raise ValueError(f"unsupported ordering mode: {mode}")

    def run_once(order_mode: str) -> Tuple[List[int], List[int], List[Optional[int]]]:
        clear_colors(proof_nodes)
        count_loads = [0] * num_colors
        weight_loads = [0] * num_colors

        def assign(node: ProofNode, color: int) -> None:
            if node.color is not None:
                old_idx = node.color - 1
                count_loads[old_idx] -= 1
                weight_loads[old_idx] -= node.weight
            node.color = color
            new_idx = color - 1
            count_loads[new_idx] += 1
            weight_loads[new_idx] += node.weight

        def greedy_choice(node: ProofNode, available: Sequence[int]) -> int:
            best_color = available[0]
            best_key: Optional[Tuple[Tuple[int, ...], int, Tuple[int, ...], int]] = None
            for color in available:
                idx = color - 1
                candidate_count = list(count_loads)
                candidate_weight = list(weight_loads)
                candidate_count[idx] += 1
                candidate_weight[idx] += node.weight
                candidate_key = (*_objective_signature(candidate_count, candidate_weight), color)
                if best_key is None or candidate_key < best_key:
                    best_key = candidate_key
                    best_color = color
            return best_color

        def greedy(node: ProofNode, ancestor_colors: set[int]) -> None:
            available = [c for c in range(1, num_colors + 1) if c not in ancestor_colors]
            if not available:
                raise RuntimeError(
                    f"No available color for node {node.index}; inspect whether num_colors < active width."
                )
            chosen = greedy_choice(node, available)
            assign(node, chosen)
            next_ancestor = set(ancestor_colors)
            next_ancestor.add(chosen)
            for child in node_order(order_mode, node.children):
                greedy(child, next_ancestor)

        for root in node_order(order_mode, roots):
            greedy(root, set())

        for _ in range(rebalance_rounds):
            current_objective = _objective_signature(count_loads, weight_loads)
            best_move: Optional[Tuple[ProofNode, int, Tuple[Tuple[int, ...], int, Tuple[int, ...]]]] = None

            colors_desc = sorted(
                range(1, num_colors + 1),
                key=lambda color: (count_loads[color - 1], weight_loads[color - 1], -color),
                reverse=True,
            )
            colors_asc = list(reversed(colors_desc))

            for heavy in colors_desc:
                candidates = [node for node in proof_nodes if node.color == heavy]
                candidates = node_order(order_mode, candidates)
                for node in candidates:
                    for light in colors_asc:
                        if light == heavy or not _can_recolor(node, light):
                            continue
                        candidate_count = list(count_loads)
                        candidate_weight = list(weight_loads)
                        candidate_count[heavy - 1] -= 1
                        candidate_count[light - 1] += 1
                        candidate_weight[heavy - 1] -= node.weight
                        candidate_weight[light - 1] += node.weight
                        candidate_objective = _objective_signature(candidate_count, candidate_weight)
                        if candidate_objective < current_objective:
                            if best_move is None or candidate_objective < best_move[2]:
                                best_move = (node, light, candidate_objective)

            if best_move is None:
                break
            assign(best_move[0], best_move[1])

        return list(count_loads), list(weight_loads), [node.color for node in proof_nodes]

    best_count_loads: List[int] = []
    best_weight_loads: List[int] = []
    best_assignment: List[Optional[int]] = []
    best_objective: Optional[Tuple[Tuple[int, ...], int, Tuple[int, ...]]] = None

    for mode in ["heavy_desc", "branch_desc", "light_asc"]:
        count_loads, weight_loads, assignment = run_once(mode)
        objective = _objective_signature(count_loads, weight_loads)
        if best_objective is None or objective < best_objective:
            best_objective = objective
            best_count_loads = count_loads
            best_weight_loads = weight_loads
            best_assignment = assignment

    clear_colors(proof_nodes)
    for node, color in zip(proof_nodes, best_assignment):
        node.color = color

    return FixedBudgetColoringResult(
        num_colors=num_colors,
        count_loads=list(best_count_loads),
        weight_loads=list(best_weight_loads),
        max_bucket=max(best_count_loads) if best_count_loads else 0,
        objective_signature=best_objective if best_objective is not None else ((), 0, ()),
    )


def budgeted_min_max_size_search(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    min_colors: int,
    max_colors: int,
    rebalance_rounds: int,
    backend_name: str,
    backend_models,
    server_weight: float = 1.0,
) -> BudgetedColoringResult:
    if max_colors < min_colors:
        raise ValueError("max_colors must be at least min_colors.")

    best_choice: Optional[BudgetedColoringResult] = None
    candidates: List[Dict[str, float | int | List[int]]] = []

    for budget in range(min_colors, max_colors + 1):
        fixed = color_proof_nodes_min_max_size(
            proof_nodes=proof_nodes,
            roots=roots,
            num_colors=budget,
            rebalance_rounds=rebalance_rounds,
        )
        costs = backend_costs(backend_models[backend_name], fixed.count_loads)
        score = (
            costs["query_total_ms"]
            + costs["extract_total_ms"]
            + server_weight * costs["server_max_ms"]
        )
        candidate = {
            "num_colors": budget,
            "score": float(score),
            "max_bucket": fixed.max_bucket,
            "query_ms": float(costs["query_total_ms"]),
            "extract_ms": float(costs["extract_total_ms"]),
            "server_max_ms": float(costs["server_max_ms"]),
            "count_loads": list(fixed.count_loads),
            "weight_loads": list(fixed.weight_loads),
        }
        candidates.append(candidate)

        current = BudgetedColoringResult(
            chosen_colors=budget,
            score=float(score),
            backend_name=backend_name,
            count_loads=list(fixed.count_loads),
            weight_loads=list(fixed.weight_loads),
            max_bucket=fixed.max_bucket,
            query_ms=float(costs["query_total_ms"]),
            extract_ms=float(costs["extract_total_ms"]),
            server_max_ms=float(costs["server_max_ms"]),
            candidates=[],
        )
        if best_choice is None:
            best_choice = current
            continue

        best_key = (
            best_choice.score,
            best_choice.max_bucket,
            best_choice.chosen_colors,
        )
        current_key = (
            current.score,
            current.max_bucket,
            current.chosen_colors,
        )
        if current_key < best_key:
            best_choice = current

    if best_choice is None:
        raise RuntimeError("Budgeted search produced no candidates.")

    best_choice.candidates = candidates
    return best_choice
