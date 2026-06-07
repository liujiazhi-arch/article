from pathlib import Path
from types import SimpleNamespace

from docx import Document
import pytest

import thesis_tool.render_verify as render_verify_module


def test_word_pdf_export_script_targets_opened_file_not_active_document(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_word_source.docx"
    source_path.write_bytes(b"docx")
    output_pdf = tmp_path / "render_verify_word.pdf"
    captured = {}

    def fake_run(command, **kwargs):
        captured["script"] = command[2]
        output_pdf.write_bytes(b"%PDF")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(render_verify_module.sys, "platform", "darwin")
    monkeypatch.setattr(render_verify_module.shutil, "which", lambda name: "/usr/bin/osascript" if name == "osascript" else None)
    monkeypatch.setattr(render_verify_module.subprocess, "run", fake_run)

    render_verify_module._export_docx_to_pdf_with_word(str(source_path), str(output_pdf))

    assert "active document" not in captured["script"]
    assert "document 1" not in captured["script"]
    assert "close every document" in captured["script"]
    assert "did not expose the opened DOCX" in captured["script"]
    assert "save as docRef" in captured["script"]


def test_word_pdf_export_timeout_explains_word_automation_block(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_word_timeout.docx"
    source_path.write_bytes(b"docx")
    output_pdf = tmp_path / "render_verify_word.pdf"

    def fake_run(command, **kwargs):
        raise render_verify_module.subprocess.TimeoutExpired(command, timeout=kwargs["timeout"])

    monkeypatch.setattr(render_verify_module.sys, "platform", "darwin")
    monkeypatch.setattr(render_verify_module.shutil, "which", lambda name: "/usr/bin/osascript" if name == "osascript" else None)
    monkeypatch.setattr(render_verify_module.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Word 自动化没有完成"):
        render_verify_module._export_docx_to_pdf_with_word(str(source_path), str(output_pdf))


def test_build_render_verify_report_writes_markdown_and_collects_pages(monkeypatch, tmp_path):
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
        "analyze_page_images",
        lambda page_images, **kwargs: {
            "findings": [
                {
                    "id": "large_blank_region",
                    "severity": "warning",
                    "page": 1,
                    "region": {"x": 0.08, "y": 0.72, "w": 0.84, "h": 0.28},
                    "message": "页底存在大块连续空白。",
                    "suggested_scope": "figures_tables",
                    "evidence_source": kwargs.get("evidence_source"),
                }
            ],
            "summary": {
                "finding_count": 1,
                "highest_severity": "warning",
                "blank_page_count": 0,
                "large_blank_count": 1,
                "render_suspect_count": 0,
            },
        },
    )
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
    assert report["evidence_trust"] == "authoritative"
    assert report["evidence_authoritative"] is True
    assert report["layout_decision_eligible"] is True
    assert report["render_pdf_path"].endswith("render_verify_word.pdf")
    assert report["render_page_dir"].endswith("word_pdf_pages")
    assert report["page_count"] == 1
    assert report["page_images"][0].endswith("page-1.png")
    assert report["evidence_source"] == "word-pdf"
    assert report["render_findings"][0]["id"] == "large_blank_region"
    assert report["render_summary"]["large_blank_count"] == 1
    assert report["structure_readiness"] == "structure-ready"
    assert report["readiness"] == "render-check-required"
    assert report["preflight_status"] == "warning"
    assert report["render_evidence_status"] == "render-review-required"
    assert report["wild_doc"]["detected"] is True
    assert report["wild_doc"]["signals"][0]["id"] == "toc_structure"
    assert report["summary"]["wild_doc_signal_count"] == 2
    assert report["summary"]["render_finding_count"] == 1
    assert report["summary"]["render_highest_severity"] == "warning"
    report_path = Path(report["report_path"])
    assert report_path.name == "render_verify_report.md"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "文件: render_verify_source.docx" in report_text
    assert "自动页图判读" in report_text
    assert not report_text.lstrip().startswith("{")


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


def test_build_render_verify_report_passes_pdf_texts_to_analyzer(monkeypatch, tmp_path):
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
        lambda pdf_path, *, page_count: (
            {1: "第一页正文", 2: "第 2 章 实验材料与方法"},
            {
                "source": "pdf",
                "available": True,
                "page_text_available_count": 2,
                "page_text_extraction_warning_count": 0,
                "warnings": [],
            },
        ),
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

    assert captured["page_texts"] == {1: "第一页正文", 2: "第 2 章 实验材料与方法"}
    assert report["render_text_summary"]["available"] is True
    assert report["summary"]["page_text_available_count"] == 2
    assert report["layout_score"]["score"] == 100
    assert report["summary"]["layout_score"] == 100


def test_external_rendered_pdf_uses_neutral_manual_pdf_evidence_source(monkeypatch, tmp_path):
    pdf_path = tmp_path / "word-export.pdf"
    pdf_path.write_bytes(b"%PDF")

    monkeypatch.setattr(render_verify_module, "_convert_pdf_to_page_images", lambda *args, **kwargs: None)

    metadata = render_verify_module._run_external_pdf_render(str(pdf_path), str(tmp_path / "proof"))

    assert metadata["engine"] == "manual-pdf"


def test_build_render_review_items_explains_likely_causes():
    diagnostics = {
        "toc": {"status": "generated_toc"},
        "heading_renumber_guard": {"status": "clear"},
    }
    verification = {
        "manual_review_rule_ids": [],
        "unsupported_rule_ids": [],
        "render_findings": [
            {"id": "large_blank_region", "page": 3, "message": "页底存在大块连续空白。"},
            {"id": "object_overflow", "page": 5, "message": "图表整体被挤到后页。"},
            {"id": "heading_isolated", "page": 7, "message": "标题落在页尾，正文被挤到下一页。"},
        ],
    }

    items = render_verify_module._build_render_review_items(diagnostics, verification)
    text = "\n".join(items)

    assert "大块空白" in text
    assert "对象塞不进当前页" in text
    assert "图表挤页" in text
    assert "首次引用位置过晚" in text
    assert "标题孤页" in text
    assert "标题后正文不足" in text


def test_run_render_engine_auto_does_not_fallback_to_artifact(monkeypatch, tmp_path):
    def fake_word_pdf_render(input_docx: str, output_dir: str) -> dict:
        raise RuntimeError("Word PDF 渲染不可用: mock")

    monkeypatch.setattr(render_verify_module, "_run_word_pdf_render", fake_word_pdf_render)

    with pytest.raises(RuntimeError, match="Word PDF 渲染不可用"):
        render_verify_module._run_render_engine("demo.docx", str(tmp_path), "auto")


def test_run_render_engine_rejects_artifact_tool_renderer(tmp_path):
    with pytest.raises(ValueError, match="artifact-tool"):
        render_verify_module._run_render_engine("demo.docx", str(tmp_path), "artifact-tool")


def test_build_render_verify_report_accepts_external_page_images(monkeypatch, tmp_path):
    source_path = tmp_path / "render_verify_external_source.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.save(source_path)
    page_dir = tmp_path / "wps-pages"
    page_dir.mkdir()
    (page_dir / "page-1.png").write_bytes(b"png")

    monkeypatch.setattr(
        render_verify_module,
        "analyze_page_images",
        lambda page_images, **kwargs: {
            "findings": [],
            "summary": {
                "finding_count": 0,
                "highest_severity": None,
                "blank_page_count": 0,
                "large_blank_count": 0,
                "render_suspect_count": 0,
            },
        },
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
            "selected_scopes": ["toc"],
            "overall_status": "verified",
            "readiness": "structure-ready",
            "manual_review_rule_ids": [],
            "unsupported_rule_ids": [],
        },
    )

    report = render_verify_module.build_render_verify_report(
        str(source_path),
        profile_path="lnu",
        scopes=["toc"],
        page_images_dir=str(page_dir),
    )

    assert report["render_engine"] == "wps-manual-images"
    assert report["evidence_source"] == "wps-manual-images"
    assert report["evidence_trust"] == "authoritative"
    assert report["layout_decision_eligible"] is True
    assert report["render_page_dir"] == str(page_dir.resolve())
    assert report["page_images"] == [str((page_dir / "page-1.png").resolve())]


def test_render_render_verify_report_includes_review_summary():
    report = {
        "document": {"name": "demo.docx"},
        "profile": {"display": "lnu-checker-2026 (requested: lnu)"},
        "render_engine": "word-pdf",
        "evidence_source": "word-pdf",
        "evidence_trust": "authoritative",
        "layout_decision_eligible": True,
        "render_page_dir": "/tmp/render-proof/word_pdf_pages",
        "render_pdf_path": "/tmp/render-proof/render_verify_word.pdf",
        "render_fallback_used": False,
        "render_warnings": [],
        "layout_score": {"score": 82, "penalty": 18},
        "render_text_summary": {
            "source": "pdf",
            "available": True,
            "page_text_available_count": 2,
            "page_text_extraction_warning_count": 0,
            "warnings": [],
        },
        "overall_status": "verified",
        "readiness": "render-check-required",
        "preflight_status": "warning",
        "render_evidence_status": "render-review-required",
        "output_dir": "/tmp/render-proof",
        "page_count": 2,
        "report_path": "/tmp/render-proof/render_verify_report.md",
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
        "render_findings": [
            {
                "id": "large_blank_region",
                "severity": "warning",
                "page": 2,
                "region": {"x": 0.08, "y": 0.7, "w": 0.84, "h": 0.3},
                "message": "页底存在大块连续空白。",
            }
        ],
        "review_items": ["逐页检查页底空白。", "逐页检查公式横线。"],
    }

    rendered = render_verify_module.render_render_verify_report(report)

    assert "文件: demo.docx" in rendered
    assert "渲染引擎: word-pdf" in rendered
    assert "渲染证据来源: word-pdf" in rendered
    assert "渲染证据可信度: authoritative" in rendered
    assert "版式决策可用: 是" in rendered
    assert "Layout Score: 82 (penalty 18)" in rendered
    assert "PDF文本页数: 2" in rendered
    assert "渲染 PDF: /tmp/render-proof/render_verify_word.pdf" in rendered
    assert "自动页图判读：" in rendered
    assert "large_blank_region [warning]" in rendered
    assert "可提交状态: render-check-required" in rendered
    assert "预检状态: warning" in rendered
    assert "渲染证据状态: render-review-required" in rendered
    assert "渲染证据目录: /tmp/render-proof" in rendered
    assert "复核范围: headings, figures_tables" in rendered
    assert "野生文档信号：" in rendered
    assert "table_heading_candidates [warning]" in rendered
    assert "- 逐页检查公式横线。" in rendered


def test_render_render_verify_report_preserves_cause_oriented_review_items():
    report = {
        "document": {"name": "demo.docx"},
        "profile": {"display": "lnu"},
        "render_engine": "word-pdf",
        "evidence_source": "word-pdf",
        "evidence_trust": "authoritative",
        "layout_decision_eligible": True,
        "overall_status": "verified",
        "readiness": "render-check-required",
        "preflight_status": "warning",
        "render_evidence_status": "render-review-required",
        "output_dir": "/tmp/render-proof",
        "page_count": 1,
        "report_path": "/tmp/render-proof/render_verify_report.md",
        "selected_scopes": ["figures_tables"],
        "wild_doc": {"detected": False, "signals": []},
        "layout_score": {"score": 80, "penalty": 20},
        "render_text_summary": {"source": "pdf", "available": True, "page_text_available_count": 1, "page_text_extraction_warning_count": 0, "warnings": []},
        "render_findings": [
            {"id": "large_blank_region", "severity": "warning", "page": 1, "message": "页底存在大块连续空白。"}
        ],
        "review_items": [
            "大块空白常见于对象塞不进当前页、段前/段后距、分页符或对象锚点位置不当。",
            "如果不进入候选稿排障，建议回 Word/WPS 检查图片环绕、分页符和段落间距设置。",
        ],
    }

    rendered = render_verify_module.render_render_verify_report(report)

    assert "对象塞不进当前页" in rendered
    assert "检查图片环绕、分页符和段落间距设置" in rendered
