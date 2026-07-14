# 架构加固执行报告

## Skill / Rule Preflight

- `AGENTS.md`
- `/Users/apple/.codex/skills/baton/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/route-selection.md`
- `/Users/apple/.codex/skills/loop-engineering/references/artifact-protocol.md`
- `/Users/apple/.codex/skills/loop-engineering/references/lane-roles.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/references/strategic-loop-contract.md`
- `/Users/apple/.agents/skills/implement/SKILL.md`
- `/Users/apple/.agents/skills/code-review/SKILL.md`
- `/Users/apple/.codex/skills/rtk-token-optimizer/SKILL.md`

## Source

- 合并计划：`docs/superpowers/plans/2026-07-14-architecture-hardening-merged-plan.md`
- 交接状态：`.baton/2026-07-14-architecture-hardening-finalization.md`
- 审查基线：`origin/main@9a0bd4b7becc24c98f23949c5f3b9caca3e73afb`
- 当前已提交增量：`69aea02 refactor: finalize maintainable thesis workflow architecture`
- `claude_policy: required`

## Scope

本轮执行统一 LNU profile/runtime/capability metadata，收紧人工 PDF 内容匹配门禁，在响应层降级旧 manual-PDF 记录，并让前端只消费 canonical evidence。封面口径、发布证据和对应测试同步更新，现有前端视觉与交互保持不变。

明确未做：未读取用户论文正文；未构建或推送 Windows 包；未进入缺少已授权 corpus 保护的大范围 `_DEPS` 重构；未推送 Git 远端。

## Change Level / Spec Scope

- Change level：C2
- Spec scope：`master_spec_addendum`
- 产品方向仍为 LNU-only、人工导出 PDF、Vanilla JS + FastAPI/CLI + OOXML 主链。

## MVP / Mainline Impact

- `config/profiles/*.yaml` 是 LNU metadata 权威源；runtime 和 capability matrix 由 parity 测试约束。
- `scripts/thesis_tool/render_verify.py` 要求 manual PDF 同时满足用户确认和内容匹配才可形成版式结论。
- `scripts/article_api/job_payloads.py` 对缺少匹配证据的历史 manual-PDF 响应 fail closed，不改写 SQLite。
- `scripts/article_api/static/js/pdfReview.js` 只按后端 eligibility、source 和 match status 判断证据可用性。

## Changed Files

- 当前未提交实现：45 个已跟踪文件，`1342 insertions / 256 deletions`。
- 相对 `origin/main` 的完整审查面：83 个文件，`6175 insertions / 2432 deletions`，包含先前提交 `69aea02` 与当前工作树。
- 新增控制产物：合并计划、本文、两份独立 review、arbitration 和 final report。

## Task Status

- Slice A 规则事实统一：完成。
- Slice B PDF 可信度闭环：完成。
- Slice C 产品口径与小型前端风险：完成；未改变视觉方向。
- Slice D 效果与发布门禁：自动 smoke 完成；真实 LNU corpus 因无数据授权停在 `data-checkpoint`；Windows Word/WPS 人工验收未执行。
- Slice E 渐进式解耦：按计划跳过，原因是 Slice D 真实 corpus 门禁尚未建立。
- Slice F 验证：自动验证已完成；fresh 双审查、仲裁和提交在本报告之后执行。

## Verification

交接前已执行并记录：

- `python3 -m compileall -q scripts tests`：通过。
- 全部静态 JS `node --check`：通过。
- focused pytest：`172 passed`。
- full pytest：`1243 passed, 1 xfailed`。
- coverage：`87.79%`，高于项目 80% 门槛。
- `python3 scripts/local_browser_smoke.py --json-output /tmp/article-architecture-browser-smoke.json`：`status: ok`；console errors 0；1366x768 无横向溢出；PDF match `matched`；layout eligible `true`。
- `python3 scripts/release_smoke.py --json-output /tmp/article-release-smoke-architecture.json`：`status: ok`，service version `0.1.2`。
- `git diff --check`：通过。

最终提交前只在没有源码修复时重跑轻量状态与 diff 检查；若审查触发源码修复，则运行对应 focused tests，范围较广时再跑 full suite。

## Artifacts

- 浏览器：`/tmp/article-architecture-browser-smoke.json`
- release smoke：`/tmp/article-release-smoke-architecture.json`
- 合并计划：`docs/superpowers/plans/2026-07-14-architecture-hardening-merged-plan.md`
- 后续 review/arbitration/final artifacts 与本文同目录。

## Git State

- 分支：`main`，相对 `origin/main` ahead 1。
- 执行报告写入前：45 个计划内 tracked modifications，1 个未跟踪合并计划。
- 当前工作树属于本次架构加固，不覆盖、不回滚。

## Architecture Impact

没有新增规则 DSL、运行时 YAML I/O、状态库、DI 容器或并行事实源。改动沿用既有 profile loader、content matcher、job payload adapter 和静态前端模块边界。

## Known Gaps

- 未获得可读取、脱敏并提交真实 LNU 论文样本的授权，真实 corpus 保持 `data-checkpoint`。
- 未在 clean Windows + Word/WPS 环境完成 bundle 和人工版式验收。
- coverage 中既有 SQLite `ResourceWarning` 未在本轮扩大范围处理。
