from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Sequence

from compressed_proof_forest import (
    compress_unary_chain_forest,
    flatten_compressed_roots,
    max_compressed_chain_length,
    per_color_hash_loads,
    per_color_payload_loads,
    verify_compressed_coloring,
)
from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
    verify_coloring,
)
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


@dataclass
class SchemeMetrics:
    name: str
    protocol_colors: int
    stored_records: int
    stored_hashes: int
    avg_segment_length: float
    record_gap: int
    hash_gap: int
    weight_gap: int
    payload_gap: int
    record_gap_norm: float
    hash_gap_norm: float
    weight_gap_norm: float
    payload_gap_norm: float
    valid_rate: float


@dataclass
class TrialMetrics:
    strategy: str
    baseline: SchemeMetrics
    compressed_exact: SchemeMetrics
    compressed_original_budget: SchemeMetrics


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("list cannot be empty")
    return values


def parse_strategy_list(raw: str) -> List[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("strategy list cannot be empty")
    for value in values:
        if value not in {"weighted", "count_balanced", "hybrid"}:
            raise ValueError(f"unsupported strategy: {value}")
    return values


def normalized_gap(loads: Sequence[int]) -> float:
    if not loads:
        return 0.0
    average = sum(loads) / len(loads)
    if average == 0:
        return 0.0
    return (max(loads) - min(loads)) / average


def summarize_scheme(
    name: str,
    protocol_colors: int,
    record_loads: Sequence[int],
    hash_loads: Sequence[int],
    weight_loads: Sequence[int],
    payload_loads: Sequence[int],
    stored_records: int,
    stored_hashes: int,
    avg_segment_length: float,
    valid: bool,
) -> SchemeMetrics:
    return SchemeMetrics(
        name=name,
        protocol_colors=protocol_colors,
        stored_records=stored_records,
        stored_hashes=stored_hashes,
        avg_segment_length=avg_segment_length,
        record_gap=max(record_loads) - min(record_loads) if record_loads else 0,
        hash_gap=max(hash_loads) - min(hash_loads) if hash_loads else 0,
        weight_gap=max(weight_loads) - min(weight_loads) if weight_loads else 0,
        payload_gap=max(payload_loads) - min(payload_loads) if payload_loads else 0,
        record_gap_norm=normalized_gap(record_loads),
        hash_gap_norm=normalized_gap(hash_loads),
        weight_gap_norm=normalized_gap(weight_loads),
        payload_gap_norm=normalized_gap(payload_loads),
        valid_rate=1.0 if valid else 0.0,
    )


def aggregate(metrics: Sequence[SchemeMetrics]) -> SchemeMetrics:
    return SchemeMetrics(
        name=metrics[0].name,
        protocol_colors=round(mean(item.protocol_colors for item in metrics), 3),
        stored_records=round(mean(item.stored_records for item in metrics), 3),
        stored_hashes=round(mean(item.stored_hashes for item in metrics), 3),
        avg_segment_length=round(mean(item.avg_segment_length for item in metrics), 3),
        record_gap=round(mean(item.record_gap for item in metrics), 3),
        hash_gap=round(mean(item.hash_gap for item in metrics), 3),
        weight_gap=round(mean(item.weight_gap for item in metrics), 3),
        payload_gap=round(mean(item.payload_gap for item in metrics), 3),
        record_gap_norm=round(mean(item.record_gap_norm for item in metrics), 3),
        hash_gap_norm=round(mean(item.hash_gap_norm for item in metrics), 3),
        weight_gap_norm=round(mean(item.weight_gap_norm for item in metrics), 3),
        payload_gap_norm=round(mean(item.payload_gap_norm for item in metrics), 3),
        valid_rate=mean(item.valid_rate for item in metrics),
    )


def run_single_trial(
    tree_height: int,
    sparsity: float,
    seed: int,
    strategy: str,
    rebalance_rounds: int,
) -> TrialMetrics:
    occupied = generate_occupied_leaves(tree_height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=tree_height, occupied_leaves=occupied)

    active_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, tree_height)
    active_roots = build_interval_forest(active_nodes)
    baseline_colors = max_chain_length(active_roots)
    baseline_count_loads, baseline_weight_loads = color_proof_nodes(
        proof_nodes=active_nodes,
        roots=active_roots,
        num_colors=baseline_colors,
        strategy=strategy,
        rebalance_rounds=rebalance_rounds,
    )
    baseline_valid, _ = verify_coloring(active_roots, occupied)
    baseline_metrics = summarize_scheme(
        name="baseline",
        protocol_colors=baseline_colors,
        record_loads=baseline_count_loads,
        hash_loads=baseline_count_loads,
        weight_loads=baseline_weight_loads,
        payload_loads=baseline_weight_loads,
        stored_records=len(active_nodes),
        stored_hashes=len(active_nodes),
        avg_segment_length=1.0,
        valid=baseline_valid,
    )

    compressed_roots = compress_unary_chain_forest(active_roots, weight_mode="relevant")
    compressed_nodes = flatten_compressed_roots(compressed_roots)
    compressed_exact_colors = max_compressed_chain_length(compressed_roots)

    compressed_exact_count_loads, compressed_exact_weight_loads = color_proof_nodes(
        proof_nodes=compressed_nodes,
        roots=compressed_roots,
        num_colors=compressed_exact_colors,
        strategy=strategy,
        rebalance_rounds=rebalance_rounds,
    )
    compressed_exact_hash_loads = per_color_hash_loads(compressed_nodes, compressed_exact_colors)
    compressed_exact_payload_loads = per_color_payload_loads(compressed_nodes, compressed_exact_colors)
    compressed_exact_valid, _ = verify_compressed_coloring(compressed_roots, occupied)
    compressed_exact_metrics = summarize_scheme(
        name="compressed_exact",
        protocol_colors=compressed_exact_colors,
        record_loads=compressed_exact_count_loads,
        hash_loads=compressed_exact_hash_loads,
        weight_loads=compressed_exact_weight_loads,
        payload_loads=compressed_exact_payload_loads,
        stored_records=len(compressed_nodes),
        stored_hashes=sum(node.hash_count for node in compressed_nodes),
        avg_segment_length=(
            sum(node.hash_count for node in compressed_nodes) / len(compressed_nodes)
            if compressed_nodes
            else 0.0
        ),
        valid=compressed_exact_valid,
    )

    compressed_original_budget_count_loads, compressed_original_budget_weight_loads = color_proof_nodes(
        proof_nodes=compressed_nodes,
        roots=compressed_roots,
        num_colors=baseline_colors,
        strategy=strategy,
        rebalance_rounds=rebalance_rounds,
    )
    compressed_original_budget_hash_loads = per_color_hash_loads(compressed_nodes, baseline_colors)
    compressed_original_budget_payload_loads = per_color_payload_loads(compressed_nodes, baseline_colors)
    compressed_original_budget_valid, _ = verify_compressed_coloring(compressed_roots, occupied)
    compressed_original_budget_metrics = summarize_scheme(
        name="compressed_original_budget",
        protocol_colors=baseline_colors,
        record_loads=compressed_original_budget_count_loads,
        hash_loads=compressed_original_budget_hash_loads,
        weight_loads=compressed_original_budget_weight_loads,
        payload_loads=compressed_original_budget_payload_loads,
        stored_records=len(compressed_nodes),
        stored_hashes=sum(node.hash_count for node in compressed_nodes),
        avg_segment_length=(
            sum(node.hash_count for node in compressed_nodes) / len(compressed_nodes)
            if compressed_nodes
            else 0.0
        ),
        valid=compressed_original_budget_valid,
    )

    return TrialMetrics(
        strategy=strategy,
        baseline=baseline_metrics,
        compressed_exact=compressed_exact_metrics,
        compressed_original_budget=compressed_original_budget_metrics,
    )


def print_summary_block(label: str, trials: Sequence[TrialMetrics]) -> None:
    baseline = aggregate([trial.baseline for trial in trials])
    compressed_exact = aggregate([trial.compressed_exact for trial in trials])
    compressed_original_budget = aggregate([trial.compressed_original_budget for trial in trials])

    print(label)
    for item in [baseline, compressed_exact, compressed_original_budget]:
        print(
            f"  {item.name}: "
            f"colors={item.protocol_colors:.3f}, "
            f"records={item.stored_records:.3f}, "
            f"hashes={item.stored_hashes:.3f}, "
            f"avg_segment={item.avg_segment_length:.3f}, "
            f"record_gap_norm={item.record_gap_norm:.3f}, "
            f"hash_gap_norm={item.hash_gap_norm:.3f}, "
            f"weight_gap_norm={item.weight_gap_norm:.3f}, "
            f"payload_gap_norm={item.payload_gap_norm:.3f}, "
            f"valid_rate={item.valid_rate * 100:.1f}%"
        )

    width_ratio = (
        compressed_exact.protocol_colors / baseline.protocol_colors
        if baseline.protocol_colors
        else 0.0
    )
    record_ratio = (
        compressed_exact.stored_records / baseline.stored_records
        if baseline.stored_records
        else 0.0
    )
    hash_gap_ratio = (
        compressed_exact.hash_gap_norm / baseline.hash_gap_norm
        if baseline.hash_gap_norm
        else 0.0
    )
    weight_gap_ratio = (
        compressed_exact.weight_gap_norm / baseline.weight_gap_norm
        if baseline.weight_gap_norm
        else 0.0
    )
    payload_gap_ratio = (
        compressed_exact.payload_gap_norm / baseline.payload_gap_norm
        if baseline.payload_gap_norm
        else 0.0
    )
    print(
        "  deltas(compressed_exact vs baseline): "
        f"width_ratio={width_ratio:.3f}, "
        f"record_ratio={record_ratio:.3f}, "
        f"hash_gap_ratio={hash_gap_ratio:.3f}, "
        f"weight_gap_ratio={weight_gap_ratio:.3f}, "
        f"payload_gap_ratio={payload_gap_ratio:.3f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the interval forest against a branch-compressed multiary proof forest."
    )
    parser.add_argument("--height", type=int, default=10, help="Sparse SMT height.")
    parser.add_argument("--sparsities", type=str, default="0.2,0.5,0.8,0.9,0.95", help="Comma-separated empty-leaf ratios.")
    parser.add_argument("--trials", type=int, default=20, help="Trials per sparsity.")
    parser.add_argument("--seed-base", type=int, default=9100, help="Base seed.")
    parser.add_argument("--rounds", type=int, default=400, help="Local rebalance rounds.")
    parser.add_argument(
        "--strategies",
        type=str,
        default="weighted,count_balanced,hybrid",
        help="Comma-separated coloring strategies.",
    )
    args = parser.parse_args()

    sparsities = parse_float_list(args.sparsities)
    strategies = parse_strategy_list(args.strategies)

    print("=== Branch-Compressed Forest Balance Experiment ===")
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
            current_trials: List[TrialMetrics] = []
            for offset in range(args.trials):
                seed = args.seed_base + strategy_index * 100000 + sparsity_index * 1000 + offset
                trial = run_single_trial(
                    tree_height=args.height,
                    sparsity=sparsity,
                    seed=seed,
                    strategy=strategy,
                    rebalance_rounds=args.rounds,
                )
                current_trials.append(trial)
                overall.append(trial)
            print_summary_block(f"  sparsity={sparsity:.2f}", current_trials)
        print_summary_block("  overall", overall)
        print()


if __name__ == "__main__":
    main()
