#!/usr/bin/env python3
"""Run the original native schedules into a fresh output tree, then audit them."""
import argparse
from pathlib import Path
import sys
from common import ROOT, CASES, EXTERNAL, SIMPLE, dump, ensure_output, invoke, linux_required, module, read, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True, help="Directory from build_native.py")
    parser.add_argument("--output", required=True, help="New directory; existing directories are refused")
    parser.add_argument("--backend", choices=["both", "simplepir", "vbpir"], default="both")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--cases", nargs="+", choices=CASES,
                        help="Default: uniform_n1000 for smoke; all seven cases for full")
    parser.add_argument("--methods", nargs="+", choices=["ab", "pbc", "flat", "first_fit"],
                        help="SimplePIR only; default is all four methods")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per independent process")
    args = parser.parse_args()
    linux_required()
    if not __debug__:
        parser.error("Do not use python -O")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if args.methods and args.backend == "vbpir":
        parser.error("--methods applies to SimplePIR only")
    output = ensure_output(args.output)
    manifest = read(args.build.resolve() / "build_manifest.json")
    cases = args.cases or (["uniform_n1000"] if args.mode == "smoke" else CASES)
    if len(cases) != len(set(cases)):
        parser.error("Duplicate cases are not allowed")
    selected = ["vbpir", "simplepir"] if args.backend == "both" else [args.backend]
    summary = {}
    for backend in selected:
        binary_record = manifest["binaries"][backend]
        binary = Path(binary_record["path"])
        if sha(binary) != binary_record["sha256"]:
            raise ValueError(f"Built binary changed: {binary}")
        runner = "run_external_extension_20260911" if backend == "vbpir" else "run_simplepir_extension_20260911"
        argv = ["--binary", str(binary), "--output", str(output / backend / "runs"),
                "--timeout", str(args.timeout), "--cases", *cases]
        if args.mode == "smoke":
            argv.append("--smoke")
        if backend == "simplepir" and args.methods:
            argv += ["--methods", *args.methods]
        # Import the unmodified runner so its existing configuration, seed,
        # scheduling, persistence and failure semantics remain authoritative.
        original_argv = sys.argv
        try:
            sys.argv = [runner, *argv]
            module(runner).main()
        finally:
            sys.argv = original_argv
        analyzer = "analyze_external_extension_20260911" if backend == "vbpir" else "analyze_simplepir_extension_20260911"
        analysis = output / backend / "analysis"
        analyzer_args = ["--runs", output / backend / "runs", "--output", analysis]
        if backend == "simplepir":
            analyzer_args += ["--input-root", ROOT / "examples" / SIMPLE / "inputs",
                              "--vbpir-root", ROOT / "examples" / EXTERNAL]
        invoke(analyzer, analyzer_args)
        audit = read(analysis / "INDEPENDENT_VERIFICATION.json")
        if backend == "vbpir":
            valid = audit.get("complete_requested_experiment") is True
        else:
            valid = audit.get("all_executed_outputs_audited") is True
        summary[backend] = {"status": audit["status"], "all_outputs_audited": valid,
                            "completion": read(output / backend / "runs" / "completion.json")}
        dump(output / "rerun_summary.json", {
            "mode": args.mode, "cases": cases, "backends": summary,
            "timings_are_new_observations": True,
            "full_original_case_order": cases == CASES,
            "scope": "New process measurements with frozen inputs and original runners; no claim that cryptographic randomness, binary hashes or timings match frozen observations."})
        if not valid:
            raise RuntimeError(f"{backend}: incomplete or invalid fresh run; inspect retained outputs")
    print(f"Native rerun and audit complete: {output / 'rerun_summary.json'}")


if __name__ == "__main__":
    main()
