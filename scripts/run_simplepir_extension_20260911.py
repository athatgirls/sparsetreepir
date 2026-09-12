"""Run paired native-32B SimplePIR proofs using the frozen VBPIR target schedule."""
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
BASE = ROOT / 'examples/tifs_simplepir_extension_20260911'
CASES = ['uniform_n1000', 'uniform_n10000', 'uniform_n100000', 'prefix64_n10000', 'cluster90_n10000', 'complete_h10', 'complete_h14']
METHODS = ['ab', 'pbc', 'flat', 'first_fit']
COMMON = ['height', 'records', 'root_hex', 'default_hashes', 'occupied_slots_hex', 'record_heap_ids_hex', 'record_intervals', 'pir', 'seed']

def dump(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + '\n', encoding='utf8')

def read(p):
    return json.loads(p.read_text(encoding='utf8'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def bounded_child():
    resource.setrlimit(resource.RLIMIT_AS, (10 * 1024**3, 10 * 1024**3))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', type=Path, default=BASE / 'backend/build/simplepir_proof_bench')
    p.add_argument('--output', type=Path, default=BASE / 'runs')
    p.add_argument('--cases', nargs='+', default=CASES)
    p.add_argument('--methods', nargs='+', choices=METHODS, default=METHODS)
    p.add_argument('--seed', type=int, default=2026091117)
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    repeats, samples, warmup = (1, 2, 1) if a.smoke else (3, 10, 2)
    if a.smoke and a.output == BASE / 'runs':
        a.output = BASE / 'smoke'
    assert a.binary.is_file()
    a.output.mkdir(parents=True, exist_ok=True)
    binary_hash = sha(a.binary)
    frozen = read(BASE / 'inputs/target_schedule.json')
    target_schedule = {(r['case'], r['repeat']): r for r in frozen}
    config = {'schema': 1, 'seed': a.seed, 'query_routing_seed_base': 2026091103,
              'repeats': repeats, 'samples': samples, 'warmup': warmup,
              'cases_requested': a.cases, 'methods_requested': a.methods,
              'binary_sha256': binary_hash, 'script_sha256': sha(Path(__file__)),
              'frozen_target_schedule_sha256': sha(BASE / 'inputs/target_schedule.json'),
              'smoke_excluded_from_performance': a.smoke, 'timeout_seconds': a.timeout,
              'address_space_limit_bytes': 10 * 1024**3, 'GOMAXPROCS': 1,
              'statistical_unit': 'independent process mean',
              'scope': 'native 32-byte long records; serialized in-process proof pipeline; no network latency'}
    cp = a.output / 'run_configuration.json'
    if cp.exists():
        if not a.resume or read(cp) != config:
            raise RuntimeError('refusing overwrite or changed configuration')
    else:
        dump(cp, config)
    ep = a.output / 'environment.json'
    if not ep.exists():
        dump(ep, {'platform': platform.platform(), 'python': platform.python_version(),
                  'cpu': next(s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),
                  'os_release': Path('/etc/os-release').read_text(), 'memory_before': Path('/proc/meminfo').read_text(),
                  'go': subprocess.check_output(['go', 'version'], text=True).strip(),
                  'compiler': subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                  'thread_policy': 'sequential processes, GOMAXPROCS=1 and native thread controls=1'})
    inputs, hashes = {}, {}
    for name in a.cases:
        audit = read(BASE / f'inputs/{name}/cross_backend_audit.json')
        assert audit['status'] == 'pass'
        baseline = None
        for method in a.methods:
            path = BASE / f'inputs/{name}/{method}.json'
            data = read(path)
            assert sha(path) == audit['outputs'][path.name]['sha256']
            assert data['mode'] == method
            common = {k: data[k] for k in COMMON}
            common['targets'] = [{k: t[k] for k in ['id', 'slot_hex', 'value_hex', 'needed']} for t in data['targets']]
            if baseline is not None:
                assert common == baseline
            baseline = common
            inputs[name, method], hashes[name, method] = data, sha(path)
    dump(a.output / 'input_availability.json', {'available': a.cases, 'unavailable': []})
    schedule = []
    for rep in range(repeats):
        rng = random.Random(a.seed + 1009 * rep)
        order = list(a.cases)
        rng.shuffle(order)
        for name in order:
            source = target_schedule[name, rep]
            selected = source['pool_indices'][:samples]
            methods = list(a.methods)
            rng.shuffle(methods)
            for method in methods:
                targets = [inputs[name, method]['targets'][i]['id'] for i in selected]
                assert targets == source['target_ids'][:samples]
                schedule.append({'case': name, 'repeat': rep, 'method': method,
                                 'pool_indices': selected, 'target_ids': targets,
                                 'input_sha256': hashes[name, method]})
    sp = a.output / 'schedule.json'
    if sp.exists() and read(sp) != schedule:
        raise RuntimeError('schedule changed')
    dump(sp, schedule)
    env = dict(os.environ, GOMAXPROCS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    outcomes = []
    for item in schedule:
        name, method, rep = item['case'], item['method'], item['repeat']
        run = a.output / name / method / f'repeat{rep}'
        status_file = run / 'status.json'
        if status_file.exists():
            if not a.resume:
                raise RuntimeError(f'refusing overwrite: {run}')
            row = read(status_file)
            assert row['binary_sha256'] == binary_hash and row['input_source_sha256'] == item['input_sha256']
            outcomes.append(row)
            continue
        if run.exists():
            raise RuntimeError(f'partial run must be audited separately: {run}')
        run.mkdir(parents=True)
        data = inputs[name, method].copy()
        data['targets'] = [data['targets'][i] for i in item['pool_indices']]
        data['seed'] = 2026091103 + rep * 1009
        infile, outfile = run / 'input.json', run / 'result.json'
        dump(infile, data)
        command = [str(a.binary), str(infile), str(outfile), str(warmup)]
        dump(run / 'command.json', {'argv': command, 'environment_overrides': {k: env[k] for k in ['GOMAXPROCS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS']}})
        print('START', name, method, rep, flush=True)
        started, timeout = time.perf_counter(), False
        with (run / 'stdout.txt').open('w') as stdout, (run / 'stderr.txt').open('w') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, preexec_fn=bounded_child, start_new_session=True)
            try:
                code = process.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                timeout = True
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
        row = {**item, 'returncode': code, 'timeout': timeout, 'wall_seconds': time.perf_counter() - started,
               'binary_sha256': binary_hash, 'input_source_sha256': item['input_sha256'],
               'run_input_sha256': sha(infile), 'result_sha256': sha(outfile) if outfile.exists() else None,
               'status': 'complete' if code == 0 and outfile.exists() else 'failed'}
        if row['status'] == 'complete':
            result = read(outfile)
            if 'error' in result or result.get('status') != 'passed' or len(result.get('queries', [])) != samples:
                row['status'] = 'invalid_result'
        dump(status_file, row)
        outcomes.append(row)
        dump(a.output / 'process_outcomes.json', outcomes)
        print('DONE', name, method, rep, row['status'], round(row['wall_seconds'], 2), 's', flush=True)
    dump(a.output / 'completion.json', {'scheduled': len(schedule), 'completed': sum(x['status'] == 'complete' for x in outcomes),
                                      'failures': [x for x in outcomes if x['status'] != 'complete'], 'unavailable_inputs': [],
                                      'measured_target_requests': samples * sum(x['status'] == 'complete' for x in outcomes),
                                      'smoke_excluded_from_performance': a.smoke})

if __name__ == '__main__':
    main()
