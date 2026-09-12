"""Standard-library-only raw reproduction checks; no runner/SMT helper imports."""
from pathlib import Path
import argparse,bisect,csv,hashlib,json,math,statistics,struct

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_layout_transfer_20260910/system';RUN=OUT/'runs'
METHODS=['first_fit','activebalance','opt_witness22','full_cache']
def H(x):return hashlib.sha256(x).digest()
def read(p):return json.loads(p.read_text())
def near(a,b):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-9),(a,b)

def parse_directory(path):
    data=path.read_bytes();assert data[:8]==b'TIFSMETA';h,n,m=struct.unpack_from('>HII',data,8);offset=18
    raw=path.with_name('occupied_slots.bin').read_bytes();slots=[int.from_bytes(raw[i:i+16],'big') for i in range(0,len(raw),16)]
    assert h==128 and len(slots)==n==100 and sorted(set(slots))==slots
    rows=[]
    for _ in range(m):
        c,count=struct.unpack_from('>II',data,offset);offset+=8
        for _ in range(count):
            l,r,t,flags,pos=struct.unpack_from('>QQHHI',data,offset);offset+=24
            assert 0<=l<=r<n and 0<=t<h
            node=(((1<<h)+slots[l])>>t)^1
            start=((node^1)-(1<<(h-t)))<<t
            assert l==bisect.bisect_left(slots,start) and r==bisect.bisect_left(slots,start+(1<<t))-1
            rows.append({'color':c,'position':pos,'left':l,'right':r,'level':t,'node':node})
    assert offset==len(data);return slots,rows

def rebuild(slots,values,h=128):
    defaults=[H(b'\x02')]
    for _ in range(h):defaults.append(H(b'\x01'+defaults[-1]*2))
    digests={(1<<h)+s:H(b'\x00'+values[s]) for s in slots};level=set(digests)
    for t in range(h):
        parents={v//2 for v in level}
        for p in parents:digests[p]=H(b'\x01'+digests.get(2*p,defaults[t])+digests.get(2*p+1,defaults[t]))
        level=parents
    active={v for v in digests if v>1 and (v^1) in digests}
    return digests,defaults,active

def main():
    global RUN
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,default=RUN);ap.add_argument('--output',type=Path,default=OUT/'independent_raw_audit.json');args=ap.parse_args();RUN=args.runs.resolve()
    snapshot=read(RUN/'snapshot.json');reference=read(RUN/'client_inputs/repeat0.json')
    values={int(t['slot_hex'],16):bytes.fromhex(t['value_hex']) for t in reference['targets']};slots=sorted(values)
    assert all(v==H(b'TIFS-revision-value\x00'+(128).to_bytes(2,'big')+s.to_bytes(16,'big')) for s,v in values.items())
    digests,defaults,active=rebuild(slots,values);assert len(active)==198 and digests[1].hex()==snapshot['root_hex']
    validated_payload=0
    for method in METHODS:
        directory=RUN/'publisher'/method;ss,rows=parse_directory(directory/'layout_metadata.bin');assert ss==slots
        assert {r['node'] for r in rows}==active and len(rows)==198
        manifest=read(directory/'server_manifest.json')
        files={s['color']:(directory/s['database_file']).read_bytes() for s in manifest['subdatabases']}
        if method=='full_cache':files={1:(directory/manifest['cache_file']).read_bytes()}
        for r in rows:
            payload=files[r['color']][32*r['position']:32*(r['position']+1)];assert payload==digests[r['node']];validated_payload+=1
        if method!='full_cache':
            for rank in range(100):
                required=[r for r in rows if r['left']<=rank<=r['right']]
                assert len({r['color'] for r in required})==len(required)
    csvrows=list(csv.DictReader((RUN/'run_summary.csv').open()));assert len(csvrows)==20
    qs_total=records_total=0;rawmeans={};parameters={}
    for rep in range(5):
        inp=read(RUN/f'client_inputs/repeat{rep}.json');targets=inp['targets'];assert len(targets)==100 and len({t['target_index'] for t in targets})==100
        assert {int(t['slot_hex'],16):bytes.fromhex(t['value_hex']) for t in targets}==values
        selected=read(RUN/f'client_inputs/repeat{rep}_selection.json');assert set(selected['method_order'])==set(METHODS)
        assert [t['target_index'] for t in targets]==selected['target_indices']
        for method in METHODS:
            path=RUN/method/f'repeat{rep}';client=read(path/'client_result.json');server=read(path/'server_result.json');queries=client['queries']
            assert len(queries)==100 and client['client_pid']!=server['server_pid'] and client['warmup_queries']==5
            assert [q['target_index'] for q in queries]==selected['target_indices']
            for q,target in zip(queries,targets):
                slot=int(target['slot_hex'],16);proof=defaults[:128].copy()
                expected={t:digests[(((1<<128)+slot)>>t)^1] for t in range(128) if ((((1<<128)+slot)>>t)^1) in active}
                got={r['level']:bytes.fromhex(r['digest_hex']) for r in q['recovered_siblings']};assert len(got)==len(q['recovered_siblings']) and got==expected
                for t,d in got.items():proof[t]=d
                current=H(b'\x00'+values[slot])
                for t,d in enumerate(proof):current=H(b'\x01'+(d+current if slot&(1<<t) else current+d))
                assert current==digests[1] and q['valid_root'] and q['corruption_rejected']
                corrupted=proof.copy();t=min(got);bad=bytearray(corrupted[t]);bad[0]^=1;corrupted[t]=bytes(bad);current=H(b'\x00'+values[slot])
                for t,d in enumerate(corrupted):current=H(b'\x01'+(d+current if slot&(1<<t) else current+d))
                assert current!=digests[1];qs_total+=1;records_total+=len(got)
            expected_batches=0 if method=='full_cache' else 105
            assert server['query_batches_including_warmup']==expected_batches
            assert len({(q['upload_wire_bytes'],q['download_wire_bytes']) for q in queries})==1
            q=queries[0]
            assert server['total_read_wire_bytes']==client['bootstrap_upload_wire_bytes']+expected_batches*q['upload_wire_bytes']
            assert server['total_written_wire_bytes']==client['bootstrap_download_wire_bytes']+expected_batches*q['download_wire_bytes']
            rr=next(r for r in csvrows if r['method']==method and int(r['repeat'])==rep)
            for key,qkey in [('mean_e2e_ms','end_to_end_ms'),('mean_query_ms','query_generation_ms'),('mean_recover_ms','decode_ms'),('mean_route_ms','known_value_decode_and_routing_ms'),('mean_verify_ms','assembly_rootcheck_ms'),('mean_request_response_ms','serialize_transport_answer_ms'),('mean_upload_wire_bytes','upload_wire_bytes'),('mean_download_wire_bytes','download_wire_bytes')]:near(float(rr[key]),statistics.mean(x[qkey] for x in queries))
            st=server['server_answer_ms_including_warmup'][5:];near(float(rr['mean_server_answer_ms']),statistics.mean(st) if st else 0)
            near(float(rr['mean_online_wire_bytes']),q['upload_wire_bytes']+q['download_wire_bytes'])
            rawmeans[method,rep]=statistics.mean(q['end_to_end_ms'] for q in queries)
            if method!='full_cache':
                canon=[(p['Color'],p['Records'],p['Chunks']) for p in server['parameters']]
                if method in parameters:assert parameters[method]==canon
                else:parameters[method]=canon
                hint=A=up=down=0
                for p in server['parameters']:
                    assert len(p['Chunks'])==8
                    for chunk in p['Chunks']:
                        cp,info=chunk['Params'],chunk['Info'];assert (cp['N'],cp['Logq'],cp['Sigma'],cp['P'])==(1024,32,6.4,991)
                        assert info['Num']==p['Records'] and info['Row_length']==32 and info['Squishing']==3
                        hint+=4*cp['L']*cp['N'];A+=4*cp['M']*cp['N']
                        up+=24+4*(math.ceil(cp['M']/info['Squishing'])*info['Squishing']);down+=24+4*cp['L']
                assert hint==server['hint_matrix_bytes'] and A==server['shared_matrix_bytes']
                assert q['upload_wire_bytes']==16+up and q['download_wire_bytes']==16+down
    summary=read(RUN/'summary.json')
    for method in METHODS:
        vals=[rawmeans[method,r] for r in range(5)];g=summary['groups'][method]['mean_e2e_ms'];near(g['mean'],statistics.mean(vals));near(g['sample_sd'],statistics.stdev(vals))
    paired={}
    for baseline in ['first_fit','activebalance']:
        ratios=[rawmeans[baseline,r]/rawmeans['opt_witness22',r] for r in range(5)];diffs=[rawmeans[baseline,r]-rawmeans['opt_witness22',r] for r in range(5)]
        near(summary['paired_e2e_ratios'][baseline+'_over_opt_witness22']['mean'],statistics.mean(ratios))
        delta=2.7764451051977987*statistics.stdev(diffs)/math.sqrt(5)
        paired[baseline]={'paired_E2E_ratio_mean':statistics.mean(ratios),'paired_E2E_difference_ms_mean':statistics.mean(diffs),'paired_difference_95pct_t_interval_ms':[statistics.mean(diffs)-delta,statistics.mean(diffs)+delta]}
    pins=read(RUN/'source_manifest.json')['sha256']
    for p,h in pins.items():assert hashlib.sha256((ROOT/p.replace('\\','/')).read_bytes()).hexdigest()==h
    dependencies=read(RUN/'dependency_source_hashes.json')['sha256'] if (RUN/'dependency_source_hashes.json').exists() else {}
    for p,h in dependencies.items():assert hashlib.sha256((ROOT/p.replace('\\','/')).read_bytes()).hexdigest()==h
    report={'status':'passed','independent_stdlib_tree_root':digests[1].hex(),'original_positional_payload_records_verified':validated_payload,
            'independent_process_pairs':20,'measured_proofs_reconstructed':qs_total,'recovered_sibling_records_verified':records_total,
            'independent_bitflip_rejections':qs_total,'paired_targets_and_five_run_statistics_verified':True,'socket_byte_conservation_verified':True,
            'matrix_parameters_and_wire_padding_verified':True,'source_hashes_verified':len(pins),'paired_E2E_analysis':paired,
            'dependency_source_hashes_verified':len(dependencies),
            'scope':'t intervals describe five paired process means; only one fixed snapshot, no broad inferential application claim.',
            'audit_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
