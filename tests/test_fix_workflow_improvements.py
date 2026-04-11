from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import audit_thesis
import pytest
import fix_thesis
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from thesis_tool.workflow import apply_scoped_fix, build_scoped_fix_preview, render_scoped_fix_preview

from .conftest import audit_rule_status, make_compliant_doc


def _paragraph_by_prefix(doc: Document, prefix: str):
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith(prefix):
            return paragraph
    raise AssertionError(f"Paragraph not found: {prefix}")


def _add_mock_drawing(paragraph) -> None:
    run = paragraph.add_run()
    run._r.append(OxmlElement("w:drawing"))


def _spacing_attrs(paragraph):
    spacing = paragraph._p.pPr.find(qn("w:spacing")) if paragraph._p.pPr is not None else None
    if spacing is None:
        return None, None, None
    return spacing.get(qn("w:before")), spacing.get(qn("w:after")), spacing.get(qn("w:line"))


def _inject_existing_footer_page_field(docx_path: Path):
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    ns = {"w": w_ns}

    with zipfile.ZipFile(docx_path, "r") as zf:
        parts = {name: zf.read(name) for name in zf.namelist()}

    rels_root = ET.fromstring(parts["word/_rels/document.xml.rels"])
    rel = ET.SubElement(rels_root, f"{{{rel_ns}}}Relationship")
    rel.set("Id", "rIdFooterTest")
    rel.set("Type", f"{office_rel_ns}/footer")
    rel.set("Target", "footer1.xml")
    parts["word/_rels/document.xml.rels"] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    document_root = ET.fromstring(parts["word/document.xml"])
    sect_pr = document_root.find("w:body/w:sectPr", ns)
    assert sect_pr is not None
    footer_ref = ET.SubElement(sect_pr, f"{{{w_ns}}}footerReference")
    footer_ref.set(f"{{{w_ns}}}type", "default")
    footer_ref.set(f"{{{office_rel_ns}}}id", "rIdFooterTest")
    parts["word/document.xml"] = ET.tostring(document_root, encoding="utf-8", xml_declaration=True)

    footer_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{w_ns}">
  <w:p>
    <w:pPr/>
    <w:r><w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
    <w:r><w:fldChar w:fldCharType="separate"/></w:r>
    <w:r><w:t>1</w:t></w:r>
    <w:r><w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:ftr>"""
    parts["word/footer1.xml"] = footer_xml.encode("utf-8")

    content_types_root = ET.fromstring(parts["[Content_Types].xml"])
    override = ET.SubElement(content_types_root, f"{{{ct_ns}}}Override")
    override.set("PartName", "/word/footer1.xml")
    override.set("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml")
    parts["[Content_Types].xml"] = ET.tostring(content_types_root, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in parts.items():
            zf.writestr(name, payload)


def test_scoped_fix_dry_run_returns_preview_without_writing_output(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="scoped_fix_preview_source.docx")
    preview_path = Path(tmp_path) / "scoped_fix_preview_output.docx"

    preview = build_scoped_fix_preview(
        str(source_path),
        output_path=str(preview_path),
        profile_path="cn-common",
        scopes=["headings"],
    )

    assert preview["selected_scopes"] == ["headings"]
    assert preview["renumber_headings"] is False
    assert not preview_path.exists()

    rendered = render_scoped_fix_preview(preview)
    assert "dry-run: 是" in rendered
    assert "修复范围: headings" in rendered
    assert "预计会触达的模块" in rendered


def test_fix_docx_keeps_heading_numbers_when_renumber_not_enabled(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="renumber_default_source.docx")
    doc = Document(source_path)
    _paragraph_by_prefix(doc, "第一章").runs[0].text = "0 引言"
    _paragraph_by_prefix(doc, "1.1 研究背景").runs[0].text = "0.1 研究背景"
    _paragraph_by_prefix(doc, "1.1.1 研究现状").runs[0].text = "0.1.1 研究现状"
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "renumber_default_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="cn-common",
        scopes=["headings"],
    )

    fixed_doc = Document(fixed_path)
    assert _paragraph_by_prefix(fixed_doc, "0 引言").text == "0 引言"
    assert _paragraph_by_prefix(fixed_doc, "0.1 研究背景").text == "0.1 研究背景"
    assert _paragraph_by_prefix(fixed_doc, "0.1.1 研究现状").text == "0.1.1 研究现状"


def test_fix_docx_can_renumber_headings_when_opted_in(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="renumber_optin_source.docx")
    doc = Document(source_path)
    _paragraph_by_prefix(doc, "第一章").runs[0].text = "0 引言"
    _paragraph_by_prefix(doc, "1.1 研究背景").runs[0].text = "0.1 研究背景"
    _paragraph_by_prefix(doc, "1.1.1 研究现状").runs[0].text = "0.1.1 研究现状"
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "renumber_optin_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="cn-common",
        scopes=["headings"],
        renumber_headings=True,
    )

    fixed_doc = Document(fixed_path)
    assert _paragraph_by_prefix(fixed_doc, "1 引言").text == "1 引言"
    assert _paragraph_by_prefix(fixed_doc, "1.1 研究背景").text == "1.1 研究背景"
    assert _paragraph_by_prefix(fixed_doc, "1.1.1 研究现状").text == "1.1.1 研究现状"


def test_heading_style_prepass_identifies_and_repairs_heading_like_paragraphs(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="heading_prepass_source.docx")
    doc = Document(source_path)
    heading = _paragraph_by_prefix(doc, "1.1 研究背景")
    heading.style = doc.styles["Normal"]
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save(source_path)

    preview_before = build_scoped_fix_preview(
        str(source_path),
        profile_path="cn-common",
        scopes=["headings"],
    )
    assert preview_before["heading_style_candidates"] >= 1

    fixed_path = Path(tmp_path) / "heading_prepass_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="cn-common",
        scopes=["headings"],
    )

    h02_status = audit_rule_status(fixed_path, "H02")
    assert h02_status["rule"]["passed"], h02_status["rule"]["issues"]

    preview_after = build_scoped_fix_preview(
        str(fixed_path),
        profile_path="cn-common",
        scopes=["headings"],
    )
    assert preview_after["heading_style_candidates"] == 0


def test_body_scope_demotes_misstyled_heading_paragraph_to_body_style(tmp_path):
    source_path = Path(tmp_path) / "body_scope_demote_heading_style.docx"
    doc = Document()
    heading = doc.add_paragraph("1 绪论")
    heading.style = doc.styles["Heading 1"]
    paragraph = doc.add_paragraph("这是一个被误套用标题样式的正文句子，包含完整语义和句号。")
    paragraph.style = doc.styles["Heading 1"]
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "body_scope_demote_heading_style_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["body_paragraphs"],
    )

    fixed_doc = Document(fixed_path)
    fixed_paragraph = fixed_doc.paragraphs[1]
    assert fixed_paragraph.style.name == "Normal"


def test_body_scope_preserves_figure_note_paragraph_formatting(tmp_path):
    source_path = Path(tmp_path) / "body_scope_preserve_figure_note_source.docx"
    doc = Document()
    heading = doc.add_paragraph("2.1.1 溶胀特性分析")
    heading.style = doc.styles["Heading 3"]

    figure = doc.add_paragraph()
    figure.add_run("[mock figure]")

    caption = doc.add_paragraph("图2.1 不同改性条件筛选组样品的溶胀率与溶失率")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    note = doc.add_paragraph("注：（A）0.5～24 h 溶胀率变化曲线；（B）24 h 溶胀率。")
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note.paragraph_format.first_line_indent = 0
    note.paragraph_format.space_before = 0
    note.paragraph_format.space_after = 0
    note.paragraph_format.line_spacing = 1.0

    body = doc.add_paragraph("这是正文段落。")
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "body_scope_preserve_figure_note_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["body_paragraphs"],
    )

    fixed_doc = Document(fixed_path)
    fixed_note = next(paragraph for paragraph in fixed_doc.paragraphs if paragraph.text.startswith("注：（A）0.5"))

    assert fixed_note.alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert fixed_note.paragraph_format.first_line_indent in (0, None)
    spacing = fixed_note._p.pPr.find(qn("w:spacing"))
    assert spacing is not None
    assert spacing.get(qn("w:line")) in {"240", None}

    results, _score, _report = audit_thesis.audit_docx(str(fixed_path), profile_path="lnu")
    t03_status = next(item for item in results if item["id"] == "T03")
    t04_status = next(item for item in results if item["id"] == "T04")
    assert t03_status["passed"], t03_status["issues"]
    assert t04_status["passed"], t04_status["issues"]


def test_figures_scope_moves_post_figure_analysis_before_figure_block(tmp_path):
    source_path = Path(tmp_path) / "lnu_figure_reorder_source.docx"
    doc = Document()
    doc.add_paragraph("第2章 实验结果与分析").style = doc.styles["Heading 1"]
    doc.add_paragraph("2.1 不同改性技术鹿皮明胶改性条件的筛选").style = doc.styles["Heading 2"]
    doc.add_paragraph("2.1.1 溶胀特性分析").style = doc.styles["Heading 3"]

    figure = doc.add_paragraph()
    _add_mock_drawing(figure)

    caption = doc.add_paragraph("图2.1 不同改性条件筛选组样品的溶胀率与溶失率")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    note = doc.add_paragraph("注：（A）0.5～24 h 溶胀率变化曲线；（B）24 h 溶胀率；（C）24 h 溶失率。")
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph("不同改性条件对鹿皮明胶冻干凝胶溶胀行为具有明显影响，具体结果如图2.1 A、B 所示。")
    doc.add_paragraph("2.1.2 溶失特性分析").style = doc.styles["Heading 3"]
    doc.add_paragraph("各组样品 24 h 溶失率结果如图2.1 C 所示。")
    doc.add_paragraph("2.2 不同改性技术对鹿皮明胶功能特性的影响").style = doc.styles["Heading 2"]
    doc.save(source_path)

    before_results, _score, _report = audit_thesis.audit_docx(str(source_path), profile_path="lnu")
    before_f03 = next(item for item in before_results if item["id"] == "LNU_F03")
    before_f06 = next(item for item in before_results if item["id"] == "LNU_F06")
    assert not before_f03["passed"]
    assert not before_f06["passed"]

    fixed_path = Path(tmp_path) / "lnu_figure_reorder_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["figures_tables"],
    )

    fixed_doc = Document(fixed_path)
    paragraph_info = [
        (idx, paragraph.text.strip(), bool(paragraph._p.xpath(".//w:drawing")))
        for idx, paragraph in enumerate(fixed_doc.paragraphs)
    ]

    idx_analysis_1 = next(idx for idx, text, has_drawing in paragraph_info if text.startswith("不同改性条件对鹿皮明胶冻干凝胶溶胀行为"))
    idx_heading_212 = next(idx for idx, text, has_drawing in paragraph_info if text == "2.1.2 溶失特性分析")
    idx_analysis_2 = next(idx for idx, text, has_drawing in paragraph_info if text.startswith("各组样品 24 h 溶失率结果如图2.1 C 所示"))
    idx_drawing = next(idx for idx, text, has_drawing in paragraph_info if has_drawing)
    idx_caption = next(idx for idx, text, has_drawing in paragraph_info if text.startswith("图2.1 "))
    idx_note = next(idx for idx, text, has_drawing in paragraph_info if text.startswith("注："))
    idx_next_h2 = next(idx for idx, text, has_drawing in paragraph_info if text == "2.2 不同改性技术对鹿皮明胶功能特性的影响")

    assert idx_analysis_1 < idx_heading_212 < idx_analysis_2 < idx_drawing < idx_caption < idx_note < idx_next_h2
    assert not any(text.startswith("见图") or text.startswith("见表") for _, text, _ in paragraph_info)

    drawing_paragraph = fixed_doc.paragraphs[idx_drawing]
    caption_paragraph = fixed_doc.paragraphs[idx_caption]
    note_paragraph = fixed_doc.paragraphs[idx_note]
    drawing_before, drawing_after, drawing_line = _spacing_attrs(drawing_paragraph)
    caption_before, caption_after, caption_line = _spacing_attrs(caption_paragraph)
    note_before, note_after, note_line = _spacing_attrs(note_paragraph)

    assert drawing_before == "360"
    assert drawing_after in {None, "0"}
    assert caption_line == "360"
    assert note_line == "240"
    assert note_after == "360"

    results, _score, _report = audit_thesis.audit_docx(str(fixed_path), profile_path="lnu")
    lnu_f03 = next(item for item in results if item["id"] == "LNU_F03")
    lnu_f05 = next(item for item in results if item["id"] == "LNU_F05")
    lnu_f06 = next(item for item in results if item["id"] == "LNU_F06")
    assert lnu_f03["passed"], lnu_f03["issues"]
    assert lnu_f05["passed"], lnu_f05["issues"]
    assert lnu_f06["passed"], lnu_f06["issues"]


def test_figures_scope_converts_existing_blank_separator_to_structured_spacing(tmp_path):
    source_path = Path(tmp_path) / "lnu_figure_blank_separator_source.docx"
    doc = Document()
    doc.add_paragraph("第2章 实验结果与分析").style = doc.styles["Heading 1"]
    doc.add_paragraph("2.1.1 溶胀特性分析").style = doc.styles["Heading 3"]
    doc.add_paragraph("")
    figure = doc.add_paragraph()
    _add_mock_drawing(figure)
    caption = doc.add_paragraph("图2.1 不同改性条件筛选组样品的溶胀率与溶失率")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note = doc.add_paragraph("注：（A）0.5～24 h 溶胀率变化曲线；（B）24 h 溶胀率。")
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("")
    doc.add_paragraph("下文正文从这里开始。")
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "lnu_figure_blank_separator_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["figures_tables"],
    )

    fixed_doc = Document(fixed_path)
    paragraph_info = [
        (idx, paragraph.text.strip(), bool(paragraph._p.xpath(".//w:drawing")))
        for idx, paragraph in enumerate(fixed_doc.paragraphs)
    ]
    idx_drawing = next(idx for idx, text, has_drawing in paragraph_info if has_drawing)
    idx_note = next(idx for idx, text, has_drawing in paragraph_info if text.startswith("注："))
    drawing_before, _, _ = _spacing_attrs(fixed_doc.paragraphs[idx_drawing])
    _, note_after, _ = _spacing_attrs(fixed_doc.paragraphs[idx_note])

    assert drawing_before == "360"
    assert note_after == "360"


def test_heading_and_figure_scopes_share_gap_budget_without_over_spacing(tmp_path):
    source_path = Path(tmp_path) / "lnu_heading_figure_spacing_source.docx"
    doc = Document()
    doc.add_paragraph("第2章 实验结果与分析").style = doc.styles["Heading 1"]
    doc.add_paragraph("2.1.1 溶胀特性分析").style = doc.styles["Heading 3"]
    figure = doc.add_paragraph()
    _add_mock_drawing(figure)
    caption = doc.add_paragraph("图2.1 不同改性条件筛选组样品的溶胀率与溶失率")
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    note = doc.add_paragraph("注：（A）0.5～24 h 溶胀率变化曲线；（B）24 h 溶胀率。")
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("2.2 不同改性技术对鹿皮明胶功能特性的影响").style = doc.styles["Heading 2"]
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "lnu_heading_figure_spacing_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["headings", "figures_tables"],
    )

    fixed_doc = Document(fixed_path)
    paragraph_info = [
        (idx, paragraph.text.strip(), bool(paragraph._p.xpath(".//w:drawing")))
        for idx, paragraph in enumerate(fixed_doc.paragraphs)
    ]
    idx_drawing = next(idx for idx, text, has_drawing in paragraph_info if has_drawing)
    idx_note = next(idx for idx, text, has_drawing in paragraph_info if text.startswith("注："))
    drawing_before, _, _ = _spacing_attrs(fixed_doc.paragraphs[idx_drawing])
    _, note_after, _ = _spacing_attrs(fixed_doc.paragraphs[idx_note])

    assert drawing_before == "360"
    assert note_after == "240"

    results, _score, _report = audit_thesis.audit_docx(str(fixed_path), profile_path="lnu")
    lnu_f03 = next(item for item in results if item["id"] == "LNU_F03")
    lnu_f06 = next(item for item in results if item["id"] == "LNU_F06")
    assert lnu_f03["passed"], lnu_f03["issues"]
    assert lnu_f06["passed"], lnu_f06["issues"]


def test_page_scope_repairs_existing_footer_page_field(tmp_docx, tmp_path):
    source_path = Path(tmp_docx(make_compliant_doc, filename="existing_footer_page_source.docx"))
    _inject_existing_footer_page_field(source_path)

    fixed_path = Path(tmp_path) / "existing_footer_page_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["page"],
    )

    results, _score, _report = audit_thesis.audit_docx(str(fixed_path), profile_path="lnu")
    pg01 = next(item for item in results if item["id"] == "PG01")
    p03 = next(item for item in results if item["id"] == "P03")
    assert pg01["passed"], pg01["issues"]
    assert p03["passed"], p03["issues"]


def test_fix_docx_writes_reopenable_docx(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="atomic_write_reopen_source.docx")
    fixed_path = Path(tmp_path) / "atomic_write_reopen_fixed.docx"

    fix_thesis.fix_docx(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["headings"],
    )

    assert fixed_path.exists()
    with zipfile.ZipFile(fixed_path, "r") as zip_handle:
        assert zip_handle.testzip() is None
    reopened = Document(fixed_path)
    assert len(reopened.paragraphs) > 0


def test_fix_docx_validation_failure_keeps_existing_output(tmp_docx, tmp_path, monkeypatch):
    source_path = tmp_docx(make_compliant_doc, filename="atomic_write_failure_source.docx")
    output_path = Path(tmp_path) / "atomic_write_failure_output.docx"
    original_payload = b"previous-good-file"
    output_path.write_bytes(original_payload)

    def _raise_reopen_error(_path):
        raise RuntimeError("forced reopen failure")

    monkeypatch.setattr(fix_thesis, "Document", _raise_reopen_error)

    with pytest.raises(RuntimeError, match="python-docx"):
        fix_thesis.fix_docx(
            str(source_path),
            str(output_path),
            profile_path="lnu",
            scopes=["headings"],
        )

    assert output_path.read_bytes() == original_payload


def test_figures_scope_renumbers_split_run_lnu_captions(tmp_path):
    source_path = Path(tmp_path) / "split_run_caption_source.docx"
    doc = Document()
    heading = doc.add_paragraph("2 结果")
    heading.style = doc.styles["Heading 1"]

    caption = doc.add_paragraph()
    caption.style = "Caption"
    caption.add_run("图 ")
    caption.add_run("")
    caption.add_run("1")
    caption.add_run(" 鹿茸成分靶点与肝毒性靶点韦恩图")
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "split_run_caption_fixed.docx"
    apply_scoped_fix(
        str(source_path),
        str(fixed_path),
        profile_path="lnu",
        scopes=["figures_tables"],
    )

    fixed_doc = Document(fixed_path)
    texts = [paragraph.text for paragraph in fixed_doc.paragraphs]
    assert "图2.1 鹿茸成分靶点与肝毒性靶点韦恩图" in texts
