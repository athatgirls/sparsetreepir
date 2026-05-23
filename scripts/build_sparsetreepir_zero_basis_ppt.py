from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import build_sparsetreepir_story_deck as base


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "presentations"
PREVIEW_DIR = OUT_DIR / "zero_basis_previews"
PPTX_PATH = OUT_DIR / "sparsetreepir_zero_basis_explainer.pptx"
MONTAGE_PATH = PREVIEW_DIR / "sparsetreepir_zero_basis_explainer_montage.png"


THEME = {
    "ink": "#17202A",
    "muted": "#5F6F7D",
    "paper": "#F7F4ED",
    "paper2": "#FFFDF8",
    "teal": "#0F766E",
    "teal2": "#CDEDE6",
    "orange": "#D97706",
    "orange2": "#F7D8A8",
    "blue": "#2563EB",
    "blue2": "#D9E8FF",
    "red": "#B91C1C",
    "red2": "#F6D6D6",
    "purple": "#7C3AED",
    "purple2": "#E6D7FF",
    "green": "#15803D",
    "green2": "#D9F4DF",
    "line": "#D7D0C4",
    "dark": "#102A2A",
}


def chinese_font_path(kind: str) -> str:
    mapping = {
        "title": [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"],
        "body": [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"],
        "body_bold": [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"],
        "mono": [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"],
    }
    for candidate in mapping.get(kind, mapping["body"]):
        if Path(candidate).exists():
            return candidate
    return base.font_path(kind)


base.font_path = chinese_font_path  # type: ignore[assignment]
base.PPTX_PATH = PPTX_PATH
base.PREVIEW_DIR = PREVIEW_DIR
base.MONTAGE_PATH = MONTAGE_PATH


Element = base.Element
SlideSpec = base.SlideSpec


def txt(
    value: str,
    x: float,
    y: float,
    w: float,
    h: float,
    size: int = 30,
    color: str = THEME["ink"],
    bold: bool = False,
    font: str = "body",
    align: str = "left",
    valign: str = "top",
    name: str = "",
) -> Element:
    return Element("text", x, y, w, h, text=value, font_size=size, color=color, bold=bold, font=font, align=align, valign=valign, name=name)


def box(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    line: str | None = None,
    radius: int = 26,
    name: str = "",
) -> Element:
    return Element("rect", x, y, w, h, fill=fill, line=line or fill, radius=radius, name=name)


def img(path: Path, x: float, y: float, w: float, h: float, fit: str = "contain", name: str = "") -> Element:
    return Element("image", x, y, w, h, path=path, fit=fit, name=name)


def slide_title(title: str, subtitle: str = "") -> List[Element]:
    elements = [
        txt(title, 90, 62, 1250, 82, size=47, bold=True, font="title", name="title"),
        Element("rect", 90, 146, 145, 6, fill=THEME["teal"], line=THEME["teal"], radius=0, name="title-rule"),
    ]
    if subtitle:
        elements.append(txt(subtitle, 90, 165, 1220, 48, size=22, color=THEME["muted"], name="subtitle"))
    return elements


def numbered_steps(items: Sequence[tuple[str, str, str]], x: float, y: float, w: float, gap: float = 118) -> List[Element]:
    elements: List[Element] = []
    for idx, (label, body, color) in enumerate(items, start=1):
        yy = y + (idx - 1) * gap
        elements.extend(
            [
                box(x, yy, 56, 56, color, color, radius=28),
                txt(str(idx), x, yy + 7, 56, 40, size=26, color=THEME["ink"], bold=True, align="center"),
                txt(label, x + 78, yy - 2, w - 78, 32, size=28, bold=True),
                txt(body, x + 78, yy + 36, w - 78, 54, size=21, color=THEME["muted"]),
            ]
        )
    return elements


def color_chip(label: str, x: float, y: float, fill: str, width: float = 190) -> List[Element]:
    return [
        box(x, y, width, 58, fill, fill, radius=20),
        txt(label, x, y + 12, width, 32, size=22, bold=True, align="center"),
    ]


def build_slides(assets: Dict[str, Path]) -> List[SlideSpec]:
    slides: List[SlideSpec] = []

    # 1. Cover.
    slides.append(
        SlideSpec(
            "cover",
            bg=THEME["paper"],
            elements=[
                box(92, 92, 250, 14, THEME["teal"], THEME["teal"], radius=0),
                txt("SparseTreePIR", 92, 162, 1120, 90, size=74, bold=True, font="title"),
                txt("从零讲清楚：SMT 里的 proof 节点如何染色、分库、批量 PIR 查询", 96, 276, 1120, 68, size=29, color=THEME["muted"]),
                txt("核心记忆点", 96, 476, 240, 36, size=25, bold=True, color=THEME["teal"]),
                txt("验证结构仍是高度 h 的完整 SMT；检索结构只放真正需要私密取回的 active proof-bearing nodes。", 96, 526, 980, 96, size=39, bold=True),
                img(assets["workflow"], 1000, 150, 470, 540, fit="contain"),
                txt("active nodes -> served intervals -> colors -> batch PIR -> proof completion", 96, 775, 1030, 34, size=23, color=THEME["muted"]),
            ],
        )
    )

    # 2. Motivation.
    slides.append(
        SlideSpec(
            "motivation",
            bg=THEME["paper2"],
            elements=slide_title("1. 问题从哪里来？", "Merkle proof 本来是验证工具，但直接请求 proof 会暴露目标 leaf。")
            + [
                txt("客户端想验证某个 leaf", 112, 264, 410, 40, size=30, bold=True),
                txt("如果直接向服务器要 proof，服务器马上知道你关心哪个 leaf。", 112, 318, 510, 80, size=27, color=THEME["muted"]),
                box(690, 254, 245, 72, THEME["red2"], THEME["red"], radius=24),
                txt("泄露目标", 690, 273, 245, 35, size=29, bold=True, align="center", color=THEME["red"]),
                txt("PIR 的作用", 1070, 264, 320, 40, size=30, bold=True),
                txt("让客户端取到记录，但服务器不知道它取的是哪条记录。", 1070, 318, 430, 80, size=27, color=THEME["muted"]),
                box(660, 450, 280, 80, THEME["teal2"], THEME["teal"], radius=26),
                txt("proof path", 660, 474, 280, 34, size=28, bold=True, align="center", color=THEME["teal"]),
                Element("rect", 522, 484, 140, 4, fill=THEME["line"], line=THEME["line"], radius=0),
                Element("rect", 940, 484, 128, 4, fill=THEME["line"], line=THEME["line"], radius=0),
                txt("这篇论文研究的是：如何把一条 SMT membership proof 组织成适合 batch PIR 的多个子查询。", 190, 665, 1220, 82, size=38, bold=True, align="center"),
            ],
        )
    )

    # 3. SMT vs ordinary Merkle.
    slides.append(
        SlideSpec(
            "smt",
            bg=THEME["paper"],
            elements=slide_title("2. SMT 和普通 Merkle tree 的关键区别", "SMT 的逻辑空间很大，但真实数据非常少；空子树 hash 是公开可算的。")
            + [
                *numbered_steps(
                    [
                        ("完整验证坐标", "SMT 高度是 h，完整 proof 仍然有 h 层 sibling position。", THEME["blue2"]),
                        ("大量空子树", "绝大多数逻辑 leaf 位置没有真实数据，对应 default hash。", THEME["orange2"]),
                        ("检索可稀疏化", "PIR 不必检索 public default hash，只需检索非空 sibling digest。", THEME["teal2"]),
                    ],
                    100,
                    260,
                    720,
                    gap=145,
                ),
                txt("验证结构", 955, 276, 220, 34, size=28, bold=True, color=THEME["blue"]),
                txt("height h", 1205, 276, 220, 34, size=28, bold=True, color=THEME["blue"]),
                Element("rect", 1000, 342, 420, 6, fill=THEME["blue"], line=THEME["blue"], radius=0),
                txt("检索结构", 955, 450, 220, 34, size=28, bold=True, color=THEME["teal"]),
                txt("active only", 1205, 450, 220, 34, size=28, bold=True, color=THEME["teal"]),
                Element("rect", 1000, 516, 170, 6, fill=THEME["teal"], line=THEME["teal"], radius=0),
                txt("本文的核心不是改变 SMT 验证，而是改变 PIR 面对的数据库形状。", 935, 640, 500, 96, size=34, bold=True),
            ],
        )
    )

    # 4. Not direct TreePIR.
    slides.append(
        SlideSpec(
            "not-treepir",
            bg=THEME["paper2"],
            elements=slide_title("3. 为什么不能直接把 SMT 补齐后跑 TreePIR？", "因为那样 PIR 数据库会继承完整逻辑树的形状。")
            + [
                img(assets["sparsetreepir_resource_comparison"], 105, 236, 680, 460, fit="contain"),
                txt("直接 perfectize 的问题", 860, 244, 520, 40, size=31, bold=True),
                txt("把很多 public default / inactive 位置放进 PIR 数据库。", 860, 298, 560, 70, size=27, color=THEME["muted"]),
                txt("只删除空记录也不够", 860, 430, 520, 40, size=31, bold=True),
                txt("删除记录只是省存储；还缺 compact lookup、dummy query、proof completion 和 balance 接口。", 860, 484, 590, 105, size=27, color=THEME["muted"]),
                txt("SparseTreePIR 的主张：不是修补 TreePIR 的输入，而是重新定义 SMT 下 PIR 应该检索什么。", 150, 765, 1260, 52, size=33, bold=True, align="center"),
            ],
        )
    )

    # 5. Active nodes.
    slides.append(
        SlideSpec(
            "active-node",
            bg=THEME["paper"],
            elements=slide_title("4. 第一个定义：active proof-bearing node", "只有非空且会作为某些 proof sibling 出现的节点，才进入 PIR 数据库。")
            + [
                txt("节点 u 是 active，当且仅当：", 118, 260, 610, 42, size=34, bold=True),
                box(118, 340, 612, 88, THEME["teal2"], THEME["teal"], radius=28),
                txt("cnt(u) > 0", 118, 365, 612, 36, size=31, bold=True, align="center", color=THEME["teal"]),
                box(118, 462, 612, 88, THEME["blue2"], THEME["blue"], radius=28),
                txt("cnt(sib(u)) > 0", 118, 487, 612, 36, size=31, bold=True, align="center", color=THEME["blue"]),
                txt("第一条：u 自己不是空子树。\n第二条：u 的兄弟方向也有真实 leaf，所以 u 会服务兄弟方向 leaf 的 proof。", 118, 600, 680, 110, size=27, color=THEME["muted"]),
                img(assets["full_tree"], 845, 222, 640, 500, fit="contain"),
                txt("服务器私有 PIR 子库只存 active node 的 digest，不存 default hash。", 848, 735, 600, 50, size=26, bold=True, color=THEME["teal"]),
            ],
        )
    )

    # 6. Served interval.
    slides.append(
        SlideSpec(
            "served-interval",
            bg=THEME["paper2"],
            elements=slide_title("5. 第二个定义：served interval", "I_srv(u) 表示 u 作为 sibling 时，服务哪些目标 leaf。")
            + [
                txt("最容易误解的一点", 100, 258, 480, 40, size=34, bold=True, color=THEME["red"]),
                txt("I_srv(u) 不是 u 自己覆盖的区间，而是 u 的兄弟子树覆盖的真实 leaf rank 区间。", 100, 318, 680, 94, size=34, bold=True),
                box(112, 486, 620, 116, THEME["paper"], THEME["line"], radius=30),
                txt("u in Path(ell)  <=>  r(ell) in I_srv(u)", 112, 522, 620, 38, size=29, bold=True, align="center", font="mono", color=THEME["teal"]),
                txt("用 served interval，客户端可以对每个颜色子库做二分查找，判断目标 leaf 是否命中某个真实节点。", 114, 642, 690, 82, size=27, color=THEME["muted"]),
                img(assets["algorithm_leaf_cases"], 888, 242, 500, 420, fit="contain"),
                txt("served intervals 是把树结构变成 PIR 索引接口的桥。", 900, 700, 500, 44, size=28, bold=True, color=THEME["teal"]),
            ],
        )
    )

    # 7. Offline pipeline.
    slides.append(
        SlideSpec(
            "offline",
            bg=THEME["paper"],
            elements=slide_title("6. 离线阶段：从 SMT 到多个 PIR 子数据库", "输入是一棵固定 SMT；输出是颜色子库和公开 metadata。")
            + [
                img(assets["workflow"], 95, 250, 660, 420, fit="contain"),
                *numbered_steps(
                    [
                        ("抽取 active nodes", "遍历压缩的 non-default skeleton，计算 cnt 和 sibling 关系。", THEME["teal2"]),
                        ("计算 served intervals", "每个 active node 得到服务的 real-leaf rank 区间。", THEME["blue2"]),
                        ("构造 interval forest", "区间包含关系形成祖先冲突结构。", THEME["orange2"]),
                        ("染色并分库", "同一路径颜色互异，每个颜色一个 PIR 子库。", THEME["green2"]),
                    ],
                    830,
                    238,
                    610,
                    gap=118,
                ),
                txt("Offline(T, L, R1) -> {D_c}, {M_c}, phi", 250, 760, 1040, 42, size=30, bold=True, align="center", font="mono", color=THEME["dark"]),
            ],
        )
    )

    # 8. Coloring and m.
    slides.append(
        SlideSpec(
            "coloring-m",
            bg=THEME["paper2"],
            elements=slide_title("7. 染色目标：每条 proof path 上颜色不重复", "这样客户端每种颜色最多取一个真实节点。")
            + [
                txt("颜色函数", 112, 260, 210, 36, size=30, bold=True),
                txt("phi: A(T) -> [m]", 112, 318, 520, 45, size=34, bold=True, font="mono", color=THEME["teal"]),
                txt("[m] = {1,2,...,m}，表示 m 个颜色。", 112, 390, 620, 45, size=27, color=THEME["muted"]),
                box(115, 496, 645, 105, THEME["teal2"], THEME["teal"], radius=30),
                txt("m = max over leaves |Path(ell)|", 115, 532, 645, 36, size=28, bold=True, align="center", font="mono", color=THEME["teal"]),
                txt("m 的意义不是“永远显著小于 h”，而是在 active-node one-query-per-color 接口下，精确描述每次 batch 需要多少个颜色子查询。", 112, 646, 680, 106, size=27, color=THEME["muted"]),
                *color_chip("C1", 945, 278, THEME["red2"], 130),
                *color_chip("C2", 1102, 278, THEME["orange2"], 130),
                *color_chip("C3", 1259, 278, THEME["green2"], 130),
                *color_chip("C4", 1026, 370, THEME["blue2"], 130),
                txt("一条 path", 1035, 514, 300, 40, size=31, bold=True, align="center"),
                txt("C1 -> C2 -> C3 -> C4", 930, 585, 520, 44, size=34, bold=True, align="center", font="mono", color=THEME["dark"]),
                txt("同色不重复，所以每个颜色只需要一次 PIR。", 948, 670, 480, 52, size=27, color=THEME["muted"], align="center"),
            ],
        )
    )

    # 9. Profile balanced.
    slides.append(
        SlideSpec(
            "profile",
            bg=THEME["paper"],
            elements=slide_title("8. profile_balanced：在不增加 m 的情况下压低最大子库", "first-fit 只保证合法；profile_balanced 负责让颜色桶更均衡。")
            + [
                img(assets["before_after"], 105, 238, 790, 430, fit="contain"),
                txt("核心操作", 980, 248, 360, 40, size=32, bold=True),
                txt("选一个子树 U，只在 U 内部做颜色置换。", 980, 308, 480, 68, size=29),
                txt("为什么合法？", 980, 434, 360, 40, size=32, bold=True, color=THEME["teal"]),
                txt("颜色置换不改变子树内部“路径异色”结构；同时避开祖先已经用过的颜色。", 980, 494, 480, 95, size=27, color=THEME["muted"]),
                txt("接受条件", 980, 646, 360, 40, size=32, bold=True, color=THEME["orange"]),
                txt("只有当 bucket profile 变好时才接受，因此单调下降并终止。", 980, 704, 480, 74, size=27, color=THEME["muted"]),
            ],
        )
    )

    # 10. Stored data structures.
    slides.append(
        SlideSpec(
            "storage",
            bg=THEME["paper2"],
            elements=slide_title("9. 最终到底存了什么？", "私有数据库只存 digest；公开 metadata 负责定位。")
            + [
                txt("Private PIR subdatabases", 118, 265, 560, 38, size=31, bold=True, color=THEME["teal"]),
                *color_chip("D1: digest, digest, ...", 118, 340, THEME["red2"], 500),
                *color_chip("D2: digest, digest, ...", 118, 425, THEME["orange2"], 500),
                *color_chip("D3: digest, digest, ...", 118, 510, THEME["green2"], 500),
                *color_chip("Dm: digest, digest, ...", 118, 595, THEME["blue2"], 500),
                txt("Public metadata M_c", 855, 265, 520, 38, size=31, bold=True, color=THEME["blue"]),
                box(855, 340, 560, 278, THEME["paper"], THEME["line"], radius=26),
                txt("每条 metadata 记录包含：", 890, 372, 500, 32, size=25, bold=True),
                txt("1. served interval I_srv(u)\n2. proof level delta(u)\n3. 在 D_c 中的 index", 890, 426, 500, 118, size=27, color=THEME["muted"]),
                txt("metadata 是公开的；隐私目标是隐藏客户端这次查询哪个 leaf / 哪个 index。", 860, 665, 550, 72, size=27, bold=True),
            ],
        )
    )

    # 11. Query generation.
    slides.append(
        SlideSpec(
            "query",
            bg=THEME["paper"],
            elements=slide_title("10. 在线查询：每个颜色发一次 PIR", "真实命中发 real query；没有命中也发 dummy query，保持外观一致。")
            + [
                img(assets["completion"], 102, 238, 740, 430, fit="contain"),
                *numbered_steps(
                    [
                        ("输入目标 leaf", "客户端知道目标位置和 real-leaf rank r(ell)。", THEME["blue2"]),
                        ("每个颜色查 metadata", "在 M_c 中二分查找是否有 interval 包含 r(ell)。", THEME["teal2"]),
                        ("生成 PIR 子查询", "命中则查真实 index；未命中则查随机 dummy index。", THEME["orange2"]),
                    ],
                    920,
                    265,
                    560,
                    gap=140,
                ),
                txt("QueryGen(ell, {M_c}) -> Q_1,...,Q_m and local map tau", 230, 755, 1050, 42, size=28, bold=True, align="center", font="mono"),
            ],
        )
    )

    # 12. Proof completion.
    slides.append(
        SlideSpec(
            "completion",
            bg=THEME["paper2"],
            elements=slide_title("11. Proof Completion：真实返回 + default hash 足够恢复完整 proof", "完整 proof 长度仍是 h；PIR 只负责其中非空 sibling。")
            + [
                txt("算法输入", 112, 258, 260, 40, size=31, bold=True, color=THEME["blue"]),
                txt("target leaf digest a0\nPIR 解出的 sigma_c\n本地 tau_c\npublic default hash chain Delta", 112, 315, 560, 150, size=26, color=THEME["muted"]),
                txt("算法输出", 112, 545, 260, 40, size=31, bold=True, color=THEME["teal"]),
                txt("完整 proof 数组 P[0..h-1]\n重建出的 root rho", 112, 602, 560, 78, size=26, color=THEME["muted"]),
                box(780, 248, 560, 96, THEME["blue2"], THEME["blue"], radius=28),
                txt("先用 default hashes 填满 P", 780, 279, 560, 34, size=28, bold=True, align="center", color=THEME["blue"]),
                box(780, 410, 560, 96, THEME["teal2"], THEME["teal"], radius=28),
                txt("再用真实 PIR 返回覆盖对应层", 780, 441, 560, 34, size=28, bold=True, align="center", color=THEME["teal"]),
                box(780, 572, 560, 96, THEME["orange2"], THEME["orange"], radius=28),
                txt("最后逐层 hash 回 root", 780, 603, 560, 34, size=28, bold=True, align="center", color=THEME["orange"]),
                txt("这一步解释了：为什么 dummy 颜色和空 sibling 层不会破坏 proof 正确性。", 270, 775, 1040, 44, size=30, bold=True, align="center"),
            ],
        )
    )

    # 13. Running example.
    slides.append(
        SlideSpec(
            "example",
            bg=THEME["paper"],
            elements=slide_title("12. 一个完整查询例子：leaf 19", "从颜色子库定位，到 batch PIR，再到本地补全 proof。")
            + [
                img(assets["full_tree"], 72, 224, 730, 460, fit="contain"),
                txt("查询 leaf 19 时，客户端做的不是“向服务器说我要 leaf 19 的 proof”。", 850, 250, 600, 82, size=31, bold=True),
                txt("它对每个颜色子库都发一个 PIR 查询：\nC1 可能是 dummy\nC2 可能命中某个 sibling\nC3 可能命中某个 sibling\nC4 可能命中某个 sibling", 852, 374, 600, 168, size=27, color=THEME["muted"]),
                txt("服务器看到的是固定形状的 batch：每个颜色一个查询；PIR 隐藏每个子库内的 index，dummy 隐藏该颜色是否真实命中。", 852, 615, 600, 122, size=28, bold=True, color=THEME["teal"]),
            ],
        )
    )

    # 14. Complexity.
    slides.append(
        SlideSpec(
            "complexity",
            bg=THEME["paper2"],
            elements=slide_title("13. 复杂度应该怎么记？", "预处理由 active 节点数 N 控制；在线查询由 m 和 h 控制。")
            + [
                box(120, 252, 590, 132, THEME["teal2"], THEME["teal"], radius=28),
                txt("Offline setup", 150, 278, 250, 34, size=28, bold=True, color=THEME["teal"]),
                txt("O(N log N) + O(R1 N m^3)", 150, 324, 520, 38, size=28, bold=True, font="mono"),
                box(120, 438, 590, 132, THEME["blue2"], THEME["blue"], radius=28),
                txt("Query indexing", 150, 464, 280, 34, size=28, bold=True, color=THEME["blue"]),
                txt("O(m log N)", 150, 510, 520, 38, size=28, bold=True, font="mono"),
                box(120, 624, 590, 132, THEME["orange2"], THEME["orange"], radius=28),
                txt("Proof completion", 150, 650, 310, 34, size=28, bold=True, color=THEME["orange"]),
                txt("O(h)", 150, 696, 520, 38, size=28, bold=True, font="mono"),
                txt("N = active proof-bearing nodes 数量\nm = 最大 active proof path 长度\nh = SMT 完整高度\nR1 = profile_balanced 轮数", 850, 282, 510, 180, size=28, color=THEME["muted"]),
                txt("重点：PIR 数据库规模不再由完整逻辑树 2^h 直接决定，而由 active retrieval structure 决定。", 830, 610, 560, 100, size=35, bold=True),
            ],
        )
    )

    # 15. Experiments.
    slides.append(
        SlideSpec(
            "experiments",
            bg=THEME["paper"],
            elements=slide_title("14. 实验到底在验证什么？", "实验不是只看一张表，而是验证四条 claim。")
            + [
                *numbered_steps(
                    [
                        ("perfectize TreePIR 的数据库形状不适合 SMT", "完整逻辑树会把大量 public default 位置带入 PIR 成本。", THEME["red2"]),
                        ("active-only 需要完整查询接口", "仅删除记录不够，还需要 served interval、dummy 和 completion。", THEME["orange2"]),
                        ("profile_balanced 改善 exact-width 子库平衡", "目标是压低最大颜色桶 M(phi)，而不是改变 proof 正确性。", THEME["green2"]),
                        ("结构收益能传到 PIR backend", "SimplePIR bridge 观察 communication 和 timing counters。", THEME["blue2"]),
                    ],
                    116,
                    244,
                    620,
                    gap=124,
                ),
                img(assets["simplepir_full_backend_comparison"], 835, 278, 560, 320, fit="contain"),
                img(assets["active_width_threshold_plot"], 890, 620, 460, 190, fit="contain"),
            ],
        )
    )

    # 16. Results.
    slides.append(
        SlideSpec(
            "results",
            bg=THEME["paper2"],
            elements=slide_title("15. 结果该怎么读？", "不要只看“快了多少”，要看是哪一个资源维度变好了。")
            + [
                txt("资源维度", 130, 245, 260, 34, size=30, bold=True, color=THEME["teal"]),
                txt("解释", 680, 245, 260, 34, size=30, bold=True, color=THEME["teal"]),
                Element("rect", 120, 300, 1290, 3, fill=THEME["line"], line=THEME["line"], radius=0),
                txt("N = |A(T)|", 130, 330, 300, 34, size=28, bold=True, font="mono"),
                txt("真实进入 PIR 的 active records 数量。", 680, 330, 650, 34, size=26, color=THEME["muted"]),
                txt("m", 130, 410, 300, 34, size=28, bold=True, font="mono"),
                txt("每次 batch 需要多少个颜色子查询。", 680, 410, 650, 34, size=26, color=THEME["muted"]),
                txt("M(phi)", 130, 490, 300, 34, size=28, bold=True, font="mono"),
                txt("最大颜色子库，决定并行 PIR 的瓶颈。", 680, 490, 650, 34, size=26, color=THEME["muted"]),
                txt("metadata", 130, 570, 300, 34, size=28, bold=True, font="mono"),
                txt("公开索引开销，不进入私有 PIR payload，但要报告。", 680, 570, 650, 34, size=26, color=THEME["muted"]),
                txt("backend counters", 130, 650, 360, 34, size=28, bold=True, font="mono"),
                txt("通信和时间计数，说明结构优化可以转化为实际查询开销变化。", 680, 650, 660, 34, size=26, color=THEME["muted"]),
            ],
        )
    )

    # 17. Contributions and boundaries.
    slides.append(
        SlideSpec(
            "conclusion",
            bg=THEME["dark"],
            elements=[
                txt("最后记住三句话", 92, 90, 900, 70, size=58, bold=True, font="title", color="#FFFFFF"),
                box(100, 238, 1280, 92, THEME["teal2"], THEME["teal"], radius=30),
                txt("1. 我们不是重新发明 PIR，也不是改变 SMT 验证。", 132, 264, 1220, 36, size=31, bold=True, color=THEME["dark"]),
                box(100, 386, 1280, 92, THEME["blue2"], THEME["blue"], radius=30),
                txt("2. 我们重新定义 SMT membership proof 的 PIR-facing organization layer。", 132, 412, 1220, 36, size=31, bold=True, color=THEME["dark"]),
                box(100, 534, 1280, 92, THEME["orange2"], THEME["orange"], radius=30),
                txt("3. 贡献链条是：active nodes -> served intervals -> exact-width coloring -> balanced subdatabases -> batch PIR + proof completion。", 132, 560, 1220, 36, size=29, bold=True, color=THEME["dark"]),
                txt("边界：当前主线是固定公开 SMT snapshot 的 membership proof retrieval；不隐藏整棵树的 occupancy pattern，也不声称提出新的 PIR primitive。", 132, 735, 1200, 58, size=26, color="#D8E7E2"),
            ],
        )
    )

    return slides


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    PREVIEW_DIR.mkdir(exist_ok=True)
    assets = base.prepare_assets()
    assets.update(
        {
            "sparsetreepir_resource_comparison": ROOT / "figures" / "sparsetreepir_resource_comparison_figure.png",
            "simplepir_full_backend_comparison": ROOT / "figures" / "simplepir_full_backend_comparison.png",
            "active_width_threshold_plot": ROOT / "figures" / "active_width_threshold_plot.png",
        }
    )
    slides = build_slides(assets)
    base.write_pptx(slides, PPTX_PATH)
    base.write_previews(slides)
    print(f"Wrote {PPTX_PATH}")
    print(f"Wrote previews to {PREVIEW_DIR}")
    print(f"Wrote montage {MONTAGE_PATH}")
    print(f"Slides: {len(slides)}")


if __name__ == "__main__":
    main()
