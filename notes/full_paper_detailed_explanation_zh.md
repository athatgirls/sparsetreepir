# Virtual-Swapped TreePIR 论文完整详细讲解

本文档用于系统梳理当前英文稿 `sparsetreepir_body_full_en.tex` 的全部逻辑、方案、算法、证明、实验和局限。它不是论文正文，而是一份“读者视角 + 作者答辩视角”的详细讲解稿，帮助我们把文章讲清楚。

当前版本的核心主线已经收敛为：

> 对于一个固定的二叉 Sparse Merkle Tree，我们不把整棵满树都放进 PIR 数据库，而是只抽取真实可能出现在 Merkle proof 中的 active proof-bearing nodes；再把这些节点组织成区间森林，并做祖先不重复颜色的染色，使客户端可以对每个颜色子库发一次 PIR 查询，最后用公开 default hash 补全完整高度为 `h` 的 Merkle proof。为了让每个颜色子库尽可能均衡，我们提出 `profile_balanced` 子树级颜色轮换算法。

一句话版本：

> 我们提出的是一个面向固定 Sparse Merkle Tree 的 Merkle proof 数据组织层，使 TreePIR 的“一种颜色一次 PIR 查询”思想能够直接作用在稀疏树的真实 proof material 上，而不是先补齐成满树再存储大量 default/无效节点。

---

## 1. 这篇论文到底想解决什么问题

### 1.1 Merkle tree 的基本作用

Merkle tree 用一个 root hash 承诺很多数据对象。客户端如果要验证某个对象是否在树中，只需要：

1. 拿到目标叶子的值或 digest。
2. 拿到从叶子到根路径上每一层的 sibling digest。
3. 从叶子开始逐层 hash。
4. 最后比较重建出的 root 是否等于公开 root。

这个 sibling digest 序列就是 membership proof。

Merkle proof 的好处是短，通常长度为树高 `h`，而不是整棵树大小。

### 1.2 Merkle proof 检索的隐私问题

如果客户端直接告诉服务器：

> 请给我账户 `x` / 证书 `y` / 状态 key `z` 的 Merkle proof。

服务器就知道客户端正在验证哪个对象。

所以这里的问题不是普通的“数据库能不能查到数据”，而是：

> 客户端如何在不暴露目标叶子的情况下，私有地拿到完整 Merkle proof？

这自然引出 PIR。

### 1.3 为什么这是 batch PIR 问题

PIR 本来解决的是：

> 客户端从数据库中取一个记录，但服务器不知道取的是哪一个。

但 Merkle proof 不是一个记录，而是一组 sibling digest。

对于高度为 `h` 的普通 Merkle proof，验证概念上需要 `h` 个 sibling digest。因此 proof retrieval 天然是 batch retrieval：

```text
one Merkle proof = multiple proof records
```

如果每一层都独立跑一次 PIR，也可以隐藏隐私，但效率很差，因为没有利用 proof path 的结构。

### 1.4 TreePIR 的思想

TreePIR 的核心思想是：

1. 对树里的 proof nodes 染色。
2. 保证一条 proof path 上不会有两个节点颜色相同。
3. 每种颜色形成一个 PIR subdatabase。
4. 客户端查一个 proof 时，对每种颜色子库发一次 PIR 查询。
5. 因为路径上每种颜色最多出现一个节点，所以每个颜色子库最多取一个真实记录。

这就是 “one query per color” 的逻辑。

### 1.5 我们和 TreePIR 的区别

TreePIR 主要针对 perfect binary tree，也就是满二叉树。对于满树，每个位置都可以自然编号，proof path 也非常规则。

但是 Sparse Merkle Tree 不一样：

1. SMT 有一个完整逻辑高度 `h`。
2. 逻辑上有 `2^h` 个叶子位置。
3. 实际上只有一小部分叶子被占用。
4. 大量子树为空。
5. 空子树的 hash 可以由公开 default hash chain 直接计算。

所以 SMT 有两个不同层次：

```text
完整 SMT 坐标系统：验证时需要，保持高度 h。
真实 PIR 数据库：只应该存需要私有检索的真实 proof material。
```

我们的核心观点是：

> 补齐坐标系统不等于补齐 PIR 数据库。

也就是说，我们可以保留完整 SMT 的验证语义，但不应该把所有 default/空节点都塞进 PIR 子库。

---

## 2. 文章的核心贡献

当前论文的贡献可以整理成五点。

### 2.1 直接 sparse-SMT proof organization

我们定义了什么节点需要进入 PIR 数据库：

```text
active proof-bearing nodes
```

这些节点是真实可能出现在某个 membership proof 中的 sibling-side nodes。

不 active 的节点不进入 PIR 子库，因为它们对应的 proof level 可以由 default hash 补齐。

### 2.2 完整 batch-PIR retrieval interface

我们不只是说“少存点节点”，而是完整定义了检索流程：

1. 服务器离线抽取 active nodes。
2. 服务器构建区间 metadata。
3. 服务器对 active nodes 染色。
4. 每种颜色形成一个子数据库。
5. 客户端每种颜色都发一个 PIR query。
6. 如果某颜色没有真实节点，就发 dummy query。
7. 客户端收到真实 responses 后补入 proof slots。
8. 缺失层用 default hash 补齐。
9. 最后恢复完整高度 `h` 的 proof。

### 2.3 exact-width coloring formulation

定义：

```text
m = 所有真实 proof path 上 active nodes 数量的最大值
```

论文证明：

```text
最少需要的 active colors 数量 = m
```

进一步：

```text
最少 private batch width = m
```

注意：

```text
h 是完整 SMT proof 高度。
m 是真实需要 PIR 私有检索的最大 active proof 长度。
```

所以 `m <= h`。

但 `m` 不一定总是明显小于 `h`。中等稀疏时可能还是 `m ≈ h`。论文实验也强调：存储减少通常先出现，width 减少在高稀疏区间更明显。

### 2.4 profile_balanced 子树级平衡染色

合法染色只保证正确性，不保证效率。

如果某个颜色子库特别大，那么这个颜色对应的 PIR 查询就会很重。因此我们真正优化的是：

```text
每个颜色子库大小尽可能平衡。
```

主算法是：

```text
profile_balanced
```

它不是逐个节点改颜色，而是选择区间森林中的一个子树，对整个子树内部颜色做合法 permutation，让全局颜色桶更均衡。

### 2.5 实验验证

实验验证三件事：

1. 直接 sparse organization 相比 perfectized TreePIR-style baseline 能减少存储 proof material。
2. `profile_balanced` 相比 node-local baseline 能显著降低最大子库和 size gap。
3. 真实数据和 backend-shaped 实验说明这个组织层不是纯玩具，而是有系统意义。

---

## 3. 关键定义逐个解释

### 3.1 固定二叉 Sparse Merkle Tree

论文考虑的是：

```text
fixed binary Sparse Merkle Tree T
```

意思是：

1. 树结构/占用叶集合是固定快照。
2. 树高为 `h`。
3. 逻辑叶位置有 `2^h` 个。
4. 真实叶集合记为 `L` 或 `\mathcal{L}`。

这里不是动态插入/删除版本，动态部分已经从主贡献里弱化或删除。

### 3.2 default-empty hash chain

Sparse Merkle Tree 中空子树的 hash 可以公开计算：

```text
Δ0 = default empty leaf hash
Δ1 = H(Δ0 || Δ0)
Δ2 = H(Δ1 || Δ1)
...
Δt+1 = H(Δt || Δt)
```

所以如果 proof 中某一层的 sibling subtree 是空的，客户端不需要服务器通过 PIR 给它返回 digest，客户端自己知道。

这就是我们能“不存空节点”的基础。

### 3.3 Active proof-bearing node

论文中的 active node 是：

```text
真实会出现在至少一个 membership proof 中的节点。
```

形式化写法是：

```latex
\mathcal{A}(T)
```

表示树 `T` 中所有 active proof-bearing nodes 的集合。

直觉判断：

一个非根节点 `u` 会出现在某个叶子的 proof 中，当且仅当它的 sibling subtree 里有真实叶。

因此：

```text
如果 sibling subtree 为空，那么这个位置的 proof digest 是 default hash，不需要存。
如果 sibling subtree 非空，那么这个节点可能作为某些叶子的 sibling digest 出现，需要进入 PIR 子库。
```

### 3.4 Virtual-swapped proof path

对于真实叶 `ℓ`，定义：

```latex
\mathsf{Path}(\ell)
```

它表示叶 `ℓ` 的完整 proof 中需要私有检索的 active nodes。

注意它不是完整长度 `h` 的 proof array，而是其中真实需要 PIR 返回的那部分。

完整 proof 长度仍然是 `h`。

但是 active path 长度可能小于 `h`。

### 3.5 m 的定义

定义：

```latex
m = \max_{\ell \in \mathcal{L}} |\mathsf{Path}(\ell)|
```

意思是：

> 在所有真实叶子的 proof path 中，最多需要多少个 active nodes。

所以：

```text
m <= h
```

`m` 的价值是：

1. 它是 active coloring 最少需要的颜色数。
2. 它是 private batch PIR 最少需要的子查询数。
3. 它把完整验证高度 `h` 和真实私有检索宽度区分开。

### 3.6 颜色集合 `[m]`

论文里写：

```latex
c \in [m]
```

这里：

```text
[m] = {1,2,...,m}
```

所以 `c` 是第 `c` 种颜色，也就是第 `c` 个 PIR 子库。

### 3.7 染色函数

论文写：

```latex
\varphi:\mathcal{A}(T)\rightarrow[m]
```

意思是：

> 对每一个 active proof-bearing node 分配一个颜色。

如果：

```latex
\varphi(u)=c
```

就表示节点 `u` 被放进颜色 `c` 的子库。

### 3.8 合法祖先染色

合法性要求：

```text
同一条 active proof path 上不能有两个节点颜色相同。
```

原因很直接：

客户端对每个颜色子库只发一次 PIR 查询。如果一条 proof path 上同一颜色有两个真实节点，就需要从同一个子库取两个记录，破坏 one-query-per-color 模型。

### 3.9 颜色子库

颜色 `c` 的子库定义为：

```latex
\mathcal{D}_c = \{u\in\mathcal{A}(T): \varphi(u)=c\}
```

意思是：

```text
所有被染成颜色 c 的 active nodes 构成 PIR subdatabase D_c。
```

子库大小：

```latex
N_c = |\mathcal{D}_c|
```

我们的核心优化目标：

```text
让所有 N_c 尽可能均衡。
```

### 3.10 平衡指标

论文当前主线保留三个指标：

```latex
M(\varphi)=\max_c N_c
```

最大颜色子库大小，也就是最重的 PIR 子库。

```latex
\Delta_N(\varphi)=\max_c N_c-\min_c N_c
```

子库大小差值。

```latex
R(\varphi)=M(\varphi)/(N/m)
```

最大子库相对平均子库大小的比例。

如果 `R=1`，说明最大子库刚好等于平均值，非常理想。

---

## 4. 叶区间和区间森林

### 4.1 为什么需要区间

客户端查询某个 leaf 时，需要知道每种颜色里是否有一个 active node 服务它。

如果每个 active node 都能表示成：

```text
它服务哪些目标叶
```

那么客户端就能通过查区间判断是否命中。

### 4.2 叶区间定义

对 active node `u`，定义：

```latex
I(u)=[L(u),R(u)]
```

这个区间表示：

> 哪些真实叶的 proof 会需要这个节点 `u`。

于是：

```latex
u\in \mathsf{Path}(\ell)
iff
\ell \in I(u)
```

直观上：

如果目标叶落在 `u` 对应 sibling subtree 服务的范围内，那么 proof 需要 `u`。

### 4.3 为什么区间是 laminar family

二叉树子树对应连续叶区间。

任意两个子树区间：

1. 要么不相交。
2. 要么一个包含另一个。

不会出现普通交叉。

这叫 laminar family。

### 4.4 区间森林

把 active nodes 按区间包含关系组织起来：

```text
大区间是小区间的祖先。
不相交区间属于不同树。
```

于是得到一个 forest，而不是一定是一棵树。

这个 forest 是我们实际做染色的对象。

### 4.5 为什么在 forest 上染色等价于 proof path 染色

因为：

```text
两个 active nodes 会同时出现在某个 proof 中
等价于
它们的区间相交
等价于
在 laminar forest 中存在祖先-后代关系。
```

所以合法染色就是：

```text
forest 中任意祖先-后代不能同色。
```

这就是论文把 Merkle proof 问题转成 forest coloring 的关键。

---

## 5. 方案完整流程

方案分为两个阶段。

### 5.1 离线阶段

离线阶段由服务器或数据发布者执行。

输入：

```text
固定 SMT T
真实叶集合 L
树高 h
```

输出：

```text
颜色子库 D_1,...,D_m
公开 metadata M_1,...,M_m
染色函数 φ
```

流程：

1. 遍历完整 SMT 或其稀疏表示。
2. 计算每个节点子树中真实叶数量。
3. 找出 active proof-bearing nodes。
4. 对每个 active node 计算服务叶区间 `I(u)`。
5. 按区间包含关系构建 interval forest。
6. 计算最大链长 `m`。
7. 先用一个合法 initializer 得到 exact-width coloring。
8. 用 `profile_balanced` 做子树级 refinement。
9. 按颜色构建子库 `D_c`。
10. 为每个子库构建公开 metadata `M_c`。

### 5.2 在线阶段

在线阶段由客户端执行。

输入：

```text
目标叶 ℓ
公开 metadata
默认 hash chain
每个颜色子库的 PIR 接口
```

输出：

```text
完整高度 h 的 Merkle proof
重建 root
```

流程：

1. 客户端知道目标 leaf 的位置。
2. 对每个颜色 `c`：
   - 在 metadata `M_c` 中二分查找包含目标叶的区间。
   - 如果找到，生成真实 PIR query。
   - 如果没找到，生成 dummy PIR query。
3. 所有 `m` 个 PIR subqueries 同时发送。
4. 服务器对每个颜色子库返回 PIR response。
5. 客户端解出真实 digest。
6. 客户端把真实 digest 写入对应 proof level。
7. 没有真实 digest 的 level 用 default hash。
8. 从目标叶 digest 逐层 hash 到 root。
9. 验证 root 是否等于公开 root。

---

## 6. 每个算法详细解释

## 6.1 Algorithm 1: Offline direct sparse-SMT organization

论文中 Algorithm 1 是整个离线组织算法。

### 输入

```text
T：固定二叉 Sparse Merkle Tree
L：真实叶集合
Init：任意合法 exact-width 初始化染色算法
R1：profile_balancing 最大轮数
```

### 输出

```text
D_c：每个颜色的私有子数据库
M_c：每个颜色的公开 metadata table
φ：最终合法染色
```

### 主要步骤

#### 第 1 步：DFS 统计真实叶区间和数量

对整棵 SMT 做 DFS，得到每个节点：

```text
它覆盖的真实叶范围
它子树内真实叶数量
它的深度
```

这一步是判断 active node 的基础。

#### 第 2 步：抽取 active proof-bearing nodes

对每个非根节点 `u`：

1. 找到它的 sibling `s`。
2. 如果 `s` 的子树包含至少一个真实叶，那么 `u` 会作为某些叶子的 proof sibling。
3. 把 `u` 加入 `A(T)`。
4. 记录 `u` 的 interval 和 proof level。

注意：

```text
进入子库的是 u。
判断 u 是否 active 看的是 sibling subtree 是否有真实叶。
```

因为 proof 的逻辑是：

目标路径走一边，proof 提供另一边的 sibling digest。

#### 第 3 步：构建 interval forest

把所有 active interval 排序：

```text
左端点升序
区间长度降序
```

然后用栈构建包含关系。

父子关系表示：

```text
一个 active node 的服务区间包含另一个 active node 的服务区间。
```

#### 第 4 步：计算 exact active width `m`

`m` 是 interval forest 的最大深度。

也就是最长 active proof path 的长度。

#### 第 5 步：初始化合法染色

用 `Init(F,m)` 得到一个合法 coloring。

论文不把 initializer 当贡献。它只需要满足：

```text
祖先-后代不同色。
使用 m 种颜色。
```

实验里用的是简单 node-local baseline，例如 `count_balanced` 和 `hybrid`。

#### 第 6 步：profile_balanced refinement

用 Algorithm 2 改进颜色桶平衡。

#### 第 7 步：构建子库和 metadata

对每个颜色：

```text
D_c = 所有颜色为 c 的 active node digest
M_c = 每个节点的区间、proof level、node id
```

PIR 子库只需要存 digest。

metadata 是公开的。

---

## 6.2 Algorithm 2: Profile-balanced subtree refinement

这是当前论文的主算法。

### 目标

给定一个合法染色，减少：

```text
max_c |D_c|
```

同时降低：

```text
max_c |D_c| - min_c |D_c|
```

### 核心思想

不要一次只移动一个节点，而是：

> 选一棵子树，把子树内部颜色整体做 permutation。

为什么这样有效？

因为在 interval forest 里，高层颜色选择会约束整个后代区域。单点 recolor 很容易被祖先/后代冲突卡住。子树级 permutation 可以在不破坏合法性的前提下，整体调整多个颜色桶。

### 关键变量

#### `N_c`

颜色 `c` 的全局节点数。

#### `C_U(c)`

子树 `U` 内部颜色 `c` 的节点数。

#### `A(U)`

子树 `U` 可用颜色集合：

```text
A(U) = 没有出现在 U 的严格祖先链上的颜色
```

为什么不能用祖先颜色？

因为子树根和所有子树节点都和祖先在同一条可能路径上，若重复祖先颜色会破坏合法性。

#### `π_U`

对子树 `U` 内颜色集合的 permutation。

例如：

```text
1 -> 2
2 -> 3
3 -> 1
4 -> 4
```

对 `U` 中所有节点统一应用。

### 为什么 subtree permutation 保持合法性

有两类关系要考虑：

1. 子树内部祖先-后代关系。
2. 子树节点和子树外祖先的关系。

对于子树内部：

```text
原来不同色。
permutation 是一一映射。
不同颜色经过 permutation 后仍然不同。
```

对于外部祖先：

```text
π_U 只使用 A(U) 里的颜色。
A(U) 排除了祖先链颜色。
所以不会和祖先冲突。
```

因此合法性保持。

### 代价矩阵

对每个候选子树 `U`，构造一个颜色 assignment 问题。

对于源颜色 `a` 和目标颜色 `b`：

```latex
\widehat{N}_b = N_b - C_U(b)
```

表示如果先把 `U` 从全局负载中拿掉，颜色 `b` 在子树外还剩多少节点。

如果把 `U` 中原来颜色为 `a` 的那部分映射到 `b`，那么目标颜色 `b` 的新负载大约是：

```latex
\widehat{N}_b + C_U(a)
```

代价定义为平方：

```latex
K_U[a,b] = (\widehat{N}_b + C_U(a))^2
```

平方代价的效果是惩罚特别大的桶，鼓励把较大的局部颜色块放到较轻的全局桶里。

### Hungarian algorithm

为了找最优 permutation，算法对这个 cost matrix 跑最小代价完美匹配，也就是 Hungarian algorithm。

复杂度：

```text
O(m^3)
```

### 接受规则

不是所有局部 assignment 都直接接受。

算法会形成候选 coloring `φ'`，然后比较全局签名：

```latex
\Psi(\varphi)=sort_down(N_1,...,N_m)
```

也就是把所有颜色桶大小从大到小排序。

如果候选让这个字典序签名变小，就接受。

这意味着优先降低最大桶；最大桶一样时，再比较第二大桶；依此类推。

### 终止性

每次接受的 move 都严格降低 `Ψ(φ)`。

由于颜色分配是有限的，所以不会无限循环。

实际算法也设置最大轮数 `R1`。

---

## 6.3 Algorithm 3: Batch-PIR query generation

这是客户端生成查询的算法。

### 输入

```text
目标叶 ℓ
颜色子库 D_1,...,D_m
公开 metadata M_1,...,M_m
```

### 输出

```text
m 个 PIR subqueries
本地 target map τ_c
```

### 过程

对每个颜色 `c`：

1. 取 metadata table `M_c`。
2. 根据目标叶在真实叶序中的 rank，对区间表做二分搜索。
3. 如果找到唯一包含目标叶的区间：
   - 该区间对应一个真实 active node。
   - 记录它在子库里的位置 `j_c`。
   - 生成真实 PIR query。
4. 如果没有找到：
   - 说明这个颜色在该 proof path 上没有真实节点。
   - 生成 dummy PIR query。
5. 所有颜色都发 query。

### 为什么二分够用

因为同色区间不相交。

所以某个颜色 `c` 中，最多有一个区间包含目标叶。

### dummy query 的作用

dummy query 不是用来恢复 proof 的。

它的作用是让服务器看到：

```text
每次查询都有 m 个 PIR subqueries。
每个颜色子库都被查询。
服务器不知道哪些颜色是真实命中，哪些是 dummy。
```

---

## 6.4 Algorithm 4: Client-side proof completion

这是证明补全算法。

### 输入

```text
目标叶位置 ℓ
目标叶 digest
metadata tables M_c
target map τ_c
PIR outputs σ_c
default hash chain Δ_0,...,Δ_{h-1}
树高 h
```

### 输出

```text
完整 proof array
重建 root
```

### 过程

1. 初始化长度为 `h` 的 proof array。
2. 先把每个 level 填成对应 default hash。
3. 遍历颜色 `c`：
   - 如果 `τ_c = ⊥`，说明该颜色是 dummy，不写入。
   - 如果 `τ_c` 是真实位置，就从 metadata 中读 proof level `δ`。
   - 把 PIR 返回的 digest 写入 `proof[δ]`。
4. 从目标叶 digest 开始，逐层向上 hash：
   - 如果当前节点是左孩子，hash(current || sibling)。
   - 如果当前节点是右孩子，hash(sibling || current)。
5. 得到 root。

### 关键直觉

客户端并不是只拿 active nodes 就结束。

它还会补齐 default hash。

所以最后恢复的是完整高度为 `h` 的 Merkle proof。

---

## 7. Running example 详细解释

论文使用一个高度 `h=4` 的 sparse SMT 示例。

真实占用叶子：

```text
{16, 17, 19, 22, 28}
```

这是 heap indexing 下的叶子编号。高度 4 时，叶子编号从 16 到 31。

### 7.1 active nodes

示例中 active proof-bearing nodes 有 8 个：

```text
3, 2, 5, 4, 9, 8, 17, 16
```

这些节点会被放入颜色子库。

其他节点虽然在完整树里存在，但如果只是 default 或不需要私有检索，就不会进入 PIR 子库。

### 7.2 exact width

最长 active proof path 长度为 4，所以：

```text
m = 4
```

因此需要 4 个颜色子库。

### 7.3 初始不平衡 coloring

一个合法但不够平衡的初始结果可能是：

```text
D1 = {3}
D2 = {5,2}
D3 = {9,4}
D4 = {17,16,8}
```

子库大小：

```text
(1,2,2,3)
```

合法，但最大子库大小为 3，size gap 为 2。

### 7.4 profile_balanced 后

`profile_balanced` 通过子树级 permutation 得到：

```text
D1 = {3,2}
D2 = {5,4}
D3 = {9,8}
D4 = {17,16}
```

子库大小：

```text
(2,2,2,2)
```

完全平衡。

### 7.5 查询示例

对于 leaf `19`：

1. 客户端查每个颜色 metadata。
2. 颜色 1、2、3 有真实命中。
3. 颜色 4 没有真实命中，发 dummy query。
4. 客户端收到三个真实 digest。
5. 剩余 proof level 用 default hash。
6. 重建 root。

这说明：

```text
不是每个颜色都一定对应真实 proof node。
但是每个颜色都要发 PIR query，以隐藏 real/dummy 差异。
```

---

## 8. 正确性和复杂度证明

## 8.1 Exact minimum active color number

定理：

```text
最少 active colors 数 = m
```

证明分两边。

### 下界

存在一条 active path 长度为 `m`。

这条路径上的节点两两都在同一个 proof 中出现，因此颜色必须两两不同。

所以至少需要 `m` 种颜色。

### 上界

区间森林最大深度为 `m`。

按照 forest depth 染色即可：

```text
深度 1 用颜色 1
深度 2 用颜色 2
...
深度 m 用颜色 m
```

同一路径深度不同，所以颜色不同。

因此 `m` 种颜色足够。

上下界相等，所以最小颜色数就是 `m`。

## 8.2 Optimal active batch width

因为每个颜色子库每次最多取一个真实节点，所以颜色数就是 batch PIR 的子查询数。

如果少于 `m` 个颜色，那么最长 active path 上会有两个节点同色，必须从同一个子库取两个真实节点，违反 one-query-per-color。

所以最少 private batch width 也是 `m`。

## 8.3 Subtree permutation validity

命题：

```text
对子树内部做合法颜色 permutation 不破坏染色合法性。
```

原因：

1. permutation 保持不同颜色仍然不同。
2. 可用颜色集合排除了祖先颜色。
3. 子树外不受影响。

## 8.4 Uniqueness

命题：

```text
任意目标叶 ℓ 和颜色 c，Path(ℓ) 中最多有一个颜色为 c 的 active node。
```

这是合法染色的直接结果。

它保证每个颜色子库最多需要一个真实 PIR target。

## 8.5 Batch-PIR compatibility

如果底层 PIR 本身正确，那么：

1. 每个颜色最多取一个真实节点。
2. 所有颜色的真实节点加起来就是 active proof path。
3. dummy 颜色不影响 proof。
4. 所以 batch-PIR 返回足够恢复所有真实 proof material。

## 8.6 Proof-completion correctness

命题：

```text
真实 PIR responses + public default hashes 足够恢复完整 proof。
```

证明：

完整 SMT proof 的每一层只有两种情况：

1. sibling subtree 非空：对应 active node，通过 PIR 返回。
2. sibling subtree 为空：对应 default hash，客户端公开计算。

两类覆盖所有 level。

所以可以恢复完整长度 `h` 的 proof。

## 8.7 Privacy compatibility

隐私 claim 是相对于公开 leakage 的 query privacy。

公开内容包括：

```text
树高 h
default hash chain
active-node metadata
颜色分配
子库大小
batch width m
```

隐藏内容包括：

```text
目标 leaf
active proof path
哪些颜色是真实 query
每个颜色中真实选中的 index
```

只要：

```text
真实 PIR query 和 dummy PIR query 在分布上不可区分
底层 PIR 对单个子库满足隐私
```

服务器看到的就是固定形状的 `m` 个 PIR queries，无法区分目标 leaf。

## 8.8 Same-color intervals are disjoint

如果同一颜色两个区间相交，那么存在一个真实叶落在交集里。

这个叶的 proof 会同时需要两个同色节点，违反合法染色。

所以同色区间必不相交。

这保证了每个颜色 metadata 可以二分查找。

## 8.9 Indexing complexity

设：

```text
N = active nodes 总数
N_c = 颜色 c 子库大小
```

预处理：

```text
O(N log N)
```

因为需要排序区间。

空间：

```text
O(N)
```

查询索引：

```text
O(m log N)
```

因为每个颜色做一次二分。

## 8.10 Profile-balancing complexity

每轮：

1. 对每个子树维护颜色 histogram：`O(Nm)`。
2. 每个子树求一个 Hungarian assignment：`O(m^3)`。
3. 所有 `N` 个子树：`O(Nm^3)`。

最多 `R1` 轮：

```text
O(R1 * N * m^3)
```

额外空间：

```text
O(Nm)
```

## 8.11 Proof completion complexity

Proof array 长度为 `h`。

写入 active responses 最多 `m` 个。

向上 hash `h` 层。

复杂度：

```text
O(h)
```

总在线客户端非 PIR 本身的工作：

```text
O(m log N + h)
```

---

## 9. 实验完整讲解

实验回答两个核心问题：

1. 颜色子库能否被 `profile_balanced` 做得更平衡？
2. 直接 sparse organization 相比 perfectized TreePIR-style baseline 是否能减少 PIR-facing 成本？

## 9.1 实验中的主要方案

### perfectized TreePIR-style baseline

这是满树基线。

它把完整高度为 `h` 的树都视为 proof-bearing layout。

例如高度 `h=10`：

```text
非根节点总数 = 2^(h+1)-2 = 2046
```

它总是使用 `h=10` 个颜色/层。

### count_balanced

简单 node-local baseline。

目标是让子库节点数量尽可能平衡。

它是一个对照组，不是主贡献。

### hybrid

较强 node-local baseline。

它混合局部 count 和 interval-profile 信号。

论文主要拿 `profile_balanced` 和 `hybrid` 比，因为 `hybrid` 是更强的 baseline。

### profile_balanced

本文主算法。

它在合法 exact-width coloring 基础上，对子树做颜色 permutation，优化全局颜色桶大小。

---

## 9.2 主平衡实验：height-10 sparse SMT

设置：

```text
tree height = 10
sparsity = 0.5, 0.8, 0.9, 0.95, 0.98
每个 sparsity 20 个随机实例
```

指标：

```text
Max bucket：最大颜色子库大小
Size gap：最大子库 - 最小子库
Bucket ratio：最大子库 / 平均子库
Valid：祖先异色合法性
```

结果表：

```text
count_balanced:
  Max bucket = 78.62
  Size gap = 76.62
  Bucket ratio = 1.731
  Valid = 100%

hybrid:
  Max bucket = 47.49
  Size gap = 32.57
  Bucket ratio = 1.222
  Valid = 100%

profile_balanced:
  Max bucket = 37.41
  Size gap = 1.00
  Bucket ratio = 1.037
  Valid = 100%
```

解释：

1. `count_balanced` 反而最大桶很大，说明单点局部平衡不足。
2. `hybrid` 明显更强，但仍有很大 size gap。
3. `profile_balanced` 把 size gap 降到约 1，接近完全均衡。
4. 相比 hybrid，最大子库从 `47.49` 降到 `37.41`，降低约 `21.2%`。

这是本文最重要的算法实验。

---

## 9.3 按 sparsity 分析

表中比较 `hybrid` 和 `profile_balanced`。

```text
sparsity 0.50:
  hybrid max = 139.45
  profile max = 103.00
  reduction = 26.1%
  hybrid gap = 118.45
  profile gap = 1.00

sparsity 0.80:
  hybrid max = 49.45
  profile max = 41.00
  reduction = 17.1%
  hybrid gap = 23.00
  profile gap = 1.00

sparsity 0.90:
  hybrid max = 26.05
  profile max = 22.90
  reduction = 12.1%
  hybrid gap = 11.70
  profile gap = 1.00

sparsity 0.95:
  hybrid max = 14.85
  profile max = 13.20
  reduction = 11.1%
  hybrid gap = 6.70
  profile gap = 1.00

sparsity 0.98:
  hybrid max = 7.65
  profile max = 6.95
  reduction = 9.2%
  hybrid gap = 3.00
  profile gap = 1.00
```

解释：

1. 越密集，颜色平衡越难，profile_balanced 的绝对收益更大。
2. 越稀疏，问题本身更小，所以 reduction 百分比降低。
3. 但所有 sparsity 下 profile gap 基本都是 1，说明稳定接近均衡。

---

## 9.4 Scale-up structural study

设置：

```text
h = 16, 20, 24
occupied leaves = 256 或 1024
distributions = uniform, clustered, adversarial
每组 3 次 trials
```

目的：

证明这不是只在 height-10 toy setting 下成立。

### 256 occupied leaves

代表结果：

```text
h=16 uniform:
  active = 510
  m = 10.67
  hybrid max = 60.33
  profile max = 48.33
  reduction = 19.9%
  profile gap = 0.67

h=16 adversarial:
  active = 510
  m = 14.00
  hybrid max = 133.00
  profile max = 53.00
  reduction = 60.2%
  profile gap = 43.00
```

解释：

adversarial 分布会制造很长 active chain 和严重局部不平衡，所以 profile_balanced 效果更明显。

### 1024 occupied leaves

代表结果：

```text
h=16 uniform:
  active = 2046
  m = 13.00
  hybrid max = 192.33
  profile max = 158.00
  reduction = 17.9%

h=16 adversarial:
  active = 2046
  m = 16.00
  hybrid max = 770.00
  profile max = 191.00
  reduction = 75.2%
```

解释：

1. active nodes 大约接近 `2n-2`，这里 `n=1024` 时 active≈2046。
2. 逻辑高度从 16 到 24 增加，并不会让 active node 数按满树爆炸。
3. direct organization 主要随真实 occupied skeleton 增长，而不是随 `2^h` 增长。

---

## 9.5 Xenon-derived real-data evaluation

设置：

```text
真实数据：Xenon 2024 certificate-log dump
逻辑高度：h=20
keys = 5000, 10000, 20000
映射模式：
  sha256：哈希后放入地址空间，较随机
  sequential：保留顺序，更聚集
```

perfectized baseline：

```text
2,097,150 non-root nodes
width = 20
```

直接 sparse 方案：

```text
只存 active proof-bearing nodes
```

结果：

```text
sha256 5000:
  m = 16
  storage ratio = 0.0048
  hybrid gap = 446
  profile gap = 216
  dummy = 0.250

sha256 10000:
  m = 17
  storage ratio = 0.0095
  hybrid gap = 974
  profile gap = 533
  dummy = 0.206

sha256 20000:
  m = 18
  storage ratio = 0.0191
  hybrid gap = 1707
  profile gap = 1213
  dummy = 0.222

sequential 5000:
  m = 14
  storage ratio = 0.0048
  hybrid gap = 2063
  profile gap = 694
  dummy = 0.036

sequential 10000:
  m = 16
  storage ratio = 0.0095
  hybrid gap = 1764
  profile gap = 1220
  dummy = 0.052

sequential 20000:
  m = 17
  storage ratio = 0.0191
  hybrid gap = 7115
  profile gap = 2949
  dummy = 0.049
```

解释：

1. 即使用真实数据，direct sparse organization 仍然只需要很小比例的存储。
2. 20,000 keys 时 storage ratio 约 1.91%。
3. `m` 是 17-18，而不是 full height 20。
4. `profile_balanced` 在真实数据上继续降低 size gap。
5. sequential 更聚集，导致 hybrid gap 更大，也更能体现 profile_balanced 的作用。

---

## 9.6 Backend-shaped 实验

目的：

证明 direct sparse organization 不只是一个抽象结构指标，也会影响后端看到的数据规模。

注意：

论文没有声称已经实现生产级 SealPIR/Spiral。

实验包含两个 backend-shaped 模型：

1. two-server XOR PIR microbenchmark。
2. single-server matrix-linear surrogate。

### two-server XOR backend

总体结果：

```text
perfectized:
  Store = 1.000
  m = 10.00
  Query bytes = 514.0
  Response bytes = 640.0
  Parallel server ms = 0.028

count:
  Store = 0.500
  m = 9.95
  Query bytes = 260.1
  Response bytes = 636.8
  Parallel server ms = 0.017

hybrid:
  Store = 0.500
  m = 9.95
  Query bytes = 264.1
  Response bytes = 636.8
  Parallel server ms = 0.012

profile:
  Store = 0.500
  m = 9.95
  Query bytes = 264.9
  Response bytes = 636.8
  Parallel server ms = 0.012
```

解释：

1. direct schemes 存储约为 perfectized 的一半。
2. query bytes 约减半。
3. response bytes 变化不大，因为该 backend 的 response 更多与颜色数/记录大小相关。
4. server parallel latency 降低明显。

### matrix-linear backend

总体结果：

```text
perfectized:
  Store = 1.000
  m = 10.00
  Query bytes = 432.0
  Response bytes = 3392.0
  Parallel server ms = 0.013

count:
  Store = 0.500
  m = 9.95
  Query bytes = 331.7
  Response bytes = 2525.3
  Parallel server ms = 0.011

hybrid:
  Store = 0.500
  m = 9.95
  Query bytes = 397.7
  Response bytes = 3034.1
  Parallel server ms = 0.012

profile:
  Store = 0.500
  m = 9.95
  Query bytes = 411.9
  Response bytes = 3098.1
  Parallel server ms = 0.011
```

解释：

1. matrix backend 对 packing shape 更敏感。
2. 最平衡的结构 coloring 不一定给出最小 query bytes。
3. 这说明 structural balance 和具体后端 packing cost 相关但不完全等价。
4. 这也是论文 discussion 中谨慎表述的原因。

---

## 9.7 Sparsity sensitivity

该实验说明：

```text
存储收益比 width 收益更早出现。
```

结果：

```text
sparsity 0.20:
  active nodes = 1636
  storage ratio = 0.800
  avg m = 10.00
  m/h = 1.000

sparsity 0.50:
  active nodes = 1022
  storage ratio = 0.500
  avg m = 10.00
  m/h = 1.000

sparsity 0.80:
  active nodes = 408
  storage ratio = 0.199
  avg m = 9.95
  m/h = 0.995

sparsity 0.90:
  active nodes = 202
  storage ratio = 0.099
  avg m = 9.15
  m/h = 0.915

sparsity 0.95:
  active nodes = 100
  storage ratio = 0.049
  avg m = 7.70
  m/h = 0.770

sparsity 0.98:
  active nodes = 38
  storage ratio = 0.019
  avg m = 6.05
  m/h = 0.605
```

核心解读：

1. 中等稀疏时，`m` 可能仍等于 `h`。
2. 但 active nodes 已经显著少于 full perfectized nodes。
3. 所以 direct organization 的第一阶段收益是存储和数据库规模。
4. 高稀疏时，`m` 才明显下降，带来 batch width 收益。

---

## 10. 文章的 Discussion 和边界

### 10.1 我们不能过度声称什么

论文不能说：

```text
我们全面优于 SealPIR/Spiral。
```

因为当前 backend 实验不是生产级 cryptographic PIR backend。

更准确的说法：

```text
我们证明 direct sparse-SMT organization 会改变 PIR backend 看到的数据库形状，并在 backend-shaped 实验中带来可观察收益。
```

### 10.2 我们隐藏什么，不隐藏什么

隐藏：

```text
目标 leaf
真实 proof path
每个颜色选中的真实 index
哪些颜色 real / dummy
```

不隐藏：

```text
树结构快照
active metadata
颜色子库大小
occupancy pattern
```

所以如果应用场景要求 occupancy pattern 也保密，这个方案不够。

### 10.3 最适合的应用场景

适合：

1. 大逻辑地址空间。
2. 占用叶较少。
3. default hash chain 公开。
4. 查询目标需要隐藏。
5. 结构快照可以公开。

例如：

```text
sparse authenticated maps
revocation/transparency maps
state commitments
```

不太适合：

```text
接近 dense 的 left-balanced tree
occupancy pattern 本身敏感的系统
```

---

## 11. 当前代码与论文主线的关系

### 11.1 代码位置

核心代码在：

```text
scripts/
```

主要文件：

```text
scripts/subtree_permutation_balance.py
scripts/run_profile_balanced_experiment.py
scripts/run_profile_balance_scale_experiment.py
scripts/run_xenon_dataset_experiment.py
scripts/run_sparse_smt_pir_backend_experiment.py
scripts/run_proof_completion_demo.py
scripts/generate_full_sparse_smt_example.py
```

### 11.2 需要注意的历史残留

当前论文已经把主线收敛为：

```text
子库大小平衡
count profile
profile_balanced
```

但是部分 Python 脚本里仍然保留历史字段：

```text
weighted
weight_gap
weight_penalty
weight_loads
```

这些来自之前探索“区间覆盖权重/查询频率负载”的版本。

当前论文正文已经不把它们作为贡献或证明对象。

因此下一步如果要整理代码，建议：

1. 把 `subtree_permutation_balance.py` 改成 count-only 实现。
2. 把 `run_profile_balanced_experiment.py` 中 weighted scheme 和 weight_gap 删除。
3. 把 backend experiment 中 weighted 行删除。
4. 把脚本输出和论文表格完全对齐。

这不是论文逻辑问题，而是代码同步问题。

---

## 12. 如果给别人讲，推荐的叙事顺序

### 12.1 一分钟版本

Merkle proof 检索会泄露查询目标。TreePIR 用染色把 proof retrieval 变成每种颜色一次 PIR 查询，但它面向 perfect tree。Sparse Merkle Tree 里大量 proof level 是 default empty hash，不应该进入 PIR 数据库。我们提出 direct sparse-SMT organization：只存 active proof-bearing nodes，用区间 metadata 索引，用祖先染色保证每色最多一个真实节点，用 dummy query 隐藏空颜色，并用 default hash 补全完整 proof。理论上最少颜色数等于最大 active proof length `m`。算法上，我们提出 `profile_balanced`，通过子树级颜色 permutation 平衡颜色子库。实验显示它显著降低最大子库和 size gap，并且 direct organization 相比 perfectized baseline 减少存储和 backend-facing 成本。

### 12.2 三分钟版本

1. Merkle proof 是一组 sibling digests，所以 private proof retrieval 是 batch PIR。
2. TreePIR 解决了 perfect tree 上的 batch organization。
3. Sparse Merkle Tree 的特殊性是 default-empty hash 可以公开重建。
4. 所以我们不应该把完整 sparse coordinate system 变成 PIR database。
5. 我们抽取 active proof-bearing nodes。
6. 每个 active node 对应服务叶区间。
7. 区间形成 laminar forest。
8. 对 forest 做祖先异色染色。
9. 每种颜色形成一个 PIR 子库。
10. 客户端每种颜色发一次 query，缺失颜色发 dummy。
11. 收到真实 responses 后，用 default hash 补全 proof。
12. `m` 是最大 active proof 长度，也是最少颜色数和最少 private batch width。
13. `profile_balanced` 通过子树颜色 permutation 降低最大子库。
14. 实验表明 `profile_balanced` 比 hybrid 降低最大子库约 21.2%，size gap 接近 1。

### 12.3 审稿人可能问的问题

#### Q1：这不就是把 SMT 补齐后跑 TreePIR 吗？

不是。我们补齐的是验证坐标，不是 PIR 数据库。PIR 子库只存 active proof-bearing nodes。default proof levels 由客户端公开补齐。

#### Q2：为什么要 dummy query？

因为如果某些颜色没有真实命中而客户端不发 query，服务器就知道目标 path 的结构。dummy query 保证每次固定 `m` 个 subqueries。

#### Q3：m 有什么意义？

`h` 是完整 proof 高度，`m` 是真实私有检索宽度。`m` 是 exact minimum active color number，也是 exact minimum private batch width。

#### Q4：如果 m 经常等于 h，那还有收益吗？

有。实验显示存储规模和子库大小会先下降。width reduction 是高稀疏时的第二阶段收益。

#### Q5：profile_balanced 为什么比 node-local 好？

因为不平衡往往来自高层颜色选择对整片后代区域的影响。单节点移动容易被祖先/后代冲突卡住，子树级 permutation 能整体重排颜色 profile，同时保持合法性。

#### Q6：隐私到底隐藏什么？

隐藏目标 leaf 和每个颜色中的真实选中 index。不隐藏 public metadata 和 occupancy pattern。

---

## 13. 当前论文最核心的亮点

如果只能强调三个亮点，建议是：

1. **直接 sparse-SMT proof organization**：把完整 SMT 验证坐标和 PIR 数据库存储对象分离，只存 active proof-bearing nodes。
2. **协议闭环完整**：active extraction、interval metadata、exact-width coloring、real/dummy batch query、proof completion 全部定义清楚。
3. **profile_balanced**：在 exact width 固定后，用子树级颜色 permutation 显著降低最大颜色子库和 size gap。

---

## 14. 当前论文最需要小心的点

1. 不要说我们提出了新的 PIR backend。
2. 不要说全面优于 SealPIR/Spiral。
3. 不要过度强调 `m<h`，因为中等稀疏时 `m` 可能仍等于 `h`。
4. 要强调 storage reduction 和 subdatabase balance 是主要收益。
5. 要明确 public leakage，不隐藏 occupancy pattern。
6. 要尽快同步清理 Python 代码里的 weighted 历史字段。

---

## 15. 最终总结

这篇论文的本质不是一个纯 PIR 后端论文，也不是一个单纯图染色论文，而是：

> Sparse Merkle proof retrieval 的数据组织论文。

它回答的问题是：

> 给定一个固定 Sparse Merkle Tree，哪些 proof nodes 应该进入 PIR 子库？这些节点如何索引？如何染色才能每色一次 PIR？如何让客户端补全完整 proof？如何让颜色子库尽量平衡？

我们的方案答案是：

```text
active proof-bearing nodes
+ leaf-interval metadata
+ interval forest
+ exact-width ancestral coloring
+ profile_balanced subtree permutation
+ fixed-shape real/dummy batch PIR
+ default-hash proof completion
```

这就是整篇文章的完整技术闭环。
