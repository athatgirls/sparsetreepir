"""Explicit comb-pair construction and two failed proof bridges, with SMT checks."""
from pathlib import Path
import hashlib, json, math, platform, time
import explore_remaining_joint_anchors_20260910 as joint
import explore_tifs_anchored_capacity_20260910 as exact
from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
from generate_full_sparse_smt_example import build_full_proof_nodes,build_interval_forest
from tifs_revision_smt import SparseSMT,verify_proof

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/tifs_sufficiency_20260910/theory/constructions'
def dump(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8')
def comb(n):return () if n==1 else ((),comb(n-1))

def comb_pair(a,b):
    assert a>=b>=1
    tree=tuple(sorted((comb(a),comb(b))));nodes,roots=joint.index_forest(tree)
    big=max(roots,key=lambda v:nodes[v]['leaves']);small=next(v for v in roots if v!=big)
    bigids=list(range(big,big+nodes[big]['size']));smallids=list(range(small,small+nodes[small]['size']))
    U=math.ceil((2*a+2*b-2)/a);colors=[-1]*len(nodes)
    for v in bigids:colors[v]=nodes[v]['depth']-1
    if U==2:
        assert b==1;colors[small]=0
    elif U==3:
        assert a>=2*b-2
        last=max((v for v in smallids if nodes[v]['children']),key=lambda v:nodes[v]['depth'])
        pair=nodes[last]['children'];assert len(pair)==2 and all(not nodes[v]['children'] for v in pair)
        for v in pair:colors[v]=0
        for c,v in enumerate((v for v in smallids if v not in pair),1):colors[v]=c
    else:
        assert U==4
        for v in smallids:colors[v]=nodes[v]['depth']-1
    loads=exact.verify(tree,colors,a);assert max(loads)==U
    return tree,colors,loads,U

def actual_certificate(tree,colors,U):
    h,slots=exact.smt_slots(tree);smt=SparseSMT.build(h,slots);occupied=[(1<<h)+s for s in slots]
    helper=FixedSparseMerkleColoring(h,occupied);proofnodes=build_full_proof_nodes(helper.raw_nodes,occupied,h);roots=build_interval_forest(proofnodes)
    ordered=[]
    def shape(v):ordered.append(v);return tuple(shape(w) for w in v.children)
    assert tuple(shape(v) for v in roots)==tree
    m=exact.height(tree)-1;loads=exact.verify(tree,colors,m);assert max(loads)==U
    colorbyid={v.index:c for v,c in zip(ordered,colors)};proofs=[]
    for slot in slots:
        needed=smt.proof_record_nodes(slot);assert len({colorbyid[v] for v in needed.values()})==len(needed)
        proof=list(smt.defaults[:h])
        for level,v in needed.items():proof[level]=smt.digests[v]
        assert proof==smt.proof(slot) and verify_proof(h,slot,smt.values[slot],proof,smt.root)
        proofs.append({'slot':slot,'real_siblings':[{'level':level,'heap_index':hex(v),'digest_hex':smt.digests[v].hex(),'color':colorbyid[v]} for level,v in needed.items()],'root_verified':True})
    return {'shape':tree,'height':h,'m':m,'N':len(ordered),'slots':slots,'capacity':U,
            'colors_preorder':colors,'loads':loads,'root_hex':smt.root.hex(),
            'interval_forest_matches':True,'all_target_proofs_verified':True,
            'records':[{'heap_index':hex(v.index),'interval':[v.interval_left,v.interval_right],
                        'color':c,'digest_hex':smt.digests[v.index].hex()} for v,c in zip(ordered,colors)],'proofs':proofs}

def main():
    if (OUT/'summary.json').exists():raise RuntimeError('preserve prior outputs')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'actual_smt').mkdir(exist_ok=True)
    started=time.monotonic();rows=[];proofs=0
    for a in range(1,21):
        for b in range(1,a+1):
            tree,colors,loads,U=comb_pair(a,b);bound=joint.joint_bound(tree);assert bound['B_joint']==U
            cert=actual_certificate(tree,colors,U);proofs+=len(cert['proofs']);name=f'comb_{a}_{b}.json';dump(OUT/'actual_smt'/name,cert)
            rows.append({'a':a,'b':b,'N':len(colors),'m':a,'average_bound':U,'B_joint':bound['B_joint'],'constructive_max_load':max(loads),'loads':loads,'certificate':'actual_smt/'+name,'proofs':len(cert['proofs'])})
    dump(OUT/'comb_pairs.json',rows)
    # The full-profile choice cannot be replaced by a locally min-max profile.
    P=exact.perfect(4);local=sorted(exact.profiles(P,3,3));assert local==[(1,3,3)]
    merged=sorted(exact.merged(local[0],local[0],100));assert min(max(v) for v in merged)==6
    flexible=tuple(sorted(exact.profiles(P,3,4)));assert (1,2,4) in flexible
    globalcert=exact.actual_smt_certificate((P,P),5);dump(OUT/'independent_balancing_counterexample_actual_smt.json',globalcert)
    failure={'forest':(P,P),'m':3,'local_minimum_cap':3,'only_profiles_at_local_minimum':local,'best_merge_of_local_optima':6,
             'alternative_each_profile':[1,2,4],'opposite_merge':[5,4,5],'global_average_bound_and_optimum':5,
             'actual_smt_certificate':'independent_balancing_counterexample_actual_smt.json'}
    dump(OUT/'failed_local_balancing_induction.json',failure)
    cherry=((),());hu=exact.actual_smt_certificate((cherry,cherry),3);dump(OUT/'failed_monotone_scheduling_bridge_actual_smt.json',hu)
    summary={'scope':'all pairs 1<=b<=a<=20; explicit construction, not exact-search coloring',
             'comb_pairs':len(rows),'comb_pair_actual_target_proofs':proofs,'all_valid':True,
             'unbounded_theorem':'all integers a>=b>=1 have OPT=ceil((2a+2b-2)/a)',
             'new_bound_required_for_this_subclass':False,
             'induction_counterexample_proofs':len(globalcert['proofs']),
             'monotone_bridge_counterexample_proofs':len(hu['proofs']),
             'seconds':time.monotonic()-started,'python':platform.python_version(),
             'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dump(OUT/'summary.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
