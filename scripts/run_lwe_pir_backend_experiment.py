from __future__ import annotations

import argparse
import bisect
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode,
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)
from lwe_pir_backend import (
    average_lwe_metrics,
    execute_lwe_batch_pir,
    random_byte_database,
    setup_lwe_pir_database,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced,
    structural_max_bucket_lower_bound,
)
from run_sparse_smt_pir_backend_experiment import build_color_indexes, direct_query_targets


@dataclass
class BackendSchemeResult:
    name: str
    width: int
    stored_nodes: int
    max_bucket: int
    lower_bound: int
    profile_over_lower: float
    query_bytes: float
    response_bytes: float
    hint_bytes: float
    setup_ms: float
    client_query_ms: float
    client_extract_ms: float
    server_total_ms: float
    server_parallel_ms: float


@dataclass
class BackendTrial:
    height: int
    sparsity: float
    seed: int
    occupied_count: int
    active_nodes: int
    exact_width: int
    pruned: BackendSchemeResult
    profile: BackendSchemeResult


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("float list cannot be empty")
    return values


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def pruned_treepir_h_indexes(nodes: Sequence[ProofNode], height: int) -> Dict[int, List[Tuple[int, int, int]]]:
    buckets: Dict[int, List[Tuple[int, int, int]]] = {color: [] for color in range(1, height + 1)}
    for node in nodes:
        if 1 <= node.depth <= height:
            buckets[node.depth].append((node.interval_left, node.interval_right, node.index))
    for color in buckets:
        buckets[color].sort()
    return buckets


def loads_from_indexes(indexes: Dict[int, List[Tuple[int, int, int]]], width: int) -> List[int]:
    return [len(indexes.get(color, [])) for color in range(1, width + 1)]


def targets_from_indexes(
    indexes: Dict[int, List[Tuple[int, int, int]]],
    occupied_leaves: Sequence[int],
    leaf_heap_index: int,
    width: int,
) -> List[Optional[int]]:
    rank = occupied_leaves.index(leaf_heap_index)
    targets: List[Optional[int]] = []
    for color in range(1, width + 1):
        entries = indexes.get(color, [])
        lefts = [left for left, _, _ in entries]
        pos = bisect.bisect_right(lefts, rank) - 1
        if pos >= 0:
            left, right, _ = entries[pos]
            if left <= rank <= right:
                targets.append(pos)
                continue
        targets.append(None)
    return targets


def run_backend_for_scheme(
    name: str,
    indexes: Dict[int, List[Tuple[int, int, int]]],
    occupied: Sequence[int],
    sampled_leaves: Sequence[int],
    width: int,
    stored_nodes: int,
    lower_bound: int,
    seed: int,
    dimension: int,
) -> BackendSchemeResult:
    loads = loads_from_indexes(indexes, width)
    max_bucket = max(loads) if loads else 0
    tables = random_byte_database(loads, seed=seed * 17 + len(name))
    prepared = setup_lwe_pir_database(tables, seed=seed * 19 + len(name), dimension=dimension)

    samples = []
    for offset, leaf in enumerate(sampled_leaves):
        targets = targets_from_indexes(indexes, occupied, leaf, width)
        samples.append(
            execute_lwe_batch_pir(
                prepared,
                targets,
                seed=seed * 23 + offset + len(name),
            )
        )
    metrics = average_lwe_metrics(samples)

    return BackendSchemeResult(
        name=name,
        width=width,
        stored_nodes=stored_nodes,
        max_bucket=max_bucket,
        lower_bound=lower_bound,
        profile_over_lower=(max_bucket / lower_bound) if lower_bound else 0.0,
        query_bytes=metrics["query_bytes"],
        response_bytes=metrics["response_bytes"],
        hint_bytes=metrics["hint_bytes"],
        setup_ms=metrics["setup_ms"],
        client_query_ms=metrics["client_query_ms"],
        client_extract_ms=metrics["client_extract_ms"],
        server_total_ms=metrics["server_total_ms"],
        server_parallel_ms=metrics["server_parallel_ms"],
    )


def run_trial(
    height: int,
    sparsity: float,
    seed: int,
    refine_rounds: int,
    query_samples: int,
    dimension: int,
) -> BackendTrial:
    occupied = generate_occupied_leaves(height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(nodes)
    exact_width = max_chain_length(roots)
    lower_bound = structural_max_bucket_lower_bound(roots, len(nodes), exact_width)

    sampled_leaves = [
        occupied[(seed + offset) % len(occupied)]
        for offset in range(min(query_samples, len(occupied)))
    ]

    pruned_indexes = pruned_treepir_h_indexes(nodes, height)
    pruned_result = run_backend_for_scheme(
        name="pruned_treepir_h",
        indexes=pruned_indexes,
        occupied=occupied,
        sampled_leaves=sampled_leaves,
        width=height,
        stored_nodes=len(nodes),
        lower_bound=lower_bound,
        seed=seed,
        dimension=dimension,
    )

    profile_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    profile_roots = build_interval_forest(profile_nodes)
    best_count_profile_balanced(
        proof_nodes=profile_nodes,
        roots=profile_roots,
        num_colors=exact_width,
        refine_rounds=refine_rounds,
    )
    profile_indexes = build_color_indexes(profile_nodes, exact_width)
    profile_result = run_backend_for_scheme(
        name="profile_balanced",
        indexes=profile_indexes,
        occupied=occupied,
        sampled_leaves=sampled_leaves,
        width=exact_width,
        stored_nodes=len(profile_nodes),
        lower_bound=lower_bound,
        seed=seed,
        dimension=dimension,
    )

    return BackendTrial(
        height=height,
        sparsity=sparsity,
        seed=seed,
        occupied_count=len(occupied),
        active_nodes=len(nodes),
        exact_width=exact_width,
        pruned=pruned_result,
        profile=profile_result,
    )


def avg(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def summarize_group(trials: Sequence[BackendTrial]) -> Dict[str, float]:
    return {
        "occupied": avg(trial.occupied_count for trial in trials),
        "active": avg(trial.active_nodes for trial in trials),
        "m": avg(trial.exact_width for trial in trials),
        "pruned_width": avg(trial.pruned.width for trial in trials),
        "profile_width": avg(trial.profile.width for trial in trials),
        "pruned_max": avg(trial.pruned.max_bucket for trial in trials),
        "profile_max": avg(trial.profile.max_bucket for trial in trials),
        "lower": avg(trial.profile.lower_bound for trial in trials),
        "profile_over_lower": avg(trial.profile.profile_over_lower for trial in trials),
        "pruned_query_bytes": avg(trial.pruned.query_bytes for trial in trials),
        "profile_query_bytes": avg(trial.profile.query_bytes for trial in trials),
        "pruned_response_bytes": avg(trial.pruned.response_bytes for trial in trials),
        "profile_response_bytes": avg(trial.profile.response_bytes for trial in trials),
        "pruned_hint_kb": avg(trial.pruned.hint_bytes for trial in trials) / 1024.0,
        "profile_hint_kb": avg(trial.profile.hint_bytes for trial in trials) / 1024.0,
        "pruned_setup_ms": avg(trial.pruned.setup_ms for trial in trials),
        "profile_setup_ms": avg(trial.profile.setup_ms for trial in trials),
        "pruned_server_parallel_ms": avg(trial.pruned.server_parallel_ms for trial in trials),
        "profile_server_parallel_ms": avg(trial.profile.server_parallel_ms for trial in trials),
        "query_reduction": 100.0
        * (1.0 - avg(trial.profile.query_bytes for trial in trials) / avg(trial.pruned.query_bytes for trial in trials)),
        "parallel_reduction": 100.0
        * (
            1.0
            - avg(trial.profile.server_parallel_ms for trial in trials)
            / avg(trial.pruned.server_parallel_ms for trial in trials)
        ),
        "max_bucket_reduction": 100.0
        * (1.0 - avg(trial.profile.max_bucket for trial in trials) / avg(trial.pruned.max_bucket for trial in trials)),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_note(path: Path, rows: Sequence[Dict[str, object]], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# LWE-PIR Backend Experiment",
        "",
        "## Settings",
        "",
        f"- `heights = {args.heights}`",
        f"- `sparsities = {args.sparsities}`",
        f"- `trials per cell = {args.trials}`",
        f"- `query_samples = {args.query_samples}`",
        f"- `lwe_dimension = {args.dimension}`",
        f"- `profile_refine_rounds = {args.refine_rounds}`",
        "",
        "This experiment uses a randomized LWE-PIR prototype rather than the earlier deterministic matrix surrogate.",
        "It compares Pruned-TreePIR-h against the final profile_balanced organization on the same active proof-bearing nodes.",
        "",
        "## Results",
        "",
        "| h | empty leaves | active | m | lower | pruned max | profile max | max red. | profile/lower | pruned par. ms | profile par. ms | par. red. |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['height']} | {float(row['sparsity']) * 100.0:.4f}% | "
            f"{row['active']:.1f} | {row['m']:.2f} | {row['lower']:.2f} | "
            f"{row['pruned_max']:.2f} | {row['profile_max']:.2f} | "
            f"{row['max_bucket_reduction']:.1f}% | {row['profile_over_lower']:.3f} | "
            f"{row['pruned_server_parallel_ms']:.4f} | {row['profile_server_parallel_ms']:.4f} | "
            f"{row['parallel_reduction']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `lower` is the structural max-bucket lower bound used as the theoretical certificate.",
            "- `max red.` is the reduction in the largest LWE subdatabase, which is the deterministic server-work bottleneck under parallel color execution.",
            "- `par. ms` is the measured maximum per-color server time. Small instances can be dominated by NumPy overhead, so the largest-bucket work metric should be read together with timing.",
            "- The LWE backend is a SimplePIR-style prototype with public matrix/hint preprocessing, not a production SealPIR or Spiral implementation.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a randomized LWE-PIR backend experiment for sparse-SMT layouts.")
    parser.add_argument("--heights", type=str, default="16,20,24")
    parser.add_argument("--sparsities", type=str, default="0.9995,0.99975,0.9999")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--seed-base", type=int, default=91000)
    parser.add_argument("--refine-rounds", type=int, default=15)
    parser.add_argument("--query-samples", type=int, default=3)
    parser.add_argument("--dimension", type=int, default=64)
    parser.add_argument("--csv", type=Path, default=Path("examples/lwe_pir_backend_results.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/lwe_pir_backend_experiment_note.md"))
    args = parser.parse_args()

    heights = parse_int_list(args.heights)
    sparsities = parse_float_list(args.sparsities)
    rows: List[Dict[str, object]] = []

    print("=== LWE-PIR Backend Experiment ===")
    print(f"heights={heights}")
    print(f"sparsities={sparsities}")
    print(f"trials={args.trials}")
    print(f"query_samples={args.query_samples}")
    print(f"dimension={args.dimension}")
    print()

    for height in heights:
        for sparsity_index, sparsity in enumerate(sparsities):
            group: List[BackendTrial] = []
            for offset in range(args.trials):
                seed = args.seed_base + height * 1000 + sparsity_index * 100 + offset
                trial = run_trial(
                    height=height,
                    sparsity=sparsity,
                    seed=seed,
                    refine_rounds=args.refine_rounds,
                    query_samples=args.query_samples,
                    dimension=args.dimension,
                )
                group.append(trial)
            stats = summarize_group(group)
            row = {"height": height, "sparsity": sparsity, **stats}
            rows.append(row)
            print(
                f"h={height}, sparsity={sparsity:.6f}: "
                f"active={stats['active']:.1f}, m={stats['m']:.2f}, "
                f"profile/lower={stats['profile_over_lower']:.3f}, "
                f"max_bucket_reduction={stats['max_bucket_reduction']:.1f}%, "
                f"parallel_reduction={stats['parallel_reduction']:.1f}%"
            )

    write_csv(args.csv, rows)
    write_note(args.note, rows, args)
    print()
    print(f"csv={args.csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
