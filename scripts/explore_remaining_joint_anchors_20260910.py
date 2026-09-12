"""Joint anchored-color packing bounds; separate bounded exploration.

No historical script or manuscript is modified. Existing exact-profile results
are treated as inputs, with source pins. The new bound uses only tree structure;
it never reads the optimum when computing a certificate.
"""
from pathlib import Path
from functools import lru_cache
import argparse, hashlib, json, math, platform, time
import explore_tifs_anchored_capacity_20260910 as exact

ROOT=Path(__file__).absolute().parents[1]
SOURCE=ROOT/'examples/tifs_revision_20260910/theory_exploration/final/small_shape_exact_results.json'
OUT=ROOT/'examples/tifs_remaining_gap_20260910/theory'
def canonical(x):return tuple(canonical(y) for y in x)
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
@lru_cache(None)
def beta(tree,k):
 """Maximum cardinality covered by k antichains in a rooted-tree poset."""
 if k==0:return 0
 return max(sum(beta(child,k) for child in tree),1+sum(beta(child,k-1) for child in tree))
def index_forest(forest):
 nodes=[]
 def rec(t,parent):
  i=len(nodes);nodes.append({'shape':t,'parent':parent,'children':[],'depth':1 if parent<0 else nodes[parent]['depth']+1,'size':exact.size(t),'leaves':exact.leaves(t)})
  for child in t:nodes[i]['children'].append(rec(child,i))
  return i
 roots=[rec(t,-1) for t in forest];return nodes,roots
def path_for(nodes,context,end):
 chain=[];v=end
 while v!=context:
  assert v>=0;chain.append(v);v=nodes[v]['parent']
 return list(reversed(chain))
def joint_capacity(nodes,roots,context,end):
 chain=path_for(nodes,context,end);k=len(chain);context_roots=roots if context<0 else nodes[context]['children'];regions=[]
 first=[r for r in context_roots if r!=chain[0]]
 regions.append({'available_anchor_colors':k,'root_ids':first,'capacity':sum(beta(nodes[r]['shape'],k) for r in first)})
 for i,v in enumerate(chain[:-1],1):
  side=[r for r in nodes[v]['children'] if r!=chain[i]];available=k-i
  regions.append({'available_anchor_colors':available,'root_ids':side,'capacity':sum(beta(nodes[r]['shape'],available) for r in side)})
 return k+sum(r['capacity'] for r in regions),chain,regions
def joint_bound(forest):
 nodes,roots=index_forest(forest);m=max((n['depth'] for n in nodes),default=0);old=exact.bounds(nodes,roots,m);best=old['hierarchical_bound'];witness=None;checks=0
 for end in range(len(nodes)):
  context=-1;contexts=[-1];p=nodes[end]['parent']
  while p>=0:contexts.append(p);p=nodes[p]['parent']
  for context in contexts:
   d0=0 if context<0 else nodes[context]['depth'];q=m-d0;k=nodes[end]['depth']-d0
   if k>=q:continue
   N=len(nodes) if context<0 else nodes[context]['size']-1
   n=sum(nodes[r]['leaves'] for r in roots) if context<0 else nodes[context]['leaves']
   J,chain,regions=joint_capacity(nodes,roots,context,end);checks+=1
   single_sum=sum(1+n-nodes[v]['leaves'] for v in chain);assert J<=single_sum
   candidate=math.ceil((N-J)/(q-k))
   if candidate>best:
    best=candidate;witness={'context':context,'terminal':end,'anchor_ids':chain,'k':k,'available_colors_q':q,'context_records':N,'joint_anchored_capacity_J':J,'sum_individual_capacities':single_sum,'unanchored_colors':q-k,'old_capacity':old['hierarchical_bound'],'deficit_at_old_bound':N-J-(q-k)*old['hierarchical_bound'],'necessary_capacity':candidate,'regions':regions}
 return {'N':len(nodes),'n':sum(nodes[r]['leaves'] for r in roots),'m':m,'B':old['B'],'B_anc':old['B_star'],'B_hier':old['hierarchical_bound'],'B_joint':best,'witness':witness,'chain_context_constraints_checked':checks}
def brute_beta(tree,k):
 nodes,roots=index_forest((tree,));best=0
 for mask in range(1<<len(nodes)):
  count=mask.bit_count()
  if count<=best:continue
  longest=[0]*len(nodes);valid=True
  for i,node in enumerate(nodes):
   longest[i]=(longest[node['parent']] if node['parent']>=0 else 0)+((mask>>i)&1)
   if longest[i]>k:valid=False;break
  if valid:best=count
 return best
def brute_joint(nodes,roots,context,end):
 """No DP/beta formula: assign anchored labels, other vertices a label or skip."""
 J,chain,regions=joint_capacity(nodes,roots,context,end);anchors={v:i for i,v in enumerate(chain)};k=len(chain)
 start=0 if context<0 else context+1;stop=len(nodes) if context<0 else context+nodes[context]['size'];ids=list(range(start,stop));colors={};best=0;visits=0
 def ancestors(v):
  out=set();p=nodes[v]['parent']
  while p>=0:out.add(p);p=nodes[p]['parent']
  return out
 ancestor={v:ancestors(v) for v in ids}
 options={v:[c for a,c in anchors.items() if a not in ancestor[v] and v not in ancestor[a]] for v in ids if v not in anchors}
 def rec(pos,count):
  nonlocal best,visits
  visits+=1
  if count+len(ids)-pos<=best:return
  if pos==len(ids):best=max(best,count);return
  v=ids[pos];forbidden={colors[a] for a in ancestor[v] if a in colors and colors[a]>=0}
  if v in anchors:
   c=anchors[v]
   if c in forbidden:return
   colors[v]=c;rec(pos+1,count+1);del colors[v];return
  for c in options[v]:
   if c not in forbidden:colors[v]=c;rec(pos+1,count+1)
  colors[v]=-1;rec(pos+1,count);del colors[v]
 rec(0,0);return best,visits
def notation(t):return 'L' if not t else '('+','.join(notation(x) for x in t)+')'
def is_subtree(tree,pattern):return tree==pattern or any(is_subtree(x,pattern) for x in tree)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--expanded-max-leaves',type=int,default=16);ap.add_argument('--expanded-max-width',type=int,default=6);ap.add_argument('--expanded-seconds',type=float,default=60);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 if (a.output/'summary.json').exists():raise RuntimeError('choose fresh output directory')
 inputrows=json.loads(SOURCE.read_text());start=time.monotonic();rows=[]
 for index,row in enumerate(inputrows):
  tree=canonical(row['shape']);bound=joint_bound(tree);assert bound['B_hier']==row['hierarchical_bound'];assert bound['B_joint']<=row['optimum']
  rows.append({'source_index':index,'shape':tree,'notation':notation(tree),**bound,'exact_optimum':row['optimum'],'old_hierarchical_gap':bound['B_hier']<row['optimum'],'joint_gap':bound['B_joint']<row['optimum']})
 remaining=[r for r in rows if r['old_hierarchical_gap']];assert len(rows)==1323 and len(remaining)==13
 dump(a.output/'all_1323_joint_bounds.json',rows);dump(a.output/'original_13_obstructions.json',remaining)
 print('BASE',len(rows),'old gaps',len(remaining),'joint gaps',sum(r['joint_gap'] for r in rows),flush=True)
 # Independently verify both the beta recurrence and the claimed exact joint
 # maximum on every context/contiguous anchored prefix in tiny trees.
 betachecks=[];jointchecks=[]
 for n in range(2,6):
  for tree in exact.shapes(n):
   nodes,roots=index_forest(tree);m=exact.height(tree)-1
   for t in tree:
    for k in range(m+1):observed=brute_beta(t,k);assert observed==beta(t,k);betachecks.append({'tree':t,'k':k,'value':observed})
   for end in range(len(nodes)):
    contexts=[-1];p=nodes[end]['parent']
    while p>=0:contexts.append(p);p=nodes[p]['parent']
    for context in contexts:
     J,chain,_=joint_capacity(nodes,roots,context,end);observed,visits=brute_joint(nodes,roots,context,end);assert observed==J
     jointchecks.append({'tree':tree,'context':context,'terminal':end,'k':len(chain),'formula_J':J,'independent_brute_J':observed,'search_visits':visits})
 dump(a.output/'brute_beta_validation.json',betachecks);dump(a.output/'brute_joint_validation.json',jointchecks)
 # Only new n>=15 shapes; fixed finite limits plus an explicit clock budget.
 expanded=[];censored=False;deadline=time.monotonic()+a.expanded_seconds;exact.DEADLINE=deadline
 try:
  for n in range(15,a.expanded_max_leaves+1):
   for tree in exact.shapes(n):
    if time.monotonic()>deadline:raise TimeoutError('expanded exact limit')
    k=exact.height(tree)-1
    if k>a.expanded_max_width:continue
    bound=joint_bound(tree);opt=None
    # Start from the old proved bound, so even the new bound is independently
    # checked rather than assumed when obtaining an optimum.
    for U in range(bound['B'],n+1):
     if exact.forest_profiles(tree,k,U):opt=U;break
    assert opt is not None and bound['B_joint']<=opt
    expanded.append({'shape':tree,'notation':notation(tree),**bound,'exact_optimum':opt,'joint_gap':bound['B_joint']<opt})
   print('EXPANDED',n,'shapes',len(expanded),'joint gaps',sum(r['joint_gap'] for r in expanded),flush=True)
 except TimeoutError:censored=True
 dump(a.output/'expanded_exact_results.json',expanded)
 firstgap=next((r for r in rows+expanded if r['joint_gap']),None)
 if firstgap:
  tree=canonical(firstgap['shape']);exact.DEADLINE=time.monotonic()+20;certificate=exact.actual_smt_certificate(tree,firstgap['exact_optimum']);dump(a.output/'first_joint_gap_actual_smt_certificate.json',certificate)
 summary={'base_shapes':len(rows),'original_hierarchical_gaps':len(remaining),'base_joint_gaps':sum(r['joint_gap'] for r in rows),'recovered_original_13':sum(not r['joint_gap'] for r in remaining),'base_scope':'all unordered unlabeled rooted full binary skeletons with 2..14 leaves and root-excluded height<=6 in preserved source','beta_independent_checks':len(betachecks),'joint_exact_max_independent_checks':len(jointchecks),'expanded_shapes':len(expanded),'expanded_joint_gaps':sum(r['joint_gap'] for r in expanded),'expanded_scope':{'leaves_from':15,'leaves_to':a.expanded_max_leaves,'width_cap':a.expanded_max_width,'time_limit_seconds':a.expanded_seconds,'censored':censored},'first_joint_gap':firstgap,'source_file':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),'script_sha256':sha(Path(__file__)),'imported_exact_script_sha256':sha(ROOT/'scripts/explore_tifs_anchored_capacity_20260910.py'),'python':platform.python_version(),'total_wall_seconds':time.monotonic()-start}
 dump(a.output/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
