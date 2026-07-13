from pathlib import Path
from types import SimpleNamespace

from docx import Document
import pytest

import thesis_tool.render_verify as render_verify_module


def test_extract_pdf_page_texts_uses_pdfium_when_pdftotext_is_missing(monkeypatch, tmp_path):
    pdf_path = tmp_path / "rendered.pdf"
    pdf_path.write_bytes(b"%PDF")

    def missing_poppler():
        raise RuntimeError("pdftotext missing")

    monkeypatch.setattr(render_verify_module, "_find_pdftotext", missing_poppler)
    monkeypatch.setattr(
        render_verify_module,
        "_extract_pdf_text_pages_with_pdfium",
        lambda _path: ["第一页正文", "第 2 章 实验材料与方法"],
        raising=False,
    )

    page_texts, summary = render_verify_module._extract_pdf_page_texts(str(pdf_path), page_count=2)

    assert page_texts == {1: "第一页正文", 2: "第 2 章 实验材料与方法"}
    assert summary["available"] is True
    assert summary["page_text_extraction_warning_count"] == 0

def test_extract_pdf_page_texts_splits_pdftotext_form_feeds(monkeypatch, tmp_path):
    pdf_path = tmp_path / "rendered.pdf"
    pdf_path.write_bytes(b"%PDF")

    def fake_run(command, **kwargs):
        assert command[-2:] == [str(pdf_path.resolve()), "-"]
        return SimpleNamespace(stdout="第一页正文\f第 2 章 实验材料与方法\f")

    monkeypatch.setattr(render_verify_module, "_find_pdftotext", lambda: "pdftotext")
    monkeypatch.setattr(render_verify_module.subprocess, "run", fake_run)

    page_texts, summary = render_verify_module._extract_pdf_page_texts(str(pdf_path), page_count=2)

    assert page_texts == {1: "第一页正文", 2: "第 2 章 实验材料与方法"}
    assert summary == {
        "source": "pdf",
        "available": True,
        "page_text_available_count": 2,
        "page_text_extraction_warning_count": 0,
        "warnings": [],
    }

@pytest.mark.parametrize(
    ("punctuation_bbox", "expected_text"),
    [
        ('xMin="518" yMin="644" xMax="530" yMax="659"', "正文末尾，\n下一行"),
        ('xMin="518" yMin="620" xMax="530" yMax="635"', "正文末尾\n，\n下一行"),
        ('xMin="96" yMin="644" xMax="108" yMax="659"', "正文末尾\n，\n下一行"),
    ],
    ids=["trailing-same-baseline", "different-baseline", "punctuation-left-of-text"],
)
def test_extract_pdf_page_texts_merges_only_trailing_same_baseline_punctuation(
    monkeypatch,
    tmp_path,
    punctuation_bbox,
    expected_text,
):
    pdf_path = tmp_path / "rendered.pdf"
    pdf_path.write_bytes(b"%PDF")
    bbox_output = f"""\
<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
  <page width="595" height="842"><flow><block>
    <line xMin="108" yMin="642" xMax="524" yMax="659"><word>正文末尾</word></line>
    <line {punctuation_bbox}><word>，</word></line>
    <line xMin="85" yMin="668" xMax="502" yMax="683"><word>下一行</word></line>
  </block></flow></page>
</doc></body></html>
"""

    def fake_run(command, **kwargs):
        output = bbox_output if "-bbox-layout" in command else "正文末尾\n，\n下一行\f"
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(render_verify_module, "_find_pdftotext", lambda: "pdftotext")
    monkeypatch.setattr(render_verify_module.subprocess, "run", fake_run)

    page_texts, _summary = render_verify_module._extract_pdf_page_texts(str(pdf_path), page_count=1)

    assert page_texts == {1: expected_text}

@pytest.mark.parametrize(
    ("page_texts", "text_summary", "expected_status"),
    [
        (
            {1: "第一页正文", 2: "第 2 章 实验材料与方法"},
            {
                "source": "pdf",
                "available": True,
                "page_text_available_count": 2,
                "page_text_extraction_warning_count": 0,
                "warnings": [],
            },
            "render-evidence-ready",
        ),
        (
            {},
            {
                "source": "pdf",
                "available": False,
                "page_text_available_count": 0,
                "page_text_extraction_warning_count": 0,
                "warnings": [],
            },
            "render-review-required",
        ),
        (
            {1: "第一页正文"},
            {
                "source": "pdf",
                "available": True,
                "page_text_available_count": 1,
                "page_text_extraction_warning_count": 0,
                "warnings": [],
            },
            "render-review-required",
        ),
        (
            {1: "第一页正文", 2: "第 2 章 实验材料与方法"},
            {
                "source": "pdf",
                "available": True,
                "page_text_available_count": 2,
                "page_text_extraction_warning_count": 1,
                "warnings": ["PDF 文本抽取需要人工确认。"],
            },
            "render-review-required",
        ),
    ],
    ids=["complete-text", "scanned-pdf", "partial-text", "extraction-warning"],
)
def test_build_render_verify_report_requires_usable_pdf_text(
    monkeypatch,
    tmp_path,
    page_texts,
    text_summary,
    expected_status,
):
    source_path = tmp_path / "render_verify_text_source.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.save(source_path)
    captured = {}

    def fake_run_render_engine(input_docx: str, output_dir: str, renderer: str) -> dict:
        page_dir = Path(output_dir) / "word_pdf_pages"
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "page-1.png").write_bytes(b"png")
        (page_dir / "page-2.png").write_bytes(b"png")
        pdf_path = Path(output_dir) / "render_verify_word.pdf"
        pdf_path.write_bytes(b"pdf")
        return {
            "engine": "word-pdf",
            "page_dir": str(page_dir),
            "pdf_path": str(pdf_path),
            "fallback_used": False,
            "warnings": [],
        }

    def fake_analyze_page_images(page_images, **kwargs):
        captured["page_texts"] = kwargs.get("page_texts")
        return {
            "findings": [],
            "summary": {
                "finding_count": 0,
                "highest_severity": None,
                "blank_page_count": 0,
                "large_blank_count": 0,
                "render_suspect_count": 0,
            },
            "layout_score": {
                "score": 100,
                "penalty": 0,
                "expected_blank_count": 0,
                "actionable_finding_count": 0,
                "object_flow_issue_count": 0,
                "heading_break_issue_count": 0,
                "render_integrity_issue_count": 0,
            },
        }

    monkeypatch.setattr(render_verify_module, "_run_render_engine", fake_run_render_engine)
    monkeypatch.setattr(
        render_verify_module,
        "_extract_pdf_page_texts",
        lambda pdf_path, *, page_count: (page_texts, text_summary),
        raising=False,
    )
    monkeypatch.setattr(render_verify_module, "analyze_page_images", fake_analyze_page_images)
    monkeypatch.setattr(
        render_verify_module,
        "build_document_preflight",
        lambda *args, **kwargs: {
            "preflight_status": "ready",
            "toc_status": "generated_toc",
            "preface_status": "not_detected",
            "heading_renumber_guard": {"status": "clear"},
            "style_conflict_count": 0,
            "table_heading_risk_count": 0,
            "recommended_actions": [],
            "diagnostics": {"toc": {"status": "generated_toc"}, "heading_renumber_guard": {"status": "clear"}},
        },
    )
    monkeypatch.setattr(
        render_verify_module,
        "build_scope_verify",
        lambda *args, **kwargs: {
            "profile_id": "lnu-checker-2026",
            "requested_profile": "lnu",
            "fallback_used": False,
            "profile_display": "lnu-checker-2026 (requested: lnu)",
            "selected_scopes": None,
            "overall_status": "verified",
            "readiness": "structure-ready",
            "manual_review_rule_ids": [],
            "unsupported_rule_ids": [],
        },
    )

    report = render_verify_module.build_render_verify_report(str(source_path), profile_path="lnu", renderer="word-pdf")

    assert captured["page_texts"] == page_texts
    assert report["render_text_summary"] == text_summary
    assert report["summary"]["page_text_available_count"] == text_summary["page_text_available_count"]
    assert report["render_evidence_status"] == expected_status
    assert report["layout_score"]["score"] == 100
    assert report["summary"]["layout_score"] == 100
