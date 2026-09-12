# SimplePIR 原生 32 B 接入只读审计（2026-09-11）

范围：官方源码、现有两份 Go 驱动和论文原文的静态核查；本次未编译、未执行查询、未测时，也未修改后端或论文。本报告不是新实验的正确性证书。

## 结论与必须遵守的接口边界

**同一批 32 字节 SMT 摘要可以使用 SimplePIR 原生长记录布局，一条记录只需一次在线 Query/Answer。** 这里 `native256` 必须解释为 **256 bits = 32 B**；若真要 256 B，则是 2048 bits，不能沿用 `Ne=26`。现有 `tifs_packed_exploration_20260910.go` 的 `make256`/`recover256` 是可复用的适配依据，但原文件明确只是小规模记录正确性探索，没有完整证明验根或性能结论。

1. 不得仅把 `MakeDB(..., row_length=256, []uint64)` 的长度参数改大，然后继续用 `Recover() uint64`。二者的数值 API 仍只有 64 位。
2. 不得直接用官方 `InitCompressedSeeded` / `DecompressState` 生成公开 A 后继续在同进程 Query。这两函数会重置 **全局** `bufPrgReader`；Query 的 secret/error 也取自该全局源，公开 seed 因而能决定后续私有随机流。必须用现有 helper 的独立 `localSeededA`，保留官方私有随机源；这是适配层处理，不需要修改密码核心。
3. 不得把 Flat 的多条全库查询直接塞进一次 `Answer(DB, MakeMsgSlice(q1,...,qk))`。该实现把数据库按行分成 k 片，每个查询只回答一片。Flat 应对同一数据库逐查询调用 `Answer(DB, MakeMsgSlice(q))`，复用 DB/H/A。

## 官方版本与参数来源

2026-09-11 读取 `git ls-remote https://github.com/ahenzinger/simplepir.git HEAD`，官方 HEAD 与本地 `.tools/simplepir/simplepir-main` 均为 **e9020b03bf2872c75b8954e749e32408b5db87ed**（2023-01-13）。`git diff HEAD -- pir go.mod` 为空；本地仅有未跟踪的既有 eval 驱动。Go 模块声明 Go 1.18，源码使用 CGo/C 编译，`-O3 -march=native`。

| 核查对象 | 固定源码位置 | 结论 |
|---|---|---|
| 参数选择 | [simple_pir.go L14–55](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/simple_pir.go#L14)、[params.go](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/params.go)、[params.csv](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/params.csv) | `n=1024, logq=32, sigma=6.4`；p 随 M 所属行选取。M≤8192 时 p=991；不能把旧 smoke 的 p=991 无条件用于宽矩形大库。 |
| 长记录存放 | [database.go L92–174](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/database.go#L92) | `SetupDB` 计算 `Ne`，要求 L 是 Ne 的倍数且 LM 足够；同记录的 base-p 数位竖直堆叠。 |
| uint64 边界 | [database.go L54–64,178–222](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/database.go#L54)、[utils.go L77–88](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/utils.go#L77) | `MakeDB` 的输入、`Reconstruct_from_base_p` 累加器、`Recover` 返回值均为 uint64。 |
| 公开/私有随机数 | [simple_pir.go L99–116,145–160](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/simple_pir.go#L99)、[rand.go L35–50,87–96,155–157](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/rand.go#L35) | 公共 seed 为 AES 的 16 B key；compressed helpers 改全局流。`localSeededA` 用独立 PRG reader 是正确的集成选择。 |
| 原生 batch 语义 | [simple_pir.go L162–182](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/simple_pir.go#L162)、[pir.go RunPIR](https://github.com/ahenzinger/simplepir/blob/e9020b03bf2872c75b8954e749e32408b5db87ed/pir/pir.go#L99) | 分行片回答，官方示例会给查询索引加相应分片偏移。不是通用重复全库查询接口。 |

原论文主文 **§4.1 / Fig.2，印刷页3894** 说明复用公开 A 和压缩为 seed；**§4.2，页3895** 给出作者按当时格攻击估算选取的 128-bit 参数及正确性误差目标；**§4.3，页3895** 明确讨论纵向数位长记录与分块批量检索。新稿应称“沿用官方参数表”，不能把功能测试或 `n=1024` 本身称为独立完成了当代 128-bit 安全证明。多条数位/多桶证明的总体解码失败概率也不能混同为 128-bit 密码安全。[USENIX 原文](https://www.usenix.org/system/files/usenixsecurity23-henzinger.pdf)

## 不改密码核心的 32 B 恢复方案

推荐复用现有 `tifs_packed_exploration_20260910.go` **L180–241** 的做法：

- 调 `PickParams(recordCount,256,1024,32)` 和 `SetupDB(recordCount,256,&p)`。检查 `Packing==0`，并用整数计算验证 `Ne` 是满足 `p^Ne >= 2^256` 的最小整数；p=991 时 Ne=26。
- 将每条原始 32 B 摘要解释为同一约定的大整数。反复除 p，数位 j 存入 `((i/M)*Ne+j, i%M)`。最后执行官方相同的中心化 `Data.Sub(p/2)`。大端编码/解码只需一致，恢复输出必须逐字节等于原摘要。
- 直接保留官方 `Setup`、`Query`、`Answer`、矩阵运算和参数表。一次 Query 得到一列，其中包含所需记录的 Ne 个数位。
- 恢复适配层照官方 `Recover` 计算 query 的中心化 offset、`H*s`、模 q 差和 `p.Round`，只把最终 base-p 拼接替换为 `big.Int`。旧 `recover256` 的减法 `&((1<<logq)-1)` 对应官方 uint32 矩阵减法；中心化修正亦一致。最后检查位长≤256，再 `FillBytes(32)`。
- **H*s 只算一次/查询。** 理论上可给 `Recover` 一个 `Ne=1, Packing=0` 的 DBinfo 视图，并对数位行 j 使用伪索引 `((i/M)*Ne+j)*M+i%M`，取出各标量再 big.Int 拼接；但每次官方 Recover 都重算整份 H*s，重复 Ne 次会人为放大解码时间。这种逐数位 native-API 路径最多作为轻量正确性对照，不应作主性能实现。

应在新增 smoke 中检查全零、全 ff、最高位为1、前导零、末行填充，以及同一 index 重复查询的恢复；既有 helper 的测试不能代替本轮实际输入的 decoded digest 与独立认证根校验。查询/回答若主表宣称序列化流程，必须让 Answer/Recover 使用反序列化后的对象。

## 防止重复状态和成本不公平

旧 `tifs_full_proof_backend.go` 每个颜色建 8 份 32-bit DB，每份均有独立 A/H，进行8次PIR。它能正确拼回摘要，但应标为 **legacy eight-32-bit implementation**；新 native32B 的 DB 参数变化，不能笼统声称 hint 必然恰好缩小8倍。

| 对象 | 正确的唯一实例与计费方式 |
|---|---|
| Flat | 一个有效摘要库及一份 H/A/seed，多条有独立私有随机数的查询复用它；不得按证明槽位、targets 或 repeats 在同进程复制同一库。 |
| AB | 每个实际桶一份长记录库。空桶若协议固定要查，按公开规则建一个 dummy；不得把默认摘要当实记录重复存入。 |
| PBC | 保留真实三哈希副本与相应桶，不能做内容去重后仍宣称原 PBC。其三个副本属于布局成本，不是32B记录编码的重复。 |
| H | 在 Setup 中真实算 `H=D*A`，按唯一数据库累计 **4 L n** 字节（不含 framing）。不能用 FakeSetup 随机 hint 替代实际预处理和恢复。公开 seed 不能消除数据库相关 H。 |
| A | 持久化/传输采用 seed 时，计实际 16 B seed 及必要参数；另列运行时展开的 **4 M n** 字节。若为序列化正确性持有 client/server 两份展开 A，合并 RSS 中说明双角色，不把它误称客户端状态下界。 |
| Online | 官方 Squish 因子3，query padding 后长度 **3 ceil(M/3)**，answer 长度 L。真实矩阵载荷为 `4*(3 ceil(M/3)+L)` 字节/单次查询；另计实际帧。不能只用未填充 M 计算。 |
| DB | 区分原始摘要载荷、布局复制载荷、矩形填充和 Squish 后物化矩阵；后者按实际 `DB.Data.Size()*4`。不得用理论10-bit数位数替代真实内存，也不得把保留的输入/验算副本隐藏在“服务器RAM”里。 |

共享 A 可用于兼容维度的多个库，前提是每条查询私有随机数独立，且生成规则公开明确。是否这样做属于固定实施政策，应对 AB/PBC/Flat 一致应用；更关键的是不得重复下载或重复初始化同一个逻辑数据库的 H。seed 复用不等于查询/secret复用。

固定快照内 setup 只做一次。AB/CSA 离线着色构造与 PBC 分桶的计时边界仍须明确，不能一侧包含构造另一侧排除后宣称总 setup 更快。固定公开 query 数并使用 dummy，不能让 Flat 仅查询目标的实际非默认数而泄漏数量，再与固定宽度方法作同隐私比较。

## 跨后端比较应支持的论断

最主要的估计量是 **每个后端内部** 的 AB/PBC、AB/Flat 差值或比值：同输入哈希、同目标与认证根、同安全参数选取政策、同固定公共查询包络、同测量边界和进程级统计。数据库维度因布局改变是被测机制本身，不应强行设成相同容量来抹去机制效果；同时必须记录每桶 L/M/p/Ne。

SimplePIR 与 VBPIR 的绝对时间可作为明确配置下的系统观测并列报告，但不能称密码参数相同、等安全成本严格归一化，也不能用一个后端内部的 AB 优势推断另一后端必有优势。两者预处理状态、RLWE/LWE 假设、参数估算和打包路径不同。Flat 是不使用证明着色的重复PIR对照，PBC 是通用批量布局对照；不要把 Flat 写成已实现了官方随机分片优化的最优 batch SimplePIR。

## 可复核文件指纹

本地固定源码 SHA-256（现有文件）：

- `pir/simple_pir.go`: `84D8CB9F016154827A1BBAA578A3DAD2B7188526F91E5F3CA617BD89B8119F15`
- `pir/database.go`: `1622CD3E91621E10D992FBBFDB0F74D7A7A20E137B00B986590A5324CCB18FD8`
- `pir/params.csv`: `B3DB22F70C038F741DACDA0AEC7A531397A32C4BFCA0DF4A98156F37ADF089CA`

未执行新后端，因此“接入正确、真实验根通过、独立进程统计完整”必须由本轮实现和验算产物另外证实。

## 本轮 root 确定的实现配置

主配置为 `native256bits/32B + expanded-A`，每个方法以内按其最大桶容量 U 调 `PickParams(U,256,1024,32)`，各桶使用同样的矩形维度。这里 AB 的 U 与 PBC 的 U 可以不同；Flat 的 U 为唯一完整摘要库大小。以上是统一实施政策，并非要求三种方法的矩阵相同。

expanded-A 方案使用普通 `Init` 即可；初次传输若实际发送展开的 A，必须计其真实矩阵/帧字节，不可同时按 seed 计通信。它是本轮明确配置下的结果，不能用来宣称 SimplePIR 原理上必须传输展开 A（官方已有 seed 压缩）。每库一份 A 属可选实例化；相同维度跨桶是否共享 A 要固定并披露，Flat仍只保留一次。
