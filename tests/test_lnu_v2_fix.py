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
    cleanup_frontmatter_redundant_page_breaks,
    HEADING_SPACING_DEFAULTS,
    fix_abstract_body,
    fix_abstract_heading,
    fix_abstract_section,
    fix_body_paragraph,
    fix_half_width_punct_in_cjk,
    fix_sp_cjk_latin,
    fix_cover_layout,
    fix_heading_paragraph,
    fix_insert_toc,
    inject_template_components,
    fix_lnu_abs03,
    fix_lnu_ack01,
    fix_lnu_s03,
    fix_lnu_title01,
    fix_remove_hidden_page_number_artifacts,
    fix_lnu_tb03,
    normalize_equation_explanation_symbols,
    normalize_lnu_preface_heading_numbering,
    normalize_toc_entry_paragraphs,
    protect_object_blocks_from_pagination,
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


def _make_hidden_page_field_paragraph(display_text: str = "—21—") -> ET.Element:
    paragraph = ET.Element(_w("p"))
    p_pr = ET.SubElement(paragraph, _w("pPr"))
    ET.SubElement(p_pr, _w("spacing")).set(_w("line"), "360")

    def _hidden_run():
        run = ET.SubElement(paragraph, _w("r"))
        r_pr = ET.SubElement(run, _w("rPr"))
        ET.SubElement(r_pr, _w("vanish"))
        return run

    if display_text.startswith("—"):
        ET.SubElement(_hidden_run(), _w("t")).text = "—"
    fld_begin = ET.SubElement(_hidden_run(), _w("fldChar"))
    fld_begin.set(_w("fldCharType"), "begin")
    ET.SubElement(_hidden_run(), _w("instrText")).text = " PAGE "
    if any(ch.isdigit() for ch in display_text):
        fld_sep = ET.SubElement(_hidden_run(), _w("fldChar"))
        fld_sep.set(_w("fldCharType"), "separate")
        digits = "".join(ch for ch in display_text if ch.isdigit())
        ET.SubElement(_hidden_run(), _w("t")).text = digits
    fld_end = ET.SubElement(_hidden_run(), _w("fldChar"))
    fld_end.set(_w("fldCharType"), "end")
    if display_text.endswith("—") or display_text.endswith("-"):
        ET.SubElement(_hidden_run(), _w("t")).text = display_text[-1]
    return paragraph


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


def test_parse_heading_chapter_number_prefers_real_chapter_titles():
    assert fix_thesis._parse_heading_chapter_number("第2章 实验结果与分析") == 2
    assert fix_thesis._parse_heading_chapter_number("23 S rRNA") is None


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

    runs = p.findall("w:r", NSMAP)
    texts = ["".join(t.text for t in r.findall(".//w:t", NSMAP) if t.text) for r in runs]
    fonts = [r.find("w:rPr/w:rFonts", NSMAP).get(_w("eastAsia")) for r in runs]
    sizes = [r.find("w:rPr/w:sz", NSMAP).get(_w("val")) for r in runs]

    assert texts == ["关键词", "：测试；审计；方法"]
    assert fonts == ["黑体", "宋体"]
    assert sizes == ["24", "24"]

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

    normalized = get_paragraph_text(p)
    assert normalized.startswith("[1]")
    assert "Some reference text." in normalized


def test_fix_half_width_punct_in_cjk_converts_body_only_and_skips_caption_and_reference():
    body = _make_paragraph("这是正文,示例.内容")
    caption = _make_paragraph("图1,实验流程.示意")
    reference = _make_paragraph("[1] 张三,论文题目.出版社")
    document = _make_doc_root(body, caption, reference)

    fix_half_width_punct_in_cjk(
        document,
        style_map={},
        allowed_ids={id(body), id(caption), id(reference)},
    )

    assert get_paragraph_text(body) == "这是正文，示例。内容"
    assert get_paragraph_text(caption) == "图1,实验流程.示意"
    assert get_paragraph_text(reference) == "[1] 张三,论文题目.出版社"


# ---------------------------------------------------------------------------
# test_fix_heading_defaults
# ---------------------------------------------------------------------------

def test_fix_heading_defaults():
    """Heading spacing defaults should exist for all levels and remain non-negative ints."""
    for level in ("h1", "h2", "h3", "h4"):
        assert level in HEADING_SPACING_DEFAULTS, f"Level {level} missing from defaults"
        defaults = HEADING_SPACING_DEFAULTS[level]
        assert isinstance(defaults["before"], int)
        assert isinstance(defaults["after"], int)
        assert defaults["before"] >= 0
        assert defaults["after"] >= 0


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


def test_fix_heading_paragraph_clears_existing_page_break_for_non_h1(lnu_cfg, lnu_runtime):
    p = _make_paragraph("2.2.1 正式实验样品得率")
    p_pr = p.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(p, _w("pPr"))
    ET.SubElement(p_pr, _w("pageBreakBefore")).set(_w("val"), "1")

    fix_heading_paragraph(p, "left", True, cfg=lnu_cfg, runtime=lnu_runtime)

    assert p.find("w:pPr/w:pageBreakBefore", NSMAP) is None


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


def test_normalize_lnu_preface_heading_numbering_preserves_chapter_form():
    preface = _make_paragraph("1 序言")
    chapter1 = _make_paragraph("1 第1章 实验材料与方法")
    chapter2 = _make_paragraph("2 第2章 实验结果与分析")
    doc = _make_doc_root(preface, chapter1, chapter2)

    for paragraph, style_id in (
        (preface, "Heading1"),
        (chapter1, "Heading1"),
        (chapter2, "Heading1"),
    ):
        p_pr = ET.SubElement(paragraph, _w("pPr"))
        p_style = ET.SubElement(p_pr, _w("pStyle"))
        p_style.set(_w("val"), style_id)

    style_map = {
        "Heading1": {"outlineLvl": 0, "sz": 30, "bold": False, "jc": "center", "name": "heading 1", "basedOn": None},
    }

    changed = normalize_lnu_preface_heading_numbering([preface, chapter1, chapter2], style_map)

    assert changed == 3
    assert get_paragraph_text(preface).strip() == "序  言"
    assert get_paragraph_text(chapter1).strip() == "第1章 实验材料与方法"
    assert get_paragraph_text(chapter2).strip() == "第2章 实验结果与分析"


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


def test_lnu_compact_text_restores_heading_gap_after_compacting_mixed_text():
    heading = _make_paragraph("1.2 CRISPR 技术基础")

    fix_thesis.fix_lnu_compact_text(heading, restore_heading_gap=True)

    assert fix_thesis.get_paragraph_text(heading) == "1.2 CRISPR技术基础"


def test_fix_cover_layout_preserves_existing_cover_layout():
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
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "520")
    doc = _make_doc_root(p)

    fix_cover_layout(doc, {id(p): "cover"})

    assert extent.get("cx") == "4686300"
    assert extent.get("cy") == "5339715"
    assert inner_extent.get("cx") == "4686300"
    assert inner_extent.get("cy") == "5339715"
    assert spacing.get(_w("line")) == "520"


def test_fix_cover_layout_preserves_lnu_cover_content(lnu_runtime):
    p = _make_paragraph("固定封面文字")
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "520")
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
    doc = _make_doc_root(p)

    fix_cover_layout(doc, {id(p): "cover"}, runtime=lnu_runtime)

    assert spacing.get(_w("line")) == "520"
    assert extent.get("cx") == "4686300"
    assert extent.get("cy") == "5339715"
    assert get_paragraph_text(p) == "固定封面文字"


def test_normalize_equation_explanation_symbols_splits_plain_tokens_to_subscripts():
    p = _make_paragraph("其中，m2 为称量后总质量（g）；m1 为称量前容器质量（g）；m0 为样品初始投料质量（g）。")

    changed = normalize_equation_explanation_symbols(p)

    assert changed is True
    runs = p.findall("w:r", NSMAP)
    texts = ["".join(t.text or "" for t in run.findall(".//w:t", NSMAP)).strip() for run in runs]
    texts = [text for text in texts if text]
    assert "m" in texts
    sub_vals = [
        run.find("w:rPr/w:vertAlign", NSMAP).get(_w("val"))
        for run in runs
        if "".join(t.text or "" for t in run.findall(".//w:t", NSMAP)) in {"0", "1", "2"}
        and run.find("w:rPr/w:vertAlign", NSMAP) is not None
    ]
    assert sub_vals == ["subscript", "subscript", "subscript"]


def test_normalize_equation_explanation_symbols_flattens_inline_math():
    p = ET.Element(_w("p"))
    p.append(_make_run("其中，"))
    o_math = ET.SubElement(p, f"{{{fix_thesis.M_NS}}}oMath")
    s_sub = ET.SubElement(o_math, f"{{{fix_thesis.M_NS}}}sSub")
    e = ET.SubElement(s_sub, f"{{{fix_thesis.M_NS}}}e")
    e_r = ET.SubElement(e, f"{{{fix_thesis.M_NS}}}r")
    e_t = ET.SubElement(e_r, f"{{{fix_thesis.M_NS}}}t")
    e_t.text = "W"
    sub = ET.SubElement(s_sub, f"{{{fix_thesis.M_NS}}}sub")
    sub_r = ET.SubElement(sub, f"{{{fix_thesis.M_NS}}}r")
    sub_t = ET.SubElement(sub_r, f"{{{fix_thesis.M_NS}}}t")
    sub_t.text = "0"
    p.append(_make_run(" 为样品初始干质量（g）。"))

    changed = normalize_equation_explanation_symbols(p)

    assert changed is True
    assert p.find("m:oMath", fix_thesis.MNSMAP) is None
    runs = p.findall("w:r", NSMAP)
    run_texts = ["".join(t.text or "" for t in run.findall(".//w:t", NSMAP)) for run in runs]
    run_texts = [text for text in run_texts if text]
    assert run_texts[:4] == ["其中，", "W", "0", " 为样品初始干质量（g）。"]
    subscript_run = runs[2]
    vert = subscript_run.find("w:rPr/w:vertAlign", NSMAP)
    assert vert is not None and vert.get(_w("val")) == "subscript"
    fonts = subscript_run.find("w:rPr/w:rFonts", NSMAP)
    assert fonts is not None and fonts.get(_w("ascii")) == "Times New Roman"


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


def test_fix_abstract_body_cn_only_keeps_scientific_names_italic():
    p = _make_paragraph("Microbispora triticiradicis 是目标菌株，M. triticiradicis 为简称。", sz=28)
    run = p.find("w:r", NSMAP)
    assert run is not None
    r_pr = run.find("w:rPr", NSMAP)
    italic = ET.SubElement(r_pr, _w("i"))
    italic.set(_w("val"), "1")

    fix_abstract_body(p, {"abstract_body_font": "宋体", "abstract_body_ascii_font": "Times New Roman"}, "abstract_cn")

    runs = p.findall("w:r", NSMAP)
    texts = ["".join(t.text or "" for t in r.findall(".//w:t", NSMAP)) for r in runs]
    italic_vals = [
        (r.find("w:rPr/w:i", NSMAP).get(_w("val")) if r.find("w:rPr/w:i", NSMAP) is not None else None)
        for r in runs
    ]

    assert texts == [
        "Microbispora triticiradicis",
        " 是目标菌株，",
        "M. triticiradicis",
        " 为简称。",
    ]
    assert italic_vals == ["1", "0", "1", "0"]


def test_protect_object_blocks_from_pagination_keeps_figure_and_short_table_together():
    heading = _make_paragraph("第2章 实验结果与分析")
    heading_p_pr = ET.SubElement(heading, _w("pPr"))
    heading_style = ET.SubElement(heading_p_pr, _w("pStyle"))
    heading_style.set(_w("val"), "Heading1")
    image = _make_paragraph("")
    drawing_run = ET.SubElement(image, _w("r"))
    ET.SubElement(drawing_run, _w("drawing"))
    figure_caption = _make_paragraph("图2.1 基因组组装结果")
    figure_note = _make_paragraph("注：A 为主成分分析；B 为聚类结果。")

    table_caption = _make_paragraph("表2.1 编码基因预测统计")
    table = ET.Element(_w("tbl"))
    for row_texts in (("项目", "数值"), ("基因数量", "7118")):
        tr = ET.SubElement(table, _w("tr"))
        for cell_text in row_texts:
            tc = ET.SubElement(tr, _w("tc"))
            p = ET.SubElement(tc, _w("p"))
            p.append(_make_run(cell_text))
    table_note = _make_paragraph("注：统计结果来自组装后注释。")
    document = _make_doc_root(heading, image, figure_caption, figure_note, table_caption, table, table_note)

    protect_object_blocks_from_pagination(document, cfg={"table_continuation_min_rows": 6})

    assert image.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "1"
    assert figure_caption.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "1"
    assert figure_note.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "0"
    assert table_caption.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "1"
    rows = table.findall("w:tr", NSMAP)
    assert rows[0].find("w:trPr/w:cantSplit", NSMAP).get(_w("val")) == "1"
    assert rows[1].find("w:trPr/w:cantSplit", NSMAP).get(_w("val")) == "1"
    first_row_para = rows[0].find(".//w:p", NSMAP)
    second_row_para = rows[1].find(".//w:p", NSMAP)
    assert first_row_para.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "1"
    assert second_row_para.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "1"
    assert table_note.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "0"


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


def test_normalize_toc_entry_paragraphs_applies_latest_lnu_line_spacing():
    toc_title = _make_paragraph("目  录")
    toc_entry = _make_paragraph("第1章 绪论\t1")
    toc_entry_pr = ET.SubElement(toc_entry, _w("pPr"))
    toc_entry_style = ET.SubElement(toc_entry_pr, _w("pStyle"))
    toc_entry_style.set(_w("val"), "TOC1")
    spacing = ET.SubElement(toc_entry_pr, _w("spacing"))
    spacing.set(_w("before"), "240")
    spacing.set(_w("after"), "0")
    spacing.set(_w("line"), "240")
    document = _make_doc_root(toc_title, toc_entry)

    changed = normalize_toc_entry_paragraphs(
        document,
        {},
        {
            "toc_entry_font": "宋体",
            "toc_entry_size": 24,
            "toc_level1_font": "宋体",
            "toc_level1_size": 24,
            "toc_entry_line": 276,
            "toc_level1_after_pt": 5,
        },
    )

    updated_spacing = toc_entry.find("w:pPr/w:spacing", NSMAP)
    assert changed > 0
    assert updated_spacing is not None
    assert updated_spacing.get(_w("before")) == "0"
    assert updated_spacing.get(_w("after")) == "100"
    assert updated_spacing.get(_w("line")) == "276"
    assert updated_spacing.get(_w("lineRule")) == "auto"


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


def test_document_level_prepasses_toc_scope_does_not_repair_abstract_keywords():
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
    runtime = fix_thesis.build_fix_runtime(profile_path="lnu", scopes=["toc"], toc=True)
    ctx = fix_thesis._rebuild_fix_context(doc, {}, runtime)

    updated_ctx, _toc_parts = fix_thesis._apply_document_level_prepasses(ctx)

    body = updated_ctx.document_root.find("w:body", NSMAP)
    texts = [get_paragraph_text(p).strip() for p in body.findall("w:p", NSMAP)]
    current_keywords = next(p for p in body.findall("w:p", NSMAP) if "Keywords:" in get_paragraph_text(p))
    current_style = current_keywords.find("w:pPr/w:pStyle", NSMAP)

    assert texts.index("Keywords: deer skin gelatin; gel strength") < texts.index("目  录")
    assert texts.index("Keywords: deer skin gelatin; gel strength") > texts.index("英文摘要内容。")
    assert current_style is not None and current_style.get(_w("val")) == "2"
    assert current_keywords.find("w:pPr/w:pageBreakBefore", NSMAP) is not None


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


def test_document_level_prepasses_abstract_scope_skips_frontmatter_pagination_normalization():
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
    runtime = fix_thesis.build_fix_runtime(profile_path="lnu", scopes=["abstract"])
    ctx = fix_thesis._rebuild_fix_context(doc, {}, runtime)

    updated_ctx, toc_parts = fix_thesis._apply_document_level_prepasses(ctx)

    updated_body = updated_ctx.document_root.find("w:body", NSMAP)
    assert toc_parts == {}
    assert abstract_break.find("w:pPr/w:sectPr", NSMAP) is not None
    assert toc_page_break.find("w:pPr/w:sectPr", NSMAP) is None
    final_pg_num = updated_body.find("w:sectPr/w:pgNumType", NSMAP)
    assert final_pg_num is not None
    assert final_pg_num.get(_w("fmt")) == "decimal"
    assert final_pg_num.get(_w("start")) == "1"


def test_cleanup_frontmatter_redundant_page_breaks_removes_stray_break_before_frontmatter_title():
    abstract_break = _make_paragraph("")
    abstract_run = ET.SubElement(abstract_break, _w("r"))
    ET.SubElement(abstract_run, _w("br")).set(_w("type"), "page")
    toc_title = _make_paragraph("目  录")
    toc_p_pr = ET.SubElement(toc_title, _w("pPr"))
    ET.SubElement(toc_p_pr, _w("pageBreakBefore")).set(_w("val"), "1")
    body_h1 = _make_paragraph("序  言")
    doc = _make_doc_root(abstract_break, toc_title, body_h1)

    changed = cleanup_frontmatter_redundant_page_breaks(doc, {})

    body = doc.find("w:body", NSMAP)
    paragraphs = body.findall("w:p", NSMAP)
    assert changed == 1
    assert paragraphs[0] is toc_title
    assert toc_title.find("w:pPr/w:pageBreakBefore", NSMAP) is not None


def test_cleanup_frontmatter_redundant_page_breaks_clears_body_heading_page_break_when_break_para_carries_section():
    toc_break = _make_paragraph("")
    toc_break_run = ET.SubElement(toc_break, _w("r"))
    ET.SubElement(toc_break_run, _w("br")).set(_w("type"), "page")
    _append_sect_pr(toc_break, "upperRoman", start=1)
    body_h1 = _make_paragraph("序  言")
    body_h1_p_pr = ET.SubElement(body_h1, _w("pPr"))
    ET.SubElement(body_h1_p_pr, _w("pageBreakBefore")).set(_w("val"), "1")
    doc = _make_doc_root(toc_break, body_h1)
    body = doc.find("w:body", NSMAP)
    body_sect_pr = ET.SubElement(body, _w("sectPr"))
    body_pg_num = ET.SubElement(body_sect_pr, _w("pgNumType"))
    body_pg_num.set(_w("fmt"), "decimal")
    body_pg_num.set(_w("start"), "1")

    changed = cleanup_frontmatter_redundant_page_breaks(doc, {})

    paragraphs = body.findall("w:p", NSMAP)
    assert changed == 1
    assert paragraphs[0] is toc_break
    assert toc_break.find("w:pPr/w:sectPr", NSMAP) is not None
    assert body_h1.find("w:pPr/w:pageBreakBefore", NSMAP) is None


def test_cleanup_frontmatter_redundant_page_breaks_does_not_touch_later_body_chapter_breaks():
    toc_break = _make_paragraph("")
    toc_break_run = ET.SubElement(toc_break, _w("r"))
    ET.SubElement(toc_break_run, _w("br")).set(_w("type"), "page")
    _append_sect_pr(toc_break, "upperRoman", start=1)
    first_body_h1 = _make_paragraph("序  言")
    first_body_h1_p_pr = ET.SubElement(first_body_h1, _w("pPr"))
    ET.SubElement(first_body_h1_p_pr, _w("pageBreakBefore")).set(_w("val"), "1")
    body_para = _make_paragraph("这是正文。")
    chapter_break = _make_paragraph("")
    chapter_break_run = ET.SubElement(chapter_break, _w("r"))
    ET.SubElement(chapter_break_run, _w("br")).set(_w("type"), "page")
    _append_sect_pr(chapter_break, "decimal", start=2)
    later_h1 = _make_paragraph("第2章 实验结果")
    later_h1_p_pr = ET.SubElement(later_h1, _w("pPr"))
    ET.SubElement(later_h1_p_pr, _w("pageBreakBefore")).set(_w("val"), "1")
    doc = _make_doc_root(toc_break, first_body_h1, body_para, chapter_break, later_h1)
    body = doc.find("w:body", NSMAP)
    body_sect_pr = ET.SubElement(body, _w("sectPr"))
    body_pg_num = ET.SubElement(body_sect_pr, _w("pgNumType"))
    body_pg_num.set(_w("fmt"), "decimal")
    body_pg_num.set(_w("start"), "1")

    changed = cleanup_frontmatter_redundant_page_breaks(doc, {})

    assert changed == 1
    assert first_body_h1.find("w:pPr/w:pageBreakBefore", NSMAP) is None
    assert later_h1.find("w:pPr/w:pageBreakBefore", NSMAP) is not None
    assert chapter_break.find("w:pPr/w:sectPr", NSMAP) is not None


def test_fix_remove_hidden_page_number_artifacts_removes_body_page_field_paragraph():
    references = _make_paragraph("参考文献")
    artifact = _make_hidden_page_field_paragraph()
    acknowledgement = _make_paragraph("致  谢")
    document = _make_doc_root(references, artifact, acknowledgement)

    removed = fix_remove_hidden_page_number_artifacts(document)

    body = document.find("w:body", NSMAP)
    texts = [get_paragraph_text(p).strip() for p in body.findall("w:p", NSMAP)]
    assert removed == 1
    assert "—21—" not in texts
    assert texts == ["参考文献", "致  谢"]


def test_fix_remove_hidden_page_number_artifacts_removes_hyphen_only_page_field_paragraph():
    references = _make_paragraph("参考文献")
    artifact = _make_hidden_page_field_paragraph("-")
    acknowledgement = _make_paragraph("致  谢")
    document = _make_doc_root(references, artifact, acknowledgement)

    removed = fix_remove_hidden_page_number_artifacts(document)

    body = document.find("w:body", NSMAP)
    texts = [get_paragraph_text(p).strip() for p in body.findall("w:p", NSMAP)]
    assert removed == 1
    assert "-" not in texts
    assert texts == ["参考文献", "致  谢"]


def test_remove_existing_toc_artifacts_removes_toc_placeholder_paragraph():
    placeholder = _make_paragraph("（本页为目录页占位，目录在 WPS 中自动生成后更新。）")
    toc_title = _make_paragraph("目  录")
    toc_field = _make_paragraph("")
    toc_field_pr = ET.SubElement(toc_field, _w("pPr"))
    toc_field_style = ET.SubElement(toc_field_pr, _w("pStyle"))
    toc_field_style.set(_w("val"), "TOCField")
    toc_field_run = toc_field.find("w:r", NSMAP)
    instr = ET.SubElement(toc_field_run, _w("instrText"))
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    body_h1 = _make_paragraph("序  言")
    doc = _make_doc_root(placeholder, toc_title, toc_field, body_h1)

    removed = remove_existing_toc_artifacts(doc)

    body = doc.find("w:body", NSMAP)
    texts = [get_paragraph_text(p).strip() for p in body.findall("w:p", NSMAP)]
    assert removed >= 2
    assert "（本页为目录页占位，目录在 WPS 中自动生成后更新。）" not in texts
    assert "目  录" not in texts


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
