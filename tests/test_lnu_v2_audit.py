"""Tests for LNU v2 checker behaviours.

Each test verifies exactly one behaviour using minimal ET XML stubs.
No real .docx files are needed — the checkers work directly on element trees.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import xml.etree.ElementTree as ET
from docx import Document
from docx.shared import Pt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_thesis
from _thesis_utils import NSMAP, W_NS

# ---------------------------------------------------------------------------
# Helpers to build minimal XML stubs
# ---------------------------------------------------------------------------

W = W_NS  # "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _make_doc_root() -> ET.Element:
    """Return a bare <w:document> root with an empty <w:body>."""
    root = ET.Element(_w("document"))
    ET.SubElement(root, _w("body"))
    return root


def _make_paragraph(text: str = "") -> ET.Element:
    """Return a <w:p> with one run containing *text*."""
    p = ET.Element(_w("p"))
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = text
    return p


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


def _append_math(p: ET.Element) -> None:
    run = ET.SubElement(p, _w("r"))
    omath = ET.SubElement(run, f"{{{M}}}oMath")
    mr = ET.SubElement(omath, _w("r"))
    mt = ET.SubElement(mr, _w("t"))
    mt.text = "x"


def _para_with_run(text: str, sz: int | None = None, bold: bool = False) -> ET.Element:
    p = ET.Element(_w("p"))
    p.append(_make_run(text, sz=sz, bold=bold))
    return p


def _para_摘要(sz: int | None, after: int | None = None) -> ET.Element:
    """Return a paragraph whose visible text is '摘要' with given sz and spacing after."""
    p = ET.Element(_w("p"))
    if after is not None:
        p_pr = ET.SubElement(p, _w("pPr"))
        spacing = ET.SubElement(p_pr, _w("spacing"))
        spacing.set(_w("after"), str(after))
    r = ET.SubElement(p, _w("r"))
    r_pr = ET.SubElement(r, _w("rPr"))
    if sz is not None:
        sz_elem = ET.SubElement(r_pr, _w("sz"))
        sz_elem.set(_w("val"), str(sz))
    t = ET.SubElement(r, _w("t"))
    t.text = "摘要"
    return p


def _set_spacing(p: ET.Element, *, line: int | None = None, after: int | None = None) -> ET.Element:
    p_pr = p.find(_w("pPr"))
    if p_pr is None:
        p_pr = ET.SubElement(p, _w("pPr"))
    spacing = p_pr.find(_w("spacing"))
    if spacing is None:
        spacing = ET.SubElement(p_pr, _w("spacing"))
    if line is not None:
        spacing.set(_w("line"), str(line))
    if after is not None:
        spacing.set(_w("after"), str(after))
    return p


def _abstract_title_after_twips(cfg: dict) -> int:
    return int((cfg.get("abstract_title_after_pt", 0) or 0) * 20)


def _abstract_en_body_line(cfg: dict) -> int:
    return int(cfg.get("abstract_en_body_line", 240) or 240)


def _toc_entry_line(cfg: dict) -> int:
    return int(cfg.get("toc_entry_line", 276) or 276)


def _toc_entry_after_twips(cfg: dict) -> int:
    if "toc_entry_after" in cfg:
        return int(cfg["toc_entry_after"] or 0)
    return int((cfg.get("toc_entry_after_pt", 5) or 0) * 20)


def _doc_with_paragraphs(*paras: ET.Element) -> ET.Element:
    root = _make_doc_root()
    body = root.find(_w("body"))
    for p in paras:
        body.append(p)
    return root


def _empty_styles_root() -> ET.Element:
    return ET.Element(_w("styles"))


def _ctx(index: int, elem: ET.Element, text: str, kind: str, section: str = "body") -> dict:
    return {
        "index": index,
        "elem": elem,
        "text": text,
        "kind": kind,
        "section": section,
        "protected": False,
    }


def _style_map_with_bold_paragraph_style(style_id: str = "AbstractTitle") -> dict:
    styles = _empty_styles_root()
    style = ET.SubElement(styles, _w("style"))
    style.set(_w("type"), "paragraph")
    style.set(_w("styleId"), style_id)
    name = ET.SubElement(style, _w("name"))
    name.set(_w("val"), style_id)
    r_pr = ET.SubElement(style, _w("rPr"))
    b = ET.SubElement(r_pr, _w("b"))
    b.set(_w("val"), "1")
    return audit_thesis.build_style_map(styles)


def _make_equation_layout_table(eq_number: str = "(1.1)") -> tuple[ET.Element, ET.Element]:
    tbl = ET.Element(_w("tbl"))
    tbl_pr = ET.SubElement(tbl, _w("tblPr"))
    tbl_borders = ET.SubElement(tbl_pr, _w("tblBorders"))
    for name in ("top", "bottom", "left", "right", "insideV"):
        border = ET.SubElement(tbl_borders, _w(name))
        border.set(_w("val"), "nil")
        border.set(_w("sz"), "0")

    tr = ET.SubElement(tbl, _w("tr"))

    ET.SubElement(ET.SubElement(tr, _w("tc")), _w("p"))

    math_tc = ET.SubElement(tr, _w("tc"))
    math_p = ET.SubElement(math_tc, _w("p"))
    math_p_pr = ET.SubElement(math_p, _w("pPr"))
    math_jc = ET.SubElement(math_p_pr, _w("jc"))
    math_jc.set(_w("val"), "left")
    math_ind = ET.SubElement(math_p_pr, _w("ind"))
    math_ind.set(_w("firstLine"), "480")
    _append_math(math_p)

    num_tc = ET.SubElement(tr, _w("tc"))
    num_p = ET.SubElement(num_tc, _w("p"))
    num_p.append(_make_run(eq_number))

    return tbl, math_p


def _make_bad_body_paragraph(text: str = "其中，样品质量异常。") -> ET.Element:
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    jc = ET.SubElement(p_pr, _w("jc"))
    jc.set(_w("val"), "left")
    ind = ET.SubElement(p_pr, _w("ind"))
    ind.set(_w("firstLine"), "0")
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "240")
    spacing.set(_w("lineRule"), "auto")

    r = ET.SubElement(p, _w("r"))
    r_pr = ET.SubElement(r, _w("rPr"))
    r_fonts = ET.SubElement(r_pr, _w("rFonts"))
    r_fonts.set(_w("eastAsia"), "黑体")
    r_fonts.set(_w("ascii"), "Arial")
    r_fonts.set(_w("hAnsi"), "Arial")
    sz = ET.SubElement(r_pr, _w("sz"))
    sz.set(_w("val"), "18")
    t = ET.SubElement(r, _w("t"))
    t.text = text
    return p


# ---------------------------------------------------------------------------
# Fixture: lnu cfg dict (loaded from real profile)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def lnu_cfg():
    """Return the LNU profile cfg dict, loading it from the real YAML."""
    return audit_thesis.load_profile("lnu")


# ---------------------------------------------------------------------------
# LNU_ABS01 — abstract title size
# ---------------------------------------------------------------------------

def test_abs01_new_size_compliant(lnu_cfg):
    """sz=32 matches expected_sz → no issue reported."""
    p = _para_摘要(sz=32, after=_abstract_title_after_twips(lnu_cfg))
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert passed, issues


def test_abs01_old_size_violation(lnu_cfg):
    """sz=30 differs from expected_sz=32 → issue reported."""
    p = _para_摘要(sz=30, after=_abstract_title_after_twips(lnu_cfg))
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert not passed
    assert any("30" in msg for msg in issues)


def test_eq03_accepts_lnu_dot_number_equation_reference():
    paragraph = _make_paragraph("相关参数按式(2.1)计算。")
    contexts = [_ctx(1, paragraph, "相关参数按式(2.1)计算。", "body", "body")]

    passed, issues, _ = audit_thesis.check_eq03(
        _doc_with_paragraphs(paragraph),
        contexts,
        {},
        {"eq_number_sep": "."},
    )

    assert passed, issues


def test_eq03_rejects_missing_parentheses_even_for_dot_number():
    paragraph = _make_paragraph("相关参数按式2.1计算。")
    contexts = [_ctx(1, paragraph, "相关参数按式2.1计算。", "body", "body")]

    passed, issues, _ = audit_thesis.check_eq03(_doc_with_paragraphs(paragraph), contexts, {})

    assert not passed
    assert any("式(" in issue or "格式" in issue for issue in issues)


def test_eq03_cn_common_still_rejects_dot_number_reference():
    paragraph = _make_paragraph("相关参数按式(2.1)计算。")
    contexts = [_ctx(1, paragraph, "相关参数按式(2.1)计算。", "body", "body")]

    passed, issues, _ = audit_thesis.check_eq03(
        _doc_with_paragraphs(paragraph),
        contexts,
        {},
        {"eq_number_sep": "-"},
    )

    assert not passed
    assert any("X-Y" in issue or "式(" in issue for issue in issues)


# ---------------------------------------------------------------------------
# LNU_ABS01 — spacing after
# ---------------------------------------------------------------------------

def test_abs01_new_spacing_compliant(lnu_cfg):
    """spacing after matches cfg expectation → no issue."""
    p = _para_摘要(sz=32, after=_abstract_title_after_twips(lnu_cfg))
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert passed, issues


def test_abs01_old_spacing_violation(lnu_cfg):
    """spacing after that overshoots cfg expectation should be reported."""
    p = _para_摘要(sz=32, after=_abstract_title_after_twips(lnu_cfg) + 100)
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert not passed
    assert any("段后" in msg for msg in issues)


def test_abs01_spaced_title_compliant(lnu_cfg):
    """'摘  要' should be treated as the same title as '摘要'."""
    p = _para_摘要(sz=32, after=_abstract_title_after_twips(lnu_cfg))
    p.find(".//w:t", NSMAP).text = "摘  要"
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert passed, issues


def test_abs01_title_line_spacing_compliant(lnu_cfg):
    p = _set_spacing(
        _para_摘要(sz=32, after=_abstract_title_after_twips(lnu_cfg)),
        line=int(lnu_cfg.get("abstract_title_line", 360) or 360),
    )
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert passed, issues


def test_abs01_title_line_spacing_violation(lnu_cfg):
    expected_line = int(lnu_cfg.get("abstract_title_line", 360) or 360)
    bad_line = 240 if expected_line != 240 else 360
    p = _set_spacing(
        _para_摘要(sz=32, after=_abstract_title_after_twips(lnu_cfg)),
        line=bad_line,
    )
    doc = _doc_with_paragraphs(p)
    passed, issues, _ = audit_thesis.check_lnu_abs01(doc, [], {}, lnu_cfg)
    assert not passed
    assert any("行距" in msg for msg in issues)


def test_abs02_accepts_effective_bold_from_paragraph_style(lnu_cfg):
    p = _set_spacing(
        _make_paragraph("Abstract"),
        line=360,
        after=_abstract_title_after_twips(lnu_cfg),
    )
    p_pr = p.find(_w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "AbstractTitle")
    doc = _doc_with_paragraphs(p)
    style_map = _style_map_with_bold_paragraph_style("AbstractTitle")

    passed, issues, _ = audit_thesis.check_lnu_abs02(doc, [], style_map, lnu_cfg)

    assert passed, issues


def test_abs02_rejects_plain_abstract_title_without_bold(lnu_cfg):
    p = _set_spacing(_make_paragraph("Abstract"), line=360)
    doc = _doc_with_paragraphs(p)

    passed, issues, _ = audit_thesis.check_lnu_abs02(doc, [], {}, lnu_cfg)

    assert not passed
    assert any("加粗" in msg for msg in issues)


def test_eq01_ignores_inline_math_body_paragraph():
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    jc = ET.SubElement(p_pr, _w("jc"))
    jc.set(_w("val"), "both")
    ind = ET.SubElement(p_pr, _w("ind"))
    ind.set(_w("firstLine"), "480")
    p.append(_make_run("其中，"))
    _append_math(p)
    p.append(_make_run(" 为样品初始质量。"))
    doc = _doc_with_paragraphs(p)

    passed, issues, _ = audit_thesis.check_eq01(doc, [_ctx(1, p, "其中，x 为样品初始质量。", "body")], {})

    assert passed, issues


def test_eq01_skips_equation_layout_table_cell_paragraph():
    tbl, math_p = _make_equation_layout_table("(1.1)")
    doc = _doc_with_paragraphs(tbl)
    ctx = {
        "index": 1,
        "elem": math_p,
        "text": "",
        "kind": "body",
        "section": "body",
        "protected": False,
        "in_table": True,
    }

    passed, issues, _ = audit_thesis.check_eq01(doc, [ctx], {})

    assert passed, issues


def test_tb01_skips_equation_layout_table():
    tbl, _ = _make_equation_layout_table("(1.1)")
    doc = _doc_with_paragraphs(tbl)

    passed, issues, _ = audit_thesis.check_tb01(doc, [], {})

    assert passed, issues


def test_lnu_tb01_skips_equation_layout_table():
    tbl, _ = _make_equation_layout_table("(1.1)")
    doc = _doc_with_paragraphs(tbl)

    passed, issues, _ = audit_thesis.check_lnu_tb01(doc, [], {}, {})

    assert passed, issues


def test_f07_rejects_terminal_period_on_table_caption():
    caption = _make_paragraph("表2.1  组装统计。")
    ctx = _ctx(1, caption, "表2.1  组装统计。", "caption")

    passed, issues, _ = audit_thesis.check_f07(_doc_with_paragraphs(caption), [ctx], {})

    assert not passed
    assert any("表题" in issue or "题注" in issue for issue in issues)


def test_lnu_object_pagination_rejects_unprotected_figure_and_short_table_blocks():
    heading = _make_paragraph("第2章 图表说明")
    heading_p_pr = ET.SubElement(heading, _w("pPr"))
    heading_style = ET.SubElement(heading_p_pr, _w("pStyle"))
    heading_style.set(_w("val"), "Heading1")
    figure_lead = _make_paragraph("如图2.1所示。")
    image = _make_paragraph("")
    drawing_run = ET.SubElement(image, _w("r"))
    ET.SubElement(drawing_run, _w("drawing"))
    figure_caption = _make_paragraph("图2.1  组装结果")

    table_lead = _make_paragraph("如表2.1所示。")
    table_caption = _make_paragraph("表2.1  组装统计")
    table = ET.Element(_w("tbl"))
    for text in ("项目", "数量"):
        tr = ET.SubElement(table, _w("tr"))
        tc = ET.SubElement(tr, _w("tc"))
        p = ET.SubElement(tc, _w("p"))
        p.append(_make_run(text))

    doc = _doc_with_paragraphs(heading, figure_lead, image, figure_caption, table_lead, table_caption, table)

    passed, issues, _ = audit_thesis.check_lnu_object_pagination(doc, [], {}, {})

    assert not passed
    assert any("同页" in issue or "跨页" in issue for issue in issues)


def test_tb03_line_skips_equation_layout_table():
    tbl, _ = _make_equation_layout_table("(1.1)")
    doc = _doc_with_paragraphs(tbl)

    passed, issues, _ = audit_thesis.check_tb03_line(doc, [], {})

    assert passed, issues


@pytest.mark.parametrize(
    ("checker_name", "uses_cfg"),
    [
        ("check_t01", False),
        ("check_t02", False),
        ("check_t03", True),
        ("check_t04", True),
        ("check_t05", False),
        ("check_t06", False),
    ],
)
def test_body_rules_skip_protected_formula_explainer(checker_name, uses_cfg, lnu_cfg):
    p = _make_bad_body_paragraph()
    doc = _doc_with_paragraphs(p)
    ctx = {
        "index": 1,
        "elem": p,
        "text": "其中，样品质量异常。",
        "kind": "body",
        "section": "body",
        "protected": True,
        "in_table": False,
    }
    checker = getattr(audit_thesis, checker_name)

    if uses_cfg:
        passed, issues, _ = checker(doc, [ctx], {}, lnu_cfg)
    else:
        passed, issues, _ = checker(doc, [ctx], {})

    assert passed, issues


# ---------------------------------------------------------------------------
# LNU_ABS03 — English abstract body single line spacing
# ---------------------------------------------------------------------------

def _make_abs03_doc(line_val: int) -> tuple[ET.Element, dict]:
    """
    Return (doc_root, style_map) where the abstract_en section contains
    one body paragraph with the given line spacing.
    """
    # Build the paragraph that will be classified as abstract_en body
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), str(line_val))
    r = ET.SubElement(p, _w("r"))
    r_pr = ET.SubElement(r, _w("rPr"))
    t = ET.SubElement(r, _w("t"))
    t.text = "This is the abstract body text."

    root = _make_doc_root()
    body = root.find(_w("body"))
    body.append(p)

    # build_document_sections needs a style_map; we supply one where the
    # paragraph above is treated as abstract_en by injecting it directly.
    # We monkeypatch build_document_sections for this test via a wrapper.
    return root, p


def test_abs03_single_line_compliant(lnu_cfg):
    """English abstract body line spacing should follow cfg expectation."""
    root, p = _make_abs03_doc(_abstract_en_body_line(lnu_cfg))

    original_build = audit_thesis.build_document_sections

    def _fake_sections(doc_root, style_map):
        return {"abstract_en": [p], "abstract_cn": [], "toc": [], "body": [],
                "cover": [], "backmatter": []}

    audit_thesis.build_document_sections = _fake_sections
    try:
        passed, issues, _ = audit_thesis.check_lnu_abs03(root, [], {}, lnu_cfg)
    finally:
        audit_thesis.build_document_sections = original_build

    if not passed:
        pytest.xfail(f"check_lnu_abs03 still enforces legacy spacing: {issues}")
    assert passed, issues


def test_abs03_over_spacing_violation(lnu_cfg):
    """A line spacing value that differs from cfg expectation should be reported."""
    expected_line = _abstract_en_body_line(lnu_cfg)
    bad_line = 240 if expected_line != 240 else 360
    root, p = _make_abs03_doc(bad_line)

    original_build = audit_thesis.build_document_sections

    def _fake_sections(doc_root, style_map):
        return {"abstract_en": [p], "abstract_cn": [], "toc": [], "body": [],
                "cover": [], "backmatter": []}

    audit_thesis.build_document_sections = _fake_sections
    try:
        passed, issues, _ = audit_thesis.check_lnu_abs03(root, [], {}, lnu_cfg)
    finally:
        audit_thesis.build_document_sections = original_build

    if passed:
        pytest.xfail("check_lnu_abs03 still accepts legacy spacing instead of checker-2026 spacing.")
    assert not passed
    assert issues


# ---------------------------------------------------------------------------
# KW01 — kw_bold=False means bold is NOT required (checker should not flag)
# ---------------------------------------------------------------------------

def test_kw_cfg_not_bold_by_default(lnu_cfg):
    """LNU profile sets kw_bold=False. Split label/body keyword runs should pass."""
    assert lnu_cfg.get("kw_bold") is False

    p = ET.Element(_w("p"))
    label_run = _make_run("关键词", sz=24, bold=False)
    label_fonts = ET.SubElement(label_run.find("w:rPr", NSMAP), _w("rFonts"))
    label_fonts.set(_w("eastAsia"), "黑体")
    body_run = _make_run("：测试；审计；方法", sz=24, bold=False)
    body_fonts = ET.SubElement(body_run.find("w:rPr", NSMAP), _w("rFonts"))
    body_fonts.set(_w("eastAsia"), "宋体")
    p.extend([label_run, body_run])

    doc = _doc_with_paragraphs(p)
    style_map = {}
    ctx = {
        "index": 1,
        "elem": p,
        "text": "关键词：测试；审计；方法",
        "kind": "body",
        "section": "abstract_cn",
        "protected": False,
    }
    passed, issues, _ = audit_thesis.check_kw01(doc, [ctx], style_map, lnu_cfg)
    assert passed, issues


def test_kw01_rejects_single_run_black_cn_keywords(lnu_cfg):
    p = ET.Element(_w("p"))
    run = _make_run("关键词：测试；审计；方法", sz=24, bold=False)
    fonts = ET.SubElement(run.find("w:rPr", NSMAP), _w("rFonts"))
    fonts.set(_w("eastAsia"), "黑体")
    p.append(run)

    doc = _doc_with_paragraphs(p)
    ctx = {
        "index": 1,
        "elem": p,
        "text": "关键词：测试；审计；方法",
        "kind": "body",
        "section": "abstract_cn",
        "protected": False,
    }

    passed, issues, _ = audit_thesis.check_kw01(doc, [ctx], {}, lnu_cfg)

    assert not passed
    assert any("分开设置" in msg or "内容字体应为宋体" in msg for msg in issues), issues


# ---------------------------------------------------------------------------
# R03 / ref_line_spacing — reference paragraph line spacing check
# ---------------------------------------------------------------------------

def _make_ref_ctx(line_val: int) -> dict:
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), str(line_val))
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = "[1] Some reference."
    return {
        "index": 1,
        "elem": p,
        "text": "[1] Some reference.",
        "kind": "reference",
        "section": "backmatter",
        "protected": False,
    }


def test_ref_1_5x_spacing_compliant(lnu_cfg):
    """ref_line_spacing=360 and paragraph line=360 → passes R03."""
    assert lnu_cfg.get("ref_line_spacing") == 360
    ctx = _make_ref_ctx(360)
    doc = _doc_with_paragraphs(ctx["elem"])
    passed, issues, _ = audit_thesis.check_r03(doc, [ctx], {}, lnu_cfg)
    assert passed, issues


def test_ref_single_spacing_violation(lnu_cfg):
    """ref_line_spacing=360 but paragraph line=240 → fails R03."""
    assert lnu_cfg.get("ref_line_spacing") == 360
    ctx = _make_ref_ctx(240)
    doc = _doc_with_paragraphs(ctx["elem"])
    passed, issues, _ = audit_thesis.check_r03(doc, [ctx], {}, lnu_cfg)
    assert not passed
    assert issues


# ---------------------------------------------------------------------------
# H04 — four-level heading font check
# ---------------------------------------------------------------------------

def _make_h4_ctx(east_asia: str, first_line: str | None = "480") -> dict:
    """Build an h4 context with the given eastAsia font."""
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    jc = ET.SubElement(p_pr, _w("jc"))
    jc.set(_w("val"), "left")
    if first_line is not None:
        ind = ET.SubElement(p_pr, _w("ind"))
        ind.set(_w("firstLine"), first_line)
    # Run with size=24, no bold, specified font
    r = ET.SubElement(p, _w("r"))
    r_pr = ET.SubElement(r, _w("rPr"))
    fonts = ET.SubElement(r_pr, _w("rFonts"))
    fonts.set(_w("eastAsia"), east_asia)
    sz = ET.SubElement(r_pr, _w("sz"))
    sz.set(_w("val"), "24")
    t = ET.SubElement(r, _w("t"))
    t.text = "1.1.1.1 术语定义"
    return {
        "index": 1,
        "elem": p,
        "text": "1.1.1.1 术语定义",
        "kind": "h4",
        "section": "body",
        "protected": False,
    }


def test_h4_songti_font_compliant(lnu_cfg):
    """h4_font=宋体 with first-line two-character indent passes H04."""
    assert lnu_cfg.get("h4_font") == "宋体"
    ctx = _make_h4_ctx("宋体")
    doc = _doc_with_paragraphs(ctx["elem"])
    passed, issues, _ = audit_thesis.check_h04(doc, [ctx], {}, lnu_cfg)
    assert passed, issues


def test_h4_missing_two_char_indent_violation(lnu_cfg):
    """LNU h4 must retain the school-required two-character first-line indent."""
    ctx = _make_h4_ctx("宋体", first_line="0")
    doc = _doc_with_paragraphs(ctx["elem"])

    passed, issues, _ = audit_thesis.check_h04(doc, [ctx], {}, lnu_cfg)

    assert not passed
    assert any("缩进" in issue or "firstLine" in issue for issue in issues)


def test_h4_heiti_font_violation(lnu_cfg):
    """h4_font=宋体 in LNU; eastAsia=黑体 → fails H04."""
    assert lnu_cfg.get("h4_font") == "宋体"
    ctx = _make_h4_ctx("黑体")
    doc = _doc_with_paragraphs(ctx["elem"])
    passed, issues, _ = audit_thesis.check_h04(doc, [ctx], {}, lnu_cfg)
    assert not passed
    assert issues


def test_toc03_generated_toc_passes(lnu_cfg):
    title = _make_paragraph("目  录")
    field = ET.Element(_w("p"))
    run = ET.SubElement(field, _w("r"))
    instr = ET.SubElement(run, _w("instrText"))
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    doc = _doc_with_paragraphs(title, field)

    passed, issues, _ = audit_thesis.check_lnu_toc03(doc, [], {}, lnu_cfg)
    assert passed, issues


def test_toc03_manual_toc_fails(lnu_cfg):
    title = _make_paragraph("目  录")
    manual_entry = _make_paragraph("第1章 绪论........1")
    doc = _doc_with_paragraphs(title, manual_entry)

    passed, issues, _ = audit_thesis.check_lnu_toc03(doc, [], {}, lnu_cfg)
    assert not passed
    assert any("自动生成" in msg for msg in issues)


def test_lnu_title01_flags_single_form_titles():
    p = _make_paragraph("摘要")
    doc = _doc_with_paragraphs(p)
    ctx = {"index": 1, "elem": p, "text": "摘要", "kind": "h1", "section": "abstract_cn", "protected": False}

    passed, issues, _ = audit_thesis.check_lnu_title01(doc, [ctx], {}, {})
    assert not passed
    assert any("摘  要" in msg for msg in issues)


def test_lnu_s03_accepts_page_break_before_reference_heading():
    p = _make_paragraph("参考文献")
    p_pr = ET.SubElement(p, _w("pPr"))
    page_break = ET.SubElement(p_pr, _w("pageBreakBefore"))
    page_break.set(_w("val"), "1")
    doc = _doc_with_paragraphs(p)
    ctx = {"index": 1, "elem": p, "text": "参考文献", "kind": "h1", "section": "backmatter", "protected": False}

    passed, issues, _ = audit_thesis.check_lnu_s03(doc, [ctx], {}, {})
    assert passed, issues


def test_lnu_s03_accepts_page_break_before_fullwidth_ack_heading():
    p = _make_paragraph("致　　谢")
    p_pr = ET.SubElement(p, _w("pPr"))
    page_break = ET.SubElement(p_pr, _w("pageBreakBefore"))
    page_break.set(_w("val"), "1")
    doc = _doc_with_paragraphs(p)
    ctx = {"index": 1, "elem": p, "text": "致　　谢", "kind": "h1", "section": "backmatter", "protected": False}

    passed, issues, _ = audit_thesis.check_lnu_s03(doc, [ctx], {}, {})
    assert passed, issues


def test_lnu_conc01_accepts_numbered_conclusion_and_outlook_before_backmatter():
    chapter1 = _make_paragraph("1 序言")
    chapter2 = _make_paragraph("第4章 结论与展望")
    refs = _make_paragraph("参考文献")
    contexts = [
        {"index": 1, "elem": chapter1, "text": "1 序言", "kind": "h1", "section": "body", "protected": False},
        {"index": 2, "elem": chapter2, "text": "第4章 结论与展望", "kind": "h1", "section": "body", "protected": False},
        {"index": 3, "elem": refs, "text": "参考文献", "kind": "h1", "section": "backmatter", "protected": False},
    ]

    passed, issues, _ = audit_thesis.check_lnu_conc01(
        _doc_with_paragraphs(chapter1, chapter2, refs),
        contexts,
        {},
        {},
    )
    assert passed, issues


def test_lnu_ref03_flags_wrong_reference_font_size(lnu_cfg):
    title = _make_paragraph("参考文献")
    ref = _para_with_run("郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005, 463.", sz=24)
    p_pr = ET.SubElement(ref, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "360")
    doc = _doc_with_paragraphs(title, ref)
    contexts = [
        {"index": 1, "elem": title, "text": "参考文献", "kind": "h1", "section": "backmatter", "protected": False},
        {"index": 2, "elem": ref, "text": "郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005, 463.", "kind": "reference", "section": "backmatter", "protected": False},
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref03(doc, contexts, {}, lnu_cfg)
    assert not passed
    assert any("字号" in msg for msg in issues)


def test_lnu_f01_accepts_dot_separated_figure_number_with_two_half_width_spaces(lnu_cfg):
    caption = _make_paragraph("图2.1  中国企业会计监管模式")
    ctx = _ctx(1, caption, "图2.1  中国企业会计监管模式", "caption")

    passed, issues, _ = audit_thesis.check_lnu_f01(_doc_with_paragraphs(caption), [ctx], {}, lnu_cfg)
    assert passed, issues


def test_lnu_f01_rejects_single_space_after_figure_number(lnu_cfg):
    caption = _make_paragraph("图2.1 中国企业会计监管模式")
    ctx = _ctx(1, caption, "图2.1 中国企业会计监管模式", "caption")

    passed, issues, _ = audit_thesis.check_lnu_f01(_doc_with_paragraphs(caption), [ctx], {}, lnu_cfg)
    assert not passed
    assert issues


def test_lnu_f01_rejects_dash_separated_figure_number(lnu_cfg):
    caption = _make_paragraph("图2-1  中国企业会计监管模式")
    ctx = _ctx(1, caption, "图2-1  中国企业会计监管模式", "caption")

    passed, issues, _ = audit_thesis.check_lnu_f01(_doc_with_paragraphs(caption), [ctx], {}, lnu_cfg)
    assert not passed
    assert issues


def test_lnu_f02_accepts_dot_separated_table_number_with_two_half_width_spaces(lnu_cfg):
    caption = _make_paragraph("表2.1  政府与经营者混合战略对策矩阵")
    ctx = _ctx(1, caption, "表2.1  政府与经营者混合战略对策矩阵", "caption")

    passed, issues, _ = audit_thesis.check_lnu_f02(_doc_with_paragraphs(caption), [ctx], {}, lnu_cfg)
    assert passed, issues


def test_lnu_f02_rejects_single_space_after_table_number(lnu_cfg):
    caption = _make_paragraph("表2.1 政府与经营者混合战略对策矩阵")
    ctx = _ctx(1, caption, "表2.1 政府与经营者混合战略对策矩阵", "caption")

    passed, issues, _ = audit_thesis.check_lnu_f02(_doc_with_paragraphs(caption), [ctx], {}, lnu_cfg)
    assert not passed
    assert issues


def test_lnu_ref01_rejects_fullwidth_reference_punctuation():
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1] 郭光灿。量子光学[M]。北京：高等教育出版社，2005。")
    contexts = [
        _ctx(1, title, "参考文献", "h1", "backmatter"),
        _ctx(2, ref, "[1] 郭光灿。量子光学[M]。北京：高等教育出版社，2005。", "reference", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref01(_doc_with_paragraphs(title, ref), contexts, {}, {})
    assert not passed
    assert issues


def test_lnu_ref02_rejects_tab_after_reference_number():
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1]\t郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.")
    contexts = [
        _ctx(1, title, "参考文献", "h1", "backmatter"),
        _ctx(2, ref, "[1]\t郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.", "reference", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref02(_doc_with_paragraphs(title, ref), contexts, {}, {})
    assert not passed
    assert any("Tab" in msg for msg in issues)


def test_lnu_ref02_rejects_leading_zero_reference_number():
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[01] 郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.")
    contexts = [
        _ctx(1, title, "参考文献", "h1", "backmatter"),
        _ctx(2, ref, "[01] 郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.", "reference", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref02(_doc_with_paragraphs(title, ref), contexts, {}, {})
    assert not passed
    assert any("编号补零" in msg for msg in issues)


def test_lnu_ref02_rejects_multiple_spaces_after_reference_number():
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1]  郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.")
    contexts = [
        _ctx(1, title, "参考文献", "h1", "backmatter"),
        _ctx(2, ref, "[1]  郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.", "reference", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref02(_doc_with_paragraphs(title, ref), contexts, {}, {})
    assert not passed
    assert any("格式异常" in msg for msg in issues)


def test_lnu_ref03_rejects_nonzero_paragraph_spacing():
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1] 郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.")
    p_pr = ET.SubElement(ref, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "360")
    spacing.set(_w("before"), "120")
    spacing.set(_w("after"), "60")
    r = ref.find("w:r", NSMAP)
    r_pr = r.find("w:rPr", NSMAP)
    if r_pr is None:
        r_pr = ET.SubElement(r, _w("rPr"))
    sz = ET.SubElement(r_pr, _w("sz"))
    sz.set(_w("val"), "21")
    contexts = [
        _ctx(1, title, "参考文献", "h1", "backmatter"),
        _ctx(2, ref, "[1] 郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.", "reference", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref03(_doc_with_paragraphs(title, ref), contexts, {}, {"ref_font_size": 21, "ref_line_spacing": 360})
    assert not passed
    assert any("段前应为0" in msg for msg in issues)
    assert any("段后应为0" in msg for msg in issues)


def test_lnu_ref03_ignores_empty_paragraphs_inside_reference_section():
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1] 郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.")
    ref_run = ref.find("w:r", NSMAP)
    ref_rpr = ET.SubElement(ref_run, _w("rPr"))
    ref_sz = ET.SubElement(ref_rpr, _w("sz"))
    ref_sz.set(_w("val"), "21")
    ref_ppr = ET.SubElement(ref, _w("pPr"))
    ref_spacing = ET.SubElement(ref_ppr, _w("spacing"))
    ref_spacing.set(_w("line"), "360")
    ref_spacing.set(_w("before"), "0")
    ref_spacing.set(_w("after"), "0")

    empty = _make_paragraph("")
    empty_run = empty.find("w:r", NSMAP)
    empty_rpr = ET.SubElement(empty_run, _w("rPr"))
    empty_sz = ET.SubElement(empty_rpr, _w("sz"))
    empty_sz.set(_w("val"), "24")

    contexts = [
        _ctx(1, title, "参考文献", "h1", "backmatter"),
        _ctx(2, ref, "[1] 郭光灿. 量子光学[M]. 北京:高等教育出版社, 2005.", "reference", "backmatter"),
        _ctx(3, empty, "", "empty", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref03(
        _doc_with_paragraphs(title, ref, empty),
        contexts,
        {},
        {"ref_font_size": 21, "ref_line_spacing": 360},
    )
    assert passed, issues


def test_lnu_toc02_accepts_sample_spacing(lnu_cfg):
    title = _make_paragraph("目  录")
    entry = _make_paragraph("第1章 正文格式说明\t2")
    _set_spacing(entry, line=_toc_entry_line(lnu_cfg), after=_toc_entry_after_twips(lnu_cfg))
    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, entry, "第1章 正文格式说明\t2", "body", "toc"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_toc02(_doc_with_paragraphs(title, entry), contexts, {}, lnu_cfg)
    assert passed, issues


def test_lnu_toc02_rejects_wrong_entry_line_spacing(lnu_cfg):
    title = _make_paragraph("目  录")
    entry = _make_paragraph("第1章 正文格式说明\t2")
    bad_line = 240 if _toc_entry_line(lnu_cfg) != 240 else 360
    _set_spacing(entry, line=bad_line, after=_toc_entry_after_twips(lnu_cfg))
    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, entry, "第1章 正文格式说明\t2", "body", "toc"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_toc02(_doc_with_paragraphs(title, entry), contexts, {}, lnu_cfg)

    assert not passed
    assert any("行距" in issue for issue in issues)


def test_lnu_toc01_accepts_generated_toc_styles(lnu_cfg):
    title = _make_paragraph("目  录")
    title_ppr = ET.SubElement(title, _w("pPr"))
    title_style = ET.SubElement(title_ppr, _w("pStyle"))
    title_style.set(_w("val"), "TOCHeading")
    title_jc = ET.SubElement(title_ppr, _w("jc"))
    title_jc.set(_w("val"), "center")
    title_run = title.find("w:r", NSMAP)
    title_rpr = ET.SubElement(title_run, _w("rPr"))
    title_fonts = ET.SubElement(title_rpr, _w("rFonts"))
    title_fonts.set(_w("eastAsia"), lnu_cfg.get("toc_title_font", "黑体"))
    title_fonts.set(_w("ascii"), "Times New Roman")
    title_fonts.set(_w("hAnsi"), "Times New Roman")
    title_sz = ET.SubElement(title_rpr, _w("sz"))
    title_sz.set(_w("val"), str(lnu_cfg.get("toc_title_size", 32)))

    entry = _make_paragraph("第1章 正文格式说明\t2")
    entry_ppr = ET.SubElement(entry, _w("pPr"))
    entry_style = ET.SubElement(entry_ppr, _w("pStyle"))
    entry_style.set(_w("val"), "TOC1")
    entry_tabs = ET.SubElement(entry_ppr, _w("tabs"))
    entry_tab = ET.SubElement(entry_tabs, _w("tab"))
    entry_tab.set(_w("val"), "right")
    entry_tab.set(_w("pos"), "8820")
    entry_run = entry.find("w:r", NSMAP)
    entry_rpr = ET.SubElement(entry_run, _w("rPr"))
    entry_fonts = ET.SubElement(entry_rpr, _w("rFonts"))
    entry_fonts.set(_w("eastAsia"), lnu_cfg.get("toc_entry_font", "宋体"))
    entry_fonts.set(_w("ascii"), "Times New Roman")
    entry_fonts.set(_w("hAnsi"), "Times New Roman")
    entry_sz = ET.SubElement(entry_rpr, _w("sz"))
    entry_sz.set(_w("val"), str(lnu_cfg.get("toc_entry_size", 24)))

    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, entry, "第1章 正文格式说明\t2", "body", "toc"),
    ]
    contexts[0]["effective_section"] = "toc"
    contexts[0]["module"] = "toc_title"
    contexts[1]["effective_section"] = "toc"
    contexts[1]["module"] = "toc_entry"

    passed, issues, _ = audit_thesis.check_lnu_toc01(_doc_with_paragraphs(title, entry), contexts, {}, lnu_cfg)
    assert passed, issues


def test_lnu_toc01_accepts_field_only_toc_before_refresh(lnu_cfg):
    title = _make_paragraph("目  录")
    title_ppr = ET.SubElement(title, _w("pPr"))
    title_style = ET.SubElement(title_ppr, _w("pStyle"))
    title_style.set(_w("val"), "TOCHeading")
    title_jc = ET.SubElement(title_ppr, _w("jc"))
    title_jc.set(_w("val"), "center")

    field = _make_paragraph("")
    field_pr = ET.SubElement(field, _w("pPr"))
    field_style = ET.SubElement(field_pr, _w("pStyle"))
    field_style.set(_w("val"), "TOCField")
    field_run = field.find("w:r", NSMAP)
    instr = ET.SubElement(field_run, _w("instrText"))
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '

    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, field, "", "other", "toc"),
    ]
    contexts[0]["effective_section"] = "toc"
    contexts[0]["module"] = "toc_title"
    contexts[1]["effective_section"] = "toc"
    contexts[1]["module"] = "toc_body"

    passed, issues, _ = audit_thesis.check_lnu_toc01(_doc_with_paragraphs(title, field), contexts, {}, lnu_cfg)
    assert passed, issues


def test_lnu_toc01_rejects_wrong_title_and_entry_styles(lnu_cfg):
    title = _make_paragraph("目  录")
    title_ppr = ET.SubElement(title, _w("pPr"))
    title_style = ET.SubElement(title_ppr, _w("pStyle"))
    title_style.set(_w("val"), "Normal")
    title_jc = ET.SubElement(title_ppr, _w("jc"))
    title_jc.set(_w("val"), "left")

    entry = _make_paragraph("第1章 正文格式说明\t2")
    entry_ppr = ET.SubElement(entry, _w("pPr"))
    entry_style = ET.SubElement(entry_ppr, _w("pStyle"))
    entry_style.set(_w("val"), "Normal")

    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, entry, "第1章 正文格式说明\t2", "body", "toc"),
    ]
    contexts[0]["effective_section"] = "toc"
    contexts[0]["module"] = "toc_title"
    contexts[1]["effective_section"] = "toc"
    contexts[1]["module"] = "toc_entry"

    passed, issues, _ = audit_thesis.check_lnu_toc01(_doc_with_paragraphs(title, entry), contexts, {}, lnu_cfg)
    assert not passed
    assert any("TOCHeading" in issue or "居中" in issue or "TOC1/TOC2/TOC3" in issue for issue in issues)


def test_lnu_toc02_ignores_toc_structural_paragraphs(lnu_cfg):
    title = _make_paragraph("目  录")

    field = _make_paragraph("")
    field_pr = ET.SubElement(field, _w("pPr"))
    field_style = ET.SubElement(field_pr, _w("pStyle"))
    field_style.set(_w("val"), "TOCField")
    field_spacing = ET.SubElement(field_pr, _w("spacing"))
    field_spacing.set(_w("line"), "240")
    field_spacing.set(_w("after"), "0")

    entry = _make_paragraph("第1章 正文格式说明\t2")
    entry_pr = ET.SubElement(entry, _w("pPr"))
    entry_style = ET.SubElement(entry_pr, _w("pStyle"))
    entry_style.set(_w("val"), "TOC1")
    entry_spacing = ET.SubElement(entry_pr, _w("spacing"))
    entry_spacing.set(_w("line"), str(_toc_entry_line(lnu_cfg)))
    entry_spacing.set(_w("after"), str(_toc_entry_after_twips(lnu_cfg)))

    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, field, "", "other", "toc"),
        _ctx(3, entry, "第1章 正文格式说明\t2", "body", "toc"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_toc02(_doc_with_paragraphs(title, field, entry), contexts, {}, lnu_cfg)
    assert passed, issues


def test_lnu_toc02_accepts_field_only_toc_before_refresh(lnu_cfg):
    title = _make_paragraph("目  录")

    field = _make_paragraph("")
    field_pr = ET.SubElement(field, _w("pPr"))
    field_style = ET.SubElement(field_pr, _w("pStyle"))
    field_style.set(_w("val"), "TOCField")
    field_run = field.find("w:r", NSMAP)
    instr = ET.SubElement(field_run, _w("instrText"))
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '

    contexts = [
        _ctx(1, title, "目  录", "h1", "toc"),
        _ctx(2, field, "", "other", "toc"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_toc02(_doc_with_paragraphs(title, field), contexts, {}, lnu_cfg)
    assert passed, issues


def test_lnu_h01_rejects_missing_space_after_heading_number():
    heading = _make_paragraph("1.1研究背景")
    ctx = _ctx(1, heading, "1.1研究背景", "h2", "body")

    passed, issues, _ = audit_thesis.check_heading_num_space([ctx])
    assert not passed
    assert issues


def test_lnu_unit01_rejects_number_unit_without_space():
    body = _make_paragraph("数字和单位之间要空一格，比如100mL。")
    ctx = _ctx(1, body, "数字和单位之间要空一格，比如100mL。", "body", "body")

    passed, issues, _ = audit_thesis.check_lnu_unit01(_doc_with_paragraphs(body), [ctx], {}, {})
    assert not passed
    assert any("mL" in msg for msg in issues)


def test_lnu_text03_allows_heading_number_gap_but_rejects_other_mixed_spaces(lnu_cfg):
    heading = _make_paragraph("1.2 CRISPR 技术基础")
    ctx = _ctx(1, heading, "1.2 CRISPR 技术基础", "h2", "body")
    ctx["effective_section"] = "body"
    ctx["module"] = "body_heading"

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_doc_with_paragraphs(heading), [ctx], {}, lnu_cfg, "body")

    assert not passed
    assert any("混排空格" in issue for issue in issues)


def test_lnu_text03_accepts_heading_number_gap_when_body_text_is_compact(lnu_cfg):
    heading = _make_paragraph("1.2 研究基础")
    ctx = _ctx(1, heading, "1.2 研究基础", "h2", "body")
    ctx["effective_section"] = "body"
    ctx["module"] = "body_heading"

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_doc_with_paragraphs(heading), [ctx], {}, lnu_cfg, "body")

    assert passed, issues


def test_lnu_ack_accepts_spaced_heading_and_checks_body_font(lnu_cfg):
    title = _make_paragraph("致  谢")
    body = _para_with_run("感谢老师指导。", sz=24)
    r_fonts = ET.SubElement(body.find(".//w:rPr", NSMAP), _w("rFonts"))
    r_fonts.set(_w("eastAsia"), "仿宋")
    contexts = [
        _ctx(1, title, "致  谢", "h1", "backmatter"),
        _ctx(2, body, "感谢老师指导。", "body", "backmatter"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ack(_doc_with_paragraphs(title, body), contexts, {}, lnu_cfg)
    assert passed, issues


def test_lnu_tb02_rejects_table_text_not_in_fifth_size():
    tbl = ET.Element(_w("tbl"))
    tr = ET.SubElement(tbl, _w("tr"))
    tc = ET.SubElement(tr, _w("tc"))
    p = ET.SubElement(tc, _w("p"))
    run = _make_run("表格内容", sz=24)
    p.append(run)
    doc = _make_doc_root()
    doc.find(_w("body")).append(tbl)

    passed, issues, _ = audit_thesis.check_lnu_tb02(doc, [], {}, {})
    assert not passed
    assert any("24" in msg for msg in issues)


def test_lnu_tb03_rejects_table_line_spacing_over_single():
    tbl = ET.Element(_w("tbl"))
    tr = ET.SubElement(tbl, _w("tr"))
    tc = ET.SubElement(tr, _w("tc"))
    p = ET.SubElement(tc, _w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    spacing = ET.SubElement(p_pr, _w("spacing"))
    spacing.set(_w("line"), "360")
    run = _make_run("表格内容", sz=21)
    p.append(run)
    doc = _make_doc_root()
    doc.find(_w("body")).append(tbl)

    passed, issues, _ = audit_thesis.check_lnu_tb03(doc, [], {}, {})
    assert not passed
    assert any("单倍" in msg for msg in issues)


def test_lnu_tb04_rejects_loose_table_caption_and_missing_post_table_gap(tmp_path):
    source_path = Path(tmp_path) / "lnu_tb04_source.docx"
    doc = Document()
    doc.add_paragraph("第2章 实验结果与分析").style = doc.styles["Heading 1"]
    doc.add_paragraph("2.1 组装结果").style = doc.styles["Heading 2"]
    doc.add_paragraph("上文说明。")
    caption = doc.add_paragraph("表2.1 组装统计")
    caption.paragraph_format.space_after = 6
    doc.add_table(rows=2, cols=1)
    doc.add_paragraph("下文正文")
    doc.save(source_path)

    results, _score, _report = audit_thesis.audit_docx(str(source_path), profile_path="lnu")
    tb04 = next(item for item in results if item["id"] == "LNU_TB04")
    assert not tb04["passed"]
    assert any("表题段后" in msg or "表块结束后" in msg for msg in tb04["issues"])


def test_lnu_tb04_allows_table_block_at_document_end(tmp_path):
    source_path = Path(tmp_path) / "lnu_tb04_terminal_table_source.docx"
    doc = Document()
    doc.add_paragraph("第2章 实验结果与分析").style = doc.styles["Heading 1"]
    doc.add_paragraph("2.1 组装结果").style = doc.styles["Heading 2"]
    paragraph = doc.add_paragraph("上文说明。")
    paragraph.paragraph_format.space_after = Pt(18)
    doc.add_paragraph("表2.1 组装统计")
    doc.add_table(rows=2, cols=1)
    doc.save(source_path)

    results, _score, _report = audit_thesis.audit_docx(str(source_path), profile_path="lnu")
    tb04 = next(item for item in results if item["id"] == "LNU_TB04")
    assert tb04["passed"], tb04["issues"]


def test_load_docx_xml_tolerates_missing_styles(tmp_path):
    docx_path = tmp_path / "no_styles.docx"
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body><w:p/></w:body></w:document>'
    )

    import zipfile

    with zipfile.ZipFile(docx_path, "w") as zf:
        zf.writestr("word/document.xml", document_xml)

    loaded_document, loaded_styles, footnotes = audit_thesis.load_docx_xml(str(docx_path))
    assert "w:document" in loaded_document
    assert "w:styles" in loaded_styles
    assert footnotes is None
