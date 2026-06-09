from __future__ import annotations

import argparse
import csv
import gc
import math
import random
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter
from typing import Dict, Iterable, List, Sequence, Tuple

from generate_full_sparse_smt_example import (
    ProofNode,
    build_interval_forest,
    max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced,
    structural_max_bucket_lower_bound,
)
from run_real_smt_final_experiment_suite import WorkloadSpec, selected_workloads
from run_real_smt_workload_experiment import iter_keys, key_to_slot
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


@dataclass(frozen=True)
class SourceModel:
    spec: WorkloadSpec
    height: int
    prefix_bits: int
    input_records: int
    unique_keys: int
    unique_source_slots: List[int]
    source_prefixes: List[int]


@dataclass
class SnapshotResult:
    dataset: str
    dataset_kind: str
    source_path: str
    source_mode: str
    coloring_strategy: str
    height: int
    prefix_bits: int
    seed: int
    epoch: int
    target_occupied: int
    actual_occupied: int
    input_records: int
    unique_source_keys: int
    active_nodes: int
    active_width_m: int
    structural_lower_bound: int
    pbc_width: int
    sparse_width: int
    pbc_stored_records: int
    sparse_stored_records: int
    pbc_max_bucket: int
    sparse_max_bucket: int
    width_gain: float
    stored_record_gain: float
    max_bucket_gain: float
    activebalance_ms: float
    total_snapshot_build_ms: float
    peak_memory_mb: float
    changed_fraction_from_previous: float | str
    jaccard_with_previous: float | str
    activebalance_ms_per_changed_leaf: float | str
    valid: bool
    skipped: bool
    skip_reason: str


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def asdict_result(result: SnapshotResult) -> Dict[str, object]:
    return {
        "dataset": result.dataset,
        "dataset_kind": result.dataset_kind,
        "source_path": result.source_path,
        "source_mode": result.source_mode,
        "coloring_strategy": result.coloring_strategy,
        "height": result.height,
        "prefix_bits": result.prefix_bits,
        "seed": result.seed,
        "epoch": result.epoch,
        "target_occupied": result.target_occupied,
        "actual_occupied": result.actual_occupied,
        "input_records": result.input_records,
        "unique_source_keys": result.unique_source_keys,
        "active_nodes": result.active_nodes,
        "active_width_m": result.active_width_m,
        "structural_lower_bound": result.structural_lower_bound,
        "pbc_width": result.pbc_width,
        "sparse_width": result.sparse_width,
        "pbc_stored_records": result.pbc_stored_records,
        "sparse_stored_records": result.sparse_stored_records,
        "pbc_max_bucket": result.pbc_max_bucket,
        "sparse_max_bucket": result.sparse_max_bucket,
        "width_gain": result.width_gain,
        "stored_record_gain": result.stored_record_gain,
        "max_bucket_gain": result.max_bucket_gain,
        "activebalance_ms": result.activebalance_ms,
        "total_snapshot_build_ms": result.total_snapshot_build_ms,
        "peak_memory_mb": result.peak_memory_mb,
        "changed_fraction_from_previous": result.changed_fraction_from_previous,
        "jaccard_with_previous": result.jaccard_with_previous,
        "activebalance_ms_per_changed_leaf": result.activebalance_ms_per_changed_leaf,
        "valid": result.valid,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
    }


def load_source_model(spec: WorkloadSpec, height: int, prefix_bits: int) -> SourceModel:
    raw_keys = list(iter_keys(path=spec.path, column=spec.column, json_field=None, limit=spec.limit))
    if not raw_keys:
        raise ValueError(f"No keys were extracted from {spec.path}.")

    unique_keys = sorted(set(raw_keys))
    slots = sorted({key_to_slot(value, height=height, key_mode=spec.key_mode) for value in unique_keys})
    if not slots:
        raise ValueError(f"No slots were produced for {spec.path}.")

    clipped_prefix_bits = min(prefix_bits, height)
    suffix_bits = height - clipped_prefix_bits
    prefixes = [slot >> suffix_bits for slot in slots]

    return SourceModel(
        spec=spec,
        height=height,
        prefix_bits=clipped_prefix_bits,
        input_records=len(raw_keys),
        unique_keys=len(unique_keys),
        unique_source_slots=slots,
        source_prefixes=prefixes,
    )


def draw_slots_from_source(
    model: SourceModel,
    target_count: int,
    seed: int,
    exclude: Iterable[int] = (),
) -> List[int]:
    if target_count <= 0:
        raise ValueError("target_count must be positive")
    if target_count > (1 << model.height):
        raise ValueError(f"target_count={target_count} exceeds the height-{model.height} universe")

    rng = random.Random(seed)
    excluded = set(exclude)
    slots: set[int] = set()

    usable_real_slots = [slot for slot in model.unique_source_slots if slot not in excluded]
    if target_count <= len(usable_real_slots):
        return sorted(rng.sample(usable_real_slots, target_count))

    slots.update(usable_real_slots)
    suffix_bits = model.height - model.prefix_bits
    prefix_pool = model.source_prefixes or [0]
    attempts = 0
    while len(slots) < target_count:
        prefix = rng.choice(prefix_pool)
        suffix = rng.getrandbits(suffix_bits) if suffix_bits > 0 else 0
        candidate = (prefix << suffix_bits) | suffix
        if candidate not in excluded:
            slots.add(candidate)
        attempts += 1
        if attempts > target_count * 1000:
            raise RuntimeError("could not draw enough unique deployment-scale slots")

    return sorted(slots)


def source_mode(model: SourceModel, target_count: int) -> str:
    if target_count <= len(model.unique_source_slots):
        return "real-trace-exact"
    return f"real-trace-bootstrapped-prefix{model.prefix_bits}"


def heap_leaves(slots: Sequence[int], height: int) -> List[int]:
    base = 1 << height
    return [base + slot for slot in sorted(set(slots))]


def build_proof_nodes_from_slots(slots: Sequence[int], height: int) -> List[ProofNode]:
    ordered = sorted(set(slots))
    proof_nodes: List[ProofNode] = []

    def recurse(left: int, right: int, depth: int, prefix: int) -> None:
        if right - left <= 1 or depth >= height:
            return

        bit_index = height - depth - 1
        bit_mask = 1 << bit_index
        mid = left
        while mid < right and (ordered[mid] & bit_mask) == 0:
            mid += 1

        if mid == left:
            recurse(left, right, depth + 1, (prefix << 1) | 1)
            return
        if mid == right:
            recurse(left, right, depth + 1, prefix << 1)
            return

        child_depth = depth + 1
        left_child_index = (1 << child_depth) + (prefix << 1)
        right_child_index = left_child_index + 1
        proof_nodes.append(
            ProofNode(
                index=left_child_index,
                depth=child_depth,
                interval_left=mid,
                interval_right=right - 1,
                weight=right - mid,
                covers_leaves=[],
            )
        )
        proof_nodes.append(
            ProofNode(
                index=right_child_index,
                depth=child_depth,
                interval_left=left,
                interval_right=mid - 1,
                weight=mid - left,
                covers_leaves=[],
            )
        )
        recurse(left, mid, child_depth, prefix << 1)
        recurse(mid, right, child_depth, (prefix << 1) | 1)

    recurse(0, len(ordered), 0, 0)
    return proof_nodes


def fast_verify_coloring(roots: Sequence[ProofNode], num_colors: int) -> bool:
    by_color: Dict[int, List[ProofNode]] = defaultdict(list)
    valid = True

    def dfs(node: ProofNode, path_colors: set[int]) -> None:
        nonlocal valid
        if node.color is None or not (1 <= node.color <= num_colors):
            valid = False
            return
        if node.color in path_colors:
            valid = False
            return
        by_color[node.color].append(node)
        next_colors = set(path_colors)
        next_colors.add(node.color)
        for child in node.children:
            dfs(child, next_colors)

    for root in roots:
        dfs(root, set())

    for nodes in by_color.values():
        ordered = sorted(nodes, key=lambda item: (item.interval_left, item.interval_right))
        for left, right in zip(ordered, ordered[1:]):
            if left.interval_right >= right.interval_left:
                valid = False
                break
    return valid


def safe_ratio(baseline: float, improved: float) -> float:
    if baseline <= 0:
        return 0.0
    return baseline / improved if improved > 0 else 0.0


def pbc_width(active_width: int) -> int:
    return max(1, math.ceil(1.5 * active_width))


def pbc_max_bucket(active_nodes: int, active_width: int) -> int:
    width = pbc_width(active_width)
    return math.ceil((3 * active_nodes) / width) if width else 0


def changed_stats(current: Sequence[int], previous: Sequence[int] | None) -> Tuple[float | str, float | str, int]:
    if previous is None:
        return "", "", len(current)
    current_set = set(current)
    previous_set = set(previous)
    changed = len(current_set.symmetric_difference(previous_set))
    union = len(current_set | previous_set)
    changed_fraction = changed / max(1, len(current_set))
    jaccard = len(current_set & previous_set) / union if union else 1.0
    return changed_fraction, jaccard, changed


def run_snapshot(
    model: SourceModel,
    target_count: int,
    slots: Sequence[int],
    previous_slots: Sequence[int] | None,
    seed: int,
    epoch: int,
    coloring_strategy: str,
    balance_rounds: int,
    max_active_nodes: int,
) -> SnapshotResult:
    leaves = heap_leaves(slots, model.height)
    changed_fraction, jaccard, changed = changed_stats(slots, previous_slots)
    tracemalloc.start()
    total_t0 = perf_counter()
    proof_nodes = build_proof_nodes_from_slots(slots, model.height)
    roots = build_interval_forest(proof_nodes)
    active_width = max_chain_length(roots)
    lower_bound = structural_max_bucket_lower_bound(roots, len(proof_nodes), active_width)

    if len(proof_nodes) > max_active_nodes:
        current, peak = tracemalloc.get_traced_memory()
        del current
        tracemalloc.stop()
        total_t1 = perf_counter()
        pbc_w = pbc_width(active_width)
        pbc_max = pbc_max_bucket(len(proof_nodes), active_width)
        return SnapshotResult(
            dataset=model.spec.label,
            dataset_kind=model.spec.kind,
            source_path=model.spec.path.as_posix(),
            source_mode=source_mode(model, target_count),
            coloring_strategy=coloring_strategy,
            height=model.height,
            prefix_bits=model.prefix_bits,
            seed=seed,
            epoch=epoch,
            target_occupied=target_count,
            actual_occupied=len(leaves),
            input_records=model.input_records,
            unique_source_keys=model.unique_keys,
            active_nodes=len(proof_nodes),
            active_width_m=active_width,
            structural_lower_bound=lower_bound,
            pbc_width=pbc_w,
            sparse_width=active_width,
            pbc_stored_records=3 * len(proof_nodes),
            sparse_stored_records=len(proof_nodes),
            pbc_max_bucket=pbc_max,
            sparse_max_bucket=0,
            width_gain=safe_ratio(float(pbc_w), float(active_width)),
            stored_record_gain=3.0,
            max_bucket_gain=0.0,
            activebalance_ms=0.0,
            total_snapshot_build_ms=(total_t1 - total_t0) * 1000.0,
            peak_memory_mb=peak / (1024.0 * 1024.0),
            changed_fraction_from_previous=changed_fraction,
            jaccard_with_previous=jaccard,
            activebalance_ms_per_changed_leaf="",
            valid=False,
            skipped=True,
            skip_reason=f"active_nodes>{max_active_nodes}",
        )

    balance_t0 = perf_counter()
    if coloring_strategy == "count_profile":
        sparse_loads, _, _ = best_count_profile_balanced(
            proof_nodes=proof_nodes,
            roots=roots,
            num_colors=active_width,
            refine_rounds=balance_rounds,
        )
    else:
        sparse_loads, _ = color_proof_nodes(
            proof_nodes=proof_nodes,
            roots=roots,
            num_colors=active_width,
            strategy=coloring_strategy,
            rebalance_rounds=balance_rounds,
        )
    balance_t1 = perf_counter()
    valid = fast_verify_coloring(roots, active_width)
    total_t1 = perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    del current
    tracemalloc.stop()

    pbc_w = pbc_width(active_width)
    pbc_max = pbc_max_bucket(len(proof_nodes), active_width)
    sparse_max = max(sparse_loads) if sparse_loads else 0
    activebalance_ms = (balance_t1 - balance_t0) * 1000.0
    ms_per_changed = activebalance_ms / changed if changed else ""

    return SnapshotResult(
        dataset=model.spec.label,
        dataset_kind=model.spec.kind,
        source_path=model.spec.path.as_posix(),
        source_mode=source_mode(model, target_count),
        coloring_strategy=coloring_strategy,
        height=model.height,
        prefix_bits=model.prefix_bits,
        seed=seed,
        epoch=epoch,
        target_occupied=target_count,
        actual_occupied=len(leaves),
        input_records=model.input_records,
        unique_source_keys=model.unique_keys,
        active_nodes=len(proof_nodes),
        active_width_m=active_width,
        structural_lower_bound=lower_bound,
        pbc_width=pbc_w,
        sparse_width=active_width,
        pbc_stored_records=3 * len(proof_nodes),
        sparse_stored_records=len(proof_nodes),
        pbc_max_bucket=pbc_max,
        sparse_max_bucket=sparse_max,
        width_gain=safe_ratio(float(pbc_w), float(active_width)),
        stored_record_gain=3.0,
        max_bucket_gain=safe_ratio(float(pbc_max), float(sparse_max)),
        activebalance_ms=activebalance_ms,
        total_snapshot_build_ms=(total_t1 - total_t0) * 1000.0,
        peak_memory_mb=peak / (1024.0 * 1024.0),
        changed_fraction_from_previous=changed_fraction,
        jaccard_with_previous=jaccard,
        activebalance_ms_per_changed_leaf=ms_per_changed,
        valid=valid,
        skipped=False,
        skip_reason="",
    )


def evolve_slots(
    model: SourceModel,
    previous_slots: Sequence[int] | None,
    target_count: int,
    churn_fraction: float,
    seed: int,
) -> List[int]:
    if previous_slots is None:
        return draw_slots_from_source(model, target_count, seed)

    rng = random.Random(seed)
    keep_count = max(0, min(target_count, round(target_count * (1.0 - churn_fraction))))
    kept = set(rng.sample(list(previous_slots), min(keep_count, len(previous_slots))))
    fill_count = target_count - len(kept)
    if fill_count <= 0:
        return sorted(kept)
    drawn = draw_slots_from_source(model, fill_count, seed + 7919, exclude=kept)
    return sorted(kept | set(drawn))


def num(value: object) -> float | None:
    if value == "":
        return None
    return float(value)


def avg(values: Iterable[float]) -> float:
    vals = list(values)
    return mean(vals) if vals else 0.0


def sd(values: Iterable[float]) -> float:
    vals = list(values)
    return stdev(vals) if len(vals) >= 2 else 0.0


def summarize_rows(results: Sequence[SnapshotResult]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, int, int, str, str], List[SnapshotResult]] = defaultdict(list)
    for result in results:
        grouped[
            (
                result.dataset,
                result.height,
                result.target_occupied,
                result.source_mode,
                result.coloring_strategy,
            )
        ].append(result)

    rows: List[Dict[str, object]] = []
    for (dataset, height, target_count, mode, strategy), group in sorted(grouped.items()):
        completed = [item for item in group if not item.skipped]
        values = {
            "dataset": dataset,
            "height": height,
            "target_occupied": target_count,
            "source_mode": mode,
            "coloring_strategy": strategy,
            "epochs": len(group),
            "completed_epochs": len(completed),
            "valid_epochs": sum(1 for item in completed if item.valid),
        }
        for field in [
            "actual_occupied",
            "active_nodes",
            "active_width_m",
            "structural_lower_bound",
            "pbc_width",
            "sparse_width",
            "pbc_max_bucket",
            "sparse_max_bucket",
            "width_gain",
            "stored_record_gain",
            "max_bucket_gain",
            "activebalance_ms",
            "total_snapshot_build_ms",
            "peak_memory_mb",
            "changed_fraction_from_previous",
            "jaccard_with_previous",
            "activebalance_ms_per_changed_leaf",
        ]:
            nums = [value for item in completed if (value := num(getattr(item, field))) is not None]
            values[f"{field}_mean"] = avg(nums)
            values[f"{field}_std"] = sd(nums)
        rows.append(values)
    return rows


def fmt_x(value: float) -> str:
    return f"{value:.2f}x"


def fmt_num(value: float) -> str:
    if value >= 1000:
        return f"{value:,.1f}"
    return f"{value:.2f}"


def write_note(path: Path, summary_rows: Sequence[Dict[str, object]], args: argparse.Namespace) -> None:
    lines = [
        "# Deployment-Scale Snapshot Experiment",
        "",
        "This experiment addresses the S&P reviewer risk that the paper only measures small fixed snapshots. It constructs dynamic, real-trace-seeded SMT snapshots, runs SparseTreePIR layout construction at deployment-scale occupied-leaf counts, and records the full snapshot-side cost needed before pairing with the executable backend experiments.",
        "",
        "## Configuration",
        "",
        f"- Workloads: `{args.workloads}`",
        f"- Heights: `{args.heights}`",
        f"- Target occupied leaves: `{args.target_counts}`",
        f"- Epochs per setting: `{args.epochs}`",
        f"- Churn per epoch after epoch 0: `{args.churn_fraction}`",
        f"- Prefix bits preserved for trace bootstrapping: `{args.prefix_bits}`",
        f"- Coloring strategy: `{args.coloring_strategy}`",
        f"- Coloring/refinement rounds: `{args.balance_rounds}`",
        "",
        "## Paper-Facing Summary",
        "",
        "| Dataset | h | occupied | mode | strategy | epochs | width gain | stored-record gain | max-bucket gain | build ms | coloring ms | peak MB |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['dataset']} | {row['height']} | {row['target_occupied']} | {row['source_mode']} | "
            f"{row['coloring_strategy']} | {row['completed_epochs']}/{row['epochs']} | "
            f"{fmt_x(float(row['width_gain_mean']))} | "
            f"{fmt_x(float(row['stored_record_gain_mean']))} | {fmt_x(float(row['max_bucket_gain_mean']))} | "
            f"{fmt_num(float(row['total_snapshot_build_ms_mean']))} | "
            f"{fmt_num(float(row['activebalance_ms_mean']))} | "
            f"{fmt_num(float(row['peak_memory_mb_mean']))} |"
        )

    lines.extend(
        [
            "",
            "## How This Should Be Used",
            "",
            "- Use this table to support the main-text claim that SparseTreePIR remains structurally useful at deployment-scale snapshot sizes.",
            "- Pair it with `real_backend_showcase_repeats_summary.csv` and `end_to_end_paired_comparison.csv`; this script measures snapshot layout construction, not a replacement for the SimplePIR/PIANO backend runs.",
            "- If a setting is skipped, raise `--max-active-nodes` on a larger Linux machine or lower `--target-counts` for a pilot run.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build dynamic deployment-scale SparseTreePIR snapshots from real workload traces. "
            "The output is intended for S&P paper evidence on large snapshots and live epoch churn."
        )
    )
    parser.add_argument(
        "--workloads",
        default="Polygon zkEVM broad,ZKsync Era broad",
        help="Comma-separated workload labels, or all.",
    )
    parser.add_argument("--heights", default="128", help="Comma-separated SMT heights.")
    parser.add_argument("--target-counts", default="1000,10000,100000", help="Comma-separated occupied-leaf counts.")
    parser.add_argument("--epochs", type=int, default=3, help="Dynamic snapshots per setting.")
    parser.add_argument("--churn-fraction", type=float, default=0.05, help="Fraction of leaves replaced per later epoch.")
    parser.add_argument("--prefix-bits", type=int, default=24, help="High-order trace prefix bits to preserve when bootstrapping.")
    parser.add_argument(
        "--coloring-strategy",
        choices=["hybrid", "count_balanced", "count_profile"],
        default="hybrid",
        help="Scalable coloring strategy for the large snapshot. count_profile matches the heavier profile pass.",
    )
    parser.add_argument("--balance-rounds", type=int, default=20, help="Coloring refinement/rebalance rounds.")
    parser.add_argument("--seed-base", type=int, default=410000, help="Base random seed.")
    parser.add_argument(
        "--max-active-nodes",
        type=int,
        default=5_000_000,
        help="Skip coloring if the materialized active proof-node count exceeds this limit.",
    )
    parser.add_argument(
        "--rows-output",
        type=Path,
        default=Path("examples/deployment_scale_snapshot_rows.csv"),
        help="Per-epoch CSV output.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("examples/deployment_scale_snapshot_summary.csv"),
        help="Aggregate CSV output.",
    )
    parser.add_argument(
        "--note",
        type=Path,
        default=Path("notes/deployment_scale_snapshot_experiment_note.md"),
        help="Markdown note output.",
    )
    args = parser.parse_args()

    if args.epochs <= 0:
        raise ValueError("--epochs must be positive")
    if not (0.0 <= args.churn_fraction <= 1.0):
        raise ValueError("--churn-fraction must be in [0, 1]")

    workloads = selected_workloads(args.workloads)
    heights = parse_int_list(args.heights)
    target_counts = parse_int_list(args.target_counts)

    print("=== Deployment-Scale Snapshot Experiment ===", flush=True)
    print(f"workloads={[spec.label for spec in workloads]}", flush=True)
    print(f"heights={heights}", flush=True)
    print(f"target_counts={target_counts}", flush=True)
    print(f"epochs={args.epochs}", flush=True)
    print(f"churn_fraction={args.churn_fraction}", flush=True)
    print(f"prefix_bits={args.prefix_bits}", flush=True)
    print(f"coloring_strategy={args.coloring_strategy}", flush=True)
    print(f"balance_rounds={args.balance_rounds}", flush=True)
    print()

    all_results: List[SnapshotResult] = []
    for spec_index, spec in enumerate(workloads):
        for height in heights:
            model = load_source_model(spec, height=height, prefix_bits=args.prefix_bits)
            for count_index, target_count in enumerate(target_counts):
                previous_slots: List[int] | None = None
                for epoch in range(args.epochs):
                    seed = args.seed_base + spec_index * 100_000 + height * 997 + count_index * 4099 + epoch
                    slots = evolve_slots(
                        model=model,
                        previous_slots=previous_slots,
                        target_count=target_count,
                        churn_fraction=args.churn_fraction,
                        seed=seed,
                    )
                    print(
                        f"dataset={spec.label} h={height} target={target_count} epoch={epoch} slots={len(slots)}",
                        flush=True,
                    )
                    result = run_snapshot(
                        model=model,
                        target_count=target_count,
                        slots=slots,
                        previous_slots=previous_slots,
                        seed=seed,
                        epoch=epoch,
                        coloring_strategy=args.coloring_strategy,
                        balance_rounds=args.balance_rounds,
                        max_active_nodes=args.max_active_nodes,
                    )
                    all_results.append(result)
                    previous_slots = slots
                    gc.collect()
                    print(
                        "  "
                        f"active_nodes={result.active_nodes} m={result.active_width_m} "
                        f"width_gain={result.width_gain:.2f}x max_bucket_gain={result.max_bucket_gain:.2f}x "
                        f"build_ms={result.total_snapshot_build_ms:.1f} skipped={result.skipped}",
                        flush=True,
                    )

    row_dicts = [asdict_result(result) for result in all_results]
    summary_rows = summarize_rows(all_results)
    write_csv(args.rows_output, row_dicts)
    write_csv(args.summary_output, summary_rows)
    write_note(args.note, summary_rows, args)

    print()
    print(f"rows_output={args.rows_output}", flush=True)
    print(f"summary_output={args.summary_output}", flush=True)
    print(f"note={args.note}", flush=True)


if __name__ == "__main__":
    main()
