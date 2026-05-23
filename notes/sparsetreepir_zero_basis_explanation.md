# SparseTreePIR 零基础完整讲解稿

这份文稿的目标不是替代正式论文，而是把论文中所有关键概念、符号、算法输入输出、数据结构、查询流程和实验逻辑，用“从零开始也能读懂”的方式重新讲一遍。读完以后，应该能回答三个问题：

1. 我们到底在解决什么问题？
2. 我们的方案每一步输入是什么、输出是什么、存了什么、查了什么？
3. 实验到底验证了哪些 claim？

---

## 1. 一句话概括

本文做的是：

> 对一个固定公开的 Sparse Merkle Tree，服务器只把真正可能出现在 membership proof 里的非空 sibling 节点放进 PIR 数据库；再把这些节点按颜色分成若干子数据库，使客户端每次对每个颜色发一次 PIR 查询，拿到真实 sibling hash 后，用公开 default hash 补齐完整高度的 SMT proof。

更短地说：

> 我们把 SMT 的“验证结构”和 PIR 的“检索结构”分离。

SMT 的验证结构仍然是高度为 `h` 的完整树；但 PIR 不应该检索完整树里的所有位置，而只应该检索真实需要隐藏的 proof-bearing nodes。

---

## 2. 最基础背景

### 2.1 Hash 是什么

哈希函数可以理解为一个确定性的压缩函数：

```text
H(input) -> fixed-length digest
```

例如输入一段数据，输出一个固定长度的 hash 值。Merkle tree 中每个内部节点的 hash 通常由两个孩子节点 hash 计算：

```text
parent_hash = H(left_child_hash || right_child_hash)
```

这里 `||` 表示拼接。

### 2.2 Merkle tree 是什么

Merkle tree 是一种用一个根 hash 承诺很多数据的树结构。

假设有多个叶子数据：

```text
leaf_0, leaf_1, leaf_2, leaf_3
```

先对每个叶子做 hash，然后两两合并：

```text
h0 = H(leaf_0)
h1 = H(leaf_1)
h2 = H(leaf_2)
h3 = H(leaf_3)

p0 = H(h0 || h1)
p1 = H(h2 || h3)

root = H(p0 || p1)
```

客户端如果想验证 `leaf_0` 是否属于这棵树，不需要下载整棵树，只需要下载它路径上的 sibling hashes：

```text
proof(leaf_0) = [h1, p1]
```

客户端从 `leaf_0` 出发，先和 `h1` 算出 `p0`，再和 `p1` 算出 `root`。如果算出的 `root` 等于公开承诺的 root，就验证成功。

### 2.3 Sparse Merkle Tree 是什么

Sparse Merkle Tree，简称 SMT，本质上还是 Merkle tree，但是它有一个固定的巨大逻辑叶子空间。

普通 Merkle tree 往往是“有多少数据，就建多少叶子附近的树”。SMT 则是：

```text
先固定高度 h
逻辑上有 2^h 个叶子位置
每个 key 被映射到某个固定位置
```

例如 `h=256` 时，逻辑叶子位置有 `2^256` 个。这是一个极大的地址空间。

但真实数据通常远远少于 `2^h`。绝大部分位置是空的。SMT 的关键性质是：

> 空子树的 hash 是公开可计算的 default hash。

也就是说，如果某个子树下面没有真实数据，那么它的 hash 不需要服务器发送，客户端可以自己算出来。

### 2.4 SMT membership proof

SMT 的 membership proof 仍然是高度 `h` 的 proof。也就是说，从叶子到根，每一层都有一个 sibling position。

但是这些 sibling position 分成两类：

1. 真实 sibling subtree：下面有真实数据，它的 hash 需要服务器提供。
2. 空 sibling subtree：下面没有真实数据，它的 hash 是公开 default hash，客户端可以自己补。

所以 SMT proof 的完整验证长度仍然是 `h`，但真正需要私密检索的 sibling hash 数量可能小于 `h`。

### 2.5 PIR 是什么

Private Information Retrieval，简称 PIR，目标是：

> 客户端从服务器数据库中取一个记录，但服务器不知道客户端取的是哪一个。

普通数据库查询会暴露索引：

```text
give me record 42
```

PIR 查询会隐藏索引。服务器只看到一个加密/随机化的查询，不能判断客户端取哪个记录。

### 2.6 Batch PIR 是什么

Merkle proof 不是一个记录，而是一组 sibling hashes。所以我们需要批量检索多个记录。

TreePIR 的核心思想是：

> 给 proof 节点染色，使任意一条 proof path 上同一种颜色最多出现一个节点。然后每个颜色对应一个 PIR 子数据库，客户端每种颜色查一次。

这样一条 proof 可以变成：

```text
color 1 -> 查询一次
color 2 -> 查询一次
...
color m -> 查询一次
```

我们的工作就是把这个思路从 perfect Merkle tree 搬到 SMT 上，但不能简单照搬，因为 SMT 里大量位置是空的。

---

## 3. 本文到底解决什么问题

### 3.1 直接套 TreePIR 的问题

TreePIR 适合 perfect binary tree。也就是每个位置都是真正的树节点，结构规则完整。

但 SMT 的逻辑树巨大，而且很多子树为空。

如果我们把 SMT 补齐成完整 perfect tree 后直接跑 TreePIR，就会出现问题：

```text
PIR 数据库包含大量 default / 空 / 不需要私密检索的位置
```

这些位置本来客户端可以公开计算，却被放进 PIR 数据库，导致数据库过大。

### 3.2 只删空节点还不够

有人可能会说：

> 那就先跑 TreePIR，然后把空节点删掉。

这仍然不够，因为删除记录只是省了存储，没有给出完整检索协议。客户端还需要知道：

1. 目标 leaf 对应哪个 compacted record？
2. 每个颜色子库里应该查哪个 index？
3. 如果某个颜色没有真实节点，如何发 dummy query？
4. 返回真实节点后，如何补回完整 height-`h` SMT proof？
5. 删除后颜色子库是否平衡？

所以本文不是简单“删空节点”，而是重新定义 SMT 下 PIR-facing proof database 的组织方式。

### 3.3 我们的核心思想

我们只存：

```text
active proof-bearing nodes
```

也就是：

> 非空、真实、并且可能作为某个 membership proof 的 sibling 节点出现的节点。

然后：

1. 给每个 active node 计算它服务哪些目标 leaf。
2. 这个服务范围是一个 served interval。
3. served intervals 构成 laminar interval forest。
4. 在这个 forest 上做祖先异色染色。
5. 每个颜色形成一个 PIR 子数据库。
6. 客户端每个颜色发一个 PIR 查询。
7. 没有真实节点的位置发 dummy PIR。
8. 返回真实 hash 后，用 default hash chain 补齐完整 SMT proof。

---

## 4. 全部符号逐一解释

### 4.1 树与叶子相关符号

| 符号 | 读法 | 含义 |
|---|---|---|
| `T` | tree | 固定的一棵 Sparse Merkle Tree |
| `h` | height | SMT 的高度，完整 proof 长度也是 `h` |
| `2^h` | two to the h | SMT 的逻辑叶子位置数量 |
| `L` 或 `\mathcal{L}` | real leaf set | 真实存在的叶子集合 |
| `ell` 或 `\ell` | leaf | 某个目标真实叶子 |
| `n = |\mathcal{L}|` | number of real leaves | 真实叶子的数量 |
| `u` | node | 树中的一个节点 |
| `sib(u)` | sibling of u | 节点 `u` 的兄弟节点 |
| `cnt(u)` | count of u | `u` 的子树中真实叶子的数量 |
| `depth(u)` | depth of u | `u` 在树中的深度，通常 root 深度为 0 |

这里 `|\mathcal{L}|` 表示集合 `\mathcal{L}` 的大小，也就是真实叶子数。

### 4.2 default hash 相关符号

| 符号 | 含义 |
|---|---|
| `Delta_t` 或 `\Delta_t` | 高度为 `t` 的空子树 default hash |
| `Delta_0` | 空叶子的 default hash |
| `Delta_{t+1}=H(Delta_t || Delta_t)` | 更高一层空子树 hash 的递推计算 |

如果一个 sibling subtree 是空的，客户端不需要 PIR 检索它，只需要用对应的 `Delta_t` 填进去。

### 4.3 active node 相关符号

| 符号 | 含义 |
|---|---|
| `A(T)` 或 `\mathcal{A}(T)` | 所有 active proof-bearing nodes 的集合 |
| `Path(ell)` 或 `\mathsf{Path}(\ell)` | 目标叶 `ell` 的 active proof path |
| `m` | 所有 active proof path 中最长的长度，也就是 active private batch width |

active proof-bearing node 的定义是：

```text
u 是非根节点
cnt(u) > 0
cnt(sib(u)) > 0
```

第一条 `cnt(u)>0` 表示 `u` 自己不是空子树。

第二条 `cnt(sib(u))>0` 表示 `u` 的兄弟方向也有真实叶子，因此 `u` 会作为某些叶子的 proof sibling 出现。

### 4.4 served interval 相关符号

| 符号 | 含义 |
|---|---|
| `r(ell)` | 真实叶 `ell` 在所有真实叶排序后的 rank |
| `I_srv(u)` | active node `u` 服务的目标叶 rank 区间 |
| `[L(s), R(s)]` | sibling subtree `s` 覆盖的真实叶 rank 区间 |

注意一个容易错的点：

```text
I_srv(u) 不是 u 自己覆盖的区间
I_srv(u) 是 u 作为 proof sibling 时服务的目标叶区间
```

如果 `u` 是某些目标叶 proof 里的 sibling，那么这些目标叶位于 `sib(u)` 的方向。因此：

```text
I_srv(u) = sibling subtree of u 覆盖的真实叶 rank 区间
```

判断一个节点是否在某个 proof path 中：

```text
u in Path(ell)  <=>  r(ell) in I_srv(u)
```

### 4.5 染色相关符号

| 符号 | 含义 |
|---|---|
| `[m]` | 颜色集合 `{1,2,...,m}` |
| `phi` 或 `\varphi` | 染色函数 |
| `\varphi: A(T) -> [m]` | 给每个 active node 分配一个颜色 |
| `D_c` 或 `\mathcal{D}_c` | 颜色 `c` 的 PIR 子数据库 |
| `N_c = |D_c|` | 颜色 `c` 子数据库的大小 |
| `N = |A(T)|` | active nodes 总数 |
| `M(phi) = max_c N_c` | 最大子数据库大小 |
| `Delta_N(phi)` | 最大子库和最小子库的大小差 |
| `B(T)` | exact-width balance 的结构下界 |

合法染色要求：

```text
同一条 active proof path 上，任意两个不同节点颜色不同
```

换句话说：

```text
每条 proof path 中，每个颜色最多出现一次
```

这就是为什么客户端每个颜色最多查一个真实节点。

### 4.6 查询相关符号

| 符号 | 含义 |
|---|---|
| `M_c` 或 `\mathcal{M}_c` | 颜色 `c` 的公开 metadata table |
| `tau_c` 或 `\tau_c` | 客户端本地记录：颜色 `c` 查的是哪个 index；如果没有真实节点则为 `bot` |
| `bot` 或 `\bot` | 空标记，表示这个颜色没有真实节点 |
| `sigma_c` 或 `\sigma_c` | PIR 返回并解出的结果 |
| `P[0..h-1]` | 完整 SMT proof 数组 |
| `rho` 或 `\rho` | 客户端重建出的 root hash |
| `a_0` | 目标叶子的 digest |

---

## 5. 服务器到底存什么

### 5.1 私有 PIR 子数据库

服务器把 active proof-bearing nodes 按颜色分成：

```text
D_1, D_2, ..., D_m
```

每个 `D_c` 是一个 PIR 子数据库。

每条私有记录只需要存：

```text
digest
```

也就是这个 active node 的 hash 值。

### 5.2 公开 metadata

每个颜色还有一个公开 metadata table：

```text
M_c = [(I_srv(u), delta(u)), ...]
```

其中：

```text
I_srv(u) = u 服务哪些目标叶
delta(u) = 这个 sibling hash 应该放到 proof 数组的哪一层
```

metadata 是公开的，不通过 PIR 隐藏。它帮助客户端定位自己应该在每个颜色里查哪个 index。

### 5.3 default hash chain

default hash chain：

```text
Delta_0, Delta_1, ..., Delta_{h-1}
```

也是公开的。客户端用它补齐空 sibling levels。

### 5.4 服务器知道什么、不知道什么

服务器可以知道：

```text
T 的公开结构
h
active node set
metadata
颜色分配
每个子库大小
m
每次请求有 m 个 PIR subqueries
```

服务器不应该知道：

```text
客户端查的是哪个 leaf
哪些颜色是真实查询
哪些颜色是 dummy 查询
每个颜色内部查的是哪个 index
```

---

## 6. 离线阶段：构建数据库和染色

离线阶段是服务器在查询前做的预处理。

### 6.1 Algorithm 1：Offline direct SMT organization

#### 输入

```text
T: 固定的 SMT
L: 真实叶集合
R_1: profile_balanced 允许的最大 refinement 轮数
```

#### 输出

```text
{D_c}_{c=1}^m: 颜色子数据库
{M_c}_{c=1}^m: 公开 metadata tables
phi: 合法染色函数
```

#### 步骤解释

第一步：排序真实叶子。

```text
按 SMT 逻辑位置排序所有真实叶
给每个真实叶一个 rank: 0,1,2,...
```

这个 rank 是之后 served interval 的端点。

第二步：构建 compressed non-default skeleton。

完整 SMT 太大，不能真的展开 `2^h` 个叶子。所以我们只根据真实叶构造非空骨架。

这个 skeleton 只保留：

```text
真实叶
真实叶之间的 branching points
连接它们的路径信息
```

第三步：提取 active proof-bearing nodes。

对于每个 branching point，检查它的两个非空 child directions。

每个满足条件的 child root `u` 都加入 `A(T)`。

第四步：给每个 active node 计算：

```text
served interval I_srv(u)
proof level delta(u)
digest
```

第五步：构建 interval forest。

所有 served intervals 具有 laminar 性质：

```text
两个区间要么不相交，要么一个包含另一个
```

按包含关系可以建一片森林。

第六步：计算 `m`。

```text
m = interval forest 的最大深度
```

它等于最长 active proof path 的长度。

第七步：first-fit coloring。

先得到一个合法染色。规则是：

```text
从根往叶遍历
给当前节点选择一个没有被祖先用过的最小颜色
```

这保证合法，但不保证平衡。

第八步：profile_balanced refinement。

对 first-fit 的结果做局部优化，让各颜色子库大小更平衡。

第九步：生成最终：

```text
D_c: 私有 digest records
M_c: 公开 interval metadata
phi: 最终颜色
```

---

## 7. profile_balanced 是什么

### 7.1 为什么需要它

只要染色合法，查询就能正确。但是如果颜色子数据库极不平衡，比如：

```text
D_1 有 10000 个节点
D_2 有 10 个节点
D_3 有 10 个节点
```

那么对 `D_1` 的 PIR 查询会很贵。系统瓶颈会被最大的子数据库拖住。

所以我们希望：

```text
所有 D_c 的大小尽量接近
```

### 7.2 profile_balanced 的核心想法

它不是随便给单个节点改颜色，因为单点改色容易破坏祖先异色性质。

它选择一个 subtree，然后在这个 subtree 内部做颜色置换：

```text
颜色 1 -> 颜色 3
颜色 3 -> 颜色 2
颜色 2 -> 颜色 1
```

只要置换不使用祖先已经用过的颜色，合法性就不会被破坏。

### 7.3 Algorithm 2：Profile-balanced subtree refinement

#### 输入

```text
F: interval forest
phi: 一个已经合法的 exact-width coloring
R_1: 最大 refinement 轮数
```

#### 输出

```text
refined phi: 更平衡的合法染色
```

#### 关键中间量

```text
N_c: 当前颜色 c 的全局子库大小
Psi(phi): 把所有 N_c 从大到小排序得到的 profile
C_U(c): subtree U 内颜色 c 的节点数
A(U): subtree U 可以使用的颜色集合
K_U[a,b]: 把 subtree 内源颜色 a 映射到目标颜色 b 的代价
```

#### 步骤解释

第一步：计算当前每个颜色子库大小。

```text
N_1, N_2, ..., N_m
```

第二步：对每个 subtree root `U`，统计它内部的颜色直方图：

```text
C_U(1), C_U(2), ..., C_U(m)
```

第三步：计算 `U` 的可用颜色集合。

祖先已经使用的颜色不能再用于这个 subtree root 方向，所以：

```text
A(U) = [m] \ ancestor colors
```

第四步：构建 assignment cost matrix。

如果把 subtree 内颜色 `a` 的节点全部映射到颜色 `b`，目标颜色 `b` 的新负载约为：

```text
N_b - C_U(b) + C_U(a)
```

算法用平方代价：

```text
K_U[a,b] = (N_b - C_U(b) + C_U(a))^2
```

这会倾向于把重的 subtree color mass 移到轻的全局颜色桶。

第五步：用 Hungarian algorithm 找最小代价匹配。

这得到一个颜色置换 `pi_U`。

第六步：检查这个置换是否真正改善全局 profile。

如果：

```text
Psi(phi') < Psi(phi)
```

就接受；否则拒绝。

第七步：重复直到没有改进或达到轮数上限。

### 7.4 它保证什么

它保证：

1. 每次接受的 move 都保持合法染色。
2. 每次接受的 move 都严格改善 lexicographic bucket profile。
3. 因为合法染色数量有限，所以算法会终止。
4. 输出是一个 subtree-permutation local optimum。

它不保证：

```text
全局最优
```

所以论文里把它称为：

```text
local refinement with instance-wise balance certificate
```

---

## 8. 在线阶段：客户端怎么查

在线阶段是客户端要查某个 target leaf 的 proof。

### 8.1 Algorithm 3：Batch-PIR query generation

#### 输入

```text
ell: 目标 leaf
r(ell): 目标 leaf 的 real-leaf rank
{D_c}: 所有颜色子数据库
{M_c}: 所有公开 metadata tables
```

#### 输出

```text
一个包含 m 个 PIR subqueries 的 batch-PIR request
本地 target map {tau_c}
```

#### 步骤解释

对于每个颜色 `c`：

1. 在 `M_c` 的 served intervals 中二分查找 `r(ell)`。
2. 如果找到一个包含 `r(ell)` 的 interval：
   - 说明这个颜色有真实 proof node。
   - 找到该节点在 `D_c` 里的 index `j_c`。
   - 生成真实 PIR query。
   - 记录 `tau_c = j_c`。
3. 如果没有找到：
   - 说明这个颜色没有真实 proof node。
   - 生成 dummy PIR query。
   - 记录 `tau_c = bot`。

最后客户端同时发送：

```text
query_1, query_2, ..., query_m
```

服务器看到的是固定数量的 `m` 个 PIR 查询。

### 8.2 为什么同色区间可以二分查找

如果两个同色 active nodes 的 served intervals 相交，那么存在某个目标 leaf 同时需要这两个节点。这样同一条 proof path 上就出现了两个同色节点，违反合法染色。

所以：

```text
同色 served intervals 必然不相交
```

因此每个颜色的 metadata table 可以排序，客户端对每个颜色做一次二分查找。

---

## 9. Proof Completion：客户端如何补完整 proof

### 9.1 Algorithm 4：Client-side proof completion

#### 输入

```text
ell: 目标 leaf 的位置
a_0: 目标 leaf digest
{M_c}: 公开 metadata tables
{tau_c}: query generation 阶段保存的本地 target map
{sigma_c}: PIR 返回结果
{Delta_t}: default-empty hash chain
```

#### 输出

```text
P[0..h-1]: 完整 proof 数组
rho: 重建出的 root digest
```

#### 步骤解释

第一步：初始化完整 proof 数组。

```text
for t = 0 to h-1:
    P[t] = Delta_t
```

也就是说，一开始假设每一层都是 default hash。

第二步：把 PIR 返回的真实 sibling hash 写进去。

对于每个颜色 `c`：

```text
if tau_c != bot:
    从 M_c[tau_c] 里读出 proof level delta
    P[delta] = sigma_c
```

第三步：从叶子向上重建 root。

从目标叶 digest `a_0` 开始，按目标 leaf 的路径方向逐层 hash：

```text
if 当前层目标节点在左边:
    rho = H(rho || P[t])
else:
    rho = H(P[t] || rho)
```

最终得到 root digest `rho`。

### 9.2 为什么 real responses + default hashes 足够

完整 SMT proof 每一层都需要 sibling digest。

但是每一层 sibling digest 分两类：

1. 非空 sibling subtree：它是 active proof-bearing node，需要通过 PIR 返回。
2. 空 sibling subtree：它等于公开 default hash `Delta_t`，客户端自己填。

Algorithm 4 初始化 `P[t]=Delta_t`，然后用 PIR 返回的真实 digest 覆盖非空层。

因此最后 `P[0..h-1]` 包含：

```text
所有真实 sibling hashes
所有空 sibling default hashes
```

这正好就是完整 SMT membership proof。

---

## 10. 一个完整例子：leaf 19 怎么查

假设有一个高度为 4 的 SMT，真实叶为：

```text
{16, 17, 19, 22, 28}
```

最终 active nodes 被分成 4 个颜色子库：

```text
D_1 = {3, 2}
D_2 = {5, 4}
D_3 = {9, 8}
D_4 = {17, 16}
```

现在客户端要查 leaf 19。

### 第一步：客户端知道 leaf 19 的 rank

真实叶排序：

```text
16, 17, 19, 22, 28
```

所以：

```text
r(19) = 2
```

### 第二步：每个颜色查 metadata

客户端在每个 `M_c` 里查 rank 2 是否落入某个 served interval。

假设结果是：

```text
color 1 -> node 3
color 2 -> node 5
color 3 -> node 8
color 4 -> no real node
```

于是：

```text
tau_1 = index(node 3 in D_1)
tau_2 = index(node 5 in D_2)
tau_3 = index(node 8 in D_3)
tau_4 = bot
```

### 第三步：发 batch PIR

客户端发送：

```text
query to D_1 for node 3
query to D_2 for node 5
query to D_3 for node 8
dummy query to D_4
```

服务器只看到每个颜色都有一个 PIR query，看不出哪个是真实，哪个是 dummy。

### 第四步：收到结果

客户端得到：

```text
sigma_1 = hash(node 3)
sigma_2 = hash(node 5)
sigma_3 = hash(node 8)
sigma_4 = dummy response, discarded
```

### 第五步：补 proof

初始化：

```text
P[0] = Delta_0
P[1] = Delta_1
P[2] = Delta_2
P[3] = Delta_3
```

然后把真实节点写入对应层：

```text
P[level(node 3)] = sigma_1
P[level(node 5)] = sigma_2
P[level(node 8)] = sigma_3
```

没有真实节点的那一层继续保留 default hash。

最后客户端从 leaf 19 向上 hash，得到 root。

---

## 11. 正确性直觉

### 11.1 为什么每个颜色最多查一个真实节点

因为染色合法：

```text
同一条 active proof path 上颜色不能重复
```

所以对于目标 leaf `ell`：

```text
Path(ell) 中每个颜色最多出现一个节点
```

因此每个颜色子库最多需要查一个真实 item。

### 11.2 为什么同色区间不相交

如果两个同色节点的 served intervals 相交，那么存在一个目标 leaf 同时被两个节点服务。

这意味着这两个节点同时出现在同一条 `Path(ell)` 上。

但它们同色，违反合法染色。

所以同色区间不相交。

### 11.3 为什么 batch PIR 查询是 fixed-shape

每次查询都发送：

```text
m 个 PIR subqueries
```

无论某个颜色是否真的有 proof node，都发一个 query。

如果有真实节点：

```text
real PIR query
```

如果没有真实节点：

```text
dummy PIR query
```

因此服务器看到的请求形状总是一样的。

### 11.4 隐私依赖什么

隐私依赖两个条件：

1. 底层 PIR 本身隐藏 index。
2. dummy query 和普通 PIR query 在分布上不可区分。

如果这两个条件成立，服务器不知道：

```text
每个颜色查的是哪个 index
某个颜色是真实查询还是 dummy 查询
目标 leaf 是哪个
```

---

## 12. 复杂度

### 12.1 记号

```text
h = SMT 高度
N = active proof-bearing nodes 数量
m = exact active width
N_c = 第 c 个颜色子数据库大小
R_1 = profile_balanced 最大轮数
```

### 12.2 预处理复杂度

构造 active nodes 和 interval forest 后，需要排序 interval：

```text
O(N log N)
```

空间：

```text
O(N)
```

### 12.3 查询定位复杂度

每个颜色做一次二分查找：

```text
O(m log N)
```

### 12.4 proof completion 复杂度

完整 proof 长度仍然是 `h`，所以补 proof 和向上 hash：

```text
O(h)
```

### 12.5 profile_balanced 复杂度

每轮检查所有 subtree，每个 subtree 解一个大小最多 `m` 的 assignment：

```text
O(R_1 N m^3)
```

额外空间：

```text
O(Nm)
```

---

## 13. 实验部分到底做了什么

实验不是单纯比较谁快，而是按 A 会常见的 resource-first 逻辑展开：

> 先证明我们的组织方式改变了 PIR-facing database shape，再验证这些结构优势能影响真实 PIR backend。

### 13.1 核心资源指标

实验主要看：

```text
N = active proof records 数量
m = 每次 batch 查询的颜色数 / PIR subqueries 数
M(phi) = 最大颜色子数据库大小
Delta_N(phi) = 子数据库大小差
metadata size = 公开索引大小
dummy fraction = dummy query 比例
SimplePIR online KB = 真实 backend 通信量
client query time = SimplePIR query generation 时间
```

### 13.2 Baseline 1：Perfectized TreePIR

做法：

```text
把 SMT 补成完整 perfect tree
然后运行 TreePIR 的 perfect-tree indexing
```

它验证的问题是：

> 直接 perfectize TreePIR 错在 database shape。

实验显示，height 24、99.95% empty 的情况下：

```text
active records = 16,776
perfectized TreePIR records = 33,554,430
```

这说明问题不是 TreePIR indexing 慢，而是它面对 SMT 时会把完整逻辑空间暴露给 PIR。

### 13.3 Baseline 2：PBC-active

PBC-active 表示：

```text
把 active proof records 当成普通 batch-PIR database
使用 generic batch code 思路
```

它的缺点是：

```text
复制多
query slots 更多
metadata/map 成本更高
没有利用 proof path 的颜色结构
```

它用于证明：

> 只知道 active records 还不够，还需要利用 proof path coloring。

### 13.4 Baseline 3：Active-only global PIR

Active-only global PIR 表示：

```text
所有 active nodes 放进一个大数据库
每个 active proof slot 都对同一个大库发 PIR
```

它存储上已经很省，但查询时每次都面对整个 active database。

它用于证明：

> coloring 和子数据库划分不是装饰，而是能让每个 PIR query 面向更小的数据库。

### 13.5 Baseline 4：hybrid / node-local exact-width

hybrid 是一个节点局部的 exact-width 染色 baseline。

它已经能保证：

```text
使用 m 个颜色
祖先异色合法
```

但它没有 subtree-level profile refinement。

它用于证明：

> profile_balanced 的改进不是 active-only 自然带来的，而是 subtree-level balance refinement 带来的。

### 13.6 实验 1：Evaluation logic table

论文新增的 evaluation logic table 说明每个实验对应哪个理论预测。

它回答：

```text
我们为什么跑这些实验？
每张表验证什么 claim？
```

### 13.7 实验 2：Official TreePIR perfectization check

这个实验下载并运行 TreePIR 公开实现里的 Java indexing class。

目的：

```text
验证 perfectized TreePIR 的 indexing 本身不是瓶颈
真正问题是完整树 database shape 太大
```

指标：

```text
TreePIR records
width
max-bucket reduction
indexing time
```

### 13.8 实验 3：High-height structural balance

设置：

```text
h = 16, 20, 24
empty ratios = 99.95%, 99.975%, 99.99%
每格 3 个随机实例
```

指标：

```text
Active
m
Lower = structural lower bound B(T)
H max = hybrid 最大子库
Profile = profile_balanced 最大子库
Prof./Lower
Red.
P gap
```

结论：

```text
profile_balanced 明显降低最大子库大小
结果接近结构下界
```

### 13.9 实验 4：Distribution stress tests

测试不同叶子分布：

```text
uniform
clustered
adversarial
```

目的：

```text
SMT 的形状强依赖 occupied leaf distribution
所以不能只跑 uniform random
```

结论：

```text
在 adversarial layout 下，node-local coloring 会很不平衡
profile_balanced 的收益更明显
```

### 13.10 实验 5：Compressed high-height SMTs

设置：

```text
h = 128, 256
n = 256 或 1024 occupied leaves
```

关键点：

```text
不 materialize 完整 2^h 树
只用 compressed non-default skeleton
```

目的：

```text
说明逻辑高度很大时，我们的 active structure 仍然跟真实叶数量相关，而不是跟 2^h 相关
```

结论：

```text
h=256 时完整 proof 仍然长 256
但 private retrieval width m 可能只有约 14
```

### 13.11 实验 6：Xenon real-data evaluation

使用 Xenon certificate-log dump 里的真实 keys。

目的：

```text
证明不是只在 synthetic 数据上成立
```

两种映射：

```text
sha256 mapping
sequential mapping
```

指标：

```text
Keys
Collisions
m
Store ratio
H gap
P gap
Dummy fraction
```

结论：

```text
真实数据下 active storage 仍然远小于 perfectized baseline
profile_balanced 仍然降低子库 gap
```

### 13.12 实验 7：Metadata overhead

metadata 是公开的，但不是免费不存在的。

实验报告：

```text
Digest KB
Metadata KB
Setup ms
```

结论：

```text
metadata 大小线性于 active nodes
没有隐藏在 PIR payload 里
不是 full 2^h coordinate space 级别
```

### 13.13 实验 8：Full SimplePIR API backend

这个实验真正接了 SimplePIR 的 Go 实现。

调用流程包括：

```text
Init
Setup
Query
Answer
Recover
```

每个 digest 是 32 bytes。由于 SimplePIR 的方便接口按 machine word 存 entry，实验把每个 digest 拆成 8 个 32-bit chunks 检索。

对比：

```text
uncolored-active PIR
profile_balanced color subdatabase PIR
```

结果：

```text
profile_balanced online communication 降低 63.8%--75.6%
height 24 下 client query generation 也明显下降
```

注意：

```text
实验记录通信和 timing counters
没有记录进程级 resident memory
memory 相关只通过 database footprint / metadata / offline state 作为 proxy
```

所以论文不能说已经证明真实 RAM 优势，只能说结构上减小了数据库形状，并在 SimplePIR 中体现为通信和部分时间优势。

---

## 14. 论文现在真正的贡献

这篇论文的贡献不是：

```text
发现 SMT 有空节点
发现 default hash 可以公开计算
发明新的 PIR primitive
证明一个很深的图染色定理
```

真正贡献是：

### 14.1 Protocol abstraction

定义固定 SMT membership proof 下，PIR 到底应该检索什么：

```text
active proof-bearing nodes
served intervals
color subdatabases
dummy queries
default-hash proof completion
```

这是一个完整的 retrieval contract。

### 14.2 Interface-exact active width

证明在 active-node one-query-per-color interface 下：

```text
最少颜色数 = m = 最大 active proof path 长度
```

并且：

```text
m <= min(h, |L|-1)
```

这说明 private retrieval width 可以小于完整 proof height。

### 14.3 Profile-balanced coloring

提出一个在 exact width 不变的情况下，改善 color subdatabase balance 的 subtree-profile refinement。

它不是全局最优算法，但有：

```text
合法性保持
单调下降
终止性
instance-wise balance certificate
```

### 14.4 Backend evidence

用 SimplePIR API bridge 说明：

```text
active interval color subdatabase layout 确实会改变真实 PIR backend 看到的数据库形状
并转化为通信和部分时间收益
```

---

## 15. 论文边界和不能夸大的地方

### 15.1 只做 membership proof

当前论文只处理：

```text
查询真实存在 leaf 的 membership proof
```

不处理：

```text
任意 absent key 的 non-membership proof
```

### 15.2 不隐藏 occupancy pattern

论文隐藏的是：

```text
客户端查询哪个 target leaf
```

不隐藏：

```text
SMT 的公开结构
active metadata
occupancy pattern
```

### 15.3 不是新 PIR primitive

本文不发明 PIR 协议，而是组织 PIR 数据库。

底层可以接：

```text
SimplePIR
SealPIR
Spiral
XPIR
PIANO
YPIR
```

### 15.4 SimplePIR 实验不是生产级最优实现

当前 SimplePIR bridge 是 conservative chunked integration。

它说明：

```text
接口能接
通信量下降
部分时间下降
```

但不能直接说：

```text
对所有 SealPIR/Spiral 部署都更快
真实 RAM 一定更低
```

---

## 16. 如果给别人讲这篇论文，推荐讲法

可以按下面顺序讲：

1. Merkle proof 泄露查询目标，需要 PIR。
2. TreePIR 给 perfect tree 提供 one-query-per-color 思路。
3. SMT 不是普通 perfect tree：验证结构是 height `h`，但很多 proof levels 是 public default hash。
4. 直接 perfectize TreePIR 会把巨大逻辑空间暴露给 PIR。
5. 只删 default records 不够，因为还缺 lookup、dummy、completion、balance interface。
6. 我们定义 active proof-bearing nodes。
7. 每个 active node 有 served interval。
8. served intervals 构成 interval forest。
9. 在 forest 上做祖先异色染色，颜色就是 PIR 子数据库。
10. `m` 是 exact active width，决定每次发多少 PIR subqueries。
11. profile_balanced 在不增加 `m` 的情况下平衡子库。
12. 客户端每个颜色查一次，没有真实节点就 dummy。
13. 返回真实 sibling hashes 后，用 default hash chain 补完整 proof。
14. 实验按资源模型验证：records、width、max bucket、metadata、SimplePIR communication/timing。

---

## 17. 一句话总结给审稿人

> SparseTreePIR is not a new PIR primitive and not merely pruning TreePIR. It defines the missing organization layer for private membership-proof retrieval over fixed public SMT snapshots: active proof-bearing records, served-interval lookup, exact active-width coloring, dummy/real fixed-shape batch queries, and public default-hash proof completion.

中文意思：

> SparseTreePIR 不是新的 PIR 协议，也不是简单剪枝 TreePIR。它定义了固定公开 SMT 快照上私密 membership proof 检索所缺失的组织层：哪些真实 proof 记录进入 PIR、如何用区间索引、最少需要多少颜色、dummy/real 查询如何固定形状、以及如何用 public default hash 补完整 proof。
