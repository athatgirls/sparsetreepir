from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced,
    structural_max_bucket_lower_bound,
)
from run_lwe_pir_backend_experiment import pruned_treepir_h_indexes
from run_sparse_smt_pir_backend_experiment import build_color_indexes


RECORD_BYTES = 32


@dataclass
class SchemeLayout:
    name: str
    indexes: Dict[int, List[Tuple[int, int, int]]]
    width: int
    stored_nodes: int
    lower_bound: int


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def parse_float_list(raw: str) -> List[float]:
    values = [float(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("float list cannot be empty")
    return values


def ensure_subst_drive(drive: str, target: Path) -> Path:
    drive = drive.rstrip(":").upper()
    target = target.resolve()
    subprocess.run(["cmd", "/c", "subst", f"{drive}:", "/D"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["cmd", "/c", "subst", f"{drive}:", str(target)], check=True)
    return Path(f"{drive}:/")


def simplepir_environment(workspace_drive: Path) -> Tuple[Path, Path, Dict[str, str]]:
    if os.name != "nt":
        workspace = workspace_drive.resolve()
        simplepir_root = workspace / ".tools" / "simplepir" / "simplepir-main"
        runner = simplepir_root / "eval" / "smt_full_backend.go"
        go_path = shutil.which("go")
        gcc_path = shutil.which("gcc")
        missing = []
        if go_path is None:
            missing.append("go on PATH")
        if gcc_path is None:
            missing.append("gcc on PATH")
        for path in [simplepir_root / "pir" / "simple_pir.go", runner]:
            if not path.exists():
                missing.append(str(path))
        if missing:
            raise SystemExit(
                "Missing Linux SimplePIR backend dependencies:\n"
                + "\n".join(missing)
                + "\nRun scripts/setup_linux_experiment_deps.sh first."
            )
        env = os.environ.copy()
        env.setdefault("GOCACHE", str(workspace / ".tools" / "gocache"))
        env.setdefault("GOMODCACHE", str(workspace / ".tools" / "gomodcache"))
        return simplepir_root, Path(go_path), env

    w64_bin = workspace_drive / ".tools" / "w64devkit113" / "w64devkit" / "bin"
    go_bin = workspace_drive / ".tools" / "go119" / "go" / "bin"
    simplepir_root = workspace_drive / ".tools" / "simplepir" / "simplepir-main"
    runner = simplepir_root / "eval" / "smt_full_backend.go"

    required = [
        w64_bin / "gcc.exe",
        go_bin / "go.exe",
        simplepir_root / "pir" / "simple_pir.go",
        runner,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(
            "Missing SimplePIR full-backend toolchain files:\n" + "\n".join(missing)
        )

    env = os.environ.copy()
    env["PATH"] = f"{w64_bin};{go_bin};" + env.get("PATH", "")
    env["GOCACHE"] = str(workspace_drive / ".tools" / "gocache119")
    env["GOMODCACHE"] = str(workspace_drive / ".tools" / "gomodcache119")
    env["CC"] = str(w64_bin / "gcc.exe")
    env["COMPILER_PATH"] = str(w64_bin)
    return simplepir_root, go_bin / "go.exe", env


def targets_from_indexes(
    indexes: Dict[int, List[Tuple[int, int, int]]],
    occupied_leaves: Sequence[int],
    leaf_heap_index: int,
    width: int,
    rng: random.Random,
) -> List[int]:
    rank = occupied_leaves.index(leaf_heap_index)
    targets: List[int] = []
    for color in range(1, width + 1):
        entries = indexes.get(color, [])
        if not entries:
            targets.append(0)
            continue
        lefts = [left for left, _, _ in entries]
        pos = bisect.bisect_right(lefts, rank) - 1
        if pos >= 0:
            left, right, _ = entries[pos]
            if left <= rank <= right:
                targets.append(pos)
                continue
        targets.append(rng.randrange(len(entries)))
    return targets


def write_manifest(
    layout: SchemeLayout,
    height: int,
    active_nodes: int,
    occupied: Sequence[int],
    sampled_leaves: Sequence[int],
    seed: int,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed * 101 + layout.width)
    dummy_rng = random.Random(seed * 103 + layout.width)

    target_lists = [
        targets_from_indexes(layout.indexes, occupied, leaf, layout.width, dummy_rng)
        for leaf in sampled_leaves
    ]

    subdatabases: List[Dict[str, object]] = []
    for color in range(1, layout.width + 1):
        entries = layout.indexes.get(color, [])
        db_path = output_dir / f"color_{color:02d}.bin"
        records = rng.integers(0, 256, size=(len(entries), RECORD_BYTES), dtype=np.uint8)
        db_path.write_bytes(records.tobytes())
        subdatabases.append(
            {
                "color": color,
                "records": len(entries),
                "record_bytes": RECORD_BYTES,
                "database_file": db_path.name,
                "query_indices": [targets[color - 1] for targets in target_lists],
            }
        )

    manifest = {
        "scheme": layout.name,
        "height": height,
        "width": layout.width,
        "active_nodes": active_nodes,
        "stored_nodes": layout.stored_nodes,
        "lower_bound": layout.lower_bound,
        "query_samples": len(sampled_leaves),
        "record_bytes": RECORD_BYTES,
        "subdatabases": subdatabases,
        "note": (
            "Full SimplePIR backend manifest. Each color subdatabase stores 32-byte "
            "Merkle-digest records. The Go runner retrieves each record as eight "
            "32-bit SimplePIR chunks and verifies all recovered chunks."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def build_pbc_active_indexes(
    active_count: int,
    exact_width: int,
) -> Dict[int, List[Tuple[int, int, int]]]:
    """Resource-level PBC-active layout for the same SimplePIR backend.

    This is the batch-code foil used in the TreePIR style of evaluation:
    active proof records are treated as an arbitrary batch, stored with
    three-copy placement, and spread over about 1.5m buckets.  The tuples
    do not define served intervals; they only materialize bucket sizes for
    the backend. Query indices are therefore dummy/random from the backend
    point of view, which is sufficient for measuring the database shape seen
    by SimplePIR.
    """

    width = max(1, int(math.ceil(1.5 * exact_width)))
    total_replicas = 3 * active_count
    indexes: Dict[int, List[Tuple[int, int, int]]] = {color: [] for color in range(1, width + 1)}
    for replica_index in range(total_replicas):
        color = replica_index % width + 1
        indexes[color].append((1, 0, replica_index))
    return indexes


def flat_query_targets(
    entries: Sequence[Tuple[int, int, int]],
    occupied_leaves: Sequence[int],
    leaf_heap_index: int,
    width: int,
    rng: random.Random,
) -> List[int]:
    rank = occupied_leaves.index(leaf_heap_index)
    real_targets = [
        pos
        for pos, (left, right, _) in enumerate(entries)
        if left <= rank <= right
    ]
    if len(real_targets) > width:
        raise ValueError(f"flat proof target count {len(real_targets)} exceeds width {width}")
    while len(real_targets) < width:
        real_targets.append(rng.randrange(max(1, len(entries))))
    return real_targets


def write_flat_manifest(
    entries: Sequence[Tuple[int, int, int]],
    height: int,
    active_nodes: int,
    exact_width: int,
    occupied: Sequence[int],
    sampled_leaves: Sequence[int],
    seed: int,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed * 107 + exact_width)
    dummy_rng = random.Random(seed * 109 + exact_width)

    records = rng.integers(0, 256, size=(len(entries), RECORD_BYTES), dtype=np.uint8)
    db_path = output_dir / "all_active.bin"
    db_path.write_bytes(records.tobytes())

    target_lists = [
        flat_query_targets(entries, occupied, leaf, exact_width, dummy_rng)
        for leaf in sampled_leaves
    ]

    subdatabases: List[Dict[str, object]] = []
    for slot in range(1, exact_width + 1):
        subdatabases.append(
            {
                "color": slot,
                "records": len(entries),
                "record_bytes": RECORD_BYTES,
                "database_file": db_path.name,
                "query_indices": [targets[slot - 1] for targets in target_lists],
            }
        )

    manifest = {
        "scheme": "flat_normal_pir_m",
        "height": height,
        "width": exact_width,
        "active_nodes": active_nodes,
        "stored_nodes": active_nodes,
        "lower_bound": 0,
        "query_samples": len(sampled_leaves),
        "record_bytes": RECORD_BYTES,
        "subdatabases": subdatabases,
        "note": (
            "Normal flat PIR baseline. All active proof-bearing nodes are stored in one "
            "global database. A membership proof issues m independent SimplePIR queries "
            "to this same database, padding missing active positions with dummy indices. "
            "The Go runner reuses setup/offline state for the shared database file."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def parse_runner_json(output: str) -> Dict[str, object]:
    start = output.rfind("{")
    if start < 0:
        raise RuntimeError(f"SimplePIR runner did not emit JSON:\n{output}")
    return json.loads(output[start:])


def path_on_drive(path: Path, workspace: Path, workspace_drive: Path) -> Path:
    if not path.is_absolute():
        return workspace_drive / path
    try:
        relative = path.resolve().relative_to(workspace.resolve())
    except ValueError:
        relative = Path(os.path.relpath(path.absolute(), workspace.absolute()))
    return workspace_drive / relative


def run_simplepir_runner(
    manifest_path: Path,
    workspace: Path,
    workspace_drive: Path,
    simplepir_root: Path,
    go_exe: Path,
    env: Dict[str, str],
    timeout: int,
) -> Dict[str, object]:
    if os.name == "nt":
        drive_manifest = path_on_drive(manifest_path, workspace, workspace_drive)
    else:
        drive_manifest = manifest_path.resolve()
    try:
        completed = subprocess.run(
            [str(go_exe), "run", "./eval/smt_full_backend.go", str(drive_manifest)],
            cwd=simplepir_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "SimplePIR runner failed.\n"
            f"command: {' '.join(map(str, exc.cmd))}\n"
            f"output:\n{exc.output}"
        ) from exc
    return parse_runner_json(completed.stdout)


def build_layouts(
    height: int,
    sparsity: float,
    seed: int,
    refine_rounds: int,
) -> Tuple[List[int], int, int, List[Tuple[int, int, int]], List[SchemeLayout]]:
    occupied = generate_occupied_leaves(height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(nodes)
    exact_width = max_chain_length(roots)
    lower_bound = structural_max_bucket_lower_bound(roots, len(nodes), exact_width)
    flat_entries = sorted((node.interval_left, node.interval_right, node.index) for node in nodes)

    pruned = SchemeLayout(
        name="pruned_treepir_h",
        indexes=pruned_treepir_h_indexes(nodes, height),
        width=height,
        stored_nodes=len(nodes),
        lower_bound=0,
    )

    pbc = SchemeLayout(
        name="pbc_active",
        indexes=build_pbc_active_indexes(len(nodes), exact_width),
        width=max(1, int(math.ceil(1.5 * exact_width))),
        stored_nodes=3 * len(nodes),
        lower_bound=0,
    )

    profile_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    profile_roots = build_interval_forest(profile_nodes)
    best_count_profile_balanced(
        proof_nodes=profile_nodes,
        roots=profile_roots,
        num_colors=exact_width,
        refine_rounds=refine_rounds,
    )
    profile = SchemeLayout(
        name="profile_balanced",
        indexes=build_color_indexes(profile_nodes, exact_width),
        width=exact_width,
        stored_nodes=len(profile_nodes),
        lower_bound=lower_bound,
    )

    return occupied, len(nodes), exact_width, flat_entries, [pbc, pruned, profile]


def flatten_result(
    height: int,
    sparsity: float,
    seed: int,
    occupied_count: int,
    active_nodes: int,
    exact_width: int,
    lower_bound: int,
    result: Dict[str, object],
) -> Dict[str, object]:
    return {
        "height": height,
        "sparsity": sparsity,
        "seed": seed,
        "occupied": occupied_count,
        "active_nodes": active_nodes,
        "exact_width": exact_width,
        "lower_bound": lower_bound,
        "scheme": result["scheme"],
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_note(path: Path, rows: Sequence[Dict[str, object]], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Full SimplePIR Backend Experiment",
        "",
        "## Settings",
        "",
        f"- `heights = {args.heights}`",
        f"- `sparsities = {args.sparsities}`",
        f"- `trials per cell = {args.trials}`",
        f"- `query samples per trial = {args.query_samples}`",
        "- backend: official `ahenzinger/simplepir` Go implementation",
        "- interface: direct calls to `Init`, `Setup`, `Query`, `Answer`, and `Recover`",
        "- digest representation: each 32-byte record is retrieved as eight 32-bit SimplePIR chunks",
        "- baselines: `pbc_active` stores three replicated copies over about `1.5m` buckets, `pruned_treepir_h` keeps height-`h` query slots after pruning inactive records, and `flat_normal_pir_m` stores all active nodes in one global PIR database and sends `m` queries to that same database with dummy padding",
        "",
        "This experiment differs from the previous SimplePIR bandwidth check: it materializes the color subdatabases, runs full SimplePIR setup/query/answer/decode, and verifies the recovered chunks.",
        "",
        "## Results",
        "",
        "| h | empty leaves | scheme | width | active | setup ms | server total ms | server parallel ms | online KB | offline KB |",
        "|---:|---:|:---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['height']} | {float(row['sparsity']) * 100.0:.4f}% | "
            f"{row['scheme']} | {row['width']} | {row['active_nodes']} | "
            f"{float(row['setup_ms']):.3f} | {float(row['server_total_ms']):.3f} | "
            f"{float(row['server_parallel_ms']):.3f} | {float(row['online_total_kb']):.3f} | "
            f"{float(row['offline_kb']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The Go runner performs correctness checks for every recovered chunk.",
            "- Empty color stores are padded with one dummy 32-byte record so that the PIR query interface remains fixed.",
            "- `pbc_active` is a resource-level PBC-style organization over the same active proof records: three replicated copies and about `1.5m` bucket queries, all executed by the same SimplePIR runner.",
            "- `flat_normal_pir_m` reuses setup/offline state for the shared global database, so the comparison does not artificially copy the database `m` times.",
            "- The chunked implementation is conservative: it proves end-to-end API compatibility, but a production implementation could pack 256-bit digests more efficiently.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full SimplePIR retrieval on SMT color subdatabases.")
    parser.add_argument("--heights", default="16")
    parser.add_argument("--sparsities", default="0.9995")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--query-samples", type=int, default=1)
    parser.add_argument("--seed-base", type=int, default=96000)
    parser.add_argument("--refine-rounds", type=int, default=10)
    parser.add_argument("--drive", default="X")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--layout-dir", type=Path, default=Path("examples/simplepir_full_backend_layouts"))
    parser.add_argument("--csv", type=Path, default=Path("examples/simplepir_full_backend_results.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/simplepir_full_backend_experiment_note.md"))
    args = parser.parse_args()

    workspace = Path.cwd()
    workspace_drive = ensure_subst_drive(args.drive, workspace) if os.name == "nt" else workspace.resolve()
    simplepir_root, go_exe, env = simplepir_environment(workspace_drive)

    heights = parse_int_list(args.heights)
    sparsities = parse_float_list(args.sparsities)
    rows: List[Dict[str, object]] = []

    print("=== Full SimplePIR Backend Experiment ===")
    print(f"workspace={workspace}")
    print(f"simplepir_root={simplepir_root}")
    print(f"heights={heights}")
    print(f"sparsities={sparsities}")

    for height in heights:
        for sparsity_index, sparsity in enumerate(sparsities):
            for offset in range(args.trials):
                seed = args.seed_base + height * 1000 + sparsity_index * 100 + offset
                occupied, active_nodes, exact_width, flat_entries, layouts = build_layouts(
                    height=height,
                    sparsity=sparsity,
                    seed=seed,
                    refine_rounds=args.refine_rounds,
                )
                sampled_leaves = [
                    occupied[(seed + idx) % len(occupied)]
                    for idx in range(min(args.query_samples, len(occupied)))
                ]
                flat_output_dir = args.layout_dir / f"h{height}_s{str(sparsity).replace('.', 'p')}_seed{seed}_flat_normal_pir_m"
                flat_manifest = write_flat_manifest(
                    entries=flat_entries,
                    height=height,
                    active_nodes=active_nodes,
                    exact_width=exact_width,
                    occupied=occupied,
                    sampled_leaves=sampled_leaves,
                    seed=seed,
                    output_dir=flat_output_dir,
                )
                flat_result = run_simplepir_runner(
                    manifest_path=flat_manifest,
                    workspace=workspace,
                    workspace_drive=workspace_drive,
                    simplepir_root=simplepir_root,
                    go_exe=go_exe,
                    env=env,
                    timeout=args.timeout,
                )
                flat_row = flatten_result(
                    height=height,
                    sparsity=sparsity,
                    seed=seed,
                    occupied_count=len(occupied),
                    active_nodes=active_nodes,
                    exact_width=exact_width,
                    lower_bound=0,
                    result=flat_result,
                )
                rows.append(flat_row)
                print(
                    f"h={height}, sparsity={sparsity:.6f}, flat_normal_pir_m: "
                    f"width={flat_row['width']}, online={float(flat_row['online_total_kb']):.3f} KB, "
                    f"server_parallel={float(flat_row['server_parallel_ms']):.3f} ms"
                )
                for layout in layouts:
                    output_dir = args.layout_dir / f"h{height}_s{str(sparsity).replace('.', 'p')}_seed{seed}_{layout.name}"
                    manifest_path = write_manifest(
                        layout=layout,
                        height=height,
                        active_nodes=active_nodes,
                        occupied=occupied,
                        sampled_leaves=sampled_leaves,
                        seed=seed,
                        output_dir=output_dir,
                    )
                    result = run_simplepir_runner(
                        manifest_path=manifest_path,
                        workspace=workspace,
                        workspace_drive=workspace_drive,
                        simplepir_root=simplepir_root,
                        go_exe=go_exe,
                        env=env,
                        timeout=args.timeout,
                    )
                    row = flatten_result(
                        height=height,
                        sparsity=sparsity,
                        seed=seed,
                        occupied_count=len(occupied),
                        active_nodes=active_nodes,
                        exact_width=exact_width,
                        lower_bound=layout.lower_bound,
                        result=result,
                    )
                    rows.append(row)
                    print(
                        f"h={height}, sparsity={sparsity:.6f}, {layout.name}: "
                        f"width={row['width']}, online={float(row['online_total_kb']):.3f} KB, "
                        f"server_parallel={float(row['server_parallel_ms']):.3f} ms"
                    )

    write_csv(args.csv, rows)
    write_note(args.note, rows, args)
    print()
    print(f"csv={args.csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
