from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode,
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)
from subtree_permutation_balance import best_profile_balanced_coloring


@dataclass
class ExactResult:
    optimum: Optional[int]
    timed_out: bool
    seconds: float


def flatten_preorder(roots: Sequence[ProofNode]) -> List[ProofNode]:
    ordered: List[ProofNode] = []

    def subtree_size(node: ProofNode) -> int:
        return 1 + sum(subtree_size(child) for child in node.children)

    def dfs(node: ProofNode) -> None:
        ordered.append(node)
        children = sorted(node.children, key=subtree_size, reverse=True)
        for child in children:
            dfs(child)

    for root in sorted(roots, key=subtree_size, reverse=True):
        dfs(root)
    return ordered


def build_parent_positions(nodes: Sequence[ProofNode]) -> List[int]:
    position = {id(node): idx for idx, node in enumerate(nodes)}
    parents: List[int] = []
    for node in nodes:
        parents.append(position.get(id(node.parent), -1))
    return parents


def feasible_with_capacity(
    nodes: Sequence[ProofNode],
    parents: Sequence[int],
    colors: int,
    cap: int,
    timeout_s: float,
) -> Tuple[bool, bool]:
    start = time.monotonic()
    n = len(nodes)
    loads = [0] * colors
    assigned = [-1] * n
    ancestor_masks = [0] * n

    def dfs(pos: int) -> bool:
        if time.monotonic() - start > timeout_s:
            raise TimeoutError
        if pos == n:
            return True

        remaining = n - pos
        if sum(cap - load for load in loads) < remaining:
            return False

        parent = parents[pos]
        forbidden = ancestor_masks[parent] | (1 << assigned[parent]) if parent >= 0 else 0
        ancestor_masks[pos] = forbidden

        candidates = [
            color
            for color in range(colors)
            if not (forbidden & (1 << color)) and loads[color] < cap
        ]
        candidates.sort(key=lambda color: (loads[color], color))

        seen_loads = set()
        for color in candidates:
            # Symmetry pruning: colors with the same current load are equivalent
            # for the current node under the same ancestor mask.
            if loads[color] in seen_loads:
                continue
            seen_loads.add(loads[color])

            assigned[pos] = color
            loads[color] += 1
            if dfs(pos + 1):
                return True
            loads[color] -= 1
            assigned[pos] = -1
        return False

    try:
        return dfs(0), False
    except TimeoutError:
        return False, True


def exact_minmax_bucket(
    roots: Sequence[ProofNode],
    colors: int,
    lower_bound: int,
    timeout_s: float,
) -> ExactResult:
    nodes = flatten_preorder(roots)
    parents = build_parent_positions(nodes)
    start = time.monotonic()

    for cap in range(lower_bound, len(nodes) + 1):
        remaining_time = timeout_s - (time.monotonic() - start)
        if remaining_time <= 0:
            return ExactResult(None, True, time.monotonic() - start)
        feasible, timed_out = feasible_with_capacity(
            nodes=nodes,
            parents=parents,
            colors=colors,
            cap=cap,
            timeout_s=remaining_time,
        )
        if timed_out:
            return ExactResult(None, True, time.monotonic() - start)
        if feasible:
            return ExactResult(cap, False, time.monotonic() - start)

    return ExactResult(None, False, time.monotonic() - start)


def run_instance(height: int, sparsity: float, seed: int, timeout_s: float) -> Dict[str, object]:
    occupied = generate_occupied_leaves(height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(proof_nodes)
    m = max_chain_length(roots)
    lower = (len(proof_nodes) + m - 1) // m if m else 0

    # Run the heuristic first. If it attains the equal-split lower bound,
    # optimality is certified without invoking the exponential exact solver.
    proof_nodes_profile = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots_profile = build_interval_forest(proof_nodes_profile)
    profile = best_profile_balanced_coloring(
        proof_nodes=proof_nodes_profile,
        roots=roots_profile,
        num_colors=m,
        initial_rounds=400,
        refine_rounds=120,
    )
    profile_max = profile.max_bucket

    if profile_max == lower:
        exact = ExactResult(lower, False, 0.0)
    else:
        exact = exact_minmax_bucket(roots=roots, colors=m, lower_bound=lower, timeout_s=timeout_s)

    ratio = (profile_max / exact.optimum) if exact.optimum else ""
    return {
        "height": height,
        "sparsity": sparsity,
        "seed": seed,
        "occupied": len(occupied),
        "active": len(proof_nodes),
        "m": m,
        "lower": lower,
        "optimum": exact.optimum if exact.optimum is not None else "",
        "profile_max": profile_max,
        "profile_over_opt": ratio,
        "exact_seconds": exact.seconds,
        "timed_out": exact.timed_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Small exact min-max balance checks for active interval forests.")
    parser.add_argument("--settings", type=str, default="10:0.98,12:0.99,14:0.995")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--seed-base", type=int, default=220000)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=Path("examples/small_opt_balance_results.csv"))
    args = parser.parse_args()

    rows: List[Dict[str, object]] = []
    for setting_index, raw in enumerate(args.settings.split(",")):
        height_raw, sparsity_raw = raw.split(":")
        height = int(height_raw)
        sparsity = float(sparsity_raw)
        for trial in range(args.trials):
            seed = args.seed_base + setting_index * 1000 + trial
            row = run_instance(height=height, sparsity=sparsity, seed=seed, timeout_s=args.timeout_s)
            rows.append(row)
            print(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
