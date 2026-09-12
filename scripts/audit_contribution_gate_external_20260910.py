"""Independent standard-library audit of frozen TreePIR common-task evidence."""
from pathlib import Path
import csv,hashlib,json,math,random,re,statistics,struct
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'
METHODS=['treepir_official','first_fit','activebalance']
def read(p):return json.loads(p.read_text())
def H(x):return hashlib.sha256(x).digest()
def check(h,slot,value,proof,root):
    current=H(b'\x00'+value)
    for level,sibling in enumerate(proof):current=H(b'\x01'+(sibling+current if slot&(1<<level) else current+sibling))
    assert current==root
    bad=proof.copy();bad[0]=bytes([bad[0][0]^1])+bad[0][1:];current=H(b'\x00'+value)
    for level,sibling in enumerate(bad):current=H(b'\x01'+(sibling+current if slot&(1<<level) else current+sibling))
    assert current!=root
def directory(p,h,n,digests):
    raw=(p/'layout_metadata.bin').read_bytes();assert raw[:8]==b'TIFSMETA'
    hh,nn,k=struct.unpack_from('>HII',raw,8);assert (hh,nn,k)==(h,n,h);offset=18;locations={}
    manifest=read(p/'manifest.json');payloads={s['color']:(p/s['database_file']).read_bytes() for s in manifest['subdatabases']}
    for _ in range(k):
        color,count=struct.unpack_from('>II',raw,offset);offset+=8
        assert len(payloads[color])==32*count
        for _ in range(count):
            left,right,level,flags,pos=struct.unpack_from('>QQHHI',raw,offset);offset+=24
            node=(((1<<h)+left)>>level)^1
            expected_left=((node^1)-(1<<(h-level)))<<level
            assert (left,right)==(expected_left,expected_left+(1<<level)-1)
            assert payloads[color][32*pos:32*(pos+1)]==digests[node]
            assert node not in locations;locations[node]=(color,pos)
    assert offset==len(raw) and set(locations)==set(range(2,2*n))
    return locations
def near(a,b):assert abs(a-b)<=1e-8*max(1,abs(a),abs(b)),(a,b)
def main():
    snapshots={};locations={};layoutchecks=cachechecks=retrievedchecks=received=0
    for h in [4,10]:
        work=OUT/f'complete_h{h}';s=read(work/'snapshot.json');n=1<<h
        values={int(k):bytes.fromhex(v) for k,v in s['values_hex'].items()};assert set(values)==set(range(n))
        digests={n+slot:H(b'\x00'+v) for slot,v in values.items()}
        for node in range(n-1,0,-1):digests[node]=H(b'\x01'+digests[2*node]+digests[2*node+1])
        assert digests[1].hex()==s['root_hex']
        assert {str(k):v.hex() for k,v in digests.items() if k!=1}==s['digest_hex']
        snapshots[h]=(values,digests)
        csa=list(csv.DictReader((work/'official_csa.tsv').open(),delimiter='\t'))
        official={int(r['swapped_node']):(ord(r['color'])-64,int(r['position'])) for r in csa}
        assert len(official)==2*n-2 and set(official)==set(range(2,2*n))
        for r in csv.DictReader((work/'official_index.tsv').open(),delimiter='\t'):
            node=int(r['swapped_node']);assert official[node]==(ord(r['color'])-64,int(r['position']))
            assert node in [(n+int(r['target_slot']))>>level for level in range(h)]
        for method in METHODS:
            loc=directory(work/method,h,n,digests);locations[h,method]=loc
            if method=='treepir_official':assert loc=={node^1:where for node,where in official.items()}
            for target in range(n):
                ids=[((n+target)>>level)^1 for level in range(h)]
                assert len({loc[node][0] for node in ids})==h
                check(h,target,values[target],[digests[node] for node in ids],digests[1]);layoutchecks+=1
        # Complete-tree caching has implicit heap coordinates and needs no interval directory.
        payload=b''.join(digests[node] for node in range(2,2*n));cache=work/'full_cache_digest_payload.bin'
        if cache.exists():assert cache.read_bytes()==payload
        else:cache.write_bytes(payload)
        payload=cache.read_bytes();assert len(payload)==32*(2*n-2)
        for target in range(n):
            ids=[((n+target)>>level)^1 for level in range(h)]
            check(h,target,values[target],[payload[(node-2)*32:(node-1)*32] for node in ids],digests[1]);cachechecks+=1
    runroot=OUT/'common_simplepir';processrows=list(csv.DictReader((runroot/'process_measurements.csv').open()));assert len(processrows)==18
    rawmeans={};parameter_shapes={}
    for h in [4,10]:
        values,digests=snapshots[h];n=1<<h
        for rep in range(3):
            paired=None
            rng=random.Random(20260911000+h*10+rep);expected_targets=rng.sample(range(n),min(n,32));expected_order=METHODS.copy();rng.shuffle(expected_order)
            for method in METHODS:
                run=runroot/f'h{h}'/f'repeat{rep}'/method;selection=read(run/'selection.json');targets=selection['targets']
                assert targets==expected_targets and selection['method_order']==expected_order
                if paired is None:paired=targets
                else:assert paired==targets
                assert len(targets)==min(n,32) and len(set(targets))==len(targets)
                result=read(run/'backend_result.json');assert result['completed_queries']==len(targets) and result['warmup_queries']==5
                assert result['gomaxprocs']==1 if 'gomaxprocs' in result else True
                loc=locations[h,method];expected_hint=expected_A=expected_up=expected_down=0
                shapes=[]
                for p in result['parameters']:
                    assert (p['lwe_dimension_n'],p['ciphertext_modulus_logq'],p['noise_sigma'],p['plaintext_modulus_p'])==(1024,32,6.4,991)
                    L,M=p['matrix_rows_l'],p['matrix_columns_m'];shapes.append((p['records_with_empty_padding'],L,M))
                    expected_hint+=8*4*1024*L;expected_A+=8*4*1024*M
                    expected_up+=8*4*3*math.ceil(M/3);expected_down+=8*4*L
                assert expected_hint==result['setup']['offline_hint_bytes'] and expected_A==result['setup']['public_shared_state_bytes']
                parameter_shapes[h,method]=sorted(shapes)
                for target,q in zip(targets,result['targets']):
                    proof=[None]*h;bycolor={loc[((n+target)>>level)^1][0]:(level,((n+target)>>level)^1) for level in range(h)}
                    for r in q['recovered_records']:
                        level,node=bycolor[r['color']];assert r['query_index']==loc[node][1]
                        value=bytes.fromhex(r['record_hex']);assert value==digests[node];proof[level]=value;received+=1
                    assert all(proof);check(h,target,values[target],proof,digests[1]);retrievedchecks+=1
                    assert (q['online_upload_bytes'],q['online_download_bytes'])==(expected_up,expected_down)
                row=next(r for r in processrows if int(r['height'])==h and int(r['repeat'])==rep and r['method']==method)
                for key in ['client_query_ms','server_answer_ms','client_decode_ms','backend_wall_ms','online_total_bytes']:
                    near(float(row[key]),statistics.mean(q[key] for q in result['targets']))
                rawmeans[h,method,rep]=statistics.mean(q['backend_wall_ms'] for q in result['targets'])
        assert parameter_shapes[h,'treepir_official']==parameter_shapes[h,'activebalance']
    paired_differences={}
    for h in [4,10]:
        differences=[rawmeans[h,'activebalance',rep]-rawmeans[h,'treepir_official',rep] for rep in range(3)]
        delta=4.302652729696142*statistics.stdev(differences)/math.sqrt(3);avg=statistics.mean(differences)
        paired_differences[str(h)]={'AB_minus_official_backend_wall_ms':avg,'95pct_t_df2_interval_ms':[avg-delta,avg+delta],'process_pairs':3,'interpretation':'Descriptive three-pair comparison; interval includes zero and does not establish equivalence.'}
    summary=read(runroot/'summary.json')
    assert hashlib.sha256((ROOT/'scripts/run_contribution_gate_common_backend_20260910.py').read_bytes()).hexdigest()==summary['source_sha256']
    assert hashlib.sha256((ROOT/'examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend').read_bytes()).hexdigest()==summary['binary_sha256']
    for g in summary['groups']:
        a=[rawmeans[g['height'],g['method'],rep] for rep in range(3)]
        near(statistics.mean(a),g['metrics']['backend_wall_ms']['mean']);near(statistics.stdev(a),g['metrics']['backend_wall_ms']['sample_sd'])
    nativeproofs=0;native=OUT/'native_vbpir/authenticated_common_runs'
    for method in ['treepir_official','activebalance']:
        vals,digests=snapshots[10];loc=locations[10,method];record=read(native/method/'process.json');text=(native/method/'stdout.txt').read_text()
        assert record['returncode']==0 and len(record['targets'])==10
        for token in ['8192','[42 + 58 + 58 + 60]','dim_size = 64','dimensions_                   = [ 64 4 ]']:assert token in text
        blocks=re.split(r'Starting example index = (\d+)',text)[1:];assert len(blocks)==20
        for j in range(0,len(blocks),2):
            target=int(blocks[j])-1;assert target==record['targets'][j//2]
            raw=re.findall(r'Hexadecimal string: 0x([0-9a-fA-F]{64})',blocks[j+1].split('Contents of decode_responses:',1)[1]);assert len(raw)==10
            bycolor={loc[((1024+target)>>level)^1][0]:level for level in range(10)};proof=[None]*10
            for c,d in enumerate(raw,1):proof[bycolor[c]]=bytes.fromhex(d)
            check(10,target,vals[target],proof,digests[1]);nativeproofs+=1
    official=read(OUT/'official_source_manifest.json')
    for name,info in official['files'].items():assert hashlib.sha256((OUT/'official_sources'/name).read_bytes()).hexdigest()==info['sha256']
    nativepins=read(OUT/'native_vbpir/source_derivation.json')
    for p,hsh in nativepins['adapted_source_sha256'].items():assert hashlib.sha256((OUT/'native_vbpir/source'/p).read_bytes()).hexdigest()==hsh
    result={'status':'passed','official_commit':official['commit'],'all_target_layout_proofs':layoutchecks,'all_target_full_cache_proofs':cachechecks,
            'simplepir_recovered_proofs':retrievedchecks,'simplepir_actual_sibling_records':received,'vbpir_recovered_proofs':nativeproofs,
            'bitflip_rejections':'every reconstructed proof','paired_simplepir_target_sets':True,'matrix_byte_accounting_and_identical_AB_TreePIR_shapes':True,
            'seeded_target_and_randomized_method_orders_independently_replayed':True,'paired_timing_differences':paired_differences,
            'official_source_files_hashed':len(official['files']),'native_source_files_hashed':len(nativepins['adapted_source_sha256']),
            'full_native_TCP_service_gate':'not completed; this audit does not convert backend components into a native service experiment',
            'audit_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'independent_raw_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
