"""Independent, standard-library audit of saved CT TCP experiment evidence.

This never launches a backend or performs a performance experiment. It rebuilds
the experimental SMT from frozen CT leaf records, checks every retained recovered
sibling and root, and recomputes process-pair statistics and socket accounting.
"""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import json
import math
import random
import statistics
import struct
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / "examples/tifs_revision_20260910/ct_application"
METHODS = ("first_fit", "activebalance", "nonempty_depth", "full_cache")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def csvrows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parent(left, right):
    return hashlib.sha256(b"\x01" + left + right).digest()


def root_from_proof(slot, value, proof):
    current = hashlib.sha256(b"\x00" + value).digest()
    for level, sibling in enumerate(proof):
        current = parent(sibling, current) if (slot >> level) & 1 else parent(current, sibling)
    return current


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10), (a, b)


def stats(values):
    mean, sd = statistics.mean(values), statistics.stdev(values)
    margin = 2.7764451051977987 * sd / math.sqrt(len(values))
    return {"mean": mean, "sample_sd": sd, "n": len(values),
            "mean_95pct_t_ci": [mean-margin, mean+margin]}


def audit(runroot, output):
    checks, artifacts = {}, {}

    def remember(path):
        artifacts[path.relative_to(ROOT).as_posix()] = digest(path)

    source = BASE / "source"
    frozen = load(source / "manifest.json")
    records = csvrows(source / "ct_records.csv")
    assert digest(source / "ct_records.csv") == frozen["csv_sha256"]
    assert digest(source / "log_list.json") == frozen["log_list_sha256"]
    exact = []
    for request in frozen["requests"]:
        path = source / request["file"]
        assert digest(path) == request["sha256"]
        entries = load(path)["entries"]
        assert len(entries) == request["returned"]
        exact.extend(entry["leaf_input"] for entry in entries)
        remember(path)
    assert len(exact) == len(records) == frozen["entries"] == 512
    source_values = {}
    for i, (row, encoded) in enumerate(zip(records, exact)):
        assert int(row["ct_index"]) == i and row["leaf_input_base64"] == encoded
        raw = base64.b64decode(encoded, validate=True)
        value = hashlib.sha256(raw).digest()
        assert len(raw) == int(row["leaf_input_bytes"])
        assert value.hex() == row["value_hex"] == row["leaf_sha256"]
        assert row["slot_hex"] == value[:16].hex()
        source_values[int.from_bytes(value[:16], "big")] = value
    assert len(source_values) == 512
    checks["frozen_512_CT_records_exactly_match_downloaded_JSON_and_CSV"] = True
    defaults = [hashlib.sha256(b"\x02").digest()]
    for _ in range(128):
        defaults.append(parent(defaults[-1], defaults[-1]))
    current = {(1 << 128) + slot: hashlib.sha256(b"\x00" + value).digest()
               for slot, value in source_values.items()}
    nodes = dict(current)
    for level in range(128):
        current = {p: parent(current.get(2*p, defaults[level]), current.get(2*p+1, defaults[level]))
                   for p in {node // 2 for node in current}}
        nodes.update(current)
    pinned = nodes[1]
    snapshot = load(runroot / "publisher/snapshot.json")
    assert pinned.hex() == snapshot["trusted_experimental_root_hex"]
    assert snapshot["source_csv_sha256"] == digest(source / "ct_records.csv")
    assert (snapshot["n"], snapshot["N"], snapshot["m"], snapshot["D"], snapshot["height"]) == (512, 1022, 13, 17, 128)
    active = {node: value for node, value in nodes.items() if node > 1 and (node ^ 1) in nodes}
    assert len(active) == 1022
    checks["independent_domain_separated_SMT_root_matches_locally_pinned_root"] = True

    # Reconstruct node identities from each stored directory and check the raw
    # digest database. This does not call the publisher's layout/hash code.
    slots = sorted(source_values)
    for method in METHODS:
        public = runroot / "publisher" / method
        manifest = load(public / "server_manifest.json")
        raw = (public / manifest["metadata_file"]).read_bytes()
        slotraw = (public / manifest["slots_file"]).read_bytes()
        assert raw[:8] == b"TIFSMETA"
        height, n, colors = struct.unpack_from(">HII", raw, 8)
        assert (height, n) == (128, 512)
        assert [int.from_bytes(slotraw[i:i+16], "big") for i in range(0, len(slotraw), 16)] == slots
        expected_colors = {"first_fit": 13, "activebalance": 13, "nonempty_depth": 17, "full_cache": 1}[method]
        assert colors == expected_colors and manifest["method"] == method
        payloads = ({1: (public / manifest["cache_file"]).read_bytes()} if method == "full_cache"
                    else {sub["color"]: (public / sub["database_file"]).read_bytes() for sub in manifest["subdatabases"]})
        seen, offset = {}, 18
        for _ in range(colors):
            color, count = struct.unpack_from(">II", raw, offset)
            offset += 8
            assert len(payloads[color]) == 32 * count
            for position in range(count):
                left, right, level, flags, pos = struct.unpack_from(">QQHHI", raw, offset)
                offset += 24
                assert 0 <= left <= right < n and 0 <= level < height and flags == 0 and pos == position
                node = (((1 << height) + slots[left]) >> level) ^ 1
                assert node in active and node not in seen
                assert payloads[color][32*pos:32*(pos+1)] == active[node]
                needed = [rank for rank, slot in enumerate(slots)
                          if ((((1 << height) + slot) >> level) ^ 1) == node]
                assert needed == list(range(left, right+1))
                seen[node] = (color, pos)
        assert offset == len(raw) and set(seen) == set(active)
        for path in public.iterdir():
            if path.is_file():
                remember(path)
    checks["all_four_saved_directories_and_4088_stored_digests_match_independent_tree"] = True

    pinned_sources = load(runroot / "source_manifest.json")["sha256"]
    for relative, expected in pinned_sources.items():
        assert digest(ROOT / relative) == expected, relative
    assert digest(ROOT / "backend/simplepir/tifs_tcp_certificate_backend.go") == digest(ROOT / ".tools/simplepir/simplepir-main/eval/tifs_tcp_certificate_backend.go")
    checks["executed_source_binary_pins_match_current_canonical_and_eval_sources"] = True
    env, completion = load(runroot / "environment.json"), load(runroot / "completion.json")
    assert env["samples"] == 100 and env["repeats"] == 5 and env["warmup"] == 5 and env["gomaxprocs"] == 1
    assert completion["status"] == "complete" and completion["failed_pairs"] == 0
    rawruns, rawqueries = csvrows(runroot / "run_summary.csv"), csvrows(runroot / "query_measurements.csv")
    assert len(rawruns) == 20 and len(rawqueries) == 2000
    assert {(r["method"], int(r["repeat"])) for r in rawruns} == {(m, r) for m in METHODS for r in range(5)}
    checks["complete_4_methods_by_5_process_pairs_with_100_targets"] = True
    recomputed, proof_checks, recovered_checks, mutation_checks, raw_result_flags = [], 0, 0, 0, 0
    process_ids = set()
    for repeat in range(5):
        client_input_path = runroot / f"client_inputs/repeat{repeat}.json"
        client_input = load(client_input_path)
        schedule = load(runroot / f"client_inputs/repeat{repeat}_selection.json")
        rng = random.Random(202609102000 + repeat)
        selected = rng.sample(records, 100)
        order = list(METHODS)
        rng.shuffle(order)
        assert schedule["method_order"] == order
        expected_targets = [{"ct_index": int(r["ct_index"]), "leaf_input_base64": r["leaf_input_base64"]} for r in selected]
        assert client_input["targets"] == expected_targets
        assert len(set(t["ct_index"] for t in expected_targets)) == 100
        assert client_input["trusted_root_hex"] == pinned.hex()
        assert client_input["warmup"] == 5 and client_input["height"] == 128
        remember(client_input_path)
        for method in METHODS:
            run = runroot / method / f"repeat{repeat}"
            client, server = load(run / "client_result.json"), load(run / "server_result.json")
            commands = load(run / "commands.json")
            assert "-input" not in commands["server"] and "-manifest" not in commands["client"]
            assert commands["client"][commands["client"].index("-input")+1].replace("\\", "/").endswith(f"client_inputs/repeat{repeat}.json")
            assert client["client_pid"] != server["server_pid"]
            process_ids.update((client["client_pid"], server["server_pid"]))
            assert client["method"] == server["method"] == method
            qs = client["queries"]
            assert len(qs) == 100 and client["warmup_queries"] == 5
            assert [q["sample_index"] for q in qs] == list(range(100))
            assert [q["ct_index"] for q in qs] == [t["ct_index"] for t in expected_targets]
            expected_q = {"first_fit": 13, "activebalance": 13, "nonempty_depth": 17, "full_cache": 0}[method]
            assert {q["logical_queries"] for q in qs} == {expected_q}
            assert len({(q["upload_wire_bytes"], q["download_wire_bytes"]) for q in qs}) == 1
            batches = 0 if method == "full_cache" else 105
            assert server["query_batches_including_warmup"] == len(server["server_answer_ms_including_warmup"]) == batches
            assert server["total_read_wire_bytes"] == client["bootstrap_upload_wire_bytes"] + batches*qs[0]["upload_wire_bytes"]
            assert server["total_written_wire_bytes"] == client["bootstrap_download_wire_bytes"] + batches*qs[0]["download_wire_bytes"]
            for q, target in zip(qs, expected_targets):
                value = hashlib.sha256(base64.b64decode(target["leaf_input_base64"], validate=True)).digest()
                slot = int.from_bytes(value[:16], "big")
                expected = {level: active[(((1 << 128)+slot) >> level)^1]
                            for level in range(128) if ((((1 << 128)+slot) >> level)^1) in active}
                retained = q["recovered_siblings"]
                assert len(retained) == len(expected) and len({x["level"] for x in retained}) == len(expected)
                assert {x["level"] for x in retained} == set(expected)
                proof = defaults[:128]
                for entry in retained:
                    recovered = bytes.fromhex(entry["digest_hex"])
                    assert len(recovered) == 32 and recovered == expected[entry["level"]]
                    proof[entry["level"]] = recovered
                    recovered_checks += 1
                assert root_from_proof(slot, value, proof) == pinned
                proof_checks += 1
                level = min(expected)
                bad = proof.copy()
                bad[level] = bytes([bad[level][0] ^ 1]) + bad[level][1:]
                assert root_from_proof(slot, value, bad) != pinned
                mutation_checks += 1
                assert q["valid_root"] is True and q["corruption_rejected"] is True
                raw_result_flags += 1
                summed = sum(q[k] for k in ["record_hash_and_routing_ms", "query_generation_ms", "serialize_transport_answer_ms", "decode_ms", "assembly_rootcheck_ms"])
                assert q["end_to_end_ms"] + 1e-6 >= summed
                csv_q = [r for r in rawqueries if r["method"] == method and int(r["repeat"]) == repeat and int(r["sample_index"]) == q["sample_index"]]
                assert len(csv_q) == 1
                for field, value_q in q.items():
                    if field == "recovered_siblings":
                        continue  # nested raw evidence may intentionally be absent from the flat CSV
                    if isinstance(value_q, bool):
                        assert csv_q[0][field].lower() == str(value_q).lower()
                    else:
                        close(csv_q[0][field], value_q)
            server_answers = server["server_answer_ms_including_warmup"][5:]
            row = {"method": method, "repeat": repeat, "mean_e2e_ms": statistics.mean(q["end_to_end_ms"] for q in qs),
                   "bootstrap_ms": client["bootstrap_ms"],
                   "bootstrap_total_wire_bytes": client["bootstrap_upload_wire_bytes"]+client["bootstrap_download_wire_bytes"],
                   "mean_online_wire_bytes": qs[0]["upload_wire_bytes"]+qs[0]["download_wire_bytes"],
                   "client_peak_rss_bytes": client["client_peak_rss_bytes"], "server_peak_rss_bytes": server["server_peak_rss_bytes"],
                   "mean_query_ms": statistics.mean(q["query_generation_ms"] for q in qs),
                   "mean_server_answer_ms": statistics.mean(server_answers) if server_answers else 0,
                   "mean_decode_ms": statistics.mean(q["decode_ms"] for q in qs),
                   "mean_route_ms": statistics.mean(q["record_hash_and_routing_ms"] for q in qs),
                   "mean_verify_ms": statistics.mean(q["assembly_rootcheck_ms"] for q in qs)}
            original = [r for r in rawruns if r["method"] == method and int(r["repeat"]) == repeat]
            assert len(original) == 1 and int(original[0]["proofs_verified"]) == 100
            for field, val in row.items():
                if field != "method":
                    close(val, original[0][field])
            recomputed.append(row)
            for name in ["client_result.json", "server_result.json", "commands.json"]:
                remember(run / name)
    checks.update({"same_randomized_100_distinct_targets_and_method_schedule_per_repeat": True,
                   "fresh_distinct_client_server_process_roles_and_command_inputs": True,
                   "2000_retained_proofs_independently_reverified_from_actual_recovered_digests": proof_checks == 2000,
                   "all_retained_digests_match_the_corresponding_raw_server_database": True,
                   "2000_independent_single_digest_corruptions_rejected": mutation_checks == 2000,
                   "fixed_8q_query_width_and_online_socket_shape": True,
                   "all_double_ended_socket_totals_match_including_5_warmups": True,
                   "raw_query_CSV_and_20_run_means_match_JSON_evidence": True,
                   "online_intervals_cover_listed_phases": True})
    supplied = load(runroot / "summary.json")["groups"]
    aggregated = {}
    for method in METHODS:
        selected = [r for r in recomputed if r["method"] == method]
        aggregated[method] = {}
        for field in supplied[method]:
            result = stats([r[field] for r in selected])
            close(result["mean"], supplied[method][field]["mean"])
            close(result["sample_sd"], supplied[method][field]["sample_sd"])
            assert supplied[method][field]["n"] == 5
            aggregated[method][field] = result
    checks["reported_means_and_sample_SD_use_five_process_pair_means"] = True
    paired = {}
    ab = {r["repeat"]: r for r in recomputed if r["method"] == "activebalance"}
    for method in (m for m in METHODS if m != "activebalance"):
        controls = {r["repeat"]: r for r in recomputed if r["method"] == method}
        ratios = [controls[r]["mean_e2e_ms"]/ab[r]["mean_e2e_ms"] for r in range(5)]
        paired[method+"_over_activebalance"] = {"ratios": ratios, **stats(ratios)}
    for path in [source/"manifest.json", source/"ct_records.csv", runroot/"source_manifest.json", runroot/"completion.json", runroot/"run_summary.csv", runroot/"query_measurements.csv", runroot/"summary.json", runroot/"publisher/snapshot.json"]:
        remember(path)
    report = {"status": "pass" if all(checks.values()) else "fail", "audit_pass": all(checks.values()), "schema": 1, "audited_run_root": runroot.relative_to(ROOT).as_posix(),
              "audit_type": "Independent read-only source/data audit; no backend launch or timing experiment",
              "checks": checks, "proofs_reverified": proof_checks, "recovered_sibling_digests_reverified": recovered_checks,
              "independent_corruptions_rejected": mutation_checks, "execution_root_flags_checked": raw_result_flags,
              "experimental_SMT_root_hex": pinned.hex(), "all_nonempty_SMT_nodes": len(nodes),
              "proof_byte_source": "Each client_result.json queries[].recovered_siblings, copied from the actual assembled proof after the timed interval; matched to saved raw server database records and independently recomputed CT-derived tree",
              "root_source": "Independent SHA256 reconstruction from 512 frozen raw CT leaf_input records, checked against publisher/snapshot.json and all five locally pinned client inputs; not the native CT log root",
              "final_independent_process_pairs": 20, "final_measured_proof_count": 2000, "development_runs_pooled": False,
              "unique_process_ids_observed": len(process_ids), "statistics": aggregated, "paired_processing_ratios": paired,
              "code_source_pins": pinned_sources, "artifact_sha256": artifacts,
              "limitations": ["Locally pinned experimental SMT root; no native CT-root/inclusion, certificate-chain or log-consistency authentication",
                              "TCP loopback application bytes include framing, not TCP/IP headers or retransmission bytes",
                              "Read separation was inspected in code and recorded commands, not enforced by an OS sandbox or syscall-trace experiment",
                              "No malicious-server, manifest-authentication, freshness or application anti-replay guarantee",
                              "Recovered-evidence retention occurs after the per-proof timer but may affect peak RSS and later garbage collection",
                              "Server setup_ms excludes bootstrap construction/file reading; client default-chain precomputation is outside bootstrap and per-proof timings"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["audit_pass", "audited_run_root", "proofs_reverified", "recovered_sibling_digests_reverified", "independent_corruptions_rejected", "experimental_SMT_root_hex"]}, indent=2))
    for method in METHODS:
        print(method, json.dumps(aggregated[method]["mean_e2e_ms"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=BASE/"runs_verified_evidence")
    parser.add_argument("--output", type=Path, default=ROOT/"manuscripts/tifs/revision_20260910/generated/ct_tcp_independent_audit.json")
    args = parser.parse_args()
    try:
        audit(args.run_root, args.output)
    except Exception as exc:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"status": "fail", "audit_pass": False,
                                          "audited_run_root": str(args.run_root),
                                          "error_type": type(exc).__name__, "error": str(exc)}, indent=2)+"\n", encoding="utf-8")
        raise
