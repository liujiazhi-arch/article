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
        "POST /uploads/docx",
        "POST /uploads/pdf",
        "POST /uploads/{docx_upload_id}/render-review-jobs",
        "GET /jobs/{job_id}",
        "GET /jobs/{job_id}/result",
    ]
    for item in required:
        assert item in text


def test_frontend_backend_contract_defines_pdf_review_boundary():
    text = CONTRACT.read_text(encoding="utf-8")

    assert "bbox = null" in text
    assert "must not draw a fake precise box" in text
    assert "text-span highlighting" in text
    assert "Not supported" in text


def test_old_visual_plan_points_to_contract_plan():
    text = OLD_PLAN.read_text(encoding="utf-8")

    assert "superseded" in text.lower()
    assert "2026-06-16-frontend-workbench-contract-implementation-plan.md" in text


def test_frontend_static_files_do_not_show_forbidden_student_terms():
    static_root = ROOT / "scripts" / "article_api" / "static"
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
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in static_root.rglob("*")
        if path.suffix in {".html", ".css"} or path.name == "copy.js"
    )
    for term in forbidden:
        assert term not in text


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


def test_frontend_js_wires_result_download_history_and_apply_result():
    static_root = ROOT / "scripts" / "article_api" / "static"
    api_js = (static_root / "js" / "api.js").read_text(encoding="utf-8")
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")

    assert "export async function listJobs" in api_js
    assert "export function downloadJobArtifactUrl" in api_js
    assert '"/jobs?limit="' in api_js
    assert 'artifacts/${encodeURIComponent(role)}/download' in api_js
    assert "getJobResult(job.job_id)" in app_js
    assert "applyResultPayload" in app_js
    assert "renderResultPanel" in app_js
    assert "renderHistory" in app_js
    assert "escapeHtml" in app_js
    assert "escapeHtml(title)" in app_js
    pdf_review_js = (static_root / "js" / "pdfReview.js").read_text(encoding="utf-8")
    assert "createFinding(labelForRule(active.rule_id), active.message" in pdf_review_js
    assert "messageNode.textContent = message" in pdf_review_js
    assert "data-download-role" in app_js
    assert "处理没有完成 请重新运行" in app_js
    assert "后端处理任务时出现内部错误" not in app_js


def test_frontend_js_wires_workbench_plan_summary():
    static_root = ROOT / "scripts" / "article_api" / "static"
    api_js = (static_root / "js" / "api.js").read_text(encoding="utf-8")
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")

    assert "export async function createPlan" in api_js
    assert 'requestJson("/plan"' in api_js
    assert "workbenchPlan" in app_js
    assert "renderWorkbenchPlan" in app_js
    assert "data-workbench-metric" in app_js
    assert "data-workbench-ledger" in app_js
    assert "createPlan(upload.stored_path)" in app_js


def test_frontend_submits_selected_repair_scopes_and_blocks_duplicate_runs():
    static_root = ROOT / "scripts" / "article_api" / "static"
    html = (static_root / "index.html").read_text(encoding="utf-8")
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")
    state_js = (static_root / "js" / "state.js").read_text(encoding="utf-8")

    for scope_id in (
        "page",
        "abstract",
        "toc",
        "headings",
        "body_paragraphs",
        "figures_tables",
        "references",
        "acknowledgement",
        "appendix",
    ):
        assert f'data-scope-option="{scope_id}"' in html
        assert f'value="{scope_id}"' in html
    assert 'type="checkbox" name="repair-scope"' in html
    assert "function selectedScopeIds" in app_js
    assert "createApplyJob(current.docxUpload.upload_id, { scopes })" in app_js
    assert "applyRunning" in app_js
    assert "button.disabled" in app_js
    assert 'stateNode.textContent = input.checked ? "已选择" : "未选择"' in app_js
    assert 'requiresReview ? "需人工确认"' in app_js
    assert "selectedScopes:" not in state_js
    assert "setState({ selectedScopes" not in app_js
    assert "createApplyJob(current.docxUpload.upload_id, {})" not in app_js


def test_frontend_js_wires_format_radar_from_plan_summary():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")
    html = (static_root / "index.html").read_text(encoding="utf-8")

    assert "function renderFormatRadar(summary)" in app_js
    assert "renderFormatRadar(summary)" in app_js
    assert "data-format-radar" in html
    assert "data-format-radar-label" in html
