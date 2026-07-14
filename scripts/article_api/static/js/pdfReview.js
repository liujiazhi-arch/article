import { renderEvidenceStatusLabels, renderRuleLabels, severityLabels } from "./copy.js";
import { downloadJobArtifactUrl } from "./api.js";

const blockingEvidenceStatuses = new Set([
  "structure-not-ready",
  "blocked-by-wild-doc",
  "unsupported-evidence",
]);
let activeEvidenceIndex = 0;
let activeEvidenceResult = null;

function labelForRule(ruleId) {
  return renderRuleLabels[ruleId] || renderRuleLabels.default;
}

function evidenceItems(result) {
  return Array.isArray(result && result.evidence_items) ? result.evidence_items : [];
}

function resultField(result, name) {
  return result?.summary?.[name] ?? result?.[name];
}

export function isPdfEvidenceUsable(result) {
  return resultField(result, "layout_decision_eligible") === true;
}

export function pdfReviewCompletionStatus(result) {
  if (!isPdfEvidenceUsable(result)) {
    return { title: "PDF 版本待确认", message: "请重新上传当前论文导出的 PDF" };
  }
  if (resultField(result, "render_evidence_status") === "render-review-required"
      && evidenceItems(result).length === 0) {
    return { title: "PDF 仍需人工复核", message: "没有返回问题位置 请继续检查页面和结构" };
  }
  if (resultField(result, "render_evidence_status") === "render-evidence-ready"
      && evidenceItems(result).length === 0) {
    return { title: "PDF 复核完成", message: "没有发现需要确认的位置" };
  }
  return { title: "PDF 复核完成", message: "可以查看页面问题" };
}

function tocMappingMessage(finalization, fallback = "目录与正文还没有完整对应") {
  const entryCount = finalization?.entry_count;
  const mappedCount = finalization?.mapped_count;
  if (entryCount == null || mappedCount == null) return fallback;
  if (!Number.isFinite(Number(entryCount)) || !Number.isFinite(Number(mappedCount))) {
    return fallback;
  }
  return `已对应 ${Number(mappedCount)} 项 共 ${Number(entryCount)} 项`;
}

function tocFinalizationCopy(finalization, downloadAvailable) {
  if (!finalization) return null;
  const status = finalization.available ? "generated" : finalization.status;
  if (status === "generated" && !downloadAvailable) {
    return { title: "目录文件暂不可下载", message: "静态目录版没有可下载文件", next: "请重新复核 PDF" };
  }
  if (status === "generated") {
    return { title: "静态目录版已生成", message: tocMappingMessage(finalization, "目录页码已经写入新副本"), next: finalization.next_action || "下载后重新导出 PDF 并再次复核" };
  }
  if (status === "incomplete") {
    return { title: "静态目录版未生成", message: tocMappingMessage(finalization), next: finalization.next_action || "请在 Word 或 WPS 中人工确认目录" };
  }
  if (status === "blocked") {
    return { title: "暂不能生成静态目录版", message: "PDF 与当前论文需要先确认", next: finalization.next_action || "确认后重新复核 PDF" };
  }
  if (status === "unavailable") {
    return { title: "静态目录暂不可生成", message: "PDF 复核结果仍可查看", next: "请先查看页面问题" };
  }
  if (status === "not-needed") {
    return { title: "无需生成静态目录版", message: "当前 PDF 没有发现目录页码问题", next: finalization.next_action || "继续查看其他页面问题" };
  }
  if (status === "not-requested") {
    return { title: "本次未生成静态目录版", message: "本次只完成 PDF 复核", next: finalization.next_action || "需要时重新复核 PDF" };
  }
  return { title: "静态目录版未生成", message: "本次目录处理没有完成", next: "请在 Word 或 WPS 中人工确认目录" };
}

function isPdfReviewReady(result) {
  return resultField(result, "render_evidence_status") === "render-evidence-ready"
    && resultField(result, "layout_decision_eligible") === true;
}

function createEmptyState(title, message) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const titleNode = document.createElement("b");
  titleNode.textContent = title;
  const messageNode = document.createElement("span");
  messageNode.textContent = message;
  empty.append(titleNode, messageNode);
  return empty;
}

export function isPdfMatchConfirmed(root = document) {
  return root.querySelector("#pdf-match-confirmation")?.checked === true;
}

export function renderPdfReviewContext(root, {
  documentName,
  pdfName,
  status,
  confirmationChecked,
} = {}) {
  const values = [
    ["[data-pdf-docx-file]", documentName],
    ["[data-pdf-file]", pdfName],
    ["[data-render-state]", status],
  ];
  values.forEach(([selector, value]) => {
    const node = root.querySelector(selector);
    if (node && value !== undefined) node.textContent = value;
  });
  const confirmation = root.querySelector("#pdf-match-confirmation");
  if (confirmation && confirmationChecked !== undefined) {
    confirmation.checked = confirmationChecked;
  }
}

function clearPdfReview(root, { title = "等待 PDF 复核", message = "上传对应 PDF 后查看页面问题" } = {}) {
  const list = root.querySelector("[data-pdf-issues]");
  const stage = root.querySelector("[data-pdf-stage]");
  const detail = root.querySelector("[data-pdf-detail]");
  if (list) list.replaceChildren(createEmptyState(title, ""));
  if (stage) stage.replaceChildren(createEmptyState(title, message));
  if (detail) detail.replaceChildren(createFinding("下一步", message));
  renderTocOutputAction(root, null, null);
}

function pdfConclusion(result, issueCount) {
  const evidenceStatus = resultField(result, "render_evidence_status");
  if (blockingEvidenceStatuses.has(evidenceStatus)) {
    return renderEvidenceStatusLabels[evidenceStatus] || "待确认";
  }
  if (Number(issueCount) > 0) return "需复核";
  if (evidenceStatus === "render-evidence-ready") {
    return isPdfReviewReady(result) ? "无异常" : "待确认";
  }
  return renderEvidenceStatusLabels[evidenceStatus] || "待确认";
}

function setPdfMetric(root, name, value) {
  const selector = `[data-pdf-metric="${name}"]`;
  const node = root.querySelector(selector) || (root === document ? null : document.querySelector(selector));
  if (node) node.textContent = String(value);
}

export function resetPdfReview(root, {
  renderState = "待上传",
  conclusion = "待确认",
  title = "等待 PDF 复核",
  message = "上传对应 PDF 后查看页面问题",
} = {}) {
  activeEvidenceIndex = 0;
  activeEvidenceResult = null;
  renderPdfReviewContext(root, {
    pdfName: "等待上传对应 PDF",
    status: renderState,
    confirmationChecked: false,
  });
  setPdfMetric(root, "conclusion", conclusion);
  setPdfMetric(root, "pages", "--");
  setPdfMetric(root, "issues", "--");
  clearPdfReview(root, { title, message });
}

function renderPdfMetrics(root, result) {
  const items = Array.isArray(result?.evidence_items) ? result.evidence_items : null;
  const pages = resultField(result, "page_count") ?? "--";
  const issues = resultField(result, "evidence_item_count")
    ?? (items ? items.length : null)
    ?? resultField(result, "actionable_finding_count")
    ?? result?.render_summary?.actionable_finding_count
    ?? (items ? items.length : "--");
  setPdfMetric(root, "conclusion", pdfConclusion(result, issues));
  setPdfMetric(root, "pages", pages);
  setPdfMetric(root, "issues", issues);
}

export function renderPdfReview(root, result, payload = null) {
  const items = evidenceItems(result);
  const evidenceUsable = isPdfEvidenceUsable(result);
  if (result !== activeEvidenceResult) {
    activeEvidenceIndex = 0;
    activeEvidenceResult = result;
  }
  const list = root.querySelector("[data-pdf-issues]");
  const stage = root.querySelector("[data-pdf-stage]");
  const detail = root.querySelector("[data-pdf-detail]");
  if (evidenceUsable) renderPdfMetrics(root, result);
  else {
    setPdfMetric(root, "conclusion", pdfConclusion(result, 0));
    setPdfMetric(root, "pages", "--");
    setPdfMetric(root, "issues", "--");
  }
  renderTocOutputAction(root, result, payload);
  if (!list || !stage || !detail) return;

  if (!evidenceUsable) {
    list.replaceChildren(createEmptyState("版本对应关系待确认", "请重新上传当前论文导出的 PDF"));
    stage.replaceChildren(createEmptyState("暂不展示页面证据", "当前 PDF 不能用于这篇论文的版式判断"));
    detail.replaceChildren(createFinding("下一步", "重新导出当前论文 PDF 后再复核"));
    return;
  }

  if (!items.length) {
    if (resultField(result, "render_evidence_status") === "render-review-required") {
      list.innerHTML = `<div class="empty-state"><b>没有返回可定位的位置</b><span>仍需继续人工复核</span></div>`;
      stage.innerHTML = `<div class="empty-state"><b>不能确认页面没有问题</b><span>本次没有可展示的页面标注</span></div>`;
      detail.innerHTML = `<div class="finding"><b>继续人工复核</b><p>请结合页面和结构检查完成确认</p></div>`;
      return;
    }
    list.innerHTML = `<div class="empty-state"><b>没有发现需要确认的位置</b><span>可以保存复核结果</span></div>`;
    stage.innerHTML = `<div class="empty-state"><b>暂无页面问题</b><span>PDF 复核没有返回可定位项目</span></div>`;
    detail.innerHTML = `<div class="finding"><b>没有发现需要确认的位置</b><p>可以保存复核结果</p></div>`;
    return;
  }

  const activeIndex = Math.max(0, Math.min(activeEvidenceIndex, items.length - 1));
  const active = items[activeIndex];

  list.replaceChildren(...items.map((item, index) => createIssueButton(item, index, activeIndex)));

  renderPageStage(stage, active);
  const details = [
    createFinding(labelForRule(active.rule_id), active.message || "这个位置需要人工确认"),
    createFinding(severityLabels[active.severity] || severityLabels.info, active.next_action || "回到 Word 调整后重新导出 PDF"),
  ];
  const repairAction = createRepairAction(active);
  if (repairAction) details.push(repairAction);
  detail.replaceChildren(...details);
}

function renderTocOutputAction(root, result, payload) {
  const action = root.querySelector("[data-toc-output-action]");
  const title = root.querySelector("[data-toc-output-title]");
  const message = root.querySelector("[data-toc-output-message]");
  const nextAction = root.querySelector("[data-toc-output-next-action]");
  const button = root.querySelector("[data-download-role='toc-output']");
  const artifact = (Array.isArray(payload?.artifacts) ? payload.artifacts : [])
    .find((item) => item.role === "toc-output");
  const finalization = result?.toc_finalization;
  const artifactAvailable = Boolean(payload?.job_id && artifact?.available);
  const available = Boolean(finalization?.available && artifactAvailable);
  const copy = tocFinalizationCopy(finalization, available);
  if (action) action.hidden = !copy;
  if (title && copy) title.textContent = copy.title;
  if (message && copy) message.textContent = copy.message;
  if (nextAction && copy) nextAction.textContent = copy.next;
  if (!button) return;
  button.disabled = !available;
  if (available) button.dataset.downloadUrl = downloadJobArtifactUrl(payload.job_id, "toc-output");
  else delete button.dataset.downloadUrl;
}

function validBbox(box) {
  if (!box || ![box.x, box.y, box.w, box.h].every(Number.isFinite)) return false;
  if (box.x < 0 || box.y < 0 || box.w <= 0 || box.h <= 0) return false;
  return box.x + box.w <= 1.000001 && box.y + box.h <= 1.000001;
}

function evidenceBoxes(item) {
  const spanBoxes = (Array.isArray(item?.text_spans) ? item.text_spans : [])
    .map((span) => span?.bbox)
    .filter(validBbox);
  if (spanBoxes.length) return spanBoxes;
  return validBbox(item?.bbox) ? [item.bbox] : [];
}

function enclosingBox(boxes) {
  const left = Math.min(...boxes.map((box) => box.x));
  const top = Math.min(...boxes.map((box) => box.y));
  const right = Math.max(...boxes.map((box) => box.x + box.w));
  const bottom = Math.max(...boxes.map((box) => box.y + box.h));
  return { x: left, y: top, w: right - left, h: bottom - top };
}

function createPageFrame(stage, view, item) {
  const frame = document.createElement("div");
  frame.className = "pdf-page-frame";
  const image = document.createElement("img");
  image.src = item.screenshot_url;
  image.alt = `第 ${item.page || "-"} 页 PDF 截图`;
  image.addEventListener("load", () => {
    if (image.naturalWidth > 0 && image.naturalHeight > 0) {
      frame.style.setProperty("--pdf-page-aspect", `${image.naturalWidth} / ${image.naturalHeight}`);
    }
  }, { once: true });
  image.addEventListener("error", () => {
    if (stage.firstElementChild !== view) return;
    stage.replaceChildren(createEmptyState("页面截图已不可用", "请重新复核 PDF"));
  }, { once: true });
  frame.append(image);
  return frame;
}

function createEvidenceHighlight(box, labelled) {
  const highlight = document.createElement("span");
  highlight.className = "evidence-highlight";
  if (labelled) highlight.dataset.label = "问题位置";
  highlight.ariaHidden = "true";
  highlight.style.left = `${box.x * 100}%`;
  highlight.style.top = `${box.y * 100}%`;
  highlight.style.width = `${box.w * 100}%`;
  highlight.style.height = `${box.h * 100}%`;
  return highlight;
}

function createEvidenceZoom(item, boxes) {
  const box = enclosingBox(boxes);
  const zoom = document.createElement("div");
  zoom.className = "pdf-evidence-zoom";
  const title = document.createElement("b");
  title.textContent = boxes.length > 1 ? `问题片段 ${boxes.length} 处` : "问题片段";
  const crop = document.createElement("div");
  crop.className = "pdf-evidence-crop";
  crop.style.backgroundImage = `url(${JSON.stringify(item.screenshot_url)})`;
  crop.style.backgroundPosition = `${(box.x + box.w / 2) * 100}% ${(box.y + box.h / 2) * 100}%`;
  crop.style.backgroundSize = `${Math.min(900, Math.max(240, Math.round(60 / box.w)))}% auto`;
  crop.role = "img";
  crop.ariaLabel = `第 ${item.page || "-"} 页 ${labelForRule(item.rule_id)} 问题片段`;
  const caption = document.createElement("span");
  caption.textContent = `第 ${item.page || "-"} 页 ${labelForRule(item.rule_id)}`;
  zoom.append(title, crop, caption);
  return zoom;
}

function fitEvidenceZoom(crop, image, box) {
  const rect = crop.getBoundingClientRect();
  const pageAspect = image.naturalWidth / image.naturalHeight;
  if (!rect.width || !rect.height || !Number.isFinite(pageAspect) || pageAspect <= 0) return;
  const preferredScale = Math.min(900, Math.max(240, 60 / box.w));
  const heightLimit = 70 * rect.height * pageAspect / (rect.width * box.h);
  const scale = Math.max(1, Math.floor(Math.min(preferredScale, heightLimit)));
  const backgroundWidth = rect.width * scale / 100;
  const backgroundHeight = backgroundWidth / pageAspect;
  const centerX = box.x + box.w / 2;
  const centerY = box.y + box.h / 2;
  const offsetX = Math.round(rect.width / 2 - centerX * backgroundWidth);
  const offsetY = Math.round(rect.height / 2 - centerY * backgroundHeight);
  crop.style.backgroundSize = `${scale}% auto`;
  crop.style.backgroundPosition = `${offsetX}px ${offsetY}px`;
}

function renderPageStage(stage, item) {
  if (!item.screenshot_url) {
    stage.replaceChildren(createEmptyState("页面截图已不可用", "请重新复核 PDF"));
    return;
  }
  const boxes = evidenceBoxes(item);
  const focusBox = boxes.length ? enclosingBox(boxes) : null;
  const hasFocus = focusBox && focusBox.w * focusBox.h < 0.8;
  const view = document.createElement("div");
  view.className = hasFocus
    ? `pdf-evidence-view${boxes.length > 1 ? " multiple" : ""}`
    : "pdf-evidence-view single";
  const frame = createPageFrame(stage, view, item);
  if (hasFocus) frame.append(...boxes.map((box, index) => createEvidenceHighlight(box, index === 0)));
  else {
    const notice = document.createElement("span");
    notice.className = "page-notice";
    notice.textContent = "这一页需要整体确认";
    frame.append(notice);
  }
  const zoom = hasFocus ? createEvidenceZoom(item, boxes) : null;
  view.append(...(zoom ? [frame, zoom] : [frame]));
  stage.replaceChildren(view);
  if (zoom) {
    const image = frame.firstElementChild;
    const crop = zoom.children[1];
    const fitZoom = () => fitEvidenceZoom(crop, image, focusBox);
    image.addEventListener("load", fitZoom, { once: true });
    if (image.complete) fitZoom();
  }
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

function createRepairAction(item) {
  if (!item.suggested_scope) return null;
  const action = createFinding(
    "继续处理",
    item.fix_mode === "auto" ? "可以回到工作台继续修正" : "这个问题需要在 Word 或 WPS 中确认",
  );
  const button = document.createElement("button");
  button.className = "theme-action";
  button.type = "button";
  button.dataset.action = "repair-scope";
  button.dataset.scope = item.suggested_scope;
  button.dataset.fixMode = item.fix_mode || "manual";
  button.textContent = "去修复";
  action.append(button);
  return action;
}

function createIssueButton(item, index, activeIndex) {
  const button = document.createElement("button");
  button.className = `film-frame ${index === activeIndex ? "active" : ""}`;
  button.type = "button";
  button.ariaPressed = String(index === activeIndex);
  button.setAttribute("aria-controls", "pdf-evidence-stage");
  button.dataset.issueIndex = String(index);
  const label = document.createElement("span");
  label.textContent = `第 ${item.page || "-"} 页`;
  const issue = document.createElement("b");
  issue.textContent = labelForRule(item.rule_id);
  button.append(label, issue);
  return button;
}

export function bindPdfReview(root, rerender) {
  root.addEventListener("click", (event) => {
    const issueButton = event.target.closest("[data-issue-index]");
    if (!issueButton) return;
    activeEvidenceIndex = Number(issueButton.dataset.issueIndex) || 0;
    rerender();
  });
}
