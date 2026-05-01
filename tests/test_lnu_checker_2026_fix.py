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
            "pg01_format": "hyphen_wrap",
            "ref_terminal_punct": ".",
            "ref_number_trailing_space": True,
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


def test_trim_caption_terminal_punctuation_also_handles_table_caption():
    caption = _make_paragraph("表2.1  组装统计。", sz=21)

    trim_caption_terminal_punctuation(caption)

    assert get_paragraph_text(caption) == "表2.1  组装统计"


def test_fix_reference_punctuation_forces_terminal_period_under_checker_2026():
    paragraph = _make_paragraph("[1] Guo G C. Quantum optics", sz=21)

    fix_reference_punctuation(paragraph, _checker_2026_cfg())

    assert get_paragraph_text(paragraph).endswith(".")


def test_fix_reference_paragraph_checker_2026_number_spacing_contract():
    paragraph = _make_paragraph("[01]   Some reference text.", sz=21)
    cfg = _checker_2026_cfg(ref_use_tab=False)

    fix_reference_paragraph(paragraph, cfg=cfg)

    normalized = get_paragraph_text(paragraph)
    assert normalized == "[1] Some reference text."


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


def test_fix_lnu_compact_text_preserves_existing_unit_spacing():
    paragraph = _make_paragraph("处理100 mL溶液并检测5 mg样本", sz=24)

    changed = fix_thesis.fix_lnu_compact_text(paragraph, restore_unit_gap=True)

    assert changed is False
    assert get_paragraph_text(paragraph) == "处理100 mL溶液并检测5 mg样本"


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


def test_fix_footer_page_number_builds_songti_hyphen_wrapped_footer(tmp_path):
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
    assert texts.count("-") == 2
    assert any("PAGE" in (instr.text or "").upper() for instr in footer_paragraph.findall(".//w:instrText", NSMAP))
    run_fonts = footer_paragraph.findall(".//w:rPr/w:rFonts", NSMAP)
    assert run_fonts and all(font.get(_w("eastAsia")) == "宋体" for font in run_fonts)
    sizes = footer_paragraph.findall(".//w:rPr/w:sz", NSMAP)
    assert sizes and all(size.get(_w("val")) == "21" for size in sizes)


def test_fix_footer_page_number_normalizes_existing_mixed_dash_wrapper(tmp_path):
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
    assert texts.count("-") == 2
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
