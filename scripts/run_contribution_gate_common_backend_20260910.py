"""Common full-tree layout comparison on the unchanged eight-chunk SimplePIR backend.

This is a backend-only matched comparison, not official TreePIR native-system
timing. Both layouts' indices are prepared before Query/Answer/Recover timing.
"""
from pathlib import Path
import csv,hashlib,json,os,random,statistics,subprocess,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'
BIN=ROOT/'examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend'
METHODS=['treepir_official','first_fit','activebalance']
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def h(x):return hashlib.sha256(x).digest()
def verify(height,slot,value,proof,root):
    current=h(b'\x00'+value)
    for i,sib in enumerate(proof):current=h(b'\x01'+(sib+current if slot&(1<<i) else current+sib))
    return current==root
def main():
    runs=OUT/'common_simplepir';runs.mkdir(exist_ok=True)
    if (runs/'summary.json').exists():raise RuntimeError('Formal output exists; preserve it.')
    rows=[];queries=[]
    for height in [4,10]:
        work=OUT/f'complete_h{height}';snap=json.loads((work/'snapshot.json').read_text());n=1<<height
        for rep in range(3):
            rng=random.Random(20260911000+height*10+rep);targets=rng.sample(range(n),min(n,32));order=METHODS.copy();rng.shuffle(order)
            for method in order:
                run=runs/f'h{height}'/f'repeat{rep}'/method;run.mkdir(parents=True)
                route=json.loads((work/method/'all_target_routes.json').read_text());layout=json.loads((work/method/'manifest.json').read_text())
                subs=[]
                for sub in layout['subdatabases']:
                    color=sub['color'];indices=[next(r['position'] for r in route[t]['records'] if r['color']==color) for t in targets]
                    subs.append({'color':color,'records':sub['records'],'record_bytes':32,'database_file':str(work/method/sub['database_file']),'query_indices':indices})
                manifest={'scheme':method,'height':height,'width':height,'active_nodes':(1<<(height+1))-2,'query_samples':len(targets),'record_bytes':32,'subdatabases':subs}
                save(run/'manifest.json',manifest);save(run/'selection.json',{'targets':targets,'method_order':order,'repeat':rep,'seed':20260911000+height*10+rep})
                command=[str(BIN),'-warmup','5','-gomaxprocs','1','-output',str(run/'backend_result.json'),str(run/'manifest.json')]
                print('START',height,rep,method,flush=True);started=time.perf_counter()
                proc=subprocess.run(command,capture_output=True,text=True,env=dict(os.environ,GOMAXPROCS='1',OMP_NUM_THREADS='1'),timeout=90)
                save(run/'process.json',{'command':command,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'wall_seconds':time.perf_counter()-started})
                if proc.returncode:raise RuntimeError(proc.stderr)
                result=json.loads((run/'backend_result.json').read_text());actuals=result['targets']
                assert len(actuals)==len(targets)
                for target,actual in zip(targets,actuals):
                    proof=[None]*height
                    bycolor={r['color']:r for r in route[target]['records']}
                    for r in actual['recovered_records']:
                        expected=bycolor[r['color']];assert r['query_index']==expected['position']
                        got=bytes.fromhex(r['record_hex']);assert got.hex()==snap['digest_hex'][str(expected['node'])]
                        proof[expected['level']]=got
                    assert all(proof) and verify(height,target,bytes.fromhex(snap['values_hex'][str(target)]),proof,bytes.fromhex(snap['root_hex']))
                    bad=proof.copy();bad[0]=bytes([bad[0][0]^1])+bad[0][1:]
                    assert not verify(height,target,bytes.fromhex(snap['values_hex'][str(target)]),bad,bytes.fromhex(snap['root_hex']))
                    queries.append({'height':height,'repeat':rep,'method':method,'target':target,'valid_root':True,**{k:actual[k] for k in ['client_query_ms','server_answer_ms','client_decode_ms','backend_wall_ms','online_total_bytes']}})
                record={'height':height,'repeat':rep,'method':method,'proofs':len(targets),'max_bucket':max(s['records'] for s in subs),
                        'hint_bytes':result['setup']['offline_hint_bytes'],'public_A_bytes':result['setup']['public_shared_state_bytes'],'cache_digest_payload_bytes':manifest['active_nodes']*32}
                for key in ['client_query_ms','server_answer_ms','client_decode_ms','backend_wall_ms','online_total_bytes']:record[key]=statistics.mean(q[key] for q in actuals)
                rows.append(record)
    groups=[]
    for height in [4,10]:
        for method in METHODS:
            rs=[r for r in rows if r['height']==height and r['method']==method]
            keys=[k for k,v in rs[0].items() if isinstance(v,(int,float)) and k not in ('height','repeat')]
            groups.append({'height':height,'method':method,'processes':len(rs),'metrics':{k:{'mean':statistics.mean(r[k] for r in rs),'sample_sd':statistics.stdev(r[k] for r in rs)} for k in keys}})
    save(runs/'summary.json',{'groups':groups,'proofs_verified':len(queries),'statistical_unit':'three independent process means, paired target sets; no timing claim across native PIR families',
          'scope':'Common unchanged SimplePIR Query/Answer/Recover backend; indices prepared before measurement. No TCP, no online Java index cost, no claim this is the official full TreePIR system.',
          'binary_sha256':hashlib.sha256(BIN.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    for name,data in [('process_measurements.csv',rows),('query_measurements.csv',queries)]:
        with (runs/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    print(json.dumps({'completed_processes':len(rows),'proofs_verified':len(queries)}))
if __name__=='__main__':main()
