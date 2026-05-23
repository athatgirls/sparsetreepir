from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Sequence

from budgeted_minmax_coloring import (
    budgeted_min_max_size_search,
    color_proof_nodes_min_max_size,
)
from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
    verify_coloring,
)
from run_pir_cost_model_experiment import backend_costs, build_backend_models
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


@dataclass
class SchemeMetrics:
    name: str
    colors: int
    stored_nodes: int
    lower_bound: int
    max_bucket: int
    avg_bucket: float
    bucket_ratio: float
    optimality_ratio: float
    size_gap: int
    weight_gap: int
    query_ms: float
    extract_ms: float
    server_max_ms: float
    online_proxy_ms: float
    valid_rate: float


@dataclass
class TrialMetrics:
    exact_width: int
    strategies: Dict[str, SchemeMetrics]


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
    backend_name: str,
    backends,
    server_weight: float,
) -> SchemeMetrics:
    costs = backend_costs(backends[backend_name], count_loads)
    max_bucket = max(count_loads) if count_loads else 0
    avg_bucket = (sum(count_loads) / len(count_loads)) if count_loads else 0.0
    lower_bound = math.ceil(stored_nodes / colors) if colors > 0 else 0
    return SchemeMetrics(
        name=name,
        colors=colors,
        stored_nodes=stored_nodes,
        lower_bound=lower_bound,
        max_bucket=max_bucket,
        avg_bucket=avg_bucket,
        bucket_ratio=(max_bucket / avg_bucket) if avg_bucket > 0 else 0.0,
        optimality_ratio=(max_bucket / lower_bound) if lower_bound > 0 else 0.0,
        size_gap=max(count_loads) - min(count_loads) if count_loads else 0,
        weight_gap=max(weight_loads) - min(weight_loads) if weight_loads else 0,
        query_ms=float(costs["query_total_ms"]),
        extract_ms=float(costs["extract_total_ms"]),
        server_max_ms=float(costs["server_max_ms"]),
        online_proxy_ms=float(
            costs["query_total_ms"] + costs["extract_total_ms"] + server_weight * costs["server_max_ms"]
        ),
        valid_rate=1.0 if valid else 0.0,
    )


def aggregate(metrics: Sequence[SchemeMetrics]) -> SchemeMetrics:
    return SchemeMetrics(
        name=metrics[0].name,
        colors=round(mean(item.colors for item in metrics), 3),
        stored_nodes=round(mean(item.stored_nodes for item in metrics), 3),
        lower_bound=round(mean(item.lower_bound for item in metrics), 3),
        max_bucket=round(mean(item.max_bucket for item in metrics), 3),
        avg_bucket=round(mean(item.avg_bucket for item in metrics), 3),
        bucket_ratio=round(mean(item.bucket_ratio for item in metrics), 3),
        optimality_ratio=round(mean(item.optimality_ratio for item in metrics), 3),
        size_gap=round(mean(item.size_gap for item in metrics), 3),
        weight_gap=round(mean(item.weight_gap for item in metrics), 3),
        query_ms=round(mean(item.query_ms for item in metrics), 3),
        extract_ms=round(mean(item.extract_ms for item in metrics), 3),
        server_max_ms=round(mean(item.server_max_ms for item in metrics), 3),
        online_proxy_ms=round(mean(item.online_proxy_ms for item in metrics), 3),
        valid_rate=mean(item.valid_rate for item in metrics),
    )


def run_single_trial(
    tree_height: int,
    sparsity: float,
    seed: int,
    rebalance_rounds: int,
    max_extra_colors: int,
    backend_name: str,
    server_weight: float,
    backends,
) -> TrialMetrics:
    occupied = generate_occupied_leaves(tree_height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=tree_height, occupied_leaves=occupied)
    proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, tree_height)
    roots = build_interval_forest(proof_nodes)
    exact_width = max_chain_length(roots)
    stored_nodes = len(proof_nodes)

    strategies: Dict[str, SchemeMetrics] = {}

    for strategy in ["weighted", "count_balanced", "hybrid"]:
        count_loads, weight_loads = color_proof_nodes(
            proof_nodes=proof_nodes,
            roots=roots,
            num_colors=exact_width,
            strategy=strategy,
            rebalance_rounds=rebalance_rounds,
        )
        valid, _ = verify_coloring(roots, occupied)
        strategies[strategy] = summarize_scheme(
            name=strategy,
            colors=exact_width,
            count_loads=count_loads,
            weight_loads=weight_loads,
            stored_nodes=stored_nodes,
            valid=valid,
            backend_name=backend_name,
            backends=backends,
            server_weight=server_weight,
        )

    minmax_exact = color_proof_nodes_min_max_size(
        proof_nodes=proof_nodes,
        roots=roots,
        num_colors=exact_width,
        rebalance_rounds=rebalance_rounds,
    )
    valid, _ = verify_coloring(roots, occupied)
    strategies["min_max_size_Beqm"] = summarize_scheme(
        name="min_max_size_Beqm",
        colors=exact_width,
        count_loads=minmax_exact.count_loads,
        weight_loads=minmax_exact.weight_loads,
        stored_nodes=stored_nodes,
        valid=valid,
        backend_name=backend_name,
        backends=backends,
        server_weight=server_weight,
    )

    for extra in range(1, max_extra_colors + 1):
        budget = exact_width + extra
        fixed = color_proof_nodes_min_max_size(
            proof_nodes=proof_nodes,
            roots=roots,
            num_colors=budget,
            rebalance_rounds=rebalance_rounds,
        )
        valid, _ = verify_coloring(roots, occupied)
        strategies[f"min_max_size_Beqm_plus_{extra}"] = summarize_scheme(
            name=f"min_max_size_Beqm_plus_{extra}",
            colors=budget,
            count_loads=fixed.count_loads,
            weight_loads=fixed.weight_loads,
            stored_nodes=stored_nodes,
            valid=valid,
            backend_name=backend_name,
            backends=backends,
            server_weight=server_weight,
        )

    budgeted = budgeted_min_max_size_search(
        proof_nodes=proof_nodes,
        roots=roots,
        min_colors=exact_width,
        max_colors=exact_width + max_extra_colors,
        rebalance_rounds=rebalance_rounds,
        backend_name=backend_name,
        backend_models=backends,
        server_weight=server_weight,
    )
    strategies["budgeted_min_max_size"] = SchemeMetrics(
        name="budgeted_min_max_size",
        colors=budgeted.chosen_colors,
        stored_nodes=stored_nodes,
        lower_bound=math.ceil(stored_nodes / budgeted.chosen_colors) if budgeted.chosen_colors > 0 else 0,
        max_bucket=max(budgeted.count_loads) if budgeted.count_loads else 0,
        avg_bucket=(sum(budgeted.count_loads) / len(budgeted.count_loads)) if budgeted.count_loads else 0.0,
        bucket_ratio=(
            (max(budgeted.count_loads) / (sum(budgeted.count_loads) / len(budgeted.count_loads)))
            if budgeted.count_loads and sum(budgeted.count_loads) > 0
            else 0.0
        ),
        optimality_ratio=(
            (max(budgeted.count_loads) / math.ceil(stored_nodes / budgeted.chosen_colors))
            if budgeted.count_loads and budgeted.chosen_colors > 0
            else 0.0
        ),
        size_gap=max(budgeted.count_loads) - min(budgeted.count_loads) if budgeted.count_loads else 0,
        weight_gap=max(budgeted.weight_loads) - min(budgeted.weight_loads) if budgeted.weight_loads else 0,
        query_ms=budgeted.query_ms,
        extract_ms=budgeted.extract_ms,
        server_max_ms=budgeted.server_max_ms,
        online_proxy_ms=budgeted.score,
        valid_rate=1.0,
    )

    return TrialMetrics(
        exact_width=exact_width,
        strategies=strategies,
    )


def print_summary(label: str, trials: Sequence[TrialMetrics], max_extra_colors: int) -> None:
    names = ["weighted", "count_balanced", "hybrid", "min_max_size_Beqm"]
    names.extend([f"min_max_size_Beqm_plus_{extra}" for extra in range(1, max_extra_colors + 1)])
    names.append("budgeted_min_max_size")

    summaries = {
        name: aggregate([trial.strategies[name] for trial in trials])
        for name in names
    }
    avg_m = mean(trial.exact_width for trial in trials)
    minmax_base = summaries["min_max_size_Beqm"]
    hybrid_base = summaries["hybrid"]

    print(label)
    print(f"  avg_exact_width_m={avg_m:.3f}")
    for name in names:
        item = summaries[name]
        reduction = (
            1.0 - (item.max_bucket / minmax_base.max_bucket)
            if minmax_base.max_bucket > 0
            else 0.0
        )
        reduction_vs_hybrid = (
            1.0 - (item.max_bucket / hybrid_base.max_bucket)
            if hybrid_base.max_bucket > 0
            else 0.0
        )
        print(
            f"  {name}: "
            f"B={item.colors:.3f}, "
            f"max_bucket={item.max_bucket:.3f}, "
            f"avg_bucket={item.avg_bucket:.3f}, "
            f"bucket_ratio={item.bucket_ratio:.3f}, "
            f"opt_ratio={item.optimality_ratio:.3f}, "
            f"size_gap={item.size_gap:.3f}, "
            f"weight_gap={item.weight_gap:.3f}, "
            f"lb_ceiling={item.lower_bound:.3f}, "
            f"reduction_vs_minmax_m={reduction * 100:.1f}%, "
            f"reduction_vs_hybrid={reduction_vs_hybrid * 100:.1f}%, "
            f"online_proxy={item.online_proxy_ms:.3f}ms, "
            f"server_max={item.server_max_ms:.3f}ms, "
            f"valid_rate={item.valid_rate * 100:.1f}%"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate fixed-budget and budgeted min-max-size coloring on sparse SMT interval forests."
    )
    parser.add_argument("--height", type=int, default=10, help="Sparse SMT height.")
    parser.add_argument(
        "--sparsities",
        type=str,
        default="0.5,0.8,0.9,0.95,0.98",
        help="Comma-separated empty-leaf ratios.",
    )
    parser.add_argument("--trials", type=int, default=20, help="Trials per sparsity.")
    parser.add_argument("--seed-base", type=int, default=13000, help="Base random seed.")
    parser.add_argument("--rounds", type=int, default=300, help="Local rebalance rounds.")
    parser.add_argument("--max-extra-colors", type=int, default=4, help="Test budgets B=m..m+delta.")
    parser.add_argument(
        "--backend",
        type=str,
        default="sealpir_like",
        choices=["sealpir_like", "spiral_like"],
        help="Backend cost model used by the budgeted search and printed proxy.",
    )
    parser.add_argument(
        "--server-weight",
        type=float,
        default=1.0,
        help="Weight applied to server-parallel cost inside the online proxy.",
    )
    args = parser.parse_args()

    sparsities = parse_float_list(args.sparsities)
    backends = build_backend_models()

    print("=== Budgeted Min-Max-Size Coloring Experiment ===")
    print(f"height={args.height}")
    print(f"sparsities={sparsities}")
    print(f"trials_per_sparsity={args.trials}")
    print(f"seed_base={args.seed_base}")
    print(f"rebalance_rounds={args.rounds}")
    print(f"max_extra_colors={args.max_extra_colors}")
    print(f"backend={args.backend}")
    print(f"server_weight={args.server_weight}")
    print("exact-width baselines=['weighted','count_balanced','hybrid','min_max_size_Beqm']")
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
                rebalance_rounds=args.rounds,
                max_extra_colors=args.max_extra_colors,
                backend_name=args.backend,
                server_weight=args.server_weight,
                backends=backends,
            )
            current_trials.append(trial)
            overall.append(trial)
        print_summary(f"sparsity={sparsity:.2f}", current_trials, args.max_extra_colors)

    print_summary("overall", overall, args.max_extra_colors)


if __name__ == "__main__":
    main()
