from pathlib import Path

from docx import Document

import thesis_tool.render_verify as render_verify_module


def test_build_render_verify_report_writes_json_and_collects_pages(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_source.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.save(source_path)

    def fake_run_render_engine(input_docx: str, output_dir: str, renderer: str) -> dict:
        page_dir = Path(output_dir) / "word_pdf_pages"
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "page-1.png").write_bytes(b"png")
        pdf_path = Path(output_dir) / "render_verify_word.pdf"
        pdf_path.write_bytes(b"pdf")
        return {
            "engine": "word-pdf",
            "page_dir": str(page_dir),
            "pdf_path": str(pdf_path),
            "fallback_used": False,
            "warnings": [],
        }

    monkeypatch.setattr(render_verify_module, "_run_render_engine", fake_run_render_engine)
    monkeypatch.setattr(
        render_verify_module,
        "build_document_preflight",
        lambda *args, **kwargs: {
            "preflight_status": "warning",
            "toc_status": "field_only",
            "preface_status": "not_detected",
            "heading_renumber_guard": {"status": "warn", "reason": "table_risk"},
            "style_conflict_count": 0,
            "table_heading_risk_count": 2,
            "recommended_actions": ["先复核目录域刷新。"],
            "diagnostics": {
                "toc": {"status": "field_only"},
                "heading_renumber_guard": {"status": "warn", "reason": "table_risk"},
            },
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
            "selected_scopes": ["headings"],
            "overall_status": "verified",
            "readiness": "structure-ready",
            "manual_review_rule_ids": [],
            "unsupported_rule_ids": [],
        },
    )

    report = render_verify_module.build_render_verify_report(
        str(source_path),
        profile_path="lnu",
        scopes=["headings"],
    )

    assert report["document"]["name"] == "render_verify_source.docx"
    assert report["render_engine"] == "word-pdf"
    assert report["render_pdf_path"].endswith("render_verify_word.pdf")
    assert report["render_page_dir"].endswith("word_pdf_pages")
    assert report["page_count"] == 1
    assert report["page_images"][0].endswith("page-1.png")
    assert report["structure_readiness"] == "structure-ready"
    assert report["readiness"] == "render-check-required"
    assert report["preflight_status"] == "warning"
    assert report["render_evidence_status"] == "render-review-required"
    assert report["wild_doc"]["detected"] is True
    assert report["wild_doc"]["signals"][0]["id"] == "toc_structure"
    assert report["summary"]["wild_doc_signal_count"] == 2
    assert Path(report["report_path"]).exists()


def test_build_render_verify_report_records_auto_fallback(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_fallback_source.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.save(source_path)

    def fake_run_render_engine(input_docx: str, output_dir: str, renderer: str) -> dict:
        page_dir = Path(output_dir)
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "page-1.png").write_bytes(b"png")
        return {
            "engine": "artifact-tool",
            "page_dir": str(page_dir),
            "pdf_path": None,
            "fallback_used": True,
            "warnings": ["Word PDF 渲染不可用，已回退 artifact-tool: mock"],
        }

    monkeypatch.setattr(render_verify_module, "_run_render_engine", fake_run_render_engine)
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

    report = render_verify_module.build_render_verify_report(str(source_path), profile_path="lnu")

    assert report["render_engine"] == "artifact-tool"
    assert report["render_fallback_used"] is True
    assert report["summary"]["render_fallback_used"] is True
    assert "Word PDF 渲染不可用" in report["render_warnings"][0]


def test_render_render_verify_report_includes_review_summary():
    report = {
        "document": {"name": "demo.docx"},
        "profile": {"display": "lnu-checker-2026 (requested: lnu)"},
        "render_engine": "word-pdf",
        "render_page_dir": "/tmp/render-proof/word_pdf_pages",
        "render_pdf_path": "/tmp/render-proof/render_verify_word.pdf",
        "render_fallback_used": False,
        "render_warnings": [],
        "overall_status": "verified",
        "readiness": "render-check-required",
        "preflight_status": "warning",
        "render_evidence_status": "render-review-required",
        "output_dir": "/tmp/render-proof",
        "page_count": 2,
        "report_path": "/tmp/render-proof/render_verify_report.json",
        "selected_scopes": ["headings", "figures_tables"],
        "wild_doc": {
            "detected": True,
            "signals": [
                {
                    "id": "table_heading_candidates",
                    "severity": "warning",
                    "message": "发现 2 个表格伪标题候选。",
                }
            ],
        },
        "review_items": ["逐页检查页底空白。", "逐页检查公式横线。"],
    }

    rendered = render_verify_module.render_render_verify_report(report)

    assert "文件: demo.docx" in rendered
    assert "渲染引擎: word-pdf" in rendered
    assert "Word PDF: /tmp/render-proof/render_verify_word.pdf" in rendered
    assert "可提交状态: render-check-required" in rendered
    assert "预检状态: warning" in rendered
    assert "渲染证据状态: render-review-required" in rendered
    assert "渲染证据目录: /tmp/render-proof" in rendered
    assert "复核范围: headings, figures_tables" in rendered
    assert "野生文档信号：" in rendered
    assert "table_heading_candidates [warning]" in rendered
    assert "- 逐页检查公式横线。" in rendered
