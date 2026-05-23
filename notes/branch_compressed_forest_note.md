# Branch-Compressed Forest for Sparse-SMT Batch PIR

## 1. Motivation

我们当前的静态方案把固定 sparse SMT 上的 active proof-bearing nodes 映射成一个 laminar interval forest，然后在这个 forest 上做祖先异色染色。你提出的进一步想法是：

- 如果某些 active 节点在原树里只是被一长串空节点隔开，
- 那么我们能不能把这些“连续链”合并成一个 super-node，
- 从而把检索对象从单个哈希扩展成一个 proof segment，
- 再在一个多叉森林上做染色和 batch PIR。

这个方向本身是有意义的，但需要先把“能合并什么”定义得足够严格，否则 proof completion 会变得不自洽。

下面给出一版严格定义、伪算法和复杂度说明。为了兼顾可实现性与一般性，我们区分两种压缩：

1. `same-support compression`
   只合并支持区间完全相同的链。这是零额外过取的安全特例。
2. `branch compression`
   合并任意最大单链，得到真正的多叉森林。但返回的 segment 可能包含对某些目标叶无用的成员哈希，因此 proof completion 要保留 member-local metadata。


## 2. Formal Definitions

### Definition 1: Active interval forest

设 `T` 是一棵固定高度为 `h` 的 binary sparse Merkle tree，真实叶按从左到右的 occupied rank 编号。记全部 active proof-bearing nodes 为 `A(T)`。

对每个 `u in A(T)`，定义：

- `I(u) = [L(u), R(u)]`：其 sibling subtree 在 occupied-rank 上覆盖的区间；
- `delta(u)`：该节点在 proof array 中对应的 level；
- `d(u)`：该节点需要私有检索的 digest；
- `w(u)`：其单节点负载权重，当前静态实现中取 `|I(u)|`。

令 `F = (A(T), E)` 表示由区间包含关系诱导出的 laminar interval forest，其中边集 `E` 由最大真包含关系给出。


### Definition 2: Maximal unary chain

在 `F` 中，一条路径

`C = (u_1, u_2, ..., u_k)`

称为一条 maximal unary chain，如果对于所有 `1 <= i < k`：

- `u_{i+1}` 是 `u_i` 的唯一孩子；
- `u_1` 的父节点不存在，或者其父节点的孩子数不等于 `1`；
- `u_k` 没有孩子，或者其孩子数不等于 `1`。


### Definition 3: Branch-compressed super-node

对任意 maximal unary chain `C = (u_1, ..., u_k)`，定义一个 super-node `S(C)`，其包含如下元数据：

- support interval:
  `J(S) = I(u_1)`；
- member list:
  `M(S) = ((delta(u_1), I(u_1), d(u_1)), ..., (delta(u_k), I(u_k), d(u_k)))`；
- segment length:
  `lambda(S) = k`；
- relevant weight:
  `W_rel(S) = sum_{j=1}^k w(u_j)`；
- payload weight:
  `W_pay(S) = |J(S)| * lambda(S)`。

解释：

- `W_rel(S)` 表示“真正有意义的 proof material 总量”；
- `W_pay(S)` 表示如果把整个 segment 当作单条 PIR record 返回，那么在 `J(S)` 上一次命中所带来的总 payload 开销。

当且仅当所有成员满足 `I(u_1)=...=I(u_k)` 时，有

`W_rel(S) = W_pay(S)`，

这就是 `same-support compression` 的零过取情形。


### Definition 4: Branch-compressed forest

将 `F` 中每一条 maximal unary chain 收缩为一个 super-node，并保留链尾到下一层链头之间的父子关系，得到的森林记为

`F^bc = (V^bc, E^bc)`，

称为 branch-compressed forest。

`F^bc` 中的每个节点都可以有任意多个孩子，因此它是一个多叉森林。


### Definition 5: Valid coloring on the compressed forest

一个映射

`phi_bc : V^bc -> [m_bc]`

称为 `F^bc` 上的合法祖先染色，如果对任意一条 root-to-leaf super-node 路径上的两个不同节点 `S, S'`，都有

`phi_bc(S) != phi_bc(S')`。

这保证了每个颜色子库对任意目标叶至多返回一个 real segment。


## 3. Query Semantics and Proof Expansion

### 3.1 Query semantics

客户端对目标叶 `ell` 做查询时，不再查询单个 active node，而是查询一个 compressed super-node `S`。

若 `ell` 的 occupied rank 落在 `J(S)` 中，则客户端向对应颜色的子库发送一条面向 `S` 的 PIR 子查询；否则发送 dummy。


### 3.2 Proof expansion

proof completion 不再直接把一条 PIR 返回写入一个 proof slot，而是要遍历返回的 segment 内部成员。

对从颜色 `c` 返回的 real segment `S`，客户端遍历

`M(S) = ((delta_j, I_j, d_j))`

并执行：

- 若 `ell in I_j`，则将 `d_j` 写入 proof array 的 `delta_j` 位置；
- 若 `ell notin I_j`，则忽略该成员；
- 最终未写入的位置仍由 public default hash chain 填充。

因此，branch-compressed 版本的 proof completion 需要 `member-local interval metadata`，而不是只用一层 segment interval 就足够。


## 4. Pseudocode

### Algorithm A: Branch-Compressed Forest Construction

```text
Input:
  active interval forest F
Output:
  branch-compressed forest F^bc

for each root r in F do
    DFS-BUILD(r)

procedure DFS-BUILD(start):
    members <- [start]
    cur <- start
    while cur has exactly one child do
        cur <- the unique child of cur
        append cur to members

    create a super-node S from members
    set J(S) <- I(start)
    set M(S) <- [(delta(u), I(u), d(u)) for u in members]
    set lambda(S) <- |members|
    set W_rel(S) <- sum w(u)
    set W_pay(S) <- |J(S)| * lambda(S)

    for each child v of cur do
        S_child <- DFS-BUILD(v)
        connect S to S_child

    return S
```


### Algorithm B: Coloring the Branch-Compressed Forest

```text
Input:
  branch-compressed forest F^bc
  color budget m_bc
  objective Obj in {weighted, count_balanced, hybrid}
Output:
  a valid coloring phi_bc

choose a node weight model:
    either W_rel or W_pay

initialize all color loads to zero

for each root S in F^bc, processed from heavy to light do
    GREEDY-COLOR(S, ancestor_colors = empty set)

perform local recoloring moves while the objective improves

procedure GREEDY-COLOR(S, ancestor_colors):
    available <- colors not used in ancestor_colors
    choose the best color according to Obj and current loads
    assign that color to S
    recurse on the children of S
```

这一步和我们现在的 interval-forest 染色框架是同构的，只是把原来的单节点换成 super-node，负载函数换成 `W_rel` 或 `W_pay`。


### Algorithm C: Branch-Compressed Proof Expansion

```text
Input:
  target occupied rank r
  one returned segment per color
  public segment metadata tables
  default hash chain Delta[0..h-1]
Output:
  completed proof array P[0..h-1]

initialize P[t] <- Delta[t] for all proof levels t

for each color c do
    if the returned item is dummy then
        continue

    let the returned segment be S
    for each member (delta_j, I_j, d_j) in M(S) do
        if r lies in I_j then
            P[delta_j] <- d_j

return P
```


## 5. Complexity

设：

- `N = |A(T)|` 是原始 active proof-bearing nodes 数量；
- `K = |V^bc|` 是压缩后 super-node 数量；
- `m_bc` 是 compressed forest 的最小颜色数；
- `b_ell` 是目标叶 `ell` 的所有 real segments 的总成员数。

则：

1. 构造 active interval forest：
   `O(N log N)`。
2. 从 interval forest 收缩得到 branch-compressed forest：
   `O(N)`。
3. 着色：
   若沿用当前实现模板，则把原算法中的 `N` 替换为 `K` 即可；因此 greedy pass 与 local rebalance 的复杂度均随着 `K` 下降。
4. 查询索引：
   若每个颜色的 segment interval 表已排序，则为 `O(m_bc log K)`。
5. Proof expansion：
   `O(h + b_ell)`。

注意：

- 在 `same-support compression` 下，每个被命中的 super-node 内所有成员都必然属于目标 proof，因此 `b_ell` 就等于真实 segment 内成员总数，不引入额外过取。
- 在一般 `branch compression` 下，`b_ell` 可能大于真实所需 proof 节点数，因为返回的 segment 内可能含有对该叶无用的成员。


## 6. Prototype Experiment and What We Learned

我们实现了一个原型实验：

- baseline：当前 active interval forest；
- compressed_exact：对 forest 做 maximal-unary-chain contraction 后，用压缩森林自己的最小颜色数染色；
- compressed_original_budget：压缩后仍沿用 baseline 的颜色预算。

实验脚本：

- `scripts/compressed_proof_forest.py`
- `scripts/run_compressed_forest_balance_experiment.py`

核心观测指标：

- `colors`：协议所需颜色数；
- `records`：子库记录数；
- `hashes`：总哈希条目数；
- `avg_segment_length`：平均每条 record 内包含多少个哈希；
- `record_gap_norm / hash_gap_norm / weight_gap_norm / payload_gap_norm`：不同颜色间的归一化不平衡度。


## 7. Main Experimental Observation

这个实验目前给出的结论非常直接：

- 在我们当前的 `occupied-rank active interval forest` 建模下，
- branch-compressed forest **没有产生任何非平凡 segment**，
- 即 `avg_segment_length = 1.000`，
- `records / colors / hash_gap / weight_gap / payload_gap` 基本与 baseline 完全一致。

进一步的结构诊断显示：

- 在高度 `10`、稀疏度 `0.2, 0.5, 0.8, 0.9, 0.95, 0.98`、
- 每个稀疏度 `30` 个随机实例、
- 共 `180` 次试验中，
- `max_segment_length = 1`，
- `trials_with_segment_gt1 = 0`。

这说明：

> 对于我们当前使用的 active-node + occupied-rank-interval 静态模型，interval forest 本身已经是一种“无单链的多叉森林”；进一步做 unary-chain contraction 是 vacuous 的。


## 8. What This Means for the Paper

这个结论其实是有价值的，因为它把一个可能的疑问排除了：

- 不是我们没有想到“多叉 forest”；
- 而是我们现在这套静态 active-interval 抽象已经把这类可压缩单链消掉了。

因此，如果后面还想从“forest compression”里挖出真正的新收益，新的对象不能还是当前这棵 occupied-rank active forest，而应该考虑下面几条线：

1. `address-space interval forest`
   不再按 occupied rank，而按完整地址空间组织，这更接近动态更新场景。
2. `proof-slot segment model`
   不按支持区间压缩，而按 proof level 段压缩，再显式分析 overfetch。
3. `update-local repair forest`
   在动态插入/删除下，研究局部重着色和局部重建触发条件。


## 9. Current Takeaway

所以，针对你最初的问题，现在可以非常明确地说：

- “把它合并成多叉树森林”这个想法本身是合理的；
- 我们已经把它形式化并实现了原型；
- 但在**当前这套静态 occupied-rank 直接染色模型**里，它**不会带来新的压缩收益**；
- 这反过来说明，我们现在的 active-interval forest 其实已经相当接近一个结构上压过的对象了。

换句话说，这个方向不是没意义，而是它帮我们确认了：

> 真正还能继续挖的新东西，不在“再压当前这棵 forest”，而在“换一个更能暴露空洞结构或动态结构的 forest 对象”。

