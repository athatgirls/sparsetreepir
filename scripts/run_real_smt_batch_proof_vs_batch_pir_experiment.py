from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode,
    build_full_proof_nodes,
    build_interval_forest,
    max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced,
    structural_max_bucket_lower_bound,
)
from run_real_smt_workload_experiment import iter_keys, key_to_slot, slots_to_heap_leaves
from run_smt_batch_proof_vs_batch_pir_experiment import (
    active_nodes_for_leaf,
    average_real_slots,
    batch_union_active_nodes,
    color_bucket_sizes,
    dummy_rate_for_layout,
    level_bucket_sizes,
    sample_targets,
)
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


def read_occupied_leaves(
    path: Path,
    height: int,
    key_mode: str,
    column: Optional[str],
    json_field: Optional[str],
    limit: Optional[int],
) -> Tuple[int, int, int, List[int]]:
    raw_keys = list(iter_keys(path=path, column=column, json_field=json_field, limit=limit))
    if not raw_keys:
        raise ValueError(f"No keys were extracted from {path}.")
    unique_keys = sorted(set(raw_keys))
    slots = [key_to_slot(value, height=height, key_mode=key_mode) for value in unique_keys]
    occupied = slots_to_heap_leaves(slots, height)
    return len(raw_keys), len(unique_keys), len(unique_keys) - len(occupied), occupied


def make_layouts(
    height: int,
    nodes: Sequence[ProofNode],
    active_width: int,
    color_indexes: Dict[int, List[Tuple[int, int, int]]],
) -> List[Layout]:
    pruned_sizes = level_bucket_sizes(nodes, height)
    sparse_sizes = color_bucket_sizes(color_indexes, active_width)
    # Perfectized TreePIR is an accounting baseline for high-height real SMTs:
    # TreePIR's artifact expects a materialized perfect-tree input, which is
    # infeasible at h=128 or h=256. Its fair resource shape has h color stores
    # over all non-root perfect-tree nodes, approximately balanced.
    full_records = (1 << (height + 1)) - 2
    perfectized_treepir_bucket = (full_records + height - 1) // height
    return [
        Layout(
            name="perfectized_treepir",
            private=True,
            width=height,
            stored_records=full_records,
            max_bucket=perfectized_treepir_bucket,
            bucket_sizes=[perfectized_treepir_bucket] * height,
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


def run_workload_setting(
    *,
    input_path: Path,
    label: str,
    height: int,
    key_mode: str,
    column: Optional[str],
    json_field: Optional[str],
    limit: Optional[int],
    batch_sizes: Sequence[int],
    refine_rounds: int,
) -> List[Dict[str, object]]:
    input_records, unique_keys, slot_collisions, occupied = read_occupied_leaves(
        path=input_path,
        height=height,
        key_mode=key_mode,
        column=column,
        json_field=json_field,
        limit=limit,
    )

    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(nodes)
    active_width = max_chain_length(roots)
    lower_bound = structural_max_bucket_lower_bound(roots, len(nodes), active_width)

    best_count_profile_balanced(
        proof_nodes=nodes,
        roots=roots,
        num_colors=active_width,
        refine_rounds=refine_rounds,
    )
    color_indexes = build_color_indexes(nodes, active_width)
    layouts = make_layouts(height, nodes, active_width, color_indexes)

    rows: List[Dict[str, object]] = []
    for batch_size in batch_sizes:
        targets = sample_targets(occupied, seed=height * 131 + batch_size * 17, batch_size=batch_size)
        avg_slots = average_real_slots(nodes, occupied, targets)
        union_count = batch_union_active_nodes(nodes, occupied, targets)
        ordinary_separate_bytes = int(round(avg_slots * len(targets) * RECORD_BYTES))
        ordinary_batch_bytes = union_count * RECORD_BYTES

        rows.append(
            {
                "dataset": label,
                "source_path": str(input_path),
                "height": height,
                "key_mode": key_mode,
                "input_records": input_records,
                "unique_keys": unique_keys,
                "occupied_leaves": len(occupied),
                "slot_collisions": slot_collisions,
                "active_records": len(nodes),
                "active_width_m": active_width,
                "structural_lower_bound": lower_bound,
                "target_batch": len(targets),
                "scheme": "ordinary_smt_batch_serving",
                "private": False,
                "width": 0,
                "stored_records": len(nodes),
                "max_bucket": 0,
                "max_bucket_log2": "",
                "sum_bucket_records": 0,
                "avg_real_slots_per_target": avg_slots,
                "dummy_rate": 0.0,
                "ordinary_separate_bytes": ordinary_separate_bytes,
                "ordinary_batch_dedup_bytes": ordinary_batch_bytes,
                "private_workload_record_proxy": 0,
                "notes": "Real-data non-private SMT proof serving; server knows all batch targets.",
            }
        )

        for layout in layouts:
            sum_bucket_records = sum(layout.bucket_sizes)
            rows.append(
                {
                    "dataset": label,
                    "source_path": str(input_path),
                    "height": height,
                    "key_mode": key_mode,
                    "input_records": input_records,
                    "unique_keys": unique_keys,
                    "occupied_leaves": len(occupied),
                    "slot_collisions": slot_collisions,
                    "active_records": len(nodes),
                    "active_width_m": active_width,
                    "structural_lower_bound": lower_bound,
                    "target_batch": len(targets),
                    "scheme": layout.name,
                    "private": layout.private,
                    "width": layout.width,
                    "stored_records": layout.stored_records,
                    "max_bucket": layout.max_bucket,
                    "max_bucket_log2": (
                        f"{math.log2(layout.max_bucket):.2f}"
                        if layout.name == "perfectized_treepir" and layout.max_bucket > 0
                        else ""
                    ),
                    "sum_bucket_records": sum_bucket_records,
                    "avg_real_slots_per_target": avg_slots,
                    "dummy_rate": dummy_rate_for_layout(layout, avg_slots),
                    "ordinary_separate_bytes": ordinary_separate_bytes,
                    "ordinary_batch_dedup_bytes": ordinary_batch_bytes,
                    "private_workload_record_proxy": len(targets) * sum_bucket_records,
                    "notes": "Real-data private PIR workload proxy; backend constants depend on packing.",
                }
            )
    return rows


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt_number(value: object, digits: int = 1) -> str:
    if isinstance(value, str):
        return value
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}"
    return f"{number:,.{digits}f}"


def fmt_perfectized_treepir_bucket(row: Dict[str, object]) -> str:
    log_value = row.get("max_bucket_log2", "")
    if log_value == "":
        return fmt_number(row["max_bucket"], 0)
    return rf"$\approx 2^{{{float(log_value):.1f}}}$"


def summarize_note(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    groups: Dict[Tuple[str, int], Dict[str, Dict[str, object]]] = {}
    max_batch_by_group: Dict[Tuple[str, int], int] = {}
    for row in rows:
        key = (str(row["dataset"]), int(row["height"]))
        max_batch_by_group[key] = max(max_batch_by_group.get(key, 0), int(row["target_batch"]))
    for row in rows:
        key = (str(row["dataset"]), int(row["height"]))
        if int(row["target_batch"]) == max_batch_by_group[key]:
            groups.setdefault(key, {})[str(row["scheme"])] = row

    lines: List[str] = []
    lines.append("# Real SMT workload: ordinary proof serving vs private proof retrieval\n")
    lines.append(
        "This experiment re-runs the SMT proof-serving comparison on real rollup-derived "
        "workloads instead of synthetic random leaves. The ordinary SMT row is the "
        "non-private lower bound: the server knows the batch targets and can return a "
        "de-duplicated set of real sibling digests. The three PIR rows hide the target "
        "set but expose different database shapes. The TreePIR row is the "
        "perfectized TreePIR accounting baseline: applying TreePIR faithfully "
        "requires completing the SMT to a perfect height-h tree first."
    )
    lines.append("")
    lines.append(
        "| Dataset | h | B | Keys | Active N | m | Ordinary batch bytes | Perfectized TreePIR width/max bucket | Pruned-h width/max bucket | SparseTreePIR width/max bucket |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for (dataset, height), schemes in sorted(groups.items()):
        ordinary = schemes["ordinary_smt_batch_serving"]
        full = schemes["perfectized_treepir"]
        pruned = schemes["pruned_level_pir_h"]
        sparse = schemes["sparsetreepir_batch_pir"]
        lines.append(
            "| {dataset} | {height} | {batch} | {keys} | {active} | {m} | {plain} | {fw}/{fb} | {pw}/{pb} | {sw}/{sb} |".format(
                dataset=dataset,
                height=height,
                batch=max_batch_by_group[(dataset, height)],
                keys=fmt_number(ordinary["unique_keys"], 0),
                active=fmt_number(ordinary["active_records"], 0),
                m=fmt_number(ordinary["active_width_m"], 0),
                plain=fmt_number(ordinary["ordinary_batch_dedup_bytes"], 0),
                fw=fmt_number(full["width"], 0),
                fb=fmt_perfectized_treepir_bucket(full),
                pw=fmt_number(pruned["width"], 0),
                pb=fmt_number(pruned["max_bucket"], 0),
                sw=fmt_number(sparse["width"], 0),
                sb=fmt_number(sparse["max_bucket"], 0),
            )
        )

    lines.append("")
    lines.append("## Interpretation\n")
    for (dataset, height), schemes in sorted(groups.items()):
        ordinary = schemes["ordinary_smt_batch_serving"]
        pruned = schemes["pruned_level_pir_h"]
        sparse = schemes["sparsetreepir_batch_pir"]
        pruned_ratio = float(pruned["max_bucket"]) / max(1.0, float(sparse["max_bucket"]))
        lines.append(
            f"- {dataset}, h={height}: ordinary batch proof serving returns "
            f"{fmt_number(ordinary['ordinary_batch_dedup_bytes'], 0)} bytes for the sampled batch, "
            f"but reveals the targets. SparseTreePIR uses width {fmt_number(sparse['width'], 0)} "
            f"instead of the height-pinned width {height}; its largest color store has "
            f"{fmt_number(sparse['max_bucket'], 0)} records, versus "
            f"{fmt_number(pruned['max_bucket'], 0)} for pruned level-wise PIR "
            f"({pruned_ratio:.2f}x larger)."
        )
    lines.append("")
    lines.append(
        "The TreePIR baseline is symbolic at heights 128 and 256 because the official "
        "TreePIR artifact operates on a perfect-tree input. Perfectizing these real SMT "
        "workloads would create $2^{h+1}-2$ private records before coloring, so the "
        "reported TreePIR bucket is an accounting value rather than a materialized run."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare ordinary SMT batch proof serving, full-coordinate PIR, pruned height-pinned PIR, "
            "and SparseTreePIR on real SMT-style key workloads."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--label", type=str, required=True)
    parser.add_argument("--heights", default="128,256")
    parser.add_argument("--key-mode", choices=["sha256", "hex-prefix", "hex-suffix"], default="sha256")
    parser.add_argument("--column", type=str, default=None)
    parser.add_argument("--json-field", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-sizes", default="1,32,128")
    parser.add_argument("--refine-rounds", type=int, default=20)
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("examples/real_smt_batch_proof_vs_batch_pir_results.csv"),
    )
    parser.add_argument(
        "--out-note",
        type=Path,
        default=Path("notes/real_smt_batch_proof_vs_batch_pir_note.md"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    heights = parse_int_list(args.heights)
    batch_sizes = parse_int_list(args.batch_sizes)
    rows: List[Dict[str, object]] = []
    for height in heights:
        rows.extend(
            run_workload_setting(
                input_path=args.input,
                label=args.label,
                height=height,
                key_mode=args.key_mode,
                column=args.column,
                json_field=args.json_field,
                limit=args.limit,
                batch_sizes=batch_sizes,
                refine_rounds=args.refine_rounds,
            )
        )
    write_csv(args.out_csv, rows)
    summarize_note(args.out_note, rows)
    print(f"Wrote {args.out_csv} ({len(rows)} rows)")
    print(f"Wrote {args.out_note}")


if __name__ == "__main__":
    main()
