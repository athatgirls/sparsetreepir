"""Independently authenticate native recovered proofs and summarize process means."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_external_extension_20260911'
T95_DF2 = 4.302652729911275
METRICS = ['serialized_proof_wall_ms', 'route_ms', 'query_ms', 'query_roundtrip_ms',
           'answer_ms', 'answer_roundtrip_ms', 'decode_ms', 'proof_verify_ms', 'online_framed_bytes']


def dump(path, x):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(x, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(path, rows):
    if rows:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with path.open('w', newline='', encoding='utf8') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


def root_hash(value, slot, proof):
    node = hashlib.sha256(b'\0' + value).digest()
    for level, sibling in enumerate(proof):
        pair = sibling + node if (slot >> level) & 1 else node + sibling
        node = hashlib.sha256(b'\x01' + pair).digest()
    return node


def stats(values):
    return {'mean': statistics.mean(values), 'sd': statistics.stdev(values) if len(values) > 1 else None,
            'n': len(values), 'min': min(values), 'max': max(values)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=Path, default=BASE / 'runs')
    ap.add_argument('--output', type=Path, default=BASE / 'analysis')
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    outcomes = json.loads((a.runs / 'process_outcomes.json').read_text())
    config = json.loads((a.runs / 'run_configuration.json').read_text())
    schedule = json.loads((a.runs / 'schedule.json').read_text())
    planned = {(s['case'], s['method'], s['repeat']): s for s in schedule}
    assert len(planned) == len(schedule)
    assert len({(s['case'], s['method'], s['repeat']) for s in outcomes}) == len(outcomes)
    paired_inputs = {}
    rows, query_rows, findings, checked = [], [], [], 0
    for outcome in outcomes:
        if outcome['status'] != 'complete':
            findings.append({'case': outcome['case'], 'method': outcome['method'], 'repeat': outcome['repeat'], 'status': outcome['status']})
            continue
        case, method, rep = outcome['case'], outcome['method'], outcome['repeat']
        scheduled = planned[case, method, rep]
        assert outcome['binary_sha256'] == config['binary_sha256']
        assert outcome['target_ids'] == scheduled['target_ids']
        directory = a.runs / case / method / f'repeat{rep}'
        inp = json.loads((directory / 'input.json').read_text())
        res = json.loads((directory / 'result.json').read_text())
        assert sha(directory / 'input.json') == outcome['run_input_sha256']
        assert sha(directory / 'result.json') == outcome['result_sha256']
        assert res['status'] == 'passed' and res['proofs_verified'] == config['samples']
        assert len(inp['targets']) == len(res['queries']) == config['samples']
        assert len(res['warmups']) == res['warmup_proofs_verified'] == config['warmup']
        assert [t['id'] for t in inp['targets']] == scheduled['target_ids']
        assert [q['target_id'] for q in res['queries']] == [str(t['id']) for t in inp['targets']]
        assert not any(q['warmup'] for q in res['queries'])
        assert all(q['warmup'] for q in res['warmups'])
        assert [q['target_id'] for q in res['warmups']] == [str(inp['targets'][i % len(inp['targets'])]['id']) for i in range(config['warmup'])]
        common = {k: inp[k] for k in ['height', 'records', 'root_hex', 'default_hashes', 'occupied_slots_hex',
                                     'record_heap_ids_hex', 'record_intervals', 'pir', 'seed']}
        common['targets'] = [{k: t[k] for k in ['id', 'slot_hex', 'value_hex', 'needed']} for t in inp['targets']]
        if (case, rep) in paired_inputs:
            assert common == paired_inputs[case, rep], (case, rep, 'cross-method common-input mismatch')
        else:
            paired_inputs[case, rep] = common
        params, setup = res['parameters'], res['setup']
        assert params['record_bytes'] == 32 and params['security_level'] == 'tc128' and params['context_parameters_valid']
        assert params['compression'] == 'none'
        assert params['records'] == len(inp['records'])
        assert sum(params['bucket_loads']) == len(inp['records']) * (3 if method == 'pbc' else 1)
        assert max(params['bucket_loads']) == params['max_bucket_records']
        assert math.prod(params['pir_dimensions']) == params['rounded_entries_per_bucket']
        assert setup['replicated_record_payload_bytes'] == 32 * sum(params['bucket_loads'])
        assert setup['max_padded_bucket_payload_bytes'] == 32 * params['bucket_count'] * params['max_bucket_records']
        known = {str(t['id']): t for t in inp['targets']}
        heap = {int(h, 16): i for i, h in enumerate(inp['record_heap_ids_hex'])}
        shapes = set()
        for q in res['warmups'] + res['queries']:
            target = known[q['target_id']]
            slot, h = int(target['slot_hex'], 16), inp['height']
            assert int(q['slot_hex'], 16) == slot
            assert q['valid_root'] and q['bitflip_rejected'] and q['wrong_coordinate_rejected'] and q['wrong_value_rejected']
            proof = [bytes.fromhex(x) for x in q['proof_bottom_up_hex']]
            assert len(proof) == h and all(len(x) == 32 for x in proof)
            need = {}
            node = (1 << h) + slot
            for level in range(h):
                if node ^ 1 in heap:
                    need[level] = heap[node ^ 1]
                node >>= 1
            assert need == {t['level']: t['record'] for t in target['needed']}
            recovered = {}
            for r in q['recovered_by_bucket']:
                if not r['real']:
                    continue
                assert r['level'] not in recovered
                assert need[r['level']] == r['record']
                assert r['record_hex'] == inp['records'][r['record']]
                recovered[r['level']] = bytes.fromhex(r['record_hex'])
                if method != 'pbc':
                    assert inp['buckets'][r['bucket']][r['position']] == r['record']
            assert set(recovered) == set(need)
            assembled = [recovered.get(t, bytes.fromhex(inp['default_hashes'][t])) for t in range(h)]
            assert assembled == proof
            value, root = bytes.fromhex(target['value_hex']), bytes.fromhex(inp['root_hex'])
            assert root_hash(value, slot, proof) == root
            bad = proof.copy()
            lev = min(need)
            bad[lev] = bytes([bad[lev][0] ^ 1]) + bad[lev][1:]
            assert root_hash(value, slot, bad) != root
            assert root_hash(value, slot ^ 1, proof) != root
            assert root_hash(bytes([value[0] ^ 1]) + value[1:], slot, proof) != root
            assert q['query_framed_bytes'] == q['query_ciphertext_payload_bytes'] + 8 * (1 + q['query_ciphertexts'])
            assert q['answer_framed_bytes'] == q['answer_ciphertext_payload_bytes'] + 8 * (1 + q['answer_ciphertexts'])
            assert q['online_framed_bytes'] == q['query_framed_bytes'] + q['answer_framed_bytes']
            shapes.add((q['query_ciphertexts'], q['answer_ciphertexts'], q['query_framed_bytes'], q['answer_framed_bytes']))
            component_sum = sum(q[k] for k in METRICS if k not in ['serialized_proof_wall_ms', 'online_framed_bytes'])
            assert all(math.isfinite(q[k]) and q[k] >= 0 for k in METRICS)
            assert component_sum <= q['serialized_proof_wall_ms'] + 0.01
            checked += 1
            if not q['warmup']:
                query_rows.append({'case': case, 'method': method, 'repeat': rep, 'target_id': q['target_id'], **{k: q[k] for k in METRICS},
                                   'real_records': q['real_records'], 'valid_root_independently_verified': True})
        assert len(shapes) == 1, (case, method, 'target-dependent envelope shape')
        row = {'case': case, 'method': method, 'repeat': rep, 'n': len(inp['occupied_slots_hex']), 'N': len(inp['records']),
               'm': params['batch_size_m'], 'buckets': params['bucket_count'], 'max_bucket': params['max_bucket_records'],
               'rounded_entries': params['rounded_entries_per_bucket'], 'pir_dimensions': 'x'.join(map(str, params['pir_dimensions'])),
               'proofs': len(res['queries']), **{k: statistics.mean(q[k] for q in res['queries']) for k in METRICS}, **setup}
        row['setup_serialized_payload_bytes'] = setup['setup_client_to_server_payload_bytes'] + setup['setup_server_to_client_payload_bytes']
        rows.append(row)
    groups = {}
    for row in rows:
        groups.setdefault((row['case'], row['method']), []).append(row)
    aggregates = []
    for (case, method), subset in groups.items():
        result = {'case': case, 'method': method, 'processes': len(subset), 'verified_measured_proofs': sum(r['proofs'] for r in subset),
                  'complete_planned_repeats': {r['repeat'] for r in subset} == set(range(config['repeats']))}
        for key in ['n', 'N', 'm', 'buckets', 'max_bucket', 'rounded_entries', 'pir_dimensions']:
            vals = {r[key] for r in subset}
            assert len(vals) == 1
            result[key] = next(iter(vals))
        for key in METRICS + list(next(r for r in rows if r['case'] == case and r['method'] == method).keys()):
            if key in result or key in ['case', 'method', 'repeat', 'proofs']:
                continue
            if all(isinstance(r.get(key), (int, float)) for r in subset):
                stat = stats([r[key] for r in subset])
                result[key + '_mean'] = stat['mean']
                result[key + '_sd'] = stat['sd']
        aggregates.append(result)
    comparisons = []
    for case in sorted({r['case'] for r in rows}):
        ab = {r['repeat']: r for r in groups.get((case, 'ab'), [])}
        for other in ['pbc', 'treepir']:
            alt = {r['repeat']: r for r in groups.get((case, other), [])}
            pairs = sorted(set(ab) & set(alt))
            if not pairs:
                continue
            diffs = [alt[i]['serialized_proof_wall_ms'] - ab[i]['serialized_proof_wall_ms'] for i in pairs]
            ratios = [alt[i]['serialized_proof_wall_ms'] / ab[i]['serialized_proof_wall_ms'] for i in pairs]
            item = {'case': case, 'comparator': other, 'paired_processes': len(pairs),
                    'complete_planned_pairs': set(pairs) == set(range(config['repeats'])),
                    'comparator_over_ab_latency_mean': statistics.mean(ratios),
                    'comparator_minus_ab_ms_mean': statistics.mean(diffs)}
            if len(pairs) == 3:
                delta = T95_DF2 * statistics.stdev(diffs) / math.sqrt(3)
                item.update(difference_ci95_low_ms=statistics.mean(diffs)-delta, difference_ci95_high_ms=statistics.mean(diffs)+delta)
            for metric in ['online_framed_bytes', 'replicated_record_payload_bytes', 'backend_rounded_raw_payload_bytes',
                           'ntt_coefficient_payload_bytes', 'setup_serialized_payload_bytes', 'persistent_setup_wall_ms']:
                item[metric + '_comparator_over_ab'] = statistics.mean(alt[i][metric] / ab[i][metric] for i in pairs) if all(ab[i][metric] for i in pairs) else None
            comparisons.append(item)
    table(a.output / 'process_means.csv', rows)
    table(a.output / 'query_measurements.csv', query_rows)
    table(a.output / 'aggregate_results.csv', aggregates)
    table(a.output / 'paired_comparisons.csv', comparisons)
    dump(a.output / 'results.json', {'process_means': rows, 'aggregates': aggregates, 'comparisons': comparisons})
    missing_inputs = json.loads((a.runs / 'input_availability.json').read_text())['unavailable']
    complete = len(rows) == len(schedule) == len(outcomes) and bool(rows) and not findings and not missing_inputs
    audit_status = 'passed' if complete else ('verified_subset_only' if rows else 'no_verified_evidence')
    dump(a.output / 'INDEPENDENT_VERIFICATION.json', {'status': audit_status, 'complete_requested_experiment': complete, 'auditor_sha256': sha(Path(__file__)),
          'process_results_verified': len(rows), 'measured_proofs_verified': len(query_rows), 'proofs_including_warmups_verified': checked,
          'source_run_configuration': config, 'authentication': 'independent Python SHA-256 reconstruction, heap-sibling need derivation, three negative controls',
          'actual_recovery_used': True, 'all_envelopes_target_independent_within_process': True, 'failed_or_invalid_processes': findings,
          'incomplete_requested_inputs': missing_inputs,
          'scope': 'in-process serialized proof pipeline; RSS combines roles; no network or isolated client RAM claim'})
    print(json.dumps({'processes_verified': len(rows), 'measured_proofs': len(query_rows), 'including_warmups': checked,
                      'comparisons': comparisons}, indent=2))


if __name__ == '__main__':
    main()
