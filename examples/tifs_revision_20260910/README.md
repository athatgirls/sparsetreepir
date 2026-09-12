# 2026-09-10 TIFS 补实验复现包

本 README 按压缩包解压后的**项目根目录**说明路径。包内保留 `scripts/`、`datasets/`、`backend/`、`.tools/simplepir/simplepir-main/` 和 `examples/tifs_revision_20260910/` 的相对关系。这里的命令是复现说明；编写本 README 时只读检查了版本、源码和哈希，没有再次运行性能实验。

## 已保存的结果与实验边界

| 目录 | 内容 | 完成状态 |
|---|---|---|
| `verified_backend/` | 六工作负载 × 六方法 × 五进程 × 100 目标；真实 32 字节 SMT 摘要经 SimplePIR 恢复和验根 | 180 个进程、18,000 个证明，无失败 |
| `correctness/` | 小树穷举、128/256 高度边界、目录往返、六方法路由及匹配器检查 | 见各 JSON 报告 |
| `backend_smoke/` | Go runner 的真实摘要、单叶、缓存复用、越界拒绝检查 | 全部通过；不作为性能样本 |
| `balance/` | 分布、规模、轮数预算、候选最优性与构造筛查 | 79 条：78 完成、1 超时 |
| `balance_repeats/` | 六工作负载与 100k uniform 的原/排序 AB 稳定性 | 42 条：39 完成、3 在 120 秒上限终止 |
| `ct_application/runs_verified_evidence/` | 512条真实公开CT记录镜像；四法×五个独立client/server进程对×100目标，通过真实loopback TCP检索 | 2000证明与18476返回摘要经独立重验，无失败 |

六工作负载的正式后端实验是同机顺序执行的**本地功能管线**，不是网络服务。`processing_ms` 为后端墙钟、Python 路由、证明重组与验根三个阶段之和；不含网络、进程启动、JSON 传输和初次目录解析。初始化、hint、共享矩阵 A、目录及整进程 RSS 分列。原稿的历史 shape-only CSV 没有被这些新数据覆盖。

新增 CT 原型的源、独立进程 TCP 运行和复现步骤见 `ct_application/README.md`。只使用 `runs_verified_evidence/` 的四法2000证明，早期三法1500次 `runs/` 是开发记录，不池化。该原型测连续在线wall time和实际socket应用层字节，bootstrap单独计时；固定的是实验SMT根，不是Google原生CT根。每个进程各设GOMAXPROCS=1，不代表两个进程只共用一个CPU线程。原始S&P评审的私有邮件PDF不在实验包内。

输入是固定 CSV 中的工作负载坐标及确定性实验叶值，不是原生链状态值。哈希格式为 `leaf=SHA256(00||value)`、`internal=SHA256(01||left||right)`、`empty_leaf=SHA256(02)`。PBC-routed 是本研究实现的三选择复制与逐证明最大匹配控制，不能称为原版 SealPIR 可执行系统的完整复现。

## 固定数据与代码依赖

必须保留以下六个 CSV，勿重新拉取链状态后冒充相同输入：

```text
datasets/fuel_smt_test_workload.csv
datasets/polygon_zkevm_account_leaf_workload.csv
datasets/zksync_era_account_leaf_workload_sample.csv
datasets/polygon_zkevm_account_leaf_workload_multiwindow.csv
datasets/polygon_zkevm_account_leaf_workload_broad_multiwindow.csv
datasets/zksync_era_account_leaf_workload_broad_sample.csv
```

递归检查 Python 本地导入后，需要以下 **14 个脚本**，不能只打包两个主驱动：

```text
scripts/analyze_tifs_verified_results_20260910.py
scripts/fixed_sparse_tree_coloring.py
scripts/generate_full_sparse_smt_example.py
scripts/run_height_sparsity_profile_balance_experiment.py
scripts/run_real_smt_workload_experiment.py
scripts/run_sparse_smt_pir_backend_experiment.py
scripts/run_tifs_balance_repeats_20260910.py
scripts/run_tifs_balance_study_20260910.py
scripts/run_tifs_verified_backend_suite_20260910.py
scripts/subtree_permutation_balance.py
scripts/test_tifs_revision_routing.py
scripts/test_tifs_revision_smt.py
scripts/tifs_revision_smt.py
scripts/verify_tifs_backend_smoke.py
```

第三方 Python 依赖只有 NumPy、Matplotlib；其余导入属于标准库。虽然主驱动本身不画图，旧算法模块在导入时依赖 Matplotlib，不能省掉它。所有脚本及数据 SHA-256 见同目录的 [reproducibility_source_manifest.json](reproducibility_source_manifest.json)。各测量子目录另保留当时的源码 manifest、环境、配置、seed、原始结果和日志；`balance_repeats/source_snapshots/` 保存测量时的重复驱动版本，最终版本仅修正汇总空值与表格措辞。

## SimplePIR 上游与新 runner

只读核验的上游仓库为 `https://github.com/ahenzinger/simplepir.git`，精确 commit：

```text
e9020b03bf2872c75b8954e749e32408b5db87ed
```

本地原始 `simplepir-main.zip` 的 SHA-256：

```text
8a325b140e74c3742209c30fb1cc3ebe965c97a95755d73662a0e234ed52f614
```

23 个上游受跟踪文件逐字节与该归档一致；受跟踪源码没有修改，`eval/` 仅新增作者 runner。打包至少需要上游 `go.mod`、完整 `pir/`（含 `.go`、`pir.h`、`params.csv`）、`LICENSE` 和 `README.md`，建议直接保留这 23 个受跟踪文件。该 commit **没有 `go.sum`**，且 `go.mod` 无外部模块依赖；不应人为生成一个假锁文件。

作者规范源码是 `backend/simplepir/tifs_full_proof_backend.go`，接口文档为 `backend/simplepir/TIFS_RUNNER_README.md`。构建时只把它复制为上游模块中的一个独立 `eval/tifs_full_proof_backend.go`；不要修改 `pir/`，也不要把整个 `eval/` 当成单一程序编译。

## WSL 后端环境与构建

正式结果的环境是 Ubuntu 24.04 / WSL2、Python **3.12.3**、Go **1.22.2 linux/amd64**、gcc **13.3.0**；`GOMAXPROCS=1`、`OMP_NUM_THREADS=1`。运行后只读确认 `/var/tmp/tifs_revision_20260910_venv` 使用 NumPy **1.26.4**、Matplotlib **3.11.1**。具体系统记录见 `verified_backend/environment.json`；机器为 Core Ultra 5 245K，未固定 CPU affinity。

下面在**新的空实验工作副本**根目录执行；原压缩包和已发表结果副本保持只读。新工作副本先放入上述代码、固定 CSV 和上游源文件，不复制已有 `runs/`，避免脚本的跳过/复用行为混入旧结果。

```bash
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install numpy==1.26.4 matplotlib==3.11.1
export GOMAXPROCS=1
export OMP_NUM_THREADS=1
artifact_root="$(pwd)"
mkdir -p examples/tifs_revision_20260910/backend_smoke
cp backend/simplepir/tifs_full_proof_backend.go .tools/simplepir/simplepir-main/eval/tifs_full_proof_backend.go
cd .tools/simplepir/simplepir-main
go build -o "$artifact_root/examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend" eval/tifs_full_proof_backend.go
cd "$artifact_root"
```

新 runner 可用 `-warmup 5 -gomaxprocs 1 -output result.json manifest.json`。输出文件是纯 JSON；SimplePIR 诊断写 stderr。每个 32 字节记录拆为八个 32-bit chunk，所以逻辑宽度 `q` 对应 `8q` 次底层调用。共享文件的多个 Flat-active 槽只初始化一次；全部目标仍逐槽查询。预热是额外执行，不删掉测量目标。

## 基础校验、六方法正式测量与轻量分析

先执行功能检查，再执行唯一的性能驱动；所有性能程序串行，不与均衡构造实验同时运行：

```bash
.venv-wsl/bin/python scripts/test_tifs_revision_smt.py
.venv-wsl/bin/python scripts/test_tifs_revision_routing.py
.venv-wsl/bin/python scripts/verify_tifs_backend_smoke.py \
  --binary "$artifact_root/examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend" \
  --output-dir "$artifact_root/examples/tifs_revision_20260910/backend_smoke"
.venv-wsl/bin/python scripts/run_tifs_verified_backend_suite_20260910.py \
  --datasets fuel,polygon-recent,zksync-sample,polygon-multi,polygon-broad,zksync-broad \
  --methods first_fit,hybrid,activebalance,nonempty_depth,flat_active,pbc_routed \
  --height 128 --samples 100 --repeats 5 --warmup 5 --timeout 240 \
  --binary "$artifact_root/examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend" \
  --output "$artifact_root/examples/tifs_revision_20260910/verified_backend"
```

每个 workload/repeat 的 100 个目标无放回抽样，六方法共享同一列表、方法次序随机。PBC setup 在固定公开快照的全部 occupied targets 上预检匹配；主表不只测随机 dummy 查询。每个 run 保留 manifest/数据库/binary/warmup/GOMAXPROCS 的签名。`--resume` 只在签名完全一致时复用结果；如要测新环境或新 binary，应使用新的输出目录。

`completion.json` 出现后，以下仅复核已保存数据和生成统计表，不运行 PIR：

```bash
.venv-wsl/bin/python scripts/analyze_tifs_verified_results_20260910.py \
  --input examples/tifs_revision_20260910/verified_backend \
  --generated replay_analysis/generated --notes replay_analysis/notes
```

分析要求完整 `6×6×5` 矩阵，独立检查 18,000 个根、18,000 个单摘要篡改拒绝、配对目标、通信不变量和恢复字节。统计单位是**五个进程均值**，使用样本 SD；均值区间为 t(df=4)。比值为五次配对 run-mean 比值的均值。不得把 500 个目标当作 500 次独立重复，也不得把五个 run 的 p95 均值叫成合并 500 目标的 p95。

生成的 `verified_backend_summary.csv/.json`、`verified_backend_paired_ratios.csv`、`verified_backend_run_ratios.csv` 及两份 LaTeX 表都位于指定输出目录。省略 `--generated/--notes` 会写入 `manuscripts/tifs/revision_20260910/`，因此复查时建议明确指定独立输出目录。

## Windows 构造/均衡实验：与 WSL 计时分开

构造实验实际使用 Windows 11、Python **3.14.2**、NumPy **2.4.1**、Matplotlib **3.10.8**，Core Ultra 5 245K。版本在本轮结束后只读确认；不应把其时间与 WSL 后端或历史 i5-13500HX 测量合并。

同样在新空工作副本的 PowerShell 中执行，先完成上述 WSL 性能程序，再运行下列程序。这里没有并行后台任务：

```powershell
py -3.14 -m venv .venv-windows
& .\.venv-windows\Scripts\python.exe -m pip install numpy==2.4.1 matplotlib==3.10.8
New-Item -ItemType Directory -Force -Path 'manuscripts/tifs/revision_20260910/notes','manuscripts/tifs/revision_20260910/generated' | Out-Null
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --selfcheck
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --suite smoke --timeout 120
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --suite real --timeout 120
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --suite scale --timeout 120
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --suite passes --timeout 120
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --suite refinement --timeout 120
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --aggregate
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_study_20260910.py --report
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_repeats_20260910.py --timeout 120
& .\.venv-windows\Scripts\python.exe scripts/run_tifs_balance_repeats_20260910.py --summarize
```

两个构造脚本使用固定默认 `balance/`、`balance_repeats/` 路径，没有 `--output` 选项，且会跳过已有结果。因此必须区分“分析包内记录”和“在新副本完整重跑”。重复实验的第 1 次明确复用前面筛查阶段的独立进程结果，第 2/3 次才新运行；前置的 `real` 和 `refinement` 结果不可缺。`--summarize` 只汇总现存记录，并会重写该工作副本中的构造补表、说明和来源版本记录。

100k 原版 AB 的三次 120 秒上限记录属于**右删失**，不是三次 120 秒完成值；保留最后有效着色、已完成轮数和每轮历史，不把部分状态当作 20 轮结果。排序 AB 的 20 轮完成也不等于全局最优或整个负载向量已收敛。Windows RSS 包括解释器及导入，新重复按每 0.5 秒观测整进程高水位；它不是纯算法额外空间。构造重复的统计单位是三个独立进程，SD 不代表不同快照的不确定性。

## 不覆盖新稿及不混淆范围

- 本 README 中的分析、构造汇总脚本会写表格/说明；原始审查请使用独立输出目录或独立工作副本。不要在最终修订稿上直接重跑 `revise_sp_tifs_20260910.py`、`assemble_sp_tifs_revision_20260910.py` 或早期 `build_sp_revision_20260910_*` 脚本：它们可能从旧输入重建并覆盖新段落、表格或引用。
- `offline_hint_bytes` 与 `public_shared_state_bytes` 是不同的矩阵元素大小；A 当前通过 `Init` 物化，未使用 `InitCompressedSeeded`。这些值都不是已测的网络传输量。`runner_peak_rss_bytes` 是整个 server/client 合并 runner 的峰值，且在 JSON 序列化前采样，不是客户端内存。
- Full-cache 是落盘并回读全部 active digests 的独立隐私参照，零在线请求以先缓存全部数据为前提；初次传输未测，其单次最多 1,000 目标的本地 p50/p95 不是六方法的五进程配对时间。
- 新结果中的负例应随正结果一同复现：AB 最大桶更小，但串行处理/总通信不一定优于 First-fit 或 Hybrid；当前小快照下 hint 加目录远大于 Full-cache 材料。不能由固定宽度直接推导总后端成本最优。

源码和数据的打包清单、精确哈希及后验版本核验统一记录在 [reproducibility_source_manifest.json](reproducibility_source_manifest.json)。没有重新采集链数据、修改上游算法库或对外发送论文。
