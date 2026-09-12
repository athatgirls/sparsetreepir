"""Verify every distributed payload against the publication manifest."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).absolute().parent
def main():
    manifest=json.loads((ROOT/'RELEASE_MANIFEST.json').read_text(encoding='utf8'))
    failures=[]
    for row in manifest['files']:
        path=ROOT/row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            failures.append(row['path'])
    if failures:raise SystemExit('Release checksum mismatch: '+repr(failures))
    print(json.dumps({'release':manifest['release'],'files_verified':len(manifest['files']),'status':'passed'},indent=2))
if __name__=='__main__':main()
