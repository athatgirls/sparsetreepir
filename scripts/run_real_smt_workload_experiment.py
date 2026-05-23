from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Iterable, List, Optional, Sequence

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    max_chain_length,
    verify_coloring,
)
from subtree_permutation_balance import best_profile_balanced_coloring


HEX_PATTERN = re.compile(r"0x[0-9a-fA-F]{40,64}|(?<![0-9a-fA-F])[0-9a-fA-F]{40,64}(?![0-9a-fA-F])")


@dataclass
class WorkloadMetrics:
    label: str
    source_path: str
    height: int
    key_mode: str
    input_records: int
    unique_keys: int
    occupied_leaves: int
    slot_collisions: int
    active_nodes: int
    exact_width: int
    avg_active_path_len: float
    max_active_path_len_by_leaf: int
    dummy_fraction: float
    ideal_max_bucket: int
    profile_max_bucket: int
    profile_size_gap: int
    profile_over_ideal: float
    profile_runtime_ms: float
    valid: bool


def normalize_hex(value: str) -> str:
    value = value.strip()
    if value.startswith(("0x", "0X")):
        value = value[2:]
    return value.lower()


def key_material(value: str) -> bytes:
    value = value.strip()
    normalized = normalize_hex(value)
    if len(normalized) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", normalized):
        try:
            return bytes.fromhex(normalized)
        except ValueError:
            pass
    return value.encode("utf-8")


def key_to_slot(value: str, height: int, key_mode: str) -> int:
    if height <= 0:
        raise ValueError("height must be positive")
    if key_mode == "sha256":
        digest = hashlib.sha256(key_material(value)).digest()
        integer = int.from_bytes(digest, "big")
        return integer >> (256 - height) if height < 256 else integer

    if key_mode == "hex-prefix":
        normalized = normalize_hex(value)
        integer = int(normalized, 16)
        bit_len = max(1, len(normalized) * 4)
        if height >= bit_len:
            return integer << (height - bit_len)
        return integer >> (bit_len - height)

    if key_mode == "hex-suffix":
        normalized = normalize_hex(value)
        integer = int(normalized, 16)
        mask = (1 << height) - 1
        return integer & mask

    raise ValueError(f"unsupported key mode: {key_mode}")


def iter_csv_column(path: Path, column: str) -> Iterable[str]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(f"Column {column!r} was not found in {path}. Found: {reader.fieldnames}")
        for row in reader:
            value = (row.get(column) or "").strip()
            if value:
                yield value


def iter_jsonl_field(path: Path, field: str) -> Iterable[str]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            value = item.get(field)
            if value is not None:
                yield str(value)


def iter_regex_hex(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            for match in HEX_PATTERN.finditer(line):
                yield match.group(0)


def iter_keys(path: Path, column: Optional[str], json_field: Optional[str], limit: Optional[int]) -> Iterable[str]:
    if column:
        source = iter_csv_column(path, column)
    elif json_field:
        source = iter_jsonl_field(path, json_field)
    else:
        source = iter_regex_hex(path)

    count = 0
    for value in source:
        if not value:
            continue
        yield value
        count += 1
        if limit is not None and count >= limit:
            break


def slots_to_heap_leaves(slots: Sequence[int], height: int) -> List[int]:
    base = 1 << height
    return [base + slot for slot in sorted(set(slots))]


def active_path_lengths(active_nodes, occupied_count: int) -> List[int]:
    diff = [0] * (occupied_count + 1)
    for node in active_nodes:
        diff[node.interval_left] += 1
        diff[node.interval_right + 1] -= 1
    current = 0
    lengths: List[int] = []
    for idx in range(occupied_count):
        current += diff[idx]
        lengths.append(current)
    return lengths


def run_workload(
    path: Path,
    label: str,
    height: int,
    key_mode: str,
    column: Optional[str],
    json_field: Optional[str],
    limit: Optional[int],
    initial_rounds: int,
    refine_rounds: int,
) -> WorkloadMetrics:
    raw_keys = list(iter_keys(path=path, column=column, json_field=json_field, limit=limit))
    if not raw_keys:
        raise ValueError(f"No keys were extracted from {path}.")

    unique_keys = sorted(set(raw_keys))
    slots = [key_to_slot(value, height=height, key_mode=key_mode) for value in unique_keys]
    occupied_leaves = slots_to_heap_leaves(slots, height)
    if not occupied_leaves:
        raise ValueError("No occupied leaves were produced.")

    helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied_leaves)
    proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied_leaves, height)
    roots = build_interval_forest(proof_nodes)
    exact_width = max_chain_length(roots)
    if exact_width == 0:
        ideal_max_bucket = 0
    else:
        ideal_max_bucket = (len(proof_nodes) + exact_width - 1) // exact_width

    t0 = perf_counter()
    profile_result = best_profile_balanced_coloring(
        proof_nodes=proof_nodes,
        roots=roots,
        num_colors=exact_width,
        initial_rounds=initial_rounds,
        refine_rounds=refine_rounds,
    )
    t1 = perf_counter()
    valid, _ = verify_coloring(roots, occupied_leaves)

    path_lengths = active_path_lengths(proof_nodes, len(occupied_leaves))
    avg_active = mean(path_lengths) if path_lengths else 0.0
    max_by_leaf = max(path_lengths) if path_lengths else 0
    dummy_fraction = 0.0
    if exact_width > 0 and path_lengths:
        dummy_fraction = mean((exact_width - value) / exact_width for value in path_lengths)

    return WorkloadMetrics(
        label=label,
        source_path=str(path),
        height=height,
        key_mode=key_mode,
        input_records=len(raw_keys),
        unique_keys=len(unique_keys),
        occupied_leaves=len(occupied_leaves),
        slot_collisions=len(unique_keys) - len(occupied_leaves),
        active_nodes=len(proof_nodes),
        exact_width=exact_width,
        avg_active_path_len=avg_active,
        max_active_path_len_by_leaf=max_by_leaf,
        dummy_fraction=dummy_fraction,
        ideal_max_bucket=ideal_max_bucket,
        profile_max_bucket=profile_result.max_bucket,
        profile_size_gap=profile_result.size_gap,
        profile_over_ideal=(profile_result.max_bucket / ideal_max_bucket) if ideal_max_bucket else 0.0,
        profile_runtime_ms=(t1 - t0) * 1000.0,
        valid=valid,
    )


def write_csv(path: Path, rows: Sequence[WorkloadMetrics]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(WorkloadMetrics.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fields})


def print_summary(row: WorkloadMetrics) -> None:
    print(
        f"{row.label}: height={row.height}, keys={row.unique_keys}, occupied={row.occupied_leaves}, "
        f"active={row.active_nodes}, m={row.exact_width}, avg_path={row.avg_active_path_len:.2f}, "
        f"dummy={row.dummy_fraction * 100:.2f}%, profile_max={row.profile_max_bucket}, "
        f"ideal={row.ideal_max_bucket}, ratio={row.profile_over_ideal:.3f}, "
        f"gap={row.profile_size_gap}, valid={row.valid}, runtime_ms={row.profile_runtime_ms:.1f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run SparseTreePIR structural metrics on real SMT-style key workloads. "
            "The input may be CSV, JSONL, or a text file containing hex addresses/keys."
        )
    )
    parser.add_argument("--input", type=Path, required=True, help="Input CSV/JSONL/TXT file.")
    parser.add_argument("--label", type=str, default="real_smt_workload", help="Dataset label.")
    parser.add_argument("--heights", type=str, default="128,256", help="Comma-separated SMT heights.")
    parser.add_argument("--key-mode", choices=["sha256", "hex-prefix", "hex-suffix"], default="sha256")
    parser.add_argument("--column", type=str, default=None, help="CSV column containing keys.")
    parser.add_argument("--json-field", type=str, default=None, help="JSONL field containing keys.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum records to read.")
    parser.add_argument("--initial-rounds", type=int, default=120)
    parser.add_argument("--refine-rounds", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("examples/real_smt_workload_results.csv"))
    args = parser.parse_args()

    heights = [int(item.strip()) for item in args.heights.split(",") if item.strip()]
    if not heights:
        raise ValueError("At least one height is required.")

    rows: List[WorkloadMetrics] = []
    for height in heights:
        row = run_workload(
            path=args.input,
            label=args.label,
            height=height,
            key_mode=args.key_mode,
            column=args.column,
            json_field=args.json_field,
            limit=args.limit,
            initial_rounds=args.initial_rounds,
            refine_rounds=args.refine_rounds,
        )
        rows.append(row)
        print_summary(row)

    write_csv(args.output, rows)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
