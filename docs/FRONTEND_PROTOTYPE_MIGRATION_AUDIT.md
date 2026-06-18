# Frontend Prototype Migration Audit

Date: 2026-06-16

## Purpose

This document records what must be migrated from `.tmp/frontend-preview/system.html` into the production frontend under `scripts/article_api/static/`.

Evidence sources:

- `docs/superpowers/plans/2026-06-16-frontend-workbench-contract-implementation-plan.md` Task 2
- `.tmp/frontend-preview/system.html`
- `docs/FRONTEND_UI_STYLE_GUIDE.md`

## Keep

- Four-theme visual system: snow, rain, morning, ginkgo.
- Theme-specific cover title treatment.
- Fixed title line structure:
  - `辽宁大学`
  - `毕业论文`
  - `格式修正器`
- Dark glass panels with readable text.
- Product-tool layout direction.
- Student-facing screen concepts:
  - cover
  - workbench
  - feature map
  - PDF review
  - history
  - result
- Compact tool surface rather than a marketing landing page.
- Theme-specific typography mood:
  - snow: cold white, clear edges, high readability
  - rain: cold gray-blue, restrained, wet glass feel
  - morning: soft light, warm white, mist green
  - ginkgo: bookish, archive-like, warm gold and deep green
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
- Student-facing job lifecycle or backend terms such as `queued`, `running`, `failed`, `succeeded`, `bbox`, `rule_id`, `page_image`, `/jobs/{id}`, `profile`, `mode`, `preflight`, `plan`, `apply job`, `JSON`, and `data contract`.
- Prototype-only copy that describes backend wiring instead of helping the student decide the next step.

## Theme Asset Findings

Source command:

```bash
rg -n -- "--hero-image|--asset-board|--asset-workflow-board|--asset-pdf-board|--asset-result-board|data-theme=\"(snow|rain|morning|ginkgo)\"" .tmp/frontend-preview/system.html
```

| Theme | Hero | Workflow Board | PDF Board | Result Board | Action |
|---|---|---|---|---|---|
| snow | `./assets/hero-v3-snow.png` | `./generated-ui-assets/lnu-snow/workflow-board-v4/gpt-image-2-20260610-011202-1.png` | `./generated-ui-assets/lnu-snow/pdf-board-clean/gpt-image-2-20260610-clean-1.png` | `./generated-ui-assets/lnu-snow/result-board-clean/gpt-image-2-20260610-clean-1.png` | Migrate these snow assets and preserve matching focus variables. |
| rain | `./assets/hero-v2-rain.png` | `./generated-ui-assets/agent-rain/gpt-image-2-20260609-134546-1.png` | `./generated-ui-assets/agent-rain/gpt-image-2-20260609-135333-1.png` | `./generated-ui-assets/asset-boards/gpt-image-2-20260609-142122-1-2.png` | Migrate these rain assets. Keep the cold gray-blue internal board direction and do not fall back to warm ginkgo or morning boards. |
| morning | `./assets/hero-v2-morning.png` | Not explicitly defined in the morning theme. | Not explicitly defined in the morning theme. | Not explicitly defined in the morning theme. | The morning theme must either reuse its same-theme `--asset-board` (`./generated-ui-assets/asset-boards/gpt-image-2-20260609-142122-1.png`) for workflow/PDF/result boards with suitable overlays, or add missing same-theme workflow/PDF/result board assets. Do not invent asset paths. |
| ginkgo | `./assets/hero-v2-ginkgo.png` | `./generated-ui-assets/theme-expansion-20260609/gpt-image-2-20260609-201919-1.png` | `./generated-ui-assets/theme-expansion-20260609/gpt-image-2-20260609-202501-1.png` | `./generated-ui-assets/theme-expansion-20260609/gpt-image-2-20260609-203027-1.png` | Migrate the default ginkgo asset chain and keep its archive-like warm gold/deep green direction. |

Additional findings:

- Ginkgo is defined on `:root`, not as a separate `[data-theme="ginkgo"]` block.
- Rain and snow define complete workflow/PDF/result board variables.
- Morning defines `--asset-board` only, so any production migration must explicitly resolve the missing workflow/PDF/result board roles.
- The prototype uses `--asset-result-board` for history backgrounds, so history should be documented as either result-board reuse or a future same-theme history asset.

## Prototype Strings To Replace

Source commands:

```bash
rg -n "preflight|apply job|profile|mode|data contract|page_image|rule_id|bbox|任务轮询|异步任务" .tmp/frontend-preview/system.html
rg -n "preflight|\bplan\b|apply job|profile|mode|data contract|page_image|rule_id|bbox|任务轮询|异步任务" .tmp/frontend-preview/system.html
```

Prototype-only strings found in student-visible or near-student prototype areas:

- `异步任务` at `.tmp/frontend-preview/system.html:2980`
- `preflight` at `.tmp/frontend-preview/system.html:2990` and `.tmp/frontend-preview/system.html:3026`
- `plan` at `.tmp/frontend-preview/system.html:2991`
- `apply job` at `.tmp/frontend-preview/system.html:2992`
- `bbox 命中框` at `.tmp/frontend-preview/system.html:2090`
- `profile` at `.tmp/frontend-preview/system.html:3096`
- `mode` at `.tmp/frontend-preview/system.html:3097`
- `data contract` at `.tmp/frontend-preview/system.html:3103`
- `page_image` at `.tmp/frontend-preview/system.html:3109`
- `rule_id` at `.tmp/frontend-preview/system.html:3110`
- `bbox` at `.tmp/frontend-preview/system.html:3111`, `.tmp/frontend-preview/system.html:3126`, and `.tmp/frontend-preview/system.html:3127`

Replacement direction:

- Replace backend lifecycle terms with student-facing labels such as `处理进度`, `下一步提示`, and `需要你确认`.
- Replace raw evidence fields with display labels such as `页面截图`, `问题位置`, and `复核提示`.
- Replace placeholder contract language with real API state and short student-facing empty states.
- Keep CSS class names such as `.plan-preview` internal if needed, but do not expose `plan` as visible student copy.

## Migration Rule

The prototype is the visual source. The production frontend must keep the look and feel while replacing fake content with real API state.
