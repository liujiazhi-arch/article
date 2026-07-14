# Arbitration: Architecture Hardening

## Source Reviews

- `docs/superpowers/plans/2026-07-14-architecture-hardening-claude-review.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-codex-subagent-review.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-codex-execution-report.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-merged-plan.md`

## Findings Disposition

- Codex P1 frontend trust duplication：accepted。契约明确要求前端只消费 canonical eligibility。
- Codex P1 legacy TOC download：accepted。历史 adapter 是所有 status/result/download 路径的共享根边界，应在该处 fail closed。
- Codex P2 authorized corpus：accepted as `data-checkpoint`。没有数据授权，不实现假样本、不读取论文正文。
- Claude review：`unavailable: timeout`。用户明确批准不再重试并继续，不能作为独立通过证据。

## Repairs

- `scripts/article_api/static/js/pdfReview.js:24`：`isPdfEvidenceUsable` 收敛为只检查 `layout_decision_eligible === true`。
- `scripts/article_api/job_payloads.py:32`：历史 manual-PDF 降级同步设置 `toc_output_available = false`。
- `scripts/article_api/job_payloads.py:66`：从规范化响应移除 `toc-output` artifact，并把 `toc_finalization` 改为 blocked、unavailable、无 output path。
- `tests/test_frontend_pdf_closure_behavior.py:141`：覆盖 canonical eligibility 单一事实。
- `tests/test_render_review_jobs.py:83`：覆盖 status/list/result 降级、下载 404 和 SQLite 不改写。

## Verification

- RED：两条新增/修改测试均失败，分别为 frontend `false !== true` 和 legacy `toc_output_available` 仍为 true。
- GREEN：相同两条测试 `2 passed in 0.36s`。
- Focused suite：`python3 -m pytest -q tests/test_frontend_pdf_closure_behavior.py tests/test_render_review_jobs.py tests/test_article_static_frontend.py tests/test_article_api.py` -> `123 passed in 26.23s`。
- `node --check scripts/article_api/static/js/pdfReview.js`：通过。
- `python3 -m compileall -q scripts/article_api/job_payloads.py tests/test_render_review_jobs.py`：通过。
- `git diff --check origin/main`：通过。

## Architecture Pass

修复没有新增 trust 事实、下载特例路由或新抽象。前端只展示 canonical backend fact；历史兼容继续集中在现有 response adapter；下载端复用同一规范化结果。

## Spec Change Control

无规格范围变化。两项修复均直接落实既有 PDF trust 和 canonical backend ownership 约束。

## PRD / Master Spec / Slice Spec Impact

- PRD：无变化，仍服务使用 LNU 工作台的学生。
- Master Spec：canonical evidence 边界更严格，没有新架构层。
- Slice Spec：manual PDF -> content match -> eligibility -> review/download 主链闭合。

## Remaining Risks

- Fresh Claude review 未完成，已按用户明确指示降级继续。
- 真实 LNU corpus 仍等待数据授权。
- clean Windows + Word/WPS bundle 与人工版式验收未执行。
- coverage 中既有 SQLite `ResourceWarning` 不在本轮范围。
