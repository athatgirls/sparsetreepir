"""Independently verify the exact matching/Hall certificates and write the memo."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RUN = BASE / 'runs/prefix64_n10000/pbc/repeat0'
diagnosis = json.loads((HERE / 'pbc_failure_diagnosis.json').read_text())
source = json.loads((RUN / 'input.json').read_text(encoding='utf-8'))
original = json.loads((RUN / 'result.json').read_text(encoding='utf-8'))
replay = diagnosis['failure_replay']
batch = replay['padded_records_in_insertion_order']
real = [x['record'] for x in replay['public_needed_intervals_outer_to_inner']]
dummy = [r for r in batch if r not in real]
assert len(batch) == len(set(batch)) == source['pir']['batch_size'] == 17
assert len(real) == 12 and len(dummy) == 5
assert diagnosis['failed_stage'] == 'measured'
assert diagnosis['failed_target_zero_based_index'] == len(original['queries']) == 7
assert len(original['warmups']) == 2
assert str(source['targets'][7]['id']) == replay['target_id'] == '3455'
assert replay['ordinal'] == 9 and replay['effective_rng_seed'] == source['seed'] + 9 == 2026091112
assert replay['failure_depth'] == 501 and not replay['cuckoo_succeeded']

def verify_matching(graph, left):
    cert = graph['matching_certificate']
    assert len(cert) == graph['maximum_matching_cardinality']
    assert len({x['record'] for x in cert}) == len(cert)
    assert len({x['bucket'] for x in cert}) == len(cert)
    for x in cert:
        assert x['record'] in left
        assert x['bucket'] in source['hash_candidates'][x['record']]
    return len(cert)

padded = diagnosis['padded_batch_matching']
matched = verify_matching(padded, batch)
assert matched == 16 and not padded['complete_matching_exists']
hall = padded['hall_witness']
witness_records = set(hall['records'])
assert witness_records <= set(batch)
neighbors = set().union(*(set(source['hash_candidates'][r]) for r in witness_records))
assert neighbors == set(hall['neighbor_buckets'])
assert len(witness_records) == 11 and len(neighbors) == 10
assert len(batch) - (len(witness_records) - len(neighbors)) == matched
for adjacency in hall['adjacency']:
    assert adjacency['candidates'] == source['hash_candidates'][adjacency['record']]
assert verify_matching(diagnosis['real_needed_only_matching'], real) == len(real)
assert diagnosis['real_needed_only_matching']['complete_matching_exists']

for filename in ['input.json', 'result.json', 'command.json']:
    key = f'runs/prefix64_n10000/pbc/repeat0/{filename}'
    assert hashlib.sha256((RUN / filename).read_bytes()).hexdigest() == diagnosis['frozen_artifact_sha256'][key]

verification = {
    'status': 'passed',
    'scope': 'Independent Python certificate checks against the frozen original input; no routing rerun or benchmark.',
    'maximum_matching_lower_bound': matched,
    'hall_upper_bound': len(batch) - (len(witness_records) - len(neighbors)),
    'therefore_exact_maximum_matching': matched,
    'padded_left_count': len(batch),
    'real_needed_exact_matching': len(real),
    'hall_real_record_count': len(witness_records & set(real)),
    'hall_dummy_record_count': len(witness_records & set(dummy)),
    'original_input_result_command_hashes_unchanged': True,
}
(HERE / 'pbc_failure_certificate_verification.json').write_text(json.dumps(verification, indent=2) + '\n', encoding='utf-8')

table = '\n'.join(f"| {r} | {'real' if r in real else 'dummy'} | {', '.join(map(str, source['hash_candidates'][r]))} |" for r in sorted(witness_records))
memo = f'''# Preserved PBC routing failure: exact diagnosis

The failed process `prefix64_n10000/pbc/repeat0` encountered an **unmatchable
fixed padded batch**, rather than a random-eviction heuristic stopping too early.
The maximum matching has size **16 for 17 requested record IDs**. A Hall witness
contains **11 records whose candidate union has only 10 buckets**, proving that
no choice of insertion order or additional eviction attempts can route this same
batch under its same candidate placement.

The target's **12 real proof records have a complete matching**. In this instance,
the five distinct existing records selected by the frozen dummy-padding policy
make the padded batch unmatchable. This result concerns that fixed padding and
candidate instance; it does not establish that the target's real proof alone is
unroutable, nor that all PBC requests fail.

## Exact failed request

| Field | Preserved value |
|---|---|
| Case / method / process | `prefix64_n10000 / pbc / repeat0` |
| Failure stage | Eighth measured request; zero-based measured index 7 |
| Successful requests before failure | 2 warmups and 7 measured requests |
| Target ID | `3455` |
| Coordinate | `{replay['slot_hex']}` |
| Driver request ordinal | 9 (two warmups plus measured index 7) |
| Input seed | `{source['seed']}` |
| Effective Go routing seed | `{replay['effective_rng_seed']}` |
| Public batch size / bucket count | 17 / 26 |
| Real / dummy record count | 12 / 5 |
| Terminal recursion | Attempt 501, rejected by the frozen 500-attempt check |
| Insertion that triggered failure | Final batch record `{batch[-1]}` (a dummy), insertion index 16 |

The padded record IDs in the exact insertion order were:

```text
{', '.join(map(str, batch))}
```

The real records were the first 12 entries. The five accepted random padding
draws were `{', '.join(map(str, dummy))}`; no draw was rejected as a duplicate.
All IDs are zero-based indices into the frozen canonical record array. No
database record or candidate bucket was regenerated for this diagnosis.

## Checkable impossibility certificate

The following subset contains seven real records and four dummy records:

| Record ID | Role | Its three fixed candidate buckets |
|---|---|---|
{table}

Their neighbor union is `{', '.join(map(str, sorted(neighbors)))}`: 10 buckets
for 11 records. The diagnostic also supplies an explicit valid 16-record
matching for the full batch. The valid matching proves a lower bound of 16;
the Hall witness proves an upper bound of 16. Thus 16 is the exact maximum.
An explicit 12-record matching for the real-only proof is included separately.

## Reproduction and preservation

From `examples/tifs_simplepir_extension_20260911` on Linux:

```sh
GOMAXPROCS=1 go run audit/diagnose_pbc_failure.go \\
  runs/prefix64_n10000/pbc/repeat0/input.json \\
  runs/prefix64_n10000/pbc/repeat0/result.json \\
  runs/prefix64_n10000/pbc/repeat0/command.json \\
  audit/pbc_failure_diagnosis.json
python3 audit/verify_pbc_failure_certificate.py
```

The helper imports only the Go standard library and performs no PIR setup,
query, answer, decoding or timing benchmark. It uses Go 1.22.2 `math/rand` and
the frozen per-request seed rule. Its independently filtered, outer-to-inner
public interval list reproduces the driver's forest-stabbing order. It then
replays the exact padding draws and empty-slot-first/random-eviction insertion.
All bucket IDs, positions, returned record IDs and real-record levels for the
nine successful requests before failure match their saved native results.
The failing request reaches the same recursion limit. The complete eviction
trace, padded IDs, candidates, matching certificates and artifact hashes are
in `pbc_failure_diagnosis.json`.

The Python script separately checks the matching and Hall certificates against
the original input, without relying on the Go matching algorithm. Its output is
`pbc_failure_certificate_verification.json`. Input, result, command, driver and
binary hashes were checked unchanged by the Go helper; the Python checker also
rechecks the first three. The original failed result is retained unchanged.

## Appropriate reporting

Suggested sentence: “One fixed PBC batch failed routing in the prefix-clustered
case: the 17 requested IDs, including five padding records, admitted a maximum
matching of 16 under the fixed three-choice placement. The 12 real proof IDs
alone remained matchable. We retain this failure and report successful-request
latencies conditional on completion.”

This offline maximum-matching check is a diagnosis, not a replacement online
router. Increasing the eviction budget alone cannot fix this particular graph.
Changing the padding set or global candidate placement would define a different
request or layout and has not been done. Do not describe the failure as a
cryptographic decoding error or a root-verification failure; it occurred in
online routing before query generation. Do not assign completion latency to
the failed request or to the two scheduled requests that were never executed.
'''
(HERE / 'pbc_failure_diagnosis.md').write_text(memo, encoding='utf-8')
print(json.dumps(verification, indent=2))
