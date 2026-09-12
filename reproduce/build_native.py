#!/usr/bin/env python3
"""Build the included adapters, with a pinned local SEAL 4.3.2 installation."""
import argparse
from pathlib import Path
import shutil
import subprocess
from common import ROOT, EXTERNAL, SIMPLE, dump, ensure_output, linux_required, read, sha, thread_environment

SEAL_REPO = "https://github.com/microsoft/SEAL.git"
SEAL_COMMIT = "e3476fad1d5bb5e5222c51a551b5a4d7e2cb4f91"
SIMPLE_COMMIT = "e9020b03bf2872c75b8954e749e32408b5db87ed"
TREE_COMMIT = "930063c5aefc441244abb4890fdf35383f3aa956"


def verify_sources(backend):
    omitted = []
    if backend == "simplepir":
        source = ROOT / "examples" / SIMPLE / "backend"
        manifest = read(source / "source_manifest.json")
        if manifest["commit"] != SIMPLE_COMMIT:
            raise ValueError("Unexpected SimplePIR source pin")
        checks = {source / "upstream" / "simplepir" / x["path"]: x["sha256"] for x in manifest["files"]}
    else:
        source = ROOT / "examples" / EXTERNAL / "native_adapter"
        manifest = read(source / "source_manifest.json")
        if manifest["commit"] != TREE_COMMIT:
            raise ValueError("Unexpected TreePIR/VBPIR source pin")
        checks = {source / "vendor" / name: digest for name, digest in manifest["copied_sha256"].items()}
    for path, expected in checks.items():
        # The original ZIP packager excluded *.out, including this empty
        # upstream profiling output. It is not compiled or read by the backend.
        if (backend == "simplepir" and path == source / "upstream/simplepir/pir/simple-cpu.out"
                and not path.exists() and expected == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"):
            omitted.append("pir/simple-cpu.out (empty profiling output omitted by source archive)")
            continue
        if sha(path) != expected:
            raise ValueError(f"Vendored source SHA-256 mismatch: {path}")
    return source, len(checks) - len(omitted), omitted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New build directory")
    parser.add_argument("--backend", choices=["both", "simplepir", "vbpir"], default="both")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--seal-prefix", type=Path, help="Use an existing SEAL 4.3.2 prefix instead of fetching/building it")
    args = parser.parse_args()
    linux_required()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    output = ensure_output(args.output)
    env = thread_environment()
    env.update(GOCACHE=str(output / "cache" / "go-build"), GOMODCACHE=str(output / "cache" / "go-mod"))
    commands, binaries, pins = [], {}, {}

    def run(command, cwd=None):
        command = list(map(str, command))
        commands.append({"argv": command, "cwd": str(cwd) if cwd else None})
        print("+", " ".join(command), flush=True)
        subprocess.run(command, check=True, cwd=cwd, env=env)

    selected = ["simplepir", "vbpir"] if args.backend == "both" else [args.backend]
    for backend in selected:
        source, count, omitted = verify_sources(backend)
        pins[backend] = {"files_hash_checked": count,
                         "omitted_non_source_manifest_entries": omitted,
                         "commit": SIMPLE_COMMIT if backend == "simplepir" else TREE_COMMIT}
        if backend == "simplepir":
            copied = output / "simplepir-source"
            shutil.copytree(source, copied, ignore=shutil.ignore_patterns(
                "build", "recorded_bin", "functional", "__pycache__", ".git"))
            binary = output / "bin" / "simplepir_proof_bench"
            binary.parent.mkdir(parents=True, exist_ok=True)
            run(["go", "build", "-trimpath", "-o", binary, "."], copied)
            run(["go", "test", "-count=1", "."], copied)
        else:
            if args.seal_prefix:
                prefix = args.seal_prefix.expanduser().resolve()
            else:
                seal_source, seal_build = output / "seal-source", output / "seal-build"
                prefix = output / "seal-install"
                run(["git", "init", seal_source])
                run(["git", "-C", seal_source, "fetch", "--depth=1", SEAL_REPO, SEAL_COMMIT])
                run(["git", "-C", seal_source, "checkout", "--detach", "FETCH_HEAD"])
                actual = subprocess.check_output(["git", "-C", str(seal_source), "rev-parse", "HEAD"], text=True).strip()
                if actual != SEAL_COMMIT:
                    raise ValueError("SEAL checkout does not match the pinned commit")
                run(["cmake", "-S", seal_source, "-B", seal_build, "-DCMAKE_BUILD_TYPE=Release",
                     f"-DCMAKE_INSTALL_PREFIX={prefix}", "-DSEAL_BUILD_DEPS=OFF", "-DSEAL_USE_MSGSL=OFF",
                     "-DSEAL_USE_ZLIB=ON", "-DSEAL_USE_ZSTD=ON", "-DSEAL_USE_INTEL_HEXL=OFF",
                     "-DSEAL_BUILD_EXAMPLES=OFF", "-DSEAL_BUILD_TESTS=OFF", "-DSEAL_BUILD_BENCH=OFF"])
                run(["cmake", "--build", seal_build, "--parallel", args.jobs])
                run(["cmake", "--install", seal_build])
            configs = list(prefix.glob("lib*/cmake/SEAL-4.3/SEALConfig.cmake"))
            if len(configs) != 1:
                raise ValueError(f"Expected one SEAL 4.3 configuration under {prefix}")
            # CMake checks the full version and usable dependency targets.
            probe = output / "seal-version-check"
            probe.mkdir()
            (probe / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.22)\nproject(seal_version_check LANGUAGES CXX)\n"
                "find_package(SEAL 4.3.2 EXACT CONFIG REQUIRED)\n", encoding="utf-8")
            run(["cmake", "-S", probe, "-B", probe / "build", f"-DSEAL_DIR={configs[0].parent}"])
            native_build = output / "vbpir-build"
            run(["cmake", "-S", source, "-B", native_build, "-DCMAKE_BUILD_TYPE=Release",
                 f"-DSEAL_DIR={configs[0].parent}"])
            run(["cmake", "--build", native_build, "--parallel", args.jobs])
            binary = native_build / "serialized_proof_bench"
            pins["seal"] = {"version": "4.3.2", "repository": SEAL_REPO,
                            "commit": SEAL_COMMIT if not args.seal_prefix else None,
                            "source": "existing prefix (version checked)" if args.seal_prefix else "pinned official Git commit"}
        binaries[backend] = {"path": str(binary), "sha256": sha(binary)}
    dump(output / "build_manifest.json", {"binaries": binaries, "pins": pins, "commands": commands})
    print(f"Native build manifest: {output / 'build_manifest.json'}")


if __name__ == "__main__":
    main()
