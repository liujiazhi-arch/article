import {
  createApplyJob,
  createRenderReviewJob,
  createUploadPlan,
  getJobResult,
  listJobs,
  uploadDocx,
  uploadPdf,
  waitForJob,
} from "./api.js";
import { getState, setState } from "./state.js";
import {
  bindPdfReview,
  isPdfMatchConfirmed,
  pdfReviewCompletionStatus,
  renderPdfReview,
  renderPdfReviewContext,
  resetPdfReview,
} from "./pdfReview.js";
import { collectCoverFields, resetCoverForm } from "./coverForm.js";
import { renderHistory, renderHistoryError } from "./historyView.js";
import { renderResult } from "./resultView.js";
import {
  bindWorkflowControls,
  renderWorkflowPlan,
  selectSuggestedScope,
  selectedScopeIds,
  setFlowStage,
  updateApplyButtons,
} from "./workflowView.js";
let historyRequestEpoch = 0;
let resultOwnerEpoch = 0;

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

function blockPdfUntilFreshDocx(root) {
  if (getState().pdfReviewRequiresFreshDocx !== true) return false;
  renderPdfReviewContext(root, { confirmationChecked: false });
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
    renderResult: null,
    renderResultPayload: null,
    pdfReviewEpoch: nextEpoch,
  });
  resetPdfReview(root, { renderState, conclusion, title, message });
  return nextEpoch;
}

function resetDocumentState(root) {
  const nextEpoch = Number(getState().documentEpoch || 0) + 1;
  setState({
    documentEpoch: nextEpoch,
    docxUpload: null,
    workbenchPlan: null,
    applyRunning: false,
  });
  renderWorkflowPlan({ state: "idle" }, root);
  renderResult(null, root);
  resetPdfReviewState(root);
  renderPdfReviewContext(root, { documentName: "等待上传论文" });
  return nextEpoch;
}

function showError(error) {
  setStatus(error.message || "操作没有完成", error.nextAction || "请检查文件后重试");
}

async function createWorkbenchPlanFromUpload(upload, documentEpoch = null) {
  renderWorkflowPlan({ state: "loading", fileName: upload.file_name, stage: "plan" });
  setStatus("论文已上传", "正在生成修复方案");
  try {
    const plan = await createUploadPlan(upload.upload_id);
    if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
    setState({ workbenchPlan: plan });
    renderWorkflowPlan({ state: "ready", plan });
    setStatus("修复方案已生成", "可以生成修正结果");
    return plan;
  } catch (planError) {
    if (documentEpoch && getState().documentEpoch !== documentEpoch) return null;
    renderWorkflowPlan({ state: "error", message: planError.nextAction || "请稍后重试生成方案" });
    setStatus("论文已上传", "修复方案暂时不可用");
    throw planError;
  }
}

function renderCurrentPdfReview() {
  const root = document.querySelector("[data-screen='pdf-review']");
  const current = getState();
  const result = current.renderResult;
  if (!root || !result) return;
  renderPdfReview(root, result, current.renderResultPayload);
}
async function refreshHistory() {
  const list = document.querySelector("[data-history-list]");
  if (!list) return;
  const requestEpoch = historyRequestEpoch;
  try {
    const jobs = await listJobs({ limit: 10 });
    if (requestEpoch !== historyRequestEpoch) return;
    renderHistory(jobs);
  } catch (error) {
    if (requestEpoch !== historyRequestEpoch) return;
    renderHistoryError(error);
  }
}

async function openHistoryJob(jobId) {
  const requestEpoch = ++historyRequestEpoch;
  const ownerEpoch = ++resultOwnerEpoch;
  const { documentEpoch, pdfReviewEpoch } = getState();
  const resultPayload = await getJobResult(jobId);
  const current = getState();
  if (
    requestEpoch !== historyRequestEpoch
    || ownerEpoch !== resultOwnerEpoch
    || current.documentEpoch !== documentEpoch
    || current.pdfReviewEpoch !== pdfReviewEpoch
  ) return;
  if (resultPayload.operation === "render-verify") {
    const summary = resultPayload.summary || {};
    setState({
      renderResult: resultPayload.result,
      renderResultPayload: resultPayload,
      pdfReviewEpoch: Number(current.pdfReviewEpoch || 0) + 1,
      pdfReviewRequiresFreshDocx: true,
    });
    renderPdfReviewContext(document, {
      documentName: summary.document_name || "历史论文",
      pdfName: summary.pdf_name || "历史 PDF",
      status: "已完成",
      confirmationChecked: false,
    });
    renderCurrentPdfReview();
    showScreen("pdf-review");
    return;
  }
  if (resultPayload.operation === "apply") {
    resetPdfReviewState(document);
    renderResult(resultPayload);
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

function buildApplyRequest(root, current) {
  if (!current.docxUpload) {
    setStatus("请先上传论文", "选择 docx 文件后再生成修正结果");
    return null;
  }
  if (!current.workbenchPlan) {
    setStatus("请先生成修复方案", "方案完成后再生成修正结果");
    return null;
  }
  const scopes = selectedScopeIds(root);
  if (!scopes.length) {
    setStatus("请选择修复范围", "先生成方案 再勾选需要处理的范围");
    return null;
  }
  const coverFields = scopes.includes("cover") ? collectCoverFields(root) : null;
  if (scopes.includes("cover") && !coverFields) {
    setStatus("请填完整封面信息", "填写六项信息后再生成修正结果");
    return null;
  }
  return { scopes, ...(coverFields ? { cover_fields: coverFields } : {}) };
}

function applyIsCurrent(documentEpoch, ownerEpoch) {
  return getState().documentEpoch === documentEpoch && resultOwnerEpoch === ownerEpoch;
}

function showApplyResult(root, resultPayload) {
  resetPdfReviewState(root, {
    title: "先上传修复稿",
    message: "上传刚下载的修复稿后再复核 PDF",
  });
  setState({ pdfReviewRequiresFreshDocx: true });
  renderResult(resultPayload, root);
  setFlowStage("download", root);
  setStatus("修正结果已生成", "可以到结果页下载副本");
  showScreen("result");
}

async function runApply(root, current, request) {
  setState({ applyRunning: true });
  const documentEpoch = current.documentEpoch;
  const ownerEpoch = resultOwnerEpoch;
  setFlowStage("apply", root);
  updateApplyButtons(root);
  try {
    setStatus("正在生成修正结果", "请稍候");
    const job = await createApplyJob(current.docxUpload.upload_id, request);
    if (!applyIsCurrent(documentEpoch, ownerEpoch)) return;
    const completed = await waitForJob(job.job_id, () => applyIsCurrent(documentEpoch, ownerEpoch));
    if (!completed) return;
    setFlowStage("verify", root);
    const resultPayload = await getJobResult(job.job_id);
    if (!applyIsCurrent(documentEpoch, ownerEpoch)) return;
    showApplyResult(root, resultPayload);
  } catch (error) {
    if (!applyIsCurrent(documentEpoch, ownerEpoch)) return;
    showError(error);
  } finally {
    if (getState().documentEpoch === documentEpoch) {
      setState({ applyRunning: false });
      updateApplyButtons(root);
    }
  }
}

async function handleCreateApplyJob(root) {
  const current = getState();
  if (current.applyRunning) return;
  const request = buildApplyRequest(root, current);
  if (request) await runApply(root, current, request);
}

async function handleDocxUpload(root, docxInput) {
  const file = docxInput.files && docxInput.files[0];
  if (!file) return;
  const hadCurrentDocument = Boolean(getState().docxUpload);
  const documentEpoch = resetDocumentState(root);
  renderWorkflowPlan({ state: "loading", fileName: file.name }, root);
  try {
    setStatus("正在上传论文", "请稍候");
    const upload = await uploadDocx(file);
    if (getState().documentEpoch !== documentEpoch) return;
    setState({ docxUpload: upload, pdfReviewRequiresFreshDocx: false });
    if (hadCurrentDocument) resetCoverForm(root);
    renderPdfReviewContext(root, { documentName: upload.file_name });
    await createWorkbenchPlanFromUpload(upload, documentEpoch);
  } catch (error) {
    if (getState().documentEpoch !== documentEpoch) return;
    showError(error);
  } finally {
    docxInput.value = "";
  }
}

function beginPdfReview(root, pdfInput) {
  const file = pdfInput.files && pdfInput.files[0];
  if (!file) return null;
  const current = getState();
  if (blockPdfUntilFreshDocx(root)) {
    pdfInput.value = "";
    return null;
  }
  if (!current.docxUpload) {
    setStatus("请先上传论文", "PDF 需要和当前论文对应");
    showScreen("workbench");
    pdfInput.value = "";
    return null;
  }
  if (!isPdfMatchConfirmed(root)) {
    resetPdfReviewState(root);
    setStatus("请确认 PDF 来源", "勾选确认后再选择 PDF");
    pdfInput.value = "";
    return null;
  }
  const pdfReviewEpoch = resetPdfReviewState(root, {
    renderState: "复核中",
    title: "正在复核 PDF",
    message: "完成后显示页面问题",
  });
  return {
    file,
    docxUploadId: current.docxUpload.upload_id,
    documentEpoch: current.documentEpoch,
    pdfReviewEpoch,
  };
}

function pdfReviewIsCurrent(context) {
  const current = getState();
  return current.documentEpoch === context.documentEpoch
    && current.pdfReviewEpoch === context.pdfReviewEpoch
    && current.docxUpload?.upload_id === context.docxUploadId;
}

async function runPdfReview(root, context) {
  try {
    setStatus("正在上传 PDF", "请稍候");
    const pdfUpload = await uploadPdf(context.file);
    if (!pdfReviewIsCurrent(context)) return;
    renderPdfReviewContext(root, { pdfName: pdfUpload.file_name });
    setStatus("正在复核 PDF", "请稍候");
    const job = await createRenderReviewJob(context.docxUploadId, pdfUpload.upload_id, true);
    if (!pdfReviewIsCurrent(context)) return;
    const completed = await waitForJob(job.job_id, () => pdfReviewIsCurrent(context));
    if (!completed) return;
    const resultPayload = await getJobResult(job.job_id);
    if (!pdfReviewIsCurrent(context)) return;
    setState({ renderResult: resultPayload.result, renderResultPayload: resultPayload });
    renderCurrentPdfReview();
    renderPdfReviewContext(root, { status: "已完成" });
    const completionStatus = pdfReviewCompletionStatus(resultPayload.result);
    setStatus(completionStatus.title, completionStatus.message);
    showScreen("pdf-review");
  } catch (error) {
    if (!pdfReviewIsCurrent(context)) return;
    resetPdfReviewState(root, {
      renderState: "未完成",
      conclusion: "待确认",
      title: "本次复核未完成",
      message: "请重新上传对应 PDF",
    });
    showError(error);
  }
}

async function handlePdfUpload(root, pdfInput) {
  const context = beginPdfReview(root, pdfInput);
  if (!context) return;
  try {
    await runPdfReview(root, context);
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
  bindWorkflowControls(root);
  if (docxInput) docxInput.addEventListener("change", () => handleDocxUpload(root, docxInput));
  if (pdfInput) pdfInput.addEventListener("change", () => handlePdfUpload(root, pdfInput));
}

function handleArtifactDownload(button) {
  const url = button.dataset.downloadUrl;
  if (!url || button.disabled) return;
  if (button.dataset.downloadRole === "toc-output") {
    setState({ pdfReviewRequiresFreshDocx: true });
    setStatus("请重新导出 PDF", "用 Word 或 WPS 打开静态目录版 重新导出 PDF 并再次复核");
  }
  window.location.href = url;
}

function handlePageAction(button, root) {
  const action = button.dataset.action;
  if (action === "enter-workbench") showScreen("workbench");
  if (action === "show-history") showScreen("history");
  if (action === "show-pdf-review") showScreen("pdf-review");
  if (action !== "repair-scope") return;
  showScreen("workbench");
  if (getState().pdfReviewRequiresFreshDocx === true) {
    setStatus("请先上传对应论文", "历史复核结果不会用于当前论文");
    return;
  }
  const status = selectSuggestedScope(root, button.dataset.scope, button.dataset.fixMode);
  setStatus(status.title, status.message);
}

function bindDocumentActions(root) {
  root.addEventListener("click", (event) => {
    const downloadButton = event.target.closest("[data-download-role]");
    if (downloadButton) {
      handleArtifactDownload(downloadButton);
      return;
    }
    const historyButton = event.target.closest("[data-history-job-id]");
    if (historyButton) {
      openHistoryJob(historyButton.dataset.historyJobId).catch(showError);
      return;
    }
    const actionButton = event.target.closest("[data-action]");
    if (actionButton) handlePageAction(actionButton, root);
  });
}

function initWorkbench() {
  const body = document.body;
  const screenButtons = document.querySelectorAll("[data-screen-target]");
  const themeButtons = document.querySelectorAll("[data-theme-choice]");

  screenButtons.forEach((button) => {
    button.addEventListener("click", () => showScreen(button.dataset.screenTarget));
  });

  bindDocumentActions(document);

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      body.dataset.theme = button.dataset.themeChoice;
      themeButtons.forEach((item) => item.classList.toggle("active", item === button));
    });
  });

  renderResult(null);
  resetPdfReviewState(document);
  bindUploads(document);
  bindPdfReview(document, renderCurrentPdfReview);
}

initWorkbench();
