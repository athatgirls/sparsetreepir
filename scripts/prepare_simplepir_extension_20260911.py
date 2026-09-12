"""Freeze four SimplePIR layouts against the completed native VBPIR inputs.

Only public placement is computed. No large SMT is rebuilt and no PIR runs here.
PBC candidates call the exact frozen C++ utility rather than a Python hash clone.
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/tifs_external_extension_20260911"
OUT = ROOT / "examples/tifs_simplepir_extension_20260911/inputs"
VENDOR = SOURCE / "native_adapter/vendor"
CASES = ["uniform_n1000", "uniform_n10000", "prefix64_n10000",
         "cluster90_n10000", "complete_h10", "complete_h14", "uniform_n100000"]
NONE = (1 << 64) - 1
COMMON = ["schema_version", "case", "height", "root_hex", "default_hashes", "records",
          "record_heap_ids_hex", "record_intervals", "occupied_slots_hex", "seed", "generator"]
SIMPLEPIR = {"record_bytes": 32, "record_bits": 256, "parts": 1,
             "encoding": "native base-p long record",
             "parameter_policy": "PickParams(U, 256, 1024, 32)",
             "parameter_U": "public maximum bucket load; N for flat",
             "secret_dimension": 1024, "logq": 32, "public_A": "expanded"}
EXPORTER = r'''// Public-placement exporter; official utility included unchanged.
#include <algorithm>
#include <fstream>
#include <functional>
#include <string>
#include "src/utils.h"
int main(int argc, char** argv) {
  if (argc != 4) return 2;
  const size_t n = std::stoull(argv[1]), b = std::stoull(argv[2]);
  if (b < 3) return 3;
  std::ofstream out(argv[3]);
  for (size_t r = 0; r < n; ++r) {
    const auto candidates = utils::get_candidate_buckets(r, 3, b);
    out << r;
    for (auto c : candidates) out << '\t' << c;
    out << '\n';
  }
  return out ? 0 : 4;
}
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value, pretty=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, indent=2 if pretty else None,
                  separators=None if pretty else (",", ":"))
        out.write("\n")
    temporary.replace(path)


def build_exporter(out):
    work = out / "_hash_exporter"
    work.mkdir(parents=True, exist_ok=True)
    source, binary = work / "export_public_placement.cpp", work / "export_public_placement"
    manifest = work / "build_manifest.json"
    expected = {"official_utils_sha256": sha(VENDOR / "src/utils.h"),
                "source_sha256": hashlib.sha256(EXPORTER.encode()).hexdigest()}
    if manifest.exists():
        prior = load(manifest)
        assert all(prior[k] == v for k, v in expected.items()), "Frozen exporter source changed"
        assert sha(binary) == prior["binary_sha256"]
        return binary
    source.write_text(EXPORTER, encoding="utf-8", newline="\n")
    cmd = ["c++", "-O2", "-std=c++17", "-I", str(VENDOR), "-I", str(VENDOR / "header"),
           "-isystem", "/usr/local/include/SEAL-4.3", str(source), "-o", str(binary)]
    begin = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    report = {**expected, "command": cmd, "returncode": result.returncode,
              "stdout": result.stdout, "stderr": result.stderr,
              "compile_wall_s": time.perf_counter() - begin,
              "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[0],
              "scope": "Only official get_candidate_buckets executed; no encryption, PIR or timing benchmark"}
    if result.returncode:
        dump(work / "build_failure.json", report)
        raise RuntimeError(result.stderr)
    report["binary_sha256"] = sha(binary)
    dump(manifest, report)
    return binary


def schedules(out):
    path = SOURCE / "runs/schedule.json"
    original = load(path)
    frozen = out / "source_vbpir_schedule.json"
    if frozen.exists():
        assert sha(frozen) == sha(path), "Frozen native schedule changed"
    else:
        shutil.copyfile(path, frozen)
    pairs = {}
    for row in original:
        key = (row["case"], row["repeat"])
        item = {k: row[k] for k in ["case", "repeat", "pool_indices", "target_ids"]}
        assert len(item["pool_indices"]) == len(item["target_ids"]) == 10
        if key in pairs:
            assert pairs[key] == item, "Native methods did not use paired targets"
        pairs[key] = item
    assert len(pairs) == 21
    canonical = [pairs[k] for k in sorted(pairs)]
    destination = out / "target_schedule.json"
    if destination.exists():
        assert load(destination) == canonical
    else:
        dump(destination, canonical)
    return canonical, sha(path)


def export_pbc(binary, case, n, m):
    count = (3 * m + 1) // 2
    tsv = case / "official_pbc_candidates.tsv"
    subprocess.run([str(binary), str(n), str(count), str(tsv)], check=True, timeout=30)
    candidates, buckets = [], [[] for _ in range(count)]
    for line in tsv.read_text().splitlines():
        record, *bs = map(int, line.split("\t"))
        assert record == len(candidates) and len(bs) == len(set(bs)) == 3
        assert all(0 <= b < count for b in bs)
        candidates.append(bs)
        for b in bs:
            buckets[b].append(record)
    assert len(candidates) == n
    assert sum(map(len, buckets)) == 3 * n
    assert all(len(b) == len(set(b)) for b in buckets)
    return buckets, candidates


def first_fit(base):
    from generate_full_sparse_smt_example import ProofNode, build_interval_forest, max_chain_length
    from run_height_sparsity_profile_balance_experiment import first_fit_coloring
    nodes = [ProofNode(index=int(base["record_heap_ids_hex"][e["record"]], 16),
                       depth=base["height"] - e["level"], interval_left=e["left"],
                       interval_right=e["right"], weight=e["right"] - e["left"] + 1,
                       covers_leaves=[]) for e in base["record_intervals"]]
    roots = build_interval_forest(nodes)
    width = max_chain_length(roots)
    assert width == base["pir"]["batch_size"]
    first_fit_coloring(roots, width)
    by_heap = {int(h, 16): r for r, h in enumerate(base["record_heap_ids_hex"])}
    buckets = [[] for _ in range(width)]
    for node in sorted(nodes, key=lambda n: (n.interval_left, n.interval_right, n.index)):
        buckets[node.color - 1].append(by_heap[node.index])
    return buckets


def check_structured(base, buckets):
    n = len(base["records"])
    assert Counter(r for b in buckets for r in b) == Counter(range(n))
    entries = base["record_intervals"]
    indices = []
    for bucket in buckets:
        rows = [entries[r] for r in bucket]
        assert all(x["right"] < y["left"] for x, y in zip(rows, rows[1:]))
        indices.append(([x["left"] for x in rows], rows))
    by_heap = {int(h, 16): r for r, h in enumerate(base["record_heap_ids_hex"])}
    for rank, slot_hex in enumerate(base["occupied_slots_hex"]):
        found = {}
        for lefts, rows in indices:
            j = bisect.bisect_right(lefts, rank) - 1
            if j >= 0 and rank <= rows[j]["right"]:
                row = rows[j]
                assert row["level"] not in found
                found[row["level"]] = row["record"]
        heap = (1 << base["height"]) + int(slot_hex, 16)
        expected = {}
        for level in range(base["height"]):
            if heap ^ 1 in by_heap:
                expected[level] = by_heap[heap ^ 1]
            heap >>= 1
        assert expected == found
    return len(base["occupied_slots_hex"])


def root_of(base, target, proof):
    cur = hashlib.sha256(b"\x00" + bytes.fromhex(target["value_hex"])).digest()
    slot = int(target["slot_hex"], 16)
    for level, item in enumerate(proof):
        sibling = bytes.fromhex(item)
        left, right = (sibling, cur) if (slot >> level) & 1 else (cur, sibling)
        cur = hashlib.sha256(b"\x01" + left + right).digest()
    return cur.hex()


def check_native_results(name, base, pbc_buckets, ab_buckets, schedule):
    totals = {"native_results": 0, "proof_roots": 0, "positions": 0,
              "real_digest_checks": 0, "pbc_filled_slot_checks": 0,
              "pbc_empty_sentinel_slots": 0}
    pins = {}
    for mode, buckets in [("pbc", pbc_buckets), ("ab", ab_buckets)]:
        for pair in [s for s in schedule if s["case"] == name]:
            path = SOURCE / f"runs/{name}/{mode}/repeat{pair['repeat']}/result.json"
            result = load(path)
            assert result["status"] == "passed"
            assert result["parameters"]["bucket_loads"] == list(map(len, buckets))
            assert [str(t) for t in pair["target_ids"]] == [q["target_id"] for q in result["queries"]]
            targets = [base["targets"][i] for i in pair["pool_indices"]]
            assert [t["id"] for t in targets] == pair["target_ids"]
            private = {str(t["id"]): t for t in targets}
            for query in result["queries"] + result["warmups"]:
                target = private[query["target_id"]]
                assert query["computed_root_hex"] == base["root_hex"]
                assert root_of(base, target, query["proof_bottom_up_hex"]) == base["root_hex"]
                actual = []
                for item in query["recovered_by_bucket"]:
                    b, j, r = item["bucket"], item["position"], item["record"]
                    if r == NONE:
                        assert mode == "pbc" and j == NONE and not item["real"]
                        totals["pbc_empty_sentinel_slots"] += 1
                        continue
                    assert buckets[b][j] == r
                    totals["positions"] += 1
                    if mode == "pbc":
                        totals["pbc_filled_slot_checks"] += 1
                    assert item["record_hex"] == base["records"][r]
                    if item["real"]:
                        assert query["proof_bottom_up_hex"][item["level"]] == item["record_hex"]
                        actual.append({"record": r, "level": item["level"]})
                        totals["real_digest_checks"] += 1
                assert sorted(actual, key=lambda x: x["level"]) == target["needed"]
                totals["proof_roots"] += 1
            pins[str(path.relative_to(ROOT))] = sha(path)
            totals["native_results"] += 1
    return {"status": "pass", **totals, "native_result_sha256": pins,
            "pbc_placement_scope": "Every record has the same three distinct official candidates, in ascending-record insertion order; all frozen recovered record/position pairs match. This does not assert identical fresh cuckoo route randomness across backends."}


def produce(name, out, binary, schedule, schedule_sha):
    case = out / name
    summary_path = case / "cross_backend_audit.json"
    if summary_path.exists():
        assert load(summary_path)["status"] == "pass"
        print(name, "frozen unchanged", flush=True)
        return
    begin = time.perf_counter()
    case.mkdir(parents=True, exist_ok=True)
    source_file = SOURCE / f"inputs/{name}/ab.json"
    source_summary = load(SOURCE / f"inputs/{name}/snapshot_summary.json")
    assert sha(source_file) == source_summary["outputs"]["ab.json"]["sha256"]
    base = load(source_file)
    m, n = base["pir"]["batch_size"], len(base["records"])
    assert [e["record"] for e in base["record_intervals"]] == list(range(n))
    print(name, "export official PBC placement", flush=True)
    pbc_buckets, candidates = export_pbc(binary, case, n, m)
    print(name, "derive original First-fit", flush=True)
    ff_buckets = first_fit(base)
    checked = check_structured(base, ff_buckets)
    cross = check_native_results(name, base, pbc_buckets, base["buckets"], schedule)
    print(name, "cross-backend placement/root audit passed", flush=True)
    outputs = {}
    for mode, buckets in [("ab", base["buckets"]), ("pbc", pbc_buckets),
                          ("flat", [list(range(n))]), ("first_fit", ff_buckets)]:
        data = dict(base)
        data["mode"] = mode
        data["backend"] = "simplepir"
        data["source_vbpir_input_sha256"] = sha(source_file)
        data["buckets"] = buckets
        data["bucket_intervals"] = [[base["record_intervals"][r] for r in bucket] for bucket in buckets]
        data["hash_candidates"] = candidates if mode == "pbc" else []
        data["logical_queries_per_proof"] = len(buckets) if mode != "flat" else m
        data["physical_database_instances"] = len(buckets)
        data["pir"] = {"batch_size": m}
        data["simplepir"] = {**SIMPLEPIR, "flat_shared_hint_and_public_A": mode == "flat"}
        data["target_expectations_scope"] = "needed/by_bucket are post-recovery audit expectations, never online routing selectors"
        data["targets"] = [dict(t) for t in base["targets"]]
        if mode in ["first_fit", "ab"]:
            lookup = {r: (b, j) for b, bucket in enumerate(buckets) for j, r in enumerate(bucket)}
            for target in data["targets"]:
                route = [None] * len(buckets)
                for item in target["needed"]:
                    b, j = lookup[item["record"]]
                    assert route[b] is None
                    route[b] = j
                target["by_bucket"] = route
        else:
            for target in data["targets"]:
                target["by_bucket"] = []
        for k in COMMON:
            assert data[k] == base[k]
        for old, new in zip(base["targets"], data["targets"]):
            assert all(old[k] == new[k] for k in ["id", "slot_hex", "value_hex", "needed"])
        path = case / f"{mode}.json"
        dump(path, data, pretty=False)
        outputs[path.name] = {"sha256": sha(path), "bytes": path.stat().st_size,
                              "bucket_count": len(buckets), "max_bucket_records": max(map(len, buckets)),
                              "stored_record_copies": sum(map(len, buckets)),
                              "logical_queries_per_proof": data["logical_queries_per_proof"]}
    report = {**cross, "case": name, "records": n, "height": base["height"], "m": m,
              "first_fit_all_occupied_routes_checked": checked,
              "source_vbpir_input_sha256": sha(source_file), "source_schedule_sha256": schedule_sha,
              "source_common_fields_sha256": {k: digest(base[k]) for k in COMMON},
              "AB_buckets_identical_to_frozen_native_input": True,
              "target_pool_preserved": len(base["targets"]),
              "target_schedule": [s for s in schedule if s["case"] == name],
              "official_candidates_sha256": sha(case / "official_pbc_candidates.tsv"),
              "pbc_record_replication": 3, "pbc_distinct_candidates_per_record": 3,
              "original_first_fit_sha256": sha(ROOT / "scripts/run_height_sparsity_profile_balance_experiment.py"),
              "original_interval_forest_sha256": sha(ROOT / "scripts/generate_full_sparse_smt_example.py"),
              "producer_sha256": sha(Path(__file__)), "outputs": outputs,
              "prepare_wall_s": time.perf_counter() - begin,
              "environment": {"platform": platform.platform(), "python": platform.python_version()},
              "scope": "Input transformation, public placement and frozen native-result audit only; no SMT rehash, no new AB run, no new PIR measurement"}
    dump(summary_path, report)
    print(name, "complete", flush=True)


def refresh_backend_metadata(name, out):
    """Correct pre-measurement metadata without regenerating any layout or target."""
    case = out / name
    report_path = case / "cross_backend_audit.json"
    report = load(report_path)
    assert report["status"] == "pass"
    correction_path = case / "metadata_correction.json"
    if correction_path.exists():
        for filename, result in report["outputs"].items():
            assert sha(case / filename) == result["sha256"]
        return
    correction = {"reason": "Before formal measurements, replace obsolete eight-by-32-bit metadata with the new native 256-bit SimplePIR policy; no record, bucket, target or route changed",
                  "prior_producer_sha256": report["producer_sha256"], "files": {}}
    for filename, result in report["outputs"].items():
        path = case / filename
        assert sha(path) == result["sha256"]
        data = load(path)
        old = {"sha256": result["sha256"], "simplepir": data["simplepir"], "pir": data["pir"]}
        unchanged = {k: digest(v) for k, v in data.items() if k not in ["simplepir", "pir"]}
        data["simplepir"] = {**SIMPLEPIR, "flat_shared_hint_and_public_A": data["mode"] == "flat"}
        data["pir"] = {"batch_size": report["m"]}
        assert unchanged == {k: digest(v) for k, v in data.items() if k not in ["simplepir", "pir"]}
        dump(path, data, pretty=False)
        result["sha256"] = sha(path)
        result["bytes"] = path.stat().st_size
        correction["files"][filename] = {"prior": old, "corrected_sha256": result["sha256"],
                                          "all_other_fields_unchanged": True}
    report["producer_sha256"] = sha(Path(__file__))
    report["simplepir_parameter_policy"] = SIMPLEPIR
    dump(correction_path, correction)
    dump(report_path, report)
    print(name, "native256 metadata frozen", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cases", default="uniform_n1000")
    p.add_argument("--output", type=Path, default=OUT)
    p.add_argument("--refresh-backend-metadata", action="store_true")
    args = p.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    schedule, schedule_sha = schedules(out)
    cases = CASES if args.cases == "all" else args.cases.split(",")
    assert all(name in CASES for name in cases)
    if args.refresh_backend_metadata:
        for name in cases:
            refresh_backend_metadata(name, out)
        return
    binary = build_exporter(out)
    for name in cases:
        produce(name, out, binary, schedule, schedule_sha)


if __name__ == "__main__":
    main()
