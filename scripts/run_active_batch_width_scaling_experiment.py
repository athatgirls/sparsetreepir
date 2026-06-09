from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import mean
from typing import Iterable, List, Sequence

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)


@dataclass
class TrialSummary:
    height: int
    sparsity: float
    occupied_leaves: int
    active_nodes: int
    perfectized_nodes: int
    active_width: int


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("height list cannot be empty")
    return values


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("sparsity list cannot be empty")
    return values


def perfectized_non_root_nodes(height: int) -> int:
    return (1 << (height + 1)) - 2


def run_trial(height: int, sparsity: float, seed: int) -> TrialSummary:
    occupied = generate_occupied_leaves(tree_height=height, sparsity=sparsity, seed=seed)
    compressed = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    proof_nodes = build_full_proof_nodes(
        raw_nodes=compressed.raw_nodes,
        occupied_leaves=occupied,
        tree_height=height,
    )
    roots = build_interval_forest(proof_nodes)
    active_width = max_chain_length(roots)
    return TrialSummary(
        height=height,
        sparsity=sparsity,
        occupied_leaves=len(occupied),
        active_nodes=len(proof_nodes),
        perfectized_nodes=perfectized_non_root_nodes(height),
        active_width=active_width,
    )


def summarize(trials: Sequence[TrialSummary]) -> dict[str, float]:
    avg_perfectized = mean(trial.perfectized_nodes for trial in trials)
    avg_height = mean(trial.height for trial in trials)
    avg_active_nodes = mean(trial.active_nodes for trial in trials)
    avg_active_width = mean(trial.active_width for trial in trials)
    return {
        "trials": float(len(trials)),
        "avg_occupied_leaves": mean(trial.occupied_leaves for trial in trials),
        "avg_active_nodes": avg_active_nodes,
        "avg_perfectized_nodes": avg_perfectized,
        "avg_storage_ratio": avg_active_nodes / avg_perfectized if avg_perfectized else 0.0,
        "avg_active_width": avg_active_width,
        "avg_width_ratio": avg_active_width / avg_height if avg_height else 0.0,
        "min_active_width": float(min(trial.active_width for trial in trials)),
        "max_active_width": float(max(trial.active_width for trial in trials)),
    }


def format_line(height: int, sparsity: float, stats: dict[str, float]) -> str:
    return (
        f"height={height}, sparsity={sparsity:.2f}: "
        f"avg_occupied={stats['avg_occupied_leaves']:.2f}, "
        f"avg_active_nodes={stats['avg_active_nodes']:.2f}, "
        f"storage_ratio={stats['avg_storage_ratio']:.3f}, "
        f"avg_m={stats['avg_active_width']:.2f}, "
        f"m_over_h={stats['avg_width_ratio']:.3f}, "
        f"width_range=[{int(stats['min_active_width'])}, {int(stats['max_active_width'])}]"
    )


def grouped_trials(trials: Iterable[TrialSummary], height: int, sparsity: float) -> List[TrialSummary]:
    return [
        trial
        for trial in trials
        if trial.height == height and abs(trial.sparsity - sparsity) < 1e-12
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure how the exact active batch width m and active-node storage "
            "scale with SMT sparsity."
        )
    )
    parser.add_argument("--height-list", type=str, default="10", help="Comma-separated tree heights.")
    parser.add_argument(
        "--sparsity-list",
        type=str,
        default="0.2,0.5,0.8,0.9,0.95,0.98",
        help="Comma-separated empty-leaf ratios.",
    )
    parser.add_argument("--trials", type=int, default=20, help="Trials per (height, sparsity) setting.")
    parser.add_argument("--seed-base", type=int, default=12000, help="Base seed.")
    args = parser.parse_args()

    heights = parse_int_list(args.height_list)
    sparsities = parse_float_list(args.sparsity_list)

    print("=== Active Batch Width Scaling Experiment ===")
    print(f"heights={heights}")
    print(f"sparsities={sparsities}")
    print(f"trials_per_setting={args.trials}")
    print(f"seed_base={args.seed_base}")
    print()

    all_trials: List[TrialSummary] = []
    for height in heights:
        print(f"[height={height}]")
        for sparsity_index, sparsity in enumerate(sparsities):
            trials: List[TrialSummary] = []
            for offset in range(args.trials):
                seed = args.seed_base + (height * 10000) + (sparsity_index * 1000) + offset
                trial = run_trial(height=height, sparsity=sparsity, seed=seed)
                trials.append(trial)
                all_trials.append(trial)
            stats = summarize(trials)
            print(format_line(height, sparsity, stats))
        print()

    print("[overall]")
    overall = summarize(all_trials)
    print(
        "overall: "
        f"avg_occupied={overall['avg_occupied_leaves']:.2f}, "
        f"avg_active_nodes={overall['avg_active_nodes']:.2f}, "
        f"avg_storage_ratio={overall['avg_storage_ratio']:.3f}, "
        f"avg_m={overall['avg_active_width']:.2f}, "
        f"m_over_h={overall['avg_width_ratio']:.3f}"
    )


if __name__ == "__main__":
    main()
