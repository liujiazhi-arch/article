import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_VIEW_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "resultView.js").as_uri()


def test_render_result_maps_readiness_to_student_facing_status():
    result = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT,
        input=f"""
import assert from "node:assert/strict";
import {{ renderResult }} from {json.dumps(RESULT_VIEW_URL)};

class FakeElement {{
  constructor() {{
    this.textContent = "";
  }}
}}

const badge = new FakeElement();
const title = new FakeElement();
const message = new FakeElement();
const root = {{
  querySelector(selector) {{
    return {{
      ".completion-orb strong": badge,
      ".result-hero h2": title,
      ".result-hero > p": message,
    }}[selector] || null;
  }},
  querySelectorAll() {{ return []; }},
}};

const cases = [
  ["needs-fix", "待修复", "仍有格式问题", "先查看审查报告 再继续处理"],
  ["manual-review-required", "待确认", "需要人工确认", "先查看报告中的人工复核项"],
  ["unsupported", "待确认", "需要人工确认", "先查看报告中的人工复核项"],
  ["render-check-required", "待复核", "修复包已生成", "下载副本后导出 PDF 复核"],
];

for (const [readiness, expectedBadge, expectedTitle, expectedMessage] of cases) {{
  renderResult({{ summary: {{ readiness }}, artifacts: [] }}, root);
  assert.deepEqual(
    {{ badge: badge.textContent, title: title.textContent, message: message.textContent }},
    {{ badge: expectedBadge, title: expectedTitle, message: expectedMessage }},
    readiness,
  );
}}
""",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout
