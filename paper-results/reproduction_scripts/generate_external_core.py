"""Build manuscript figures/tables from frozen, independently verified cohorts."""
from pathlib import Path
import json
import hashlib
import statistics
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).absolute().parents[1]
ROOT = BASE.parent
CASES = ['uniform_n1000', 'uniform_n10000', 'uniform_n100000']
SOURCES = {'SimplePIR': ROOT / 'examples/tifs_simplepir_extension_20260911',
           'VBPIR': ROOT / 'examples/tifs_external_extension_20260911'}

def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def fmt(x): return f'{x:.2f}'

def main():
    # Derive displayed plot citations from the main bibliography, never hardcode.
    bibkeys = re.findall(r'\\bibitem\{([^}]+)\}', (BASE/'references.tex').read_text(encoding='utf-8-sig'))
    bibnums = {key: i+1 for i,key in enumerate(bibkeys)}
    backend_keys = {'SimplePIR': 'simplepir', 'VBPIR': 'vectorbatchpir'}
    # Packaged manuscripts carry frozen summaries so regeneration does not need
    # the original workspace. Raw observations remain in their separate archive.
    snapshots = BASE / 'verification/frozen_evidence'
    snapshots.mkdir(parents=True, exist_ok=True)
    data = {}
    provenance = {}
    for backend, source in SOURCES.items():
        canonical = source / 'analysis/results.json'
        local = snapshots / (backend.lower() + '_results.json')
        if canonical.exists():
            raw = canonical.read_bytes()
            if local.exists(): assert local.read_bytes() == raw
            else: local.write_bytes(raw)
        data[backend] = read(local)
        provenance[backend] = {'results_sha256': sha(local), 'original_source': 'examples/' + source.name}
    by = {b: {(r['case'], r['method']): r for r in d['aggregates']} for b,d in data.items()}
    for b in by:
        for c in CASES:
            for m in ['ab', 'pbc']:
                assert by[b][c,m]['processes'] == 3
                assert by[b][c,m]['complete_planned_repeats']
    def metric(b,c,m,k): return by[b][c,m][k+'_mean']
    def mean_sd(b,c,m,k):
        r=by[b][c,m]
        return f"${r[k+'_mean']:.2f}\\pm {r[k+'_sd']:.2f}$"
    rows=[]
    for backend in ['SimplePIR','VBPIR']:
        for c,n in zip(CASES,[1000,10000,100000]):
            cited_backend = backend + r'~\cite{' + backend_keys[backend] + '}'
            rows.append(f"{cited_backend} & {n:,} & {mean_sd(backend,c,'ab','serialized_proof_wall_ms')} & {mean_sd(backend,c,'pbc','serialized_proof_wall_ms')} & {metric(backend,c,'ab','online_framed_bytes')/1024:.2f} & {metric(backend,c,'pbc','online_framed_bytes')/1024:.2f} \\\\")
        rows.append(r'\addlinespace')
    text=r'''\begin{table*}[t]
\centering\small
\caption{Private retrieval of one sparse Merkle proof on identical uniform-key snapshots. AB is our layout; PBC follows the batch-code construction of Angel et al.~\cite{sealpir}, with three-choice placement from the VBPIR implementation~\cite{vectorbatchpir}. Processing time includes routing, cryptographic operations, serialization/deserialization, proof reconstruction, and root verification in one process. Values are mean $\pm$ sample SD of three independent process means; each process measures ten paired targets. Online traffic includes actual message framing. Backend comparisons are made within each row.}
\label{tab:external-core}
\setlength{\tabcolsep}{8pt}
\begin{tabular}{llrrrr}\toprule
 & & \multicolumn{2}{c}{Proof processing (ms)} & \multicolumn{2}{c}{Online traffic (KiB)}\\
Backend & Occupied leaves & AB (ours) & PBC~\cite{sealpir} & AB (ours) & PBC~\cite{sealpir}\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}
\end{table*}
'''
    (BASE / 'generated/main_external_summary.tex').write_text(text,encoding='utf8')
    rows=[]
    ablation=[]
    for c,n in zip(CASES,[1000,10000,100000]):
        ab,ff=by['SimplePIR'][c,'ab'],by['SimplePIR'][c,'first_fit']
        paired=next(r for r in data['SimplePIR']['comparisons'] if r['case']==c and r['comparator']=='first_fit')
        row={'leaves':n,'ff_capacity':ff['max_bucket'],'ab_capacity':ab['max_bucket'],
             'capacity_ratio':ff['max_bucket']/ab['max_bucket'],
             'paired_time_ratio':paired['comparator_over_ab_latency_mean'],
             'traffic_ratio':paired['online_framed_bytes_comparator_over_ab']}
        ablation.append(row)
        rows.append(f"{n:,} & {row['ff_capacity']:,} & {row['ab_capacity']:,} & {row['paired_time_ratio']:.2f} & {row['traffic_ratio']:.2f} \\\\")
    text=r'''\begin{table}[t]
\centering\footnotesize
\caption{Effect of balancing under native 32-byte SimplePIR~\cite{simplepir}. AB is ours; First-fit (FF) is an internal control. Both colorings use the same minimum batch width. $U$ is the largest bucket; time ratios average the three paired process ratios. Ratios above one favor AB.}
\label{tab:native-ablation}
\setlength{\tabcolsep}{3.2pt}
\begin{tabular}{rrrrr}\toprule
Leaves & $U_{\rm FF}$ & $U_{\rm AB}$ & Time FF/AB & Bytes FF/AB\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}
\end{table}
'''
    (BASE / 'generated/main_native_ablation.tex').write_text(text,encoding='utf8')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,
                         'legend.fontsize':9,'pdf.fonttype':42,'ps.fonttype':42,
                         'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(7.1,4.9))
    for i,backend in enumerate(['SimplePIR','VBPIR']):
        for j,(key,unit,ylabel) in enumerate([('serialized_proof_wall_ms',1,'Proof processing (ms)'),('online_framed_bytes',1024,'Online traffic (KiB)')]):
            ax=axes[i,j]
            for method,color,marker in [('ab','#0072B2','o'),('pbc','#D55E00','s')]:
                rr=[by[backend][c,method] for c in CASES]
                ax.errorbar([1000,10000,100000],[r[key+'_mean']/unit for r in rr],
                            yerr=[r[key+'_sd']/unit for r in rr],label='SparseTreePIR (AB, ours)' if method=='ab' else f'PBC [{bibnums["sealpir"]}]',
                            color=color,marker=marker,markerfacecolor='none',
                            markersize=7 if method=='ab' else 3.5,markeredgewidth=1.1,
                            linestyle='-' if method=='ab' else (0,(4,3)),
                            linewidth=1.4,capsize=3,zorder=3 if method=='ab' else 4)
            ymax=max((by[backend][c,m][key+'_mean']+by[backend][c,m][key+'_sd'])/unit
                     for c in CASES for m in ['ab','pbc'])
            ax.set_xscale('log');ax.set_ylim(0,ymax*1.12);ax.set_xlabel('Occupied leaves');ax.set_ylabel(ylabel)
            ax.set_title(f'({"abcd"[2*i+j]}) {backend} [{bibnums[backend_keys[backend]]}]',fontsize=9)
            ax.grid(alpha=.2)
            if backend=='VBPIR' and j==1:
                ax.text(.5,.45,'Identical online traffic\n(overlapping curves)',transform=ax.transAxes,
                        ha='center',fontsize=8,color='#444444')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',ncol=2,frameon=False,bbox_to_anchor=(.5,1.005))
    fig.tight_layout(rect=(0,0,1,.94),h_pad=1.4,w_pad=2)
    for ext in ['pdf','png']:fig.savefig(BASE/f'figures/sp_external_scaling.{ext}',dpi=260,bbox_inches='tight')
    plt.close(fig)
    cohorts=[]
    for backend,case_list,methods in [('SimplePIR',CASES,['ab','pbc','flat','first_fit']),('VBPIR',CASES,['ab','pbc']),('VBPIR',['complete_h10','complete_h14'],['ab','pbc','treepir'])]:
        records=[r for r in data[backend]['process_means'] if r['case'] in case_list and r['method'] in methods]
        assert len(records)==len(case_list)*len(methods)*3
        cohorts.append({'backend':backend,'cases':case_list,'methods':methods,'processes':len(records),'measured_proofs':10*len(records)})
    report={'reported_scope':'Uniform-key scaling and complete-tree controls. This manuscript selection does not redefine the original full experimental schedule or assert success of all exploratory runs.',
            'cohorts':cohorts,'reported_processes':sum(x['processes'] for x in cohorts),
            'reported_measured_proofs':sum(x['measured_proofs'] for x in cohorts),
            'reported_warmup_proofs':2*sum(x['processes'] for x in cohorts),
            'sources':provenance,'ablation':ablation,'script_sha256':sha(Path(__file__))}
    (BASE/'verification/PRIMARY_EVIDENCE_SELECTION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
