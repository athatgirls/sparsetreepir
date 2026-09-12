"""Generate publication figures and a concise report from independently verified data."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).absolute().parents[1]
BASE = ROOT / 'examples/tifs_simplepir_extension_20260911'
OUT = BASE / 'analysis'
OLD = ROOT / 'examples/tifs_external_extension_20260911'
METHODS = ['ab', 'pbc', 'flat', 'first_fit']
LABELS = {'ab': 'SparseTreePIR (AB)', 'pbc': 'PBC', 'flat': 'Flat-active', 'first_fit': 'First-fit'}
COLORS = {'ab': '#0072B2', 'pbc': '#D55E00', 'flat': '#666666', 'first_fit': '#009E73'}
MARKERS = {'ab': 'o', 'pbc': 's', 'flat': '^', 'first_fit': 'D'}
UNIFORM = ['uniform_n1000', 'uniform_n10000', 'uniform_n100000']
CASENAMES = {'uniform_n1000': 'Uniform 1k', 'uniform_n10000': 'Uniform 10k', 'uniform_n100000': 'Uniform 100k',
             'prefix64_n10000': 'Prefix 10k', 'cluster90_n10000': 'Cluster 10k', 'complete_h10': 'Complete h10', 'complete_h14': 'Complete h14'}

def read(p):
    return json.loads(p.read_text(encoding='utf8'))

def main():
    verified = read(OUT / 'INDEPENDENT_VERIFICATION.json')
    assert (verified['status'] == 'passed' and verified['complete_requested_experiment']) or (verified['status'] == 'audited_with_observed_failures' and verified['scheduled_executed_all'])
    data, older = read(OUT / 'results.json'), read(OLD / 'analysis/results.json')
    by = {(r['case'], r['method']): r for r in data['aggregates']}
    vb = {(r['case'], r['method']): r for r in older['aggregates']}
    def val(c, m, k): return by[c, m][k + '_mean']
    def texmean(c, m):
        r = by[c, m]
        if r['processes'] != 3:
            return r'Failure (1/3)'
        return f"${r['serialized_proof_wall_ms_mean']:.2f} \\pm {r['serialized_proof_wall_ms_sd']:.2f}$"
    figdir = OUT / 'figures'
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.labelsize': 9,
                         'legend.fontsize': 9, 'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    panels = [('serialized_proof_wall_ms', 1, 'Proof processing (ms)'),
              ('online_framed_bytes', 1024, 'Online traffic (KiB)'),
              ('encoded_db_bytes', 1024**2, 'Encoded DB matrix (MiB)')]
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.25))
    for ax, (key, unit, ylabel) in zip(axes, panels):
        for method in METHODS:
            rr = [by[c, method] for c in UNIFORM]
            ax.errorbar([r['leaves'] for r in rr], [r[key + '_mean'] / unit for r in rr],
                        yerr=[(r[key + '_sd'] or 0) / unit for r in rr], color=COLORS[method],
                        marker=MARKERS[method], linestyle='--' if method == 'first_fit' else '-',
                        label=LABELS[method], capsize=3, linewidth=1.4)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlabel('Occupied leaves')
        ax.set_ylabel(ylabel)
        ax.grid(alpha=.2, which='both')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(.5, 1.01))
    fig.tight_layout(rect=(0, 0, 1, .88))
    for ext in ['pdf', 'png']: fig.savefig(figdir / f'simplepir_scaling.{ext}', dpi=230, bbox_inches='tight')
    plt.close(fig)

    # Ratios of process-average costs within each backend, not pooled cryptosystems.
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.1))
    for ax, (key, _, ylabel) in zip(axes, panels):
        oldkey = 'ntt_coefficient_payload_bytes' if key == 'encoded_db_bytes' else key
        for source, name, color, marker in [(by, 'SimplePIR', '#0072B2', 'o'), (vb, 'VBPIR', '#CC79A7', 's')]:
            actual_key = oldkey if source is vb else key
            yy = [source[c, 'ab'][actual_key + '_mean'] / source[c, 'pbc'][actual_key + '_mean'] for c in UNIFORM]
            ax.plot([1000, 10000, 100000], yy, marker=marker, color=color, label=name)
        ax.axhline(1, color='#777777', linewidth=.8, linestyle='--')
        ax.set_xscale('log')
        ax.set_xlabel('Occupied leaves')
        ax.set_ylabel('AB / PBC: ' + ['processing time', 'online bytes', 'encoded storage'][list(axes).index(ax)])
        ax.set_ylim(bottom=0)
        ax.grid(alpha=.2)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(.5, 1.01))
    fig.tight_layout(rect=(0, 0, 1, .9))
    for ext in ['pdf', 'png']: fig.savefig(figdir / f'backend_consistency.{ext}', dpi=230, bbox_inches='tight')
    plt.close(fig)

    biggest = UNIFORM[-1]
    time_gain = 100 * (1 - val(biggest, 'ab', 'serialized_proof_wall_ms') / val(biggest, 'pbc', 'serialized_proof_wall_ms'))
    online_gain = 100 * (1 - val(biggest, 'ab', 'online_framed_bytes') / val(biggest, 'pbc', 'online_framed_bytes'))
    db_gain = 100 * (1 - val(biggest, 'ab', 'encoded_db_bytes') / val(biggest, 'pbc', 'encoded_db_bytes'))
    text_rows = []
    tex_rows = []
    for c in UNIFORM:
        for m in METHODS:
            r = by[c, m]
            text_rows.append(f"| {r['leaves']:,} | {LABELS[m]} | {r['serialized_proof_wall_ms_mean']:.2f} ± {r['serialized_proof_wall_ms_sd']:.2f} | {val(c,m,'online_framed_bytes')/1024:.2f} | {val(c,m,'encoded_db_bytes')/1024**2:.3f} |")
            tex_rows.append(f"{r['leaves']:,} & {LABELS[m]} & {texmean(c,m)} & {val(c,m,'online_framed_bytes')/1024:.2f} & {val(c,m,'encoded_db_bytes')/1024**2:.3f} \\\\")
        tex_rows.append(r'\addlinespace')
    table = r'''\begin{table*}[t]
\centering\small
\caption{Native 32-byte SimplePIR proof retrieval on common sparse snapshots. Time is mean $\pm$ sample SD of three process means, each with ten measured proofs. Online bytes include actual matrix framing. Encoded DB counts the squished matrix payload, not total server RAM.}
\label{tab:simplepir-native-comparison}
\begin{tabular}{rlrrr}\toprule
Leaves & Layout & Proof time (ms) & Online (KiB) & Encoded DB (MiB)\\\midrule
''' + '\n'.join(tex_rows) + r'''
\bottomrule\end{tabular}\end{table*}
'''
    prose = r'''\subsection{Sparse-proof layouts with SimplePIR}
We evaluate whether exploiting proof structure remains beneficial with a different PIR backend. A batch consists of the non-default 32-byte sibling digests of one Merkle membership proof. Flat-active stores the active records in one database and performs $m$ independent queries using shared initialization state. PBC applies the three-choice probabilistic batch-code placement~\cite{vectorbatchpir}; AB and First-fit assign conflicting proof nodes to distinct buckets. All methods use the same occupied coordinates, records, targets, default digests, and authentication root.

We use the authors' SimplePIR implementation~\cite{simplepir2023}, commit \texttt{e9020b03bf28}, with its vertical base-$p$ long-record representation. An integer-width adapter handles 256-bit input and recovery; the cryptographic initialization, preprocessing, query, and answer routines are unchanged. Each layout applies the official parameter-selection rule to its largest bucket. The resulting matrices differ, while the official parameter-table row remains $n=1024$, $\log_2 q=32$, $p=991$, and $\sigma=6.4$. Actual database-dependent hints are computed. Initialization transfers expanded public matrices and hints; both are accounted for separately.

We schedule three fresh sequential processes for each of seven snapshots and four layouts, with two warmups and ten measured proofs per process. Of 84 processes, 83 complete all ten proofs. One PBC process on the prefix input reaches the 500-eviction routing limit after seven measured proofs; its partial timings are excluded from process-level comparisons and the failure is retained. All 1,005 recovered proofs, including warmups and the partial run, pass independent root reconstruction. Timing includes routing, cryptographic operations, actual message serialization and loading, proof assembly, and root verification in one process; it excludes network delay and external layout construction. Targets match the preceding VBPIR experiment. Table~\ref{tab:simplepir-native-comparison} reports uniform-key scaling, for which all planned processes complete.

''' + f"At 100,000 occupied leaves, AB reduces proof-processing time, online traffic, and encoded matrix storage relative to PBC by {time_gain:.1f}\\%, {online_gain:.1f}\\%, and {db_gain:.1f}\\%, respectively. " + r'''These quantities measure different benefits and are not inferred from the maximum bucket capacity alone. First-fit is retained as an ablation rather than an external system. Cross-backend conclusions use within-backend AB/PBC ratios; the two cryptosystems' absolute timings and storage encodings are not treated as identical configurations.

''' + table
    (OUT / 'paper_ready_simplepir_results.tex').write_text(prose, encoding='utf8')

    costs, cost_md = [], []
    for m in METHODS:
        r = by[biggest, m]
        fields = ['persistent_setup_wall_ms', 'hint_matrix_bytes', 'public_A_matrix_bytes', 'public_metadata_serialized_bytes', 'bootstrap_framed_components_bytes']
        values = [val(biggest, m, k) / (1000 if i == 0 else 1024**2) for i, k in enumerate(fields)]
        costs.append(LABELS[m] + ' & ' + ' & '.join(f'{v:.3f}' for v in values) + r' \\')
        cost_md.append('| ' + LABELS[m] + ' | ' + ' | '.join(f'{v:.3f}' for v in values) + ' |')
    sensitivity = []
    for c in CASENAMES:
        sensitivity.append(CASENAMES[c] + ' & ' + ' & '.join(texmean(c,m) for m in METHODS) + r' \\')
    cachekeys = [k for k in by[biggest, 'ab'] if 'cache' in k or 'common' in k]
    cache_display = {k: by[biggest, 'ab'][k] for k in cachekeys}
    (OUT / 'REPORT_INPUT_CHECK.json').write_text(json.dumps({'time_reduction_percent':time_gain,'online_reduction_percent':online_gain,'encoded_storage_reduction_percent':db_gain,'cache_fields':cache_display}, indent=2), encoding='utf8')
    # A common metadata cache reference is provided by the independent analyzer.
    common_cache = by[biggest,'ab'].get('full_cache_reference_bytes_mean')
    cache_note = (f"A complete active cache is {common_cache/1024**2:.3f} MiB with the common public directory. " if common_cache is not None else '')
    cache_note += f"The digest-only payload is {val(biggest,'ab','active_digest_payload_bytes')/1024**2:.3f} MiB. "
    cache_note += r'''Expanded $A$ is the measured transfer policy, not an intrinsic SimplePIR communication lower bound; public-seed compression is possible. Database-dependent hints remain. Fixed-snapshot communication is $I+QC$ for initialization $I$, per-proof cost $C$, and query count $Q$. When $I\geq F$ and $C>0$, it cannot undercut a full-cache transfer $F$.'''
    brief = r'''\documentclass[10pt,a4paper]{article}
\usepackage[margin=18mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,booktabs,graphicx,float,amsmath,microtype}
\usepackage[hidelinks]{hyperref}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\renewcommand{\thesubsection}{\arabic{subsection}}
\renewenvironment{table*}[1][]{\begin{table}[H]}{\end{table}}
\begin{document}
\begin{center}{\Large\bfseries SparseTreePIR: SimplePIR and Backend Consistency}\\[4pt]
{\small Additional verified experiments --- 11 September 2026}\end{center}
\textbf{Environment.} Intel Core Ultra 5 245K; Ubuntu 24.04; Go 1.22.2; GCC 13.3. All native processes run sequentially with \texttt{GOMAXPROCS=1} and one native thread. The complete raw environment is preserved in the artifact.
\input{paper_ready_simplepir_results}
\clearpage
\begin{figure}[H]\centering
\includegraphics[width=\textwidth]{figures/simplepir_scaling.pdf}
\caption{Uniform height-128 snapshots. Both axes are logarithmic; error bars show the SD of three process means. All methods use native 32-byte records and the same parameter-selection policy. First-fit is an auxiliary ablation.}\end{figure}
\begin{table}[H]\centering\small
\caption{Initialization at 100,000 occupied leaves. Time includes native input preparation and true backend preprocessing; external tree construction and coloring are excluded for every layout. Hint and A columns are matrix payload; total includes their frames, metadata, and DB descriptors.}
\begin{tabular}{lrrrrr}\toprule
Layout & Setup (s) & Hint (MiB) & A (MiB) & Directory (MiB) & Total (MiB)\\\midrule
''' + '\n'.join(costs) + r'''
\bottomrule\end{tabular}\end{table}
\textbf{Client state and cache.} ''' + cache_note + r'''

The directory is the actual transmitted JSON representation. Persistent serialized state and matrix payloads are measured; isolated client and server resident memory are not. Combined peak RSS includes both roles, input and audit copies, derived indexes, and temporary buffers. Detailed per-case state, storage, and timing tables are supplied as CSV. A smaller bucket capacity does not by itself imply lower total memory or initialization cost.

\begin{table}[H]\centering\small
\caption{Proof-processing time (ms), mean $\pm$ SD of three complete process means. Prefix denotes a shared 64-bit prefix; Cluster places 90\% of keys in that prefix. One of three Prefix/PBC processes fails in routing and is explicitly marked instead of reporting an unconditional latency. Complete-tree rows compare SimplePIR layouts, not a new official TreePIR execution.}
\begin{tabular}{lrrrr}\toprule
Snapshot & AB & PBC & Flat-active & First-fit\\\midrule
''' + '\n'.join(sensitivity) + r'''
\bottomrule\end{tabular}\end{table}
\clearpage
\begin{figure}[H]\centering
\includegraphics[width=\textwidth]{figures/backend_consistency.pdf}
\caption{Within-backend AB/PBC ratios of mean costs on the same frozen snapshots and paired target schedules. Values below one favor AB. VBPIR data are the preceding frozen measurements, not reruns. Encoded storage means SimplePIR squished matrices and VBPIR NTT coefficients, respectively; each ratio compares like representations within its backend.}\end{figure}
\textbf{Comparability.} PBC uses three candidate buckets exported from the pinned official VBPIR utility. The SimplePIR wrapper preserves placement, but implements cuckoo routing in Go with deterministic insertion order and an independent routing RNG; it does not reproduce the C++ unordered-map eviction trajectory byte for byte. Flat-active performs repeated full-database PIR; it is not presented as the optimal possible batched SimplePIR implementation. No cryptographic RNG is replaced with a public experiment seed.

\textbf{Observed routing failure.} An offline maximum-matching check explains the Prefix/PBC failure: the fixed batch of 17 records has matching size 16. A Hall witness contains 11 records whose candidate union has only 10 buckets. The 12 actual proof records are matchable; adding the five random dummy records causes infeasibility. This is a limitation of the adapter's fixed random-padding policy on this instance, not evidence that PBC cannot retrieve the actual proof. Alternative padding or routing policies were not timed and are not substituted into the recorded results.

\textbf{Evidence limits.} There is one fixed synthetic snapshot per structure and scale. The three fresh process means describe timing variability on this host; they do not characterize workload or deployment variability. The main statistics contain 830 measured proofs from 83 complete processes; seven partial-run proofs and 168 warmups are separately verified and excluded. All 1,005 recovered proofs pass independent SHA-256 authentication. The eighth measured target in the failed PBC process fails during routing, and the remaining two are not attempted. Expected digests are consulted only after native recovery. Three negative controls alter a used sibling, a coordinate, and a leaf value. Sources, commands, parameters, schedules, per-proof observations, and hashes accompany the report.

\begin{thebibliography}{3}
\bibitem{simplepir2023} A. Henzinger, M. M. Hong, H. Corrigan-Gibbs, S. Meiklejohn, and V. Vaikuntanathan, ``One Server for the Price of Two: Simple and Fast Single-Server Private Information Retrieval,'' \emph{USENIX Security}, 2023. \href{https://www.usenix.org/conference/usenixsecurity23/presentation/henzinger}{Authors' paper}. Source: \href{https://github.com/ahenzinger/simplepir/tree/e9020b03bf2872c75b8954e749e32408b5db87ed}{official repository}.
\bibitem{vectorbatchpir} M. H. Mughees and L. Ren, ``Vectorized Batch Private Information Retrieval,'' \emph{IEEE Symposium on Security and Privacy}, 2023, pp. 437--452. \href{https://doi.org/10.1109/SP46215.2023.10179329}{doi:10.1109/SP46215.2023.10179329}.
\bibitem{treepir} Q. Cao et al., ``TreePIR: Efficient Private Retrieval of Merkle Proofs via Tree Colorings with Fast Indexing and Zero Storage Overhead,'' \emph{IEEE Symposium on Security and Privacy}, 2025. PBC source: \href{https://github.com/PIR-PIXR/TreePIR/tree/930063c5aefc441244abb4890fdf35383f3aa956}{pinned authors' implementation}.
\end{thebibliography}\end{document}
'''
    (OUT / 'simplepir_evaluation_brief.tex').write_text(brief, encoding='utf8')
    md = f'''# SimplePIR 新增实验与双后端核查

已执行 7 组输入 × 4 种布局 × 3 个独立进程的全部 84 项计划；83 个进程完整完成，主统计包含 830 份正式证明。Prefix/PBC 的一个进程在第 8 份正式证明的路由中达到 500 次驱逐上限，后两份未执行。该进程前 7 份证明和全部 168 份预热另行保留；共 1,005 份实际恢复的证明均通过独立验根。失败没有被替换，部分时间不进入完整进程统计。新测量使用原生 256 位（32 字节）长记录，不与旧八段拆分结果混合。VBPIR 数据保持冻结，所有输入和配对查询目标复用。

在 100,000 个有效叶子的均匀输入上，相对 PBC，AB 的证明处理时间变化为 {-time_gain:+.1f}%，在线通信变化为 {-online_gain:+.1f}%，编码数据库载荷变化为 {-db_gain:+.1f}%。这些是具体配置下三个不同成本的实测结果；不以最大桶容量代替系统指标。

| 有效叶子 | 布局 | 证明处理时间 ms（均值 ± SD） | 在线 KiB | 编码数据库 MiB |
|---:|---|---:|---:|---:|
''' + '\n'.join(text_rows) + '''

时间包括路由、Query、实际消息编码/解码、Answer、32 字节恢复、原层位还原和验根，是同进程序列化处理时间。没有包含网络往返，不标为 TCP 端到端延迟。独立统计单位是进程均值（每进程 10 次，3 进程）；配对差值区间保存在 paired_comparisons.csv，不将 30 个相关查询当作 30 个独立重复。

## 初始化及客户端状态（100,000 叶子）

| 布局 | 初始化 s | Hint MiB | 展开 A MiB | 目录 MiB | 初始化合计 MiB |
|---|---:|---:|---:|---:|---:|
''' + '\n'.join(cost_md) + '''

Flat 只初始化一个数据库、一份 hint 和 A；重复查询共享它们。PBC 保留真实三副本。hint 均来自实际预处理，未替换为随机假 hint。A 按本轮实际展开矩阵传输计费，同时明确公共 seed 压缩是可用优化，不能把展开 A 说成协议下界。目录使用实际 JSON 大小。独立客户端、服务器 RAM 未隔离；CSV 中峰值 RSS 是双角色及辅助副本合计。

完整缓存保留为参照，digest-only 与 common-directory 口径均在 CSV 中列明。固定快照中若初始化已经大于缓存，正的在线成本不会让查询次数增加后反超缓存。不能把处理时间或在线通信收益扩大为全成本优于缓存。

## 论文使用方式

主比较为 AB 与通用 PBC、Flat-active；First-fit 为内部消融。双后端图采用各自 AB/PBC 比值，检验收益方向是否持续；没有把两种密码系统当成相同参数而直接排名。PBC 桶位置来自固定官方函数；Go 路由的插入顺序与随机驱逐轨迹和 C++ 不保证逐位相同，适配边界已披露。

离线最大匹配说明了失败原因：本次固定补齐批次共 17 条记录，最大匹配只有 16；其中 11 条记录的候选桶并集仅有 10 个桶。实际证明需要的 12 条记录可以完整匹配，是随机加入的 5 条 dummy 使这一次补齐批次无解。因此，这只说明适配层固定随机补齐策略在该实例上失败，不能宣称 PBC 无法检索这份真实证明。未把更改补齐规则后的结果替换进原测量。

paper_ready_simplepir_results.tex 是可插入实验部分的学术段落和表格，simplepir_evaluation_brief.pdf 汇总图、表与解释。当前正文历史版本未被覆盖；应围绕“同一稀疏证明的多个节点批量检索”插入这些证据，避免再扩展为无关的理论主线。

来源：[SimplePIR 官方代码](https://github.com/ahenzinger/simplepir/tree/e9020b03bf2872c75b8954e749e32408b5db87ed)、[USENIX Security 2023 原文](https://www.usenix.org/conference/usenixsecurity23/presentation/henzinger)、[TreePIR/VBPIR-PBC 固定源码](https://github.com/PIR-PIXR/TreePIR/tree/930063c5aefc441244abb4890fdf35383f3aa956)。
'''
    (OUT / 'SimplePIR新增实验报告.md').write_text(md, encoding='utf8')
    print(json.dumps({'status': 'reported', 'largest_time_reduction_percent': time_gain, 'largest_online_reduction_percent': online_gain}, indent=2))

if __name__ == '__main__':
    main()
