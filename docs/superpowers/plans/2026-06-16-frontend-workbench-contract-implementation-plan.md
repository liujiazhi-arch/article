# Frontend Workbench Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deliverable student-facing frontend workbench that is served by the local Article API, preserves and migrates the approved four-theme visual direction from the existing frontend prototype, and connects PDF review to real backend evidence instead of static placeholders.

**Architecture:** Treat `.tmp/frontend-preview/system.html` as the source-of-truth visual reference for style, theme mood, typography direction, glass material, and screen composition, but migrate that design into formal static frontend files under `scripts/article_api/static/` so it can be served and packaged by the FastAPI app. Keep frontend/backend behavior frozen in `docs/FRONTEND_BACKEND_CONTRACT.md`. First version PDF review supports page screenshots plus normalized `bbox` overlays; character-level text spans are explicitly out of scope.

**Tech Stack:** FastAPI static file serving, vanilla HTML/CSS/JavaScript modules, existing Article API endpoints, pytest, FastAPI TestClient, Playwright or Browser for visual verification.

---

## Goal-Mode Objective

Use this objective when starting Codex Goal mode:

```text
Implement the deliverable frontend workbench plan in docs/superpowers/plans/2026-06-16-frontend-workbench-contract-implementation-plan.md: migrate the approved visual style from .tmp/frontend-preview/system.html into a formal static frontend served by the local Article API, freeze frontend/backend contracts, connect PDF review to real upload/render evidence flow, preserve the approved four-theme typography/UI direction, and verify with tests plus browser screenshots.
```

## Non-Negotiable Decisions

These decisions are part of the plan and should not be reopened during implementation unless code evidence proves they are impossible.

1. `.tmp/frontend-preview/system.html` is the approved visual reference and must be preserved as the design baseline.
2. Production frontend files live under `scripts/article_api/static/`.
3. The local API serves the frontend at `/` and static assets under `/static/...`.
4. The implementation should migrate the prototype's visual language into production files, not discard it or replace it with a generic console.
5. The old `local_console.html` from git history can be inspected as functional reference, but should not be restored wholesale.
6. PDF review mainline is student-provided PDF.
7. `docx -> PDF` auto-render remains a diagnostic path, not the primary student UI path.
8. First version PDF preview means page screenshot plus normalized region highlight.
9. `text_spans` or character-level PDF highlighting is a second-stage backend project.
10. Student-facing UI must not show backend terms such as `bbox`, `rule_id`, `preflight`, `plan`, `apply job`, `profile`, `mode`, `data contract`, `queued`, `running`, `failed`, or `/jobs/{id}`.
11. All frontend work must obey `docs/FRONTEND_UI_STYLE_GUIDE.md`.

## Preservation-First Frontend Rule

This implementation is a preservation-first migration, not a frontend rewrite.

The approved prototype at `.tmp/frontend-preview/system.html` is the primary visual and interaction baseline. Production frontend work must migrate and preserve the existing four-theme visual system, screen composition, glass material, typography mood, page structure, and already-designed functional areas as much as possible.

Do not replace the prototype with a simplified skeleton, generic dashboard, minimal demo page, or newly invented UI direction. The goal is to keep the existing frontend experience and connect it to real backend behavior.

Allowed changes are limited to:

- Moving production files into `scripts/article_api/static/`.
- Replacing `.tmp` asset paths with production `/static/...` paths.
- Removing or rewriting fake data and placeholder backend contract text.
- Replacing student-visible technical terms with student-facing copy.
- Wiring existing UI areas to real upload, job, result, and PDF evidence APIs.
- Making small targeted layout fixes only when needed for real data, responsiveness, or readability.

Disallowed changes:

- Do not discard existing screen layouts.
- Do not flatten the design into a basic HTML scaffold.
- Do not remove existing theme-specific visual treatments.
- Do not replace the four-theme style with a new design system.
- Do not simplify away functional sections that already exist in the prototype.
- Do not add broad fallback logic or speculative features unrelated to the plan.

Implementation rule:

```text
Keep the prototype experience.
Replace fake data with real backend state.
Move it into production static files.
Do not redesign it.
```

## Visual Baseline Contract

The existing prototype is visually valuable and should not be thrown away. The problem is its delivery and data wiring, not its overall style direction.

Use `.tmp/frontend-preview/system.html` and its referenced assets as the visual baseline for:

- Four-theme direction: snow, rain, morning, ginkgo.
- Cover title structure and theme-specific typography mood.
- Glass panels, dark translucent reading surfaces, borders, and depth.
- Screen concepts: cover, workbench, feature map, PDF review, history, result.
- Image-led theme assets and background board roles.
- Button density, compact tool surface, and non-marketing product feel.

Do not preserve these prototype parts:

- Static fake data as final data.
- Student-visible technical terms.
- Placeholder contract text.
- Hardcoded PDF evidence boxes that do not use backend evidence.
- `.tmp` paths as production asset paths.

Implementation rule:

```text
Prototype visual language stays.
Prototype directory and fake data do not.
```

## Current Evidence Baseline

Current repository facts that drove this plan:

- `.tmp/frontend-preview/system.html` has the approved four-theme visual direction and remains the visual baseline, but it is not a real app.
- `.tmp/frontend-preview/system.html` contains placeholder and technical strings such as `preflight`, `plan`, `apply job`, `profile`, `mode`, `data contract`, `page_image`, `rule_id`, and `bbox`.
- Current HEAD does not contain `scripts/article_api/local_console.html`; it exists only in git history.
- `/uploads/pdf` stores a PDF but does not currently trigger render verification.
- `/render-verify` is synchronous and expects `rendered_pdf` or `page_images_dir`.
- `evidence_items` contain `page`, `screenshot_path`, `rule_id`, `bbox`, `message`, `severity`, and `next_action`; API registration adds `screenshot_url` when a valid PNG exists.
- screenshot URL tokens are currently process-memory only.
- Rain theme has workflow/pdf/result board variables; morning is the theme that currently lacks explicit workflow/pdf/result board overrides.

## File Structure Target

Create or modify these files.

### Documentation

- Create: `docs/FRONTEND_BACKEND_CONTRACT.md`
  - Freezes API endpoints, payload fields, state names, coordinate system, screenshot lifetime, and UI text mapping ownership.
- Modify: `docs/superpowers/plans/2026-06-16-frontend-workbench-and-pdf-review-plan.md`
  - Add a short note that it has been superseded by this implementation plan.
- Keep: `docs/FRONTEND_UI_STYLE_GUIDE.md`
  - Source of typography and theme rules. Do not rewrite unless implementation reveals a missing project memory.

### Backend API

- Create: `scripts/article_api/static_routes.py`
  - Registers `/` and `/static/{path:path}` routes.
- Create: `scripts/article_api/render_review_jobs.py`
  - Builds render-review job payloads from uploaded DOCX and PDF records.
- Modify: `scripts/article_api/app.py`
  - Registers static frontend routes.
  - Wires render-review job route dependencies.
- Modify: `scripts/article_api/routes_uploads.py`
  - Adds `POST /uploads/{docx_upload_id}/render-review-jobs`.
- Modify: `scripts/article_api/schemas.py`
  - Adds request schema for render-review jobs.
- Modify: `scripts/article_api/jobs.py`
  - Allows a `render-verify` job operation.
- Modify: `scripts/article_api/job_runner.py`
  - Routes `render-verify` jobs to the existing render verification function.
- Modify: `scripts/article_api/job_artifacts.py`
  - Persists render evidence screenshots as job artifacts or stable artifact paths.
- Modify: `scripts/article_api/render_evidence.py`
  - Supports stable screenshot URLs tied to artifact paths, not only process-memory tokens.

### Frontend

- Create: `scripts/article_api/static/index.html`
  - App shell and semantic markup migrated from the approved prototype. No business logic.
- Create: `scripts/article_api/static/styles/tokens.css`
  - Typography, spacing, radius, surface, semantic color, and theme variables extracted from the approved prototype and style guide.
- Create: `scripts/article_api/static/styles/layout.css`
  - Workbench, result, history, PDF viewer, responsive layout migrated from the prototype and corrected for real data.
- Create: `scripts/article_api/static/styles/themes.css`
  - Four theme implementations migrated from the prototype: snow, rain, morning, ginkgo.
- Create: `scripts/article_api/static/js/api.js`
  - Fetch wrapper and typed API functions.
- Create: `scripts/article_api/static/js/state.js`
  - Small app state store.
- Create: `scripts/article_api/static/js/copy.js`
  - Student-facing labels and `rule_id -> label` mapping.
- Create: `scripts/article_api/static/js/pdfReview.js`
  - Evidence viewer state, image loading, bbox overlay, zoom, fallback rendering.
- Create: `scripts/article_api/static/js/app.js`
  - Screen composition and event wiring.
- Create: `scripts/article_api/static/assets/README.md`
  - Documents which prototype assets were migrated and why.
- Migrate approved assets from `.tmp/frontend-preview/` into `scripts/article_api/static/assets/`.

### Tests

- Create: `tests/test_article_static_frontend.py`
  - Static frontend route tests.
- Create: `tests/test_render_review_jobs.py`
  - Upload PDF to render-review job contract tests.
- Create: `tests/test_frontend_backend_contract.py`
  - Contract doc consistency checks for endpoint names and forbidden UI terms.
- Modify: `tests/test_article_api.py`
  - Update route expectations for static frontend and render-review job route.
- Modify: `tests/test_article_http_smoke.py`
  - Add live smoke for PDF upload -> render-review job -> evidence screenshot URL.
- Modify: `tests/test_packaging_metadata.py`
  - Stop asserting static frontend is absent once the frontend is finalized.

## API Contract To Freeze

Create `docs/FRONTEND_BACKEND_CONTRACT.md` with these exact sections.

```markdown
# Frontend Backend Contract

Date: 2026-06-16

## Frontend Entry

- `GET /` returns the student frontend.
- `GET /static/{path}` returns frontend assets.

## Uploads

- `POST /uploads/docx`
  - Form field: `file`
  - Returns: `upload_id`, `file_name`, `stored_path`, `workspace_dir`, `runtime_root`, `size_bytes`, `created_at`

- `POST /uploads/pdf`
  - Form field: `file`
  - Returns: `upload_id`, `file_name`, `stored_path`, `workspace_dir`, `runtime_root`, `size_bytes`, `created_at`

## Jobs

- `POST /uploads/{upload_id}/jobs/apply`
  - Creates a DOCX repair job from a DOCX upload.

- `POST /uploads/{docx_upload_id}/render-review-jobs`
  - Body: `{ "pdf_upload_id": "..." }`
  - Creates a background `render-verify` job.
  - Resolves `file_path` from the DOCX upload.
  - Resolves `rendered_pdf` from the PDF upload.

- `GET /jobs/{job_id}`
  - Returns `status`, `summary`, `artifacts`, and student-safe job metadata.

- `GET /jobs/{job_id}/result`
  - Returns the final operation result after success.

## Render Evidence Item

Each PDF review evidence item uses backend field names:

```json
{
  "page": 12,
  "screenshot_url": "/render-evidence/screenshot/...",
  "rule_id": "render.isolated_punctuation",
  "bbox": { "x": 0.12, "y": 0.74, "w": 0.72, "h": 0.06 },
  "message": "这一页底部有单独标点。",
  "severity": "warning",
  "next_action": "回到 Word 调整段落后重新导出 PDF。"
}
```

## Coordinate System

- `bbox` is normalized to the page image.
- `x`, `y`, `w`, and `h` are numbers from `0` to `1`.
- Frontend overlays use percentage positioning.
- `bbox = null` means the frontend must show an entire-page notice and must not draw a fake precise box.

## Screenshot Lifetime

- Screenshot URLs used by the frontend must survive process restart while the job artifact exists.
- If a screenshot is missing, the frontend shows a student-facing message: `页面截图已不可用 请重新复核 PDF`.

## Student Copy Ownership

- Backend owns factual fields: page, rule_id, message, severity, next_action.
- Frontend owns short display labels through `copy.js`.
- The UI must never display raw `rule_id`, `bbox`, job lifecycle words, endpoint paths, or contract terms in student-facing screens.

## PDF Review V1 Boundary

- Supported: page screenshot, problem list, bbox overlay, page fallback, zoom, previous/next issue.
- Not supported: text-span highlighting, single-character highlighting, direct PDF editing.
```

## Student Copy Rules

Use these labels in `scripts/article_api/static/js/copy.js`.

```js
export const forbiddenStudentTerms = [
  "/jobs/{id}",
  "queued",
  "running",
  "failed",
  "succeeded",
  "bbox",
  "rule_id",
  "page_image",
  "data contract",
  "profile",
  "mode",
  "preflight",
  "plan",
  "apply job",
  "JSON",
  "report artifact"
];

export const severityLabels = {
  error: "需要处理",
  warning: "建议确认",
  info: "提示"
};

export const renderRuleLabels = {
  "render.isolated_punctuation": "标点单独成行",
  "render.heading_orphan_at_page_bottom": "标题靠近页底",
  "render.formula_number_split_page": "公式编号分页",
  "render.toc_page_number_mismatch": "目录页码疑似错位",
  "render.toc_page_number_missing": "目录页码缺失",
  "render.blank_page": "出现空白页",
  "render.render_suspect": "页面版式需要确认",
  default: "版式位置需要确认"
};
```

## Responsive Layout Contract

Desktop PDF review:

```text
左侧问题列表 | 中间页面预览 | 右侧说明面板
底部工具条
```

Narrow viewport PDF review:

```text
顶部问题选择
页面预览
问题说明
底部工具条
```

Rules:

- At widths below `860px`, collapse to one column.
- Issue list becomes horizontal chips or a select-like list.
- Page preview remains the largest visual element.
- Toolbar remains sticky at the bottom of the PDF review panel.
- No text can overlap the page image or toolbar.

## Task 1: Freeze Contract And Mark Old Plan Superseded

**Files:**
- Create: `docs/FRONTEND_BACKEND_CONTRACT.md`
- Modify: `docs/superpowers/plans/2026-06-16-frontend-workbench-and-pdf-review-plan.md`
- Test: `tests/test_frontend_backend_contract.py`

- [x] **Step 1: Write the contract doc test**

Create `tests/test_frontend_backend_contract.py`.

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "FRONTEND_BACKEND_CONTRACT.md"
OLD_PLAN = ROOT / "docs" / "superpowers" / "plans" / "2026-06-16-frontend-workbench-and-pdf-review-plan.md"


def test_frontend_backend_contract_freezes_required_endpoints():
    text = CONTRACT.read_text(encoding="utf-8")

    required = [
        "GET /",
        "GET /static/{path}",
        "POST /uploads/docx",
        "POST /uploads/pdf",
        "POST /uploads/{docx_upload_id}/render-review-jobs",
        "GET /jobs/{job_id}",
        "GET /jobs/{job_id}/result",
    ]
    for item in required:
        assert item in text


def test_frontend_backend_contract_defines_pdf_review_boundary():
    text = CONTRACT.read_text(encoding="utf-8")

    assert "bbox = null" in text
    assert "must not draw a fake precise box" in text
    assert "text-span highlighting" in text
    assert "Not supported" in text


def test_old_visual_plan_points_to_contract_plan():
    text = OLD_PLAN.read_text(encoding="utf-8")

    assert "superseded" in text.lower()
    assert "2026-06-16-frontend-workbench-contract-implementation-plan.md" in text
```

- [x] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_frontend_backend_contract.py -q
```

Expected:

```text
FAILED
```

The failure should be because `docs/FRONTEND_BACKEND_CONTRACT.md` does not exist or the old plan lacks the superseded note.

- [x] **Step 3: Create `docs/FRONTEND_BACKEND_CONTRACT.md`**

Use the exact contract content from the "API Contract To Freeze" section above.

- [x] **Step 4: Add superseded note to old plan**

Add this block immediately after the title in `docs/superpowers/plans/2026-06-16-frontend-workbench-and-pdf-review-plan.md`.

```markdown
> Superseded: This visual/product plan is retained as context. Implementation must follow `docs/superpowers/plans/2026-06-16-frontend-workbench-contract-implementation-plan.md` and `docs/FRONTEND_BACKEND_CONTRACT.md` first.
```

- [x] **Step 5: Run the test**

Run:

```bash
python3 -m pytest tests/test_frontend_backend_contract.py -q
```

Expected:

```text
3 passed
```

## Task 2: Audit Prototype For Visual Migration

**Files:**
- Create: `docs/FRONTEND_PROTOTYPE_MIGRATION_AUDIT.md`
- Read: `.tmp/frontend-preview/system.html`
- Read: `docs/FRONTEND_UI_STYLE_GUIDE.md`

- [x] **Step 1: Create prototype audit document**

Create `docs/FRONTEND_PROTOTYPE_MIGRATION_AUDIT.md`.

```markdown
# Frontend Prototype Migration Audit

Date: 2026-06-16

## Purpose

This document records what must be migrated from `.tmp/frontend-preview/system.html` into the production frontend under `scripts/article_api/static/`.

## Keep

- Four-theme visual system: snow, rain, morning, ginkgo.
- Theme-specific cover title treatment.
- Fixed title line structure:
  - `辽宁大学`
  - `毕业论文`
  - `格式修正器`
- Dark glass panels with readable text.
- Product-tool layout direction.
- Screen concepts:
  - cover
  - workbench
  - feature map
  - PDF review
  - history
  - result
- Theme asset roles:
  - hero
  - workflow board
  - PDF board
  - result board
  - history board

## Do Not Keep

- Student-visible technical labels.
- Fake backend evidence.
- Hardcoded PDF highlight boxes.
- Placeholder text that says backend data is waiting.
- `.tmp` file paths in production code.
- White paper cards that conflict with dark glass themes.

## Theme Asset Findings

Fill this table during implementation:

| Theme | Hero | Workflow Board | PDF Board | Result Board | Action |
|---|---|---|---|---|---|
| snow |  |  |  |  |  |
| rain |  |  |  |  |  |
| morning |  |  |  |  |  |
| ginkgo |  |  |  |  |  |

## Prototype Strings To Replace

Fill this list from `rg` output:

- `preflight`
- `plan`
- `apply job`
- `profile`
- `mode`
- `data contract`
- `page_image`
- `rule_id`
- `bbox`

## Migration Rule

The prototype is the visual source. The production frontend must keep the look and feel while replacing fake content with real API state.
```

- [x] **Step 2: Populate asset table from prototype**

Run:

```bash
rg -n -- "--hero-image|--asset-board|--asset-workflow-board|--asset-pdf-board|--asset-result-board|data-theme=\\\"(snow|rain|morning|ginkgo)\\\"" .tmp/frontend-preview/system.html
```

Expected:

```text
Output includes theme variable definitions for snow, rain, morning, and ginkgo.
```

Update the table in `docs/FRONTEND_PROTOTYPE_MIGRATION_AUDIT.md`.

- [x] **Step 3: Populate forbidden prototype strings**

Run:

```bash
rg -n "preflight|apply job|profile|mode|data contract|page_image|rule_id|bbox|任务轮询|异步任务" .tmp/frontend-preview/system.html
```

Expected:

```text
Output lists prototype-only strings that must not appear as student-facing production copy.
```

Update the replacement list in `docs/FRONTEND_PROTOTYPE_MIGRATION_AUDIT.md`.

- [x] **Step 4: Review audit before coding**

Confirm the audit distinguishes:

- Visual elements to migrate.
- Fake data to replace.
- Theme assets to commit.
- Theme gaps to fix.

Do not continue to Task 3 until this audit exists.

## Task 3: Serve A Formal Static Frontend

**Files:**
- Create: `scripts/article_api/static_routes.py`
- Create: `scripts/article_api/static/index.html`
- Create: `scripts/article_api/static/styles/tokens.css`
- Create: `scripts/article_api/static/styles/layout.css`
- Create: `scripts/article_api/static/styles/themes.css`
- Create: `scripts/article_api/static/js/app.js`
- Modify: `scripts/article_api/app.py`
- Test: `tests/test_article_static_frontend.py`
- Modify: `tests/test_article_api.py`

- [x] **Step 1: Write static route tests that protect the migrated visual baseline**

Create `tests/test_article_static_frontend.py`.

```python
from fastapi.testclient import TestClient

from article_api.app import create_app


def test_static_frontend_serves_index_at_root():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "辽宁大学" in response.text
    assert "data-app=\"lnu-thesis-workbench\"" in response.text
    assert "data-screen=\"workbench\"" in response.text
    assert "data-screen=\"pdf-review\"" in response.text
    assert "data-screen=\"history\"" in response.text
    assert "data-screen=\"result\"" in response.text


def test_static_frontend_serves_css_and_js_assets():
    client = TestClient(create_app())

    css_response = client.get("/static/styles/tokens.css")
    js_response = client.get("/static/js/app.js")

    assert css_response.status_code == 200
    assert "--text-base: 16px" in css_response.text
    assert js_response.status_code == 200
    assert "initWorkbench" in js_response.text


def test_static_frontend_contains_four_theme_controls():
    client = TestClient(create_app())

    response = client.get("/")

    assert 'data-theme-choice="snow"' in response.text
    assert 'data-theme-choice="rain"' in response.text
    assert 'data-theme-choice="morning"' in response.text
    assert 'data-theme-choice="ginkgo"' in response.text
```

- [x] **Step 2: Run the failing tests**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py -q
```

Expected:

```text
FAILED
```

The failure should be 404 for `/` or missing static files.

- [x] **Step 3: Create static route module**

Create `scripts/article_api/static_routes.py`.

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


STATIC_ROOT = Path(__file__).resolve().parent / "static"


def register_static_frontend_routes(app: Any, *, file_response_cls: Any, http_exception_cls: Any) -> None:
    @app.get("/", include_in_schema=False)
    def frontend_index():
        index_path = STATIC_ROOT / "index.html"
        if not index_path.exists():
            raise http_exception_cls(status_code=404, detail="Frontend index is unavailable.")
        return file_response_cls(str(index_path), media_type="text/html; charset=utf-8")

    @app.get("/static/{asset_path:path}", include_in_schema=False)
    def frontend_asset(asset_path: str):
        requested = (STATIC_ROOT / asset_path).resolve()
        try:
            requested.relative_to(STATIC_ROOT.resolve())
        except ValueError as exc:
            raise http_exception_cls(status_code=404, detail="Frontend asset is unavailable.") from exc
        if not requested.exists() or not requested.is_file():
            raise http_exception_cls(status_code=404, detail="Frontend asset is unavailable.")
        return file_response_cls(str(requested))
```

- [x] **Step 4: Register static routes in app**

Modify `scripts/article_api/app.py`.

Add import:

```python
from article_api import static_routes
```

Inside `create_app()`, after `app = FastAPI(...)`, add:

```python
    static_routes.register_static_frontend_routes(
        app,
        file_response_cls=FileResponse,
        http_exception_cls=HTTPException,
    )
```

- [x] **Step 5: Create production frontend files by migrating the prototype structure**

Create `scripts/article_api/static/index.html`.

The file should be derived from `.tmp/frontend-preview/system.html`, but cleaned for production:

- Keep the screen concepts and theme controls.
- Keep the fixed title lines `辽宁大学` / `毕业论文` / `格式修正器`.
- Keep cover, workbench, PDF review, history, and result screens.
- Remove fake data that claims to be backend output.
- Replace student-visible technical terms with student-safe labels.
- Replace placeholder PDF contract text with real upload and evidence viewer containers.

Minimum structure:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>辽宁大学毕业论文格式修正器</title>
    <link rel="stylesheet" href="/static/styles/tokens.css">
    <link rel="stylesheet" href="/static/styles/themes.css">
    <link rel="stylesheet" href="/static/styles/layout.css">
  </head>
  <body data-app="lnu-thesis-workbench" data-theme="snow">
    <main class="app-shell">
      <section class="cover-screen" data-screen="cover">
        <div class="cover-copy">
          <h1 class="cover-title">
            <span>辽宁大学</span>
            <span>毕业论文</span>
            <span>格式修正器</span>
          </h1>
          <div class="cover-actions">
            <button class="button primary" type="button" data-action="enter-workbench">进入工具</button>
            <button class="button secondary" type="button" data-action="show-history">查看历史</button>
          </div>
          <div class="theme-switcher" aria-label="主题选择">
            <button type="button" data-theme-choice="snow">雪景</button>
            <button type="button" data-theme-choice="rain">雨后</button>
            <button type="button" data-theme-choice="morning">清晨</button>
            <button type="button" data-theme-choice="ginkgo">银杏</button>
          </div>
        </div>
      </section>
      <section class="screen" data-screen="workbench">
        <h2>上传论文</h2>
        <p>放入 docx 文件</p>
      </section>
      <section class="screen" data-screen="pdf-review">
        <h2>PDF 复核</h2>
        <p>上传导出的 PDF 查看页面问题</p>
      </section>
      <section class="screen" data-screen="history">
        <h2>历史记录</h2>
        <p>查看修正副本和复核结果</p>
      </section>
      <section class="screen" data-screen="result">
        <h2>修正结果</h2>
        <p>下载副本和审查报告</p>
      </section>
    </main>
    <script type="module" src="/static/js/app.js"></script>
  </body>
</html>
```

Create `scripts/article_api/static/styles/tokens.css`.

Extract token values from `.tmp/frontend-preview/system.html` where they match `docs/FRONTEND_UI_STYLE_GUIDE.md`. The initial token file may be smaller than the prototype, but it must keep the same reading direction: dark glass surfaces, readable text, 8px-or-less card radius, and themeable buttons.

```css
:root {
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  --text-xs: 12px;
  --text-sm: 14px;
  --text-base: 16px;
  --text-card-title: 17px;
  --text-panel-title: 28px;
  --text-hero: 40px;
  --line-readable: 1.65;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --radius-sm: 4px;
  --radius-md: 8px;
  --color-bg: #101820;
  --color-fg: rgba(255, 255, 255, .88);
  --color-muted: rgba(255, 255, 255, .68);
  --color-surface: rgba(12, 18, 24, .72);
  --color-border: rgba(255, 255, 255, .18);
  --color-primary: #d9f2ff;
  --color-primary-fg: #10202a;
  --shadow-panel: 0 20px 60px rgba(0, 0, 0, .28);
}
```

Create `scripts/article_api/static/styles/themes.css`.

Use the prototype themes as the baseline. Do not invent a new generic palette.

```css
[data-theme="snow"] {
  --color-bg: #101820;
  --color-primary: #d9f2ff;
  --color-primary-fg: #10202a;
}

[data-theme="rain"] {
  --color-bg: #111923;
  --color-primary: #9fc7d8;
  --color-primary-fg: #0e1a21;
}

[data-theme="morning"] {
  --color-bg: #172019;
  --color-primary: #e9dec7;
  --color-primary-fg: #1f241a;
}

[data-theme="ginkgo"] {
  --color-bg: #1b2116;
  --color-primary: #f1d07a;
  --color-primary-fg: #26210f;
}
```

Create `scripts/article_api/static/styles/layout.css`.

Port the prototype's product-tool layout direction. Do not create a marketing landing page.

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: var(--color-bg);
  color: var(--color-fg);
  font-family: var(--font-sans);
}

.app-shell {
  min-height: 100vh;
}

.cover-screen {
  min-height: 100vh;
  display: grid;
  align-items: center;
  padding: clamp(24px, 6vw, 72px);
}

.cover-title {
  display: grid;
  gap: 8px;
  margin: 0 0 28px;
  font-size: var(--text-hero);
  line-height: 1.12;
  letter-spacing: 0;
}

.cover-title span {
  display: block;
  white-space: nowrap;
}

.screen {
  min-height: 100vh;
  padding: clamp(24px, 5vw, 56px);
}

.cover-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.button {
  min-height: 44px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 0 18px;
  font: inherit;
  font-size: var(--text-base);
}

.button.primary {
  background: var(--color-primary);
  color: var(--color-primary-fg);
}

.button.secondary {
  background: var(--color-surface);
  color: var(--color-fg);
}
```

Create `scripts/article_api/static/js/app.js`.

```js
export function initWorkbench() {
  document.documentElement.classList.add("workbench-ready");
  document.addEventListener("click", (event) => {
    const themeButton = event.target.closest("[data-theme-choice]");
    if (!themeButton) return;
    document.body.dataset.theme = themeButton.dataset.themeChoice;
  });
}

initWorkbench();
```

- [x] **Step 6: Run static tests**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py -q
```

Expected:

```text
2 passed
```

## Task 4: Add Render Review Job Flow

**Files:**
- Create: `scripts/article_api/render_review_jobs.py`
- Modify: `scripts/article_api/schemas.py`
- Modify: `scripts/article_api/routes_uploads.py`
- Modify: `scripts/article_api/app.py`
- Modify: `scripts/article_api/jobs.py`
- Modify: `scripts/article_api/job_runner.py`
- Test: `tests/test_render_review_jobs.py`

- [x] **Step 1: Write route contract tests**

Create `tests/test_render_review_jobs.py`.

```python
from pathlib import Path

from fastapi.testclient import TestClient

from article_api.app import create_app


def test_render_review_job_requires_pdf_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTICLE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    client = TestClient(create_app())
    docx_path = tmp_path / "demo.docx"
    docx_path.write_bytes(b"docx")

    docx_response = client.post(
        "/uploads/docx",
        files={"file": ("demo.docx", docx_path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    docx_upload_id = docx_response.json()["upload_id"]

    response = client.post(
        f"/uploads/{docx_upload_id}/render-review-jobs",
        json={"pdf_upload_id": "missing-pdf"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["user_message"] == "没有找到这个 PDF 文件。"


def test_render_review_job_creates_background_render_verify_job(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTICLE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    client = TestClient(create_app())
    docx_path = tmp_path / "demo.docx"
    pdf_path = tmp_path / "demo.pdf"
    docx_path.write_bytes(b"docx")
    pdf_path.write_bytes(b"%PDF")

    docx_response = client.post(
        "/uploads/docx",
        files={"file": ("demo.docx", docx_path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    pdf_response = client.post(
        "/uploads/pdf",
        files={"file": ("demo.pdf", pdf_path.read_bytes(), "application/pdf")},
    )

    response = client.post(
        f"/uploads/{docx_response.json()['upload_id']}/render-review-jobs",
        json={"pdf_upload_id": pdf_response.json()["upload_id"]},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["operation"] == "render-verify"
    assert payload["status"] == "queued"
    assert payload["resolved_request"]["workflow_mode"] == "default_user"
    assert payload["resolved_request"]["rendered_pdf"].endswith(".pdf")
```

- [x] **Step 2: Run failing tests**

Run:

```bash
python3 -m pytest tests/test_render_review_jobs.py -q
```

Expected:

```text
FAILED
```

The failure should be 404 for the new render-review route.

- [x] **Step 3: Add schema**

Modify `scripts/article_api/schemas.py`.

```python
class UploadRenderReviewRequest(BaseModel):
    pdf_upload_id: str = Field(min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
```

- [x] **Step 4: Add payload builder**

Create `scripts/article_api/render_review_jobs.py`.

```python
from __future__ import annotations

from typing import Any, Callable


def build_render_review_job_kwargs(
    docx_upload_id: str,
    request: Any,
    *,
    resolve_upload_fn: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    docx_upload = resolve_upload_fn(docx_upload_id)
    pdf_upload = resolve_upload_fn(request.pdf_upload_id)

    if not str(docx_upload.get("file_name", "")).lower().endswith(".docx"):
        raise ValueError("请选择 Word 论文文件。")
    if not str(pdf_upload.get("file_name", "")).lower().endswith(".pdf"):
        raise ValueError("请选择从 Word 或 WPS 导出的 PDF 文件。")

    return {
        "file_path": docx_upload["stored_path"],
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
        "workflow_mode": "default_user",
        "rendered_pdf": pdf_upload["stored_path"],
        "source_display_name": docx_upload.get("file_name"),
        "pdf_display_name": pdf_upload.get("file_name"),
        "runtime_root": docx_upload.get("runtime_root") or pdf_upload.get("runtime_root"),
        "mode": "background",
    }
```

- [x] **Step 5: Add route**

Modify `scripts/article_api/routes_uploads.py`.

Add `UploadRenderReviewRequest` to imports.

Extend `register_upload_routes(...)` parameters:

```python
    render_review_job_kwargs_fn: Callable[[str, UploadRenderReviewRequest], dict[str, Any]],
```

Add route:

```python
    @app.post("/uploads/{docx_upload_id}/render-review-jobs", status_code=201)
    def create_render_review_job(docx_upload_id: str, request: UploadRenderReviewRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("render-verify", render_review_job_kwargs_fn(docx_upload_id, request))

        return call_with_http_error(action, raise_job_http_error)
```

- [x] **Step 6: Wire route in app**

Modify `scripts/article_api/app.py`.

Import:

```python
from article_api.render_review_jobs import build_render_review_job_kwargs
from article_api.schemas import UploadRenderReviewRequest
```

Add helper:

```python
def _render_review_job_kwargs(docx_upload_id: str, request: UploadRenderReviewRequest) -> dict[str, Any]:
    return build_render_review_job_kwargs(docx_upload_id, request, resolve_upload_fn=resolve_upload)
```

Pass into `routes_uploads.register_upload_routes(...)`:

```python
        render_review_job_kwargs_fn=lambda upload_id, request: _render_review_job_kwargs(upload_id, request),
```

- [x] **Step 7: Allow `render-verify` jobs**

Modify `scripts/article_api/job_runner.py`.

Add `render_verify_document` to imports from `article_engine` and extend operation map:

```python
from article_engine import apply_fix, normalize_document, render_verify_document, verify_document

RUNNERS = {
    "apply": apply_fix,
    "normalize": normalize_document,
    "verify": verify_document,
    "render-verify": render_verify_document,
}
```

Modify `scripts/article_api/jobs.py` anywhere operation allow-lists currently only include apply/normalize/verify so `render-verify` can be queued and executed. Keep artifact building minimal in Task 3; evidence persistence is Task 4.

- [x] **Step 8: Map missing PDF upload error**

If missing upload currently returns a generic `LookupError`, update `scripts/article_api/errors.py` so route errors for render-review missing PDF return:

```json
{
  "code": "upload_not_found",
  "user_message": "没有找到这个 PDF 文件。",
  "next_action": "请重新上传从 Word 或 WPS 导出的 PDF。"
}
```

- [x] **Step 9: Run render review job tests**

Run:

```bash
python3 -m pytest tests/test_render_review_jobs.py -q
```

Expected:

```text
2 passed
```

## Task 5: Persist Render Evidence Screenshots

**Files:**
- Modify: `scripts/article_api/render_evidence.py`
- Modify: `scripts/article_api/response_payloads.py`
- Modify: `scripts/article_api/job_artifacts.py`
- Modify: `scripts/article_api/routes_metadata.py`
- Test: `tests/test_article_http_smoke.py`
- Test: `tests/test_article_api.py`

- [x] **Step 1: Write persistence test**

Add to `tests/test_article_api.py`.

```python
def test_render_evidence_screenshot_url_can_resolve_from_artifact_path(tmp_path):
    from article_api.render_evidence import register_render_evidence_screenshots, resolve_render_evidence_screenshot

    screenshot = tmp_path / "page-1.png"
    screenshot.write_bytes(b"png")
    payload = {
        "job_id": "job-render-1",
        "evidence_items": [
            {
                "page": 1,
                "screenshot_path": str(screenshot),
                "rule_id": "render.isolated_punctuation",
                "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
                "message": "需要确认。",
                "severity": "warning",
                "next_action": "重新导出 PDF。",
            }
        ],
    }

    registered = register_render_evidence_screenshots(payload)
    url = registered["evidence_items"][0]["screenshot_url"]
    token = url.rsplit("/", 1)[-1]

    assert resolve_render_evidence_screenshot(token) == str(screenshot.resolve())
```

This test exists today in similar form, but keep or update it to cover the stable path behavior introduced here.

- [x] **Step 2: Define stable screenshot policy**

Implementation rule:

- When render verification runs inside a job, screenshots must live under the job runtime directory.
- Evidence items keep `screenshot_path`.
- `screenshot_url` may still use a token, but token registration must be reproducible from persisted job result when possible.
- If the process restarts, `GET /jobs/{job_id}/result` should re-register screenshot URLs from stored `screenshot_path`.

- [x] **Step 3: Re-register screenshots when returning job results**

Modify `scripts/article_api/jobs.py` so `get_job_result(job_id)` calls `register_render_evidence_screenshots(result)` before returning a render-verify result.

Use this pattern:

```python
if payload.get("operation") == "render-verify" and isinstance(result, dict):
    result = register_render_evidence_screenshots(dict(result))
```

- [x] **Step 4: Keep missing screenshots student-safe**

Modify `scripts/article_api/render_evidence.py` so missing paths remove `screenshot_url` and leave the item usable. Do not raise until the screenshot endpoint is called.

Student UI will display:

```text
页面截图已不可用 请重新复核 PDF
```

- [x] **Step 5: Run evidence tests**

Run:

```bash
python3 -m pytest tests/test_article_api.py -q -k "render_evidence or render_verify"
```

Expected:

```text
passed
```

## Task 6: Build Frontend API And State Modules

**Files:**
- Create: `scripts/article_api/static/js/api.js`
- Create: `scripts/article_api/static/js/state.js`
- Create: `scripts/article_api/static/js/copy.js`
- Modify: `scripts/article_api/static/js/app.js`
- Test: `tests/test_frontend_backend_contract.py`

- [x] **Step 1: Add forbidden UI term scan test**

Extend `tests/test_frontend_backend_contract.py`.

```python
def test_frontend_static_files_do_not_show_forbidden_student_terms():
    static_root = ROOT / "scripts" / "article_api" / "static"
    forbidden = [
        "/jobs/{id}",
        "queued",
        "running",
        "failed",
        "succeeded",
        "bbox",
        "rule_id",
        "page_image",
        "data contract",
        "profile",
        "mode",
        "preflight",
        "apply job",
        "report artifact",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in static_root.rglob("*")
        if path.suffix in {".html", ".css"}
    )
    for term in forbidden:
        assert term not in text
```

Note: JavaScript may contain backend field names as code identifiers, but HTML and CSS must not show them as student-facing copy.

- [x] **Step 2: Create API module**

Create `scripts/article_api/static/js/api.js`.

```js
async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : payload;
    const message = detail && detail.user_message ? detail.user_message : "操作没有完成";
    const nextAction = detail && detail.next_action ? detail.next_action : "请稍后重试";
    const error = new Error(message);
    error.nextAction = nextAction;
    error.status = response.status;
    throw error;
  }

  return payload;
}

export async function uploadDocx(file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson("/uploads/docx", { method: "POST", body });
}

export async function uploadPdf(file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson("/uploads/pdf", { method: "POST", body });
}

export async function createApplyJob(uploadId, body = {}) {
  return requestJson(`/uploads/${encodeURIComponent(uploadId)}/jobs/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export async function createRenderReviewJob(docxUploadId, pdfUploadId) {
  return requestJson(`/uploads/${encodeURIComponent(docxUploadId)}/render-review-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pdf_upload_id: pdfUploadId })
  });
}

export async function getJob(jobId) {
  return requestJson(`/jobs/${encodeURIComponent(jobId)}`);
}

export async function getJobResult(jobId) {
  return requestJson(`/jobs/${encodeURIComponent(jobId)}/result`);
}
```

- [x] **Step 3: Create state module**

Create `scripts/article_api/static/js/state.js`.

```js
const state = {
  theme: "snow",
  docxUpload: null,
  pdfUpload: null,
  activeJob: null,
  renderResult: null,
  activeEvidenceIndex: 0,
  highlightVisible: true,
  zoom: 1
};

const listeners = new Set();

export function getState() {
  return { ...state };
}

export function setState(patch) {
  Object.assign(state, patch);
  for (const listener of listeners) {
    listener(getState());
  }
}

export function subscribe(listener) {
  listeners.add(listener);
  listener(getState());
  return () => listeners.delete(listener);
}
```

- [x] **Step 4: Create copy module**

Create `scripts/article_api/static/js/copy.js` with the exact labels from "Student Copy Rules".

- [x] **Step 5: Wire app boot**

Modify `scripts/article_api/static/js/app.js`.

```js
import { subscribe } from "./state.js";

export function initWorkbench() {
  document.documentElement.classList.add("workbench-ready");
  subscribe(() => {});
}

initWorkbench();
```

- [x] **Step 6: Run contract tests**

Run:

```bash
python3 -m pytest tests/test_frontend_backend_contract.py -q
```

Expected:

```text
passed
```

## Task 7: Implement Workbench Screens And Student Copy

**Files:**
- Modify: `scripts/article_api/static/index.html`
- Modify: `scripts/article_api/static/styles/layout.css`
- Modify: `scripts/article_api/static/js/app.js`
- Modify: `scripts/article_api/static/js/api.js`

- [x] **Step 1: Replace one-screen placeholder with full app shell**

`index.html` must contain these panels:

```html
<section class="screen active" data-screen="cover"></section>
<section class="screen" data-screen="workbench"></section>
<section class="screen" data-screen="pdf-review"></section>
<section class="screen" data-screen="history"></section>
<section class="screen" data-screen="result"></section>
```

Visible student copy must use short lines:

```text
上传论文
放入 docx 文件
生成修正方案
先查看问题 再选择范围
上传 PDF
查看页面问题
下载修正副本
```

- [x] **Step 2: Add file inputs**

Use accessible hidden inputs paired with visible buttons:

```html
<input id="docx-input" class="visually-hidden" type="file" accept=".docx">
<button class="button primary" type="button" data-action="choose-docx">选择论文</button>

<input id="pdf-input" class="visually-hidden" type="file" accept=".pdf">
<button class="button secondary" type="button" data-action="choose-pdf">选择 PDF</button>
```

- [x] **Step 3: Wire upload handlers**

In `app.js`, wire:

```js
import { uploadDocx, uploadPdf, createRenderReviewJob } from "./api.js";
import { setState, getState } from "./state.js";

function bindUploads(root) {
  const docxInput = root.querySelector("#docx-input");
  const pdfInput = root.querySelector("#pdf-input");

  root.querySelector("[data-action='choose-docx']").addEventListener("click", () => docxInput.click());
  root.querySelector("[data-action='choose-pdf']").addEventListener("click", () => pdfInput.click());

  docxInput.addEventListener("change", async () => {
    const file = docxInput.files && docxInput.files[0];
    if (!file) return;
    setStatus("正在上传论文", "请稍候");
    const upload = await uploadDocx(file);
    setState({ docxUpload: upload });
    setStatus("论文已上传", "可以生成修正方案");
  });

  pdfInput.addEventListener("change", async () => {
    const file = pdfInput.files && pdfInput.files[0];
    if (!file) return;
    const current = getState();
    if (!current.docxUpload) {
      setStatus("请先上传论文", "PDF 需要和论文原稿对应");
      return;
    }
    setStatus("正在上传 PDF", "请稍候");
    const pdfUpload = await uploadPdf(file);
    const job = await createRenderReviewJob(current.docxUpload.upload_id, pdfUpload.upload_id);
    setState({ pdfUpload, activeJob: job });
    setStatus("PDF 已开始复核", "完成后可以查看页面问题");
  });
}
```

Also implement `setStatus(title, message)` to update a student-facing status panel. Do not expose raw error objects.

- [x] **Step 4: Add friendly error display**

In `app.js`, wrap event handlers:

```js
function showError(error) {
  setStatus(error.message || "操作没有完成", error.nextAction || "请检查文件后重试");
}
```

- [x] **Step 5: Run API and static tests**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py tests/test_frontend_backend_contract.py -q
```

Expected:

```text
passed
```

## Task 8: Implement PDF Evidence Viewer

**Files:**
- Create: `scripts/article_api/static/js/pdfReview.js`
- Modify: `scripts/article_api/static/js/app.js`
- Modify: `scripts/article_api/static/styles/layout.css`
- Test: `tests/test_frontend_backend_contract.py`

- [x] **Step 1: Create PDF review module**

Create `scripts/article_api/static/js/pdfReview.js`.

```js
import { renderRuleLabels, severityLabels } from "./copy.js";
import { getState, setState } from "./state.js";

function labelForRule(ruleId) {
  return renderRuleLabels[ruleId] || renderRuleLabels.default;
}

function evidenceItems(result) {
  return Array.isArray(result && result.evidence_items) ? result.evidence_items : [];
}

export function renderPdfReview(root, result) {
  const items = evidenceItems(result);
  const list = root.querySelector("[data-pdf-issues]");
  const stage = root.querySelector("[data-pdf-stage]");
  const detail = root.querySelector("[data-pdf-detail]");

  if (!items.length) {
    list.innerHTML = `<div class="empty-state"><b>没有发现需要确认的位置</b><span>可以保存复核结果</span></div>`;
    stage.innerHTML = `<div class="empty-state"><b>暂无页面问题</b><span>PDF 复核没有返回可定位项目</span></div>`;
    detail.innerHTML = "";
    return;
  }

  const state = getState();
  const activeIndex = Math.max(0, Math.min(state.activeEvidenceIndex, items.length - 1));
  const active = items[activeIndex];

  list.innerHTML = items.map((item, index) => `
    <button class="issue-chip ${index === activeIndex ? "active" : ""}" type="button" data-issue-index="${index}">
      <b>第 ${item.page || "-"} 页</b>
      <span>${labelForRule(item.rule_id)}</span>
    </button>
  `).join("");

  renderPageStage(stage, active);
  detail.innerHTML = `
    <h3>${labelForRule(active.rule_id)}</h3>
    <p>${active.message || "这个位置需要人工确认"}</p>
    <dl>
      <dt>严重程度</dt>
      <dd>${severityLabels[active.severity] || severityLabels.info}</dd>
      <dt>下一步</dt>
      <dd>${active.next_action || "回到 Word 调整后重新导出 PDF"}</dd>
    </dl>
  `;
}

function renderPageStage(stage, item) {
  if (!item.screenshot_url) {
    stage.innerHTML = `<div class="empty-state"><b>页面截图已不可用</b><span>请重新复核 PDF</span></div>`;
    return;
  }

  const box = item.bbox;
  const overlay = box
    ? `<span class="evidence-highlight" style="left:${box.x * 100}%;top:${box.y * 100}%;width:${box.w * 100}%;height:${box.h * 100}%"></span>`
    : `<span class="page-notice">这一页需要整体确认</span>`;

  stage.innerHTML = `
    <div class="pdf-page-frame">
      <img src="${item.screenshot_url}" alt="第 ${item.page || "-"} 页 PDF 截图">
      ${overlay}
    </div>
  `;
}

export function bindPdfReview(root, rerender) {
  root.addEventListener("click", (event) => {
    const issueButton = event.target.closest("[data-issue-index]");
    if (!issueButton) return;
    setState({ activeEvidenceIndex: Number(issueButton.dataset.issueIndex) || 0 });
    rerender();
  });
}
```

- [x] **Step 2: Add PDF viewer markup**

In `index.html`, the PDF review screen must include:

```html
<div class="pdf-review-grid">
  <aside class="glass pdf-issues" data-pdf-issues></aside>
  <section class="glass pdf-stage" data-pdf-stage></section>
  <aside class="glass pdf-detail" data-pdf-detail></aside>
  <div class="glass pdf-toolbar">
    <button type="button" data-action="previous-issue">上一处</button>
    <button type="button" data-action="next-issue">下一处</button>
    <button type="button" data-action="toggle-highlight">隐藏高亮</button>
  </div>
</div>
```

- [x] **Step 3: Add responsive CSS**

Add to `layout.css`.

```css
.pdf-review-grid {
  display: grid;
  grid-template-columns: minmax(210px, 280px) minmax(360px, 1fr) minmax(240px, 320px);
  grid-template-areas:
    "issues stage detail"
    "toolbar toolbar toolbar";
  gap: 16px;
}

.pdf-issues { grid-area: issues; }
.pdf-stage { grid-area: stage; }
.pdf-detail { grid-area: detail; }
.pdf-toolbar { grid-area: toolbar; }

.pdf-page-frame {
  position: relative;
  max-width: min(100%, 760px);
  margin: 0 auto;
}

.pdf-page-frame img {
  display: block;
  width: 100%;
  height: auto;
}

.evidence-highlight {
  position: absolute;
  border: 2px solid var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 24%, transparent);
  box-shadow: 0 0 0 999px rgba(0, 0, 0, .18);
}

.page-notice {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 16px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-fg);
  font-size: var(--text-base);
}

@media (max-width: 860px) {
  .pdf-review-grid {
    grid-template-columns: 1fr;
    grid-template-areas:
      "issues"
      "stage"
      "detail"
      "toolbar";
  }

  .pdf-issues {
    display: flex;
    overflow-x: auto;
    gap: 8px;
  }
}
```

- [x] **Step 4: Wire result rendering**

In `app.js`, after `getJobResult(jobId)` returns a render result:

```js
import { bindPdfReview, renderPdfReview } from "./pdfReview.js";

function renderCurrentPdfReview() {
  const root = document.querySelector("[data-screen='pdf-review']");
  const result = getState().renderResult;
  if (!root || !result) return;
  renderPdfReview(root, result);
}
```

Call `bindPdfReview(document, renderCurrentPdfReview)` during init.

- [x] **Step 5: Run frontend contract tests**

Run:

```bash
python3 -m pytest tests/test_frontend_backend_contract.py -q
```

Expected:

```text
passed
```

## Task 9: Port Approved Themes And Assets

**Files:**
- Modify: `scripts/article_api/static/styles/themes.css`
- Modify: `scripts/article_api/static/styles/tokens.css`
- Create/Copy: `scripts/article_api/static/assets/...`
- Create: `scripts/article_api/static/assets/README.md`

- [x] **Step 1: Copy only approved assets**

Copy from `.tmp/frontend-preview/` into `scripts/article_api/static/assets/`:

```text
assets/hero-v2-ginkgo.png
assets/hero-v2-rain.png
assets/hero-v2-morning.png
assets/hero-v3-snow.png
```

Copy board assets only after checking the paths in `.tmp/frontend-preview/system.html`.

Important correction:

- Rain has explicit workflow/pdf/result board variables.
- Morning needs explicit workflow/pdf/result board review first.

- [x] **Step 2: Document asset provenance**

Create `scripts/article_api/static/assets/README.md`.

```markdown
# Static Frontend Assets

These assets are committed for the local student frontend.

Source reference:

- `.tmp/frontend-preview/system.html`
- `.tmp/frontend-preview/assets/`
- `.tmp/frontend-preview/generated-ui-assets/`

Rules:

- `.tmp` remains scratch space and is not the production frontend.
- Add only assets that are used by `scripts/article_api/static/styles/themes.css`.
- Every theme must define hero, workflow, pdf, result, and history visual roles before release.
```

- [x] **Step 3: Define theme tokens**

`themes.css` must define for each theme:

```css
[data-theme="snow"] {
  --hero-image: url("/static/assets/hero-v3-snow.png");
  --theme-title-shadow: 0 12px 38px rgba(190, 224, 255, .28);
  --theme-title-accent: #d9f2ff;
}
```

Repeat for rain, morning, and ginkgo. Do not make the four themes differ only by button color.

- [x] **Step 4: Verify title rules**

The cover title must keep:

```html
<span>辽宁大学</span>
<span>毕业论文</span>
<span>格式修正器</span>
```

CSS must keep:

```css
.cover-title span {
  white-space: nowrap;
}
```

- [x] **Step 5: Run static frontend tests**

Run:

```bash
python3 -m pytest tests/test_article_static_frontend.py tests/test_frontend_backend_contract.py -q
```

Expected:

```text
passed
```

## Task 10: Add Empty Loading Error States

**Files:**
- Modify: `scripts/article_api/static/index.html`
- Modify: `scripts/article_api/static/js/app.js`
- Modify: `scripts/article_api/static/js/pdfReview.js`
- Modify: `scripts/article_api/static/styles/layout.css`

- [x] **Step 1: Add state containers**

Add these UI regions:

```html
<section class="status-panel glass" aria-live="polite" data-status-panel>
  <b data-status-title>准备开始</b>
  <span data-status-message>请先上传论文</span>
</section>
```

- [x] **Step 2: Implement exact student messages**

Use these messages:

```js
const friendlyMessages = {
  uploadFailed: ["上传没有完成", "请检查文件后重新选择"],
  pdfMissing: ["请先上传 PDF", "需要使用 Word 或 WPS 导出的 PDF"],
  renderFailed: ["PDF 复核没有完成", "请重新导出 PDF 后再试"],
  noIssues: ["没有发现需要确认的位置", "可以保存复核结果"],
  screenshotMissing: ["页面截图已不可用", "请重新复核 PDF"],
  networkError: ["连接本地服务失败", "请确认工具仍在运行"]
};
```

- [x] **Step 3: Add loading states**

When uploading or polling:

```text
正在上传论文
正在生成修正结果
正在复核 PDF
```

Do not show `queued`, `running`, or endpoint paths.

- [x] **Step 4: Run forbidden term scan**

Run:

```bash
python3 -m pytest tests/test_frontend_backend_contract.py -q
```

Expected:

```text
passed
```

## Task 11: Package And Release Metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_packaging_metadata.py`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/USER_GUIDE.md`

- [x] **Step 1: Update packaging test expectation**

Find the test that currently asserts these paths are absent:

```text
article_api/static/index.html
article_api/static/assets/lnu-emblem.jpg
```

Change it to assert the new static frontend files are included after finalization:

```python
assert "article_api/static/index.html" in names
assert "article_api/static/styles/tokens.css" in names
assert "article_api/static/js/app.js" in names
```

- [x] **Step 2: Update package data**

Modify `pyproject.toml` package-data configuration so the wheel includes:

```text
scripts/article_api/static/**/*.html
scripts/article_api/static/**/*.css
scripts/article_api/static/**/*.js
scripts/article_api/static/assets/**
```

Use the existing packaging style in `pyproject.toml`; do not introduce a new build system.

- [x] **Step 3: Update docs**

In `docs/USER_GUIDE.md`, add a short section:

```markdown
## 本地前端

启动本地 API 后，浏览器打开 `http://127.0.0.1:<port>/`。

PDF 复核需要先用 Word 或 WPS 导出 PDF，再上传到工具中查看页面问题。
```

In `docs/DEVELOPMENT.md`, add:

```markdown
## Frontend Workbench

The deliverable frontend lives in `scripts/article_api/static/`.
The `.tmp/frontend-preview/` directory remains the approved visual reference and asset source, but production code must not serve files from `.tmp`.
Run frontend checks with:

```bash
python3 -m pytest tests/test_article_static_frontend.py tests/test_frontend_backend_contract.py -q
```
```

- [x] **Step 4: Run packaging tests**

Run:

```bash
python3 -m pytest tests/test_packaging_metadata.py -q
```

Expected:

```text
passed
```

## Task 12: Browser Verification

**Files:**
- No code changes unless verification exposes issues.

- [x] **Step 1: Start local API**

Run from repo root:

```bash
python3 -m uvicorn article_api.app:create_app --factory --host 127.0.0.1 --port 4173
```

Expected:

```text
Uvicorn running on http://127.0.0.1:4173
```

If port 4173 is busy, use 4174 and record the actual URL.

- [x] **Step 2: Open in Browser or Playwright**

Open:

```text
http://127.0.0.1:4173/
```

Check:

- Cover snow desktop
- Cover rain desktop
- Cover morning desktop
- Cover ginkgo desktop
- Workbench desktop
- PDF review desktop
- Result desktop
- Cover mobile width
- PDF review mobile width

- [x] **Step 3: Console check**

Expected:

```text
No uncaught JavaScript errors
No missing static asset 404
```

- [x] **Step 4: Visual acceptance checklist**

Pass only if all are true:

- `辽宁大学` stays on one line.
- Four themes have distinct title treatments.
- Primary and secondary buttons follow current theme.
- Important body copy is at least 15px.
- PDF review collapses cleanly below 860px.
- No student-facing text shows forbidden backend terms.
- PDF viewer shows a real page image when `screenshot_url` exists.
- PDF viewer shows an entire-page notice when `bbox` is null.
- Missing screenshot shows `页面截图已不可用 请重新复核 PDF`.

## Task 13: Full Verification

**Files:**
- No code changes unless tests fail.

- [x] **Step 1: Run focused test suite**

Run:

```bash
python3 -m pytest \
  tests/test_frontend_backend_contract.py \
  tests/test_article_static_frontend.py \
  tests/test_render_review_jobs.py \
  tests/test_article_api.py \
  tests/test_article_http_smoke.py \
  tests/test_packaging_metadata.py \
  -q
```

Expected:

```text
passed
```

- [x] **Step 2: Run full test suite if focused tests pass**

Run:

```bash
python3 -m pytest -q
```

Expected:

```text
passed
```

- [x] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected:

```text
Only files touched by this plan are changed, plus pre-existing unrelated changes.
```

Do not revert unrelated user or parallel-agent changes.

## Definition Of Done

The goal is complete only when:

- `docs/FRONTEND_BACKEND_CONTRACT.md` exists and tests pass.
- `/` serves the formal student frontend from `scripts/article_api/static/index.html`.
- `.tmp/frontend-preview/` has been used as the visual baseline, but the deliverable frontend is served from `scripts/article_api/static/`.
- PDF upload can create a render-review job tied to a DOCX upload.
- Render evidence items can be displayed with screenshot and normalized overlay.
- `bbox = null` degrades to a whole-page notice.
- Student-facing screens do not expose backend/developer terms.
- Four themes are present and visually distinct.
- Cover title keeps `辽宁大学` on one line.
- Empty, loading, and error states are implemented with friendly Chinese copy.
- Static frontend files are packaged or explicitly included in release metadata.
- Focused tests pass.
- Browser verification passes on desktop and narrow viewport.

## Completion Evidence

Recorded on 2026-06-16 after preservation-first implementation:

- Focused suite passed: `92 passed in 33.47s`.
- Full suite passed: `951 passed, 1 xfailed in 96.47s`.
- Static route check passed: `/` plus 26 production static files returned 200.
- Browser desktop check passed at `http://127.0.0.1:4174/`: six screens, four themes, `.runway`, `.pdf-lens`, and `.result-hero` present; visible forbidden backend terms empty; console error logs empty.
- Browser narrow viewport check passed: six screens and four themes present; title line uses `nowrap`; visible forbidden backend terms empty; console error logs empty.
- Screenshot URL persistence check passed: render evidence screenshot URLs resolve from signed artifact-path tokens after clearing the in-memory token map, and raw file paths are rejected.

## Out Of Scope

- Character-level PDF highlighting.
- Direct PDF editing.
- Cloud accounts.
- Multi-user history sync.
- Reintroducing Microsoft Word automation as the primary student flow.
- Building a React/Vue app or adding a frontend bundler.
- Restoring `local_console.html` wholesale.

## Self-Review Notes

- The plan fixes the core issue in the previous visual plan by adding a frontend/backend contract before UI work.
- The plan does not assume `student_title` or `student_message` exists in backend payloads.
- The plan does not promise precise PDF text-span highlighting.
- The plan corrects the theme asset target: morning needs explicit board review; rain is not assumed missing.
- The plan defines narrow viewport PDF behavior before implementation.
- The plan includes failure, empty, loading, screenshot-missing, and network states.
