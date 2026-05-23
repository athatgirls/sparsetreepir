from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    max_chain_length,
    verify_coloring,
)
from run_sparse_smt_pir_backend_experiment import (
    SchemeMetrics,
    TrialResult,
    average_metrics,
    build_color_indexes,
    direct_query_targets,
    execute_single_server_matrix_batch_pir,
    execute_two_server_batch_pir,
    matrix_database,
    perfectized_query_targets,
    random_database,
    color_proof_nodes,
)
from run_xenon_dataset_experiment import iter_entry_numbers
from subtree_permutation_balance import best_profile_balanced_coloring


@dataclass
class SnapshotInfo:
    label: str
    requested_keys: int
    consumed_entries: int
    collisions: int
    occupied: List[int]


def map_entry_to_slot(entry_number: int, tree_height: int, mode: str) -> int:
    universe = 1 << tree_height
    if mode == "sequential":
        return entry_number % universe
    if mode == "sha256":
        digest = hashlib.sha256(str(entry_number).encode("ascii")).digest()
        value = int.from_bytes(digest[:8], "big")
        return value % universe
    raise ValueError(f"unsupported address mode: {mode}")


def build_snapshot(
    dataset_path: Path,
    tree_height: int,
    requested_keys: int,
    address_mode: str,
) -> SnapshotInfo:
    base = 1 << tree_height
    seen_slots: set[int] = set()
    collisions = 0
    consumed_entries = 0

    for entry_number in iter_entry_numbers(dataset_path):
        consumed_entries += 1
        slot = map_entry_to_slot(entry_number, tree_height, address_mode)
        if slot in seen_slots:
            collisions += 1
            continue
        seen_slots.add(slot)
        if len(seen_slots) >= requested_keys:
            break

    if len(seen_slots) < requested_keys:
        raise RuntimeError(
            f"Could only derive {len(seen_slots)} unique sparse-SMT addresses "
            f"from {consumed_entries} Xenon entries; requested {requested_keys}."
        )

    occupied = sorted(base + slot for slot in seen_slots)
    return SnapshotInfo(
        label=f"xenon_{requested_keys}",
        requested_keys=requested_keys,
        consumed_entries=consumed_entries,
        collisions=collisions,
        occupied=occupied,
    )


def sample_query_leaves(occupied: Sequence[int], query_samples: int) -> List[int]:
    if not occupied:
        return []
    if query_samples >= len(occupied):
        return list(occupied)
    step = max(1, len(occupied) // query_samples)
    return [occupied[min(index * step, len(occupied) - 1)] for index in range(query_samples)]


def run_snapshot_trial(
    snapshot: SnapshotInfo,
    tree_height: int,
    rebalance_rounds: int,
    query_samples: int,
    profile_rounds: int,
) -> TrialResult:
    occupied = snapshot.occupied
    helper = FixedSparseMerkleColoring(original_height=tree_height, occupied_leaves=occupied)
    perfectized_sizes = [1 << depth for depth in range(1, tree_height + 1)]
    perfectized_nodes = sum(perfectized_sizes)
    sampled_leaves = sample_query_leaves(occupied, query_samples)

    perfectized_db = random_database(perfectized_sizes, tree_height * 101 + len(occupied))
    perfectized_mat_db = matrix_database(perfectized_sizes, tree_height * 103 + len(occupied))
    perfectized_sample_metrics: List[Dict[str, float]] = []
    perfectized_matrix_metrics: List[Dict[str, float]] = []
    for offset, leaf in enumerate(sampled_leaves):
        leaf_slot = leaf - (1 << tree_height)
        targets = perfectized_query_targets(leaf_slot=leaf_slot, tree_height=tree_height)
        perfectized_sample_metrics.append(
            execute_two_server_batch_pir(perfectized_db, targets, seed=tree_height * 107 + offset)
        )
        perfectized_matrix_metrics.append(
            execute_single_server_matrix_batch_pir(perfectized_mat_db, targets)
        )
    perfectized_backend = average_metrics(perfectized_sample_metrics)
    perfectized_matrix_backend = average_metrics(perfectized_matrix_metrics)

    schemes: Dict[str, SchemeMetrics] = {
        "perfectized_treepir": SchemeMetrics(
            name="perfectized_treepir",
            protocol_colors=tree_height,
            stored_nodes=perfectized_nodes,
            storage_ratio_vs_perfectized=1.0,
            subdatabase_sizes=perfectized_sizes,
            size_gap=max(perfectized_sizes) - min(perfectized_sizes),
            weight_loads=[len(occupied)] * tree_height,
            weight_gap=0,
            valid=True,
            xor_query_bytes=perfectized_backend["query_bytes"],
            xor_response_bytes=perfectized_backend["response_bytes"],
            xor_client_query_ms=perfectized_backend["client_query_ms"],
            xor_client_extract_ms=perfectized_backend["client_extract_ms"],
            xor_server_total_ms=perfectized_backend["server_total_ms"],
            xor_server_parallel_ms=perfectized_backend["server_parallel_ms"],
            mat_query_bytes=perfectized_matrix_backend["query_bytes"],
            mat_response_bytes=perfectized_matrix_backend["response_bytes"],
            mat_client_query_ms=perfectized_matrix_backend["client_query_ms"],
            mat_client_extract_ms=perfectized_matrix_backend["client_extract_ms"],
            mat_server_total_ms=perfectized_matrix_backend["server_total_ms"],
            mat_server_parallel_ms=perfectized_matrix_backend["server_parallel_ms"],
        )
    }

    for strategy in ["hybrid", "profile_balanced"]:
        proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, tree_height)
        roots = build_interval_forest(proof_nodes)
        num_colors = max_chain_length(roots)
        color_start = perf_counter()
        if strategy == "profile_balanced":
            result = best_profile_balanced_coloring(
                proof_nodes=proof_nodes,
                roots=roots,
                num_colors=num_colors,
                initial_strategies=("hybrid",),
                initial_rounds=rebalance_rounds,
                refine_rounds=profile_rounds,
            )
            count_loads = result.count_loads
            weight_loads = result.weight_loads
        else:
            count_loads, weight_loads = color_proof_nodes(
                proof_nodes=proof_nodes,
                roots=roots,
                num_colors=num_colors,
                strategy="hybrid",
                rebalance_rounds=rebalance_rounds,
            )
        color_end = perf_counter()

        valid, _ = verify_coloring(roots, occupied)
        color_indexes = build_color_indexes(proof_nodes, num_colors)
        database = random_database(count_loads, tree_height * 109 + len(strategy) + len(occupied))
        matrix_db = matrix_database(count_loads, tree_height * 113 + len(strategy) + len(occupied))

        per_query_metrics: List[Dict[str, float]] = []
        per_query_matrix_metrics: List[Dict[str, float]] = []
        real_color_counts: List[int] = []
        for offset, leaf in enumerate(sampled_leaves):
            targets = direct_query_targets(color_indexes, occupied, leaf, num_colors)
            real_color_counts.append(sum(1 for target in targets if target is not None))
            per_query_metrics.append(
                execute_two_server_batch_pir(database, targets, seed=tree_height * 127 + offset)
            )
            per_query_matrix_metrics.append(
                execute_single_server_matrix_batch_pir(matrix_db, targets)
            )
        backend = average_metrics(per_query_metrics)
        matrix_backend = average_metrics(per_query_matrix_metrics)

        # Fold preprocessing and coloring time into the query-generation field so it is not lost.
        backend["client_query_ms"] += (color_end - color_start) * 1000.0
        matrix_backend["client_query_ms"] += (color_end - color_start) * 1000.0

        schemes[strategy] = SchemeMetrics(
            name=strategy,
            protocol_colors=num_colors,
            stored_nodes=len(proof_nodes),
            storage_ratio_vs_perfectized=len(proof_nodes) / perfectized_nodes,
            subdatabase_sizes=list(count_loads),
            size_gap=max(count_loads) - min(count_loads) if count_loads else 0,
            weight_loads=list(weight_loads),
            weight_gap=max(weight_loads) - min(weight_loads) if weight_loads else 0,
            valid=valid,
            xor_query_bytes=backend["query_bytes"],
            xor_response_bytes=backend["response_bytes"],
            xor_client_query_ms=backend["client_query_ms"],
            xor_client_extract_ms=backend["client_extract_ms"],
            xor_server_total_ms=backend["server_total_ms"],
            xor_server_parallel_ms=backend["server_parallel_ms"],
            mat_query_bytes=matrix_backend["query_bytes"],
            mat_response_bytes=matrix_backend["response_bytes"],
            mat_client_query_ms=matrix_backend["client_query_ms"],
            mat_client_extract_ms=matrix_backend["client_extract_ms"],
            mat_server_total_ms=matrix_backend["server_total_ms"],
            mat_server_parallel_ms=matrix_backend["server_parallel_ms"],
        )
        print(
            f"  {strategy}: avg_real_colors_per_query={mean(real_color_counts):.2f}, "
            f"dummy_ratio={1.0 - (mean(real_color_counts) / num_colors):.3f}"
        )

    return TrialResult(
        height=tree_height,
        sparsity=1.0 - (len(occupied) / (1 << tree_height)),
        seed=0,
        occupied_leaf_count=len(occupied),
        perfectized_nodes=perfectized_nodes,
        schemes=schemes,
    )


def print_snapshot_header(snapshot: SnapshotInfo, tree_height: int, address_mode: str) -> None:
    print(
        f"{snapshot.label}: height={tree_height}, address_mode={address_mode}, "
        f"requested_keys={snapshot.requested_keys}, consumed_entries={snapshot.consumed_entries}, "
        f"collisions={snapshot.collisions}, occupied={len(snapshot.occupied)}, "
        f"sparsity={1.0 - (len(snapshot.occupied) / (1 << tree_height)):.6f}"
    )


def print_summary(result: TrialResult) -> None:
    for scheme in ["perfectized_treepir", "hybrid", "profile_balanced"]:
        metrics = result.schemes[scheme]
        print(
            f"  {scheme}: "
            f"protocol_colors={metrics.protocol_colors:.2f}, "
            f"stored_nodes={metrics.stored_nodes}, "
            f"storage_ratio={metrics.storage_ratio_vs_perfectized:.6f}, "
            f"size_gap={metrics.size_gap}, "
            f"weight_gap={metrics.weight_gap}, "
            f"xor(query_bytes={metrics.xor_query_bytes:.1f}, "
            f"response_bytes={metrics.xor_response_bytes:.1f}, "
            f"server_parallel={metrics.xor_server_parallel_ms:.3f}ms), "
            f"mat(query_bytes={metrics.mat_query_bytes:.1f}, "
            f"response_bytes={metrics.mat_response_bytes:.1f}, "
            f"server_parallel={metrics.mat_server_parallel_ms:.3f}ms), "
            f"valid={metrics.valid}"
        )


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("list cannot be empty")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Xenon-derived sparse-SMT backend experiment with executable PIR backends."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(r"c:\Users\15313\Downloads\xenon2024_log_entries"),
        help="Path to the Xenon2024 dataset dump.",
    )
    parser.add_argument("--height", type=int, default=20, help="Sparse SMT height.")
    parser.add_argument(
        "--sizes",
        type=str,
        default="5000,10000,20000",
        help="Comma-separated requested occupied-key counts derived from Xenon entries.",
    )
    parser.add_argument(
        "--address-mode",
        type=str,
        choices=["sequential", "sha256"],
        default="sha256",
        help="How Xenon entry numbers are mapped into the sparse-SMT address space.",
    )
    parser.add_argument("--rounds", type=int, default=120, help="Hybrid initialization rounds.")
    parser.add_argument("--profile-rounds", type=int, default=8, help="Profile-balancing rounds.")
    parser.add_argument("--query-samples", type=int, default=8, help="Backend query samples per snapshot.")
    args = parser.parse_args()

    sizes = parse_int_list(args.sizes)
    print("=== Xenon-Derived Sparse SMT Backend Experiment ===")
    print(f"dataset={args.dataset}")
    print(f"height={args.height}")
    print(f"sizes={sizes}")
    print(f"address_mode={args.address_mode}")
    print(f"rounds={args.rounds}")
    print(f"profile_rounds={args.profile_rounds}")
    print(f"query_samples={args.query_samples}")
    print("schemes=['perfectized_treepir','hybrid','profile_balanced']")
    print()

    for requested_keys in sizes:
        snapshot = build_snapshot(
            dataset_path=args.dataset,
            tree_height=args.height,
            requested_keys=requested_keys,
            address_mode=args.address_mode,
        )
        print_snapshot_header(snapshot, tree_height=args.height, address_mode=args.address_mode)
        result = run_snapshot_trial(
            snapshot=snapshot,
            tree_height=args.height,
            rebalance_rounds=args.rounds,
            query_samples=args.query_samples,
            profile_rounds=args.profile_rounds,
        )
        print_summary(result)
        print()


if __name__ == "__main__":
    main()
