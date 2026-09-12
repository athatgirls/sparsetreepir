"""Independent exact profile DP and anchored capacity bound; no legacy solver.

Tree = () for a leaf or a sorted pair of child trees. An SMT proof interval
forest is the two children of its compressed full binary skeleton root.
Canonicalization quotients only global color-label permutations, never merely
equal current loads in a partial coloring. Raw small-tree exhaustive checks
provide an independent second implementation for the DP.
"""
from pathlib import Path
from functools import lru_cache
import argparse, csv, hashlib, itertools, json, math, platform, time

ROOT=Path(__file__).absolute().parents[1]
OUT=ROOT/'examples/tifs_revision_20260910/theory_exploration'
DEADLINE=float('inf')
def checktime():
 if time.monotonic()>DEADLINE:raise TimeoutError('explicit exploration time budget')
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
@lru_cache(None)
def size(t):return 1+sum(size(x) for x in t)
@lru_cache(None)
def leaves(t):return 1 if not t else sum(leaves(x) for x in t)
@lru_cache(None)
def height(t):return 1+max((height(x) for x in t),default=0)
@lru_cache(None)
def shapes(n):
 if n==1:return ((),)
 return tuple(sorted({tuple(sorted((l,r))) for a in range(1,n//2+1) for l in shapes(a) for r in shapes(n-a)}))
def perfect(n):
 assert n>=1 and n&(n-1)==0
 return () if n==1 else (perfect(n//2),perfect(n//2))
def flatten(forest):
 nodes=[]
 def rec(t,parent):
  i=len(nodes);nodes.append({'parent':parent,'children':[],'leaves':leaves(t),'size':size(t),'depth':1 if parent<0 else nodes[parent]['depth']+1})
  for child in t:nodes[i]['children'].append(rec(child,i))
  return i
 roots=[rec(t,-1) for t in forest]
 return nodes,roots
def bounds(nodes,roots,m):
 N=len(nodes);n=sum(nodes[r]['leaves'] for r in roots)
 if not m:return {'N':N,'n':n,'m':0,'B':0,'C':0,'B_star':0}
 B=(N+m-1)//m;C=B;H=B;pathsum=[0]*N;leafpathsum=[0]*N;certificate=None;hcertificate=None
 for i,node in enumerate(nodes):
  d=node['depth'];a=1+n-node['leaves'];s=a+(pathsum[node['parent']] if node['parent']>=0 else 0);pathsum[i]=s
  leafpathsum[i]=node['leaves']+(leafpathsum[node['parent']] if node['parent']>=0 else 0)
  if d<m:
   B=max(B,math.ceil((node['size']-1)/(m-d)))
   c=math.ceil((N-s)/(m-d))
   if c>C:C=c;certificate={'node':i,'depth':d,'sum_anchor_capacities':s,'denominator':m-d,'N_minus_sum':N-s}
   context=node['parent']
   while context>=0:
    v=nodes[context];distance=d-v['depth'];anchor_sum=distance*(1+v['leaves'])-(leafpathsum[i]-leafpathsum[context]);localN=v['size']-1
    hc=math.ceil((localN-anchor_sum)/(m-d))
    if hc>H:H=hc;hcertificate={'context':context,'node':i,'local_N':localN,'local_available_colors':m-v['depth'],'anchored_colors':distance,'anchor_sum':anchor_sum,'denominator':m-d}
    context=v['parent']
  else:assert s>=N
 return {'N':N,'n':n,'m':m,'B':B,'C':C,'B_star':max(B,C),'hierarchical_bound':max(B,C,H),'C_witness':certificate,'hierarchical_witness':hcertificate}
@lru_cache(None)
def permutations(values):
 # Distinct multiset permutations; avoids factorial duplicate generation.
 counts={v:values.count(v) for v in sorted(set(values))};out=[]
 def rec(prefix):
  if len(prefix)==len(values):out.append(tuple(prefix));return
  for v in counts:
   if counts[v]:counts[v]-=1;prefix.append(v);rec(prefix);prefix.pop();counts[v]+=1
 rec([]);return tuple(out)
def merged(p,q,cap):
 for r in permutations(q):
  values=tuple(a+b for a,b in zip(p,r))
  if max(values,default=0)<=cap:yield tuple(sorted(values))
@lru_cache(None)
def profiles(t,k,cap):
 checktime()
 if k<height(t) or size(t)>k*cap:return frozenset()
 if not t:return frozenset({(0,)*(k-1)+(1,)})
 out=set()
 for p in profiles(t[0],k-1,cap):
  for q in profiles(t[1],k-1,cap):
   for s in merged(p,q,cap):out.add(tuple(sorted((1,)+s)))
 return frozenset(out)
def forest_profiles(forest,k,cap):
 checktime();current={(0,)*k}
 for t in forest:
  current={s for p in current for q in profiles(t,k,cap) for s in merged(p,q,cap)}
 return current
def brute_profiles(forest,k,cap):
 """No color symmetry pruning: enumerate every valid labeled node coloring."""
 nodes,roots=flatten(forest);assigned=[-1]*len(nodes);loads=[0]*k;out=set();visits=0
 def rec(i):
  nonlocal visits
  visits+=1
  if i==len(nodes):out.add(tuple(sorted(loads)));return
  forbidden=set();p=nodes[i]['parent']
  while p>=0:forbidden.add(assigned[p]);p=nodes[p]['parent']
  for c in range(k):
   if c not in forbidden and loads[c]<cap:assigned[i]=c;loads[c]+=1;rec(i+1);loads[c]-=1
 rec(0);return out,visits
def witness(t,k,cap,target):
 """Return preorder color labels realizing an already DP-certified profile."""
 if not t:
  assert sorted(target)==[0]*(k-1)+[1];return [target.index(1)]
 # The root color is unique inside a rooted component.
 for rootcolor,count in enumerate(target):
  if count!=1:continue
  available=[c for c in range(k) if c!=rootcolor];remaining=tuple(target[c] for c in available)
  for p in profiles(t[0],k-1,cap):
   for lp in permutations(p):
    rp=tuple(r-l for r,l in zip(remaining,lp))
    if min(rp)<0 or tuple(sorted(rp)) not in profiles(t[1],k-1,cap):continue
    left=witness(t[0],k-1,cap,lp);right=witness(t[1],k-1,cap,rp)
    return [rootcolor]+[available[c] for c in left+right]
 raise AssertionError('witness reconstruction failed')
def forest_witness(forest,k,cap):
 assert len(forest)==2
 for p in profiles(forest[0],k,cap):
  for q in profiles(forest[1],k,cap):
   for qp in permutations(q):
    if max(a+b for a,b in zip(p,qp))<=cap:
     result=witness(forest[0],k,cap,p)+witness(forest[1],k,cap,qp);verify(forest,result,k);return result
 raise AssertionError('no forest witness')
def verify(forest,assigned,k):
 nodes,roots=flatten(forest);assert len(nodes)==len(assigned)
 for i,c in enumerate(assigned):
  assert 0<=c<k;p=nodes[i]['parent']
  while p>=0:assert assigned[p]!=c;p=nodes[p]['parent']
 return [assigned.count(c) for c in range(k)]
def smt_slots(tree,h=None):
 """Embed any full binary skeleton as fixed-height occupied coordinates."""
 h=height(tree)-1 if h is None else h;out=[]
 def rec(t,prefix,d):
  if not t:out.append(prefix<<(h-d));return
  rec(t[0],prefix<<1,d+1);rec(t[1],(prefix<<1)|1,d+1)
 rec(tree,0,0);assert len(out)==len(set(out));return h,sorted(out)
def actual_smt_certificate(tree,cap):
 """Validate the combinatorial example against the paper's actual proof API."""
 from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
 from generate_full_sparse_smt_example import build_full_proof_nodes,build_interval_forest
 from tifs_revision_smt import SparseSMT,verify_proof
 h,slots=smt_slots(tree);smt=SparseSMT.build(h,slots);occupied=[(1<<h)+s for s in slots]
 helper=FixedSparseMerkleColoring(h,occupied);actual=build_full_proof_nodes(helper.raw_nodes,occupied,h);roots=build_interval_forest(actual)
 ordered=[]
 def shape(node):
  ordered.append(node);return tuple(shape(x) for x in node.children)
 actualshape=tuple(shape(root) for root in roots);assert actualshape==tree
 m=height(tree)-1;coloring=forest_witness(tree,m,cap);assert len(ordered)==len(coloring)
 byid={p.index:(p,c) for p,c in zip(ordered,coloring)};records=[];proofs=[]
 for p,c in zip(ordered,coloring):records.append({'heap_index':hex(p.index),'interval':[p.interval_left,p.interval_right],'color':c,'digest_hex':smt.digests[p.index].hex()})
 for slot in slots:
  needed=smt.proof_record_nodes(slot);assert len({byid[node][1] for node in needed.values()})==len(needed)
  proof=list(smt.defaults[:h])
  for level,node in needed.items():proof[level]=smt.digests[node]
  assert proof==smt.proof(slot) and verify_proof(h,slot,smt.values[slot],proof,smt.root)
  proofs.append({'slot':slot,'levels':sorted(needed),'colors':[byid[node][1] for node in needed.values()],'root_verified':True})
 nodes,roots=flatten(tree)
 return {'height':h,'slots':slots,'shape':tree,**bounds(nodes,roots,m),'optimum':cap,'witness_loads':verify(tree,coloring,m),'root_hex':smt.root.hex(),'actual_interval_forest_matches_abstract_shape':True,'every_occupied_target_proof_verified':True,'records':records,'proofs':proofs}
def read_binary_forest(meta):
 import struct
 raw=meta.read_bytes();assert raw[:8]==b'TIFSMETA';h,n,count=struct.unpack_from('>HII',raw,8);offset=18;records=[]
 for _ in range(count):
  c,length=struct.unpack_from('>II',raw,offset);offset+=8
  for pos in range(length):
   left,right,level,flags,index=struct.unpack_from('>QQHHI',raw,offset);offset+=24;records.append((left,right,level))
 assert offset==len(raw);records.sort(key=lambda r:(r[0],-r[1],r[2]));nodes=[];roots=[];stack=[]
 for left,right,level in records:
  while stack and not(nodes[stack[-1]]['left']<=left and right<=nodes[stack[-1]]['right']):stack.pop()
  parent=stack[-1] if stack else -1;i=len(nodes);nodes.append({'left':left,'right':right,'parent':parent,'depth':len(stack)+1,'children':[],'size':1,'leaves':0})
  if parent<0:roots.append(i)
  else:nodes[parent]['children'].append(i)
  stack.append(i)
 for i in reversed(range(len(nodes))):
  ch=nodes[i]['children'];assert len(ch) in (0,2)
  nodes[i]['size']=1+sum(nodes[j]['size'] for j in ch);nodes[i]['leaves']=sum(nodes[j]['leaves'] for j in ch) if ch else 1
 assert len(roots)==2 and sum(nodes[r]['leaves'] for r in roots)==n
 return bounds(nodes,roots,max(x['depth'] for x in nodes))
def main():
 global DEADLINE
 ap=argparse.ArgumentParser();ap.add_argument('--max-leaves',type=int,default=12);ap.add_argument('--max-width',type=int,default=6);ap.add_argument('--seconds',type=float,default=90);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True);DEADLINE=time.monotonic()+a.seconds;start=time.monotonic()
 checks=[];rows=[];brute_visits=0;timedout=False
 for n in range(2,6):
  for tree in shapes(n):
   k=height(tree)-1;dp=forest_profiles(tree,k,2*n-2);brute,visited=brute_profiles(tree,k,2*n-2);brute_visits+=visited;assert dp==brute;checks.append({'leaves':n,'shape':tree,'width':k,'profiles':len(dp),'brute_visits':visited})
 try:
  for n in range(2,a.max_leaves+1):
   for tree in shapes(n):
    checktime();k=height(tree)-1
    if k>a.max_width:continue
    nodes,roots=flatten(tree);bound=bounds(nodes,roots,k);opt=None
    for cap in range(bound['B'],n+1):
     if forest_profiles(tree,k,cap):opt=cap;break
    assert opt is not None and bound['hierarchical_bound']<=opt
    rows.append({'leaves':n,'shape':tree,**bound,'optimum':opt,'strict_B_gap':opt>bound['B'],'strict_Bstar_gap':opt>bound['B_star'],'strict_hierarchical_gap':opt>bound['hierarchical_bound']})
   print('ENUM',n,'total',len(rows),'B gaps',sum(r['strict_B_gap'] for r in rows),'B* gaps',sum(r['strict_Bstar_gap'] for r in rows),flush=True)
 except TimeoutError:timedout=True
 # Give the explicit twenty-leaf counterexample an independent bounded budget.
 DEADLINE=time.monotonic()+30;tree=(perfect(16),perfect(4));nodes,roots=flatten(tree);bound=bounds(nodes,roots,5)
 assert bound['B']==8 and bound['B_star']==9 and not forest_profiles(tree,5,8)
 coloring=forest_witness(tree,5,9);loads=verify(tree,coloring,5);assert max(loads)==9
 h,slots=smt_slots(tree);example={'shape':tree,'height':h,'slots':slots,**bound,'optimum':9,'preorder_coloring_zero_based':coloring,'loads':loads,'nodes':nodes,'exact_dp_capacity8_infeasible':True,'capacity9_witness_valid':True}
 dump(a.output/'explicit_20_leaf_counterexample.json',example)
 for label,case,cap in [('twenty_leaf',tree,9),('nine_leaf',next(r['shape'] for r in rows if r['strict_B_gap']),5),('ten_leaf',next(r['shape'] for r in rows if r['strict_Bstar_gap']),5),('eleven_leaf',next(r['shape'] for r in rows if r['strict_hierarchical_gap']),5)]:
  dump(a.output/f'{label}_actual_smt_certificate.json',actual_smt_certificate(case,cap))
 real=[];vb=ROOT/'examples/tifs_revision_20260910/verified_backend'
 for path in sorted(vb.glob('*_h128/activebalance/layout_metadata.bin')):real.append({'input':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**read_binary_forest(path)})
 ct=ROOT/'examples/tifs_revision_20260910/ct_application/runs_verified_evidence/publisher/activebalance/layout_metadata.bin'
 if ct.exists():real.append({'input':str(ct.relative_to(ROOT)),'sha256':hashlib.sha256(ct.read_bytes()).hexdigest(),**read_binary_forest(ct)})
 dump(a.output/'real_workload_bounds.json',real);dump(a.output/'small_shape_exact_results.json',rows);dump(a.output/'independent_brute_validation.json',{'cases':checks,'total_brute_visits':brute_visits,'all_equal':True,'symmetry_pruning':'none in brute force; DP quotients only complete global color permutations'})
 summary={'enumerated_shapes':len(rows),'max_requested_leaves':a.max_leaves,'width_cap':a.max_width,'explicit_time_budget_seconds':a.seconds,'enumeration_censored':timedout,'B_gaps':sum(r['strict_B_gap'] for r in rows),'Bstar_gaps':sum(r['strict_Bstar_gap'] for r in rows),'hierarchical_gaps':sum(r['strict_hierarchical_gap'] for r in rows),'first_B_gap':next((r for r in rows if r['strict_B_gap']),None),'first_Bstar_gap':next((r for r in rows if r['strict_Bstar_gap']),None),'first_hierarchical_gap':next((r for r in rows if r['strict_hierarchical_gap']),None),'brute_validation_cases':len(checks),'seconds':time.monotonic()-start,'python':platform.python_version(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'dp_cache':str(profiles.cache_info())}
 dump(a.output/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
