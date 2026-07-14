from tests.frontend_app_harness import PDF_REVIEW_URL, run_node as _run_node, run_state_script


def test_pdf_can_be_selected_again_after_docx_precondition_rejects_it():
    _run_node(
        """
pdfInput.files = [{ name: "same.pdf" }];
pdfInput.value = "same.pdf";
await pdfInput.emit("change");
assert.equal(pdfInput.value, "");
"""
    )


def test_state_declares_document_and_pdf_review_lifecycle_defaults():
    run_state_script(
        """
const current = getState();
assert.equal(current.documentEpoch, 0);
assert.equal(current.pdfReviewEpoch, 0);
assert.equal(current.pdfReviewRequiresFreshDocx, false);
"""
    )


def test_format_radar_uses_the_backend_score_without_recounting_findings():
    _run_node(
        """
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    return jsonResponse({
      score: 93,
      summary: {
        autofixable_scopes: 2,
        manual_confirmation_items: 2,
        total_failed_rules: 3,
      },
      scopes: [],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
docxInput.value = "paper.docx";
await docxInput.emit("change");

assert.equal(formatRadarLabel.textContent, "93分");
assert.equal(formatRadar.styleValues["--radar-progress"], "93%");
"""
    )


def test_workbench_plan_uses_upload_identity_instead_of_server_path():
    _run_node(
        """
fetchHandler = async (url, options) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    assert.deepEqual(JSON.parse(options.body), {});
    return jsonResponse({
      score: 93,
      scope_radar_summary: {
        scope_count: 0,
        failed_scope_count: 0,
        autofixable_scope_count: 0,
        manual_review_count: 0,
        unsupported_count: 0,
        manual_confirmation_count: 0,
        unknown_count: 0,
      },
      scopes: [],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.equal(getState().workbenchPlan.score, 93);
assert.equal(fetchCalls.some(({ url }) => url === "/plan"), false);
"""
    )


def test_unknown_scope_count_does_not_become_manual_confirmation_total():
    _run_node(
        """
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    return jsonResponse({
      score: 90,
      scope_radar_summary: {
        scope_count: 2,
        failed_scope_count: 1,
        autofixable_scope_count: 1,
        manual_review_count: 0,
        unsupported_count: 0,
        manual_confirmation_count: 0,
        unknown_count: 2,
      },
      scopes: [
        { id: "toc", failed_count: 1, autofixable_count: 1, manual_review_count: 0, unsupported_count: 0, unknown_count: 2 },
      ],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.equal(document.querySelector('[data-workbench-metric="manual-confirmation"]').textContent, "0");
"""
    )


def test_incomplete_plan_does_not_claim_zero_workbench_items():
    _run_node(
        """
exposeScopeOption = true;
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") return jsonResponse({ score: 92 });
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.equal(document.querySelector('[data-workbench-metric="autofixable-scopes"]').textContent, "--");
assert.equal(document.querySelector('[data-workbench-metric="manual-confirmation"]').textContent, "--");
assert.equal(structureMain.counter.textContent, "--");
assert.equal(scopeState.textContent, "等待方案");
assert.equal(scopeInput.disabled, true);
assert.match(workbenchLedger.innerHTML, /方案统计暂不可用/);
"""
    )


def test_partial_radar_keeps_complete_backend_scope_plan_selectable():
    _run_node(
        """
exposeScopeOption = true;
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    return jsonResponse({
      score: null,
      scope_radar_summary: {
        scope_count: 1,
        failed_scope_count: 1,
        autofixable_scope_count: 1,
        manual_review_count: 0,
        unsupported_count: 0,
        unknown_count: 0,
      },
      scopes: [{
        id: "toc",
        failed_count: 1,
        autofixable_count: 1,
        manual_review_count: 0,
        unsupported_count: 0,
        unknown_count: 0,
      }],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.equal(formatRadarLabel.textContent, "暂无分数");
assert.equal(docxFile.textContent, "paper.docx");
assert.equal(structureToc.counter.textContent, "1");
assert.equal(scopeInput.disabled, false);
assert.equal(scopeInput.checked, true);
assert.equal(scopeState.textContent, "已选择");
assert.equal(applyButton.disabled, false);
"""
    )


def test_plan_updates_structure_counts_and_preserves_mixed_scope_warning():
    _run_node(
        """
exposeScopeOption = true;
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    return jsonResponse({
      score: 90,
      summary: { autofixable_scopes: 1, manual_confirmation_items: 1 },
      scopes: [
        { id: "abstract", failed_count: 1, autofixable_count: 1, manual_review_count: 0, unsupported_count: 0 },
        { id: "toc", failed_count: 2, autofixable_count: 1, manual_review_count: 1, unsupported_count: 0 },
        { id: "body_paragraphs", failed_count: 3, autofixable_count: 1, manual_review_count: 0, unsupported_count: 0 },
        { id: "references", failed_count: 4, autofixable_count: 1, manual_review_count: 0, unsupported_count: 0 },
        { id: "figures_tables", failed_count: 5, autofixable_count: 1, manual_review_count: 0, unsupported_count: 0 },
      ],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.equal(structureMain.counter.textContent, "15");
assert.equal(structureAbstract.counter.textContent, "1");
assert.equal(structureToc.counter.textContent, "2");
assert.equal(structureBody.counter.textContent, "3");
assert.equal(structureReferences.counter.textContent, "4");
assert.equal(structureFigures.counter.textContent, "5");
assert.equal(scopeState.textContent, "已选 仍需确认");
"""
    )


def test_plan_keeps_unknown_rule_scope_visible_for_manual_confirmation():
    _run_node(
        """
exposeScopeOption = true;
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    return jsonResponse({
      score: 100,
      scope_radar_summary: {
        scope_count: 1,
        failed_scope_count: 1,
        autofixable_scope_count: 0,
        manual_review_count: 0,
        unsupported_count: 0,
        unknown_count: 1,
      },
      scopes: [
        { id: "toc", failed_count: 1, autofixable_count: 0, manual_review_count: 0, unsupported_count: 0, unknown_count: 1 },
      ],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.equal(scopeInput.disabled, true);
assert.equal(scopeState.textContent, "需人工确认");
"""
    )


def test_plan_ledger_does_not_claim_a_scope_count_for_manual_items():
    _run_node(
        """
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/uploads/docx-1/plan") {
    return jsonResponse({
      score: 90,
      summary: { autofixable_scopes: 1, manual_confirmation_items: 2 },
      scopes: [
        { id: "abstract", failed_count: 1, autofixable_count: 1, manual_review_count: 1, unsupported_count: 0 },
        { id: "headings", failed_count: 1, autofixable_count: 0, manual_review_count: 1, unsupported_count: 0 },
        { id: "body_paragraphs", failed_count: 1, autofixable_count: 0, manual_review_count: 0, unsupported_count: 0 },
      ],
    });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
await docxInput.emit("change");

assert.match(workbenchLedger.innerHTML, /2 项需要你确认/);
assert.doesNotMatch(workbenchLedger.innerHTML, /摘要 标题 正文/);
"""
    )


def test_stale_history_response_does_not_overwrite_newer_screen_state():
    _run_node(
        """
historyList.innerHTML = "unchanged";
let resolveHistory;
fetchHandler = () => new Promise((resolve) => { resolveHistory = resolve; });

await historyNav.emit("click");
assert.ok(resolveHistory, "history screen should request the job list");
await workbenchNav.emit("click");
resolveHistory(jsonResponse([{ job_id: "stale-job", status: "succeeded" }]));
await new Promise((resolve) => setImmediate(resolve));

assert.equal(historyList.innerHTML, "unchanged");
"""
    )


def test_empty_history_record_links_back_to_the_workbench():
    _run_node(
        """
fetchHandler = async () => jsonResponse([]);

await historyNav.emit("click");
await new Promise((resolve) => setImmediate(resolve));

assert.match(historyList.innerHTML, /data-action="enter-workbench"/);
assert.match(historyList.innerHTML, /上传论文/);
"""
    )


def test_flow_stays_on_upload_until_the_upload_response_starts_planning():
    _run_node(
        """
let resolveUpload;
let resolvePlan;
fetchHandler = (url) => {
  if (url === "/uploads/docx") {
    return new Promise((resolve) => { resolveUpload = resolve; });
  }
  if (url === "/uploads/docx-1/plan") {
    return new Promise((resolve) => { resolvePlan = resolve; });
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "paper.docx" }];
const uploadFlow = docxInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));
assert.ok(resolveUpload);
assert.equal(flowSteps.find((step) => step.dataset.flowStage === "upload").classList.contains("active"), true);

resolveUpload(jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" }));
await new Promise((resolve) => setImmediate(resolve));
assert.ok(resolvePlan);
assert.equal(flowSteps.find((step) => step.dataset.flowStage === "plan").classList.contains("active"), true);

resolvePlan(jsonResponse({ score: 100, summary: {}, scopes: [] }));
await uploadFlow;
assert.equal(flowSteps.find((step) => step.dataset.flowStage === "plan").classList.contains("active"), true);
"""
    )


def test_apply_requires_a_completed_workbench_plan():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  workbenchPlan: null,
});
scopeInput.checked = true;
scopeInput.disabled = false;
fetchHandler = async () => { throw new Error("apply must not be requested"); };

await applyButton.emit("click");

assert.equal(fetchCalls.length, 0);
assert.equal(statusTitle.textContent, "请先生成修复方案");
assert.equal(statusMessage.textContent, "方案完成后再生成修正结果");
"""
    )


def test_apply_submits_selected_scopes_once_while_the_job_is_starting():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  workbenchPlan: { scopes: [] },
});
scopeInput.checked = true;
scopeInput.disabled = false;
let resolveCreate;
let createCount = 0;
fetchHandler = async (url, options) => {
  if (url.endsWith("/jobs/apply")) {
    createCount += 1;
    assert.deepEqual(JSON.parse(options.body).scopes, ["toc"]);
    return new Promise((resolve) => { resolveCreate = resolve; });
  }
  if (url === "/jobs/apply-1") return jsonResponse({ job_id: "apply-1", status: "succeeded" });
  if (url === "/jobs/apply-1/result") {
    return jsonResponse({ operation: "apply", job_id: "apply-1", result: {}, summary: {}, artifacts: [] });
  }
  throw new Error(`unexpected request ${url}`);
};

const firstRun = applyButton.emit("click");
await new Promise((resolve) => setImmediate(resolve));
const duplicateRun = applyButton.emit("click");
await new Promise((resolve) => setImmediate(resolve));

assert.equal(createCount, 1);
resolveCreate(jsonResponse({ job_id: "apply-1" }, 201));
await Promise.all([firstRun, duplicateRun]);
"""
    )


def test_result_spectrum_uses_backend_scope_results_instead_of_fixed_cells():
    _run_node(
        r"""
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulApply({
  operation: "apply",
  job_id: "apply-1",
  summary: { selected_scopes: ["toc", "figures_tables"] },
  artifacts: [],
  result: {
    post_verify_notices: [],
    verification: {
      scopes: [
        { id: "toc", title: "目录", failed_count: 0 },
        { id: "figures_tables", title: "图表", failed_count: 2 },
        { id: "cover", title: "固定封面", failed_count: 0, status: "not_checked" },
      ],
    },
  },
});
scopeInput.checked = true;
scopeInput.disabled = false;
await applyButton.emit("click");

assert.match(resultHeatmap.innerHTML, /目录/);
assert.match(resultHeatmap.innerHTML, /图表/);
assert.match(resultHeatmap.innerHTML, /通过/);
assert.match(resultHeatmap.innerHTML, /2项/);
assert.match(resultHeatmap.innerHTML, /class="pass"[^>]*>\s*<b>目录<\/b>\s*<small>通过<\/small>/);
assert.match(resultHeatmap.innerHTML, /class="warn"[^>]*>\s*<b>图表<\/b>\s*<small>2项<\/small>/);
assert.match(resultHeatmap.innerHTML, /class="warn"[^>]*>\s*<b>固定封面<\/b>\s*<small>未检查<\/small>/);
assert.doesNotMatch(resultHeatmap.innerHTML, /固定封面.*通过/);
assert.equal((resultHeatmap.innerHTML.match(/<span/g) || []).length, 3);
assert.equal(flowSteps.find((step) => step.dataset.flowStage === "download").classList.contains("active"), true);
"""
    )


def test_result_copy_distinguishes_not_generated_from_missing_artifacts():
    _run_node(
        """
assert.equal(resultDownloadNote.textContent, "生成结果后可下载");
assert.equal(resultReportText.textContent, "生成结果后可下载报告");
assert.equal(resultEmpty.hidden, false);
assert.equal(resultDetails.every((node) => node.hidden === true), true);

setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulApply();
scopeInput.checked = true;
scopeInput.disabled = false;
await applyButton.emit("click");

assert.equal(resultDownloadNote.textContent, "下载文件已不可用 请重新运行修复");
assert.equal(resultReportText.textContent, "报告文件已不可用 请重新运行修复");
assert.equal(resultEmpty.hidden, true);
assert.equal(resultDetails.every((node) => node.hidden === false), true);
"""
    )


def test_result_spectrum_shows_actual_cover_operation_status():
    _run_node(
        r"""
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulApply({
  operation: "apply",
  job_id: "apply-1",
  summary: { selected_scopes: ["cover"] },
  artifacts: [],
  result: {
    cover_replacement: { status: "inserted", field_count: 6 },
    verification: { scopes: [{ id: "cover", title: "固定封面", failed_count: 0 }] },
  },
});
scopeInput.checked = true;
scopeInput.disabled = false;
await applyButton.emit("click");

assert.match(resultHeatmap.innerHTML, /固定封面/);
assert.match(resultHeatmap.innerHTML, /已添加/);
assert.doesNotMatch(resultHeatmap.innerHTML, /固定封面.*通过/);
"""
    )


def test_history_pdf_result_restores_its_document_and_pdf_context():
    _run_node(
        """
setState({
  documentEpoch: 10,
  pdfReviewEpoch: 20,
  docxUpload: { upload_id: "other-docx", file_name: "other.docx" },
  pdfReviewRequiresFreshDocx: false,
});
pdfMatchConfirmation.checked = true;
fetchHandler = async () => jsonResponse({
  operation: "render-verify",
  job_id: "history-pdf",
  artifacts: [{ role: "toc-output", available: true }],
  summary: { document_name: "paper-fixed.docx", pdf_name: "paper-fixed.pdf" },
  result: {
    evidence_items: [],
    summary: { render_evidence_status: "render-review-required" },
    toc_finalization: { available: true },
  },
});
const target = {
  closest(selector) {
    return selector === "[data-history-job-id]" ? { dataset: { historyJobId: "history-pdf" } } : null;
  },
};

await document.emit("click", { target });
await new Promise((resolve) => setImmediate(resolve));

assert.equal(pdfDocxFile.textContent, "paper-fixed.docx");
assert.equal(pdfFile.textContent, "paper-fixed.pdf");
assert.equal(renderState.textContent, "已完成");
assert.equal(pdfScreen.classList.contains("active"), true);
assert.equal(getState().pdfReviewRequiresFreshDocx, true);
assert.equal(getState().docxUpload.upload_id, "other-docx");
assert.equal(pdfMatchConfirmation.checked, false);
assert.equal(tocOutputButton.dataset.downloadUrl, "/jobs/history-pdf/artifacts/toc-output/download");

const pdfClicksBefore = pdfInput.clickCount;
await choosePdfButton.emit("click");
assert.equal(pdfInput.clickCount, pdfClicksBefore);
assert.equal(statusTitle.textContent, "先上传修复稿");
"""
    )


def test_pdf_review_requires_confirmation_and_sends_it_explicitly():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulPdfReview({
  summary: {
    render_evidence_status: "render-evidence-ready",
    evidence_source: "manual-pdf",
    evidence_trust: "user-confirmed",
    evidence_authoritative: false,
    layout_decision_eligible: true,
    pdf_matches_docx_confirmed: true,
    pdf_content_match_status: "matched",
    actionable_finding_count: 0,
  },
  evidence_items: [],
});
setState({ renderResult: { marker: "stale-pdf" } });

pdfInput.files = [{ name: "paper.pdf" }];
pdfInput.value = "paper.pdf";
await pdfInput.emit("change");
assert.equal(fetchCalls.some(({ url }) => url.endsWith("/render-review-jobs")), false);
assert.equal(getState().renderResult, null);
assert.equal(pdfInput.value, "");

fetchCalls = [];
pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "paper.pdf" }];
pdfInput.value = "paper.pdf";
await pdfInput.emit("change");
const reviewRequest = fetchCalls.find(({ url }) => url.endsWith("/render-review-jobs"));
assert.ok(reviewRequest, "confirmed PDF should start review");
assert.deepEqual(JSON.parse(reviewRequest.options.body), {
  pdf_upload_id: "pdf-1",
  pdf_matches_docx_confirmed: true,
  generate_static_toc: true,
});
assert.equal(pdfMatchConfirmation.checked, false);
assert.equal(pdfInput.value, "");
assert.equal(pdfConclusion.textContent, "无异常");
assert.equal(statusTitle.textContent, "PDF 复核完成");
assert.equal(statusMessage.textContent, "没有发现需要确认的位置");
assert.doesNotMatch(statusMessage.textContent, /查看页面问题/);
"""
    )


def test_pdf_completion_status_closes_unusable_and_empty_review_results():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulPdfReview({
  summary: {
    render_evidence_status: "unsupported-evidence",
    evidence_source: "manual-pdf",
    layout_decision_eligible: false,
    pdf_content_match_status: "mismatch",
  },
  evidence_items: [{
    page: 4,
    screenshot_url: "/wrong-pdf/page-4.png",
    rule_id: "render.formula_number_split_page",
  }],
});

pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "wrong.pdf" }];
await pdfInput.emit("change");

assert.equal(statusTitle.textContent, "PDF 版本待确认");
assert.equal(statusMessage.textContent, "请重新上传当前论文导出的 PDF");
assert.doesNotMatch(statusMessage.textContent, /查看页面问题/);

installSuccessfulPdfReview({
  summary: {
    render_evidence_status: "render-review-required",
    evidence_source: "word-pdf",
    layout_decision_eligible: true,
  },
  evidence_items: [],
});
pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "paper.pdf" }];
await pdfInput.emit("change");
assert.equal(statusTitle.textContent, "PDF 仍需人工复核");
assert.equal(statusMessage.textContent, "没有返回问题位置 请继续检查页面和结构");
assert.doesNotMatch(statusMessage.textContent, /查看页面问题/);
"""
    )


def test_apply_requires_the_downloaded_docx_before_another_pdf_review():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulApply();
await applyButton.emit("click");
assert.equal(getState().pdfReviewRequiresFreshDocx, true);

const clicksBefore = pdfInput.clickCount;
await choosePdfButton.emit("click");
assert.equal(pdfInput.clickCount, clicksBefore);
assert.equal(statusTitle.textContent, "先上传修复稿");
assert.equal(statusMessage.textContent, "上传刚下载的修复稿后再复核 PDF");

await chooseDocxButton.emit("click");
assert.equal(docxInput.clickCount, 1);
"""
    )


def test_successful_new_docx_upload_clears_the_fresh_docx_requirement():
    _run_node(
        """
setState({ pdfReviewRequiresFreshDocx: true, documentEpoch: 10 });
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-2", file_name: "paper-fixed.docx", stored_path: "/tmp/paper-fixed.docx" });
  }
  if (url === "/uploads/docx-2/plan") return jsonResponse({ scopes: [], summary: {} });
  throw new Error(`unexpected request ${url}`);
};
docxInput.files = [{ name: "paper-fixed.docx" }];
docxInput.value = "paper-fixed.docx";
pdfMatchConfirmation.checked = true;
await docxInput.emit("change");
assert.equal(getState().pdfReviewRequiresFreshDocx, false);
assert.equal(pdfMatchConfirmation.checked, false);
assert.equal(docxInput.value, "");
"""
    )


def test_static_toc_download_uses_the_render_job_artifact_and_requires_a_fresh_docx():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulPdfReview(
  {
    summary: {
      render_evidence_status: "render-review-required",
      evidence_source: "manual-pdf",
      evidence_trust: "user-confirmed",
      layout_decision_eligible: true,
      pdf_matches_docx_confirmed: true,
    },
    evidence_items: [],
    toc_finalization: {
      status: "generated",
      available: true,
      next_action: "下载后重新导出 PDF 并再次复核",
    },
  },
  { artifacts: [{ role: "toc-output", available: true, download_name: "static_toc.docx" }] },
);

pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "paper.pdf" }];
await pdfInput.emit("change");

assert.equal(tocOutputAction.hidden, false);
assert.equal(tocOutputNextAction.textContent, "下载后重新导出 PDF 并再次复核");
assert.equal(tocOutputButton.disabled, false);
assert.equal(tocOutputButton.dataset.downloadUrl, "/jobs/render-1/artifacts/toc-output/download");

const downloadTarget = {
  closest(selector) {
    return selector === "[data-download-role]" ? tocOutputButton : null;
  },
};
await document.emit("click", { target: downloadTarget });
assert.equal(window.location.href, "/jobs/render-1/artifacts/toc-output/download");
assert.equal(getState().pdfReviewRequiresFreshDocx, true);
assert.equal(statusTitle.textContent, "请重新导出 PDF");
assert.match(statusMessage.textContent, /重新导出 PDF 并再次复核/);
"""
    )


def test_static_toc_status_stays_visible_without_an_available_artifact():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
installSuccessfulPdfReview({
  summary: {
    render_evidence_status: "render-review-required",
    evidence_source: "manual-pdf",
    evidence_trust: "user-confirmed",
    layout_decision_eligible: true,
    pdf_matches_docx_confirmed: true,
  },
  evidence_items: [],
  toc_finalization: { status: "generated", available: true },
});

pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "paper.pdf" }];
await pdfInput.emit("change");

assert.equal(tocOutputAction.hidden, false);
assert.equal(tocOutputButton.disabled, true);
assert.equal(tocOutputButton.dataset.downloadUrl, undefined);
"""
    )
