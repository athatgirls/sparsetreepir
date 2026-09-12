"""Save structural witnesses and actual SMT checks for the original 13 gaps."""
from pathlib import Path
import json, hashlib, statistics
import explore_remaining_joint_anchors_20260910 as joint
import explore_tifs_anchored_capacity_20260910 as exact

ROOT=Path(__file__).absolute().parents[1]
OUT=ROOT/'examples/tifs_remaining_gap_20260910/theory'
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def main():
 rows=json.loads((OUT/'original_13_obstructions.json').read_text());classified=[];proof_count=0
 certificates=OUT/'actual_smt_certificates';certificates.mkdir(exist_ok=True)
 for row in rows:
  tree=joint.canonical(row['shape']);nodes,roots=joint.index_forest(tree);old=row['B_hier'];m=row['m'];violations=[]
  for end,node in enumerate(nodes):
   contexts=[-1];p=node['parent']
   while p>=0:contexts.append(p);p=nodes[p]['parent']
   for context in contexts:
    d0=0 if context<0 else nodes[context]['depth'];q=m-d0;k=node['depth']-d0
    if k>=q:continue
    N=len(nodes) if context<0 else nodes[context]['size']-1
    J,chain,regions=joint.joint_capacity(nodes,roots,context,end);deficit=N-J-(q-k)*old
    if deficit>0:
     violations.append({'context':context,'N_context':N,'q':q,'k':k,'J':J,'chain':chain,'unanchored_colors':q-k,'deficit_at_H':deficit,'side_regions':[{'colors':r['available_anchor_colors'],'beta':r['capacity'],'shapes':[nodes[v]['shape'] for v in r['root_ids']],'notations':[joint.notation(nodes[v]['shape']) for v in r['root_ids']]} for r in regions]})
  assert violations
  minimum=min(violations,key=lambda w:(w['k'],w['N_context'],w['J'],w['chain']))
  cert=exact.actual_smt_certificate(tree,row['exact_optimum']);assert cert['every_occupied_target_proof_verified'];proof_count+=len(cert['proofs'])
  filename=f"source_{row['source_index']:04d}.json";dump(certificates/filename,cert)
  classified.append({'source_index':row['source_index'],'n':row['n'],'N':row['N'],'m':m,'shape':tree,'notation':row['notation'],'B_hier':old,'B_joint':row['B_joint'],'optimum':row['exact_optimum'],'minimum_anchor_witness':minimum,'violating_constraints':len(violations),'actual_smt_certificate':str((certificates/filename).relative_to(ROOT)),'target_proofs_checked':len(cert['proofs'])})
 dump(OUT/'classified_13_joint_obstructions.json',classified)
 result={'classified_shapes':len(classified),'all_13_have_joint_obstruction':True,'minimum_anchor_counts':{str(k):sum(r['minimum_anchor_witness']['k']==k for r in classified) for k in sorted({r['minimum_anchor_witness']['k'] for r in classified})},'local_context_counts':{'global':sum(r['minimum_anchor_witness']['context']==-1 for r in classified),'strict_descendant':sum(r['minimum_anchor_witness']['context']>=0 for r in classified)},'actual_smt_target_proofs_checked':proof_count,'all_witness_colorings_and_roots_valid':True,'report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 dump(OUT/'classification_summary.json',result)
 print(json.dumps(result,indent=2))
 print('id n m H opt k localN q J deficit side_regions')
 for r in classified:
  w=r['minimum_anchor_witness'];print(r['source_index'],r['n'],r['m'],r['B_hier'],r['optimum'],w['k'],w['N_context'],w['q'],w['J'],w['deficit_at_H'],[(s['colors'],s['beta'],s['notations']) for s in w['side_regions']])
if __name__=='__main__':main()
