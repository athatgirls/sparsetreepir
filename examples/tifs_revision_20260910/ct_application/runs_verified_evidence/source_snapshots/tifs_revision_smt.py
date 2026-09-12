"""Real digest and query-layout helpers for the 2026-09-10 TIFS experiments.

This is an experimental binary SMT, not Fuel/Polygon/ZKsync's native tree.
SHA256 domain separation: occupied leaf H(00 || value), internal node
H(01 || left || right), empty leaf H(02). Slots are zero-based h-bit integers;
heap node ids have root=1 and leaves=(1<<h)+slot. Proofs are bottom-up.
Only occupied ancestor paths are materialized: hashing takes O(n*h), never 2**h.
The imported coloring functions are the existing manuscript implementation.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Mapping, Sequence

from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import (
    ProofNode, build_full_proof_nodes, build_interval_forest, max_chain_length,
)
from run_height_sparsity_profile_balance_experiment import (
    best_count_profile_balanced, first_fit_coloring,
)
from run_sparse_smt_pir_backend_experiment import color_proof_nodes

DIGEST_BYTES = 32
HASH_FORMAT = "sha256:leaf=H(00||value),internal=H(01||left||right),empty_leaf=H(02)"


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_digest(value: bytes) -> bytes:
    return sha256(b"\x00" + value)


def parent_digest(left: bytes, right: bytes) -> bytes:
    return sha256(b"\x01" + left + right)


def default_hash_chain(height: int) -> list[bytes]:
    if not isinstance(height, int) or isinstance(height, bool) or not 0 <= height <= 256:
        raise ValueError("height must be an integer in [0,256]")
    chain = [sha256(b"\x02")]
    for _ in range(height):
        chain.append(parent_digest(chain[-1], chain[-1]))
    return chain


def default_value(slot: int, height: int) -> bytes:
    """Deterministic experiment value; not a deployed-chain account value."""
    return sha256(b"TIFS-revision-value\x00" + height.to_bytes(2, "big")
                  + slot.to_bytes(max(1, (height + 7) // 8), "big"))


def verify_proof(height: int, slot: int, value: bytes,
                 proof: Sequence[bytes], expected_root: bytes) -> bool:
    """Return False for malformed proofs, invalid slots, or a root mismatch."""
    if (not isinstance(height, int) or isinstance(height, bool) or not 0 <= height <= 256
            or not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot < (1 << height)
            or not isinstance(value, bytes) or not isinstance(expected_root, bytes)
            or len(expected_root) != DIGEST_BYTES or len(proof) != height
            or any(not isinstance(x, bytes) or len(x) != DIGEST_BYTES for x in proof)):
        return False
    current = leaf_digest(value)
    for level, sibling in enumerate(proof):
        current = (parent_digest(sibling, current) if ((slot >> level) & 1)
                   else parent_digest(current, sibling))
    return current == expected_root


@dataclass
class SparseSMT:
    height: int
    slots: tuple[int, ...]
    values: dict[int, bytes]
    defaults: list[bytes]
    digests: dict[int, bytes]
    root: bytes

    @classmethod
    def build(cls, height: int, slots: Sequence[int],
              values: Mapping[int, bytes] | None = None) -> "SparseSMT":
        defaults = default_hash_chain(height)
        raw = list(slots)
        if any(not isinstance(s, int) or isinstance(s, bool) or not 0 <= s < (1 << height) for s in raw):
            raise ValueError("slots must be h-bit nonnegative integers")
        if len(set(raw)) != len(raw):
            raise ValueError("duplicate slots are not permitted")
        ordered = tuple(sorted(raw))
        if values is None:
            stored_values = {s: default_value(s, height) for s in ordered}
        else:
            if set(values) != set(ordered) or any(not isinstance(v, bytes) for v in values.values()):
                raise ValueError("values must map exactly the occupied slots to bytes")
            stored_values = dict(values)
        current = {(1 << height) + s: leaf_digest(stored_values[s]) for s in ordered}
        digests = dict(current)
        for level in range(height):
            parents = {node // 2 for node in current}
            current = {p: parent_digest(current.get(2*p, defaults[level]),
                                        current.get(2*p+1, defaults[level])) for p in parents}
            digests.update(current)
        return cls(height, ordered, stored_values, defaults, digests,
                   digests.get(1, defaults[height]))

    def proof(self, slot: int) -> list[bytes]:
        if slot not in self.values:
            raise ValueError("membership proof target is not occupied")
        node = (1 << self.height) + slot
        proof = []
        for level in range(self.height):
            proof.append(self.digests.get(node ^ 1, self.defaults[level]))
            node //= 2
        return proof

    def proof_record_nodes(self, slot: int) -> dict[int, int]:
        """Map proof level to the non-default sibling's heap id."""
        if slot not in self.values:
            raise ValueError("membership proof target is not occupied")
        node = (1 << self.height) + slot
        needed = {}
        for level in range(self.height):
            if (node ^ 1) in self.digests:
                needed[level] = node ^ 1
            node //= 2
        return needed


@dataclass(frozen=True)
class MetadataEntry:
    left: int
    right: int
    proof_level: int
    node_index: int


@dataclass
class SMTLayout:
    tree: SparseSMT
    color_strategy: str
    width: int
    active_records: dict[int, bytes]
    buckets: dict[int, list[int]]
    metadata: dict[int, list[MetadataEntry]]
    proof_nodes: list[ProofNode]
    forest: list[ProofNode]
    timings_ms: dict[str, float]
    passes: int = 0
    moves: int = 0
    _left_endpoints: dict[int, list[int]] = field(default_factory=dict)
    _rank: dict[int, int] = field(default_factory=dict)

    @property
    def height(self): return self.tree.height
    @property
    def slots(self): return self.tree.slots
    @property
    def values(self): return self.tree.values
    @property
    def root(self): return self.tree.root
    @property
    def defaults(self): return self.tree.defaults

    def selection(self, slot: int, rng: random.Random | None = None) -> list[dict]:
        """Private client context, including dummy roles; not server metadata."""
        if slot not in self._rank:
            raise ValueError("target is not an occupied slot")
        rng = rng or random.Random(0)
        rank = self._rank[slot]
        result = []
        for color in range(1, self.width + 1):
            entries = self.metadata[color]
            pos = bisect.bisect_right(self._left_endpoints[color], rank) - 1
            real = pos >= 0 and entries[pos].left <= rank <= entries[pos].right
            if not real:
                pos = rng.randrange(len(entries)) if entries else 0
            entry = entries[pos] if entries else None
            result.append({"color": color, "index": pos, "real": real,
                           "proof_level": entry.proof_level if real else None,
                           "node_index_hex": hex(entry.node_index) if entry else None})
        return result


def build_layout(height: int, slots: Sequence[int], values: Mapping[int, bytes] | None = None,
                 *, color_strategy: str = "activebalance", refine_rounds: int = 20,
                 hybrid_rounds: int = 60) -> SMTLayout:
    """Build real records and the current first-fit/hybrid/ActiveBalance layout."""
    if color_strategy not in ("first_fit", "hybrid", "activebalance"):
        raise ValueError("unknown color strategy")
    if refine_rounds < 0 or hybrid_rounds < 0:
        raise ValueError("round counts must be nonnegative")
    timings = {}
    start = perf_counter()
    tree = SparseSMT.build(height, slots, values)
    timings["hash_tree"] = (perf_counter() - start) * 1000
    occupied = [(1 << height) + s for s in tree.slots]
    start = perf_counter()
    if len(occupied) > 1:
        helper = FixedSparseMerkleColoring(original_height=height, occupied_leaves=occupied)
        nodes = build_full_proof_nodes(helper.raw_nodes, occupied, height)
    else:
        nodes = []
    timings["active_extraction"] = (perf_counter() - start) * 1000
    start = perf_counter()
    forest = build_interval_forest(nodes)
    width = max_chain_length(forest)
    timings["forest_build"] = (perf_counter() - start) * 1000
    passes = moves = 0
    start = perf_counter()
    if width:
        if color_strategy == "activebalance":
            _, passes, moves = best_count_profile_balanced(nodes, forest, width, refine_rounds)
        elif color_strategy == "first_fit":
            first_fit_coloring(forest, width)
        else:
            color_proof_nodes(nodes, forest, width, "hybrid", hybrid_rounds)
    timings["coloring"] = (perf_counter() - start) * 1000
    start = perf_counter()
    active = {node.index: tree.digests[node.index] for node in nodes}
    metadata: dict[int, list[MetadataEntry]] = {c: [] for c in range(1, width+1)}
    for node in nodes:
        if node.color not in metadata:
            raise AssertionError("uncolored proof node")
        metadata[node.color].append(MetadataEntry(node.interval_left, node.interval_right,
                                                  height-node.depth, node.index))
    for entries in metadata.values():
        entries.sort(key=lambda e: (e.left, e.right, e.node_index))
        if any(a.right >= b.left for a, b in zip(entries, entries[1:])):
            raise AssertionError("same-color service intervals overlap")
    buckets = {c: [entry.node_index for entry in entries] for c, entries in metadata.items()}
    timings["metadata_build"] = (perf_counter() - start) * 1000
    return SMTLayout(tree, color_strategy, width, active, buckets, metadata, nodes, forest,
                     timings, passes, moves,
                     {c: [entry.left for entry in entries] for c, entries in metadata.items()},
                     {s: r for r, s in enumerate(tree.slots)})


def reconstruct_proof(layout: SMTLayout, target_slot: int, recovered_by_color: Mapping[int, bytes],
                      selection: Sequence[dict]) -> list[bytes]:
    """Assemble proof from decoded records and the client's selection map.

    It deliberately does not compare with expected digests. Cryptographic
    integrity is checked separately by verify_proof against a trusted root.
    """
    if target_slot not in layout.values:
        raise ValueError("target is not occupied")
    if len(selection) != layout.width or {x["color"] for x in selection} != set(range(1, layout.width+1)):
        raise ValueError("selection must contain each color exactly once")
    if set(recovered_by_color) != set(range(1, layout.width+1)):
        raise ValueError("each color must have a decoded record, including dummies")
    proof = list(layout.defaults[:layout.height])
    used = set()
    for item in selection:
        digest = recovered_by_color[item["color"]]
        if not isinstance(digest, bytes) or len(digest) != DIGEST_BYTES:
            raise ValueError("record must contain exactly 32 bytes")
        if not item["real"]:
            continue
        level = item["proof_level"]
        if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level < layout.height or level in used:
            raise ValueError("invalid or duplicate proof level")
        proof[level] = digest
        used.add(level)
    return proof


def write_record_manifest(*, height: int, scheme: str, active_nodes: int,
                          bucket_records: Mapping[int, Sequence[bytes]],
                          query_indices: Mapping[int, Sequence[int]], output_dir: Path,
                          warmup_queries: int = 0, query_samples: int | None = None) -> Path:
    """Generic 32-byte manifest writer, also usable by independently built controls.

    Empty physical buckets get one zero dummy record. For width=0 provide
    query_samples explicitly, since it cannot be inferred from an empty map.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if set(bucket_records) != set(query_indices):
        raise ValueError("bucket and query colors differ")
    lengths = {len(v) for v in query_indices.values()}
    if len(lengths) > 1:
        raise ValueError("all buckets must serve the same number of samples")
    inferred = next(iter(lengths), 0)
    if query_samples is None:
        query_samples = inferred
    if lengths and query_samples != inferred:
        raise ValueError("query_samples does not match index arrays")
    subdatabases = []
    for color in sorted(bucket_records):
        records = list(bucket_records[color]) or [bytes(DIGEST_BYTES)]
        if any(not isinstance(x, bytes) or len(x) != DIGEST_BYTES for x in records):
            raise ValueError("database records must be 32-byte strings")
        indices = list(query_indices[color])
        if any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(records) for i in indices):
            raise ValueError("query index outside database")
        db_path = output_dir / f"color_{color:02d}.bin"
        db_path.write_bytes(b"".join(records))
        subdatabases.append({"color": color, "records": len(records), "record_bytes": DIGEST_BYTES,
                            "database_file": db_path.name, "query_indices": indices})
    manifest = {"scheme": scheme, "height": height, "width": len(subdatabases),
                "active_nodes": active_nodes, "query_samples": query_samples,
                "record_bytes": DIGEST_BYTES, "warmup_queries": warmup_queries,
                "subdatabases": subdatabases, "hash_format": HASH_FORMAT}
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def export_manifest(layout: SMTLayout, target_slots: Sequence[int], output_dir: Path, *,
                    seed: int = 20260910, warmup_queries: int = 0) -> Path:
    """Write real records plus separate private verification context for the test client."""
    rng = random.Random(seed)
    selections = [layout.selection(s, rng) for s in target_slots]
    records = {c: [layout.active_records[node] for node in nodes] for c, nodes in layout.buckets.items()}
    query_indices = {c: [sel[c-1]["index"] for sel in selections] for c in layout.buckets}
    path = write_record_manifest(height=layout.height, scheme="SparseTreePIR-"+layout.color_strategy,
                                 active_nodes=len(layout.active_records), bucket_records=records,
                                 query_indices=query_indices, output_dir=output_dir,
                                 query_samples=len(target_slots), warmup_queries=warmup_queries)
    context = {"height": layout.height, "root_hex": layout.root.hex(), "hash_format": HASH_FORMAT,
               "notice": "PRIVATE experiment client context; never publish target roles to a PIR server.",
               "targets": [{"sample_index": i, "slot_hex": hex(slot),
                            "value_hex": layout.values[slot].hex(), "expected_root_hex": layout.root.hex(),
                            "expected_proof_hex": [x.hex() for x in layout.tree.proof(slot)],
                            "selection": selections[i]} for i, slot in enumerate(target_slots)]}
    (Path(output_dir)/"client_context.json").write_text(json.dumps(context, indent=2)+"\n", encoding="utf-8")
    return path
