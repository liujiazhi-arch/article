from pathlib import Path
from html.parser import HTMLParser


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "FRONTEND_BACKEND_CONTRACT.md"
OLD_PLAN = ROOT / "docs" / "superpowers" / "plans" / "2026-06-16-frontend-workbench-and-pdf-review-plan.md"


class _TextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data)


def test_frontend_backend_contract_freezes_required_endpoints():
    text = CONTRACT.read_text(encoding="utf-8")

    required = [
        "GET /",
        "GET /static/{path}",
        "POST /plan",
        "POST /uploads/docx",
        "POST /uploads/pdf",
        "POST /uploads/{upload_id}/plan",
        "POST /uploads/{docx_upload_id}/render-review-jobs",
        "GET /jobs/{job_id}",
        "GET /jobs/{job_id}/result",
        "GET /jobs?limit={count}",
        "GET /jobs/{job_id}/artifacts/{role}/download",
    ]
    for item in required:
        assert item in text


def test_frontend_backend_contract_defines_pdf_review_boundary():
    text = CONTRACT.read_text(encoding="utf-8")

    assert "Public PDF review never converts DOCX to PDF" in text
    assert "repaired DOCX upload must precede the repaired PDF upload" in text
    assert '"pdf_matches_docx_confirmed": true' in text
    assert "bbox = null" in text
    assert "must not draw a fake precise box" in text
    assert '"text_spans"' in text
    assert "uniquely matched text-line highlighting" in text
    assert "arbitrary text-span highlighting" in text
    assert "Not supported" in text
    assert "It is not a full PDF reader" in text
    assert "zoom controls" in text
    assert "removes the automatic TOC field markers" in text
    assert "preserves the document-level field-update request" in text


def test_frontend_backend_contract_maps_dynamic_features_to_backend_results():
    text = CONTRACT.read_text(encoding="utf-8")

    for feature in (
        "Format radar",
        "Thesis structure index",
        "Repair scope selection",
        "Processing flow",
        "Rule spectrum",
        "PDF issue evidence",
        "History",
    ):
        assert feature in text
    assert "Show the backend score directly" in text
    assert "verification.scopes[]" in text
    assert "must not replace a newer document or PDF flow" in text


def test_old_visual_plan_points_to_contract_plan():
    text = OLD_PLAN.read_text(encoding="utf-8")

    assert "superseded" in text.lower()
    assert "2026-06-16-frontend-workbench-contract-implementation-plan.md" in text


def test_frontend_static_files_do_not_show_forbidden_student_terms():
    html = (ROOT / "scripts" / "article_api" / "static" / "index.html").read_text(encoding="utf-8")
    parser = _TextCollector()
    parser.feed(html)
    visible_text = "\n".join(parser.parts)
    forbidden = [
        "/jobs/{id}",
        "queued",
        "running",
        "failed",
        "succeeded",
        "bbox",
        "rule_id",
        "page_image",
        "data contract",
        "profile",
        "mode",
        "preflight",
        "apply job",
        "report artifact",
    ]
    for term in forbidden:
        assert term not in visible_text


def test_frontend_html_keeps_student_copy_out_of_backend_field_names():
    html = (ROOT / "scripts" / "article_api" / "static" / "index.html").read_text(encoding="utf-8")
    parser = _TextCollector()
    parser.feed(html)
    visible_text = "\n".join(parser.parts)

    for term in ["lnu-checker-2026", "page", "abstract", "toc", "headings", "figures", "refs", "message", "severity"]:
        assert term not in visible_text
    assert "后端" not in visible_text
    assert "本地" in visible_text
    assert "辽大规范" in visible_text
