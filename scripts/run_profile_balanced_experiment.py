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
    max_chain_length,
    verify_coloring,
)
from run_sparse_smt_pir_backend_experiment import color_proof_nodes
from subtree_permutation_balance import best_profile_balanced_coloring


@dataclass
class SchemeMetrics:
    name: str
    colors: int
    stored_nodes: int
    max_bucket: int
    avg_bucket: float
    bucket_ratio: float
    size_gap: int
    weight_gap: int
    valid_rate: float


@dataclass
class TrialMetrics:
    exact_width: int
    schemes: Dict[str, SchemeMetrics]


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("list cannot be empty")
    return values


def summarize_scheme(
    name: str,
    colors: int,
    count_loads: Sequence[int],
    weight_loads: Sequence[int],
    stored_nodes: int,
    valid: bool,
) -> SchemeMetrics:
    max_bucket = max(count_loads) if count_loads else 0
    avg_bucket = (sum(count_loads) / len(count_loads)) if count_loads else 0.0
    return SchemeMetrics(
        name=name,
        colors=colors,
        stored_nodes=stored_nodes,
        max_bucket=max_bucket,
        avg_bucket=avg_bucket,
        bucket_ratio=(max_bucket / avg_bucket) if avg_bucket > 0 else 0.0,
        size_gap=max(count_loads) - min(count_loads) if count_loads else 0,
        weight_gap=max(weight_loads) - min(weight_loads) if weight_loads else 0,
        valid_rate=1.0 if valid else 0.0,
    )


def aggregate(metrics: Sequence[SchemeMetrics]) -> SchemeMetrics:
    return SchemeMetrics(
        name=metrics[0].name,
        colors=round(mean(item.colors for item in metrics), 3),
        stored_nodes=round(mean(item.stored_nodes for item in metrics), 3),
        max_bucket=round(mean(item.max_bucket for item in metrics), 3),
        avg_bucket=round(mean(item.avg_bucket for item in metrics), 3),
        bucket_ratio=round(mean(item.bucket_ratio for item in metrics), 3),
        size_gap=round(mean(item.size_gap for item in metrics), 3),
        weight_gap=round(mean(item.weight_gap for item in metrics), 3),
        valid_rate=mean(item.valid_rate for item in metrics),
    )


def run_single_trial(
    tree_height: int,
    sparsity: float,
    seed: int,
    initial_rounds: int,
    refine_rounds: int,
) -> TrialMetrics:
    occupied = generate_occupied_leaves(tree_height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=tree_height, occupied_leaves=occupied)

    schemes: Dict[str, SchemeMetrics] = {}
    for strategy in ["weighted", "count_balanced", "hybrid", "profile_balanced"]:
        proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, tree_height)
        roots = build_interval_forest(proof_nodes)
        exact_width = max_chain_length(roots)

        if strategy == "profile_balanced":
            result = best_profile_balanced_coloring(
                proof_nodes=proof_nodes,
                roots=roots,
                num_colors=exact_width,
                initial_rounds=initial_rounds,
                refine_rounds=refine_rounds,
            )
            count_loads = result.count_loads
            weight_loads = result.weight_loads
        else:
            count_loads, weight_loads = color_proof_nodes(
                proof_nodes=proof_nodes,
                roots=roots,
                num_colors=exact_width,
                strategy=strategy,
                rebalance_rounds=initial_rounds,
            )

        valid, _ = verify_coloring(roots, occupied)
        schemes[strategy] = summarize_scheme(
            name=strategy,
            colors=exact_width,
            count_loads=count_loads,
            weight_loads=weight_loads,
            stored_nodes=len(proof_nodes),
            valid=valid,
        )

    return TrialMetrics(
        exact_width=schemes["weighted"].colors,
        schemes=schemes,
    )


def print_summary(label: str, trials: Sequence[TrialMetrics]) -> None:
    names = ["weighted", "count_balanced", "hybrid", "profile_balanced"]
    summaries = {
        name: aggregate([trial.schemes[name] for trial in trials])
        for name in names
    }
    hybrid = summaries["hybrid"]
    profile = summaries["profile_balanced"]
    print(label)
    print(f"  avg_exact_width_m={mean(trial.exact_width for trial in trials):.3f}")
    for name in names:
        item = summaries[name]
        reduction_vs_hybrid = (
            1.0 - (item.max_bucket / hybrid.max_bucket)
            if hybrid.max_bucket > 0
            else 0.0
        )
        print(
            f"  {name}: "
            f"max_bucket={item.max_bucket:.3f}, "
            f"avg_bucket={item.avg_bucket:.3f}, "
            f"bucket_ratio={item.bucket_ratio:.3f}, "
            f"size_gap={item.size_gap:.3f}, "
            f"weight_gap={item.weight_gap:.3f}, "
            f"reduction_vs_hybrid={reduction_vs_hybrid * 100:.1f}%, "
            f"valid_rate={item.valid_rate * 100:.1f}%"
        )
    print(
        "  profile_vs_hybrid: "
        f"max_bucket_delta={profile.max_bucket - hybrid.max_bucket:.3f}, "
        f"size_gap_delta={profile.size_gap - hybrid.size_gap:.3f}, "
        f"bucket_ratio_delta={profile.bucket_ratio - hybrid.bucket_ratio:.3f}"
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare subtree-permutation profile balancing against existing exact-width forest colorings."
    )
    parser.add_argument("--height", type=int, default=10, help="Sparse SMT height.")
    parser.add_argument(
        "--sparsities",
        type=str,
        default="0.5,0.8,0.9,0.95,0.98",
        help="Comma-separated empty-leaf ratios.",
    )
    parser.add_argument("--trials", type=int, default=20, help="Trials per sparsity.")
    parser.add_argument("--seed-base", type=int, default=17000, help="Base random seed.")
    parser.add_argument("--initial-rounds", type=int, default=400, help="Initial local rebalance rounds.")
    parser.add_argument("--refine-rounds", type=int, default=120, help="Subtree-permutation passes.")
    args = parser.parse_args()

    sparsities = parse_float_list(args.sparsities)

    print("=== Profile-Balanced Forest Coloring Experiment ===")
    print(f"height={args.height}")
    print(f"sparsities={sparsities}")
    print(f"trials_per_sparsity={args.trials}")
    print(f"seed_base={args.seed_base}")
    print(f"initial_rounds={args.initial_rounds}")
    print(f"refine_rounds={args.refine_rounds}")
    print("schemes=['weighted','count_balanced','hybrid','profile_balanced']")
    print()

    overall: List[TrialMetrics] = []
    for sparsity_index, sparsity in enumerate(sparsities):
        current_trials: List[TrialMetrics] = []
        for offset in range(args.trials):
            seed = args.seed_base + sparsity_index * 1000 + offset
            trial = run_single_trial(
                tree_height=args.height,
                sparsity=sparsity,
                seed=seed,
                initial_rounds=args.initial_rounds,
                refine_rounds=args.refine_rounds,
            )
            current_trials.append(trial)
            overall.append(trial)
        print_summary(f"sparsity={sparsity:.2f}", current_trials)

    print_summary("overall", overall)


if __name__ == "__main__":
    main()

