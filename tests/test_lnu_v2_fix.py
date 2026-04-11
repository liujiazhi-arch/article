"""Tests for LNU v2 fix function behaviours.

Each test verifies exactly one fix behaviour by building a minimal ET XML stub,
calling the fix function, then asserting on the mutated tree.
No real .docx files are required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fix_thesis
from fix_thesis import (
    HEADING_SPACING_DEFAULTS,
    fix_abstract_body,
    fix_abstract_heading,
    fix_abstract_section,
    fix_body_paragraph,
    fix_sp_cjk_latin,
    fix_cover_layout,
    fix_heading_paragraph,
    fix_insert_toc,
    inject_template_components,
    fix_lnu_abs03,
    fix_lnu_ack01,
    fix_lnu_s03,
    fix_lnu_title01,
    fix_lnu_tb03,
    normalize_lnu_preface_heading_numbering,
    remove_paragraphs_from_body,
    remove_existing_toc_artifacts,
    normalize_frontmatter_page_sections,
    fix_reference_paragraph,
    renumber_body_headings,
)
from _thesis_utils import NSMAP, W_NS, build_document_model, get_paragraph_text

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

W = W_NS


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _make_run(text: str = "", sz: int | None = None, bold: bool = False) -> ET.Element:
    r = ET.Element(_w("r"))
    r_pr = ET.SubElement(r, _w("rPr"))
    if sz is not None:
        sz_elem = ET.SubElement(r_pr, _w("sz"))
        sz_elem.set(_w("val"), str(sz))
    if bold:
        b_elem = ET.SubElement(r_pr, _w("b"))
        b_elem.set(_w("val"), "1")
    t = ET.SubElement(r, _w("t"))
    t.text = text
    return r


def _make_paragraph(text: str = "", sz: int | None = None, bold: bool = False) -> ET.Element:
    p = ET.Element(_w("p"))
    p.append(_make_run(text, sz=sz, bold=bold))
    return p


def _make_doc_root(*paragraphs: ET.Element) -> ET.Element:
    root = ET.Element(_w("document"))
    body = ET.SubElement(root, _w("body"))
    for p in paragraphs:
        body.append(p)
    return root


def _append_sect_pr(target: ET.Element, fmt: str, start: int = 1) -> ET.Element:
    p_pr = target.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(target, _w("pPr"))
    sect_pr = ET.SubElement(p_pr, _w("sectPr"))
    pg_num_type = ET.SubElement(sect_pr, _w("pgNumType"))
    pg_num_type.set(_w("fmt"), fmt)
    pg_num_type.set(_w("start"), str(start))
    return sect_pr


# ---------------------------------------------------------------------------
# Fixture: lnu cfg (real profile values)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def lnu_cfg():
    import audit_thesis
    return audit_thesis.load_profile("lnu")


@pytest.fixture()
def lnu_runtime():
    return fix_thesis.build_fix_runtime(profile_path="lnu")


# ---------------------------------------------------------------------------
# test_fix_abs_title_size
# ---------------------------------------------------------------------------

def test_fix_abs_title_size(lnu_cfg):
    """After fix_abstract_heading for abstract_cn, the title run has sz=32."""
    p = _make_paragraph("摘要", sz=28)  # wrong size initially
    fix_abstract_heading(p, lnu_cfg, "abstract_cn")

    sz_elems = p.findall(".//w:sz", NSMAP)
    assert sz_elems, "No w:sz element found after fix"
    actual_sz = int(sz_elems[0].get(_w("val")))
    assert actual_sz == 32, f"Expected sz=32, got {actual_sz}"


# ---------------------------------------------------------------------------
# test_fix_abs_title_spacing
# ---------------------------------------------------------------------------

def test_fix_abs_title_spacing(lnu_cfg):
    """After fix_abstract_heading, spacing after = abstract_title_after_pt * 20.

    LNU profile sets abstract_title_after_pt=0, so after=0 and line=360.
    """
    p = _make_paragraph("摘要", sz=28)
    # Add a pre-existing spacing after with a wrong value
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("after"), "220")

    fix_abstract_heading(p, lnu_cfg, "abstract_cn")

    spacing_elems = p.findall(".//w:spacing", NSMAP)
    assert spacing_elems, "No w:spacing found after fix"
    after_val = spacing_elems[0].get(_w("after"))
    line_val = spacing_elems[0].get(_w("line"))
    assert after_val is not None, "w:spacing/@w:after not set"
    expected_after = int(lnu_cfg.get("abstract_title_after_pt", 0) * 20)
    assert int(after_val) == expected_after, (
        f"Expected after={expected_after}, got {after_val}"
    )
    assert line_val == "360", f"Expected line=360, got {line_val}"


# ---------------------------------------------------------------------------
# test_fix_kw_no_bold
# ---------------------------------------------------------------------------

def test_fix_kw_no_bold(lnu_cfg):
    """fix_abstract_section with kw_bold=False removes or omits <w:b> on keyword runs."""
    assert lnu_cfg.get("kw_bold") is False

    # Build a paragraph "关键词：..." with a bold run
    p = _make_paragraph("关键词：测试；审计；方法", bold=True)
    doc = _make_doc_root(p)

    fix_abstract_section(doc, lnu_cfg)

    # After fix, no run in the keyword paragraph should have an active <w:b>
    for r in p.findall(".//w:r", NSMAP):
        r_pr = r.find("w:rPr", NSMAP)
        if r_pr is None:
            continue
        b_elem = r_pr.find("w:b", NSMAP)
        if b_elem is not None:
            val = b_elem.get(_w("val"), "1")
            assert val in ("0", "false", "False", "off"), (
                f"Bold element still active after fix with kw_bold=False: val={val!r}"
            )


# ---------------------------------------------------------------------------
# test_fix_ref_line_spacing
# ---------------------------------------------------------------------------

def test_fix_ref_line_spacing(lnu_cfg):
    """fix_reference_paragraph sets spacing line to ref_line_spacing (360 for LNU)."""
    assert lnu_cfg.get("ref_line_spacing") == 360

    p = _make_paragraph("[1] Some reference text.")
    # Set wrong line spacing initially
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "240")
    spacing.set(_w("lineRule"), "auto")

    fix_reference_paragraph(p, cfg=lnu_cfg)

    spacing_elems = p.findall(".//w:spacing", NSMAP)
    assert spacing_elems, "No w:spacing found after fix"
    line_val = spacing_elems[0].get(_w("line"))
    before_val = spacing_elems[0].get(_w("before"))
    after_val = spacing_elems[0].get(_w("after"))
    assert line_val == "360", f"Expected line=360, got {line_val!r}"
    assert before_val == "0", f"Expected before=0, got {before_val!r}"
    assert after_val == "0", f"Expected after=0, got {after_val!r}"

    ind_elems = p.findall(".//w:ind", NSMAP)
    assert ind_elems, "No w:ind found after fix"
    hanging_val = ind_elems[0].get(_w("hanging"))
    left_val = ind_elems[0].get(_w("left"))
    assert hanging_val == "420", f"Expected hanging=420, got {hanging_val!r}"
    assert left_val == "420", f"Expected left=420, got {left_val!r}"


def test_fix_reference_paragraph_normalizes_leading_zero_number(lnu_cfg):
    p = _make_paragraph("[01]   Some reference text.")

    fix_reference_paragraph(p, cfg=lnu_cfg)

    assert get_paragraph_text(p) == "[1] Some reference text."


# ---------------------------------------------------------------------------
# test_fix_heading_defaults
# ---------------------------------------------------------------------------

def test_fix_heading_defaults():
    """HEADING_SPACING_DEFAULTS has before=120 and after=120 for all four levels."""
    for level in ("h1", "h2", "h3", "h4"):
        assert level in HEADING_SPACING_DEFAULTS, f"Level {level} missing from defaults"
        defaults = HEADING_SPACING_DEFAULTS[level]
        assert defaults["before"] == 120, (
            f"{level} before={defaults['before']}, expected 120"
        )
        assert defaults["after"] == 120, (
            f"{level} after={defaults['after']}, expected 120"
        )


# ---------------------------------------------------------------------------
# test_fix_lnu_title01_converts
# ---------------------------------------------------------------------------

def test_fix_lnu_title01_converts():
    """fix_lnu_title01 converts a single '摘要' paragraph to '摘  要'."""
    p = _make_paragraph("摘要")
    doc = _make_doc_root(p)

    count = fix_lnu_title01(doc, {})

    assert count >= 1, "Expected at least one conversion"
    t_elems = p.findall(".//w:t", NSMAP)
    texts = [t.text for t in t_elems if t.text]
    assert any("摘  要" in text for text in texts), (
        f"Expected '摘  要' in text elements, got {texts}"
    )


def test_fix_lnu_s03_matches_allowed_titles_by_normalized_text():
    title = _make_paragraph("致　　谢")
    doc = _make_doc_root(title)

    count = fix_lnu_s03(doc, {}, allowed_titles={"致谢"})

    assert count == 1
    page_break = title.find("w:pPr/w:pageBreakBefore", NSMAP)
    assert page_break is not None


def test_fix_heading_paragraph_uses_tnr_for_ascii(lnu_cfg, lnu_runtime):
    p = _make_paragraph("1.2 TP53 与 Akt1")
    fix_heading_paragraph(p, "left", False, cfg=lnu_cfg, runtime=lnu_runtime)


def test_fix_sp_cjk_latin_handles_empty_intermediate_run():
    p = ET.Element(_w("p"))
    first = ET.SubElement(p, _w("r"))
    first_t = ET.SubElement(first, _w("t"))
    first_t.text = "相互作用"
    empty_run = ET.SubElement(p, _w("r"))
    ET.SubElement(empty_run, _w("t")).text = ""
    third = ET.SubElement(p, _w("r"))
    ET.SubElement(third, _w("t")).text = "TNF"

    changed = fix_sp_cjk_latin(p)

    assert changed is True
    text = "".join(t.text or "" for t in p.findall(".//w:t", NSMAP))
    assert text == "相互作用 TNF"


def test_remove_existing_toc_artifacts_removes_visible_toc_block():
    title = _make_paragraph("目  录")
    entry = _make_paragraph("摘  要\t2")
    body_heading = _make_paragraph("1 序言")
    doc = _make_doc_root(title, entry, body_heading)

    removed = remove_existing_toc_artifacts(doc)

    assert removed == 2
    body = doc.find(f"{{{W}}}body")
    assert body is not None
    texts = [get_paragraph_text(p).strip() for p in body.findall(_w("p"))]
    assert texts == ["1 序言"]


def test_remove_existing_toc_artifacts_removes_field_based_toc_block():
    title = _make_paragraph("目  录")
    entry = ET.Element(_w("p"))
    p_pr = ET.SubElement(entry, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "8")
    r1 = ET.SubElement(entry, _w("r"))
    instr = ET.SubElement(r1, _w("instrText"))
    instr.text = ' HYPERLINK \\l "_Toc123" '
    r2 = ET.SubElement(entry, _w("r"))
    t2 = ET.SubElement(r2, _w("t"))
    t2.text = "摘  要"
    body_heading = _make_paragraph("1 序言")
    doc = _make_doc_root(title, entry, body_heading)

    removed = remove_existing_toc_artifacts(doc)

    assert removed == 2
    body = doc.find(f"{{{W}}}body")
    assert body is not None
    texts = [get_paragraph_text(p).strip() for p in body.findall(_w("p"))]
    assert texts == ["1 序言"]


def test_remove_paragraphs_from_body_removes_sdt_container_when_it_contains_targets():
    title = _make_paragraph("目  录")
    entry = _make_paragraph("摘  要\t2")
    body_heading = _make_paragraph("1 序言")
    doc = _make_doc_root(body_heading)
    body = doc.find(f"{{{W}}}body")
    assert body is not None
    body.remove(body_heading)
    sdt = ET.SubElement(body, _w("sdt"))
    content = ET.SubElement(sdt, _w("sdtContent"))
    content.append(title)
    content.append(entry)
    body.append(body_heading)

    remove_paragraphs_from_body(doc, [title, entry])

    children = list(body)
    assert len(children) == 1
    assert children[0] is body_heading


def test_normalize_lnu_preface_heading_numbering_uses_zero_preface():
    preface = _make_paragraph("1 序言")
    preface_h2 = _make_paragraph("1.1 研究背景")
    preface_h3 = _make_paragraph("1.1.1 研究现状")
    chapter1 = _make_paragraph("2 材料与方法")
    chapter1_h2 = _make_paragraph("2.1 实验设计")
    doc = _make_doc_root(preface, preface_h2, preface_h3, chapter1, chapter1_h2)

    for paragraph, style_id in (
        (preface, "Heading1"),
        (preface_h2, "Heading2"),
        (preface_h3, "Heading3"),
        (chapter1, "Heading1"),
        (chapter1_h2, "Heading2"),
    ):
        p_pr = ET.SubElement(paragraph, _w("pPr"))
        p_style = ET.SubElement(p_pr, _w("pStyle"))
        p_style.set(_w("val"), style_id)

    style_map = {
        "Heading1": {"outlineLvl": 0, "sz": 30, "bold": False, "jc": "center", "name": "heading 1", "basedOn": None},
        "Heading2": {"outlineLvl": 1, "sz": 30, "bold": False, "jc": "left", "name": "heading 2", "basedOn": None},
        "Heading3": {"outlineLvl": 2, "sz": 24, "bold": False, "jc": "left", "name": "heading 3", "basedOn": None},
    }

    changed = normalize_lnu_preface_heading_numbering([preface, preface_h2, preface_h3, chapter1, chapter1_h2], style_map)

    assert changed == 5
    assert get_paragraph_text(preface).strip() == "序  言"
    assert get_paragraph_text(preface_h2).strip() == "0.1 研究背景"
    assert get_paragraph_text(preface_h3).strip() == "0.1.1 研究现状"
    assert get_paragraph_text(chapter1).strip() == "1 材料与方法"
    assert get_paragraph_text(chapter1_h2).strip() == "1.1 实验设计"


def test_normalize_lnu_preface_heading_numbering_skips_table_paragraphs():
    preface = _make_paragraph("1 序言")
    preface_p = _make_paragraph("1.1 研究背景")
    table_like = _make_paragraph("3 1,4-Diaminobutane")
    chapter1 = _make_paragraph("2 材料与方法")
    body = [preface, preface_p, table_like, chapter1]
    for paragraph, style_id in (
        (preface, "Heading1"),
        (preface_p, "Heading2"),
        (table_like, "Heading1"),
        (chapter1, "Heading1"),
    ):
        p_pr = ET.SubElement(paragraph, _w("pPr"))
        p_style = ET.SubElement(p_pr, _w("pStyle"))
        p_style.set(_w("val"), style_id)

    style_map = {
        "Heading1": {"outlineLvl": 0, "sz": 30, "bold": False, "jc": "center", "name": "heading 1", "basedOn": None},
        "Heading2": {"outlineLvl": 1, "sz": 30, "bold": False, "jc": "left", "name": "heading 2", "basedOn": None},
    }

    changed = normalize_lnu_preface_heading_numbering(body, style_map, table_para_ids={id(table_like)})

    assert changed == 3
    assert get_paragraph_text(table_like).strip() == "3 1,4-Diaminobutane"
    assert get_paragraph_text(chapter1).strip() == "1 材料与方法"


def test_fix_heading_paragraph_forces_heading_style_and_clears_char_indent(lnu_cfg, lnu_runtime):
    p = _make_paragraph("0.1 标题")
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "11")
    ind = ET.SubElement(p_pr, _w("ind"))
    ind.set(_w("firstLine"), "0")
    ind.set(_w("firstLineChars"), "200")
    fix_heading_paragraph(p, "left", False, cfg=lnu_cfg, runtime=lnu_runtime)

    updated_style = p.find("w:pPr/w:pStyle", NSMAP)
    updated_ind = p.find("w:pPr/w:ind", NSMAP)
    assert updated_style is not None
    assert updated_style.get(_w("val")) != "11"
    assert updated_ind is not None
    assert updated_ind.get(_w("firstLine")) == "0"
    assert updated_ind.get(_w("firstLineChars")) is None


def test_renumber_body_headings_rewrites_zero_based_intro():
    h1 = _make_paragraph("0 引言")
    h1_pr = ET.SubElement(h1, _w("pPr"))
    style1 = ET.SubElement(h1_pr, _w("pStyle"))
    style1.set(_w("val"), "2")

    h2 = _make_paragraph("0.1 研究背景")
    h2_pr = ET.SubElement(h2, _w("pPr"))
    style2 = ET.SubElement(h2_pr, _w("pStyle"))
    style2.set(_w("val"), "3")

    h3 = _make_paragraph("0.1.1 研究基础")
    h3_pr = ET.SubElement(h3, _w("pPr"))
    style3 = ET.SubElement(h3_pr, _w("pStyle"))
    style3.set(_w("val"), "4")

    h1b = _make_paragraph("1 材料与方法")
    h1b_pr = ET.SubElement(h1b, _w("pPr"))
    style1b = ET.SubElement(h1b_pr, _w("pStyle"))
    style1b.set(_w("val"), "2")

    paragraphs = [h1, h2, h3, h1b]
    style_map = {
        "2": {"outlineLvl": 0, "sz": 32, "bold": False, "jc": "center", "basedOn": None},
        "3": {"outlineLvl": 1, "sz": 28, "bold": False, "jc": "left", "basedOn": None},
        "4": {"outlineLvl": 2, "sz": 24, "bold": False, "jc": "left", "basedOn": None},
    }

    renumber_body_headings(paragraphs, style_map)

    assert fix_thesis.get_paragraph_text(h1).strip() == "1 引言"
    assert fix_thesis.get_paragraph_text(h2).strip() == "1.1 研究背景"
    assert fix_thesis.get_paragraph_text(h3).strip() == "1.1.1 研究基础"
    assert fix_thesis.get_paragraph_text(h1b).strip() == "2 材料与方法"


def test_fix_cover_layout_scales_cover_image():
    p = ET.Element(_w("p"))
    drawing = ET.SubElement(p, _w("drawing"))
    inline = ET.SubElement(
        drawing,
        "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline",
    )
    extent = ET.SubElement(
        inline,
        "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent",
    )
    extent.set("cx", "4686300")
    extent.set("cy", "5339715")
    graphic = ET.SubElement(inline, "{http://schemas.openxmlformats.org/drawingml/2006/main}graphic")
    graphic_data = ET.SubElement(
        graphic,
        "{http://schemas.openxmlformats.org/drawingml/2006/main}graphicData",
    )
    pic = ET.SubElement(
        graphic_data,
        "{http://schemas.openxmlformats.org/drawingml/2006/picture}pic",
    )
    sp_pr = ET.SubElement(pic, "{http://schemas.openxmlformats.org/drawingml/2006/picture}spPr")
    xfrm = ET.SubElement(sp_pr, "{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm")
    inner_extent = ET.SubElement(xfrm, "{http://schemas.openxmlformats.org/drawingml/2006/main}ext")
    inner_extent.set("cx", "4686300")
    inner_extent.set("cy", "5339715")
    doc = _make_doc_root(p)

    fix_cover_layout(doc, {id(p): "cover"})

    assert int(extent.get("cx")) <= fix_thesis.COVER_IMAGE_MAX_CX
    assert int(extent.get("cy")) <= fix_thesis.COVER_IMAGE_MAX_CY
    assert int(inner_extent.get("cx")) <= fix_thesis.COVER_IMAGE_MAX_CX
    assert int(inner_extent.get("cy")) <= fix_thesis.COVER_IMAGE_MAX_CY


def test_fix_abstract_section_formats_english_keywords():
    p = _make_paragraph("Key words: alpha; beta; gamma")
    doc = _make_doc_root(p)

    fix_abstract_section(doc, {"ack_font": "仿宋"})

    runs = p.findall("w:r", NSMAP)
    texts = ["".join(t.text for t in r.findall(".//w:t", NSMAP) if t.text) for r in runs]
    sizes = [r.find("w:rPr/w:sz", NSMAP).get(_w("val")) for r in runs]
    bold_flags = [r.find("w:rPr/w:b", NSMAP) is not None for r in runs]
    jc = p.find("w:pPr/w:jc", NSMAP)

    assert texts == ["Key words:", " ", "alpha; beta; gamma"]
    assert sizes == ["28", "28", "24"]
    assert bold_flags == [True, False, False]
    assert jc is not None and jc.get(_w("val")) == "center"


def test_fix_abstract_section_accepts_spaced_cn_title():
    p = _make_paragraph("摘  要", sz=28)
    doc = _make_doc_root(p)

    fix_abstract_section(doc, {"ack_font": "仿宋", "abstract_title_size": 32, "abstract_title_after_pt": 0})

    sz_elem = p.find(".//w:sz", NSMAP)
    assert sz_elem is not None
    assert sz_elem.get(_w("val")) == "32"


def test_fix_lnu_abs03_accepts_title_case_abstract():
    title = _make_paragraph("Abstract")
    body = _make_paragraph("This is the abstract body.", sz=28)
    doc = _make_doc_root(title, body)

    fixed = fix_lnu_abs03(doc, {})

    assert fixed == 1
    spacing = body.find("w:pPr/w:spacing", NSMAP)
    assert spacing is not None
    assert spacing.get(_w("line")) == "240"
    sz_elem = body.find(".//w:sz", NSMAP)
    assert sz_elem is not None
    assert sz_elem.get(_w("val")) == "24"


def test_fix_abstract_body_uses_section_specific_english_config():
    p = _make_paragraph("This is the abstract body.", sz=28)
    cfg = {
        "abstract_en_body_font": "Arial",
        "abstract_en_body_ascii_font": "Arial",
        "abstract_en_body_size": 22,
        "abstract_en_body_line": 300,
        "abstract_en_body_indent": 360,
    }

    fix_abstract_body(p, cfg, "abstract_en")

    spacing = p.find("w:pPr/w:spacing", NSMAP)
    ind = p.find("w:pPr/w:ind", NSMAP)
    r_fonts = p.find(".//w:r/w:rPr/w:rFonts", NSMAP)
    sz_elem = p.find(".//w:r/w:rPr/w:sz", NSMAP)

    assert spacing is not None and spacing.get(_w("line")) == "300"
    assert ind is not None and ind.get(_w("firstLine")) == "360"
    assert r_fonts is not None and r_fonts.get(_w("ascii")) == "Arial"
    assert sz_elem is not None and sz_elem.get(_w("val")) == "22"


def test_fix_body_paragraph_uses_profile_body_settings():
    p = _make_paragraph("这是正文。", sz=28)
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "240")

    fix_body_paragraph(
        p,
        cfg={
            "body_font": "仿宋",
            "body_ascii_font": "Arial",
            "body_size": 26,
            "body_line": 420,
            "body_indent": 600,
            "body_alignment": "left",
        },
    )

    spacing = p.find("w:pPr/w:spacing", NSMAP)
    ind = p.find("w:pPr/w:ind", NSMAP)
    jc = p.find("w:pPr/w:jc", NSMAP)
    r_fonts = p.find(".//w:r/w:rPr/w:rFonts", NSMAP)
    sz_elem = p.find(".//w:r/w:rPr/w:sz", NSMAP)

    assert spacing is not None and spacing.get(_w("line")) == "420"
    assert ind is not None and ind.get(_w("firstLine")) == "600"
    assert jc is not None and jc.get(_w("val")) == "left"
    assert r_fonts is not None and r_fonts.get(_w("eastAsia")) == "仿宋"
    assert r_fonts.get(_w("ascii")) == "Arial"
    assert sz_elem is not None and sz_elem.get(_w("val")) == "26"


def test_fix_body_paragraph_clears_heading_style_when_treated_as_body():
    p = _make_paragraph("这是一个被误套用标题样式的正文句子。", sz=28)
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "Heading1")

    fix_body_paragraph(
        p,
        cfg={
            "body_font": "宋体",
            "body_ascii_font": "Times New Roman",
            "body_size": 24,
            "body_line": 360,
            "body_indent": 480,
            "body_alignment": "both",
        },
        style_map={
            "Heading1": {"outlineLvl": 0, "name": "heading 1", "basedOn": None},
        },
    )

    assert p.find("w:pPr/w:pStyle", NSMAP) is None


def test_fix_lnu_s03_adds_page_break_before_appendix():
    appendix = _make_paragraph("附  录")
    doc = _make_doc_root(appendix)

    fixed = fix_lnu_s03(doc, {})

    assert fixed == 1
    pb = appendix.find("w:pPr/w:pageBreakBefore", NSMAP)
    assert pb is not None


def test_fix_lnu_s03_allowed_titles_uses_normalized_matching():
    acknowledgement = _make_paragraph("致谢")
    references = _make_paragraph("参考文献")
    doc = _make_doc_root(acknowledgement, references)

    fixed = fix_lnu_s03(doc, {}, allowed_titles={"致  谢"})

    ack_pb = acknowledgement.find("w:pPr/w:pageBreakBefore", NSMAP)
    ref_pb = references.find("w:pPr/w:pageBreakBefore", NSMAP)
    assert fixed == 1
    assert ack_pb is not None
    assert ref_pb is None


def test_fix_insert_toc_removes_raw_toc_block_and_inserts_before_body(lnu_runtime):
    cover = _make_paragraph("封面信息")
    abstract_title = _make_paragraph("Abstract")
    abstract_body = _make_paragraph("英文摘要内容。")
    keywords = _make_paragraph("Key words: alpha；beta目  录")
    raw_toc_begin = _make_paragraph(' TOC \\o "1-3" \\h \\z \\u ')
    raw_toc_entry = _make_paragraph(' HYPERLINK \\l "_Toc1" 第1章 绪论\t1')
    body_h1 = _make_paragraph("第1章 绪论")
    body_h2 = _make_paragraph("1.1 研究背景")
    body_para = _make_paragraph("这是正文。")
    doc = _make_doc_root(
        cover,
        abstract_title,
        abstract_body,
        keywords,
        raw_toc_begin,
        raw_toc_entry,
        body_h1,
        body_h2,
        body_para,
    )

    fix_insert_toc(doc, {"toc_auto": True, "toc_title": "目录", "toc_max_level": 3}, runtime=lnu_runtime)

    body = doc.find("w:body", NSMAP)
    texts = [get_paragraph_text(p).strip() for p in body.findall("w:p", NSMAP)]
    model = build_document_model(doc, {})
    body_texts = [node.text.strip() for node in model.section_nodes("body", effective=False) if node.text.strip()]

    assert "Key words: alpha；beta" in texts
    assert all('HYPERLINK \\l "_Toc1"' not in text for text in texts)
    assert texts.index("目  录") > texts.index("Key words: alpha；beta")
    assert texts.index("目  录") < texts.index("第1章 绪论")
    assert not any(text.endswith("1") and "Abstract" in text for text in texts)
    assert not any(text.endswith("1") and "第1章" in text for text in texts)
    assert body_texts[0] == "第1章 绪论"
    toc_title = next(p for p in body.findall("w:p", NSMAP) if get_paragraph_text(p).strip() == "目  录")
    page_break_before = toc_title.find("w:pPr/w:pageBreakBefore", NSMAP)
    assert page_break_before is not None and page_break_before.get(_w("val")) in {"1", "true"}


def test_fix_insert_toc_ignores_numeric_body_style_ids(lnu_runtime):
    body_h1 = _make_paragraph("第1章 绪论")
    body_h1_pr = ET.SubElement(body_h1, _w("pPr"))
    body_h1_style = ET.SubElement(body_h1_pr, _w("pStyle"))
    body_h1_style.set(_w("val"), "2")

    body_h2 = _make_paragraph("1.1 研究背景")
    body_h2_pr = ET.SubElement(body_h2, _w("pPr"))
    body_h2_style = ET.SubElement(body_h2_pr, _w("pStyle"))
    body_h2_style.set(_w("val"), "4")

    body_para = _make_paragraph("这是正文，不应进入目录。")
    body_ppr = ET.SubElement(body_para, _w("pPr"))
    body_style = ET.SubElement(body_ppr, _w("pStyle"))
    body_style.set(_w("val"), "3")
    doc = _make_doc_root(body_h1, body_h2, body_para)
    style_map = {
        "2": {"outlineLvl": 0, "sz": 32, "bold": False, "jc": "center", "basedOn": None},
        "3": {"outlineLvl": 9, "sz": 24, "bold": None, "jc": "both", "basedOn": None},
        "4": {"outlineLvl": 1, "sz": 28, "bold": False, "jc": "left", "basedOn": None},
    }

    fix_insert_toc(
        doc,
        {"toc_auto": True, "toc_title": "目录", "toc_max_level": 3},
        style_map=style_map,
        runtime=lnu_runtime,
    )

    body = doc.find("w:body", NSMAP)
    toc_style_ids = []
    for p_elem in body.findall("w:p", NSMAP):
        p_style = p_elem.find("w:pPr/w:pStyle", NSMAP)
        style_id = p_style.get(_w("val")) if p_style is not None else None
        if style_id:
            toc_style_ids.append(style_id)

    assert "TOCHeading" in toc_style_ids
    assert "TOCField" in toc_style_ids
    assert "TOCEnd" in toc_style_ids
    assert "TOCPageBreak" in toc_style_ids
    assert not any(style_id in {"TOC1", "TOC2", "TOC3"} for style_id in toc_style_ids)
    assert any(get_paragraph_text(p).strip() == "这是正文，不应进入目录。" for p in body.findall("w:p", NSMAP))


def test_fix_insert_toc_moves_misplaced_english_keywords_back_before_toc(lnu_runtime):
    abstract_title = _make_paragraph("Abstract")
    abstract_body = _make_paragraph("英文摘要内容。")
    empty_keywords = _make_paragraph("")
    empty_keywords_pr = ET.SubElement(empty_keywords, _w("pPr"))
    empty_keywords_style = ET.SubElement(empty_keywords_pr, _w("pStyle"))
    empty_keywords_style.set(_w("val"), "58")
    raw_toc_begin = _make_paragraph(' TOC \\o "1-3" \\h \\z \\u ')
    raw_toc_entry = _make_paragraph(' HYPERLINK \\l "_Toc1" 第1章 绪论\t1')
    misplaced_keywords = _make_paragraph("Keywords: deer skin gelatin; gel strength")
    misplaced_keywords_pr = ET.SubElement(misplaced_keywords, _w("pPr"))
    misplaced_keywords_style = ET.SubElement(misplaced_keywords_pr, _w("pStyle"))
    misplaced_keywords_style.set(_w("val"), "2")
    ET.SubElement(misplaced_keywords_pr, _w("pageBreakBefore")).set(_w("val"), "1")
    body_h1 = _make_paragraph("第1章 绪论")
    doc = _make_doc_root(
        abstract_title,
        abstract_body,
        empty_keywords,
        raw_toc_begin,
        raw_toc_entry,
        misplaced_keywords,
        body_h1,
    )

    fix_insert_toc(
        doc,
        {"toc_auto": True, "toc_title": "目录", "toc_max_level": 3},
        style_map={},
        runtime=lnu_runtime,
    )

    body = doc.find("w:body", NSMAP)
    texts = [get_paragraph_text(p).strip() for p in body.findall("w:p", NSMAP)]
    moved_para = next(p for p in body.findall("w:p", NSMAP) if "Keywords:" in get_paragraph_text(p))
    moved_style = moved_para.find("w:pPr/w:pStyle", NSMAP)

    assert texts.index("Keywords: deer skin gelatin; gel strength") < texts.index("目  录")
    assert texts.index("Keywords: deer skin gelatin; gel strength") > texts.index("英文摘要内容。")
    assert moved_style is not None and moved_style.get(_w("val")) == "58"
    assert moved_para.find("w:pPr/w:pageBreakBefore", NSMAP) is None


def test_normalize_frontmatter_page_sections_moves_roman_section_break_to_pre_body():
    cn_title = _make_paragraph("摘  要")
    cn_body = _make_paragraph("中文摘要。")
    cn_keywords = _make_paragraph("关键词：测试；修复")
    abstract_break = _make_paragraph("")
    _append_sect_pr(abstract_break, "upperRoman", start=1)
    en_title = _make_paragraph("Abstract")
    en_body = _make_paragraph("English abstract.")
    en_keywords = _make_paragraph("Keywords: alpha; beta")
    toc_title = _make_paragraph("目  录")
    toc_field = _make_paragraph("")
    toc_field_pr = ET.SubElement(toc_field, _w("pPr"))
    toc_field_style = ET.SubElement(toc_field_pr, _w("pStyle"))
    toc_field_style.set(_w("val"), "TOCField")
    toc_field_run = toc_field.find("w:r", NSMAP)
    instr = ET.SubElement(toc_field_run, _w("instrText"))
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    toc_end = _make_paragraph("")
    toc_end_pr = ET.SubElement(toc_end, _w("pPr"))
    toc_end_style = ET.SubElement(toc_end_pr, _w("pStyle"))
    toc_end_style.set(_w("val"), "TOCEnd")
    toc_page_break = _make_paragraph("")
    toc_page_break_pr = ET.SubElement(toc_page_break, _w("pPr"))
    toc_page_break_style = ET.SubElement(toc_page_break_pr, _w("pStyle"))
    toc_page_break_style.set(_w("val"), "TOCPageBreak")
    body_h1 = _make_paragraph("序 言")
    doc = _make_doc_root(
        cn_title,
        cn_body,
        cn_keywords,
        abstract_break,
        en_title,
        en_body,
        en_keywords,
        toc_title,
        toc_field,
        toc_end,
        toc_page_break,
        body_h1,
    )
    body = doc.find("w:body", NSMAP)
    body_sect_pr = ET.SubElement(body, _w("sectPr"))
    body_pg_num = ET.SubElement(body_sect_pr, _w("pgNumType"))
    body_pg_num.set(_w("fmt"), "decimal")
    body_pg_num.set(_w("start"), "1")

    changed = normalize_frontmatter_page_sections(doc, {})

    assert changed > 0
    moved_sect_pr = toc_page_break.find("w:pPr/w:sectPr", NSMAP)
    assert moved_sect_pr is not None
    moved_pg_num = moved_sect_pr.find("w:pgNumType", NSMAP)
    assert moved_pg_num is not None
    assert moved_pg_num.get(_w("fmt")) == "upperRoman"
    assert moved_pg_num.get(_w("start")) == "1"
    assert abstract_break.find("w:pPr/w:sectPr", NSMAP) is None

    final_pg_num = body.find("w:sectPr/w:pgNumType", NSMAP)
    assert final_pg_num is not None
    assert final_pg_num.get(_w("fmt")) == "decimal"
    assert final_pg_num.get(_w("start")) == "1"


def test_fix_lnu_abs03_does_not_touch_toc_entries(lnu_cfg):
    abstract_title = _make_paragraph("Abstract", sz=32)
    abstract_body = _make_paragraph("  Example abstract body.", sz=32)
    keywords = _make_paragraph("Key words: alpha; beta", sz=24)
    toc_title = _make_paragraph("目  录", sz=32)
    toc_entry = _make_paragraph("Abstract\t1", sz=32)
    toc_ppr = ET.SubElement(toc_entry, _w("pPr"))
    toc_spacing = ET.SubElement(toc_ppr, _w("spacing"))
    toc_spacing.set(_w("line"), "276")
    toc_spacing.set(_w("after"), "100")
    doc = _make_doc_root(abstract_title, abstract_body, keywords, toc_title, toc_entry)

    fix_lnu_abs03(doc, lnu_cfg)

    body_run_sz = abstract_body.find(".//w:sz", NSMAP)
    toc_spacing = toc_entry.find("w:pPr/w:spacing", NSMAP)
    assert body_run_sz is not None and body_run_sz.get(_w("val")) == "24"
    assert toc_spacing is not None and toc_spacing.get(_w("line")) == "276"
    assert toc_spacing.get(_w("after")) == "100"


def test_fix_lnu_ack01_skips_acknowledgement_titles(lnu_cfg):
    body_h1 = _make_paragraph("第1章 绪论", sz=30)
    ack_title = _make_paragraph("致  谢", sz=32)
    ack_h2 = _make_paragraph("1.1 致谢说明", sz=28)
    ack_body = _make_paragraph("感谢内容。", sz=32)
    doc = _make_doc_root(body_h1, ack_title, ack_h2, ack_body)

    fix_lnu_ack01(doc, lnu_cfg)

    title_sz = ack_h2.find(".//w:sz", NSMAP)
    body_sz = ack_body.find(".//w:sz", NSMAP)
    assert title_sz is not None and title_sz.get(_w("val")) == "28"
    assert body_sz is not None and body_sz.get(_w("val")) == "24"


def test_inject_template_components_copies_missing_styles(tmp_path):
    tool_root = tmp_path / "tool"
    template_dir = tool_root / "config" / "templates" / "demo"
    target_word_dir = tmp_path / "work" / "word"
    template_dir.mkdir(parents=True)
    target_word_dir.mkdir(parents=True)

    (template_dir / "styles.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        encoding="utf-8",
    )

    original_tool_root = fix_thesis.TOOL_ROOT
    try:
        fix_thesis.TOOL_ROOT = str(tool_root)
        inject_template_components(str(tmp_path / "work"), "demo")
    finally:
        fix_thesis.TOOL_ROOT = original_tool_root

    copied = target_word_dir / "styles.xml"
    assert copied.exists()


# ---------------------------------------------------------------------------
# test_fix_lnu_tb03_fixes_spacing
# ---------------------------------------------------------------------------

def test_fix_lnu_tb03_fixes_spacing():
    """fix_lnu_tb03 sets line=240 on a table cell paragraph with line=360."""
    # Build: <w:tbl><w:tr><w:tc><w:p><w:pPr><w:spacing line=360></w:pPr></w:p></w:tc></w:tr></w:tbl>
    tbl = ET.Element(_w("tbl"))
    tr = ET.SubElement(tbl, _w("tr"))
    tc = ET.SubElement(tr, _w("tc"))
    p = ET.SubElement(tc, _w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "360")
    spacing.set(_w("lineRule"), "auto")

    doc = ET.Element(_w("document"))
    body = ET.SubElement(doc, _w("body"))
    body.append(tbl)

    count = fix_lnu_tb03(doc, {})

    assert count >= 1, "Expected at least one paragraph to be fixed"
    line_val = spacing.get(_w("line"))
    assert line_val == "240", f"Expected line=240 after fix, got {line_val!r}"
