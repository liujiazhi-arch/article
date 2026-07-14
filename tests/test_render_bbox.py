from pathlib import Path

from docx import Document

import thesis_tool.render_verify as render_verify_module
import thesis_tool.render_sources as render_sources_module
from thesis_tool.render_bbox import attach_text_line_spans


def test_build_evidence_items_validates_bbox_and_keeps_unlocatable_findings(tmp_path):
    page1 = tmp_path / "page-1.png"
    page2 = tmp_path / "page-2.png"
    page1.write_bytes(b"png")
    page2.write_bytes(b"png")

    items = render_verify_module._build_evidence_items(
        [
            {
                "id": "isolated_punctuation",
                "rule_id": "render.isolated_punctuation",
                "severity": "warning",
                "page": 2,
                "bbox": {"x": 0.12, "y": 0.64, "w": 0.72, "h": 0.18},
                "text_spans": [
                    {"text": "，", "bbox": {"x": 0.48, "y": 0.74, "w": 0.02, "h": 0.03}},
                    {"text": "", "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.03}},
                    {"text": "。", "bbox": {"x": 1.2, "y": 0.2, "w": 0.2, "h": 0.03}},
                ],
                "message": "页面文本存在单独成行的标点，疑似换行或排版挤压导致。",
                "suggested_action": "回到 WPS/Word 检查该处换行、字距和段落排版，调整后重新导出 PDF。",
                "suggested_scope": "body_paragraphs",
                "image_path": str(page2),
            },
            {
                "id": "pdf_text_missing",
                "severity": "info",
                "page": 1,
                "bbox": {"x": 1.2, "y": 0.2, "w": 0.2, "h": 0.2},
                "message": "PDF 文本不可读",
            },
            {
                "id": "manual_review",
                "severity": "warning",
                "page": 1,
                "message": "需要人工复核页面",
            },
        ],
        page_images=[str(page1), str(page2)],
    )

    assert items[0] == {
        "page": 2,
        "screenshot_path": str(page2.resolve()),
        "rule_id": "render.isolated_punctuation",
        "bbox": {"x": 0.12, "y": 0.64, "w": 0.72, "h": 0.18},
        "text_spans": [{"text": "，", "bbox": {"x": 0.48, "y": 0.74, "w": 0.02, "h": 0.03}}],
        "message": "页面文本存在单独成行的标点，疑似换行或排版挤压导致。",
        "severity": "warning",
        "next_action": "回到 WPS/Word 检查该处换行、字距和段落排版，调整后重新导出 PDF。",
        "suggested_scope": "body_paragraphs",
        "fix_mode": "manual",
    }
    assert items[1]["screenshot_path"] == str(page1.resolve())
    assert items[1]["bbox"] is None
    assert items[1]["message"] == "PDF 文本不可读"
    assert items[2]["bbox"] is None
    assert items[2]["next_action"] == "回到 DOCX 调整对应版式问题后重新导出 PDF。"


def test_attach_text_line_spans_replaces_heuristic_boxes_only_when_matches_are_unambiguous():
    findings = [
        {
            "page": 1,
            "rule_id": "render.isolated_punctuation",
            "punctuation": "，",
            "bbox": {"x": 0, "y": 0, "w": 1, "h": 1},
        },
        {
            "page": 2,
            "rule_id": "render.formula_number_split_page",
            "formula_number": "（ 1.2 ）",
            "bbox": {"x": 0, "y": 0, "w": 1, "h": 0.12},
        },
        {
            "page": 3,
            "rule_id": "render.heading_orphan_at_page_bottom",
            "heading_text": "1.1 研究背景",
            "bbox": {"x": 0, "y": 0.7, "w": 1, "h": 0.12},
        },
        {
            "page": 4,
            "rule_id": "render.heading_orphan_at_page_bottom",
            "heading_text": "2.1 重复标题",
            "bbox": {"x": 0, "y": 0.7, "w": 1, "h": 0.12},
        },
        {
            "page": 4,
            "rule_id": "render.heading_orphan_at_page_bottom",
            "heading_text": "2.1 重复标题",
            "bbox": {"x": 0, "y": 0.7, "w": 1, "h": 0.12},
        },
    ]
    lines = {
        1: [{"text": "，", "bbox": {"x": 0.48, "y": 0.74, "w": 0.02, "h": 0.03}}],
        2: [{"text": "(1.2)", "bbox": {"x": 0.82, "y": 0.03, "w": 0.08, "h": 0.025}}],
        3: [{"text": "1.1研究背景", "bbox": {"x": 0.12, "y": 0.81, "w": 0.28, "h": 0.028}}],
        4: [
            {"text": "2.1重复标题", "bbox": {"x": 0.12, "y": 0.2, "w": 0.28, "h": 0.028}},
            {"text": "2.1重复标题", "bbox": {"x": 0.12, "y": 0.8, "w": 0.28, "h": 0.028}},
        ],
    }

    resolved = attach_text_line_spans(findings, lines)

    assert [item["bbox"] for item in resolved[:3]] == [lines[1][0]["bbox"], lines[2][0]["bbox"], lines[3][0]["bbox"]]
    assert [item["text_spans"][0]["text"] for item in resolved[:3]] == ["，", "（ 1.2 ）", "1.1 研究背景"]
    for item in resolved[3:]:
        assert item["bbox"] is None
        assert "text_spans" not in item
    assert findings[0]["bbox"] == {"x": 0, "y": 0, "w": 1, "h": 1}


def test_extract_pdf_line_boxes_logs_whole_page_fallback(monkeypatch, caplog):
    def fail(_path):
        raise RuntimeError("broken text layer")

    monkeypatch.setattr(render_verify_module, "_extract_pdf_line_boxes_with_pdfium", fail)

    with caplog.at_level("WARNING"):
        assert render_verify_module._extract_pdf_line_boxes("broken.pdf") == {}

    assert "降级为整页证据" in caplog.text

def test_build_render_verify_report_adds_evidence_items(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_evidence_source.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.save(source_path)

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
        return {
            "findings": [
                {
                    "id": "isolated_punctuation",
                    "rule_id": "render.isolated_punctuation",
                    "severity": "warning",
                    "page": 2,
                    "bbox": {"x": 0.08, "y": 0.72, "w": 0.84, "h": 0.2},
                    "message": "页面文本存在单独成行的标点，疑似换行或排版挤压导致。",
                    "actionable": True,
                    "suggested_action": "回到 WPS/Word 检查该处换行、字距和段落排版，调整后重新导出 PDF。",
                    "image_path": page_images[1],
                    "punctuation": "，",
                },
                {
                    "id": "manual_review",
                    "severity": "info",
                    "page": 1,
                    "message": "需要人工复核页面。",
                },
            ],
            "summary": {
                "finding_count": 2,
                "highest_severity": "warning",
                "blank_page_count": 0,
                "render_suspect_count": 0,
                "actionable_finding_count": 1,
            },
            "layout_score": {"score": 100, "penalty": 0, "actionable_finding_count": 0},
        }

    monkeypatch.setattr(render_sources_module, "_run_render_engine", fake_run_render_engine)
    monkeypatch.setattr(render_verify_module, "analyze_page_images", fake_analyze_page_images)
    monkeypatch.setattr(
        render_verify_module,
        "_extract_pdf_line_boxes",
        lambda *_args: {2: [{"text": "，", "bbox": {"x": 0.48, "y": 0.74, "w": 0.02, "h": 0.03}}]},
    )
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
            "selected_scopes": ["figures_tables"],
            "overall_status": "verified",
            "readiness": "structure-ready",
            "manual_review_rule_ids": [],
            "unsupported_rule_ids": [],
        },
    )

    report = render_verify_module.build_render_verify_report(str(source_path), profile_path="lnu")

    assert [finding["id"] for finding in report["render_findings"]] == ["isolated_punctuation", "manual_review"]
    assert report["summary"]["evidence_item_count"] == 2
    assert report["summary"]["isolated_punctuation_count"] == 1
    assert report["summary"]["review_item_count"] == 5
    assert report["evidence_items"][0]["rule_id"] == "render.isolated_punctuation"
    assert report["evidence_items"][0]["bbox"] == {"x": 0.48, "y": 0.74, "w": 0.02, "h": 0.03}
    assert report["evidence_items"][0]["text_spans"] == [
        {"text": "，", "bbox": {"x": 0.48, "y": 0.74, "w": 0.02, "h": 0.03}}
    ]
    assert report["evidence_items"][0]["screenshot_path"].endswith("page-2.png")
    assert report["evidence_items"][1]["bbox"] is None
