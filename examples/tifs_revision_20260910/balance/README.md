# 2026-09-10 新增均衡实验

已记录 79 个独立进程配置：完成 78、timeout 1、失败 0、已校验结果无效 0。

原始入口：`scripts/run_tifs_balance_study_20260910.py`。历史算法/CSV未修改。所有配置、随机种子、key哈希、source哈希、原始stdout/stderr和每轮中间状态均保留。

## 正确性验证

939 个候选配置逐一枚举全部排列，共 181,665 个排列，旧纯计数Hungarian与反向排序都达到最小降序负载签名。24个小SMT验证提取记录及顺序、hybrid逐色结果、原AB逐色结果；24/24小SMT新旧AB最终负载签名一致。

这不保证后续路径总一致：comb n128/h16 的5轮结果原AB U/B=1.25、排序版=1.1875；uniform n1000/h128 的10轮结果原版=1、排序版约1.007。平局置换可改变后续候选。每候选最优不是全局色分配最优；U/B=1才认证该实例最大桶达到结构下界。

## 计时与内存口径

每个配置启动新进程并限制120秒；`coloring_s`为算法时间，扣除单独计量的checkpoint校验/文件IO。`extraction_forest_stats_s`是新压缩提取器及forest/下界统计时间，不是历史展开raw树构造时间。`measured_total_s`包含这些阶段及checkpoint开销，`subprocess_wall_s`还包括解释器/imports和输出layout文件。

`rss_bytes`/`peak_rss_bytes`是Windows实际WorkingSet/PeakWorkingSet，包含解释器与imports，不是tracemalloc、不是纯算法额外内存。默认不启用Python分配跟踪以避免其扰动，缺失allocation列表示未测。工作站未固定CPU affinity/独占资源，真实六workload各为一次执行；单次时间倍率属于新实验pilot，不能当作置信区间。n1000固定输入的独立进程重复数量与有重复时的样本SD，以 `repeated_timing_summary.json` 实际记录为准。

timeout行仅表示最后完成并校验的轮次；计时小于120秒是因为下一轮被中止。不可把partial当成20轮完成，也不可拿hybrid替代未完成AB。

## 分布和规模

uniform：按给定seed抽取无重复h位坐标。prefix-cluster：所有坐标共享高位0前缀，前缀位数记录在配置结果；剩余位均匀采样。comb：含0和单比特坐标，强制目标0具有min(h,n−1)非默认siblings，剩余坐标随机补齐。saturated：取0…n−1且n为2的幂，形成完整占用子树（n65536/h16时整个树饱和）。

规模覆盖1k/10k/100k，h16/128/256；h16不能容纳100k，因此未创建不可行配置。高度配置使用明确记录的坐标seed/哈希，不把不同坐标抽样解释成同一棵树的纯高度效应。每轮扫描所有候选根、只接受一个最佳改善；20轮任务的history保留0/1/2/5/10/20中真实完成的状态。

## 真实workload的结构比较

| Workload | n | m | 非空深度桶 | FF max | Hybrid max | 原AB max | 排序AB max | 原AB秒 | 排序AB秒 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fuel | 100 | 9 | 11 | 58 | 26 | 23 | 23 | 0.0282 | 0.0072 |
| polygon-recent | 384 | 11 | 16 | 210 | 83 | 70 | 70 | 0.2168 | 0.0572 |
| zksync-sample | 956 | 13 | 19 | 556 | 180 | 147 | 147 | 0.9346 | 0.1641 |
| polygon-multi | 1348 | 14 | 19 | 772 | 236 | 193 | 193 | 1.1705 | 0.2721 |
| polygon-broad | 7040 | 17 | 26 | 3844 | 929 | 829 | 829 | 11.3059 | 2.5652 |
| zksync-broad | 7740 | 17 | 25 | 4282 | 1162 | 911 | 911 | 10.0616 | 2.2706 |

非空深度桶/SparseTreePIR query数量比仅约1.22–1.53，而不是h/m的7.53–14.22。应把这个更强且保持目标隐私的Depth-active控制纳入主文。新旧AB六workload最大桶一致，但停止轮数可能不同；部分20轮任务虽然U/B=1，仍未满足整个降序向量的局部停止条件。

## 输出图和可复用数据

- `balance_real_quality_time.pdf/png`：六个固定真实key workload的结构质量和着色时间；每系列名称明确算法，时间不含PIR。
- `balance_round_budget.pdf/png`：1k/10k/100k uniform的完整扫描轮数与U/B关系，timeout在曲线标注。
- `real_comparison.csv`：工作量、非空深度控制、四种算法的质量/时间/内存。
- `per_run.csv`、`runs/*/result.json`：所有独立配置原始结果（CSV同时有n与N，区分大小写；JSON保留原字段）。
- `runs/*/round_history.json`：真实每轮checkpoint。
- `runs/*/layout_records.csv`：完成任务的node index、SMT depth、target rank interval、weight、color，可用于同一真实digest的PIR物化；本实验自身不执行PIR、也不伪称root验证。

原版/排序候选的速度是实测实现比较；不把其差值宣传成private-proof服务速度，后者需独立backend及root验证实验。
