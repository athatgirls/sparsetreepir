"""Smoke verification for the separate 2026-09-10 real-record SimplePIR runner.

Run this in WSL from the workspace with a usable numpy environment. The checks
exercise real PIR, record reassembly, the independent SMT verifier, warmup
exclusion, repeated-file setup sharing, and malformed-index rejection.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from tifs_revision_smt import build_layout, export_manifest, reconstruct_proof, verify_proof


def runner_command(binary: Path, manifest: Path, output: Path | None = None) -> list[str]:
    """Also permit Windows Python to invoke the Linux runner through WSL."""
    def native_argument(path: Path) -> str:
        if os.name != "nt":
            return str(path)
        resolved = path.resolve()
        return f"/mnt/{resolved.drive[0].lower()}{resolved.as_posix()[2:]}"
    prefix = (["wsl", "-d", "Ubuntu-24.04", "--", binary.as_posix()]
              if os.name == "nt" else [str(binary)])
    return prefix + (["-output", native_argument(output)] if output else []) + [native_argument(manifest)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name, height, slots in [("real_four", 128, [0, 1, 9, 255]), ("singleton", 128, [7])]:
        layout = build_layout(height, slots)
        manifest = export_manifest(layout, slots, args.output_dir/name, seed=90210, warmup_queries=2)
        output_path = manifest.parent / "backend_result.json"
        command = runner_command(args.binary, manifest, output_path)
        run = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120)
        (manifest.parent/"runner_stderr.txt").write_text(run.stderr, encoding="utf-8")
        if run.returncode:
            raise RuntimeError(f"backend exited {run.returncode}: {run.stderr}")
        data = json.loads(output_path.read_text())
        context = json.loads((manifest.parent/"client_context.json").read_text())
        assert data["warmup_queries"] == 2
        assert len(data["targets"]) == len(slots) == data["completed_queries"]
        assert data["gomaxprocs"] == 1
        expected_public = sum(p["matrix_columns_m"] * p["lwe_dimension_n"] * 4 * 8
                              for p in data["parameters"])
        assert data["setup"]["public_shared_state_bytes"] == expected_public
        assert data["process_peak_rss_bytes"] > 0
        for row, target in zip(data["targets"], context["targets"]):
            recovered = {x["color"]: bytes.fromhex(x["record_hex"]) for x in row["recovered_records"]}
            slot = int(target["slot_hex"], 16)
            proof = reconstruct_proof(layout, slot, recovered, target["selection"])
            expected = [bytes.fromhex(x) for x in target["expected_proof_hex"]]
            assert proof == expected
            assert verify_proof(height, slot, bytes.fromhex(target["value_hex"]), proof, bytes.fromhex(target["expected_root_hex"]))
            assert row["chunk_checks_passed"]
            assert row["chunk_query_count"] == 8 * layout.width
            assert row["sample_index"] == target["sample_index"]
        results.append({"case": name, "targets": len(slots), "width": layout.width, "root_checks_passed": len(slots), "warmup_excluded": True})

    # Shared file slots must be initialized once but still execute two queries.
    shared_dir = args.output_dir/"shared_file"
    shared_dir.mkdir(exist_ok=True)
    records = [bytes(range(32)), bytes(reversed(range(32)))]
    (shared_dir/"records.bin").write_bytes(b"".join(records))
    manifest_obj = {"scheme": "flat_cache_smoke", "height": 2, "width": 2, "active_nodes": 2, "query_samples": 2, "warmup_queries": 1,
                    "subdatabases": [{"color": c, "records": 2, "record_bytes": 32, "database_file": "records.bin", "query_indices": [c-1, 2-c]} for c in (1, 2)]}
    manifest_path = shared_dir/"manifest.json"
    manifest_path.write_text(json.dumps(manifest_obj), encoding="utf-8")
    run = subprocess.run(runner_command(args.binary, manifest_path), text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120, check=True)
    data = json.loads(run.stdout)
    (shared_dir/"backend_result.json").write_text(run.stdout, encoding="utf-8")
    (shared_dir/"runner_stderr.txt").write_text(run.stderr, encoding="utf-8")
    assert data["unique_database_files"] == 1 and data["stored_records_with_padding"] == 2
    p = data["parameters"][0]
    assert data["setup"]["public_shared_state_bytes"] == p["matrix_columns_m"] * p["lwe_dimension_n"] * 4 * 8
    assert data["process_peak_rss_bytes"] > 0
    for row in data["targets"]:
        assert row["chunk_query_count"] == 16
        for item in row["recovered_records"]:
            assert bytes.fromhex(item["record_hex"]) == records[item["query_index"]]
    results.append({"case": "shared_file", "targets": 2, "unique_initializations": 1, "records_checked": 4})
    manifest_obj["subdatabases"][0]["query_indices"][0] = 999
    bad_path = shared_dir/"bad_index_manifest.json"
    bad_path.write_text(json.dumps(manifest_obj), encoding="utf-8")
    bad = subprocess.run(runner_command(args.binary, bad_path), text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=120)
    assert bad.returncode != 0 and "out of range" in bad.stderr and not bad.stdout.strip()
    (shared_dir/"bad_index_stderr.txt").write_text(bad.stderr, encoding="utf-8")
    results.append({"case": "out_of_range_index", "rejected": True, "exit_code": bad.returncode})
    report = {"status": "passed", "cases": results, "binary": str(args.binary), "scope": "smoke correctness, not publishable timing sample"}
    (args.output_dir/"SMOKE_VALIDATION.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
