"""Read frozen Fuel TCP runs; generate process-mean CIs, report, TeX and plots."""
from pathlib import Path
import hashlib,json,math,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_layout_transfer_20260910/system';RUN=OUT/'runs'
METHODS=['first_fit','activebalance','opt_witness22','full_cache'];NAMES=['First-fit','AB','OPT witness','Full-cache']
TC=2.7764451051977987

def main():
    source=RUN/'summary.json';s=json.loads(source.read_text());audit=json.loads((OUT/'independent_raw_audit.json').read_text());g=s['groups'];report={}
    for method in METHODS:
        report[method]={}
        for key,value in g[method].items():
            delta=TC*value['sample_sd']/math.sqrt(value['runs'])
            report[method][key]={'mean':value['mean'],'sample_sd':value['sample_sd'],'95pct_t_interval':[value['mean']-delta,value['mean']+delta],'process_pairs':value['runs']}
    output={'statistical_unit':'five independent paired client/server process means, 100 measured targets each; 95% Student-t intervals df=4, descriptive for this fixed snapshot',
            'methods':report,'paired_E2E_differences':audit['paired_E2E_analysis'],'summary_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    (OUT/'process_mean_CIs.json').write_text(json.dumps(output,indent=2)+'\n')
    def mean(m,k):return g[m][k]['mean']
    assert [mean(m,'mean_online_wire_bytes') for m in METHODS]==[8640,9536,9536,0]
    assert mean('opt_witness22','bootstrap_total_wire_bytes')-mean('activebalance','bootstrap_total_wire_bytes')==32768
    assert mean('opt_witness22','shared_A_matrix_bytes')-mean('activebalance','shared_A_matrix_bytes')==32768
    lines=['# Frozen Fuel layout transfer to TCP SimplePIR','',
      'A max-bucket improvement does not automatically reduce real PIR cost. The separate capacity-22 witness lowers U from the frozen AB value 23 to the proven optimum 22, but both layouts transmit exactly 9,536 online application bytes per proof. The witness needs 32,768 more bootstrap bytes. Its paired timing interval includes zero improvement. First-fit uses fewer online/bootstrap bytes, and full caching dominates this small fixed snapshot.','',
      '## Exact comparison and security/interface scope','',
      'All methods use the same 100 occupied slots, height 128, 198 original 32-byte sibling digests, deterministic experimental leaf values, and root 283ea1495be5cd0619e21c176a986dab657f1b29ecf35d8309e94cb1f9599ecb. First-fit and AB binary directories are byte-for-byte identical to the old frozen layouts. The new witness layout is checked against every original positional record and every target. It is an independent exact feasible assignment, **not** AB, the small-palette recoloring prototype, or a timed scalable construction.','',
      'The prior TCP client only accepted raw CT records and derived slots from their hashes. Applying it unchanged would rekey Fuel and violate this experiment. A new derived Go file therefore accepts an already-known 16-byte slot and 32-byte value; the client receives only these selected inputs and the pinned root locally. All public lookup and PIR state arrives through TCP. The original backend file is preserved. Query/Answer/Recover, eight independent 32-bit chunks per digest, serialization, timing boundaries, and PickParams(records,32,1024,32) are retained.','',
      'The measured parameters use lattice dimension 1024, logq=32, sigma=6.4 and plaintext modulus 991. There are nine logical PIR slots / 72 chunk calls for all three PIR layouts. The server enforces a fixed batch size, and unused slots use valid dummy queries. This is a loopback, fixed-snapshot, known-value membership experiment, not a native Fuel service, hidden-occupancy protocol, or certificate application.','',
      '## Five paired process means','',
      'Each repeat starts a fresh server and client process, uses one persistent loopback TCP connection, excludes five warmups, and measures all 100 distinct targets in a new deterministic shuffled order. The same target order is used by every method; method order is separately shuffled. All 20 process pairs run serially with GOMAXPROCS=1 on the recorded WSL environment. CIs below use the five process means, not 500 target observations.','',
      '| Layout | U | Query ms | Server ms | Recover ms | E2E ms | 95% CI for E2E mean | Upload / download bytes |',
      '|---|---:|---:|---:|---:|---:|---|---:|']
    for m,name in zip(METHODS,NAMES):
        ci=report[m]['mean_e2e_ms']['95pct_t_interval']
        lines.append(f'| {name} | {int(mean(m,"max_bucket"))} | {mean(m,"mean_query_ms"):.6f} | {mean(m,"mean_server_answer_ms"):.6f} | {mean(m,"mean_recover_ms"):.6f} | {mean(m,"mean_e2e_ms"):.6f} | [{ci[0]:.6f}, {ci[1]:.6f}] | {int(mean(m,"mean_upload_wire_bytes"))} / {int(mean(m,"mean_download_wire_bytes"))} |')
    lines+=['','Full-cache U=198 denotes the cached payload database, not a 198-record PIR query; it has zero online queries. All timing components and CIs are retained in process_mean_CIs.json.','',
      '| Layout | Bootstrap bytes | Bootstrap ms | Metadata + slots bytes | Hint bytes | Expanded A bytes | Client peak RSS MiB | Server peak RSS MiB |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for m,name in zip(METHODS,NAMES):lines.append(f'| {name} | {int(mean(m,"bootstrap_total_wire_bytes"))} | {mean(m,"bootstrap_ms"):.6f} | {int(mean(m,"metadata_bytes"))} + {int(mean(m,"slots_bytes"))} | {int(mean(m,"hint_matrix_bytes"))} | {int(mean(m,"shared_A_matrix_bytes"))} | {mean(m,"client_peak_rss_bytes")/2**20:.3f} | {mean(m,"server_peak_rss_bytes")/2**20:.3f} |')
    lines+=['','Bootstrap includes actual serialized directory, occupied slots, Params/DBinfo, full public A, hints or the full cache, plus framing. Full-cache sends 6,336 digest payload bytes and has 12,830 total bootstrap bytes. RSS values are means of five separate process peaks from Linux VmHWM; they are not isolated logical client-state sizes. The full per-process values and CIs are available.','',
      '## Why the capacity gain does not become a bandwidth gain','',
      'The AB loads are (23,22,22,21,22,22,22,22,22); the witness has nine loads of 22. A 23-record and a 22-record chunk both select L=12, M=8. The 21-record AB bucket uses L=12, M=7; making it 22 changes its M to 8. SimplePIR pads query length to a multiple of DBinfo.Squishing=3, so both M=7 and M=8 send a 9-element query. Answers have the same L=12. Consequently upload and download shapes are identical between AB and the witness.','',
      'Expanded A is not padded in the same way: changing M=7 to M=8 adds 8 × 1024 × 4 = 32,768 bytes. Hint dimensions do not change. The server output records each color/chunk Params and DBinfo; the independent auditor derives exact query/answer wire bytes from those dimensions and verifies the socket counters.','',
      'Paired timing comparisons (baseline minus witness, positive favors witness):']
    for key,name in [('first_fit','First-fit'),('activebalance','AB')]:
        p=audit['paired_E2E_analysis'][key];ci=p['paired_difference_95pct_t_interval_ms'];lines.append(f'- {name}: mean difference {p["paired_E2E_difference_ms_mean"]:.6f} ms; 95% interval [{ci[0]:.6f}, {ci[1]:.6f}] ms. Mean of paired E2E ratios = {p["paired_E2E_ratio_mean"]:.6f}.')
    lines+=['','Both intervals contain zero. These five paired runs do not establish a reliable latency advantage of the exact witness. This does not prove equality or exclude smaller effects; bytes and matrix sizes, unlike timing, are deterministic here. The experiment supports a narrow negative result: optimizing U alone can leave online cost unchanged and increase initialization state.','',
      '## Accounting and reproduction','',
      'Warm E2E continuously includes known-value hex decoding, public-directory routing, query generation, serialization, actual loopback request/response, server Answer, Recover, proof assembly and root verification. Bootstrap, process launch, earlier publisher/server setup, and post-timing corruption/evidence checks are separate. Wire counters include successful application reads/writes and framing, excluding TCP/IP headers and retransmissions. Full-cache uses the same client proof task after its one-time download.','',
      'Linux/WSL reproduction needs Python 3 with matplotlib (an existing imported layout helper uses it), Go and a C compiler for the unchanged cgo backend. Run the following from the project root. The module is .tools/simplepir/simplepir-main/go.mod; it has no external Go requirements or go.sum. Build only the new Go file, using a new binary name to preserve the measured binary:',
      '```bash',
      'project_root="$PWD"',
      'cd "$project_root/.tools/simplepir/simplepir-main"',
      'go build -o "$project_root/examples/tifs_layout_transfer_20260910/system/tifs_layout_transfer_tcp_rebuilt" "$project_root/scripts/tifs_layout_transfer_tcp_20260910.go"',
      'cd "$project_root"',
      'python scripts/run_layout_transfer_tcp_20260910.py --binary "$project_root/examples/tifs_layout_transfer_20260910/system/tifs_layout_transfer_tcp_rebuilt" --samples 100 --repeats 5 --warmup 5 --output examples/tifs_layout_transfer_20260910/system/new_reproduction',
      'python scripts/audit_layout_transfer_tcp_20260910.py --runs examples/tifs_layout_transfer_20260910/system/new_reproduction --output examples/tifs_layout_transfer_20260910/system/new_reproduction_audit.json',
      '```','',
      'The runner refuses an output directory containing a measured summary. runs/ is the sole formal 20-pair result. smoke_v2/ is an 8-proof development check and is not pooled. The first smoke/ stopped before measurements on a Python tuple/list comparison; that input check was fixed before smoke_v2 and the formal run.','',
      'Run `python scripts/audit_layout_transfer_tcp_20260910.py` for standard-library-only reproduction checks. It does not import the SMT, layout, or measurement implementation. It independently rebuilds the frozen root, validates 792 stored records across four layouts, verifies all 13,760 recovered sibling records and 2,000 proofs/bit flips, and checks paired targets, process IDs, fixed wire shapes, socket byte conservation, matrix-derived bytes, source pins, and statistics. Report: independent_raw_audit.json.','',
      'run_summary.csv and query_measurements.csv accompany all raw client/server JSONs; every result retains recovered sibling digests. runs/source_snapshots/ preserves the derived source/binary and original TCP source, while source_manifest.json and dependency_source_hashes.json pin the environment inputs. The report and figure are generated without rerunning measurements.','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf8')
    tex=[r'\section{Fuel Layout-to-Backend Transfer}',r'\label{sec:fuel-layout-transfer}',
      r'To test whether a tighter construction improves a real backend, we materialize the separate capacity-22 witness on the unchanged Fuel experimental snapshot ($n=100$, $N=198$, $h=128$). It is an exact feasible layout, not an AB or small-palette recoloring result. First-fit, frozen AB, the witness, and Full-cache use identical slots, values, digests, and root.',
      r'The same derived TCP backend uses eight 32-bit SimplePIR chunks per logical slot, lattice dimension 1024, $\log q=32$, and $\sigma=6.4$. Its only client-input change accepts the known Fuel slot/value directly; using the CT record-hash interface would change the snapshot. Five independent client/server pairs per method each execute five warmups and 100 paired targets, with randomized method order. The statistical unit is a process-pair mean.',
      r'\begin{table*}[t]\centering\small',r'\caption{Frozen Fuel layout transfer over loopback TCP. E2E intervals are 95\% $t$ intervals over five process means. Q/A/R are query generation, server Answer, and Recover; bootstrap is measured serialized application bytes.}',r'\label{tab:fuel-layout-transfer}',
      r'\begin{tabular}{lrrrrrr}\toprule',r'Layout & $U$ & Q/A/R (ms) & E2E (ms) & 95\% CI & Upload / down (B) & Bootstrap (B)\\\midrule']
    for m,name in zip(METHODS,NAMES):
        ci=report[m]['mean_e2e_ms']['95pct_t_interval'];u='--' if m=='full_cache' else str(int(mean(m,'max_bucket')))
        tex.append(f"{name} & {u} & {mean(m,'mean_query_ms'):.3f}/{mean(m,'mean_server_answer_ms'):.3f}/{mean(m,'mean_recover_ms'):.3f} & {mean(m,'mean_e2e_ms'):.3f} & [{ci[0]:.3f},{ci[1]:.3f}] & {int(mean(m,'mean_upload_wire_bytes'))}/{int(mean(m,'mean_download_wire_bytes'))} & {int(mean(m,'bootstrap_total_wire_bytes'))}\\\\")
    tex += [r'\bottomrule\end{tabular}\end{table*}',
      r'The maximum bucket improves from 23 to 22, but online traffic remains 9536 bytes per proof. Both sizes select $L=12,M=8$; the original 21-record AB bucket has $M=7$, which becomes 8 in the witness. Query padding rounds both to nine elements, leaving online shapes unchanged. Expanded public $A$ instead grows by 32768 bytes; hint size is unchanged. Full-cache transfers only 12830 bootstrap bytes and sends no online request.',
      r'The paired AB-minus-witness E2E difference is 0.259\,ms with 95\% interval $[-0.307,0.825]$\,ms; First-fit-minus-witness is 0.029\,ms with interval $[-0.114,0.172]$\,ms. Both contain zero, so these runs do not establish a reliable latency gain from the exact layout. They also do not prove equal running times. The deterministic byte result shows that minimizing $U$ alone need not minimize online or initialization cost.',
      r'\begin{figure*}[t]\centering\includegraphics[width=\textwidth]{figures/fuel_layout_transfer.pdf}',r'\caption{Structural improvement versus measured backend cost on the same snapshot. Traffic is deterministic; timing estimates and intervals appear in Table~\ref{tab:fuel-layout-transfer}. The last panel isolates the witness-minus-AB bootstrap change.}',r'\label{fig:fuel-layout-transfer}\end{figure*}',
      r'All 2000 measured proofs pass an independent standard-library audit of the original root, 13760 recovered sibling digests, corruption rejection, paired schedules, socket counters, matrix parameters, and source hashes. Separate client/server RSS, metadata, slots, hints, public matrices, bootstrap time, and per-query records are retained in the artifact. Warm E2E excludes bootstrap and process launch; loopback application bytes exclude TCP/IP headers. These fixed-snapshot measurements establish neither a deployed Fuel service nor a scalable witness-construction method.']
    (OUT/'fuel_layout_transfer.tex').write_text('\n\n'.join(tex)+'\n',encoding='utf8')
    byte_tex=[r'\begin{table*}[t]\centering\small',r'\caption{Exact initialization bytes on the frozen Fuel snapshot. Total bootstrap also includes serialized parameters, matrix/cache framing, and the client handshake; component columns are payload sizes.}',r'\label{tab:fuel-layout-transfer-bytes}',r'\begin{tabular}{lrrrrr}\toprule',r'Layout & Bootstrap total & Directory & Occupied slots & Hint payload & Public $A$ payload\\\midrule']
    for m,name in zip(METHODS,NAMES):
        byte_tex.append(name+' & '+' & '.join(str(int(mean(m,k))) for k in ('bootstrap_total_wire_bytes','metadata_bytes','slots_bytes','hint_matrix_bytes','shared_A_matrix_bytes'))+r'\\')
    byte_tex += [r'\bottomrule\end{tabular}',r'\par\smallskip\footnotesize Full-cache additionally transfers 6336 digest payload bytes; its hint and public-$A$ payloads are zero. OPT-minus-AB bootstrap and public-$A$ increments are both exactly 32768 bytes.',r'\end{table*}']
    (OUT/'fuel_layout_transfer_bytes.tex').write_text('\n'.join(byte_tex)+'\n',encoding='utf8')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42,'ps.fonttype':42})
    fig,axes=plt.subplots(1,3,figsize=(7.1,2.8));fig.subplots_adjust(left=.065,right=.99,bottom=.27,top=.80,wspace=.48)
    xs=['FF','AB','OPT'];colors=['#7B909E','#16819A','#C07C23']
    vals=[58,23,22];axes[0].bar(xs,vals,color=colors);axes[0].set_title('Largest bucket U',fontsize=10,fontweight='bold');axes[0].set_ylabel('Digest records',fontsize=9);axes[0].set_ylim(0,68)
    for i,v in enumerate(vals):axes[0].text(i,v+1,str(v),ha='center',fontsize=9)
    vals=[8640,9536,9536];axes[1].bar(xs,[v/1024 for v in vals],color=colors);axes[1].set_title('Online bytes / proof',fontsize=10,fontweight='bold');axes[1].set_ylabel('KiB incl. framing',fontsize=9);axes[1].set_ylim(0,11.5)
    for i,v in enumerate(vals):axes[1].text(i,v/1024+.2,str(v),ha='center',fontsize=9)
    vals=[0,32,0];axes[2].bar(['Hint','Public A','Other'],vals,color=['#7B909E','#C07C23','#7B909E']);axes[2].set_title('OPT − AB bootstrap',fontsize=10,fontweight='bold');axes[2].set_ylabel('Change (KiB)',fontsize=9);axes[2].set_ylim(0,40)
    for i,v in enumerate(vals):axes[2].text(i,v+.8,'+32' if v else '0',ha='center',fontsize=9)
    for ax in axes:ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=9)
    fig.text(.5,.96,'Capacity 23 → 22: unchanged online bytes, larger initialization',ha='center',va='top',fontsize=10.6,fontweight='bold',color='#193548')
    fig.text(.5,.055,'Full-cache: 12,830 B bootstrap, 0 B online. OPT is a separate exact witness.',ha='center',fontsize=9,color='#354B5A')
    stem=OUT/'fuel_layout_transfer'
    for ext in ('.pdf','.png'):fig.savefig(stem.with_suffix(ext),dpi=300)
    plt.close(fig)
    (OUT/'report_manifest.json').write_text(json.dumps({'report_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'README.md',OUT/'fuel_layout_transfer.tex',OUT/'fuel_layout_transfer_bytes.tex',OUT/'process_mean_CIs.json',stem.with_suffix('.pdf'),stem.with_suffix('.png')]}},indent=2)+'\n')
    print('Generated process-mean CIs, negative-result report, TeX and three-panel figure.')

if __name__=='__main__':main()
