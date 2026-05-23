from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from typing import Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

import build_sparsetreepir_story_deck as editable


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "presentations"
PREVIEW_DIR = OUT_DIR / "previews"
STABLE_PPTX = OUT_DIR / "sparsetreepir_story_deck_stable.pptx"

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def find_template() -> Path:
    desktop = Path.home() / "Desktop"
    candidates = []
    for path in desktop.glob("*.pptx"):
        if "sparsetreepir" in path.name.lower() or "sparse_treepir" in path.name.lower():
            continue
        candidates.append(path)
    if not candidates:
        raise RuntimeError("No existing desktop .pptx template was found.")
    # Prefer the smallest ordinary deck as a lightweight compatibility container.
    return sorted(candidates, key=lambda item: item.stat().st_size)[0]


def get_slide_size(template: Path) -> Tuple[int, int]:
    with zipfile.ZipFile(template) as zf:
        xml = zf.read("ppt/presentation.xml")
    root = ET.fromstring(xml)
    ns = {"p": P_NS}
    size = root.find("p:sldSz", ns)
    if size is None:
        return 12192000, 6858000
    return int(size.attrib["cx"]), int(size.attrib["cy"])


def get_slide_layout_target(template: Path, slide_index: int) -> str:
    rel_path = f"ppt/slides/_rels/slide{slide_index}.xml.rels"
    with zipfile.ZipFile(template) as zf:
        xml = zf.read(rel_path)
    root = ET.fromstring(xml)
    for rel in root:
        if rel.attrib.get("Type", "").endswith("/slideLayout"):
            return rel.attrib["Target"]
    return "../slideLayouts/slideLayout1.xml"


def rels_xml(layout_target: str, image_target: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="{layout_target}"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{image_target}"/>
</Relationships>"""


def slide_xml(cx: int, cy: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:pic>
        <p:nvPicPr><p:cNvPr id="2" name="slide-render.png"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def ensure_png_default(content_types: bytes) -> bytes:
    text = content_types.decode("utf-8")
    if 'Extension="png"' in text:
        return text.encode("utf-8")
    insert = '  <Default Extension="png" ContentType="image/png"/>\n'
    text = text.replace("</Types>", insert + "</Types>")
    return text.encode("utf-8")


def ensure_slide_overrides(content_types: bytes, slide_indices: range) -> bytes:
    text = ensure_png_default(content_types).decode("utf-8")
    for index in slide_indices:
        part = f'/ppt/slides/slide{index}.xml'
        if part in text:
            continue
        override = (
            f'  <Override PartName="{part}" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>\n'
        )
        text = text.replace("</Types>", override + "</Types>")
    return text.encode("utf-8")


def max_rid_number(root: ET.Element) -> int:
    max_id = 0
    for rel in root:
        rid = rel.attrib.get("Id", "")
        match = re.match(r"rId(\d+)$", rid)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id


def append_presentation_relationships(data: bytes, extra: Sequence[Tuple[int, str]]) -> bytes:
    ET.register_namespace("", REL_NS)
    root = ET.fromstring(data)
    for slide_index, rid in extra:
        rel = ET.SubElement(root, f"{{{REL_NS}}}Relationship")
        rel.set("Id", rid)
        rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide")
        rel.set("Target", f"slides/slide{slide_index}.xml")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def append_presentation_slide_ids(data: bytes, extra: Sequence[Tuple[int, str]]) -> bytes:
    ET.register_namespace("p", P_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("r", R_NS)
    root = ET.fromstring(data)
    ns = {"p": P_NS}
    slide_id_list = root.find("p:sldIdLst", ns)
    if slide_id_list is None:
        slide_id_list = ET.SubElement(root, f"{{{P_NS}}}sldIdLst")
    max_id = 255
    for item in slide_id_list:
        value = item.attrib.get("id")
        if value and value.isdigit():
            max_id = max(max_id, int(value))
    for slide_index, rid in extra:
        max_id += 1
        item = ET.SubElement(slide_id_list, f"{{{P_NS}}}sldId")
        item.set("id", str(max_id))
        item.set(f"{{{R_NS}}}id", rid)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_app_slide_count(data: bytes, count: int) -> bytes:
    text = data.decode("utf-8", errors="ignore")
    text = re.sub(r"<Slides>\d+</Slides>", f"<Slides>{count}</Slides>", text)
    return text.encode("utf-8")


def choose_unlocked_output(preferred: Path) -> Path:
    try:
        with preferred.open("ab"):
            pass
        return preferred
    except PermissionError:
        for index in range(1, 100):
            candidate = preferred.with_name(f"{preferred.stem}_new{index}{preferred.suffix}")
            if not candidate.exists():
                return candidate
            try:
                with candidate.open("ab"):
                    pass
                return candidate
            except PermissionError:
                continue
    raise PermissionError(f"Could not find an unlocked output path near {preferred}")


def slide_count(template: Path) -> int:
    with zipfile.ZipFile(template) as zf:
        return len([name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)])


def make_final_discussion_slide(path: Path) -> None:
    w, h = 1600, 900
    bg = (246, 240, 231)
    ink = (23, 32, 42)
    teal = (15, 118, 110)
    muted = (95, 111, 125)
    canvas = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(canvas)
    title_font = editable.load_font("title", 64)
    body_font = editable.load_font("body", 30)
    small_font = editable.load_font("body", 24)
    draw.text((92, 120), "Discussion", font=title_font, fill=ink)
    draw.rounded_rectangle([92, 270, 660, 360], radius=28, fill=(205, 237, 230))
    draw.text((132, 296), "Does the organization layer make sense?", font=body_font, fill=teal)
    draw.rounded_rectangle([92, 420, 660, 510], radius=28, fill=(217, 232, 255))
    draw.text((132, 446), "Where should backend integration go next?", font=body_font, fill=(37, 99, 235))
    draw.rounded_rectangle([92, 570, 660, 660], radius=28, fill=(230, 215, 255))
    draw.text((132, 596), "Can we prove stronger balance guarantees?", font=body_font, fill=(124, 58, 237))
    draw.text((980, 720), "Sparse Merkle proof retrieval", font=small_font, fill=muted)
    draw.text((980, 760), "active nodes -> colors -> batch PIR", font=small_font, fill=muted)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def build_stable_pptx() -> None:
    # Regenerate previews first, so the stable deck is always synchronized.
    original_main_pptx = editable.PPTX_PATH
    editable_draft = OUT_DIR / "sparsetreepir_story_deck_editable_draft.pptx"
    editable.PPTX_PATH = editable_draft
    editable.main()
    editable.PPTX_PATH = original_main_pptx

    template = find_template()
    cx, cy = get_slide_size(template)
    n_template = slide_count(template)
    preview_paths = sorted(PREVIEW_DIR.glob("slide_*.png"))
    if n_template > len(preview_paths):
        qna = PREVIEW_DIR / f"slide_{len(preview_paths) + 1:02d}_discussion.png"
        make_final_discussion_slide(qna)
        preview_paths.append(qna)
    total_slides = len(preview_paths)

    with zipfile.ZipFile(template) as src:
        rel_root = ET.fromstring(src.read("ppt/_rels/presentation.xml.rels"))
    next_rid = max_rid_number(rel_root) + 1
    extra_slide_rels = [
        (slide_index, f"rId{next_rid + offset}")
        for offset, slide_index in enumerate(range(n_template + 1, total_slides + 1))
    ]

    slide_targets = {
        f"ppt/slides/slide{i}.xml": slide_xml(cx, cy)
        for i in range(1, total_slides + 1)
    }
    default_layout_target = get_slide_layout_target(template, 1)
    rel_targets = {
        f"ppt/slides/_rels/slide{i}.xml.rels": rels_xml(
            get_slide_layout_target(template, i) if i <= n_template else default_layout_target,
            f"../media/codex_stable_slide_{i:02d}.png",
        )
        for i in range(1, total_slides + 1)
    }

    stable_output = choose_unlocked_output(STABLE_PPTX)
    with zipfile.ZipFile(template, "r") as src, zipfile.ZipFile(stable_output, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = ensure_slide_overrides(data, range(n_template + 1, total_slides + 1))
            elif item.filename == "ppt/presentation.xml":
                data = append_presentation_slide_ids(data, extra_slide_rels)
            elif item.filename == "ppt/_rels/presentation.xml.rels":
                data = append_presentation_relationships(data, extra_slide_rels)
            elif item.filename == "docProps/app.xml":
                data = update_app_slide_count(data, total_slides)
            if item.filename in slide_targets:
                dst.writestr(item, slide_targets[item.filename])
            elif item.filename in rel_targets:
                dst.writestr(item, rel_targets[item.filename])
            else:
                dst.writestr(item, data)
        for i in range(n_template + 1, total_slides + 1):
            dst.writestr(f"ppt/slides/slide{i}.xml", slide_targets[f"ppt/slides/slide{i}.xml"])
            dst.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", rel_targets[f"ppt/slides/_rels/slide{i}.xml.rels"])
        for i, image_path in enumerate(preview_paths, start=1):
            dst.write(image_path, f"ppt/media/codex_stable_slide_{i:02d}.png")

    print(f"Template: {template}")
    print(f"Stable PPTX: {stable_output}")
    print(f"Slides written: {total_slides}")

    try:
        shutil.copyfile(stable_output, original_main_pptx)
        print(f"Main PPTX updated: {original_main_pptx}")
    except PermissionError:
        unlocked_copy = OUT_DIR / "sparsetreepir_story_deck_with_leaf_examples.pptx"
        unlocked_copy = choose_unlocked_output(unlocked_copy)
        if unlocked_copy != stable_output:
            shutil.copyfile(stable_output, unlocked_copy)
        print(f"Main PPTX is locked and was not overwritten: {original_main_pptx}")
        print(f"Unlocked updated copy: {unlocked_copy}")


if __name__ == "__main__":
    build_stable_pptx()
