from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List

from direct_arbitrary_merkle_coloring import DirectArbitraryMerkleColoring
from run_pir_cost_model_experiment import build_backend_models, pack_metrics
from run_random_merkle_coloring_experiment import build_random_merkle_tree


@dataclass
class StrategySummary:
    name: str
    size_gap: float
    weight_gap: float
    hybrid_score: float
    hybrid_excess: float
    hybrid_ratio: float
    pass_rate: float
    seal_server_max_ms: float
    seal_query_ms: float
    spiral_server_max_ms: float
    spiral_query_ms: float


STRATEGIES = [
    ("baseline_depth", None, None),
    ("weighted_greedy", "weighted", 0),
    ("weighted", "weighted", 400),
    ("count_balanced", "count_balanced", 400),
    ("hybrid", "hybrid", 400),
]


def run_single_tree(num_leaves: int, seed: int, rounds: int) -> Dict[str, Dict[str, float | bool]]:
    root = build_random_merkle_tree(num_leaves=num_leaves, seed=seed)
    coloring = DirectArbitraryMerkleColoring(root)
    backends = build_backend_models()
    result: Dict[str, Dict[str, float | bool]] = {}
    lower_bounds = coloring.universal_lower_bounds()
    hybrid_lb = float(lower_bounds["hybrid_lb"])

    def hybrid_stats(weight_loads: List[int], count_loads: List[int]) -> Dict[str, float]:
        score = coloring.hybrid_score_from_loads(weight_loads, count_loads)
        excess = score - hybrid_lb
        ratio = (score / hybrid_lb) if hybrid_lb > 0 else 1.0
        return {
            "hybrid_score": score,
            "hybrid_excess": excess,
            "hybrid_ratio": ratio,
        }

    baseline = coloring.baseline_metrics()
    baseline_hybrid = hybrid_stats(
        baseline["weight_loads"],  # type: ignore[arg-type]
        baseline["count_loads"],  # type: ignore[arg-type]
    )
    baseline_metrics = pack_metrics(
        name="baseline_depth",
        count_loads=baseline["count_loads"],  # type: ignore[arg-type]
        weight_loads=baseline["weight_loads"],  # type: ignore[arg-type]
        num_leaves=len(coloring.leaf_order),
        backends=backends,
    )
    result["baseline_depth"] = {
        "size_gap": float(baseline_metrics.size_gap),
        "weight_gap": float(baseline_metrics.weight_gap),
        "hybrid_score": baseline_hybrid["hybrid_score"],
        "hybrid_excess": baseline_hybrid["hybrid_excess"],
        "hybrid_ratio": baseline_hybrid["hybrid_ratio"],
        "pass": True,
        "seal_server_max_ms": baseline_metrics.seal_server_max_ms,
        "seal_query_ms": baseline_metrics.seal_query_ms,
        "spiral_server_max_ms": baseline_metrics.spiral_server_max_ms,
        "spiral_query_ms": baseline_metrics.spiral_query_ms,
    }

    for name, strategy, custom_rounds in STRATEGIES[1:]:
        coloring.color(rebalance_rounds=rounds if custom_rounds is None else custom_rounds, strategy=strategy)  # type: ignore[arg-type]
        ok, _ = coloring.verify()
        metrics = pack_metrics(
            name=name,
            count_loads=coloring.color_count_loads,
            weight_loads=coloring.color_weight_loads,
            num_leaves=len(coloring.leaf_order),
            backends=backends,
        )
        hybrid = hybrid_stats(coloring.color_weight_loads, coloring.color_count_loads)
        result[name] = {
            "size_gap": float(metrics.size_gap),
            "weight_gap": float(metrics.weight_gap),
            "hybrid_score": hybrid["hybrid_score"],
            "hybrid_excess": hybrid["hybrid_excess"],
            "hybrid_ratio": hybrid["hybrid_ratio"],
            "pass": ok,
            "seal_server_max_ms": metrics.seal_server_max_ms,
            "seal_query_ms": metrics.seal_query_ms,
            "spiral_server_max_ms": metrics.spiral_server_max_ms,
            "spiral_query_ms": metrics.spiral_query_ms,
        }

    return result


def summarize(records: List[Dict[str, Dict[str, float | bool]]]) -> Dict[str, StrategySummary]:
    summary: Dict[str, StrategySummary] = {}
    for name, _, _ in STRATEGIES:
        entries = [record[name] for record in records]
        summary[name] = StrategySummary(
            name=name,
            size_gap=sum(float(item["size_gap"]) for item in entries) / len(entries),
            weight_gap=sum(float(item["weight_gap"]) for item in entries) / len(entries),
            hybrid_score=sum(float(item["hybrid_score"]) for item in entries) / len(entries),
            hybrid_excess=sum(float(item["hybrid_excess"]) for item in entries) / len(entries),
            hybrid_ratio=sum(float(item["hybrid_ratio"]) for item in entries) / len(entries),
            pass_rate=sum(1.0 for item in entries if bool(item["pass"])) / len(entries),
            seal_server_max_ms=sum(float(item["seal_server_max_ms"]) for item in entries) / len(entries),
            seal_query_ms=sum(float(item["seal_query_ms"]) for item in entries) / len(entries),
            spiral_server_max_ms=sum(float(item["spiral_server_max_ms"]) for item in entries) / len(entries),
            spiral_query_ms=sum(float(item["spiral_query_ms"]) for item in entries) / len(entries),
        )
    return summary


def print_summary(label: str, summary: Dict[str, StrategySummary]) -> None:
    print(label)
    for name, _, _ in STRATEGIES:
        item = summary[name]
        print(
            f"  {name}: "
            f"size_gap={item.size_gap:.3f}, "
            f"weight_gap={item.weight_gap:.3f}, "
            f"hybrid_score={item.hybrid_score:.3f}, "
            f"hybrid_excess={item.hybrid_excess:.3f}, "
            f"hybrid_ratio={item.hybrid_ratio:.3f}, "
            f"pass_rate={item.pass_rate * 100:.1f}%, "
            f"seal(query={item.seal_query_ms:.3f}ms, server_max={item.seal_server_max_ms:.3f}ms), "
            f"spiral(query={item.spiral_query_ms:.3f}ms, server_max={item.spiral_server_max_ms:.3f}ms)"
        )


def parse_leaf_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("leaf list cannot be empty")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Run extended hybrid/ablation coloring experiments.")
    parser.add_argument("--leaf-list", type=str, default="8,12,16,20", help="Comma-separated leaf counts.")
    parser.add_argument("--trials", type=int, default=100, help="Trees per leaf count.")
    parser.add_argument("--seed-base", type=int, default=3000, help="Base seed.")
    parser.add_argument("--rounds", type=int, default=400, help="Local rebalance rounds.")
    args = parser.parse_args()

    leaf_sizes = parse_leaf_list(args.leaf_list)
    print("=== Extended Coloring Strategy Experiment ===")
    print(f"leaf_sizes={leaf_sizes}")
    print(f"trials_per_size={args.trials}")
    print(f"seed_base={args.seed_base}")
    print(f"rebalance_rounds={args.rounds}")
    print("strategies=['baseline_depth','weighted_greedy','weighted','count_balanced','hybrid']")
    print()

    overall_records: List[Dict[str, Dict[str, float | bool]]] = []
    for leaf_count in leaf_sizes:
        per_size_records: List[Dict[str, Dict[str, float | bool]]] = []
        for offset in range(args.trials):
            record = run_single_tree(num_leaves=leaf_count, seed=args.seed_base + offset, rounds=args.rounds)
            per_size_records.append(record)
            overall_records.append(record)
        print_summary(f"leaves={leaf_count}", summarize(per_size_records))
        print()

    print_summary("overall", summarize(overall_records))


if __name__ == "__main__":
    main()
