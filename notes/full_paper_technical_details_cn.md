# Virtual-Swapped TreePIR 全部技术细节讲解

这份文档是对当前英文论文的完整技术解释。它不是论文正文，而是帮助我们自己、答辩听众、合作者或审稿前自查理解整套方案的详细说明。

核心问题可以概括为：

**给定一个固定的 Sparse Merkle Tree（SMT），客户端想私密获得某个已存在叶子的 membership proof。我们要把 proof 中真正需要从服务器取的 sibling digest 组织成若干个 PIR 子数据库，使客户端每个颜色子库查一次，最终恢复完整高度 `h` 的 SMT proof。**

本文不是提出新的哈希树，也不是提出新的 PIR 密码协议。本文提出的是一个 **SMT proof retrieval organization layer**：在 SMT 的真实 proof 结构和 PIR backend 之间，定义到底哪些节点要存、怎么索引、怎么染色、怎么批量查询、怎么补全 proof。

---

## 1. 为什么这个问题存在

### 1.1 Merkle proof 的隐私问题

Merkle tree 的作用是让服务器发布一个 root hash，客户端拿到某个叶子值和一条 proof 后，可以验证该叶子确实被 root 承诺。

普通 membership proof 的形式是：

- 目标叶子 digest；
- 从叶子到根的每一层 sibling digest；
- 目标叶子位置的 path bits；
- 最后从底向上重算 root。

如果客户端直接对服务器说：

> 请给我 leaf `x` 的 Merkle proof。

服务器马上知道客户端正在查 `x`。这就是隐私泄漏。

PIR 可以隐藏“客户端查数据库里的哪条记录”，但 Merkle proof 不是一条记录，而是一组 sibling digest。因此我们需要把 proof retrieval 组织成一个 batch PIR 问题。

### 1.2 TreePIR 的思想

TreePIR 的核心思想是：

1. 对 Merkle proof 相关节点染色。
2. 同一条 proof path 上的节点颜色必须互不相同。
3. 所有同色节点放入一个 PIR subdatabase。
4. 查询某个 proof 时，每种颜色最多需要一个节点。
5. 客户端对每个颜色子库发一次 PIR query。

这样，一个 proof retrieval 就变成：

```text
one proof = one PIR query per color
```

问题是，TreePIR 原文主要面向 perfect binary tree 的结构。而 SMT 有大量空子树，不能直接把完整满树都放进 PIR 数据库。

### 1.3 SMT 的特殊性

SMT 是 Sparse Merkle Tree。它有一个很大的逻辑高度 `h`，例如 `h=256`。理论上它有 `2^h` 个叶子位置，但真实 occupied leaves 可能很少。

SMT 的关键性质是：

```text
空子树的 hash 是公开 default hash，可由高度唯一确定。
```

令：

```text
Delta_0 = default empty leaf hash
Delta_{t+1} = H(Delta_t || Delta_t)
```

那么高度为 `t` 的空子树 digest 就是 `Delta_t`。

因此，一个完整 SMT proof 仍然有 `h` 个 proof levels，但不是每一层都需要服务器私密返回：

- 如果 sibling subtree 非空，则该 sibling digest 是真实数据，需要 PIR 获取；
- 如果 sibling subtree 为空，则 digest 是公开 default hash，客户端自己补。

这就产生了本文最核心的分离：

```text
验证结构：完整高度 h 的 SMT proof。
检索结构：只包含真实非空 sibling digest 的 active proof structure。
```

---

## 2. 本文到底解决什么，不解决什么

### 2.1 解决的问题

本文解决的是：

```text
固定 public SMT snapshot 上，occupied leaf 的 membership proof 的 target-private retrieval。
```

也就是说：

- 树是固定的；
- 树的 active structure 和 metadata 可以公开；
- 客户端要隐藏自己查的是哪个真实叶子；
- 查询结果必须能恢复标准高度 `h` 的 SMT membership proof；
- 底层可以接不同 PIR backend。

### 2.2 不解决的问题

当前论文不声称解决：

- 隐藏整棵树的 occupied leaf 分布；
- 隐藏 public metadata；
- 对 arbitrary absent key 的 non-membership proof retrieval；
- 完整动态更新安全模型；
- 一个新的生产级 PIR backend；
- 对所有 SealPIR/Spiral/SimplePIR 部署都一定最优。

这几个边界要主动说清楚，因为它们是审稿人最可能问的点。

---

## 3. 全部核心对象和符号

### 3.1 SMT 基本对象

设：

```text
T: 固定二叉 Sparse Merkle Tree
h: 树高
L: occupied real leaves 集合
n = |L|
```

SMT 的叶子逻辑位置是 `0, 1, ..., 2^h - 1`。

在代码和图中也可能使用 heap index：

- root index = `1`
- 左子 = `2i`
- 右子 = `2i+1`
- 高度 `h` 的叶子 heap index 在 `[2^h, 2^{h+1}-1]`

论文正文更关注逻辑位置和 real-leaf rank，而不是 heap index。

### 3.2 default-empty hash chain

公开默认哈希链：

```text
Delta_0: 空叶子默认 hash
Delta_{t+1} = H(Delta_t || Delta_t)
```

用途：

- proof completion 时填充空 sibling level；
- 不进入 PIR subdatabase；
- 所有客户端都能本地计算。

### 3.3 subtree real-leaf count

对 SMT 中任意节点 `u`，定义：

```text
cnt(u) = u 的 subtree 中真实 occupied leaves 数量
```

如果：

```text
cnt(u) = 0
```

则 `u` 是空子树，其 digest 是 default hash，不需要服务器存入 PIR 数据库。

### 3.4 active proof-bearing node

一个非根节点 `u` 是 active proof-bearing node，当且仅当：

```text
cnt(u) > 0
and
cnt(sib(u)) > 0
```

解释：

- `cnt(u)>0`：`u` 自己是非空 subtree，digest 是真实数据，不是 default hash；
- `cnt(sib(u))>0`：`u` 的兄弟子树中也有真实叶子，所以 `u` 会作为某些目标叶子的 proof sibling 出现。

因此 active proof-bearing node 是：

```text
真实非空，并且可能出现在至少一个 membership proof 中的 sibling-side node。
```

所有 active nodes 构成：

```text
A(T)
```

这些节点才会进入 PIR subdatabases。

### 3.5 active swapped proof path

对一个真实目标叶子 `ell in L`，完整 SMT proof 有 `h` 个 sibling levels。

其中只有非空 sibling subtree 对应的节点需要 PIR 检索。

定义：

```text
Path(ell) = ell 的完整 proof 中所有 active proof-bearing nodes
```

注意：

```text
Path(ell) 不是完整 proof。
Path(ell) 只是完整 proof 里需要私密检索的 active part。
```

完整 proof 长度仍然是 `h`。

### 3.6 exact active width m

定义：

```text
m = max_{ell in L} |Path(ell)|
```

含义：

- 所有真实叶子的 active proof path 中，最长那条有多少个真实 sibling digest；
- 这就是本文 TreePIR-style interface 下最少需要的颜色数；
- 也是 batch PIR 的 exact active width。

一般有：

```text
m <= min(h, n-1)
```

这个界是 tight 的。如果 occupied leaves 分布很“梳子状”，可以让 `m=h`。所以不能无条件声称 `m` 一定远小于 `h`。

---

## 4. served interval 是什么

这是全文最容易误解的概念。

### 4.1 served interval 不是节点自己的 subtree interval

对 active node `u`，它进入 proof 的方式是：

```text
u 是某些 target leaves 的 sibling proof node。
```

哪些 target leaves 会用到 `u`？

答案是：

```text
位于 sib(u) 子树里的 target leaves。
```

所以 `u` 的 served interval 是：

```text
I_srv(u) = sib(u) 覆盖的真实 target leaves 的 rank interval
```

不是：

```text
u 自己覆盖的 leaves。
```

这是核心。

### 4.2 real-leaf rank endpoint

将所有 occupied leaves 按逻辑位置排序：

```text
L = [ell_0, ell_1, ..., ell_{n-1}]
```

定义 rank：

```text
r(ell_i) = i
```

那么 metadata 中的 interval endpoint 使用 rank：

```text
I_srv(u) = [left_rank, right_rank]
```

好处：

- metadata endpoint 与真实叶子数量 `n` 相关；
- 不需要在 metadata 中保存完整 `h` 位 logical coordinate；
- 在 `h=256` 时仍然紧凑；
- 客户端只需要知道目标 leaf 的 rank。

### 4.3 served interval 的判定关系

对任意真实叶子 `ell`：

```text
u in Path(ell) iff r(ell) in I_srv(u)
```

也就是说，客户端想知道颜色 `c` 里是否有真实节点要查，只需要在颜色 `c` 的 interval metadata 里查 `r(ell)` 是否落入某个 interval。

### 4.4 interval forest

所有 served intervals 形成 laminar family：

```text
任意两个 interval 要么不相交，要么一个包含另一个。
```

原因是二叉树的 subtree intervals 天然是层叠结构。

根据 interval containment 建立森林：

```text
如果 I_srv(v) 是 I_srv(u) 的最大真包含子区间，则 v 是 u 的孩子。
```

得到的就是 interval forest。

这个 forest 不是 SMT 原树本身，而是 active proof-bearing nodes 的 conflict/containment structure。

---

## 5. 服务器到底存什么

服务器有两类存储：

1. 私有 PIR 数据库内容；
2. 公开 metadata。

### 5.1 私有 PIR subdatabases

对每个颜色 `c in [m]`，定义：

```text
D_c = {u in A(T): phi(u)=c}
```

`D_c` 是第 `c` 个 PIR subdatabase。

每条记录只需要存：

```text
digest(u)
```

即 Merkle proof 里要返回的 sibling digest。

通常 digest 是 32 bytes，例如 SHA-256。

私有 payload 大小：

```text
32 * |A(T)| bytes
```

如果按颜色拆分：

```text
private payload of D_c = 32 * |D_c| bytes
```

### 5.2 public metadata tables

每个颜色有一个 public metadata table：

```text
M_c = [(I_srv(u), delta(u)) for u in D_c]
```

其中：

- `I_srv(u) = [left_rank, right_rank]`
- `delta(u)` 是 proof level，从叶子向根数；
- `M_c` 按 interval left endpoint 排序；
- metadata 与 `D_c` 的记录顺序一一对应。

一个 compact metadata record 可以设计成：

```text
left_rank: 64-bit
right_rank: 64-bit
proof_level: small integer / aligned field
flags/alignment
```

论文实验里使用 24 bytes per metadata record 的估算。

因此 public metadata 大约是：

```text
24 * |A(T)| bytes
```

注意：

```text
metadata 是公开的，不进入 PIR payload。
```

但是 metadata 仍然是系统成本，需要在实验里报告。

### 5.3 服务器不存什么

服务器的 PIR database 不存：

- empty subtree default digest；
- 不会出现在任何 proof 中的节点；
- 完整满树的所有节点；
- proof path 的每个 level；
- 每个目标叶子的完整 proof。

这些是本文 storage gain 的来源。

---

## 6. 客户端需要知道什么

对目标 leaf `ell`，客户端公开/本地输入包括：

```text
h: SMT height
ell 的逻辑位置
r(ell): ell 在 occupied leaves 中的 rank
default hash chain Delta_0 ... Delta_{h-1}
每个颜色的 metadata table M_c
底层 PIR public parameters
```

客户端私有输入是：

```text
目标 leaf ell
```

服务器允许知道：

- 树高；
- active structure；
- metadata；
- 每个子库大小；
- 颜色分配；
- 每次查询有 exactly `m` 个 subqueries。

服务器不应该知道：

- 客户端查哪个 leaf；
- 哪些颜色是真实命中；
- 哪些颜色是 dummy；
- 每个颜色里查哪个 index。

---

## 7. 离线算法：构建数据库和 metadata

离线阶段由服务器对固定 SMT snapshot 执行。

### 7.1 输入输出

输入：

```text
T: fixed SMT snapshot
L: occupied leaves
R1: profile balancing rounds
```

输出：

```text
D_1 ... D_m: color PIR subdatabases
M_1 ... M_m: public metadata tables
phi: coloring
m: exact active width
```

### 7.2 Step 1：排序真实叶子并分配 rank

把 occupied leaves 按逻辑位置排序：

```text
ell_0 < ell_1 < ... < ell_{n-1}
```

分配：

```text
r(ell_i)=i
```

后续所有 served interval endpoint 都使用 rank。

### 7.3 Step 2：构建 compressed non-default skeleton

不用 materialize 完整 `2^h` 树。

只从 occupied leaves 往上构造包含真实节点的路径，并压缩掉 unary non-default paths。

直觉：

- 如果一个路径上长期只有一个非空孩子，那么这些节点不会产生 active sibling proof material；
- 只有出现两个非空孩子的 branching point 才会产生真实 sibling proof node。

compressed skeleton 的作用是：

```text
高效找到所有 branching ancestors。
```

### 7.4 Step 3：提取 active proof-bearing nodes

对 skeleton 中每个 branching node `p`：

- 它在原 SMT 中有两个非空 child roots；
- 每个 child root 都会作为另一侧 leaves 的 proof sibling；
- 因此两个 child roots 都是 active proof-bearing nodes。

对每个 active node `u`：

```text
s = sib(u)
I_srv(u) = s 覆盖的真实叶 rank interval
delta(u) = h - depth(u)
digest(u) = subtree hash of u
```

将 `u` 加入 `A(T)`。

### 7.5 Step 4：构造 interval forest

将所有 active nodes 按：

```text
left endpoint ascending
interval length descending
```

排序。

然后用栈根据 interval containment 构造 forest。

每个 forest node 对应一个 active proof-bearing node。

### 7.6 Step 5：计算 exact active width m

在 interval forest 中计算最大 root-to-leaf chain length：

```text
m = max forest depth
```

等价于：

```text
m = max_{ell in L} |Path(ell)|
```

### 7.7 Step 6：first-fit 可行染色

先做一个合法初始染色。

遍历 forest：

```text
对每个节点 u：
  used = ancestor chain 上已经使用的颜色
  给 u 分配 [m] 中最小的未使用颜色
```

因为任何 path 最长只有 `m`，所以一定能找到颜色。

first-fit 的作用只是：

```text
快速构造一个 valid exact-width coloring。
```

它不是本文的主要平衡算法。

### 7.8 Step 7：profile_balanced refinement

在 first-fit 的基础上做平衡优化。

目标是减少：

```text
M(phi) = max_c |D_c|
```

也就是最大颜色子库大小。

原因：

很多 PIR backend 的并行 latency 或 server work 会被最大子库支配。

### 7.9 Step 8：生成子库和 metadata

染色完成后：

```text
for each color c:
  D_c = all active nodes with phi(u)=c
  M_c = corresponding [(I_srv(u), delta(u))]
```

`D_c` 中记录是 private digest。

`M_c` 是 public metadata，按 interval 排序，支持二分查找。

---

## 8. profile_balanced 算法细节

### 8.1 为什么不能只做单节点 recoloring

单节点 recoloring 的问题是：

- 一个节点颜色受所有祖先和后代约束；
- 移动一个节点可能破坏 path-distinctness；
- 高层颜色选择会影响整片子树的可用颜色；
- 很容易陷入局部不平衡。

因此本文使用 subtree-level color permutation。

### 8.2 legal subtree permutation

取 interval forest 中一个 rooted subtree `U`。

设：

```text
AncestorColors(U) = U 的 strict ancestor chain 上使用过的颜色
A(U) = [m] \ AncestorColors(U)
```

`A(U)` 是 `U` 内节点允许使用的颜色集合。

如果当前 coloring 合法，那么 `U` 内所有节点颜色都在 `A(U)`。

对 `A(U)` 做一个 permutation：

```text
pi_U: A(U) -> A(U)
```

并对 `U` 内所有节点统一替换：

```text
color(x) = pi_U(color(x))
```

这一定保持合法性：

- 子树内部原本颜色不同，permutation 后仍然不同；
- 子树外不可比节点与 `U` 不在同一 proof path；
- 子树祖先颜色不在 `A(U)` 中，所以不会冲突。

### 8.3 bucket profile 目标

定义每个颜色的 count load：

```text
N_c = |D_c|
```

定义 lexicographic signature：

```text
Psi(phi) = sort_down(N_1, ..., N_m)
```

比较两个 coloring 时，先看最大 bucket，再看第二大 bucket，以此类推。

目标：

```text
让 Psi(phi) 字典序下降。
```

这等价于优先降低最大子库，再整体拉平 profile。

### 8.4 local assignment cost

对一个候选 subtree `U`：

定义：

```text
C_U(a) = U 内当前颜色为 a 的节点数量
```

如果把 source color `a` 映射到 target color `b`，则 target bucket 的新局部贡献为：

```text
N_b - C_U(b) + C_U(a)
```

算法用二次成本：

```text
K_U[a,b] = (N_b - C_U(b) + C_U(a))^2
```

然后求 minimum-cost perfect matching，得到一个颜色 permutation。

这一步可以用 Hungarian algorithm，复杂度 `O(m^3)`。

### 8.5 接受规则

matching 得到的是候选 move，不一定接受。

真正接受条件是：

```text
Psi(candidate) < Psi(current)
```

也就是说，只有全局 bucket profile 真正变好，才执行这个 subtree permutation。

每轮从所有候选 subtree 中选最优改进。

### 8.6 终止性

每次接受 move 都严格降低 `Psi`。

合法 coloring 数量有限。

因此算法必然终止。

终止时达到：

```text
subtree-permutation local optimum
```

注意：

```text
这不是全局最优保证。
```

我们提供的是 a posteriori certificate。

---

## 9. 查询算法：客户端怎么发 batch PIR

### 9.1 输入输出

输入：

```text
target leaf ell
rank r(ell)
D_1 ... D_m
M_1 ... M_m
PIR public parameters
```

输出：

```text
m 个 PIR subqueries
local target map tau_1 ... tau_m
```

### 9.2 对每个颜色查 metadata

对每个颜色 `c=1...m`：

1. 在 `M_c` 的 interval projection 中二分查找 `r(ell)`；
2. 如果存在唯一 interval 包含 `r(ell)`：
   - 说明颜色 `c` 有一个真实 proof node；
   - 该 metadata record 的位置就是 `D_c` 中的 index `j_c`；
   - 生成 real PIR query targeting `D_c[j_c]`；
   - 本地记录 `tau_c = j_c`。
3. 如果没有 interval 包含：
   - 说明该颜色对当前 proof 是 dummy；
   - 生成 dummy PIR query over `D_c`；
   - 本地记录 `tau_c = bottom`。

### 9.3 为什么每个颜色最多一个 real target

因为 same-color served intervals 是 disjoint。

如果同一颜色中两个 interval 同时包含 `r(ell)`，则两个 active nodes 会同时出现在同一个 proof path 上，违反 valid coloring。

所以二分搜索结果唯一。

### 9.4 fixed-shape batch

无论目标 leaf 是谁，客户端都发送：

```text
exactly m PIR subqueries
```

每个颜色一个。

服务器看到的 batch shape 固定：

```text
query to D_1, query to D_2, ..., query to D_m
```

服务器不知道：

- 哪些 query 是 real；
- 哪些 query 是 dummy；
- real query 选了哪个 index。

### 9.5 dummy query 怎么生成

dummy query 必须和普通 PIR query 分布不可区分。

实现上可以：

```text
从 D_c 中随机选择一个 public dummy target 或随机 valid index，
生成一条普通 PIR query，
客户端丢弃返回值。
```

如果某个颜色子库为空，有两种处理：

- setup 时移除空颜色；
- 或者 pad 一个 public dummy record。

当前 exact-width coloring 通常每个 active color 都非空，因为最大 active path 使用了所有颜色。

---

## 10. proof completion 算法

### 10.1 问题

PIR 返回的只是 active nodes，不是完整 proof。

但 SMT verifier 需要长度为 `h` 的 proof：

```text
P[0], P[1], ..., P[h-1]
```

其中 `P[t]` 是第 `t` 层 sibling digest。

### 10.2 输入输出

输入：

```text
target leaf position ell
target leaf digest a_0
metadata M_c
local target map tau_c
PIR outputs sigma_c
default hash chain Delta_0 ... Delta_{h-1}
```

输出：

```text
complete proof array P[0...h-1]
recomputed root rho
```

### 10.3 算法步骤

1. 初始化：

```text
for t=0...h-1:
  P[t] = Delta_t
```

也就是先假设所有 sibling 都是空子树。

2. 处理每个颜色：

```text
for c=1...m:
  if tau_c != bottom:
    (I_srv, delta) = M_c[tau_c]
    P[delta] = sigma_c
```

把真实 PIR 返回的 digest 写入对应 proof level。

3. 从叶子向上重算 root：

```text
x = target leaf digest
for t=0...h-1:
  if path bit at level t says target is left:
    x = H(x || P[t])
  else:
    x = H(P[t] || x)
rho = x
```

4. 检查 `rho` 是否等于 public committed root。

### 10.4 为什么正确

对每个 proof level：

- 如果 sibling subtree 非空，那么对应 active node 会通过 PIR 返回并写入；
- 如果 sibling subtree 为空，那么初始化的 `Delta_t` 正是正确 digest。

所以每个 slot 都正确。

因此最终重算 root 正确。

---

## 11. 一个完整小例子

假设 height-4 SMT，occupied leaves 为：

```text
{16, 17, 19, 22, 28}
```

active proof-bearing nodes 包括：

```text
3, 2, 5, 4, 9, 8, 17, 16
```

最长 active path 长度：

```text
m = 4
```

一种 first-fit coloring 可能是：

```text
D_1 = {3}
D_2 = {5, 2}
D_3 = {9, 4}
D_4 = {17, 16, 8}
```

bucket sizes：

```text
(1,2,2,3)
```

profile_balanced 后：

```text
D_1 = {3, 2}
D_2 = {5, 4}
D_3 = {9, 8}
D_4 = {17, 16}
```

bucket sizes：

```text
(2,2,2,2)
```

查询 leaf `19`：

- metadata 查到颜色 1 需要 node `3`；
- 颜色 2 需要 node `5`；
- 颜色 3 需要 node `8`；
- 颜色 4 没有真实节点，发送 dummy。

客户端发送：

```text
PIR(D_1, index of 3)
PIR(D_2, index of 5)
PIR(D_3, index of 8)
DummyPIR(D_4)
```

收到 digest 后：

- 把 `3,5,8` 写入对应 proof levels；
- 其余 level 保持 default hash；
- 从 leaf `19` 向上重算 root。

这样即使颜色 4 是 dummy，完整 SMT proof 仍然可以恢复。

---

## 12. 安全模型和隐私证明

### 12.1 public leakage

服务器允许知道：

```text
h
default hash chain
active node set
metadata tables M_c
color assignment
subdatabase sizes N_c
exact active width m
每次查询固定 m 个 subqueries
```

这是 public structure。

### 12.2 hidden information

服务器不应知道：

```text
target leaf ell
Path(ell)
哪些颜色 real
哪些颜色 dummy
每个颜色中的 selected index
```

### 12.3 privacy game

攻击者选择两个真实目标叶：

```text
ell_0, ell_1
```

challenger 随机选 `b`，生成 `ell_b` 的 batch query transcript。

攻击者猜 `b`。

如果猜测优势可忽略，则满足 target privacy。

### 12.4 证明思路

对每个颜色：

- real vs real：由 PIR query privacy 隐藏 index；
- real vs dummy：dummy query 与普通 query 不可区分；
- dummy vs dummy：分布相同。

对 `m` 个颜色做 hybrid argument。

因此整个 batch transcript 对 `ell_0` 和 `ell_1` 不可区分。

注意：

```text
这个隐私是 relative to public leakage。
```

它不隐藏整棵树结构。

---

## 13. 复杂度

设：

```text
N = |A(T)| active proof-bearing nodes
m = exact active width
h = SMT height
N_c = |D_c|
```

### 13.1 离线构建

提取 active nodes、构建 interval forest、排序 metadata：

```text
O(N log N)
```

空间：

```text
O(N)
```

如果从 occupied leaves 构建 compressed skeleton，还与 occupied leaf 数量和路径插入成本有关，但核心 PIR-facing structure 是 `N` 规模。

### 13.2 query indexing

每个颜色做一次二分：

```text
sum_{c=1}^m O(log N_c) <= O(m log N)
```

### 13.3 profile_balanced

每轮：

- 给每个 subtree 计算 histogram：`O(Nm)`；
- 每个 subtree 做一个 `m x m` matching：`O(m^3)`；
- `N` 个 subtree。

所以 `R1` 轮：

```text
O(R1 * N * m^3)
```

额外空间：

```text
O(Nm)
```

### 13.4 proof completion

初始化长度 `h` proof array，重算 `h` 层 hash：

```text
O(h)
```

空间：

```text
O(h)
```

### 13.5 总在线客户端工作

```text
O(m log N + h)
```

其中：

- `m log N` 是查 metadata；
- `h` 是 proof completion；
- PIR cryptographic cost 取决于具体 backend 和各 `N_c`。

---

## 14. 为什么不是简单 pruning TreePIR

这是文章最重要的防御点。

### 14.1 Perfectized TreePIR

如果把 SMT 当成完整 perfect tree：

- 子库包含大量 default/empty proof positions；
- storage 近似完整树规模；
- batch width 固定为 `h`。

### 14.2 Pruned-TreePIR-h

一个更强 baseline 是：

1. 先按 perfect-tree/TreePIR layout；
2. 删除 default/empty records；
3. 但保留 inherited height-`h` color interface。

它的问题：

- pruning 只删记录，不给 compact interval lookup；
- batch width 仍是 `h`；
- inherited color buckets 可能严重不平衡；
- proof completion 需要额外 mapping 才能系统化完成。

### 14.3 本文 direct SMT organization

本文从一开始就把数据库对象定义成：

```text
active proof-bearing nodes
```

然后直接建立：

- served interval metadata；
- exact active width `m`；
- balanced color subdatabases；
- fixed-shape real/dummy query；
- default hash completion。

所以本文不是 pruning 的小修改，而是完整 retrieval interface 的重新定义。

---

## 15. 实验部分到底做了什么

实验不是在证明一个单一指标，而是在建立证据链。

### 15.1 High-height structural balance

设置：

```text
h = 16, 20, 24
empty ratios = 99.95%, 99.975%, 99.99%
```

比较：

- Pruned-TreePIR-h；
- hybrid node-local baseline；
- profile_balanced；
- structural lower bound `B(T)`。

主要结论：

- profile_balanced 接近 lower bound；
- 相比 hybrid 最大 bucket 平均下降约 17.8%；
- 相比 pruning-only inherited buckets，最大子库小很多。

### 15.2 Distribution stress tests

设置：

```text
occupied leaves = 256 or 1024
distributions = uniform, clustered, adversarial
h = 16,20,24
```

目的：

- 检查不同 leaf 分布下是否仍然有效；
- 特别看 clustered/adversarial 是否会破坏平衡。

结论：

- uniform/clustered 下仍有稳定收益；
- adversarial 下收益更明显，因为 node-local coloring 会更不平衡。

### 15.3 Compressed high-height SMTs

设置：

```text
h = 128, 256
occupied leaves = 256, 1024
```

目的：

- 证明算法不需要 materialize `2^h` 完整树；
- PIR-facing structure 依赖 compressed non-default skeleton；
- metadata endpoint 用 real-leaf rank，不随着 `h` 变成巨大坐标。

结论：

- active nodes 仍是 `O(n)` 量级；
- profile_balanced size gap 约为 1；
- profile/lower ratio 接近 1。

### 15.4 Xenon real-data evaluation

数据：

```text
Xenon certificate-log derived keys
logical height h=20
keys = 5000, 10000, 20000
mapping = sha256 / sequential
```

指标：

- store ratio；
- exact width `m`；
- hybrid gap；
- profile gap；
- dummy fraction；
- collisions。

结论：

- 真实 key 分布下，direct SMT schemes 仍只存 perfectized baseline 的很小比例；
- profile_balanced 继续降低 count gap；
- sequential/clustered 情况下 gap 更明显，说明真实分布下平衡问题非平凡。

### 15.5 Metadata overhead

估算：

```text
digest payload = 32 bytes per active node
metadata = 24 bytes per active node
```

结论：

- metadata 是 public setup artifact；
- 不进入 PIR payload；
- 但应该报告大小；
- 总体仍是 `O(N)`，不是 `O(2^h)`。

### 15.6 LWE-PIR prototype

实现了一个 randomized LWE-PIR 风格 prototype：

- server 有 matrix `A`；
- server 预计算 hint；
- client query 是 LWE noisy vector 加 selection term；
- server matrix-vector response；
- client decode 32-byte digest。

目的：

- 不是生产级 SealPIR/Spiral；
- 但说明 randomized computational PIR workflow 与我们的 database shape 兼容；
- 最大颜色子库会影响并行 bottleneck。

### 15.7 Official SimplePIR communication check

使用 official SimplePIR artifact 的 bandwidth/parameter model：

- 每个 color subdatabase 向上取 power-of-two；
- digest record 是 256 bits；
- 统计 total online communication 和 parallel bottleneck。

结论：

- profile_balanced 通常降低最大 per-color communication；
- total communication 不一定单调下降，因为 SimplePIR 有 parameter tiering；
- 因此未来需要 backend-aware balancing。

---

## 16. backend-aware balancing 的扩展方向

当前 profile_balanced 优化的是：

```text
count profile: N_c
```

如果某个 PIR backend 有公开成本模型：

```text
g(n) = subdatabase size n 对应的 online bytes/server work/latency
```

可以把目标换成：

```text
Psi_g(phi) =
(max_c g(N_c), sum_c g(N_c), sort_down(N_1,...,N_m))
```

subtree permutation 的合法性证明不变，因为改变的是目标函数，不是 move set。

这说明：

- 当前算法是结构平衡版本；
- backend-aware 版本是自然后续；
- SimplePIR tiering 实验说明这个方向有必要。

---

## 17. 动态和 epoch maintenance

当前论文是 fixed snapshot。

实际部署可以按 epoch：

1. epoch 开始时构建 active interval forest；
2. 计算 `m`；
3. 运行 profile_balanced；
4. 发布 metadata；
5. epoch 内所有查询使用同一 fixed-shape interface。

更新时：

- Merkle hash update 本身是 path-local，`O(h)`；
- active-node metadata 只在 sibling-side active status 改变处更新；
- 如果 active width 增加或 balance certificate 超过阈值，则 full rebuild。

当前论文不完整证明 dynamic privacy 和 amortized update，这是 future work。

---

## 18. 文章贡献的准确表述

最准确的贡献不是：

```text
我们发明了一个更强的 PIR。
```

也不是：

```text
我们证明了一个很深的 coloring theorem。
```

而是：

```text
我们定义并验证了一个面向 SMT membership proof 的 TreePIR-style organization layer：
它把完整高度 h 的验证结构和 active proof-bearing retrieval structure 分离；
只存真实会出现在 proof 中的节点；
用 served interval metadata 支持客户端查找；
用 exact-width coloring 支持 fixed-shape batch PIR；
用 default hash chain 本地补全完整 proof；
并用 profile_balanced 改善颜色子库平衡。
```

---

## 19. 最容易被问到的问题和回答

### Q1：为什么不是把 SMT 补齐后直接用 TreePIR？

因为补齐后会把大量 default/empty proof positions 暴露给 PIR backend，存储和子库都膨胀。即使 pruning 删除空记录，也没有自动得到 compact lookup interface、exact active width `m` 和 balanced color stores。

### Q2：为什么 dummy query 不影响正确性？

因为 dummy 只对应没有真实 active proof node 的颜色。完整 proof 中该 level 要么由其它颜色返回真实 digest，要么是空 sibling level。空 sibling level 可以用 default hash chain 补齐。

### Q3：服务器怎么看不出哪些是 dummy？

每个颜色固定收到一个 PIR query。dummy query 是同一 subdatabase 上 syntactically ordinary PIR query。底层 PIR query privacy 隐藏 index，dummy indistinguishability 隐藏 real/dummy 类型。

### Q4：m 的意义是什么？

`m` 是 active proof path 最大长度，不是完整 proof 长度。它是本文 TreePIR-style interface 下最小颜色数和最小 batch width。它满足 `m <= min(h,n-1)`，但没有分布假设时可能等于 `h`。

### Q5：metadata 会不会泄漏？

metadata 本来就是 public leakage。本文隐藏的是 fixed public SMT snapshot 内的 queried target，不隐藏 occupancy structure。

### Q6：是否支持 non-membership proof？

当前严格支持 occupied leaves 的 membership proof。non-membership 需要把 interval endpoint 从 real-leaf rank 扩展到 full logical coordinate space，这是 future work。

### Q7：profile_balanced 有全局最优保证吗？

没有全局最优保证。它保证合法性、单调下降和 subtree-permutation local optimum，并提供 instance-wise certificate `U/B(T)`。

### Q8：SimplePIR 实验是不是完整 backend benchmark？

不是。它是 official artifact 的 parameter-level communication check。它说明 database shape 与 backend communication tier 的关系，但不等于完整生产系统 benchmark。

---

## 20. 最终可以怎么给别人讲

如果只用一段话讲：

> 我们研究的是固定 Sparse Merkle Tree 上 membership proof 的批量 PIR 检索。完整 SMT proof 仍有高度 `h`，但其中很多 sibling 是空子树，可以由公开 default hash chain 本地补齐。因此服务器不应该把完整满树 proof positions 都放入 PIR 数据库，而应该只存真实会出现在 proof 中的 active proof-bearing nodes。我们用 served interval 表示每个 active node 服务哪些目标叶子，用 interval forest 描述 proof-path 冲突关系，然后做祖先异色染色，使每个颜色子库在一条 proof path 上最多命中一个节点。客户端每个颜色发一次 PIR query，没有真实节点的颜色发 dummy，拿到真实 digest 后再用 default hashes 补全完整 proof。理论上最少颜色数等于最大 active proof length `m`，且 `m <= min(h, |L|-1)`；算法上我们用 `profile_balanced` 做 subtree-level color permutation 来降低最大子库大小；实验显示它能接近结构下界，并且在高高度、真实数据和 PIR-shaped backend check 中都能改善 PIR-facing database shape。

