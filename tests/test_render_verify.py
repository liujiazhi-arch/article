from pathlib import Path

from docx import Document

import thesis_tool.render_verify as render_verify_module


def test_build_render_verify_report_writes_json_and_collects_pages(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_source.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.save(source_path)

    def fake_run_render_docx(input_docx: str, output_dir: str) -> None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "page-1.png").write_bytes(b"png")

    monkeypatch.setattr(render_verify_module, "_run_render_docx", fake_run_render_docx)
    monkeypatch.setattr(
        render_verify_module,
        "build_document_diagnostics",
        lambda *args, **kwargs: {
            "toc": {"status": "field_only"},
            "heading_renumber_guard": {"status": "warn", "reason": "table_risk"},
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
    assert report["page_count"] == 1
    assert report["page_images"][0].endswith("page-1.png")
    assert report["readiness"] == "structure-ready"
    assert Path(report["report_path"]).exists()


def test_render_render_verify_report_includes_review_summary():
    report = {
        "document": {"name": "demo.docx"},
        "profile": {"display": "lnu-checker-2026 (requested: lnu)"},
        "overall_status": "verified",
        "readiness": "render-check-required",
        "output_dir": "/tmp/render-proof",
        "page_count": 2,
        "report_path": "/tmp/render-proof/render_verify_report.json",
        "selected_scopes": ["headings", "figures_tables"],
        "review_items": ["逐页检查页底空白。", "逐页检查公式横线。"],
    }

    rendered = render_verify_module.render_render_verify_report(report)

    assert "文件: demo.docx" in rendered
    assert "可提交状态: render-check-required" in rendered
    assert "渲染证据目录: /tmp/render-proof" in rendered
    assert "复核范围: headings, figures_tables" in rendered
    assert "- 逐页检查公式横线。" in rendered
