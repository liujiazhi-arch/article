import { bindCoverForm, coverSelectionIsValid, prepareCoverScope } from "./coverForm.js";
import { escapeHtml, scopeLabel } from "./copy.js";
import { renderFormatRadar } from "./formatRadar.js?v=20260714-module-ownership";
import { getState } from "./state.js?v=20260714-module-ownership";

function setMetric(root, name, value) {
  const node = root.querySelector(`[data-workbench-metric="${name}"]`);
  if (node) node.textContent = String(value);
}

function renderDocumentName(root) {
  const node = root.querySelector("[data-docx-file]");
  if (node) node.textContent = getState().docxUpload?.file_name || "等待上传论文";
}

function renderLedger(root, lines) {
  const ledger = root.querySelector("[data-workbench-ledger]");
  if (!ledger) return;
  ledger.innerHTML = lines.map((line) => `
    <div class="ledger-line"><em>${escapeHtml(line.time)}</em><span>${escapeHtml(line.message)}</span><strong>${escapeHtml(line.status)}</strong></div>
  `).join("");
}

function renderStructureCounts(plan, root) {
  const scopeList = Array.isArray(plan?.scopes) ? plan.scopes : [];
  const scopes = new Map(scopeList.map((scope) => [scope.id, scope]));
  root.querySelectorAll("[data-structure-scopes]").forEach((node) => {
    const counter = node.querySelector("[data-structure-count]");
    if (!counter) return;
    const ids = node.dataset.structureScopes.split(",");
    const count = ids.reduce(
      (total, id) => total + Number(scopes.get(id)?.failed_count || 0),
      0,
    );
    counter.textContent = plan ? String(count) : "--";
  });
}

export function setFlowStage(stage, root = document) {
  root.querySelectorAll("[data-flow-stage]").forEach((step) => {
    step.classList.toggle("active", step.dataset.flowStage === stage);
  });
}

export function selectedScopeIds(root = document) {
  return Array.from(
    root.querySelectorAll("[data-scope-option] input:checked:not(:disabled)"),
    (input) => input.value,
  );
}

export function updateApplyButtons(root = document) {
  const current = getState();
  const ready = Boolean(current.docxUpload && current.workbenchPlan);
  const canRun = ready && selectedScopeIds(root).length > 0
    && coverSelectionIsValid(root) && !current.applyRunning;
  root.querySelectorAll("[data-action='create-apply-job']").forEach((button) => {
    button.disabled = !canRun;
    const label = button.querySelector("b");
    if (label) label.textContent = current.applyRunning ? "正在生成" : "生成结果";
  });
}

function scopeState(scope, plan) {
  const available = Number(scope?.autofixable_count || 0) > 0;
  const requiresReview = Number(scope?.manual_review_count || 0) > 0
    || Number(scope?.unsupported_count || 0) > 0
    || Number(scope?.unknown_count || 0) > 0;
  if (available) return requiresReview ? "已选 仍需确认" : "已选择";
  if (requiresReview) return "需人工确认";
  return plan ? "无需处理" : "等待方案";
}

function renderScopeOption(option, scopes, plan, root) {
  if (option.dataset.scopeOption === "cover") {
    prepareCoverScope(root);
    return;
  }
  const scope = scopes.get(option.dataset.scopeOption);
  const available = Number(scope?.autofixable_count || 0) > 0;
  const input = option.querySelector("input");
  if (input) {
    input.disabled = !available;
    input.checked = available;
    input.dataset.requiresReview = String(scopeState(scope, plan).includes("确认"));
  }
  const stateNode = option.querySelector("[data-scope-state]");
  if (stateNode) stateNode.textContent = scopeState(scope, plan);
}

function renderScopeOptions(plan, root) {
  const scopes = new Map((Array.isArray(plan?.scopes) ? plan.scopes : [])
    .map((scope) => [scope.id, scope]));
  root.querySelectorAll("[data-scope-option]").forEach((option) => {
    renderScopeOption(option, scopes, plan, root);
  });
  updateApplyButtons(root);
}

function bindScopeControls(root) {
  root.querySelectorAll("[data-scope-option] input").forEach((input) => {
    input.addEventListener("change", () => {
      const stateNode = input.closest("[data-scope-option]").querySelector("[data-scope-state]");
      stateNode.textContent = input.checked ? "已选择" : "未选择";
      if (input.checked && input.dataset.requiresReview === "true") {
        stateNode.textContent = "已选 仍需确认";
      }
      updateApplyButtons(root);
    });
  });
}

export function bindWorkflowControls(root) {
  bindScopeControls(root);
  bindCoverForm(root, () => updateApplyButtons(root));
}

export function selectSuggestedScope(root, scopeId, fixMode = "manual") {
  const option = Array.from(root.querySelectorAll("[data-scope-option]"))
    .find((item) => item.dataset.scopeOption === scopeId);
  const input = option?.querySelector("input");
  const label = scopeLabel(scopeId);
  if (!input || input.disabled) {
    const title = fixMode === "auto" ? `${label}范围暂不能自动修复` : `${label}范围需要人工确认`;
    return { title, message: "请按页面提示在 Word 或 WPS 中处理" };
  }
  input.checked = true;
  const stateNode = option.querySelector("[data-scope-state]");
  if (stateNode) {
    stateNode.textContent = input.dataset.requiresReview === "true" ? "已选 仍需确认" : "已选择";
  }
  updateApplyButtons(root);
  const title = fixMode === "auto" ? `已选择${label}范围` : `已定位${label}范围`;
  const message = fixMode === "auto" ? "可以检查后生成修正结果" : "这个问题仍需在 Word 或 WPS 中确认";
  return { title, message };
}

function reviewLine(metrics, manualConfirmation) {
  if (metrics == null) {
    return { time: "刚刚", message: "方案统计暂不可用  请重新生成方案", status: "提示" };
  }
  if (metrics.unknown > 0) {
    return { time: "刚刚", message: `${metrics.unknown} 项暂未归类  请查看格式雷达`, status: "待归类" };
  }
  const message = manualConfirmation > 0
    ? `${manualConfirmation} 项需要你确认`
    : "暂未发现需要人工确认的项目";
  return { time: "刚刚", message, status: manualConfirmation > 0 ? "需确认" : "完成" };
}

function renderReadyPlan(plan, root) {
  const radar = renderFormatRadar({ state: "ready", plan }, root);
  const metrics = radar.metrics.scopeCount > 0
    && !Object.values(radar.metrics).some((value) => value == null)
    ? radar.metrics
    : null;
  const completePlan = metrics && Array.isArray(plan?.scopes) ? plan : null;
  const autofixable = metrics?.autofixableScopes;
  const manualConfirmation = metrics ? metrics.manualReview + metrics.unsupported : null;
  renderStructureCounts(completePlan, root);
  setFlowStage("plan", root);
  setMetric(root, "autofixable-scopes", autofixable ?? "--");
  setMetric(root, "manual-confirmation", manualConfirmation ?? "--");
  setMetric(root, "output-kind", "修复副本");
  renderScopeOptions(completePlan, root);
  renderLedger(root, [
    { time: "刚刚", message: "论文已上传并完成初步检查", status: "完成" },
    { time: "刚刚", message: metrics ? `发现 ${autofixable} 个可修复范围` : "可修复范围暂不可用", status: metrics ? "完成" : "提示" },
    reviewLine(metrics, manualConfirmation),
  ]);
}

function renderPendingPlan(fileName, stage, root) {
  renderScopeOptions(null, root);
  renderFormatRadar({ state: "loading" }, root);
  renderStructureCounts(null, root);
  setFlowStage(stage, root);
  setMetric(root, "autofixable-scopes", "生成中");
  setMetric(root, "manual-confirmation", "生成中");
  setMetric(root, "output-kind", "修复副本");
  renderLedger(root, [
    { time: "刚刚", message: `${fileName || "论文"} 已上传`, status: "完成" },
    { time: "刚刚", message: "正在生成真实修复方案", status: "处理中" },
    { time: "等待", message: "方案完成后会更新可修复范围", status: "等待" },
  ]);
}

function renderUnavailablePlan(message, root) {
  renderScopeOptions(null, root);
  renderFormatRadar({ state: "error" }, root);
  renderStructureCounts(null, root);
  setFlowStage("plan", root);
  setMetric(root, "autofixable-scopes", "待重试");
  setMetric(root, "manual-confirmation", "待重试");
  renderLedger(root, [
    { time: "刚刚", message: "论文已上传", status: "完成" },
    { time: "刚刚", message: message || "修复方案暂时不可用", status: "提示" },
    { time: "等待", message: "请重新生成方案后选择修复范围", status: "待处理" },
  ]);
}

export function renderWorkflowPlan({ state, plan, fileName, stage = "upload", message } = {}, root = document) {
  renderDocumentName(root);
  if (state === "ready") return renderReadyPlan(plan, root);
  if (state === "loading") return renderPendingPlan(fileName, stage, root);
  if (state === "error") return renderUnavailablePlan(message, root);
  renderScopeOptions(null, root);
  renderFormatRadar({ state: "idle" }, root);
  renderStructureCounts(null, root);
}
