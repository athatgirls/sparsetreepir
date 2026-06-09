from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Sequence

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
)
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


@dataclass
class SchemeMetrics:
    name: str
    stored_nodes: int
    size_gap: int
    weight_gap: int
    max_bucket: int
    min_bucket: int
    valid_rate: float


@dataclass
class TrialMetrics:
    strategy: str
    active_only: SchemeMetrics
    all_nodes: SchemeMetrics
    perfectized_depth: SchemeMetrics


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("list cannot be empty")
    return values


def objective_score(strategy: str, count_loads: Sequence[int], weight_loads: Sequence[int]) -> tuple[float, int, int, int]:
    count_gap = max(count_loads) - min(count_loads)
    weight_gap = max(weight_loads) - min(weight_loads)
    if strategy == "count_balanced":
        return (float(count_gap), count_gap, weight_gap, max(count_loads))
    if strategy == "weighted":
        return (float(weight_gap), weight_gap, count_gap, max(count_loads))
    avg_count = max(1.0, sum(count_loads) / len(count_loads))
    avg_weight = max(1.0, sum(weight_loads) / len(weight_loads))
    hybrid = (weight_gap / avg_weight) + (count_gap / avg_count)
    return (hybrid, count_gap, weight_gap, max(count_loads))


def pad_with_inactive_nodes(
    count_loads: Sequence[int],
    weight_loads: Sequence[int],
    extra_nodes: int,
    strategy: str,
) -> tuple[List[int], List[int]]:
    padded_counts = list(count_loads)
    padded_weights = list(weight_loads)

    for _ in range(extra_nodes):
        best_color = None
        best_key = None
        for color in range(len(padded_counts)):
            candidate_counts = list(padded_counts)
            candidate_counts[color] += 1
            candidate_key = objective_score(strategy, candidate_counts, padded_weights)
            if best_key is None or candidate_key < best_key:
                best_key = candidate_key
                best_color = color
        padded_counts[best_color] += 1  # type: ignore[index]

    return padded_counts, padded_weights


def summarize_scheme(name: str, count_loads: Sequence[int], weight_loads: Sequence[int], stored_nodes: int, valid: bool) -> SchemeMetrics:
    return SchemeMetrics(
        name=name,
        stored_nodes=stored_nodes,
        size_gap=max(count_loads) - min(count_loads) if count_loads else 0,
        weight_gap=max(weight_loads) - min(weight_loads) if weight_loads else 0,
        max_bucket=max(count_loads) if count_loads else 0,
        min_bucket=min(count_loads) if count_loads else 0,
        valid_rate=1.0 if valid else 0.0,
    )


def run_single_trial(tree_height: int, sparsity: float, seed: int, strategy: str, rebalance_rounds: int) -> TrialMetrics:
    occupied = generate_occupied_leaves(tree_height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=tree_height, occupied_leaves=occupied)

    active_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, tree_height)
    active_roots = build_interval_forest(active_nodes)
    active_colors = tree_height
    active_count_loads, active_weight_loads = color_proof_nodes(
        proof_nodes=active_nodes,
        roots=active_roots,
        num_colors=active_colors,
        strategy=strategy,
        rebalance_rounds=rebalance_rounds,
    )
    active_valid = True
    active_metrics = summarize_scheme(
        name="active_only",
        count_loads=active_count_loads,
        weight_loads=active_weight_loads,
        stored_nodes=len(active_nodes),
        valid=active_valid,
    )

    perfectized_nodes = (1 << (tree_height + 1)) - 2
    extra_nodes = perfectized_nodes - len(active_nodes)
    all_count_loads, all_weight_loads = pad_with_inactive_nodes(
        count_loads=active_count_loads,
        weight_loads=active_weight_loads,
        extra_nodes=extra_nodes,
        strategy=strategy,
    )
    all_valid = True
    all_metrics = summarize_scheme(
        name="all_nodes",
        count_loads=all_count_loads,
        weight_loads=all_weight_loads,
        stored_nodes=perfectized_nodes,
        valid=all_valid,
    )

    perfectized_sizes = [1 << depth for depth in range(1, tree_height + 1)]
    perfectized_weight_loads = [len(occupied)] * tree_height
    perfectized_metrics = summarize_scheme(
        name="perfectized_depth",
        count_loads=perfectized_sizes,
        weight_loads=perfectized_weight_loads,
        stored_nodes=sum(perfectized_sizes),
        valid=True,
    )

    return TrialMetrics(
        strategy=strategy,
        active_only=active_metrics,
        all_nodes=all_metrics,
        perfectized_depth=perfectized_metrics,
    )


def aggregate(metrics: Sequence[SchemeMetrics]) -> SchemeMetrics:
    return SchemeMetrics(
        name=metrics[0].name,
        stored_nodes=round(mean(item.stored_nodes for item in metrics)),
        size_gap=round(mean(item.size_gap for item in metrics), 3),
        weight_gap=round(mean(item.weight_gap for item in metrics), 3),
        max_bucket=round(mean(item.max_bucket for item in metrics), 3),
        min_bucket=round(mean(item.min_bucket for item in metrics), 3),
        valid_rate=mean(item.valid_rate for item in metrics),
    )


def print_triplet(label: str, trials: Sequence[TrialMetrics]) -> None:
    active_summary = aggregate([item.active_only for item in trials])
    all_summary = aggregate([item.all_nodes for item in trials])
    perfect_summary = aggregate([item.perfectized_depth for item in trials])

    print(label)
    for item in [active_summary, all_summary, perfect_summary]:
        print(
            f"  {item.name}: "
            f"stored_nodes={item.stored_nodes}, "
            f"size_gap={item.size_gap:.3f}, "
            f"weight_gap={item.weight_gap:.3f}, "
            f"bucket_range=[{item.min_bucket:.3f}, {item.max_bucket:.3f}], "
            f"valid_rate={item.valid_rate * 100:.1f}%"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare active-only storage against putting all non-root nodes into subdatabases."
    )
    parser.add_argument("--height", type=int, default=10, help="Sparse SMT height.")
    parser.add_argument("--sparsities", type=str, default="0.2,0.5,0.8", help="Comma-separated empty-leaf ratios.")
    parser.add_argument("--trials", type=int, default=20, help="Trials per sparsity.")
    parser.add_argument("--seed-base", type=int, default=7000, help="Base seed.")
    parser.add_argument("--rounds", type=int, default=400, help="Local rebalance rounds.")
    parser.add_argument(
        "--strategies",
        type=str,
        default="weighted,count_balanced,hybrid",
        help="Comma-separated strategies to compare.",
    )
    args = parser.parse_args()

    sparsities = parse_float_list(args.sparsities)
    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    if not strategies:
        raise ValueError("at least one strategy is required")

    print("=== Active-Only vs All-Nodes Balance Experiment ===")
    print(f"height={args.height}")
    print(f"sparsities={sparsities}")
    print(f"trials_per_sparsity={args.trials}")
    print(f"seed_base={args.seed_base}")
    print(f"rebalance_rounds={args.rounds}")
    print(f"strategies={strategies}")
    print()

    for strategy_index, strategy in enumerate(strategies):
        print(f"strategy={strategy}")
        overall: List[TrialMetrics] = []
        for sparsity_index, sparsity in enumerate(sparsities):
            trials: List[TrialMetrics] = []
            for offset in range(args.trials):
                seed = args.seed_base + strategy_index * 10000 + sparsity_index * 1000 + offset
                trial = run_single_trial(
                    tree_height=args.height,
                    sparsity=sparsity,
                    seed=seed,
                    strategy=strategy,
                    rebalance_rounds=args.rounds,
                )
                trials.append(trial)
                overall.append(trial)
            print_triplet(f"  sparsity={sparsity:.2f}", trials)
        print_triplet("  overall", overall)
        print()


if __name__ == "__main__":
    main()
