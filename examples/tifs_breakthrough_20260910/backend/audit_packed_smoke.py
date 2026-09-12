"""Independent byte/record checks for the bounded long-record Go smoke.
Standard library only. No backend launch, timing, or data mutation.
"""
from pathlib import Path
import csv, hashlib, json, math, struct, subprocess

ROOT = Path(__file__).absolute().parents[3]
OUT = Path(__file__).absolute().parent
PUB = ROOT/'examples/tifs_revision_20260910/ct_application/runs_verified_evidence/publisher'
RAW = ROOT/'examples/tifs_revision_20260910/ct_application/runs_verified_evidence'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf8'))
data=load(OUT/'packed_smoke.json')
assert len(data['summaries'])==15
assert len(data['synthetic_boundary_checks'])==10
secrets,queries,seeds=set(),set(),set()
record_checks=0
summary=[]
for result in data['summaries']:
    method=result['method']; manifest=load(PUB/method/'server_manifest.json')
    sources={s['color']:PUB/method/s['database_file'] for s in manifest['subdatabases']}
    assert len(result['colors'])==result['logical_queries']==len(sources)
    for color in result['colors']:
        raw=sources[color['color']].read_bytes()
        assert hashlib.sha256(raw).hexdigest()==color['input_sha256']
        color['_source_raw']=raw
    row={k:v for k,v in result.items() if k not in ('colors','bootstrap_header_sha256')}
    if result['variant']=='eight32_square_expanded':
        old=load(RAW/method/'repeat0/client_result.json')
        assert result['encoded_bootstrap_bytes']==old['bootstrap_upload_wire_bytes']+old['bootstrap_download_wire_bytes']
        assert result['encoded_online_bytes_per_proof']==old['queries'][0]['upload_wire_bytes']+old['queries'][0]['download_wire_bytes']
    assert result['hint_matrix_bytes']==sum(c['hint_matrix_bytes'] for c in result['colors'])
    assert result['expanded_A_matrix_bytes']==sum(c['expanded_A_matrix_bytes'] for c in result['colors'])
    assert result['online_matrix_bytes_per_proof']==sum(c['query_matrix_bytes']+c['answer_matrix_bytes'] for c in result['colors'])
    assert result['encoded_online_bytes_per_proof']==result['online_matrix_bytes_per_proof']+32+48*result['PIR_calls_per_proof']
    summary.append(row)

for color in data['synthetic_boundary_checks']:
    n=color['records'];raw=bytearray(32*n)
    for i in range(1,n): raw[32*i:32*(i+1)]=hashlib.sha256(f'synthetic-{i}'.encode()).digest()
    raw[-32:]=bytes([255])*32
    color['_source_raw']=bytes(raw)

allcolors=[c for r in data['summaries'] for c in r['colors']]+data['synthetic_boundary_checks']
for c in allcolors:
    p,i=c['params'],c['db_info'];parts=c['scalar_queries_per_record'];bits=i['Row_length']
    assert p['N']==1024 and p['M']<=8192 and p['P']==991 and p['Logq']==32 and p['Sigma']==6.4
    ne=0
    while 991**ne < 2**bits: ne+=1
    assert i['Ne']==ne and (ne==26 if bits==256 else ne==4)
    assert p['L']%ne==0 and p['L']*p['M']>=c['records']*ne
    assert i['Basis']==10 and i['Squishing']==3 and p['P']<=2**10 and p['Logq']>=30
    assert c['hint_matrix_bytes']==parts*p['L']*1024*4
    assert c['expanded_A_matrix_bytes']==parts*p['M']*1024*4
    assert c['query_matrix_bytes']==parts*4*(3*math.ceil(p['M']/3))
    assert c['answer_matrix_bytes']==parts*4*p['L']
    assert c['query_encoded_matrices_bytes']==c['query_matrix_bytes']+24*parts
    assert c['answer_encoded_matrices_bytes']==c['answer_matrix_bytes']+24*parts
    assert c['shared_A_sha256']==c['client_A_sha256']
    assert c['all_sampled_secret_states_distinct'] and c['repeated_query_fingerprints_distinct']
    for seed in c.get('public_seed_hex',[]):
        assert len(bytes.fromhex(seed))==16 and seed not in seeds
        seeds.add(seed)
    for s in c['samples']:
        expected=c['_source_raw'][32*s['index']:32*(s['index']+1)]
        assert len(expected)==32 and s['valid']
        assert bytes.fromhex(s['expected_hex'])==bytes.fromhex(s['recovered_hex'])==expected
        assert s['query_fingerprint'] not in queries
        queries.add(s['query_fingerprint'])
        for secret in s['secret_state_fingerprints']:
            assert secret not in secrets
            secrets.add(secret)
        record_checks+=1
assert record_checks==1125
assert sum(r['checked_records'] for r in data['summaries'])==1075
# The first/last rank needs only the first/last record in each proper-color or
# depth bucket. Those records are already retained by the Go boundary smoke.
# Reassemble these two complete proofs per method/policy from actual returned
# bytes, without new PIR calls or using server digests as proof contents.
source_csv=ROOT/'examples/tifs_revision_20260910/ct_application/source/ct_records.csv'
with source_csv.open(encoding='utf8',newline='') as f:
    values={int(r['slot_hex'],16):bytes.fromhex(r['value_hex']) for r in csv.DictReader(f)}
expected_root=bytes.fromhex(load(PUB/'snapshot.json')['trusted_experimental_root_hex'])
def parent(left,right): return hashlib.sha256(b'\x01'+left+right).digest()
defaults=[hashlib.sha256(b'\x02').digest()]
for _ in range(128): defaults.append(parent(defaults[-1],defaults[-1]))
proof_checks=0
for result in data['summaries']:
    public=PUB/result['method'];raw=(public/'layout_metadata.bin').read_bytes();packed=(public/'occupied_slots.bin').read_bytes()
    slots=[int.from_bytes(packed[i:i+16],'big') for i in range(0,len(packed),16)]
    h,n,nc=struct.unpack_from('>HII',raw,8);assert h==128 and n==512
    decoded={(c['color'],s['index']):bytes.fromhex(s['recovered_hex']) for c in result['colors'] for s in c['samples']}
    entries=[];offset=18
    for _ in range(nc):
        color,count=struct.unpack_from('>II',raw,offset);offset+=8
        for _ in range(count):
            left,right,level,flags,pos=struct.unpack_from('>QQHHI',raw,offset);offset+=24
            entries.append((color,left,right,level,pos))
    for rank in (0,n-1):
        proof=defaults[:128];seen_levels=set()
        for color,left,right,level,pos in entries:
            if left<=rank<=right:
                assert (color,pos) in decoded and level not in seen_levels
                proof[level]=decoded[color,pos];seen_levels.add(level)
        slot=slots[rank];current=hashlib.sha256(b'\x00'+values[slot]).digest()
        for level,sibling in enumerate(proof):
            current=parent(sibling,current) if (slot>>level)&1 else parent(current,sibling)
        assert current==expected_root
        proof_checks+=1
assert proof_checks==30
with (OUT/'packed_costs.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
paths=[ROOT/'backend/simplepir/tifs_packed_exploration_20260910.go',OUT/'packed_exploration',OUT/'packed_smoke.json',Path(__file__),ROOT/'backend/simplepir/tifs_full_proof_backend.go',ROOT/'backend/simplepir/tifs_tcp_certificate_backend.go',ROOT/'.tools/simplepir/simplepir-main/pir/simple_pir.go',ROOT/'.tools/simplepir/simplepir-main/pir/database.go',ROOT/'.tools/simplepir/simplepir-main/pir/params.csv',ROOT/'.tools/simplepir/simplepir-main/pir/rand.go']
result={'status':'pass','real_record_checks':1075,'synthetic_boundary_record_checks':50,'complete_boundary_SMT_proofs_from_recovered_bytes':proof_checks,
 'total_record_checks':record_checks,'distinct_private_state_hashes':len(secrets),'distinct_complete_query_hashes':len(queries),'distinct_public_seeds':len(seeds),
 'checks':{'source_file_bytes_match_every_recovered_record':True,'parameters_match_pinned_security_table':True,'database_capacity_and_base_p_digits_exact':True,'byte_formulas_match_actual_matrix_and_encoder_sizes':True,'baseline_encoder_matches_frozen_TCP_bytes_for_all_three_methods':True,'independent_server_client_public_seed_expansions_match':True,'query_and_secret_state_hashes_distinct':True,'complete_min_max_target_SMT_proofs_reconstructed_from_logged_recovered_bytes':True},
 'scope':'Independent read-only audit of local functional Go smoke plus 30 offline SMT-root checks from logged recovered boundary records; no TCP experiment and no publishable runtime comparison.',
 'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
 'upstream_commit':subprocess.check_output(['git','-C',str(ROOT/'.tools/simplepir/simplepir-main'),'rev-parse','HEAD'],text=True).strip(),
 'cost_rows':summary}
(OUT/'packed_smoke_audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:result[k] for k in ['status','real_record_checks','synthetic_boundary_record_checks','complete_boundary_SMT_proofs_from_recovered_bytes','distinct_private_state_hashes','distinct_complete_query_hashes','distinct_public_seeds']},indent=2))
