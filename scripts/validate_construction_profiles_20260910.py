"""Independent projection-closure and brute labeled-color checks for the new DP."""
from pathlib import Path
import hashlib,itertools,json,time
from prototype_construction_kempe_20260910 import graph,induced_forest,tree_profiles

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_sufficiency_20260910/construction'

def dp_profiles(forest,k):
    current={(0,0,0,0)}
    for shape,ids in forest:
        current={tuple(a+b for a,b in zip(p,q)) for p in current for q in tree_profiles(shape,(1<<k)-1)}
    return current

def brute_profiles(indices,edges,k):
    # Deliberately no profile/symmetry pruning. Counts every valid labeled state.
    chosen={};result=set();visits=0;neighbors={i:set() for i in indices}
    for a,b in edges:
        if a in neighbors and b in neighbors:neighbors[a].add(b);neighbors[b].add(a)
    def rec(offset):
        nonlocal visits
        visits+=1
        if offset==len(indices):result.add(tuple(sum(c==j for c in chosen.values()) for j in range(4)));return
        v=indices[offset];forbidden={chosen[u] for u in neighbors[v] if u in chosen}
        for c in range(k):
            if c not in forbidden:chosen[v]=c;rec(offset+1);del chosen[v]
    rec(0);return result,visits

def projection_edges(forest):
    edges=set();arities=[]
    for shape,ids in forest:
        cursor=0
        def rec(t,ancestors):
            nonlocal cursor
            v=ids[cursor];cursor+=1;arities.append(len(t))
            for a in ancestors:edges.add(tuple(sorted((v,a))))
            for c in t:rec(c,ancestors+[v])
        rec(shape,[]);assert cursor==len(ids)
    return edges,arities

def main():
    source=ROOT/'examples/tifs_remaining_gap_20260910/algorithm/small_shape_algorithm_results.json'
    rows=json.loads(source.read_text());brute=[];projection_checks=0;maxarity=0;maxroots=0;unary=0;visits=0;start=time.perf_counter()
    chosenrows=[r for r in rows if r['n']<=5]+rows[::17]
    for r in chosenrows:
        records=r['activebalance']['records'];parent,edges=graph(records);colors=[v['color'] for v in records]
        for k in range(1,min(4,r['m'])+1):
            for palette in itertools.combinations(range(1,r['m']+1),k):
                forest=induced_forest(parent,colors,palette);projected,arities=projection_edges(forest)
                expected={tuple(sorted((a,b))) for a,b in edges if colors[a] in palette and colors[b] in palette}
                assert projected==expected
                projection_checks+=1;maxarity=max(maxarity,max(arities,default=0));maxroots=max(maxroots,len(forest));unary+=arities.count(1)
                if r['n']<=5:
                    order=[v for _,ids in forest for v in ids];actual,nv=brute_profiles(order,edges,k);visits+=nv
                    dp=dp_profiles(forest,k);assert actual==dp
                    brute.append({'id':r['id'],'palette':palette,'vertices':len(order),'profile_count':len(dp),'labeled_visits':nv})
    old={r['id']:r for r in rows};measured=json.loads((OUT/'base_construction_results.json').read_text())
    for r in measured:
        prior=old[r['id']];assert r['original_AB']==prior['activebalance']['max_bucket']
        assert {v['heap_node']:c for v,c in zip(r['records'],r['initial_colors'])}=={v['heap_node']:v['color'] for v in prior['activebalance']['records']}
    result={'projection_checks':projection_checks,'max_induced_children':maxarity,'max_induced_roots':maxroots,'unary_nodes_observed':unary,
            'brute_profile_cases':len(brute),'brute_labeled_recursion_visits':visits,'all_DP_profile_sets_equal_brute':True,
            'original_AB_exact_coloring_matches':len(measured),'brute_results':brute,'seconds':time.perf_counter()-start,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'independent_DP_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='brute_results'}))

if __name__=='__main__':main()
