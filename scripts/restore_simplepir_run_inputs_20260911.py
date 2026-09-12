"""Restore exact per-run inputs from immutable snapshots and the recorded schedule."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_simplepir_extension_20260911'


def reconstruct(base, verify_only=False):
    checked = 0
    for run_name in ['runs', 'smoke']:
        directory = base / run_name
        if not directory.is_dir():
            continue
        config = json.loads((directory / 'run_configuration.json').read_text(encoding='utf8'))
        schedule = json.loads((directory / 'schedule.json').read_text(encoding='utf8'))
        cache = {}
        for item in schedule:
            case, method, rep = item['case'], item['method'], item['repeat']
            status_path = directory / case / method / f'repeat{rep}/status.json'
            if not status_path.exists():
                continue
            status = json.loads(status_path.read_text(encoding='utf8'))
            key = (case, method)
            if key not in cache:
                source = base / 'inputs' / case / (method + '.json')
                raw = source.read_bytes()
                assert hashlib.sha256(raw).hexdigest() == item['input_sha256']
                cache[key] = json.loads(raw)
            data = cache[key].copy()
            data['targets'] = [data['targets'][i] for i in item['pool_indices']]
            data['seed'] = config['query_routing_seed_base'] + rep * 1009
            raw = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf8')
            assert hashlib.sha256(raw).hexdigest() == status['run_input_sha256'], (case, method, rep)
            dest = status_path.with_name('input.json')
            if dest.exists():
                assert hashlib.sha256(dest.read_bytes()).hexdigest() == status['run_input_sha256']
            elif not verify_only:
                dest.write_bytes(raw)
            checked += 1
    return checked


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, default=BASE)
    ap.add_argument('--verify-only', action='store_true')
    args = ap.parse_args()
    print(json.dumps({'run_inputs_exactly_reconstructed': reconstruct(args.base, args.verify_only), 'verify_only': args.verify_only}))

