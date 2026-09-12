"""Dense-tree verification of the explanatory example; no PIR or timing run."""
from pathlib import Path
from hashlib import sha256
import json
import argparse

def H(x): return sha256(x).digest()

def run():
    height=6
    keys=[0,4,16,24,32,48,56]
    default=[H(b'empty')]
    for _ in range(height): default.append(H(b'node'+default[-1]+default[-1]))
    values={x:('example-value-'+str(x)).encode() for x in keys}
    digests={64+x:(H(b'leaf'+x.to_bytes(1,'big')+values[x]) if x in values else default[0]) for x in range(64)}
    counts={64+x:int(x in values) for x in range(64)}
    for u in range(63,0,-1):
        digests[u]=H(b'node'+digests[2*u]+digests[2*u+1])
        counts[u]=counts[2*u]+counts[2*u+1]
    prefix=lambda u:bin(u)[3:]
    active=[u for u in range(2,128) if counts[u]>0 and counts[u^1]>0]
    rows=[]
    for u in active:
        sibling_prefix=prefix(u^1)
        ranks=[r for r,x in enumerate(keys) if format(x,'06b').startswith(sibling_prefix)]
        rows.append({'node':u,'prefix':prefix(u),'interval':[min(ranks),max(ranks)],'level':height-len(prefix(u))})
    assert len(rows)==12
    for row in rows:
        a,b=row['interval']
        row['color']=1+sum(r['interval'][0]<=a<=b<=r['interval'][1] and r is not row for r in rows)
    by_color={c:sorted([r for r in rows if r['color']==c],key=lambda r:r['interval']) for c in (1,2,3)}
    for c,rr in by_color.items():
        for j,row in enumerate(rr):row['index']=j
    assert [len(by_color[c]) for c in (1,2,3)]==[2,4,6]
    assert {c:[tuple(r['interval']) for r in rr] for c,rr in by_color.items()}=={
        1:[(0,3),(4,6)],2:[(0,1),(2,3),(4,4),(5,6)],3:[(0,0),(1,1),(2,2),(3,3),(5,5),(6,6)]}
    def root_for(x,proof):
        z=digests[64+x]
        for level,sib in enumerate(proof):
            z=H(b'node'+(sib+z if (x>>level)&1 else z+sib))
        return z
    targets=[]
    for rank,x in enumerate(keys):
        proof=default[:height]
        selections=[]
        for c in (1,2,3):
            hits=[r for r in by_color[c] if r['interval'][0]<=rank<=r['interval'][1]]
            assert len(hits)<=1
            row=hits[0] if hits else by_color[c][0]
            selections.append({'color':c,'index':row['index'],'real':bool(hits),
                               'prefix':row['prefix'],'restore_level':row['level'] if hits else None})
            if hits:proof[row['level']]=digests[row['node']]
        u=64+x
        oracle=[]
        while u>1:oracle.append(digests[u^1]);u//=2
        assert proof==oracle
        assert root_for(x,proof)==digests[1]
        targets.append({'coordinate':x,'rank':rank,'selections':selections,
                        'proof_hex':[d.hex() for d in proof],'root_verified':True})
    def selected(x):return [(r['index'],r['prefix'],r['restore_level']) for r in targets[keys.index(x)]['selections']]
    assert selected(24)==[(0,'1',5),(1,'00',4),(3,'010',3)]
    assert selected(32)==[(1,'0',5),(2,'11',4),(0,'0001',None)]
    assert selected(0)==[(0,'1',5),(0,'01',4),(0,'0001',2)]
    corrupted=[bytes.fromhex(z) for z in targets[keys.index(32)]['proof_hex']]
    corrupted[2]=digests[int('1'+'0001',2)]
    assert root_for(32,corrupted)!=digests[1]
    return {'purpose':'Explanatory example; direct digest reads, not a PIR benchmark',
            'hash_encoding':'SHA-256: empty; leaf||one-byte coordinate||example-value-X; node||left||right',
            'height':height,'occupied_coordinates':keys,'root_hex':digests[1].hex(),
            'records':12,'logical_queries_per_target':3,'targets_checked':7,'proof_levels_checked':42,
            'dummy_overwrite_rejected':True,'all_verified':True,
            'directory_rows':sorted(rows,key=lambda r:(r['color'],r['index'])),'targets':targets}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(__file__).absolute().parents[1]);args=ap.parse_args()
    result=run();dest=args.output/'verification/worked_batch_example.json';dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('7 targets, 42 proof levels; all verify; erroneous dummy insertion rejected. No PIR execution.')
