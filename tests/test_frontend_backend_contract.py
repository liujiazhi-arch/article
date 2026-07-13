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

    assert '"pdf_matches_docx_confirmed": true' in text
    assert "bbox = null" in text
    assert "must not draw a fake precise box" in text
    assert "text-span highlighting" in text
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
    copy_js = (static_root / "js" / "copy.js").read_text(encoding="utf-8")
    assert "renderEvidenceStatusLabels" in copy_js
    assert "summary.actionable_finding_count" in app_js
    assert "summary.evidence_item_count" in app_js
    assert 'setPdfMetric("conclusion"' in app_js
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
        "cover",
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
    assert "createApplyJob(current.docxUpload.upload_id, { scopes, ...(coverFields ? { cover_fields: coverFields } : {}) })" in app_js
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


def test_frontend_resets_stale_pdf_evidence_for_each_new_document():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")
    pdf_review_js = (static_root / "js" / "pdfReview.js").read_text(encoding="utf-8")

    assert "function resetPdfReviewState" in app_js
    assert "pdfUpload: null" in app_js
    assert "renderResult: null" in app_js
    assert "resetPdfMatchConfirmation(root)" in app_js
    assert "pdfVersionConfirmed" not in app_js
    assert "clearPdfReview(root" in app_js
    assert "export function clearPdfReview" in pdf_review_js
    document_reset = app_js.index("function resetDocumentState")
    assert app_js.index("resetPdfReviewState(root", document_reset) > document_reset
    docx_change = app_js.index("async function handleDocxUpload")
    reset = app_js.index("resetDocumentState(root", docx_change)
    upload = app_js.index("await uploadDocx(file)", docx_change)
    assert reset < upload


def test_frontend_clears_pdf_evidence_and_leaves_reviewing_state_after_failure():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")
    pdf_review_js = (static_root / "js" / "pdfReview.js").read_text(encoding="utf-8")

    assert 'renderState: "未完成"' in app_js
    assert 'conclusion: "待确认"' in app_js
    assert "list.replaceChildren" in pdf_review_js
    assert "stage.replaceChildren" in pdf_review_js
    assert "detail.replaceChildren" in pdf_review_js
    assert 'list.replaceChildren(createEmptyState(title, ""))' in pdf_review_js
    assert 'detail.replaceChildren(createFinding("下一步", message))' in pdf_review_js
    pdf_change = app_js.index("async function handlePdfUpload")
    reviewing = app_js.index('renderState: "复核中"', pdf_change)
    poll = app_js.index("await pollJob", pdf_change)
    failed = app_js.index('renderState: "未完成"', poll)
    assert reviewing < poll < failed


def test_frontend_result_copy_reflects_business_status_and_readiness():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")

    assert "function resultPanelStatus" in app_js
    assert 'businessStatus === "needs_fix"' in app_js
    assert "reviewRequiredResultStatuses" in app_js
    assert 'badge: "待修复"' in app_js
    assert 'badge: "待确认"' in app_js
    assert 'badge: "待复核"' in app_js
    assert 'document.querySelector(".completion-orb strong")' in app_js
    assert 'document.querySelector(".result-hero h2")' in app_js


def test_frontend_result_copy_treats_manual_and_unsupported_outcomes_as_pending():
    app_js = (
        ROOT / "scripts" / "article_api" / "static" / "js" / "app.js"
    ).read_text(encoding="utf-8")

    for status in ("manual-review-required", "manual_review", "unsupported", "mixed"):
        assert f'"{status}"' in app_js
    assert "reviewRequiredResultStatuses.has(readiness)" in app_js
    assert "reviewRequiredResultStatuses.has(businessStatus)" in app_js


def test_frontend_pdf_conclusion_prioritizes_blockers_and_requires_version_confirmation():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")

    assert "blockingRenderEvidenceStatuses" in app_js
    assert '"structure-not-ready"' in app_js
    assert '"blocked-by-wild-doc"' in app_js
    assert '"unsupported-evidence"' in app_js
    blocker = app_js.index("blockingRenderEvidenceStatuses.has(evidenceStatus)")
    issue_count = app_js.index("Number(issues) > 0", blocker)
    assert blocker < issue_count
    assert "isPdfReviewReady(result)" in app_js
    assert "pdfVersionConfirmed" not in app_js
    assert 'isPdfReviewReady(result) ? "无异常" : "待确认"' in app_js


def test_frontend_empty_pdf_review_requires_authoritative_ready_evidence():
    pdf_review_js = (
        ROOT / "scripts" / "article_api" / "static" / "js" / "pdfReview.js"
    ).read_text(encoding="utf-8")

    empty_branch = pdf_review_js.split("if (!items.length) {", 1)[1]
    pending_branch, ready_branch = empty_branch.split("if (!isPdfReviewReady(result)) {", 1)[1].split("return;", 1)
    assert "export function isPdfReviewReady" in pdf_review_js
    assert 'resultField(result, "render_evidence_status") !== "render-evidence-ready"' in pdf_review_js
    assert 'resultField(result, "pdf_matches_docx_confirmed") === true' in pdf_review_js
    assert 'resultField(result, "layout_decision_eligible") === true' in pdf_review_js
    assert 'trust === "authoritative"' in pdf_review_js
    assert 'trust === "user-confirmed"' in pdf_review_js
    assert "pdfVersionConfirmed" not in pdf_review_js
    assert "版本对应关系待确认" in pending_branch
    assert "没有发现需要确认的位置" not in pending_branch
    assert "可以保存复核结果" not in pending_branch
    assert "没有发现需要确认的位置" in ready_branch


def test_frontend_pdf_review_requires_explicit_current_document_confirmation():
    static_root = ROOT / "scripts" / "article_api" / "static"
    html = (static_root / "index.html").read_text(encoding="utf-8")
    api_js = (static_root / "js" / "api.js").read_text(encoding="utf-8")
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")

    assert '<input id="pdf-match-confirmation" type="checkbox">' in html
    assert "我确认这个 PDF 由当前论文导出" in html
    assert "data-pdf-docx-file" in html
    assert "PDF 需要和论文原稿对应" not in html
    assert 'data-action="choose-docx"><b>上传修复稿再复核</b>' in html
    assert "pdf_matches_docx_confirmed: pdfMatchesDocxConfirmed === true" in api_js
    assert "createRenderReviewJob(docxUploadId, pdfUpload.upload_id, true)" in app_js
    assert "pdfReviewRequiresFreshDocx: true" in app_js
    assert "pdfReviewRequiresFreshDocx: false" in app_js


def test_frontend_ignores_an_older_pdf_review_for_the_same_document():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")

    assert "pdfReviewEpoch" in app_js
    assert "pdfReviewEpoch: nextEpoch" in app_js
    assert "getState().pdfReviewEpoch !== pdfReviewEpoch" in app_js
    pdf_change = app_js.index("async function handlePdfUpload")
    epoch = app_js.index("const pdfReviewEpoch = resetPdfReviewState", pdf_change)
    upload = app_js.index("await uploadPdf(file)", pdf_change)
    poll = app_js.index("await pollJob", upload)
    assert epoch < upload < poll
    result_fetch = app_js.index("await getJobResult(jobId)")
    post_fetch_guard = app_js.index("getState().pdfReviewEpoch !== pdfReviewEpoch", result_fetch)
    result_write = app_js.index("setState({ renderResult", result_fetch)
    assert result_fetch < post_fetch_guard < result_write


def test_frontend_invalidates_older_document_uploads_and_results():
    app_js = (
        ROOT / "scripts" / "article_api" / "static" / "js" / "app.js"
    ).read_text(encoding="utf-8")

    assert "function resetDocumentState" in app_js
    assert "documentEpoch: nextEpoch" in app_js
    assert "docxUpload: null" in app_js
    assert "workbenchPlan: null" in app_js
    assert "applyResultPayload: null" in app_js
    assert "getState().documentEpoch !== documentEpoch" in app_js
    docx_change = app_js.index("async function handleDocxUpload")
    epoch = app_js.index("const documentEpoch = resetDocumentState", docx_change)
    upload = app_js.index("await uploadDocx(file)", docx_change)
    guard = app_js.index("getState().documentEpoch !== documentEpoch", upload)
    plan = app_js.index("createWorkbenchPlanFromUpload(upload, documentEpoch)", guard)
    assert epoch < upload < guard < plan
