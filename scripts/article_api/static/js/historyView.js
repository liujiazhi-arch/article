import { escapeHtml, formatDateTime, jobStatusLabels } from "./copy.js";

function isOpenable(job) {
  return job.status === "succeeded"
    && job.result_available
    && ["apply", "render-verify"].includes(job.operation);
}

function historyItem(job) {
  const display = job.display || {};
  const title = display.document_name || display.title || "本地处理记录";
  const openable = isOpenable(job);
  const detail = openable
    ? (display.output_name || display.title || "点击查看处理结果")
    : job.status === "failed" ? "处理没有完成 请重新运行" : "处理完成后可以查看结果";
  const status = jobStatusLabels[job.status] || "处理中";
  const time = formatDateTime(display.updated_at || job.updated_at).replace(" ", "<br>");
  return `
    <button class="task-card" type="button" ${openable ? `data-history-job-id="${escapeHtml(job.job_id)}"` : "disabled"}>
      <div class="task-date">${time}</div>
      <div><b>${escapeHtml(title)}</b><span>${escapeHtml(detail)}</span></div>
      <span class="status">${escapeHtml(status)}</span>
    </button>
  `;
}

export function renderHistory(jobs, root = document) {
  const list = root.querySelector("[data-history-list]");
  if (!list) return;
  if (!Array.isArray(jobs) || !jobs.length) {
    list.innerHTML = `<button class="task-card" type="button" data-action="enter-workbench"><div class="task-date">等待<br>记录</div><div><b>还没有历史记录</b><span>上传论文后会显示在这里</span></div><span class="status">上传论文</span></button>`;
    return;
  }
  const sorted = [...jobs].sort((left, right) => Number(isOpenable(right)) - Number(isOpenable(left)));
  list.innerHTML = sorted.map(historyItem).join("");
}

export function renderHistoryError(error, root = document) {
  const list = root.querySelector("[data-history-list]");
  if (!list) return;
  const nextAction = escapeHtml(error.nextAction || "请稍后刷新");
  list.innerHTML = `<div class="task-card"><div class="task-date">稍后<br>重试</div><div><b>历史记录暂时不可用</b><span>${nextAction}</span></div><span class="status">提示</span></div>`;
}
