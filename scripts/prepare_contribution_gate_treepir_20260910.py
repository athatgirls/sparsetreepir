"""Compile unchanged official CSA/indexing, verify full-tree common instances."""
from pathlib import Path
import csv, hashlib, json, os, subprocess
from tifs_revision_smt import build_layout, verify_proof
from run_tifs_verified_backend_suite_20260910 import metadata_file
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'

def run(cmd,log):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=90)
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(json.dumps({'command':[str(x) for x in cmd],'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n')
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout

def main():
    official=OUT/'official_sources';build=OUT/'java_build';gson=official/'CSA/gson-2.10.1.jar'
    for mode,cls,source in [('csa','CSA',official/'CSA/src/CSA.java'),('index','SubCSA',official/'TreePIR-Indexing/src/SubCSA.java')]:
        dest=build/mode;dest.mkdir(parents=True,exist_ok=True)
        cmd=['javac','-d',dest,'-cp',gson,source]
        if mode=='csa':cmd.append(official/'CSA/src/MerkleTrees.java')
        cmd.append(ROOT/f'scripts/contribution_gate_{mode}_20260910.java')
        run(cmd,OUT/f'logs/javac_{mode}.json')
    summary=[]
    for h in [4,10]:
        work=OUT/f'complete_h{h}';work.mkdir(exist_ok=True)
        records={};indexrows=[]
        for mode in ['csa','index']:
            output=run(['java','-cp',str(build/mode)+os.pathsep+str(gson),f'contribution_gate_{mode}_20260910',str(h)],OUT/f'logs/{mode}_h{h}.json')
            (work/f'official_{mode}.tsv').write_text(output)
            rows=list(csv.DictReader(output.splitlines(),delimiter='\t'))
            if mode=='csa':
                for r in rows:
                    node=int(r['swapped_node']);color=ord(r['color'])-64;pos=int(r['position'])
                    assert node not in records;records[node]=(color,pos)
            else:indexrows=rows
        assert set(records)==set(range(2,1<<(h+1)))
        for r in indexrows:
            node=int(r['swapped_node']);slot=int(r['target_slot'])
            assert records[node]==(ord(r['color'])-64,int(r['position']))
            assert node in [((1<<h)+slot)>>level for level in range(h)]
        assert len(indexrows)==(1<<h)*h
        base=build_layout(h,range(1<<h),color_strategy='first_fit')
        ab=build_layout(h,range(1<<h),color_strategy='activebalance',refine_rounds=20)
        nodes={n.index:n for n in base.proof_nodes}
        tb={c:[] for c in range(1,h+1)}
        for node,(color,pos) in sorted(records.items(),key=lambda x:x[1]):
            assert len(tb[color])==pos;tb[color].append(node^1)
        layouts={'treepir_official':tb,'first_fit':base.buckets,'activebalance':ab.buckets}
        assert set(base.active_records)==set(range(2,1<<(h+1)))
        for method,buckets in layouts.items():
            directory=work/method;directory.mkdir(exist_ok=True)
            metadata_file(directory/'layout_metadata.bin',buckets,nodes,h,base.slots)
            manifest={'method':method,'height':h,'metadata_file':'layout_metadata.bin','slots_file':'occupied_slots.bin','subdatabases':[]}
            colorlookup={v:(c,pos) for c,vs in buckets.items() for pos,v in enumerate(vs)}
            for c,vs in buckets.items():
                name=f'color_{c:02d}.bin';(directory/name).write_bytes(b''.join(base.active_records[v] for v in vs))
                manifest['subdatabases'].append({'color':c,'records':len(vs),'database_file':name})
            proofs=[]
            for slot in base.slots:
                need=base.tree.proof_record_nodes(slot)
                assert len({colorlookup[v][0] for v in need.values()})==h
                assert verify_proof(h,slot,base.values[slot],base.tree.proof(slot),base.root)
                proofs.append({'slot':slot,'records':[{'level':level,'node':node,'color':colorlookup[node][0],'position':colorlookup[node][1]} for level,node in sorted(need.items())]})
            (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            (directory/'all_target_routes.json').write_text(json.dumps(proofs,indent=2)+'\n')
            summary.append({'height':h,'method':method,'leaves':1<<h,'records':len(base.active_records),'width':h,
                            'loads':[len(vs) for vs in buckets.values()],'max_bucket':max(map(len,buckets.values())),
                            'all_target_proofs_verified':len(base.slots),'root_hex':base.root.hex()})
        snapshot={'height':h,'slots':list(base.slots),'values_hex':{str(s):v.hex() for s,v in base.values.items()},'root_hex':base.root.hex(),
                  'digest_hex':{str(n):v.hex() for n,v in base.active_records.items()},'official_csa_and_fast_index_agree_all_targets':True,
                  'swapping':'Original Merkle digest at node v is stored at official swapped node v xor 1. No record omitted or replicated.'}
        (work/'snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    (OUT/'common_instance_layouts.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
