from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode,
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced,
    structural_max_bucket_lower_bound,
)
from run_lwe_pir_backend_experiment import pruned_treepir_h_indexes
from run_sparse_smt_pir_backend_experiment import build_color_indexes


RECORD_BYTES = 32


@dataclass
class Layout:
    name: str
    private: bool
    width: int
    stored_records: int
    max_bucket: int
    bucket_sizes: List[int]


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


def active_nodes_for_rank(nodes: Sequence[ProofNode], rank: int) -> List[ProofNode]:
    return [node for node in nodes if node.interval_left <= rank <= node.interval_right]


def active_nodes_for_leaf(
    nodes: Sequence[ProofNode], occupied_leaves: Sequence[int], leaf: int
) -> List[ProofNode]:
    rank = occupied_leaves.index(leaf)
    return active_nodes_for_rank(nodes, rank)


def level_bucket_sizes(nodes: Sequence[ProofNode], height: int) -> List[int]:
    sizes = [0] * height
    for node in nodes:
        if 1 <= node.depth <= height:
            sizes[node.depth - 1] += 1
    return sizes


def color_bucket_sizes(indexes: Dict[int, List[Tuple[int, int, int]]], width: int) -> List[int]:
    return [len(indexes.get(color, [])) for color in range(1, width + 1)]


def average_real_slots(nodes: Sequence[ProofNode], occupied: Sequence[int], targets: Sequence[int]) -> float:
    if not targets:
        return 0.0
    return mean(len(active_nodes_for_leaf(nodes, occupied, leaf)) for leaf in targets)


def batch_union_active_nodes(
    nodes: Sequence[ProofNode], occupied: Sequence[int], targets: Sequence[int]
) -> int:
    union = set()
    for leaf in targets:
        for node in active_nodes_for_leaf(nodes, occupied, leaf):
            union.add(node.index)
    return len(union)


def sample_targets(occupied: Sequence[int], seed: int, batch_size: int) -> List[int]:
    if not occupied:
        return []
    start = seed % len(occupied)
    # Deterministic spread through the occupied leaves to avoid choosing one
    # tightly clustered prefix by accident.
    step = max(1, len(occupied) // max(1, batch_size))
    return [occupied[(start + i * step) % len(occupied)] for i in range(min(batch_size, len(occupied)))]


def make_layouts(
    height: int,
    nodes: Sequence[ProofNode],
    color_indexes: Dict[int, List[Tuple[int, int, int]]],
    active_width: int,
) -> List[Layout]:
    perfect_level_sizes = [1 << depth for depth in range(1, height + 1)]
    pruned_sizes = level_bucket_sizes(nodes, height)
    sparse_sizes = color_bucket_sizes(color_indexes, active_width)
    return [
        Layout(
            name="full_coordinate_level_pir",
            private=True,
            width=height,
            stored_records=(1 << (height + 1)) - 2,
            max_bucket=max(perfect_level_sizes) if perfect_level_sizes else 0,
            bucket_sizes=perfect_level_sizes,
        ),
        Layout(
            name="pruned_level_pir_h",
            private=True,
            width=height,
            stored_records=len(nodes),
            max_bucket=max(pruned_sizes) if pruned_sizes else 0,
            bucket_sizes=pruned_sizes,
        ),
        Layout(
            name="sparsetreepir_batch_pir",
            private=True,
            width=active_width,
            stored_records=len(nodes),
            max_bucket=max(sparse_sizes) if sparse_sizes else 0,
            bucket_sizes=sparse_sizes,
        ),
    ]


def dummy_rate_for_layout(layout: Layout, avg_real_slots: float) -> float:
    if layout.name == "full_coordinate_level_pir":
        # The naive full-coordinate baseline retrieves one complete proof slot
        # per level, including default coordinates, so it has no dummy slots.
        return 0.0
    if layout.width <= 0:
        return 0.0
    return max(0.0, (layout.width - avg_real_slots) / layout.width)


def run_trial(
    height: int,
    sparsity: float,
    seed: int,
    batch_sizes: Sequence[int],
    refine_rounds: int,
) -> List[Dict[str, object]]:
    occupied = generate_occupied_leaves(height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)

    nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(nodes)
    active_width = max_chain_length(roots)
    lower_bound = structural_max_bucket_lower_bound(roots, len(nodes), active_width)

    profile_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    profile_roots = build_interval_forest(profile_nodes)
    best_count_profile_balanced(
        proof_nodes=profile_nodes,
        roots=profile_roots,
        num_colors=active_width,
        refine_rounds=refine_rounds,
    )
    color_indexes = build_color_indexes(profile_nodes, active_width)
    layouts = make_layouts(height, profile_nodes, color_indexes, active_width)

    rows: List[Dict[str, object]] = []
    for batch_size in batch_sizes:
        targets = sample_targets(occupied, seed + batch_size * 31, batch_size)
        avg_slots = average_real_slots(profile_nodes, occupied, targets)
        union_count = batch_union_active_nodes(profile_nodes, occupied, targets)
        ordinary_separate_bytes = int(round(avg_slots * len(targets) * RECORD_BYTES))
        ordinary_batch_bytes = union_count * RECORD_BYTES

        rows.append(
            {
                "height": height,
                "empty_pct": sparsity * 100.0,
                "seed": seed,
                "occupied_leaves": len(occupied),
                "active_records": len(profile_nodes),
                "active_width_m": active_width,
                "structural_lower_bound": lower_bound,
                "target_batch": len(targets),
                "scheme": "ordinary_smt_batch_serving",
                "private": False,
                "width": 0,
                "stored_records": len(profile_nodes),
                "max_bucket": 0,
                "sum_bucket_records": 0,
                "avg_real_slots_per_target": avg_slots,
                "dummy_rate": 0.0,
                "ordinary_separate_bytes": ordinary_separate_bytes,
                "ordinary_batch_dedup_bytes": ordinary_batch_bytes,
                "private_workload_record_proxy": 0,
                "notes": "Non-private semantic lower bound; server knows all targets.",
            }
        )

        for layout in layouts:
            sum_bucket_records = sum(layout.bucket_sizes)
            rows.append(
                {
                    "height": height,
                    "empty_pct": sparsity * 100.0,
                    "seed": seed,
                    "occupied_leaves": len(occupied),
                    "active_records": len(profile_nodes),
                    "active_width_m": active_width,
                    "structural_lower_bound": lower_bound,
                    "target_batch": len(targets),
                    "scheme": layout.name,
                    "private": layout.private,
                    "width": layout.width,
                    "stored_records": layout.stored_records,
                    "max_bucket": layout.max_bucket,
                    "sum_bucket_records": sum_bucket_records,
                    "avg_real_slots_per_target": avg_slots,
                    "dummy_rate": dummy_rate_for_layout(layout, avg_slots),
                    "ordinary_separate_bytes": ordinary_separate_bytes,
                    "ordinary_batch_dedup_bytes": ordinary_batch_bytes,
                    "private_workload_record_proxy": len(targets) * sum_bucket_records,
                    "notes": "Private PIR workload proxy; constants depend on backend packing.",
                }
            )
    return rows


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float, digits: int = 1) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.{digits}f}"


def summarize_note(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use the largest realized batch size per setting. This matters when a
    # small SMT snapshot has fewer occupied leaves than the requested batch.
    by_setting: Dict[Tuple[int, float], List[Dict[str, object]]] = {}
    for row in rows:
        key = (int(row["height"]), float(row["empty_pct"]))
        by_setting.setdefault(key, []).append(row)

    groups: Dict[Tuple[int, float], Dict[str, Dict[str, object]]] = {}
    setting_batch: Dict[Tuple[int, float], int] = {}
    for key, setting_rows in by_setting.items():
        max_batch = max(int(row["target_batch"]) for row in setting_rows)
        setting_batch[key] = max_batch
        for row in setting_rows:
            if int(row["target_batch"]) == max_batch:
                groups.setdefault(key, {})[str(row["scheme"])] = row

    lines: List[str] = []
    lines.append("# Ordinary SMT batch serving vs full-proof PIR vs SparseTreePIR\n")
    lines.append(
        "This experiment compares three proof-retrieval views on the same SMT snapshots. "
        "`ordinary_smt_batch_serving` is the non-private lower bound: the server knows "
        "the target leaves and can return a de-duplicated batch of active sibling digests. "
        "`full_coordinate_level_pir` is the naive private complete-proof baseline: query "
        "one full SMT coordinate database per proof level. `pruned_level_pir_h` stores only "
        "active nodes but still keeps height-`h` proof slots. `sparsetreepir_batch_pir` is "
        "our active-interval batch PIR organization."
    )
    lines.append("")
    lines.append(
        "The table below reports the largest realized target batch for each setting "
        "(up to the requested maximum batch size).\n"
    )
    lines.append(
        "| h | Empty | B | Occupied | Active N | m | Ordinary batch bytes | Full-coordinate width/max bucket | Pruned-h width/max bucket | SparseTreePIR width/max bucket |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for (height, empty), schemes in sorted(groups.items()):
        ordinary = schemes["ordinary_smt_batch_serving"]
        full = schemes["full_coordinate_level_pir"]
        pruned = schemes["pruned_level_pir_h"]
        sparse = schemes["sparsetreepir_batch_pir"]
        lines.append(
            "| {h} | {empty:.3f}% | {batch} | {occ} | {active} | {m} | {plain} | {fw}/{fb} | {pw}/{pb} | {sw}/{sb} |".format(
                h=height,
                empty=empty,
                batch=setting_batch[(height, empty)],
                occ=fmt(float(ordinary["occupied_leaves"]), 0),
                active=fmt(float(ordinary["active_records"]), 0),
                m=fmt(float(ordinary["active_width_m"]), 0),
                plain=fmt(float(ordinary["ordinary_batch_dedup_bytes"]), 0),
                fw=fmt(float(full["width"]), 0),
                fb=fmt(float(full["max_bucket"]), 0),
                pw=fmt(float(pruned["width"]), 0),
                pb=fmt(float(pruned["max_bucket"]), 0),
                sw=fmt(float(sparse["width"]), 0),
                sb=fmt(float(sparse["max_bucket"]), 0),
            )
        )
    lines.append("")

    ratios = []
    pruned_ratios = []
    for schemes in groups.values():
        sparse = schemes["sparsetreepir_batch_pir"]
        full = schemes["full_coordinate_level_pir"]
        pruned = schemes["pruned_level_pir_h"]
        ratios.append(float(full["max_bucket"]) / max(1.0, float(sparse["max_bucket"])))
        pruned_ratios.append(float(pruned["max_bucket"]) / max(1.0, float(sparse["max_bucket"])))
    lines.append("## Main observations\n")
    lines.append(
        f"- Ordinary SMT batch proof serving is dramatically smaller in bytes, but it is not private: the server receives the target set."
    )
    lines.append(
        f"- Naive full-coordinate complete-proof PIR is dominated by the full SMT coordinate space. Its max level database is {fmt(min(ratios))}x to {fmt(max(ratios))}x larger than SparseTreePIR's largest color store in these settings."
    )
    lines.append(
        f"- Pruned level-wise PIR removes default records but remains height-pinned. Its largest level bucket is {fmt(min(pruned_ratios))}x to {fmt(max(pruned_ratios))}x larger than SparseTreePIR's largest color store."
    )
    lines.append(
        "- SparseTreePIR does not beat ordinary non-private serving; it reduces the private workload once target privacy is required."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare ordinary SMT batch proof serving, naive full-proof level-wise PIR, "
            "pruned level-wise PIR, and SparseTreePIR batch PIR on the same snapshots."
        )
    )
    parser.add_argument("--heights", default="16,20,24")
    parser.add_argument("--sparsities", default="0.9995,0.99975")
    parser.add_argument("--seeds", default="120000")
    parser.add_argument("--batch-sizes", default="1,8,32")
    parser.add_argument("--refine-rounds", type=int, default=60)
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("examples/smt_batch_proof_vs_batch_pir_results.csv"),
    )
    parser.add_argument(
        "--out-note",
        type=Path,
        default=Path("notes/smt_batch_proof_vs_batch_pir_note.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    heights = parse_int_list(args.heights)
    sparsities = parse_float_list(args.sparsities)
    seeds = parse_int_list(args.seeds)
    batch_sizes = parse_int_list(args.batch_sizes)

    rows: List[Dict[str, object]] = []
    for height in heights:
        for sparsity in sparsities:
            for seed in seeds:
                rows.extend(run_trial(height, sparsity, seed, batch_sizes, args.refine_rounds))

    write_csv(args.out_csv, rows)
    summarize_note(args.out_note, rows)
    print(f"Wrote {args.out_csv} ({len(rows)} rows)")
    print(f"Wrote {args.out_note}")


if __name__ == "__main__":
    main()
