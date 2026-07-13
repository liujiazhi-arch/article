from pathlib import Path

from docx import Document

import thesis_tool.render_verify as render_verify_module


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

    monkeypatch.setattr(render_verify_module, "_run_render_engine", fake_run_render_engine)
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
    assert report["evidence_items"][0]["rule_id"] == "render.isolated_punctuation"
    assert report["evidence_items"][0]["bbox"] == {"x": 0.08, "y": 0.72, "w": 0.84, "h": 0.2}
    assert report["evidence_items"][0]["screenshot_path"].endswith("page-2.png")
    assert report["evidence_items"][1]["bbox"] is None

def test_bbox_page_lines_normalizes_real_pdf_coordinates():
    pages = render_verify_module._bbox_page_lines(
        """<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
        <page width="600" height="800"><flow><block>
        <line xMin="60" yMin="160" xMax="540" yMax="184"><word>1</word><word>绪论</word><word>2</word></line>
        </block></flow></page></doc></body></html>"""
    )

    assert pages == {
        1: [
            {
                "text": "1绪论2",
                "bbox": {"x": 0.1, "y": 0.2, "w": 0.8, "h": 0.03},
            }
        ]
    }
