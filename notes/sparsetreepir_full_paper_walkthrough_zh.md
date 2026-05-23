# SparseTreePIR 全文内容讲解稿

本文档用于讲清楚当前英文稿 `manuscripts/sparsetreepir_body_full_en.tex` 的完整逻辑。它不是论文正文，而是一份“读者视角 + 作者答辩视角”的中文讲解稿：帮助我们自己把故事讲顺，也方便后续写 introduction、准备 PPT、回答审稿人问题。

---

## 0. 一句话概括

这篇论文研究的问题是：

**在一个固定且公开结构的 Sparse Merkle Tree（SMT）里，客户端如何用 batch PIR 私密检索某个已存在叶子的 Merkle membership proof，同时服务器不知道客户端查的是哪个叶子。**

核心方法是：

**不要把完整高度为 \(h\) 的 SMT 坐标树直接当作 PIR 数据库，而是只把真正可能出现在证明里的非空 sibling digest 抽出来，形成 active proof-bearing nodes；再按 served interval 建立索引，并用祖先染色把这些节点分到若干颜色子库中。客户端每个颜色发一次 PIR 查询，真实缺失的 proof level 用公开 default hash 本地补齐。**

论文的中心问题不是“TreePIR 能不能用于 SMT”，而是：

**TreePIR 的 one-query-per-color 思想在 SMT 上应该给什么对象染色？**

本文的答案是：

**给 active proof-bearing interval forest 染色，而不是给完整 SMT 坐标树染色，也不是先按 perfect tree 染色再删除空节点。**

---

## 1. 论文整体主线

全文可以按下面这条逻辑理解：

1. Merkle proof retrieval 本身会泄露隐私。
2. TreePIR 已经说明：如果证明节点有路径结构，可以用“染色 + 每色一次 PIR”来做 batch private proof retrieval。
3. 但是 TreePIR 的原始对象是 perfect binary tree；SMT 的情况不同。
4. SMT 验证时仍然需要完整高度 \(h\) 的 proof coordinate system。
5. 但 SMT 里大量空子树的 digest 是公开 default hash，不需要通过 PIR 私密检索。
6. 因此 SMT 有两个视角：
   - 验证视角：完整高度 \(h\) 的 proof；
   - PIR 检索视角：只需要真实、非空、会出现在 proof 里的 active sibling digest。
7. 本文定义 active proof-bearing nodes 和 served intervals，把 SMT 的 PIR-facing proof object 抽象成 interval forest。
8. 在这个 forest 上做 ancestral coloring，保证同一条 proof path 上没有两个同色节点。
9. 这样客户端可以每个颜色子库发一次 PIR 查询。
10. 如果某个颜色没有真实节点，就发 dummy query，保持 batch 形状一致。
11. 客户端拿到真实 digest 后，用公开 default hash chain 补齐完整高度 \(h\) 的 SMT proof。
12. 论文证明：
    - 这样能恢复正确 proof；
    - 在底层 PIR 安全的情况下，目标叶隐私成立；
    - 需要的颜色数/批量宽度是 active proof length 的最大值 \(m\)，而不是一定等于树高 \(h\)；
    - profile-balanced refinement 能在不增加 \(m\) 的情况下平衡颜色子库。
13. 实验验证：
    - 相比 perfectized TreePIR，完整树坐标空间会造成巨大数据库形状浪费；
    - 相比 active-only global PIR，分颜色子库能降低最大查询库大小；
    - 相比 Pruned-TreePIR-h，本文方法把固定宽度从 \(h\) 降到 \(m\)，并使最大子库更平；
    - SimplePIR backend 说明这种组织方式可以接入真实 PIR API。

---

## 2. 基本概念和符号

### 2.1 SMT 是什么

SMT 是 Sparse Merkle Tree。它仍然是 Merkle tree，只是逻辑地址空间很大，例如高度 \(h=128\) 或 \(h=256\)，理论上有 \(2^h\) 个叶子位置，但实际只有很少一部分叶子被占用。

SMT 的关键性质是：

**空子树的 digest 是公开默认值。**

例如第 0 层空叶子的 digest 是 \(\Delta_0\)，上一层空子树 digest 是 \(\Delta_1\)，依此类推。这条 default hash chain 是公开可计算的。

所以，如果某个 proof level 的 sibling subtree 是空的，客户端不需要向服务器要这个 hash，可以自己计算出来。

### 2.2 完整 proof 与 active proof

对一个高度为 \(h\) 的 SMT，一个普通 membership proof 仍然有 \(h\) 个 sibling digest 位置。

但是其中一些 sibling digest 是：

- 真实非空子树 digest：需要服务器提供；
- 空子树 default digest：客户端公开计算即可。

因此本文把 proof 分成两部分：

- **private retrieval part**：真实非空 sibling digest；
- **public completion part**：default hash 补齐。

### 2.3 主要符号

| 符号 | 含义 |
|---|---|
| \(T\) | 一个固定的 SMT snapshot |
| \(h\) | SMT 的逻辑高度 |
| \(\mathcal{L}\) | 真实占用的叶子集合 |
| \(n=|\mathcal{L}|\) | 真实叶子数量 |
| \(u\) | SMT 中的一个节点 |
| \(\operatorname{sib}(u)\) | 节点 \(u\) 的兄弟节点 |
| \(\operatorname{cnt}(u)\) | 节点 \(u\) 子树中真实叶子的数量 |
| \(\mathcal{A}(T)\) | active proof-bearing node 集合 |
| \(N=|\mathcal{A}(T)|\) | 需要放入 PIR 数据库的真实 proof records 数量 |
| \(\mathsf{Path}(\ell)\) | 目标叶 \(\ell\) 的 active proof path |
| \(m\) | 最大 active proof path 长度，也就是 exact active width |
| \(\varphi\) | 染色函数，把 active node 映射到颜色 |
| \([m]\) | 颜色集合，表示 \(\{1,2,\ldots,m\}\) |
| \(\mathcal{D}_c\) | 颜色 \(c\) 的 PIR 子数据库 |
| \(M(\varphi)\) | 最大颜色子库大小，即 \(\max_c |\mathcal{D}_c|\) |
| \(\mathcal{M}_c\) | 颜色 \(c\) 的公开 interval metadata |
| \(\Delta_i\) | 第 \(i\) 层空子树的 default hash |

### 2.4 \(\varphi:\mathcal{A}(T)\rightarrow[m]\) 是什么意思

\(\varphi\) 是染色函数。

它的输入是一个 active proof-bearing node，输出是一个颜色编号。

例如：

\[
\varphi(u)=3
\]

表示节点 \(u\) 被放入第 3 个颜色子数据库 \(\mathcal{D}_3\)。

\([m]\) 表示颜色编号集合：

\[
[m]=\{1,2,\ldots,m\}.
\]

为什么颜色数是 \(m\)，而不是 \(h\)？

因为本文的 PIR-facing proof path 只包含 active nodes。某条 proof 真实需要私密检索的节点数可能小于 \(h\)。令所有叶子中最长 active proof path 的长度为 \(m\)，则 \(m\) 个颜色刚好足够，并且在本文 one-query-per-color interface 下是 tight 的。

---

## 3. 论文各部分内容详解

## 3.1 Introduction

### 这一节想解决什么

Introduction 的目标不是先讲算法，而是先讲清楚问题为什么存在。

它的故事线是：

1. Merkle proof 是认证数据结构中非常重要的东西。
2. 客户端向服务器请求某个 key 的 proof，会暴露自己在查哪个 key。
3. PIR 可以解决“服务器不知道客户端查哪个位置”的问题。
4. TreePIR 已经证明，对 perfect tree 的 Merkle proof，可以利用路径结构做 batch PIR。
5. 但是 SMT 与 perfect tree 不同：
   - verifier 看到的是完整高度 \(h\) 的 proof；
   - PIR 不应该检索所有 \(h\) 层坐标；
   - 因为空 sibling 可以用 default hash 补齐。
6. 所以 SMT 需要重新定义“PIR 数据库对象”。

### Introduction 的核心问题句

文章现在最重要的问题意识是：

**The central question is not whether TreePIR's one-query-per-color principle is useful for SMTs, but what object the principle should color.**

中文就是：

**关键问题不是 TreePIR 的每色一次查询思想能不能用于 SMT，而是这个思想在 SMT 上应该给什么对象染色。**

这句话把论文从“TreePIR 的简单扩展”变成了“SMT proof retrieval 数据组织问题”。

### Introduction 中的三个自然但不充分的方法

论文指出，读者可能会想到三种自然做法：

1. **Perfectized TreePIR**
   - 把 SMT 补成完整 perfect tree；
   - 然后直接跑 TreePIR；
   - 问题：PIR 数据库包含大量空节点和无关坐标，数据库形状错了。

2. **PBC-active / generic batch PIR**
   - 只取 active records，但把 proof retrieval 当成普通 batch PIR；
   - 问题：没有利用 Merkle proof path 的祖先结构，可能有复制、额外 batch overhead。

3. **Pruned-TreePIR-h**
   - 先在完整 tree 上按 TreePIR 思路染色；
   - 再删除 inactive/default records；
   - 问题：仍然被高度 \(h\) 绑定，且 compact lookup、dummy query、proof completion 并不是 pruning 自动给出的。

本文提出第四种方案：

**直接在 active proof-bearing interval forest 上组织数据库和染色。**

---

## 3.2 Background

Background 不是泛泛介绍 Merkle tree，而是只讲后文需要的背景。

### 3.2.1 Sparse Merkle proofs as private records

这一小节说明：

SMT 的 membership proof 仍然长度为 \(h\)，但不是所有位置都需要服务器返回。

如果某个 sibling subtree 是空的，它的 digest 是公开 default hash。

因此服务器真正需要私密提供的是：

**非空 sibling subtree 的 digest。**

这就是 active proof-bearing records 的来源。

### 3.2.2 From one proof to one batch workload

这一小节连接 TreePIR。

如果每一层 proof 都单独 PIR，开销很大。

TreePIR 的思想是：

对 proof-bearing nodes 染色，使得一条 proof path 上每个颜色最多出现一次。

这样客户端可以：

每种颜色发一次 PIR 查询。

SMT 中也想保留这个思想，但 coloring object 要改变：

**不是完整 tree nodes，而是 active proof-bearing nodes。**

### 3.2.3 Cost model

论文用四个量描述组织层对 PIR backend 的影响：

1. \(N=|\mathcal{A}(T)|\)
   - 私有 proof records 总数；
   - 决定总存储。

2. \(w\)
   - 每个 proof 需要多少 PIR subqueries；
   - 本文方法中 \(w=m\)。

3. \(M=\max_c |\mathcal{D}_c|\)
   - 最大颜色子库大小；
   - 对并行 PIR 来说，最大子库往往是瓶颈。

4. \(|\mathsf{Meta}|\)
   - 公开 metadata 大小；
   - 不进入 PIR payload，但需要发布、存储、搜索。

这套资源模型很重要，因为后面的实验都是围绕它展开。

---

## 3.3 SparseTreePIR organization contract

论文在 Background 中给了一个 contract。它可以理解成系统承诺。

输入：

- 一个固定公开 SMT snapshot \(T\)；
- 真实叶子集合公开；
- default hash chain 公开；
- 客户端想查询某个 occupied leaf 的 membership proof。

Setup 输出：

- active color subdatabases \(\mathcal{D}_1,\ldots,\mathcal{D}_m\)；
- 每个颜色对应的公开 metadata table \(\mathcal{M}_c\)；
- active width \(m\)。

在线查询：

- 客户端对每个颜色发一个 PIR subquery；
- 如果该颜色有真实 proof node，就查询真实 index；
- 如果没有，就查询 dummy index。

客户端完成：

- 收集真实 digest；
- 用 default hash 补齐空层；
- 得到普通高度 \(h\) 的 SMT proof；
- 验证 root。

这个 contract 是全文的核心接口。

---

## 3.4 Related Work

Related Work 不是简单堆文献，而是定位本文在已有工作中的位置。

### 3.4.1 Merkle trees and authenticated data structures

这一段说明：

Merkle tree 被广泛用于：

- Certificate Transparency；
- Key Transparency；
- authenticated dictionaries；
- blockchain state commitment；
- stateless clients。

这些工作说明 Merkle-style commitments 很重要，但大多数不解决：

**客户端如何私密获取 proof material。**

### 3.4.2 Sparse Merkle trees

这一段说明：

SMT 的 default hash 机制已经在很多系统中出现。

本文不是发明 SMT，而是利用 SMT 的 public default completion 语义，把 proof 分成：

- 私密检索的真实 digest；
- 公开补齐的 default digest。

### 3.4.3 Private proof retrieval and TreePIR

这一段说明：

TreePIR 是最接近的 organization-layer 工作。

本文继承 TreePIR 的 one-query-per-color 思想，但不同点是：

- TreePIR 给 perfect tree proof nodes 染色；
- 本文给 SMT induced active interval forest 染色。

### 3.4.4 Batch and practical PIR

这一段说明：

本文不是新的 PIR primitive。

底层可以接：

- XPIR；
- SealPIR；
- OnionPIR；
- Spiral；
- SimplePIR；
- PIANO；
- YPIR；
- vectorized/batch PIR。

本文的贡献是：

**把 Merkle proof records 组织成适合这些 PIR backend 查询的子数据库形状。**

---

## 3.5 Model, Leakage, and Problem Formulation

这一节是形式化定义部分。

### 3.5.1 固定公开 SMT snapshot

论文假设：

- SMT snapshot 是固定的；
- 树高 \(h\) 公开；
- 真实叶集合或 occupancy pattern 公开；
- active metadata 公开。

本文不隐藏：

- 哪些 key 存在；
- 树的稀疏结构；
- active intervals；
- color subdatabase sizes。

本文隐藏：

- 客户端查的是哪个 occupied leaf；
- proof path 上哪些 active nodes 被查询；
- 每个颜色子库内的真实查询 index；
- 哪些颜色是真实查询，哪些是 dummy。

这很重要，因为安全主张必须和 leakage model 对齐。

### 3.5.2 Active proof-bearing node

定义：

对非根节点 \(u\)，如果：

\[
\operatorname{cnt}(u)>0
\]

且

\[
\operatorname{cnt}(\operatorname{sib}(u))>0,
\]

则 \(u\) 是 active proof-bearing node。

直观解释：

1. \(u\) 自己必须是非空的，否则它的 digest 是 default hash，不需要存；
2. \(u\) 的兄弟子树必须也有真实叶子，否则 \(u\) 不会作为某个真实目标叶子的 sibling proof 出现。

换句话说：

**active node 是真实存在、并且确实可能作为某个 proof sibling 被需要的节点。**

### 3.5.3 Active proof path

对目标叶 \(\ell\)，\(\mathsf{Path}(\ell)\) 是该叶 proof 中所有需要私密检索的 active sibling nodes。

注意：

普通 SMT proof 长度是 \(h\)。

但 active proof path 长度可能小于 \(h\)。

### 3.5.4 为什么 \(m\) 可以小于 \(h\)

定义：

\[
m=\max_{\ell\in\mathcal{L}} |\mathsf{Path}(\ell)|.
\]

也就是说，\(m\) 是所有真实叶子的 active proof path 中最长的长度。

如果 SMT 非常稀疏，很多 proof level 的 sibling subtree 都是空的，那么这些层不需要 PIR 检索。

所以：

\[
m\le h.
\]

更进一步，论文证明：

\[
m\le \min\{h,|\mathcal{L}|-1\}.
\]

直观上，如果一棵树里只有 \(n\) 个真实叶子，那么一条路径上最多遇到 \(n-1\) 个“真正有另一个真实叶子分叉出来”的 sibling。

### 3.5.5 Client public inputs

客户端在查询前知道：

- 目标叶的公开位置或 rank；
- public default hash chain；
- active interval metadata；
- color assignment；
- 每个颜色子库大小；
- \(m\)。

这些都是公开输入，不作为隐私保护对象。

### 3.5.6 Target privacy game

安全游戏是：

1. Challenger 公开 leakage。
2. Adversary 选择两个目标叶 \(\ell_0,\ell_1\)。
3. Challenger 随机选 \(b\in\{0,1\}\)。
4. Challenger 为 \(\ell_b\) 生成完整 batch PIR transcript。
5. Adversary 猜 \(b\)。

如果 adversary 无法显著优于随机猜测，则 target privacy 成立。

这说明本文隐藏的是：

**在公开 snapshot 中，客户端到底查哪个叶子。**

---

## 3.6 Served-interval representation

这是本文很关键的数据结构。

### 为什么需要 served interval

一个 active node \(u\) 会服务哪些目标叶？

如果目标叶在 \(u\) 的兄弟子树里，那么 \(u\) 会作为它的 sibling proof node。

因此定义 \(u\) 的 served interval：

\[
I_{\mathsf{srv}}(u)=[L(\operatorname{sib}(u)),R(\operatorname{sib}(u))].
\]

注意：

这不是 \(u\) 自己覆盖的叶区间。

这是 \(u\) 的兄弟子树覆盖的目标叶区间。

核心等价关系是：

\[
u\in \mathsf{Path}(\ell)
\Longleftrightarrow
\ell \in I_{\mathsf{srv}}(u).
\]

### 为什么 served interval 有用

每个颜色子库中，所有同色 active nodes 的 served intervals 不相交。

所以客户端给定目标叶 rank 后，只需要在每个颜色的 interval table 中二分搜索，就知道：

- 该颜色有没有真实 proof node；
- 如果有，它在子数据库中的 index 是多少；
- 如果没有，就发 dummy query。

---

## 3.7 Ancestral coloring

### Valid ancestral coloring

染色函数：

\[
\varphi:\mathcal{A}(T)\rightarrow[m].
\]

合法性要求：

对任意真实叶 \(\ell\)，如果两个不同节点 \(u,v\) 都在 \(\mathsf{Path}(\ell)\) 上，则：

\[
\varphi(u)\neq \varphi(v).
\]

也就是说：

**同一条 active proof path 上不能有两个节点同色。**

### 为什么这个约束足够

因为客户端每个颜色只发一次 PIR 查询。

如果同一条 proof path 上某个颜色出现两个真实节点，那么客户端需要从同一个颜色子库拿两个 records，这就破坏 one-query-per-color interface。

因此 ancestral coloring 是 batch PIR correctness 的核心条件。

### Balance metrics

合法染色还不够。

如果某个颜色子库特别大，PIR 查询这个颜色就会很贵。

所以还要关心：

\[
M(\varphi)=\max_c |\mathcal{D}_c|.
\]

目标是让颜色子库尽量平衡，让 \(M(\varphi)\) 接近理论下界。

---

## 4. Direct SMT Organization and Retrieval

这一节是方案主体。

它分成：

1. running example；
2. offline setup；
3. profile-balanced refinement；
4. online query generation；
5. proof completion；
6. retrieval walk-through。

---

## 4.1 Running example

这一小节用图展示：

- 完整 SMT 坐标树是什么样；
- 哪些节点是真实非空节点；
- 哪些节点是 default empty；
- 哪些真实节点会进入 PIR 子数据库；
- 最后每个颜色子库里有哪些节点。

重点是：

**图里的完整树只是解释用，真正存到 PIR 子数据库里的只有 active proof-bearing nodes。**

这个图帮助读者理解：

我们不是压缩 proof 后不管原树结构，而是在完整 SMT proof 语义下，只把需要私密检索的 digest 存入 PIR。

---

## 4.2 Algorithm 1：Offline direct SMT organization

### 输入

- 固定 SMT snapshot \(T\)；
- 真实叶集合 \(\mathcal{L}\)；
- profile balancing 的迭代参数；
- 底层 hash/default hash 规则。

### 输出

- active color subdatabases \(\mathcal{D}_1,\ldots,\mathcal{D}_m\)；
- 每个颜色的 interval metadata \(\mathcal{M}_c\)；
- 染色函数 \(\varphi\)；
- active width \(m\)。

### 主要步骤

1. 遍历 SMT 或 compressed non-default skeleton。
2. 对每个节点计算 \(\operatorname{cnt}(u)\)。
3. 按 active node 定义提取 \(\mathcal{A}(T)\)。
4. 为每个 active node 计算 served interval。
5. 根据 interval containment 建立 interval forest。
6. 计算最大 active proof path 长度 \(m\)。
7. 用 first-fit 得到一个合法 exact-width 初始染色。
8. 调用 profile-balanced refinement 继续优化子库平衡。
9. 按颜色把节点写入子数据库。
10. 为每个颜色生成 sorted interval metadata。

### 这一步的本质

把一个完整 SMT snapshot 转换成：

**一个公开可索引的 active proof database organization。**

---

## 4.3 Algorithm 2：Profile-balanced subtree refinement

### 为什么需要它

first-fit coloring 可以保证合法，但不一定平衡。

例如某些颜色可能包含很多节点，而另一些颜色很少。

PIR 成本往往由最大子库决定，所以需要进一步平衡。

### 核心思想

不是随便给单个节点改颜色。

单节点改色容易破坏祖先约束。

本文采用：

**对子树内部做颜色 permutation。**

如果一个子树 \(U\) 的祖先链已经用了某些颜色，那么 \(U\) 内部可用颜色集合是剩下的颜色。

对 \(U\) 内所有节点做同一个合法颜色置换 \(\pi\)，可以保持路径异色性质。

### 输入

- interval forest；
- 当前合法染色 \(\varphi\)；
- 当前颜色子库大小向量；
- 最大 refinement 轮数 \(R_1\)。

### 输出

- 更平衡的合法染色。

### 主要步骤

1. 枚举候选 subtree \(U\)。
2. 计算该 subtree 的 local color profile。
3. 找到祖先链禁用颜色。
4. 在可用颜色集合上构造合法 permutation。
5. 通过 matching / assignment 选择能改善全局 bucket profile 的置换。
6. 如果改进全局 signature，就接受。
7. 否则拒绝。
8. 重复直到没有改进或达到轮数上限。

### 为什么合法

因为 permutation 不改变 subtree 内部“不同颜色之间的相对区分”，同时不使用祖先已经用过的颜色。

论文中的 Proposition “Validity of subtree color permutations” 证明了这一点。

### 它优化什么

主要优化：

\[
M(\varphi)=\max_c |\mathcal{D}_c|.
\]

也就是最大颜色子库大小。

### 它不是声称什么

它不是全局最优算法，也没有声称通用 approximation ratio。

论文只说：

- 它单调改进；
- 它保留合法性和 exact width；
- 它输出后可用 structural lower bound 给出 instance-wise certificate；
- 小规模 exact OPT 实验显示它在测试实例上接近最优。

---

## 4.4 Algorithm 3：Batch-PIR query generation

### 输入

- 目标叶 \(\ell\)；
- 每个颜色的 metadata table \(\mathcal{M}_c\)；
- 每个颜色子库 \(\mathcal{D}_c\) 的大小；
- 底层 PIR query generator。

### 输出

- 一个包含 \(m\) 个 PIR subqueries 的 batch；
- 客户端本地记录哪些颜色是真实查询、哪些是 dummy；
- 每个真实查询对应的 proof level。

### 主要步骤

对每个颜色 \(c=1,\ldots,m\)：

1. 在 \(\mathcal{M}_c\) 中二分搜索目标叶 rank。
2. 如果某个 served interval 包含目标叶：
   - 找到对应节点在 \(\mathcal{D}_c\) 中的 index；
   - 生成真实 PIR query。
3. 如果没有 interval 包含目标叶：
   - 生成 dummy PIR query；
   - dummy query 要与普通 PIR query 分布不可区分。
4. 把所有颜色的 query 一起发给服务器。

### 服务器看到什么

服务器看到：

- 每个颜色都有一个 PIR query；
- query 格式相同；
- 不知道真实 index；
- 不知道哪个颜色是 dummy。

---

## 4.5 Algorithm 4：Client-side proof completion

### 输入

- 目标叶；
- PIR 返回的真实 digest；
- query generation 时记录的 proof level 信息；
- default hash chain；
- 目标叶自身 value/digest；
- SMT hash function。

### 输出

- 完整高度 \(h\) 的 SMT membership proof；
- 或直接输出重构 root。

### 主要步骤

1. 创建长度为 \(h\) 的 proof slot array。
2. 对有真实 PIR output 的 level，填入对应真实 sibling digest。
3. 对没有真实 output 的 level，填入对应 default hash。
4. 从叶子向上逐层计算 hash。
5. 得到 root，与公开 root 比较。

### 这一步解决了什么疑问

它解决了一个重要问题：

**如果某些颜色只是 dummy，客户端怎么恢复完整 proof？**

答案是：

dummy 对应的是没有真实 active sibling 的颜色位置；完整 SMT proof 中这些缺失 level 是 default hash，可以由客户端公开补齐。

所以：

**real PIR responses + default hashes 足够恢复完整 proof。**

---

## 5. Correctness and Complexity

这一节证明方案不是“看起来能跑”，而是形式上正确。

---

## 5.1 Interface-exact active color number

定理：

在本文 one-query-per-color active-node interface 下，最少颜色数等于：

\[
m=\max_{\ell\in\mathcal{L}}|\mathsf{Path}(\ell)|.
\]

### 下界

如果某条 active proof path 长度是 \(m\)，这 \(m\) 个节点两两都在同一条查询路径上，因此必须全都不同色。

所以至少需要 \(m\) 个颜色。

### 上界

按照 active interval forest 的深度或路径顺序给颜色，可以用 \(m\) 个颜色完成合法染色。

所以 \(m\) 个颜色足够。

因此颜色数 exact。

### 这个定理的意义

它不是说所有可能 PIR 协议的全局最优宽度都是 \(m\)。

它说的是：

**在本文这种 active-node、one-query-per-color、每个节点只放一个颜色子库的 TreePIR-style interface 下，宽度精确等于 \(m\)。**

这点非常重要，避免 claim 过大。

---

## 5.2 Sharp structural bounds

论文证明：

\[
m\le \min\{h,|\mathcal{L}|-1\}.
\]

含义：

- \(m\) 不可能超过树高 \(h\)；
- 也不可能超过真实叶子数减一。

如果 SMT 很稀疏、真实叶子很少，则 \(m\) 可能远小于 \(h\)。

---

## 5.3 Active-record bound

论文还证明 active records 数量与真实叶子数量有关，而不是与 \(2^h\) 直接绑定。

直观上：

完整 SMT coordinate tree 可能巨大。

但 active proof-bearing nodes 只来自真实叶子之间的 branching structure。

这支持本文的存储主张：

**PIR 私有数据库规模应随 active proof material 增长，而不是随完整逻辑坐标空间 \(2^h\) 增长。**

---

## 5.4 Subtree permutation validity

证明：

对子树内部做合法颜色 permutation，不会破坏 ancestral coloring。

这是 profile-balanced refinement 的正确性基础。

如果没有这个证明，算法就像 heuristic。

有了这个证明，至少可以保证：

**每次接受的 refinement move 都仍然保持查询正确性。**

---

## 5.5 Uniqueness

命题：

如果染色合法，那么任意目标叶 \(\ell\) 和任意颜色 \(c\)，\(\mathsf{Path}(\ell)\) 中最多有一个颜色为 \(c\) 的 active node。

这直接支持：

**每个颜色只需要一次 PIR 查询。**

---

## 5.6 Batch-PIR compatibility

命题：

如果底层单项 PIR 正确，则合法染色允许客户端用 \(m\) 个 PIR subqueries 恢复所有真实 proof nodes。

证明逻辑：

- 每个颜色最多一个真实节点；
- 有真实节点就查真实 index；
- 没有就 dummy；
- 收集所有颜色返回值即可得到 active proof material。

---

## 5.7 Proof-completion correctness

命题：

Algorithm 4 可以用 real PIR outputs 和 default hash chain 重构完整 SMT proof。

证明逻辑：

- 每个 proof level 要么有真实 sibling；
- 要么 sibling subtree 为空；
- 真实 sibling 来自 PIR；
- 空 sibling 来自 default hash；
- 因此 \(h\) 个 proof slots 都能填满；
- 自底向上 hash 得到正确 root。

---

## 5.8 Target privacy theorem

定理：

如果：

- 每个底层 PIR query 是 query-private；
- dummy query 与普通 PIR query 分布不可区分；
- 每次都发送固定 \(m\) 个 subqueries；

那么服务器无法区分客户端查询的是 \(\ell_0\) 还是 \(\ell_1\)，除了 public leakage 中已经公开的信息。

证明直觉：

服务器看到的是固定形状 batch：

\[
(Q_1,\ldots,Q_m).
\]

每个 \(Q_c\) 都是对应子库上的 PIR query。

真实 index 被 PIR 隐藏。

dummy 与真实 query 不可区分。

所以目标叶隐私归约到底层 PIR。

---

## 5.9 Same-color intervals are disjoint

引理：

同一个颜色下的 served intervals 互不相交。

否则，如果两个同色 interval 交叠，那么存在某个目标叶同时需要这两个节点，违反路径异色约束。

这个引理支持：

**每个颜色 metadata table 可以用二分搜索定位唯一命中区间。**

---

## 5.10 Structural lower bound

论文给出 exact-width balance 的结构下界 \(B(T)\)。

直观上，最大颜色子库不可能小于：

\[
\left\lceil \frac{N}{m}\right\rceil.
\]

但 interval forest 中某些深层结构也会产生额外限制。

所以 \(B(T)\) 是一个比简单平均更强的 lower bound。

实验中报告：

\[
\frac{M(\varphi)}{B(T)}.
\]

这个比例越接近 1，说明染色越接近结构下界。

---

## 5.11 Profile-balancing certificate

命题：

对于算法输出的染色 \(\varphi_{\mathsf{out}}\)，可以报告：

\[
\rho=\frac{M(\varphi_{\mathsf{out}})}{B(T)}.
\]

这不是先验 approximation guarantee。

它是 instance-wise certificate：

**告诉读者这个具体实例上，我们离结构下界有多远。**

---

## 5.12 Complexity

### Indexing complexity

预处理：

\[
O(N\log N).
\]

空间：

\[
O(N).
\]

在线 lookup：

\[
O(m\log N).
\]

### Profile-balancing complexity

如果 interval forest 有 \(N\) 个 active nodes，颜色数是 \(m\)，最多做 \(R_1\) 轮 refinement，则朴素候选搜索复杂度大致依赖：

- 候选 subtree 数；
- 每次 assignment/matching 的代价；
- \(m\) 的规模。

论文给出 profile-balancing 的形式复杂度，重点是说明：

它是 offline setup 阶段做的，不影响每次 query 的在线开销。

### Proof completion complexity

Proof completion 是：

\[
O(h)
\]

时间和空间。

因为客户端最终仍然要处理完整高度 \(h\) 的 SMT proof slots。

### End-to-end theorem

Theorem VI.7 是全文理论收束：

给定固定 SMT snapshot、active set、合法染色、metadata 和安全 PIR backend，SparseTreePIR 满足：

1. 返回合法高度 \(h\) 的 SMT membership proof；
2. 在 public leakage 下 target-private；
3. 私有 payload 正好是 \(N=|\mathcal{A}(T)|\) 个 digest records；
4. metadata 是 \(O(N)\)；
5. lookup + completion 是 \(O(m\log N+h)\)；
6. backend workload 由颜色子库 profile \(\{|\mathcal{D}_c|\}\) 决定。

这相当于整篇论文的系统 contract theorem。

---

## 6. Experimental Evaluation

实验部分不是随便跑数据，而是验证资源模型。

它围绕四个核心资源：

1. private records 数量 \(N\)；
2. batch width \(m\)；
3. 最大颜色子库 \(M\)；
4. public metadata 大小。

---

## 6.1 Evaluation logic

论文先说明每个实验验证什么：

| 理论预测 | 观察指标 | 实验位置 |
|---|---|---|
| 不应存完整坐标树 | \(N\) vs. \(2^h\) | resource comparison |
| active width 可能小于 \(h\) | \(m\) vs. \(h\) | sparsity/high-height |
| 平衡染色很重要 | \(M/B(T)\), gap | profile-balanced experiments |
| metadata 不是隐藏成本 | metadata bytes, setup time | metadata table |
| backend 会受数据库形状影响 | SimplePIR KB/timing | backend experiment |

---

## 6.2 Headline resource-shape comparison

Figure 6 比较：

- Perfectized TreePIR；
- PBC-active；
- Active-only global PIR；
- Pruned-TreePIR-h；
- SparseTreePIR。

它展示三个指标：

1. private records；
2. batch width；
3. largest subdatabase。

代表性结论：

- Perfectized TreePIR 的 records 数由完整坐标树决定，巨大；
- Active-only global PIR 虽然只存 active records，但每次查询还是面对一个大库；
- Pruned-TreePIR-h 删除 inactive records，但仍然 width \(h\)，最大桶也更大；
- SparseTreePIR 同时做到 active-only storage、width \(m\)、更平衡的最大子库。

注意：

Figure 6 是单实例代表图，不是 Table III 的平均值。

---

## 6.3 Height-sparsity balance grid

这个实验测试：

- \(h=16,20,24\)；
- 不同 empty ratios；
- profile-balanced 与 node-local hybrid 比较。

主要指标：

- Avg. active；
- Avg. \(m\)；
- Avg. lower；
- Avg. hybrid max；
- Avg. profile max；
- Profile/Lower；
- Reduction；
- Profile gap。

结论：

profile-balanced 能显著降低最大子库，并接近 structural lower bound。

但是当 \(h=24\) 且 active forest 很大时，有限轮 refinement 可能还留有残余 gap。

这说明：

大规模 active forest 可能需要更多 refinement passes 或更快候选搜索实现。

---

## 6.4 Distribution stress tests

这个实验固定 occupied leaves 数量，改变叶子分布：

1. uniform；
2. clustered；
3. adversarial。

目的：

测试 profile-balanced 是否只在随机均匀数据上有效。

结论：

- 在 clustered/adversarial 分布中，active forest 更不均匀；
- node-local coloring 更容易产生大桶；
- profile-balanced 的收益反而更明显。

这说明算法确实是在 forest structure 上起作用，而不是只靠随机平均。

---

## 6.5 Compressed high-height SMTs

这个实验用：

- \(h=128\)；
- \(h=256\)。

这些高度接近真实 SMT 大地址空间。

实验不 materialize 完整 \(2^h\) 树，而是用 compressed active structure。

结论：

- verifier proof 仍然是高度 \(h\)；
- 但 private retrieval width \(m\) 只由 active path 决定；
- 对高高度 SMT，\(m\) 可以远小于 \(h\)。

这直接体现本文最重要的 separation：

**verification height \(\neq\) private retrieval width。**

---

## 6.6 Public metadata and preprocessing overhead

这个实验回答：

metadata 是不是隐藏成本？

论文报告：

- 每个 active node 的 metadata 大小；
- metadata / digest payload ratio；
- setup time。

结论：

metadata 是公开成本，不能假装不存在。

但它是：

\[
O(N)
\]

而不是：

\[
O(2^h).
\]

所以它随 active records 增长，而不是随完整 SMT 坐标空间增长。

---

## 6.7 Full SimplePIR API backend

这个实验接入了 SimplePIR API。

### 为什么做这个实验

结构指标好看不够。

审稿人会问：

真实 PIR backend 下是否还能跑？

所以论文用 SimplePIR 做 end-to-end API check。

### 怎么接

每个颜色子库中存的是 32-byte Merkle digest。

由于 SimplePIR artifact 的方便接口按 machine word 存 entry，实验把每个 32-byte digest 拆成 8 个 32-bit chunks。

对每个颜色：

1. Init；
2. Setup；
3. Query；
4. Answer；
5. Recover。

### 比较对象

1. Flat / uncolored-active PIR；
2. Pruned-TreePIR-h；
3. SparseTreePIR / profile-balanced。

### 实验结论

相对 flat uncolored-active，SparseTreePIR 明显降低通信和部分 client-side work。

相对 Pruned-TreePIR-h，byte-level 结果是 mixed：

- 有些 setting SparseTreePIR 更好；
- 有些 h=24 tier 下 Pruned-h byte count 更低。

论文没有夸大，而是诚实说明：

SimplePIR 参数 tier 和 32-byte chunking 会导致 byte-level 非平滑。

稳定结论是：

- SparseTreePIR 宽度是 \(m\)，而 Pruned-h 宽度是 \(h\)；
- SparseTreePIR 的最大子库更平；
- backend byte count 受具体 PIR packing 和参数 tier 影响。

---

## 6.8 Appendix A：Full SimplePIR timing

Appendix A 给完整 timing 表：

- Setup；
- QueryGen；
- Answer；
- Recover；
- Online KB。

每个 setting 都包含：

- Flat；
- Pruned-h；
- SparseTreePIR。

这增强了系统实验可信度。

---

## 6.9 Appendix B：Real-key high-height workload

Appendix B 用 Polygon / ZKsync 派生 key workload 做补充。

它不是完整 public state dump，所以放在 appendix，而不是主实验。

它的作用是避免“全是 synthetic”的质疑。

实验说明：

在真实 key workload 里，映射到 \(h=128/256\) 的 SMT 后，active width 和 active records 仍然可由 compressed active skeleton 控制。

---

## 6.10 Appendix C：Small exact-optimum sanity check

这个实验在小规模实例上求 exact min-max optimum。

目的：

检查 profile-balanced 是否明显偏离最优。

结论：

在测试的小实例上，profile-balanced 达到 exact OPT。

注意：

这不是通用 approximation proof。

它只是 sanity check。

---

## 7. Discussion and scope

这一节主动框定文章边界。

### 当前解决的问题

本文解决的是：

**固定公开 SMT snapshot 下，已存在叶子的 membership proof private retrieval organization。**

### 当前不解决的问题

1. Non-membership proof retrieval
   - 任意 absent coordinate 的 proof；
   - 需要重新定义 served intervals 覆盖整个 logical coordinate space。

2. 动态更新
   - 插入/删除叶子后 active metadata 和 coloring 如何维护；
   - 需要 epoch 或 amortized update 模型。

3. 隐藏 occupancy pattern
   - 本文 public leakage 中包括 active structure；
   - 不解决 key set 隐藏。

4. Production-optimized PIR backend
   - SimplePIR bridge 是 API compatibility 和 shape-sensitive check；
   - 不是 SealPIR / Spiral / YPIR 级别的完整性能调优。

### 为什么这些限制不破坏主贡献

因为本文主张是：

**为固定公开 SMT membership proof retrieval 定义正确的 PIR-facing organization layer。**

只要这个 scope 写清楚，这些限制就是边界，不是漏洞。

---

## 8. Conclusion

结论收束三点：

1. SparseTreePIR 把 SMT 的验证结构和 PIR 检索结构分开。
2. Active width \(m\) 是本文 interface 下的 exact batch width。
3. Profile-balanced refinement 在不增加 \(m\) 的情况下让颜色子库接近结构下界。

未来工作：

- non-membership query；
- dynamic SMT；
- 更强 profile-balancing 理论保证；
- 更深的 production PIR backend integration。

---

## 9. 数据结构总览

### 9.1 服务器端存什么

服务器存：

1. 每个颜色子库 \(\mathcal{D}_c\)；
2. 子库中每条 record 是一个 active proof-bearing node 的 digest；
3. 这些 digest 是真实非空 sibling subtree digest；
4. 不存 default empty nodes；
5. 不存完整 \(2^h\) 坐标树。

### 9.2 公开 metadata 存什么

每个颜色 \(c\) 有 metadata table \(\mathcal{M}_c\)。

每条 metadata 通常包含：

- served interval 左端点；
- served interval 右端点；
- node 在 \(\mathcal{D}_c\) 中的 index；
- 对应 proof level；
- 方向信息或路径位信息。

metadata 是公开的。

### 9.3 客户端本地存什么

查询时客户端知道：

- 目标叶；
- metadata；
- default hash chain；
- public root；
- 自己生成的 query plan；
- 哪些颜色是真实，哪些颜色是 dummy。

服务器不知道 query plan 中哪个是真实。

---

## 10. 查询流程完整例子

假设 \(m=4\)，颜色子库是：

- \(\mathcal{D}_1\)；
- \(\mathcal{D}_2\)；
- \(\mathcal{D}_3\)；
- \(\mathcal{D}_4\)。

客户端要查叶子 \(\ell\)。

### Step 1：本地查 metadata

客户端对每个颜色查 interval table：

- 颜色 1：没有 interval 覆盖 \(\ell\)，dummy；
- 颜色 2：找到 index 5；
- 颜色 3：找到 index 9；
- 颜色 4：找到 index 1。

### Step 2：生成 PIR queries

客户端生成：

- \(Q_1\)：dummy query；
- \(Q_2\)：查询 \(\mathcal{D}_2[5]\)；
- \(Q_3\)：查询 \(\mathcal{D}_3[9]\)；
- \(Q_4\)：查询 \(\mathcal{D}_4[1]\)。

### Step 3：服务器返回

服务器对每个颜色子库运行 PIR answer。

服务器只看到：

每个颜色都有一个查询。

它不知道：

- \(Q_1\) 是 dummy；
- \(Q_2,Q_3,Q_4\) 是真实；
- 真实 index 是多少。

### Step 4：客户端恢复 active proof nodes

客户端解码得到：

- 颜色 2 的 digest；
- 颜色 3 的 digest；
- 颜色 4 的 digest。

颜色 1 的 dummy response 被丢弃。

### Step 5：Proof completion

客户端创建长度 \(h\) 的 proof slots。

有真实 digest 的 level 填真实 digest。

其他 level 填 default hash。

### Step 6：验证 root

客户端从目标叶向上 hash。

如果得到 public root，则 proof 验证通过。

---

## 11. 论文贡献该怎么讲

最推荐的贡献表述是三层：

### Contribution 1：Active proof-object abstraction

本文定义了 SMT 下真正需要 PIR 检索的对象：

**active proof-bearing nodes。**

这把完整验证坐标树和私有检索数据库分开。

### Contribution 2：Complete retrieval interface

本文不仅说“少存空节点”，还给出了完整接口：

- served interval metadata；
- 每色一次 real/dummy PIR query；
- proof completion；
- correctness；
- privacy game；
- complexity。

这回应了“pruning 不就行了吗”的质疑。

### Contribution 3：Exact width and balanced color stores

本文证明：

\[
m=\max_\ell |\mathsf{Path}(\ell)|
\]

是 active-node one-query-per-color interface 下的 exact width。

同时提出 profile-balanced refinement，让颜色子库更平衡，降低最大 PIR 子库大小。

### Contribution 4：Resource-model and backend evidence

实验从资源模型出发验证：

- records；
- width；
- largest subdatabase；
- metadata；
- SimplePIR backend。

---

## 12. 审稿人可能问的问题与回答

### Q1：这是不是简单把 TreePIR 用到 SMT？

不是。

TreePIR 的 coloring object 是 perfect tree proof nodes。

本文的 coloring object 是 fixed SMT induced active interval forest。

区别在于：

- 不存 default nodes；
- 用 served interval metadata 做 compact lookup；
- 用 default hash completion 恢复完整 proof；
- width 从 \(h\) 变成 \(m\)；
- profile-balanced 优化 active color stores。

### Q2：这是不是简单 pruning？

不是。

Pruning 只说明删除哪些 records。

它没有自动给出：

- compact lookup interface；
- dummy query 规则；
- proof completion 规则；
- exact width \(m\)；
- active interval forest 上的平衡染色。

本文补的是完整 organization contract。

### Q3：为什么 \(m\) 有意义？

因为 SMT 的验证 proof 长度仍是 \(h\)，但私有检索不一定需要 \(h\) 个真实 digest。

\(m\) 衡量的是：

**一条 proof 中最多有多少个需要 PIR 私密检索的 active digest。**

在稀疏 SMT 中，\(m\) 可以显著小于 \(h\)。

### Q4：服务器如何看起来一样？

每次查询都发送固定 \(m\) 个 PIR subqueries。

每个颜色一个。

真实查询和 dummy query 在底层 PIR query distribution 中不可区分。

所以服务器不知道哪个颜色命中真实 proof node。

### Q5：metadata 会不会泄露？

metadata 是 public leakage。

本文不隐藏 SMT snapshot structure 或 occupancy pattern。

本文隐藏的是：

**给定公开 snapshot，客户端查的是哪个 occupied leaf。**

### Q6：是否支持 non-membership？

当前正文主张是 membership-only。

Non-membership over arbitrary absent coordinates 是 future work。

这是刻意收窄 scope，避免 claim 过大。

### Q7：profile-balanced 是否有理论近似保证？

目前没有通用 approximation ratio。

论文提供：

- 合法性证明；
- 单调改进；
- structural lower bound；
- instance-wise certificate；
- small exact-optimum sanity check。

---

## 13. 如何给零基础读者讲

可以这样讲：

1. Merkle proof 就像一条从叶子到根的“证明链”。
2. 客户端问服务器要哪条 proof，会暴露自己关心哪个 key。
3. PIR 可以让服务器不知道客户端查哪个数据库位置。
4. 但一个 proof 有多个节点，所以需要 batch PIR。
5. TreePIR 的想法是：给树节点染色，让一条 proof 中每个颜色最多出现一次。
6. 这样每个颜色查一次，就能拿到整条 proof。
7. SMT 的特殊点是：很多节点是空的，空节点 hash 是公开的。
8. 所以我们不应该把空节点也放进 PIR 数据库。
9. 我们只存真实会出现在 proof 中的 sibling digest。
10. 每个这样的 digest 服务一段目标叶区间。
11. 我们根据这些区间建 forest，再染色。
12. 客户端查目标叶时，用区间找到每个颜色要查哪个 index。
13. 没有真实节点的颜色就发 dummy。
14. 服务器看到每个颜色都有查询，但不知道哪个是真实。
15. 客户端拿到真实 digest 后，用公开 default hash 补齐完整 proof。

---

## 14. 当前论文最重要的主张

如果只能记住一句技术主张：

**SparseTreePIR separates the height-\(h\) verification interface of an SMT from the smaller active private-retrieval interface, and organizes the latter as an active interval forest that supports exact-width one-query-per-color PIR retrieval plus public default-hash proof completion.**

中文：

**SparseTreePIR 把 SMT 的高度 \(h\) 验证接口和更小的 active 私有检索接口分离，并把后者组织成 active interval forest，从而支持 exact-width 的每色一次 PIR 检索和公开 default hash proof completion。**

---

## 15. 当前文件对应关系

主稿：

- `manuscripts/sparsetreepir_conference.tex`
- `manuscripts/sparsetreepir_body_full_en.tex`

主 PDF：

- `build/sparsetreepir_conference.pdf`

主图：

- `figures/sparsetreepir_smt_logical_storage_figure.pdf`
- `figures/sparsetreepir_workflow_figure.pdf`
- `figures/sparsetreepir_running_example_figure.pdf`
- `figures/sparsetreepir_profile_balanced_before_after_figure.pdf`
- `figures/sparsetreepir_proof_completion_figure.pdf`
- `figures/sparsetreepir_resource_comparison_figure.pdf`
- `figures/sparsetreepir_simplepir_timing_figure.pdf`

主要实验/绘图脚本：

- `scripts/plot_sparsetreepir_resource_comparison.py`
- `scripts/plot_sparsetreepir_simplepir_timing.py`
- `scripts/run_height_sparsity_profile_balance_experiment.py`
- `scripts/run_profile_balance_scale_experiment.py`
- `scripts/run_simplepir_full_backend_experiment.py`
- `scripts/run_real_smt_workload_experiment.py`
- `scripts/run_small_opt_balance_experiment.py`

---

## 16. 后续写作建议

如果后续继续改稿，优先保持以下原则：

1. 不要把文章写成“TreePIR 的小修小补”。
2. 始终强调 SMT 的两个视角：
   - verification coordinate view；
   - PIR-facing active proof-object view。
3. 不要过度 claim。
4. 所有 exact / optimal 说法都限定在 active-node one-query-per-color interface 下。
5. 实验不要堆表，始终围绕 \(N,m,M,\mathsf{Meta}\) 四个资源量。
6. 相关工作不要追求数量，优先引用近年高质量、贴合 key transparency / SMT / PIR backend 的文章。
7. profile-balanced 要讲成“合法、单调、有 certificate 的 local refinement”，不要讲成全局最优算法。

