# Final Report: Architecture Hardening

## Final Status

架构加固实现与 P0/P1 仲裁已完成，可以提交。

规则 metadata、manual-PDF trust、legacy history、静态目录下载和前端 evidence ownership 已收敛到既有权威边界。没有读取用户论文正文，没有构建或推送 Windows 包，没有推送 Git 远端。

Fresh Claude review 因超时未形成 artifact；用户明确要求停止 Claude 联动并批准继续。该项记录为 degraded continuation，不记为审查通过。

## Changed Files

- Profile/runtime/capability parity：`config/profiles/`、`config/capability_matrix.md`、`scripts/thesis_rules/lnu_runtime.py` 与对应测试。
- PDF trust 与历史兼容：`scripts/thesis_tool/render_verify.py`、`scripts/article_api/job_payloads.py`、`scripts/article_api/jobs.py` 与对应测试。
- 前端 canonical adapter：`scripts/article_api/static/js/pdfReview.js` 及相关静态前端测试；现有视觉和交互不变。
- 发布证据：local browser/release/Windows smoke 脚本与测试；未生成 Windows bundle。
- 文档与控制产物：合并计划、execution report、Claude unavailable record、Codex review、arbitration、本文。

## Review Dispositions

- P0：0。
- P1 frontend re-derived trust：accepted and fixed。
- P1 legacy unsafe `toc-output` download：accepted and fixed。
- P2 authorized LNU corpus：accepted as `data-checkpoint`。
- Claude review：unavailable after timeout；user-approved degraded continuation。

## Verification

架构加固实现完成后、交接前已验证：

- focused pytest：`172 passed`。
- full pytest：`1243 passed, 1 xfailed`。
- coverage：`87.79%`，高于 80%。
- Python compileall、全部静态 JS `node --check`、`git diff --check`：通过。
- browser smoke：`/tmp/article-architecture-browser-smoke.json` -> `status: ok`，console errors 0，1366x768 无横向溢出，PDF content `matched`，layout eligible true。
- release smoke：`/tmp/article-release-smoke-architecture.json` -> `status: ok`，service version `0.1.2`，HTTP/render smoke 正常。

P1 修复后已验证：

- TDD RED：两条测试先按预期失败。
- TDD GREEN：`2 passed in 0.36s`。
- 受影响完整套件：`123 passed in 26.23s`。
- 修改后的 JS `node --check`、Python compileall、`git diff --check origin/main`：通过。
- 无残留 Claude review、Playwright 或 headless Chromium 进程。

## Artifact Paths

- `docs/superpowers/plans/2026-07-14-architecture-hardening-merged-plan.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-codex-execution-report.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-claude-review.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-codex-subagent-review.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-arbitration.md`
- `docs/superpowers/plans/2026-07-14-architecture-hardening-final-report.md`

## Git State

- Branch：`main`，提交前相对 `origin/main` ahead 1。
- 当前工作树仅包含本次架构加固与上述控制产物。
- 本报告写入后执行 staged diff 检查和当前分支提交；最终 commit SHA 以提交后的 `git rev-parse HEAD` 为准。
- 不 push。

## Residual Risks

- 未完成 fresh Claude review；这是用户明确批准的质量门降级。
- 未获授权的真实 LNU corpus 仍为空，不宣称已通过真实论文效果门禁。
- clean Windows + Word/WPS bundle/人工验收仍是发布前检查点。
- 既有 SQLite `ResourceWarning` 留待独立任务处理。
