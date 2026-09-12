"""Excluded functional smoke: four layouts, one target and one warmup each."""
from pathlib import Path
import hashlib
import json
import subprocess

here = Path(__file__).resolve().parent
out = here / 'functional'
out.mkdir(exist_ok=True)
def linux(path):
    p = Path(path).resolve()
    return '/mnt/' + p.drive[0].lower() + '/' + '/'.join(p.parts[1:])

summary = {'scope': 'Excluded correctness smoke only; not formal benchmark samples.', 'methods': []}
for method in ['flat', 'ab', 'pbc', 'first_fit']:
    source = here.parent / 'inputs/uniform_n1000' / f'{method}.json'
    data = json.loads(source.read_text(encoding='utf-8'))
    data['targets'] = data['targets'][:1]
    input_path = out / f'{method}_input.json'
    output_path = out / f'{method}_result.json'
    input_path.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
    with (out / f'{method}.log').open('wb') as log:
        process = subprocess.run(['wsl.exe', '-e', linux(here / 'build/simplepir_proof_bench'), linux(input_path), linux(output_path), '1'], stdout=log, stderr=subprocess.STDOUT)
    assert process.returncode == 0, (method, process.returncode)
    result = json.loads(output_path.read_text())
    assert result['status'] == 'passed'
    assert len(result['queries']) == len(result['warmups']) == 1
    for row in result['queries'] + result['warmups']:
        assert row['valid_root'] and row['bitflip_rejected'] and row['wrong_coordinate_rejected'] and row['wrong_value_rejected']
        assert row['query_framed_bytes'] == row['query_matrix_payload_bytes'] + 8 + 24 * row['PIR_calls']
        assert row['answer_framed_bytes'] == row['answer_matrix_payload_bytes'] + 8 + 24 * row['PIR_calls']
    if method == 'flat':
        assert result['setup']['initialized_databases'] == 1
        assert len(result['setup']['bucket_metrics']) == 1
        assert result['parameters']['PIR_calls_per_proof'] == data['pir']['batch_size']
    summary['methods'].append({'method': method, 'status': result['status'], 'proofs': 2,
                              'initialized_databases': result['setup']['initialized_databases'],
                              'PIR_calls_per_proof': result['parameters']['PIR_calls_per_proof'],
                              'result_sha256': hashlib.sha256(output_path.read_bytes()).hexdigest()})
    print(method, 'passed', flush=True)
summary['binary_sha256'] = hashlib.sha256((here / 'build/simplepir_proof_bench').read_bytes()).hexdigest()
(out / 'smoke_validation.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
