from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from statistics import mean
from time import perf_counter
from typing import Dict, Iterable, List, Sequence

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    max_chain_length,
    verify_coloring,
)
from run_sparse_smt_pir_backend_experiment import color_proof_nodes
from subtree_permutation_balance import best_profile_balanced_coloring


@dataclass
class TrialMetrics:
    height: int
    occupied_count: int
    distribution: str
    active_nodes: int
    exact_width: int
    hybrid_max_bucket: int
    hybrid_size_gap: int
    profile_max_bucket: int
    profile_size_gap: int
    profile_runtime_ms: float
    valid: bool


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def parse_str_list(raw: str) -> List[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("string list cannot be empty")
    return values


def _slots_to_heap_indices(slots: Iterable[int], tree_height: int) -> List[int]:
    base = 1 << tree_height
    return sorted(base + slot for slot in slots)


def sample_unique_slots(total_slots: int, occupied_count: int, rng: random.Random) -> List[int]:
    if total_slots <= 1_000_000:
        return sorted(rng.sample(range(total_slots), occupied_count))

    slots: set[int] = set()
    while len(slots) < occupied_count:
        slots.add(rng.randrange(total_slots))
    return sorted(slots)


def generate_occupied_leaves_with_distribution(
    tree_height: int,
    occupied_count: int,
    distribution: str,
    seed: int,
) -> List[int]:
    total_slots = 1 << tree_height
    occupied_count = max(1, min(total_slots, occupied_count))
    rng = random.Random(seed)

    if distribution == "uniform":
        slots = sample_unique_slots(total_slots, occupied_count, rng)
        return _slots_to_heap_indices(slots, tree_height)

    if distribution == "sequential":
        start = 0 if occupied_count >= total_slots else rng.randint(0, total_slots - occupied_count)
        slots = list(range(start, start + occupied_count))
        return _slots_to_heap_indices(slots, tree_height)

    if distribution == "clustered":
        cluster_count = max(1, min(4, occupied_count))
        base = occupied_count // cluster_count
        remainder = occupied_count % cluster_count
        window = min(total_slots, max(16, occupied_count * 4))
        slots_set: set[int] = set()
        for cluster_index in range(cluster_count):
            cluster_size = base + (1 if cluster_index < remainder else 0)
            if cluster_size == 0:
                continue
            if window >= total_slots:
                left = 0
            else:
                left = rng.randint(0, total_slots - window)
            candidates = list(range(left, min(total_slots, left + window)))
            if cluster_size >= len(candidates):
                chosen = candidates
            else:
                chosen = rng.sample(candidates, cluster_size)
            slots_set.update(chosen)

        while len(slots_set) < occupied_count:
            slots_set.add(rng.randrange(total_slots))
        slots = sorted(slots_set)[:occupied_count]
        return _slots_to_heap_indices(slots, tree_height)

    if distribution == "adversarial":
        dense_count = max(1, math.ceil(occupied_count * 0.75))
        dense_count = min(dense_count, occupied_count)
        sparse_count = occupied_count - dense_count
        slots: List[int] = list(range(dense_count))
        if sparse_count > 0:
            remaining = total_slots - dense_count
            for idx in range(sparse_count):
                pos = dense_count + ((idx + 1) * remaining) // (sparse_count + 1)
                slots.append(min(total_slots - 1, pos))
        return _slots_to_heap_indices(sorted(set(slots))[:occupied_count], tree_height)

    raise ValueError(f"unsupported distribution: {distribution}")


def run_single_trial(
    height: int,
    occupied_count: int,
    distribution: str,
    seed: int,
    initial_rounds: int,
    refine_rounds: int,
) -> TrialMetrics:
    occupied = generate_occupied_leaves_with_distribution(
        tree_height=height,
        occupied_count=occupied_count,
        distribution=distribution,
        seed=seed,
    )
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)

    hybrid_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    hybrid_roots = build_interval_forest(hybrid_nodes)
    exact_width = max_chain_length(hybrid_roots)
    hybrid_count_loads, _ = color_proof_nodes(
        proof_nodes=hybrid_nodes,
        roots=hybrid_roots,
        num_colors=exact_width,
        strategy="hybrid",
        rebalance_rounds=initial_rounds,
    )
    valid_hybrid, _ = verify_coloring(hybrid_roots, occupied)

    profile_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    profile_roots = build_interval_forest(profile_nodes)
    t0 = perf_counter()
    profile_result = best_profile_balanced_coloring(
        proof_nodes=profile_nodes,
        roots=profile_roots,
        num_colors=exact_width,
        initial_rounds=initial_rounds,
        refine_rounds=refine_rounds,
    )
    t1 = perf_counter()
    valid_profile, _ = verify_coloring(profile_roots, occupied)

    return TrialMetrics(
        height=height,
        occupied_count=occupied_count,
        distribution=distribution,
        active_nodes=len(profile_nodes),
        exact_width=exact_width,
        hybrid_max_bucket=max(hybrid_count_loads) if hybrid_count_loads else 0,
        hybrid_size_gap=max(hybrid_count_loads) - min(hybrid_count_loads) if hybrid_count_loads else 0,
        profile_max_bucket=profile_result.max_bucket,
        profile_size_gap=profile_result.size_gap,
        profile_runtime_ms=(t1 - t0) * 1000.0,
        valid=valid_hybrid and valid_profile,
    )


def summarize(trials: Sequence[TrialMetrics]) -> Dict[str, float]:
    return {
        "avg_active_nodes": mean(trial.active_nodes for trial in trials),
        "avg_exact_width": mean(trial.exact_width for trial in trials),
        "avg_hybrid_max": mean(trial.hybrid_max_bucket for trial in trials),
        "avg_hybrid_gap": mean(trial.hybrid_size_gap for trial in trials),
        "avg_profile_max": mean(trial.profile_max_bucket for trial in trials),
        "avg_profile_gap": mean(trial.profile_size_gap for trial in trials),
        "avg_runtime_ms": mean(trial.profile_runtime_ms for trial in trials),
        "valid_rate": mean(1.0 if trial.valid else 0.0 for trial in trials),
    }


def format_summary_line(height: int, occupied_count: int, distribution: str, stats: Dict[str, float]) -> str:
    reduction = 0.0
    if stats["avg_hybrid_max"] > 0:
        reduction = 100.0 * (1.0 - (stats["avg_profile_max"] / stats["avg_hybrid_max"]))
    return (
        f"height={height}, occupied={occupied_count}, dist={distribution}: "
        f"active_nodes={stats['avg_active_nodes']:.1f}, "
        f"m={stats['avg_exact_width']:.2f}, "
        f"hybrid_max={stats['avg_hybrid_max']:.2f}, "
        f"profile_max={stats['avg_profile_max']:.2f}, "
        f"reduction={reduction:.1f}%, "
        f"hybrid_gap={stats['avg_hybrid_gap']:.2f}, "
        f"profile_gap={stats['avg_profile_gap']:.2f}, "
        f"runtime_ms={stats['avg_runtime_ms']:.1f}, "
        f"valid_rate={stats['valid_rate'] * 100.0:.1f}%"
    )


def print_latex_table(trials: Sequence[TrialMetrics], heights: Sequence[int], distributions: Sequence[str], occupied_count: int) -> None:
    print("latex_table_rows:")
    for height in heights:
        for distribution in distributions:
            group = [
                trial
                for trial in trials
                if trial.height == height
                and trial.occupied_count == occupied_count
                and trial.distribution == distribution
            ]
            if not group:
                continue
            stats = summarize(group)
            reduction = 0.0
            if stats["avg_hybrid_max"] > 0:
                reduction = 100.0 * (1.0 - (stats["avg_profile_max"] / stats["avg_hybrid_max"]))
            print(
                f"{height} & {distribution} & "
                f"{stats['avg_active_nodes']:.1f} & {stats['avg_exact_width']:.2f} & "
                f"{stats['avg_hybrid_max']:.2f} & {stats['avg_profile_max']:.2f} & "
                f"{reduction:.1f}\\% & {stats['avg_profile_gap']:.2f} & "
                f"{stats['avg_runtime_ms']:.1f} \\\\"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scale exact-width profile balancing to larger SMT heights and non-uniform leaf distributions."
    )
    parser.add_argument("--heights", type=str, default="16,20,24", help="Comma-separated tree heights.")
    parser.add_argument("--occupied-counts", type=str, default="256", help="Comma-separated occupied-leaf counts.")
    parser.add_argument(
        "--distributions",
        type=str,
        default="uniform,clustered,adversarial",
        help="Comma-separated distributions: uniform, sequential, clustered, adversarial.",
    )
    parser.add_argument("--trials", type=int, default=3, help="Trials per setting.")
    parser.add_argument("--seed-base", type=int, default=26000, help="Base random seed.")
    parser.add_argument("--initial-rounds", type=int, default=120, help="Hybrid initializer rounds.")
    parser.add_argument("--refine-rounds", type=int, default=20, help="Profile-balancing rounds.")
    args = parser.parse_args()

    heights = parse_int_list(args.heights)
    occupied_counts = parse_int_list(args.occupied_counts)
    distributions = parse_str_list(args.distributions)

    print("=== Profile-Balanced Scale Experiment ===")
    print(f"heights={heights}")
    print(f"occupied_counts={occupied_counts}")
    print(f"distributions={distributions}")
    print(f"trials_per_setting={args.trials}")
    print(f"initial_rounds={args.initial_rounds}")
    print(f"refine_rounds={args.refine_rounds}")
    print()

    all_trials: List[TrialMetrics] = []
    for occupied_count in occupied_counts:
        print(f"[occupied_count={occupied_count}]")
        for height in heights:
            for distribution_index, distribution in enumerate(distributions):
                group: List[TrialMetrics] = []
                for offset in range(args.trials):
                    seed = (
                        args.seed_base
                        + occupied_count * 1000
                        + height * 100
                        + distribution_index * 10
                        + offset
                    )
                    trial = run_single_trial(
                        height=height,
                        occupied_count=occupied_count,
                        distribution=distribution,
                        seed=seed,
                        initial_rounds=args.initial_rounds,
                        refine_rounds=args.refine_rounds,
                    )
                    group.append(trial)
                    all_trials.append(trial)
                stats = summarize(group)
                print(format_summary_line(height, occupied_count, distribution, stats))
        print()

    if occupied_counts:
        print_latex_table(all_trials, heights, distributions, occupied_counts[0])


if __name__ == "__main__":
    main()
