# Fixed-B and Budgeted Coloring for Better Subdatabase Balance

## 1. Problem Reframing

我们现在真正关心的问题不是：

- 颜色数是不是最少，

而是：

- 在保证祖先异色约束的前提下，最大的颜色子库会不会过大，
- 从而拖慢 batch PIR 的整体效率。

因此，我们把原来的“exact-width coloring”问题，扩展成下面两个更偏系统优化的版本。


## 2. Formal Definitions

设 `T` 是一棵固定 binary sparse SMT，`A(T)` 是全部 active proof-bearing nodes，`N = |A(T)|`。设

- `m` 是 exact active width，也就是任一真实 proof path 上 active 节点数的最大值；
- `Phi_B(T)` 表示所有满足祖先异色约束、且颜色取值属于 `[B]` 的合法着色集合。

由我们已有的 exact-width 结论可知：

- 当 `B < m` 时，`Phi_B(T)` 为空；
- 当 `B >= m` 时，`Phi_B(T)` 非空。


### Definition 1: Fixed-B valid coloring

对任意整数 `B >= m`，一个映射

`phi : A(T) -> [B]`

称为一个 `B`-budget valid coloring，如果对任意真实叶 `ell`，其 active proof path `Path(ell)` 上任意两个不同节点 `u != v` 满足

`phi(u) != phi(v)`。

也就是说，`B` 不再固定等于最小宽度 `m`，而是被看作一个可调预算。


### Definition 2: Fixed-B min-max-size objective

对一个合法着色 `phi in Phi_B(T)`，记第 `c` 个颜色子库大小为

`N_c(phi) = |{u in A(T) : phi(u) = c}|`。

定义固定预算 `B` 下的 min-max-size 目标为

`M_B(phi) = max_{c in [B]} N_c(phi)`。

相应的优化问题是

`OPT_size(B) = min_{phi in Phi_B(T)} M_B(phi)`。

这个目标直接对应“最大颜色子库有多大”。


### Definition 3: Budgeted online-cost objective

仅仅最小化 `M_B(phi)` 还不够，因为更大的 `B` 会带来更多 PIR 子查询。因此我们再定义一个 budgeted 目标。

设底层 PIR 后端对一个大小为 `s` 的子库有：

- query-generation surrogate `Q(s)`；
- extraction surrogate `E(s)`；
- parallel server-latency surrogate `S(s)`。

则对一个 `B`-budget 着色 `phi`，定义 online cost proxy 为

`C_B(phi) = sum_{c=1}^B Q(N_c(phi)) + sum_{c=1}^B E(N_c(phi)) + beta * max_{c in [B]} S(N_c(phi))`

其中 `beta > 0` 用于调节我们对并行服务器瓶颈的重视程度。本文原型实验中默认取 `beta = 1`。

对应的 budgeted 问题是

`OPT_budget(Delta) = min_{B in {m,...,m+Delta}} min_{phi in Phi_B(T)} C_B(phi)`。

这里 `Delta` 表示允许比 exact width 多使用多少个颜色。


## 3. Basic Bounds and Properties

### Proposition 1: Counting lower bound

对任意 `B >= m` 和任意合法着色 `phi in Phi_B(T)`，都有

`M_B(phi) >= ceil(N / B)`。

证明很直接，因为 `N` 个 active 节点被分配到 `B` 个颜色类中，至少有一个颜色类大小不小于平均值。


### Proposition 2: Monotonicity in B

`OPT_size(B)` 关于 `B` 单调不增。

原因是：若 `B' > B`，则任意 `B`-budget 合法着色都可视为一个 `B'`-budget 合法着色，因此可行域只会扩大。


### Interpretation

这两个基本事实说明：

- `B = m` 是“最少 query 数”的点；
- `B > m` 才给了我们进一步压小最大子库的空间；
- 但压小最大子库是否值得，还要看 `Q/E/S` 带来的总在线代价。


## 4. Prototype Algorithm

### 4.1 Fixed-B Min-Max-Size Coloring

我们实现的原型不是全局最优算法，而是一个启发式的 lexicographic min-max 着色器。

对当前负载向量 `(N_1,...,N_B)`，定义其降序签名为

`Sig_N = sort_desc(N_1,...,N_B)`。

对 weighted loads `(W_1,...,W_B)`，定义

`Sig_W = sort_desc(W_1,...,W_B)`。

则固定 `B` 的比较目标为

`Obj(phi) = (Sig_N(phi), max_c W_c(phi), Sig_W(phi))`。

也就是说：

1. 首先最小化整个降序子库大小向量，这等价于先压最坏 bucket，再压第二坏 bucket，依此类推；
2. 然后再用 weighted-load profile 做 tie-break。

实现上分两阶段：

- greedy phase:
  按若干个确定性的根/子节点遍历顺序进行多起点贪心着色；
- local repair phase:
  枚举合法单点重染色，只要 `Obj(phi)` 改善就接受。


### Algorithm A: Fixed-B Min-Max-Size Coloring

```text
Input:
  interval forest F
  color budget B >= m
Output:
  a valid coloring phi in Phi_B(T)

best_phi <- null

for each deterministic traversal order pi do
    initialize all color loads to zero
    greedily color F top-down under order pi:
        for each node u:
            among colors not used on the ancestor chain,
            choose the color minimizing the candidate objective
            (Sig_N, max W_c, Sig_W)
    repeat local one-node recoloring moves
        while the objective improves
    keep the best local optimum across all starts

return best_phi
```


### 4.2 Budgeted Search

在 budgeted 版本里，我们不是直接设计一个新的大算法，而是把 fixed-B 版本当作子程序，对 `B = m, m+1, ..., m+Delta` 做扫描。


### Algorithm B: Budgeted Min-Max-Size Search

```text
Input:
  interval forest F
  exact width m
  extra-color allowance Delta
  backend surrogates Q, E, S
Output:
  best budget B* and its coloring phi*

best_score <- +infinity

for B = m to m + Delta do
    phi_B <- Fixed-B-Min-Max-Size(F, B)
    compute C_B(phi_B)
    if C_B(phi_B) improves the best score:
        keep (B, phi_B)

return (B*, phi*)
```


## 5. Complexity

设：

- `N = |A(T)|`；
- `B >= m`；
- `R` 是局部重平衡轮数。

则在当前原型里：

1. 单次 fixed-B greedy 着色约为 `O(N * B log B)`；
2. 单次局部重平衡最坏为 `O(R * N * B)` 级别；
3. budgeted 扫描 `B = m,...,m+Delta` 的总代价是在单次 fixed-B 原型外再乘一个 `Delta+1`。

这是一个可运行的原型复杂度，而不是最终论文中应主张的最优算法复杂度。


## 6. Prototype Experiment

实验脚本：

- `scripts/budgeted_minmax_coloring.py`
- `scripts/run_budgeted_coloring_experiment.py`

默认配置：

- sparse SMT height `h = 10`
- sparsities: `0.5, 0.8, 0.9, 0.95, 0.98`
- `20` trials per sparsity
- tested budgets: `B = m, m+1, ..., m+4`
- budgeted objective backend: `sealpir_like`
- online proxy:
  `query_ms + extract_ms + server_max_ms`


## 7. Main Results

### 7.1 B > m does reduce the largest subdatabase

在全部实验汇总上：

- `min_max_size(B=m)` 的平均最大子库大小约为 `77.54`
- `B=m+1` 时降到 `59.67`
- `B=m+2` 时降到 `48.65`
- `B=m+3` 时降到 `41.51`
- `B=m+4` 时降到 `36.47`

因此，相对于 `min_max_size(B=m)` 自己的 exact-width 基线：

- `B=m+1`: 最大子库下降约 `23.0%`
- `B=m+2`: 下降约 `37.3%`
- `B=m+3`: 下降约 `46.5%`
- `B=m+4`: 下降约 `53.0%`

这说明：

> 如果我们允许多用几个颜色，确实能显著压低最大的颜色子库。


### 7.2 But the online proxy gets worse under the current backend model

同一组实验里，`sealpir_like` online proxy 从

- `24.20 ms` at `B=m`

上升到

- `26.53 ms` at `B=m+1`
- `28.92 ms` at `B=m+2`
- `31.36 ms` at `B=m+3`
- `33.82 ms` at `B=m+4`

这意味着：

- 虽然 `max_bucket` 变小了，
- 但增加颜色数带来的 query/extract 开销在当前 surrogate 下更大，
- 所以 budgeted 搜索最终仍然选择 `B = m`。


### 7.3 Compared with the current exact-width best baseline

需要诚实地指出：

- 在 `B = m` 时，我们这个 `min_max_size` 原型本身还不是最强的 exact-width solver；
- 当前实验里，`hybrid` 往往给出更小的 `max_bucket` 和更好的 online proxy。

例如在 overall 结果中：

- `hybrid` 的平均最大子库约为 `48.29`
- `min_max_size(B=m+2)` 约为 `48.65`
- `min_max_size(B=m+3)` 才下降到 `41.51`
- `min_max_size(B=m+4)` 进一步下降到 `36.47`

所以更准确的结论是：

> “放宽预算 B > m” 这件事是有效的；
> 但“如何在 fixed-B 下求到真正好的 min-max coloring” 还没有被我们这个原型完全解决。


## 8. What This Means for the Paper

这一组结果其实很有价值，因为它把三个层次分清楚了。

### Level 1: Exact-width theorem

`m` 是最小合法 batch width，这个理论仍然成立。


### Level 2: Systems tradeoff

`m` 不一定是最小最大子库的最优点；允许 `B > m` 的确能改善最大 bucket。


### Level 3: End-to-end reality

是否值得把 `B` 放大，不能只看 `max_bucket`，还要看新增 batch width 带来的在线开销。

因此论文里更合理的表达应该是：

- `exact-width` 给出了最小 batch width；
- `budgeted coloring` 则研究“多花几个颜色预算，能否换到更小的最大子库”；
- 这本质上是一个 batch width 和 subdatabase balance 之间的系统权衡问题。


## 9. Immediate Next Step

如果要把这部分真正推进成论文亮点，下一步最值得做的不是继续压缩森林，而是：

1. 改进 fixed-B min-max solver
   例如加 swap moves、局部交换、或者小规模 ILP/DP 对照。
2. 把 budgeted objective 接到 concrete backend
   而不是只用 `sealpir_like` surrogate。
3. 画出 `B`-sweep frontier
   即 `B` vs `max_bucket` vs `online proxy` 的 Pareto 曲线。

这样这一部分就会从“一个合理直觉”升级成真正有说服力的系统优化贡献。

