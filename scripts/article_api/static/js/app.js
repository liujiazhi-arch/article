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
import { bindPdfReview, renderPdfReview } from "./pdfReview.js";

const finishedStates = new Set(["succeeded", "failed"]);
const scopeLabels = {
  abstract: "摘要",
  acknowledgement: "致谢",
  appendix: "附录",
  body_paragraphs: "正文",
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

const scopeShortLabels = {
  abstract: "摘要",
  acknowledgement: "致谢",
  appendix: "附录",
  body_paragraphs: "正文",
  figures_tables: "图表",
  headings: "标题",
  page: "页面",
  references: "文献",
  toc: "目录",
};

function showScreen(name) {
  const screenButtons = document.querySelectorAll("[data-screen-target]");
  const screens = document.querySelectorAll("[data-screen]");
  const validScreens = new Set(Array.from(screens, (screen) => screen.dataset.screen));
  if (!validScreens.has(name)) return;
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

function planSummary(plan) {
  const summary = plan && plan.summary ? plan.summary : {};
  const scopes = Array.isArray(plan?.scopes) ? plan.scopes : [];
  return {
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
  const failedCount = Number(summary.failedCount || 0);
  const manualCount = Number(summary.manualConfirmation || 0);
  const totalAttention = failedCount + manualCount;
  const progress = Math.max(8, Math.min(100, 100 - totalAttention * 6));
  radar.style.setProperty("--radar-progress", `${progress}%`);
  label.textContent = totalAttention > 0 ? `${totalAttention}项需确认` : "格式较稳";
}

function renderWorkbenchPlan(plan) {
  const summary = planSummary(plan);
  renderFormatRadar(summary);
  setWorkbenchMetric("autofixable-scopes", summary.autofixableScopes);
  setWorkbenchMetric("manual-confirmation", summary.manualConfirmation);
  setWorkbenchMetric("output-kind", "修复副本");
  const scopes = Array.isArray(plan?.scopes) ? plan.scopes : [];
  const focusScopes = scopes
    .filter((scope) => Number(scope.failed_count || 0) > 0)
    .slice(0, 3)
    .map((scope) => scopeShortLabels[scope.id] || scope.title || "论文范围")
    .join(" ");
  renderWorkbenchLedger([
    { time: "刚刚", message: "论文已上传并完成初步检查", status: "完成" },
    { time: "刚刚", message: `发现 ${summary.autofixableScopes} 个可修复范围`, status: "完成" },
    { time: "刚刚", message: summary.manualConfirmation > 0 ? `${summary.manualConfirmation} 项需要你确认 ${focusScopes}`.trim() : "暂未发现需要人工确认的项目", status: summary.manualConfirmation > 0 ? "需确认" : "完成" },
  ]);
}

function renderWorkbenchPlanPending(fileName) {
  renderFormatRadar({ failedCount: 0, manualConfirmation: 0 });
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
  renderFormatRadar({ failedCount: 0, manualConfirmation: 1 });
  setWorkbenchMetric("autofixable-scopes", "待重试");
  setWorkbenchMetric("manual-confirmation", "待重试");
  renderWorkbenchLedger([
    { time: "刚刚", message: "论文已上传", status: "完成" },
    { time: "刚刚", message: message || "修复方案暂时不可用", status: "提示" },
    { time: "等待", message: "可以稍后重新上传或直接生成修正结果", status: "待处理" },
  ]);
}

function showError(error) {
  setStatus(error.message || "操作没有完成", error.nextAction || "请检查文件后重试");
}

async function createWorkbenchPlanFromUpload(upload) {
  renderWorkbenchPlanPending(upload.file_name);
  setStatus("论文已上传", "正在生成修复方案");
  try {
    const plan = await createPlan(upload.stored_path);
    setState({ workbenchPlan: plan });
    renderWorkbenchPlan(plan);
    setStatus("修复方案已生成", "可以生成修正结果");
    return plan;
  } catch (planError) {
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
  const result = payload && payload.result ? payload.result : {};
  const verification = result.verification || {};
  const summary = verification.summary || {};
  const failed = Number(summary.failed_rules || 0);
  const notices = Array.isArray(result.post_verify_notices)
    ? result.post_verify_notices.length
    : Number(payload?.summary?.post_verify_notice_count || 0);
  const passCount = Math.max(1, Math.min(27, 27 - failed - notices));
  heatmap.innerHTML = Array.from({ length: 27 }, (_item, index) => {
    const className = index < passCount ? "pass" : index < passCount + notices + failed ? "warn" : "";
    return `<span class="${className}"></span>`;
  }).join("");
}

function renderResultPanel(payload) {
  const summary = payload && payload.summary ? payload.summary : {};
  const output = artifactByRole(payload, "output");
  const report = artifactByRole(payload, "report");
  const fileName = output?.download_name
    || summary.output_name
    || (summary.output_path ? summary.output_path.split("/").pop() : null)
    || "等待修复结果";
  const scopeText = formatScopes(summary.selected_scopes);
  const timeText = `${formatDateTime(payload?.finished_at || payload?.updated_at)} 本地生成`;
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
  setDownloadButton(document.querySelector("[data-download-role='output']"), payload, "output", "下载文件已不可用 请重新运行修复");
  setDownloadButton(document.querySelector("[data-download-role='report']"), payload, "report", "报告文件已不可用 请重新运行修复");
  if (report && report.available) {
    const reportButton = document.querySelector("[data-download-role='report']");
    const reportText = reportButton && reportButton.querySelector("span");
    if (reportText) reportText.textContent = "下载报告文件 查看规则摘要和人工复核项";
  }
  renderHeatmap(payload);
}

function renderPdfMetrics(result) {
  const summary = result && result.summary ? result.summary : {};
  const score = summary.layout_score ?? "--";
  const pages = summary.page_count ?? result?.page_count ?? "--";
  const issues = summary.evidence_item_count ?? (Array.isArray(result?.evidence_items) ? result.evidence_items.length : "--");
  const scoreNode = document.querySelector("[data-pdf-metric='score']");
  const pagesNode = document.querySelector("[data-pdf-metric='pages']");
  const issuesNode = document.querySelector("[data-pdf-metric='issues']");
  if (scoreNode) scoreNode.textContent = String(score);
  if (pagesNode) pagesNode.textContent = String(pages);
  if (issuesNode) issuesNode.textContent = String(issues);
}

async function pollJob(jobId, { renderResult = false } = {}) {
  while (true) {
    const job = await getJob(jobId);
    setState({ activeJob: job });
    if (finishedStates.has(job.status)) {
      if (job.status === "failed") {
        throw new Error("处理没有完成");
      }
      if (renderResult) {
        const resultPayload = await getJobResult(jobId);
        setState({ renderResult: resultPayload.result, activeEvidenceIndex: 0 });
        renderCurrentPdfReview();
      }
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

function renderCurrentPdfReview() {
  const root = document.querySelector("[data-screen='pdf-review']");
  const result = getState().renderResult;
  if (!root || !result) return;
  renderPdfReview(root, result);
  renderPdfMetrics(result);
}

async function refreshHistory() {
  const list = document.querySelector("[data-history-list]");
  if (!list) return;
  try {
    const jobs = await listJobs({ limit: 10 });
    setState({ jobHistory: jobs });
    renderHistory(jobs);
  } catch (error) {
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
  const resultPayload = await getJobResult(jobId);
  setState({ selectedHistoryJob: resultPayload });
  if (resultPayload.operation === "render-verify") {
    setState({ renderResult: resultPayload.result, activeEvidenceIndex: 0 });
    renderCurrentPdfReview();
    showScreen("pdf-review");
    return;
  }
  if (resultPayload.operation === "apply") {
    setState({ applyResultPayload: resultPayload });
    renderResultPanel(resultPayload);
    showScreen("result");
  }
}

function bindUploads(root) {
  const docxInput = root.querySelector("#docx-input");
  const pdfInput = root.querySelector("#pdf-input");
  const chooseDocxButtons = root.querySelectorAll("[data-action='choose-docx']");

  chooseDocxButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (docxInput) {
        docxInput.click();
      }
    });
  });
  root.querySelectorAll("[data-action='choose-pdf']").forEach((button) => {
    button.addEventListener("click", () => pdfInput && pdfInput.click());
  });
  root.querySelectorAll("[data-action='create-plan']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const current = getState();
        if (!current.docxUpload) {
          setStatus("请先上传论文", "选择 docx 文件后再生成修复方案");
          return;
        }
        await createWorkbenchPlanFromUpload(current.docxUpload);
      } catch (error) {
        showError(error);
      }
    });
  });
  root.querySelectorAll("[data-action='create-apply-job']").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const current = getState();
        if (!current.docxUpload) {
          setStatus("请先上传论文", "选择 docx 文件后再生成修正结果");
          return;
        }
        setStatus("正在生成修正结果", "请稍候");
        const job = await createApplyJob(current.docxUpload.upload_id, {});
        setState({ activeJob: job });
        await pollJob(job.job_id);
        const resultPayload = await getJobResult(job.job_id);
        setState({ applyResultPayload: resultPayload });
        renderResultPanel(resultPayload);
        setStatus("修正结果已生成", "可以到结果页下载副本");
        showScreen("result");
      } catch (error) {
        showError(error);
      }
    });
  });
  root.querySelectorAll("[data-action='refresh-render-result']").forEach((button) => {
    button.addEventListener("click", () => renderCurrentPdfReview());
  });

  if (docxInput) {
    docxInput.addEventListener("change", async () => {
      const file = docxInput.files && docxInput.files[0];
      if (!file) return;
      try {
        setStatus("正在上传论文", "请稍候");
        const upload = await uploadDocx(file);
        setState({ docxUpload: upload });
        const fileNode = root.querySelector("[data-docx-file]");
        if (fileNode) fileNode.textContent = upload.file_name;
        await createWorkbenchPlanFromUpload(upload);
      } catch (error) {
        showError(error);
      }
    });
  }

  if (pdfInput) {
    pdfInput.addEventListener("change", async () => {
      const file = pdfInput.files && pdfInput.files[0];
      if (!file) return;
      try {
        const current = getState();
        if (!current.docxUpload) {
          setStatus("请先上传论文", "PDF 需要和论文原稿对应");
          showScreen("workbench");
          return;
        }
        setStatus("正在上传 PDF", "请稍候");
        const pdfUpload = await uploadPdf(file);
        const fileNode = root.querySelector("[data-pdf-file]");
        if (fileNode) fileNode.textContent = pdfUpload.file_name;
        setStatus("正在复核 PDF", "请稍候");
        const job = await createRenderReviewJob(current.docxUpload.upload_id, pdfUpload.upload_id);
        setState({ pdfUpload, activeJob: job });
        const renderState = root.querySelector("[data-render-state]");
        if (renderState) renderState.textContent = "复核中";
        await pollJob(job.job_id, { renderResult: true });
        renderCurrentPdfReview();
        if (renderState) renderState.textContent = "已完成";
        setStatus("PDF 复核完成", "可以查看页面问题");
        showScreen("pdf-review");
      } catch (error) {
        showError(error);
      }
    });
  }
}

export function initWorkbench() {
  const body = document.body;
  const screenButtons = document.querySelectorAll("[data-screen-target]");
  const themeButtons = document.querySelectorAll("[data-theme-choice]");

  screenButtons.forEach((button) => {
    button.addEventListener("click", () => showScreen(button.dataset.screenTarget));
  });

  document.addEventListener("click", (event) => {
    const downloadButton = event.target.closest("[data-download-role]");
    if (downloadButton) {
      const url = downloadButton.dataset.downloadUrl;
      if (url && !downloadButton.disabled) window.location.href = url;
      return;
    }
    const historyButton = event.target.closest("[data-history-job-id]");
    if (historyButton) {
      openHistoryJob(historyButton.dataset.historyJobId).catch(showError);
      return;
    }
    const jumpButton = event.target.closest("[data-action]");
    if (!jumpButton) return;
    const action = jumpButton.dataset.action;
    if (action === "enter-workbench") showScreen("workbench");
    if (action === "show-history") showScreen("history");
    if (action === "show-pdf-review") showScreen("pdf-review");
  });

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      body.dataset.theme = button.dataset.themeChoice;
      themeButtons.forEach((item) => item.classList.toggle("active", item === button));
    });
  });

  bindUploads(document);
  bindPdfReview(document, renderCurrentPdfReview);
}

initWorkbench();
