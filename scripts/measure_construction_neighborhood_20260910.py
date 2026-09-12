"""Separate construction-only evaluation; existing AB and PIR files are read-only."""
from pathlib import Path
import collections,csv,hashlib,itertools,json,platform,time
from functools import lru_cache
from prototype_construction_kempe_20260910 import graph,loads,signature,valid,improve,improve_three,tree_profiles
from tifs_revision_smt import build_layout,verify_proof
from measure_gap_algorithm_20260910 import slot_embedding
from run_height_sparsity_profile_balance_experiment import best_count_mapping,candidate_loads_after_mapping

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_sufficiency_20260910/construction'
BASE=ROOT/'examples/tifs_remaining_gap_20260910/theory/all_1323_joint_bounds.json'
HOLDOUT=BASE.with_name('expanded_exact_results.json')
OLD=ROOT/'examples/tifs_remaining_gap_20260910/algorithm/small_shape_algorithm_results.json'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf8')

def audit_subtree_neighborhood():
    source=json.loads(OLD.read_text());cases=[];permutations=0;candidates=0
    for r in source:
        if r['activebalance']['max_bucket']==r['optimum']:continue
        records=r['activebalance']['records'];byid={v['heap_node']:v for v in records};m=r['m']
        global_loads=r['activebalance']['loads'];current=tuple(sorted(global_loads,reverse=True));checked=0
        for node in records:
            ancestors=set();p=node['parent']
            while p is not None:ancestors.add(byid[p]['color']);p=byid[p]['parent']
            available=[c for c in range(1,m+1) if c not in ancestors]
            if len(available)<2:continue
            descendants=[]
            def visit(v):
                descendants.append(v)
                for c in v['children']:visit(byid[c])
            visit(node);counts=[sum(v['color']==c for v in descendants) for c in range(1,m+1)]
            mapping=best_count_mapping(available,global_loads,counts)
            hs=tuple(sorted(candidate_loads_after_mapping(mapping,available,global_loads,counts),reverse=True))
            exact=None
            for perm in itertools.permutations(available):
                candidate=global_loads.copy()
                for c in available:candidate[c-1]-=counts[c-1]
                for a,b in zip(available,perm):candidate[b-1]+=counts[a-1]
                sig=tuple(sorted(candidate,reverse=True));permutations+=1
                if exact is None or sig<exact:exact=sig
            assert hs==exact and exact>=current
            checked+=1;candidates+=1
        cases.append({'id':r['id'],'candidate_subtrees':checked,'Hungarian_equals_exact_lex_minimum':True,'no_strict_subtree_permutation_improvement':True})
    report={'source':str(OLD.relative_to(ROOT)),'source_sha256':sha(OLD),'cases':len(cases),
            'candidate_subtrees':candidates,'exhaustive_labeled_permutations':permutations,'results':cases,
            'scope':'Exhaustive audit of every available-color permutation on every eligible rooted subtree in all 200 nonoptimal original-AB base outputs. No claim that such local optimality is global optimality.'}
    dump(OUT/'original_AB_subtree_neighborhood_audit.json',report);return report

def check_actual_proofs(layout,records,colors):
    bynode={r['heap_node']:c for r,c in zip(records,colors)};verified=0
    for slot in layout.slots:
        needed=layout.tree.proof_record_nodes(slot)
        assert len({bynode[node] for node in needed.values()})==len(needed)
        proof=list(layout.defaults[:layout.height])
        recovered={}
        for level,node in needed.items():
            color=bynode[node];assert color not in recovered
            recovered[color]=layout.active_records[node];proof[level]=recovered[color]
        assert proof==layout.tree.proof(slot)
        assert verify_proof(layout.height,slot,layout.values[slot],proof,layout.root)
        verified+=1
    return verified

def dataset(p,name):
    rows=json.loads(p.read_text());out=[];start=time.perf_counter()
    for i,r in enumerate(rows):
        h,slots=slot_embedding(r['shape']);t=time.perf_counter()
        layout=build_layout(h,slots,color_strategy='activebalance',refine_rounds=20)
        original_seconds=time.perf_counter()-t
        assert layout.width==r['m'] and len(layout.active_records)==r['N']
        records=[{'heap_node':v.index,'parent':v.parent.index if v.parent else None,'children':[c.index for c in v.children],
                  'left':v.interval_left,'right':v.interval_right,'proof_level':h-v.depth,'color':v.color} for v in layout.proof_nodes]
        parent,edges=graph(records);initial=[v['color'] for v in records];lb=r['B_joint'];opt=r['exact_optimum']
        # Compute the new candidates only from the coloring and valid LB; exact OPT
        # is used below exclusively for assessment, never for selecting moves.
        tree_profiles.cache_clear();t=time.perf_counter()
        pair,pairmoves,pairreason=improve(initial,edges,r['m'],lb)
        pair_seconds=time.perf_counter()-t
        tree_profiles.cache_clear();t=time.perf_counter()
        three,threemoves,threereason=improve_three(initial,parent,edges,r['m'],lb,k=3)
        three_seconds=time.perf_counter()-t
        t=time.perf_counter()
        final,fourmoves,finalreason=improve_three(three,parent,edges,r['m'],lb,k=4)
        four_seconds=time.perf_counter()-t
        cache_states=tree_profiles.cache_info().currsize
        maxima=[max(loads(c,r['m'])) for c in (initial,pair,three,final)]
        assert lb<=opt<=min(maxima) and valid(final,edges)
        checks={}
        for key,c in [('original_AB',initial),('pair_union',pair),('three_color',three),('three_then_four',final)]:
            checks[key]=check_actual_proofs(layout,records,c)
        row={'dataset':name,'source_index':r.get('source_index',i),'id':('S' if name=='base' else 'H')+f'{i:04d}',
             'shape':r['shape'],'height':h,'slots':slots,'n':r['n'],'N':r['N'],'m':r['m'],
             'B_joint':lb,'OPT':opt,'original_AB':maxima[0],'pair_union':maxima[1],'three_color':maxima[2],'three_then_four':maxima[3],
             'original_AB_passes':layout.passes,'original_AB_moves':layout.moves,'original_AB_budget_exhausted':layout.passes==20 and layout.moves==20,
             'original_AB_build_seconds':original_seconds,'original_AB_coloring_seconds':layout.timings_ms['coloring']/1000,
             'pair_additional_seconds':pair_seconds,'three_additional_seconds':three_seconds,'four_additional_seconds':four_seconds,
             'pair_moves':pairmoves,'three_moves':threemoves,'four_moves':fourmoves,
             'pair_stop':pairreason,'three_stop':threereason,'final_stop':finalreason,
             'DP_cached_subproblems_after_four':cache_states,
             'final_capacity_certificate_attained':maxima[3]==lb,'actual_proofs_verified':checks,
             'records':records,'initial_colors':initial,'pair_colors':pair,'three_colors':three,'final_colors':final}
        out.append(row)
        if (i+1)%500==0:print(f'{name}: {i+1}/{len(rows)}, wall={time.perf_counter()-start:.2f}s',flush=True)
    dump(OUT/f'{name}_construction_results.json',out)
    summary={'shapes':len(out),'source':str(p.relative_to(ROOT)),'source_sha256':sha(p),'total_wall_seconds':time.perf_counter()-start,
             'scope':'base: n2..14,m<=6; holdout: n15..16,m<=6. One canonical orientation per unlabeled shape.',
             'original_AB_budget_exhaustions':sum(r['original_AB_budget_exhausted'] for r in out)}
    for method in ('original_AB','pair_union','three_color','three_then_four'):
        summary[method]={'OPT_attained':sum(r[method]==r['OPT'] for r in out),
          'max_exact_gap':max((r[method]-r['OPT'])/r['OPT'] for r in out),
          'actual_target_proofs_verified':sum(r['actual_proofs_verified'][method] for r in out)}
    summary['original_AB_coloring_seconds']=sum(r['original_AB_coloring_seconds'] for r in out)
    summary['additional_seconds']={method:sum(r[method+'_additional_seconds'] for r in out) for method in ('pair','three','four')}
    summary['remaining_ids']=[r['id'] for r in out if r['three_then_four']>r['OPT']]
    summary['max_DP_cached_subproblems']=max(r['DP_cached_subproblems_after_four'] for r in out)
    with (OUT/f'{name}_construction_results.csv').open('w',newline='',encoding='utf8') as f:
        keys=['id','source_index','n','N','m','B_joint','OPT','original_AB','pair_union','three_color','three_then_four','original_AB_coloring_seconds','pair_additional_seconds','three_additional_seconds','four_additional_seconds','final_stop']
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(out)
    print(json.dumps(summary),flush=True);return summary

def main():
    OUT.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    audit=audit_subtree_neighborhood();print(f"Audited {audit['exhaustive_labeled_permutations']} subtree permutations in {time.perf_counter()-start:.2f}s",flush=True)
    base=dataset(BASE,'base');holdout=dataset(HOLDOUT,'holdout')
    summary={'base':base,'holdout':holdout,'subtree_audit':{k:audit[k] for k in ('cases','candidate_subtrees','exhaustive_labeled_permutations')},
             'python':platform.python_version(),'platform':platform.platform(),'total_wall_seconds':time.perf_counter()-start,
             'neighborhood':'Exact pair-component unions; exact 3-color induced-forest recoloring; then exact 4-color induced-forest recoloring. No more than four colors are optimized at once.',
             'iteration_caps':100,'original_AB_round_cap':20,'state_cache_policy':'Cleared per shape and between pair/3-color stages. 4-color stage retains same-instance 3-color subproblem cache.',
             'hard_scope_and_state_caps':'N<=30, m<=6; maximum 20000 profiles per merge and 10000 cached rooted subproblems. Exceeding a cap raises an explicit failure instead of claiming local optimality. No cap was reached.',
             'lower_bound_scope':'B_joint from frozen theory results used only as a valid stopping certificate; exact OPT never influences move selection.',
             'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'scripts/prototype_construction_kempe_20260910.py',ROOT/'scripts/tifs_revision_smt.py',ROOT/'scripts/run_height_sparsity_profile_balance_experiment.py',BASE,HOLDOUT,OLD)}}
    dump(OUT/'summary.json',summary)

if __name__=='__main__':main()
