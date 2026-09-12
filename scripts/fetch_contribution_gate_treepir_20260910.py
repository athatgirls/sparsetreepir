"""Pin a small source subset from the public official TreePIR commit."""
from pathlib import Path
import concurrent.futures, hashlib, json, urllib.request
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'
COMMIT='930063c5aefc441244abb4890fdf35383f3aa956'
FILES=['README.md','TreePIR-Indexing/src/SubCSA.java','CSA/src/CSA.java','CSA/src/MerkleTrees.java',
       'CSA/gson-2.10.1.jar','VBPIR_TreePIR/src/main.cpp','VBPIR_TreePIR/src/batchpirserver.cpp',
       'VBPIR_TreePIR/CMakeLists.txt','SealPIRplus/pirmessage_client.cpp',
       'SealPIRplus/pirmessage_server.cpp','SealPIRplus/CMakeLists.txt','SealPIR-Orchestrator/orchestrator.py']
def fetch(name):
    url=f'https://raw.githubusercontent.com/PIR-PIXR/TreePIR/{COMMIT}/{name}'
    target=OUT/'official_sources'/name
    if target.exists():data=target.read_bytes()
    else:
        data=urllib.request.urlopen(url,timeout=45).read();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    local=ROOT/'external/TreePIR-main'/name
    return name,{'url':url,'sha256':hashlib.sha256(data).hexdigest(),
                 'same_as_historical_local_copy':local.exists() and local.read_bytes()==data}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=dict(pool.map(fetch,FILES))
    report={'repository':'https://github.com/PIR-PIXR/TreePIR','commit':COMMIT,
            'pin_obtained_by':'git ls-remote HEAD refs/heads/main, 2026-09-11','files':results}
    (OUT/'official_source_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'files':len(results),'all_identical_to_local':all(r['same_as_historical_local_copy'] for r in results.values())}))
if __name__=='__main__':main()
