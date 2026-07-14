from tests.frontend_app_harness import run_node as _run_node


def test_latest_docx_upload_owns_the_workbench_when_responses_arrive_out_of_order():
    _run_node(
        """
let firstUpload;
let secondUpload;
let uploadCount = 0;
fetchHandler = (url) => {
  if (url === "/uploads/docx") {
    uploadCount += 1;
    return new Promise((resolve) => {
      if (uploadCount === 1) firstUpload = resolve;
      else secondUpload = resolve;
    });
  }
  if (url === "/uploads/docx-2/plan") {
    return Promise.resolve(jsonResponse({ score: 96, scopes: [], summary: {}, owner: "second" }));
  }
  throw new Error(`unexpected request ${url}`);
};

docxInput.files = [{ name: "first.docx" }];
const firstFlow = docxInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));
docxInput.files = [{ name: "second.docx" }];
const secondFlow = docxInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));

secondUpload(jsonResponse({ upload_id: "docx-2", file_name: "second.docx" }));
await secondFlow;
firstUpload(jsonResponse({ upload_id: "docx-1", file_name: "first.docx" }));
await firstFlow;

assert.equal(getState().docxUpload.upload_id, "docx-2");
assert.equal(getState().workbenchPlan.owner, "second");
assert.equal(docxFile.textContent, "second.docx");
assert.equal(pdfDocxFile.textContent, "second.docx");
assert.deepEqual(fetchCalls.filter(({ url }) => url.endsWith("/plan")).map(({ url }) => url), [
  "/uploads/docx-2/plan",
]);
"""
    )


def test_latest_pdf_review_owns_the_view_when_uploads_finish_out_of_order():
    _run_node(
        """
setState({
  docxUpload: { upload_id: "docx-1", file_name: "paper.docx" },
  documentEpoch: 10,
  pdfReviewRequiresFreshDocx: false,
});
let firstUpload;
let secondUpload;
let uploadCount = 0;
const reviewRequests = [];
fetchHandler = (url, options) => {
  if (url === "/uploads/pdf") {
    uploadCount += 1;
    return new Promise((resolve) => {
      if (uploadCount === 1) firstUpload = resolve;
      else secondUpload = resolve;
    });
  }
  if (url.endsWith("/render-review-jobs")) {
    reviewRequests.push(JSON.parse(options.body));
    return Promise.resolve(jsonResponse({ job_id: "render-2" }, 201));
  }
  if (url === "/jobs/render-2") {
    return Promise.resolve(jsonResponse({ job_id: "render-2", status: "succeeded" }));
  }
  if (url === "/jobs/render-2/result") {
    return Promise.resolve(jsonResponse({
      operation: "render-verify",
      job_id: "render-2",
      artifacts: [],
      result: { marker: "second", evidence_items: [] },
    }));
  }
  throw new Error(`unexpected request ${url}`);
};

pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "first.pdf" }];
const firstFlow = pdfInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));
pdfMatchConfirmation.checked = true;
pdfInput.files = [{ name: "second.pdf" }];
const secondFlow = pdfInput.emit("change");
await new Promise((resolve) => setImmediate(resolve));

secondUpload(jsonResponse({ upload_id: "pdf-2", file_name: "second.pdf" }));
await secondFlow;
firstUpload(jsonResponse({ upload_id: "pdf-1", file_name: "first.pdf" }));
await firstFlow;

assert.equal(getState().renderResult.marker, "second");
assert.equal(pdfFile.textContent, "second.pdf");
assert.deepEqual(reviewRequests, [{
  pdf_upload_id: "pdf-2",
  pdf_matches_docx_confirmed: true,
  generate_static_toc: true,
}]);
"""
    )
