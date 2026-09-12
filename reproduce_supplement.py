#!/usr/bin/env python3
"""Verify frozen supplementary proofs and theory with outputs in a new directory."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def new_output(path):
    output = path.expanduser().resolve()
    require(output != ROOT and output not in ROOT.parents, "Choose a dedicated new output directory")
    # Existing source/evidence directories are protected; designated generated
    # output roots and a new top-level output directory are permitted.
    allowed = {".reproduce", "output", "audit-output"}
    for directory in ROOT.iterdir():
        if directory.is_dir() and directory.name not in allowed:
            require(output != directory and directory not in output.parents,
                    "Output must be outside the checked-in source/evidence directories")
    output.mkdir(parents=True, exist_ok=False)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing directories are refused")
    parser.add_argument("--checks", choices=["all", "legacy", "theory"], default="all",
                        help="all: both the earlier six-workload proof audit and the three theory checks")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Do not use Python -O; original verifiers contain assertions")
    output = new_output(args.output)
    sys.path.insert(0, str(ROOT / "scripts"))
    summary = {"status": "passed", "selected_checks": args.checks,
               "native_backend_executed": False, "new_performance_measurements": False,
               "recorded_executable_authentication": "not performed; recorded executables are omitted",
               "checks": {}, "source_sha256": {}}
    sources = [Path(__file__).resolve()]

    if args.checks in ["all", "legacy"]:
        script = ROOT / "scripts/analyze_tifs_verified_results_20260910.py"
        sources.append(script)
        destination = output / "legacy"
        destination.mkdir()
        print("Auditing 18,000 recorded proofs from the earlier six-workload experiment...", flush=True)
        with (destination / "verifier.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-B", str(script),
                            "--generated", str(destination / "generated"),
                            "--notes", str(destination / "notes")],
                           cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        result = read(destination / "generated/verified_backend_summary.json")
        require(result["audit_status"] == "passed", "Earlier workload audit failed")
        require(result["counts"]["root_checks"] == result["counts"]["tamper_rejections"] == 18000,
                "Earlier workload audit count changed")
        summary["checks"]["earlier_six_workloads"] = {
            "status": result["audit_status"], "processes": 180, **result["counts"]}

    if args.checks in ["all", "theory"]:
        print("Checking 3,438 frozen joint-bound rows, wrapper proofs and five residual states...", flush=True)
        theory_source = ROOT / "examples/tifs_contribution_gate_20260910/theory"
        joint_source = theory_source / "verify_joint_linear.py"
        wrapper_source = theory_source / "verify_wrapping_family.py"
        five_source = ROOT / "scripts/verify_layout_transfer_theory_20260910.py"
        sources.extend([joint_source, wrapper_source, five_source])
        with (output / "theory_verifier.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log):
            joint = load("verify_joint_linear", joint_source)
            joint.OUT = output / "joint"
            joint.OUT.mkdir()
            joint.main()

            wrapper = load("verify_wrapping_family", wrapper_source)
            wrapper.OUT = output / "wrapper"
            wrapper.OUT.mkdir()
            # The original wrapper verifier hashes this helper beside its
            # outputs; copy the exact source, without changing its implementation.
            shutil.copy2(joint_source, wrapper.OUT / "verify_joint_linear.py")
            wrapper.main()

            five = load("verify_layout_transfer_theory_20260910", five_source)
            source_analysis = five.OUT / "five_case_analysis.json"
            five.OUT = output / "five_states"
            five.OUT.mkdir()
            shutil.copy2(source_analysis, five.OUT / "five_case_analysis.json")
            five.main()

        joint_result = read(joint.OUT / "frozen_3438_consistency.json")
        wrapper_result = read(wrapper.OUT / "wrapping_family_verification.json")
        five_result = read(five.OUT / "independent_verification.json")
        require(joint_result["status"] == wrapper_result["status"] == five_result["status"] == "pass",
                "A supplementary theory check failed")
        require(joint_result["frozen_rows_checked"] == 3438 and joint_result["mismatches"] == 0,
                "Frozen joint-bound check count changed")
        require(wrapper_result["actual_smt_proofs"] == 109 and five_result["actual_target_proofs"] == 222,
                "Supplementary proof count changed")
        summary["checks"].update({
            "joint_bound": {"status": "passed", "frozen_rows_checked": 3438, "mismatches": 0},
            "wrapper_family": {"status": "passed", "proofs_verified": 109,
                               "fixed_wrapper_counts": wrapper_result["selected_wrapper_counts"]},
            "five_states": {"status": "passed", "proofs_verified": 222,
                            "projected_inequalities": five_result["independent_joint_projection_constraints"]}})

    for source in sources:
        summary["source_sha256"][source.relative_to(ROOT).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    summary["scope"] = "Frozen recovered-byte authentication and explicit theory checks; no exact census, backend execution, benchmark rerun or replacement of checked-in evidence."
    (output / "supplement_verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "checks": summary["checks"]}, indent=2))


if __name__ == "__main__":
    main()
