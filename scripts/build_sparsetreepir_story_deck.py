from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "presentations"
ASSET_DIR = OUT_DIR / "assets"
PREVIEW_DIR = OUT_DIR / "previews"
PPTX_PATH = OUT_DIR / "sparsetreepir_story_deck.pptx"
MONTAGE_PATH = PREVIEW_DIR / "sparsetreepir_story_deck_montage.png"

SLIDE_W_PX = 1600
SLIDE_H_PX = 900
SLIDE_CX = 12192000
SLIDE_CY = 6858000

EMU_PER_PX_X = SLIDE_CX / SLIDE_W_PX
EMU_PER_PX_Y = SLIDE_CY / SLIDE_H_PX

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"


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


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.strip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def strip_hash(value: str) -> str:
    return value.strip("#").upper()


def emu_x(px: float) -> int:
    return int(round(px * EMU_PER_PX_X))


def emu_y(px: float) -> int:
    return int(round(px * EMU_PER_PX_Y))


def text_escape(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def font_path(name: str) -> str:
    candidates = {
        "title": [
            r"C:\Windows\Fonts\georgiab.ttf",
            r"C:\Windows\Fonts\Georgia.ttf",
            r"C:\Windows\Fonts\cambriab.ttf",
        ],
        "body": [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ],
        "body_bold": [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\calibrib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ],
        "mono": [
            r"C:\Windows\Fonts\consola.ttf",
            r"C:\Windows\Fonts\cour.ttf",
        ],
    }
    for path in candidates[name]:
        if Path(path).exists():
            return path
    return candidates["body"][0]


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_path(kind), size)
    except OSError:
        return ImageFont.load_default()


@dataclass
class Element:
    kind: str
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    fill: Optional[str] = None
    line: Optional[str] = None
    radius: int = 0
    font_size: int = 28
    color: str = "#17202A"
    bold: bool = False
    font: str = "body"
    align: str = "left"
    valign: str = "top"
    path: Optional[Path] = None
    fit: str = "contain"
    opacity: float = 1.0
    name: str = ""


@dataclass
class SlideSpec:
    title: str
    subtitle: str = ""
    bg: str = THEME["paper"]
    elements: List[Element] = field(default_factory=list)


def prepare_assets() -> Dict[str, Path]:
    OUT_DIR.mkdir(exist_ok=True)
    ASSET_DIR.mkdir(exist_ok=True)
    PREVIEW_DIR.mkdir(exist_ok=True)

    pdfs = {
        "workflow": ROOT / "figures" / "sparsetreepir_workflow_figure.pdf",
        "full_tree": ROOT / "figures" / "sparsetreepir_running_example_figure.pdf",
        "before_after": ROOT / "figures" / "sparsetreepir_profile_balanced_before_after_figure.pdf",
        "completion": ROOT / "figures" / "sparsetreepir_proof_completion_figure.pdf",
        "backend": ROOT / "figures" / "backend_results_bars.pdf",
        "sparsity": ROOT / "figures" / "sparsity_sensitivity_plot.pdf",
    }
    assets: Dict[str, Path] = {}
    for key, pdf in pdfs.items():
        output_base = ASSET_DIR / key
        png = ASSET_DIR / f"{key}.png"
        if not png.exists() or png.stat().st_mtime < pdf.stat().st_mtime:
            subprocess.run(
                [
                    "pdftoppm",
                    "-r",
                    "220",
                    "-png",
                    "-singlefile",
                    str(pdf),
                    str(output_base),
                ],
                check=True,
            )
        assets[key] = png
    assets.update(create_algorithm_assets())
    return assets


def create_algorithm_assets() -> Dict[str, Path]:
    specs = {
        "algorithm_step1": "full",
        "algorithm_step2": "active",
        "algorithm_step3": "forest",
        "algorithm_step4": "colored",
        "algorithm_leaf_cases": "leaf_cases",
    }
    assets: Dict[str, Path] = {}
    for name, mode in specs.items():
        path = ASSET_DIR / f"{name}.png"
        draw_algorithm_asset(path, mode)
        assets[name] = path
    return assets


def draw_node(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    fill: str,
    outline: str,
    font: ImageFont.FreeTypeFont,
    radius: int = 24,
    text_color: str = THEME["ink"],
    width: int = 3,
) -> None:
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=hex_to_rgb(fill), outline=hex_to_rgb(outline), width=width)
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text((x - (bbox[2] - bbox[0]) / 2, y - (bbox[3] - bbox[1]) / 2 - 2), label, font=font, fill=hex_to_rgb(text_color))


def draw_small_tree(draw: ImageDraw.ImageDraw, mode: str, origin_x: int, origin_y: int) -> None:
    node_font = load_font("body_bold", 18)
    small_font = load_font("body", 15)
    active_nodes = {2, 3, 4, 5, 8, 9, 16, 17}
    occupied = {16, 17, 19, 22, 28}
    target_path_nodes = {1, 2, 5, 11, 22}
    coords: Dict[int, Tuple[int, int]] = {}
    for depth in range(0, 5):
        count = 1 << depth
        span = 760
        for offset in range(count):
            heap = (1 << depth) + offset
            x = origin_x + int((offset + 0.5) * span / count)
            y = origin_y + depth * 102
            coords[heap] = (x, y)
    for heap in range(1, 16):
        x, y = coords[heap]
        for child in [heap * 2, heap * 2 + 1]:
            cx, cy = coords[child]
            line_color = "#A7A29A"
            line_width = 2
            if mode == "active" and (heap in target_path_nodes or child in target_path_nodes):
                line_color = THEME["orange"]
                line_width = 4
            draw.line([x, y + 22, cx, cy - 22], fill=hex_to_rgb(line_color), width=line_width)
    for heap in range(1, 32):
        x, y = coords[heap]
        if mode == "active" and heap in active_nodes:
            fill, outline, text_color, width = "#FFF2D8", THEME["orange"], THEME["ink"], 4
        elif mode == "full" and heap in occupied:
            fill, outline, text_color, width = "#FFFFFF", THEME["ink"], THEME["ink"], 4
        elif heap >= 16 and heap not in occupied:
            fill, outline, text_color, width = "#D7D7D7", "#B5B5B5", "#777777", 2
        elif heap in target_path_nodes and mode == "full":
            fill, outline, text_color, width = THEME["teal2"], THEME["teal"], THEME["teal"], 4
        else:
            fill, outline, text_color, width = "#F8F6F0", "#A7A29A", THEME["ink"], 2
        if heap in active_nodes and mode == "active":
            label = str(heap)
        elif heap in occupied or heap < 16:
            label = str(heap)
        else:
            label = ""
        draw_node(draw, x, y, label, fill, outline, node_font, radius=22 if heap < 16 else 18, text_color=text_color, width=width)
    draw.text((origin_x + 18, origin_y + 458), "occupied leaves: {16, 17, 19, 22, 28}", font=small_font, fill=hex_to_rgb(THEME["muted"]))
    if mode == "active":
        draw.text((origin_x + 18, origin_y + 486), "orange = proof-bearing nodes stored in color subdatabases", font=small_font, fill=hex_to_rgb(THEME["orange"]))


def draw_forest_asset(draw: ImageDraw.ImageDraw, colored: bool = False, y_offset: int = 0) -> None:
    font = load_font("body_bold", 23)
    small = load_font("body", 18)
    edge = "#A7A29A"
    positions = {
        3: (360, 120 + y_offset),
        2: (920, 120 + y_offset),
        5: (260, 245 + y_offset),
        4: (470, 245 + y_offset),
        9: (205, 370 + y_offset),
        8: (355, 370 + y_offset),
        17: (150, 500 + y_offset),
        16: (260, 500 + y_offset),
    }
    edges = [(3, 5), (3, 4), (5, 9), (5, 8), (9, 17), (9, 16)]
    colors = {
        3: (THEME["red2"], THEME["red"], "C1"),
        2: (THEME["red2"], THEME["red"], "C1"),
        5: (THEME["orange2"], THEME["orange"], "C2"),
        4: (THEME["orange2"], THEME["orange"], "C2"),
        9: (THEME["green2"], THEME["green"], "C3"),
        8: (THEME["green2"], THEME["green"], "C3"),
        17: (THEME["blue2"], THEME["blue"], "C4"),
        16: (THEME["blue2"], THEME["blue"], "C4"),
    }
    intervals = {
        3: "{16,17,19,22}",
        2: "{28}",
        5: "{16,17,19}",
        4: "{22}",
        9: "{16,17}",
        8: "{19}",
        17: "{16}",
        16: "{17}",
    }
    for a, b in edges:
        ax, ay = positions[a]
        bx, by = positions[b]
        draw.line([ax, ay + 30, bx, by - 30], fill=hex_to_rgb(edge), width=4)
    for node, (x, y) in positions.items():
        if colored:
            fill, outline, cname = colors[node]
        else:
            fill, outline, cname = "#FFFFFF", THEME["teal"], ""
        draw_node(draw, x, y, str(node), fill, outline, font, radius=34, text_color=THEME["ink"], width=4)
        draw.text((x - 68, y + 42), f"I={intervals[node]}", font=small, fill=hex_to_rgb(THEME["muted"]))
        if cname:
            draw.text((x + 42, y - 34), cname, font=small, fill=hex_to_rgb(outline))
    if colored:
        bucket_x = 1110
        bucket_y = 135 + y_offset
        buckets = [
            ("C1", "3, 2", THEME["red2"], THEME["red"]),
            ("C2", "5, 4", THEME["orange2"], THEME["orange"]),
            ("C3", "9, 8", THEME["green2"], THEME["green"]),
            ("C4", "17, 16", THEME["blue2"], THEME["blue"]),
        ]
        for idx, (name, nodes, fill, line) in enumerate(buckets):
            y = bucket_y + idx * 105
            draw.rounded_rectangle([bucket_x, y, bucket_x + 265, y + 72], radius=18, fill=hex_to_rgb(fill), outline=hex_to_rgb(line), width=3)
            draw.text((bucket_x + 20, y + 15), name, font=font, fill=hex_to_rgb(line))
            draw.text((bucket_x + 92, y + 20), nodes, font=small, fill=hex_to_rgb(THEME["ink"]))


def draw_leaf_cases_asset(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1400, 620), hex_to_rgb("#FFFDF8"))
    draw = ImageDraw.Draw(canvas)
    title_font = load_font("title", 34)
    body_font = load_font("body", 21)
    body_bold = load_font("body_bold", 21)
    small = load_font("body", 17)
    tiny = load_font("body", 15)

    draw.text((48, 36), "Concrete leaf queries: 19, 22, and 28", font=title_font, fill=hex_to_rgb(THEME["ink"]))
    draw.text(
        (52, 88),
        "The client queries every color. Real hits come from interval metadata; missing proof levels are completed by default hashes.",
        font=body_font,
        fill=hex_to_rgb(THEME["muted"]),
    )

    # Left: compact colored subdatabase reminder.
    draw.rounded_rectangle([62, 150, 382, 548], radius=28, fill=hex_to_rgb("#F8FBFA"), outline=hex_to_rgb(THEME["line"]), width=2)
    draw.text((92, 176), "Colored subdatabases", font=body_bold, fill=hex_to_rgb(THEME["ink"]))
    buckets = [
        ("C1", "nodes 3, 2", THEME["red2"], THEME["red"]),
        ("C2", "nodes 5, 4", THEME["orange2"], THEME["orange"]),
        ("C3", "nodes 9, 8", THEME["green2"], THEME["green"]),
        ("C4", "nodes 17, 16", THEME["blue2"], THEME["blue"]),
    ]
    for i, (name, nodes, fill, line) in enumerate(buckets):
        y = 230 + i * 72
        draw.rounded_rectangle([92, y, 350, y + 52], radius=16, fill=hex_to_rgb(fill), outline=hex_to_rgb(line), width=2)
        draw.text((112, y + 13), name, font=body_bold, fill=hex_to_rgb(line))
        draw.text((176, y + 15), nodes, font=small, fill=hex_to_rgb(THEME["ink"]))

    # Right: three target leaves and their real/dummy behavior.
    examples = [
        {
            "leaf": "19",
            "hits": [("C1", "3"), ("C2", "5"), ("C3", "8"), ("C4", "dummy")],
            "proof": ["d0", "node 8", "node 5", "node 3"],
            "note": "leaf sibling 18 is empty",
        },
        {
            "leaf": "22",
            "hits": [("C1", "3"), ("C2", "4"), ("C3", "dummy"), ("C4", "dummy")],
            "proof": ["d0", "d1", "node 4", "node 3"],
            "note": "siblings 23 and 10 are empty",
        },
        {
            "leaf": "28",
            "hits": [("C1", "2"), ("C2", "dummy"), ("C3", "dummy"), ("C4", "dummy")],
            "proof": ["d0", "d1", "d2", "node 2"],
            "note": "only the top sibling subtree is real",
        },
    ]
    color_lookup = {
        "C1": (THEME["red2"], THEME["red"]),
        "C2": (THEME["orange2"], THEME["orange"]),
        "C3": (THEME["green2"], THEME["green"]),
        "C4": (THEME["blue2"], THEME["blue"]),
    }
    start_x = 430
    card_w = 292
    gap = 36
    for idx, ex in enumerate(examples):
        x = start_x + idx * (card_w + gap)
        draw.rounded_rectangle([x, 150, x + card_w, 548], radius=28, fill=hex_to_rgb("#FFFFFF"), outline=hex_to_rgb(THEME["line"]), width=2)
        draw.text((x + 24, 176), f"target leaf {ex['leaf']}", font=body_bold, fill=hex_to_rgb(THEME["ink"]))
        draw.text((x + 24, 210), ex["note"], font=small, fill=hex_to_rgb(THEME["muted"]))

        y = 252
        for cname, value in ex["hits"]:
            fill, line = color_lookup[cname]
            draw.rounded_rectangle([x + 24, y, x + 108, y + 36], radius=13, fill=hex_to_rgb(fill), outline=hex_to_rgb(line), width=2)
            draw.text((x + 45, y + 8), cname, font=tiny, fill=hex_to_rgb(line))
            if value == "dummy":
                draw.text((x + 126, y + 7), "dummy PIR", font=small, fill=hex_to_rgb(THEME["muted"]))
            else:
                draw.text((x + 126, y + 7), f"real node {value}", font=small, fill=hex_to_rgb(THEME["ink"]))
            y += 48

        draw.line([x + 28, 454, x + card_w - 28, 454], fill=hex_to_rgb(THEME["line"]), width=2)
        draw.text((x + 24, 470), "completed height-4 proof", font=tiny, fill=hex_to_rgb(THEME["muted"]))
        proof_text = " + ".join(ex["proof"])
        draw.text((x + 24, 500), proof_text, font=small, fill=hex_to_rgb(THEME["teal"]))

    draw.text(
        (126, 580),
        "d0, d1, d2 are public default-empty hashes. They are not stored in any subdatabase, but they still appear in the completed Merkle proof.",
        font=small,
        fill=hex_to_rgb(THEME["muted"]),
    )
    canvas.save(path)


def draw_algorithm_asset(path: Path, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "leaf_cases":
        draw_leaf_cases_asset(path)
        return
    canvas = Image.new("RGB", (1400, 620), hex_to_rgb("#FFFDF8"))
    draw = ImageDraw.Draw(canvas)
    title_font = load_font("title", 34)
    body_font = load_font("body", 22)
    if mode == "full":
        draw.text((48, 38), "Step 1  Start from the full binary SMT", font=title_font, fill=hex_to_rgb(THEME["ink"]))
        draw.text((52, 92), "No compression is applied; the verifier still expects a height-h proof.", font=body_font, fill=hex_to_rgb(THEME["muted"]))
        draw_small_tree(draw, "full", 330, 140)
    elif mode == "active":
        draw.text((48, 38), "Step 2  Extract active proof-bearing nodes", font=title_font, fill=hex_to_rgb(THEME["ink"]))
        draw.text((52, 92), "A node is active if it appears as a sibling digest in some real membership proof.", font=body_font, fill=hex_to_rgb(THEME["muted"]))
        draw_small_tree(draw, "active", 330, 140)
    elif mode == "forest":
        draw.text((48, 38), "Step 3  Build the interval forest", font=title_font, fill=hex_to_rgb(THEME["ink"]))
        draw.text((52, 92), "Each active node serves a leaf interval; interval containment gives the coloring constraints.", font=body_font, fill=hex_to_rgb(THEME["muted"]))
        draw_forest_asset(draw, colored=False, y_offset=44)
    elif mode == "colored":
        draw.text((48, 38), "Step 4  Color the forest and write subdatabases", font=title_font, fill=hex_to_rgb(THEME["ink"]))
        draw.text((52, 92), "Same-path nodes receive distinct colors; each color becomes one PIR subdatabase.", font=body_font, fill=hex_to_rgb(THEME["muted"]))
        draw_forest_asset(draw, colored=True, y_offset=44)
    canvas.save(path)


def t(
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    size: int = 28,
    color: str = THEME["ink"],
    bold: bool = False,
    font: str = "body",
    align: str = "left",
    valign: str = "top",
    name: str = "",
) -> Element:
    return Element("text", x, y, w, h, text=text, font_size=size, color=color, bold=bold, font=font, align=align, valign=valign, name=name)


def r(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    line: Optional[str] = None,
    radius: int = 0,
    name: str = "",
) -> Element:
    return Element("rect", x, y, w, h, fill=fill, line=line, radius=radius, name=name)


def img(path: Path, x: float, y: float, w: float, h: float, fit: str = "contain", name: str = "") -> Element:
    return Element("image", x, y, w, h, path=path, fit=fit, name=name)


def slide_title(slide: SlideSpec, title: str, subtitle: str = "") -> None:
    slide.elements.append(t(title, 84, 52, 1180, 100, size=40, bold=True, font="title"))
    if subtitle:
        slide.elements.append(t(subtitle, 86, 150, 1180, 44, size=20, color=THEME["muted"]))
    slide.elements.append(r(84, 200, 210, 5, THEME["teal"]))


def build_slides(assets: Dict[str, Path]) -> List[SlideSpec]:
    slides: List[SlideSpec] = []

    s = SlideSpec("cover", bg="#F6F0E7")
    s.elements += [
        r(0, 0, 1600, 900, "#F6F0E7"),
        r(1080, -120, 620, 1120, "#0F766E"),
        r(1160, 72, 290, 38, "#F7D8A8", radius=18),
        t("Sparse Merkle Proofs", 1186, 80, 250, 24, size=18, color="#6B3F00", bold=True, align="center"),
        t("Direct Sparse TreePIR", 86, 130, 910, 150, size=64, color=THEME["ink"], bold=True, font="title"),
        t("PIR-compatible organization for fixed Sparse Merkle Trees", 90, 296, 760, 78, size=30, color=THEME["teal"], bold=True),
        t("A clear story: keep TreePIR's one-query-per-color idea, but store only active proof-bearing nodes and complete empty levels publicly.", 92, 410, 780, 124, size=27, color=THEME["muted"]),
        r(90, 642, 240, 6, THEME["orange"]),
        t("Research deck", 92, 674, 290, 40, size=22, color=THEME["ink"], bold=True),
        t("Problem -> organization layer -> coloring -> query completion -> evidence", 92, 716, 760, 40, size=20, color=THEME["muted"]),
        t("active nodes only", 1198, 230, 240, 46, size=24, color="#FFFFFF", bold=True, align="center"),
        t("interval metadata", 1198, 342, 240, 46, size=24, color="#FFFFFF", bold=True, align="center"),
        t("batch PIR", 1198, 454, 240, 46, size=24, color="#FFFFFF", bold=True, align="center"),
        t("proof completion", 1198, 566, 240, 46, size=24, color="#FFFFFF", bold=True, align="center"),
    ]
    for yy in [220, 332, 444, 556]:
        s.elements.append(r(1150, yy, 36, 36, "#F7D8A8", radius=18))
    slides.append(s)

    s = SlideSpec("story")
    slide_title(s, "The problem is not just PIR. It is proof organization.", "A Merkle proof is small for one leaf, but all possible proof nodes form the database seen by PIR.")
    s.elements += [
        t("Direct request", 120, 270, 260, 42, size=28, bold=True),
        t("The server learns which leaf the client verifies.", 120, 322, 290, 88, size=22, color=THEME["muted"]),
        t("TreePIR answer", 542, 270, 260, 42, size=28, bold=True),
        t("Color a proof path; send one PIR query per color.", 542, 322, 300, 88, size=22, color=THEME["muted"]),
        t("Sparse SMT mismatch", 968, 270, 330, 42, size=28, bold=True),
        t("The proof has height h, but many sibling digests are public defaults.", 968, 322, 360, 112, size=22, color=THEME["muted"]),
        r(140, 530, 230, 92, THEME["red2"], radius=24),
        t("leakage", 184, 560, 140, 32, size=26, color=THEME["red"], bold=True, align="center"),
        r(548, 530, 250, 92, THEME["blue2"], radius=24),
        t("batch PIR", 592, 560, 160, 32, size=26, color=THEME["blue"], bold=True, align="center"),
        r(985, 530, 300, 92, THEME["teal2"], radius=24),
        t("active + default", 1020, 560, 230, 32, size=26, color=THEME["teal"], bold=True, align="center"),
        t("The paper asks: what should be placed into the PIR subdatabases for a fixed sparse SMT?", 260, 740, 1080, 52, size=31, color=THEME["ink"], bold=True, align="center"),
    ]
    slides.append(s)

    s = SlideSpec("not pruning", bg="#FFFDF8")
    slide_title(s, "Why this is not just pruning TreePIR", "Deleting empty nodes is not yet a retrieval protocol.")
    xs = [118, 468, 818, 1168]
    heads = ["What is colored?", "How to index?", "How to hide gaps?", "How to verify?"]
    desc = [
        "Only active proof-bearing nodes, not every perfect-tree position.",
        "Sibling-leaf intervals replace perfect-tree position indexing.",
        "Every color sends a query; missing real nodes become dummy PIR queries.",
        "Default-empty hashes fill the untouched levels of the height-h proof.",
    ]
    colors = [THEME["teal2"], THEME["blue2"], THEME["orange2"], THEME["purple2"]]
    inks = [THEME["teal"], THEME["blue"], THEME["orange"], THEME["purple"]]
    for i, x in enumerate(xs):
        s.elements += [
            r(x, 270, 250, 260, colors[i], radius=28),
            t(str(i + 1), x + 24, 292, 44, 44, size=30, color=inks[i], bold=True, align="center"),
            t(heads[i], x + 34, 360, 190, 42, size=25, bold=True, color=THEME["ink"]),
            t(desc[i], x + 34, 425, 188, 82, size=20, color=THEME["muted"]),
        ]
    s.elements += [
        r(210, 656, 1180, 6, THEME["line"]),
        t("Our contribution is an organization layer: active-node extraction + interval metadata + exact-width coloring + dummy-filled batch query + public proof completion.", 214, 698, 1160, 78, size=27, color=THEME["ink"], bold=True, align="center"),
    ]
    slides.append(s)

    s = SlideSpec("example")
    slide_title(s, "Core object: active proof-bearing nodes", "The full SMT remains intact; only real proof material enters color subdatabases.")
    s.elements += [
        img(assets["full_tree"], 82, 210, 1430, 520, fit="contain", name="full tree example"),
        t("Colored nodes are stored privately. Gray/default structure is reconstructed publicly.", 146, 770, 1320, 40, size=23, color=THEME["muted"], align="center"),
    ]
    slides.append(s)

    algorithm_steps = [
        (
            "Algorithm walkthrough 1/4",
            "Start from the complete binary SMT, not a compressed tree.",
            "algorithm_step1",
            "We keep the original SMT semantics: the verifier still receives a height-h proof.",
        ),
        (
            "Algorithm walkthrough 2/4",
            "Extract only nodes that can appear in at least one real proof.",
            "algorithm_step2",
            "This is the first real saving: default-only structure is not placed in PIR subdatabases.",
        ),
        (
            "Algorithm walkthrough 3/4",
            "Turn active nodes into an interval forest.",
            "algorithm_step3",
            "Intervals tell the client which node serves which target leaves; containment gives the coloring constraints.",
        ),
        (
            "Algorithm walkthrough 4/4",
            "Color the forest and materialize the subdatabases.",
            "algorithm_step4",
            "After coloring, each proof path hits at most one node per color, so one batch query covers the proof.",
        ),
    ]
    for title, subtitle, asset_key, takeaway in algorithm_steps:
        s = SlideSpec(asset_key, bg="#FFFDF8")
        slide_title(s, title, subtitle)
        s.elements += [
            img(assets[asset_key], 100, 225, 1400, 500, fit="contain", name=asset_key),
            t(takeaway, 165, 770, 1260, 52, size=25, color=THEME["teal"], bold=True, align="center"),
        ]
        slides.append(s)

    s = SlideSpec("leaf_cases", bg="#FFFDF8")
    slide_title(
        s,
        "Running example: leaves 19, 22, and 28",
        "These leaves are not all stored as proof nodes; each target leaf induces a different real-vs-dummy color pattern.",
    )
    s.elements += [
        img(assets["algorithm_leaf_cases"], 100, 224, 1400, 500, fit="contain", name="leaf query cases"),
        t(
            "This slide is the missing bridge: color subdatabases store reusable sibling nodes; the client expands each target leaf's full proof with public default hashes.",
            150,
            770,
            1300,
            54,
            size=24,
            color=THEME["teal"],
            bold=True,
            align="center",
        ),
    ]
    slides.append(s)

    s = SlideSpec("pipeline", bg="#F8FBFA")
    slide_title(s, "Offline pipeline: from sparse tree to PIR subdatabases", "One fixed SMT snapshot is transformed into an exact-width, interval-indexed organization.")
    s.elements += [
        img(assets["workflow"], 95, 242, 1410, 330, fit="contain"),
        t("Offline", 118, 654, 180, 34, size=26, color=THEME["teal"], bold=True),
        t("Extract active nodes, build the interval forest, color the forest, and store one subdatabase per color.", 118, 698, 580, 66, size=22, color=THEME["muted"]),
        t("Online", 852, 654, 180, 34, size=26, color=THEME["orange"], bold=True),
        t("Use public interval metadata to find at most one real target per color, then issue a fixed-shape batch PIR request.", 852, 698, 600, 66, size=22, color=THEME["muted"]),
    ]
    slides.append(s)

    s = SlideSpec("m")
    slide_title(s, "Exact active width: m is the private batch width", "The full proof length is h, but only active proof positions need private retrieval.")
    s.elements += [
        t("m = max active proof length", 118, 250, 520, 54, size=38, color=THEME["teal"], bold=True, font="title"),
        t("Minimum number of colors = m", 118, 332, 500, 42, size=29, color=THEME["ink"], bold=True),
        t("Reason: one leaf path of length m forces m distinct colors; depth coloring of the interval forest reaches that bound.", 118, 396, 560, 122, size=25, color=THEME["muted"]),
        r(780, 238, 560, 82, THEME["teal2"], radius=28),
        t("same color intervals are disjoint", 820, 260, 480, 34, size=25, color=THEME["teal"], bold=True, align="center"),
        r(780, 382, 560, 82, THEME["blue2"], radius=28),
        t("one real item per color", 820, 404, 480, 34, size=25, color=THEME["blue"], bold=True, align="center"),
        r(780, 526, 560, 82, THEME["orange2"], radius=28),
        t("dummy fills missing colors", 820, 548, 480, 34, size=25, color=THEME["orange"], bold=True, align="center"),
        t("h stays the verifier's proof height; m is the private retrieval width.", 286, 730, 1020, 48, size=32, color=THEME["ink"], bold=True, align="center"),
    ]
    slides.append(s)

    s = SlideSpec("complexity", bg="#FFFDF8")
    slide_title(s, "Complexity: what is paid offline and online?", "The organization layer is preprocessed once; each proof query then uses interval lookup, batch PIR, and proof completion.")
    s.elements += [
        t("Symbols", 118, 250, 180, 38, size=31, color=THEME["ink"], bold=True),
        r(118, 314, 250, 72, THEME["teal2"], radius=22),
        t("N", 148, 330, 46, 32, size=28, color=THEME["teal"], bold=True),
        t("active proof nodes", 202, 333, 138, 28, size=20, color=THEME["muted"]),
        r(118, 410, 250, 72, THEME["blue2"], radius=22),
        t("m", 148, 426, 46, 32, size=28, color=THEME["blue"], bold=True),
        t("colors / PIR width", 202, 429, 142, 28, size=20, color=THEME["muted"]),
        r(118, 506, 250, 72, THEME["orange2"], radius=22),
        t("h", 148, 522, 46, 32, size=28, color=THEME["orange"], bold=True),
        t("full proof height", 202, 525, 136, 28, size=20, color=THEME["muted"]),
        r(118, 602, 250, 72, THEME["purple2"], radius=22),
        t("R", 148, 618, 46, 32, size=28, color=THEME["purple"], bold=True),
        t("profile passes", 202, 621, 122, 28, size=20, color=THEME["muted"]),

        t("Offline preprocessing", 472, 250, 420, 38, size=31, color=THEME["teal"], bold=True),
        r(468, 318, 452, 86, "#F8FBFA", line=THEME["line"], radius=24),
        t("Build active intervals", 496, 336, 330, 28, size=21, color=THEME["ink"], bold=True),
        t("O(N log N) time | O(N) space", 496, 374, 360, 26, size=18, color=THEME["muted"]),
        r(468, 432, 452, 86, "#F8FBFA", line=THEME["line"], radius=24),
        t("Initial exact-width coloring", 496, 450, 340, 28, size=21, color=THEME["ink"], bold=True),
        t("O(N) after forest construction", 496, 488, 360, 26, size=18, color=THEME["muted"]),
        r(468, 546, 452, 104, "#F8FBFA", line=THEME["line"], radius=24),
        t("Profile refinement", 496, 564, 300, 28, size=21, color=THEME["ink"], bold=True),
        t("O(R N m^3) time | O(Nm) space", 496, 602, 368, 26, size=18, color=THEME["muted"]),
        t("offline only; flattens color buckets", 496, 626, 330, 24, size=17, color=THEME["muted"]),

        t("Online per proof", 1008, 250, 360, 38, size=31, color=THEME["orange"], bold=True),
        r(1000, 318, 438, 86, "#FFF9EF", line=THEME["line"], radius=24),
        t("Interval lookup", 1028, 336, 300, 28, size=21, color=THEME["ink"], bold=True),
        t("O(m log N) over color tables", 1028, 374, 340, 26, size=18, color=THEME["muted"]),
        r(1000, 432, 438, 86, "#FFF9EF", line=THEME["line"], radius=24),
        t("Batch PIR request", 1028, 448, 300, 28, size=22, color=THEME["ink"], bold=True),
        t("m subqueries; cost depends on max bucket", 1028, 486, 360, 26, size=18, color=THEME["muted"]),
        r(1000, 546, 438, 104, "#FFF9EF", line=THEME["line"], radius=24),
        t("Proof completion", 1028, 562, 300, 28, size=22, color=THEME["ink"], bold=True),
        t("O(h) time | O(h) space", 1028, 600, 320, 26, size=18, color=THEME["muted"]),
        t("fills missing levels with default hashes", 1028, 626, 350, 24, size=17, color=THEME["muted"]),

        r(284, 724, 1032, 74, THEME["teal2"], radius=28),
        t("Client-side online work excluding PIR crypto:  O(m log N + h)", 310, 748, 980, 32, size=25, color=THEME["teal"], bold=True, align="center"),
    ]
    slides.append(s)

    s = SlideSpec("profile")
    slide_title(s, "Balancing is the algorithmic bottleneck after width is fixed", "Node-local recoloring is legal, but can leave one color subdatabase much larger than the rest.")
    s.elements += [
        img(assets["before_after"], 120, 225, 1350, 460, fit="contain"),
        t("Profile-Balanced permutes colors inside legal subtrees. It preserves m and validity, but flattens the global bucket profile.", 160, 742, 1280, 54, size=27, color=THEME["ink"], bold=True, align="center"),
    ]
    slides.append(s)

    s = SlideSpec("query")
    slide_title(s, "Online query: real responses plus default hashes complete the proof", "The client always sends the same number of color queries; sparse variability is hidden as real vs dummy targets.")
    s.elements += [
        img(assets["completion"], 100, 218, 1400, 470, fit="contain"),
        t("For each color: interval search -> real PIR target or dummy target.", 130, 744, 620, 40, size=24, color=THEME["muted"]),
        t("For each proof level: real response if active, otherwise public default hash.", 820, 744, 640, 40, size=24, color=THEME["muted"]),
    ]
    slides.append(s)

    s = SlideSpec("guarantees", bg="#102A2A")
    s.elements += [
        t("What the proofs give us", 88, 68, 820, 70, size=48, color="#FFFFFF", bold=True, font="title"),
        t("The paper is not a new PIR primitive. It proves that the sparse-SMT organization composes cleanly with a private single-item PIR backend.", 90, 150, 1080, 62, size=24, color="#CDEDE6"),
    ]
    ys = [290, 420, 550, 680]
    heads = ["Uniqueness", "Completeness", "Query privacy", "Complexity"]
    desc = [
        "A valid coloring gives at most one real node per color on any proof path.",
        "Returned real nodes plus public default hashes reconstruct the height-h SMT proof.",
        "Relative to public metadata, real and dummy PIR queries are indistinguishable.",
        "Preprocessing is near-linear plus sorting; each query does m interval lookups.",
    ]
    for i, y in enumerate(ys):
        s.elements += [
            r(120, y, 50, 50, "#F7D8A8", radius=25),
            t(str(i + 1), 136, y + 9, 18, 24, size=22, color="#6B3F00", bold=True, align="center"),
            t(heads[i], 210, y, 250, 34, size=28, color="#FFFFFF", bold=True),
            t(desc[i], 470, y + 2, 850, 42, size=23, color="#CDEDE6"),
        ]
    slides.append(s)

    s = SlideSpec("structural")
    slide_title(s, "Main structural result: the buckets become nearly flat", "Height-10 sparse SMTs, sparsity 0.5-0.98, exact width for every scheme.")
    # Custom editable-looking bars.
    base_x = 170
    base_y = 680
    scale = 3.8
    vals = [50.59, 78.62, 47.49, 37.41]
    names = ["weighted", "count", "hybrid", "profile"]
    fills = [THEME["orange"], THEME["blue"], THEME["green"], THEME["purple"]]
    for i, value in enumerate(vals):
        x = base_x + i * 155
        h = value * scale
        s.elements += [
            r(x, base_y - h, 90, h, fills[i], radius=10),
            t(f"{value:.1f}", x - 20, base_y - h - 44, 130, 28, size=24, color=THEME["ink"], bold=True, align="center"),
            t(names[i], x - 42, base_y + 24, 172, 28, size=20, color=THEME["muted"], align="center"),
        ]
    s.elements += [
        r(126, base_y, 720, 4, THEME["line"]),
        t("Average largest subdatabase", 155, 230, 470, 38, size=30, color=THEME["ink"], bold=True),
        t("Profile-Balanced lowers the largest bucket from 47.49 to 37.41 vs the strongest node-local baseline, and drives the average size gap from 32.57 to 1.00.", 910, 286, 560, 166, size=30, color=THEME["teal"], bold=True),
        t("The right claim is structural: after exact width is fixed, subtree-level moves flatten the PIR subdatabase layout.", 910, 526, 560, 96, size=24, color=THEME["muted"]),
    ]
    slides.append(s)

    s = SlideSpec("backend")
    slide_title(s, "Backend-shaped experiments close the loop", "The strongest structural balancer is now included in the executable backend tables.")
    s.elements += [
        img(assets["backend"], 100, 222, 760, 420, fit="contain"),
        t("Direct organization reduces stored proof material before any cryptographic backend trick.", 920, 250, 500, 74, size=29, color=THEME["ink"], bold=True),
        t("XOR backend: query bytes fall from 514.0 to about 260-265.", 920, 365, 500, 54, size=23, color=THEME["muted"]),
        t("Matrix surrogate: count-balanced has the lowest byte packing, while profile-balanced has the flattest structural buckets.", 920, 452, 520, 84, size=23, color=THEME["muted"]),
        t("Interpretation: structural balance and backend-specific packing cost are related, but not identical.", 920, 590, 520, 70, size=25, color=THEME["teal"], bold=True),
    ]
    slides.append(s)

    s = SlideSpec("realdata")
    slide_title(s, "Real-data check: Xenon-derived sparse SMT snapshots", "The method is tested beyond toy random trees.")
    s.elements += [
        t("Dataset mapping", 130, 250, 320, 36, size=30, bold=True, color=THEME["teal"]),
        t("Entry numbers are mapped into a height-20 SMT by sha256 hashing or sequential placement. Collisions are counted and skipped until the requested number of unique occupied leaves is reached.", 130, 304, 520, 140, size=24, color=THEME["muted"]),
        t("Observed pattern", 820, 250, 340, 36, size=30, bold=True, color=THEME["orange"]),
        t("Profile-Balanced reduces count gaps on both hashed and clustered layouts. Clustered layouts expose a harder trade-off between count balance and weighted balance.", 820, 304, 520, 140, size=24, color=THEME["muted"]),
        r(180, 570, 260, 90, THEME["teal2"], radius=26),
        t("height 20", 220, 598, 180, 32, size=28, color=THEME["teal"], bold=True, align="center"),
        r(500, 570, 260, 90, THEME["blue2"], radius=26),
        t("5k / 10k / 20k", 526, 598, 210, 32, size=26, color=THEME["blue"], bold=True, align="center"),
        r(820, 570, 260, 90, THEME["orange2"], radius=26),
        t("sha256 + seq.", 848, 598, 200, 32, size=26, color=THEME["orange"], bold=True, align="center"),
        r(1140, 570, 260, 90, THEME["purple2"], radius=26),
        t("profile wins gap", 1166, 598, 210, 32, size=25, color=THEME["purple"], bold=True, align="center"),
    ]
    slides.append(s)

    s = SlideSpec("landing", bg="#F6F0E7")
    s.elements += [
        t("The contribution in one sentence", 88, 74, 920, 58, size=42, bold=True, font="title"),
        t("We define and validate the sparse-SMT proof organization layer that TreePIR needs before batch PIR can be applied directly.", 90, 176, 1180, 104, size=38, color=THEME["teal"], bold=True),
        r(100, 384, 320, 112, THEME["teal2"], radius=28),
        t("1. Direct object", 132, 416, 250, 30, size=25, bold=True, color=THEME["teal"]),
        t("active proof-bearing nodes", 132, 456, 250, 28, size=20, color=THEME["muted"]),
        r(470, 384, 320, 112, THEME["blue2"], radius=28),
        t("2. Exact width", 502, 416, 250, 30, size=25, bold=True, color=THEME["blue"]),
        t("minimum colors = m", 502, 456, 250, 28, size=20, color=THEME["muted"]),
        r(840, 384, 320, 112, THEME["orange2"], radius=28),
        t("3. Protocol complete", 872, 416, 260, 30, size=25, bold=True, color=THEME["orange"]),
        t("PIR + default completion", 872, 456, 250, 28, size=20, color=THEME["muted"]),
        r(1210, 384, 320, 112, THEME["purple2"], radius=28),
        t("4. Balanced layout", 1242, 416, 250, 30, size=25, bold=True, color=THEME["purple"]),
        t("subtree profile moves", 1242, 456, 250, 28, size=20, color=THEME["muted"]),
        t("What we do not claim yet: a new PIR primitive or universal superiority over production SealPIR/Spiral deployments.", 160, 636, 1260, 58, size=28, color=THEME["ink"], bold=True, align="center"),
        t("Next step: connect this organization layer to a production PIR backend and sharpen approximation guarantees for balancing.", 230, 724, 1120, 46, size=24, color=THEME["muted"], align="center"),
    ]
    slides.append(s)

    return slides


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text_value: str,
    box: Tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    align: str = "left",
    valign: str = "top",
    line_spacing: int = 8,
) -> None:
    x, y, w, h = box
    words = text_value.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= w or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
    total_h = sum(line_heights) + max(0, len(lines) - 1) * line_spacing
    if valign == "middle":
        cursor_y = y + max(0, (h - total_h) // 2)
    elif valign == "bottom":
        cursor_y = y + max(0, h - total_h)
    else:
        cursor_y = y

    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        if align == "center":
            cursor_x = x + (w - tw) // 2
        elif align == "right":
            cursor_x = x + w - tw
        else:
            cursor_x = x
        draw.text((cursor_x, cursor_y), line, font=font, fill=fill)
        cursor_y += lh + line_spacing


def render_preview(slide: SlideSpec, path: Path) -> None:
    canvas = Image.new("RGB", (SLIDE_W_PX, SLIDE_H_PX), hex_to_rgb(slide.bg))
    draw = ImageDraw.Draw(canvas)
    for element in slide.elements:
        x, y, w, h = map(int, [element.x, element.y, element.w, element.h])
        if element.kind == "rect":
            fill = hex_to_rgb(element.fill or "#FFFFFF")
            outline = hex_to_rgb(element.line) if element.line else None
            draw.rounded_rectangle([x, y, x + w, y + h], radius=element.radius, fill=fill, outline=outline, width=2 if outline else 1)
        elif element.kind == "text":
            kind = "title" if element.font == "title" else ("body_bold" if element.bold else "body")
            if element.font == "mono":
                kind = "mono"
            font = load_font(kind, element.font_size)
            draw_wrapped_text(
                draw,
                element.text,
                (x, y, w, h),
                font,
                hex_to_rgb(element.color),
                align=element.align,
                valign=element.valign,
            )
        elif element.kind == "image" and element.path:
            im = Image.open(element.path).convert("RGBA")
            iw, ih = im.size
            scale = min(w / iw, h / ih)
            if element.fit == "cover":
                scale = max(w / iw, h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            im = im.resize((nw, nh), Image.Resampling.LANCZOS)
            if element.fit == "cover":
                left = max(0, (nw - w) // 2)
                top = max(0, (nh - h) // 2)
                im = im.crop((left, top, left + w, top + h))
                px, py = x, y
            else:
                px, py = x + (w - nw) // 2, y + (h - nh) // 2
            canvas.alpha_composite(im, (px, py)) if canvas.mode == "RGBA" else canvas.paste(im, (px, py), im)
    canvas.save(path)


def image_size_for_box(path: Path, x: float, y: float, w: float, h: float, fit: str) -> Tuple[float, float, float, float]:
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    if fit == "cover":
        scale = max(w / iw, h / ih)
    nw, nh = iw * scale, ih * scale
    if fit == "cover":
        return x, y, w, h
    return x + (w - nw) / 2, y + (h - nh) / 2, nw, nh


def ppt_text_shape(shape_id: int, element: Element) -> str:
    font = "Georgia" if element.font == "title" else ("Consolas" if element.font == "mono" else "Segoe UI")
    paragraphs = element.text.split("\n")
    runs = []
    for para in paragraphs:
        runs.append(
            f"""<a:p><a:pPr algn="{element.align[0] if element.align in {'left','right'} else 'ctr'}"/><a:r><a:rPr lang="en-US" sz="{element.font_size * 100}" {'b="1"' if element.bold else ''}><a:solidFill><a:srgbClr val="{strip_hash(element.color)}"/></a:solidFill><a:latin typeface="{font}"/><a:cs typeface="{font}"/></a:rPr><a:t>{text_escape(para)}</a:t></a:r></a:p>"""
        )
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{text_escape(element.name or 'Text')}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{emu_x(element.x)}" y="{emu_y(element.y)}"/><a:ext cx="{emu_x(element.w)}" cy="{emu_y(element.h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
  <p:txBody><a:bodyPr wrap="square" anchor="{'mid' if element.valign == 'middle' else 't'}"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{''.join(runs)}</p:txBody>
</p:sp>"""


def ppt_rect_shape(shape_id: int, element: Element) -> str:
    fill = strip_hash(element.fill or "#FFFFFF")
    line = strip_hash(element.line) if element.line else fill
    geom = "roundRect" if element.radius >= 14 else "rect"
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{text_escape(element.name or 'Shape')}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{emu_x(element.x)}" y="{emu_y(element.y)}"/><a:ext cx="{emu_x(element.w)}" cy="{emu_y(element.h)}"/></a:xfrm><a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>
</p:sp>"""


def ppt_image_shape(shape_id: int, element: Element, rel_id: str) -> str:
    assert element.path is not None
    x, y, w, h = image_size_for_box(element.path, element.x, element.y, element.w, element.h, element.fit)
    return f"""
<p:pic>
  <p:nvPicPr><p:cNvPr id="{shape_id}" name="{text_escape(element.name or element.path.name)}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="{emu_x(x)}" y="{emu_y(y)}"/><a:ext cx="{emu_x(w)}" cy="{emu_y(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>"""


def slide_xml(slide: SlideSpec, image_rels: Dict[str, str]) -> str:
    shapes = [
        """<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>"""
    ]
    shape_id = 2
    bg = strip_hash(slide.bg)
    for element in slide.elements:
        if element.kind == "text":
            shapes.append(ppt_text_shape(shape_id, element))
        elif element.kind == "rect":
            shapes.append(ppt_rect_shape(shape_id, element))
        elif element.kind == "image" and element.path:
            rel_id = image_rels[str(element.path)]
            shapes.append(ppt_image_shape(shape_id, element, rel_id))
        shape_id += 1
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>{''.join(shapes)}</p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def rels_xml(rels: Sequence[Tuple[str, str, str]]) -> str:
    body = "\n".join(
        f'<Relationship Id="{rid}" Type="{typ}" Target="{escape(target)}"/>'
        for rid, typ, target in rels
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{body}
</Relationships>"""


def write_pptx(slides: Sequence[SlideSpec], pptx_path: Path) -> None:
    image_paths: List[Path] = []
    for slide in slides:
        for element in slide.elements:
            if element.kind == "image" and element.path and element.path not in image_paths:
                image_paths.append(element.path)

    media_name = {path: f"image{idx + 1}.png" for idx, path in enumerate(image_paths)}

    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(slides) + 1)
    )
    content_types = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{slide_overrides}
</Types>"""

    presentation_rels = [("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "slideMasters/slideMaster1.xml")]
    for i in range(1, len(slides) + 1):
        presentation_rels.append((f"rId{i + 1}", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide", f"slides/slide{i}.xml"))

    slide_ids = "\n".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, len(slides) + 1))
    presentation_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_CX}" cy="{SLIDE_CY}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle/>
</p:presentation>"""

    master_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>"""
    layout_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""
    theme_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{NS_A}" name="SparseTreePIR">
  <a:themeElements>
    <a:clrScheme name="SparseTreePIR"><a:dk1><a:srgbClr val="17202A"/></a:dk1><a:lt1><a:srgbClr val="F7F4ED"/></a:lt1><a:dk2><a:srgbClr val="102A2A"/></a:dk2><a:lt2><a:srgbClr val="FFFDF8"/></a:lt2><a:accent1><a:srgbClr val="0F766E"/></a:accent1><a:accent2><a:srgbClr val="D97706"/></a:accent2><a:accent3><a:srgbClr val="2563EB"/></a:accent3><a:accent4><a:srgbClr val="7C3AED"/></a:accent4><a:accent5><a:srgbClr val="15803D"/></a:accent5><a:accent6><a:srgbClr val="B91C1C"/></a:accent6><a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="SparseTreePIR"><a:majorFont><a:latin typeface="Georgia"/></a:majorFont><a:minorFont><a:latin typeface="Segoe UI"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="SparseTreePIR"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>"""

    core_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Direct Sparse TreePIR</dc:title><dc:creator>Codex</dc:creator><cp:lastModifiedBy>Codex</cp:lastModifiedBy></cp:coreProperties>"""
    app_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Codex</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>{len(slides)}</Slides></Properties>"""

    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml([
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "ppt/presentation.xml"),
            ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
            ("rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "docProps/app.xml"),
        ]))
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)
        zf.writestr("ppt/presentation.xml", presentation_xml)
        zf.writestr("ppt/_rels/presentation.xml.rels", rels_xml(presentation_rels))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", master_xml)
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels_xml([
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme", "../theme/theme1.xml"),
        ]))
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", layout_xml)
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", rels_xml([
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "../slideMasters/slideMaster1.xml"),
        ]))
        zf.writestr("ppt/theme/theme1.xml", theme_xml)

        for idx, image_path in enumerate(image_paths, start=1):
            zf.write(image_path, f"ppt/media/{media_name[image_path]}")

        for slide_idx, slide in enumerate(slides, start=1):
            image_rels: Dict[str, str] = {}
            rels = [("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml")]
            next_rel = 2
            for element in slide.elements:
                if element.kind == "image" and element.path:
                    key = str(element.path)
                    if key not in image_rels:
                        rid = f"rId{next_rel}"
                        next_rel += 1
                        image_rels[key] = rid
                        rels.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", f"../media/{media_name[element.path]}"))
            zf.writestr(f"ppt/slides/slide{slide_idx}.xml", slide_xml(slide, image_rels))
            zf.writestr(f"ppt/slides/_rels/slide{slide_idx}.xml.rels", rels_xml(rels))


def write_previews(slides: Sequence[SlideSpec]) -> None:
    for old in PREVIEW_DIR.glob("slide_*.png"):
        old.unlink()
    preview_paths = []
    for idx, slide in enumerate(slides, start=1):
        path = PREVIEW_DIR / f"slide_{idx:02d}.png"
        render_preview(slide, path)
        preview_paths.append(path)

    thumb_w = 320
    thumb_h = 180
    cols = 3
    rows = (len(preview_paths) + cols - 1) // cols
    montage = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (245, 243, 238))
    for idx, path in enumerate(preview_paths):
        im = Image.open(path).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        montage.paste(im, ((idx % cols) * thumb_w, (idx // cols) * thumb_h))
    montage.save(MONTAGE_PATH)


def main() -> None:
    assets = prepare_assets()
    slides = build_slides(assets)
    write_pptx(slides, PPTX_PATH)
    write_previews(slides)
    print(f"Wrote {PPTX_PATH}")
    print(f"Wrote previews to {PREVIEW_DIR}")
    print(f"Wrote montage {MONTAGE_PATH}")
    print(f"Slides: {len(slides)}")


if __name__ == "__main__":
    main()
