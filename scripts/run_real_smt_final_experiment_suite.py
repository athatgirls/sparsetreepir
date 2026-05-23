from __future__ import annotations

import argparse
import csv
import math
import os
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
    max_chain_length,
    verify_coloring,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced,
    count_loads_for_nodes,
    first_fit_coloring,
    structural_max_bucket_lower_bound,
    summarize_scheme,
)
from run_real_smt_batch_proof_vs_batch_pir_experiment import (
    average_real_slots,
    batch_union_active_nodes,
    sample_targets,
)
from run_real_smt_workload_experiment import active_path_lengths, iter_keys, key_to_slot, slots_to_heap_leaves
from run_simplepir_full_backend_experiment import (
    SchemeLayout,
    build_pbc_active_indexes,
    ensure_subst_drive,
    run_simplepir_runner,
    simplepir_environment,
    write_flat_manifest,
    write_manifest,
)
from run_sparse_smt_pir_backend_experiment import build_color_indexes, color_proof_nodes


RECORD_BYTES = 32
METADATA_BYTES_PER_ACTIVE = 24


@dataclass(frozen=True)
class WorkloadSpec:
    label: str
    path: Path
    column: str
    key_mode: str
    limit: Optional[int] = None
    kind: str = "deployment-trace"


@dataclass
class InstanceArtifacts:
    spec: WorkloadSpec
    height: int
    input_records: int
    unique_keys: int
    occupied_leaves: List[int]
    slot_collisions: int
    active_nodes: List[ProofNode]
    roots: List[ProofNode]
    active_width: int
    structural_lower_bound: int
    first_fit_loads: List[int]
    hybrid_loads: List[int]
    sparse_loads: List[int]
    color_indexes: Dict[int, List[Tuple[int, int, int]]]
    profile_runtime_ms: float
    valid: bool


DEFAULT_WORKLOADS = [
    WorkloadSpec(
        label="Polygon zkEVM recent",
        path=Path("datasets/polygon_zkevm_account_leaf_workload.csv"),
        column="key",
        key_mode="sha256",
    ),
    WorkloadSpec(
        label="Polygon zkEVM multi-window",
        path=Path("datasets/polygon_zkevm_account_leaf_workload_multiwindow.csv"),
        column="key",
        key_mode="sha256",
    ),
    WorkloadSpec(
        label="Polygon zkEVM broad",
        path=Path("datasets/polygon_zkevm_account_leaf_workload_broad_multiwindow.csv"),
        column="key",
        key_mode="sha256",
    ),
    WorkloadSpec(
        label="ZKsync Era sample",
        path=Path("datasets/zksync_era_account_leaf_workload_sample.csv"),
        column="key",
        key_mode="sha256",
    ),
    WorkloadSpec(
        label="ZKsync Era broad",
        path=Path("datasets/zksync_era_account_leaf_workload_broad_sample.csv"),
        column="key",
        key_mode="sha256",
    ),
    WorkloadSpec(
        label="FuelLabs SMT test vectors",
        path=Path("datasets/fuel_smt_test_workload.csv"),
        column="key",
        key_mode="hex-prefix",
        kind="smt-test-vector",
    ),
]


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def selected_workloads(raw: str) -> List[WorkloadSpec]:
    if raw.strip().lower() == "all":
        return DEFAULT_WORKLOADS
    wanted = {item.strip().lower() for item in raw.split(",") if item.strip()}
    selected = [spec for spec in DEFAULT_WORKLOADS if spec.label.lower() in wanted]
    missing = wanted - {spec.label.lower() for spec in selected}
    if missing:
        known = ", ".join(spec.label for spec in DEFAULT_WORKLOADS)
        raise ValueError(f"unknown workload label(s): {sorted(missing)}. Known labels: {known}")
    return selected


def read_occupied_leaves(spec: WorkloadSpec, height: int) -> Tuple[int, int, int, List[int]]:
    raw_keys = list(iter_keys(path=spec.path, column=spec.column, json_field=None, limit=spec.limit))
    if not raw_keys:
        raise ValueError(f"No keys were extracted from {spec.path}.")
    unique_keys = sorted(set(raw_keys))
    slots = [key_to_slot(value, height=height, key_mode=spec.key_mode) for value in unique_keys]
    occupied = slots_to_heap_leaves(slots, height)
    return len(raw_keys), len(unique_keys), len(unique_keys) - len(occupied), occupied


def clone_active_structure(height: int, occupied: Sequence[int]) -> Tuple[List[ProofNode], List[ProofNode]]:
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(nodes)
    return nodes, roots


def build_instance(spec: WorkloadSpec, height: int, hybrid_rounds: int, balance_rounds: int) -> InstanceArtifacts:
    input_records, unique_keys, slot_collisions, occupied = read_occupied_leaves(spec, height)

    base_nodes, base_roots = clone_active_structure(height, occupied)
    active_width = max_chain_length(base_roots)
    lower_bound = structural_max_bucket_lower_bound(base_roots, len(base_nodes), active_width)

    ff_nodes, ff_roots = clone_active_structure(height, occupied)
    if active_width > 0:
        first_fit_coloring(ff_roots, active_width)
    first_fit_loads = count_loads_for_nodes(ff_nodes, active_width)

    hybrid_nodes, hybrid_roots = clone_active_structure(height, occupied)
    if active_width > 0:
        color_proof_nodes(
            proof_nodes=hybrid_nodes,
            roots=hybrid_roots,
            num_colors=active_width,
            strategy="hybrid",
            rebalance_rounds=hybrid_rounds,
        )
    hybrid_loads = count_loads_for_nodes(hybrid_nodes, active_width)

    sparse_nodes, sparse_roots = clone_active_structure(height, occupied)
    t0 = perf_counter()
    if active_width > 0:
        best_count_profile_balanced(
            proof_nodes=sparse_nodes,
            roots=sparse_roots,
            num_colors=active_width,
            refine_rounds=balance_rounds,
        )
    t1 = perf_counter()
    sparse_loads = count_loads_for_nodes(sparse_nodes, active_width)
    color_indexes = build_color_indexes(sparse_nodes, active_width) if active_width > 0 else {}
    valid, _ = verify_coloring(sparse_roots, occupied)

    return InstanceArtifacts(
        spec=spec,
        height=height,
        input_records=input_records,
        unique_keys=unique_keys,
        occupied_leaves=occupied,
        slot_collisions=slot_collisions,
        active_nodes=sparse_nodes,
        roots=sparse_roots,
        active_width=active_width,
        structural_lower_bound=lower_bound,
        first_fit_loads=first_fit_loads,
        hybrid_loads=hybrid_loads,
        sparse_loads=sparse_loads,
        color_indexes=color_indexes,
        profile_runtime_ms=(t1 - t0) * 1000.0,
        valid=valid,
    )


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b if b else 0


def full_tree_record_count(height: int) -> int:
    return (1 << (height + 1)) - 2


def pbc_width(active_width: int) -> int:
    return max(1, math.ceil(1.5 * active_width))


def scheme_layout_rows(instance: InstanceArtifacts) -> List[Dict[str, object]]:
    active_count = len(instance.active_nodes)
    full_records = full_tree_record_count(instance.height)
    pbc_w = pbc_width(instance.active_width)
    pbc_stored = 3 * active_count
    first_fit_max = max(instance.first_fit_loads) if instance.first_fit_loads else 0
    hybrid_max = max(instance.hybrid_loads) if instance.hybrid_loads else 0
    sparse_max = max(instance.sparse_loads) if instance.sparse_loads else 0
    avg_path_lengths = active_path_lengths(instance.active_nodes, len(instance.occupied_leaves))
    avg_active_path = mean(avg_path_lengths) if avg_path_lengths else 0.0
    dummy_fraction = (
        mean((instance.active_width - value) / instance.active_width for value in avg_path_lengths)
        if instance.active_width > 0 and avg_path_lengths
        else 0.0
    )

    common = {
        "dataset": instance.spec.label,
        "dataset_kind": instance.spec.kind,
        "source_path": str(instance.spec.path),
        "height": instance.height,
        "key_mode": instance.spec.key_mode,
        "input_records": instance.input_records,
        "unique_keys": instance.unique_keys,
        "occupied_leaves": len(instance.occupied_leaves),
        "slot_collisions": instance.slot_collisions,
        "active_records": active_count,
        "active_width_m": instance.active_width,
        "avg_active_path": avg_active_path,
        "dummy_fraction": dummy_fraction,
        "structural_lower_bound": instance.structural_lower_bound,
        "metadata_kb": active_count * METADATA_BYTES_PER_ACTIVE / 1024.0,
        "digest_payload_kb": active_count * RECORD_BYTES / 1024.0,
        "profile_runtime_ms": instance.profile_runtime_ms,
        "valid": instance.valid,
    }

    rows = [
        {
            **common,
            "scheme": "plain_smt_proof_serving",
            "private": False,
            "width": 0,
            "stored_records": active_count,
            "replication": 1.0,
            "max_bucket": 0,
            "sum_bucket_records": 0,
            "max_bucket_log2": "",
            "notes": "Non-private reference: server receives the target and returns ordinary SMT sibling digests.",
        },
        {
            **common,
            "scheme": "perfectized_treepir",
            "private": True,
            "width": instance.height,
            "stored_records": full_records,
            "replication": 1.0,
            "max_bucket": ceil_div(full_records, instance.height),
            "sum_bucket_records": full_records,
            "max_bucket_log2": f"{math.log2(ceil_div(full_records, instance.height)):.3f}",
            "notes": "Accounting baseline: literal TreePIR-style perfect-tree object before SMT active compaction.",
        },
        {
            **common,
            "scheme": "pbc_smt_active",
            "private": True,
            "width": pbc_w,
            "stored_records": pbc_stored,
            "replication": 3.0,
            "max_bucket": ceil_div(pbc_stored, pbc_w),
            "sum_bucket_records": pbc_stored,
            "max_bucket_log2": "",
            "notes": "PBC-style generic batch route over real SMT active proof records: 3 replicated copies over about 1.5m buckets.",
        },
        {
            **common,
            "scheme": "flat_active_pir",
            "private": True,
            "width": instance.active_width,
            "stored_records": active_count,
            "replication": 1.0,
            "max_bucket": active_count,
            "sum_bucket_records": active_count * instance.active_width,
            "max_bucket_log2": "",
            "notes": "Ablation: all active records in one global PIR database, queried m times.",
        },
        {
            **common,
            "scheme": "first_fit_active_coloring",
            "private": True,
            "width": instance.active_width,
            "stored_records": active_count,
            "replication": 1.0,
            "max_bucket": first_fit_max,
            "sum_bucket_records": active_count,
            "max_bucket_log2": "",
            "notes": "Correct exact-width active coloring without load refinement.",
        },
        {
            **common,
            "scheme": "hybrid_active_coloring",
            "private": True,
            "width": instance.active_width,
            "stored_records": active_count,
            "replication": 1.0,
            "max_bucket": hybrid_max,
            "sum_bucket_records": active_count,
            "max_bucket_log2": "",
            "notes": "Prior node-local balancing baseline on the active interval forest.",
        },
        {
            **common,
            "scheme": "sparsetreepir_activebalance",
            "private": True,
            "width": instance.active_width,
            "stored_records": active_count,
            "replication": 1.0,
            "max_bucket": sparse_max,
            "sum_bucket_records": active_count,
            "max_bucket_log2": "",
            "notes": "SparseTreePIR direct active-interval organization with subtree-load balancing.",
        },
    ]
    return rows


def proof_batch_rows(instance: InstanceArtifacts, batch_sizes: Sequence[int]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for batch_size in batch_sizes:
        targets = sample_targets(
            instance.occupied_leaves,
            seed=instance.height * 131 + batch_size * 17 + len(instance.occupied_leaves),
            batch_size=batch_size,
        )
        avg_slots = average_real_slots(instance.active_nodes, instance.occupied_leaves, targets)
        union_count = batch_union_active_nodes(instance.active_nodes, instance.occupied_leaves, targets)
        ordinary_separate = int(round(avg_slots * len(targets) * RECORD_BYTES))
        ordinary_dedup = union_count * RECORD_BYTES
        rows.append(
            {
                "dataset": instance.spec.label,
                "height": instance.height,
                "target_batch": len(targets),
                "unique_keys": instance.unique_keys,
                "active_records": len(instance.active_nodes),
                "active_width_m": instance.active_width,
                "avg_real_slots_per_target": avg_slots,
                "ordinary_separate_bytes": ordinary_separate,
                "ordinary_batch_dedup_bytes": ordinary_dedup,
                "plain_payload_vs_single_target": (
                    ordinary_dedup / max(RECORD_BYTES, avg_slots * RECORD_BYTES)
                    if avg_slots > 0
                    else 0.0
                ),
                "notes": "Non-private ordinary SMT batch proof serving over real target samples; server knows targets.",
            }
        )
    return rows


def backend_instances(workloads: Sequence[WorkloadSpec], heights: Sequence[int], backend_labels: str) -> List[Tuple[WorkloadSpec, int]]:
    if backend_labels.strip().lower() == "none":
        return []
    if backend_labels.strip().lower() == "all":
        return [(spec, heights[0]) for spec in workloads]
    wanted = {item.strip().lower() for item in backend_labels.split(",") if item.strip()}
    selected: List[Tuple[WorkloadSpec, int]] = []
    for spec in workloads:
        if spec.label.lower() in wanted:
            selected.append((spec, heights[0]))
    missing = wanted - {spec.label.lower() for spec, _ in selected}
    if missing:
        known = ", ".join(spec.label for spec in workloads)
        raise ValueError(f"unknown backend workload label(s): {sorted(missing)}. Known labels: {known}")
    return selected


def simplepir_rows_for_instance(
    instance: InstanceArtifacts,
    *,
    query_samples: int,
    seed: int,
    layout_dir: Path,
    workspace: Path,
    workspace_drive: Path,
    simplepir_root: Path,
    go_exe: Path,
    env: Dict[str, str],
    timeout: int,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    sampled = [
        instance.occupied_leaves[(seed + idx) % len(instance.occupied_leaves)]
        for idx in range(min(query_samples, len(instance.occupied_leaves)))
    ]
    flat_entries = sorted((node.interval_left, node.interval_right, node.index) for node in instance.active_nodes)
    base_dir = layout_dir / (
        instance.spec.label.lower().replace(" ", "_").replace("/", "_")
        + f"_h{instance.height}"
    )

    flat_manifest = write_flat_manifest(
        entries=flat_entries,
        height=instance.height,
        active_nodes=len(instance.active_nodes),
        exact_width=instance.active_width,
        occupied=instance.occupied_leaves,
        sampled_leaves=sampled,
        seed=seed,
        output_dir=base_dir / "flat_active_pir",
    )
    flat_result = run_simplepir_runner(
        manifest_path=flat_manifest,
        workspace=workspace,
        workspace_drive=workspace_drive,
        simplepir_root=simplepir_root,
        go_exe=go_exe,
        env=env,
        timeout=timeout,
    )
    rows.append(flatten_simplepir_result(instance, "flat_active_pir", flat_result))

    pbc_indexes = build_pbc_active_indexes(len(instance.active_nodes), instance.active_width)
    pbc_layout = SchemeLayout(
        name="pbc_smt_active",
        indexes=pbc_indexes,
        width=pbc_width(instance.active_width),
        stored_nodes=3 * len(instance.active_nodes),
        lower_bound=0,
    )
    sparse_layout = SchemeLayout(
        name="sparsetreepir_activebalance",
        indexes=instance.color_indexes,
        width=instance.active_width,
        stored_nodes=len(instance.active_nodes),
        lower_bound=instance.structural_lower_bound,
    )
    for layout in [pbc_layout, sparse_layout]:
        manifest = write_manifest(
            layout=layout,
            height=instance.height,
            active_nodes=len(instance.active_nodes),
            occupied=instance.occupied_leaves,
            sampled_leaves=sampled,
            seed=seed,
            output_dir=base_dir / layout.name,
        )
        result = run_simplepir_runner(
            manifest_path=manifest,
            workspace=workspace,
            workspace_drive=workspace_drive,
            simplepir_root=simplepir_root,
            go_exe=go_exe,
            env=env,
            timeout=timeout,
        )
        rows.append(flatten_simplepir_result(instance, layout.name, result))
    return rows


def flatten_simplepir_result(instance: InstanceArtifacts, scheme: str, result: Dict[str, object]) -> Dict[str, object]:
    return {
        "dataset": instance.spec.label,
        "height": instance.height,
        "unique_keys": instance.unique_keys,
        "active_records": len(instance.active_nodes),
        "active_width_m": instance.active_width,
        "scheme": scheme,
        "width": result["width"],
        "colors": result["colors"],
        "stored_records_padded": result["stored_records_with_padding"],
        "query_samples": result["query_samples"],
        "setup_ms": result["setup_ms"],
        "client_query_ms": result["client_query_ms"],
        "server_total_ms": result["server_total_ms"],
        "server_parallel_ms": result["server_parallel_ms"],
        "client_decode_ms": result["client_decode_ms"],
        "offline_kb": result["offline_kb"],
        "online_upload_kb": result["online_upload_kb"],
        "online_download_kb": result["online_download_kb"],
        "online_total_kb": result["online_total_kb"],
    }


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object, digits: int = 2) -> str:
    if isinstance(value, str):
        return value
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}"
    return f"{number:,.{digits}f}"


def pct(value: float, digits: int = 1) -> str:
    return f"{100.0 * value:.{digits}f}%"


def write_note(
    path: Path,
    layout_rows: Sequence[Dict[str, object]],
    proof_rows: Sequence[Dict[str, object]],
    simplepir_rows: Sequence[Dict[str, object]],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sparse_rows = [row for row in layout_rows if row["scheme"] == "sparsetreepir_activebalance"]
    pbc_rows = [row for row in layout_rows if row["scheme"] == "pbc_smt_active"]
    flat_rows = [row for row in layout_rows if row["scheme"] == "flat_active_pir"]
    full_rows = [row for row in layout_rows if row["scheme"] == "perfectized_treepir"]
    hybrid_rows = [row for row in layout_rows if row["scheme"] == "hybrid_active_coloring"]

    lines = [
        "# Real-only SMT Evaluation Suite",
        "",
        "This note replaces the previous synthetic height/sparsity experiments. Every SMT instance here is induced from a real or engineering SMT workload: Polygon zkEVM key workloads, ZKsync Era key workloads, and FuelLabs SMT test vectors. Synthetic random leaves are not used in this suite.",
        "",
        "## Workloads",
        "",
        "| Workload | Kind | Key mode | Source |",
        "|---|---|---|---|",
    ]
    for spec in selected_workloads(args.workloads):
        lines.append(f"| {spec.label} | {spec.kind} | {spec.key_mode} | `{spec.path}` |")

    lines.extend(
        [
            "",
            "## 1. Main real-workload resource shape",
            "",
            "| Dataset | h | keys | active N | m | avg path | dummy | PBC width/max | Flat max | Sparse max | Sparse/lower |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    sparse_by_key = {(row["dataset"], row["height"]): row for row in sparse_rows}
    pbc_by_key = {(row["dataset"], row["height"]): row for row in pbc_rows}
    flat_by_key = {(row["dataset"], row["height"]): row for row in flat_rows}
    for key in sorted(sparse_by_key):
        sparse = sparse_by_key[key]
        pbc = pbc_by_key[key]
        flat = flat_by_key[key]
        ratio = float(sparse["max_bucket"]) / max(1.0, float(sparse["structural_lower_bound"]))
        lines.append(
            "| {dataset} | {h} | {keys} | {active} | {m} | {avg_path} | {dummy} | {pbc_width}/{pbc_max} | {flat_max} | {sparse_max} | {ratio:.3f} |".format(
                dataset=sparse["dataset"],
                h=sparse["height"],
                keys=fmt(sparse["unique_keys"], 0),
                active=fmt(sparse["active_records"], 0),
                m=fmt(sparse["active_width_m"], 0),
                avg_path=fmt(sparse["avg_active_path"], 2),
                dummy=pct(float(sparse["dummy_fraction"]), 2),
                pbc_width=fmt(pbc["width"], 0),
                pbc_max=fmt(pbc["max_bucket"], 0),
                flat_max=fmt(flat["max_bucket"], 0),
                sparse_max=fmt(sparse["max_bucket"], 0),
                ratio=ratio,
            )
        )

    lines.extend(
        [
            "",
            "## 2. Improvement source summary",
            "",
            "| Comparison | Mean resource change on real workloads | Interpretation |",
            "|---|---:|---|",
        ]
    )
    if sparse_rows:
        max_active = max(int(row["stored_records"]) for row in sparse_rows)
        width_reduction_pbc = mean(
            1.0 - float(s["width"]) / float(p["width"])
            for s, p in zip(sparse_rows, pbc_rows)
        )
        bucket_reduction_pbc = mean(
            1.0 - float(s["max_bucket"]) / float(p["max_bucket"])
            for s, p in zip(sparse_rows, pbc_rows)
        )
        bucket_reduction_flat = mean(
            1.0 - float(s["max_bucket"]) / float(f["max_bucket"])
            for s, f in zip(sparse_rows, flat_rows)
        )
        bucket_reduction_hybrid = mean(
            1.0 - float(s["max_bucket"]) / max(1.0, float(h["max_bucket"]))
            for s, h in zip(sparse_rows, hybrid_rows)
        )
        lines.append(
            "| vs perfectized TreePIR object | "
            f"active N <= {max_active:,}, while full h=128/256 trees have $2^{{129}}-2$ / $2^{{257}}-2$ records | "
            "Full coordinate tree is the wrong PIR-facing object for real SMT workloads. |"
        )
        lines.append(
            f"| vs PBC-SMT active route | width down {pct(width_reduction_pbc)}, max bucket down {pct(bucket_reduction_pbc)} | Generic batch coding does not exploit active interval/path structure. |"
        )
        lines.append(
            f"| vs flat active PIR | max searched database down {pct(bucket_reduction_flat)} | Storing only active records is not enough; color partitioning changes backend shape. |"
        )
        lines.append(
            f"| vs node-local hybrid coloring | max color store down {pct(bucket_reduction_hybrid)} | ActiveBalance improves the exact-width active color-store profile. |"
        )

    lines.extend(
        [
            "",
            "## 3. Non-private ordinary SMT batch proof serving",
            "",
            "Plain SMT proof serving is included only as a semantic reference. It is much cheaper because the server is told the target leaves, so it is not a privacy-preserving competitor.",
            "",
            "| Dataset | h | batch | avg real slots/target | ordinary separate bytes | ordinary dedup bytes |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    max_batch_by_group: Dict[Tuple[str, int], int] = {}
    for row in proof_rows:
        key = (str(row["dataset"]), int(row["height"]))
        max_batch_by_group[key] = max(max_batch_by_group.get(key, 0), int(row["target_batch"]))
    for row in proof_rows:
        if int(row["target_batch"]) == max_batch_by_group[(str(row["dataset"]), int(row["height"]))]:
            lines.append(
                f"| {row['dataset']} | {row['height']} | {row['target_batch']} | "
                f"{float(row['avg_real_slots_per_target']):.2f} | "
                f"{fmt(row['ordinary_separate_bytes'], 0)} | {fmt(row['ordinary_batch_dedup_bytes'], 0)} |"
            )

    if simplepir_rows:
        lines.extend(
            [
                "",
                "## 4. SimplePIR backend bridge on real workloads",
                "",
                "| Dataset | h | scheme | width | active | queries | setup ms | query ms | answer parallel ms | recover ms | online KB |",
                "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in simplepir_rows:
            lines.append(
                f"| {row['dataset']} | {row['height']} | {row['scheme']} | "
                f"{row['width']} | {row['active_records']} | {row['query_samples']} | "
                f"{float(row['setup_ms']):.3f} | {float(row['client_query_ms']):.3f} | "
                f"{float(row['server_parallel_ms']):.3f} | {float(row['client_decode_ms']):.3f} | "
                f"{float(row['online_total_kb']):.3f} |"
            )
    else:
        lines.extend(
            [
                "",
                "## 4. SimplePIR backend bridge",
                "",
                "Not run in this pass. Re-run with `--run-simplepir` to materialize real workload color stores and call the SimplePIR Go API.",
            ]
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the final SparseTreePIR evaluation suite using real SMT workloads only."
    )
    parser.add_argument("--workloads", default="all", help="Comma-separated workload labels or 'all'.")
    parser.add_argument("--heights", default="128,256")
    parser.add_argument("--batch-sizes", default="1,32,128")
    parser.add_argument("--hybrid-rounds", type=int, default=60)
    parser.add_argument("--balance-rounds", type=int, default=20)
    parser.add_argument("--run-simplepir", action="store_true")
    parser.add_argument(
        "--simplepir-workloads",
        default="FuelLabs SMT test vectors,Polygon zkEVM broad,ZKsync Era broad",
        help="Comma-separated workload labels for backend runs, or 'none'.",
    )
    parser.add_argument("--simplepir-height", type=int, default=128)
    parser.add_argument("--query-samples", type=int, default=20)
    parser.add_argument("--simplepir-drive", default="X")
    parser.add_argument("--simplepir-timeout", type=int, default=900)
    parser.add_argument("--layout-dir", type=Path, default=Path("examples/real_smt_final_suite_simplepir_layouts"))
    parser.add_argument("--instances-csv", type=Path, default=Path("examples/real_smt_final_suite_instances.csv"))
    parser.add_argument("--layouts-csv", type=Path, default=Path("examples/real_smt_final_suite_layouts.csv"))
    parser.add_argument("--proof-csv", type=Path, default=Path("examples/real_smt_final_suite_plain_proofs.csv"))
    parser.add_argument("--simplepir-csv", type=Path, default=Path("examples/real_smt_final_suite_simplepir.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/real_smt_final_suite_note.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workloads = selected_workloads(args.workloads)
    heights = parse_int_list(args.heights)
    batch_sizes = parse_int_list(args.batch_sizes)

    instances: Dict[Tuple[str, int], InstanceArtifacts] = {}
    instance_rows: List[Dict[str, object]] = []
    layout_rows: List[Dict[str, object]] = []
    proof_rows: List[Dict[str, object]] = []

    print("=== Real-only SMT Evaluation Suite ===")
    print(f"workloads={[spec.label for spec in workloads]}")
    print(f"heights={heights}")
    print(f"batch_sizes={batch_sizes}")
    print(f"hybrid_rounds={args.hybrid_rounds}, balance_rounds={args.balance_rounds}")
    print()

    for spec in workloads:
        for height in heights:
            t0 = perf_counter()
            instance = build_instance(
                spec=spec,
                height=height,
                hybrid_rounds=args.hybrid_rounds,
                balance_rounds=args.balance_rounds,
            )
            t1 = perf_counter()
            instances[(spec.label, height)] = instance
            sparse_max = max(instance.sparse_loads) if instance.sparse_loads else 0
            hybrid_max = max(instance.hybrid_loads) if instance.hybrid_loads else 0
            instance_rows.append(
                {
                    "dataset": spec.label,
                    "dataset_kind": spec.kind,
                    "height": height,
                    "key_mode": spec.key_mode,
                    "input_records": instance.input_records,
                    "unique_keys": instance.unique_keys,
                    "occupied_leaves": len(instance.occupied_leaves),
                    "slot_collisions": instance.slot_collisions,
                    "active_records": len(instance.active_nodes),
                    "active_width_m": instance.active_width,
                    "structural_lower_bound": instance.structural_lower_bound,
                    "hybrid_max_bucket": hybrid_max,
                    "sparse_max_bucket": sparse_max,
                    "sparse_over_lower": sparse_max / max(1, instance.structural_lower_bound),
                    "metadata_kb": len(instance.active_nodes) * METADATA_BYTES_PER_ACTIVE / 1024.0,
                    "digest_payload_kb": len(instance.active_nodes) * RECORD_BYTES / 1024.0,
                    "profile_runtime_ms": instance.profile_runtime_ms,
                    "total_instance_runtime_ms": (t1 - t0) * 1000.0,
                    "valid": instance.valid,
                }
            )
            layout_rows.extend(scheme_layout_rows(instance))
            proof_rows.extend(proof_batch_rows(instance, batch_sizes=batch_sizes))
            print(
                f"{spec.label}, h={height}: keys={instance.unique_keys}, active={len(instance.active_nodes)}, "
                f"m={instance.active_width}, hybrid_max={hybrid_max}, sparse_max={sparse_max}, "
                f"lower={instance.structural_lower_bound}, valid={instance.valid}, "
                f"runtime={(t1 - t0) * 1000.0:.1f} ms"
            )

    simplepir_rows: List[Dict[str, object]] = []
    if args.run_simplepir:
        workspace = Path.cwd()
        workspace_drive = ensure_subst_drive(args.simplepir_drive, workspace) if os.name == "nt" else workspace.resolve()
        simplepir_root, go_exe, env = simplepir_environment(workspace_drive)
        backend_specs = backend_instances(workloads, [args.simplepir_height], args.simplepir_workloads)
        print()
        print("=== Real-only SimplePIR Backend Bridge ===")
        for spec, height in backend_specs:
            key = (spec.label, height)
            if key not in instances:
                instances[key] = build_instance(
                    spec=spec,
                    height=height,
                    hybrid_rounds=args.hybrid_rounds,
                    balance_rounds=args.balance_rounds,
                )
            instance = instances[key]
            rows = simplepir_rows_for_instance(
                instance,
                query_samples=args.query_samples,
                seed=73000 + height + instance.unique_keys,
                layout_dir=args.layout_dir,
                workspace=workspace,
                workspace_drive=workspace_drive,
                simplepir_root=simplepir_root,
                go_exe=go_exe,
                env=env,
                timeout=args.simplepir_timeout,
            )
            simplepir_rows.extend(rows)
            for row in rows:
                print(
                    f"{row['dataset']}, h={row['height']}, {row['scheme']}: "
                    f"width={row['width']}, online={float(row['online_total_kb']):.3f} KB, "
                    f"answer_parallel={float(row['server_parallel_ms']):.3f} ms"
                )

    write_csv(args.instances_csv, instance_rows)
    write_csv(args.layouts_csv, layout_rows)
    write_csv(args.proof_csv, proof_rows)
    if simplepir_rows:
        write_csv(args.simplepir_csv, simplepir_rows)
    write_note(args.note, layout_rows, proof_rows, simplepir_rows, args)

    print()
    print(f"instances={args.instances_csv}")
    print(f"layouts={args.layouts_csv}")
    print(f"proofs={args.proof_csv}")
    if simplepir_rows:
        print(f"simplepir={args.simplepir_csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
