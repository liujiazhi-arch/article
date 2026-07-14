import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_VERSION = "20260714-module-ownership"
APP_URL = f"{(ROOT / 'scripts' / 'article_api' / 'static' / 'js' / 'app.js').as_uri()}?v={ASSET_VERSION}"
PDF_REVIEW_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "pdfReview.js").as_uri()
STATE_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "state.js").as_uri()


_NODE_HARNESS = f"""
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
    this.attributes = new Map();
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
  setAttribute(name, value) {{ this.attributes.set(name, String(value)); }}
  getAttribute(name) {{ return this.attributes.get(name) ?? null; }}
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
const autofixableScopesMetric = new FakeElement();
const manualConfirmationMetric = new FakeElement();
const resultHeatmap = new FakeElement();
const resultFileName = new FakeElement();
const resultDownloadNote = new FakeElement();
const resultReportText = new FakeElement();
const resultReportButton = new FakeElement();
resultReportButton.querySelector = (selector) => selector === "span" ? resultReportText : null;
const resultEmpty = new FakeElement();
resultEmpty.hidden = false;
const resultDetails = [new FakeElement(), new FakeElement()];
const workbenchLedger = new FakeElement();
const historyList = new FakeElement();
const docxFile = new FakeElement();
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
      '[data-workbench-metric="autofixable-scopes"]': autofixableScopesMetric,
      '[data-workbench-metric="manual-confirmation"]': manualConfirmationMetric,
      "[data-result-heatmap]": resultHeatmap,
      "[data-result-file-name]": resultFileName,
      "[data-result-download-note]": resultDownloadNote,
      "[data-download-role='report']": resultReportButton,
      "[data-result-empty]": resultEmpty,
      "[data-workbench-ledger]": workbenchLedger,
      "[data-history-list]": historyList,
      "[data-docx-file]": docxFile,
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
      "[data-result-detail]": resultDetails,
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


def _run_source(source: str) -> None:
    result = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT,
        input=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def run_node(scenario: str) -> None:
    _run_source(f"{_NODE_HARNESS}\n{scenario}")


def run_state_script(scenario: str) -> None:
    _run_source(
        f"""
import assert from "node:assert/strict";
import {{ getState }} from {json.dumps(STATE_URL)};
{scenario}
"""
    )
