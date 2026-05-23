# SparseTreePIR 论文完整讲解稿

本文档用于从零开始讲清楚当前论文 **SparseTreePIR: Active-Interval Coloring for Batch Private Information Retrieval of Sparse Merkle Proofs** 的核心内容、算法流程、数据结构、证明逻辑、实验设计和答辩要点。

它可以作为：

- 组会汇报讲稿；
- 答辩讲解稿；
- 投稿前自查文档；
- 给不熟悉 TreePIR / SMT / PIR 的读者的导读。

---

## 1. 一句话概括

这篇文章研究的是：

> 普通 Sparse Merkle Tree 已经能高效给出 membership proof，但服务器会知道客户端查询的是哪个 key；我们要把这个 proof retrieval 过程变成 target-private 的 batch PIR 查询。关键不是设计新的 PIR，而是重新定义 SMT proof 里哪些节点应该进入 PIR database，以及如何把这些节点分成多个平衡的子数据库，让客户端每个颜色查一次，最后补全完整 SMT proof。

换句话说：

> SparseTreePIR 是一个面向固定 SMT snapshot 的 **private proof-retrieval organization layer**。

它不是新的 Merkle tree。

它不是新的 PIR primitive。

它不是让普通 SMT proof 变短。

它做的是：在普通 SMT proof 语义不变的情况下，让 proof retrieval 对服务器隐藏 target leaf。

---

## 2. 背景：Merkle Tree 和 SMT

### 2.1 Merkle Tree 做什么

Merkle tree 是一种认证数据结构。

服务器把数据放在叶子上，然后自底向上哈希：

```text
leaf hash -> parent hash -> ... -> root hash
```

最终得到一个公开 root digest。

如果客户端想验证某个叶子属于这棵树，它需要：

- 目标叶子的值；
- 从叶子到根路径上每一层的 sibling digest；
- 公开 root。

客户端拿到这些 sibling digests 后，自底向上重新计算 root。如果计算结果等于公开 root，就说明证明通过。

这组 sibling digests 就是 Merkle proof。

### 2.2 普通 Merkle Proof 的隐私问题

如果客户端直接问服务器：

```text
请给我 leaf i 的 proof
```

服务器马上知道客户端在查 leaf `i`。

所以 Merkle proof retrieval 有隐私问题：

> 客户端想验证某个对象，但不想让服务器知道自己在验证哪个对象。

TreePIR 就是针对 perfect binary tree 上这个问题提出的。

### 2.3 Sparse Merkle Tree 是什么

Sparse Merkle Tree，也就是 SMT，是 Merkle tree 在巨大逻辑地址空间上的版本。

一个高度为 `h` 的 SMT 有：

```text
2^h
```

个逻辑叶子位置。

但实际 occupied leaves 可能很少。

例如：

```text
h = 256
逻辑空间 = 2^256
真实存在的 key 可能只有几千、几万
```

SMT 的核心机制是：

> 空子树的 digest 是公开 default hash，可以由客户端本地计算。

因此普通 SMT proof serving 很省。

服务器不需要返回所有 `h` 层的 sibling digest。

如果某一层 sibling subtree 是空的，客户端可以直接用 default hash chain 补上。

### 2.4 普通 SMT Proof Serving 已经很好，但不隐私

普通 SMT proof serving 的流程是：

1. 客户端告诉服务器目标 key；
2. 服务器沿着该 key 的路径查找 proof；
3. 服务器返回非空 sibling digests；
4. 客户端用 default hashes 补空层；
5. 客户端验证 root。

这个过程很高效。

但是它不隐私，因为服务器知道目标 key。

本文的问题就是：

> 如何把这个普通 SMT proof serving 过程，变成 target-private retrieval？

---

## 3. TreePIR 的启发与 SMT 的差异

### 3.1 TreePIR 的核心思想

TreePIR 研究的是 perfect binary Merkle tree 上的 private proof retrieval。

它的关键观察是：

> Merkle proof 不是任意 batch，而是一条路径。

所以 TreePIR 给 proof-bearing nodes 染色，使得：

```text
同一条 proof path 上，每种颜色最多出现一个节点
```

这样客户端可以：

```text
每种颜色发一次 PIR query
```

从而取回整条 proof。

### 3.2 为什么不能直接把 TreePIR 套到 SMT 上

TreePIR 的对象是 perfect tree。

但 SMT 有两个不同的 view：

```text
Verifier-facing view:
    完整 height-h SMT proof coordinate system

PIR-facing view:
    只有真实非默认 sibling digest 需要私密检索
```

也就是说：

> SMT verifier 仍然需要 height-`h` proof，但 PIR database 不应该包含所有 height-`h` 逻辑节点。

很多 proof levels 只是 public default hash，不应该进入 PIR。

### 3.3 本文的中心问题

这篇文章最核心的问题不是：

```text
TreePIR 能不能用于 SMT？
```

而是：

```text
TreePIR 的 one-query-per-color principle 在 SMT 上应该 color 什么对象？
```

本文的答案是：

> 应该 color active proof-bearing interval forest，而不是完整 logical SMT，也不是先 TreePIR coloring 后再 prune。

---

## 4. 论文的核心对象

### 4.1 Active Proof-Bearing Node

论文定义 active proof-bearing node。

对一个非根节点 `u`，如果满足：

```text
cnt(u) > 0
cnt(sib(u)) > 0
```

那么 `u` 是 active proof-bearing node。

其中：

- `cnt(u) > 0` 表示 `u` 的子树中有真实 occupied leaf，所以 `u` 不是 public default hash；
- `cnt(sib(u)) > 0` 表示 `u` 会作为某些真实 target leaf 的 sibling proof node 出现。

因此 active proof-bearing node 的含义是：

> 会出现在某个 occupied leaf membership proof 中，并且自身不是默认空节点的 sibling digest。

所有 active nodes 组成：

```text
A(T)
```

这些节点才是真正需要进入 PIR database 的 private proof records。

### 4.2 为什么空节点不进入数据库

如果某个 sibling subtree 是空的，那么它的 digest 是 public default hash。

客户端可以本地计算，不需要服务器返回。

所以空节点不进入子数据库。

这点非常重要：

> SparseTreePIR 不是存完整 SMT，而是只存 active proof-bearing nodes。

### 4.3 Active Proof Path

对一个 occupied target leaf `ell`，定义：

```text
Path(ell)
```

为它的完整 SMT proof 中需要私密检索的真实 sibling nodes。

注意：

```text
完整 SMT proof 长度 = h
active proof path 长度 <= h
```

完整 proof 中某些 level 是 default hash，不在 active proof path 里。

---

## 5. Served Interval

### 5.1 为什么需要 Served Interval

每个 active node `u` 会服务一批 target leaves。

但要注意：

> `u` 服务的不是 `u` 自己子树里的 leaves，而是 `sib(u)` 方向的 target leaves。

因为 Merkle proof 中，某个节点作为 sibling 出现，是给它兄弟方向的 target leaf 使用。

### 5.2 定义

对 active node `u`，定义：

```text
I_srv(u)
```

表示哪些 target leaves 的 proof 会需要 `u`。

如果目标 leaf `ell` 落在 `I_srv(u)` 中，那么：

```text
u ∈ Path(ell)
```

### 5.3 为什么 Served Interval 很关键

Served interval 是客户端查询子数据库的索引基础。

客户端知道目标 leaf 的 rank。

对每个颜色子库，客户端在公开 metadata table 中查找：

```text
有没有一个 served interval 覆盖我的 target leaf rank？
```

如果有，就说明这个颜色库里有一个真实 proof node 要取。

如果没有，就发 dummy query。

---

## 6. Active Interval Forest

### 6.1 Laminar Structure

所有 active nodes 的 served intervals 形成 laminar family：

```text
任意两个区间要么不相交，要么一个包含另一个
```

这可以组织成 interval forest。

### 6.2 Coloring Constraint

如果两个 active nodes 在同一条 active proof path 上，它们可能同时被某个 target proof 使用。

因此它们不能同色。

合法 coloring 要求：

```text
对任意 occupied leaf ell，
Path(ell) 上的任意两个不同节点颜色不同。
```

这样可以保证：

```text
每个颜色子数据库中，目标 proof 最多需要一个真实节点。
```

这就是 batch PIR 接口成立的基础。

---

## 7. m 的意义

### 7.1 定义

论文定义：

```text
m = max_{ell in L} |Path(ell)|
```

也就是所有 occupied leaves 的 active proof path 中，最多需要私密检索多少个真实 sibling digest。

### 7.2 m 和 h 的区别

`h` 是完整 SMT verifier proof length。

`m` 是 PIR-facing active width。

完整 proof 仍然是 height `h`。

但是私密检索不一定需要查询 `h` 个真实节点。

因为很多 proof levels 是 public default hash。

### 7.3 本文中 m 的三个名字

在当前 active-node one-query-per-color interface 下，`m` 同时对应：

- active width；
- active color count；
- active batch width。

也就是说：

```text
m 个颜色
m 个颜色子数据库
每次 retrieval 发 m 个 PIR subqueries
```

### 7.4 m 不是调参

`m` 不是算法随便选择的参数。

它由 fixed SMT snapshot 的 occupied leaves 分布决定。

setup 阶段会公开 `m`。

它类似 TreePIR 中 perfect tree 的 `h`，但只针对 active proof material。

---

## 8. 离线 Setup 算法

### 8.1 输入输出

输入：

```text
固定 public SMT snapshot T
occupied leaf set L
balancing rounds R1
```

输出：

```text
active color count m
color subdatabases D_1, ..., D_m
metadata tables M_1, ..., M_m
valid coloring phi
```

### 8.2 离线流程

服务器执行：

1. 按逻辑坐标排序 occupied leaves；
2. 给每个 occupied leaf 分配 real-leaf rank；
3. 遍历 compressed non-default skeleton；
4. 计算每个节点的 real-leaf count；
5. 提取 active proof-bearing nodes；
6. 为每个 active node 计算 served interval 和 proof level；
7. 根据 interval containment 建 active interval forest；
8. 计算 active width `m`；
9. 用 first-fit 得到可行 coloring；
10. 用 ActiveBalance 做子树级 load refinement；
11. 构造每个颜色子数据库；
12. 构造公开 metadata tables。

### 8.3 输出的数据结构

每个颜色子数据库：

```text
D_c = [digest records of color c]
```

每个 metadata table：

```text
M_c = [(served interval, proof level, subdatabase index), ...]
```

metadata 是公开的。

digest records 通过 PIR 私密检索。

---

## 9. First-Fit Coloring

### 9.1 作用

First-fit coloring 只是可行性步骤。

它保证产生一个合法 coloring。

它不是主要贡献。

### 9.2 做法

从 interval forest 的根到叶遍历。

对每个 node，选一个没有被祖先用过的最小颜色。

由于任意 active path 最长是 `m`，所以总能找到可用颜色。

### 9.3 问题

First-fit 可能导致颜色库不平衡。

例如：

```text
C1 很大
C2 很小
C3 很小
...
```

PIR 成本通常受最大数据库影响，所以必须做 balance。

---

## 10. ActiveBalance 算法

### 10.1 核心直觉

ActiveBalance 的目标是：

> 在不破坏合法 coloring 的情况下，让 color subdatabases 更平衡。

它不是单节点移动，而是对子树做 color permutation。

原因是：

如果一个 rooted subtree 内部 coloring 已经合法，那么将这个 subtree 内部颜色整体重命名，只要不和祖先颜色冲突，合法性仍然保持。

### 10.2 算法步骤

ActiveBalance 对每个候选 subtree `U`：

1. 计算 `U` 内部每个颜色的节点数；
2. 计算当前全局每个颜色桶大小；
3. 构造颜色 assignment / matching；
4. 找一个颜色置换，让重的 subtree color mass 尽量映射到轻的 global bucket；
5. 检查置换后全局 bucket signature 是否真的变好；
6. 如果变好就接受；
7. 重复若干轮。

### 10.3 接受准则

论文使用 lexicographic bucket signature：

```text
Psi(phi) = sorted bucket sizes from large to small
```

只有当新的 signature 变小时才接受。

因此：

```text
每次接受都会严格改善全局 bucket profile。
```

### 10.4 终止性

因为合法 coloring 数量有限，而且每次接受都严格降低 signature，所以算法一定终止。

### 10.5 Certificate

论文给出 structural lower bound `B(T)`。

如果输出最大桶为 `U`，则：

```text
U / B(T)
```

是 instance-wise balance certificate。

它说明当前结果距离结构下界有多远。

这不是一般 approximation guarantee，但提供了实例级可审计证据。

---

## 11. 在线查询算法

### 11.1 客户端输入

客户端知道：

```text
target leaf coordinate ell
target leaf digest
tree height h
default hash chain
target real-leaf rank r(ell)
metadata tables M_1, ..., M_m
```

### 11.2 对每个颜色执行 lookup

对于每个颜色 `c`：

1. 在 `M_c` 中二分搜索；
2. 判断是否有 served interval 覆盖 `r(ell)`；
3. 如果有，得到真实 subdatabase index；
4. 如果没有，生成 dummy index；
5. 生成 PIR query。

服务器看到的是：

```text
每个颜色子数据库收到一个 PIR query。
```

服务器不知道：

- query 是 real 还是 dummy；
- real query 的 index 是什么；
- target leaf 是什么。

---

## 12. Proof Completion

### 12.1 为什么需要 Proof Completion

PIR 返回的只是真实 active sibling digests。

但普通 SMT verification 需要 height-`h` proof array。

所以客户端需要补全 proof。

### 12.2 流程

1. 初始化长度为 `h` 的 proof array；
2. 把真实 PIR replies 放到对应 proof level；
3. 对没有真实 sibling digest 的 level，用 default hash chain 填充；
4. 得到完整 height-`h` SMT proof；
5. 自底向上 recompute root；
6. 检查是否等于 public root。

### 12.3 关键结论

dummy response 不会造成 proof 缺失。

因为 dummy 只用于隐藏查询形状。

真正缺失的 proof levels 都是 public default hash，可以本地补。

---

## 13. 隐私模型

### 13.1 Public Leakage

服务器可以知道：

- SMT height；
- default hash chain；
- active-node set；
- interval metadata；
- color assignment；
- color subdatabase sizes；
- active width / color count `m`；
- 每次查询固定发 `m` 个 subqueries。

### 13.2 Hidden Target Information

服务器不应该知道：

- target leaf；
- active proof path；
- 哪些颜色 query 是 real；
- 哪些颜色 query 是 dummy；
- 每个颜色库中真实查询的 index。

### 13.3 不隐藏的内容

论文不隐藏：

- SMT occupancy pattern；
- 哪些 leaves 已经存在；
- public metadata；
- fixed snapshot shape。

### 13.4 隐私证明直觉

对任意两个 target leaves：

1. 服务器看到的 query 数量一样，都是 `m`；
2. 每个颜色库都收到一个 query；
3. 底层 PIR 隐藏 index；
4. dummy query 与 ordinary PIR query 分布一致；
5. 因此服务器无法区分目标 leaf。

---

## 14. 主要理论结果

### 14.1 Correctness

如果 coloring 合法，则每个颜色库中目标 proof 最多需要一个真实节点。

客户端通过 served interval metadata 可以找到这个节点。

真实 PIR replies 加上 default hashes 足以恢复完整 height-`h` SMT proof。

### 14.2 Target Privacy

如果底层 PIR query-private，且 dummy query 与真实 query 分布一致，则 SparseTreePIR 在 public leakage 下 target-private。

### 14.3 Storage and Metadata

Private digest payload：

```text
|A(T)|
```

也就是只存 active proof-bearing nodes。

Public metadata：

```text
O(|A(T)|)
```

### 14.4 Client Complexity

Client lookup：

```text
O(m log N)
```

Proof completion：

```text
O(h)
```

### 14.5 Backend Workload

如果每个颜色子数据库大小为：

```text
|D_1|, ..., |D_m|
```

那么 PIR backend 成本由这些数据库大小决定。

并行 server bottleneck 受：

```text
max_c |D_c|
```

影响。

所以 balance 很重要。

---

## 15. 实验设计

### 15.1 实验不是证明 private retrieval 更便宜

普通 SMT proof serving 一定更便宜，因为它不隐私。

SparseTreePIR 的目标是：

> 量化把普通 SMT proof serving 变成 target-private retrieval 要付出多少成本，并比较不同 private organization 的资源形状。

### 15.2 实验回答的问题

实验回答：

1. 普通 SMT proof payload 多小？
2. target-private retrieval 需要多大额外通信？
3. 不同 private organizations 的 `N`、`m`、largest bucket 是什么？
4. ActiveBalance 是否真的改善颜色库平衡？
5. SimplePIR 后端能否执行这种 workload？

---

## 16. Baselines

### 16.1 Ordinary SMT Proof Serving

这是非隐私语义下界。

服务器知道 target，直接返回真实 sibling digests。

客户端补 default hashes。

它很便宜，但不隐私。

### 16.2 Perfectized TreePIR

把 SMT 补成完整 perfect tree，再用 TreePIR。

问题：

```text
把很多 public default positions 也当成 private records。
```

数据库对象错了。

### 16.3 Pruned-TreePIR-h

先继承 TreePIR height-based layout，再删除 inactive records。

问题：

- 存储减少；
- 但仍然保留 `h` 个 query slots；
- bottleneck bucket 可能更大；
- 不是直接 SMT-first organization。

### 16.4 PBC-active

把 active proof records 当成普通 batch-PIR objects。

问题：

- 不利用 path/interval structure；
- 需要复制；
- batch width 更大；
- largest bucket 更大。

### 16.5 Active-only Global PIR

只存 active records，但不分颜色库。

每个 proof position 都查同一个大库。

问题：

```text
active-only storage 不等于好的 PIR workload。
```

### 16.6 SparseTreePIR

只存 active nodes；

按 active interval forest 染色；

每个颜色一个子数据库；

用 ActiveBalance 平衡；

每次发 `m` 个 fixed-shape PIR subqueries。

---

## 17. Figure 6 的含义

Figure 6 是 compact resource-shape comparison。

它展示：

- Private records；
- Batch width；
- Largest subdatabase。

所有数值都归一化到 SparseTreePIR。

它说明：

- Perfectized TreePIR 的 private records 极大；
- PBC-active 有复制和更宽 batch；
- Active-only global PIR 的 largest searched database 很大；
- Pruned-h 仍然 height-pinned；
- SparseTreePIR 的优势是组合资源形状更好。

---

## 18. 普通 SMT Proof Serving 对比

论文有一张表比较：

```text
Plain SMT proof payload
vs
SparseTreePIR private batch communication
```

结果显示：

```text
SparseTreePIR 通信比普通 SMT proof payload 大 21x 到 127x
```

这不是失败，而是隐私成本。

普通 SMT proof serving 暴露 target。

SparseTreePIR 隐藏 target，所以必须付出 PIR overhead。

这张表让论文更诚实：

> 我们没有假装 private retrieval 免费。

---

## 19. ActiveBalance 实验

### 19.1 对比对象

比较：

```text
node-local hybrid initializer
vs
ActiveBalance
```

两者使用相同 active nodes 和相同 `m`。

区别是：

```text
hybrid 不做 subtree-level balancing
ActiveBalance 做 subtree-load refinement
```

### 19.2 指标

实验记录：

- average active nodes；
- average `m`；
- structural lower bound；
- hybrid max bucket；
- ActiveBalance max bucket；
- AB/lower ratio；
- reduction；
- bucket gap。

### 19.3 结论

ActiveBalance 稳定降低 largest bucket。

对于 `h=16` 和 `h=20`，基本接近结构下界。

对于 `h=24` 大实例，也明显改善，但由于 refinement rounds 有限，仍存在残余 gap。

整体：

```text
平均最大桶从 260.77 降到 224.71
约 13.8% improvement
```

这证明：

> valid coloring 还不够，颜色库 balance 是真实问题。

---

## 20. SimplePIR 实验

### 20.1 为什么接 SimplePIR

论文不是只做结构指标，还用 SimplePIR bridge 检查：

> 这种 color subdatabase workload 是否能被真实 PIR API 执行。

### 20.2 实现方式

每个 Merkle digest 是 32 bytes。

SimplePIR 的方便接口按 machine word 处理。

所以每个 digest 被拆成：

```text
8 个 32-bit chunks
```

对每个颜色子数据库调用：

```text
Init
Setup
Query
Answer
Recover
```

每个 setting 采样 50 个 target leaves。

### 20.3 对比对象

SimplePIR 实验比较：

- uncolored-active PIR；
- Pruned-TreePIR-h；
- SparseTreePIR / ActiveBalance。

### 20.4 结果

相比 flat uncolored-active PIR：

```text
SparseTreePIR 在线通信降低 63.8% 到 75.6%
```

相比 Pruned-h：

```text
byte count 是 mixed
```

有些 setting 更好，有些持平或略差。

论文没有夸大这一点。

稳定 claim 是：

```text
Pruned-h 保持 width h 和较大 bottleneck bucket
SparseTreePIR 保持 width m 和更平 load vector
```

### 20.5 Timing

在最大 setting：

```text
h = 24
99.95% empty
```

SparseTreePIR：

- query generation 从 flat 的 `44.1 ms` 降到 `16.3 ms`；
- answer bottleneck 从 Pruned-h 的 `0.23 ms` 降到 `0.17 ms`；
- recovery 从 flat 的 `7.9 ms` 降到 `2.0 ms`。

这些不是 production performance claim，而是 executable compatibility 和 sanity check。

---

## 21. 论文的最终 Takeaways

### 21.1 Takeaway 1

普通 SMT proof serving 很便宜，但不隐私。

SparseTreePIR 研究的是把它变成 target-private retrieval 的组织层。

### 21.2 Takeaway 2

TreePIR 的 one-query-per-color 思想有用，但在 SMT 中不能 color full coordinate tree。

正确对象是：

```text
active proof-bearing interval forest
```

### 21.3 Takeaway 3

一旦确定 active proof objects，关键资源量是：

```text
N = |A(T)|
m = active width / active color count / active batch width
M = largest color subdatabase
metadata size
```

### 21.4 Takeaway 4

ActiveBalance 解决的是：

```text
合法 coloring 之后颜色库仍然可能不平衡
```

它用 subtree-level color permutation 把 color stores 变平。

---

## 22. 论文边界

本文明确不解决：

- non-membership proof retrieval；
- arbitrary absent coordinate privacy；
- dynamic SMT updates；
- hiding occupancy pattern；
- designing a new PIR primitive；
- production-optimized SimplePIR / SealPIR / Spiral backend；
- general approximation guarantee for ActiveBalance。

这些是后续工作。

本文解决的是：

```text
fixed public SMT snapshot
occupied-leaf membership proof
target-private batch PIR retrieval organization
```

---

## 23. 答辩问题准备

### 23.1 如果被问：你的贡献是什么？

可以回答：

> 我们不是发现 SMT 有 default hashes，这一点已有工作都知道。我们的贡献是把这个语义变成完整的 target-private proof retrieval interface。我们定义 active proof-bearing records，给出 served interval metadata，让客户端能在压缩后的 color subdatabase 中定位真实节点；用 fixed-shape real/dummy PIR queries 隐藏 target；用 default hash completion 恢复普通 height-`h` proof；证明 correctness、privacy 和复杂度；并提出 ActiveBalance 来平衡颜色库，使该组织层对实际 PIR backend 更友好。

### 23.2 如果被问：这不就是剪枝 TreePIR 吗？

可以回答：

> 不是。剪枝只解决少存 default records，但没有自动解决 compacted active records 的 lookup、fixed-shape real/dummy transcript、以及 height-`h` proof completion。SparseTreePIR 是 SMT-first 的组织层：先定义 active proof-bearing interval forest，再在这个对象上做 coloring、metadata、query generation 和 proof completion。

### 23.3 如果被问：m 的意义是什么？

可以回答：

> `h` 是 verifier-facing proof length。完整 SMT proof 最后仍然是 height `h`。`m` 是 PIR-facing active width，表示一条 proof 中最多有多少个非公开 sibling digest 需要私密检索。在本文接口下，它也是 active color count 和 active batch width。它的意义是把验证坐标长度和私密检索宽度分开。

### 23.4 如果被问：为什么 SimplePIR 对 Pruned-h 不是全面赢？

可以回答：

> SimplePIR 的 byte count 受 parameter tiers 和 chunked digest retrieval 影响，不一定严格随 width 和 bucket size 单调变化。因此我们没有声称全面 beat Pruned-h。我们的稳定 claim 是结构性的：Pruned-h 保持 width `h` 和更大 bottleneck bucket；SparseTreePIR 保持 width `m` 和更平 color-store load vector。SimplePIR bridge 主要证明 workload 可执行，并展示相比 flat uncolored-active PIR 的明显收益。

### 23.5 如果被问：为什么只做 membership proof？

可以回答：

> Membership proof 的 served interval 可以建立在 occupied-leaf rank 上。Non-membership query 面向 arbitrary absent logical coordinate，需要把 served interval 扩展到完整逻辑坐标空间，查询接口和泄漏模型都不同。我们把 fixed public snapshot membership retrieval 作为第一个清晰 endpoint，non-membership 是自然下一步。

---

## 24. 最终评价

这篇文章现在的形态是一个完整的安全/系统方向 organization-layer paper。

它不是：

- 新 PIR primitive；
- 普通 SMT proof 优化；
- TreePIR 的简单剪枝；
- 隐藏整个 SMT occupancy 的方案。

它是：

> fixed public SMT snapshot 上 membership proof 的 target-private batch PIR retrieval organization。

它把：

- SMT 的 public default completion；
- TreePIR 的 one-query-per-color intuition；
- PIR 的 fixed-shape query privacy；
- active interval metadata；
- color subdatabase balancing；

组合成一个完整、可证明、可实验的系统接口。

---

## 25. 最适合放在汇报结尾的一句话

> SparseTreePIR does not make SMT proofs smaller; it makes ordinary SMT proof serving target-private by identifying the right PIR-facing proof objects, indexing them by served intervals, coloring the active interval forest, and completing the standard height-`h` proof locally from public default hashes.

中文版本：

> SparseTreePIR 不是让 SMT proof 更短，而是把普通 SMT proof serving 变成 target-private retrieval：它找出真正需要私密检索的 active proof objects，用 served intervals 索引，用 active interval forest 染色分库，并用公开 default hashes 在客户端补回标准 height-`h` proof。

