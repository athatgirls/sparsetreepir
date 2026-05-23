from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Dict, Iterable, List, Sequence

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import best_count_profile_balanced
from run_sparse_smt_pir_backend_experiment import build_color_indexes


DIGEST_BYTES = 32
# Compact public metadata per active record:
# left rank (u64), right rank (u64), proof level (u16), flags/padding (u16),
# and row alignment. The database row index is implicit in the sorted table.
COMPACT_METADATA_BYTES = 24


@dataclass
class MetadataTrial:
    height: int
    sparsity: float
    seed: int
    occupied: int
    active: int
    width: int
    digest_bytes: int
    metadata_bytes: int
    setup_ms: float


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


def run_trial(height: int, sparsity: float, seed: int, refine_rounds: int) -> MetadataTrial:
    start = perf_counter()
    occupied = generate_occupied_leaves(height, sparsity, seed)
    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
    proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    roots = build_interval_forest(proof_nodes)
    width = max_chain_length(roots)
    best_count_profile_balanced(
        proof_nodes=proof_nodes,
        roots=roots,
        num_colors=width,
        refine_rounds=refine_rounds,
    )
    build_color_indexes(proof_nodes, width)
    setup_ms = (perf_counter() - start) * 1000.0

    active = len(proof_nodes)
    return MetadataTrial(
        height=height,
        sparsity=sparsity,
        seed=seed,
        occupied=len(occupied),
        active=active,
        width=width,
        digest_bytes=active * DIGEST_BYTES,
        metadata_bytes=active * COMPACT_METADATA_BYTES,
        setup_ms=setup_ms,
    )


def avg(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def summarize(trials: Sequence[MetadataTrial]) -> Dict[str, float]:
    return {
        "occupied": avg(t.occupied for t in trials),
        "active": avg(t.active for t in trials),
        "m": avg(t.width for t in trials),
        "digest_kb": avg(t.digest_bytes for t in trials) / 1024.0,
        "metadata_kb": avg(t.metadata_bytes for t in trials) / 1024.0,
        "metadata_over_digest": avg(t.metadata_bytes / t.digest_bytes for t in trials if t.digest_bytes),
        "setup_ms": avg(t.setup_ms for t in trials),
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
        "# Public Metadata Overhead Experiment",
        "",
        "## Settings",
        "",
        f"- `heights = {args.heights}`",
        f"- `sparsities = {args.sparsities}`",
        f"- `trials per cell = {args.trials}`",
        f"- `profile_refine_rounds = {args.refine_rounds}`",
        f"- digest payload: `{DIGEST_BYTES}` bytes per active node",
        f"- compact metadata: `{COMPACT_METADATA_BYTES}` bytes per active node",
        "",
        "The compact metadata model stores two 64-bit served-interval endpoints, a 16-bit proof level, and alignment/flags.",
        "The database row position is implicit in the sorted metadata table. A more defensive format that stores an explicit 64-bit node id would use 32 bytes per active node.",
        "",
        "## Results",
        "",
        "| h | empty leaves | active | m | digest KB | metadata KB | meta/digest | setup ms |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['height']} | {float(row['sparsity']) * 100.0:.4f}% | "
            f"{float(row['active']):.1f} | {float(row['m']):.2f} | "
            f"{float(row['digest_kb']):.2f} | {float(row['metadata_kb']):.2f} | "
            f"{float(row['metadata_over_digest']):.2f} | {float(row['setup_ms']):.1f} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure public metadata overhead for profile-balanced SMT layouts.")
    parser.add_argument("--heights", default="16,20,24")
    parser.add_argument("--sparsities", default="0.9995,0.99975,0.9999")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--seed-base", type=int, default=91000)
    parser.add_argument("--refine-rounds", type=int, default=15)
    parser.add_argument("--csv", type=Path, default=Path("examples/metadata_overhead_results.csv"))
    parser.add_argument("--note", type=Path, default=Path("notes/metadata_overhead_experiment_note.md"))
    args = parser.parse_args()

    heights = parse_int_list(args.heights)
    sparsities = parse_float_list(args.sparsities)
    rows: List[Dict[str, object]] = []

    print("=== Public Metadata Overhead Experiment ===")
    print(f"heights={heights}")
    print(f"sparsities={sparsities}")
    print(f"trials={args.trials}")

    for height in heights:
        for sparsity_index, sparsity in enumerate(sparsities):
            trials = [
                run_trial(
                    height=height,
                    sparsity=sparsity,
                    seed=args.seed_base + height * 1000 + sparsity_index * 100 + offset,
                    refine_rounds=args.refine_rounds,
                )
                for offset in range(args.trials)
            ]
            stats = summarize(trials)
            row: Dict[str, object] = {"height": height, "sparsity": sparsity, **stats}
            rows.append(row)
            print(
                f"h={height}, sparsity={sparsity:.6f}: active={stats['active']:.1f}, "
                f"metadata={stats['metadata_kb']:.2f} KB, setup={stats['setup_ms']:.1f} ms"
            )

    write_csv(args.csv, rows)
    write_note(args.note, rows, args)
    print(f"csv={args.csv}")
    print(f"note={args.note}")


if __name__ == "__main__":
    main()
