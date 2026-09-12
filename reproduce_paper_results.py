"""Regenerate current numeric paper outputs in a new isolated directory."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys

ROOT=Path(__file__).absolute().parent
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.expanduser().resolve()
    root=ROOT.resolve()
    protected=[root/name for name in ['examples','scripts','paper-results','reproduce','docs','datasets','backend','provenance']]
    if out==root or out in root.parents or any(out==p or p in out.parents for p in protected):
        parser.error('Output must be outside the checked-in evidence and source directories.')
    if out.exists():parser.error('Use a new output directory; existing paths are not overwritten.')
    shutil.copytree(ROOT/'paper-results',out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for script in ['generate_external_core.py','build_external_supplement_table.py','check_worked_batch_example.py']:
        subprocess.run([sys.executable,str(out/'reproduction_scripts'/script)],cwd=out,check=True)
    outputs=['generated/main_external_summary.tex','generated/main_native_ablation.tex',
             'generated/external_initialization_rows.tex','reproduction_scripts/external_initialization_values.csv']
    for name in outputs:
        if digest(out/name)!=digest(ROOT/'paper-results'/name):raise ValueError('Numeric output mismatch: '+name)
    result={'status':'passed','regenerated_numeric_files':outputs,
            'figure':'figures/sp_external_scaling.pdf','new_benchmark_executed':False,
            'note':'Rendering hashes may vary across Matplotlib/font versions; table numerical source bytes must match.'}
    (out/'PAPER_RESULTS_CHECK.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
