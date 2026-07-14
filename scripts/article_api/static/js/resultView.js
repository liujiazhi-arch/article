import { downloadJobArtifactUrl } from "./api.js";
import { escapeHtml, formatDateTime, scopeLabel } from "./copy.js";

const REVIEW_STATUSES = new Set([
  "manual-review-required",
  "manual_review",
  "unsupported",
  "mixed",
]);

function artifactByRole(payload, role) {
  const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
  return artifacts.find((item) => item.role === role);
}

function formatScopes(scopes) {
  if (!Array.isArray(scopes) || !scopes.length) return "全部范围";
  return scopes.map(scopeLabel).join(" / ");
}

function setDownloadButton(button, payload, role, unavailableText) {
  if (!button) return;
  const artifact = artifactByRole(payload, role);
  const available = Boolean(payload?.job_id && artifact?.available);
  button.disabled = !available;
  button.dataset.jobId = payload?.job_id || "";
  if (available) button.dataset.downloadUrl = downloadJobArtifactUrl(payload.job_id, role);
  else delete button.dataset.downloadUrl;
  const text = button.querySelector("span");
  if (text && !available) text.textContent = unavailableText;
}

function heatmapItem(scope, coverStatus) {
  const failedCount = Number(scope.failed_count || 0);
  const label = scope.title || scopeLabel(scope.id);
  const status = scope.id === "cover" && coverStatus
    ? coverStatus
    : failedCount > 0 ? `${failedCount}项` : "通过";
  const description = escapeHtml(`${label} ${status}`);
  const state = failedCount > 0 ? "warn" : "pass";
  return `<span class="${state}" title="${description}" aria-label="${description}"><b>${escapeHtml(label)}</b><small>${escapeHtml(status)}</small></span>`;
}

function renderHeatmap(root, payload) {
  const heatmap = root.querySelector("[data-result-heatmap]");
  if (!heatmap) return;
  const scopes = payload?.result?.verification?.scopes;
  if (!Array.isArray(scopes)) {
    heatmap.replaceChildren();
    return;
  }
  const coverStatus = {
    inserted: "已添加",
    replaced: "已替换",
  }[payload?.result?.cover_replacement?.status];
  heatmap.innerHTML = scopes.map((scope) => heatmapItem(scope, coverStatus)).join("");
}

function resultStatus(payload) {
  const summary = payload?.summary || {};
  const result = payload?.result || {};
  const businessStatus = summary.business_status ?? result.overall_status ?? result.verification?.overall_status;
  const readiness = summary.readiness ?? result.readiness ?? result.verification?.readiness;
  if (REVIEW_STATUSES.has(readiness) || REVIEW_STATUSES.has(businessStatus)) {
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

function renderStatus(root, payload) {
  const status = resultStatus(payload);
  const badge = root.querySelector(".completion-orb strong");
  const title = root.querySelector(".result-hero h2");
  const message = root.querySelector(".result-hero > p");
  if (badge) badge.textContent = status.badge;
  if (title) title.textContent = status.title;
  if (message) message.textContent = status.message;
}

function resultMetadata(payload) {
  const summary = payload?.summary || {};
  const output = artifactByRole(payload, "output");
  const fileName = output?.download_name
    || summary.output_name
    || (summary.output_path ? summary.output_path.split("/").pop() : null)
    || "等待修复结果";
  return {
    fileName,
    output,
    scopeText: payload ? formatScopes(summary.selected_scopes) : "等待选择范围",
    timeText: payload ? `${formatDateTime(payload.finished_at || payload.updated_at)} 本地生成` : "等待本地生成",
  };
}

function renderMetadata(root, payload, metadata) {
  const values = {
    "[data-result-file-name]": metadata.fileName,
    "[data-result-scope]": metadata.scopeText,
    "[data-result-time]": metadata.timeText,
    "[data-result-download-name]": metadata.fileName,
  };
  Object.entries(values).forEach(([selector, value]) => {
    const node = root.querySelector(selector);
    if (node) node.textContent = value;
  });
  const empty = root.querySelector("[data-result-empty]");
  if (empty) empty.hidden = Boolean(payload);
  root.querySelectorAll("[data-result-detail]").forEach((node) => { node.hidden = !payload; });
}

function renderDownloads(root, payload, metadata) {
  const note = root.querySelector("[data-result-download-note]");
  if (note) {
    note.textContent = metadata.output?.available
      ? "原文件未覆盖"
      : payload ? "下载文件已不可用 请重新运行修复" : "生成结果后可下载";
  }
  setDownloadButton(root.querySelector("[data-download-role='output']"), payload, "output", payload ? "下载文件已不可用 请重新运行修复" : "生成结果后可下载");
  setDownloadButton(root.querySelector("[data-download-role='report']"), payload, "report", payload ? "报告文件已不可用 请重新运行修复" : "生成结果后可下载报告");
  if (!artifactByRole(payload, "report")?.available) return;
  const text = root.querySelector("[data-download-role='report'] span");
  if (text) text.textContent = "下载报告文件 查看规则摘要和人工复核项";
}

export function renderResult(payload, root = document) {
  const metadata = resultMetadata(payload);
  renderMetadata(root, payload, metadata);
  renderDownloads(root, payload, metadata);
  renderStatus(root, payload);
  renderHeatmap(root, payload);
}
