import {
  createApplyJob,
  createPlan,
  createRenderReviewJob,
  downloadJobArtifactUrl,
  getJob,
  getJobResult,
  listJobs,
  uploadDocx,
  uploadPdf,
} from "./api.js";
import { getState, setState } from "./state.js";
import {
  bindPdfReview,
  clearPdfReview,
  isPdfReviewReady,
  renderPdfReview,
} from "./pdfReview.js";
import { renderEvidenceStatusLabels } from "./copy.js";
import { bindGlobalActions } from "./globalActions.js";
import { bindCoverForm, collectCoverFields, coverSelectionIsValid, prepareCoverScope, resetCoverForm } from "./coverForm.js";
import { renderStructureCounts, setFlowStage } from "./workflowView.js";
const finishedStates = new Set(["succeeded", "failed"]);
const blockingRenderEvidenceStatuses = new Set([
  "structure-not-ready",
  "blocked-by-wild-doc",
  "unsupported-evidence",
]);
const reviewRequiredResultStatuses = new Set([
  "manual-review-required",
  "manual_review",
  "unsupported",
  "mixed",
]);
const scopeLabels = {
  abstract: "摘要",
  acknowledgement: "致谢",
  appendix: "附录",
  body_paragraphs: "正文",
  cover: "封面",
  figures_tables: "图表",
  headings: "标题",
  page: "页面",
  references: "参考文献",
  toc: "目录",
};
const jobStatusLabels = {
  queued: "等待处理",
  running: "处理中",
  succeeded: "已完成",
  failed: "需要重试",
};
let historyRequestEpoch = 0;

function showScreen(name) {
  const screenButtons = document.querySelectorAll("[data-screen-target]");
  const screens = document.querySelectorAll("[data-screen]");
  const validScreens = new Set(Array.from(screens, (screen) => screen.dataset.screen));
  if (!validScreens.has(name)) return;
  historyRequestEpoch += 1;
  screens.forEach((screen) => screen.classList.toggle("active", screen.dataset.screen === name));
  screenButtons.forEach((button) => button.classList.toggle("active", button.dataset.screenTarget === name));
  if (name === "history") refreshHistory();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setStatus(title, message) {
  const titleNode = document.querySelector("[data-status-title]");
  const messageNode = document.querySelector("[data-status-message]");
  const nextActionNode = document.querySelector("[data-next-action]");
  if (titleNode) titleNode.textContent = title;
  if (messageNode) messageNode.textContent = message;
  if (nextActionNode) nextActionNode.textContent = message;
}

function setWorkbenchMetric(name, value) {
  const node = document.querySelector(`[data-workbench-metric="${name}"]`);
  if (node) node.textContent = String(value);
}
function setPdfMetric(name, value) {
  const node = document.querySelector(`[data-pdf-metric="${name}"]`);
  if (node) node.textContent = String(value);
}
function resetPdfMatchConfirmation(root) {
  const input = root.querySelector("#pdf-match-confirmation");
  if (input) input.checked = false;
}
function setPdfDocxFile(root, fileName = "等待上传论文") {
  const node = root.querySelector("[data-pdf-docx-file]");
  if (node) node.textContent = fileName;
}

function blockPdfUntilFreshDocx(root) {
  if (getState().pdfReviewRequiresFreshDocx !== true) return false;
  resetPdfMatchConfirmation(root);
  setStatus("先上传修复稿", "上传刚下载的修复稿后再复核 PDF");
  showScreen("result");
  return true;
}

function resetPdfReviewState(root, {
  renderState = "待上传",
  conclusion = "待确认",
  title = "等待 PDF 复核",
  message = "上传对应 PDF 后查看页面问题",
} = {}) {
  const nextEpoch = Number(getState().pdfReviewEpoch || 0) + 1;
  setState({
    pdfUpload: null,
    renderResult: null,
    renderResultPayload: null,
    activeEvidenceIndex: 0,
    pdfReviewEpoch: nextEpoch,
  });
  resetPdfMatchConfirmation(root);
  setPdfMetric("conclusion", conclusion);
  setPdfMetric("pages", "--");
  setPdfMetric("issues", "--");
  const stateNode = root.querySelector("[data-render-state]");
  const fileNode = root.querySelector("[data-pdf-file]");
  if (stateNode) stateNode.textContent = renderState;
  if (fileNode) fileNode.textContent = "等待上传对应 PDF";
  clearPdfReview(root, { title, message });
  return nextEpoch;
}

function resetDocumentState(root) {
  const nextEpoch = Number(getState().documentEpoch || 0) + 1;
  setState({
    documentEpoch: nextEpoch,
    docxUpload: null,
    workbenchPlan: null,
    applyResultPayload: null,
    activeJob: null,
    applyRunning: false,
  });
  renderScopeOptions(null, root);
  renderResultPanel(null);
  resetPdfReviewState(root);
  const fileNode = root.querySelector("[data-docx-file]");
  if (fileNode) fileNode.textContent = "等待上传论文";
  setPdfDocxFile(root);
  return nextEpoch;
}

function planSummary(plan) {
  const summary = plan && plan.summary ? plan.summary : {};
  const scopes = Array.isArray(plan?.scopes) ? plan.scopes : [];
  return {
    score: plan?.score,
    autofixableScopes: summary.autofixable_scopes ?? scopes.filter((scope) => Number(scope.autofixable_count || 0) > 0).length,
    manualConfirmation: summary.manual_confirmation_items ?? scopes.reduce((total, scope) => total + Number(scope.manual_review_count || 0) + Number(scope.unsupported_count || 0), 0),
    failedCount: summary.total_failed_count ?? plan?.total_failed_count ?? plan?.failed_count ?? scopes.reduce((total, scope) => total + Number(scope.failed_count || 0), 0),
  };
}

function renderWorkbenchLedger(lines) {
  const ledger = document.querySelector("[data-workbench-ledger]");
  if (!ledger) return;
  ledger.innerHTML = lines.map((line) => `
    <div class="ledger-line"><em>${escapeHtml(line.time)}</em><span>${escapeHtml(line.message)}</span><strong>${escapeHtml(line.status)}</strong></div>
  `).join("");
}

function renderFormatRadar(summary) {
  const radar = document.querySelector("[data-format-radar]");
  const label = document.querySelector("[data-format-radar-label]");
  if (!radar || !label) return;
  const score = Number(summary?.score);
  const hasScore = summary?.score != null && Number.isFinite(score);
  const progress = hasScore ? Math.max(0, Math.min(100, score)) : 0;
  radar.style.setProperty("--radar-progress", `${progress}%`);
  label.textContent = hasScore ? `${Math.round(progress)}分` : summary?.emptyLabel || "等待检查";
}

function selectedScopeIds(root = document) {
  return Array.from(root.querySelectorAll("[data-scope-option] input:checked:not(:disabled)"), (input) => input.value);
}

function updateApplyButtons(root = document) {
  const current = getState();
  const canRun = Boolean(current.docxUpload && current.workbenchPlan) && selectedScopeIds(root).length > 0 && coverSelectionIsValid(root) && !current.applyRunning;
  root.querySelectorAll("[data-action='create-apply-job']").forEach((button) => {
    button.disabled = !canRun;
    const label = button.querySelector("b");
    if (label) label.textContent = current.applyRunning ? "正在生成" : "生成结果";
  });
}

function renderScopeOptions(plan, root = document) {
  const scopes = new Map((Array.isArray(plan?.scopes) ? plan.scopes : []).map((scope) => [scope.id, scope]));
  root.querySelectorAll("[data-scope-option]").forEach((option) => {
    if (option.dataset.scopeOption === "cover") {
      prepareCoverScope(root);
      return;
    }
    const scope = scopes.get(option.dataset.scopeOption);
    const available = Number(scope?.autofixable_count || 0) > 0;
    const requiresReview = Number(scope?.manual_review_count || 0) > 0 || Number(scope?.unsupported_count || 0) > 0;
    const input = option.querySelector("input");
    const stateNode = option.querySelector("[data-scope-state]");
    if (input) {
      input.disabled = !available;
      input.checked = available;
      input.dataset.requiresReview = String(requiresReview);
    }
    if (stateNode) {
      stateNode.textContent = available
        ? requiresReview ? "已选 仍需确认" : "已选择"
        : requiresReview ? "需人工确认" : plan ? "无需处理" : "等待方案";
    }
  });
  updateApplyButtons(root);
}

function bindScopeControls(root) {
  root.querySelectorAll("[data-scope-option] input").forEach((input) => {
    input.addEventListener("change", () => {
      const stateNode = input.closest("[data-scope-option]").querySelector("[data-scope-state]");
      stateNode.textContent = input.checked ? "已选择" : "未选择";
      if (input.checked && input.dataset.requiresReview === "true") stateNode.textContent = "已选 仍需确认";
      updateApplyButtons(root);
    });
  });
}

function renderWorkbenchPlan(plan) {
  const summary = planSummary(plan);
  renderFormatRadar(summary);
  renderStructureCounts(plan);
  setFlowStage("plan");
  setWorkbenchMetric("autofixable-scopes", summary.autofixableScopes);
  setWorkbenchMetric("manual-confirmation", summary.manualConfirmation);
  setWorkbenchMetric("output-kind", "修复副本");
  renderScopeOptions(plan);
  renderWorkbenchLedger([
    { time: "刚刚", message: "论文已上传并完成初步检查", status: "完成" },
    { time: "刚刚", message: `发现 ${summary.autofixableScopes} 个可修复范围`, status: "完成" },
    { time: "刚刚", message: summary.manualConfirmation > 0 ? `${summary.manualConfirmation} 项需要你确认` : "暂未发现需要人工确认的项目", status: summary.manualConfirmation > 0 ? "需确认" : "完成" },
  ]);
}

function renderWorkbenchPlanPending(fileName, stage = "upload") {
  renderScopeOptions(null);
  renderFormatRadar({ emptyLabel: "检查中" });
  renderStructureCounts(null);
  setFlowStage(stage);
  setWorkbenchMetric("autofixable-scopes", "生成中");
  setWorkbenchMetric("manual-confirmation", "生成中");
  setWorkbenchMetric("output-kind", "修复副本");
  renderWorkbenchLedger([
    { time: "刚刚", message: `${fileName || "论文"} 已上传`, status: "完成" },
    { time: "刚刚", message: "正在生成真实修复方案", status: "处理中" },
    { time: "等待", message: "方案完成后会更新可修复范围", status: "等待" },
  ]);
}

function renderWorkbenchPlanUnavailable(message) {
  renderScopeOptions(null);
  renderFormatRadar({ emptyLabel: "待重试" });
  renderStructureCounts(null);
  setFlowStage("plan");
  setWorkbenchMetric("autofixable-scopes", "待重试");
  setWorkbenchMetric("manual-confirmation", "待重试");
  renderWorkbenchLedger([
    { time: "刚刚", message: "论文已上传", status: "完成" },
    { time: "刚刚", message: message || "修复方案暂时不可用", status: "提示" },
    { time: "等待", message: "请重新生成方案后选择修复范围", status: "待处理" },
  ]);
}

function showError(error) {
  setStatus(error.message || "操作没有完成", error.nextAction || "请检查文件后重试");
}

async function createWorkbenchPlanFromUpload(upload, documentEpoch = null) {
  renderWorkbenchPlanPending(upload.file_name, "plan");
  setStatus("论文已上传", "正在生成修复方案");
  try {
    const plan = await createPlan(upload.stored_path);
    if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
    setState({ workbenchPlan: plan });
    renderWorkbenchPlan(plan);
    setStatus("修复方案已生成", "可以生成修正结果");
    return plan;
  } catch (planError) {
    if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
    renderWorkbenchPlanUnavailable(planError.nextAction || "请稍后重试生成方案");
    setStatus("论文已上传", "修复方案暂时不可用");
    throw planError;
  }
}

function formatDateTime(value) {
  if (!value) return "本地";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "本地";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatScopes(scopes) {
  if (!Array.isArray(scopes) || !scopes.length) return "全部范围";
  return scopes.map((scope) => scopeLabels[scope] || "论文范围").join(" / ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function artifactByRole(payload, role) {
  return (payload && Array.isArray(payload.artifacts) ? payload.artifacts : []).find((item) => item.role === role);
}

function setDownloadButton(button, payload, role, unavailableText) {
  if (!button) return;
  const artifact = artifactByRole(payload, role);
  const available = Boolean(payload && payload.job_id && artifact && artifact.available);
  button.disabled = !available;
  button.dataset.jobId = payload && payload.job_id ? payload.job_id : "";
  if (available) {
    button.dataset.downloadUrl = downloadJobArtifactUrl(payload.job_id, role);
  } else {
    delete button.dataset.downloadUrl;
  }
  const span = button.querySelector("span");
  if (span && !available) span.textContent = unavailableText;
}

function renderHeatmap(payload) {
  const heatmap = document.querySelector("[data-result-heatmap]");
  if (!heatmap) return;
  if (!payload) {
    heatmap.replaceChildren();
    return;
  }
  const scopes = payload?.result?.verification?.scopes;
  if (!Array.isArray(scopes)) {
    heatmap.replaceChildren();
    return;
  }
  const coverStatus = {
    inserted: "已添加",
    replaced: "已替换",
  }[payload?.result?.cover_replacement?.status];
  heatmap.innerHTML = scopes.map((scope) => {
    const failedCount = Number(scope.failed_count || 0);
    const label = scope.title || scopeLabels[scope.id] || "论文范围";
    const status = scope.id === "cover" && coverStatus ? coverStatus : failedCount > 0 ? `${failedCount}项` : "通过";
    const description = escapeHtml(`${label} ${status}`);
    return `<span class="${failedCount > 0 ? "warn" : "pass"}" title="${description}" aria-label="${description}"><b>${escapeHtml(label)}</b><small>${escapeHtml(status)}</small></span>`;
  }).join("");
}

function resultPanelStatus(payload) {
  const summary = payload?.summary || {};
  const result = payload?.result || {};
  const businessStatus = summary.business_status ?? result.overall_status ?? result.verification?.overall_status;
  const readiness = summary.readiness ?? result.readiness ?? result.verification?.readiness;
  if (reviewRequiredResultStatuses.has(readiness) || reviewRequiredResultStatuses.has(businessStatus)) {
    return { badge: "待确认", title: "需要人工确认", message: "先查看报告中的人工复核项" };
  }
  if (businessStatus === "needs_fix" || readiness === "needs-fix") {
    return { badge: "待修复", title: "仍有格式问题", message: "先查看审查报告 再继续处理" };
  }
  if (readiness === "render-check-required") {
    return { badge: "待复核", title: "修复包已生成", message: "下载副本后导出 PDF 复核" };
  }
  if (!payload) return { badge: "待生成", title: "等待修复结果", message: "上传论文后生成修复副本" };
  return { badge: "已生成", title: "修复包已生成", message: "原文件未覆盖 下载后再复核" };
}

function renderResultStatus(payload) {
  const status = resultPanelStatus(payload);
  const badgeNode = document.querySelector(".completion-orb strong");
  const titleNode = document.querySelector(".result-hero h2");
  const messageNode = document.querySelector(".result-hero > p");
  if (badgeNode) badgeNode.textContent = status.badge;
  if (titleNode) titleNode.textContent = status.title;
  if (messageNode) messageNode.textContent = status.message;
}

function renderResultPanel(payload) {
  const summary = payload && payload.summary ? payload.summary : {};
  const output = artifactByRole(payload, "output");
  const report = artifactByRole(payload, "report");
  const fileName = output?.download_name
    || summary.output_name
    || (summary.output_path ? summary.output_path.split("/").pop() : null)
    || "等待修复结果";
  const scopeText = payload ? formatScopes(summary.selected_scopes) : "等待选择范围";
  const timeText = payload
    ? `${formatDateTime(payload.finished_at || payload.updated_at)} 本地生成`
    : "等待本地生成";
  const resultFileNode = document.querySelector("[data-result-file-name]");
  const resultScopeNode = document.querySelector("[data-result-scope]");
  const resultTimeNode = document.querySelector("[data-result-time]");
  const downloadNameNode = document.querySelector("[data-result-download-name]");
  const downloadNoteNode = document.querySelector("[data-result-download-note]");
  if (resultFileNode) resultFileNode.textContent = fileName;
  if (resultScopeNode) resultScopeNode.textContent = scopeText;
  if (resultTimeNode) resultTimeNode.textContent = timeText;
  if (downloadNameNode) downloadNameNode.textContent = fileName;
  if (downloadNoteNode) {
    downloadNoteNode.textContent = output?.available ? "原文件未覆盖" : "下载文件已不可用 请重新运行修复";
  }
  renderResultStatus(payload);
  setDownloadButton(document.querySelector("[data-download-role='output']"), payload, "output", "下载文件已不可用 请重新运行修复");
  setDownloadButton(document.querySelector("[data-download-role='report']"), payload, "report", "报告文件已不可用 请重新运行修复");
  if (report && report.available) {
    const reportButton = document.querySelector("[data-download-role='report']");
    const reportText = reportButton && reportButton.querySelector("span");
    if (reportText) reportText.textContent = "下载报告文件 查看规则摘要和人工复核项";
  }
  renderHeatmap(payload);
}

function pdfConclusion(result, issues) {
  const summary = result && result.summary ? result.summary : {};
  const evidenceStatus = summary.render_evidence_status ?? result?.render_evidence_status;
  if (blockingRenderEvidenceStatuses.has(evidenceStatus)) {
    return renderEvidenceStatusLabels[evidenceStatus] || "待确认";
  }
  if (Number(issues) > 0) return "需复核";
  if (evidenceStatus === "render-evidence-ready") return isPdfReviewReady(result) ? "无异常" : "待确认";
  return renderEvidenceStatusLabels[evidenceStatus] || "待确认";
}

function renderPdfMetrics(result) {
  const summary = result && result.summary ? result.summary : {};
  const pages = summary.page_count ?? result?.page_count ?? "--";
  const issues = summary.evidence_item_count
    ?? (Array.isArray(result?.evidence_items) ? result.evidence_items.length : null)
    ?? summary.actionable_finding_count
    ?? result?.render_summary?.actionable_finding_count
    ?? (Array.isArray(result?.evidence_items) ? result.evidence_items.length : "--");
  setPdfMetric("conclusion", pdfConclusion(result, issues));
  setPdfMetric("pages", pages);
  setPdfMetric("issues", issues);
}

async function pollJob(jobId, {
  renderResult = false,
  docxUploadId = null,
  pdfReviewEpoch = null,
  documentEpoch = null,
} = {}) {
  while (true) {
    if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
    if (pdfReviewEpoch && getState().pdfReviewEpoch !== pdfReviewEpoch) return null;
    const job = await getJob(jobId);
    if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
    if (pdfReviewEpoch && getState().pdfReviewEpoch !== pdfReviewEpoch) return null;
    setState({ activeJob: job });
    if (finishedStates.has(job.status)) {
      if (job.status === "failed") {
        throw new Error("处理没有完成");
      }
      if (renderResult) {
        if (pdfReviewEpoch && getState().pdfReviewEpoch !== pdfReviewEpoch) return null;
        if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
        if (docxUploadId && getState().docxUpload?.upload_id !== docxUploadId) return null;
        const resultPayload = await getJobResult(jobId);
        if (pdfReviewEpoch && getState().pdfReviewEpoch !== pdfReviewEpoch) return null;
        if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
        if (docxUploadId && getState().docxUpload?.upload_id !== docxUploadId) return null;
        setState({ renderResult: resultPayload.result, renderResultPayload: resultPayload, activeEvidenceIndex: 0 });
        renderCurrentPdfReview();
      }
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

function renderCurrentPdfReview() {
  const root = document.querySelector("[data-screen='pdf-review']");
  const current = getState();
  const result = current.renderResult;
  if (!root || !result) return;
  renderPdfReview(root, result, current.renderResultPayload);
  renderPdfMetrics(result);
}
async function refreshHistory() {
  const list = document.querySelector("[data-history-list]");
  if (!list) return;
  const requestEpoch = historyRequestEpoch;
  try {
    const jobs = await listJobs({ limit: 10 });
    if (requestEpoch !== historyRequestEpoch) return;
    setState({ jobHistory: jobs });
    renderHistory(jobs);
  } catch (error) {
    if (requestEpoch !== historyRequestEpoch) return;
    list.innerHTML = `<div class="task-card"><div class="task-date">稍后<br>重试</div><div><b>历史记录暂时不可用</b><span>${escapeHtml(error.nextAction || "请稍后刷新")}</span></div><span class="status">提示</span></div>`;
  }
}

function renderHistory(jobs) {
  const list = document.querySelector("[data-history-list]");
  if (!list) return;
  if (!Array.isArray(jobs) || !jobs.length) {
    list.innerHTML = `<div class="task-card"><div class="task-date">等待<br>记录</div><div><b>还没有历史记录</b><span>上传论文后会显示在这里</span></div><span class="status">待开始</span></div>`;
    return;
  }
  const sortedJobs = [...jobs].sort((left, right) => {
    const leftOpen = left.status === "succeeded" && left.result_available && ["apply", "render-verify"].includes(left.operation);
    const rightOpen = right.status === "succeeded" && right.result_available && ["apply", "render-verify"].includes(right.operation);
    return Number(rightOpen) - Number(leftOpen);
  });
  list.innerHTML = sortedJobs.map((job) => {
    const display = job.display || {};
    const title = display.document_name || display.title || "本地处理记录";
    const openable = job.status === "succeeded" && job.result_available && ["apply", "render-verify"].includes(job.operation);
    const detail = openable
      ? (display.output_name || display.title || "点击查看处理结果")
      : job.status === "failed"
        ? "处理没有完成 请重新运行"
        : "处理完成后可以查看结果";
    const status = jobStatusLabels[job.status] || "处理中";
    const time = formatDateTime(display.updated_at || job.updated_at);
    return `
      <button class="task-card" type="button" ${openable ? `data-history-job-id="${escapeHtml(job.job_id)}"` : "disabled"}>
        <div class="task-date">${time.replace(" ", "<br>")}</div>
        <div><b>${escapeHtml(title)}</b><span>${escapeHtml(detail)}</span></div>
        <span class="status">${escapeHtml(status)}</span>
      </button>
    `;
  }).join("");
}

async function openHistoryJob(jobId) {
  const requestEpoch = ++historyRequestEpoch;
  const { documentEpoch, pdfReviewEpoch } = getState();
  const resultPayload = await getJobResult(jobId);
  const current = getState();
  if (
    requestEpoch !== historyRequestEpoch
    || current.documentEpoch !== documentEpoch
    || current.pdfReviewEpoch !== pdfReviewEpoch
  ) return;
  setState({ selectedHistoryJob: resultPayload });
  if (resultPayload.operation === "render-verify") {
    const summary = resultPayload.summary || {};
    setState({
      renderResult: resultPayload.result,
      renderResultPayload: resultPayload,
      activeEvidenceIndex: 0,
      pdfReviewEpoch: Number(current.pdfReviewEpoch || 0) + 1,
      pdfReviewRequiresFreshDocx: true,
    });
    resetPdfMatchConfirmation(document);
    setPdfDocxFile(document, summary.document_name || "历史论文");
    const pdfFileNode = document.querySelector("[data-pdf-file]");
    const renderStateNode = document.querySelector("[data-render-state]");
    if (pdfFileNode) pdfFileNode.textContent = summary.pdf_name || "历史 PDF";
    if (renderStateNode) renderStateNode.textContent = "已完成";
    renderCurrentPdfReview();
    showScreen("pdf-review");
    return;
  }
  if (resultPayload.operation === "apply") {
    resetPdfReviewState(document);
    setState({ applyResultPayload: resultPayload });
    renderResultPanel(resultPayload);
    showScreen("result");
  }
}

async function handleCreatePlan() {
  try {
    const current = getState();
    if (!current.docxUpload) {
      setStatus("请先上传论文", "选择 docx 文件后再生成修复方案");
      return;
    }
    await createWorkbenchPlanFromUpload(current.docxUpload, current.documentEpoch);
  } catch (error) {
    showError(error);
  }
}

async function handleCreateApplyJob(root) {
  const current = getState();
  if (!current.docxUpload) {
    setStatus("请先上传论文", "选择 docx 文件后再生成修正结果");
    return;
  }
  if (!current.workbenchPlan) {
    setStatus("请先生成修复方案", "方案完成后再生成修正结果");
    return;
  }
  const scopes = selectedScopeIds(root);
  if (!scopes.length) {
    setStatus("请选择修复范围", "先生成方案 再勾选需要处理的范围");
    return;
  }
  const coverFields = scopes.includes("cover") ? collectCoverFields(root) : null;
  if (scopes.includes("cover") && !coverFields) {
    setStatus("请填完整封面信息", "填写六项信息后再生成修正结果");
    return;
  }
  setState({ applyRunning: true });
  const documentEpoch = current.documentEpoch;
  const requestEpoch = historyRequestEpoch;
  setFlowStage("apply");
  updateApplyButtons(root);
  try {
    setStatus("正在生成修正结果", "请稍候");
    const job = await createApplyJob(current.docxUpload.upload_id, { scopes, ...(coverFields ? { cover_fields: coverFields } : {}) });
    if (getState().documentEpoch !== documentEpoch || historyRequestEpoch !== requestEpoch) return;
    setState({ activeJob: job });
    await pollJob(job.job_id, { documentEpoch });
    if (getState().documentEpoch !== documentEpoch || historyRequestEpoch !== requestEpoch) return;
    setFlowStage("verify");
    const resultPayload = await getJobResult(job.job_id);
    if (getState().documentEpoch !== documentEpoch || historyRequestEpoch !== requestEpoch) return;
    resetPdfReviewState(root, {
      title: "先上传修复稿",
      message: "上传刚下载的修复稿后再复核 PDF",
    });
    setState({ applyResultPayload: resultPayload, pdfReviewRequiresFreshDocx: true });
    renderResultPanel(resultPayload);
    setFlowStage("download");
    setStatus("修正结果已生成", "可以到结果页下载副本");
    showScreen("result");
  } catch (error) {
    if (getState().documentEpoch !== documentEpoch || historyRequestEpoch !== requestEpoch) return;
    showError(error);
  } finally {
    if (getState().documentEpoch === documentEpoch) {
      setState({ applyRunning: false });
      updateApplyButtons(root);
    }
  }
}

async function handleDocxUpload(root, docxInput) {
  const file = docxInput.files && docxInput.files[0];
  if (!file) return;
  const hadCurrentDocument = Boolean(getState().docxUpload);
  const documentEpoch = resetDocumentState(root);
  renderWorkbenchPlanPending(file.name);
  try {
    setStatus("正在上传论文", "请稍候");
    const upload = await uploadDocx(file);
    if (getState().documentEpoch !== documentEpoch) return;
    setState({ docxUpload: upload, pdfReviewRequiresFreshDocx: false });
    if (hadCurrentDocument) resetCoverForm(root);
    const fileNode = root.querySelector("[data-docx-file]");
    if (fileNode) fileNode.textContent = upload.file_name;
    setPdfDocxFile(root, upload.file_name);
    await createWorkbenchPlanFromUpload(upload, documentEpoch);
  } catch (error) {
    if (getState().documentEpoch !== documentEpoch) return;
    showError(error);
  } finally {
    docxInput.value = "";
  }
}

async function handlePdfUpload(root, pdfInput) {
  const file = pdfInput.files && pdfInput.files[0];
  if (!file) return;
  const current = getState();
  if (blockPdfUntilFreshDocx(root)) {
    pdfInput.value = "";
    return;
  }
  if (!current.docxUpload) {
    setStatus("请先上传论文", "PDF 需要和当前论文对应");
    showScreen("workbench");
    pdfInput.value = "";
    return;
  }
  const confirmation = root.querySelector("#pdf-match-confirmation");
  if (!confirmation || confirmation.checked !== true) {
    resetPdfReviewState(root);
    setStatus("请确认 PDF 来源", "勾选确认后再选择 PDF");
    pdfInput.value = "";
    return;
  }
  const docxUploadId = current.docxUpload.upload_id;
  const documentEpoch = current.documentEpoch;
  const pdfReviewEpoch = resetPdfReviewState(root, {
    renderState: "复核中",
    title: "正在复核 PDF",
    message: "完成后显示页面问题",
  });
  try {
    setStatus("正在上传 PDF", "请稍候");
    const pdfUpload = await uploadPdf(file);
    if (getState().pdfReviewEpoch !== pdfReviewEpoch) return;
    const fileNode = root.querySelector("[data-pdf-file]");
    if (fileNode) fileNode.textContent = pdfUpload.file_name;
    setStatus("正在复核 PDF", "请稍候");
    const job = await createRenderReviewJob(docxUploadId, pdfUpload.upload_id, true);
    if (getState().pdfReviewEpoch !== pdfReviewEpoch) return;
    setState({ pdfUpload, activeJob: job });
    const renderState = root.querySelector("[data-render-state]");
    await pollJob(job.job_id, { renderResult: true, docxUploadId, pdfReviewEpoch, documentEpoch });
    if (getState().pdfReviewEpoch !== pdfReviewEpoch) return;
    if (getState().docxUpload?.upload_id !== docxUploadId) return;
    renderCurrentPdfReview();
    if (renderState) renderState.textContent = "已完成";
    setStatus("PDF 复核完成", "可以查看页面问题");
    showScreen("pdf-review");
  } catch (error) {
    if (getState().pdfReviewEpoch !== pdfReviewEpoch) return;
    if (getState().docxUpload?.upload_id !== docxUploadId) return;
    resetPdfReviewState(root, {
      renderState: "未完成",
      conclusion: "待确认",
      title: "本次复核未完成",
      message: "请重新上传对应 PDF",
    });
    showError(error);
  } finally {
    pdfInput.value = "";
  }
}

function bindUploads(root) {
  const docxInput = root.querySelector("#docx-input");
  const pdfInput = root.querySelector("#pdf-input");
  root.querySelectorAll("[data-action='choose-docx']").forEach((button) => {
    button.addEventListener("click", () => docxInput && docxInput.click());
  });
  root.querySelectorAll("[data-action='choose-pdf']").forEach((button) => {
    button.addEventListener("click", () => {
      if (!blockPdfUntilFreshDocx(root) && pdfInput) pdfInput.click();
    });
  });
  root.querySelectorAll("[data-action='create-plan']").forEach((button) => {
    button.addEventListener("click", handleCreatePlan);
  });
  root.querySelectorAll("[data-action='create-apply-job']").forEach((button) => {
    button.addEventListener("click", () => handleCreateApplyJob(root));
  });
  bindScopeControls(root);
  bindCoverForm(root, () => updateApplyButtons(root));
  root.querySelectorAll("[data-action='refresh-render-result']").forEach((button) => {
    button.addEventListener("click", renderCurrentPdfReview);
  });
  if (docxInput) docxInput.addEventListener("change", () => handleDocxUpload(root, docxInput));
  if (pdfInput) pdfInput.addEventListener("change", () => handlePdfUpload(root, pdfInput));
}

export function initWorkbench() {
  const body = document.body;
  const screenButtons = document.querySelectorAll("[data-screen-target]");
  const themeButtons = document.querySelectorAll("[data-theme-choice]");

  screenButtons.forEach((button) => {
    button.addEventListener("click", () => showScreen(button.dataset.screenTarget));
  });

  bindGlobalActions(document, {
    openHistoryJob,
    scopeLabel: (scopeId) => scopeLabels[scopeId] || "对应",
    setStatus,
    showError,
    showScreen,
    updateApplyButtons,
  });

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      body.dataset.theme = button.dataset.themeChoice;
      themeButtons.forEach((item) => item.classList.toggle("active", item === button));
    });
  });

  renderResultPanel(null);
  resetPdfReviewState(document);
  bindUploads(document);
  bindPdfReview(document, renderCurrentPdfReview);
}

initWorkbench();
