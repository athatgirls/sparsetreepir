from __future__ import annotations

import argparse
import bisect
from dataclasses import dataclass
from statistics import mean
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode,
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
    verify_coloring,
)


RECORD_BYTES = 32
RECORD_WORDS = RECORD_BYTES // 8
MATRIX_QUERY_COEFF_BYTES = 4


@dataclass
class SchemeMetrics:
    name: str
    protocol_colors: int
    stored_nodes: int
    storage_ratio_vs_perfectized: float
    subdatabase_sizes: List[int]
    size_gap: int
    weight_loads: List[int]
    weight_gap: int
    valid: bool
    xor_query_bytes: float
    xor_response_bytes: float
    xor_client_query_ms: float
    xor_client_extract_ms: float
    xor_server_total_ms: float
    xor_server_parallel_ms: float
    mat_query_bytes: float
    mat_response_bytes: float
    mat_client_query_ms: float
    mat_client_extract_ms: float
    mat_server_total_ms: float
    mat_server_parallel_ms: float


@dataclass
class TrialResult:
    height: int
    sparsity: float
    seed: int
    occupied_leaf_count: int
    perfectized_nodes: int
    schemes: Dict[str, SchemeMetrics]


def clear_colors(proof_nodes: Sequence[ProofNode]) -> None:
    for node in proof_nodes:
        node.color = None


def hybrid_score(weight_loads: Sequence[int], count_loads: Sequence[int]) -> float:
    if not weight_loads or not count_loads:
        return 0.0
    avg_weight = max(1.0, sum(weight_loads) / len(weight_loads))
    avg_count = max(1.0, sum(count_loads) / len(count_loads))
    return ((max(weight_loads) - min(weight_loads)) / avg_weight) + (
        (max(count_loads) - min(count_loads)) / avg_count
    )


def objective(strategy: str, weight_loads: Sequence[int], count_loads: Sequence[int]) -> Tuple[float, int, int, int, int]:
    if not weight_loads:
        return (0.0, 0, 0, 0, 0)
    weight_gap = max(weight_loads) - min(weight_loads)
    count_gap = max(count_loads) - min(count_loads)
    max_weight = max(weight_loads)
    max_count = max(count_loads)
    if strategy == "count_balanced":
        return (float(count_gap), count_gap, weight_gap, max_count, max_weight)
    if strategy == "hybrid":
        return (hybrid_score(weight_loads, count_loads), count_gap, weight_gap, max_count, max_weight)
    return (float(weight_gap), weight_gap, count_gap, max_weight, max_count)


def can_recolor(node: ProofNode, new_color: int) -> bool:
    current = node.parent
    while current is not None:
        if current.color == new_color:
            return False
        current = current.parent

    stack = list(node.children)
    while stack:
        current = stack.pop()
        if current.color == new_color:
            return False
        stack.extend(current.children)
    return True


def color_proof_nodes(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    num_colors: int,
    strategy: str,
    rebalance_rounds: int,
) -> Tuple[List[int], List[int]]:
    if strategy not in {"weighted", "count_balanced", "hybrid"}:
        raise ValueError("unsupported strategy")

    clear_colors(proof_nodes)
    count_loads = [0] * num_colors
    weight_loads = [0] * num_colors
    base, remainder = divmod(len(proof_nodes), num_colors)
    target_counts = [base + (1 if idx < remainder else 0) for idx in range(num_colors)]

    def assign(node: ProofNode, color: int) -> None:
        if node.color is not None:
            old_idx = node.color - 1
            count_loads[old_idx] -= 1
            weight_loads[old_idx] -= node.weight
        node.color = color
        new_idx = color - 1
        count_loads[new_idx] += 1
        weight_loads[new_idx] += node.weight

    def greedy_key(node: ProofNode, color: int) -> Tuple[float, int, int, int, int]:
        idx = color - 1
        if strategy == "count_balanced":
            return (
                float(count_loads[idx] - target_counts[idx]),
                count_loads[idx],
                weight_loads[idx],
                abs(count_loads[idx] - target_counts[idx]),
                color,
            )
        if strategy == "hybrid":
            candidate_weight_loads = list(weight_loads)
            candidate_count_loads = list(count_loads)
            candidate_weight_loads[idx] += node.weight
            candidate_count_loads[idx] += 1
            hybrid_obj = objective(strategy, candidate_weight_loads, candidate_count_loads)
            return (
                hybrid_obj[0],
                hybrid_obj[1],
                hybrid_obj[2],
                abs(candidate_count_loads[idx] - target_counts[idx]),
                color,
            )
        return (
            float(weight_loads[idx]),
            count_loads[idx],
            abs(count_loads[idx] - target_counts[idx]),
            0,
            color,
        )

    def greedy(node: ProofNode, ancestor_colors: set[int]) -> None:
        available = [c for c in range(1, num_colors + 1) if c not in ancestor_colors]
        chosen = min(available, key=lambda color: greedy_key(node, color))
        assign(node, chosen)
        next_ancestor = set(ancestor_colors)
        next_ancestor.add(chosen)
        for child in sorted(node.children, key=lambda item: item.weight, reverse=True):
            greedy(child, next_ancestor)

    for root in sorted(roots, key=lambda item: item.weight, reverse=True):
        greedy(root, set())

    for _ in range(rebalance_rounds):
        current_objective = objective(strategy, weight_loads, count_loads)
        best_move: Optional[Tuple[ProofNode, int, Tuple[float, int, int, int, int]]] = None

        if strategy == "count_balanced":
            colors_desc = sorted(
                range(1, num_colors + 1),
                key=lambda color: (count_loads[color - 1], weight_loads[color - 1]),
                reverse=True,
            )
        elif strategy == "hybrid":
            avg_count = max(1.0, sum(count_loads) / len(count_loads))
            avg_weight = max(1.0, sum(weight_loads) / len(weight_loads))
            colors_desc = sorted(
                range(1, num_colors + 1),
                key=lambda color: (count_loads[color - 1] / avg_count) + (weight_loads[color - 1] / avg_weight),
                reverse=True,
            )
        else:
            colors_desc = sorted(
                range(1, num_colors + 1),
                key=lambda color: (weight_loads[color - 1], count_loads[color - 1]),
                reverse=True,
            )
        colors_asc = list(reversed(colors_desc))

        for heavy in colors_desc:
            candidates = [node for node in proof_nodes if node.color == heavy]
            if strategy == "count_balanced":
                candidates.sort(key=lambda node: (node.weight, node.depth), reverse=True)
            else:
                candidates.sort(key=lambda node: (node.weight, node.interval_right - node.interval_left), reverse=True)
            for node in candidates:
                for light in colors_asc:
                    if light == heavy or not can_recolor(node, light):
                        continue
                    candidate_weight_loads = list(weight_loads)
                    candidate_count_loads = list(count_loads)
                    candidate_weight_loads[heavy - 1] -= node.weight
                    candidate_weight_loads[light - 1] += node.weight
                    candidate_count_loads[heavy - 1] -= 1
                    candidate_count_loads[light - 1] += 1
                    candidate_objective = objective(strategy, candidate_weight_loads, candidate_count_loads)
                    if candidate_objective < current_objective:
                        if best_move is None or candidate_objective < best_move[2]:
                            best_move = (node, light, candidate_objective)

        if best_move is None:
            break
        assign(best_move[0], best_move[1])

    return count_loads, weight_loads


def build_color_indexes(proof_nodes: Sequence[ProofNode], protocol_colors: int) -> Dict[int, List[Tuple[int, int, int]]]:
    buckets: Dict[int, List[Tuple[int, int, int]]] = {color: [] for color in range(1, protocol_colors + 1)}
    for node in proof_nodes:
        if node.color is None:
            continue
        buckets[node.color].append((node.interval_left, node.interval_right, node.index))
    for color in buckets:
        buckets[color].sort()
    return buckets


def direct_query_targets(
    color_indexes: Dict[int, List[Tuple[int, int, int]]],
    occupied_leaves: Sequence[int],
    leaf_heap_index: int,
    protocol_colors: int,
) -> List[Optional[int]]:
    rank = occupied_leaves.index(leaf_heap_index)
    targets: List[Optional[int]] = []
    for color in range(1, protocol_colors + 1):
        entries = color_indexes.get(color, [])
        left_endpoints = [left for left, _, _ in entries]
        pos = bisect.bisect_right(left_endpoints, rank) - 1
        if pos >= 0:
            left, right, _ = entries[pos]
            if left <= rank <= right:
                targets.append(pos)
                continue
        targets.append(None)
    return targets


def perfectized_query_targets(leaf_slot: int, tree_height: int) -> List[int]:
    targets: List[int] = []
    for depth in range(1, tree_height + 1):
        group_size = 1 << (tree_height - depth)
        path_pos = leaf_slot // group_size
        sibling_pos = path_pos ^ 1
        targets.append(sibling_pos)
    return targets


def random_database(subdatabase_sizes: Sequence[int], seed: int) -> List[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [
        rng.integers(0, np.iinfo(np.uint64).max, size=(size, RECORD_WORDS), dtype=np.uint64)
        if size > 0
        else np.zeros((0, RECORD_WORDS), dtype=np.uint64)
        for size in subdatabase_sizes
    ]


def xor_rows(rows: np.ndarray) -> np.ndarray:
    if rows.size == 0:
        return np.zeros(RECORD_WORDS, dtype=np.uint64)
    return np.bitwise_xor.reduce(rows, axis=0)


def execute_two_server_batch_pir(
    database: Sequence[np.ndarray],
    targets: Sequence[Optional[int]],
    seed: int,
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    query_bytes = 0
    response_bytes = 0
    query_time = 0.0
    extract_time = 0.0
    server_total = 0.0
    server_parallel = 0.0

    for table, target in zip(database, targets):
        size = int(table.shape[0])
        if size == 0:
            continue

        t0 = perf_counter()
        q1 = rng.integers(0, 2, size=size, dtype=np.uint8)
        q2 = q1.copy()
        if target is not None:
            q2[target] ^= 1
        t1 = perf_counter()
        query_time += t1 - t0

        s0 = perf_counter()
        resp1 = xor_rows(table[q1.astype(bool)])
        resp2 = xor_rows(table[q2.astype(bool)])
        s1 = perf_counter()
        current_server = s1 - s0
        server_total += current_server
        server_parallel = max(server_parallel, current_server)

        e0 = perf_counter()
        recovered = np.bitwise_xor(resp1, resp2)
        expected = np.zeros(RECORD_WORDS, dtype=np.uint64) if target is None else table[target]
        if not np.array_equal(recovered, expected):
            raise RuntimeError("Concrete two-server PIR backend returned an incorrect block.")
        e1 = perf_counter()
        extract_time += e1 - e0

        query_bytes += 2 * ((size + 7) // 8)
        response_bytes += 2 * RECORD_BYTES

    return {
        "query_bytes": float(query_bytes),
        "response_bytes": float(response_bytes),
        "client_query_ms": query_time * 1000.0,
        "client_extract_ms": extract_time * 1000.0,
        "server_total_ms": server_total * 1000.0,
        "server_parallel_ms": server_parallel * 1000.0,
    }


def matrix_database(subdatabase_sizes: Sequence[int], seed: int) -> List[np.ndarray]:
    rng = np.random.default_rng(seed)
    tables: List[np.ndarray] = []
    for size in subdatabase_sizes:
        if size <= 0:
            tables.append(np.zeros((0, 0, RECORD_WORDS), dtype=np.uint64))
            continue
        cols = int(np.ceil(np.sqrt(size)))
        rows = int(np.ceil(size / cols))
        padded = rows * cols
        flat = rng.integers(0, np.iinfo(np.uint64).max, size=(padded, RECORD_WORDS), dtype=np.uint64)
        flat[size:] = 0
        tables.append(flat.reshape(rows, cols, RECORD_WORDS))
    return tables


def execute_single_server_matrix_batch_pir(
    database: Sequence[np.ndarray],
    targets: Sequence[Optional[int]],
) -> Dict[str, float]:
    query_bytes = 0
    response_bytes = 0
    query_time = 0.0
    extract_time = 0.0
    server_total = 0.0
    server_parallel = 0.0

    for table, target in zip(database, targets):
        rows = int(table.shape[0])
        cols = int(table.shape[1]) if table.ndim >= 2 else 0
        if rows == 0 or cols == 0:
            continue

        chosen = 0 if target is None else int(target)
        row_index = chosen // cols
        col_index = chosen % cols

        t0 = perf_counter()
        query = np.zeros(cols, dtype=np.uint64)
        if target is not None:
            query[col_index] = 1
        t1 = perf_counter()
        query_time += t1 - t0

        s0 = perf_counter()
        response = np.tensordot(table, query, axes=([1], [0]))
        s1 = perf_counter()
        current_server = s1 - s0
        server_total += current_server
        server_parallel = max(server_parallel, current_server)

        e0 = perf_counter()
        recovered = response[row_index]
        expected = np.zeros(RECORD_WORDS, dtype=np.uint64) if target is None else table[row_index, col_index]
        if not np.array_equal(recovered, expected):
            raise RuntimeError("Matrix PIR surrogate returned an incorrect block.")
        e1 = perf_counter()
        extract_time += e1 - e0

        query_bytes += cols * MATRIX_QUERY_COEFF_BYTES
        response_bytes += rows * RECORD_BYTES

    return {
        "query_bytes": float(query_bytes),
        "response_bytes": float(response_bytes),
        "client_query_ms": query_time * 1000.0,
        "client_extract_ms": extract_time * 1000.0,
        "server_total_ms": server_total * 1000.0,
        "server_parallel_ms": server_parallel * 1000.0,
    }


def average_metrics(samples: Sequence[Dict[str, float]]) -> Dict[str, float]:
    return {key: mean(item[key] for item in samples) for key in samples[0]}


def run_trial(
    tree_height: int,
    sparsity: float,
    seed: int,
    rebalance_rounds: int,
    profile_rounds: int,
    query_samples: int,
) -> TrialResult:
    occupied = generate_occupied_leaves(tree_height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=tree_height, occupied_leaves=occupied)
    perfectized_sizes = [1 << depth for depth in range(1, tree_height + 1)]
    perfectized_nodes = sum(perfectized_sizes)

    perfectized_db = random_database(perfectized_sizes, seed * 13 + 1)
    perfectized_mat_db = matrix_database(perfectized_sizes, seed * 17 + 1)
    perfectized_sample_metrics: List[Dict[str, float]] = []
    perfectized_matrix_metrics: List[Dict[str, float]] = []
    for offset in range(min(query_samples, len(occupied))):
        leaf = occupied[(seed + offset) % len(occupied)]
        leaf_slot = leaf - (1 << tree_height)
        targets = perfectized_query_targets(leaf_slot=leaf_slot, tree_height=tree_height)
        perfectized_sample_metrics.append(
            execute_two_server_batch_pir(
                perfectized_db,
                targets,
                seed=seed * 97 + offset,
            )
        )
        perfectized_matrix_metrics.append(
            execute_single_server_matrix_batch_pir(
                perfectized_mat_db,
                targets,
            )
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

    for strategy in ["weighted", "count_balanced", "hybrid", "profile_balanced"]:
        proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, tree_height)
        roots = build_interval_forest(proof_nodes)
        num_colors = max_chain_length(roots)
        if strategy == "profile_balanced":
            from subtree_permutation_balance import best_profile_balanced_coloring

            result = best_profile_balanced_coloring(
                proof_nodes=proof_nodes,
                roots=roots,
                num_colors=num_colors,
                initial_strategies=("hybrid", "weighted", "count_balanced"),
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
                strategy=strategy,
                rebalance_rounds=rebalance_rounds,
            )
        valid, _ = verify_coloring(roots, occupied)
        protocol_colors = num_colors
        color_indexes = build_color_indexes(proof_nodes, protocol_colors)
        database = random_database(count_loads, seed * 29 + len(strategy))
        matrix_db = matrix_database(count_loads, seed * 31 + len(strategy))

        per_query_metrics: List[Dict[str, float]] = []
        per_query_matrix_metrics: List[Dict[str, float]] = []
        for offset in range(min(query_samples, len(occupied))):
            leaf = occupied[(seed + offset) % len(occupied)]
            targets = direct_query_targets(color_indexes, occupied, leaf, protocol_colors)
            per_query_metrics.append(
                execute_two_server_batch_pir(
                    database,
                    targets,
                    seed=seed * 131 + offset,
                )
            )
            per_query_matrix_metrics.append(
                execute_single_server_matrix_batch_pir(
                    matrix_db,
                    targets,
                )
            )
        backend = average_metrics(per_query_metrics)
        matrix_backend = average_metrics(per_query_matrix_metrics)

        schemes[strategy] = SchemeMetrics(
            name=strategy,
            protocol_colors=protocol_colors,
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

    return TrialResult(
        height=tree_height,
        sparsity=sparsity,
        seed=seed,
        occupied_leaf_count=len(occupied),
        perfectized_nodes=perfectized_nodes,
        schemes=schemes,
    )


def summarize(trials: Sequence[TrialResult]) -> Dict[str, Dict[str, float]]:
    scheme_names = list(trials[0].schemes.keys())
    summary: Dict[str, Dict[str, float]] = {}
    for scheme in scheme_names:
        summary[scheme] = {
            "protocol_colors": mean(trial.schemes[scheme].protocol_colors for trial in trials),
            "stored_nodes": mean(trial.schemes[scheme].stored_nodes for trial in trials),
            "storage_ratio": mean(trial.schemes[scheme].storage_ratio_vs_perfectized for trial in trials),
            "size_gap": mean(trial.schemes[scheme].size_gap for trial in trials),
            "weight_gap": mean(trial.schemes[scheme].weight_gap for trial in trials),
            "xor_query_bytes": mean(trial.schemes[scheme].xor_query_bytes for trial in trials),
            "xor_response_bytes": mean(trial.schemes[scheme].xor_response_bytes for trial in trials),
            "xor_client_query_ms": mean(trial.schemes[scheme].xor_client_query_ms for trial in trials),
            "xor_client_extract_ms": mean(trial.schemes[scheme].xor_client_extract_ms for trial in trials),
            "xor_server_total_ms": mean(trial.schemes[scheme].xor_server_total_ms for trial in trials),
            "xor_server_parallel_ms": mean(trial.schemes[scheme].xor_server_parallel_ms for trial in trials),
            "mat_query_bytes": mean(trial.schemes[scheme].mat_query_bytes for trial in trials),
            "mat_response_bytes": mean(trial.schemes[scheme].mat_response_bytes for trial in trials),
            "mat_client_query_ms": mean(trial.schemes[scheme].mat_client_query_ms for trial in trials),
            "mat_client_extract_ms": mean(trial.schemes[scheme].mat_client_extract_ms for trial in trials),
            "mat_server_total_ms": mean(trial.schemes[scheme].mat_server_total_ms for trial in trials),
            "mat_server_parallel_ms": mean(trial.schemes[scheme].mat_server_parallel_ms for trial in trials),
            "valid_rate": mean(1.0 if trial.schemes[scheme].valid else 0.0 for trial in trials),
        }
    return summary


def print_summary(label: str, summary: Dict[str, Dict[str, float]]) -> None:
    print(label)
    for scheme in ["perfectized_treepir", "weighted", "count_balanced", "hybrid", "profile_balanced"]:
        metrics = summary[scheme]
        print(
            f"  {scheme}: "
            f"protocol_colors={metrics['protocol_colors']:.2f}, "
            f"stored_nodes={metrics['stored_nodes']:.1f}, "
            f"storage_ratio={metrics['storage_ratio']:.3f}, "
            f"size_gap={metrics['size_gap']:.3f}, "
            f"weight_gap={metrics['weight_gap']:.3f}, "
            f"xor(query_bytes={metrics['xor_query_bytes']:.1f}, "
            f"response_bytes={metrics['xor_response_bytes']:.1f}, "
            f"server_parallel={metrics['xor_server_parallel_ms']:.3f}ms), "
            f"mat(query_bytes={metrics['mat_query_bytes']:.1f}, "
            f"response_bytes={metrics['mat_response_bytes']:.1f}, "
            f"server_parallel={metrics['mat_server_parallel_ms']:.3f}ms), "
            f"valid_rate={metrics['valid_rate'] * 100:.1f}%"
        )


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("list cannot be empty")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare direct sparse-SMT coloring against a perfectized TreePIR baseline using a concrete two-server PIR backend.")
    parser.add_argument("--height", type=int, default=10, help="Sparse SMT height.")
    parser.add_argument("--sparsities", type=str, default="0.2,0.5,0.8", help="Comma-separated empty-leaf ratios.")
    parser.add_argument("--trials", type=int, default=20, help="Trials per sparsity.")
    parser.add_argument("--seed-base", type=int, default=5000, help="Base random seed.")
    parser.add_argument("--rounds", type=int, default=400, help="Local rebalance rounds.")
    parser.add_argument("--profile-rounds", type=int, default=80, help="Subtree-permutation profile-balancing rounds.")
    parser.add_argument("--query-samples", type=int, default=8, help="Sampled occupied leaves per trial for backend timing.")
    args = parser.parse_args()

    sparsities = parse_float_list(args.sparsities)
    print("=== Sparse SMT Concrete PIR Experiment ===")
    print(f"height={args.height}")
    print(f"sparsities={sparsities}")
    print(f"trials_per_sparsity={args.trials}")
    print(f"seed_base={args.seed_base}")
    print(f"rebalance_rounds={args.rounds}")
    print(f"profile_rounds={args.profile_rounds}")
    print(f"query_samples={args.query_samples}")
    print("backends=['two_server_xor_pir','single_server_matrix_pir_surrogate']")
    print()

    overall: List[TrialResult] = []
    for sparsity_index, sparsity in enumerate(sparsities):
        trials: List[TrialResult] = []
        for offset in range(args.trials):
            seed = args.seed_base + sparsity_index * 1000 + offset
            trial = run_trial(
                tree_height=args.height,
                sparsity=sparsity,
                seed=seed,
                rebalance_rounds=args.rounds,
                profile_rounds=args.profile_rounds,
                query_samples=args.query_samples,
            )
            trials.append(trial)
            overall.append(trial)
        print_summary(f"sparsity={sparsity:.2f}", summarize(trials))
        print()

    print_summary("overall", summarize(overall))


if __name__ == "__main__":
    main()
