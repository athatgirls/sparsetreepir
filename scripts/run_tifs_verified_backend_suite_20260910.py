"""Paired local SimplePIR experiments with independent full SMT-root verification.

New experiment, separate from all historical shape measurements. Run under WSL.
The 3-choice control is implemented here, not the published SealPIR executable.
"""
from pathlib import Path
import argparse, bisect, csv, hashlib, json, math, os, platform, random, statistics, struct, subprocess, time
from tifs_revision_smt import build_layout, verify_proof, HASH_FORMAT
from run_real_smt_workload_experiment import iter_keys,key_to_slot

ROOT=Path(__file__).absolute().parents[1]
OUT=ROOT/'examples/tifs_revision_20260910/verified_backend'
DATASETS={
 'fuel':('Fuel vectors','fuel_smt_test_workload.csv','hex-prefix'),
 'polygon-recent':('Polygon recent','polygon_zkevm_account_leaf_workload.csv','sha256'),
 'zksync-sample':('ZKsync sample','zksync_era_account_leaf_workload_sample.csv','sha256'),
 'polygon-multi':('Polygon multi','polygon_zkevm_account_leaf_workload_multiwindow.csv','sha256'),
 'polygon-broad':('Polygon broad','polygon_zkevm_account_leaf_workload_broad_multiwindow.csv','sha256'),
 'zksync-broad':('ZKsync broad','zksync_era_account_leaf_workload_broad_sample.csv','sha256')}
METHODS=['first_fit','hybrid','activebalance','nonempty_depth','flat_active','pbc_routed']

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def csvwrite(path,rows):
 if not rows:return
 with path.open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def need_for(slot,h,active):
 node=(1<<h)+slot;result={}
 for level in range(h):
  if node^1 in active:result[level]=node^1
  node//=2
 return result
def matching(nodes,choices):
 assigned={}
 def place(node,seen):
  for c in choices[node]:
   if c in seen:continue
   seen.add(c)
   if c not in assigned or place(assigned[c],seen):assigned[c]=node;return True
  return False
 for n in nodes:
  if not place(n,set()):return None
 return {node:color for color,node in assigned.items()}
def pbc_buckets(base,allneeds):
 b=max(3,math.ceil(1.5*base.width));attempts=[];start=time.perf_counter()
 for attempt in range(20):
  seed=202609100+attempt;choices={};buckets={c:[] for c in range(1,b+1)}
  for node in sorted(base.active_records):
   rng=random.Random(int.from_bytes(hashlib.sha256(f'{seed}:{node}'.encode()).digest(),'big'))
   choices[node]=rng.sample(range(1,b+1),3)
   for c in choices[node]:buckets[c].append(node)
  failures=sum(matching(list(needed.values()),choices) is None for needed in allneeds.values())
  attempts.append({'seed':seed,'failed_targets':failures,'tested_targets':len(allneeds)})
  if failures==0:return buckets,choices,{'hash_seed':seed,'public_setup_attempts':attempts,'routing_preflight_ms':1000*(time.perf_counter()-start),'bucket_count':b,'placement':'three distinct pseudorandom choices per active record; maximum bipartite matching; all occupied targets preflighted before publication'}
 raise RuntimeError('PBC public setup did not find a placement serving every occupied target')
def metadata_file(path,buckets,nodes,h,slots):
 # Executable compact layout directory: explicit counts, interval endpoints,
 # proof level, flags and within-bucket position. 24 bytes per stored record.
 raw=bytearray(b'TIFSMETA'+struct.pack('>HII',h,len(slots),len(buckets)))
 for c,ids in sorted(buckets.items()):
  raw.extend(struct.pack('>II',c,len(ids)))
  for pos,node in enumerate(ids):
   n=nodes[node];raw.extend(struct.pack('>QQHHI',n.interval_left,n.interval_right,h-n.depth,0,pos))
 path.write_bytes(raw)
 keypath=path.with_name('occupied_slots.bin');keypath.write_bytes(b''.join(s.to_bytes((h+7)//8,'big') for s in slots))
 return len(raw)+keypath.stat().st_size
def read_directory(path):
 start=time.perf_counter();raw=path.read_bytes();assert raw[:8]==b'TIFSMETA'
 h,n,count=struct.unpack_from('>HII',raw,8);offset=18
 keybytes=path.with_name('occupied_slots.bin').read_bytes();size=(h+7)//8
 slots=[int.from_bytes(keybytes[i:i+size],'big') for i in range(0,len(keybytes),size)];assert len(slots)==n
 locations={};sizes={};by_position={};intervals={}
 for _ in range(count):
  c,length=struct.unpack_from('>II',raw,offset);offset+=8;sizes[c]=length;intervals[c]=[]
  for _ in range(length):
   left,right,level,flags,pos=struct.unpack_from('>QQHHI',raw,offset);offset+=24
   assert 0<=left<=right<n and level<h
   node=(((1<<h)+slots[left])>>level)^1
   locations.setdefault(node,[]).append((c,pos));by_position[c,pos]=node
   intervals[c].append((left,right,level,pos))
 assert offset==len(raw)
 for entries in intervals.values():entries.sort()
 return {'height':h,'locations':locations,'sizes':sizes,'by_position':by_position,'slots':slots,'intervals':intervals,'lefts':{c:[e[0] for e in entries] for c,entries in intervals.items()},'parse_ms':1000*(time.perf_counter()-start)}
def directory_route(directory,slot,method,width):
 if method in ('first_fit','hybrid','activebalance','nonempty_depth'):
  rank=bisect.bisect_left(directory['slots'],slot);assert rank<len(directory['slots']) and directory['slots'][rank]==slot
  selection={}
  for c,entries in directory['intervals'].items():
   pos=bisect.bisect_right(directory['lefts'][c],rank)-1
   if pos>=0 and entries[pos][1]>=rank:
    left,right,level,index=entries[pos];selection[c]=(index,level)
  return selection
 needed=need_for(slot,directory['height'],directory['locations']);selection={}
 if method=='pbc_routed':
  choices={node:[c for c,pos in directory['locations'][node]] for node in needed.values()}
  assigned=matching(list(needed.values()),choices);assert assigned is not None
  for level,node in needed.items():
   c=assigned[node];pos=next(pos for color,pos in directory['locations'][node] if color==c);selection[c]=(pos,level)
 elif method=='flat_active':
  for c,(level,node) in enumerate(sorted(needed.items()),1):selection[c]=(directory['locations'][node][0][1],level)
 else:
  for level,node in needed.items():
   c,pos=directory['locations'][node][0];assert c not in selection;selection[c]=(pos,level)
 assert len(selection)<=width
 return selection
def prepare_manifest(base,buckets,method,targets,needs,choices,path,rng,directory=None):
 path.mkdir(parents=True,exist_ok=True);routing=[];indices={c:[] for c in buckets};route_times=[]
 if directory is None:directory=read_directory(path.parent/'layout_metadata.bin')
 locations={node:(c,pos) for c,ids in buckets.items() for pos,node in enumerate(ids)}
 pbcpos={c:{node:pos for pos,node in enumerate(ids)} for c,ids in buckets.items()}
 for slot in targets:
  start=time.perf_counter();selection=directory_route(directory,slot,method,len(buckets))
  for c,ids in buckets.items():indices[c].append(selection[c][0] if c in selection else rng.randrange(max(1,len(ids))))
  route_times.append((time.perf_counter()-start)*1000);routing.append({str(c):lev for c,(_,lev) in selection.items()})
 unique={};subdbs=[];stored=0
 for c,ids in buckets.items():
  content=b''.join(base.active_records[n] for n in ids) or bytes(32);digest=hashlib.sha256(content).hexdigest()
  if digest not in unique:
   filename=f'color_{c:02d}.bin';(path/filename).write_bytes(content);unique[digest]=filename;stored+=len(content)
  subdbs.append({'color':c,'records':max(1,len(ids)),'record_bytes':32,'database_file':unique[digest],'query_indices':indices[c]})
 manifest={'scheme':method,'height':base.height,'width':len(buckets),'active_nodes':len(base.active_records),'query_samples':len(targets),'record_bytes':32,'subdatabases':subdbs,'hash_format':HASH_FORMAT}
 dump(path/'manifest.json',manifest)
 context={'notice':'Local benchmark CLIENT context, not a server-visible protocol message','root':base.root.hex(),'slots':[hex(s) for s in targets],'real_color_to_level':routing,'routing_ms':route_times}
 dump(path/'client_context.json',context)
 return path/'manifest.json',routing,route_times,stored
def percentile(values,p):
 return float(__import__('numpy').percentile(values,p))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--datasets',default=','.join(DATASETS));ap.add_argument('--height',type=int,default=128);ap.add_argument('--samples',type=int,default=100);ap.add_argument('--repeats',type=int,default=5);ap.add_argument('--warmup',type=int,default=5);ap.add_argument('--timeout',type=int,default=240);ap.add_argument('--methods',default=','.join(METHODS));ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--binary',type=Path,default=ROOT/'examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend');ap.add_argument('--resume',action='store_true');a=ap.parse_args()
 a.output.mkdir(parents=True,exist_ok=True);methods=a.methods.split(',');assert all(m in METHODS for m in methods)
 env=os.environ.copy();env['GOMAXPROCS']='1';env['OMP_NUM_THREADS']='1'
 environment={'platform':platform.platform(),'python':platform.python_version(),'processor':platform.processor(),'gomaxprocs':1,'warmup_extra_queries':a.warmup,'samples_per_run':a.samples,'independent_process_repeats':a.repeats,'height':a.height,'backend':'SimplePIR eight 32bit chunks per digest','network':'none; local API functional pipeline','value_source':'deterministic experiment values on workload-derived coordinates; not native chain state','hash_format':HASH_FORMAT,'timing':'backend wall + Python routing + independent proof assembly/verification; excludes process startup, JSON transport and network','binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest()}
 dump(a.output/'environment.json',environment);rows=[];queries=[];failures=[]
 for key in a.datasets.split(','):
  label,filename,mode=DATASETS[key];source=ROOT/'datasets'/filename
  slots=sorted({key_to_slot(k,a.height,mode) for k in iter_keys(source,'key',None,None)})
  dpath=a.output/f'{key}_h{a.height}';dpath.mkdir(exist_ok=True)
  print('BUILD',key,'n=',len(slots),flush=True)
  layouts={m:build_layout(a.height,slots,color_strategy=m) for m in ['first_fit','hybrid','activebalance'] if m in methods or m=='first_fit'}
  base=layouts['first_fit'];assert all(l.root==base.root for l in layouts.values())
  needs={s:need_for(s,a.height,base.active_records) for s in slots};nodes={n.index:n for n in base.proof_nodes}
  buckets={m:l.buckets for m,l in layouts.items()};choices=None;pbcinfo={}
  depth=sorted({n.depth for n in base.proof_nodes});buckets['nonempty_depth']={c:sorted([n.index for n in base.proof_nodes if n.depth==dep],key=lambda n:nodes[n].interval_left) for c,dep in enumerate(depth,1)}
  allids=sorted(base.active_records);buckets['flat_active']={c:allids for c in range(1,base.width+1)}
  if 'pbc_routed' in methods:buckets['pbc_routed'],choices,pbcinfo=pbc_buckets(base,needs)
  dump(dpath/'layout_setup.json',{'dataset':label,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'n':len(slots),'N':len(base.active_records),'m':base.width,'root':base.root.hex(),'build_timings_ms':{m:l.timings_ms for m,l in layouts.items()},'pbc':pbcinfo})
  metadata={}
  for method in methods:
   meta_dir=dpath/method;meta_dir.mkdir(exist_ok=True)
   mb={1:allids} if method=='flat_active' else buckets[method]
   metadata[method]=metadata_file(meta_dir/'layout_metadata.bin',mb,nodes,a.height,slots)
  # Full-cache reference really writes the complete active digest payload and
  # the same canonical flat directory, then verifies locally without PIR.
  (dpath/'full_active_cache.bin').write_bytes(b''.join(base.active_records[n] for n in allids))
  cache_meta=metadata_file(dpath/'full_cache_metadata.bin',{1:allids},nodes,a.height,slots)
  cache_bytes=(dpath/'full_active_cache.bin').stat().st_size+cache_meta
  cache_times=[];cache_directory=read_directory(dpath/'full_cache_metadata.bin');cache_data=(dpath/'full_active_cache.bin').read_bytes()
  for s in slots[:min(1000,len(slots))]:
   t=time.perf_counter();proof=list(base.defaults[:a.height])
   for pos,level in directory_route(cache_directory,s,'flat_active',base.width).values():proof[level]=cache_data[pos*32:(pos+1)*32]
   assert verify_proof(a.height,s,base.values[s],proof,base.root)
   cache_times.append((time.perf_counter()-t)*1000)
  dump(dpath/'full_cache_reference.json',{'stored_and_bootstrap_bytes':cache_bytes,'digest_payload_bytes':32*len(allids),'directory_and_slots_bytes':cache_meta,'proofs_checked':len(cache_times),'local_proof_p50_ms':statistics.median(cache_times),'local_proof_p95_ms':percentile(cache_times,95),'online_request_bytes':0,'scope':'private by full download; client holds all active digests plus directory; initial transfer time is not measured'})
  for rep in range(a.repeats):
   seed=2026091000+rep; rng=random.Random(seed)
   targets=rng.sample(slots,a.samples) if a.samples<=len(slots) else [rng.choice(slots) for _ in range(a.samples)]
   order=list(methods);rng.shuffle(order)
   dump(dpath/f'targets_repeat{rep}.json',{'seed':seed,'slots':[hex(s) for s in targets],'method_order':order})
   for method in order:
    run=dpath/method/f'repeat{rep}';directory=read_directory(dpath/method/'layout_metadata.bin')
    manifest,routing,route_ms,stored=prepare_manifest(base,buckets[method],method,targets,needs,choices,run,random.Random(seed+METHODS.index(method)),directory)
    resultfile=run/'backend_result.json'
    signature={'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'database_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in run.glob('*.bin')},'binary_sha256':environment['binary_sha256'],'warmup':a.warmup,'gomaxprocs':1,'schema':'verified-backend-v2'}
    signaturefile=run/'run_signature.json'
    reuse=a.resume and resultfile.exists() and signaturefile.exists() and json.loads(signaturefile.read_text(encoding='utf8'))==signature
    if not reuse:
     try:
      process=subprocess.run([str(a.binary),'-warmup',str(a.warmup),'-gomaxprocs','1','-output',str(resultfile),str(manifest)],env=env,capture_output=True,text=True,timeout=a.timeout)
      (run/'stderr.txt').write_text(process.stderr,encoding='utf8')
      if process.returncode!=0:raise RuntimeError(process.stderr[-1500:])
      dump(signaturefile,signature)
     except (subprocess.TimeoutExpired,RuntimeError) as exc:
      failure={'dataset':label,'method':method,'repeat':rep,'error':str(exc)};failures.append(failure);dump(a.output/'failures.json',failures);print('FAILED',failure,flush=True);continue
    result=json.loads(resultfile.read_text(encoding='utf8'));assert len(result['targets'])==len(targets)
    qr=[]
    for i,(target,actual) in enumerate(zip(targets,result['targets'])):
     assert actual['sample_index']==i
     start=time.perf_counter();proof=list(base.defaults[:a.height]);recovered={int(r['color']):bytes.fromhex(r['record_hex']) for r in actual['recovered_records']}
     for c,level in routing[i].items():proof[level]=recovered[int(c)]
     assert verify_proof(a.height,target,base.values[target],proof,base.root),(label,method,rep,i)
     verify_ms=(time.perf_counter()-start)*1000
     # Independent corruption check on an actual recovered, used proof digest.
     if needs[target]:
      level=next(iter(needs[target]));bad=list(proof);bad[level]=bytes([bad[level][0]^1])+bad[level][1:]
      assert not verify_proof(a.height,target,base.values[target],bad,base.root)
     q={'dataset':label,'height':a.height,'method':method,'repeat':rep,'sample_index':i,'target_slot':hex(target),'query_ms':actual['client_query_ms'],'answer_ms':actual['server_answer_ms'],'decode_ms':actual['client_decode_ms'],'backend_wall_ms':actual['backend_wall_ms'],'routing_ms':route_ms[i],'proof_assembly_verify_ms':verify_ms,'processing_ms':actual['backend_wall_ms']+route_ms[i]+verify_ms,'online_bytes':actual['online_total_bytes'],'valid_root':True}
     qr.append(q);queries.append(q)
    setup=result['setup'];row={'dataset':label,'height':a.height,'method':method,'repeat':rep,'n':len(slots),'N':len(allids),'m':base.width,'logical_queries':len(buckets[method]),'chunk_queries':8*len(buckets[method]),'max_bucket':max(map(len,buckets[method].values())),'proofs_verified':len(qr),'online_bytes':statistics.mean(q['online_bytes'] for q in qr),'processing_mean_ms':statistics.mean(q['processing_ms'] for q in qr),'processing_p50_ms':statistics.median(q['processing_ms'] for q in qr),'processing_p95_ms':percentile([q['processing_ms'] for q in qr],95),'query_mean_ms':statistics.mean(q['query_ms'] for q in qr),'answer_mean_ms':statistics.mean(q['answer_ms'] for q in qr),'decode_mean_ms':statistics.mean(q['decode_ms'] for q in qr),'verify_mean_ms':statistics.mean(q['proof_assembly_verify_ms'] for q in qr),'setup_api_ms':setup['setup_api_ms'],'setup_total_wall_ms':setup['total_setup_wall_ms'],'offline_hint_bytes':setup['offline_hint_bytes'],'client_metadata_bytes':metadata[method],'directory_plus_hint_bytes':metadata[method]+setup['offline_hint_bytes'],'public_shared_state_bytes':setup.get('public_shared_state_bytes',-1),'server_payload_bytes':stored,'full_cache_bootstrap_bytes':cache_bytes}
    row['client_directory_parse_ms']=directory['parse_ms'];row['runner_peak_rss_bytes']=result.get('process_peak_rss_bytes')
    rows.append(row);csvwrite(run/'verified_queries.csv',qr);dump(run/'verified_summary.json',row)
    csvwrite(a.output/'run_summary.csv',rows);csvwrite(a.output/'query_measurements.csv',queries)
    print('DONE',key,method,rep,'proofs',len(qr),'ms',round(row['processing_mean_ms'],3),flush=True)
 dump(a.output/'completion.json',{'completed_process_runs':len(rows),'verified_proofs':len(queries),'failed_process_runs':failures,'requested_datasets':a.datasets,'methods':methods,'repeats':a.repeats,'samples':a.samples})

if __name__=='__main__':main()
