from __future__ import annotations

import argparse
from dataclasses import dataclass
import random
from typing import Dict, List

from direct_arbitrary_merkle_coloring import DirectArbitraryMerkleColoring, MerkleNode


@dataclass
class TrialResult:
    strategy: str
    seed: int
    num_leaves: int
    proof_nodes: int
    num_colors: int
    subdatabase_sizes: List[int]
    subdatabase_size_gap: int
    weighted_loads: List[int]
    weighted_gap: int
    ancestral_property_valid: bool


def build_random_merkle_tree(num_leaves: int, seed: int) -> MerkleNode:
    """
    Build a random binary Merkle tree bottom-up.

    We start from ordered leaves and repeatedly merge a random adjacent pair.
    This preserves the left-to-right leaf order while producing an irregular
    binary tree shape.
    """
    if num_leaves < 2:
        raise ValueError("num_leaves must be at least 2.")

    rng = random.Random(seed)
    forest: List[MerkleNode] = [MerkleNode(label=f"L{i}") for i in range(num_leaves)]
    internal_index = 0

    while len(forest) > 1:
        merge_at = rng.randrange(len(forest) - 1)
        left = forest[merge_at]
        right = forest[merge_at + 1]
        internal_index += 1
        parent = MerkleNode(label=f"I{internal_index}", left=left, right=right)
        left.parent = parent
        right.parent = parent
        forest = forest[:merge_at] + [parent] + forest[merge_at + 2 :]

    return forest[0]


def stringify(node: MerkleNode) -> str:
    if node.is_leaf:
        return node.label
    return f"({stringify(node.left)},{stringify(node.right)})"


def run_single_trial(num_leaves: int, seed: int, rebalance_rounds: int, strategy: str) -> TrialResult:
    root = build_random_merkle_tree(num_leaves=num_leaves, seed=seed)
    coloring = DirectArbitraryMerkleColoring(root)
    coloring.color(rebalance_rounds=rebalance_rounds, strategy=strategy)
    ok, issues = coloring.verify()
    size_gap = max(coloring.color_count_loads) - min(coloring.color_count_loads) if coloring.color_count_loads else 0
    weighted_gap = (
        max(coloring.color_weight_loads) - min(coloring.color_weight_loads)
        if coloring.color_weight_loads
        else 0
    )

    if not ok:
        print(f"seed={seed} validation issues:")
        for issue in issues:
            print(f"  - {issue}")

    return TrialResult(
        strategy=strategy,
        seed=seed,
        num_leaves=num_leaves,
        proof_nodes=len(coloring.proof_nodes),
        num_colors=coloring.num_colors,
        subdatabase_sizes=list(coloring.color_count_loads),
        subdatabase_size_gap=size_gap,
        weighted_loads=list(coloring.color_weight_loads),
        weighted_gap=weighted_gap,
        ancestral_property_valid=ok,
    )


def print_single_trial_detail(num_leaves: int, seed: int, rebalance_rounds: int, strategy: str) -> None:
    root = build_random_merkle_tree(num_leaves=num_leaves, seed=seed)
    coloring = DirectArbitraryMerkleColoring(root)
    coloring.color(rebalance_rounds=rebalance_rounds, strategy=strategy)
    ok, issues = coloring.verify()

    print("=== Random Merkle Coloring Experiment ===")
    print(f"strategy={strategy}")
    print(f"seed={seed}")
    print(f"num_leaves={num_leaves}")
    print(f"tree_shape={stringify(root)}")
    print(f"proof_nodes={len(coloring.proof_nodes)}")
    print(f"num_colors={coloring.num_colors}")
    print(f"subdatabase_sizes={coloring.color_count_loads}")
    print(
        "subdatabase_size_gap="
        f"{max(coloring.color_count_loads) - min(coloring.color_count_loads) if coloring.color_count_loads else 0}"
    )
    print(f"weighted_loads={coloring.color_weight_loads}")
    print(
        "weighted_gap="
        f"{max(coloring.color_weight_loads) - min(coloring.color_weight_loads) if coloring.color_weight_loads else 0}"
    )
    print(f"ancestral_property_valid={ok}")
    if not ok:
        print("issues:")
        for issue in issues:
            print(f"  - {issue}")

    print("per_color_indexes:")
    for color, entries in coloring.color_indexes().items():
        print(f"  C{color}: size={len(entries)} entries={entries}")


def parse_leaf_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("leaf list cannot be empty")
    return values


def summarize_trials(trials: List[TrialResult]) -> Dict[str, float]:
    total = len(trials)
    valid = sum(1 for trial in trials if trial.ancestral_property_valid)
    avg_size_gap = sum(trial.subdatabase_size_gap for trial in trials) / total
    avg_weighted_gap = sum(trial.weighted_gap for trial in trials) / total
    avg_proof_nodes = sum(trial.proof_nodes for trial in trials) / total
    avg_num_colors = sum(trial.num_colors for trial in trials) / total
    return {
        "trials": float(total),
        "pass_rate": valid / total,
        "avg_size_gap": avg_size_gap,
        "avg_weighted_gap": avg_weighted_gap,
        "avg_proof_nodes": avg_proof_nodes,
        "avg_num_colors": avg_num_colors,
    }


def run_batch_mode(
    leaf_sizes: List[int],
    trials_per_size: int,
    rounds: int,
    seed_base: int,
    compare: bool,
    strategy: str,
) -> None:
    label = "=== Batch Random Merkle Coloring Comparison ===" if compare else "=== Batch Random Merkle Coloring Experiment ==="
    print(label)
    print(f"leaf_sizes={leaf_sizes}")
    print(f"trials_per_size={trials_per_size}")
    print(f"seed_base={seed_base}")
    print(f"rebalance_rounds={rounds}")
    if not compare:
        print(f"strategy={strategy}")
    print()
    print("per_size_summary:")

    all_trials: Dict[str, List[TrialResult]] = {"weighted": [], "count_balanced": []}
    active_strategies = ["weighted", "count_balanced"] if compare else [strategy]
    for num_leaves in leaf_sizes:
        trials_by_strategy: Dict[str, List[TrialResult]] = {name: [] for name in active_strategies}
        for offset in range(trials_per_size):
            seed = seed_base + offset
            for current_strategy in active_strategies:
                trial = run_single_trial(
                    num_leaves=num_leaves,
                    seed=seed,
                    rebalance_rounds=rounds,
                    strategy=current_strategy,
                )
                trials_by_strategy[current_strategy].append(trial)
                all_trials[current_strategy].append(trial)

        if compare:
            weighted_summary = summarize_trials(trials_by_strategy["weighted"])
            count_summary = summarize_trials(trials_by_strategy["count_balanced"])
            print(
                f"  leaves={num_leaves:<3} "
                f"weighted(avg_size_gap={weighted_summary['avg_size_gap']:.3f}, "
                f"avg_weighted_gap={weighted_summary['avg_weighted_gap']:.3f}, "
                f"pass_rate={weighted_summary['pass_rate'] * 100:.1f}%) "
                f"count_balanced(avg_size_gap={count_summary['avg_size_gap']:.3f}, "
                f"avg_weighted_gap={count_summary['avg_weighted_gap']:.3f}, "
                f"pass_rate={count_summary['pass_rate'] * 100:.1f}%)"
            )
        else:
            summary = summarize_trials(trials_by_strategy[strategy])
            print(
                f"  leaves={num_leaves:<3} "
                f"avg_size_gap={summary['avg_size_gap']:.3f} "
                f"avg_weighted_gap={summary['avg_weighted_gap']:.3f} "
                f"pass_rate={summary['pass_rate'] * 100:.1f}% "
                f"avg_colors={summary['avg_num_colors']:.2f} "
                f"avg_proof_nodes={summary['avg_proof_nodes']:.2f}"
            )

    print()
    print("overall_summary:")
    if compare:
        weighted_overall = summarize_trials(all_trials["weighted"])
        count_overall = summarize_trials(all_trials["count_balanced"])
        print(
            f"  weighted(total_trials={int(weighted_overall['trials'])}, "
            f"avg_size_gap={weighted_overall['avg_size_gap']:.3f}, "
            f"avg_weighted_gap={weighted_overall['avg_weighted_gap']:.3f}, "
            f"pass_rate={weighted_overall['pass_rate'] * 100:.1f}%)"
        )
        print(
            f"  count_balanced(total_trials={int(count_overall['trials'])}, "
            f"avg_size_gap={count_overall['avg_size_gap']:.3f}, "
            f"avg_weighted_gap={count_overall['avg_weighted_gap']:.3f}, "
            f"pass_rate={count_overall['pass_rate'] * 100:.1f}%)"
        )
    else:
        overall = summarize_trials(all_trials[strategy])
        print(
            f"  total_trials={int(overall['trials'])} "
            f"avg_size_gap={overall['avg_size_gap']:.3f} "
            f"avg_weighted_gap={overall['avg_weighted_gap']:.3f} "
            f"pass_rate={overall['pass_rate'] * 100:.1f}% "
            f"avg_colors={overall['avg_num_colors']:.2f} "
            f"avg_proof_nodes={overall['avg_proof_nodes']:.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run random Merkle coloring experiments.")
    parser.add_argument("--leaves", type=int, default=12, help="Number of leaf nodes for single mode.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for single mode.")
    parser.add_argument("--rounds", type=int, default=400, help="Maximum local rebalancing rounds.")
    parser.add_argument(
        "--strategy",
        type=str,
        default="weighted",
        choices=["weighted", "count_balanced"],
        help="Coloring strategy for single mode or non-compare batch mode.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run multiple random trees and print aggregate statistics.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="In batch mode, compare weighted and count_balanced on the same random trees.",
    )
    parser.add_argument(
        "--leaf-list",
        type=str,
        default="8,12,16,20",
        help="Comma-separated leaf counts for batch mode.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=50,
        help="Number of random trees per leaf count in batch mode.",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=1000,
        help="Starting seed for batch mode; seeds are seed_base + offset.",
    )
    args = parser.parse_args()

    if args.batch:
        leaf_sizes = parse_leaf_list(args.leaf_list)
        run_batch_mode(
            leaf_sizes=leaf_sizes,
            trials_per_size=args.trials,
            rounds=args.rounds,
            seed_base=args.seed_base,
            compare=args.compare,
            strategy=args.strategy,
        )
        return

    print_single_trial_detail(
        num_leaves=args.leaves,
        seed=args.seed,
        rebalance_rounds=args.rounds,
        strategy=args.strategy,
    )


if __name__ == "__main__":
    main()
