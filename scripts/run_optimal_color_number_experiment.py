from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from direct_arbitrary_merkle_coloring import DirectArbitraryMerkleColoring, ProofIntervalNode
from run_random_merkle_coloring_experiment import build_random_merkle_tree


@dataclass
class TrialSummary:
    seed: int
    leaves: int
    proof_nodes: int
    theorem_width: int
    exact_width: int


def conflict_graph(nodes: Sequence[ProofIntervalNode]) -> List[List[int]]:
    adjacency = [[False for _ in nodes] for _ in nodes]
    for left in range(len(nodes)):
        for right in range(left + 1, len(nodes)):
            a = nodes[left]
            b = nodes[right]
            if not (a.interval_right < b.interval_left or b.interval_right < a.interval_left):
                adjacency[left][right] = True
                adjacency[right][left] = True
    return adjacency


def exact_chromatic_number(nodes: Sequence[ProofIntervalNode]) -> int:
    if not nodes:
        return 0

    adjacency = conflict_graph(nodes)
    order = sorted(range(len(nodes)), key=lambda index: sum(adjacency[index]), reverse=True)
    assigned = [-1] * len(nodes)
    best = len(nodes)

    def search(position: int, used_colors: int) -> None:
        nonlocal best
        if used_colors >= best:
            return
        if position == len(order):
            best = min(best, used_colors)
            return

        node_index = order[position]
        blocked = {
            assigned[neighbor]
            for neighbor, has_edge in enumerate(adjacency[node_index])
            if has_edge and assigned[neighbor] != -1
        }
        for color in range(used_colors):
            if color in blocked:
                continue
            assigned[node_index] = color
            search(position + 1, used_colors)
            assigned[node_index] = -1

        assigned[node_index] = used_colors
        search(position + 1, used_colors + 1)
        assigned[node_index] = -1

    search(0, 0)
    return best


def run_trial(leaves: int, seed: int) -> TrialSummary:
    root = build_random_merkle_tree(num_leaves=leaves, seed=seed)
    coloring = DirectArbitraryMerkleColoring(root)
    theorem_width = coloring.minimum_batch_width()
    exact_width = exact_chromatic_number(coloring.proof_nodes)
    return TrialSummary(
        seed=seed,
        leaves=leaves,
        proof_nodes=len(coloring.proof_nodes),
        theorem_width=theorem_width,
        exact_width=exact_width,
    )


def summarize(trials: Sequence[TrialSummary]) -> Dict[str, float]:
    matches = sum(1 for trial in trials if trial.theorem_width == trial.exact_width)
    return {
        "trials": float(len(trials)),
        "avg_proof_nodes": sum(trial.proof_nodes for trial in trials) / len(trials),
        "avg_theorem_width": sum(trial.theorem_width for trial in trials) / len(trials),
        "avg_exact_width": sum(trial.exact_width for trial in trials) / len(trials),
        "match_rate": matches / len(trials),
    }


def parse_leaf_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("leaf list cannot be empty")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate that the exact minimum color number equals the maximum active proof length."
    )
    parser.add_argument("--leaf-list", type=str, default="5,6,7,8", help="Comma-separated leaf counts.")
    parser.add_argument("--trials", type=int, default=25, help="Trials per leaf count.")
    parser.add_argument("--seed-base", type=int, default=9000, help="Base seed.")
    args = parser.parse_args()

    leaf_sizes = parse_leaf_list(args.leaf_list)
    print("=== Optimal Color Number Validation ===")
    print(f"leaf_sizes={leaf_sizes}")
    print(f"trials_per_size={args.trials}")
    print(f"seed_base={args.seed_base}")
    print()

    overall: List[TrialSummary] = []
    for leaf_count in leaf_sizes:
        trials: List[TrialSummary] = []
        for offset in range(args.trials):
            trial = run_trial(leaves=leaf_count, seed=args.seed_base + offset)
            trials.append(trial)
            overall.append(trial)
        stats = summarize(trials)
        print(
            f"leaves={leaf_count}: "
            f"avg_proof_nodes={stats['avg_proof_nodes']:.2f}, "
            f"avg_theorem_width={stats['avg_theorem_width']:.2f}, "
            f"avg_exact_width={stats['avg_exact_width']:.2f}, "
            f"match_rate={stats['match_rate'] * 100:.1f}%"
        )

    overall_stats = summarize(overall)
    print()
    print(
        "overall: "
        f"avg_proof_nodes={overall_stats['avg_proof_nodes']:.2f}, "
        f"avg_theorem_width={overall_stats['avg_theorem_width']:.2f}, "
        f"avg_exact_width={overall_stats['avg_exact_width']:.2f}, "
        f"match_rate={overall_stats['match_rate'] * 100:.1f}%"
    )


if __name__ == "__main__":
    main()
