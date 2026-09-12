"""Small, non-performance tests of the six-layout verified backend driver.

These test root-correct routing from a binary directory and serialized records.
An independent interval scan and a brute-force matching oracle cross-check it.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import struct
import tempfile
from collections import Counter

import run_tifs_verified_backend_suite_20260910 as driver
from tifs_revision_smt import build_layout, verify_proof


def brute_feasible(nodes, choices):
    colors=sorted(set(c for n in nodes for c in choices[n]))
    return any(all(c in choices[n] for n,c in zip(nodes,assignment))
               for assignment in itertools.permutations(colors,len(nodes)))


def test_matching(counts):
    # A genuine Hall violation: four records each have three distinct choices,
    # but their union has only three buckets. No fake failed return is injected.
    choices={n:[1,2,3] for n in range(4)}
    assert driver.matching(list(choices),choices) is None
    counts['hall_failure_rejected']+=1
    choices[3]=[1,2,4]
    assigned=driver.matching(list(choices),choices)
    assert assigned is not None and len(set(assigned.values()))==4
    counts['augmenting_path_success']+=1
    options=list(itertools.combinations(range(1,5),3))
    for picks in itertools.product(options,repeat=4):
        choices=dict(enumerate(picks))
        actual=driver.matching(list(choices),choices)
        feasible=brute_feasible(list(choices),choices)
        assert (actual is not None)==feasible
        if actual is not None:
            assert len(set(actual.values()))==len(choices)
            assert all(c in choices[n] for n,c in actual.items())
        counts['matching_vs_bruteforce_graphs']+=1


def read_metadata(path, expected_slots):
    raw=path.read_bytes()
    assert raw[:8]==b'TIFSMETA'
    h,n,b=struct.unpack_from('>HII',raw,8)
    assert n==len(expected_slots)
    offset=18;entries={}
    for _ in range(b):
        color,size=struct.unpack_from('>II',raw,offset);offset+=8
        entries[color]=[]
        for i in range(size):
            left,right,level,flags,pos=struct.unpack_from('>QQHHI',raw,offset);offset+=24
            assert 0<=left<=right<n and 0<=level<h and flags==0 and pos==i
            entries[color].append((left,right,level,pos))
    assert offset==len(raw)
    expected=b''.join(s.to_bytes((h+7)//8,'big') for s in expected_slots)
    assert path.with_name('occupied_slots.bin').read_bytes()==expected
    return entries


def one_case(h,slots,folder,counts):
    layouts={method:build_layout(h,slots,color_strategy=method,refine_rounds=20,hybrid_rounds=20)
             for method in ('first_fit','hybrid','activebalance')}
    base=layouts['first_fit'];active=base.active_records
    assert all(l.root==base.root for l in layouts.values())
    nodes={n.index:n for n in base.proof_nodes}
    needs={s:driver.need_for(s,h,active) for s in slots}
    assert all(needs[s]==base.tree.proof_record_nodes(s) for s in slots)
    buckets={method:layout.buckets for method,layout in layouts.items()}
    depths=sorted({node.depth for node in base.proof_nodes})
    buckets['nonempty_depth']={c:sorted([n.index for n in base.proof_nodes if n.depth==d],
                                      key=lambda n:nodes[n].interval_left)
                               for c,d in enumerate(depths,1)}
    allids=sorted(active)
    buckets['flat_active']={c:allids for c in range(1,base.width+1)}
    buckets['pbc_routed'],choices,info=driver.pbc_buckets(base,needs)
    assert all(len(set(ch))==len(ch)==3 for ch in choices.values())
    assert all(driver.matching(list(need.values()),choices) is not None for need in needs.values())
    assert info['public_setup_attempts'][-1]['failed_targets']==0
    assert sum(map(len,buckets['pbc_routed'].values()))==3*len(active)
    counts['pbc_all_target_public_preflights']+=1
    for method in driver.METHODS:
        method_folder=folder/method;method_folder.mkdir(parents=True)
        meta_buckets={1:allids} if method=='flat_active' else buckets[method]
        metapath=method_folder/'layout_metadata.bin'
        byte_count=driver.metadata_file(metapath,meta_buckets,nodes,h,slots)
        parsed=driver.read_directory(metapath)
        assert parsed['height']==h and parsed['slots']==slots
        assert set(parsed['locations'])==set(active)
        assert all(parsed['by_position'][c,pos]==node
                   for c,ids in meta_buckets.items() for pos,node in enumerate(ids))
        path,routing,route_times,payload=driver.prepare_manifest(
            base,buckets[method],method,slots,None,None,method_folder/'repeat0',random.Random(11))
        # needs/choices=None ensures no precomputed target->record oracle is used.
        manifest=json.loads(path.read_text(encoding='utf-8'))
        assert manifest['query_samples']==len(slots)
        assert manifest['width']==len(buckets[method])
        assert len(route_times)==len(slots)
        unique_files={x['database_file'] for x in manifest['subdatabases']}
        assert payload==sum((path.parent/f).stat().st_size for f in unique_files)
        if method=='flat_active':
            assert payload==32*len(active)
            assert len(unique_files)==(1 if active else 0)
        for sample,slot in enumerate(slots):
            proof=list(base.defaults[:h]);recovered={}
            for db in manifest['subdatabases']:
                raw=(path.parent/db['database_file']).read_bytes()
                assert len(raw)==32*db['records']
                pos=db['query_indices'][sample]
                assert 0<=pos<db['records']
                recovered[db['color']]=raw[32*pos:32*(pos+1)]
            used=set()
            for color,level in routing[sample].items():
                assert level not in used;used.add(level)
                proof[level]=recovered[int(color)]
            assert used==set(needs[slot])
            assert proof==base.tree.proof(slot)
            assert verify_proof(h,slot,base.values[slot],proof,base.root)
            counts['six_layout_target_proofs']+=1
        entries=read_metadata(metapath,slots)
        assert set(entries)==set(meta_buckets)
        assert byte_count==18+8*len(meta_buckets)+24*sum(map(len,meta_buckets.values()))+len(slots)*math.ceil(h/8)
        # The compact directory actually contains sufficient service intervals
        # and locations; recover all required records by scanning it independently.
        for rank,slot in enumerate(slots):
            found=set()
            for color,records in entries.items():
                for left,right,level,pos in records:
                    if left<=rank<=right:
                        node=meta_buckets[color][pos]
                        assert needs[slot][level]==node
                        found.add((level,node))
            assert found==set(needs[slot].items())
        counts['metadata_binary_roundtrips']+=1
        counts['driver_directory_read_and_route_checks']+=1
    cache=folder/'full_cache';cache.mkdir()
    payload_path=cache/'full_active_cache.bin'
    payload_path.write_bytes(b''.join(active[n] for n in allids))
    meta=cache/'full_cache_metadata.bin'
    bytes_metadata=driver.metadata_file(meta,{1:allids},nodes,h,slots)
    directory=read_metadata(meta,slots)[1];raw=payload_path.read_bytes()
    parsed_cache=driver.read_directory(meta)
    assert len(raw)+bytes_metadata==56*len(active)+26+len(slots)*math.ceil(h/8)
    for rank,slot in enumerate(slots):
        proof=list(base.defaults[:h])
        for left,right,level,pos in directory:
            if left<=rank<=right:proof[level]=raw[32*pos:32*(pos+1)]
        assert verify_proof(h,slot,base.values[slot],proof,base.root)
        routed=list(base.defaults[:h])
        for pos,level in driver.directory_route(parsed_cache,slot,'flat_active',base.width).values():
            routed[level]=raw[32*pos:32*(pos+1)]
        assert routed==proof
        counts['full_cache_disk_reconstruction_proofs']+=1
    counts['cases']+=1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,
                        default=Path('examples/tifs_revision_20260910/correctness/routing_test_report.json'))
    args=parser.parse_args();counts=Counter();test_matching(counts)
    cases=[(3,[0]),(3,[0,1]),(3,[0,7]),(3,list(range(8))),
           (4,[0,1,3,6,12]),(4,[2,3,4,9,10,11,15]),
           (128,[0,1,3,7,31]),(256,[0,1,3,7,31])]
    for h in (128,256):
        rng=random.Random(970+h)
        cases.append((h,sorted({rng.getrandbits(h) for _ in range(24)})))
    with tempfile.TemporaryDirectory(prefix='tifs-routing-') as temp:
        for i,(height,slots) in enumerate(cases):
            one_case(height,slots,Path(temp)/str(i),counts)
    report={'status':'passed','counts':dict(counts),
            'scope':'Six layouts route all occupied targets of ten small test trees, with real digest-record serialization and root verification. Matching checked against brute force on 256 graphs. No PIR run or performance measurement.',
            'metadata_result':'The driver reads the actual binary directory, recovers heap-id positions and routes each target without precomputed needs/choices. Cross-checked with an independent interval scan; index parsing is preprocessing; proper-color and Nonempty-depth queries use per-bucket interval binary search, while flat/PBC queries use h sibling-id lookups.',
            'full_cache_byte_formula':'56*N + 26 + n*ceil(h/8), comprising 32*N payload, 24*N rows, 18-byte header, 8-byte bucket header, and occupied slots.',
            'observed_boundary':'For singleton trees, m=0 and the five non-PBC layouts send zero queries; pbc_buckets currently produces three empty padded buckets. Treat that as a control-specific boundary, not useful PIR work.',
            'driver_sha256':hashlib.sha256(Path(driver.__file__).read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
