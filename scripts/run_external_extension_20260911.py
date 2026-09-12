"""Sequential, paired native VBPIR proof experiments; never overwrite raw runs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import random
import resource
import signal
import subprocess
import time

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_external_extension_20260911'


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded_child():
    resource.setrlimit(resource.RLIMIT_AS, (10 * 1024**3, 10 * 1024**3))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input-root', type=Path, default=BASE / 'inputs')
    p.add_argument('--binary', type=Path, default=BASE / 'native_adapter/build/serialized_proof_bench')
    p.add_argument('--output', type=Path, default=BASE / 'runs')
    p.add_argument('--cases', nargs='+', default=['uniform_n1000', 'uniform_n10000', 'uniform_n100000', 'prefix64_n10000', 'cluster90_n10000', 'complete_h10', 'complete_h14'])
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--samples', type=int, default=10)
    p.add_argument('--warmup', type=int, default=2)
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--seed', type=int, default=2026091103)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    if a.smoke:
        a.repeats, a.samples, a.warmup = 1, 2, 1
        if a.output == BASE / 'runs':
            a.output = BASE / 'smoke'
    if not a.binary.is_file():
        raise FileNotFoundError(a.binary)
    a.output.mkdir(parents=True, exist_ok=True)
    binary_hash = sha(a.binary)
    setup = {'schema': 1, 'seed': a.seed, 'repeats': a.repeats, 'samples': a.samples,
             'warmup': a.warmup, 'cases_requested': a.cases, 'smoke_excluded_from_performance': a.smoke,
             'binary_sha256': binary_hash, 'script_sha256': sha(Path(__file__)),
             'timeout_seconds': a.timeout, 'address_space_limit_bytes': 10 * 1024**3,
             'OMP_NUM_THREADS': 1, 'statistical_unit': 'independent process mean',
             'scope': 'serialized in-process proof pipeline; no network latency'}
    manifest_path = a.output / 'run_configuration.json'
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if not a.resume or previous != setup:
            raise RuntimeError('existing run configuration: use --resume only with identical source, binary and parameters')
    else:
        dump(manifest_path, setup)
    environment = {'platform': platform.platform(), 'python': platform.python_version(),
                   'cpu': next((s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')), 'unknown'),
                   'os_release': Path('/etc/os-release').read_text(),
                   'memory_before': Path('/proc/meminfo').read_text(),
                   'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
                   'thread_policy': 'all native benchmark processes run sequentially; OMP_NUM_THREADS=1'}
    if not (a.output / 'environment.json').exists():
        dump(a.output / 'environment.json', environment)
    cases = {}
    missing = []
    for name in a.cases:
        directory = a.input_root / name
        snapshot = directory / 'snapshot_summary.json'
        if not snapshot.is_file() or json.loads(snapshot.read_text()).get('status') != 'complete':
            missing.append(name)
            continue
        files = {m: directory / (m + '.json') for m in ['ab', 'pbc', 'treepir'] if (directory / (m + '.json')).is_file()}
        assert {'ab', 'pbc'}.issubset(files)
        if name.startswith('complete_'):
            assert 'treepir' in files
        inputs = {m: json.loads(f.read_text()) for m, f in files.items()}
        first = next(iter(inputs.values()))
        target_ids = [t['id'] for t in first['targets']]
        if len(set(target_ids)) != len(target_ids) or len(target_ids) < a.samples:
            raise AssertionError('invalid or insufficient target pool')
        for m, data in inputs.items():
            assert data['records'] == first['records'] and data['root_hex'] == first['root_hex']
            assert data['height'] == first['height'] and data['default_hashes'] == first['default_hashes']
            assert [t['id'] for t in data['targets']] == target_ids
            for left, right in zip(data['targets'], first['targets']):
                assert all(left[k] == right[k] for k in ['slot_hex', 'value_hex', 'needed'])
        cases[name] = (files, inputs)
    dump(a.output / 'input_availability.json', {'available': list(cases), 'unavailable': missing})
    schedule = []
    for rep in range(a.repeats):
        rng = random.Random(a.seed + 1009 * rep)
        order = list(cases)
        rng.shuffle(order)
        for name in order:
            files, inputs = cases[name]
            source = next(iter(inputs.values()))
            selected = rng.sample(range(len(source['targets'])), a.samples)
            methods = list(inputs)
            rng.shuffle(methods)
            for method in methods:
                schedule.append({'case': name, 'repeat': rep, 'method': method,
                                 'pool_indices': selected, 'target_ids': [source['targets'][i]['id'] for i in selected],
                                 'input_sha256': sha(files[method])})
    existing_schedule = a.output / 'schedule.json'
    if existing_schedule.exists() and json.loads(existing_schedule.read_text()) != schedule:
        raise RuntimeError('input/schedule changed: choose a new output directory')
    dump(existing_schedule, schedule)
    outcomes = []
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for item in schedule:
        name, method, rep = item['case'], item['method'], item['repeat']
        run = a.output / name / method / f'repeat{rep}'
        status = run / 'status.json'
        if status.exists():
            if not a.resume:
                raise RuntimeError(f'refusing overwrite: {run}')
            previous = json.loads(status.read_text())
            if previous['binary_sha256'] != binary_hash or previous['input_source_sha256'] != item['input_sha256']:
                raise RuntimeError('resume provenance mismatch')
            outcomes.append(previous)
            continue
        if run.exists():
            raise RuntimeError(f'partial raw run requires manual audit, not silent replacement: {run}')
        run.mkdir(parents=True)
        data = cases[name][1][method].copy()
        data['targets'] = [data['targets'][i] for i in item['pool_indices']]
        data['seed'] = a.seed + rep * 1009
        infile, outfile = run / 'input.json', run / 'result.json'
        dump(infile, data)
        command = [str(a.binary), str(infile), str(outfile), str(a.warmup)]
        dump(run / 'command.json', {'argv': command, 'environment_overrides': {k: env[k] for k in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']}})
        print('START', name, method, rep, f'{a.samples} proofs', flush=True)
        started = time.perf_counter()
        timeout = False
        with (run / 'stdout.txt').open('w') as stdout, (run / 'stderr.txt').open('w') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env,
                                       preexec_fn=bounded_child, start_new_session=True)
            try:
                code = process.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                timeout = True
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
        row = {**item, 'returncode': code, 'timeout': timeout,
               'wall_seconds': time.perf_counter() - started, 'binary_sha256': binary_hash,
               'input_source_sha256': item['input_sha256'], 'run_input_sha256': sha(infile),
               'result_sha256': sha(outfile) if outfile.exists() else None,
               'status': 'complete' if code == 0 and outfile.exists() else 'failed'}
        if row['status'] == 'complete':
            result = json.loads(outfile.read_text())
            if 'error' in result or len(result.get('queries', [])) != a.samples:
                row['status'] = 'invalid_result'
        dump(status, row)
        outcomes.append(row)
        dump(a.output / 'process_outcomes.json', outcomes)
        print('DONE', name, method, rep, row['status'], round(row['wall_seconds'], 2), 's', flush=True)
    dump(a.output / 'completion.json', {'scheduled': len(schedule), 'completed': sum(x['status'] == 'complete' for x in outcomes),
                                      'failures': [x for x in outcomes if x['status'] != 'complete'], 'unavailable_inputs': missing,
                                      'measured_target_requests': a.samples * sum(x['status'] == 'complete' for x in outcomes),
                                      'smoke_excluded_from_performance': a.smoke})


if __name__ == '__main__':
    main()
