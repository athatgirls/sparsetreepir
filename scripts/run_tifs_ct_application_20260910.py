"""Real loopback certificate-record membership audit; separate client/server.

Run with the WSL experiment environment. No historical measurement is modified.
The publisher creates a fresh experimental SMT from frozen public CT records.
Client inputs contain only selected raw records and a locally pinned trusted root;
the client executable does not open the server manifest, databases, or directory.
"""
from pathlib import Path
import argparse, csv, hashlib, json, os, platform, random, statistics, subprocess, time
from tifs_revision_smt import build_layout, HASH_FORMAT
from run_tifs_verified_backend_suite_20260910 import metadata_file

ROOT=Path(__file__).absolute().parents[1]
BASE=ROOT/'examples/tifs_revision_20260910/ct_application'
METHODS=['first_fit','activebalance','nonempty_depth','full_cache']
def dump(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def csvwrite(path,rows):
 if rows:
  with path.open('w',newline='',encoding='utf8') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def meanstd(values):return {'mean':statistics.mean(values),'sample_sd':statistics.stdev(values) if len(values)>1 else None,'n':len(values)}
def prepare(source,out):
 records=list(csv.DictReader(source.open(encoding='utf-8-sig')))
 slots=[int(r['slot_hex'],16) for r in records];assert len(slots)==len(set(slots))
 values={int(r['slot_hex'],16):bytes.fromhex(r['value_hex']) for r in records}
 import base64
 for row in records:
  h=hashlib.sha256(base64.b64decode(row['leaf_input_base64'])).hexdigest()
  assert h==row['leaf_sha256']==row['value_hex'] and int(h[:32],16)==int(row['slot_hex'],16)
 start=time.perf_counter();base=build_layout(128,slots,values,color_strategy='activebalance');first=build_layout(128,slots,values,color_strategy='first_fit')
 assert first.root==base.root and first.active_records==base.active_records and first.width==base.width
 nodes={n.index:n for n in base.proof_nodes};allids=sorted(base.active_records)
 depths=sorted({n.depth for n in base.proof_nodes});buckets={'first_fit':first.buckets,'activebalance':base.buckets,'nonempty_depth':{c:sorted([n.index for n in base.proof_nodes if n.depth==dep],key=lambda k:nodes[k].interval_left) for c,dep in enumerate(depths,1)},'full_cache':{1:allids}}
 for method in METHODS:
  target=out/'publisher'/method;target.mkdir(parents=True,exist_ok=True)
  meta=metadata_file(target/'layout_metadata.bin',buckets[method],nodes,128,base.slots)
  manifest={'method':method,'height':128,'metadata_file':'layout_metadata.bin','slots_file':'occupied_slots.bin','subdatabases':[]}
  if method=='full_cache':
   manifest['cache_file']='full_active_cache.bin';(target/manifest['cache_file']).write_bytes(b''.join(base.active_records[n] for n in allids))
  else:
   for c,ids in buckets[method].items():
    name=f'color_{c:02d}.bin';(target/name).write_bytes(b''.join(base.active_records[n] for n in ids))
    manifest['subdatabases'].append({'color':c,'records':len(ids),'database_file':name})
  dump(target/'server_manifest.json',manifest)
 setup={'n':len(slots),'N':len(allids),'m':base.width,'D':len(depths),'height':128,'trusted_experimental_root_hex':base.root.hex(),'source_csv_sha256':digest(source),'hash_format':HASH_FORMAT,'value':'SHA256(raw CT MerkleTreeLeaf record)','slot':'first 128 bits of the value digest','build_wall_ms':1000*(time.perf_counter()-start),'build_timings_ms':base.timings_ms,'root_publication':'locally pinned experimental SMT root, not signed and not a native CT log root','max_bucket':{m:max(map(len,b.values())) for m,b in buckets.items()},'activebalance_passes':base.passes,'activebalance_moves':base.moves}
 dump(out/'publisher'/'snapshot.json',setup)
 return records,setup
def run_pair(binary,manifest,clientinput,run,timeout):
 run.mkdir(parents=True,exist_ok=True);ready=run/'ready.json';serverresult=run/'server_result.json';clientresult=run/'client_result.json'
 if ready.exists():raise RuntimeError(f'fresh run required: {run}')
 env=os.environ.copy();env['GOMAXPROCS']='1';env['OMP_NUM_THREADS']='1'
 servercmd=[str(binary),'-mode','server','-manifest',str(manifest),'-ready',str(ready),'-result',str(serverresult)]
 dump(run/'commands.json',{'server':servercmd,'client_input':str(clientinput),'timeout_per_pair_seconds':timeout})
 with (run/'server_stderr.txt').open('w') as serr:
  started=time.monotonic();server=subprocess.Popen(servercmd,stdout=serr,stderr=serr,env=env)
  try:
   while not ready.exists():
    if server.poll() is not None:raise RuntimeError(f'server exited {server.returncode}: {run}')
    if time.monotonic()-started>timeout:raise TimeoutError('server readiness timeout')
    time.sleep(.05)
   info=json.loads(ready.read_text());clientcmd=[str(binary),'-mode','client','-address',info['address'],'-input',str(clientinput),'-result',str(clientresult)]
   dump(run/'commands.json',{'server':servercmd,'client':clientcmd,'timeout_per_pair_seconds':timeout})
   client=subprocess.run(clientcmd,text=True,capture_output=True,env=env,timeout=max(1,timeout-(time.monotonic()-started)))
   (run/'client_stderr.txt').write_text(client.stderr,encoding='utf8')
   if client.returncode:raise RuntimeError(f'client failed {client.returncode}: {client.stderr[-1500:]}')
   server.wait(timeout=max(1,timeout-(time.monotonic()-started)))
   if server.returncode:raise RuntimeError(f'server failed {server.returncode}')
   result=json.loads(clientresult.read_text());serv=json.loads(serverresult.read_text());assert result['client_pid']!=serv['server_pid']
   assert all(q['valid_root'] and q['corruption_rejected'] for q in result['queries'])
   assert all(q['recovered_siblings'] and [x['level'] for x in q['recovered_siblings']]==sorted({x['level'] for x in q['recovered_siblings']}) for q in result['queries'])
   expectedbatches=0 if result['method']=='full_cache' else len(result['queries'])+result['warmup_queries']
   assert serv['query_batches_including_warmup']==expectedbatches
   assert len({(q['upload_wire_bytes'],q['download_wire_bytes']) for q in result['queries']})==1
   q=result['queries'][0];assert serv['total_read_wire_bytes']==result['bootstrap_upload_wire_bytes']+expectedbatches*q['upload_wire_bytes']
   assert serv['total_written_wire_bytes']==result['bootstrap_download_wire_bytes']+expectedbatches*q['download_wire_bytes']
   return result,serv,time.monotonic()-started
  finally:
   if server.poll() is None:server.kill();server.wait()
def summarize(out,rows):
 groups={}
 for method in METHODS:
  selected=[r for r in rows if r['method']==method]
  if selected:groups[method]={k:meanstd([r[k] for r in selected]) for k in ['mean_e2e_ms','bootstrap_ms','bootstrap_total_wire_bytes','mean_online_wire_bytes','client_peak_rss_bytes','server_peak_rss_bytes','mean_query_ms','mean_server_answer_ms','mean_decode_ms','mean_route_ms','mean_verify_ms']}
 dump(out/'summary.json',{'schema':1,'groups':groups,'completed_independent_pairs':len(rows),'verified_measured_proofs':sum(r['proofs_verified'] for r in rows),'warmup_queries_excluded':True,'statistical_unit':'independent client/server process pair mean; sample SD across pairs','network':'TCP loopback only; framing included, TCP/IP headers and retransmissions excluded','bootstrap':'actual serialized metadata, slots, Params/DBinfo, fully materialized public A and hints; full cache instead sends all active records; excludes publisher/server setup before listening'})
 return groups
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=BASE/'source/ct_records.csv');ap.add_argument('--binary',type=Path,default=BASE/'tifs_tcp_certificate_backend');ap.add_argument('--output',type=Path,default=BASE/'runs_verified_evidence');ap.add_argument('--samples',type=int,default=100);ap.add_argument('--repeats',type=int,default=5);ap.add_argument('--warmup',type=int,default=5);ap.add_argument('--timeout',type=int,default=120);a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=True)
 if (a.output/'run_summary.csv').exists():raise RuntimeError('choose a new output directory; no raw overwrites')
 records,setup=prepare(a.source,a.output);assert a.samples<=len(records)
 sources=[Path(__file__),ROOT/'backend/simplepir/tifs_tcp_certificate_backend.go',ROOT/'scripts/tifs_revision_smt.py',ROOT/'scripts/run_tifs_verified_backend_suite_20260910.py',a.source,a.binary]
 dump(a.output/'source_manifest.json',{'sha256':{str(p.relative_to(ROOT)):digest(p) for p in sources}})
 dump(a.output/'environment.json',{'platform':platform.platform(),'python':platform.python_version(),'go':subprocess.check_output(['go','version'],text=True).strip(),'cpu':next((x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'unknown'),'gomaxprocs':1,'execution':'sequential independent server/client pair, 127.0.0.1 ephemeral TCP port','samples':a.samples,'repeats':a.repeats,'warmup':a.warmup,'target_selection':'100 distinct records uniformly sampled per repeat, paired across methods; controlled workload, not an actual browser access trace','method_order':'independently shuffled for each repeat','server_client_role':'server opens only public snapshot files; client opens only target records and pinned root, receives all other state through TCP'})
 rows=[];allqueries=[]
 for rep in range(a.repeats):
  rng=random.Random(202609102000+rep);targets=rng.sample(records,a.samples);order=METHODS.copy();rng.shuffle(order)
  private=a.output/'client_inputs';private.mkdir(exist_ok=True);clientinput=private/f'repeat{rep}.json'
  dump(clientinput,{'trusted_root_hex':setup['trusted_experimental_root_hex'],'height':128,'warmup':a.warmup,'targets':[{'ct_index':int(r['ct_index']),'leaf_input_base64':r['leaf_input_base64']} for r in targets]})
  dump(private/f'repeat{rep}_selection.json',{'seed':202609102000+rep,'method_order':order,'ct_indices':[int(r['ct_index']) for r in targets]})
  for method in order:
   run=a.output/method/f'repeat{rep}';print('START',method,rep,flush=True)
   result,server,wall=run_pair(a.binary,a.output/'publisher'/method/'server_manifest.json',clientinput,run,a.timeout)
   qs=result['queries'];server_times=server['server_answer_ms_including_warmup'][a.warmup:]
   row={'method':method,'repeat':rep,'proofs_verified':len(qs),'mean_e2e_ms':statistics.mean(q['end_to_end_ms'] for q in qs),'bootstrap_ms':result['bootstrap_ms'],'bootstrap_total_wire_bytes':result['bootstrap_upload_wire_bytes']+result['bootstrap_download_wire_bytes'],'mean_online_wire_bytes':statistics.mean(q['upload_wire_bytes']+q['download_wire_bytes'] for q in qs),'client_peak_rss_bytes':result['client_peak_rss_bytes'],'server_peak_rss_bytes':server['server_peak_rss_bytes'],'server_setup_ms':server['setup_ms'],'mean_query_ms':statistics.mean(q['query_generation_ms'] for q in qs),'mean_server_answer_ms':statistics.mean(server_times) if server_times else 0,'mean_decode_ms':statistics.mean(q['decode_ms'] for q in qs),'mean_route_ms':statistics.mean(q['record_hash_and_routing_ms'] for q in qs),'mean_verify_ms':statistics.mean(q['assembly_rootcheck_ms'] for q in qs),'pair_process_wall_seconds':wall,'logical_queries':qs[0]['logical_queries'],'client_pid':result['client_pid'],'server_pid':server['server_pid']}
   rows.append(row)
   for q in qs:allqueries.append({'method':method,'repeat':rep,**q})
   csvwrite(a.output/'run_summary.csv',rows);csvwrite(a.output/'query_measurements.csv',allqueries);summarize(a.output,rows)
   print('DONE',method,rep,'proofs',len(qs),'e2e',round(row['mean_e2e_ms'],3),'ms','bootstrap',row['bootstrap_total_wire_bytes'],flush=True)
 dump(a.output/'completion.json',{'status':'complete','independent_client_server_pairs':len(rows),'measured_proofs_verified':len(allqueries),'failed_pairs':0,'fixed_wire_shape_all_queries':True,'socket_byte_counters_match':True,'distinct_process_ids':True})
if __name__=='__main__':main()
