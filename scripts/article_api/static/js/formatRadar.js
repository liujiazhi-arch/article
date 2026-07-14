const EMPTY_METRICS = Object.freeze({
  scopeCount: null,
  affectedScopes: null,
  autofixableScopes: null,
  manualReview: null,
  unsupported: null,
  unknown: 0,
});

const UNKNOWN_METRICS = Object.freeze({
  scopeCount: null,
  affectedScopes: null,
  autofixableScopes: null,
  manualReview: null,
  unsupported: null,
  unknown: null,
});

const PASSIVE_STATES = Object.freeze({
  idle: {
    scoreLabel: "等待检查",
    conclusion: "上传论文后查看格式检查结果",
    note: "仅代表已接入的结构规则\n原稿不会被覆盖",
  },
  loading: {
    scoreLabel: "检查中",
    conclusion: "正在读取论文结构",
    note: "完成后会显示真实处理范围\n原稿不会被覆盖",
  },
  error: {
    scoreLabel: "待重试",
    conclusion: "暂时没有生成检查结果",
    note: "请重新生成修复方案\n原稿不会被覆盖",
  },
});

function firstCount(...values) {
  for (const value of values) {
    if (value == null || value === "") continue;
    const count = Number(value);
    if (Number.isFinite(count) && count >= 0) return count;
  }
  return null;
}

function scopeCounts(scopes, field) {
  const counts = scopes.map((scope) => firstCount(scope?.[field]));
  return counts.some((count) => count == null) ? null : counts;
}

function countAffectedScopes(scopes, field) {
  const counts = scopeCounts(scopes, field);
  return counts == null ? null : counts.filter((count) => count > 0).length;
}

function sumScopeCount(scopes, field) {
  const counts = scopeCounts(scopes, field);
  return counts == null ? null : counts.reduce((total, count) => total + count, 0);
}

function legacyManualReview(summary) {
  if (summary.manual_review_items != null) return summary.manual_review_items;
  if (summary.manual_confirmation_items == null) return null;
  return Math.max(
    0,
    (firstCount(summary.manual_confirmation_items) ?? 0) - (firstCount(summary.unsupported_items) ?? 0),
  );
}

function buildMetrics(plan) {
  const hasScopes = Array.isArray(plan?.scopes);
  const scopes = hasScopes ? plan.scopes : [];
  const radar = plan?.scope_radar_summary || {};
  const summary = plan?.summary || {};
  const hasRadarSummary = plan?.scope_radar_summary != null;
  if (!hasRadarSummary && !hasScopes) return { ...UNKNOWN_METRICS };
  return {
    scopeCount: firstCount(radar.scope_count, hasScopes ? scopes.length : null),
    affectedScopes: firstCount(
      radar.failed_scope_count,
      hasScopes ? countAffectedScopes(scopes, "failed_count") : null,
    ),
    autofixableScopes: firstCount(
      radar.autofixable_scope_count,
      summary.autofixable_scopes,
      hasScopes ? countAffectedScopes(scopes, "autofixable_count") : null,
    ),
    manualReview: firstCount(
      radar.manual_review_count,
      legacyManualReview(summary),
      hasScopes ? sumScopeCount(scopes, "manual_review_count") : null,
    ),
    unsupported: firstCount(
      radar.unsupported_count,
      summary.unsupported_items,
      hasScopes ? sumScopeCount(scopes, "unsupported_count") : null,
    ),
    unknown: firstCount(
      radar.unknown_count,
      hasScopes ? sumScopeCount(scopes, "unknown_count") : null,
      summary.manual_confirmation_items != null ? 0 : null,
    ),
  };
}

function metricsAreIncomplete(metrics) {
  return metrics.scopeCount == null
    || metrics.scopeCount <= 0
    || Object.values(metrics).some((value) => value == null);
}

function formatConclusion(metrics, score) {
  if (score == null || metricsAreIncomplete(metrics)) return "检查结果不完整  请重新生成方案";
  const affected = metrics.affectedScopes;
  if (metrics.unknown > 0) {
    return affected > 0
      ? `${affected} 个范围存在问题  ${metrics.unknown} 项暂未归类`
      : `${metrics.unknown} 项问题暂未归类`;
  }
  if (metrics.unsupported > 0) return `${affected} 个范围存在问题  ${metrics.unsupported} 项暂不支持自动处理`;
  if (metrics.manualReview > 0) return `${affected} 个范围存在问题  ${metrics.manualReview} 项需要你确认`;
  if (affected > 0 && metrics.autofixableScopes > 0) return `${affected} 个范围存在问题  可先处理已支持的范围`;
  if (affected > 0) return `${affected} 个范围存在问题  请查看处理范围`;
  return "已接入的结构规则暂未发现问题";
}

function buildAriaLabel(model) {
  if (model.state !== "ready") return `${model.scoreLabel}  ${model.conclusion}`;
  const scoreText = model.score == null ? "暂无结构规则分" : `结构规则得分 ${model.score} 分`;
  const metrics = model.metrics;
  const unknownText = metrics.unknown > 0 ? ` 暂未归类 ${metrics.unknown} 项` : "";
  return `${scoreText} 方案包含 ${metrics.scopeCount} 个范围 受影响 ${metrics.affectedScopes} 个范围 可自动处理 ${metrics.autofixableScopes} 个范围 人工确认 ${metrics.manualReview} 项 暂不支持 ${metrics.unsupported} 项${unknownText}`;
}

function buildPassiveModel(state) {
  const copy = PASSIVE_STATES[state] || PASSIVE_STATES.idle;
  const model = {
    state,
    score: null,
    progress: 0,
    metrics: { ...EMPTY_METRICS },
    ...copy,
    liveStatus: state === "error" ? `${copy.scoreLabel}  ${copy.conclusion}` : copy.scoreLabel,
  };
  return { ...model, ariaLabel: buildAriaLabel(model) };
}

export function buildFormatRadarModel(input = {}) {
  const state = input.state || (input.plan ? "ready" : "idle");
  if (state !== "ready") return buildPassiveModel(state);
  const rawScore = input.plan?.score;
  const score = typeof rawScore === "number" && Number.isFinite(rawScore)
    ? Math.max(0, Math.min(100, rawScore))
    : null;
  const metrics = buildMetrics(input.plan);
  const isPartial = score == null || metricsAreIncomplete(metrics);
  const conclusion = formatConclusion(metrics, score);
  const model = {
    state: isPartial ? "partial" : state,
    score,
    progress: score ?? 0,
    scoreLabel: score == null ? "暂无分数" : `${Math.round(score)}分`,
    conclusion,
    note: isPartial ? "方案结果不完整\n请重新生成方案" : "仅代表已接入的结构规则\n封面和 PDF 仍需复核",
    liveStatus: conclusion,
    metrics,
  };
  return { ...model, ariaLabel: buildAriaLabel(model) };
}

function setText(root, selector, value) {
  const node = root.querySelector(selector);
  if (node) node.textContent = value;
}

function renderMetrics(root, metrics) {
  const entries = {
    "scope-count": metrics.scopeCount,
    "affected-scopes": metrics.affectedScopes,
    "autofixable-scopes": metrics.autofixableScopes,
    "manual-review": metrics.manualReview,
    unsupported: metrics.unsupported,
  };
  Object.entries(entries).forEach(([name, value]) => {
    setText(root, `[data-format-radar-metric="${name}"]`, value == null ? "--" : String(value));
  });
}

export function renderFormatRadar(input, root = document) {
  const model = buildFormatRadarModel(input);
  const panel = root.querySelector("[data-format-radar-panel]");
  const dial = root.querySelector("[data-format-radar]");
  if (panel) panel.dataset.state = model.state;
  if (dial) {
    dial.style.setProperty("--radar-progress", `${model.progress}%`);
    dial.setAttribute("aria-label", model.ariaLabel);
  }
  setText(root, "[data-format-radar-label]", model.scoreLabel);
  setText(root, "[data-format-radar-conclusion]", model.conclusion);
  setText(root, "[data-format-radar-note]", model.note);
  setText(root, "[data-format-radar-status]", model.liveStatus);
  renderMetrics(root, model.metrics);
  const unknown = root.querySelector("[data-format-radar-unknown]");
  if (unknown) {
    unknown.hidden = model.state !== "ready" || model.metrics.unknown === 0;
    unknown.textContent = model.metrics.unknown > 0 ? `${model.metrics.unknown} 项暂未归类  建议人工确认` : "";
  }
  return model;
}
