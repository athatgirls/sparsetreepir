"""Authenticate all native SimplePIR outputs against frozen SMT inputs, then summarize.

This auditor never executes the backend. Missing/failed/unverified planned runs cannot
produce a formal 'passed' status. The independent sampling unit is a process mean.
"""
from pathlib import Path
import argparse
import bisect
import collections
import csv
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_simplepir_extension_20260911'
VBPIR = ROOT / 'examples/tifs_external_extension_20260911'
CASES = ['uniform_n1000', 'uniform_n10000', 'uniform_n100000', 'prefix64_n10000',
         'cluster90_n10000', 'complete_h10', 'complete_h14']
METHODS = ['ab', 'pbc', 'flat', 'first_fit']
COMMIT = 'e9020b03bf2872c75b8954e749e32408b5db87ed'
T95_DF2 = 4.302652729911275
METRICS = ['serialized_proof_wall_ms', 'route_ms', 'query_ms', 'query_roundtrip_ms',
           'answer_ms', 'answer_roundtrip_ms', 'decode_ms', 'proof_verify_ms',
           'query_matrix_payload_bytes', 'query_framed_bytes',
           'answer_matrix_payload_bytes', 'answer_framed_bytes', 'online_framed_bytes']
COMMON = ['height', 'records', 'root_hex', 'default_hashes', 'occupied_slots_hex',
          'record_heap_ids_hex', 'record_intervals']
TARGET_COMMON = ['id', 'slot_hex', 'value_hex', 'needed']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def table(path, rows, default_fields):
    fields = list(dict.fromkeys(k for row in rows for k in row)) if rows else default_fields
    with path.open('w', newline='', encoding='utf8') as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def root_hash(value, slot, proof):
    node = hashlib.sha256(b'\0' + value).digest()
    for level, sibling in enumerate(proof):
        pair = sibling + node if (slot >> level) & 1 else node + sibling
        node = hashlib.sha256(b'\x01' + pair).digest()
    return node


def normhex(text, size=None):
    text = text.removeprefix('0x')
    raw = bytes.fromhex(('0' if len(text) % 2 else '') + text)
    if size is not None:
        require(len(raw) <= size, 'hex field too wide')
        raw = raw.rjust(size, b'\0')
    return raw


def json_size(obj):
    # All fields used here are ASCII integer/hex/public metadata, without HTML.
    # The ordered objects below reproduce Go's struct order, not map order.
    return len(json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode())


def triple_key(item):
    return item['case'], item['method'], item['repeat']


def mean_sd(values):
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else None


class SourceAudit:
    def __init__(self, input_root, vbpir_root):
        self.input_root, self.vbpir = input_root, vbpir_root
        self.cache = {}
        self.source_schedule = read(vbpir_root / 'runs/schedule.json')
        self.schedule = {}
        for row in self.source_schedule:
            key = row['case'], row['repeat']
            selected = {k: row[k] for k in ['pool_indices', 'target_ids']}
            require(key not in self.schedule or self.schedule[key] == selected,
                    'original VBPIR methods did not share targets')
            self.schedule[key] = selected
        frozen = read(input_root / 'target_schedule.json')
        require(len(frozen) == len(self.schedule), 'target-schedule length differs from frozen VBPIR')
        for row in frozen:
            require({k: row[k] for k in ['pool_indices', 'target_ids']} == self.schedule[row['case'], row['repeat']],
                    'copied target schedule differs from original VBPIR')

    def get(self, case, method):
        key = case, method
        if key in self.cache:
            return self.cache[key]
        path = self.input_root / case / f'{method}.json'
        inp = read(path)
        audit = read(path.parent / 'cross_backend_audit.json')
        require(audit['status'] == 'pass', 'input-producer audit incomplete')
        require(sha(path) == audit['outputs'][path.name]['sha256'], 'frozen SimplePIR input hash changed')
        old_path = self.vbpir / 'inputs' / case / 'ab.json'
        old = read(old_path)
        summary = read(old_path.parent / 'snapshot_summary.json')
        require(sha(old_path) == summary['outputs']['ab.json']['sha256'] == inp['source_vbpir_input_sha256'],
                'original VBPIR snapshot hash changed')
        for field in COMMON:
            require(inp[field] == old[field], f'cross-backend snapshot differs: {field}')
        require(inp['pir'] == {'batch_size': old['pir']['batch_size']}, 'public batch width differs')
        require([{k: t[k] for k in TARGET_COMMON} for t in inp['targets']] ==
                [{k: t[k] for k in TARGET_COMMON} for t in old['targets']], 'target pool differs')
        require(inp['mode'] == method and inp['backend'] == 'simplepir', 'wrong backend/method input')
        policy = inp['simplepir']
        require(policy['record_bytes'] == 32 and policy['record_bits'] == 256 and policy['parts'] == 1,
                'input is not native 256-bit / 32-byte')
        require(policy['secret_dimension'] == 1024 and policy['logq'] == 32 and policy['public_A'] == 'expanded',
                'input security/public-A policy differs')
        require(policy['flat_shared_hint_and_public_A'] == (method == 'flat'), 'flat state policy differs')
        count, height = len(inp['records']), inp['height']
        raw = [bytes.fromhex(x) for x in inp['records']]
        require(all(len(x) == 32 for x in raw), 'record is not 32 bytes')
        slots = [int(x, 16) for x in inp['occupied_slots_hex']]
        require(slots == sorted(set(slots)) and all(0 <= x < (1 << height) for x in slots), 'invalid occupied coordinates')
        heap = {int(h, 16): i for i, h in enumerate(inp['record_heap_ids_hex'])}
        require(len(heap) == count, 'duplicate/missing original heap identifiers')
        require(len(inp['record_intervals']) == count, 'incomplete public intervals')
        # Derive each record's query-support interval from its ORIGINAL sibling
        # subtree, independently of the interval-forest/layout producer.
        for node, record in heap.items():
            depth = node.bit_length() - 1
            require(1 <= depth <= height, 'record heap coordinate outside original tree')
            level = height - depth
            sibling = node ^ 1
            start = (sibling - (1 << depth)) << level
            left = bisect.bisect_left(slots, start)
            right = bisect.bisect_left(slots, start + (1 << level)) - 1
            require(left <= right, 'record has empty query support')
            require(inp['record_intervals'][record] == dict(left=left, right=right, level=level, record=record),
                    'public interval/level does not equal original sibling support')
        buckets, m = inp['buckets'], inp['pir']['batch_size']
        copies = collections.Counter(record for bucket in buckets for record in bucket)
        require(copies == collections.Counter({i: 3 if method == 'pbc' else 1 for i in range(count)}),
                'missing/extra/duplicated record placement')
        for bucket, iv in zip(buckets, inp['bucket_intervals']):
            require(len(bucket) == len(set(bucket)), 'duplicate record inside bucket')
            require(iv == [inp['record_intervals'][r] for r in bucket], 'bucket positions/intervals differ')
            if method in ['ab', 'first_fit']:
                iv = sorted(iv, key=lambda x: x['left'])
                require(all(a['right'] < b['left'] for a, b in zip(iv, iv[1:])), 'proof conflicts within bucket')
        require(len(inp['bucket_intervals']) == len(buckets), 'bucket metadata missing')
        if method == 'ab':
            require(buckets == old['buckets'] and len(buckets) == m, 'AB layout differs from frozen experiment')
        elif method == 'flat':
            require(buckets == [list(range(count))], 'Flat is not one full active-record database')
        elif method == 'first_fit':
            require(len(buckets) == m, 'frozen First-fit width differs')
        else:
            require(len(buckets) == (3*m+1)//2, 'PBC bucket count differs')
            candidates = []
            candidate_path = path.parent / 'official_pbc_candidates.tsv'
            require(sha(candidate_path) == audit['official_candidates_sha256'], 'official placement export changed')
            reconstructed = [[] for _ in buckets]
            for line in candidate_path.read_text().splitlines():
                record, *bs = map(int, line.split('\t'))
                require(record == len(candidates) and len(bs) == len(set(bs)) == 3, 'bad PBC candidate export')
                candidates.append(bs)
                for b in bs:
                    require(0 <= b < len(buckets), 'invalid PBC candidate bucket')
                    reconstructed[b].append(record)
            require(candidates == inp['hash_candidates'] and reconstructed == buckets, 'PBC differs from official placement')
        calls = m if method == 'flat' else len(buckets)
        require(inp['logical_queries_per_proof'] == calls and inp['physical_database_instances'] == len(buckets),
                'logical/physical count metadata differs')
        # Match placement against actual frozen native results, not only exporter labels.
        if method in ['ab', 'pbc']:
            for rep in range(3):
                old_result_path = self.vbpir / f'runs/{case}/{method}/repeat{rep}/result.json'
                old_result = read(old_result_path)
                old_status = read(old_result_path.parent / 'status.json')
                require(sha(old_result_path) == old_status['result_sha256'], 'frozen VBPIR result hash changed')
                require(old_result['parameters']['bucket_loads'] == list(map(len, buckets)), 'cross-backend bucket loads differ')
                require([str(x) for x in self.schedule[case, rep]['target_ids']] ==
                        [q['target_id'] for q in old_result['queries']], 'frozen VBPIR target schedule mismatch')
                for query in old_result['warmups'] + old_result['queries']:
                    for item in query['recovered_by_bucket']:
                        if item['record'] == 2**64-1:
                            require(not item['real'] and method == 'pbc', 'invalid native dummy sentinel')
                        else:
                            require(buckets[item['bucket']][item['position']] == item['record'],
                                    'actual frozen native bucket position differs')
                            require(inp['records'][item['record']] == item['record_hex'], 'frozen native recovered digest differs')
        result = dict(input=inp, source_hash=sha(path), raw=raw, slots=slots, heap=heap,
                      common_hash=digest({k: inp[k] for k in COMMON}),
                      original_vbpir_hash=sha(old_path), calls=calls)
        self.cache[key] = result
        return result


def validate_setup(inp, res):
    parameters, setup = res['parameters'], res['setup']
    buckets, count, mode = inp['buckets'], len(inp['records']), inp['mode']
    loads = list(map(len, buckets))
    capacity, instances = max(loads), len(buckets)
    calls = inp['pir']['batch_size'] if mode == 'flat' else instances
    require(parameters['mode'] == mode and parameters['height'] == inp['height'], 'output method/height differs')
    require(parameters['records'] == count and parameters['record_bytes'] == 32, 'output record count/width differs')
    require(parameters['batch_size_m'] == inp['pir']['batch_size'], 'output batch width differs')
    require(parameters['bucket_count'] == instances and parameters['bucket_loads'] == loads, 'output bucket placement differs')
    require(parameters['max_bucket_records'] == capacity and parameters['PIR_calls_per_proof'] == calls, 'capacity/call count differs')
    require(parameters['source_commit'] == COMMIT and parameters['gomaxprocs'] == 1, 'backend pin/thread policy differs')
    require(parameters['experiment_seed'] == inp['seed'], 'routing seed differs')
    p = parameters['params']
    require(p['N'] == 1024 and p['Logq'] == 32 and p['P'] == 991 and p['Sigma'] == 6.4,
            'outside frozen official security parameter row')
    ne = 1
    while 991**ne < 2**256:
        ne += 1
    require(ne == 26 and parameters['base_p_digits_per_record'] == ne, 'long-record digit count wrong')
    # For this frozen params.csv first row, PickParams reaches mod_p=991 and
    # computes these dimensions before stopping at mod_p=992.
    rows = math.isqrt(capacity * ne)
    rows = ((rows + ne - 1)//ne)*ne
    cols = (capacity * ne + rows - 1)//rows
    require(p['L'] == rows and p['M'] == cols and cols <= 8192, 'not official PickParams(max bucket,256,1024,32)')
    rounded = rows//ne*cols
    require(parameters['pir_dimensions'] == [rows, cols], 'reported matrix dimensions differ')
    require(parameters['squished_dimensions'] == [rows, (cols+2)//3], 'reported squished dimensions differ')
    require(parameters['rounded_entries_per_bucket'] == rounded, 'rounded record capacity differs')
    require(setup['initialized_databases'] == instances, 'incorrect physical DB/state instance count')
    metrics = setup['bucket_metrics']
    require(len(metrics) == instances and [x['bucket'] for x in metrics] == list(range(instances)), 'missing/duplicate setup state')
    A, H = 4*cols*1024, 4*rows*1024
    infosizes = 0
    for b, bm in enumerate(metrics):
        require(bm['records'] == loads[b] and bm['initialized_records'] == max(1, loads[b]), 'empty/real DB count differs')
        require(bm['params'] == p, 'bucket-specific parameter policy differs')
        info = dict(Num=max(1, loads[b]), Row_length=256, Packing=0, Ne=ne, X=ne,
                    P=991, Logq=32, Basis=10, Squishing=3, Cols=cols)
        require(bm['db_info'] == info, 'DBinfo does not describe native32B')
        info_size = json_size(info)
        require(bm['db_info_json_bytes'] == info_size, 'DBinfo serialized size differs')
        infosizes += info_size
        for key, expected in [('public_A_matrix_bytes', A), ('public_A_framed_bytes', A+32),
                              ('hint_matrix_bytes', H), ('hint_framed_bytes', H+32),
                              ('encoded_db_bytes', 4*rows*((cols+2)//3)),
                              ('unsquished_db_matrix_bytes', 4*rows*cols), ('rounded_record_capacity', rounded)]:
            require(bm[key] == expected, f'bucket {b}: {key} differs')
    height = inp['height']
    public = dict(mode=mode, height=height, root_hex=inp['root_hex'], default_hashes=inp['default_hashes'],
                  occupied_slots_hex=[normhex(s, (height+7)//8).hex() for s in inp['occupied_slots_hex']],
                  record_intervals=inp['record_intervals'], buckets=buckets)
    if inp['hash_candidates']:
        public['hash_candidates'] = inp['hash_candidates']
    public['batch_size'] = inp['pir']['batch_size']
    metadata = json_size(public)
    common_metadata = {key: value for key, value in public.items()
                       if key not in ['mode', 'buckets', 'hash_candidates']}
    # A concrete shared-directory cache reference, not a minimal cache bound.
    common_bytes = json_size(common_metadata)
    expected = {'public_metadata_serialized_bytes': metadata, 'db_info_serialized_bytes': infosizes,
                'public_A_matrix_bytes': instances*A, 'public_A_framed_bytes': instances*(A+32),
                'hint_matrix_bytes': instances*H, 'hint_framed_bytes': instances*(H+32),
                'bootstrap_payload_bytes': instances*(A+H)+metadata+infosizes,
                'bootstrap_framed_components_bytes': instances*(A+H+64)+metadata+infosizes,
                'setup_server_to_client_serialized_components_bytes': instances*(A+H+64)+metadata+infosizes,
                'setup_client_to_server_bytes': 0, 'active_digest_payload_bytes': count*32,
                'replicated_record_payload_bytes': sum(loads)*32,
                'max_padded_bucket_payload_bytes': instances*capacity*32,
                'backend_rounded_raw_payload_bytes': instances*rounded*32,
                'unsquished_db_matrix_bytes': instances*4*rows*cols,
                'encoded_db_bytes': instances*4*rows*((cols+2)//3)}
    for key, value in expected.items():
        require(setup[key] == value, f'setup {key} differs: {setup[key]} != {value}')
    for key, value in setup.items():
        if isinstance(value, (int, float)):
            require(math.isfinite(value) and value >= 0, f'invalid setup metric {key}')
    require(setup['combined_peak_rss_final_bytes'] >= setup['combined_peak_rss_after_setup_bytes'], 'peak RSS decreased')
    return calls, rows, cols, common_bytes


def validate_process(outcome, scheduled, config, runs, sources, partial=False):
    case, method, rep = triple_key(outcome)
    source = sources.get(case, method)
    frozen = source['input']
    for field in ['case', 'method', 'repeat', 'target_ids', 'pool_indices', 'input_sha256']:
        require(outcome[field] == scheduled[field], f'outcome/schedule differs: {field}')
    require(outcome['binary_sha256'] == config['binary_sha256'], 'binary hash differs')
    require(outcome['input_source_sha256'] == outcome['input_sha256'] == source['source_hash'], 'input provenance differs')
    if not partial:
        require(outcome['returncode'] == 0 and outcome['timeout'] is False, 'complete process failed/timed out')
    else:
        require(outcome['status'] == 'failed' and (outcome['returncode'] != 0 or outcome['timeout']), 'not an observed backend failure')
    selected = sources.schedule[case, rep]
    for field in ['pool_indices', 'target_ids']:
        require(scheduled[field] == selected[field][:config['samples']], 'targets differ from frozen VBPIR pairing')
    directory = runs / case / method / f'repeat{rep}'
    require(read(directory / 'status.json') == outcome, 'outcome does not match persisted status')
    inp, res = read(directory / 'input.json'), read(directory / 'result.json')
    require(sha(directory/'input.json') == outcome['run_input_sha256'] == res['input_sha256'], 'run input hash differs')
    require(sha(directory/'result.json') == outcome['result_sha256'], 'result hash differs')
    expected_input = dict(frozen)
    expected_input['targets'] = [frozen['targets'][i] for i in scheduled['pool_indices']]
    expected_input['seed'] = config['query_routing_seed_base'] + 1009*rep
    require(inp == expected_input, 'run input changed beyond scheduled selection/routing seed')
    command = read(directory/'command.json')
    require(command['argv'][-1] == str(config['warmup']), 'invoked warmup differs')
    require(all(command['environment_overrides'][k] == '1' for k in
                ['GOMAXPROCS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']), 'native thread controls differ')
    if partial:
        require(res['status'] == 'failed' and bool(res.get('error')), 'failed native output missing explicit error')
        require(len(res['queries']) <= config['samples'] and len(res['warmups']) <= config['warmup'], 'failed process has extra outputs')
        require(not res['queries'] or len(res['warmups']) == config['warmup'], 'formal queries precede required warmups')
    else:
        require(res['status'] == 'passed' and 'error' not in res, 'native did not finish successfully')
        require(len(res['queries']) == res['proofs_verified'] == config['samples'], 'measured proof count differs')
        require(len(res['warmups']) == res['warmup_proofs_verified'] == config['warmup'], 'warmup proof count differs')
    require([q['target_id'] for q in res['queries']] == [str(t['id']) for t in inp['targets'][:len(res['queries'])]], 'measured target order differs')
    require([q['target_id'] for q in res['warmups']] ==
            [str(inp['targets'][i % len(inp['targets'])]['id']) for i in range(len(res['warmups']))], 'warmup target order differs')
    require(all(q['warmup'] is False for q in res['queries']) and all(q['warmup'] is True for q in res['warmups']), 'warmup flags differ')
    if not partial:
        require(res['all_encrypted_queries_distinct'] is True and res['all_private_secrets_distinct'] is True, 'native freshness sanity check failed')
    calls, L, M, common_bytes = validate_setup(inp, res)
    targets = {str(t['id']): t for t in inp['targets']}
    shapes, query_rows, all_query_rows, checked_records = set(), [], [], 0
    for ordinal, query in enumerate(res['warmups'] + res['queries']):
        target = targets[query['target_id']]
        slot, height = int(target['slot_hex'], 16), inp['height']
        require(int(query['slot_hex'], 16) == slot, 'result coordinate differs')
        require(query['upstream_uint64_recover_low64_checked'] == (ordinal == 0), 'upstream width crosscheck schedule differs')
        need, node = {}, (1 << height) + slot
        for level in range(height):
            if node ^ 1 in source['heap']:
                need[level] = source['heap'][node ^ 1]
            node >>= 1
        require(need == {x['level']: x['record'] for x in target['needed']}, 'target need differs from original heap siblings')
        require(need and len(need) <= inp['pir']['batch_size'], 'invalid proof need width')
        items = query['recovered_by_bucket']
        require(len(items) == calls == query['PIR_calls'], 'variable/incorrect PIR call count')
        require([item['query_slot'] for item in items] == list(range(calls)), 'missing/duplicate query slots')
        expected_buckets = [0]*calls if method == 'flat' else list(range(calls))
        require([item['bucket'] for item in items] == expected_buckets, 'physical DB scheduling differs')
        require(query['positions_by_query'] == [x['position'] for x in items], 'reported positions differ')
        recovered = {}
        for item in items:
            b, position, record = item['bucket'], item['position'], item['record']
            bucket = inp['buckets'][b]
            raw = bytes.fromhex(item['record_hex'])
            require(len(raw) == 32, 'decoded digest width wrong')
            if bucket:
                require(0 <= position < len(bucket) and bucket[position] == record, 'decoded original record/position mismatch')
                require(raw == source['raw'][record], 'ACTUAL recovered digest differs from original publisher record')
            else:
                require(position == 0 and record == -1 and not item['real'] and raw == bytes(32), 'invalid empty-bucket dummy')
            if item['real']:
                level = item['level']
                require(level not in recovered and need.get(level) == record, 'missing/wrong/duplicate real proof record')
                recovered[level] = raw
            else:
                require('level' not in item, 'dummy carries an original proof level')
            checked_records += 1
        require(set(recovered) == set(need), 'recovered real proof set incomplete')
        require(query['real_records'] == len(need) and query['dummy_logical_slots'] == calls-len(need), 'real/dummy count differs')
        proof = [bytes.fromhex(x) for x in query['proof_bottom_up_hex']]
        assembled = [recovered.get(level, bytes.fromhex(inp['default_hashes'][level])) for level in range(height)]
        require(proof == assembled, 'proof contains values other than actual recovery/defaults')
        root, value = bytes.fromhex(inp['root_hex']), bytes.fromhex(target['value_hex'])
        computed = root_hash(value, slot, proof)
        require(computed == root and query['computed_root_hex'] == computed.hex(), 'independent SHA-256 root mismatch')
        bad = proof.copy()
        level = min(need)
        bad[level] = bytes([bad[level][0] ^ 1]) + bad[level][1:]
        require(root_hash(value, slot, bad) != root, 'bitflip unexpectedly authenticated')
        require(root_hash(value, slot ^ 1, proof) != root, 'wrong coordinate unexpectedly authenticated')
        require(root_hash(bytes([value[0] ^ 1])+value[1:], slot, proof) != root, 'wrong value unexpectedly authenticated')
        require(all(query[k] is True for k in ['valid_root', 'bitflip_rejected', 'corruption_rejected',
                    'wrong_coordinate_rejected', 'wrong_value_rejected']), 'native positive/negative flags differ')
        qp, ap = calls*4*(3*((M+2)//3)), calls*4*L
        qf, af = 8+24*calls+qp, 8+24*calls+ap
        for key, expected in [('query_matrix_payload_bytes', qp), ('answer_matrix_payload_bytes', ap),
                              ('query_framed_bytes', qf), ('answer_framed_bytes', af), ('online_framed_bytes', qf+af)]:
            require(query[key] == expected, f'actual matrix framing formula differs: {key}')
        shapes.add((calls, qp, ap, qf, af))
        require(all(isinstance(query[k], (int, float)) and math.isfinite(query[k]) and query[k] >= 0 for k in METRICS), 'invalid metric')
        component_sum = sum(query[k] for k in METRICS if k.endswith('_ms') and k != 'serialized_proof_wall_ms')
        require(component_sum <= query['serialized_proof_wall_ms']+0.01, 'stage times exceed full proof timer')
        entry = dict(case=case, method=method, repeat=rep, target_id=query['target_id'], warmup=query['warmup'],
                     ordinal=ordinal, process_complete=not partial, included_in_performance=not partial and not query['warmup'],
                     **{k: query[k] for k in METRICS}, real_records=len(need),
                     PIR_calls=calls, root_independently_verified=True, three_negatives_independently_verified=True)
        all_query_rows.append(entry)
        if not query['warmup']:
            query_rows.append(entry)
    require(len(shapes) <= 1 and (partial or len(shapes) == 1), 'target-dependent message envelope')
    if partial:
        return None, query_rows, all_query_rows, checked_records, source['common_hash']
    setup, p = res['setup'], res['parameters']['params']
    row = dict(case=case, method=method, repeat=rep, leaves=len(inp['occupied_slots_hex']), records=len(inp['records']),
               m=inp['pir']['batch_size'], buckets=len(inp['buckets']), max_bucket=max(map(len, inp['buckets'])),
               rounded_entries=res['parameters']['rounded_entries_per_bucket'], pir_dimensions=f'{L}x{M}',
               L=L, M=M, matrix_rows=L, matrix_cols=M, lwe_dimension=p['N'], plaintext_modulus=p['P'],
               ciphertext_logq=p['Logq'], noise_sigma=p['Sigma'], base_p_digits=26,
               PIR_calls=calls, proofs=len(query_rows), **{k: statistics.mean(q[k] for q in query_rows) for k in METRICS},
               **{k: v for k, v in setup.items() if isinstance(v, (int, float))})
    row['setup_serialized_payload_bytes'] = setup['bootstrap_framed_components_bytes']
    row['common_metadata_payload_bytes'] = common_bytes
    row['digest_only_cache_bytes'] = 32*len(inp['records'])
    row['full_cache_reference_bytes'] = row['digest_only_cache_bytes']+common_bytes
    row['source_input_sha256'], row['result_sha256'] = source['source_hash'], outcome['result_sha256']
    return row, query_rows, all_query_rows, checked_records, source['common_hash']


def summarize(rows, repeats):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row['case'], row['method']].append(row)
    aggregates = []
    structural = ['leaves', 'records', 'm', 'buckets', 'max_bucket', 'rounded_entries', 'pir_dimensions',
                  'L', 'M', 'matrix_rows', 'matrix_cols', 'lwe_dimension', 'plaintext_modulus', 'ciphertext_logq',
                  'noise_sigma', 'base_p_digits', 'PIR_calls']
    for (case, method), subset in sorted(groups.items()):
        item = dict(case=case, method=method, processes=len(subset),
                    verified_measured_proofs=sum(x['proofs'] for x in subset),
                    complete_planned_repeats={x['repeat'] for x in subset} == set(range(repeats)))
        item['estimation_scope'] = 'all_planned_processes' if item['complete_planned_repeats'] else 'successful_processes_conditional'
        for key in structural:
            values = {x[key] for x in subset}
            require(len(values) == 1, f'configuration changed across repeats: {case}/{method}/{key}')
            item[key] = next(iter(values))
        for key in subset[0]:
            if key not in item and key not in ['repeat', 'proofs'] and all(isinstance(x[key], (int, float)) for x in subset):
                item[key+'_mean'], item[key+'_sd'] = mean_sd([x[key] for x in subset])
        aggregates.append(item)
    comparisons = []
    ratio_metrics = ['online_framed_bytes', 'hint_matrix_bytes', 'public_A_matrix_bytes', 'replicated_record_payload_bytes',
                     'backend_rounded_raw_payload_bytes', 'encoded_db_bytes', 'setup_serialized_payload_bytes', 'persistent_setup_wall_ms']
    for case in sorted({r['case'] for r in rows}):
        ab = {x['repeat']: x for x in groups.get((case, 'ab'), [])}
        for method in ['pbc', 'flat', 'first_fit']:
            other = {x['repeat']: x for x in groups.get((case, method), [])}
            pairs = sorted(set(ab) & set(other))
            if not pairs:
                continue
            diffs = [other[i]['serialized_proof_wall_ms']-ab[i]['serialized_proof_wall_ms'] for i in pairs]
            ratios = [other[i]['serialized_proof_wall_ms']/ab[i]['serialized_proof_wall_ms'] for i in pairs]
            item = dict(case=case, comparator=method, paired_processes=len(pairs),
                        complete_planned_pairs=set(pairs) == set(range(repeats)),
                        comparator_over_ab_latency_mean=statistics.mean(ratios),
                        comparator_minus_ab_ms_mean=statistics.mean(diffs),
                        difference_ci95_low_ms=None, difference_ci95_high_ms=None)
            item['estimation_scope'] = 'all_planned_pairs' if item['complete_planned_pairs'] else 'successful_pairs_conditional'
            if len(pairs) == 3 and repeats == 3:
                delta = T95_DF2*statistics.stdev(diffs)/math.sqrt(3)
                item['difference_ci95_low_ms'] = statistics.mean(diffs)-delta
                item['difference_ci95_high_ms'] = statistics.mean(diffs)+delta
            for metric in ratio_metrics:
                item[metric+'_comparator_over_ab'] = statistics.mean(other[i][metric]/ab[i][metric] for i in pairs) if all(ab[i][metric] for i in pairs) else None
            comparisons.append(item)
    return aggregates, comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=BASE/'runs')
    parser.add_argument('--output', type=Path, default=BASE/'analysis')
    parser.add_argument('--input-root', type=Path, default=BASE/'inputs')
    parser.add_argument('--vbpir-root', type=Path, default=VBPIR)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, queries, all_queries, findings, partial_queries, audited_failures = [], [], [], [], [], []
    checked_records, paired_inputs = 0, {}
    config, schedule, outcomes = {}, [], []
    global_valid = True
    try:
        config = read(args.runs/'run_configuration.json')
        schedule = read(args.runs/'schedule.json')
        outcomes = read(args.runs/'process_outcomes.json') if (args.runs/'process_outcomes.json').is_file() else []
        sources = SourceAudit(args.input_root, args.vbpir_root)
        require(config['frozen_target_schedule_sha256'] == sha(args.input_root/'target_schedule.json'), 'frozen target schedule hash changed')
        require(config['statistical_unit'] == 'independent process mean' and config['GOMAXPROCS'] == 1, 'run statistical/thread policy differs')
        counts = (1, 2, 1) if config['smoke_excluded_from_performance'] else (3, 10, 2)
        require((config['repeats'], config['samples'], config['warmup']) == counts, 'unplanned repetition/warmup/sample count')
        planned = {triple_key(s): s for s in schedule}
        require(len(planned) == len(schedule), 'duplicate planned process')
        expected = {(c, m, r) for c in config['cases_requested'] for m in config['methods_requested'] for r in range(config['repeats'])}
        require(set(planned) == expected, 'schedule omits/adds configured method/case/repeat')
        require(len({triple_key(o) for o in outcomes}) == len(outcomes), 'duplicate outcome')
        require({triple_key(o) for o in outcomes} <= set(planned), 'unscheduled outcome')
        for outcome in outcomes:
            key = triple_key(outcome)
            if outcome['status'] != 'complete':
                try:
                    _, measured, all_rows, count, common_hash = validate_process(outcome, planned[key], config, args.runs, sources, partial=True)
                    partial_queries.extend(measured); all_queries.extend(all_rows); checked_records += count
                    failed_result = read(args.runs / key[0] / key[1] / f'repeat{key[2]}' / 'result.json')
                    warm_count, query_count = len(failed_result['warmups']), len(measured)
                    failed_phase = 'warmup' if warm_count < config['warmup'] else 'measured'
                    phase_ordinal = warm_count if failed_phase == 'warmup' else query_count
                    ids = planned[key]['target_ids']
                    next_id = ids[phase_ordinal % len(ids)] if (failed_phase == 'warmup' or phase_ordinal < len(ids)) else None
                    failure = dict(case=key[0], method=key[1], repeat=key[2], status='observed_backend_failure_audited',
                        backend_error=failed_result['error'], returncode=outcome['returncode'], timeout=outcome['timeout'],
                        verified_warmups=warm_count, verified_partial_measured_proofs=query_count,
                        first_uncompleted_phase=failed_phase, first_uncompleted_phase_ordinal_zero_based=phase_ordinal,
                        first_uncompleted_target_id=next_id, first_uncompleted_overall_ordinal_zero_based=warm_count+query_count,
                        ordinal_evidence='inferred from successfully persisted output prefix and source-reviewed sequential loop; no failed-query latency/result is imputed',
                        result_sha256=outcome['result_sha256'], excluded_from_performance_aggregates=True)
                    audited_failures.append(failure); findings.append(failure)
                except Exception as exc:
                    findings.append(dict(case=key[0], method=key[1], repeat=key[2], status='failed_process_independent_verification_failed', error=str(exc)))
                continue
            try:
                row, measured, all_rows, count, common_hash = validate_process(outcome, planned[key], config, args.runs, sources)
                pair = key[0], key[2]
                require(pair not in paired_inputs or paired_inputs[pair] == common_hash, 'cross-method paired snapshot mismatch')
                paired_inputs[pair] = common_hash
                rows.append(row); queries.extend(measured); all_queries.extend(all_rows); checked_records += count
            except Exception as exc:
                findings.append(dict(case=key[0], method=key[1], repeat=key[2], status='independent_verification_failed',
                                     error=str(exc), exception=type(exc).__name__))
        for key in sorted(set(planned)-{triple_key(o) for o in outcomes}):
            findings.append(dict(case=key[0], method=key[1], repeat=key[2], status='not_run_or_not_recorded'))
        availability = read(args.runs/'input_availability.json')
        require(not availability['unavailable'], 'requested input unavailable')
    except Exception as exc:
        global_valid = False
        findings.append(dict(status='global_provenance_or_configuration_failed', error=str(exc), exception=type(exc).__name__))
    try:
        aggregates, comparisons = summarize(rows, config.get('repeats', 3))
    except Exception as exc:
        global_valid = False
        findings.append(dict(status='aggregation_configuration_failed', error=str(exc)))
        aggregates, comparisons = [], []
    complete_plan = bool(rows) and global_valid and not findings and len(rows) == len(schedule) == len(outcomes)
    scheduled_executed_all = bool(schedule) and len(outcomes) == len(schedule) and {triple_key(o) for o in outcomes} == {triple_key(s) for s in schedule}
    audited_all = global_valid and scheduled_executed_all and len(rows)+len(audited_failures) == len(schedule) and all(x['status'] == 'observed_backend_failure_audited' for x in findings)
    formal_keys = {(c, m, r) for c in CASES for m in METHODS for r in range(3)}
    formal_complete = complete_plan and not config.get('smoke_excluded_from_performance', True) and {triple_key(r) for r in rows} == formal_keys
    status = ('passed' if formal_complete else 'audited_with_observed_failures' if audited_all and audited_failures else
              'smoke_passed' if complete_plan and config.get('smoke_excluded_from_performance') else
              'verified_subset_only' if rows else 'no_verified_evidence')
    verification = dict(status=status, complete_requested_experiment=formal_complete, complete_run_plan=complete_plan,
        smoke_excluded_from_performance=config.get('smoke_excluded_from_performance'), auditor_sha256=sha(Path(__file__)),
        scheduled_executed_all=scheduled_executed_all, all_executed_outputs_audited=audited_all or complete_plan,
        process_results_verified=len(rows), failed_process_results_audited=len(audited_failures),
        total_process_results_audited=len(rows)+len(audited_failures),
        measured_proofs_verified=len(queries)+len(partial_queries), complete_process_measured_proofs=len(queries),
        partial_process_measured_proofs=len(partial_queries), proofs_including_warmups_verified=len(all_queries),
        valid_completed_cells=sum(x['complete_planned_repeats'] for x in aggregates),
        incomplete_cells=[dict(case=x['case'], method=x['method'], processes=x['processes'], scope=x['estimation_scope']) for x in aggregates if not x['complete_planned_repeats']],
        actual_recovered_record_slots_checked=checked_records, expected_formal_processes=84,
        expected_formal_measured_proofs=840, expected_formal_proofs_including_warmups=1008,
        source_run_configuration=config, failed_or_invalid_or_missing_processes=findings,
        authentication='Python derives siblings and query-support intervals from original heap coordinates; checks every real/dummy recovered digest and bucket position; rebuilds roots from actual decoded bytes and defaults; three independent negative controls.',
        actual_recovery_used=bool(rows), all_envelopes_target_independent_within_process=bool(rows),
        cross_backend_scope='Snapshots, original records/levels/root, AB placement, official PBC placement and case/repeat target selection match frozen VBPIR. Crypto parameters and dummy/eviction traces are not asserted equal.',
        serialization_scope='Independent exact frame/DBinfo/public-metadata lengths from source-reviewed actual encode/decode path; raw matrix wires are not retained, so no independent re-execution of lattice decryption is claimed.',
        randomness_scope='Native duplicate query/secret sanity flags checked; cryptographic randomness/security is source-audited, not independently proved by these flags.',
        statistical_unit='independent process mean; sample SD; paired df=2 Student-t interval only for three matched processes',
        cache_reference='digest_only_cache_bytes counts all active 32B digests; full_cache_reference_bytes also includes the same compact JSON height/root/defaults/slots/intervals/batch directory, omitting mode/buckets/candidates. This is a specified shared-directory reference, not a lower bound or minimum necessary cache state.',
        scope='native256bits/32B; expanded-A; same-process serialized proof processing, no network. RSS combines client/server and audit buffers. Full construction is outside backend setup.')
    dump(args.output/'results.json', dict(status=status, process_means=rows, aggregates=aggregates, comparisons=comparisons))
    dump(args.output/'INDEPENDENT_VERIFICATION.json', verification)
    dump(args.output/'failure_audit.json', audited_failures)
    table(args.output/'process_means.csv', rows, ['case', 'method', 'repeat', 'proofs'])
    table(args.output/'query_measurements.csv', queries, ['case', 'method', 'repeat', 'target_id'])
    table(args.output/'partial_query_measurements.csv', partial_queries, ['case', 'method', 'repeat', 'target_id'])
    table(args.output/'all_proof_verification.csv', all_queries, ['case', 'method', 'repeat', 'target_id', 'warmup'])
    table(args.output/'aggregate_results.csv', aggregates, ['case', 'method', 'processes'])
    table(args.output/'paired_comparisons.csv', comparisons, ['case', 'comparator', 'paired_processes'])
    print(json.dumps(dict(status=status, processes_verified=len(rows), measured_proofs=len(queries), partial_measured_proofs=len(partial_queries),
                          including_warmups=len(all_queries), failures=findings), indent=2))
    # Subsets are valid descriptive artifacts; failed audits must be visible to the caller.
    return 2 if any('failed' in x['status'] for x in findings) else 0


if __name__ == '__main__':
    raise SystemExit(main())
