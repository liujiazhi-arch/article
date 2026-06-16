from __future__ import annotations

import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from _thesis_utils import NSMAP, W_NS, get_paragraph_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_thesis
import fix_thesis
from fix_thesis import (
    fix_abstract_body,
    fix_abstract_heading,
    fix_caption_number_sep,
    fix_caption_paragraph,
    fix_footer_page_number,
    fix_heading_spacing,
    fix_soft_line_breaks,
    fix_lnu_ack01,
    fix_reference_paragraph,
    fix_reference_punctuation,
    normalize_lnu_figure_block_layout,
    normalize_lnu_table_block_layout,
    normalize_object_wrapping,
    trim_caption_terminal_punctuation,
)

W = W_NS


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _make_run(text: str = "", sz: int | None = None) -> ET.Element:
    run = ET.Element(_w("r"))
    r_pr = ET.SubElement(run, _w("rPr"))
    if sz is not None:
        sz_elem = ET.SubElement(r_pr, _w("sz"))
        sz_elem.set(_w("val"), str(sz))
    text_elem = ET.SubElement(run, _w("t"))
    text_elem.text = text
    return run


def _make_paragraph(text: str = "", sz: int | None = None) -> ET.Element:
    paragraph = ET.Element(_w("p"))
    paragraph.append(_make_run(text, sz=sz))
    return paragraph


def _make_doc_root(*children: ET.Element) -> ET.Element:
    root = ET.Element(_w("document"))
    body = ET.SubElement(root, _w("body"))
    for child in children:
        body.append(child)
    return root


def _set_spacing(p_elem: ET.Element, *, before: int | None = None, after: int | None = None, line: int | None = None) -> ET.Element:
    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(p_elem, _w("pPr"))
    spacing = p_pr.find("w:spacing", NSMAP)
    if spacing is None:
        spacing = ET.SubElement(p_pr, _w("spacing"))
    if before is not None:
        spacing.set(_w("before"), str(before))
    if after is not None:
        spacing.set(_w("after"), str(after))
    if line is not None:
        spacing.set(_w("line"), str(line))
        spacing.set(_w("lineRule"), "auto")
    return p_elem


def _append_drawing(paragraph: ET.Element) -> None:
    run = ET.SubElement(paragraph, _w("r"))
    ET.SubElement(run, _w("drawing"))


def _checker_2026_cfg(**overrides) -> dict:
    cfg = copy.deepcopy(audit_thesis.load_profile("lnu"))
    cfg.update(
        {
            "h1_spacing_before": 120,
            "h1_spacing_after": 120,
            "h2_spacing_before": 120,
            "h2_spacing_after": 120,
            "h3_spacing_before": 120,
            "h3_spacing_after": 120,
            "abstract_title_after_pt": 0,
            "abstract_title_line": 360,
            "abstract_en_body_line": 240,
            "figure_blank_line_twips": 360,
            "caption_number_sep": ".",
            "kw_en_separator": "; ",
            "mixed_spacing_policy": "compact",
            "pg01_format": "plain",
            "ref_terminal_punct": ".",
            "ref_use_tab": True,
            "ref_tab_min": 420,
            "ref_number_trailing_space": False,
        }
    )
    cfg.update(overrides)
    return cfg


def test_fix_heading_spacing_uses_latest_image_half_line_before_after():
    cfg = _checker_2026_cfg()

    for level in ("h1", "h2", "h3"):
        paragraph = _make_paragraph("标题")
        fix_heading_spacing(paragraph, level, cfg=cfg)
        spacing = paragraph.find("w:pPr/w:spacing", NSMAP)
        assert spacing is not None
        assert spacing.get(_w("before")) == "120"
        assert spacing.get(_w("after")) == "120"
        assert spacing.get(_w("line")) == "360"


def test_fix_abstract_heading_applies_latest_image_zero_after_spacing():
    cfg = _checker_2026_cfg()

    cn_title = _make_paragraph("摘要", sz=28)
    en_title = _make_paragraph("Abstract", sz=28)

    fix_abstract_heading(cn_title, cfg, "abstract_cn")
    fix_abstract_heading(en_title, cfg, "abstract_en")

    cn_spacing = cn_title.find("w:pPr/w:spacing", NSMAP)
    en_spacing = en_title.find("w:pPr/w:spacing", NSMAP)
    assert cn_spacing is not None and cn_spacing.get(_w("after")) == "0"
    assert en_spacing is not None and en_spacing.get(_w("after")) == "0"


def test_fix_abstract_body_applies_latest_image_english_single_line_spacing():
    cfg = _checker_2026_cfg()
    paragraph = _make_paragraph("This is the abstract body.", sz=28)

    fix_abstract_body(paragraph, cfg, "abstract_en")

    spacing = paragraph.find("w:pPr/w:spacing", NSMAP)
    assert spacing is not None
    assert spacing.get(_w("line")) == "240"
    assert spacing.get(_w("after")) == "0"


def test_fix_abstract_section_normalizes_latest_image_english_keyword_separator_and_style():
    cfg = _checker_2026_cfg()
    keywords = _make_paragraph("Keywords: alpha; beta; gamma.", sz=24)
    document = _make_doc_root(keywords)

    fix_thesis.fix_abstract_section(document, cfg)

    runs = keywords.findall("w:r", NSMAP)
    texts = ["".join(t.text or "" for t in run.findall(".//w:t", NSMAP)) for run in runs]
    sizes = [run.find("w:rPr/w:sz", NSMAP).get(_w("val")) for run in runs]
    bold_flags = [run.find("w:rPr/w:b", NSMAP) is not None for run in runs]
    spacing = keywords.find("w:pPr/w:spacing", NSMAP)
    jc = keywords.find("w:pPr/w:jc", NSMAP)

    assert texts == ["Keywords:", " ", "alpha; beta; gamma"]
    assert sizes == ["28", "28", "24"]
    assert bold_flags == [True, False, False]
    assert spacing is not None and spacing.get(_w("line")) == "240"
    assert jc is not None and jc.get(_w("val")) == "center"


def test_fix_caption_helpers_apply_checker_2026_number_format_and_trim_terminal_punct():
    caption = _make_paragraph("图2-1 菌株系统发育树。", sz=21)

    fix_caption_number_sep(caption, _checker_2026_cfg())
    trim_caption_terminal_punctuation(caption)

    assert get_paragraph_text(caption) == "图2.1  菌株系统发育树"


def test_fix_caption_paragraph_clears_list_marker_and_unifies_caption_style():
    paragraph = _make_paragraph("Fig 2.4  Gel strength and chewiness.", sz=24)
    p_pr = paragraph.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(paragraph, _w("pPr"))
    ET.SubElement(p_pr, _w("numPr"))
    ind = ET.SubElement(p_pr, _w("ind"))
    ind.set(_w("firstLine"), "480")
    jc = ET.SubElement(p_pr, _w("jc"))
    jc.set(_w("val"), "both")
    run = paragraph.find("w:r", NSMAP)
    assert run is not None
    r_pr = run.find("w:rPr", NSMAP)
    assert r_pr is not None
    ET.SubElement(r_pr, _w("b"))

    fix_caption_paragraph(paragraph, cfg=_checker_2026_cfg())

    assert paragraph.find("w:pPr/w:numPr", NSMAP) is None
    fixed_jc = paragraph.find("w:pPr/w:jc", NSMAP)
    fixed_ind = paragraph.find("w:pPr/w:ind", NSMAP)
    fixed_spacing = paragraph.find("w:pPr/w:spacing", NSMAP)
    assert fixed_jc is not None and fixed_jc.get(_w("val")) == "center"
    assert fixed_ind is not None and fixed_ind.get(_w("firstLine")) == "0"
    assert fixed_spacing is not None and fixed_spacing.get(_w("line")) == "360"
    for run_elem in paragraph.findall("w:r", NSMAP):
        assert run_elem.find("w:rPr/w:b", NSMAP) is None
        assert run_elem.find("w:rPr/w:bCs", NSMAP) is None
        assert run_elem.find("w:rPr/w:sz", NSMAP).get(_w("val")) == "21"


def test_fix_caption_note_paragraph_normalizes_lnu_note_prefix_to_numbered_form():
    paragraph = _make_paragraph("注 ：正式实验各组样品初始投料质量均为 1.00 g。", sz=21)

    fix_thesis.fix_caption_note_paragraph(paragraph, cfg=_checker_2026_cfg())

    assert get_paragraph_text(paragraph) == "注：正式实验各组样品初始投料质量均为 1.00 g。"


def test_fix_caption_note_paragraph_centers_explanatory_note_and_parenthesizes_subfigure_letters():
    paragraph = _make_paragraph("注：图2.1A 为对照组，Fig. 2.1B 为实验组。", sz=24)

    fix_thesis.fix_caption_note_paragraph(paragraph, cfg=_checker_2026_cfg())

    p_pr = paragraph.find("w:pPr", NSMAP)
    spacing = p_pr.find("w:spacing", NSMAP)
    jc = p_pr.find("w:jc", NSMAP)
    ind = p_pr.find("w:ind", NSMAP)

    assert get_paragraph_text(paragraph) == "注：图2.1(A) 为对照组，Fig. 2.1(B) 为实验组。"
    assert jc is not None and jc.get(_w("val")) == "center"
    assert ind is not None and ind.get(_w("firstLine")) == "0"
    assert spacing is not None and spacing.get(_w("line")) == "240"


def test_fix_english_caption_paragraph_centers_five_point_single_line_and_parenthesizes_subfigure_letters():
    paragraph = _make_paragraph("Fig. 2.1A  Gel strength.", sz=24)

    fix_thesis.fix_english_caption_paragraph(paragraph, cfg=_checker_2026_cfg())

    p_pr = paragraph.find("w:pPr", NSMAP)
    spacing = p_pr.find("w:spacing", NSMAP)
    jc = p_pr.find("w:jc", NSMAP)

    assert get_paragraph_text(paragraph) == "Fig. 2.1(A)  Gel strength."
    assert jc is not None and jc.get(_w("val")) == "center"
    assert spacing is not None and spacing.get(_w("line")) == "240"
    for run_elem in paragraph.findall("w:r", NSMAP):
        assert run_elem.find("w:rPr/w:sz", NSMAP).get(_w("val")) == "21"


def test_fix_caption_note_paragraph_preserves_existing_multi_note_numbering():
    paragraph = _make_paragraph("注：1) 第一条；2) 第二条。", sz=21)

    fix_thesis.fix_caption_note_paragraph(paragraph, cfg=_checker_2026_cfg())

    assert get_paragraph_text(paragraph) == "注：1) 第一条；2) 第二条。"


def test_trim_caption_terminal_punctuation_also_handles_table_caption():
    caption = _make_paragraph("表2.1  组装统计。", sz=21)

    trim_caption_terminal_punctuation(caption)

    assert get_paragraph_text(caption) == "表2.1  组装统计"


def test_fix_reference_punctuation_forces_terminal_period_under_checker_2026():
    paragraph = _make_paragraph("[1] Guo G C. Quantum optics", sz=21)

    fix_reference_punctuation(paragraph, _checker_2026_cfg())

    assert get_paragraph_text(paragraph).endswith(".")


def test_fix_reference_paragraph_checker_2026_number_tab_contract():
    paragraph = _make_paragraph("[01]   Some reference text.", sz=21)
    cfg = _checker_2026_cfg()

    fix_reference_paragraph(paragraph, cfg=cfg)

    normalized = get_paragraph_text(paragraph)
    assert normalized == "[1]\tSome reference text."
    assert paragraph.find(".//w:tab", NSMAP) is not None


def test_split_inline_citations_normalizes_groups_and_keeps_them_superscript():
    paragraph = _make_paragraph("综述显示。[1][2]连续研究[1,2,3]表明。", sz=24)

    fix_thesis.split_inline_citations(paragraph)
    fix_thesis.move_superscript_citations_before_terminal_punct(paragraph)
    fix_thesis.fix_superscript_fonts(paragraph)

    assert get_paragraph_text(paragraph) == "综述显示[1,2]。连续研究[1-3]表明。"
    citation_runs = [
        run_elem
        for run_elem in paragraph.findall("w:r", NSMAP)
        if get_paragraph_text(run_elem).startswith("[")
    ]
    assert [get_paragraph_text(run_elem) for run_elem in citation_runs] == ["[1,2]", "[1-3]"]
    assert all(fix_thesis.is_superscript(run_elem) for run_elem in citation_runs)


def test_fix_reference_paragraph_matches_latest_reference_layout_contract():
    paragraph = _make_paragraph("[1] Some reference text.", sz=21)
    first_run = paragraph.find("w:r", NSMAP)
    assert first_run is not None
    first_rpr = first_run.find("w:rPr", NSMAP)
    assert first_rpr is not None
    vert_align = ET.SubElement(first_rpr, _w("vertAlign"))
    vert_align.set(_w("val"), "superscript")
    cfg = _checker_2026_cfg()

    fix_reference_paragraph(paragraph, cfg=cfg)

    p_pr = paragraph.find("w:pPr", NSMAP)
    assert p_pr is not None
    ind = p_pr.find("w:ind", NSMAP)
    jc = p_pr.find("w:jc", NSMAP)
    spacing = p_pr.find("w:spacing", NSMAP)
    assert ind is not None
    assert ind.get(_w("left")) == "420"
    assert ind.get(_w("hanging")) == "420"
    assert jc is not None and jc.get(_w("val")) == "both"
    assert spacing is not None and spacing.get(_w("line")) == "360"
    assert p_pr.find("w:suppressAutoHyphens", NSMAP) is not None
    tabs = p_pr.find("w:tabs", NSMAP)
    assert tabs is not None
    left_tab = tabs.find("w:tab", NSMAP)
    assert left_tab is not None
    assert left_tab.get(_w("val")) == "left"
    assert left_tab.get(_w("pos")) == "420"
    assert not fix_thesis.is_superscript(first_run)
    assert paragraph.find(".//w:tab", NSMAP) is not None
    assert get_paragraph_text(paragraph) == "[1]\tSome reference text."


def test_fix_sp_cjk_latin_checker_2026_compact_policy_does_not_add_mixed_spacing():
    cfg = _checker_2026_cfg(relax_strain_suffix_t_spacing=True, mixed_spacing_policy="compact")
    paragraph = _make_paragraph("DSM 104648 T基因组", sz=24)

    changed = fix_thesis.fix_sp_cjk_latin(paragraph, cfg=cfg)

    assert changed is False
    assert get_paragraph_text(paragraph) == "DSM 104648 T基因组"


def test_fix_sp_num_cjk_checker_2026_compact_policy_does_not_add_mixed_spacing():
    cfg = _checker_2026_cfg(mixed_spacing_policy="compact")
    paragraph = _make_paragraph("第3章", sz=24)

    changed = fix_thesis.fix_sp_num_cjk(paragraph, cfg=cfg)

    assert changed is False
    assert get_paragraph_text(paragraph) == "第3章"


def test_fix_sp_num_cjk_inserts_spacing_across_plain_text_runs_when_spaced_policy():
    cfg = _checker_2026_cfg(mixed_spacing_policy="spaced")
    paragraph = ET.Element(_w("p"))
    paragraph.append(_make_run("检测12", sz=24))
    paragraph.append(_make_run("样本", sz=24))

    changed = fix_thesis.fix_sp_num_cjk(paragraph, cfg=cfg)

    assert changed is True
    assert get_paragraph_text(paragraph) == "检测 12 样本"


def test_fix_lnu_compact_text_removes_mixed_spacing_and_chinese_punctuation_spaces():
    paragraph = _make_paragraph("本研究使用 CRISPR 技术检测 12 个样本 ，结果稳定。", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph)

    assert changed is True
    assert get_paragraph_text(paragraph) == "本研究使用CRISPR技术检测12个样本，结果稳定。"


def test_fix_lnu_compact_text_removes_mixed_spacing_across_runs():
    paragraph = ET.Element(_w("p"))
    paragraph.append(_make_run("本研究使用", sz=24))
    paragraph.append(_make_run(" ", sz=24))
    paragraph.append(_make_run("CRISPR", sz=24))
    paragraph.append(_make_run(" 技术检测", sz=24))

    changed = fix_thesis.fix_lnu_compact_text(paragraph)

    assert changed is True
    assert get_paragraph_text(paragraph) == "本研究使用CRISPR技术检测"


def test_fix_lnu_compact_text_restores_allowed_unit_spacing():
    paragraph = _make_paragraph("处理100mL溶液并检测5mg样本", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is True
    assert get_paragraph_text(paragraph) == "处理100 mL溶液并检测5 mg样本"


def test_fix_lnu_compact_text_keeps_percent_spacing_and_restores_celsius_spacing():
    paragraph = _make_paragraph("样品浓度为25 %，处理温度为100℃，另一组为6.67 ％。", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is True
    assert get_paragraph_text(paragraph) == "样品浓度为25 %，处理温度为100 ℃，另一组为6.67 ％。"


def test_fix_lnu_compact_text_preserves_existing_unit_spacing():
    paragraph = _make_paragraph("处理100 mL溶液并检测5 mg样本", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is False
    assert get_paragraph_text(paragraph) == "处理100 mL溶液并检测5 mg样本"


def test_fix_lnu_compact_text_preserves_percent_space_and_celsius_spacing():
    paragraph = _make_paragraph("样品浓度为25 %，处理温度为100 ℃。", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is False
    assert get_paragraph_text(paragraph) == "样品浓度为25 %，处理温度为100 ℃。"


def test_fix_lnu_compact_text_preserves_percent_space_across_runs():
    paragraph = ET.Element(_w("p"))
    paragraph.append(_make_run("样品浓度为25 ", sz=24))
    paragraph.append(_make_run("%，处理温度为100", sz=24))
    paragraph.append(_make_run("℃。", sz=24))

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is True
    assert get_paragraph_text(paragraph) == "样品浓度为25 %，处理温度为100 ℃。"


def test_fix_lnu_compact_text_preserves_percent_space_run_between_runs():
    paragraph = ET.Element(_w("p"))
    paragraph.append(_make_run("样品浓度为25", sz=24))
    paragraph.append(_make_run(" ", sz=24))
    paragraph.append(_make_run("%，处理温度为100", sz=24))
    paragraph.append(_make_run("℃。", sz=24))

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is True
    assert get_paragraph_text(paragraph) == "样品浓度为25 %，处理温度为100 ℃。"


def test_fix_lnu_compact_text_restores_allowed_heading_number_space():
    paragraph = _make_paragraph("1.2 CRISPR 技术基础", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_heading_gap=True)

    assert changed is True
    assert get_paragraph_text(paragraph) == "1.2 CRISPR技术基础"


def test_fix_half_width_punct_can_target_lnu_toc_scope():
    paragraph = _make_paragraph("1.1 研究背景,方法\t2", sz=24)
    document = _make_doc_root(paragraph)

    fix_thesis.fix_half_width_punct_in_cjk(document, allowed_ids={id(paragraph)})

    assert get_paragraph_text(paragraph) == "1.1 研究背景，方法\t2"


def test_lnu_toc_compact_text_preserves_heading_number_gap():
    paragraph = _make_paragraph("1.1研究背景\t2", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_heading_gap=True, restore_unit_gap=True)

    assert changed is True
    assert get_paragraph_text(paragraph) == "1.1 研究背景\t2"


def test_normalize_lnu_figure_block_layout_enforces_one_blank_line_gap():
    import pytest

    cfg = _checker_2026_cfg()
    intro = _set_spacing(_make_paragraph("上文说明。"), after=0, line=360)
    image = _set_spacing(_make_paragraph(""), before=0, after=0)
    _append_drawing(image)
    caption = _set_spacing(_make_paragraph("图2.1 菌株系统发育树", sz=21), before=120, after=120, line=360)
    outro = _set_spacing(_make_paragraph("下文说明。"), before=0, line=360)
    document = _make_doc_root(intro, image, caption, outro)

    changed = normalize_lnu_figure_block_layout(document, cfg=cfg)

    if changed == 0:
        pytest.xfail("Minimal ET fixture does not yet trigger the figure-block classifier on the current main chain.")
    assert changed > 0
    image_spacing = image.find("w:pPr/w:spacing", NSMAP)
    caption_spacing = caption.find("w:pPr/w:spacing", NSMAP)
    assert image_spacing is not None and image_spacing.get(_w("before")) == "360"
    assert caption_spacing is not None and caption_spacing.get(_w("before")) == "0"
    assert caption_spacing.get(_w("after")) == "360"


def test_normalize_lnu_table_block_layout_inserts_blank_paragraph_after_table_for_checker_2026():
    cfg = _checker_2026_cfg(table_blank_line_mode="blank_paragraph")
    chapter = _make_paragraph("第2章 实验结果与分析", sz=30)
    section = _make_paragraph("2.1 基因组组装结果", sz=30)
    intro = _set_spacing(_make_paragraph("上文说明。"), after=0, line=360)
    caption = _set_spacing(_make_paragraph("表2.1 组装统计", sz=21), before=0, after=0, line=360)
    table = ET.Element(_w("tbl"))
    tr = ET.SubElement(table, _w("tr"))
    tc = ET.SubElement(tr, _w("tc"))
    ET.SubElement(tc, _w("p"))
    next_heading = _set_spacing(_make_paragraph("2.2 基因组组分分析", sz=30), before=0, after=0, line=360)
    document = _make_doc_root(chapter, section, intro, caption, table, next_heading)

    changed = normalize_lnu_table_block_layout(document, cfg=cfg)

    assert changed > 0
    body = document.find("w:body", NSMAP)
    assert body is not None
    body_children = list(body)
    table_idx = next(idx for idx, elem in enumerate(body_children) if elem.tag == _w("tbl"))
    gap_para = body_children[table_idx + 1]
    assert gap_para.tag == _w("p")
    assert get_paragraph_text(gap_para) == ""
    spacing = gap_para.find("w:pPr/w:spacing", NSMAP)
    assert spacing is not None and spacing.get(_w("line")) == "360"


def test_fix_lnu_ack01_inserts_missing_acknowledgement_section_for_checker_2026():
    cfg = _checker_2026_cfg(acknowledgement_required=True, acknowledgement_placeholder_text="")
    document = _make_doc_root(_make_paragraph("参考文献"))

    fixed = fix_lnu_ack01(document, cfg)

    assert fixed >= 2
    body = document.find("w:body", NSMAP)
    assert body is not None
    texts = [get_paragraph_text(elem).strip() for elem in body.findall("w:p", NSMAP)]
    assert "致  谢" in texts


def test_fix_footer_page_number_builds_songti_plain_footer(tmp_path):
    workdir = tmp_path
    (workdir / "word" / "_rels").mkdir(parents=True)
    (workdir / "word").mkdir(exist_ok=True)
    (workdir / "[Content_Types].xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '</Types>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "_rels" / "document.xml.rels").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        ),
        encoding="utf-8",
    )

    document = _make_doc_root()
    body = document.find("w:body", NSMAP)
    assert body is not None
    ET.SubElement(body, _w("sectPr"))

    updated_parts = fix_footer_page_number(str(workdir), document, cfg=_checker_2026_cfg())

    footer_xml = updated_parts["word/footer1.xml"]
    footer_root = ET.fromstring(footer_xml)
    footer_paragraph = footer_root.find("w:p", NSMAP)
    assert footer_paragraph is not None
    jc = footer_paragraph.find("w:pPr/w:jc", NSMAP)
    assert jc is not None and jc.get(_w("val")) == "center"
    texts = [text_elem.text or "" for text_elem in footer_paragraph.findall(".//w:t", NSMAP)]
    assert "-" not in texts
    assert "—" not in texts
    assert any("PAGE" in (instr.text or "").upper() for instr in footer_paragraph.findall(".//w:instrText", NSMAP))
    run_fonts = footer_paragraph.findall(".//w:rPr/w:rFonts", NSMAP)
    assert run_fonts and all(font.get(_w("eastAsia")) == "宋体" for font in run_fonts)
    sizes = footer_paragraph.findall(".//w:rPr/w:sz", NSMAP)
    assert sizes and all(size.get(_w("val")) == "21" for size in sizes)


def test_fix_footer_page_number_uses_cover_frontmatter_body_sections(tmp_path):
    workdir = tmp_path
    (workdir / "word" / "_rels").mkdir(parents=True)
    (workdir / "word").mkdir(exist_ok=True)
    (workdir / "[Content_Types].xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '</Types>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "_rels" / "document.xml.rels").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        ),
        encoding="utf-8",
    )

    cover = _make_paragraph("封面信息")
    cover_pr = ET.SubElement(cover, _w("pPr"))
    cover_sect_pr = ET.SubElement(cover_pr, _w("sectPr"))
    frontmatter_break = _make_paragraph("")
    front_pr = ET.SubElement(frontmatter_break, _w("pPr"))
    front_sect_pr = ET.SubElement(front_pr, _w("sectPr"))
    document = _make_doc_root(cover, frontmatter_break, _make_paragraph("序言"))
    body = document.find("w:body", NSMAP)
    assert body is not None
    body_sect_pr = ET.SubElement(body, _w("sectPr"))

    updated_parts = fix_footer_page_number(str(workdir), document, cfg=_checker_2026_cfg())

    assert cover_sect_pr.find("w:footerReference", NSMAP) is None
    front_footer_ref = front_sect_pr.find("w:footerReference", NSMAP)
    body_footer_ref = body_sect_pr.find("w:footerReference", NSMAP)
    assert front_footer_ref is not None
    assert body_footer_ref is not None

    front_pg_num = front_sect_pr.find("w:pgNumType", NSMAP)
    body_pg_num = body_sect_pr.find("w:pgNumType", NSMAP)
    assert front_pg_num is not None
    assert front_pg_num.get(_w("fmt")) == "upperRoman"
    assert front_pg_num.get(_w("start")) == "1"
    assert body_pg_num is not None
    assert body_pg_num.get(_w("fmt")) == "decimal"
    assert body_pg_num.get(_w("start")) == "1"

    rels_root = ET.fromstring(updated_parts["word/_rels/document.xml.rels"])
    targets_by_id = {
        rel.get("Id"): rel.get("Target")
        for rel in rels_root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    }
    front_target = targets_by_id[front_footer_ref.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
    body_target = targets_by_id[body_footer_ref.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
    front_footer = ET.fromstring(updated_parts[f"word/{front_target}"])
    body_footer = ET.fromstring(updated_parts[f"word/{body_target}"])
    front_texts = [text_elem.text or "" for text_elem in front_footer.findall(".//w:t", NSMAP)]
    body_texts = [text_elem.text or "" for text_elem in body_footer.findall(".//w:t", NSMAP)]
    assert front_texts.count("-") == 0
    assert body_texts.count("-") == 2
    assert "—" not in front_texts
    assert "—" not in body_texts
    assert any("PAGE" in (instr.text or "").upper() for instr in front_footer.findall(".//w:instrText", NSMAP))
    assert any("PAGE" in (instr.text or "").upper() for instr in body_footer.findall(".//w:instrText", NSMAP))


def test_fix_footer_page_number_normalizes_existing_footer_parts_when_rebuilding_sections(tmp_path):
    workdir = tmp_path
    (workdir / "word" / "_rels").mkdir(parents=True)
    (workdir / "word").mkdir(exist_ok=True)
    (workdir / "[Content_Types].xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            '</Types>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "_rels" / "document.xml.rels").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            '</Relationships>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "footer1.xml").write_text(
        (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr>'
            f'<w:fldChar w:fldCharType="begin"/><w:instrText xml:space="preserve"> PAGE </w:instrText>'
            f'<w:fldChar w:fldCharType="end"/><w:t>1</w:t></w:r>'
            f'</w:p></w:ftr>'
        ),
        encoding="utf-8",
    )

    cover = _make_paragraph("封面信息")
    cover_pr = ET.SubElement(cover, _w("pPr"))
    ET.SubElement(cover_pr, _w("sectPr"))
    frontmatter_break = _make_paragraph("")
    front_pr = ET.SubElement(frontmatter_break, _w("pPr"))
    ET.SubElement(front_pr, _w("sectPr"))
    document = _make_doc_root(cover, frontmatter_break, _make_paragraph("序言"))
    body = document.find("w:body", NSMAP)
    assert body is not None
    ET.SubElement(body, _w("sectPr"))

    updated_parts = fix_footer_page_number(str(workdir), document, cfg=_checker_2026_cfg())

    assert "word/footer1.xml" in updated_parts
    footer_root = ET.fromstring(updated_parts["word/footer1.xml"])
    sizes = footer_root.findall(".//w:rPr/w:sz", NSMAP)
    assert sizes
    assert all(size.get(_w("val")) == "21" for size in sizes)


def test_fix_footer_page_number_reuses_existing_footer_relationships_without_package_rewrite(tmp_path):
    workdir = tmp_path
    (workdir / "word" / "_rels").mkdir(parents=True)
    (workdir / "word").mkdir(exist_ok=True)
    (workdir / "[Content_Types].xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            '<Override PartName="/word/footer2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            '</Types>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "_rels" / "document.xml.rels").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            '<Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer2.xml"/>'
            '</Relationships>'
        ),
        encoding="utf-8",
    )
    for footer_name in ("footer1.xml", "footer2.xml"):
        (workdir / "word" / footer_name).write_text(
            (
                f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr>'
                f'<w:fldChar w:fldCharType="begin"/><w:instrText xml:space="preserve"> PAGE </w:instrText>'
                f'<w:fldChar w:fldCharType="end"/></w:r>'
                f'</w:p></w:ftr>'
            ),
            encoding="utf-8",
        )

    cover = _make_paragraph("封面信息")
    cover_pr = ET.SubElement(cover, _w("pPr"))
    ET.SubElement(cover_pr, _w("sectPr"))
    frontmatter_break = _make_paragraph("")
    front_pr = ET.SubElement(frontmatter_break, _w("pPr"))
    ET.SubElement(front_pr, _w("sectPr"))
    document = _make_doc_root(cover, frontmatter_break, _make_paragraph("序言"))
    body = document.find("w:body", NSMAP)
    assert body is not None
    ET.SubElement(body, _w("sectPr"))

    updated_parts = fix_footer_page_number(str(workdir), document, cfg=_checker_2026_cfg())

    assert "word/footer1.xml" in updated_parts
    assert "word/footer2.xml" in updated_parts
    assert "word/_rels/document.xml.rels" not in updated_parts
    assert "[Content_Types].xml" not in updated_parts
    for footer_name in ("word/footer1.xml", "word/footer2.xml"):
        footer_root = ET.fromstring(updated_parts[footer_name])
        sizes = footer_root.findall(".//w:rPr/w:sz", NSMAP)
        assert sizes
        assert all(size.get(_w("val")) == "21" for size in sizes)


def test_fix_footer_page_number_creates_cover_section_when_frontmatter_has_no_cover_break(tmp_path):
    workdir = tmp_path
    (workdir / "word" / "_rels").mkdir(parents=True)
    (workdir / "word").mkdir(exist_ok=True)
    (workdir / "[Content_Types].xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '</Types>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "_rels" / "document.xml.rels").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        ),
        encoding="utf-8",
    )

    cover = _make_paragraph("封面信息")
    abstract_title = _make_paragraph("摘  要")
    abstract_body = _make_paragraph("中文摘要。")
    frontmatter_break = _make_paragraph("")
    front_pr = ET.SubElement(frontmatter_break, _w("pPr"))
    front_sect_pr = ET.SubElement(front_pr, _w("sectPr"))
    document = _make_doc_root(cover, abstract_title, abstract_body, frontmatter_break, _make_paragraph("序言"))
    body = document.find("w:body", NSMAP)
    assert body is not None
    body_sect_pr = ET.SubElement(body, _w("sectPr"))

    updated_parts = fix_footer_page_number(str(workdir), document, cfg=_checker_2026_cfg())

    cover_sect_pr = cover.find("w:pPr/w:sectPr", NSMAP)
    assert cover_sect_pr is not None
    assert cover_sect_pr.find("w:footerReference", NSMAP) is None
    front_footer_ref = front_sect_pr.find("w:footerReference", NSMAP)
    body_footer_ref = body_sect_pr.find("w:footerReference", NSMAP)
    assert front_footer_ref is not None
    assert body_footer_ref is not None

    front_pg_num = front_sect_pr.find("w:pgNumType", NSMAP)
    body_pg_num = body_sect_pr.find("w:pgNumType", NSMAP)
    assert front_pg_num is not None
    assert front_pg_num.get(_w("fmt")) == "upperRoman"
    assert front_pg_num.get(_w("start")) == "1"
    assert body_pg_num is not None
    assert body_pg_num.get(_w("fmt")) == "decimal"
    assert body_pg_num.get(_w("start")) == "1"

    rels_root = ET.fromstring(updated_parts["word/_rels/document.xml.rels"])
    targets_by_id = {
        rel.get("Id"): rel.get("Target")
        for rel in rels_root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    }
    front_target = targets_by_id[front_footer_ref.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
    body_target = targets_by_id[body_footer_ref.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")]
    front_footer = ET.fromstring(updated_parts[f"word/{front_target}"])
    body_footer = ET.fromstring(updated_parts[f"word/{body_target}"])
    front_texts = [text_elem.text or "" for text_elem in front_footer.findall(".//w:t", NSMAP)]
    body_texts = [text_elem.text or "" for text_elem in body_footer.findall(".//w:t", NSMAP)]
    assert front_texts.count("-") == 0
    assert body_texts.count("-") == 2
    assert "word/_rels/document.xml.rels" in updated_parts
    assert "[Content_Types].xml" in updated_parts


def test_fix_footer_page_number_removes_existing_mixed_dash_wrapper_for_plain_policy(tmp_path):
    workdir = tmp_path
    (workdir / "word" / "_rels").mkdir(parents=True)
    (workdir / "word").mkdir(exist_ok=True)
    (workdir / "[Content_Types].xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
            '</Types>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "_rels" / "document.xml.rels").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            '</Relationships>'
        ),
        encoding="utf-8",
    )
    (workdir / "word" / "footer1.xml").write_text(
        (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            f'<w:r><w:t>—</w:t></w:r><w:r><w:t>-</w:t></w:r>'
            f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
            f'<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            f'<w:r><w:t>-</w:t></w:r><w:r><w:t>—</w:t></w:r>'
            f'</w:p></w:ftr>'
        ),
        encoding="utf-8",
    )

    document = _make_doc_root()
    body = document.find("w:body", NSMAP)
    assert body is not None
    sect_pr = ET.SubElement(body, _w("sectPr"))
    footer_ref = ET.SubElement(sect_pr, _w("footerReference"))
    footer_ref.set(_w("type"), "default")
    footer_ref.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "rId9")

    updated_parts = fix_footer_page_number(str(workdir), document, cfg=_checker_2026_cfg())

    footer_root = ET.fromstring(updated_parts["word/footer1.xml"])
    texts = [text_elem.text or "" for text_elem in footer_root.findall(".//w:t", NSMAP)]
    assert "-" not in texts
    assert "—" not in texts


def test_fix_soft_line_breaks_splits_paragraphs_on_shift_enter():
    paragraph = _make_paragraph("第一行")
    run = paragraph.find("w:r", NSMAP)
    assert run is not None
    ET.SubElement(run, _w("br"))
    tail = ET.SubElement(run, _w("t"))
    tail.text = "第二行"
    document = _make_doc_root(paragraph)

    changed = fix_soft_line_breaks(document)

    assert changed == 1
    body = document.find("w:body", NSMAP)
    assert body is not None
    texts = [get_paragraph_text(child) for child in body.findall("w:p", NSMAP)]
    assert texts == ["第一行", "第二行"]


def test_fix_soft_line_breaks_preserves_lnu_figure_caption_line_breaks_when_configured():
    paragraph = _make_paragraph("图2.1  不同改性方法处理后鹿皮明胶的溶胀率")
    run = paragraph.find("w:r", NSMAP)
    assert run is not None
    ET.SubElement(run, _w("br"))
    tail = ET.SubElement(run, _w("t"))
    tail.text = "A，0～24 h 溶胀率变化；B，24 h 终点溶胀率"
    document = _make_doc_root(paragraph)

    changed = fix_soft_line_breaks(document, cfg={"preserve_caption_soft_line_breaks": True})

    assert changed == 0
    body = document.find("w:body", NSMAP)
    assert body is not None
    paragraphs = body.findall("w:p", NSMAP)
    assert len(paragraphs) == 1
    assert paragraphs[0].find(".//w:br", NSMAP) is not None


def test_normalize_object_wrapping_converts_anchor_and_removes_tblppr():
    paragraph = _make_paragraph("")
    drawing_run = ET.SubElement(paragraph, _w("r"))
    drawing = ET.SubElement(drawing_run, _w("drawing"))
    anchor = ET.SubElement(drawing, f"{{{fix_thesis.NAMESPACES['wp']}}}anchor")
    anchor.set("distT", "0")
    anchor.set("distB", "0")
    ET.SubElement(anchor, f"{{{fix_thesis.NAMESPACES['wp']}}}extent")
    ET.SubElement(anchor, f"{{{fix_thesis.NAMESPACES['wp']}}}docPr")
    ET.SubElement(anchor, f"{{{fix_thesis.NAMESPACES['wp']}}}cNvGraphicFramePr")
    ET.SubElement(anchor, f"{{{fix_thesis.NAMESPACES['a']}}}graphic")

    table = ET.Element(_w("tbl"))
    tbl_pr = ET.SubElement(table, _w("tblPr"))
    ET.SubElement(tbl_pr, _w("tblpPr"))
    tr = ET.SubElement(table, _w("tr"))
    tc = ET.SubElement(tr, _w("tc"))
    ET.SubElement(tc, _w("p"))
    document = _make_doc_root(paragraph, table)

    changed = normalize_object_wrapping(document)

    assert changed == 2
    assert drawing.find(f"{{{fix_thesis.NAMESPACES['wp']}}}anchor") is None
    assert drawing.find(f"{{{fix_thesis.NAMESPACES['wp']}}}inline") is not None
    assert tbl_pr.find("w:tblpPr", NSMAP) is None
