from __future__ import annotations

import argparse
import csv
import math
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Sequence, Tuple

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
from run_lwe_pir_backend_experiment import loads_from_indexes, pruned_treepir_h_indexes
from run_sparse_smt_pir_backend_experiment import build_color_indexes


@dataclass(frozen=True)
class SimplePirBW:
    log_records: int
    padded_records: int
    l_dim: int
    m_dim: int
    n_dim: int
    logq: int
    packed_mb: float
    offline_kb: float
    online_upload_kb: float
    online_download_kb: float

    @property
    def online_total_kb(self) -> float:
        return self.online_upload_kb + self.online_download_kb


@dataclass
class SchemeComm:
    width: int
    stored_nodes: int
    max_bucket: int
    max_log_records: int
    sum_offline_kb: float
    sum_online_upload_kb: float
    sum_online_download_kb: float
    max_color_offline_kb: float
    max_color_online_kb: float

    @property
    def sum_online_kb(self) -> float:
        return self.sum_online_upload_kb + self.sum_online_download_kb


@dataclass
class Trial:
    height: int
    sparsity: float
    seed: int
    occupied: int
    active_nodes: int
    exact_width: int
    lower_bound: int
    pruned: SchemeComm
    profile: SchemeComm


WORKING_RE = re.compile(
    r"Working with: n=(?P<n>\d+); db size=2\^(?P<dbexp>\d+) "
    r"\(l=(?P<l>\d+), m=(?P<m>\d+)\); logq=(?P<logq>\d+);"
)
PACKED_RE = re.compile(r"Total packed DB size is ~(?P<mb>[0-9.]+) MB")


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


def ceil_log2_for_simplepir(records: int) -> int:
    # The official test treats LOG_N=0 as "use the default large database".
    # We therefore pad empty or one-record color stores to two records.
    return max(1, int(math.ceil(math.log2(max(records, 2)))))


def ensure_subst_drive(drive: str, target: Path) -> Path:
    drive = drive.rstrip(":").upper()
    target = target.resolve()
    subprocess.run(["cmd", "/c", "subst", f"{drive}:", str(target)], check=True)
    return Path(f"{drive}:/")


def simplepir_environment(workspace_drive: Path) -> Tuple[Path, Path, Dict[str, str]]:
    w64_bin = workspace_drive / ".tools" / "w64devkit113" / "w64devkit" / "bin"
    go_bin = workspace_drive / ".tools" / "go119" / "go" / "bin"
    simplepir_dir = workspace_drive / ".tools" / "simplepir" / "simplepir-main" / "pir"

    required = [
        w64_bin / "gcc.exe",
        go_bin / "go.exe",
        simplepir_dir / "pir_test.go",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(
            "Missing official SimplePIR toolchain files. Expected local tools under .tools; missing:\n"
            + "\n".join(missing)
        )

    env = os.environ.copy()
    env["PATH"] = f"{w64_bin};{go_bin};" + env.get("PATH", "")
    env["GOCACHE"] = str(workspace_drive / ".tools" / "gocache119")
    env["GOMODCACHE"] = str(workspace_drive / ".tools" / "gomodcache119")
    env["CC"] = str(w64_bin / "gcc.exe")
    env["COMPILER_PATH"] = str(w64_bin)
    env["D"] = "256"
    return simplepir_dir, go_bin / "go.exe", env


def run_simplepir_bw(
    log_records: int,
    simplepir_dir: Path,
    go_exe: Path,
    base_env: Dict[str, str],
) -> SimplePirBW:
    env = dict(base_env)
    env["LOG_N"] = str(log_records)
    completed = subprocess.run(
        [str(go_exe), "test", "-run=TestSimplePirBW", "-count=1"],
        cwd=simplepir_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    output = completed.stdout
    working = WORKING_RE.search(output)
    packed = PACKED_RE.search(output)
    if working is None or packed is None:
        raise RuntimeError(f"Could not parse SimplePIR output for LOG_N={log_records}:\n{output}")

    n_dim = int(working.group("n"))
    l_dim = int(working.group("l"))
    m_dim = int(working.group("m"))
    logq = int(working.group("logq"))
    packed_mb = float(packed.group("mb"))

    # Use the exact formula implemented by SimplePIR.GetBW instead of the
    # integer-truncated printed KB values, otherwise small SMT buckets round to 0.
    offline_kb = l_dim * n_dim * logq / (8.0 * 1024.0)
    online_upload_kb = m_dim * logq / (8.0 * 1024.0)
    online_download_kb = l_dim * logq / (8.0 * 1024.0)

    return SimplePirBW(
        log_records=log_records,
        padded_records=1 << log_records,
        l_dim=l_dim,
        m_dim=m_dim,
        n_dim=n_dim,
        logq=logq,
        packed_mb=packed_mb,
        offline_kb=offline_kb,
        online_upload_kb=online_upload_kb,
        online_download_kb=online_download_kb,
    )


def comm_for_loads(
    loads: Sequence[int],
    stored_nodes: int,
    bw_cache: Dict[int, SimplePirBW],
) -> SchemeComm:
    padded_loads = [max(1, load) for load in loads]
    log_records = [ceil_log2_for_simplepir(load) for load in padded_loads]
    entries = [bw_cache[logn] for logn in log_records]

    return SchemeComm(
        width=len(loads),
        stored_nodes=stored_nodes,
        max_bucket=max(loads) if loads else 0,
        max_log_records=max(log_records) if log_records else 0,
        sum_offline_kb=sum(entry.offline_kb for entry in entries),
        sum_online_upload_kb=sum(entry.online_upload_kb for entry in entries),
        sum_online_download_kb=sum(entry.online_download_kb for entry in entries),
        max_color_offline_kb=max((entry.offline_kb for entry in entries), default=0.0),
        max_color_online_kb=max((entry.online_total_kb for entry in entries), default=0.0),
    )


def collect_loads(height: int, sparsity: float, seed: int, refine_rounds: int) -> Tuple[int, int, int, int, List[int], List[int]]:
    occupied = generate_occupied_leaves(height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(nodes)
    exact_width = max_chain_length(roots)
    lower_bound = structural_max_bucket_lower_bound(roots, len(nodes), exact_width)

    pruned_indexes = pruned_treepir_h_indexes(nodes, height)
    pruned_loads = loads_from_indexes(pruned_indexes, height)

    profile_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    profile_roots = build_interval_forest(profile_nodes)
    best_count_profile_balanced(
        proof_nodes=profile_nodes,
        roots=profile_roots,
        num_colors=exact_width,
        refine_rounds=refine_rounds,
    )
    profile_indexes = build_color_indexes(profile_nodes, exact_width)
    profile_loads = loads_from_indexes(profile_indexes, exact_width)

    return len(occupied), len(nodes), exact_width, lower_bound, pruned_loads, profile_loads


def all_required_logs(load_sets: Iterable[Sequence[int]]) -> List[int]:
    logs = set()
    for loads in load_sets:
        for load in loads:
            logs.add(ceil_log2_for_simplepir(max(1, load)))
    return sorted(logs)


def average_trials(trials: Sequence[Trial]) -> Dict[str, float]:
    def avg(values: Iterable[float]) -> float:
        values = list(values)
        return mean(values) if values else 0.0

    return {
        "occupied": avg(trial.occupied for trial in trials),
        "active": avg(trial.active_nodes for trial in trials),
        "m": avg(trial.exact_width for trial in trials),
        "lower": avg(trial.lower_bound for trial in trials),
        "pruned_width": avg(trial.pruned.width for trial in trials),
        "profile_width": avg(trial.profile.width for trial in trials),
        "pruned_max": avg(trial.pruned.max_bucket for trial in trials),
        "profile_max": avg(trial.profile.max_bucket for trial in trials),
        "pruned_logN": avg(trial.pruned.max_log_records for trial in trials),
        "profile_logN": avg(trial.profile.max_log_records for trial in trials),
        "pruned_offline_kb": avg(trial.pruned.sum_offline_kb for trial in trials),
        "profile_offline_kb": avg(trial.profile.sum_offline_kb for trial in trials),
        "pruned_online_kb": avg(trial.pruned.sum_online_kb for trial in trials),
        "profile_online_kb": avg(trial.profile.sum_online_kb for trial in trials),
        "pruned_parallel_online_kb": avg(trial.pruned.max_color_online_kb for trial in trials),
        "profile_parallel_online_kb": avg(trial.profile.max_color_online_kb for trial in trials),
        "offline_reduction": 100.0
        * (1.0 - avg(trial.profile.sum_offline_kb for trial in trials) / avg(trial.pruned.sum_offline_kb for trial in trials)),
        "online_reduction": 100.0
        * (1.0 - avg(trial.profile.sum_online_kb for trial in trials) / avg(trial.pruned.sum_online_kb for trial in trials)),
        "parallel_online_reduction": 100.0
        * (
            1.0
            - avg(trial.profile.max_color_online_kb for trial in trials)
            / avg(trial.pruned.max_color_online_kb for trial in trials)
        ),
        "max_bucket_reduction": 100.0
        * (1.0 - avg(trial.profile.max_bucket for trial in trials) / avg(trial.pruned.max_bucket for trial in trials)),
        "profile_over_lower": avg(
            (trial.profile.max_bucket / trial.lower_bound) if trial.lower_bound else 0.0
            for trial in trials
        ),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_note(path: Path, rows: Sequence[Dict[str, object]], bw_cache: Dict[int, SimplePirBW], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Official SimplePIR Backend Experiment",
        "",
        "## Settings",
        "",
        f"- `heights = {args.heights}`",
        f"- `sparsities = {args.sparsities}`",
        f"- `trials per cell = {args.trials}`",
        f"- `digest record size = 256 bits`",
        f"- `profile_refine_rounds = {args.refine_rounds}`",
        "- backend: official `ahenzinger/simplepir` Go implementation, `TestSimplePirBW`",
        "- local toolchain: Go 1.19 + w64devkit 1.13, required for stable cgo on Windows",
        "",
        "The script pads each color subdatabase to the next power-of-two record count because the official benchmark takes `LOG_N` as input.",
        "Empty pruning-only colors are padded to one dummy record and then rounded to two records so that the PIR interface remains defined.",
        "The table reports the exact KB values obtained from SimplePIR's own parameter formulas, avoiding the integer truncation in the printed benchmark output.",
        "",
        "## Per-bucket SimplePIR parameter cache",
        "",
        "| log records | records | L | M | packed MB | offline KB | online KB |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for logn in sorted(bw_cache):
        entry = bw_cache[logn]
        lines.append(
            f"| {logn} | {entry.padded_records} | {entry.l_dim} | {entry.m_dim} | "
            f"{entry.packed_mb:.6f} | {entry.offline_kb:.2f} | {entry.online_total_kb:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Layout-level results",
            "",
            "| h | empty leaves | active | m | pruned max | profile max | P/lower | total online KB | parallel online KB | online red. | par. red. |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['height']} | {float(row['sparsity']) * 100.0:.4f}% | "
            f"{float(row['active']):.1f} | {float(row['m']):.2f} | "
            f"{float(row['pruned_max']):.2f} | {float(row['profile_max']):.2f} | "
            f"{float(row['profile_over_lower']):.3f} | "
            f"{float(row['pruned_online_kb']):.3f}$\\to${float(row['profile_online_kb']):.3f} | "
            f"{float(row['pruned_parallel_online_kb']):.3f}$\\to${float(row['profile_parallel_online_kb']):.3f} | "
            f"{float(row['online_reduction']):.1f}% | {float(row['parallel_online_reduction']):.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `total online KB` sums SimplePIR query plus answer communication across all color subdatabases.",
            "- `parallel online KB` is the largest per-color online communication after SimplePIR parameter rounding; it is the more relevant number when color subqueries are issued in parallel.",
            "- The result is intentionally more nuanced than the structural model. `profile_balanced` consistently lowers the max bucket and usually lowers the parallel per-color SimplePIR bottleneck, but total communication can increase when many balanced color stores round up to the same SimplePIR parameter tier.",
            "- This supports a cleaner paper claim: profile balancing is a strong exact-width bottleneck reducer, while a production backend may still need a backend-aware secondary objective for total communication.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official SimplePIR BW test on sparse-SMT color layouts.")
    parser.add_argument("--heights", default="16,20,24")
    parser.add_argument("--sparsities", default="0.9995,0.99975,0.9999")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--seed-base", type=int, default=91000)
    parser.add_argument("--refine-rounds", type=int, default=15)
    parser.add_argument("--drive", default="X")
    parser.add_argument("--csv", type=Path, default=Path("examples/simplepir_official_backend_results.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/simplepir_official_backend_experiment_note.md"))
    args = parser.parse_args()

    workspace = Path.cwd()
    workspace_drive = ensure_subst_drive(args.drive, workspace)
    simplepir_dir, go_exe, env = simplepir_environment(workspace_drive)

    heights = parse_int_list(args.heights)
    sparsities = parse_float_list(args.sparsities)

    print("=== Official SimplePIR Backend Experiment ===")
    print(f"workspace={workspace}")
    print(f"simplepir_dir={simplepir_dir}")
    print(f"heights={heights}")
    print(f"sparsities={sparsities}")
    print()

    raw_trials: List[Tuple[int, float, int, int, int, int, int, List[int], List[int]]] = []
    load_sets: List[List[int]] = []
    for height in heights:
        for sparsity_index, sparsity in enumerate(sparsities):
            for offset in range(args.trials):
                seed = args.seed_base + height * 1000 + sparsity_index * 100 + offset
                occupied, active, exact_width, lower, pruned_loads, profile_loads = collect_loads(
                    height=height,
                    sparsity=sparsity,
                    seed=seed,
                    refine_rounds=args.refine_rounds,
                )
                raw_trials.append((height, sparsity, seed, occupied, active, exact_width, lower, pruned_loads, profile_loads))
                load_sets.append(pruned_loads)
                load_sets.append(profile_loads)

    needed_logs = all_required_logs(load_sets)
    print(f"SimplePIR LOG_N values needed: {needed_logs}")
    bw_cache = {
        logn: run_simplepir_bw(logn, simplepir_dir=simplepir_dir, go_exe=go_exe, base_env=env)
        for logn in needed_logs
    }

    grouped: Dict[Tuple[int, float], List[Trial]] = {}
    for height, sparsity, seed, occupied, active, exact_width, lower, pruned_loads, profile_loads in raw_trials:
        pruned = comm_for_loads(pruned_loads, stored_nodes=active, bw_cache=bw_cache)
        profile = comm_for_loads(profile_loads, stored_nodes=active, bw_cache=bw_cache)
        grouped.setdefault((height, sparsity), []).append(
            Trial(
                height=height,
                sparsity=sparsity,
                seed=seed,
                occupied=occupied,
                active_nodes=active,
                exact_width=exact_width,
                lower_bound=lower,
                pruned=pruned,
                profile=profile,
            )
        )

    rows: List[Dict[str, object]] = []
    for (height, sparsity), trials in sorted(grouped.items()):
        stats = average_trials(trials)
        row: Dict[str, object] = {"height": height, "sparsity": sparsity, **stats}
        rows.append(row)
        print(
            f"h={height}, sparsity={sparsity:.6f}: "
            f"profile/lower={stats['profile_over_lower']:.3f}, "
            f"online={stats['pruned_online_kb']:.3f}->{stats['profile_online_kb']:.3f} KB, "
            f"offline={stats['pruned_offline_kb']:.1f}->{stats['profile_offline_kb']:.1f} KB"
        )

    write_csv(args.csv, rows)
    write_note(args.note, rows, bw_cache, args)
    print()
    print(f"csv={args.csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
