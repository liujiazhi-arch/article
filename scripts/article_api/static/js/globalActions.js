import { getState, setState } from "./state.js";

function handleDownload(button, setStatus) {
  const url = button.dataset.downloadUrl;
  if (!url || button.disabled) return;
  if (button.dataset.downloadRole === "toc-output") {
    setState({ pdfReviewRequiresFreshDocx: true });
    setStatus("请重新导出 PDF", "用 Word 或 WPS 打开静态目录版 重新导出 PDF 并再次复核");
  }
  window.location.href = url;
}

function selectSuggestedScope(button, actions, root) {
  const scopeId = button.dataset.scope;
  const fixMode = button.dataset.fixMode || "manual";
  const option = Array.from(root.querySelectorAll("[data-scope-option]"))
    .find((item) => item.dataset.scopeOption === scopeId);
  const input = option?.querySelector("input");
  const label = actions.scopeLabel(scopeId);
  if (!input || input.disabled) {
    const title = fixMode === "auto" ? `${label}范围暂不能自动修复` : `${label}范围需要人工确认`;
    actions.setStatus(title, "请按页面提示在 Word 或 WPS 中处理");
    return;
  }
  input.checked = true;
  const stateNode = option.querySelector("[data-scope-state]");
  if (stateNode) stateNode.textContent = input.dataset.requiresReview === "true" ? "已选 仍需确认" : "已选择";
  actions.updateApplyButtons(root);
  if (fixMode === "auto") actions.setStatus(`已选择${label}范围`, "可以检查后生成修正结果");
  else actions.setStatus(`已定位${label}范围`, "这个问题仍需在 Word 或 WPS 中确认");
}

function handleAction(button, actions, root) {
  const action = button.dataset.action;
  if (action === "enter-workbench") actions.showScreen("workbench");
  if (action === "repair-scope") {
    actions.showScreen("workbench");
    if (getState().pdfReviewRequiresFreshDocx === true) {
      actions.setStatus("请先上传对应论文", "历史复核结果不会用于当前论文");
      return;
    }
    selectSuggestedScope(button, actions, root);
  }
  if (action === "show-history") actions.showScreen("history");
  if (action === "show-pdf-review") actions.showScreen("pdf-review");
}

export function bindGlobalActions(root, actions) {
  root.addEventListener("click", (event) => {
    const downloadButton = event.target.closest("[data-download-role]");
    if (downloadButton) {
      handleDownload(downloadButton, actions.setStatus);
      return;
    }
    const historyButton = event.target.closest("[data-history-job-id]");
    if (historyButton) {
      actions.openHistoryJob(historyButton.dataset.historyJobId).catch(actions.showError);
      return;
    }
    const actionButton = event.target.closest("[data-action]");
    if (actionButton) handleAction(actionButton, actions, root);
  });
}
