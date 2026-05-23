from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Sequence

from direct_arbitrary_merkle_coloring import DirectArbitraryMerkleColoring
from run_random_merkle_coloring_experiment import build_random_merkle_tree


PERFECT_TREE_H = [10, 12, 14, 16, 18, 20]

# TreePIR paper measurements for TreePIR + SealPIR / Spiral on perfect trees.
# Query/extraction tables report total batch cost over h subdatabases.
SEAL_QUERY_TOTAL_MS = [13.0, 16.0, 18.0, 21.0, 24.0, 27.0]
SEAL_EXTRACT_TOTAL_MS = [12.6, 15.0, 17.2, 19.4, 22.2, 24.3]
SEAL_SERVER_MAX_MS = [5.8, 5.8, 9.1, 18.9, 36.0, 76.0]

SPIRAL_QUERY_TOTAL_MS = [20.0, 24.0, 29.0, 33.0, 37.0, 41.0]
SPIRAL_EXTRACT_TOTAL_MS = [5.8, 7.2, 8.4, 9.6, 10.5, 12.2]
SPIRAL_SERVER_MAX_MS = [30.0, 31.0, 31.0, 31.0, 32.0, 33.0]


@dataclass
class PowerLawModel:
    coefficient: float
    exponent: float

    def evaluate(self, size: float) -> float:
        return self.coefficient * (size ** self.exponent)


@dataclass
class BackendModels:
    name: str
    query_per_subdb_ms: PowerLawModel
    extract_per_subdb_ms: PowerLawModel
    server_per_subdb_ms: PowerLawModel


@dataclass
class StrategyCostMetrics:
    name: str
    count_loads: List[int]
    weight_loads: List[int]
    size_gap: int
    weight_gap: int
    real_hit_probabilities: List[float]
    real_hit_gap: float
    real_hit_stddev: float
    seal_query_ms: float
    seal_extract_ms: float
    seal_server_max_ms: float
    seal_server_total_ms: float
    spiral_query_ms: float
    spiral_extract_ms: float
    spiral_server_max_ms: float
    spiral_server_total_ms: float


@dataclass
class TrialRecord:
    seed: int
    num_leaves: int
    proof_nodes: int
    num_colors: int
    strategies: Dict[str, StrategyCostMetrics]
    valid: bool


def perfect_tree_subdb_sizes() -> List[float]:
    sizes: List[float] = []
    for h in PERFECT_TREE_H:
        total_nodes_excluding_root = (1 << (h + 1)) - 2
        sizes.append(total_nodes_excluding_root / h)
    return sizes


def fit_power_law(xs: Sequence[float], ys: Sequence[float]) -> PowerLawModel:
    log_x = [math.log(value) for value in xs]
    log_y = [math.log(value) for value in ys]
    mean_x = mean(log_x)
    mean_y = mean(log_y)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(log_x, log_y))
    denominator = sum((x - mean_x) ** 2 for x in log_x)
    exponent = numerator / denominator
    intercept = mean_y - exponent * mean_x
    return PowerLawModel(coefficient=math.exp(intercept), exponent=exponent)


def build_backend_models() -> Dict[str, BackendModels]:
    xs = perfect_tree_subdb_sizes()

    seal_query_subdb = [total / h for total, h in zip(SEAL_QUERY_TOTAL_MS, PERFECT_TREE_H)]
    seal_extract_subdb = [total / h for total, h in zip(SEAL_EXTRACT_TOTAL_MS, PERFECT_TREE_H)]
    spiral_query_subdb = [total / h for total, h in zip(SPIRAL_QUERY_TOTAL_MS, PERFECT_TREE_H)]
    spiral_extract_subdb = [total / h for total, h in zip(SPIRAL_EXTRACT_TOTAL_MS, PERFECT_TREE_H)]

    return {
        "sealpir_like": BackendModels(
            name="sealpir_like",
            query_per_subdb_ms=fit_power_law(xs, seal_query_subdb),
            extract_per_subdb_ms=fit_power_law(xs, seal_extract_subdb),
            server_per_subdb_ms=fit_power_law(xs, SEAL_SERVER_MAX_MS),
        ),
        "spiral_like": BackendModels(
            name="spiral_like",
            query_per_subdb_ms=fit_power_law(xs, spiral_query_subdb),
            extract_per_subdb_ms=fit_power_law(xs, spiral_extract_subdb),
            server_per_subdb_ms=fit_power_law(xs, SPIRAL_SERVER_MAX_MS),
        ),
    }


def backend_costs(model: BackendModels, count_loads: Sequence[int]) -> Dict[str, float]:
    safe_sizes = [max(1, size) for size in count_loads]
    query_total = sum(model.query_per_subdb_ms.evaluate(size) for size in safe_sizes)
    extract_total = sum(model.extract_per_subdb_ms.evaluate(size) for size in safe_sizes)
    server_per_color = [model.server_per_subdb_ms.evaluate(size) for size in safe_sizes]
    return {
        "query_total_ms": query_total,
        "extract_total_ms": extract_total,
        "server_max_ms": max(server_per_color) if server_per_color else 0.0,
        "server_total_ms": sum(server_per_color),
    }


def real_hit_probabilities(weight_loads: Sequence[int], num_leaves: int) -> List[float]:
    if num_leaves <= 0:
        return [0.0 for _ in weight_loads]
    return [weight / num_leaves for weight in weight_loads]


def stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def pack_metrics(
    name: str,
    count_loads: Sequence[int],
    weight_loads: Sequence[int],
    num_leaves: int,
    backends: Dict[str, BackendModels],
) -> StrategyCostMetrics:
    probs = real_hit_probabilities(weight_loads, num_leaves)
    seal = backend_costs(backends["sealpir_like"], count_loads)
    spiral = backend_costs(backends["spiral_like"], count_loads)

    return StrategyCostMetrics(
        name=name,
        count_loads=list(count_loads),
        weight_loads=list(weight_loads),
        size_gap=max(count_loads) - min(count_loads) if count_loads else 0,
        weight_gap=max(weight_loads) - min(weight_loads) if weight_loads else 0,
        real_hit_probabilities=probs,
        real_hit_gap=max(probs) - min(probs) if probs else 0.0,
        real_hit_stddev=stddev(probs),
        seal_query_ms=seal["query_total_ms"],
        seal_extract_ms=seal["extract_total_ms"],
        seal_server_max_ms=seal["server_max_ms"],
        seal_server_total_ms=seal["server_total_ms"],
        spiral_query_ms=spiral["query_total_ms"],
        spiral_extract_ms=spiral["extract_total_ms"],
        spiral_server_max_ms=spiral["server_max_ms"],
        spiral_server_total_ms=spiral["server_total_ms"],
    )


def run_trial(num_leaves: int, seed: int, rounds: int, backends: Dict[str, BackendModels]) -> TrialRecord:
    root = build_random_merkle_tree(num_leaves=num_leaves, seed=seed)
    coloring = DirectArbitraryMerkleColoring(root)

    baseline = coloring.baseline_metrics()
    baseline_metrics = pack_metrics(
        name="baseline_depth",
        count_loads=baseline["count_loads"],  # type: ignore[arg-type]
        weight_loads=baseline["weight_loads"],  # type: ignore[arg-type]
        num_leaves=len(coloring.leaf_order),
        backends=backends,
    )

    coloring.color(rebalance_rounds=rounds, strategy="weighted")
    weighted_ok, weighted_issues = coloring.verify()
    weighted_metrics = pack_metrics(
        name="weighted",
        count_loads=coloring.color_count_loads,
        weight_loads=coloring.color_weight_loads,
        num_leaves=len(coloring.leaf_order),
        backends=backends,
    )

    coloring.color(rebalance_rounds=rounds, strategy="count_balanced")
    count_ok, count_issues = coloring.verify()
    count_metrics = pack_metrics(
        name="count_balanced",
        count_loads=coloring.color_count_loads,
        weight_loads=coloring.color_weight_loads,
        num_leaves=len(coloring.leaf_order),
        backends=backends,
    )

    valid = weighted_ok and count_ok
    if not valid:
        print(f"seed={seed} validation issues:")
        for issue in weighted_issues[:5] + count_issues[:5]:
            print(f"  - {issue}")

    return TrialRecord(
        seed=seed,
        num_leaves=num_leaves,
        proof_nodes=len(coloring.proof_nodes),
        num_colors=coloring.num_colors,
        strategies={
            "baseline_depth": baseline_metrics,
            "weighted": weighted_metrics,
            "count_balanced": count_metrics,
        },
        valid=valid,
    )


def average_metric(records: Sequence[TrialRecord], strategy: str, getter) -> float:
    return sum(getter(record.strategies[strategy]) for record in records) / len(records)


def summarize(records: Sequence[TrialRecord]) -> Dict[str, Dict[str, float]]:
    result: Dict[str, Dict[str, float]] = {}
    for strategy in ["baseline_depth", "weighted", "count_balanced"]:
        result[strategy] = {
            "size_gap": average_metric(records, strategy, lambda item: item.size_gap),
            "weight_gap": average_metric(records, strategy, lambda item: item.weight_gap),
            "real_hit_gap": average_metric(records, strategy, lambda item: item.real_hit_gap),
            "seal_query_ms": average_metric(records, strategy, lambda item: item.seal_query_ms),
            "seal_extract_ms": average_metric(records, strategy, lambda item: item.seal_extract_ms),
            "seal_server_max_ms": average_metric(records, strategy, lambda item: item.seal_server_max_ms),
            "seal_server_total_ms": average_metric(records, strategy, lambda item: item.seal_server_total_ms),
            "spiral_query_ms": average_metric(records, strategy, lambda item: item.spiral_query_ms),
            "spiral_extract_ms": average_metric(records, strategy, lambda item: item.spiral_extract_ms),
            "spiral_server_max_ms": average_metric(records, strategy, lambda item: item.spiral_server_max_ms),
            "spiral_server_total_ms": average_metric(records, strategy, lambda item: item.spiral_server_total_ms),
        }
    return result


def print_summary(label: str, summary: Dict[str, Dict[str, float]]) -> None:
    print(label)
    for strategy in ["baseline_depth", "weighted", "count_balanced"]:
        metrics = summary[strategy]
        print(
            f"  {strategy}: "
            f"size_gap={metrics['size_gap']:.3f}, "
            f"weight_gap={metrics['weight_gap']:.3f}, "
            f"real_hit_gap={metrics['real_hit_gap']:.3f}, "
            f"seal(server_max={metrics['seal_server_max_ms']:.3f}ms, "
            f"server_total={metrics['seal_server_total_ms']:.3f}ms, "
            f"query={metrics['seal_query_ms']:.3f}ms), "
            f"spiral(server_max={metrics['spiral_server_max_ms']:.3f}ms, "
            f"server_total={metrics['spiral_server_total_ms']:.3f}ms, "
            f"query={metrics['spiral_query_ms']:.3f}ms)"
        )


def parse_leaf_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("leaf list cannot be empty")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end PIR cost model experiments.")
    parser.add_argument("--leaf-list", type=str, default="8,12,16,20", help="Comma-separated leaf counts.")
    parser.add_argument("--trials", type=int, default=100, help="Random trees per leaf count.")
    parser.add_argument("--rounds", type=int, default=400, help="Maximum local rebalance rounds.")
    parser.add_argument("--seed-base", type=int, default=1000, help="Base seed for random trees.")
    args = parser.parse_args()

    leaf_sizes = parse_leaf_list(args.leaf_list)
    backends = build_backend_models()

    print("=== PIR Cost Model Experiment ===")
    print(f"leaf_sizes={leaf_sizes}")
    print(f"trials_per_size={args.trials}")
    print(f"seed_base={args.seed_base}")
    print(f"rebalance_rounds={args.rounds}")
    print("cost_models=['sealpir_like','spiral_like']")
    print("note=size-driven PIR costs come from fitted TreePIR paper measurements; weighted loads are reported as real-hit diagnostics.")
    print()

    overall_records: List[TrialRecord] = []
    for num_leaves in leaf_sizes:
        records: List[TrialRecord] = []
        for offset in range(args.trials):
            seed = args.seed_base + offset
            record = run_trial(num_leaves=num_leaves, seed=seed, rounds=args.rounds, backends=backends)
            records.append(record)
            overall_records.append(record)

        summary = summarize(records)
        print_summary(f"leaves={num_leaves}", summary)
        print()

    overall_summary = summarize(overall_records)
    print_summary("overall", overall_summary)


if __name__ == "__main__":
    main()
