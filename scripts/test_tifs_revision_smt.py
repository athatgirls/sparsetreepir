"""Bounded reproducible correctness checks; no PIR execution or performance claim.

Run from the workspace root: python scripts/test_tifs_revision_smt.py
The JSON/CSV report records actual checks and explicitly separates direct
decoded-record simulation from a cryptographic backend run.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from time import perf_counter

from tifs_revision_smt import (
    HASH_FORMAT, SparseSMT, build_layout, export_manifest, leaf_digest,
    parent_digest, reconstruct_proof, verify_proof, write_record_manifest,
)


def flip(data: bytes) -> bytes:
    return bytes([data[0] ^ 1]) + data[1:]


def dense_reference(tree: SparseSMT) -> tuple[bytes, dict[int, list[bytes]]]:
    """Independent dense level reduction for small-height cross-checking."""
    level = [leaf_digest(tree.values[s]) if s in tree.values else tree.defaults[0]
             for s in range(1 << tree.height)]
    levels = [level]
    for _ in range(tree.height):
        level = [parent_digest(level[i], level[i+1]) for i in range(0, len(level), 2)]
        levels.append(level)
    proofs = {s: [levels[k][(s >> k) ^ 1] for k in range(tree.height)] for s in tree.slots}
    return level[0], proofs


def validate_layout(label: str, height: int, slots: list[int], strategy: str,
                    counts: Counter, rows: list[dict], *, dense=False, rounds=20):
    start = perf_counter()
    layout = build_layout(height, slots, color_strategy=strategy, refine_rounds=rounds, hybrid_rounds=20)
    needed_union = set()
    for s in layout.slots:
        needed_union.update(layout.tree.proof_record_nodes(s).values())
    assert needed_union == set(layout.active_records), (label, "active records mismatch")
    assert len(layout.active_records) == max(0, 2*len(slots)-2), (label, "branch record count")
    assert sum(map(len, layout.buckets.values())) == len(layout.active_records)
    assert set(n for bucket in layout.buckets.values() for n in bucket) == needed_union
    observed_width = max((len(layout.tree.proof_record_nodes(s)) for s in layout.slots), default=0)
    assert layout.width == observed_width, (label, "not exact width")
    assert layout.width <= min(height, max(0, len(slots)-1))
    counts["layouts"] += 1
    if dense:
        root, proofs = dense_reference(layout.tree)
        assert root == layout.root
        assert all(proofs[s] == layout.tree.proof(s) for s in slots)
        counts["dense_tree_crosschecks"] += 1
    rng = random.Random(9191)
    for slot in layout.slots:
        selection = layout.selection(slot, rng)
        decoded = {item["color"]: layout.active_records[layout.buckets[item["color"]][item["index"]]]
                   for item in selection}
        real_records = {item["proof_level"]: int(item["node_index_hex"],16)
                        for item in selection if item["real"]}
        assert real_records == layout.tree.proof_record_nodes(slot)
        proof = reconstruct_proof(layout, slot, decoded, selection)
        assert proof == layout.tree.proof(slot), (label, slot, "proof mismatch")
        assert verify_proof(height,slot,layout.values[slot],proof,layout.root)
        counts["verified_membership_proofs"] += 1
        counts["dummy_records_discarded"] += sum(not item["real"] for item in selection)
        assert not verify_proof(height,slot,layout.values[slot],proof,flip(layout.root))
        counts["wrong_root_rejected"] += 1
        assert not verify_proof(height,slot,flip(layout.values[slot]),proof,layout.root)
        counts["wrong_value_rejected"] += 1
        if height:
            bad_proof = list(proof)
            bad_proof[0] = flip(bad_proof[0])
            assert not verify_proof(height,slot,layout.values[slot],bad_proof,layout.root)
            counts["proof_bitflip_rejected"] += 1
        real = [item for item in selection if item["real"]]
        if real:
            color = real[0]["color"]
            corrupt = dict(decoded)
            corrupt[color] = flip(corrupt[color])
            bad_proof = reconstruct_proof(layout,slot,corrupt,selection)
            assert not verify_proof(height,slot,layout.values[slot],bad_proof,layout.root)
            counts["decoded_record_bitflip_rejected"] += 1
            changed = copy.deepcopy(selection)
            next(x for x in changed if x["color"] == color)["proof_level"] = height
            try:
                reconstruct_proof(layout,slot,decoded,changed)
            except ValueError:
                counts["out_of_range_level_rejected"] += 1
            else:
                raise AssertionError("out-of-range metadata was accepted")
            if height > 1:
                changed = copy.deepcopy(selection)
                item = next(x for x in changed if x["color"] == color)
                item["proof_level"] = (item["proof_level"]+1) % height
                try:
                    bad_proof = reconstruct_proof(layout,slot,decoded,changed)
                except ValueError:
                    pass  # A duplicate proof-level is malformed and rejected.
                else:
                    assert not verify_proof(height,slot,layout.values[slot],bad_proof,layout.root)
                counts["wrong_in_range_level_rejected"] += 1
        for item in selection:
            if not item["real"]:
                changed = dict(decoded)
                changed[item["color"]] = flip(changed[item["color"]])
                proof2 = reconstruct_proof(layout,slot,changed,selection)
                assert verify_proof(height,slot,layout.values[slot],proof2,layout.root)
                counts["dummy_mutation_ignored"] += 1
                break
    rows.append({"case": label, "height": height, "occupied":len(slots),
                 "strategy":strategy, "active_records":len(layout.active_records),
                 "width":layout.width,"max_bucket":max(map(len,layout.buckets.values()),default=0),
                 "proofs_checked":len(slots),"materialized_hash_nodes":len(layout.tree.digests),
                 "passed":True,"check_runtime_ms":(perf_counter()-start)*1000})
    return layout


def manifest_roundtrip(layout, folder: Path, counts: Counter):
    path = export_manifest(layout, layout.slots, folder, seed=610)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    contexts = json.loads((folder/"client_context.json").read_text(encoding="utf-8"))["targets"]
    assert manifest["width"] == layout.width
    assert manifest["query_samples"] == len(layout.slots)
    for context in contexts:
        sample = context["sample_index"]
        decoded = {}
        for db in manifest["subdatabases"]:
            data = (folder/db["database_file"]).read_bytes()
            assert len(data) == db["records"]*32
            i = db["query_indices"][sample]
            decoded[db["color"]] = data[32*i:32*(i+1)]
        slot = int(context["slot_hex"],16)
        proof = reconstruct_proof(layout,slot,decoded,context["selection"])
        assert [p.hex() for p in proof] == context["expected_proof_hex"]
        assert verify_proof(layout.height,slot,bytes.fromhex(context["value_hex"]),proof,
                            bytes.fromhex(context["expected_root_hex"]))
        counts["manifest_binary_roundtrip_proofs"] += 1
    counts["manifest_roundtrip_layouts"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("examples/tifs_revision_20260910/correctness"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    counts = Counter()
    rows = []
    started = perf_counter()
    # Exhaust every occupancy mask, including empty, through h=3.
    for height in range(4):
        for mask in range(1 << (1 << height)):
            slots = [s for s in range(1 << height) if mask & (1 << s)]
            validate_layout(f"exhaustive_h{height}_mask{mask}",height,slots,"activebalance",counts,rows,dense=True)
    print("Exhaustive occupancy h=0..3 passed", flush=True)
    export_candidates = []
    for height in (128,256):
        cases = [("empty",[]),("singleton",[7]),("two_adjacent",[7,8]),
                 ("two_opposite",[0,(1<<height)-1]),("clustered64",list(range(64))),
                 ("shared_prefix17",[(1<<(height-1))+x for x in range(17)])]
        for seed in (8101,8102,8103):
            rng = random.Random(seed)
            slots = sorted({rng.getrandbits(height) for _ in range(32)})
            cases.append((f"uniform32_seed{seed}",slots))
        for label,slots in cases:
            for strategy in ("first_fit","hybrid","activebalance"):
                layout=validate_layout(f"h{height}_{label}",height,slots,strategy,counts,rows)
                if strategy=="activebalance" and label in ("singleton","uniform32_seed8101"):
                    export_candidates.append((f"h{height}_{label}",layout))
        print(f"All h={height} targets and three layouts passed",flush=True)
    for label,layout in export_candidates:
        manifest_roundtrip(layout,args.output_dir/label,counts)
    # The generic writer's empty bucket is a physical dummy, not an active record.
    path=write_record_manifest(height=4,scheme="empty-bucket-check",active_nodes=0,
                               bucket_records={1:[]},query_indices={1:[0]},
                               output_dir=args.output_dir/"empty_bucket")
    m=json.loads(path.read_text(encoding="utf-8"))
    assert m["subdatabases"][0]["records"]==1
    assert (path.parent/"color_01.bin").read_bytes()==bytes(32)
    counts["empty_bucket_manifest_checks"]+=1
    for invalid in ([0,0],[-1],[256]):
        try: SparseSMT.build(8,invalid)
        except ValueError: counts["invalid_slot_inputs_rejected"]+=1
        else: raise AssertionError("invalid input accepted")
    source_paths=[Path(__file__),Path(__file__).with_name("tifs_revision_smt.py"),
                  Path(__file__).with_name("run_height_sparsity_profile_balance_experiment.py"),
                  Path(__file__).with_name("run_sparse_smt_pir_backend_experiment.py"),
                  Path(__file__).with_name("generate_full_sparse_smt_example.py")]
    report={"status":"passed","hash_format":HASH_FORMAT,"counts":dict(counts),
            "wall_seconds":perf_counter()-started,
            "scope":"Real SHA-256 SMT and exact-width first-fit/hybrid/ActiveBalance correctness; decoded records are read directly in these tests. No cryptographic PIR execution or performance claim.",
            "enumeration":"Every occupied subset (including empty) at h=0,1,2,3; every occupied target. Independent dense reference roots/proofs.",
            "large_heights":"h=128,256; empty/singleton/two-leaf/clustered/shared-prefix and 3 fixed random samples of 32 slots; every occupied target for all 3 layouts.",
            "source_sha256":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}}
    (args.output_dir/"correctness_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    with (args.output_dir/"correctness_cases.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (args.output_dir/"README.md").write_text(
        "# TIFS revision correctness checks\n\nRun: `python scripts/test_tifs_revision_smt.py` from the workspace root.\n\n"
        "The JSON report and CSV contain completed checks. Small heights exhaust all occupancy masks and use an independent dense reference; h=128/256 never materialize a full coordinate tree.\n\n"
        "This directory tests real hashes, metadata lookup, digest-record serialization and root reconstruction. The records are read directly during verification; actual PIR runs belong in a separate backend report. Client context files are private test inputs and contain queried target identities and real/dummy roles.\n",
        encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__": main()
