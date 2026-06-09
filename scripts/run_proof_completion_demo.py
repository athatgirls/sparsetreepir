from __future__ import annotations

import argparse
import bisect
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import build_full_proof_nodes, build_interval_forest
from run_sparse_smt_pir_backend_experiment import color_proof_nodes


HashBytes = bytes


@dataclass
class MetadataEntry:
    left: int
    right: int
    proof_level: int
    node_index: int


def parse_leaf_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("leaf list cannot be empty")
    return sorted(set(values))


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def empty_hash_chain(height: int) -> List[HashBytes]:
    chain = [sha256(b"empty:0")]
    for level in range(height):
        chain.append(sha256(chain[level] + chain[level]))
    return chain


def leaf_hash(index: int) -> HashBytes:
    return sha256(f"leaf:{index}".encode("ascii"))


def subtree_hash(
    node_index: int,
    tree_height: int,
    occupied: set[int],
    defaults: Sequence[HashBytes],
    memo: Dict[int, HashBytes],
) -> HashBytes:
    if node_index in memo:
        return memo[node_index]

    depth = node_index.bit_length() - 1
    if depth == tree_height:
        digest = leaf_hash(node_index) if node_index in occupied else defaults[0]
        memo[node_index] = digest
        return digest

    left = subtree_hash(node_index * 2, tree_height, occupied, defaults, memo)
    right = subtree_hash(node_index * 2 + 1, tree_height, occupied, defaults, memo)
    digest = sha256(left + right)
    memo[node_index] = digest
    return digest


def direct_full_proof(
    leaf_index: int,
    tree_height: int,
    occupied: set[int],
    defaults: Sequence[HashBytes],
) -> List[HashBytes]:
    memo: Dict[int, HashBytes] = {}
    current = leaf_index
    proof: List[HashBytes] = []
    for _level in range(tree_height):
        sibling = current - 1 if current % 2 == 1 else current + 1
        proof.append(subtree_hash(sibling, tree_height, occupied, defaults, memo))
        current //= 2
    return proof


def build_metadata_tables(proof_nodes, tree_height: int, num_colors: int) -> Dict[int, List[MetadataEntry]]:
    tables: Dict[int, List[MetadataEntry]] = {color: [] for color in range(1, num_colors + 1)}
    for node in proof_nodes:
        if node.color is None:
            continue
        tables[node.color].append(
            MetadataEntry(
                left=node.interval_left,
                right=node.interval_right,
                proof_level=tree_height - node.depth,
                node_index=node.index,
            )
        )
    for color in tables:
        tables[color].sort(key=lambda item: (item.left, item.right, item.node_index))
    return tables


def local_target_map(
    metadata: Dict[int, List[MetadataEntry]],
    occupied_leaves: Sequence[int],
    target_leaf: int,
    num_colors: int,
) -> Dict[int, Optional[int]]:
    rank = occupied_leaves.index(target_leaf)
    targets: Dict[int, Optional[int]] = {}
    for color in range(1, num_colors + 1):
        entries = metadata[color]
        left_endpoints = [entry.left for entry in entries]
        pos = bisect.bisect_right(left_endpoints, rank) - 1
        if pos >= 0 and entries[pos].left <= rank <= entries[pos].right:
            targets[color] = pos
        else:
            targets[color] = None
    return targets


def proof_completion(
    target_leaf: int,
    target_leaf_digest: HashBytes,
    metadata: Dict[int, List[MetadataEntry]],
    targets: Dict[int, Optional[int]],
    extracted_outputs: Dict[int, HashBytes],
    defaults: Sequence[HashBytes],
    tree_height: int,
) -> Tuple[List[HashBytes], HashBytes]:
    proof = [defaults[level] for level in range(tree_height)]
    for color, pos in targets.items():
        if pos is None:
            continue
        entry = metadata[color][pos]
        proof[entry.proof_level] = extracted_outputs[color]

    current = target_leaf_digest
    leaf_slot = target_leaf - (1 << tree_height)
    for level in range(tree_height):
        bit = (leaf_slot >> level) & 1
        sibling_digest = proof[level]
        current = sha256(current + sibling_digest) if bit == 0 else sha256(sibling_digest + current)
    return proof, current


def main() -> None:
    parser = argparse.ArgumentParser(description="Demonstrate client-side proof completion on a sparse SMT.")
    parser.add_argument("--height", type=int, default=4, help="SMT height.")
    parser.add_argument("--occupied", type=str, default="16,17,19,22,28", help="Comma-separated occupied leaf heap indices.")
    parser.add_argument("--target", type=int, default=19, help="Target occupied leaf heap index.")
    parser.add_argument("--strategy", type=str, default="hybrid", choices=["weighted", "count_balanced", "hybrid"])
    parser.add_argument("--rounds", type=int, default=400, help="Rebalance rounds.")
    args = parser.parse_args()

    occupied = parse_leaf_list(args.occupied)
    if args.target not in occupied:
        raise ValueError("target must be one of the occupied leaves")

    helper = FixedSparseMerkleColoring(original_height=args.height, occupied_leaves=occupied)
    proof_nodes = build_full_proof_nodes(helper.raw_nodes, occupied, args.height)
    roots = build_interval_forest(proof_nodes)
    count_loads, weight_loads = color_proof_nodes(
        proof_nodes=proof_nodes,
        roots=roots,
        num_colors=args.height,
        strategy=args.strategy,
        rebalance_rounds=args.rounds,
    )
    metadata = build_metadata_tables(proof_nodes, args.height, args.height)
    targets = local_target_map(metadata, occupied, args.target, args.height)

    defaults = empty_hash_chain(args.height)
    occupied_set = set(occupied)
    memo: Dict[int, HashBytes] = {}
    extracted_outputs: Dict[int, HashBytes] = {}
    for color, pos in targets.items():
        if pos is None:
            continue
        entry = metadata[color][pos]
        extracted_outputs[color] = subtree_hash(entry.node_index, args.height, occupied_set, defaults, memo)

    completed_proof, reconstructed_root = proof_completion(
        target_leaf=args.target,
        target_leaf_digest=leaf_hash(args.target),
        metadata=metadata,
        targets=targets,
        extracted_outputs=extracted_outputs,
        defaults=defaults,
        tree_height=args.height,
    )

    direct_proof = direct_full_proof(args.target, args.height, occupied_set, defaults)
    direct_root = subtree_hash(1, args.height, occupied_set, defaults, memo)

    proof_match = completed_proof == direct_proof
    root_match = reconstructed_root == direct_root

    print("=== Proof Completion Demo ===")
    print(f"height={args.height}")
    print(f"occupied={occupied}")
    print(f"target={args.target}")
    print(f"strategy={args.strategy}")
    print(f"count_loads={count_loads}")
    print(f"weight_loads={weight_loads}")
    print(f"local_targets={targets}")
    print(f"real_response_colors={sorted(extracted_outputs.keys())}")
    print(f"proof_match={proof_match}")
    print(f"root_match={root_match}")


if __name__ == "__main__":
    main()
