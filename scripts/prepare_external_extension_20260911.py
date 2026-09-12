"""Prepare real SMT proof inputs for the external 32-byte batch-PIR experiment.

No PIR timing is performed here. Historical files are read-only. The original
Hungarian ActiveBalance entry point is used with a 20-scan budget. Each case runs
in a separate, bounded process; incomplete cases never publish usable inputs.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples/tifs_external_extension_20260911/inputs"
SEED = 2026091103
CASES = {
    "uniform_n1000": (128, 1000, "uniform_sha256"),
    "uniform_n10000": (128, 10000, "uniform_sha256"),
    "uniform_n100000": (128, 100000, "uniform_sha256"),
    "prefix64_n10000": (128, 10000, "prefix64_zero"),
    "cluster90_n10000": (128, 10000, "cluster90_prefix64"),
    "complete_h10": (10, 1024, "complete"),
    "complete_h14": (14, 16384, "complete"),
}
PIR = {"poly_degree": 8192, "coeff_bits": [42, 58, 58, 60],
       "plain_bits": 28, "first_dimension": 64}
SOURCE_FILES = [
    "scripts/prepare_external_extension_20260911.py",
    "scripts/tifs_revision_smt.py", "scripts/fixed_sparse_tree_coloring.py",
    "scripts/generate_full_sparse_smt_example.py",
    "scripts/run_height_sparsity_profile_balance_experiment.py",
    "scripts/run_sparse_smt_pir_backend_experiment.py",
    "scripts/contribution_gate_csa_20260910.java",
    "scripts/contribution_gate_index_20260910.java",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2 if pretty else None,
                  separators=None if pretty else (",", ":"))
        f.write("\n")
    temp.replace(path)


def progress(case: Path, stage: str, **kwargs) -> None:
    dump(case / "progress.json", {"stage": stage, "unix_time": time.time(), **kwargs})
    print(case.name, stage, flush=True)


def key_material(index: int) -> bytes:
    # This is a reproducible synthetic key, not an application request trace.
    return (b"SparseTreePIR-external-20260911-key\x00"
            + SEED.to_bytes(8, "big") + index.to_bytes(8, "big"))


def make_slots(height: int, n: int, distribution: str):
    if distribution == "complete":
        return list(range(n)), {"generator": "all logical coordinates", "collisions": 0}
    raw = [hashlib.sha256(key_material(i)).digest() for i in range(n)]
    uniform = [int.from_bytes(x[:16], "big") for x in raw]
    if distribution == "prefix64_zero":
        generated = [x & ((1 << 64) - 1) for x in uniform]
    elif distribution == "cluster90_prefix64":
        generated = [(x & ((1 << 64) - 1)) if i < n * 9 // 10 else x
                     for i, x in enumerate(uniform)]
    else:
        generated = uniform
    if len(set(generated)) != n:
        raise ValueError("Synthetic coordinate collision; no silent deduplication/resampling")
    slots = sorted(generated)
    return slots, {
        "generator": "SHA256(domain || seed_uint64_be || source_index_uint64_be), first 128 bits",
        "key_domain_hex": b"SparseTreePIR-external-20260911-key\x00".hex(),
        "source_indices": [0, n - 1], "seed": SEED, "collisions": 0,
        "shared_prefix_bits": 64 if distribution == "prefix64_zero" else 0,
        "prefix_transform": "zero top 64 bits; preserve the exact low 64 bits of uniform_n10000"
                            if distribution == "prefix64_zero" else
                            "source indices 0..8999: zero top 64 bits; 9000..9999: unchanged uniform 128 bits"
                            if distribution == "cluster90_prefix64" else "none",
        "cluster_fraction": 0.9 if distribution == "cluster90_prefix64" else None,
        "scope": "Synthetic deterministic coordinates; not real keys or a real request trace",
        "unsorted_uniform_coordinates_sha256": hashlib.sha256(
            b"".join(x.to_bytes(16, "big") for x in uniform)).hexdigest(),
    }


def required(slot: int, height: int, active: dict) -> dict[int, int]:
    node = (1 << height) + slot
    result = {}
    for level in range(height):
        sibling = node ^ 1
        if sibling in active:
            result[level] = sibling
        node //= 2
    return result


def read_official(case: Path, height: int, java_timeout: int):
    """Execute unchanged official CSA and SubCSA; preserve original positions."""
    official = ROOT / "examples/tifs_contribution_gate_20260910/external/official_sources"
    historical = ROOT / f"examples/tifs_contribution_gate_20260910/external/complete_h{height}"
    gson = official / "CSA/gson-2.10.1.jar"
    audit = {"commit": "930063c5aefc441244abb4890fdf35383f3aa956", "sources": {}, "commands": []}
    for name in ["CSA/src/CSA.java", "CSA/src/MerkleTrees.java", "TreePIR-Indexing/src/SubCSA.java"]:
        audit["sources"][name] = sha(official / name)
    outputs = {}
    for mode, source in [("csa", official / "CSA/src/CSA.java"),
                         ("index", official / "TreePIR-Indexing/src/SubCSA.java")]:
        saved = historical / f"official_{mode}.tsv"
        if height == 10 and saved.exists():
            result = saved.read_text(encoding="utf-8")
            audit.setdefault("reused_frozen_outputs", {})[str(saved.relative_to(ROOT))] = sha(saved)
        else:
            build = case / "java_build" / mode
            build.mkdir(parents=True, exist_ok=True)
            cmd = ["javac", "-d", str(build), "-cp", str(gson), str(source)]
            if mode == "csa":
                cmd.append(str(official / "CSA/src/MerkleTrees.java"))
            cmd.append(str(ROOT / f"scripts/contribution_gate_{mode}_20260910.java"))
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=java_timeout)
            audit["commands"].append({"command": cmd, "returncode": p.returncode,
                                      "stderr": p.stderr, "stdout": p.stdout})
            if p.returncode:
                raise RuntimeError(p.stderr)
            cmd = ["java", "-Xmx2g", "-cp", str(build) + os.pathsep + str(gson),
                   f"contribution_gate_{mode}_20260910", str(height)]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=java_timeout)
            audit["commands"].append({"command": cmd, "returncode": p.returncode,
                                      "stderr": p.stderr})
            if p.returncode:
                raise RuntimeError(p.stderr)
            result = p.stdout
        (case / f"official_{mode}.tsv").write_text(result, encoding="utf-8")
        outputs[mode] = list(csv.DictReader(result.splitlines(), delimiter="\t"))
    colored = {}
    buckets = [[] for _ in range(height)]
    for row in outputs["csa"]:
        swapped, c, j = int(row["swapped_node"]), ord(row["color"]) - 65, int(row["position"])
        if swapped in colored or len(buckets[c]) != j:
            raise AssertionError("Official CSA record/position mismatch")
        colored[swapped] = (c, j)
        buckets[c].append(swapped ^ 1)
    assert set(colored) == set(range(2, 1 << (height + 1)))
    for row in outputs["index"]:
        slot, swapped = int(row["target_slot"]), int(row["swapped_node"])
        assert colored[swapped] == (ord(row["color"]) - 65, int(row["position"]))
        assert swapped in [((1 << height) + slot) >> t for t in range(height)]
    assert len(outputs["index"]) == (1 << height) * height
    audit["all_occupied_targets_official_index_checked"] = 1 << height
    audit["original_index_order_preserved"] = True
    dump(case / "official_source_audit.json", audit)
    return buckets


def layout_input(case_name: str, mode: str, base, record_nodes, record_ids,
                 bucket_nodes, targets, generator):
    nodes = {n.index: n for n in base.proof_nodes}
    entries = [{"left": nodes[v].interval_left, "right": nodes[v].interval_right,
                "level": base.height - nodes[v].depth, "record": record_ids[v]}
               for v in record_nodes]
    buckets = [[record_ids[v] for v in vs] for vs in bucket_nodes]
    bucket_intervals = [[dict(entries[r]) for r in bucket] for bucket in buckets]
    # Official positions are retained. Search metadata may be sorted separately:
    # its record ID resolves back to the original within-bucket PIR index.
    # AB buckets already follow the same interval order as the metadata.
    lookup = {v: (c, j) for c, vs in enumerate(bucket_nodes) for j, v in enumerate(vs)}
    tgt = []
    for rank in targets:
        slot = base.slots[rank]
        need = required(slot, base.height, base.active_records)
        by_bucket = [None] * len(buckets)
        for v in need.values():
            if buckets:
                c, j = lookup[v]
                assert by_bucket[c] is None
                by_bucket[c] = j
        tgt.append({"id": rank, "slot_hex": slot.to_bytes((base.height + 7) // 8, "big").hex(),
                    "value_hex": base.values[slot].hex(),
                    "needed": [{"record": record_ids[v], "level": t} for t, v in sorted(need.items())],
                    "by_bucket": by_bucket})
    return {
        "schema_version": 1, "case": case_name, "mode": mode, "height": base.height,
        "root_hex": base.root.hex(), "default_hashes": [x.hex() for x in base.defaults[:base.height]],
        "records": [base.active_records[v].hex() for v in record_nodes],
        "record_heap_ids_hex": [hex(v) for v in record_nodes],
        "record_intervals": entries,
        "buckets": buckets, "occupied_slots_hex": [s.to_bytes((base.height + 7) // 8, "big").hex() for s in base.slots],
        "bucket_intervals": bucket_intervals, "targets": tgt,
        "pir": {**PIR, "batch_size": base.width}, "seed": SEED,
        "metadata_scope": "Record IDs, intervals, levels and indices are public. No expected digest is embedded in routing metadata. records is the server payload; targets is private client/audit input.",
        "target_expectations_scope": "needed/by_bucket are post-recovery audit expectations, not online routing inputs",
        "generator": generator,
    }


def check_all_routes(base, buckets, root_limit: int):
    from tifs_revision_smt import verify_proof
    nodes = {n.index: n for n in base.proof_nodes}
    assert set(v for vs in buckets for v in vs) == set(base.active_records)
    assert sum(map(len, buckets)) == len(base.active_records)
    indices = []
    for vs in buckets:
        rows = sorted((nodes[v].interval_left, nodes[v].interval_right,
                       base.height - nodes[v].depth, v) for v in vs)
        assert all(a[1] < b[0] for a, b in zip(rows, rows[1:]))
        indices.append(([r[0] for r in rows], rows))
    if len(base.slots) <= root_limit:
        roots = set(range(len(base.slots)))
    else:
        roots = set(random.Random(SEED + 81).sample(range(len(base.slots)), root_limit))
        roots.update([0, len(base.slots) - 1])
    for rank, slot in enumerate(base.slots):
        selected = {}
        for lefts, rows in indices:
            pos = bisect.bisect_right(lefts, rank) - 1
            if pos >= 0 and rows[pos][1] >= rank:
                _, _, level, v = rows[pos]
                assert level not in selected
                selected[level] = v
        expected = required(slot, base.height, base.active_records)
        assert selected == expected
        if rank in roots:
            proof = list(base.defaults[:base.height])
            for level, v in selected.items():
                proof[level] = base.active_records[v]
            assert proof == base.tree.proof(slot)
            assert verify_proof(base.height, slot, base.values[slot], proof, base.root)
            if selected:
                t = next(iter(selected)); bad = list(proof)
                bad[t] = bytes([bad[t][0] ^ 1]) + bad[t][1:]
                assert not verify_proof(base.height, slot, base.values[slot], bad, base.root)
    return {"all_target_routes_checked": len(base.slots), "root_proofs_checked": len(roots),
            "root_sampling": "all" if len(roots) == len(base.slots) else "fixed uniform sample plus first/last rank",
            "wrong_used_digest_rejections": len(roots), "routing_independent_of_target_expectations": True}


def worker(args):
    case = args.output / args.worker
    case.mkdir(parents=True, exist_ok=True)
    if (case / "snapshot_summary.json").exists():
        raise RuntimeError("Case already complete; use a fresh output directory")
    if os.name != "nt":
        import resource
        limit = int(args.memory_gib * (1 << 30))
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    started = time.perf_counter()
    try:
        from tifs_revision_smt import build_layout, HASH_FORMAT
        h, n, distribution = CASES[args.worker]
        progress(case, "generate coordinates", n=n, height=h)
        slots, generator = make_slots(h, n, distribution)
        progress(case, "original Hungarian ActiveBalance construction", n=n, height=h, scans=20)
        build_start = time.perf_counter()
        base = build_layout(h, slots, color_strategy="activebalance", refine_rounds=20)
        build_s = time.perf_counter() - build_start
        assert len(base.active_records) == 2*n - 2
        progress(case, "validate all occupied routes", build_s=build_s)
        buckets = [base.buckets[c] for c in range(1, base.width + 1)]
        checks = {"ab": check_all_routes(base, buckets, args.root_limit)}
        records = sorted(base.active_records)
        record_ids = {v: i for i, v in enumerate(records)}
        pool = sorted(random.Random(SEED + 7).sample(range(n), min(args.pool, n)))
        official_buckets = None
        if distribution == "complete":
            progress(case, "unchanged official CSA/SubCSA")
            official_buckets = read_official(case, h, args.java_timeout)
            checks["treepir"] = check_all_routes(base, official_buckets, args.root_limit)
        progress(case, "write verified input JSON")
        outputs = {}
        for mode, bs in [("ab", buckets), ("pbc", [])] + ([("treepir", official_buckets)] if official_buckets is not None else []):
            data = layout_input(args.worker, mode, base, records, record_ids, bs, pool, generator)
            path = case / f"{mode}.json"
            dump(path, data, pretty=False)
            outputs[path.name] = {"sha256": sha(path), "bytes": path.stat().st_size}
        peak = None
        if os.name != "nt":
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        summary = {
            "status": "complete", "case": args.worker, "n": n, "height": h,
            "N": len(records), "m": base.width, "ab_loads": list(map(len, buckets)),
            "ab_max_bucket": max(map(len, buckets)), "ab_scan_budget": 20,
            "ab_reported_passes": base.passes, "ab_reported_moves": base.moves,
            "algorithm": "unchanged tifs_revision_smt.build_layout -> original best_count_profile_balanced (Hungarian)",
            "root_hex": base.root.hex(), "hash_format": HASH_FORMAT, "generator": generator,
            "target_pool": len(pool), "target_rank_ids": pool, "checks": checks,
            "build_layout_wall_s": build_s, "build_layout_stages_ms": base.timings_ms,
            "total_preparation_wall_s": time.perf_counter() - started,
            "peak_process_rss_bytes": peak, "address_space_limit_bytes": int(args.memory_gib * (1 << 30)),
            "environment": {"platform": platform.platform(), "python": platform.python_version()},
            "sources_sha256": {name: sha(ROOT / name) for name in SOURCE_FILES},
            "outputs": outputs,
            "scope": "Synthetic/complete experimental SMT input generation and direct-hash validation only; no PIR or latency benchmark performed.",
            "pbc_scope": "Global records/intervals only; original external PBC implementation must construct its own placement and real/dummy routing.",
        }
        if official_buckets is not None:
            summary["treepir_loads"] = list(map(len, official_buckets))
        dump(case / "snapshot_summary.json", summary)
        progress(case, "complete", n=n, N=len(records), m=base.width, build_s=build_s)
    except BaseException as exc:
        dump(case / "failure.json", {"status": "failed", "type": type(exc).__name__, "error": str(exc),
                                    "elapsed_s": time.perf_counter() - started, "traceback": traceback.format_exc()})
        raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cases", default="uniform_n1000")
    p.add_argument("--worker", choices=CASES)
    p.add_argument("--output", type=Path, default=OUT)
    p.add_argument("--pool", type=int, default=32)
    p.add_argument("--root-limit", type=int, default=20000)
    p.add_argument("--memory-gib", type=float, default=10)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--java-timeout", type=int, default=180)
    args = p.parse_args()
    args.output = args.output.resolve()
    if args.worker:
        worker(args)
        return
    if not 32 <= args.pool or not 0 < args.memory_gib <= 10:
        raise ValueError("At least 32 pool targets and at most 10 GiB required")
    cases = list(CASES) if args.cases == "all" else args.cases.split(",")
    if any(case not in CASES for case in cases):
        raise ValueError("Unknown case")
    args.output.mkdir(parents=True, exist_ok=True)
    for name in cases:
        case = args.output / name
        if (case / "snapshot_summary.json").exists():
            print(name, "already complete; retained unchanged", flush=True)
            continue
        case.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", name,
               "--output", str(args.output), "--pool", str(args.pool),
               "--root-limit", str(args.root_limit), "--memory-gib", str(args.memory_gib),
               "--java-timeout", str(args.java_timeout)]
        started = time.perf_counter()
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", GOMAXPROCS="1")
        with (case / "worker_stdout.txt").open("w", encoding="utf-8") as stdout, \
             (case / "worker_stderr.txt").open("w", encoding="utf-8") as stderr:
            proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, env=env)
            try:
                code = proc.wait(timeout=args.timeout)
                status = "complete" if code == 0 and (case / "snapshot_summary.json").exists() else "failed"
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(); code = None; status = "timeout"
        report = {"case": name, "status": status, "exit_code": code,
                  "process_wall_s": time.perf_counter() - started, "timeout_s": args.timeout,
                  "memory_limit_gib": args.memory_gib, "command": cmd}
        dump(case / "process.json", report)
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
