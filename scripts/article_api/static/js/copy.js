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
