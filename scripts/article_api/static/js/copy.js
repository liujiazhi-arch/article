export const severityLabels = {
  error: "需要处理",
  warning: "建议确认",
  info: "提示",
};

export const renderEvidenceStatusLabels = {
  "render-evidence-ready": "无异常",
  "render-review-required": "需复核",
  "structure-not-ready": "先修复",
  "blocked-by-wild-doc": "先整理",
  "unsupported-evidence": "待确认",
};

export const renderRuleLabels = {
  "render.isolated_punctuation": "标点单独成行",
  "render.heading_orphan_at_page_bottom": "标题靠近页底",
  "render.formula_number_split_page": "公式编号分页",
  "render.toc_page_number_mismatch": "目录页码疑似错位",
  "render.toc_page_number_unconfirmed": "目录页码需要确认",
  "render.blank_page": "出现空白页",
  "render.render_suspect": "页面版式需要确认",
  default: "版式位置需要确认",
};

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

export const jobStatusLabels = {
  queued: "等待处理",
  running: "处理中",
  succeeded: "已完成",
  failed: "需要重试",
};

export function scopeLabel(scopeId) {
  return scopeLabels[scopeId] || "论文范围";
}

export function formatDateTime(value) {
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

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
