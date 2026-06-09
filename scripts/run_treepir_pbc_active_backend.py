from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from run_real_smt_final_experiment_suite import (
    DEFAULT_WORKLOADS,
    WorkloadSpec,
    build_instance,
    parse_int_list,
    selected_workloads,
)
from run_simplepir_full_backend_experiment import (
    RECORD_BYTES,
    ensure_subst_drive,
    run_simplepir_runner,
    simplepir_environment,
)


NUM_HASH_FUNCTIONS = 3
CUCKOO_FACTOR = 1.5
MAX_ATTEMPTS = 500
DEFAULT_QUERY_INDEX = 0


@dataclass
class PBCManifestStats:
    manifest_path: Path
    dataset: str
    height: int
    seed: int
    active_records: int
    active_width: int
    pbc_buckets: int
    max_bucket_size: int
    replicated_records: int
    padded_records: int
    query_samples: int
    cuckoo_failures: int
    cuckoo_failure_rate: float
    server_map_ms: float
    client_cuckoo_ms: float


def stable_hash_mod(hash_id: int, nonce: int, item: int, modulus: int) -> int:
    material = f"{hash_id}:{nonce}:{item}".encode("ascii")
    digest = hashlib.blake2b(material, digest_size=8).digest()
    return int.from_bytes(digest, "little") % modulus


def candidate_buckets(item: int, total_buckets: int, num_hashes: int = NUM_HASH_FUNCTIONS) -> List[int]:
    buckets: List[int] = []
    for hash_id in range(num_hashes):
        nonce = 0
        bucket = stable_hash_mod(hash_id, nonce, item, total_buckets)
        while bucket in buckets:
            nonce += 1
            bucket = stable_hash_mod(hash_id, nonce, item, total_buckets)
        buckets.append(bucket)
    return buckets


def deterministic_record(dataset: str, height: int, node_id: int) -> bytes:
    material = f"{dataset}|h={height}|node={node_id}".encode("utf-8")
    return hashlib.sha256(material).digest()


def displace_insert(
    key: int,
    key_to_buckets: Dict[int, List[int]],
    bucket_to_key: Dict[int, int],
    rng: random.Random,
    attempt: int = 0,
) -> None:
    if attempt > MAX_ATTEMPTS:
        raise RuntimeError("Cuckoo hashing failed")

    for bucket in key_to_buckets[key]:
        if bucket not in bucket_to_key:
            bucket_to_key[bucket] = key
            return

    bucket = rng.choice(key_to_buckets[key])
    evicted = bucket_to_key[bucket]
    bucket_to_key[bucket] = key
    displace_insert(evicted, key_to_buckets, bucket_to_key, rng, attempt + 1)


def cuckoo_assign(batch: Sequence[int], total_buckets: int, rng: random.Random) -> List[Optional[int]]:
    if len(set(batch)) != len(batch):
        raise ValueError("PBC batch contains duplicate item labels")
    key_to_buckets = {item: candidate_buckets(item, total_buckets) for item in batch}
    bucket_to_key: Dict[int, int] = {}
    for item in batch:
        displace_insert(item, key_to_buckets, bucket_to_key, rng)
    return [bucket_to_key.get(bucket) for bucket in range(total_buckets)]


def write_bucket_databases(
    *,
    output_dir: Path,
    dataset: str,
    height: int,
    record_ids: Sequence[int],
    total_buckets: int,
) -> Tuple[List[Dict[str, object]], Dict[Tuple[int, int], int], int]:
    buckets: List[List[int]] = [[] for _ in range(total_buckets)]
    index_map: Dict[Tuple[int, int], int] = {}
    records_by_label: Dict[int, bytes] = {}
    for record_id in record_ids:
        label = record_id + 2  # Match TreePIR PBC's convention of reserving 0/1.
        records_by_label[label] = deterministic_record(dataset, height, record_id)
        for bucket in candidate_buckets(label, total_buckets):
            index_map[(label, bucket)] = len(buckets[bucket])
            buckets[bucket].append(label)

    max_bucket_size = max((len(bucket) for bucket in buckets), default=0)
    max_bucket_size = max(1, max_bucket_size)
    dummy_record = b"\x00" * RECORD_BYTES
    subdatabases: List[Dict[str, object]] = []
    for bucket_id, labels in enumerate(buckets, start=1):
        db_path = output_dir / f"pbc_bucket_{bucket_id:02d}.bin"
        payload = bytearray()
        for label in labels:
            payload.extend(records_by_label[label])
        for _ in range(max_bucket_size - len(labels)):
            payload.extend(dummy_record)
        db_path.write_bytes(bytes(payload))
        subdatabases.append(
            {
                "color": bucket_id,
                "records": max_bucket_size,
                "unpadded_records": len(labels),
                "record_bytes": RECORD_BYTES,
                "database_file": db_path.name,
                "query_indices": [],
            }
        )
    return subdatabases, index_map, max_bucket_size


def real_record_ids_for_rank(instance, record_id_by_node: Dict[int, int], rank: int) -> List[int]:
    real: List[int] = []
    for node in instance.active_nodes:
        if node.interval_left <= rank <= node.interval_right:
            real.append(record_id_by_node[node.index])
    return sorted(real)


def padded_batch(
    *,
    real_ids: Sequence[int],
    active_count: int,
    active_width: int,
    rng: random.Random,
) -> List[int]:
    real = list(real_ids)
    if len(real) > active_width:
        raise ValueError(f"target needs {len(real)} active records, exceeds active width {active_width}")
    available = [idx for idx in range(active_count) if idx not in set(real)]
    rng.shuffle(available)
    needed = active_width - len(real)
    if needed > len(available):
        raise ValueError("not enough distinct active records for dummy padding")
    return [item + 2 for item in real + available[:needed]]


def sampled_leaves(occupied: Sequence[int], seed: int, query_samples: int) -> List[int]:
    if not occupied:
        return []
    return [occupied[(seed + idx) % len(occupied)] for idx in range(min(query_samples, len(occupied)))]


def write_treepir_pbc_manifest(
    *,
    instance,
    seed: int,
    query_samples: int,
    output_dir: Path,
) -> PBCManifestStats:
    output_dir.mkdir(parents=True, exist_ok=True)
    active_nodes = sorted(instance.active_nodes, key=lambda node: node.index)
    record_id_by_node = {node.index: pos for pos, node in enumerate(active_nodes)}
    active_count = len(active_nodes)
    active_width = instance.active_width
    total_buckets = max(1, math.ceil(CUCKOO_FACTOR * active_width))

    t0 = time.perf_counter()
    subdatabases, index_map, max_bucket_size = write_bucket_databases(
        output_dir=output_dir,
        dataset=instance.spec.label,
        height=instance.height,
        record_ids=list(range(active_count)),
        total_buckets=total_buckets,
    )
    t1 = time.perf_counter()

    leaves = sampled_leaves(instance.occupied_leaves, seed, query_samples)
    rank_by_leaf = {leaf: rank for rank, leaf in enumerate(instance.occupied_leaves)}
    dummy_rng = random.Random(seed * 1009 + active_width)
    cuckoo_failures = 0
    client_cuckoo_start = time.perf_counter()

    for sample_index, leaf in enumerate(leaves):
        rank = rank_by_leaf[leaf]
        real_ids = real_record_ids_for_rank(instance, record_id_by_node, rank)
        batch = padded_batch(
            real_ids=real_ids,
            active_count=active_count,
            active_width=active_width,
            rng=dummy_rng,
        )
        try:
            assignment = cuckoo_assign(batch, total_buckets, random.Random(seed * 2003 + sample_index))
        except RuntimeError:
            cuckoo_failures += 1
            assignment = [None for _ in range(total_buckets)]

        for bucket, label in enumerate(assignment):
            if label is None:
                query_index = DEFAULT_QUERY_INDEX
            else:
                query_index = index_map[(label, bucket)]
            subdatabases[bucket]["query_indices"].append(query_index)

    client_cuckoo_end = time.perf_counter()

    manifest = {
        "scheme": "treepir_pbc_active",
        "baseline": "PBC baseline",
        "height": instance.height,
        "width": total_buckets,
        "active_width": active_width,
        "active_nodes": active_count,
        "stored_nodes": 3 * active_count,
        "stored_nodes_with_padding": max_bucket_size * total_buckets,
        "query_samples": len(leaves),
        "record_bytes": RECORD_BYTES,
        "pbc_parameters": {
            "num_hash_functions": NUM_HASH_FUNCTIONS,
            "cuckoo_factor": CUCKOO_FACTOR,
            "max_attempts": MAX_ATTEMPTS,
            "label_offset": 2,
            "dummy_query_index": DEFAULT_QUERY_INDEX,
        },
        "subdatabases": subdatabases,
        "note": (
            "This manifest adapts TreePIR's PBC mechanics to SparseTreePIR active proof records: "
            "three replicated bucket placements, ceil(1.5m) buckets, per-request Cuckoo assignment, "
            "and dummy padding to active width m. It is intended for the existing SimplePIR manifest runner."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return PBCManifestStats(
        manifest_path=manifest_path,
        dataset=instance.spec.label,
        height=instance.height,
        seed=seed,
        active_records=active_count,
        active_width=active_width,
        pbc_buckets=total_buckets,
        max_bucket_size=max_bucket_size,
        replicated_records=3 * active_count,
        padded_records=max_bucket_size * total_buckets,
        query_samples=len(leaves),
        cuckoo_failures=cuckoo_failures,
        cuckoo_failure_rate=(cuckoo_failures / len(leaves)) if leaves else 0.0,
        server_map_ms=(t1 - t0) * 1000.0,
        client_cuckoo_ms=(client_cuckoo_end - client_cuckoo_start) * 1000.0,
    )


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def stats_to_row(stats: PBCManifestStats) -> Dict[str, object]:
    return {
        "dataset": stats.dataset,
        "height": stats.height,
        "seed": stats.seed,
        "active_records": stats.active_records,
        "active_width_m": stats.active_width,
        "pbc_buckets": stats.pbc_buckets,
        "max_bucket_size": stats.max_bucket_size,
        "replicated_records": stats.replicated_records,
        "padded_records": stats.padded_records,
        "query_samples": stats.query_samples,
        "cuckoo_failures": stats.cuckoo_failures,
        "cuckoo_failure_rate": stats.cuckoo_failure_rate,
        "server_map_ms": stats.server_map_ms,
        "client_cuckoo_ms": stats.client_cuckoo_ms,
        "manifest": stats.manifest_path.as_posix(),
    }


def simplepir_row(stats: PBCManifestStats, result: Dict[str, object]) -> Dict[str, object]:
    return {
        **stats_to_row(stats),
        "backend": "SimplePIR",
        "width": result["width"],
        "colors": result["colors"],
        "stored_records_padded_runner": result["stored_records_with_padding"],
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export and optionally run a PBC baseline over "
            "SparseTreePIR active proof records."
        )
    )
    parser.add_argument("--workloads", default="FuelLabs SMT test vectors")
    parser.add_argument("--heights", default="128")
    parser.add_argument("--seeds", default="73000,83000,93000")
    parser.add_argument("--queries", type=int, default=50)
    parser.add_argument("--hybrid-rounds", type=int, default=8)
    parser.add_argument("--balance-rounds", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("examples/treepir_pbc_active"))
    parser.add_argument("--run-simplepir", action="store_true")
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--workspace-drive", type=Path, default=Path("T:/"))
    parser.add_argument("--simplepir-root", type=Path, default=Path("external/simplepir"))
    parser.add_argument("--go-exe", type=Path, default=Path("external/go/bin/go"))
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    workloads: List[WorkloadSpec] = selected_workloads(args.workloads)
    heights = parse_int_list(args.heights)
    seeds = parse_int_list(args.seeds)

    workspace = args.workspace.resolve()
    workspace_drive = ensure_subst_drive(workspace, args.workspace_drive) if args.run_simplepir else args.workspace_drive
    env = simplepir_environment(workspace) if args.run_simplepir else {}

    manifest_rows: List[Dict[str, object]] = []
    backend_rows: List[Dict[str, object]] = []

    for spec in workloads:
        for height in heights:
            instance = build_instance(
                spec=spec,
                height=height,
                hybrid_rounds=args.hybrid_rounds,
                balance_rounds=args.balance_rounds,
            )
            safe_name = spec.label.lower().replace(" ", "_").replace("/", "_")
            for seed in seeds:
                out_dir = args.output_dir / f"seed{seed}" / f"{safe_name}_h{height}" / "treepir_pbc_active"
                stats = write_treepir_pbc_manifest(
                    instance=instance,
                    seed=seed,
                    query_samples=args.queries,
                    output_dir=out_dir,
                )
                row = stats_to_row(stats)
                manifest_rows.append(row)
                print(
                    "manifest={manifest} failures={failures}/{samples} buckets={buckets} max={max_bucket}".format(
                        manifest=stats.manifest_path,
                        failures=stats.cuckoo_failures,
                        samples=stats.query_samples,
                        buckets=stats.pbc_buckets,
                        max_bucket=stats.max_bucket_size,
                    )
                )

                if args.run_simplepir:
                    result = run_simplepir_runner(
                        manifest_path=stats.manifest_path,
                        workspace=workspace,
                        workspace_drive=workspace_drive,
                        simplepir_root=args.simplepir_root,
                        go_exe=args.go_exe,
                        env=env,
                        timeout=args.timeout,
                    )
                    backend_rows.append(simplepir_row(stats, result))
                    print(
                        "simplepir online_kb={:.3f} setup_ms={:.3f}".format(
                            float(result["online_total_kb"]),
                            float(result["setup_ms"]),
                        )
                    )

    write_csv(args.output_dir / "treepir_pbc_active_manifest_summary.csv", manifest_rows)
    if backend_rows:
        write_csv(args.output_dir / "treepir_pbc_active_simplepir_summary.csv", backend_rows)


if __name__ == "__main__":
    main()
