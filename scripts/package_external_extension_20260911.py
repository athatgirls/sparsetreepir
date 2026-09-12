"""Package verified data and source, deduplicating byte-reconstructible run inputs."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_external_extension_20260911'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    audit = json.loads((BASE / 'analysis/INDEPENDENT_VERIFICATION.json').read_text(encoding='utf8'))
    assert audit['status'] == 'passed' and audit['complete_requested_experiment']
    archive = BASE / 'SparseTreePIR_新增外部实验_结果图表与复现代码.zip'
    if archive.exists():
        raise RuntimeError('preserve existing release archive')
    readme = '''# SparseTreePIR external evaluation — 11 September 2026

48 independent processes / 480 measured proofs / 576 proofs including warmups.
All are independently verified. The experiment is a common-backend, in-process
serialized proof pipeline, with no network timing claim. It is not a reproduction
of either complete published system. The immutable manuscript release is unchanged.

Start with `examples/tifs_external_extension_20260911/analysis/external_evaluation_brief.pdf`
or the Chinese report beside it. Full tables, SVG-independent vector PDF figures,
paired differences, per-query output and limitations are included. The ready-to-insert
LaTeX subsection is also included. No repeated measurements were added for significance.

## Reconstruct and independently verify raw run inputs

The package omits only repeated `runs/.../input.json` and `smoke/.../input.json`
copies. Each is exactly reconstructed from its frozen case snapshot, selected
target indices and seed. Restoration checks the SHA-256 originally recorded
before execution; it does not regenerate experimental results.

From the unpacked project root, use Python 3.12 or newer:

    python3 scripts/restore_external_run_inputs_20260911.py
    python3 scripts/analyze_external_extension_20260911.py

The independent verifier checks actual recovered digests and original proof levels,
recomputes authentication roots, checks three negative cases, paired targets and
parameters, excludes warmups, and verifies constant envelope shapes. It rejects
mispaired results. A failed or incomplete study cannot be labelled fully passed.

## Build the common native adapter and run a fresh repetition

The captured Ubuntu environment uses GCC 13.3, SEAL 4.3.2 and OpenSSL 3.0.13.
With matching dependencies installed, compile the included pinned vendor source:

    cmake -S examples/tifs_external_extension_20260911/native_adapter -B examples/tifs_external_extension_20260911/native_adapter/build
    cmake --build examples/tifs_external_extension_20260911/native_adapter/build --parallel 2
    python3 scripts/run_external_extension_20260911.py --output examples/tifs_external_extension_20260911/rerun

The executable used for the recorded experiment is preserved separately in
`native_adapter/recorded_bin/serialized_proof_bench`. Compiler outputs and caches
are omitted. The captured raw runs are never overwritten by the runner.
The native adapter's three cryptographic .cpp files match the upstream TreePIR
VBPIR_PBC source. Header-only observation getters and the application adapter are
documented in `native_adapter/source_manifest.json` and `native_adapter/README.md`.
The upstream source-copy preparation script expects the original wider repository;
it is unnecessary for building the already verified vendor files in this archive.

## Other evidence

All seven frozen inputs, complete-tree CSA/SubCSA outputs, generation source,
original Java sources, source hashes, raw commands, timing observations and
environment records are preserved. Rendering figures needs matplotlib; regenerating
the PDF brief also needs a LaTeX installation. The Respire directory contains only
its separately labelled source/interface feasibility evidence, including the
original debug failure and the successful 32-byte release-mode single-record test.
It is not part of the 480-proof VBPIR comparison.

`SOURCE_MANIFEST.json` lists every payload file's SHA-256. The archive is checked
after writing. Large repeated run inputs are intentionally deduplicated, not lost.
'''
    (BASE / 'README.md').write_text(readme, encoding='utf8')
    files = {}

    def add(path, dest=None):
        if path.is_file():
            files[dest or path.relative_to(ROOT).as_posix()] = path

    for p in BASE.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(BASE)
        parts = rel.parts
        if p.suffix == '.zip' or '__pycache__' in parts or '.git' in parts or 'qa' in parts or 'java_build' in parts:
            continue
        if parts[0] == 'respire' and any(x in parts for x in ['build-check', 'target']):
            continue
        if parts[0] == 'native_adapter' and 'build' in parts:
            if p.name == 'serialized_proof_bench':
                add(p, 'examples/tifs_external_extension_20260911/native_adapter/recorded_bin/serialized_proof_bench')
            continue
        if parts[0] in ['runs', 'smoke'] and p.name == 'input.json':
            continue
        if p.name in ['SOURCE_MANIFEST.json', 'PACKAGE_CHECK.json'] or p.suffix in ['.aux', '.out', '.synctex.gz']:
            continue
        add(p)
    # All transitively imported local Python modules needed by the entry points.
    pending = [ROOT / 'scripts' / n for n in ['prepare_external_extension_20260911.py',
               'run_external_extension_20260911.py', 'analyze_external_extension_20260911.py',
               'report_external_extension_20260911.py', 'restore_external_run_inputs_20260911.py',
               'package_external_extension_20260911.py']]
    seen = set()
    while pending:
        p = pending.pop()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        add(p)
        tree = ast.parse(p.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else ([n.name for n in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                candidate = ROOT / 'scripts' / (name.split('.')[0] + '.py')
                if candidate.exists():
                    pending.append(candidate)
    for name in ['contribution_gate_csa_20260910.java', 'contribution_gate_index_20260910.java']:
        add(ROOT / 'scripts' / name)
    official = ROOT / 'examples/tifs_contribution_gate_20260910/external/official_sources'
    for name in ['CSA/src/CSA.java', 'CSA/src/MerkleTrees.java', 'CSA/gson-2.10.1.jar', 'TreePIR-Indexing/src/SubCSA.java']:
        add(official / name)
    for name in ['official_csa.tsv', 'official_index.tsv']:
        add(ROOT / 'examples/tifs_contribution_gate_20260910/external/complete_h10' / name)
    add(ROOT / 'external/TreePIR-main/LICENSE', 'examples/tifs_external_extension_20260911/native_adapter/vendor/UPSTREAM_LICENSE')
    manifest = {'schema': 1, 'payload_files': len(files), 'measured_processes': 48, 'measured_proofs': 480,
                'omission': '53 redundant per-run input.json files are byte-exactly reconstructible from frozen snapshots and schedules',
                'sha256': {name: sha(path.read_bytes()) for name, path in sorted(files.items())}}
    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode('utf8')
    (BASE / 'SOURCE_MANIFEST.json').write_bytes(manifest_bytes)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, path in sorted(files.items()):
            z.write(path, name)
        z.writestr('SOURCE_MANIFEST.json', manifest_bytes)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, digest in manifest['sha256'].items():
            assert sha(z.read(name)) == digest, name
    check = {'status': 'passed', 'archive': archive.name, 'bytes': archive.stat().st_size,
             'sha256': sha(archive.read_bytes()), 'payload_files_hash_checked': len(files),
             'redundant_inputs_restore_verified': 53,
             'independent_measured_proofs_verified': audit['measured_proofs_verified']}
    (BASE / 'PACKAGE_CHECK.json').write_text(json.dumps(check, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    print(json.dumps(check, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
