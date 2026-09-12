"""Copy the local official SimplePIR source into this new, isolated adapter."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

here = Path(__file__).resolve().parent
repo = here.parents[2]
source = repo / '.tools/simplepir/simplepir-main'
dest = here / 'upstream/simplepir'
dest.mkdir(parents=True, exist_ok=True)
files = [source / 'go.mod'] + sorted((source / 'pir').glob('*'))
files += [p for p in source.glob('LICENSE*') if p.is_file()]
entries = []
for src in files:
    if not src.is_file():
        continue
    relative = src.relative_to(source)
    dst = dest / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    assert digest == hashlib.sha256(dst.read_bytes()).hexdigest()
    entries.append({'path': relative.as_posix(), 'sha256': digest})
commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--', 'pir', 'go.mod'], text=True).strip()
manifest = {'official_repository': 'https://github.com/ahenzinger/simplepir', 'commit': commit,
            'source_status_pir_and_go_mod': status, 'source': str(source),
            'copied_unmodified': True, 'files': entries,
            'adapter_scope': 'Real Init/Setup/Query/Answer; standard vertical 256-bit input/recovery width wrapper; actual matrix frames and local proof pipeline.'}
(here / 'source_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'copied', 'commit': commit, 'files': len(entries), 'source_dirty': bool(status)}))
