import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "app.js").as_uri()
PDF_REVIEW_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "pdfReview.js").as_uri()
STATE_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "state.js").as_uri()


NODE_HARNESS = f"""
import assert from "node:assert/strict";

class FakeElement {{
  constructor() {{
    this.dataset = {{}};
    this.files = [];
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.textContent = "";
    this.innerHTML = "";
    this.clickCount = 0;
    this.children = [];
    this.listeners = new Map();
    this.classes = new Set();
    this.styleValues = {{}};
    this.classList = {{
      toggle: (name, force) => {{
        if (force === undefined ? !this.classes.has(name) : force) this.classes.add(name);
        else this.classes.delete(name);
      }},
      contains: (name) => this.classes.has(name),
    }};
    this.style = {{
      setProperty: (name, value) => {{ this.styleValues[name] = value; }},
    }};
  }}

  addEventListener(type, listener) {{
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }}

  async emit(type, event = {{}}) {{
    for (const listener of this.listeners.get(type) || []) {{
      await listener({{ target: this, ...event }});
    }}
  }}

  querySelector() {{ return null; }}
  querySelectorAll() {{ return []; }}
  get firstElementChild() {{ return this.children[0] || null; }}
  replaceChildren(...children) {{ this.children = children; }}
  append(...children) {{ this.children.push(...children); }}
  click() {{ this.clickCount += 1; }}
}}

const pdfInput = new FakeElement();
const docxInput = new FakeElement();
const pdfMatchConfirmation = new FakeElement();
const choosePdfButton = new FakeElement();
const chooseDocxButton = new FakeElement();
const applyButton = new FakeElement();
const scopeInput = new FakeElement();
scopeInput.checked = true;
scopeInput.value = "toc";
const scopeState = new FakeElement();
const scopeOption = new FakeElement();
scopeOption.dataset.scopeOption = "toc";
scopeOption.querySelector = (selector) => selector === "input" ? scopeInput : selector === "[data-scope-state]" ? scopeState : null;
scopeInput.closest = () => scopeOption;
let exposeScopeOption = false;
const statusTitle = new FakeElement();
const statusMessage = new FakeElement();
const nextAction = new FakeElement();
const pdfConclusion = new FakeElement();
const formatRadar = new FakeElement();
const formatRadarLabel = new FakeElement();
const resultHeatmap = new FakeElement();
const workbenchLedger = new FakeElement();
const historyList = new FakeElement();
const pdfFile = new FakeElement();
const pdfDocxFile = new FakeElement();
const renderState = new FakeElement();
const tocOutputAction = new FakeElement();
tocOutputAction.hidden = true;
const tocOutputNextAction = new FakeElement();
const tocOutputButton = new FakeElement();
tocOutputButton.dataset.downloadRole = "toc-output";
tocOutputButton.disabled = true;

function createStructureNode(scopes) {{
  const node = new FakeElement();
  node.dataset.structureScopes = scopes;
  node.counter = new FakeElement();
  node.querySelector = (selector) => selector === "[data-structure-count]" ? node.counter : null;
  return node;
}}

const structureMain = createStructureNode("abstract,toc,body_paragraphs,references,figures_tables");
const structureAbstract = createStructureNode("abstract");
const structureToc = createStructureNode("toc");
const structureBody = createStructureNode("body_paragraphs");
const structureReferences = createStructureNode("references");
const structureFigures = createStructureNode("figures_tables");
const structureNodes = [structureMain, structureAbstract, structureToc, structureBody, structureReferences, structureFigures];
const flowSteps = ["upload", "plan", "apply", "verify", "download"].map((stage) => {{
  const step = new FakeElement();
  step.dataset.flowStage = stage;
  return step;
}});
const pdfScreen = new FakeElement();
pdfScreen.dataset.screen = "pdf-review";
pdfScreen.querySelector = (selector) => ({{
  "[data-toc-output-action]": tocOutputAction,
  "[data-toc-output-next-action]": tocOutputNextAction,
  "[data-download-role='toc-output']": tocOutputButton,
}}[selector] || null);
const workbenchScreen = new FakeElement();
workbenchScreen.dataset.screen = "workbench";
const historyScreen = new FakeElement();
historyScreen.dataset.screen = "history";
const resultScreen = new FakeElement();
resultScreen.dataset.screen = "result";
const workbenchNav = new FakeElement();
workbenchNav.dataset.screenTarget = "workbench";
const historyNav = new FakeElement();
historyNav.dataset.screenTarget = "history";
class FakeDocument extends FakeElement {{
  constructor() {{
    super();
    this.body = new FakeElement();
  }}

  querySelector(selector) {{
    const elements = {{
      "#pdf-input": pdfInput,
      "#docx-input": docxInput,
      "#pdf-match-confirmation": pdfMatchConfirmation,
      "[data-status-title]": statusTitle,
      "[data-status-message]": statusMessage,
      "[data-next-action]": nextAction,
      '[data-pdf-metric="conclusion"]': pdfConclusion,
      "[data-format-radar]": formatRadar,
      "[data-format-radar-label]": formatRadarLabel,
      "[data-result-heatmap]": resultHeatmap,
      "[data-workbench-ledger]": workbenchLedger,
      "[data-history-list]": historyList,
      "[data-pdf-file]": pdfFile,
      "[data-pdf-docx-file]": pdfDocxFile,
      "[data-render-state]": renderState,
      "[data-toc-output-action]": tocOutputAction,
      "[data-toc-output-next-action]": tocOutputNextAction,
      "[data-download-role='toc-output']": tocOutputButton,
      "[data-screen='pdf-review']": pdfScreen,
    }};
    return elements[selector] || null;
  }}

  querySelectorAll(selector) {{
    const elements = {{
      "[data-action='choose-docx']": [chooseDocxButton],
      "[data-action='choose-pdf']": [choosePdfButton],
      "[data-action='create-apply-job']": [applyButton],
      "[data-screen-target]": [workbenchNav, historyNav],
      "[data-screen]": [workbenchScreen, historyScreen, pdfScreen, resultScreen],
      "[data-scope-option]": exposeScopeOption ? [scopeOption] : [],
      "[data-scope-option] input": exposeScopeOption ? [scopeInput] : [],
      "[data-structure-scopes]": structureNodes,
      "[data-flow-stage]": flowSteps,
      "[data-scope-option] input:checked:not(:disabled)": scopeInput.checked && !scopeInput.disabled ? [scopeInput] : [],
    }};
    return elements[selector] || [];
  }}

  createElement() {{ return new FakeElement(); }}
}}

globalThis.document = new FakeDocument();
globalThis.window = {{ location: {{ href: "" }}, scrollTo() {{}} }};
globalThis.FormData = class {{ append() {{}} }};

let resolveFetch;
let fetchCalls = [];
let fetchHandler = () => new Promise((resolve) => {{ resolveFetch = resolve; }});
globalThis.fetch = (url, options = {{}}) => {{
  fetchCalls.push({{ url, options }});
  return fetchHandler(url, options);
}};

function jsonResponse(payload, status = 200) {{
  return {{
    ok: status >= 200 && status < 300,
    status,
    async text() {{ return JSON.stringify(payload); }},
  }};
}}

function installSuccessfulPdfReview(result, payload = {{}}) {{
  fetchHandler = async (url) => {{
    if (url === "/uploads/pdf") return jsonResponse({{ upload_id: "pdf-1", file_name: "paper.pdf" }});
    if (url.endsWith("/render-review-jobs")) return jsonResponse({{ job_id: "render-1" }}, 201);
    if (url === "/jobs/render-1") return jsonResponse({{ job_id: "render-1", status: "succeeded" }});
    if (url === "/jobs/render-1/result") return jsonResponse({{
      operation: "render-verify",
      job_id: "render-1",
      artifacts: [],
      ...payload,
      result,
    }});
    throw new Error(`unexpected request ${{url}}`);
  }};
}}

function installSuccessfulApply(resultPayload = null) {{
  setState({{ workbenchPlan: {{ scopes: [] }} }});
  const payload = resultPayload || {{ operation: "apply", job_id: "apply-1", result: {{}}, summary: {{}}, artifacts: [] }};
  fetchHandler = async (url) => {{
    if (url.endsWith("/jobs/apply")) return jsonResponse({{ job_id: "apply-1" }}, 201);
    if (url === "/jobs/apply-1") return jsonResponse({{ job_id: "apply-1", status: "succeeded" }});
    if (url === "/jobs/apply-1/result") {{
      return jsonResponse(payload);
    }}
    throw new Error(`unexpected request ${{url}}`);
  }};
}}

await import({json.dumps(APP_URL)});
const {{ getState, setState }} = await import({json.dumps(STATE_URL)});

async function openHistoryAndResolve(payload, mutateEpoch) {{
  const historyButton = {{ dataset: {{ historyJobId: "history-job" }} }};
  const target = {{
    closest(selector) {{
      return selector === "[data-history-job-id]" ? historyButton : null;
    }},
  }};
  await document.emit("click", {{ target }});
  assert.ok(resolveFetch, "history click should request the job result");
  mutateEpoch();
  resolveFetch({{
    ok: true,
    status: 200,
    async text() {{ return JSON.stringify(payload); }},
  }});
  await new Promise((resolve) => setImmediate(resolve));
}}
"""


def _run_node(scenario: str) -> None:
    result = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT,
        input=f"{NODE_HARNESS}\n{scenario}",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_pdf_can_be_selected_again_after_docx_precondition_rejects_it():
    _run_node(
        """
pdfInput.files = [{ name: "same.pdf" }];
pdfInput.value = "same.pdf";
await pdfInput.emit("change");
assert.equal(pdfInput.value, "");
"""
    )


def test_format_radar_uses_the_backend_score_without_recounting_findings():
    _run_node(
        """
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/plan") {
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


def test_plan_updates_structure_counts_and_preserves_mixed_scope_warning():
    _run_node(
        """
exposeScopeOption = true;
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/plan") {
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


def test_plan_ledger_does_not_claim_a_scope_count_for_manual_items():
    _run_node(
        """
fetchHandler = async (url) => {
  if (url === "/uploads/docx") {
    return jsonResponse({ upload_id: "docx-1", file_name: "paper.docx", stored_path: "/tmp/paper.docx" });
  }
  if (url === "/plan") {
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
assert.deepEqual(getState().jobHistory, []);
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
  if (url === "/plan") {
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
assert.equal((resultHeatmap.innerHTML.match(/<span/g) || []).length, 2);
assert.equal(flowSteps.find((step) => step.dataset.flowStage === "download").classList.contains("active"), true);
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
  if (url === "/plan") return jsonResponse({ scopes: [], summary: {} });
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
