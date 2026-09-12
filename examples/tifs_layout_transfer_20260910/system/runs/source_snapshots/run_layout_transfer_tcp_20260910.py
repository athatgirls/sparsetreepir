"""Frozen Fuel layout -> real TCP SimplePIR transfer; no historical overwrites."""
from pathlib import Path
import argparse,csv,hashlib,json,os,platform,random,statistics,subprocess,time
from tifs_revision_smt import build_layout,HASH_FORMAT
from measure_gap_algorithm_20260910 import metadata
from run_tifs_verified_backend_suite_20260910 import metadata_file
from run_tifs_ct_application_20260910 import run_pair

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'examples/tifs_layout_transfer_20260910/system'
FROZEN=ROOT/'examples/tifs_revision_20260910/verified_backend/fuel_h128'
WITNESS=ROOT/'examples/tifs_remaining_gap_20260910/fuel/capacity22_result.json'
METHODS=['first_fit','activebalance','opt_witness22','full_cache']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf8')
def csvwrite(p,rows):
    if rows:
        with p.open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def prepare(out):
    abp=FROZEN/'activebalance/layout_metadata.bin';ab=metadata(abp);ff=metadata(FROZEN/'first_fit/layout_metadata.bin')
    tree=build_layout(128,ab['slots'],color_strategy='activebalance');snapshot=json.loads((FROZEN/'layout_setup.json').read_text())
    assert tree.root.hex()==snapshot['root'] and len(tree.active_records)==198 and tree.width==9
    assert list(tree.slots)==ff['slots']
    nodes={v.index:v for v in tree.proof_nodes};buckets={}
    frozen_sources=[]
    for method,d in [('first_fit',ff),('activebalance',ab)]:
        bs={c:[] for c in range(1,d['m']+1)}
        for r in sorted(d['records'],key=lambda r:(r['color'],r['position'])):bs[r['color']].append(r['heap_node'])
        oldmanifest=FROZEN/method/'repeat0/manifest.json';manifest=json.loads(oldmanifest.read_text())
        for sub in manifest['subdatabases']:
            oldfile=oldmanifest.parent/sub['database_file'];payload=oldfile.read_bytes()
            assert payload==b''.join(tree.active_records[v] for v in bs[sub['color']])
            frozen_sources.append(oldfile)
        buckets[method]=bs
    witness=json.loads(WITNESS.read_text());assert witness['source_sha256']==sha(abp)
    lookup={(r['left'],r['right'],r['level']):r['heap_node'] for r in ab['records']};opt={c:[] for c in range(1,10)}
    for r in witness['records']:
        assert type(r['witness_color']) is int and 0<=r['witness_color']<9
        opt[r['witness_color']+1].append(lookup[r['left'],r['right'],r['level']])
    assert sorted(map(len,opt.values()))==[22]*9 and {v for vs in opt.values() for v in vs}==set(tree.active_records)
    for vs in opt.values():vs.sort(key=lambda v:nodes[v].interval_left)
    for slot in tree.slots:
        needed=set(tree.tree.proof_record_nodes(slot).values())
        assert all(len(needed.intersection(vs))<=1 for vs in opt.values())
    buckets['opt_witness22']=opt;buckets['full_cache']={1:sorted(tree.active_records)}
    for method,bs in buckets.items():
        d=out/'publisher'/method;d.mkdir(parents=True,exist_ok=True)
        metadata_file(d/'layout_metadata.bin',bs,nodes,128,tree.slots)
        if method in ('first_fit','activebalance'):
            assert (d/'layout_metadata.bin').read_bytes()==(FROZEN/method/'layout_metadata.bin').read_bytes()
        manifest={'method':method,'height':128,'metadata_file':'layout_metadata.bin','slots_file':'occupied_slots.bin','subdatabases':[]}
        if method=='full_cache':
            manifest['cache_file']='full_active_cache.bin';(d/'full_active_cache.bin').write_bytes(b''.join(tree.active_records[v] for v in bs[1]))
        else:
            for c,vs in bs.items():
                name=f'color_{c:02d}.bin';(d/name).write_bytes(b''.join(tree.active_records[v] for v in vs))
                manifest['subdatabases'].append({'color':c,'records':len(vs),'database_file':name})
        dump(d/'server_manifest.json',manifest)
    private=out/'client_inputs';private.mkdir(exist_ok=True)
    targets=[{'target_index':i,'slot_hex':s.to_bytes(16,'big').hex(),'value_hex':tree.values[s].hex()} for i,s in enumerate(tree.slots)]
    dump(out/'snapshot.json',{'height':128,'n':100,'N':198,'m':9,'root_hex':tree.root.hex(),'hash_format':HASH_FORMAT,
                            'source_snapshot':str(FROZEN.relative_to(ROOT)),'values':'same deterministic experimental values as frozen Fuel SMT; not native Fuel values',
                            'max_bucket':{method:max(map(len,bs.values())) for method,bs in buckets.items()},
                            'loads':{method:list(map(len,bs.values())) for method,bs in buckets.items()},
                            'witness_scope':'Separate exact capacity-22 feasible witness, not AB and not the bounded 3/4-color prototype.'})
    (out/'capacity22_witness_frozen.json').write_bytes(WITNESS.read_bytes())
    return tree,targets,[abp,FROZEN/'first_fit/layout_metadata.bin',FROZEN/'layout_setup.json',WITNESS,*frozen_sources]

def summarize(out,rows):
    groups={}
    keys=[k for k,v in rows[0].items() if isinstance(v,(int,float)) and k not in ('repeat','client_pid','server_pid')]
    for method in METHODS:
        selected=[r for r in rows if r['method']==method]
        if not selected:continue
        groups[method]={k:{'mean':statistics.mean(r[k] for r in selected),'sample_sd':statistics.stdev(r[k] for r in selected) if len(selected)>1 else None,'runs':len(selected)} for k in keys}
    paired={}
    for baseline in ['first_fit','activebalance']:
        ratios=[]
        for rep in sorted({r['repeat'] for r in rows}):
            found={r['method']:r for r in rows if r['repeat']==rep}
            if baseline in found and 'opt_witness22' in found:ratios.append(found[baseline]['mean_e2e_ms']/found['opt_witness22']['mean_e2e_ms'])
        if ratios:paired[baseline+'_over_opt_witness22']={'values':ratios,'mean':statistics.mean(ratios),'sample_sd':statistics.stdev(ratios) if len(ratios)>1 else None}
    dump(out/'summary.json',{'groups':groups,'paired_e2e_ratios':paired,'completed_process_pairs':len(rows),
                           'verified_measured_proofs':sum(r['proofs_verified'] for r in rows),
                           'statistical_unit':'one independent server/client process-pair mean; five paired repeats, not 500 independent targets',
                           'scope':'TCP loopback application-byte framing included; excludes TCP/IP headers, initial bootstrap from warm E2E, publisher setup, and network deployment claims.'})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=BASE/'runs');ap.add_argument('--binary',type=Path,default=BASE/'tifs_layout_transfer_tcp')
    ap.add_argument('--samples',type=int,default=100);ap.add_argument('--repeats',type=int,default=5);ap.add_argument('--warmup',type=int,default=5);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    if (a.output/'run_summary.csv').exists():raise RuntimeError('fresh output directory required')
    tree,targets,sources=prepare(a.output);assert a.samples<=len(targets)
    sources += [Path(__file__),ROOT/'scripts/tifs_layout_transfer_tcp_20260910.go',ROOT/'backend/simplepir/tifs_tcp_certificate_backend.go',ROOT/'scripts/run_tifs_ct_application_20260910.py',ROOT/'scripts/tifs_revision_smt.py',a.binary]
    dump(a.output/'source_manifest.json',{'sha256':{str(p.relative_to(ROOT)):sha(p) for p in sources}})
    dump(a.output/'environment.json',{'python':platform.python_version(),'platform':platform.platform(),'go':subprocess.check_output(['go','version'],text=True).strip(),
         'cpu':next((x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'unknown'),
         'samples':a.samples,'repeats':a.repeats,'warmup':a.warmup,'gomaxprocs':1,
         'target_schedule':'100 distinct Fuel targets shuffled per repeat, exactly paired across four methods; fixed seed 202609103000+repeat',
         'method_order':'independently shuffled per repeat with the same per-repeat seeded RNG',
         'client_role':'Only known selected slots/values and pinned root are opened locally; public directory, Params/DBinfo, expanded A, hints/cache all arrive through TCP.'})
    rows=[];queries=[]
    for rep in range(a.repeats):
        rng=random.Random(202609103000+rep);chosen=rng.sample(targets,a.samples);order=METHODS.copy();rng.shuffle(order)
        inp=a.output/'client_inputs'/f'repeat{rep}.json';dump(inp,{'trusted_root_hex':tree.root.hex(),'height':128,'warmup':a.warmup,'targets':chosen})
        dump(inp.with_name(f'repeat{rep}_selection.json'),{'seed':202609103000+rep,'method_order':order,'target_indices':[r['target_index'] for r in chosen]})
        for method in order:
            run=a.output/method/f'repeat{rep}';print('START',method,rep,flush=True)
            client,server,wall=run_pair(a.binary,a.output/'publisher'/method/'server_manifest.json',inp,run,120)
            qs=client['queries'];times=server['server_answer_ms_including_warmup'][a.warmup:]
            row={'method':method,'repeat':rep,'proofs_verified':len(qs),'max_bucket':max(json.loads((a.output/'snapshot.json').read_text())['loads'][method]),
              'mean_e2e_ms':statistics.mean(q['end_to_end_ms'] for q in qs),'mean_query_ms':statistics.mean(q['query_generation_ms'] for q in qs),
              'mean_server_answer_ms':statistics.mean(times) if times else 0,'mean_recover_ms':statistics.mean(q['decode_ms'] for q in qs),
              'mean_route_ms':statistics.mean(q['known_value_decode_and_routing_ms'] for q in qs),'mean_verify_ms':statistics.mean(q['assembly_rootcheck_ms'] for q in qs),
              'mean_request_response_ms':statistics.mean(q['serialize_transport_answer_ms'] for q in qs),
              'mean_upload_wire_bytes':statistics.mean(q['upload_wire_bytes'] for q in qs),'mean_download_wire_bytes':statistics.mean(q['download_wire_bytes'] for q in qs),
              'mean_online_wire_bytes':statistics.mean(q['upload_wire_bytes']+q['download_wire_bytes'] for q in qs),
              'bootstrap_ms':client['bootstrap_ms'],'bootstrap_upload_wire_bytes':client['bootstrap_upload_wire_bytes'],'bootstrap_download_wire_bytes':client['bootstrap_download_wire_bytes'],
              'bootstrap_total_wire_bytes':client['bootstrap_upload_wire_bytes']+client['bootstrap_download_wire_bytes'],
              'metadata_bytes':client['metadata_bytes'],'slots_bytes':client['slots_bytes'],'hint_matrix_bytes':server['hint_matrix_bytes'],
              'shared_A_matrix_bytes':server['shared_matrix_bytes'],'cache_payload_bytes':client['cache_payload_bytes'],
              'client_peak_rss_bytes':client['client_peak_rss_bytes'],'server_peak_rss_bytes':server['server_peak_rss_bytes'],
              'server_setup_ms':server['setup_ms'],'logical_queries':qs[0]['logical_queries'],'pair_wall_seconds':wall,
              'client_pid':client['client_pid'],'server_pid':server['server_pid']}
            rows.append(row);queries += [{'method':method,'repeat':rep,**q} for q in qs]
            csvwrite(a.output/'run_summary.csv',rows);csvwrite(a.output/'query_measurements.csv',queries);summarize(a.output,rows)
            print('DONE',method,rep,'E2E_ms',round(row['mean_e2e_ms'],4),'online_bytes',row['mean_online_wire_bytes'],flush=True)
    dump(a.output/'completion.json',{'independent_process_pairs':len(rows),'verified_measured_proofs':len(queries),'status':'complete','warmup_proofs_per_pair':a.warmup,'failures':0})

if __name__=='__main__':main()
