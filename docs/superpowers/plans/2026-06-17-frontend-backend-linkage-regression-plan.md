# Frontend Backend Linkage Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify and restore the migrated frontend's real-time linkage with backend upload, plan, apply, history, PDF review, result downloads, format radar, and rule heatmap features.

**Architecture:** Keep the existing production static frontend under `scripts/article_api/static/` and backend API contracts under `scripts/article_api/`. Add regression coverage around the real user flows instead of replacing the UI. Fix only broken bindings, stale selectors, and missing data hooks discovered by tests.

**Tech Stack:** FastAPI, vanilla HTML/CSS/JavaScript modules, pytest, FastAPI TestClient, `scripts/local_browser_smoke.py`, Playwright CLI wrapper.

---

## Current Evidence

Verified on 2026-06-17:

- `python3 -m pytest tests/test_article_static_frontend.py tests/test_article_api.py tests/test_article_jobs.py -q`
  - Result: `139 passed in 40.37s`
- `python3 scripts/local_browser_smoke.py --work-dir /tmp/article-local-browser-smoke-20260617 --json-output /tmp/article-local-browser-smoke-20260617.json --command-timeout-seconds 120`
  - Result: failed.
  - Root cause: smoke still clicks old selectors:
    - `label[for='paper-file']`
    - `#run-all-button`
    - `#report-action-button`
    - `#report-output`
  - Current frontend uses migrated selectors and hooks:
    - `[data-action='choose-docx']`
    - `[data-action='create-plan']`
    - `[data-action='create-apply-job']`
    - `[data-download-role='output']`
- Component hook inventory:
  - Workbench metrics and ledger are wired through `data-workbench-metric` and `data-workbench-ledger`.
  - History list is wired through `data-history-list`.
  - PDF review evidence viewer is wired through `data-pdf-stage`, `data-pdf-issues`, `data-pdf-detail`, and `data-pdf-metric`.
  - Result file and downloads are wired through `data-result-*` and `data-download-role`.
  - Rule heatmap is wired through `data-result-heatmap`.
  - Format radar is currently visual-only CSS through `.radar`; it has no `data-*` hook and is not updated by backend plan state.

## Codex Arbitration After Dual-Model Review

Verified against repository code on 2026-06-17:

- **D1 accepted:** browser smoke must navigate into the workbench before clicking upload. `scripts/article_api/static/index.html:31` makes the cover screen active on load, `scripts/article_api/static/index.html:84` contains the workbench screen, `scripts/article_api/static/index.html:128` contains `[data-action='choose-docx']`, and `scripts/article_api/static/styles/layout.css:678-685` hides inactive screens with `display: none`.
- **D2 accepted:** successful apply writes `修正结果已生成`, not `修复结果已生成`. The plan text must use the exact runtime string from `scripts/article_api/static/js/app.js:388`. `修复方案已生成` remains valid because it is written by `scripts/article_api/static/js/app.js:140`.
- **D3 accepted:** smoke assertions must prefer dynamic linkage signals. `可修复范围` is static HTML at `scripts/article_api/static/index.html:136`, `修复包已生成` is static HTML at `scripts/article_api/static/index.html:274`, and `规则色谱` is static HTML at `scripts/article_api/static/index.html:292`. Stronger result checks should assert `data-result-file-name` is no longer `等待修复结果` after `renderResultPanel` writes it at `scripts/article_api/static/js/app.js:226`, and that download buttons become enabled through `setDownloadButton` at `scripts/article_api/static/js/app.js:233-234`.
- **D4 accepted:** extend `tests/test_frontend_backend_contract.py`; do not create `tests/test_frontend_backend_linkage.py`. Existing tests already cover endpoints, workbench plan wiring, result download/history/apply result wiring, and PDF review hooks at `tests/test_frontend_backend_contract.py:20-126`.
- **D5 confirmed:** missing PDF upload raises `LookupError` at `scripts/article_api/render_review_jobs.py:15-16`; non-PDF upload raises `ValueError("请选择从 Word 或 WPS 导出的 PDF 文件。")` at `scripts/article_api/render_review_jobs.py:20-21`, so `pytest.raises(ValueError, match="PDF")` is valid.
- **D6 accepted:** radar CSS replacement must remove the old visible `content: "格式雷达"` pseudo-element from `scripts/article_api/static/styles/layout.css:1476-1488` before adding a real `[data-format-radar-label]` span.
- **D7 accepted:** history smoke must assert a real rendered job title, not only static history chrome. `scripts/article_api/static/index.html:175` and `scripts/article_api/static/index.html:183` are static copy, while `scripts/article_api/static/js/app.js:307-323` writes `display.document_name` into each history card. The smoke source file is `browser_smoke.docx` from `scripts/local_browser_smoke.py:130`, so history linkage should wait for `browser_smoke`.
- **D8 accepted:** cache-bust maintenance must be explicit. CSS is loaded with `?v=20260617-upload-circle` at `scripts/article_api/static/index.html:9`, JS is loaded with the same key at `scripts/article_api/static/index.html:313`, and `tests/test_article_static_frontend.py:136` locks that string. This phase may keep the key if browser smoke uses a fresh service/session, but any intentional bump must update HTML and the lock test together.

## Files

Modify:

- `scripts/local_browser_smoke.py`
  - Update browser smoke selectors to the migrated frontend.
  - Add assertions for workbench metrics, history, result download, and rule heatmap.
- `scripts/article_api/static/index.html`
  - Add missing `data-*` hooks for format radar if tests prove it is still static.
- `scripts/article_api/static/js/app.js`
  - Update format radar from real plan/job state.
  - Keep existing workbench/history/result/PDF code paths unless tests prove a break.
- `scripts/article_api/static/styles/layout.css`
  - Add data-driven radar styling through CSS variables if needed.
- `tests/test_article_static_frontend.py`
  - Lock the expected frontend hooks and forbid stale selectors.
- `tests/test_frontend_backend_contract.py`
  - Extend existing source-level contract tests with only missing radar wiring assertions.
- `tests/test_render_review_jobs.py` or existing API tests
  - Add missing render-review job checks only if PDF review linkage is not already covered.

Do not modify:

- `.tmp/frontend-preview/`
- Broad theme assets unrelated to linkage
- Core thesis formatting engines unless an API test proves backend payload shape is wrong

## Execution Boundary

Frontend scope is surgical. Modify only `scripts/article_api/static/index.html`, `scripts/article_api/static/js/app.js`, and `scripts/article_api/static/styles/layout.css` for UI linkage fixes. Keep the existing vanilla HTML/CSS/JS module architecture; do not introduce a framework, bundler, npm dependency, or new frontend runtime.

Do not change `scripts/article_api/static/js/pdfReview.js`, `scripts/article_api/static/js/api.js`, `scripts/article_api/static/js/state.js`, or `scripts/article_api/static/js/copy.js` unless a targeted test proves their contract is broken. These files are already covered by `tests/test_frontend_backend_contract.py`, and this plan is about restoring migrated linkage rather than redesigning the frontend.

Backend scope is contract verification only. Do not change API payload shapes, `scripts/article_api/render_review_jobs.py` behavior, or the thesis formatting engines (`scripts/audit_thesis.py`, `scripts/fix_thesis.py`, `scripts/_thesis_utils.py`) unless an API test proves a backend payload is wrong. Do not update `config/capability_matrix.md` for the radar work: the radar is a frontend display of existing `planSummary` counts, not a new runtime rule.

Testing scope stays narrow. Do not create `tests/test_frontend_backend_linkage.py`; add missing radar assertions to `tests/test_frontend_backend_contract.py`. Do not modify `.tmp/frontend-preview/`, broad theme assets, or `config/` for this linkage regression.

Avoid overengineering the radar. Its center label must use real `planSummary` counts, but the conic angle is only a visual urgency hint. Do not add a backend field, configuration layer, fake precision score, or new abstraction for this phase.

## Linked Code Maintenance

This frontend has no type system or build step, so linkage drift must be guarded by tests and smoke checks:

1. Changing an `index.html` `data-*` hook requires updating the matching `app.js` `querySelector`, `tests/test_article_static_frontend.py` hook assertions, and `scripts/local_browser_smoke.py` selector.
2. Changing an `app.js` status string, such as `修正结果已生成`, requires updating `scripts/local_browser_smoke.py` `_wait_for_snapshot_text` calls and any test that asserts the string.
3. Changing `.radar` CSS or markup requires keeping `index.html` radar structure, `layout.css`, and `tests/test_article_static_frontend.py` in sync. Also evaluate whether to bump `20260617-upload-circle` in both CSS and JS asset URLs; if bumped, update the test that locks the string.
4. Adding student-facing copy must still satisfy `tests/test_frontend_backend_contract.py` forbidden-term checks. Do not expose backend terms such as `bbox`, `rule_id`, `queued`, `running`, `failed`, or `profile` in the visible UI.
5. Task 2 and Task 6 both edit `scripts/local_browser_smoke.py`; merge them into one sequence: navigate to workbench, upload, wait for plan, generate result, assert result dynamic content, assert history real job record, return to result, then download.

## Task 1: Freeze Current Frontend Hook Contract

**Files:**

- Modify: `tests/test_article_static_frontend.py`

- [ ] **Step 1: Add failing test for migrated selectors and removed stale selectors**

Add this test:

```python
def test_static_frontend_uses_migrated_action_hooks_not_legacy_console_ids():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert 'data-action="choose-docx"' in html
    assert 'data-action="create-plan"' in html
    assert 'data-action="create-apply-job"' in html
    assert 'data-download-role="output"' in html
    assert 'data-history-list' in html
    assert 'data-result-heatmap' in html
    assert 'label for="paper-file"' not in html
    assert 'id="paper-file"' not in html
    assert 'id="run-all-button"' not in html
    assert 'id="report-action-button"' not in html
    assert 'id="report-output"' not in html
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py::test_static_frontend_uses_migrated_action_hooks_not_legacy_console_ids -q
```

Expected before implementation: pass if all hooks already exist. If it fails, use the failure as the exact hook drift to fix.

- [ ] **Step 3: Commit hook contract test after green**

Run:

```bash
git add tests/test_article_static_frontend.py
git commit -m "test: freeze migrated frontend action hooks"
```

Skip commit only if the current task is being executed in a no-commit review session.

## Task 2: Restore Browser Smoke For The Migrated Frontend

**Files:**

- Modify: `scripts/local_browser_smoke.py`

- [ ] **Step 1: Write failing selector regression test**

Create or extend a test in `tests/test_article_static_frontend.py`:

```python
def test_local_browser_smoke_does_not_reference_removed_frontend_selectors():
    smoke = Path("scripts/local_browser_smoke.py").read_text(encoding="utf-8")

    assert "label[for='paper-file']" not in smoke
    assert "#run-all-button" not in smoke
    assert "#report-action-button" not in smoke
    assert "#report-output" not in smoke
    assert "[data-action='enter-workbench']" in smoke
    assert "[data-action='choose-docx']" in smoke
    assert "[data-action='create-apply-job']" in smoke
    assert "[data-download-role='output']" in smoke
```

Add `from pathlib import Path` at the top of the test file if it is not already imported.

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py::test_local_browser_smoke_does_not_reference_removed_frontend_selectors -q
```

Expected: FAIL because current `scripts/local_browser_smoke.py` still uses legacy selectors.

- [ ] **Step 3: Update browser smoke selectors**

In `scripts/local_browser_smoke.py`, change:

```python
_run_playwright(pwcli_path, "click", "label[for='paper-file']", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "upload", docx_path, cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "已上传", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "click", "#run-all-button", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "方案已生成", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "click", "#report-action-button", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修复完成", cwd=smoke_dir, timeout=timeout)
download_result = _run_playwright(pwcli_path, "click", "#report-output", cwd=smoke_dir, timeout=timeout)
```

To:

```python
_run_playwright(pwcli_path, "click", "[data-action='enter-workbench']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "上传论文开始修正", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "click", "[data-action='choose-docx']", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "upload", docx_path, cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修复方案已生成", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "click", "[data-action='create-apply-job']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修正结果已生成", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修复包已生成", cwd=smoke_dir, timeout=timeout)
download_result = _run_playwright(pwcli_path, "click", "[data-download-role='output']", cwd=smoke_dir, timeout=timeout)
```

If Playwright CLI cannot click `data-*` selectors directly, use CSS selector syntax with double quotes exactly as:

```python
"button[data-action='enter-workbench']"
"button[data-action='choose-docx']"
"button[data-action='create-apply-job']"
"button[data-download-role='output']"
```

- [ ] **Step 4: Run the selector regression test**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py::test_local_browser_smoke_does_not_reference_removed_frontend_selectors -q
```

Expected: PASS.

- [ ] **Step 5: Run full browser smoke**

Run:

```bash
python3 scripts/local_browser_smoke.py \
  --work-dir /tmp/article-local-browser-smoke-20260617-fixed \
  --json-output /tmp/article-local-browser-smoke-20260617-fixed.json \
  --command-timeout-seconds 180
```

Expected: JSON payload with `"status": "ok"`, nonzero `download_bytes`, and a valid `.docx` at `downloaded_docx`.

## Task 3: Make Format Radar Data-Driven

**Files:**

- Modify: `scripts/article_api/static/index.html`
- Modify: `scripts/article_api/static/js/app.js`
- Modify: `scripts/article_api/static/styles/layout.css`
- Modify: `tests/test_article_static_frontend.py`
- Modify: `tests/test_frontend_backend_contract.py`

- [ ] **Step 1: Add failing static hook test**

Add:

```python
def test_format_radar_exposes_real_state_hooks():
    client = TestClient(create_app())

    response = client.get("/")
    css_response = client.get("/static/styles/layout.css")

    assert response.status_code == 200
    assert css_response.status_code == 200
    html = response.text
    css = css_response.text
    assert 'class="radar"' in html
    assert 'data-format-radar' in html
    assert 'data-format-radar-label' in html
    assert "--radar-progress" in css
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py::test_format_radar_exposes_real_state_hooks -q
```

Expected: FAIL because `.radar` currently has no data hook.

- [ ] **Step 3: Add hooks to HTML**

In `scripts/article_api/static/index.html`, replace:

```html
<div class="radar" aria-label="格式雷达盘"></div>
```

With:

```html
<div class="radar" aria-label="格式雷达盘" data-format-radar style="--radar-progress: 0%">
  <span data-format-radar-label>等待检查</span>
</div>
```

- [ ] **Step 4: Update radar CSS**

In `scripts/article_api/static/styles/layout.css`, update `.radar`:

```css
.radar {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 168px;
  border-radius: 24px;
  background:
    radial-gradient(circle, transparent 0 34%, rgba(255, 255, 255, 0.10) 35% 36%, transparent 37% 56%, rgba(255, 255, 255, 0.12) 57% 58%, transparent 59%),
    conic-gradient(from -20deg, var(--accent) 0 var(--radar-progress, 0%), rgba(255, 255, 255, 0.14) var(--radar-progress, 0%) 100%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
}

.radar::after {
  content: "";
  position: absolute;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: rgba(6, 9, 8, 0.64);
  backdrop-filter: blur(16px);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
}

.radar span {
  position: relative;
  z-index: 1;
  max-width: 72px;
  color: rgba(255, 255, 255, 0.88);
  font-size: 14px;
  font-weight: 850;
  line-height: 1.25;
  text-align: center;
}
```

Remove the old `.radar::after { content: "格式雷达"; }` visible text pseudo-element. After this change, the visible radar label must come only from `[data-format-radar-label]`.

- [ ] **Step 5: Update radar from plan state**

In `scripts/article_api/static/js/app.js`, add:

```javascript
function renderFormatRadar(summary) {
  const radar = document.querySelector("[data-format-radar]");
  const label = document.querySelector("[data-format-radar-label]");
  if (!radar || !label) return;
  const failedCount = Number(summary.failedCount || 0);
  const manualCount = Number(summary.manualConfirmation || 0);
  const totalAttention = failedCount + manualCount;
  const progress = Math.max(8, Math.min(100, 100 - totalAttention * 6));
  radar.style.setProperty("--radar-progress", `${progress}%`);
  label.textContent = totalAttention > 0 ? `${totalAttention}项需确认` : "格式较稳";
}
```

The label text must use real `planSummary` counts. The conic progress is only a visual urgency hint; do not present it as a precise score or add a new backend field for it in this phase.

Then in `renderWorkbenchPlan(plan)`, after `const summary = planSummary(plan);`, add:

```javascript
renderFormatRadar(summary);
```

In `renderWorkbenchPlanPending(fileName)`, add:

```javascript
renderFormatRadar({ failedCount: 0, manualConfirmation: 0 });
```

In `renderWorkbenchPlanUnavailable(message)`, add:

```javascript
renderFormatRadar({ failedCount: 0, manualConfirmation: 1 });
```

- [ ] **Step 6: Run static tests**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py -q
```

Expected: PASS.

## Task 4: Extend Existing Frontend Contract Tests

**Files:**

- Modify: `tests/test_frontend_backend_contract.py`

- [ ] **Step 1: Add only the missing radar contract to the existing file**

Do not create `tests/test_frontend_backend_linkage.py`. `tests/test_frontend_backend_contract.py` already covers the workbench plan summary, history/result download wiring, apply result rendering, and PDF review evidence hooks.

Append a focused radar assertion:

```python
def test_frontend_js_wires_format_radar_from_plan_summary():
    static_root = ROOT / "scripts" / "article_api" / "static"
    app_js = (static_root / "js" / "app.js").read_text(encoding="utf-8")
    html = (static_root / "index.html").read_text(encoding="utf-8")

    assert "function renderFormatRadar(summary)" in app_js
    assert "renderFormatRadar(summary)" in app_js
    assert "data-format-radar" in html
    assert "data-format-radar-label" in html
```

- [ ] **Step 2: Run existing source-level render contract tests**

Run:

```bash
python3 -m pytest tests/test_frontend_backend_contract.py -q
```

Expected: PASS after Task 3 is implemented. If it fails before Task 3, keep it red until radar linkage is implemented.

## Task 5: Verify PDF Review Backend Contract

**Files:**

- Modify: `tests/test_article_api.py` or `tests/test_render_review_jobs.py`

- [ ] **Step 1: Add or confirm render-review job route test**

Add this test to `tests/test_render_review_jobs.py`:

```python
from types import SimpleNamespace

import pytest

from article_api.render_review_jobs import build_render_review_job_kwargs


def test_build_render_review_job_kwargs_links_docx_and_pdf_uploads():
    uploads = {
        "docx-1": {
            "file_name": "论文.docx",
            "stored_path": "/tmp/runtime/uploads/paper.docx",
            "runtime_root": "/tmp/runtime",
        },
        "pdf-1": {
            "file_name": "论文.pdf",
            "stored_path": "/tmp/runtime/uploads/paper.pdf",
            "runtime_root": "/tmp/runtime",
        },
    }
    request = SimpleNamespace(
        pdf_upload_id="pdf-1",
        profile="lnu",
        strict_profile=None,
        scopes=None,
        max_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=None,
    )

    payload = build_render_review_job_kwargs(
        "docx-1",
        request,
        resolve_upload_fn=lambda upload_id: uploads[upload_id],
    )

    assert payload["file_path"] == "/tmp/runtime/uploads/paper.docx"
    assert payload["rendered_pdf"] == "/tmp/runtime/uploads/paper.pdf"
    assert payload["workflow_mode"] == "default_user"
    assert payload["source_display_name"] == "论文.docx"
    assert payload["pdf_display_name"] == "论文.pdf"
    assert payload["runtime_root"] == "/tmp/runtime"
    assert payload["_public_request"] == {
        "docx_upload_id": "docx-1",
        "pdf_upload_id": "pdf-1",
    }


def test_build_render_review_job_kwargs_rejects_non_pdf_upload():
    uploads = {
        "docx-1": {"file_name": "论文.docx", "stored_path": "/tmp/paper.docx"},
        "pdf-1": {"file_name": "截图.png", "stored_path": "/tmp/page.png"},
    }
    request = SimpleNamespace(
        pdf_upload_id="pdf-1",
        profile="lnu",
        strict_profile=None,
        scopes=None,
        max_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=None,
    )

    with pytest.raises(ValueError, match="PDF"):
        build_render_review_job_kwargs(
            "docx-1",
            request,
            resolve_upload_fn=lambda upload_id: uploads[upload_id],
        )
```

If `tests/test_render_review_jobs.py` already exists, append these tests rather than replacing existing coverage.

- [ ] **Step 2: Run API render-review tests**

Run:

```bash
python3 -m pytest tests/test_article_api.py -q -k "render_review or render_verify or screenshot"
```

Expected: PASS.

## Task 6: Expand Browser Smoke To Assert Distinct UI Features

**Files:**

- Modify: `scripts/local_browser_smoke.py`

- [ ] **Step 1: Add post-apply dynamic UI checks**

After waiting for `"修复包已生成"`, capture a snapshot and assert the placeholder result text has been replaced by real job output:

```python
result_snapshot = _wait_for_snapshot_text(pwcli_path, "browser_smoke", cwd=smoke_dir, timeout=timeout)
if "等待修复结果" in result_snapshot:
    raise RuntimeError("Result panel did not replace the placeholder file name")
```

Do not use `规则色谱`, `下载 修复副本`, `审查报告`, or `修复包已生成` as proof of backend linkage. They are static result-screen copy and only prove that the screen is visible.

- [ ] **Step 2: Add history dynamic UI check**

After the repaired screenshot, click history and assert the real job appears. The main assertion must be the source document name written by `renderHistory`, not static history chrome:

```python
_run_playwright(pwcli_path, "click", "[data-screen-target='history']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "browser_smoke", cwd=smoke_dir, timeout=timeout)
```

`每一次修正都有记录` and `可下载` are static history-screen copy. They may be used only as a fallback screen-arrival check, not as evidence that backend history data was rendered.

- [ ] **Step 3: Keep download click on enabled result output**

Before clicking output download, return to result if history navigation changed the screen:

```python
_run_playwright(pwcli_path, "click", "[data-screen-target='result']", cwd=smoke_dir, timeout=timeout)
download_result = _run_playwright(pwcli_path, "click", "[data-download-role='output']", cwd=smoke_dir, timeout=timeout)
```

The following `download_bytes > 0` and `zipfile.is_zipfile(download_path)` checks remain the authoritative proof that the output download button became usable and returned a real `.docx`.

- [ ] **Step 4: Run smoke**

Run:

```bash
python3 scripts/local_browser_smoke.py \
  --work-dir /tmp/article-local-browser-smoke-20260617-linkage \
  --json-output /tmp/article-local-browser-smoke-20260617-linkage.json \
  --command-timeout-seconds 180
```

Expected:

```json
{
  "status": "ok",
  "ready": "ok",
  "download_bytes": 1
}
```

`download_bytes` must be greater than zero, not literally `1`.

## Task 7: Optional PDF Review Browser Smoke

**Files:**

- Modify: `scripts/local_browser_smoke.py` or create `scripts/local_pdf_review_browser_smoke.py`

- [ ] **Step 1: Decide whether the environment can generate a valid PDF**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
path = Path('/tmp/article-pdf-smoke.pdf')
path.write_bytes(b'%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n')
print(path, path.exists(), path.stat().st_size)
PY
```

Expected: creates a minimal PDF file. If backend rejects it because it cannot render pages, keep this as an API-level test only and do not block the normal upload/apply smoke on PDF review.

- [ ] **Step 2: Add PDF review browser smoke only if backend accepts the sample PDF**

Flow:

```python
_run_playwright(pwcli_path, "click", "[data-screen-target='pdf-review']", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "click", "[data-action='choose-pdf']", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "upload", pdf_path, cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "PDF 复核完成", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "PDF 证据槽", cwd=smoke_dir, timeout=timeout)
```

If the renderer dependency is not available locally, document the skip in the smoke payload instead of faking success.

## Task 8: Full Verification

**Files:** no code changes unless previous tasks require fixes.

- [ ] **Step 1: Run focused static and source tests**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py tests/test_frontend_backend_contract.py tests/test_render_review_jobs.py -q
```

Expected: all pass.

- [ ] **Step 2: Run API and job tests**

Run:

```bash
python3 -m pytest tests/test_article_api.py tests/test_article_jobs.py -q
```

Expected: all pass.

- [ ] **Step 3: Run browser smoke**

Run:

```bash
python3 scripts/local_browser_smoke.py \
  --work-dir /tmp/article-local-browser-smoke-final \
  --json-output /tmp/article-local-browser-smoke-final.json \
  --command-timeout-seconds 180
```

Expected: `"status": "ok"` and valid downloaded docx.

- [ ] **Step 4: Open the final smoke screenshots**

Inspect:

```bash
open /tmp/article-local-browser-smoke-final/local-console-home.png
open /tmp/article-local-browser-smoke-final/local-console-repaired.png
```

Expected visual checks:

- Workbench upload panel renders without native file input.
- Workbench metrics update after upload/plan.
- Format radar label updates from plan state.
- Result page shows generated file metadata.
- Rule heatmap is present and not empty.
- Download button is enabled.

## Completion Criteria

This plan is complete only when all of these are true:

- Stale browser smoke selectors are removed.
- Browser smoke passes on the migrated frontend.
- Format radar is connected to real plan state or explicitly documented as decorative only. Preferred outcome: connected.
- History list loads real jobs and can reopen apply/render results.
- Result heatmap renders from real apply job payload.
- PDF review evidence viewer still renders `evidence_items`, `screenshot_url`, and `bbox` overlays.
- No student-facing UI shows backend terms such as `bbox`, `rule_id`, `/jobs/{id}`, `queued`, `running`, or `failed`.
- Final evidence includes exact command output for pytest and browser smoke.
