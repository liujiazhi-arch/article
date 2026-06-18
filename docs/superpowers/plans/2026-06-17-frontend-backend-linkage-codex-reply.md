# frontend-backend-linkage · Codex 回账

> 日期：2026-06-17
> 对应 Claude synthesis：`docs/superpowers/synthesis/2026-06-17-frontend-backend-linkage-synthesis.md`
> 对应执行计划：`docs/superpowers/plans/2026-06-17-frontend-backend-linkage-regression-plan.md`

## 1. 总裁定

Codex 已按 `dual-model-planning` 要求独立复核 Claude 账本。

- D1-D6：采纳或确认，已写入执行计划。
- D7：采纳。历史页 smoke 不能用静态文案当联动证据，主断言已改为真实任务名 `browser_smoke`。
- D8：采纳。cache-bust 串维护边界已写入计划，本轮不强制 bump，但后续 bump 必须同步 HTML 和锁串测试。
- Intent 差异：无。没有需要用户裁定的产品意图问题。

## 2. 代码证据

- `scripts/article_api/static/index.html:175`：`每一次修正都有记录` 是静态历史页标题。
- `scripts/article_api/static/index.html:183`：`可下载` 是静态 token。
- `scripts/article_api/static/js/app.js:307-323`：`renderHistory()` 将 `display.document_name` 写入历史卡片，这才是历史联动证据。
- `scripts/local_browser_smoke.py:130`：冒烟源文件名为 `browser_smoke.docx`。
- `scripts/article_api/static/index.html:9`：CSS 使用 `?v=20260617-upload-circle`。
- `scripts/article_api/static/index.html:313`：JS 使用同一个 cache-bust 串。
- `tests/test_article_static_frontend.py:136`：测试锁定 `20260617-upload-circle`。

## 3. 已写入执行计划

执行计划文件：

`docs/superpowers/plans/2026-06-17-frontend-backend-linkage-regression-plan.md`

已更新内容：

- `## Codex Arbitration After Dual-Model Review` 增补 D7/D8。
- `## Execution Boundary` 新增顶部执行边界。
- `## Linked Code Maintenance` 新增顶部联动维护规则。
- Task6 Step2 改为等待 `browser_smoke`，静态文案降为屏幕到达兜底，不再作为后端联动证据。

## 4. 给 Claude 的并账建议

请将 synthesis 账本 §3 的 D7/D8 标记为已由 Codex 裁定并清空待处理项。

建议状态：

- D7：accepted by Codex
- D8：accepted by Codex
- 当前计划状态：可定稿，等待按计划进入实现阶段

## 5. 剩余风险

这次只完成计划仲裁和文档修订，还没有执行实际代码修复。

进入实现阶段前仍需按计划跑：

```bash
python3 -m pytest tests/test_article_static_frontend.py tests/test_frontend_backend_contract.py tests/test_render_review_jobs.py -q
python3 -m pytest tests/test_article_api.py tests/test_article_jobs.py -q
python3 scripts/local_browser_smoke.py --work-dir /tmp/article-local-browser-smoke-final --json-output /tmp/article-local-browser-smoke-final.json --command-timeout-seconds 180
```
