"""Exact unions of two-color Kempe components, a separate construction variant.

Starts from the original Hungarian AB output. It optimizes a stronger legal
neighborhood via subset-sum, not an early-stop rule or replacement AB result.
No PIR timings or historical measurements are overwritten.
"""
from __future__ import annotations
import collections, itertools, json, time
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/tifs_sufficiency_20260910/construction'
MAX_PROFILE_STATES=20000
MAX_CACHED_SUBPROBLEMS=10000

def graph(records):
    ids=[r['heap_node'] for r in records];idx={x:i for i,x in enumerate(ids)}
    parent=[idx.get(r['parent'],-1) for r in records];edges=[]
    for i,p in enumerate(parent):
        while p>=0:edges.append((i,p));p=parent[p]
    return parent,edges

def valid(colors,edges):return all(colors[a]!=colors[b] for a,b in edges)
def loads(colors,m):return [colors.count(c) for c in range(1,m+1)]
def signature(colors,m):return tuple(sorted(loads(colors,m),reverse=True))

def components(colors,edges,a,b):
    indices=[i for i,c in enumerate(colors) if c in (a,b)];parent={i:i for i in indices}
    def root(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    for x,y in edges:
        if x in parent and y in parent:
            xx,yy=root(x),root(y)
            if xx!=yy:parent[yy]=xx
    grouped={}
    for i in indices:grouped.setdefault(root(i),[]).append(i)
    return list(grouped.values())

def best_exchange(colors,edges,m):
    current_loads=loads(colors,m);current=tuple(sorted(current_loads,reverse=True));best=None
    for a in range(1,m):
        for b in range(a+1,m+1):
            comp=components(colors,edges,a,b)
            deltas=[sum(1 if colors[v]==a else -1 for v in vertices) for vertices in comp]
            reachable={0:0}
            for k,d in enumerate(deltas):
                for total,mask in list(reachable.items()):reachable.setdefault(total+d,mask|(1<<k))
            for transfer,mask in reachable.items():
                candidate=current_loads.copy();candidate[a-1]-=transfer;candidate[b-1]+=transfer
                sig=tuple(sorted(candidate,reverse=True))
                if sig<current and (best is None or sig<best[0]):
                    best=(sig,a,b,[v for k,vs in enumerate(comp) if mask&(1<<k) for v in vs],transfer,len(comp))
    return best

def improve(colors,edges,m,lower_bound=None,limit=100):
    colors=list(colors);assert valid(colors,edges);moves=[];reason='move_budget'
    for _ in range(limit):
        if lower_bound is not None and max(loads(colors,m))==lower_bound:reason='capacity_certificate';break
        move=best_exchange(colors,edges,m)
        if move is None:reason='no_strict_pair_component_union_improvement';break
        sig,a,b,vertices,transfer,component_count=move
        before=signature(colors,m)
        for v in vertices:colors[v]=b if colors[v]==a else a
        assert valid(colors,edges) and signature(colors,m)==sig<before
        moves.append({'colors':[a,b],'vertices':vertices,'transfer_from_first':transfer,
                      'pair_components':component_count,'signature_before':before,'signature_after':sig})
    return colors,moves,reason

@lru_cache(None)
def tree_profiles(shape,mask):
    if tree_profiles.cache_info().currsize>=MAX_CACHED_SUBPROBLEMS:raise RuntimeError('explicit DP cache-state cap')
    out={}
    for c in range(4):
        if not mask&(1<<c):continue
        base=[0,0,0,0];base[c]=1;current={tuple(base):(c,)}
        for child in shape:
            options=tree_profiles(child,mask^(1<<c));nexts={}
            for p,w in current.items():
                for q,v in options.items():
                    z=tuple(a+b for a,b in zip(p,q));nexts.setdefault(z,w+v)
            current=nexts
            if len(current)>MAX_PROFILE_STATES:raise RuntimeError('explicit DP profile-state cap')
            if not current:break
        for p,w in current.items():out.setdefault(p,w)
    return out

def induced_forest(parent,colors,palette):
    selected={i for i,c in enumerate(colors) if c in palette};children={i:[] for i in selected};roots=[]
    for i in sorted(selected):
        p=parent[i]
        while p>=0 and p not in selected:p=parent[p]
        if p<0:roots.append(i)
        else:children[p].append(i)
    def rec(i):
        flat=[i];shape=[]
        for c in children[i]:s,v=rec(c);shape.append(s);flat+=v
        return tuple(shape),flat
    return [rec(i) for i in roots]

def best_three_color(colors,parent,edges,m,k=3):
    if not (len(colors)<=30 and m<=6 and k in (3,4)):
        raise ValueError('Bounded prototype supports N<=30, m<=6, and k=3 or 4 only')
    before=signature(colors,m);baseline=loads(colors,m);best=None
    for palette in itertools.combinations(range(1,m+1),min(k,m)):
        current={(0,0,0,0):()};order=[]
        for shape,ids in induced_forest(parent,colors,palette):
            options=tree_profiles(shape,(1<<len(palette))-1);nexts={}
            for p,w in current.items():
                for q,v in options.items():
                    z=tuple(a+b for a,b in zip(p,q));nexts.setdefault(z,w+v)
            current=nexts;order+=ids
            if len(current)>MAX_PROFILE_STATES:raise RuntimeError('explicit DP profile-state cap')
        for profile,assignment in current.items():
            totals=baseline.copy()
            for c,v in zip(palette,profile):totals[c-1]=v
            sig=tuple(sorted(totals,reverse=True))
            if sig<before and (best is None or sig<best[0]):
                best=(sig,palette,order,assignment,profile)
    return best

def improve_three(colors,parent,edges,m,lower_bound=None,limit=100,k=3):
    colors=list(colors);assert valid(colors,edges);moves=[];reason='move_budget'
    for _ in range(limit):
        if lower_bound is not None and max(loads(colors,m))==lower_bound:reason='capacity_certificate';break
        candidate=best_three_color(colors,parent,edges,m,k=k)
        if candidate is None:reason=f'no_strict_{k}_color_improvement';break
        sig,palette,order,assignment,profile=candidate;before=signature(colors,m)
        for i,c in zip(order,assignment):colors[i]=palette[c]
        assert valid(colors,edges) and signature(colors,m)==sig<before
        moves.append({'palette':palette,'signature_before':before,'signature_after':sig,'selected_profile':profile})
    return colors,moves,reason

def main():
    p=ROOT/'examples/tifs_remaining_gap_20260910/algorithm/small_shape_algorithm_results.json'
    rows=json.loads(p.read_text());start=time.perf_counter();result=[]
    joint=json.loads((ROOT/'examples/tifs_remaining_gap_20260910/theory/all_1323_joint_bounds.json').read_text())
    for r,j in zip(rows,joint):
        assert j['source_index']==r['source_index'] and j['shape']==r['shape']
        rec=r['activebalance']['records'];parent,edges=graph(rec)
        c,moves,reason=improve_three([v['color'] for v in rec],parent,edges,r['m'],j['B_joint'])
        if max(loads(c,r['m']))>j['B_joint']:
            c,more,reason=improve_three(c,parent,edges,r['m'],j['B_joint'],k=4);moves+=more
        result.append({'id':r['id'],'n':r['n'],'m':r['m'],'OPT':r['optimum'],
                       'AB':r['activebalance']['max_bucket'],'variant':max(loads(c,r['m'])),
                       'moves':len(moves),'reason':reason})
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'pilot_base_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'seconds':time.perf_counter()-start,'shapes':len(result),
                      'attained':sum(r['variant']==r['OPT'] for r in result),
                      'improved':sum(r['variant']<r['AB'] for r in result),
                      'remaining':dict(collections.Counter(f"{r['OPT']}->{r['variant']}" for r in result if r['variant']>r['OPT']))},default=str))

if __name__=='__main__':main()
