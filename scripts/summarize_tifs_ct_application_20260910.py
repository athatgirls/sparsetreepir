"""Generate reviewable CT application findings and LaTeX from preserved raw runs."""
from pathlib import Path
import csv, hashlib, json, re, shutil, statistics

ROOT=Path(__file__).absolute().parents[1]
BASE=ROOT/'examples/tifs_revision_20260910/ct_application'
RUN=BASE/'runs_verified_evidence'
PAPER=ROOT/'manuscripts/tifs/revision_20260910'
METHODS=['first_fit','activebalance','nonempty_depth','full_cache']
NAMES={'first_fit':'First-fit','activebalance':'ActiveBalance','nonempty_depth':'Nonempty-depth','full_cache':'Full-cache'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf8'))
def dump(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def main():
 summary=load(RUN/'summary.json');s=summary['groups'];snapshot=load(RUN/'publisher/snapshot.json');completion=load(RUN/'completion.json')
 audit=load(PAPER/'generated/ct_tcp_independent_audit.json');assert audit['status']=='pass'
 depth_ci=audit['paired_processing_ratios']['nonempty_depth_over_activebalance']['mean_95pct_t_ci']
 assert completion['independent_client_server_pairs']==20 and completion['measured_proofs_verified']==2000
 source_manifest=load(RUN/'source_manifest.json')['sha256'];assert all(sha(ROOT/p)==v for p,v in source_manifest.items())
 repeats=list(csv.DictReader((RUN/'run_summary.csv').open()));queryrows=list(csv.DictReader((RUN/'query_measurements.csv').open()))
 assert len(repeats)==20 and len(queryrows)==2000
 for rep in range(5):
  sequences=[[q['ct_index'] for q in queryrows if q['repeat']==str(rep) and q['method']==m] for m in METHODS]
  assert all(x==sequences[0] for x in sequences) and len(set(sequences[0]))==100
  for m in METHODS:
   client=load(RUN/m/f'repeat{rep}/client_result.json');server=load(RUN/m/f'repeat{rep}/server_result.json')
   assert client['client_pid']!=server['server_pid']
   assert all(q['valid_root'] and q['corruption_rejected'] for q in client['queries'])
   assert len({(q['upload_wire_bytes'],q['download_wire_bytes']) for q in client['queries']})==1
 def v(m,k):return s[m][k]['mean']
 def fmt(m,k,d=3,scale=1):return f"{v(m,k)/scale:.{d}f} ± {s[m][k]['sample_sd']/scale:.{d}f}"
 def tex(m,k,d=3,scale=1):return r'\('+fmt(m,k,d,scale).replace(' ± ',r'\pm')+r'\)'
 ratio=[];firstfit_ratio=[]
 for rep in range(5):
  row={r['method']:r for r in repeats if r['repeat']==str(rep)};ratio.append(float(row['nonempty_depth']['mean_e2e_ms'])/float(row['activebalance']['mean_e2e_ms']));firstfit_ratio.append(float(row['first_fit']['mean_e2e_ms'])/float(row['activebalance']['mean_e2e_ms']))
 paired={'depth_over_ab_e2e_mean_ratio':statistics.mean(ratio),'sample_sd':statistics.stdev(ratio),'n':5,'bootstrap_ab_over_cache':v('activebalance','bootstrap_total_wire_bytes')/v('full_cache','bootstrap_total_wire_bytes'),'online_depth_over_ab':v('nonempty_depth','mean_online_wire_bytes')/v('activebalance','mean_online_wire_bytes')}
 paired.update({'firstfit_over_ab_e2e_mean_ratio':statistics.mean(firstfit_ratio),'firstfit_over_ab_sample_sd':statistics.stdev(firstfit_ratio),'online_firstfit_over_ab':v('first_fit','mean_online_wire_bytes')/v('activebalance','mean_online_wire_bytes')})
 dump(RUN/'paired_comparison.json',paired)
 # Preserve precisely the measured program, binary, and directly tracked inputs.
 snapshotdir=RUN/'source_snapshots';snapshotdir.mkdir(exist_ok=True)
 for rel,expected in source_manifest.items():
  if rel.endswith('ct_records.csv'):continue
  path=ROOT/rel;dst=snapshotdir/path.name
  if not dst.exists():shutil.copy2(path,dst)
  assert sha(dst)==expected
 upstream=ROOT/'.tools/simplepir/simplepir-main'
 sources=[p for p in (upstream/'pir').iterdir() if p.is_file() and p.suffix in ('.go','.c','.h','.csv')]
 sources += [upstream/'go.mod',upstream/'go.sum',ROOT/'scripts/fixed_sparse_tree_coloring.py',ROOT/'scripts/generate_full_sparse_smt_example.py',ROOT/'scripts/run_height_sparsity_profile_balance_experiment.py',ROOT/'scripts/run_sparse_smt_pir_backend_experiment.py']
 dump(RUN/'dependency_source_hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in sources if p.exists()})
 table=[
 r"We froze entries 0--511 from Google's public Argon2026h2 CT log~\cite{ctlogsample}. Each raw \texttt{leaf\_input} record is hashed with SHA-256; its first 128 bits give the occupied coordinate and its full digest gives the value in a new experimental SMT. This yields $n=512$, $N=1022$, $m=13$, and $D=17$. These records include certificate/precertificate entries. The commitment is a locally pinned, unsigned experimental SMT root, not a native CT root; certificate-chain, revocation, and log-consistency validation are not implemented.",
 r'The publisher writes the snapshot, and distinct Go server and client processes communicate over one persistent TCP connection bound to \texttt{127.0.0.1}. The server loads only the public snapshot. The client reads selected records already in its possession and the pinned root; it receives the directory, occupied coordinates, parameters, expanded public $A$, and hints through TCP. It never opens the server database files. A request serializes one fixed batch of eight 32-bit SimplePIR chunk queries per color. Full-cache instead downloads all active digests and their directory once, then audits locally.',
 r'For each of five repetitions, we select 100 distinct records uniformly without replacement and pair those targets across First-fit, ActiveBalance, Nonempty-depth, and Full-cache, with randomized method order. Each method uses a fresh client/server process pair and five additional warmup audits. These are controlled audit requests, not an observed browsing trace. The WSL2/Ubuntu 24.04 host, Go 1.22.2, and per-process GOMAXPROCS=1 match the verified backend suite; the two processes can be scheduled independently. All $4\times5\times100=2000$ measured audits verify; modifying a used proof sibling is rejected in every audit outside the measured interval. Both socket byte counters agree, and per-method request/response sizes remain constant across targets. Every used recovered sibling is retained with its proof level after timing, enabling independent root reconstruction from the returned bytes. This evidence retention can affect process memory and later garbage collection; these runs are analyzed separately from the earlier development runs.',
 r'\begin{table}[H]',r'\centering',r'\caption{Certificate-record audit on one fixed 512-record snapshot. Time is mean $\pm$ sample SD across five independent process-pair means. Every pair performs 100 measured audits.}',r'\label{tab:ct_application_tcp}',r'\footnotesize',r'\setlength{\tabcolsep}{4pt}',r'\begin{tabular}{lrrrrr}',r'\toprule',r'Method & Queries & Online KiB & Audit ms & Bootstrap KiB & Bootstrap ms \\',r'\midrule']
 for m in METHODS:
  width={'first_fit':13,'activebalance':13,'nonempty_depth':17,'full_cache':0}[m]
  table.append(f"{NAMES[m]} & {width} & {v(m,'mean_online_wire_bytes')/1024:.3f} & {tex(m,'mean_e2e_ms',4 if m=='full_cache' else 3)} & {v(m,'bootstrap_total_wire_bytes')/1024:.3f} & {tex(m,'bootstrap_ms',3)} "+r'\\')
 table += [r'\bottomrule',r'\end{tabular}',r'\par\smallskip\parbox{\linewidth}{\footnotesize Audit time starts with client record decoding/hashing and routing, and includes query generation, serialization, actual TCP transport, server answering, PIR decoding, proof assembly, and the full 128-level root check. It excludes process launch and bootstrap. Bootstrap time starts at connection setup and ends after reception, deserialization, and directory parsing; earlier publisher/server preparation and subsequent one-time default-chain precomputation are excluded. Online and bootstrap bytes count successful application socket reads/writes, including framing; TCP/IP headers and retransmissions are excluded. Bootstrap includes full public matrices and hints for PIR, and the complete active-record package for Full-cache. No cold first-query total was directly timed.}',r'\end{table}',
 r'\begin{table}[H]',r'\centering',r'\caption{Observed process peak RSS for the same certificate-record audit, including bootstrap and transient allocations. Means and sample SDs are across five independent processes for each role.}',r'\label{tab:ct_application_memory}',r'\footnotesize',r'\begin{tabular}{lrr}',r'\toprule',r'Method & Client MiB & Server MiB \\',r'\midrule']
 for m in METHODS:table.append(f"{NAMES[m]} & {tex(m,'client_peak_rss_bytes',2,1048576)} & {tex(m,'server_peak_rss_bytes',2,1048576)} "+r'\\')
 table += [r'\bottomrule',r'\end{tabular}',r'\end{table}',
 f"The paired Nonempty-depth/ActiveBalance audit-time ratio is \\({paired['depth_over_ab_e2e_mean_ratio']:.3f}\\pm{paired['sample_sd']:.3f}\\); its online-byte ratio is {paired['online_depth_over_ab']:.3f}. The 95\\% Student-$t$ interval for this mean ratio (4 degrees of freedom) is [{depth_ci[0]:.3f},{depth_ci[1]:.3f}] and includes one; one of the five pairs favors Nonempty-depth, so a robust speedup is not established. First-fit/ActiveBalance audit time is \\({paired['firstfit_over_ab_e2e_mean_ratio']:.3f}\\pm{paired['firstfit_over_ab_sample_sd']:.3f}\\), with an online-byte ratio of {paired['online_firstfit_over_ab']:.3f}: balancing does not improve these costs over First-fit. ActiveBalance bootstrap is {paired['bootstrap_ab_over_cache']:.2f} times Full-cache bootstrap, and Full-cache needs no subsequent network request. This prototype therefore establishes a target-private certificate-record retrieval workflow under the stated PIR assumptions, while providing no cost advantage over unrestricted full caching on this snapshot. It is a loopback experiment, not WAN latency, a deployed CT integration, a real browsing workload, or a non-revocation service.",
 r'An independent standard-library Python audit rebuilds this SMT from the frozen raw records, checks all 18\,476 retained sibling digests against the server payloads, and reconstructs all 2000 roots and corruption checks. It also checks target pairing, socket counters, source hashes, and the five-process summary statistics.']
 (PAPER/'generated/ct_application_results.tex').write_text('\n\n'.join(table)+'\n',encoding='utf8')
 notes=['# 公开证书记录应用闭环：真实 TCP 实验（2026-09-10）','已完成，不是预计值。原始记录、代码、每进程输出与统计均保留。没有改动历史 CSV。',
 '## 实验对象与安全主体',
 '冻结 Google Argon2026h2 CT API 的 entries 0–511，共 512 条 certificate/precertificate 的 raw leaf_input。使用 SHA256(raw record) 的前 128 位作坐标、完整 32-byte hash 作 value，构建新的实验 SMT：N=1022、AB m=13、Nonempty-depth D=17，AB 最大桶79、depth最大桶196。客户端已持 raw record，私密目标是正在审计哪一条记录；镜像服务方持公共快照。publisher 的根在 client 输入中本地可信固定，未实现签名发布。这不是 Google 原生 CT root，也不验证证书链、non-revocation 或 CT log consistency。',
 '[Google CT get-entries source](https://ct.googleapis.com/logs/us1/argon2026h2/ct/v1/get-entries?start=0&end=511)。source/manifest.json 保存16次实际API响应URL、SHA256、时间和原始JSON；CSV SHA256：70d7daa6c33a8fee866eb62db0653019171fd6fb5698a25402b008efc11dce2d。',
 '## 测量设计与正确性',
 'First-fit、AB、Nonempty-depth、Full-cache四个方法各五对全新独立 Go client/server 进程，方法顺序逐重复随机化；每对先额外 warmup 5 次，再测100个不同目标。每重复的目标跨方法配对，来自公开记录的控制性均匀抽样，不是实际浏览器访问轨迹。20对共2000个测量证明全部验根，篡改一个真实使用 sibling 后全部拒绝。server 检查固定8×颜色数的query batch；客户端/服务端socket实际计数字节相等，同方法所有target请求/响应尺寸一致。两个进程PID不同；client只打开选定record和pinroot输入文件，目录/A/hint/cache全通过TCP取得。',
 '每次计时结束后保存实际使用的 recovered_siblings:[{level,digest_hex}]，含Full-cache且按level排序，供独立程序从实际返回摘要重算根。留存发生在计时之后，但其内存分配和随后GC可能影响后续测量和RSS。故本次2000proof与早期未留存返回摘要的1500proof开发运行完全独立统计，不合并。',
 '独立标准库审核 scripts/audit_tifs_ct_tcp_20260910.py 已通过：18,476条实际返回 sibling 与 serverDB 和独立重建CT-SMT节点全部吻合，2000根/篡改检查、配对目标、双端wire、源码hash和5进程均值/SD全部一致；报告generated/ct_tcp_independent_audit.json。',
 '服务器仅bind127.0.0.1，每对一个持久TCP连接，真实序列化二进制矩阵/长度framing。WSL2 Ubuntu24.04、Go1.22.2、Python3.12.3、Intel Core Ultra5 245K，GOMAXPROCS=1；串行执行进程对。',
 '## 主要结果（均值 ± 样本SD，统计单位为5个进程对的均值）',
 '|方法|完整每次审计 ms|在线实际 bytes|首次bootstrap实际 bytes|bootstrap ms|客户端峰值RSS MiB|',
 '|---|---:|---:|---:|---:|---:|']
 for m in METHODS:notes.append(f"|{NAMES[m]}|{fmt(m,'mean_e2e_ms',5 if m=='full_cache' else 3)}|{v(m,'mean_online_wire_bytes'):,}|{v(m,'bootstrap_total_wire_bytes'):,}|{fmt(m,'bootstrap_ms',3)}|{fmt(m,'client_peak_rss_bytes',2,1048576)}|")
 notes += [f"配对 depth/AB 时延比 {paired['depth_over_ab_e2e_mean_ratio']:.4f} ± {paired['sample_sd']:.4f}；在线字节比 {paired['online_depth_over_ab']:.4f}。First-fit/AB 时延比 {paired['firstfit_over_ab_e2e_mean_ratio']:.4f} ± {paired['firstfit_over_ab_sample_sd']:.4f}，在线字节比 {paired['online_firstfit_over_ab']:.4f}；AB相对First-fit更慢且通信更多，不能只报对depth的收益。AB bootstrap 是 Full-cache 的 {paired['bootstrap_ab_over_cache']:.2f} 倍。",
 f'depth/AB时延5对中1对小于1，独立audit JSON的t(df=4)95%区间为[{depth_ci[0]:.5f},{depth_ci[1]:.5f}]，不能宣称稳定/显著加速。FF/AB五对均小于1。',
 '## 必须保留的计时与成本边界',
 '- 每次审计连续计时覆盖 raw record base64 decode、SHA256、路由、PIR Query、请求序列化、TCP传输、server Answer、响应反序列化、Recover、proof assembly与128层rootcheck。Full-cache也计相同record hash与rootcheck，只省去PIR/网络。篡改负控在该计时之后执行。',
 '- Bootstrap另计connect到接收/反序列化/目录解析；含真实传输目录、occupied coordinates、参数、完整public A及hint，或完整cache。不含先前publisher建树、服务器预备过程、之后一次性default hash chain预计算。不能把bootstrap与在线均值相加叫作已连续测得的首次请求时延。',
 '- server_result的setup_ms只计PIR建库初始化阶段，不含其后bootstrap buffer构造、metadata读取和序列化；Full-cache该值几乎为空操作，不应用来声称完整服务端准备更快。',
 '- 实际wire是成功socket应用层read/write字节，含framing，不含TCP/IP包头与重传；本机loopback不是WAN。RSS是各角色进程VmHWM，含bootstrap临时buffer、Go运行时和分配器，不是纯数据库/客户端持久状态。',
 '- 证书来源真实，不使控制性随机审计变成真实访问trace；新的SMT不使实验变成原生Google CT集成。隐私依赖每个真实SimplePIR子查询及固定调度的理论假设，不以2000次功能检查证明密码学隐私。',
 '## 对原评审B的回应与仍有限制',
 '已补：明确publisher/mirror/privacy-seeking client分工、真实公开记录绑定、client/server进程分離、实际批次消息、全路径本机传输与验根、真实bootstrap和完整缓存比较。由此不再只使用rollup坐标形状充当应用证据。',
 '仍未建立：WAN/并发/动态更新、真实浏览请求分布、原生CT承诺/证书语义/恶意服务器验证，或当前SimplePIR相对 unrestricted Full-cache 的成本优势。完整缓存此固定快照明显更便宜，这一负结果必须留在主文。',
 '## 复现与定位',
 '- 后端：backend/simplepir/tifs_tcp_certificate_backend.go（在upstream模块中单文件编译）；驱动：scripts/run_tifs_ct_application_20260910.py；统计生成：scripts/summarize_tifs_ct_application_20260910.py。',
 '- 正式原始数据：examples/tifs_revision_20260910/ct_application/runs_verified_evidence/{method}/repeat0..4/{client_result,server_result,commands}.json；run_summary.csv、query_measurements.csv、summary.json、completion.json。',
 '- 代码/二进制/输入hash：runs_verified_evidence/source_manifest.json；测量版本保存在同目录source_snapshots；依赖源码hash为dependency_source_hashes.json。较早smoke_v1发生encoding拼写错误、smoke_v2功能通过；原runs保留三法1500proof开发记录与其原测量源码/二进制，未保存恢复摘要且不含FF，因此不并入正式统计。',
 '- 新补充片段：generated/ct_application_results.tex；节sec:ct-application-supp，主表tab:ct_application_tcp，内存表tab:ct_application_memory；引用key=ctlogsample。',
 '```bash\ncd /path/to/sparsetreepir\n/var/tmp/tifs_revision_20260910_venv/bin/python scripts/run_tifs_ct_application_20260910.py --samples 100 --repeats 5 --warmup 5 --output examples/tifs_revision_20260910/ct_application/new_reproduction\n/var/tmp/tifs_revision_20260910_venv/bin/python scripts/summarize_tifs_ct_application_20260910.py\n```',
 '复现需新输出目录，驱动拒绝覆盖已有run_summary。统计脚本默认读取正式runs_verified_evidence，重做独立复现后若比较新结果应显式修改统计输入，不覆盖本次正式数据。']
 note_text=re.sub(r'(?m)(^\|[^\n]*\|)\n\n(?=\|)',r'\1\n','\n\n'.join(notes)+'\n')
 (PAPER/'notes/ct_application_findings.md').write_text(note_text,encoding='utf8')
 dump(RUN/'ANALYSIS_VALIDATION.json',{'source_hashes_match':True,'independent_pairs':20,'measured_proofs':2000,'paired_targets':True,'distinct_targets_each_repeat':100,'root_and_actual_sibling_corruption_checks':True,'fixed_wire_shape':True,'tables_generated_from_summary_json':True,'actual_recovered_sibling_evidence_retained':True})
 print(json.dumps({'completion':completion,'paired':paired,'generated':'generated/ct_application_results.tex'},indent=2))
if __name__=='__main__':main()
