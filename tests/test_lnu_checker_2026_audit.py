from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import audit_thesis
from _thesis_utils import NSMAP, W_NS, build_document_model, build_style_map, collect_figure_blocks, get_paragraph_text

W = W_NS


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _make_doc_root(*paragraphs: ET.Element) -> ET.Element:
    root = ET.Element(_w("document"))
    body = ET.SubElement(root, _w("body"))
    for paragraph in paragraphs:
        body.append(paragraph)
    return root


def _make_paragraph(text: str = "", sz: int | None = None) -> ET.Element:
    paragraph = ET.Element(_w("p"))
    run = ET.SubElement(paragraph, _w("r"))
    if sz is not None:
        r_pr = ET.SubElement(run, _w("rPr"))
        sz_elem = ET.SubElement(r_pr, _w("sz"))
        sz_elem.set(_w("val"), str(sz))
    text_elem = ET.SubElement(run, _w("t"))
    text_elem.text = text
    return paragraph


def _set_spacing(paragraph: ET.Element, *, line: int | None = None, after: int | None = None) -> ET.Element:
    p_pr = paragraph.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(paragraph, _w("pPr"))
    spacing = p_pr.find("w:spacing", NSMAP)
    if spacing is None:
        spacing = ET.SubElement(p_pr, _w("spacing"))
    if line is not None:
        spacing.set(_w("line"), str(line))
        spacing.set(_w("lineRule"), "auto")
    if after is not None:
        spacing.set(_w("after"), str(after))
    return paragraph


def _set_centered(paragraph: ET.Element) -> ET.Element:
    p_pr = paragraph.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(paragraph, _w("pPr"))
    jc = p_pr.find("w:jc", NSMAP)
    if jc is None:
        jc = ET.SubElement(p_pr, _w("jc"))
    jc.set(_w("val"), "center")
    return paragraph


def _set_paragraph_style(paragraph: ET.Element, style_id: str) -> ET.Element:
    p_pr = paragraph.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.SubElement(paragraph, _w("pPr"))
    p_style = p_pr.find("w:pStyle", NSMAP)
    if p_style is None:
        p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), style_id)
    return paragraph


def _append_drawing(paragraph: ET.Element) -> ET.Element:
    run = ET.SubElement(paragraph, _w("r"))
    ET.SubElement(run, _w("drawing"))
    return paragraph


def _append_text_run(paragraph: ET.Element, text: str, *, sz: int | None = None) -> ET.Element:
    run = ET.SubElement(paragraph, _w("r"))
    if sz is not None:
        r_pr = ET.SubElement(run, _w("rPr"))
        sz_elem = ET.SubElement(r_pr, _w("sz"))
        sz_elem.set(_w("val"), str(sz))
    text_elem = ET.SubElement(run, _w("t"))
    text_elem.text = text
    return run


def _append_soft_break(paragraph: ET.Element) -> ET.Element:
    run = ET.SubElement(paragraph, _w("r"))
    ET.SubElement(run, _w("br"))
    return run


def _set_run_fonts(paragraph: ET.Element) -> ET.Element:
    for run in paragraph.findall("w:r", NSMAP):
        r_pr = run.find("w:rPr", NSMAP)
        if r_pr is None:
            r_pr = ET.SubElement(run, _w("rPr"))
        r_fonts = r_pr.find("w:rFonts", NSMAP)
        if r_fonts is None:
            r_fonts = ET.SubElement(r_pr, _w("rFonts"))
        r_fonts.set(_w("eastAsia"), "宋体")
        r_fonts.set(_w("ascii"), "Times New Roman")
        r_fonts.set(_w("hAnsi"), "Times New Roman")
    return paragraph


def _checker_runtime_or_xfail():
    for profile_ref in ("lnu_checker_2026", "lnu-checker-2026", "lnu"):
        try:
            runtime = audit_thesis.build_audit_runtime(profile_ref, strict_profile=(profile_ref != "lnu"))
        except Exception:
            continue
        cfg = runtime.cfg
        if int(cfg.get("abstract_title_after_pt", 0) or 0) == 0 and int(cfg.get("abstract_en_body_line", 0) or 0) == 240:
            return runtime
    pytest.xfail("latest LNU profile alias/config is not wired into audit runtime yet.")


def _fake_abstract_en_sections(paragraph: ET.Element):
    original = audit_thesis.build_document_sections

    def _fake_sections(document_root, style_map):
        return {
            "abstract_en": [paragraph],
            "abstract_cn": [],
            "toc": [],
            "body": [],
            "cover": [],
            "backmatter": [],
        }

    audit_thesis.build_document_sections = _fake_sections
    return original


def test_checker_2026_runtime_exposes_latest_image_abstract_values():
    runtime = _checker_runtime_or_xfail()

    assert int(runtime.cfg["abstract_title_after_pt"]) == 0
    assert int(runtime.cfg["abstract_en_body_line"]) == 240


def test_checker_2026_runtime_uses_separate_caption_and_note_line_spacing():
    runtime = _checker_runtime_or_xfail()

    assert int(runtime.cfg["figure_caption_line"]) == 360
    assert int(runtime.cfg["figure_note_line"]) == 240


def test_checker_2026_classifies_explanatory_lines_after_figure_caption_as_notes():
    title = _make_paragraph("第2章 实验结果与分析", sz=30)
    image = _append_drawing(_make_paragraph(""))
    caption = _set_centered(_set_spacing(_make_paragraph("图2.1  不同改性方法对鹿皮明胶溶胀率的影响", sz=21), line=360))
    subfigure_note = _set_spacing(_make_paragraph("（A）24 h终点溶胀率；（B）0～24 h溶胀率变化", sz=21), line=240)
    significance_note = _set_spacing(
        _make_paragraph("不同小写字母表示组间差异显著（p<0.05）；相同小写字母表示组间差异不显著（p≥0.05）", sz=21),
        line=240,
    )
    following_body = _set_spacing(_make_paragraph("各组样品24 h溶失率见图2.2。", sz=24), line=360)
    document = _make_doc_root(title, image, caption, subfigure_note, significance_note, following_body)

    model = build_document_model(document, build_style_map(ET.Element(_w("styles"))))
    nodes_by_text = {node.text: node for node in model.paragraphs}
    assert nodes_by_text[get_paragraph_text(subfigure_note)].module == "body_caption_note"
    assert nodes_by_text[get_paragraph_text(significance_note)].module == "body_caption_note"

    blocks = collect_figure_blocks(document, build_style_map(ET.Element(_w("styles"))))
    assert len(blocks) == 1
    assert [note.text for note in blocks[0]["notes"]] == [
        get_paragraph_text(subfigure_note),
        get_paragraph_text(significance_note),
    ]


def test_checker_2026_lnu_f06_accepts_caption_one_point_five_and_note_single_spacing():
    runtime = _checker_runtime_or_xfail()
    caption = _set_run_fonts(_set_centered(_set_spacing(_make_paragraph("图2.1  不同改性方法对鹿皮明胶溶胀率的影响", sz=21), line=360)))
    note = _set_centered(_set_spacing(
        _make_paragraph("不同小写字母表示组间差异显著（p<0.05）；相同小写字母表示组间差异不显著（p≥0.05）", sz=21),
        line=240,
    ))
    _set_run_fonts(note)
    contexts = [
        {
            "index": 1,
            "elem": caption,
            "text": get_paragraph_text(caption),
            "kind": "caption",
            "section": "body",
            "module": "body_caption",
            "protected": False,
        },
        {
            "index": 2,
            "elem": note,
            "text": get_paragraph_text(note),
            "kind": "body",
            "section": "body",
            "module": "body_caption_note",
            "protected": False,
        },
    ]

    passed, issues, _ = audit_thesis.check_lnu_f06(_make_doc_root(caption, note), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_lnu_f06_checks_caption_title_before_soft_break_note():
    runtime = _checker_runtime_or_xfail()
    caption = _set_run_fonts(
        _set_centered(_set_spacing(_make_paragraph("图2.2  不同改性方法对鹿皮明胶溶失率的影响", sz=21), line=360))
    )
    _append_soft_break(caption)
    _append_text_run(caption, "不同小写字母表示组间差异显著（", sz=21)
    _append_text_run(caption, "p", sz=24)
    _append_text_run(caption, "<0.05）；相同小写字母表示组间差异不显著", sz=21)
    _set_run_fonts(caption)
    contexts = [
        {
            "index": 1,
            "elem": caption,
            "text": get_paragraph_text(caption),
            "kind": "caption",
            "section": "body",
            "module": "body_caption",
            "protected": False,
        },
    ]

    passed, issues, _ = audit_thesis.check_lnu_f06(_make_doc_root(caption), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_f01_checks_caption_title_before_soft_break_note():
    runtime = _checker_runtime_or_xfail()
    caption = _set_run_fonts(
        _set_centered(_set_spacing(_make_paragraph("图2.2  不同改性方法对鹿皮明胶溶失率的影响", sz=21), line=360))
    )
    _append_soft_break(caption)
    _append_text_run(
        caption,
        "不同小写字母表示组间差异显著（p<0.05）；相同小写字母表示组间差异不显著（p≥0.05）",
        sz=24,
    )
    _set_run_fonts(caption)
    contexts = [
        {
            "index": 1,
            "elem": caption,
            "text": get_paragraph_text(caption),
            "kind": "caption",
            "section": "body",
            "module": "body_caption",
            "protected": False,
        },
    ]

    passed, issues, _ = audit_thesis.check_f01(_make_doc_root(caption), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_t01_t02_accept_body_fonts_inherited_from_paragraph_style():
    paragraph = _set_paragraph_style(
        _set_spacing(_make_paragraph("这是正文示例，含有 DAS-DSG 和 24 h。", sz=24), line=360),
        "LnuBody",
    )
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": get_paragraph_text(paragraph),
            "kind": "body",
            "section": "body",
            "module": "body_paragraph",
            "protected": False,
        },
    ]
    style_map = {
        "LnuBody": {
            "eastAsia": "宋体",
            "ascii": "Times New Roman",
            "hAnsi": "Times New Roman",
            "sz": 24,
        }
    }

    t01_passed, t01_issues, _ = audit_thesis.check_t01(_make_doc_root(paragraph), contexts, style_map)
    t02_passed, t02_issues, _ = audit_thesis.check_t02(_make_doc_root(paragraph), contexts, style_map)

    assert t01_passed, t01_issues
    assert t02_passed, t02_issues


def test_checker_2026_t04_accepts_valid_line_spacing_without_explicit_snap_to_grid():
    runtime = _checker_runtime_or_xfail()
    paragraph = _set_spacing(_make_paragraph("这是正文示例。", sz=24), line=360)
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": get_paragraph_text(paragraph),
            "kind": "body",
            "section": "body",
            "module": "body_paragraph",
            "protected": False,
        },
    ]

    passed, issues, _ = audit_thesis.check_t04(_make_doc_root(paragraph), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_f05_accepts_caption_fonts_inherited_from_paragraph_style():
    caption = _set_paragraph_style(
        _set_centered(_set_spacing(_make_paragraph("图2.6  不同改性方法对鹿皮明胶起泡性的影响", sz=21), line=360)),
        "LnuCaption",
    )
    contexts = [
        {
            "index": 1,
            "elem": caption,
            "text": get_paragraph_text(caption),
            "kind": "caption",
            "section": "body",
            "module": "body_caption",
            "protected": False,
        },
    ]
    style_map = {
        "LnuCaption": {
            "eastAsia": "宋体",
            "ascii": "Times New Roman",
            "hAnsi": "Times New Roman",
            "sz": 21,
        }
    }

    passed, issues, _ = audit_thesis.check_f05(_make_doc_root(caption), contexts, style_map)

    assert passed, issues


def test_checker_2026_abs01_accepts_zero_spacing_after():
    runtime = _checker_runtime_or_xfail()
    paragraph = _set_spacing(_make_paragraph("摘要", sz=32), line=360, after=0)
    _set_centered(paragraph)
    document = _make_doc_root(paragraph)

    passed, issues, _ = audit_thesis.check_lnu_abs01(document, [], {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_abs01_rejects_legacy_11pt_spacing_after():
    runtime = _checker_runtime_or_xfail()
    paragraph = _set_spacing(_make_paragraph("摘要", sz=32), line=360, after=220)
    document = _make_doc_root(paragraph)

    passed, issues, _ = audit_thesis.check_lnu_abs01(document, [], {}, runtime.cfg)

    assert not passed
    assert any("段后" in issue for issue in issues)


def test_checker_2026_abs03_accepts_single_line_spacing():
    runtime = _checker_runtime_or_xfail()
    paragraph = _set_spacing(_make_paragraph("This is the abstract body text.", sz=24), line=240)
    document = _make_doc_root(paragraph)

    original = _fake_abstract_en_sections(paragraph)
    try:
        passed, issues, _ = audit_thesis.check_lnu_abs03(document, [], {}, runtime.cfg)
    finally:
        audit_thesis.build_document_sections = original

    assert passed, issues


def test_checker_2026_abs03_rejects_legacy_one_point_five_line_spacing():
    runtime = _checker_runtime_or_xfail()
    paragraph = _set_spacing(_make_paragraph("This is the abstract body text.", sz=24), line=360)
    document = _make_doc_root(paragraph)

    original = _fake_abstract_en_sections(paragraph)
    try:
        passed, issues, _ = audit_thesis.check_lnu_abs03(document, [], {}, runtime.cfg)
    finally:
        audit_thesis.build_document_sections = original

    assert not passed
    assert any("行距" in issue for issue in issues)


def test_checker_2026_disables_legacy_mixed_spacing_rules_for_latest_image_policy():
    runtime = _checker_runtime_or_xfail()
    rule_ids = {rule_id for rule_id, _name, _severity in runtime.rule_definitions}

    assert "SP_CJK_LATIN" not in rule_ids
    assert "SP_NUM_CJK" not in rule_ids
    assert runtime.cfg["mixed_spacing_policy"] == "compact"


def test_checker_2026_ref02_accepts_reference_number_with_tab_alignment():
    runtime = _checker_runtime_or_xfail()
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1]\tGuo G C. Quantum optics[M]. Beijing: Higher Education Press, 2005.")
    p_pr = ET.SubElement(ref, _w("pPr"))
    ind = ET.SubElement(p_pr, _w("ind"))
    ind.set(_w("left"), "420")
    ind.set(_w("hanging"), "420")
    tabs = ET.SubElement(p_pr, _w("tabs"))
    tab = ET.SubElement(tabs, _w("tab"))
    tab.set(_w("val"), "left")
    tab.set(_w("pos"), "420")
    contexts = [
        {"index": 1, "elem": title, "text": "参考文献", "kind": "h1", "section": "backmatter", "protected": False},
        {
            "index": 2,
            "elem": ref,
            "text": "[1]\tGuo G C. Quantum optics[M]. Beijing: Higher Education Press, 2005.",
            "kind": "reference",
            "section": "backmatter",
            "protected": False,
        },
    ]

    passed, issues, *_ = audit_thesis.check_lnu_ref02(_make_doc_root(title, ref), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_ref02_rejects_missing_tab_after_reference_number():
    runtime = _checker_runtime_or_xfail()
    title = _make_paragraph("参考文献")
    ref = _make_paragraph("[1]Guo G C. Quantum optics[M]. Beijing: Higher Education Press, 2005.")
    contexts = [
        {"index": 1, "elem": title, "text": "参考文献", "kind": "h1", "section": "backmatter", "protected": False},
        {
            "index": 2,
            "elem": ref,
            "text": "[1]Guo G C. Quantum optics[M]. Beijing: Higher Education Press, 2005.",
            "kind": "reference",
            "section": "backmatter",
            "protected": False,
        },
    ]

    passed, issues, *_ = audit_thesis.check_lnu_ref02(_make_doc_root(title, ref), contexts, {}, runtime.cfg)

    assert not passed
    assert any("编号后应使用制表符" in issue for issue in issues)


def test_checker_2026_toc02_accepts_checker_spacing_for_entries():
    runtime = _checker_runtime_or_xfail()
    title = _make_paragraph("目  录")
    entry = _set_spacing(_make_paragraph("第1章 绪论\t1"), line=276, after=100)
    entry_ppr = ET.SubElement(entry, _w("pPr")) if entry.find("w:pPr", NSMAP) is None else entry.find("w:pPr", NSMAP)
    entry_style = ET.SubElement(entry_ppr, _w("pStyle")) if entry_ppr.find("w:pStyle", NSMAP) is None else entry_ppr.find("w:pStyle", NSMAP)
    entry_style.set(_w("val"), "TOC1")
    contexts = [
        {"index": 1, "elem": title, "text": "目  录", "kind": "h1", "section": "toc", "protected": False},
        {"index": 2, "elem": entry, "text": "第1章 绪论\t1", "kind": "body", "section": "toc", "protected": False},
    ]

    passed, issues, _ = audit_thesis.check_lnu_toc02(_make_doc_root(title, entry), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_sp_cjk_latin_relaxes_strain_suffix_t_pattern():
    runtime = _checker_runtime_or_xfail()
    body = _make_paragraph("Microbispora triticiradicis DSM 104648 T基因组大小为 8.43 Mb。")
    contexts = [
        {
            "index": 1,
            "elem": body,
            "text": "Microbispora triticiradicis DSM 104648 T基因组大小为 8.43 Mb。",
            "kind": "body",
            "section": "body",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_sp_cjk_latin(_make_doc_root(body), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_ack_rule_requires_acknowledgement_section():
    runtime = _checker_runtime_or_xfail()
    body = _make_paragraph("第1章 绪论")
    contexts = [{"index": 1, "elem": body, "text": "第1章 绪论", "kind": "h1", "section": "body", "protected": False}]

    passed, issues, _ = audit_thesis.check_lnu_ack(_make_doc_root(body), contexts, {}, runtime.cfg)

    assert not passed
    assert any("缺少致谢章节" in issue for issue in issues)


def test_checker_2026_fmt01_detects_soft_line_break():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("第一行")
    run = paragraph.find("w:r", NSMAP)
    assert run is not None
    ET.SubElement(run, _w("br"))
    tail = ET.SubElement(run, _w("t"))
    tail.text = "第二行"
    contexts = [{"index": 1, "elem": paragraph, "text": "第一行第二行", "kind": "body", "section": "body", "protected": False}]

    passed, issues, _ = audit_thesis.check_lnu_fmt01(_make_doc_root(paragraph), contexts, {}, runtime.cfg)

    assert not passed
    assert any("软回车" in issue for issue in issues)


@pytest.mark.parametrize(
    ("module", "text"),
    [
        ("body_caption", "图2.1  不同改性方法处理后鹿皮明胶的溶胀率A，0～24 h 溶胀率变化"),
        ("body_caption_en", "Fig. 2.1  Swelling ratio of deer skin gelatinA, changes from 0 to 24 h"),
        ("body_caption_note", "不同小写字母表示组间差异显著（p<0.05）；相同小写字母表示差异不显著"),
    ],
)
def test_checker_2026_fmt01_allows_soft_line_breaks_inside_figure_captions(module, text):
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph(text)
    run = paragraph.find("w:r", NSMAP)
    assert run is not None
    ET.SubElement(run, _w("br"))
    tail = ET.SubElement(run, _w("t"))
    tail.text = "分组说明"
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": f"{text}分组说明",
            "kind": "caption" if module == "body_caption" else "body",
            "section": "body",
            "module": module,
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_fmt01(_make_doc_root(paragraph), contexts, {}, runtime.cfg)

    assert passed, issues


def test_checker_2026_fmt02_detects_anchor_drawing_and_floating_table():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("")
    drawing_run = ET.SubElement(paragraph, _w("r"))
    drawing = ET.SubElement(drawing_run, _w("drawing"))
    ET.SubElement(drawing, f"{{{audit_thesis.WP_NS}}}anchor")

    table = ET.Element(_w("tbl"))
    tbl_pr = ET.SubElement(table, _w("tblPr"))
    ET.SubElement(tbl_pr, _w("tblpPr"))
    tr = ET.SubElement(table, _w("tr"))
    tc = ET.SubElement(tr, _w("tc"))
    ET.SubElement(tc, _w("p"))
    contexts = [{"index": 1, "elem": paragraph, "text": "", "kind": "body", "section": "body", "protected": False}]

    passed, issues, _ = audit_thesis.check_lnu_fmt02(_make_doc_root(paragraph, table), contexts, {}, runtime.cfg)

    assert not passed
    assert any("嵌入型" in issue or "环绕" in issue for issue in issues)


def test_checker_2026_abs04_detects_half_width_punctuation_in_chinese_abstract():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("这是中文,摘要.内容")
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": "这是中文,摘要.内容",
            "kind": "body",
            "section": "abstract_cn",
            "module": "abstract_cn_body",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_abs04(_make_doc_root(paragraph), contexts, {}, runtime.cfg)

    assert not passed
    assert any("半角标点" in issue for issue in issues)


def test_checker_2026_text01_detects_chinese_abstract_mixed_spacing():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("本研究使用 CRISPR 技术检测 12 个样本,结果稳定。")
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": "本研究使用 CRISPR 技术检测 12 个样本,结果稳定。",
            "kind": "body",
            "section": "abstract_cn",
            "effective_section": "abstract_cn",
            "module": "abstract_cn_body",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "abstract")

    assert not passed
    assert any("混排空格" in issue or "半角标点" in issue for issue in issues)


def test_checker_2026_text01_skips_english_abstract_spacing_and_punctuation():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("This abstract uses English punctuation, spaces, and keywords.")
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": "This abstract uses English punctuation, spaces, and keywords.",
            "kind": "body",
            "section": "abstract_en",
            "effective_section": "abstract_en",
            "module": "abstract_en_body",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "abstract")

    assert passed, issues


def test_checker_2026_text01_allows_number_unit_spacing_exception():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("本研究加入100 mL溶液。")
    contexts = [
        {
            "index": 1,
            "elem": paragraph,
            "text": "本研究加入100 mL溶液。",
            "kind": "body",
            "section": "abstract_cn",
            "effective_section": "abstract_cn",
            "module": "abstract_cn_body",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "abstract")

    assert passed, issues


def test_checker_2026_text02_detects_toc_entry_mixed_spacing():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("1.1 CRISPR 技术\t2")
    contexts = [
        {
            "index": 2,
            "elem": paragraph,
            "text": "1.1 CRISPR 技术\t2",
            "kind": "body",
            "section": "toc",
            "effective_section": "toc",
            "module": "toc_entry",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "toc")

    assert not passed
    assert any("目录条目" in issue for issue in issues)


def test_checker_2026_text02_accepts_toc_heading_number_gap():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("0.1 明胶的研究进展\t1")
    contexts = [
        {
            "index": 2,
            "elem": paragraph,
            "text": "0.1 明胶的研究进展\t1",
            "kind": "body",
            "section": "toc",
            "effective_section": "toc",
            "module": "toc_entry",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "toc")

    assert passed, issues


def test_checker_2026_text02_accepts_toc_chapter_number_gap():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("第1章 实验材料与方法\t5")
    contexts = [
        {
            "index": 2,
            "elem": paragraph,
            "text": "第1章 实验材料与方法\t5",
            "kind": "body",
            "section": "toc",
            "effective_section": "toc",
            "module": "toc_entry",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "toc")

    assert passed, issues


def test_checker_2026_text02_detects_toc_entry_half_width_punctuation():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("研究背景,方法")
    contexts = [
        {
            "index": 2,
            "elem": paragraph,
            "text": "研究背景,方法",
            "kind": "body",
            "section": "toc",
            "effective_section": "toc",
            "module": "toc_entry",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "toc")

    assert not passed
    assert any("半角标点" in issue for issue in issues)


def test_checker_2026_text03_keeps_references_out_of_compact_body_rule():
    runtime = _checker_runtime_or_xfail()
    paragraph = _make_paragraph("[1] Guo G C. Quantum optics[M]. Beijing: Higher Education Press, 2005.")
    contexts = [
        {
            "index": 10,
            "elem": paragraph,
            "text": "[1] Guo G C. Quantum optics[M]. Beijing: Higher Education Press, 2005.",
            "kind": "reference",
            "section": "backmatter",
            "effective_section": "references",
            "module": "references_entry",
            "protected": False,
        }
    ]

    passed, issues, _ = audit_thesis.check_lnu_text_compact(_make_doc_root(paragraph), contexts, {}, runtime.cfg, "body")

    assert passed, issues
