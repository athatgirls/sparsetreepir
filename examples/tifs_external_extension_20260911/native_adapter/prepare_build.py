"""Copy pinned official VBPIR core into this adapter, then optionally build."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = '930063c5aefc441244abb4890fdf35383f3aa956'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    args = ap.parse_args()
    src = ROOT / 'external/TreePIR-main/VBPIR_PBC'
    git = json.loads((ROOT / 'examples/tifs_contribution_gate_20260910/external/official_git_tree.json').read_text())
    entries = {x['path']: x for x in git['tree']}
    vendor = HERE / 'vendor'
    pins = {}
    names = ['src/client.cpp','src/server.cpp','src/pirparams.cpp','src/utils.h',
             'header/client.h','header/server.h','header/pirparams.h','header/database_constants.h']
    for name in names:
        data = (src/name).read_bytes()
        key = 'VBPIR_PBC/'+name
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if key in entries:
            assert blob == entries[key]['sha'], key
        else:
            raise RuntimeError('Missing pinned source: '+key)
        dest = vendor/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        pins[key] = {'git_blob':blob,'sha256':hashlib.sha256(data).hexdigest()}
    # Observational getter only: the encryption/answer/decode implementations stay byte-identical.
    h = vendor/'header/server.h'
    content = h.read_text()
    content = content.replace('private:\n', '''public:
    size_t audit_ntt_coefficient_bytes() const {
        size_t n=0; for(const auto& p: encoded_db_) n += p.coeff_count()*sizeof(uint64_t); return n;
    }
    size_t audit_ntt_plaintext_count() const { return encoded_db_.size(); }
    size_t audit_raw_padded_bytes() const {
        size_t n=0; for(const auto& db: rawdb_list_) for(const auto& row: db) n += row.size(); return n;
    }
private:
''', 1)
    h.write_text(content)
    const = vendor/'header/database_constants.h'
    const.write_text(const.read_text().replace('#include <limits>', '#include <limits>\n#include <cstdint>'))
    rapid = ROOT/'external/TreePIR-main/VBPIR_PBC/rapidjson'
    if not rapid.exists():
        rapid = ROOT/'external/TreePIR-main/VBPIR_TreePIR/rapidjson'
    shutil.copytree(rapid, vendor/'rapidjson', dirs_exist_ok=True)
    manifest = {'commit':COMMIT,'official_repo':'https://github.com/PIR-PIXR/TreePIR',
                'original_files':pins,'adaptations':['server.h observational NTT/raw getters',
                'database_constants.h missing cstdint include','common driver replaces complete-tree I/O and metrics',
                'PBC three-candidate hash and recursive cuckoo routing copied with per-query reset and fixed experiment RNG seed'],
                'crypto_cpp_unchanged':['src/client.cpp','src/server.cpp','src/pirparams.cpp'],
                'copied_sha256':{str(p.relative_to(vendor)):hashlib.sha256(p.read_bytes()).hexdigest() for p in vendor.rglob('*') if p.is_file()}}
    (HERE/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if args.build:
        for label,cmd in [('configure',['cmake','-S',str(HERE),'-B',str(HERE/'build')]),
                          ('build',['cmake','--build',str(HERE/'build'),'--parallel','2'])]:
            p=subprocess.run(cmd,capture_output=True,text=True,env=dict(os.environ,OMP_NUM_THREADS='1'),timeout=180)
            (HERE/(label+'_log.json')).write_text(json.dumps({'command':cmd,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n')
            print(p.stdout[-4000:],p.stderr[-4000:],flush=True)
            if p.returncode: raise SystemExit(p.returncode)
    print(json.dumps({'status':'built' if args.build else 'prepared','directory':str(HERE)}))

if __name__ == '__main__': main()
