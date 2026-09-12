"""Independent stdlib audit of Fuel's capacity22 witness and all hash proofs."""
from pathlib import Path
import hashlib, json, struct

ROOT = Path(__file__).absolute().parents[1]
OUT = ROOT/'examples/tifs_remaining_gap_20260910/fuel'
BASE = ROOT/'examples/tifs_revision_20260910/verified_backend/fuel_h128/activebalance'
H = lambda b: hashlib.sha256(b).digest()

def main():
    wpath=OUT/'capacity22_result.json'
    witness=json.loads(wpath.read_text(encoding='utf8'))
    raw=(BASE/'layout_metadata.bin').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==witness['source_sha256']
    assert raw[:8]==b'TIFSMETA'
    h,n,m=struct.unpack_from('>HII',raw,8)
    sb=(BASE/'occupied_slots.bin').read_bytes()
    slots=[int.from_bytes(sb[i:i+16],'big') for i in range(0,len(sb),16)]
    assert h==128 and n==100 and m==9 and len(slots)==n and slots==sorted(set(slots))
    defaults=[H(b'\x02')]
    for _ in range(h): defaults.append(H(b'\x01'+defaults[-1]+defaults[-1]))
    values={s:H(b'TIFS-revision-value\x00'+h.to_bytes(2,'big')+s.to_bytes(16,'big')) for s in slots}
    current={(1<<h)+s:H(b'\x00'+values[s]) for s in slots}
    digests=dict(current)
    for level in range(h):
        parents={v//2 for v in current}
        current={p:H(b'\x01'+current.get(2*p,defaults[level])+current.get(2*p+1,defaults[level])) for p in parents}
        digests.update(current)
    root=digests[1]
    records={};offset=18;hashes={}
    for _ in range(m):
        c,length=struct.unpack_from('>II',raw,offset);offset+=8
        path=BASE/'repeat0'/f'color_{c:02d}.bin';payload=path.read_bytes()
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(payload).hexdigest()
        assert len(payload)==32*length
        for _ in range(length):
            l,r,lev,flags,pos=struct.unpack_from('>QQHHI',raw,offset);offset+=24
            assert flags==0 and 0<=pos<length
            node=(((1<<h)+slots[l])>>lev)^1
            digest=payload[pos*32:(pos+1)*32]
            assert digest==digests[node]
            records[c,pos]=(l,r,lev,node,digest)
    assert offset==len(raw) and len(records)==198
    assert len(witness['records'])==198
    assigned={};buckets={c:[] for c in range(m)}
    for r in witness['records']:
        key=(r['original_color'],r['original_position'])
        assert key in records and key not in assigned
        assert (r['left'],r['right'],r['level'])==records[key][:3]
        c=r['witness_color'];assert isinstance(c,int) and 0<=c<m
        assigned[key]=c;buckets[c].append(records[key])
    assert all(len(v)==22 for v in buckets.values())
    proofs=[]
    for rank,s in enumerate(slots):
        proof=list(defaults[:h]);used=set();selected=[]
        for c,entries in buckets.items():
            hits=[r for r in entries if r[0]<=rank<=r[1]]
            assert len(hits)<=1
            if hits:
                _,_,level,node,digest=hits[0]
                assert level not in used and node==((((1<<h)+s)>>level)^1)
                proof[level]=digest;used.add(level);selected.append(c)
        x=H(b'\x00'+values[s])
        for level,sibling in enumerate(proof):
            expected=digests.get(((((1<<h)+s)>>level)^1),defaults[level])
            assert sibling==expected
            x=H(b'\x01'+(sibling+x if (s>>level)&1 else x+sibling))
        assert x==root
        proofs.append(dict(rank=rank,slot=hex(s),selected_colors=selected,active_records=len(selected),root_verified=True))
    out=dict(status='pass',scope='Offline recoloring and byte/hash audit; no PIR calls or timing claims.',
             witness_sha256=hashlib.sha256(wpath.read_bytes()).hexdigest(),
             audit_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             metadata_sha256=hashlib.sha256(raw).hexdigest(),slots_sha256=hashlib.sha256(sb).hexdigest(),
             payload_sha256=hashes,root_hex=root.hex(),unique_records=198,capacity=22,
             loads=[len(buckets[c]) for c in range(m)],all_occupied_proofs_verified=100,proofs=proofs)
    (OUT/'independent_witness_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in out.items() if k not in ['proofs','payload_sha256']},indent=2))

if __name__=='__main__':main()
