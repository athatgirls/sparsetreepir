"""Deterministic cost analysis, not a timing or network experiment.

Reproduce the pinned SimplePIR matrix dimensions, check eight-chunk costs
against the frozen runs, and enumerate rectangular long-record dimensions.
All methods receive the same dimension-selection policy. No measured file is
modified and no analytical number is presented as a measured network result.
"""
from pathlib import Path
import csv, hashlib, json, math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'examples/tifs_breakthrough_20260910/cost_frontier'
OLD = ROOT / 'examples/tifs_revision_20260910/verified_backend'
CT = ROOT / 'examples/tifs_revision_20260910/ct_application/runs_verified_evidence'
PARAM = ROOT / '.tools/simplepir/simplepir-main/pir/params.csv'
METHODS = ['first_fit', 'activebalance', 'nonempty_depth']

def readj(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ceildiv(x, y): return (x+y-1)//y
TABLE = list(csv.DictReader(PARAM.open(encoding='utf8')))

def plain_modulus(columns):
    for r in TABLE:
        if int(r['log(n)']) == 10 and int(r['log(q)']) == 32 and columns <= 2**int(r['log(m)']):
            return int(r['p_simple'])
    raise ValueError('No pinned security-table parameters')

def digits(bits, p):
    # Matches upstream, with an independent integer coverage check.
    d = math.ceil(bits/math.log2(p))
    assert p**d >= 2**bits and p**(d-1) < 2**bits
    return d

def square(n, bits):
    good = None
    for candidate_p in range(2, 10000):
        ne = digits(bits, candidate_p)
        l = ceildiv(math.isqrt(n*ne), ne)*ne
        m = ceildiv(n*ne, l)
        p = plain_modulus(m)
        if p < candidate_p:
            assert good is not None
            return good
        good = {'L':l, 'M':m, 'P':p, 'Ne':digits(bits, p)}
    raise AssertionError('parameter search did not terminate')

def rectangular(n, record_rows):
    m = ceildiv(n, record_rows)
    p = plain_modulus(m)
    ne = digits(256, p)
    return {'L':ne*record_rows, 'M':m, 'P':p, 'Ne':ne}

def cost(p, copies=1):
    return {'hint_bytes':copies*4096*p['L'],
            'expanded_A_bytes':copies*4096*p['M'],
            'seed_bytes':copies*16,
            'upload_matrix_bytes':copies*4*ceildiv(p['M'], 3)*3,
            'download_matrix_bytes':copies*4*p['L']}

def aggregate(ps, copies=1):
    cs = [cost(p, copies) for p in ps]
    result = {k:sum(c[k] for c in cs) for k in cs[0]}
    result['online_matrix_bytes'] = result['upload_matrix_bytes']+result['download_matrix_bytes']
    return result

def csvwrite(p, rows):
    with p.open('w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = list(csv.DictReader((OLD/'run_summary.csv').open(encoding='utf8')))
    manifests = []
    for folder in sorted(OLD.glob('*_h128')):
        setup = readj(folder/'layout_setup.json')
        for method in METHODS:
            p = folder/method/'repeat0/manifest.json'
            manifests.append((setup['dataset'], method, p, setup['n'], setup['N']))
    ctsnapshot = readj(CT/'publisher/snapshot.json')
    for method in METHODS:
        manifests.append(('CT 512', method, CT/'publisher'/method/'server_manifest.json', ctsnapshot['n'], ctsnapshot['N']))
    rows, validations, sources = [], [], []
    for dataset, method, manifest, n, N in manifests:
        loads = [d['records'] for d in readj(manifest)['subdatabases']]
        assert sum(loads)==N
        meta = 24*N + 18 + 8*len(loads) + 16*n
        cache = 56*N + 26 + 16*n
        ps32 = [square(x,32) for x in loads]
        baseline = aggregate(ps32, 8)
        if dataset != 'CT 512':
            previous = [r for r in frozen if r['dataset']==dataset and r['method']==method]
            assert len(previous)==5
            for r in previous:
                assert baseline['hint_bytes']==int(r['offline_hint_bytes'])
                assert baseline['expanded_A_bytes']==int(r['public_shared_state_bytes'])
                assert baseline['online_matrix_bytes']==int(float(r['online_bytes']))
                assert meta==int(r['client_metadata_bytes']) and cache==int(r['full_cache_bootstrap_bytes'])
            validations.append({'dataset':dataset,'method':method,'checked_frozen_process_rows':5,'all_exact':True})
        sources.append({'path':str(manifest.relative_to(ROOT)),'sha256':sha(manifest)})
        policies = [('eight_chunks_square',ps32,8), ('long_record_square',[square(x,256) for x in loads],1), ('long_record_one_record_row',[rectangular(x,1) for x in loads],1)]
        for policy, ps, copies in policies:
            c=aggregate(ps,copies)
            seeded=meta+c['hint_bytes']+c['seed_bytes']
            rows.append({'dataset':dataset,'method':method,'policy':policy,'N':N,'colors':len(loads),'max_bucket':max(loads),
                         'directory_and_slots_bytes':meta,'full_cache_package_bytes':cache,**c,
                         'seeded_core_bootstrap_bytes':seeded,
                         'cache_dominates_bytes_for_all_Q_ge_0':seeded>=cache,
                         'break_even_Q_excluding_framing':max(0,(cache-seeded)/c['online_matrix_bytes'])})
        # Exact minimization of the stated matrix-only total-byte objective,
        # separately for each bucket; all possible meaningful record rows.
        for q in [1,10,100,1000,10000]:
            best=[]
            for x in loads:
                choices=[rectangular(x,r) for r in range(1,x+1)]
                def score(p):
                    c=cost(p)
                    return (c['hint_bytes']+c['seed_bytes']+q*(c['upload_matrix_bytes']+c['download_matrix_bytes']),p['L'],p['M'])
                best.append(min(choices,key=score))
            c=aggregate(best)
            seeded=meta+c['hint_bytes']+c['seed_bytes']
            rows.append({'dataset':dataset,'method':method,'policy':f'long_record_min_total_Q{q}','N':N,'colors':len(loads),'max_bucket':max(loads),
                         'directory_and_slots_bytes':meta,'full_cache_package_bytes':cache,**c,
                         'seeded_core_bootstrap_bytes':seeded,
                         'cache_dominates_bytes_for_all_Q_ge_0':seeded>=cache,
                         'break_even_Q_excluding_framing':max(0,(cache-seeded)/c['online_matrix_bytes'])})
    csvwrite(OUT/'cost_frontier.csv',rows)
    horizon=[]
    groups=readj(CT/'summary.json')['groups']
    for q in [0,1,10,100,1000,10000]:
        for method, g in groups.items():
            init=g['bootstrap_total_wire_bytes']['mean']; online=g['mean_online_wire_bytes']['mean']
            horizon.append({'method':method,'queries_in_one_unchanged_snapshot':q,'measured_bootstrap_bytes':init,
                            'measured_online_bytes_per_query':online,'projected_total_application_wire_bytes':init+q*online})
    csvwrite(OUT/'frozen_tcp_query_horizon.csv',horizon)
    certificate={'schema':1,'scope':'Analytical matrix-byte counts; no new timing/network samples. Public-A seed variant assumes correct independent PRG streams and excludes all framing/parameter serialization. The frozen TCP horizon uses measured byte counts, extrapolated without further execution.',
        'security_table_sha256':sha(PARAM),'sources':sources,'frozen_validation':validations,
        'minimum_long_record_hint_bytes_per_nonempty_bucket':26*4096,
        'minimum_hint_proof':'For the full uncompressed native hint matrix: pinned security table has p<=991; a 256-bit record needs >=26 field elements. Each nonempty bucket needs L>=26. Its L x 1024 32-bit hint therefore occupies >=106496 bytes, regardless of rectangular dimensions. This is not a lower bound for compressed hints, shared-hint batching or other PIR schemes.',
        'dominance_rule':'With a fixed snapshot, totalBytes(Q)=bootstrap+Q*online. If bootstrap>=fullCache and online>0, increasing Q cannot produce a bandwidth break-even. This is not a claim about other PIR protocols or dynamic authenticated updates.',
        'all_seven_three_method_minimum_hints_exceed_cache_payload':all(26*4096*r['colors']>32*r['N'] for r in rows),
        'rows':len(rows),'measured_process_rows_reproduced':sum(r['checked_frozen_process_rows'] for r in validations),
        'script_sha256':sha(Path(__file__))}
    (OUT/'validation.json').write_text(json.dumps(certificate,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:certificate[k] for k in ['rows','measured_process_rows_reproduced','all_seven_three_method_minimum_hints_exceed_cache_payload']},indent=2))

if __name__=='__main__':main()
