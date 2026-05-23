from __future__ import annotations

import html
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPTS = ROOT / "manuscripts"
FIGURES = ROOT / "figures"
OUT = ROOT / "manuscripts" / "sparsetreepir_word_draft.docx"
ASSET_DIR = ROOT / "build" / "docx_assets"

BODY = MANUSCRIPTS / "sparsetreepir_body_full_en.tex"
ENTRY = MANUSCRIPTS / "sparsetreepir_conference.tex"
AUX = ROOT / "build" / "sparsetreepir_conference.aux"

EMU_PER_INCH = 914400
MAX_IMAGE_WIDTH_IN = 5.9


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    rows: Optional[List[List[str]]] = None
    image: Optional[Path] = None
    caption: str = ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_bibliography(body: str) -> Tuple[Dict[str, int], List[str], str]:
    bib_match = re.search(r"\\begin\{thebibliography\}\{[^}]*\}(.*?)\\end\{thebibliography\}", body, re.S)
    if not bib_match:
        return {}, [], body
    bib_text = bib_match.group(1)
    body_without = body[: bib_match.start()] + body[bib_match.end() :]
    keys: Dict[str, int] = {}
    refs: List[str] = []
    parts = re.split(r"\\bibitem\{([^}]+)\}", bib_text)
    # parts[0] is preamble; then key, text, key, text...
    for idx in range(1, len(parts), 2):
        key = parts[idx].strip()
        raw = parts[idx + 1].strip()
        number = len(refs) + 1
        keys[key] = number
        refs.append(clean_inline(raw, {}, keys, for_bib=True))
    return keys, refs, body_without


def parse_labels() -> Dict[str, str]:
    labels: Dict[str, str] = {}
    if not AUX.exists():
        return labels
    text = read_text(AUX)
    for match in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", text):
        labels[match.group(1)] = match.group(2)
    return labels


def strip_comments(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        # Avoid treating escaped \% as a comment marker.
        line = re.sub(r"(?<!\\)%.*$", "", line)
        out_lines.append(line)
    return "\n".join(out_lines)


def replace_cite(match: re.Match[str], cite_map: Dict[str, int]) -> str:
    nums = []
    for key in match.group(1).split(","):
        key = key.strip()
        nums.append(str(cite_map.get(key, key)))
    return "[" + ",".join(nums) + "]"


def clean_inline(
    text: str,
    labels: Dict[str, str],
    cite_map: Dict[str, int],
    for_bib: bool = False,
) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\\cite\{([^}]+)\}", lambda m: replace_cite(m, cite_map), text)
    text = re.sub(r"\\ref\{([^}]+)\}", lambda m: labels.get(m.group(1), m.group(1)), text)
    text = re.sub(r"\\label\{[^}]+\}", "", text)
    text = re.sub(r"\\(emph|textit|textbf|texttt|mathrm|mathsf|operatorname)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\newblock\s*", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})", r"\1", text)
    text = text.replace("\\%", "%").replace("\\_", "_").replace("\\&", "&")
    text = text.replace("\\#", "#").replace("\\$", "$").replace("\\{", "{").replace("\\}", "}")
    text = text.replace("``", '"').replace("''", '"')
    text = text.replace("~", " ")
    text = text.replace("---", "-").replace("--", "-")
    text = re.sub(r"\s+", " ", text).strip()
    if not for_bib:
        text = re.sub(r"\$(.*?)\$", r"\1", text)
    return text


def extract_caption(env_text: str, labels: Dict[str, str], cite_map: Dict[str, int]) -> str:
    match = re.search(r"\\caption(?:\[[^\]]*\])?\{(.*?)\}", env_text, re.S)
    if not match:
        return ""
    return clean_inline(match.group(1), labels, cite_map)


def figure_path(env_text: str) -> Optional[Path]:
    match = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", env_text)
    if not match:
        return None
    raw = match.group(1).strip()
    path = (MANUSCRIPTS / raw).resolve()
    if path.exists():
        return path
    alt = (ROOT / raw).resolve()
    return alt if alt.exists() else None


def convert_pdf_to_png(pdf: Path) -> Optional[Path]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    outbase = ASSET_DIR / pdf.stem
    png = ASSET_DIR / f"{pdf.stem}.png"
    if not png.exists() or png.stat().st_mtime < pdf.stat().st_mtime:
        subprocess.run(
            ["pdftoppm", "-r", "180", "-png", "-singlefile", str(pdf), str(outbase)],
            check=True,
            cwd=str(ROOT),
        )
    return png if png.exists() else None


def parse_tabular(env_text: str, labels: Dict[str, str], cite_map: Dict[str, int]) -> List[List[str]]:
    match = re.search(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", env_text, re.S)
    if not match:
        return []
    raw = match.group(1)
    raw = re.sub(r"\\(toprule|midrule|bottomrule)", "", raw)
    raw = re.sub(r"\\cmidrule(?:\([^)]*\))?\{[^}]+\}", "", raw)
    raw = re.sub(r"\\multicolumn\{[^}]+\}\{[^}]+\}\{([^{}]*)\}", r"\1", raw)
    rows = []
    for line in raw.split(r"\\"):
        line = line.strip()
        if not line:
            continue
        cells = [clean_inline(cell.strip(), labels, cite_map) for cell in line.split("&")]
        if any(cells):
            rows.append(cells)
    return rows


def parse_algorithm(env_text: str, labels: Dict[str, str], cite_map: Dict[str, int]) -> str:
    caption = extract_caption(env_text, labels, cite_map)
    body = re.sub(r".*?\\begin\{algorithmic\}(?:\[[^\]]*\])?", "", env_text, flags=re.S)
    body = re.sub(r"\\end\{algorithmic\}.*", "", body, flags=re.S)
    lines: List[str] = []
    if caption:
        lines.append(caption)
        lines.append("")
    for raw in body.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        raw = re.sub(r"\\State\s*", "", raw)
        raw = re.sub(r"\\Require\s*", "Input: ", raw)
        raw = re.sub(r"\\Ensure\s*", "Output: ", raw)
        raw = re.sub(r"\\For\{(.*?)\}", r"for \1:", raw)
        raw = re.sub(r"\\If\{(.*?)\}", r"if \1:", raw)
        raw = re.sub(r"\\Else", "else:", raw)
        raw = re.sub(r"\\End(For|If)", "end", raw)
        raw = clean_inline(raw, labels, cite_map)
        if raw:
            lines.append(raw)
    return "\n".join(lines)


def split_special_blocks(body: str, labels: Dict[str, str], cite_map: Dict[str, int]) -> List[Block]:
    blocks: List[Block] = []
    pos = 0
    pattern = re.compile(
        r"\\begin\{(figure|table|algorithm|equation|align\*?|alignat\*?)\}(.*?)\\end\{\1\}",
        re.S,
    )
    for match in pattern.finditer(body):
        blocks.extend(parse_plain(body[pos : match.start()], labels, cite_map))
        env_name = match.group(1)
        env_text = match.group(0)
        if env_name == "figure":
            cap = extract_caption(env_text, labels, cite_map)
            fig = figure_path(env_text)
            image = None
            if fig:
                image = convert_pdf_to_png(fig) if fig.suffix.lower() == ".pdf" else fig
            blocks.append(Block("figure", image=image, caption=cap))
        elif env_name == "table":
            cap = extract_caption(env_text, labels, cite_map)
            rows = parse_tabular(env_text, labels, cite_map)
            if cap:
                blocks.append(Block("caption", cap))
            if rows:
                blocks.append(Block("table", rows=rows))
        elif env_name == "algorithm":
            blocks.append(Block("code", parse_algorithm(env_text, labels, cite_map)))
        else:
            eq = clean_inline(match.group(2), labels, cite_map)
            blocks.append(Block("equation", eq))
        pos = match.end()
    blocks.extend(parse_plain(body[pos:], labels, cite_map))
    return blocks


def parse_plain(text: str, labels: Dict[str, str], cite_map: Dict[str, int]) -> List[Block]:
    blocks: List[Block] = []
    text = re.sub(r"\\\[(.*?)\\\]", lambda m: "\n<<EQUATION>>" + m.group(1) + "<<END>>\n", text, flags=re.S)
    text = re.sub(r"\\begin\{(definition|theorem|proposition|lemma|remark|proof|corollary)\}(?:\[[^\]]*\])?", r"\n<<SUBHEAD>>\1<<END>>\n", text)
    text = re.sub(r"\\end\{(definition|theorem|proposition|lemma|remark|proof|corollary)\}", "\n", text)
    text = text.replace(r"\begin{enumerate}[leftmargin=2em]", "\n").replace(r"\begin{enumerate}", "\n")
    text = text.replace(r"\end{enumerate}", "\n")
    text = text.replace(r"\begin{itemize}", "\n").replace(r"\end{itemize}", "\n")
    parts = re.split(r"\n\s*\n", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        while True:
            sec = re.search(r"\\(section|subsection|subsubsection)\{([^{}]+)\}", part)
            if not sec:
                break
            before = part[: sec.start()].strip()
            if before:
                blocks.extend(parse_plain(before, labels, cite_map))
            level = {"section": 1, "subsection": 2, "subsubsection": 3}[sec.group(1)]
            blocks.append(Block("heading", clean_inline(sec.group(2), labels, cite_map), level=level))
            part = part[sec.end() :].strip()
        if not part:
            continue
        if part.startswith("<<EQUATION>>"):
            eq = part.replace("<<EQUATION>>", "").replace("<<END>>", "")
            blocks.append(Block("equation", clean_inline(eq, labels, cite_map)))
            continue
        if part.startswith("<<SUBHEAD>>"):
            sub = part.replace("<<SUBHEAD>>", "").replace("<<END>>", "")
            blocks.append(Block("subhead", sub.capitalize()))
            continue
        for line in part.splitlines():
            line = line.strip()
            if not line:
                continue
            is_item = line.startswith(r"\item")
            line = re.sub(r"^\\item\s*", "", line)
            cleaned = clean_inline(line, labels, cite_map)
            if not cleaned:
                continue
            blocks.append(Block("bullet" if is_item else "paragraph", cleaned))
    return blocks


def get_title_and_abstract() -> Tuple[str, str, str]:
    entry = read_text(ENTRY)
    title = re.search(r"\\title\{(.*?)\}", entry, re.S)
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", entry, re.S)
    keywords = re.search(r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", entry, re.S)
    labels = parse_labels()
    cite_map, _, _ = parse_bibliography(read_text(BODY))
    return (
        clean_inline(title.group(1), labels, cite_map) if title else "Virtual-Swapped TreePIR",
        clean_inline(abstract.group(1), labels, cite_map) if abstract else "",
        clean_inline(keywords.group(1), labels, cite_map) if keywords else "",
    )


def xml_escape(text: str) -> str:
    return html.escape(text, quote=False)


def run_xml(text: str, bold: bool = False, italic: bool = False, size: Optional[int] = None) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if size:
        props.append(f'<w:sz w:val="{size * 2}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t></w:r>"


def para_xml(
    text: str,
    style: str = "Normal",
    bold: bool = False,
    italic: bool = False,
    align: Optional[str] = None,
    shade: Optional[str] = None,
) -> str:
    ppr_parts = [f'<w:pStyle w:val="{style}"/>'] if style else []
    if align:
        ppr_parts.append(f'<w:jc w:val="{align}"/>')
    if shade:
        ppr_parts.append(f'<w:shd w:fill="{shade}"/>')
    ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>" if ppr_parts else ""
    return f"<w:p>{ppr}{run_xml(text, bold=bold, italic=italic)}</w:p>"


def table_xml(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)
    out = [
        "<w:tbl>",
        "<w:tblPr><w:tblStyle w:val=\"TableGrid\"/><w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblLook w:firstRow=\"1\" w:lastRow=\"0\" w:firstColumn=\"0\" w:lastColumn=\"0\" w:noHBand=\"0\" w:noVBand=\"1\"/></w:tblPr>",
    ]
    for r_i, row in enumerate(rows):
        out.append("<w:tr>")
        for c in range(max_cols):
            text = row[c] if c < len(row) else ""
            shade = "<w:shd w:fill=\"EAF4F2\"/>" if r_i == 0 else ""
            out.append(
                "<w:tc><w:tcPr><w:tcW w:w=\"2200\" w:type=\"dxa\"/>"
                + shade
                + "</w:tcPr>"
                + para_xml(text, style="TableText", bold=(r_i == 0))
                + "</w:tc>"
            )
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def image_xml(rid: str, width_emu: int, height_emu: int, descr: str = "figure") -> str:
    return f"""
<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>
<wp:inline distT="0" distB="0" distL="0" distR="0"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
<wp:extent cx="{width_emu}" cy="{height_emu}"/>
<wp:docPr id="1" name="{xml_escape(descr)}"/>
<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:nvPicPr><pic:cNvPr id="0" name="{xml_escape(descr)}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{rid}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic>
</wp:inline></w:drawing></w:r></w:p>
"""


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="36"/><w:color w:val="143C38"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:qFormat/><w:pPr><w:spacing w:before="360" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="30"/><w:color w:val="143C38"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:qFormat/><w:pPr><w:spacing w:before="260" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="25"/><w:color w:val="1F2937"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:qFormat/><w:pPr><w:spacing w:before="180" w:after="90"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:b/><w:sz w:val="22"/><w:color w:val="334155"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="160"/></w:pPr><w:rPr><w:i/><w:sz w:val="18"/><w:color w:val="475569"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:qFormat/><w:pPr><w:spacing w:before="120" w:after="160"/><w:shd w:fill="F3F7F6"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/><w:color w:val="1F2937"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:pPr><w:spacing w:after="40" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="CBD5E1"/><w:left w:val="single" w:sz="4" w:color="CBD5E1"/><w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/><w:right w:val="single" w:sz="4" w:color="CBD5E1"/><w:insideH w:val="single" w:sz="4" w:color="CBD5E1"/><w:insideV w:val="single" w:sz="4" w:color="CBD5E1"/></w:tblBorders><w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
</w:styles>"""


def build_docx(blocks: Sequence[Block], refs: Sequence[str]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    title, abstract, keywords = get_title_and_abstract()
    doc_parts: List[str] = []
    relationships: List[str] = []
    media_files: List[Tuple[Path, str]] = []
    next_rid = 1

    def add_image(path: Path, caption: str) -> None:
        nonlocal next_rid
        if not path or not path.exists():
            if caption:
                doc_parts.append(para_xml(caption, style="Caption"))
            return
        rid = f"rId{next_rid}"
        next_rid += 1
        ext = path.suffix.lower().lstrip(".")
        name = f"image{len(media_files)+1}.{ext}"
        media_files.append((path, f"word/media/{name}"))
        relationships.append(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>'
        )
        with Image.open(path) as im:
            w_px, h_px = im.size
        width_in = min(MAX_IMAGE_WIDTH_IN, w_px / 180)
        height_in = width_in * h_px / w_px
        doc_parts.append(image_xml(rid, int(width_in * EMU_PER_INCH), int(height_in * EMU_PER_INCH), caption or path.stem))
        if caption:
            doc_parts.append(para_xml(caption, style="Caption"))

    doc_parts.append(para_xml(title, style="Title"))
    doc_parts.append(para_xml("Anonymous Author(s)", align="center", italic=True))
    doc_parts.append(para_xml("Abstract", style="Heading1"))
    doc_parts.append(para_xml(abstract))
    doc_parts.append(para_xml("Keywords", style="Heading2"))
    doc_parts.append(para_xml(keywords))

    for block in blocks:
        if block.kind == "heading":
            doc_parts.append(para_xml(block.text, style=f"Heading{min(block.level, 3)}"))
        elif block.kind == "subhead":
            doc_parts.append(para_xml(block.text, style="Heading3"))
        elif block.kind == "paragraph":
            doc_parts.append(para_xml(block.text))
        elif block.kind == "bullet":
            doc_parts.append(para_xml("• " + block.text))
        elif block.kind == "equation":
            doc_parts.append(para_xml(block.text, style="Code"))
        elif block.kind == "code":
            for line in block.text.splitlines():
                doc_parts.append(para_xml(line if line else " ", style="Code"))
        elif block.kind == "caption":
            doc_parts.append(para_xml(block.text, style="Caption"))
        elif block.kind == "table" and block.rows:
            doc_parts.append(table_xml(block.rows))
        elif block.kind == "figure":
            add_image(block.image, block.caption)

    doc_parts.append(para_xml("References", style="Heading1"))
    for i, ref in enumerate(refs, start=1):
        doc_parts.append(para_xml(f"[{i}] {ref}", style="Normal"))

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
<w:body>
{''.join(doc_parts)}
<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>
</w:body></w:document>"""

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    doc_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(relationships)
        + "</Relationships>"
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>"""
    settings_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:zoom w:percent="100"/></w:settings>"""

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", styles_xml())
        zf.writestr("word/settings.xml", settings_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        for src, dst in media_files:
            zf.write(src, dst)


def main() -> None:
    labels = parse_labels()
    body = strip_comments(read_text(BODY))
    cite_map, refs, body = parse_bibliography(body)
    # Drop LaTeX-only options that confuse the lightweight parser.
    body = re.sub(r"\\setlength\{[^}]+\}\{[^}]+\}", "", body)
    body = re.sub(r"\\resizebox\{[^}]+\}\{[^}]+\}\{", "", body)
    blocks = split_special_blocks(body, labels, cite_map)
    build_docx(blocks, refs)
    print(f"Wrote {OUT}")
    print(f"Blocks: {len(blocks)}, references: {len(refs)}")


if __name__ == "__main__":
    main()
