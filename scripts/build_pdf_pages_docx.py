from __future__ import annotations

import html
import subprocess
import zipfile
from pathlib import Path
from typing import List, Tuple

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "build" / "sparsetreepir_conference.pdf"
OUT = ROOT / "manuscripts" / "sparsetreepir_word_layout.docx"
PAGE_DIR = ROOT / "build" / "docx_pdf_pages"
EMU_PER_INCH = 914400


def xml_escape(text: str) -> str:
    return html.escape(text, quote=False)


def ensure_pages() -> List[Path]:
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    prefix = PAGE_DIR / "paper_page"
    existing = sorted(PAGE_DIR.glob("paper_page-*.png"))
    if not existing or max(p.stat().st_mtime for p in existing) < PDF.stat().st_mtime:
        for old in existing:
            old.unlink()
        subprocess.run(
            ["pdftoppm", "-r", "180", "-png", str(PDF), str(prefix)],
            cwd=str(ROOT),
            check=True,
        )
    return sorted(PAGE_DIR.glob("paper_page-*.png"))


def image_xml(rid: str, width_emu: int, height_emu: int, descr: str) -> str:
    return f"""
<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:drawing>
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


def build_docx(pages: List[Path]) -> None:
    relationships: List[str] = []
    media: List[Tuple[Path, str]] = []
    body_parts: List[str] = []
    # Keep the rendered PDF page comfortably inside Word's printable body.
    # If the image is too tall, Word pushes it to the next page and leaves
    # alternating blank pages.
    page_width_in = 7.25
    for idx, page in enumerate(pages, start=1):
        rid = f"rId{idx}"
        name = f"page_{idx:02d}.png"
        media.append((page, f"word/media/{name}"))
        relationships.append(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>'
        )
        with Image.open(page) as im:
            w_px, h_px = im.size
        width_emu = int(page_width_in * EMU_PER_INCH)
        height_emu = int(page_width_in * h_px / w_px * EMU_PER_INCH)
        body_parts.append(image_xml(rid, width_emu, height_emu, f"paper page {idx}"))
        if idx != len(pages):
            body_parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
<w:body>
{''.join(body_parts)}
<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="360" w:right="360" w:bottom="360" w:left="360" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>
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
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>"""
    settings_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:zoom w:percent="100"/></w:settings>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/settings.xml", settings_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        for src, dst in media:
            zf.write(src, dst)


def main() -> None:
    if not PDF.exists():
        raise FileNotFoundError(f"Compile the paper first: {PDF}")
    pages = ensure_pages()
    build_docx(pages)
    print(f"Wrote {OUT}")
    print(f"Pages: {len(pages)}")


if __name__ == "__main__":
    main()
