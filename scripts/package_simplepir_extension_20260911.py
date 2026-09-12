"""Preserve verified SimplePIR measurements, sources and paired VBPIR evidence."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile
from restore_simplepir_run_inputs_20260911 import reconstruct

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_simplepir_extension_20260911'
OLD = ROOT / 'examples/tifs_external_extension_20260911'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    audit = json.loads((BASE / 'analysis/INDEPENDENT_VERIFICATION.json').read_text(encoding='utf8'))
    assert (audit['status'] == 'passed' and audit['complete_requested_experiment']) or (audit['status'] == 'audited_with_observed_failures' and audit['scheduled_executed_all'])
    restored = reconstruct(BASE, verify_only=True)
    archive = BASE / 'SparseTreePIR_SimplePIR双后端实验_结果与复现代码.zip'
    if archive.exists():
        raise RuntimeError('preserve existing release archive')
    files = {}
    def add(p, dest=None):
        if p.is_file():
            files[dest or p.relative_to(ROOT).as_posix()] = p
    for p in BASE.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(BASE)
        parts = rel.parts
        if p.suffix == '.zip' or any(x in parts for x in ['__pycache__', '.git', 'qa']):
            continue
        if p.name in ['SOURCE_MANIFEST.json', 'PACKAGE_CHECK.json'] or p.suffix in ['.aux', '.out']:
            continue
        if parts[0] == 'backend' and 'build' in parts:
            if p.name == 'simplepir_proof_bench':
                add(p, 'examples/tifs_simplepir_extension_20260911/backend/recorded_bin/simplepir_proof_bench')
            continue
        if parts[0] in ['runs', 'smoke'] and p.name == 'input.json':
            continue
        add(p)
    # Previous observations are frozen, not regenerated or pooled into SimplePIR.
    for sub in ['inputs', 'runs']:
        for p in (OLD / sub).rglob('*'):
            if p.is_file() and not (sub == 'runs' and p.name == 'input.json') and '__pycache__' not in p.parts:
                add(p)
    for sub in ['analysis/results.json', 'analysis/INDEPENDENT_VERIFICATION.json', 'PROTOCOL.md',
                'native_adapter/vendor/src/utils.h', 'native_adapter/README.md', 'native_adapter/source_manifest.json']:
        add(OLD / sub)
    for p in (OLD / 'native_adapter/vendor/header').rglob('*'):
        add(p)
    pending = [ROOT / 'scripts' / name for name in [
        'prepare_simplepir_extension_20260911.py', 'run_simplepir_extension_20260911.py',
        'analyze_simplepir_extension_20260911.py', 'report_simplepir_extension_20260911.py',
        'restore_simplepir_run_inputs_20260911.py', 'package_simplepir_extension_20260911.py',
        'restore_external_run_inputs_20260911.py', 'analyze_external_extension_20260911.py']]
    seen = set()
    while pending:
        p = pending.pop()
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        add(p)
        for node in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
            names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else ([n.name for n in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                local = ROOT / 'scripts' / (name.split('.')[0] + '.py')
                if local.is_file():
                    pending.append(local)
    manifest = {'schema': 1, 'payload_files': len(files),
                'measured_proofs': audit['measured_proofs_verified'],
                'deduplicated_inputs_verified': restored,
                'omission': 'per-run input copies in runs/smoke are byte-exactly restorable from canonical inputs and schedule; no measured result omitted',
                'sha256': {name: sha(p.read_bytes()) for name, p in sorted(files.items())}}
    raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    (BASE / 'SOURCE_MANIFEST.json').write_bytes(raw)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, p in sorted(files.items()):
            z.write(p, name)
        z.writestr('SOURCE_MANIFEST.json', raw)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, digest in manifest['sha256'].items():
            assert sha(z.read(name)) == digest, name
    check = {'status': 'passed', 'archive': archive.name, 'bytes': archive.stat().st_size,
             'sha256': sha(archive.read_bytes()), 'payload_files_hash_checked': len(files),
             'run_inputs_restore_verified': restored, 'independent_measured_proofs_verified': audit['measured_proofs_verified']}
    (BASE / 'PACKAGE_CHECK.json').write_text(json.dumps(check, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    print(json.dumps(check, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
