from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode,
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
    traverse,
    verify_coloring,
)
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


@dataclass
class SchemeMetrics:
    max_bucket: int
    size_gap: int
    bucket_ratio: float
    valid: bool


@dataclass
class TrialMetrics:
    height: int
    sparsity: float
    seed: int
    occupied_count: int
    active_nodes: int
    exact_width: int
    ideal_max_bucket: int
    structural_lower_bound: int
    pruned_h: SchemeMetrics
    count: SchemeMetrics
    hybrid: SchemeMetrics
    profile: SchemeMetrics
    profile_passes: int
    profile_moves: int
    profile_runtime_ms: float
    skipped: bool = False


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("float list cannot be empty")
    return values


def count_signature(loads: Sequence[int]) -> Tuple[int, ...]:
    return tuple(sorted(loads, reverse=True))


def count_loads_for_nodes(nodes: Sequence[ProofNode], num_colors: int) -> List[int]:
    loads = [0] * num_colors
    for node in nodes:
        if node.color is not None:
            loads[node.color - 1] += 1
    return loads


def pruned_treepir_h_loads(nodes: Sequence[ProofNode], height: int) -> List[int]:
    loads = [0] * height
    for node in nodes:
        if 1 <= node.depth <= height:
            loads[node.depth - 1] += 1
    return loads


def structural_max_bucket_lower_bound(roots: Sequence[ProofNode], active_nodes: int, num_colors: int) -> int:
    """Instance-level lower bound for any exact-width valid coloring.

    Besides the equal-split bound ceil(N/m), every active prefix of length d
    blocks d colors for all strict descendants. Those descendants must fit into
    at most m-d remaining colors, so one remaining color must contain at least
    ceil(descendants / (m-d)) nodes.
    """
    if active_nodes <= 0 or num_colors <= 0:
        return 0

    lower = (active_nodes + num_colors - 1) // num_colors

    def dfs(node: ProofNode, active_depth: int) -> int:
        nonlocal lower
        subtree_size = 1
        for child in node.children:
            subtree_size += dfs(child, active_depth + 1)

        strict_descendants = subtree_size - 1
        remaining_colors = num_colors - active_depth
        if strict_descendants > 0 and remaining_colors > 0:
            lower = max(lower, (strict_descendants + remaining_colors - 1) // remaining_colors)
        return subtree_size

    for root in roots:
        dfs(root, 1)
    return lower


def first_fit_coloring(roots: Sequence[ProofNode], num_colors: int) -> None:
    def dfs(node: ProofNode, used_mask: int) -> None:
        chosen_color: Optional[int] = None
        for color in range(1, num_colors + 1):
            if not (used_mask & (1 << (color - 1))):
                chosen_color = color
                break
        if chosen_color is None:
            raise ValueError("first-fit coloring ran out of colors")

        node.color = chosen_color
        next_mask = used_mask | (1 << (chosen_color - 1))
        for child in node.children:
            dfs(child, next_mask)

    for root in roots:
        dfs(root, 0)


def summarize_scheme(loads: Sequence[int], valid: bool) -> SchemeMetrics:
    if not loads:
        return SchemeMetrics(max_bucket=0, size_gap=0, bucket_ratio=0.0, valid=valid)
    max_bucket = max(loads)
    avg_bucket = sum(loads) / len(loads)
    return SchemeMetrics(
        max_bucket=max_bucket,
        size_gap=max(loads) - min(loads),
        bucket_ratio=(max_bucket / avg_bucket) if avg_bucket else 0.0,
        valid=valid,
    )


def hungarian_assignment(cost_matrix: Sequence[Sequence[float]]) -> List[int]:
    n = len(cost_matrix)
    if n == 0:
        return []
    if any(len(row) != n for row in cost_matrix):
        raise ValueError("Hungarian assignment expects a square matrix.")

    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        j0 = 0
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    if any(index < 0 for index in assignment):
        raise RuntimeError("Hungarian assignment failed.")
    return assignment


def annotate_count_state(
    roots: Sequence[ProofNode],
    num_colors: int,
) -> Tuple[Dict[int, int], Dict[int, List[int]]]:
    ancestor_masks: Dict[int, int] = {}
    subtree_counts: Dict[int, List[int]] = {}

    def dfs(node: ProofNode, ancestor_mask: int) -> List[int]:
        ancestor_masks[id(node)] = ancestor_mask
        counts = [0] * num_colors
        next_mask = ancestor_mask
        if node.color is not None:
            next_mask |= 1 << (node.color - 1)

        for child in node.children:
            child_counts = dfs(child, next_mask)
            for idx in range(num_colors):
                counts[idx] += child_counts[idx]

        if node.color is not None:
            counts[node.color - 1] += 1
        subtree_counts[id(node)] = counts
        return counts

    for root in roots:
        dfs(root, 0)
    return ancestor_masks, subtree_counts


def best_count_mapping(
    available_colors: Sequence[int],
    global_loads: Sequence[int],
    subtree_counts: Sequence[int],
) -> Dict[int, int]:
    colors = list(available_colors)
    cost_matrix: List[List[float]] = []
    for source in colors:
        source_idx = source - 1
        row: List[float] = []
        for target in colors:
            target_idx = target - 1
            outside = global_loads[target_idx] - subtree_counts[target_idx]
            row.append(float((outside + subtree_counts[source_idx]) ** 2))
        cost_matrix.append(row)
    assignment = hungarian_assignment(cost_matrix)
    return {colors[src_idx]: colors[tgt_idx] for src_idx, tgt_idx in enumerate(assignment)}


def candidate_loads_after_mapping(
    mapping: Dict[int, int],
    available_colors: Sequence[int],
    global_loads: Sequence[int],
    subtree_counts: Sequence[int],
) -> List[int]:
    candidate = list(global_loads)
    for color in available_colors:
        candidate[color - 1] -= subtree_counts[color - 1]
    for old_color, new_color in mapping.items():
        candidate[new_color - 1] += subtree_counts[old_color - 1]
    return candidate


def apply_mapping_to_subtree(node: ProofNode, mapping: Dict[int, int]) -> None:
    for current in traverse(node):
        if current.color is not None:
            current.color = mapping.get(current.color, current.color)


def count_profile_refine(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    num_colors: int,
    refine_rounds: int,
) -> Tuple[List[int], int, int]:
    first_fit_coloring(roots, num_colors)
    loads = count_loads_for_nodes(proof_nodes, num_colors)
    current_signature = count_signature(loads)
    all_nodes = [node for root in roots for node in traverse(root)]
    moves = 0
    passes = 0

    for _ in range(refine_rounds):
        passes += 1
        ancestor_masks, subtree_counts_by_node = annotate_count_state(roots, num_colors)
        best_move: Optional[Tuple[ProofNode, Dict[int, int], List[int], Tuple[int, ...]]] = None

        for node in all_nodes:
            ancestor_mask = ancestor_masks[id(node)]
            available_colors = [
                color for color in range(1, num_colors + 1)
                if not (ancestor_mask & (1 << (color - 1)))
            ]
            if len(available_colors) <= 1:
                continue

            subtree_counts = subtree_counts_by_node[id(node)]
            mapping = best_count_mapping(available_colors, loads, subtree_counts)
            if all(mapping[color] == color for color in available_colors):
                continue

            candidate_loads = candidate_loads_after_mapping(
                mapping=mapping,
                available_colors=available_colors,
                global_loads=loads,
                subtree_counts=subtree_counts,
            )
            candidate_signature = count_signature(candidate_loads)
            if candidate_signature < current_signature:
                if best_move is None or candidate_signature < best_move[3]:
                    best_move = (node, mapping, candidate_loads, candidate_signature)

        if best_move is None:
            break

        node, mapping, loads, current_signature = best_move
        apply_mapping_to_subtree(node, mapping)
        moves += 1

    return loads, passes, moves


def best_count_profile_balanced(
    proof_nodes: List[ProofNode],
    roots: Sequence[ProofNode],
    num_colors: int,
    refine_rounds: int,
) -> Tuple[List[int], int, int]:
    return count_profile_refine(
        proof_nodes=proof_nodes,
        roots=roots,
        num_colors=num_colors,
        refine_rounds=refine_rounds,
    )


def sample_occupied_leaves_by_count(height: int, occupied_count: int, seed: int) -> List[int]:
    total_leaves = 1 << height
    count = max(1, min(total_leaves, occupied_count))
    rng = random.Random(seed)
    slots: set[int] = set()
    while len(slots) < count:
        slots.add(rng.getrandbits(height))
    base = 1 << height
    return sorted(base + slot for slot in slots)


def build_instance(
    height: int,
    sparsity: float,
    seed: int,
    occupied_count: Optional[int] = None,
) -> Tuple[List[int], FixedSparseMerkleColoring, float]:
    if occupied_count is None:
        occupied = generate_occupied_leaves(height, sparsity, seed)
    else:
        occupied = sample_occupied_leaves_by_count(height, occupied_count, seed)
        sparsity = 1.0 - (len(occupied) / float(1 << height))
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    return occupied, helper, sparsity


def run_one_trial(
    height: int,
    sparsity: float,
    seed: int,
    initial_rounds: int,
    refine_rounds: int,
    max_active_nodes: int,
    occupied_count: Optional[int] = None,
) -> TrialMetrics:
    occupied, helper, actual_sparsity = build_instance(height, sparsity, seed, occupied_count)
    base_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    base_roots = build_interval_forest(base_nodes)
    exact_width = max_chain_length(base_roots)
    active_nodes = len(base_nodes)
    ideal_max_bucket = (active_nodes + exact_width - 1) // exact_width if exact_width else 0
    structural_lower_bound = structural_max_bucket_lower_bound(base_roots, active_nodes, exact_width)
    if active_nodes > max_active_nodes:
        empty = SchemeMetrics(0, 0, 0.0, False)
        return TrialMetrics(
            height=height,
            sparsity=actual_sparsity,
            seed=seed,
            occupied_count=len(occupied),
            active_nodes=active_nodes,
            exact_width=exact_width,
            ideal_max_bucket=ideal_max_bucket,
            structural_lower_bound=structural_lower_bound,
            pruned_h=empty,
            count=empty,
            hybrid=empty,
            profile=empty,
            profile_passes=0,
            profile_moves=0,
            profile_runtime_ms=0.0,
            skipped=True,
        )

    pruned_loads = pruned_treepir_h_loads(base_nodes, height)
    pruned_metrics = summarize_scheme(pruned_loads, True)

    scheme_metrics: Dict[str, SchemeMetrics] = {}
    for strategy in ("count_balanced", "hybrid"):
        nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
        roots = build_interval_forest(nodes)
        loads, _ = color_proof_nodes(
            proof_nodes=nodes,
            roots=roots,
            num_colors=exact_width,
            strategy=strategy,
            rebalance_rounds=initial_rounds,
        )
        valid, _ = verify_coloring(roots, occupied)
        scheme_metrics[strategy] = summarize_scheme(loads, valid)

    profile_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    profile_roots = build_interval_forest(profile_nodes)
    t0 = perf_counter()
    profile_loads, passes, moves = best_count_profile_balanced(
        proof_nodes=profile_nodes,
        roots=profile_roots,
        num_colors=exact_width,
        refine_rounds=refine_rounds,
    )
    t1 = perf_counter()
    valid_profile, _ = verify_coloring(profile_roots, occupied)

    return TrialMetrics(
        height=height,
        sparsity=actual_sparsity,
        seed=seed,
        occupied_count=len(occupied),
        active_nodes=active_nodes,
        exact_width=exact_width,
        ideal_max_bucket=ideal_max_bucket,
        structural_lower_bound=structural_lower_bound,
        pruned_h=pruned_metrics,
        count=scheme_metrics["count_balanced"],
        hybrid=scheme_metrics["hybrid"],
        profile=summarize_scheme(profile_loads, valid_profile),
        profile_passes=passes,
        profile_moves=moves,
        profile_runtime_ms=(t1 - t0) * 1000.0,
    )


def aggregate(trials: Sequence[TrialMetrics]) -> Dict[str, float]:
    valid_trials = [trial for trial in trials if not trial.skipped]
    if not valid_trials:
        return {"skipped": 1.0, "trials": float(len(trials))}

    def avg(values: Iterable[float]) -> float:
        values = list(values)
        return mean(values) if values else 0.0

    hybrid_max = avg(trial.hybrid.max_bucket for trial in valid_trials)
    profile_max = avg(trial.profile.max_bucket for trial in valid_trials)
    return {
        "skipped": 0.0,
        "trials": float(len(valid_trials)),
        "occupied": avg(trial.occupied_count for trial in valid_trials),
        "active": avg(trial.active_nodes for trial in valid_trials),
        "m": avg(trial.exact_width for trial in valid_trials),
        "ideal_max": avg(trial.ideal_max_bucket for trial in valid_trials),
        "structural_lb": avg(trial.structural_lower_bound for trial in valid_trials),
        "pruned_max": avg(trial.pruned_h.max_bucket for trial in valid_trials),
        "pruned_gap": avg(trial.pruned_h.size_gap for trial in valid_trials),
        "count_max": avg(trial.count.max_bucket for trial in valid_trials),
        "count_gap": avg(trial.count.size_gap for trial in valid_trials),
        "hybrid_max": hybrid_max,
        "hybrid_gap": avg(trial.hybrid.size_gap for trial in valid_trials),
        "profile_max": profile_max,
        "profile_gap": avg(trial.profile.size_gap for trial in valid_trials),
        "profile_ratio": avg(trial.profile.bucket_ratio for trial in valid_trials),
        "profile_over_ideal": avg(
            (trial.profile.max_bucket / trial.ideal_max_bucket) if trial.ideal_max_bucket else 0.0
            for trial in valid_trials
        ),
        "profile_over_lb": avg(
            (trial.profile.max_bucket / trial.structural_lower_bound) if trial.structural_lower_bound else 0.0
            for trial in valid_trials
        ),
        "reduction_vs_hybrid": 100.0 * (1.0 - profile_max / hybrid_max) if hybrid_max else 0.0,
        "runtime_ms": avg(trial.profile_runtime_ms for trial in valid_trials),
        "moves": avg(trial.profile_moves for trial in valid_trials),
        "valid_rate": avg(1.0 if trial.count.valid and trial.hybrid.valid and trial.profile.valid else 0.0 for trial in valid_trials),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: Sequence[Dict[str, object]], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Height-Sparsity Profile-Balancing Experiment",
        "",
        "## Settings",
        "",
        f"- `heights = {args.heights}`",
        f"- `occupied_counts = {args.occupied_counts}`" if args.occupied_counts else f"- `sparsities = {args.sparsities}`",
        f"- `trials per cell = {args.trials}`",
        f"- `initial_rounds = {args.initial_rounds}`",
        f"- `refine_rounds = {args.refine_rounds}`",
        f"- `max_active_nodes = {args.max_active_nodes}`",
        "",
        "The experiment compares `count_balanced`, `hybrid`, and the self-contained count-only `profile_balanced` refinement.",
        "All schemes use the exact active width `m` of the generated sparse SMT instance.",
        "",
        "## Results",
        "",
        "| h | empty leaves | occupied | active | m | pruned-h max | lower | profile max | profile/lower | reduction | profile gap | runtime ms | valid |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        sparsity_pct = float(row["sparsity"]) * 100.0
        if row.get("skipped"):
            lines.append(
                f"| {row['height']} | {sparsity_pct:.4f}% | skipped | {row.get('active', 0):.1f} | {row.get('m', 0):.2f} | - | - | - | - | - | - | - | - |"
            )
            continue
        lines.append(
            f"| {row['height']} | {sparsity_pct:.4f}% | "
            f"{row['occupied']:.1f} | {row['active']:.1f} | {row['m']:.2f} | "
            f"{row['pruned_max']:.2f} | {row['structural_lb']:.2f} | {row['profile_max']:.2f} | "
            f"{row['profile_over_lb']:.3f} | {row['reduction_vs_hybrid']:.1f}% | "
            f"{row['profile_gap']:.2f} | {row['runtime_ms']:.1f} | "
            f"{row['valid_rate'] * 100:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Reading the Table",
            "",
            "- `active` is the number of active proof-bearing nodes stored by the direct sparse organization.",
            "- `empty leaves` is the induced SMT sparsity, computed as `1 - occupied / 2^h`.",
            "- `m` is the exact active batch width.",
            "- `pruned-h max` is the largest inherited height-color bucket after pruning empty/default records but keeping width `h`.",
            "- `lower` is the maximum of the equal-split bound `ceil(active / m)` and the active-prefix capacity bound.",
            "- `profile max` is the largest color subdatabase after subtree-profile refinement.",
            "- `profile/lower` measures the instance-wise certified ratio of `profile_balanced` to the structural lower bound.",
            "- `reduction` is the percentage decrease of `profile max` relative to the stronger node-local baseline `hybrid`.",
            "- `profile gap` is the post-refinement subdatabase size gap.",
            "- `profile ratio` is `profile max / average bucket size`; values close to `1` mean near-perfect balance.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate profile-balanced coloring across different SMT heights and sparsities."
    )
    parser.add_argument("--heights", type=str, default="16,20,24")
    parser.add_argument(
        "--occupied-counts",
        type=str,
        default="256,1024,4096",
        help="Comma-separated occupied-leaf counts. If set, sparsities are derived from h and n.",
    )
    parser.add_argument(
        "--sparsities",
        type=str,
        default="",
        help="Comma-separated empty-leaf ratios used only when --occupied-counts is empty.",
    )
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=52000)
    parser.add_argument("--initial-rounds", type=int, default=120)
    parser.add_argument("--refine-rounds", type=int, default=25)
    parser.add_argument("--max-active-nodes", type=int, default=12000)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("examples/height16_24_sparsity_profile_balance_results.csv"),
    )
    parser.add_argument(
        "--note",
        type=Path,
        default=Path("notes/height16_24_sparsity_profile_balance_experiment_note.md"),
    )
    args = parser.parse_args()

    heights = parse_int_list(args.heights)
    occupied_counts = parse_int_list(args.occupied_counts) if args.occupied_counts.strip() else []
    sparsities = parse_float_list(args.sparsities) if args.sparsities.strip() else []
    if not occupied_counts and not sparsities:
        raise ValueError("provide either --occupied-counts or --sparsities")

    all_trials: List[TrialMetrics] = []
    summary_rows: List[Dict[str, object]] = []

    print("=== Height-Sparsity Profile-Balancing Experiment ===")
    print(f"heights={heights}")
    if occupied_counts:
        print(f"occupied_counts={occupied_counts}")
    else:
        print(f"sparsities={sparsities}")
    print(f"trials={args.trials}")
    print(f"initial_rounds={args.initial_rounds}")
    print(f"refine_rounds={args.refine_rounds}")
    print(f"max_active_nodes={args.max_active_nodes}")
    print()

    for height in heights:
        groups = [(index, None, count) for index, count in enumerate(occupied_counts)]
        if not groups:
            groups = [(index, sparsity, None) for index, sparsity in enumerate(sparsities)]
        for sparsity_index, sparsity, occupied_count in groups:
            group: List[TrialMetrics] = []
            for offset in range(args.trials):
                seed = args.seed_base + height * 1000 + sparsity_index * 100 + offset
                trial = run_one_trial(
                    height=height,
                    sparsity=sparsity if sparsity is not None else 0.0,
                    seed=seed,
                    initial_rounds=args.initial_rounds,
                    refine_rounds=args.refine_rounds,
                    max_active_nodes=args.max_active_nodes,
                    occupied_count=occupied_count,
                )
                group.append(trial)
                all_trials.append(trial)
            stats = aggregate(group)
            row: Dict[str, object] = {
                "height": height,
                "sparsity": group[0].sparsity if group else (sparsity if sparsity is not None else 0.0),
                **stats,
            }
            summary_rows.append(row)
            if stats.get("skipped"):
                print(
                    f"h={height}, sparsity={row['sparsity']:.6f}: skipped "
                    f"(active_nodes={stats.get('active', 0):.1f})"
                )
            else:
                print(
                    f"h={height}, sparsity={row['sparsity']:.6f}: "
                    f"active={stats['active']:.1f}, m={stats['m']:.2f}, "
                    f"count_max={stats['count_max']:.2f}, "
                    f"hybrid_max={stats['hybrid_max']:.2f}, "
                    f"profile_max={stats['profile_max']:.2f}, "
                    f"reduction={stats['reduction_vs_hybrid']:.1f}%, "
                    f"profile_gap={stats['profile_gap']:.2f}, "
                    f"profile_ratio={stats['profile_ratio']:.3f}, "
                    f"runtime_ms={stats['runtime_ms']:.1f}, "
                    f"valid={stats['valid_rate'] * 100:.1f}%"
                )

    write_csv(args.csv, summary_rows)
    write_markdown(args.note, summary_rows, args)
    print()
    print(f"csv={args.csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
