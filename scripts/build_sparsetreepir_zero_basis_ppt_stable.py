from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import build_sparsetreepir_story_deck_stable as stable
import build_sparsetreepir_zero_basis_ppt as zero


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "presentations"
STABLE_PPTX = OUT_DIR / "sparsetreepir_zero_basis_explainer_stable.pptx"


def find_template() -> Path:
    preferred = Path.home() / "Desktop" / "汇报.pptx"
    if preferred.exists():
        return preferred
    candidates = sorted(Path.home().joinpath("Desktop").glob("*.pptx"), key=lambda p: p.stat().st_size)
    if not candidates:
        raise RuntimeError("No desktop .pptx template was found for compatibility wrapping.")
    return candidates[0]


def build_stable_zero_basis_pptx() -> Path:
    # Regenerate the PNG previews first. The image-wrapped deck is intentionally
    # conservative because it is meant to open reliably in PowerPoint/WPS.
    zero.main()

    template = find_template()
    cx, cy = stable.get_slide_size(template)
    n_template = stable.slide_count(template)
    preview_paths = sorted(zero.PREVIEW_DIR.glob("slide_*.png"))
    if not preview_paths:
        raise RuntimeError(f"No slide previews found under {zero.PREVIEW_DIR}.")
    total_slides = len(preview_paths)

    with zipfile.ZipFile(template) as src:
        rel_root = ET.fromstring(src.read("ppt/_rels/presentation.xml.rels"))
    next_rid = stable.max_rid_number(rel_root) + 1
    extra_slide_rels = [
        (slide_index, f"rId{next_rid + offset}")
        for offset, slide_index in enumerate(range(n_template + 1, total_slides + 1))
    ]

    slide_targets = {
        f"ppt/slides/slide{i}.xml": stable.slide_xml(cx, cy)
        for i in range(1, total_slides + 1)
    }
    default_layout_target = stable.get_slide_layout_target(template, 1)
    rel_targets = {
        f"ppt/slides/_rels/slide{i}.xml.rels": stable.rels_xml(
            stable.get_slide_layout_target(template, i) if i <= n_template else default_layout_target,
            f"../media/codex_zero_basis_slide_{i:02d}.png",
        )
        for i in range(1, total_slides + 1)
    }

    stable_output = stable.choose_unlocked_output(STABLE_PPTX)
    with zipfile.ZipFile(template, "r") as src, zipfile.ZipFile(stable_output, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = stable.ensure_slide_overrides(data, range(n_template + 1, total_slides + 1))
            elif item.filename == "ppt/presentation.xml":
                data = stable.append_presentation_slide_ids(data, extra_slide_rels)
            elif item.filename == "ppt/_rels/presentation.xml.rels":
                data = stable.append_presentation_relationships(data, extra_slide_rels)
            elif item.filename == "docProps/app.xml":
                data = stable.update_app_slide_count(data, total_slides)

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
            dst.write(image_path, f"ppt/media/codex_zero_basis_slide_{i:02d}.png")

    # Also keep a clearly named fallback copy. Some Office apps lock the first
    # file after a failed open attempt, so this gives the user a second clean path.
    fallback = OUT_DIR / "sparsetreepir_zero_basis_explainer_openable.pptx"
    if fallback != stable_output:
        shutil.copyfile(stable_output, fallback)

    print(f"Template: {template}")
    print(f"Stable PPTX: {stable_output}")
    print(f"Fallback copy: {fallback}")
    print(f"Slides written: {total_slides}")
    return stable_output


if __name__ == "__main__":
    build_stable_zero_basis_pptx()
