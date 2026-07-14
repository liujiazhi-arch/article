from tests.frontend_app_harness import run_node as _run_node


def test_history_pdf_result_does_not_replace_a_new_document_flow():
    _run_node(
        """
setState({ documentEpoch: 10, pdfReviewEpoch: 20 });
await openHistoryAndResolve(
  { operation: "render-verify", result: { marker: "stale-pdf" } },
  () => setState({ documentEpoch: 11 }),
);
assert.equal(getState().renderResult, null);
assert.equal(pdfScreen.classList.contains("active"), false);
"""
    )


def test_inflight_pdf_review_does_not_replace_a_newly_opened_history_result():
    _run_node(
        """
setState({
  documentEpoch: 10,
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  pdfReviewRequiresFreshDocx: false,
});
pdfMatchConfirmation.checked = true;
let resolveOldJob;
fetchHandler = async (url) => {
  if (url === "/uploads/pdf") return jsonResponse({ upload_id: "pdf-1", file_name: "paper.pdf" });
  if (url.endsWith("/render-review-jobs")) return jsonResponse({ job_id: "old-render" }, 201);
  if (url === "/jobs/old-render") {
    return new Promise((resolve) => { resolveOldJob = resolve; });
  }
  if (url === "/jobs/old-render/result") {
    return jsonResponse({
      operation: "render-verify",
      job_id: "old-render",
      artifacts: [{ role: "toc-output", available: true }],
      result: { marker: "old-render", toc_finalization: { available: true } },
    });
  }
  if (url === "/jobs/history-render/result") {
    return jsonResponse({
      operation: "render-verify",
      job_id: "history-render",
      artifacts: [{ role: "toc-output", available: true }],
      summary: { document_name: "history.docx", pdf_name: "history.pdf" },
      result: { marker: "history-render", evidence_items: [], toc_finalization: { available: true } },
    });
  }
  throw new Error(`unexpected request ${url}`);
};

pdfInput.files = [{ name: "paper.pdf" }];
const oldReview = pdfInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));
assert.ok(resolveOldJob, "old review should be polling");

const historyTarget = {
  closest(selector) {
    return selector === "[data-history-job-id]"
      ? { dataset: { historyJobId: "history-render" } }
      : null;
  },
};
await document.emit("click", { target: historyTarget });
await new Promise((resolve) => setImmediate(resolve));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(getState().renderResult.marker, "history-render");
assert.equal(tocOutputButton.dataset.downloadUrl, "/jobs/history-render/artifacts/toc-output/download");

resolveOldJob(jsonResponse({ job_id: "old-render", status: "succeeded" }));
await oldReview;
assert.equal(getState().renderResult.marker, "history-render");
assert.equal(tocOutputButton.dataset.downloadUrl, "/jobs/history-render/artifacts/toc-output/download");
assert.equal(fetchCalls.some(({ url }) => url === "/jobs/old-render/result"), false);
"""
    )


def test_inflight_apply_does_not_replace_a_newly_opened_history_result():
    _run_node(
        """
setState({
  documentEpoch: 10,
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  workbenchPlan: { scopes: [] },
});
scopeInput.checked = true;
scopeInput.disabled = false;
let resolveApplyJob;
fetchHandler = async (url) => {
  if (url.endsWith("/jobs/apply")) return jsonResponse({ job_id: "apply-1" }, 201);
  if (url === "/jobs/apply-1") return new Promise((resolve) => { resolveApplyJob = resolve; });
  if (url === "/jobs/history-render/result") {
    return jsonResponse({
      operation: "render-verify",
      job_id: "history-render",
      summary: { document_name: "history.docx", pdf_name: "history.pdf" },
      result: { marker: "history-render", evidence_items: [] },
    });
  }
  if (url === "/jobs/apply-1/result") {
    return jsonResponse({ operation: "apply", job_id: "apply-1", result: { marker: "apply" } });
  }
  throw new Error(`unexpected request ${url}`);
};

const applyFlow = applyButton.emit("click");
await new Promise((resolve) => setImmediate(resolve));
assert.ok(resolveApplyJob, "apply should be polling");
const historyTarget = {
  closest(selector) {
    return selector === "[data-history-job-id]"
      ? { dataset: { historyJobId: "history-render" } }
      : null;
  },
};
await document.emit("click", { target: historyTarget });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(getState().renderResult.marker, "history-render");

resolveApplyJob(jsonResponse({ job_id: "apply-1", status: "succeeded" }));
await applyFlow;
assert.equal(getState().renderResult.marker, "history-render");
assert.equal(resultScreen.classList.contains("active"), false);
assert.equal(fetchCalls.some(({ url }) => url === "/jobs/apply-1/result"), false);
"""
    )


def test_inflight_apply_survives_ordinary_screen_navigation():
    _run_node(
        """
setState({
  documentEpoch: 10,
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  workbenchPlan: { scopes: [] },
});
scopeInput.checked = true;
scopeInput.disabled = false;
let resolveApplyJob;
fetchHandler = async (url) => {
  if (url.endsWith("/jobs/apply")) return jsonResponse({ job_id: "apply-1" }, 201);
  if (url === "/jobs/apply-1") return new Promise((resolve) => { resolveApplyJob = resolve; });
  if (url === "/jobs/apply-1/result") {
    return jsonResponse({ operation: "apply", job_id: "apply-1", summary: { output_name: "apply-result.docx" }, result: { marker: "apply" } });
  }
  throw new Error(`unexpected request ${url}`);
};

const applyFlow = applyButton.emit("click");
await new Promise((resolve) => setImmediate(resolve));
assert.ok(resolveApplyJob, "apply should be polling");

await workbenchNav.emit("click");
resolveApplyJob(jsonResponse({ job_id: "apply-1", status: "succeeded" }));
await applyFlow;

assert.equal(resultFileName.textContent, "apply-result.docx");
assert.equal(resultScreen.classList.contains("active"), true);
assert.equal(fetchCalls.some(({ url }) => url === "/jobs/apply-1/result"), true);
"""
    )


def test_history_apply_result_does_not_replace_a_new_pdf_flow():
    _run_node(
        """
setState({ documentEpoch: 10, pdfReviewEpoch: 20 });
await openHistoryAndResolve(
  { operation: "apply", result: { marker: "stale-apply" } },
  () => setState({ pdfReviewEpoch: 21 }),
);
assert.equal(resultScreen.classList.contains("active"), false);
"""
    )


def test_history_apply_result_cancels_an_older_pdf_review():
    _run_node(
        """
setState({
  documentEpoch: 10,
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  pdfReviewRequiresFreshDocx: false,
});
pdfMatchConfirmation.checked = true;
let resolveOldJob;
fetchHandler = async (url) => {
  if (url === "/uploads/pdf") return jsonResponse({ upload_id: "pdf-1", file_name: "paper.pdf" });
  if (url.endsWith("/render-review-jobs")) return jsonResponse({ job_id: "old-render" }, 201);
  if (url === "/jobs/old-render") return new Promise((resolve) => { resolveOldJob = resolve; });
  if (url === "/jobs/old-render/result") {
    return jsonResponse({ operation: "render-verify", job_id: "old-render", result: { marker: "old-pdf" } });
  }
  if (url === "/jobs/history-apply/result") {
    return jsonResponse({ operation: "apply", job_id: "history-apply", summary: { output_name: "history-apply.docx" }, result: { marker: "history-apply" } });
  }
  throw new Error(`unexpected request ${url}`);
};

pdfInput.files = [{ name: "paper.pdf" }];
const oldReview = pdfInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));
assert.ok(resolveOldJob, "old review should be polling");
const historyTarget = {
  closest(selector) {
    return selector === "[data-history-job-id]"
      ? { dataset: { historyJobId: "history-apply" } }
      : null;
  },
};
await document.emit("click", { target: historyTarget });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(resultFileName.textContent, "history-apply.docx");

resolveOldJob(jsonResponse({ job_id: "old-render", status: "succeeded" }));
await oldReview;
assert.equal(resultFileName.textContent, "history-apply.docx");
assert.equal(getState().renderResult, null);
assert.equal(fetchCalls.some(({ url }) => url === "/jobs/old-render/result"), false);
"""
    )


def test_history_detail_only_opens_the_last_clicked_job_when_responses_are_out_of_order():
    _run_node(
        """
const resolvers = [];
fetchHandler = () => new Promise((resolve) => resolvers.push(resolve));
const historyTarget = (jobId) => ({
  closest(selector) {
    return selector === "[data-history-job-id]" ? { dataset: { historyJobId: jobId } } : null;
  },
});

await document.emit("click", { target: historyTarget("older-job") });
await document.emit("click", { target: historyTarget("latest-job") });
assert.equal(resolvers.length, 2);

resolvers[1](jsonResponse({ operation: "apply", job_id: "latest-job", summary: { output_name: "latest.docx" }, result: { marker: "latest" } }));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(resultFileName.textContent, "latest.docx");

resolvers[0](jsonResponse({ operation: "apply", job_id: "older-job", summary: { output_name: "older.docx" }, result: { marker: "older" } }));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(resultFileName.textContent, "latest.docx");
"""
    )


def test_history_detail_does_not_reopen_results_after_leaving_history():
    _run_node(
        """
historyScreen.classList.toggle("active", true);
const target = {
  closest(selector) {
    return selector === "[data-history-job-id]"
      ? { dataset: { historyJobId: "history-job" } }
      : null;
  },
};

await document.emit("click", { target });
assert.ok(resolveFetch);
await workbenchNav.emit("click");
assert.equal(workbenchScreen.classList.contains("active"), true);

resolveFetch(jsonResponse({ operation: "apply", job_id: "history-job", result: { marker: "stale" } }));
await new Promise((resolve) => setImmediate(resolve));
assert.equal(workbenchScreen.classList.contains("active"), true);
assert.equal(resultScreen.classList.contains("active"), false);
"""
    )
