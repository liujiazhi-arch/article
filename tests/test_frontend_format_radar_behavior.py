import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORMAT_RADAR_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "formatRadar.js").as_uri()


def _run_node(scenario: str) -> None:
    result = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT,
        input=f"""
import assert from "node:assert/strict";
import {{ buildFormatRadarModel, renderFormatRadar }} from {json.dumps(FORMAT_RADAR_URL)};

class FakeElement {{
  constructor() {{
    this.dataset = {{}};
    this.textContent = "";
    this.hidden = false;
    this.attributes = new Map();
    this.styleValues = {{}};
    this.style = {{
      setProperty: (name, value) => {{ this.styleValues[name] = value; }},
    }};
  }}

  setAttribute(name, value) {{ this.attributes.set(name, String(value)); }}
  getAttribute(name) {{ return this.attributes.get(name) ?? null; }}
}}

const panel = new FakeElement();
const dial = new FakeElement();
const score = new FakeElement();
const conclusion = new FakeElement();
const note = new FakeElement();
const unknown = new FakeElement();
const liveStatus = new FakeElement();
const metrics = new Map([
  ["scope-count", new FakeElement()],
  ["affected-scopes", new FakeElement()],
  ["autofixable-scopes", new FakeElement()],
  ["manual-review", new FakeElement()],
  ["unsupported", new FakeElement()],
]);

const elements = {{
  "[data-format-radar-panel]": panel,
  "[data-format-radar]": dial,
  "[data-format-radar-label]": score,
  "[data-format-radar-conclusion]": conclusion,
  "[data-format-radar-note]": note,
  "[data-format-radar-unknown]": unknown,
  "[data-format-radar-status]": liveStatus,
}};

const root = {{
  querySelector(selector) {{
    const metricMatch = selector.match(/^\\[data-format-radar-metric="(.+)"\\]$/);
    if (metricMatch) return metrics.get(metricMatch[1]) || null;
    return elements[selector] || null;
  }},
}};

{scenario}
""",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_format_radar_model_uses_backend_score_and_keeps_review_buckets_separate():
    _run_node(
        """
const model = buildFormatRadarModel({
  state: "ready",
  plan: {
    score: 93,
    findings: Array.from({ length: 40 }),
    scope_radar_summary: {
      scope_count: 8,
      failed_scope_count: 3,
      autofixable_scope_count: 2,
      manual_review_count: 4,
      unsupported_count: 1,
      unknown_count: 2,
    },
  },
});

assert.equal(model.score, 93);
assert.equal(model.progress, 93);
assert.equal(model.metrics.scopeCount, 8);
assert.equal(model.metrics.affectedScopes, 3);
assert.equal(model.metrics.autofixableScopes, 2);
assert.equal(model.metrics.manualReview, 4);
assert.equal(model.metrics.unsupported, 1);
assert.equal(model.metrics.unknown, 2);
assert.match(model.conclusion, /2 项暂未归类/);

const unscopedOnly = buildFormatRadarModel({
  state: "ready",
  plan: {
    score: 98,
    scope_radar_summary: {
      scope_count: 10,
      failed_scope_count: 0,
      autofixable_scope_count: 0,
      manual_review_count: 0,
      unsupported_count: 0,
      unknown_count: 1,
      unscoped_count: 1,
    },
  },
});
assert.equal(unscopedOnly.conclusion, "1 项问题暂未归类");
assert.doesNotMatch(unscopedOnly.conclusion, /暂未发现问题/);

const fallback = buildFormatRadarModel({
  state: "ready",
  plan: {
    score: 90,
    scope_radar_summary: { scope_count: null, failed_scope_count: null },
    scopes: [
      { failed_count: 1, autofixable_count: 1, manual_review_count: 2, unsupported_count: 0, unknown_count: 0 },
    ],
  },
});
assert.equal(fallback.metrics.scopeCount, 1);
assert.equal(fallback.metrics.affectedScopes, 1);
assert.equal(fallback.metrics.manualReview, 2);

const legacy = buildFormatRadarModel({
  state: "ready",
  plan: {
    score: 88,
    summary: {
      autofixable_scopes: 2,
      manual_confirmation_items: 3,
      unsupported_items: 1,
    },
    scopes: [],
  },
});
assert.equal(legacy.metrics.autofixableScopes, 2);
assert.equal(legacy.metrics.manualReview, 2);
assert.equal(legacy.metrics.unsupported, 1);

const incomplete = buildFormatRadarModel({ state: "ready", plan: { score: 92 } });
assert.equal(incomplete.state, "partial");
assert.equal(incomplete.scoreLabel, "92分");
assert.equal(incomplete.metrics.scopeCount, null);
assert.match(incomplete.conclusion, /检查结果不完整/);

const incompleteSummary = buildFormatRadarModel({
  state: "ready",
  plan: { score: 91, scope_radar_summary: { scope_count: 8 } },
});
assert.equal(incompleteSummary.state, "partial");
assert.equal(incompleteSummary.metrics.scopeCount, 8);
assert.equal(incompleteSummary.metrics.affectedScopes, null);
assert.match(incompleteSummary.ariaLabel, /检查结果不完整/);

const incompleteScopes = buildFormatRadarModel({
  state: "ready",
  plan: { score: 90, scopes: [{ id: "toc", failed_count: 1 }] },
});
assert.equal(incompleteScopes.state, "partial");
assert.equal(incompleteScopes.metrics.affectedScopes, 1);
assert.equal(incompleteScopes.metrics.autofixableScopes, null);
assert.match(incompleteScopes.conclusion, /检查结果不完整/);
"""
    )


def test_format_radar_model_treats_zero_as_a_real_score_and_explains_full_score_limits():
    _run_node(
        """
const zero = buildFormatRadarModel({ state: "ready", plan: { score: 0, scopes: [] } });
assert.equal(zero.scoreLabel, "0分");
assert.equal(zero.progress, 0);
assert.equal(zero.state, "partial");
assert.match(zero.conclusion, /检查结果不完整/);

const full = buildFormatRadarModel({
  state: "ready",
  plan: {
    score: 100,
    scope_radar_summary: {
      scope_count: 8,
      failed_scope_count: 0,
      autofixable_scope_count: 0,
      manual_review_count: 0,
      unsupported_count: 0,
      unknown_count: 0,
    },
  },
});
assert.match(full.conclusion, /结构规则暂未发现问题/);
assert.equal(full.note, `仅代表已接入的结构规则
封面和 PDF 仍需复核`);
"""
    )


def test_format_radar_model_requires_a_finite_numeric_backend_score():
    _run_node(
        """
const completeSummary = {
  scope_count: 8,
  failed_scope_count: 0,
  autofixable_scope_count: 0,
  manual_review_count: 0,
  unsupported_count: 0,
  unknown_count: 0,
};

for (const scoreValue of [undefined, null, "", "93", Number.NaN, Number.POSITIVE_INFINITY]) {
  const model = buildFormatRadarModel({
    state: "ready",
    plan: { score: scoreValue, scope_radar_summary: completeSummary },
  });
  assert.equal(model.state, "partial");
  assert.equal(model.score, null);
  assert.equal(model.scoreLabel, "暂无分数");
  assert.match(model.conclusion, /检查结果不完整/);
  assert.equal(model.note, `方案结果不完整
请重新生成方案`);
  assert.doesNotMatch(model.conclusion, /暂未发现问题/);
}
"""
    )


def test_format_radar_renderer_updates_real_metrics_state_and_accessible_summary():
    _run_node(
        """
renderFormatRadar({
  state: "ready",
  plan: {
    score: 86,
    scope_radar_summary: {
      scope_count: 8,
      failed_scope_count: 4,
      autofixable_scope_count: 3,
      manual_review_count: 2,
      unsupported_count: 1,
      unknown_count: 1,
    },
  },
}, root);

assert.equal(panel.dataset.state, "ready");
assert.equal(dial.styleValues["--radar-progress"], "86%");
assert.equal(score.textContent, "86分");
assert.equal(metrics.get("scope-count").textContent, "8");
assert.equal(metrics.get("affected-scopes").textContent, "4");
assert.equal(metrics.get("autofixable-scopes").textContent, "3");
assert.equal(metrics.get("manual-review").textContent, "2");
assert.equal(metrics.get("unsupported").textContent, "1");
assert.equal(unknown.hidden, false);
assert.match(unknown.textContent, /1 项暂未归类/);
assert.match(dial.getAttribute("aria-label"), /结构规则得分 86 分/);
assert.match(dial.getAttribute("aria-label"), /方案包含 8 个范围/);
assert.match(dial.getAttribute("aria-label"), /人工确认 2 项/);
assert.equal(liveStatus.textContent, "4 个范围存在问题  1 项暂未归类");

renderFormatRadar({ state: "loading" }, root);
assert.equal(panel.dataset.state, "loading");
assert.equal(score.textContent, "检查中");
assert.equal(dial.styleValues["--radar-progress"], "0%");
assert.equal(metrics.get("scope-count").textContent, "--");
assert.equal(unknown.hidden, true);
assert.equal(liveStatus.textContent, "检查中");

renderFormatRadar({ state: "error" }, root);
assert.equal(panel.dataset.state, "error");
assert.equal(liveStatus.textContent, "待重试  暂时没有生成检查结果");
"""
    )
