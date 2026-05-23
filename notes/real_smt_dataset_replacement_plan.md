# Real SMT Workload Evaluation Plan

这份说明用于替换原来把 Xenon 写成 “real-data SMT evaluation” 的叙述。结论先说清楚：

> Xenon log entries are useful as a real key distribution, but they are not an SMT dataset. In the paper, they should not be presented as real SMT data.

更严谨的做法是把真实数据实验分成两类：

1. **Real SMT system workload / key snapshot**：来自真实使用 SMT 或 SMT-like state tree 的系统，抽取其 address、state key、storage key 或 derived key，然后映射到 SMT leaf coordinate，重建 active interval forest。
2. **Full SMT node dump**：直接拿到某个系统某个 snapshot 的 SMT 节点表、leaf key、value、branch node、root。这种公开数据很少，通常需要运行 archive/full node 或使用项目方内部 DB。

当前论文应该优先采用第 1 类，并在文字中明确称为 **SMT workload evaluation**，不要称为完整 SMT dump evaluation。

---

## 1. 候选真实系统与数据源

### 1.1 Polygon zkEVM

Polygon zkEVM 文档明确说明其 L2 state tree 采用 Sparse Merkle Trie / SMT。它是最适合写进相关工作和数据动机的真实 SMT 系统之一。

参考资料：Polygon 文档的 main state machine 页面写到 zkEVM state 以 Sparse Merkle Tree 形式存储，并解释账户参数如何分散到不同 leaf type 中：
https://docs.polygon.technology/zkEVM/architecture/zkprover/main-state-machine/

可用性：

- 官方文档清楚说明 state 存在 SMT / Sparse Merkle Trie 中。
- 但公开可直接下载的完整 state-tree node dump 不容易获得。
- 若要做严格 full SMT dump，需要运行节点或获得其 state DB。
- 短期可做 workload 级实验：从交易、账户、合约/storage key 快照中抽取 key，映射成 SMT leaf positions。

适合论文表述：

> Polygon zkEVM is a real deployment target for SMT-style state commitments. Since public full node dumps are not directly available, we use extracted key workloads rather than claiming a full SMT snapshot.

### 1.2 ZKsync Era / rollup state-diff workloads

ZKsync 文档和论文资料说明 rollup 系统依赖 state diffs / state tree 组织。公开数据方面，Matter Labs 有 `zksync-data-dump`，数据门户提供 transaction、block、log 等 parquet dump。

参考资料：

- ZKsync public dataset paper: https://arxiv.org/abs/2407.18699
- Matter Labs data-dump repository: https://github.com/matter-labs/zksync-data-dump

可用性：

- 数据集规模很大，完整下载可能达到几十 GB 到数百 GB。
- 公开 dump 更多是 transaction/log/block 维度，不一定直接包含完整 SMT leaf node dump。
- 可以抽取 addresses / storage-like keys，作为 rollup SMT workload。
- 该公开数据集 README 报告了 7,322,502 个 unique wallet addresses，因此非常适合作为大型真实 workload；但它仍然不是完整 SMT node dump。

适合论文表述：

> We evaluate on rollup-derived state-access workloads extracted from public data dumps. These workloads are mapped into SMT coordinates and used to rebuild the active proof-bearing skeleton.

注意：

- 不要说 “we use the ZKsync SMT snapshot” 除非真的拿到了 tree node dump。
- 可以说 “ZKsync-derived SMT workload” 或 “rollup-derived SMT key workload”。

### 1.3 Scroll zkTrie

Scroll 文档说明其 zkTrie 是 sparse binary Merkle Patricia Trie，用于状态和存储。虽然不是我们论文里的普通 binary SMT 完全同构，但作为 SMT-like sparse authenticated state tree 很有价值。

参考资料：Scroll zkTrie 文档明确称 zkTrie 是 sparse binary Merkle Patricia Trie:
https://docs.scroll.io/en/technology/sequencer/zktrie/

可用性：

- 可用于动机和系统背景。
- 若能拿到账户/合约/storage key snapshot，可以作为 workload。
- 完整 zkTrie node dump 通常需要跑节点或导出 DB。

### 1.4 Trillian Verifiable Map

Trillian 的 verifiable map 与 Sparse Merkle Tree / verifiable map 模型高度相关，适合作为通用 transparency-map 背景。

参考资料：Trillian verifiable-map 文档说明 map mode 是 fixed-size tree，key 经 hash 后映射到固定 leaf location:
https://transparency.dev/verifiable-data-structures/

可用性：

- Trillian 本身是框架，不提供一个统一“大型公开 map dump”。
- 具体数据取决于 personality，例如 firmware transparency / binary transparency 等。
- 如果能导出 map entries，可以作为真实 verifiable-map key workload。

### 1.5 Aptos / Diem Jellyfish Merkle Tree

Aptos/Diem 的 Jellyfish Merkle Tree 是 state commitment 的真实系统结构。它不是最普通的 binary SMT，但它属于 sparse authenticated state commitment 方向。

可用性：

- 完整 state snapshot 需要 indexer / node / BigQuery 类数据接口。
- 可以抽取 account addresses / state keys 做 workload。

---

## 2. 为什么不能继续把 Xenon 当作 SMT 数据

Xenon 数据来自 log entries，更像 Certificate Transparency / transparency log workload。

它可以用于：

- 真实 key/order 分布；
- left-balanced Merkle log 结构；
- 说明非 perfect tree / log tree 下的行为。

但它不应该用于：

- 声称真实 SMT state tree；
- 证明 SMT 高度 128/256 下的 sparse key behavior；
- 证明 rollup/account-state tree 的 workload 特征。

因此论文里应改成：

> Xenon is retained only as a transparency-log workload, not as the main SMT real-data evaluation.

或者如果篇幅紧张，直接把 Xenon 放到 appendix / secondary workload。

---

## 3. 新增实验脚本

我已经新增：

```text
scripts/run_real_smt_workload_experiment.py
```

它的作用是：从真实 key 文件中读取 address / derived key / storage key，映射到指定高度的 SMT leaf coordinate，然后运行：

1. active proof-bearing node extraction；
2. served interval forest construction；
3. exact active width `m`；
4. profile_balanced coloring；
5. dummy fraction；
6. max bucket / ideal bucket ratio；
7. coloring validity check。

### 输入格式

支持三类输入：

1. CSV：通过 `--column address` 指定 key 列；
2. JSONL：通过 `--json-field key` 指定字段；
3. 普通文本：自动用正则抽取 20-byte 或 32-byte hex strings。

### 运行示例

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\polygon_zkevm_keys.csv `
  --column key `
  --label polygon_zkevm_state_keys `
  --heights 128,256 `
  --key-mode hex-prefix `
  --limit 50000 `
  --output examples\polygon_zkevm_smt_workload_results.csv
```

如果输入是普通 address，而不是已经 hash 后的 SMT key，可以用：

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\zksync_addresses.csv `
  --column address `
  --label zksync_address_workload `
  --heights 128,256 `
  --key-mode sha256 `
  --limit 50000 `
  --output examples\zksync_smt_workload_results.csv
```

### 输出字段

输出 CSV 包含：

- `height`
- `input_records`
- `unique_keys`
- `occupied_leaves`
- `slot_collisions`
- `active_nodes`
- `exact_width`
- `avg_active_path_len`
- `max_active_path_len_by_leaf`
- `dummy_fraction`
- `ideal_max_bucket`
- `profile_max_bucket`
- `profile_size_gap`
- `profile_over_ideal`
- `profile_runtime_ms`
- `valid`

这些指标可以直接进入论文实验表。

---

## 4. 已完成 smoke test

为了确认脚本可运行，已经用一个小型地址文件做了 smoke test：

```text
examples/smt_workload_smoke_keys.csv
```

输出：

```text
examples/real_smt_workload_smoke_results.csv
```

结果示例：

```text
height=16, keys=16, occupied=16, active=30, m=6, dummy=25.00%, valid=True
height=32, keys=16, occupied=16, active=30, m=6, dummy=25.00%, valid=True
```

这个 smoke test 只验证 pipeline，不作为论文实验。

---

## 5. 论文实验部分建议改法

原来的：

```text
Xenon real-data evaluation
```

建议改成：

```text
Real SMT-Workload Evaluation
```

正文中要明确：

> Public full SMT node dumps are rarely available. We therefore evaluate on key workloads extracted from real SMT or SMT-like state-commitment systems, and reconstruct the active proof-bearing skeleton under the target SMT height.

然后实验表分三组：

1. `synthetic-uniform / clustered / adversarial`：控制变量；
2. `rollup-derived workload`：ZKsync / Scroll / Polygon zkEVM addresses or state keys；
3. `transparency-log workload`：Xenon，作为 non-SMT secondary workload。

---

## 6. 最稳的下一步

优先级建议：

1. 找一个可下载的 rollup address / transaction dump，先抽取 unique sender / receiver addresses。
2. 用 `--key-mode sha256` 映射到 height 128/256。
3. 报告 `N_active, m, dummy_fraction, profile_over_ideal, profile_max_bucket`。
4. 如果后续能导出真实 state/storage keys，再改用 `--key-mode hex-prefix` 或系统指定的 key derivation。

这样写不会过度声称，也能比 Xenon 更贴近 SMT 应用场景。
