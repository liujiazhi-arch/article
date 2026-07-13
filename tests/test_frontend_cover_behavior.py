import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COVER_FORM_URL = (ROOT / "scripts" / "article_api" / "static" / "js" / "coverForm.js").as_uri()
INDEX_PATH = ROOT / "scripts" / "article_api" / "static" / "index.html"
APP_PATH = ROOT / "scripts" / "article_api" / "static" / "js" / "app.js"


def _run_node(scenario: str) -> None:
    result = subprocess.run(
        ["node", "--input-type=module"],
        cwd=ROOT,
        input=scenario,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_cover_form_requires_all_six_trimmed_fields() -> None:
    _run_node(
        f"""
import assert from "node:assert/strict";
import {{ collectCoverFields, coverSelectionIsValid }} from {json.dumps(COVER_FORM_URL)};

const values = {{
  thesis_title: "  论文题目  ",
  college: "生命科学院",
  major: "生物技术",
  student_name: "测试学生",
  advisor: "测试教师",
  completion_date: "2026年6月",
}};
const fields = Object.entries(values).map(([name, value]) => ({{ dataset: {{ coverField: name }}, value }}));
const checkbox = {{ checked: true }};
const option = {{ querySelector: () => checkbox }};
const root = {{
  querySelector: (selector) => selector === "[data-scope-option='cover']" ? option : null,
  querySelectorAll: (selector) => selector === "[data-cover-field]" ? fields : [],
}};

assert.deepEqual(collectCoverFields(root), {{ ...values, thesis_title: "论文题目" }});
assert.equal(coverSelectionIsValid(root), true);
fields[5].value = "";
assert.equal(collectCoverFields(root), null);
assert.equal(coverSelectionIsValid(root), false);
checkbox.checked = false;
assert.equal(coverSelectionIsValid(root), true);
"""
    )


def test_cover_form_syncs_student_status_and_resets_personal_data() -> None:
    _run_node(
        f"""
import assert from "node:assert/strict";
import {{ resetCoverForm, syncCoverForm }} from {json.dumps(COVER_FORM_URL)};

const checkbox = {{ checked: true }};
const state = {{ textContent: "" }};
const option = {{ querySelector: (selector) => selector === "input" ? checkbox : state }};
const panel = {{ hidden: true }};
const fields = ["thesis_title", "college", "major", "student_name", "advisor", "completion_date"]
  .map((name) => ({{ dataset: {{ coverField: name }}, value: "已填写" }}));
const root = {{
  querySelector(selector) {{
    if (selector === "[data-scope-option='cover']") return option;
    if (selector === "[data-cover-fields]") return panel;
    return null;
  }},
  querySelectorAll: (selector) => selector === "[data-cover-field]" ? fields : [],
}};

syncCoverForm(root);
assert.equal(panel.hidden, false);
assert.equal(state.textContent, "已填写");
fields[0].value = "";
syncCoverForm(root);
assert.equal(state.textContent, "请填完整");

resetCoverForm(root);
assert.equal(checkbox.checked, false);
assert.equal(panel.hidden, true);
assert.equal(state.textContent, "填写后可用");
assert.deepEqual(fields.map((field) => field.value), ["", "", "", "", "", ""]);
"""
    )


def test_cover_form_is_wired_to_the_apply_request() -> None:
    html = INDEX_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")

    assert 'data-scope-option="cover"' in html
    assert 'data-cover-fields' in html
    for field_name in (
        "thesis_title",
        "college",
        "major",
        "student_name",
        "advisor",
        "completion_date",
    ):
        assert f'data-cover-field="{field_name}"' in html
    assert 'from "./coverForm.js"' in app
    assert "cover_fields: coverFields" in app
    assert "const hadCurrentDocument = Boolean(getState().docxUpload);" in app
    assert "if (hadCurrentDocument) resetCoverForm(root);" in app
