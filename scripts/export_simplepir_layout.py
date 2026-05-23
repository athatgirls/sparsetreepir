from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    build_full_proof_nodes,
    build_interval_forest,
    generate_occupied_leaves,
    max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import best_count_profile_balanced
from run_sparse_smt_pir_backend_experiment import build_color_indexes


RECORD_BYTES = 32


def export_layout(
    height: int,
    sparsity: float,
    seed: int,
    refine_rounds: int,
    output_dir: Path,
) -> Dict[str, object]:
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
    indexes = build_color_indexes(proof_nodes, width)

    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    subdatabases: List[Dict[str, object]] = []
    for color in range(1, width + 1):
        entries: List[Tuple[int, int, int]] = indexes.get(color, [])
        db_path = output_dir / f"color_{color:02d}.bin"
        records = rng.integers(0, 256, size=(len(entries), RECORD_BYTES), dtype=np.uint8)
        db_path.write_bytes(records.tobytes())
        subdatabases.append(
            {
                "color": color,
                "records": len(entries),
                "record_bytes": RECORD_BYTES,
                "database_file": db_path.name,
                "metadata": [
                    {"interval_left": left, "interval_right": right, "node_id": node_id}
                    for left, right, node_id in entries
                ],
            }
        )

    manifest = {
        "backend_target": "simplepir_external",
        "height": height,
        "sparsity": sparsity,
        "seed": seed,
        "occupied_leaves": len(occupied),
        "active_nodes": len(proof_nodes),
        "width": width,
        "record_bytes": RECORD_BYTES,
        "subdatabases": subdatabases,
        "note": (
            "Each color_XX.bin file is a row-major database of fixed-size records. "
            "An external SimplePIR runner should instantiate one PIR database per color "
            "and issue one real or dummy query to each non-empty color database."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export profile-balanced color subdatabases for an external SimplePIR runner.")
    parser.add_argument("--height", type=int, default=20)
    parser.add_argument("--sparsity", type=float, default=0.99975)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--refine-rounds", type=int, default=15)
    parser.add_argument("--output-dir", type=Path, default=Path("examples/simplepir_layout"))
    args = parser.parse_args()

    manifest = export_layout(
        height=args.height,
        sparsity=args.sparsity,
        seed=args.seed,
        refine_rounds=args.refine_rounds,
        output_dir=args.output_dir,
    )
    print(f"manifest={args.output_dir / 'manifest.json'}")
    print(f"height={manifest['height']}")
    print(f"active_nodes={manifest['active_nodes']}")
    print(f"width={manifest['width']}")
    print(f"colors={len(manifest['subdatabases'])}")


if __name__ == "__main__":
    main()
