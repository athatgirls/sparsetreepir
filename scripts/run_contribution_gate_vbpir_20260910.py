"""Official VBPIR query/recovery with common data and a separate SHA-256 verifier.

There is no interprocess transport, and verifier time is not included in the
official component intervals. This is not a native full-system E2E experiment.
"""
from pathlib import Path
import argparse,csv,hashlib,json,os,random,re,statistics,subprocess,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'
NATIVE=OUT/'native_vbpir';BIN=NATIVE/'source/build/bin/vbpir_treepir'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def H(x):return hashlib.sha256(x).digest()
def verify(slot,value,proof,root):
    now=H(b'\x00'+value)
    for level,d in enumerate(proof):now=H(b'\x01'+(d+now if slot&(1<<level) else now+d))
    return now.hex()==root
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    runs=NATIVE/('smoke' if args.smoke else 'authenticated_common_runs');runs.mkdir(exist_ok=True)
    if (runs/'summary.json').exists():raise RuntimeError('preserve completed output')
    work=OUT/'complete_h10';snap=json.loads((work/'snapshot.json').read_text())
    targets=[0] if args.smoke else [0,1,127,255,511,512,767,895,1022,1023]
    order=['treepir_official','activebalance'];random.Random(2026091102).shuffle(order)
    rows=[];allproofs=[]
    for method in order:
        inp=runs/method/'input';(inp/'treedata').mkdir(parents=True,exist_ok=True);(inp/'colorSubDB').mkdir(exist_ok=True);(inp/'subIndices').mkdir(exist_ok=True)
        # Official whole-tree JSON is indexed by swapped IDs, ordered from 2 upward.
        whole={str(node):snap['digest_hex'][str(node^1)] for node in range(2,2048)}
        save(inp/'treedata/WholeTree_10_2.json',whole)
        routes=json.loads((work/method/'all_target_routes.json').read_text());manifest=json.loads((work/method/'manifest.json').read_text())
        for sub in manifest['subdatabases']:
            c=sub['color'];ordered={}
            # Derive every bucket's position-to-node mapping from public checked routes.
            lookup={r['position']:r['node'] for target in routes for r in target['records'] if r['color']==c}
            assert set(lookup)==set(range(sub['records']))
            for pos in range(sub['records']):node=lookup[pos];ordered[str(node^1)]=snap['digest_hex'][str(node)]
            save(inp/f'colorSubDB/color{chr(64+c)}_10_2.json',[ordered])
        (inp/'list_TXs_10_2.txt').write_text(''.join(str(t+1)+'\n' for t in targets))
        indexlines=[]
        for target in targets:
            indexlines.append(f'TX_index: {target+1}')
            for r in sorted(routes[target]['records'],key=lambda r:r['color']):indexlines.append(f'color{chr(64+r["color"])}_10_2.json; NodeID: {r["node"]^1}; Index: {r["position"]}')
        (inp/'subIndices/color_indices_10_2.txt').write_text('\n'.join(indexlines)+'\n')
        env=dict(os.environ,TREEPIR_INPUT_DIR=str(inp),OMP_NUM_THREADS='1');started=time.perf_counter()
        print('START native VBPIR',method,len(targets),'targets',flush=True)
        process=subprocess.run([str(BIN)],capture_output=True,text=True,env=env,timeout=150)
        wall=time.perf_counter()-started
        run=runs/method;(run/'stdout.txt').write_text(process.stdout);(run/'stderr.txt').write_text(process.stderr)
        save(run/'process.json',{'binary':str(BIN),'returncode':process.returncode,'wall_seconds':wall,'targets':targets,'method_order':order,'OMP_NUM_THREADS':1,'TREEPIR_INPUT_DIR':str(inp)})
        if process.returncode:raise RuntimeError(process.stderr[-1800:])
        blocks=re.split(r'Starting example index = (\d+)',process.stdout)[1:];assert len(blocks)==2*len(targets)
        proofs=[]
        for j in range(0,len(blocks),2):
            target=int(blocks[j])-1;block=blocks[j+1];assert target==targets[j//2]
            recovered=re.findall(r'Hexadecimal string: 0x([0-9a-fA-F]{64})',block.split('Contents of decode_responses:',1)[1])
            assert len(recovered)==10
            proof=[None]*10
            for r,d in zip(sorted(routes[target]['records'],key=lambda r:r['color']),recovered):
                assert d.lower()==snap['digest_hex'][str(r['node'])],(method,target,r['color'])
                proof[r['level']]=bytes.fromhex(d)
            value=bytes.fromhex(snap['values_hex'][str(target)]);assert verify(target,value,proof,snap['root_hex'])
            bad=proof.copy();bad[0]=bytes([bad[0][0]^1])+bad[0][1:];assert not verify(target,value,bad,snap['root_hex'])
            proofs.append({'target':target,'recovered_by_color':recovered,'proof_bottom_up_hex':[d.hex() for d in proof],'valid_root':True,'bitflip_rejected':True})
        save(run/'independent_root_verification.json',{'root_hex':snap['root_hex'],'proofs':proofs});allproofs.extend(proofs)
        record={'method':method,'height':10,'processes':1,'queries':len(targets),'proofs_verified':len(proofs),'process_wall_seconds':wall}
        for key,text in [('query_us','Query generation time'),('answer_us','Response generation time'),('recover_us','Extraction time')]:
            match=re.search(re.escape(text)+r': (\d+) microseconds',process.stdout);assert match;record[key]=int(match.group(1))
        for key,text in [('query_artifact_estimate_KB','Total Query communication'),('answer_artifact_estimate_KB','Total Answer communication')]:
            matches=re.findall(re.escape(text)+r': (\d+) KB',process.stdout);assert matches;record[key]=int(matches[-1])
        rows.append(record)
    save(runs/'summary.json',{'rows':rows,'proofs_verified':len(allproofs),'binary_sha256':hashlib.sha256(BIN.read_bytes()).hexdigest(),
           'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'scope':'Official VBPIR core plus portable input path/build adaptation and independent external authentication. One process per layout, fresh server/client objects per target as in official main; no warmup. Reported native microsecond means are descriptive only, not independent-run confidence intervals.',
           'full_native_service_e2e_gate':'NOT COMPLETED: no network, external verifier excluded from native component timers, native code lacks client root verifier.',
           'bytes_warning':'Original artifact query estimate uses Ciphertext.save_size()/2 and answer uses save_size(), rounded to integer KiB; these are not measured transport bytes.'})
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
