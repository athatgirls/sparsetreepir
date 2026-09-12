"""Verified source copy + narrow portable-path/build adapter of official VBPIR."""
from pathlib import Path
import hashlib,json,shutil,subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'
COMMIT='930063c5aefc441244abb4890fdf35383f3aa956'
def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def main():
    path=OUT/'official_git_tree.json'
    if not path.exists():
        req=urllib.request.Request(f'https://api.github.com/repos/PIR-PIXR/TreePIR/git/trees/{COMMIT}?recursive=1',headers={'User-Agent':'academic-reproducibility-audit'})
        path.write_bytes(urllib.request.urlopen(req,timeout=45).read())
    git=json.loads(path.read_text());assert not git.get('truncated');entries={e['path']:e for e in git['tree']}
    base=OUT/'native_vbpir';source=base/'source';pins={}
    for name,e in entries.items():
        if not name.startswith('VBPIR_TreePIR/') or e['type']!='blob':continue
        relative=name.split('/',1)[1]
        if not (relative.startswith(('src/','header/','rapidjson/')) or relative in ('CMakeLists.txt','LICENSE')):continue
        local=ROOT/'external/TreePIR-main'/name;data=local.read_bytes()
        assert blob(data)==e['sha'],name
        target=source/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        pins[name]={'git_blob_sha1':e['sha'],'sha256':hashlib.sha256(data).hexdigest()}
    # Only portability edits. Algorithmic source remains the official implementation.
    cm=source/'CMakeLists.txt';s=cm.read_text().replace('CXX_STANDARD 11','CXX_STANDARD 17').replace('find_package(SEAL 4.0 REQUIRED)','find_package(SEAL CONFIG REQUIRED)')
    cm.write_text(s)
    edits={str(cm.relative_to(OUT)):'C++17; resolve installed SEAL CONFIG package (version recorded in configure log).'}
    constants=source/'header/database_constants.h'
    constants.write_text(constants.read_text().replace('#include <limits>','#include <limits>\n#include <cstdint>'))
    edits[str(constants.relative_to(OUT))]='Add missing standard <cstdint> include required for uint64_t on this compiler.'
    for name in ['main.cpp','batchpirserver.cpp']:
        p=source/'src'/name;s=p.read_text();prefix='/home/quang/Desktop/PIR-CSA/VBPIR_CSA/'
        assert prefix in s
        s='#include <cstdlib>\n'+s.replace('"'+prefix,'std::string(std::getenv("TREEPIR_INPUT_DIR")) + "/')
        p.write_text(s);edits[str(p.relative_to(OUT))]='Hard-coded input-directory string replaced by TREEPIR_INPUT_DIR environment variable; query/recovery/timing logic unchanged.'
    base.mkdir(parents=True,exist_ok=True)
    (base/'source_derivation.json').write_text(json.dumps({'commit':COMMIT,'verified_original_files':pins,'adapter_edits':edits,
           'adapted_source_sha256':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}},indent=2)+'\n')
    for label,cmd in [('configure',['cmake','-S',str(source),'-B',str(base/'build')]),('build',['cmake','--build',str(base/'build'),'--parallel','2'])]:
        previous=base/f'{label}_log.json'
        if previous.exists():
            attempt=1
            while (base/f'{label}_attempt{attempt}.json').exists():attempt+=1
            shutil.copy2(previous,base/f'{label}_attempt{attempt}.json')
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (base/f'{label}_log.json').write_text(json.dumps({'command':cmd,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr},indent=2)+'\n')
        print(label,proc.returncode,proc.stdout[-1200:],proc.stderr[-1200:],flush=True)
        if proc.returncode:raise SystemExit(proc.returncode)
if __name__=='__main__':main()
