# Virtual-Swapped TreePIR 整篇文章重写说明与逐节注意事项

这份说明用于指导后续整篇论文的写作和修改。核心目标不是把所有技术点堆进去，而是让读者在没有我们前期讨论背景的情况下，也能顺着论文自然理解：

**我们研究的问题是什么，为什么 TreePIR 不能直接搬过来，我们到底存什么、怎么染色、怎么查询、怎么补全 proof、证明了什么、实验验证了什么，以及哪些事情不是本文声称解决的。**

## 一句话主线

本文把 TreePIR 中“给 proof path 染色，然后每种颜色发一次 PIR 查询”的思想，重新组织到固定 Sparse Merkle Tree 上。关键不是提出一个新的 PIR primitive，而是定义一个适合 SMT membership proof 的 **direct SMT organization layer**：

- SMT 验证仍然需要完整高度 `h` 的 proof 坐标。
- PIR 数据库不应该存完整树上的所有 proof 位置。
- 服务器只存真实会出现在 membership proof 里的 active proof-bearing nodes。
- 空 sibling subtree 对应的 proof level 由客户端用公开 default hash chain 补齐。
- 活跃节点通过 served interval 组织成 interval forest，并用 `profile_balanced` 做颜色子库平衡。

## 摘要注意事项

摘要必须在很短空间内交代五件事：

1. 问题：直接请求 Merkle proof 会泄漏目标对象。
2. TreePIR 背景：TreePIR 适合 perfect tree，但 SMT 有完整坐标结构和稀疏真实 proof material 的分离。
3. 方法：active nodes、served intervals、interval forest、fixed-shape real/dummy batch queries、proof completion。
4. 理论：exact active width `m`，并且限定在 TreePIR-style interface；强调 `m <= min(h, |L|-1)`。
5. 实验：storage、width、balance、metadata、backend-shaped checks。

不要在摘要里过度声称“优于所有 PIR backend”或“支持 non-membership”。当前严格范围是固定 public SMT snapshot 上 occupied leaves 的 membership-proof retrieval。

## Introduction 注意事项

Introduction 要讲故事，而不是先给定义。

推荐逻辑：

1. Merkle tree 为什么重要：验证、透明日志、key transparency、authenticated dictionary、blockchain state。
2. 隐私问题出现在哪里：proof retrieval 暴露目标 key/account/certificate。
3. PIR 能隐藏单条记录，但 Merkle proof 是 batch records。
4. TreePIR 解决 perfect tree 的 batch organization。
5. SMT 的新问题：验证结构是完整高度 `h`，但真实需要私密检索的 proof material 很少。
6. 不能简单 perfectize，也不能只 pruning：
   - perfectize 会让 PIR backend 看到大量 default/irrelevant records；
   - pruning 不给 lookup interface；
   - pruning 不降低 inherited width `h`；
   - pruning 不解决 color subdatabase imbalance。
7. 本文提出 direct SMT organization。
8. 后续问题是颜色子库平衡，因此引入 `profile_balanced`。

这一节要避免的误解：

- 不要让读者以为我们改变了 SMT 的哈希构造。
- 不要让读者以为我们隐藏整棵树的 occupancy structure。
- 不要把贡献写成“一个深奥 coloring theorem”；真正贡献是 protocol-complete organization layer。

## Background 注意事项

Background 应该只放读者后面必须用到的知识。

必须解释：

- SMT height `h` 和完整 proof 长度 `h`。
- default-empty hash chain 的作用。
- Merkle proof 中哪些 sibling digest 需要从服务器拿，哪些可以本地补。
- PIR 单记录隐私和 batch retrieval 的关系。
- TreePIR 的 one-query-per-color 直觉。

不要把 background 写成相关工作综述。相关工作应该留到 Related Work。

## Why Not Trivial Pruning 注意事项

这是防审稿人攻击的关键段落。必须正面回答：

“如果把 SMT 补成满树，再删掉空节点，不就是你们了吗？”

回答必须分三层：

1. Pruning only removes records, but does not define lookup.
2. Pruning inherits height-`h` color interface, but our active width is `m`.
3. Pruning does not rebalance surviving color stores.

这里要把 Pruned-TreePIR-`h` 作为 baseline 写清楚。不要贬低 baseline，说它“不能完成 proof”；更准确的说法是 pruning alone does not provide the complete retrieval interface。

## Related Work 注意事项

Related Work 要服务主线，不要泛泛罗列。

建议分组：

- Merkle trees and authenticated data structures。
- Sparse Merkle Trees and verifiable maps。
- PIR backends。
- TreePIR and coloring-based proof retrieval。
- Balanced partitioning for PIR-facing databases。

这一节要强调：

- 我们不是新的 PIR primitive。
- 我们不是新的 authenticated dictionary。
- 我们是连接 SMT proof structure 和 batch PIR retrieval 的 organization layer。

## Model and Problem Formulation 注意事项

这是最容易出符号问题的一节。必须非常严谨。

必须定义清楚：

- `T`: fixed binary Sparse Merkle Tree snapshot。
- `h`: SMT height。
- `L`: occupied real leaves。
- `n=|L|`。
- `cnt(u)`: subtree 中真实叶子数量。
- active proof-bearing node：必须满足 `cnt(u)>0` 且 `cnt(sib(u))>0`。
- `Path(l)`: membership proof 中需要私密检索的非空 sibling nodes。
- `m=max_l |Path(l)|`。
- client public inputs。
- leakage profile。

特别注意：

- active node 不是 default empty node。
- `Path(l)` 不是完整 proof，它只是需要 PIR 检索的 active part。
- 完整 proof 长度仍然是 `h`。
- 当前只处理 membership proof for occupied leaves。
- non-membership 是 future work，除非以后重写成 full logical-coordinate interval。

## Served Interval 注意事项

这是本文 indexing 的核心，必须写得不含糊。

定义时要说：

- `I_srv(u)` 不是 `u` 自己的 subtree interval。
- `u` 是 proof 中返回的 sibling node。
- `I_srv(u)` 是哪些 target leaves 会需要 `u` 作为 sibling proof node。
- 也就是 `sib(u)` 的 subtree 覆盖的 target leaves。
- endpoint 是 real-leaf rank，不是完整 SMT heap index。

推荐表述：

`u in Path(l) iff r(l) in I_srv(u)`。

注意：

- 这里的 rank 设计是为了让 metadata 和 active leaves 数量相关，而不是和 `2^h` 地址空间相关。
- 对 membership proof 足够；如果以后支持 non-membership，需要改成 logical-coordinate interval。

## Coloring Formulation 注意事项

这一节要让读者知道：为什么染色正好对应 batch PIR。

必须解释：

- colors `[m]` 是 active colors，不是完整树高度 colors。
- valid coloring 要求同一个 active proof path 上颜色互异。
- 每个颜色形成一个 subdatabase `D_c`。
- 因为路径上每个颜色最多一个节点，所以每个颜色最多一个 real PIR query。
- 没有 real node 的颜色发送 dummy query。

平衡目标：

- 主目标是 count balance，即子库大小平衡。
- weighted、count_balanced、hybrid 不再作为主体算法。
- hybrid 只作为实验 ablation baseline。

## Direct Organization Algorithm 注意事项

Algorithm 1 应该体现我们不是 materialize 满树。

输入：

- fixed SMT snapshot。
- occupied leaf set。
- profile-balancing rounds。

输出：

- color subdatabases。
- public metadata。
- coloring。

关键步骤：

1. sort occupied leaves and assign ranks。
2. build compressed non-default skeleton。
3. 对 branching skeleton node 找 active proof-bearing children。
4. 给每个 active node 生成 served rank interval 和 proof level。
5. 构造 interval forest。
6. 计算 `m`。
7. first-fit 得到 feasible exact-width coloring。
8. profile_balanced refinement。
9. build subdatabases and metadata。

注意：

- first-fit 只是可行性初始化，不是贡献主算法。
- profile_balanced 才是平衡算法贡献。
- 不要写成遍历完整 `2^h` 节点。

## Profile-Balanced Algorithm 注意事项

这一节要写得可复现。

必须说明：

- 它做的是 subtree-level color permutation，不是单节点 recoloring。
- 为什么 permutation 合法：不会改变子树内部颜色互异性，也不会用 ancestor-forbidden colors。
- 它的目标是 lexicographic bucket signature。
- local matching/Hungarian 只是找候选 permutation 的 surrogate。
- 真正接受条件是 global signature 下降。
- 因此算法单调终止。

要避免的误解：

- 不要说它有全局最优保证。
- 它有 a posteriori certificate `U/B(T)`，不是先验 approximation ratio。
- backend-aware balancing 是 future extension，不是当前实验证明的主结果。

## Query Generation 注意事项

在线算法必须强调 fixed-shape。

输入：

- target leaf 和 real-leaf rank。
- color subdatabases。
- public metadata。

输出：

- exactly `m` PIR subqueries。
- local target map。

注意：

- 每个颜色都发一个 query。
- real 和 dummy 在 PIR transcript 中不可区分。
- dummy query 必须是同一 subdatabase 上 syntactically ordinary PIR query。
- 如果实现中出现 empty color class，要 remove 或 pad dummy record。

## Proof Completion 注意事项

这是回答“dummy 怎么还能恢复 proof”的关键。

必须写清楚：

- 完整 SMT proof 有 `h` 个 levels。
- 先用 default hash chain 初始化所有 proof slots。
- 对每个 real PIR response，根据 metadata 中的 proof level 写入对应 slot。
- 没被写入的 slot 保持 default hash。
- 最后按普通 SMT verification 从 leaf hash 向上算 root。

注意：

- proof completion 是本地算法，不需要额外 server round。
- 这是为什么只存 active nodes 仍然能恢复完整 proof。

## Correctness and Complexity 注意事项

这一节要按逻辑顺序证明，不要堆定理。

推荐顺序：

1. exact color number `m`。
2. sharp structural bound `m <= min(h,n-1)`。
3. optimal active batch width，限定 TreePIR-style interface。
4. subtree permutation validity。
5. uniqueness: 每个颜色每条 path 最多一个 active node。
6. batch-PIR compatibility。
7. proof completion correctness。
8. target privacy under public leakage。
9. same-color intervals disjoint。
10. structural lower bound for balance。
11. profile-balancing certificate。
12. complexity。

注意：

- Exact width 的 optimality 不能说成所有可能协议的 lower bound，只能说 TreePIR-style interface 下的 exact width。
- 隐私证明必须相对于 public leakage。
- `same-color intervals disjoint` 使用 served interval。
- preprocessing/indexing 的求和应该是 `sum_{c=1}^m`，不是 `h`。

## Experimental Evaluation 注意事项

实验部分要变成证据链，而不是表格堆叠。

实验顺序建议：

1. High-height structural balance。
2. Distribution stress tests。
3. Compressed high-height SMTs。
4. Real-data Xenon snapshots。
5. Public metadata overhead。
6. Executable backend checks。
7. Discussion。

每个实验必须回答一个问题：

- Table I/at-a-glance：为什么不是 pruning。
- 高度/稀疏度实验：profile_balanced 是否接近 structural lower bound。
- 分布压力实验：clustered/adversarial 下是否仍有效。
- h=128/256：是否不需要 materialize full tree。
- Xenon：真实 key 分布下是否仍有结构收益。
- Metadata：public metadata 是否是隐藏成本。
- LWE/SimplePIR：backend-facing bottleneck 是否真的随最大子库变化。

表格缩写必须解释：

- `H max`: hybrid max bucket。
- `P max`: profile_balanced max bucket。
- `Red.`: reduction of P max over H max。
- `Coll.`: address collisions。
- `Dummy`: dummy query fraction。

注意：

- 不要说 SimplePIR 是完整 end-to-end backend benchmark。
- 只能说 official artifact parameter-level communication check。
- 不要说 profile_balanced 一定降低 total bytes，因为 SimplePIR tiering 会让 total communication 不单调。
- 可以说它降低 parallel bottleneck / largest per-color store。

## Discussion 注意事项

Discussion 要诚实，不能像宣传稿。

必须承认：

- 当前主张是 fixed public SMT snapshot。
- 只隐藏 queried target，不隐藏 active structure。
- 当前严格支持 membership proof。
- non-membership 需要 full logical-coordinate interval。
- dynamic updates/epoch maintenance 只是部署思路，不是本文主贡献。
- production backend integration 还需要 backend-aware balancing。

同时强调：

- 这些限制不是漏洞，而是 threat model 和 problem scope。
- 本文贡献在于定义并验证 direct SMT proof retrieval organization layer。

## Conclusion 注意事项

Conclusion 要收束，不要引入新东西。

应该强调：

- SMT 验证结构和 PIR 检索结构分离。
- active proof-bearing nodes + served interval metadata + exact-width coloring + proof completion 构成完整方案。
- `profile_balanced` 在 exact-width 下改善子库平衡。
- 实验支持 storage、width、balance、backend-facing bottleneck 的收益。
- 后续方向是 non-membership、dynamic epoch maintenance、production PIR backend-aware balancing。

## 全文术语统一表

| 概念 | 推荐写法 | 避免写法 |
|---|---|---|
| 方案名称 | direct SMT organization | redundant SMT wording |
| 树 | fixed binary Sparse Merkle Tree (SMT) | arbitrary Merkle tree |
| 检索对象 | active proof-bearing nodes | all nodes / compressed nodes only |
| 区间 | served interval / served-rank interval | subtree interval of u |
| 宽度 | exact active width m | proof length h |
| 隐私 | target privacy relative to public leakage | hiding the whole tree |
| 查询 | fixed-shape real/dummy batch queries | variable-length queries |
| 后端 | PIR backend check / communication model | full production benchmark |

## 最重要的审稿风险与防御

1. **“这不就是 pruning 吗？”**
   防御：Pruned-TreePIR-h baseline + not just pruning subsection。

2. **“m 的意义是不是很弱？”**
   防御：exact TreePIR-style width + sharp bound `m <= min(h,n-1)` + compressed skeleton interpretation。

3. **“metadata 会不会很大？”**
   防御：metadata overhead table，rank endpoint 说明。

4. **“dummy 是否泄漏？”**
   防御：fixed shape + dummy indistinguishability assumption + target privacy game。

5. **“支持 non-membership 吗？”**
   防御：明确 membership-only，non-membership 需要 logical-coordinate intervals。

6. **“实验太 toy？”**
   防御：h=16/20/24、h=128/256 compressed、clustered/adversarial、Xenon real-data、SimplePIR artifact check。

7. **“backend 结果是否过度声称？”**
   防御：只声称 backend-facing bottleneck 和 communication-shape check，不声称 universal deployment superiority。
