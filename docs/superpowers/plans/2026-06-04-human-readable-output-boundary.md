# Human Readable Output Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the public thesis output folder limited to final DOCX files and human-readable reports.

**Architecture:** Preserve the existing engines and API shape. Change only default output naming for normalize jobs and render-verify report persistence so machine-oriented artifacts do not appear as user-facing outputs.

**Tech Stack:** Python, pytest, existing `article_api` and `thesis_tool.render_verify` modules.

---

### Task 1: Lock Output Boundary With Tests

**Files:**
- Modify: `tests/test_article_api.py`
- Modify: `tests/test_article_jobs.py`
- Modify: `tests/test_render_verify.py`

- [ ] **Step 1: Add tests that expect normalize defaults outside the public output directory and render reports as Markdown.**

- [ ] **Step 2: Run the targeted tests and confirm they fail on current behavior.**

Run: `python3 -m pytest tests/test_article_api.py::test_fake_app_upload_normalize_job_keeps_original_name tests/test_article_jobs.py::test_normalize_job_freezes_default_output_path_when_not_provided tests/test_render_verify.py::test_build_render_verify_report_writes_json_and_collects_pages -q`

Expected: FAIL because normalize still uses `结构整理` in the public output directory for uploaded docs and render-verify still writes `render_verify_report.json`.

### Task 2: Implement Public/Internal Output Split

**Files:**
- Modify: `scripts/article_api/output_naming.py`
- Modify: `scripts/article_api/job_payloads.py`
- Modify: `scripts/article_api/jobs.py`
- Modify: `scripts/thesis_tool/render_verify.py`

- [ ] **Step 1: Add an internal normalize output directory and make source-display normalize jobs default there.**

- [ ] **Step 2: Keep staged normalize outputs inside per-job workspace outputs.**

- [ ] **Step 3: Write render-verify Markdown as the user-facing report and JSON as internal debug data.**

- [ ] **Step 4: Remove user-facing wording that points users to JSON reports.**

### Task 3: Verify

**Files:**
- Test: `tests/test_article_api.py`
- Test: `tests/test_article_jobs.py`
- Test: `tests/test_render_verify.py`
- Test: `tests/test_article_http_smoke.py`

- [ ] **Step 1: Run targeted tests.**

Run: `python3 -m pytest tests/test_article_api.py::test_fake_app_upload_normalize_job_keeps_original_name tests/test_article_jobs.py::test_normalize_job_freezes_default_output_path_when_not_provided tests/test_render_verify.py::test_build_render_verify_report_writes_json_and_collects_pages -q`

- [ ] **Step 2: Run smoke coverage around HTTP upload/apply/download.**

Run: `python3 -m pytest tests/test_article_http_smoke.py::test_live_http_upload_apply_result_download_and_cleanup -q`

- [ ] **Step 3: Inspect the diff and summarize changed files.**
