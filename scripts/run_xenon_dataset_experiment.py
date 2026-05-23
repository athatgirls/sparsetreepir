from __future__ import annotations

import argparse
import gc
import math
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, Iterable, List, Sequence

from direct_arbitrary_merkle_coloring import DirectArbitraryMerkleColoring, MerkleNode


ENTRY_NUMBER_PATTERN = re.compile(rb'"entry_number":(\d+)')
SCAN_CHUNK_SIZE = 8 * 1024 * 1024
SCAN_CARRY_BYTES = 64


@dataclass
class DatasetSummary:
    path: Path
    file_size_bytes: int
    unique_entry_count: int
    min_entry: int
    max_entry: int
    missing_count: int
    missing_examples: List[int]

    @property
    def paper_full_size(self) -> int:
        return self.max_entry + 1


@dataclass
class StrategyResult:
    strategy: str
    leaf_count: int
    proof_nodes: int
    num_colors: int
    subdatabase_size_gap: int
    weighted_gap: int
    subdatabase_sizes: List[int]
    weighted_loads: List[int]
    ancestral_property_valid: bool
    runtime_seconds: float


@dataclass
class TreeResult:
    label: str
    leaf_count: int
    build_seconds: float
    prepare_seconds: float
    proof_nodes: int
    num_colors: int
    baseline_size_gap: int
    baseline_weighted_gap: int
    strategy_results: Dict[str, StrategyResult]


def iter_entry_numbers(path: Path) -> Iterable[int]:
    carry = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(SCAN_CHUNK_SIZE)
            if not chunk:
                data = carry
                carry = b""
            else:
                data = carry + chunk
                carry = data[-SCAN_CARRY_BYTES:]
                data = data[:-SCAN_CARRY_BYTES]

            for match in ENTRY_NUMBER_PATTERN.finditer(data):
                yield int(match.group(1))

            if not chunk:
                break


def scan_dataset(path: Path) -> DatasetSummary:
    values = set(iter_entry_numbers(path))
    if not values:
        raise ValueError(f"No entry_number fields were found in {path}.")

    min_entry = min(values)
    max_entry = max(values)
    missing_examples: List[int] = []
    if min_entry == 0:
        for value in range(max_entry + 1):
            if value not in values:
                missing_examples.append(value)
                if len(missing_examples) >= 10:
                    break

    missing_count = (max_entry - min_entry + 1) - len(values)
    return DatasetSummary(
        path=path,
        file_size_bytes=path.stat().st_size,
        unique_entry_count=len(values),
        min_entry=min_entry,
        max_entry=max_entry,
        missing_count=missing_count,
        missing_examples=missing_examples,
    )


def build_ct_merkle_tree(start_leaf: int, leaf_count: int, internal_counter: List[int]) -> MerkleNode:
    """
    Build the canonical left-balanced CT / RFC6962 Merkle tree shape.

    The coloring metrics in this project depend on tree topology rather than
    certificate payloads, so once the real leaf count is known we only need
    the induced binary tree shape.
    """
    if leaf_count < 1:
        raise ValueError("leaf_count must be positive.")

    if leaf_count == 1:
        return MerkleNode(label=f"L{start_leaf}")

    left_size = 1 << ((leaf_count - 1).bit_length() - 1)
    if left_size == leaf_count:
        left_size //= 2

    left = build_ct_merkle_tree(start_leaf, left_size, internal_counter)
    right = build_ct_merkle_tree(start_leaf + left_size, leaf_count - left_size, internal_counter)
    internal_counter[0] += 1
    parent = MerkleNode(label=f"I{internal_counter[0]}", left=left, right=right)
    left.parent = parent
    right.parent = parent
    return parent


def run_tree_experiment(leaf_count: int, label: str, rounds: int) -> TreeResult:
    build_start = perf_counter()
    root = build_ct_merkle_tree(start_leaf=0, leaf_count=leaf_count, internal_counter=[0])
    build_end = perf_counter()

    coloring = DirectArbitraryMerkleColoring(root)
    prepare_end = perf_counter()
    baseline = coloring.baseline_metrics()

    strategy_results: Dict[str, StrategyResult] = {}
    for strategy in ["weighted", "count_balanced"]:
        strategy_start = perf_counter()
        coloring.color(rebalance_rounds=rounds, strategy=strategy)
        ok, issues = coloring.verify()
        strategy_end = perf_counter()

        if not ok:
            print(f"{label} {strategy} issues:")
            for issue in issues[:10]:
                print(f"  - {issue}")

        strategy_results[strategy] = StrategyResult(
            strategy=strategy,
            leaf_count=leaf_count,
            proof_nodes=len(coloring.proof_nodes),
            num_colors=coloring.num_colors,
            subdatabase_size_gap=max(coloring.color_count_loads) - min(coloring.color_count_loads),
            weighted_gap=max(coloring.color_weight_loads) - min(coloring.color_weight_loads),
            subdatabase_sizes=list(coloring.color_count_loads),
            weighted_loads=list(coloring.color_weight_loads),
            ancestral_property_valid=ok,
            runtime_seconds=strategy_end - strategy_start,
        )

    result = TreeResult(
        label=label,
        leaf_count=leaf_count,
        build_seconds=build_end - build_start,
        prepare_seconds=prepare_end - build_end,
        proof_nodes=len(coloring.proof_nodes),
        num_colors=coloring.num_colors,
        baseline_size_gap=int(baseline["count_gap"]),
        baseline_weighted_gap=int(baseline["weight_gap"]),
        strategy_results=strategy_results,
    )

    del coloring
    del root
    gc.collect()
    return result


def parse_sizes(raw: str, dataset: DatasetSummary) -> List[tuple[str, int]]:
    sizes: List[tuple[str, int]] = []
    for token in [item.strip() for item in raw.split(",") if item.strip()]:
        lowered = token.lower()
        if lowered == "actual":
            sizes.append(("actual_unique", dataset.unique_entry_count))
        elif lowered == "paper_full":
            sizes.append(("paper_full", dataset.paper_full_size))
        else:
            value = int(token)
            sizes.append((str(value), value))
    return sizes


def print_dataset_summary(dataset: DatasetSummary) -> None:
    print("=== Xenon2024 Dataset Summary ===")
    print(f"path={dataset.path}")
    print(f"file_size_bytes={dataset.file_size_bytes}")
    print(f"file_size_gib={dataset.file_size_bytes / (1024 ** 3):.3f}")
    print(f"unique_entry_count={dataset.unique_entry_count}")
    print(f"min_entry={dataset.min_entry}")
    print(f"max_entry={dataset.max_entry}")
    print(f"paper_full_size={dataset.paper_full_size}")
    print(f"missing_count_within_range={dataset.missing_count}")
    print(f"missing_examples={dataset.missing_examples}")
    print(
        "note=Coloring metrics depend on the induced Merkle tree topology, "
        "so the experiment uses the real Xenon entry-count snapshots to build CT-style trees."
    )
    print()


def print_tree_result(result: TreeResult) -> None:
    weighted = result.strategy_results["weighted"]
    count_balanced = result.strategy_results["count_balanced"]

    print(
        f"{result.label}: leaves={result.leaf_count} proof_nodes={result.proof_nodes} "
        f"colors={result.num_colors} build_s={result.build_seconds:.3f} prep_s={result.prepare_seconds:.3f}"
    )
    print(
        "  baseline"
        f" size_gap={result.baseline_size_gap}"
        f" weighted_gap={result.baseline_weighted_gap}"
    )
    print(
        "  weighted"
        f" size_gap={weighted.subdatabase_size_gap}"
        f" weighted_gap={weighted.weighted_gap}"
        f" valid={weighted.ancestral_property_valid}"
        f" runtime_s={weighted.runtime_seconds:.3f}"
    )
    print(
        "  count_balanced"
        f" size_gap={count_balanced.subdatabase_size_gap}"
        f" weighted_gap={count_balanced.weighted_gap}"
        f" valid={count_balanced.ancestral_property_valid}"
        f" runtime_s={count_balanced.runtime_seconds:.3f}"
    )


def print_overall_summary(results: Sequence[TreeResult]) -> None:
    def avg(values: Iterable[float]) -> float:
        values = list(values)
        return sum(values) / len(values) if values else math.nan

    weighted_size_gap_avg = avg(item.strategy_results["weighted"].subdatabase_size_gap for item in results)
    weighted_weight_gap_avg = avg(item.strategy_results["weighted"].weighted_gap for item in results)
    count_size_gap_avg = avg(item.strategy_results["count_balanced"].subdatabase_size_gap for item in results)
    count_weight_gap_avg = avg(item.strategy_results["count_balanced"].weighted_gap for item in results)
    baseline_size_gap_avg = avg(item.baseline_size_gap for item in results)
    baseline_weight_gap_avg = avg(item.baseline_weighted_gap for item in results)

    print()
    print("overall_summary:")
    print(
        f"  baseline(avg_size_gap={baseline_size_gap_avg:.3f}, "
        f"avg_weighted_gap={baseline_weight_gap_avg:.3f})"
    )
    print(
        f"  weighted(avg_size_gap={weighted_size_gap_avg:.3f}, "
        f"avg_weighted_gap={weighted_weight_gap_avg:.3f})"
    )
    print(
        f"  count_balanced(avg_size_gap={count_size_gap_avg:.3f}, "
        f"avg_weighted_gap={count_weight_gap_avg:.3f})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Xenon2024-driven Merkle coloring experiments.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(r"c:\Users\15313\Downloads\xenon2024_log_entries"),
        help="Path to the Xenon2024 dataset dump.",
    )
    parser.add_argument(
        "--sizes",
        type=str,
        default="100000,300000,750000,actual,paper_full",
        help="Comma-separated leaf counts or tokens: actual, paper_full.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=200,
        help="Maximum local rebalancing rounds for each strategy.",
    )
    args = parser.parse_args()

    dataset = scan_dataset(args.dataset)
    print_dataset_summary(dataset)

    results: List[TreeResult] = []
    for label, leaf_count in parse_sizes(args.sizes, dataset):
        result = run_tree_experiment(leaf_count=leaf_count, label=label, rounds=args.rounds)
        results.append(result)
        print_tree_result(result)

    print_overall_summary(results)


if __name__ == "__main__":
    main()
