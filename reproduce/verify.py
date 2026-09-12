#!/usr/bin/env python3
"""Restore and independently verify frozen main observations in a fresh directory."""
import argparse
import shutil
import sys
from common import ROOT, EXTERNAL, SIMPLE, dump, ensure_output, invoke, module, read, sha


def stage(source, destination):
    # Copy only audit inputs and observations. Omitted per-process inputs are
    # restored below, after checking their originally recorded SHA-256 values.
    shutil.copytree(source / "inputs", destination / "inputs",
                    ignore=shutil.ignore_patterns("__pycache__", "build", "java_build", "*.exe"))
    shutil.copytree(source / "runs", destination / "runs",
                    ignore=shutil.ignore_patterns("input.json", "__pycache__"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New directory; existing directories are refused")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Do not use python -O: the original auditors contain assertions")
    output = ensure_output(args.output)
    evidence = output / "evidence" / "examples"
    reports = {}
    primary = {}
    for backend, directory, restorer, analyzer in [
        ("vbpir", EXTERNAL, "restore_external_run_inputs_20260911", "analyze_external_extension_20260911"),
        ("simplepir", SIMPLE, "restore_simplepir_run_inputs_20260911", "analyze_simplepir_extension_20260911"),
    ]:
        source, staged = ROOT / "examples" / directory, evidence / directory
        print(f"Copying {backend} audit inputs and observations to {staged}", flush=True)
        stage(source, staged)
        restored = module(restorer).reconstruct(staged)
        analysis = output / "analysis" / backend
        argv = ["--runs", staged / "runs", "--output", analysis]
        if backend == "simplepir":
            argv += ["--input-root", staged / "inputs", "--vbpir-root", evidence / EXTERNAL]
        invoke(analyzer, argv)
        current = read(analysis / "INDEPENDENT_VERIFICATION.json")
        expected = read(source / "analysis" / "INDEPENDENT_VERIFICATION.json")
        # Compare scientific/audit outcomes. Paths and the verifier's own source
        # hash may legitimately differ in a redistributed artifact.
        keys = ["status", "process_results_verified", "measured_proofs_verified",
                "proofs_including_warmups_verified", "complete_requested_experiment"]
        if backend == "simplepir":
            keys += ["failed_process_results_audited", "all_executed_outputs_audited",
                     "complete_process_measured_proofs", "partial_process_measured_proofs"]
        for key in keys:
            if current.get(key) != expected.get(key):
                raise ValueError(f"{backend}: frozen verification changed for {key}: "
                                 f"{current.get(key)!r} != {expected.get(key)!r}")
        if backend == "vbpir" and current["status"] != "passed":
            raise ValueError("Frozen VBPIR evidence did not fully verify")
        if backend == "simplepir" and not current.get("all_executed_outputs_audited"):
            raise ValueError("Some frozen SimplePIR outputs could not be audited")
        reports[backend] = {key: current[key] for key in keys}
        reports[backend]["run_inputs_restored"] = restored
        reports[backend]["source_schedule_sha256"] = sha(source / "runs" / "schedule.json")
        selected_cases = {"uniform_n1000", "uniform_n10000", "uniform_n100000"}
        if backend == "vbpir":
            selected_cases |= {"complete_h10", "complete_h14"}
        rows = [row for row in read(analysis / "results.json")["process_means"]
                if row["case"] in selected_cases]
        if len(rows) != 36 or any(row["proofs"] != 10 for row in rows):
            raise ValueError(f"{backend}: current main evidence selection is incomplete")
        primary[backend] = {"complete_processes": len(rows),
                            "measured_proofs": sum(row["proofs"] for row in rows),
                            "warmups": len(rows) * current["source_run_configuration"]["warmup"]}
    dump(output / "verification_summary.json", {
        "status": "verified_frozen_evidence", "native_backend_executed": False,
        "observations": reports,
        "current_main_selection": primary,
        "scope": "Recorded recovered bytes, hashes, schedules, accounting and authentication are audited; cryptographic operations and timings are not rerun."})
    print(f"Verified frozen evidence. Summary: {output / 'verification_summary.json'}")


if __name__ == "__main__":
    main()
