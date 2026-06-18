import { renderRuleLabels, severityLabels } from "./copy.js";
import { getState, setState } from "./state.js";

function labelForRule(ruleId) {
  return renderRuleLabels[ruleId] || renderRuleLabels.default;
}

function evidenceItems(result) {
  return Array.isArray(result && result.evidence_items) ? result.evidence_items : [];
}

export function renderPdfReview(root, result) {
  const items = evidenceItems(result);
  const list = root.querySelector("[data-pdf-issues]");
  const stage = root.querySelector("[data-pdf-stage]");
  const detail = root.querySelector("[data-pdf-detail]");
  if (!list || !stage || !detail) return;

  if (!items.length) {
    list.innerHTML = `<div class="empty-state"><b>没有发现需要确认的位置</b><span>可以保存复核结果</span></div>`;
    stage.innerHTML = `<div class="empty-state"><b>暂无页面问题</b><span>PDF 复核没有返回可定位项目</span></div>`;
    detail.innerHTML = `<div class="finding"><b>没有发现需要确认的位置</b><p>可以保存复核结果</p></div>`;
    return;
  }

  const state = getState();
  const activeIndex = Math.max(0, Math.min(state.activeEvidenceIndex, items.length - 1));
  const active = items[activeIndex];

  list.replaceChildren(...items.map((item, index) => createIssueButton(item, index, activeIndex)));

  renderPageStage(stage, active);
  detail.replaceChildren(
    createFinding(labelForRule(active.rule_id), active.message || "这个位置需要人工确认"),
    createFinding(severityLabels[active.severity] || severityLabels.info, active.next_action || "回到 Word 调整后重新导出 PDF"),
  );
}

function renderPageStage(stage, item) {
  if (!item.screenshot_url) {
    stage.innerHTML = `<div class="empty-state"><b>页面截图已不可用</b><span>请重新复核 PDF</span></div>`;
    return;
  }

  const frame = document.createElement("div");
  frame.className = "pdf-page-frame";
  const image = document.createElement("img");
  image.src = item.screenshot_url;
  image.alt = `第 ${item.page || "-"} 页 PDF 截图`;
  frame.append(image);
  const box = item.bbox;
  if (box) {
    const highlight = document.createElement("span");
    highlight.className = "evidence-highlight";
    highlight.style.left = `${box.x * 100}%`;
    highlight.style.top = `${box.y * 100}%`;
    highlight.style.width = `${box.w * 100}%`;
    highlight.style.height = `${box.h * 100}%`;
    frame.append(highlight);
  } else {
    const notice = document.createElement("span");
    notice.className = "page-notice";
    notice.textContent = "这一页需要整体确认";
    frame.append(notice);
  }
  stage.replaceChildren(frame);
}

function createFinding(title, message) {
  const finding = document.createElement("div");
  finding.className = "finding";
  const titleNode = document.createElement("b");
  titleNode.textContent = title;
  const messageNode = document.createElement("p");
  messageNode.textContent = message;
  finding.append(titleNode, messageNode);
  return finding;
}

function createIssueButton(item, index, activeIndex) {
  const button = document.createElement("button");
  button.className = `film-frame ${index === activeIndex ? "active" : ""}`;
  button.type = "button";
  button.dataset.issueIndex = String(index);
  const label = document.createElement("span");
  label.textContent = `第 ${item.page || "-"} 页`;
  button.append(label);
  return button;
}

export function bindPdfReview(root, rerender) {
  root.addEventListener("click", (event) => {
    const issueButton = event.target.closest("[data-issue-index]");
    if (!issueButton) return;
    setState({ activeEvidenceIndex: Number(issueButton.dataset.issueIndex) || 0 });
    rerender();
  });
}
