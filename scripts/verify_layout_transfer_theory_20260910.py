"""Independent stdlib verification of the five frozen-state paths and certificates."""
from pathlib import Path
import hashlib,json,collections
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/tifs_layout_transfer_20260910/theory'
SOURCE=ROOT/'examples/tifs_sufficiency_20260910/construction'
def H(x):return hashlib.sha256(x).digest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf8')
def parent_hash(a,b):return H(b'\x01'+a+b)

def main():
    if (OUT/'independent_verification.json').exists():raise RuntimeError('preserve outputs')
    audit=json.loads((OUT/'five_case_analysis.json').read_text())
    originals={r['id']:r for name in ['base_construction_results.json','holdout_construction_results.json'] for r in json.loads((SOURCE/name).read_text())}
    results=[];constraint_count=0;proof_count=0
    (OUT/'verified_paths').mkdir(exist_ok=True)
    for row in audit:
        orig=originals[row['id']];rec=orig['records'];idx={r['heap_node']:i for i,r in enumerate(rec)};parents=[idx.get(r['parent'],-1) for r in rec]
        c0=orig['final_colors'];w=row['neutral_then_strict_witness'];c1=w['neutral_colors'];c2=w['optimal_colors'];m=orig['m'];L=orig['OPT']
        stages={'initial':c0,'neutral':c1,'optimal':c2}
        sigs={}
        for stage,c in stages.items():
            assert len(c)==len(rec) and all(1<=v<=m for v in c)
            for v in range(len(rec)):
                p=parents[v]
                while p>=0:assert c[v]!=c[p];p=parents[p]
            sigs[stage]=sorted(collections.Counter(c).values(),reverse=True)
        assert sigs['initial']==sigs['neutral']==[L+1]+[L]*(m-2)+[L-1]
        assert sigs['optimal']==[L]*m
        for a,b,palette in [(c0,c1,w['neutral_palette']),(c1,c2,w['strict_palette'])]:
            assert len(palette)==4
            for old,new in zip(a,b):
                if old!=new:assert old in palette and new in palette
        support={label for old,new in zip(c0,c2) if old!=new for label in (old,new)}
        assert len(support)>=5
        # Rebuild each selected forest from original parents; do not call the
        # searcher's projection, beta recurrence, DP, or bound implementation.
        for pcase in row['critical_four_palettes']:
            palette=set(pcase['palette']);selected={v for v,c in enumerate(c0) if c in palette};child={v:[] for v in selected};roots=[]
            for v in sorted(selected):
                p=parents[v]
                while p>=0 and p not in selected:p=parents[p]
                if p<0:roots.append(v)
                else:child[p].append(v)
            nodes=[]
            def visit(v,parent):
                i=len(nodes);nodes.append({'parent':parent,'children':[]})
                for c in child[v]:nodes[i]['children'].append(visit(c,i))
                nodes[i]['end']=len(nodes);nodes[i]['height']=1+max((nodes[j]['height'] for j in nodes[i]['children']),default=0)
                return i
            rids=[visit(v,-1) for v in roots]
            def shape(v):return [shape(c) for c in nodes[v]['children']]
            assert [shape(r) for r in rids]==pcase['forest']
            wit=pcase['structural_witness'];assert wit['type']=='joint_anchors' and wit['context']==-1 and wit['q']==4
            anchors=[];p=wit['terminal']
            while p>=0:anchors.append(p);p=nodes[p]['parent']
            def ancestor(a,b):return a<=b<nodes[a]['end']
            J=len(anchors)
            for v in range(len(nodes)):
                if v in anchors:continue
                available=sum(not ancestor(a,v) and not ancestor(v,a) for a in anchors)
                J+=nodes[v]['height']<=available
            assert J==wit['J']==len(anchors)*L-1
            assert len(nodes)==4*L and len(nodes)>J+(4-len(anchors))*L
            constraint_count+=1
        # Rebuild the actual SMT and evaluate standard SHA256 proofs directly.
        h=orig['height'];slots=orig['slots'];defaults=[H(b'\x02')]
        for _ in range(h):defaults.append(parent_hash(defaults[-1],defaults[-1]))
        values={s:H(b'TIFS-revision-value\x00'+h.to_bytes(2,'big')+s.to_bytes(max(1,(h+7)//8),'big')) for s in slots}
        current={(1<<h)+s:H(b'\x00'+values[s]) for s in slots};digests=dict(current)
        for level in range(h):
            current={p:parent_hash(current.get(2*p,defaults[level]),current.get(2*p+1,defaults[level])) for p in {v//2 for v in current}}
            digests.update(current)
        root=digests[1];proofs=[];needed_union=set()
        for s in slots:
            v=(1<<h)+s;real=[];proof=[]
            for level in range(h):
                sib=v^1;digest=digests.get(sib,defaults[level]);proof.append(digest)
                if sib in digests:
                    assert sib in idx;needed_union.add(sib);real.append({'level':level,'heap_node':sib,'digest_hex':digest.hex(),'record_index':idx[sib]})
                v//=2
            for stage,c in stages.items():
                assert len({c[r['record_index']] for r in real})==len(real)
                digest=H(b'\x00'+values[s])
                for level,sib in enumerate(proof):digest=parent_hash(sib,digest) if (s>>level)&1 else parent_hash(digest,sib)
                assert digest==root;proof_count+=1
            proofs.append({'slot':s,'value_hex':values[s].hex(),'real_siblings':real,'all_three_layouts_root_verified':True})
        assert needed_union==set(idx)
        evidence={'id':row['id'],'height':h,'m':m,'L':L,'root_hex':root.hex(),'records':rec,'stage_colors':stages,'signatures':sigs,'proofs':proofs}
        dump(OUT/'verified_paths'/f"{row['id']}.json",evidence)
        results.append({'id':row['id'],'signatures':sigs,'critical_palettes_verified':len(row['critical_four_palettes']),
                        'two_legal_four_palette_moves_verified':True,'membership_changed_colors':sorted(support),
                        'proofs_per_layout':len(slots),'layout_count':3,'minimum_number_of_at_most_four_palette_moves_to_OPT':2})
    report={'status':'pass','cases':results,'independent_joint_projection_constraints':constraint_count,
            'actual_target_proofs':proof_count,'proof_scope':'same occupied targets under initial, neutral, optimal layouts',
            'imports_from_coloring_or_SMT_implementation':False,
            'input_sha256':hashlib.sha256((OUT/'five_case_analysis.json').read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dump(OUT/'independent_verification.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
