"""Independent height-count bound plus bounded MILP search; no theory imports."""
from pathlib import Path
import hashlib, json, math, random, time, platform
import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
START = time.monotonic()

def canonical(t): return tuple(canonical(x) for x in t)

def flatten(tree):
    records = []
    def add(t, parent):
        i = len(records)
        records.append({'parent': parent, 'depth': 1 if parent < 0 else records[parent]['depth'] + 1})
        children = [add(x, i) for x in t]
        records[i].update(children=children, end=len(records),
                          height=1+max((records[j]['height'] for j in children), default=0),
                          leaves=sum(records[j]['leaves'] for j in children) if children else 1)
        return i
    roots = [add(t, -1) for t in tree]
    return records, roots

def contains(records, a, b): return a <= b < records[a]['end']

def height_union_count(records, ids, anchors):
    # A non-anchor is in an off-path region; its allowed anchored labels are
    # exactly those incomparable with it. Bottom-up heights independently
    # characterize the maximum union of that many antichains in its region.
    selected = len(anchors)
    for v in ids:
        if v in anchors: continue
        k = sum(not contains(records, a, v) and not contains(records, v, a) for a in anchors)
        selected += records[v]['height'] <= k
    return selected

def bound(tree):
    records, roots = flatten(tree)
    N = len(records)
    m = max(r['depth'] for r in records)
    result = (N+m-1)//m
    zero_checks = 0
    for context in [-1] + list(range(N)):
        ids = list(range(N)) if context < 0 else list(range(context+1, records[context]['end']))
        q = m if context < 0 else m-records[context]['depth']
        if not ids: continue
        assert q > 0
        result = max(result, (len(ids)+q-1)//q)
        for end in ids:
            anchors = []
            p = end
            while p != context:
                assert p >= 0
                anchors.append(p)
                p = records[p]['parent']
            J = height_union_count(records, ids, anchors)
            k = len(anchors)
            if q == k:
                assert J == len(ids)
                zero_checks += 1
            else:
                assert q > k
                result = max(result, (len(ids)-J+q-k-1)//(q-k))
    return result, records, roots, zero_checks

def feasible(records, roots, cap, seconds):
    N=len(records);m=max(r['depth'] for r in records)
    ii=[];jj=[];vv=[];low=[];high=[]
    def row(cols, lo, hi):
        number=len(low)
        for col in cols: ii.append(number);jj.append(col);vv.append(1.)
        low.append(lo);high.append(hi)
    for v in range(N): row([v*m+c for c in range(m)],1,1)
    # Full root-to-leaf clique constraints, independently constructed.
    paths=[]
    for v,r in enumerate(records):
        if r['children']: continue
        path=[];p=v
        while p>=0: path.append(p);p=records[p]['parent']
        paths.append(path)
        for c in range(m): row([w*m+c for w in path],0,1)
    for c in range(m): row([v*m+c for v in range(N)],0,cap)
    lb=np.zeros(N*m);ub=np.ones(N*m)
    chain=max(paths,key=len)
    for c,v in enumerate(chain): lb[v*m+c]=1;ub[v*m:v*m+m]=0;ub[v*m+c]=1
    matrix=coo_matrix((vv,(ii,jj)),shape=(len(low),N*m)).tocsc()
    started=time.monotonic()
    r=milp(np.zeros(N*m),integrality=np.ones(N*m),bounds=Bounds(lb,ub),
           constraints=LinearConstraint(matrix,np.array(low),np.array(high)),
           options={'time_limit':seconds,'presolve':True})
    item={'status':int(r.status),'message':r.message,'seconds':time.monotonic()-started}
    if r.x is not None:
        x=np.rint(r.x).reshape(N,m).astype(int)
        assert np.max(np.abs(r.x-x.reshape(-1)))<1e-5
        colors=[int(np.argmax(row)) for row in x]
        assert all(sum(row)==1 for row in x)
        assert max(colors.count(c) for c in range(m))<=cap
        for p in paths: assert len(set(colors[v] for v in p))==len(p)
        item.update(integer_witness_verified=True,colors=colors,loads=[colors.count(c) for c in range(m)])
    return item

def random_tree(n,rng,mode=0):
    if n==1:return ()
    if mode==1 and n>4: split=rng.choice([1,2,max(1,n//2),n-1])
    elif mode==2: split=max(1,min(n-1,n//2+rng.randint(-2,2)))
    else:split=rng.randrange(1,n)
    return tuple(sorted((random_tree(split,rng,mode),random_tree(n-split,rng,mode))))

def main():
    source=ROOT/'examples/tifs_remaining_gap_20260910/theory'
    checked=[];zero=0
    for name in ['all_1323_joint_bounds.json','expanded_exact_results.json']:
        path=source/name;rows=json.loads(path.read_text())
        for r in rows:
            value,_,_,z=bound(canonical(r['shape']));zero+=z
            assert value==r['B_joint'],(name,r,value)
        checked.append({'file':str(path.relative_to(ROOT)),'rows':len(rows),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    rng=random.Random(2026091073);seen=set();tests=[];attempts=0
    # Overall search budget excludes the completed deterministic source check.
    search_start=time.monotonic();deadline=min(START+88,search_start+70)
    while len(tests)<300 and time.monotonic()<deadline-0.1:
        attempts+=1;n=rng.randint(17,48);tree=random_tree(n,rng,attempts%3)
        if tree in seen:continue
        seen.add(tree)
        value,records,roots,z=bound(tree)
        m=max(r['depth'] for r in records)
        if m>11:continue
        remaining=deadline-time.monotonic()
        if remaining<=0.1:break
        result=feasible(records,roots,value,min(1.5,remaining))
        case={'n':n,'N':len(records),'m':m,'shape':tree,'independent_B_joint':value,**result}
        tests.append(case)
        if result['status']==2:
            print('COUNTEREXAMPLE',n,m,value,flush=True)
            break
    report={'scope':'Independent node-height capacity calculation, then finite pseudorandom MILP feasibility search; no imported theory code.',
            'source_checks':checked,'zero_denominator_equalities_checked':zero,
            'all_saved_joint_bounds_reproduced':True,'random_seed':2026091073,
            'random_generation_attempts':attempts,'tests':tests,'tested':len(tests),
            'verified_feasible':sum(t.get('integer_witness_verified',False) for t in tests),
            'certified_infeasible':sum(t['status']==2 for t in tests),
            'unknown_or_limited_without_witness':sum(t['status'] not in [0,2] and not t.get('integer_witness_verified',False) for t in tests),
            'search_budget_seconds':70,'per_milp_limit_seconds':1.5,
            'search_time_seconds':time.monotonic()-search_start,'total_seconds':time.monotonic()-START,
            'time_censored':time.monotonic()>=deadline-0.1,'first_counterexample':next((t for t in tests if t['status']==2),None),
            'scipy':scipy.__version__,'python':platform.python_version(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'joint_independent_validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['tests','first_counterexample']},indent=2),flush=True)

if __name__=='__main__':main()
