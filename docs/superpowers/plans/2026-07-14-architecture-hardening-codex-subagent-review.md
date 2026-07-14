# Codex Independent Review: Architecture Hardening

## Skill / Rule Preflight

两名只读审查者分别读取 `AGENTS.md`、`code-review/SKILL.md`、`loop-engineering/SKILL.md` 和 `artifact-protocol.md`。Spec 审查者另读取合并计划；两者均未读取 Claude 或彼此的 review 结论。

## Source

- Fixed point：`origin/main@9a0bd4b7becc24c98f23949c5f3b9caca3e73afb`
- Commit list：`69aea02 refactor: finalize maintainable thesis workflow architecture`
- Diff：`git diff origin/main`，包含 HEAD 与当前未提交工作树。
- Spec：`docs/superpowers/plans/2026-07-14-architecture-hardening-merged-plan.md`
- Standards：`AGENTS.md` 与 code-review smell baseline。
- `claude_policy: required`；本 review 与 Claude lane 独立。

## Findings

### P1 Frontend Re-derived Backend Trust

Review snapshot：`scripts/article_api/static/js/pdfReview.js:24` 在 `layout_decision_eligible` 之外再次按 evidence source 和 `pdf_content_match_status` 判断证据可用性。

Evidence：`docs/FRONTEND_BACKEND_CONTRACT.md:39` 要求前端消费 canonical `render_evidence_status` 和 `layout_decision_eligible`，不得重新推导 trust。

Impact：后端已判可用的 canonical payload 仍可能被前端阻断，形成跨层事实漂移。

Smallest action：`isPdfEvidenceUsable` 只读取 canonical eligibility，并用行为测试锁定。

### P1 Legacy Manual-PDF TOC Artifact Remained Downloadable

Review snapshot：`scripts/article_api/job_payloads.py:44` 只降级 metadata；`scripts/article_api/jobs.py:1067` 通过规范化后的 artifact 列表提供下载。

Evidence：旧 manual-PDF 记录可能仍携带 `toc_finalization.available = true` 和 `toc-output` artifact。仅降级 layout status 不会撤销该衍生文件。

Impact：学生仍可能下载由未验证 PDF 页码生成的静态目录，绕过新的内容匹配门禁。

Smallest action：在统一历史响应 adapter 中删除不可信 `toc-output` artifact，并将 toc finalization 标记为 blocked；下载端继续复用该 adapter。

### P2 Authorized LNU Corpus Checkpoint

Evidence：合并计划 `:188-192` 要求至少 3 个经授权、脱敏、可提交的 LNU 样本；`tests/real_docx_samples/manifest.yaml` 当前没有这些样本。

Impact：不能宣称真实 Word/WPS 效果门禁已经完成。

Action：保持 `data-checkpoint`，不读取用户论文，不进入大范围 `_DEPS` 重构。

## Criteria Check

- P0：0。
- P1：2，均需在提交前修复。
- P2：1，为已计划的数据授权检查点。
- Spec 审查运行相关 focused tests：`137 passed`。
- 两名审查者均运行 `git diff origin/main`、`git log origin/main..HEAD --oneline` 和 `git diff --check origin/main`；Standards 审查未运行长测试。
- 没有发现用户论文或 Windows 二进制进入 diff。

## Lifecycle

- Standards lane：fresh、只读、completed、`next_expected_use: none`。
- Spec lane：fresh、只读、completed、`next_expected_use: none`。
- 两个 lane 无文件写权限；本 artifact 由主任务按两份独立返回结果汇总，不改变 finding 的严重度。
