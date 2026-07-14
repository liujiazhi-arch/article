# 论文格式工具架构加固合并计划

## Source Plans

- 用户已确认：完整列出计划并按计划执行；沿用此前推荐路线。
- Codex 架构审查：当前 `main@69aea02`，重点风险为规则元数据漂移、PDF trust、真实 LNU 效果证据和 `thesis_fix` 全局依赖。
- Claude Opus pressure test：会话 `0f74674c-7edf-411a-a5cc-d15d07583aba`；经代码证据纠正后，将规则单一事实源、PDF trust、真实 LNU corpus 排为前三。
- 独立 Codex 前端/后端只读审查：格式雷达模块本身健康；后端发现 6 条 severity 和 1 条 check_level 已漂移。

## Skill / Rule Preflight

- `AGENTS.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/route-selection.md`
- `/Users/apple/.codex/skills/loop-engineering/references/artifact-protocol.md`
- `/Users/apple/.codex/skills/loop-engineering/references/lane-roles.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/references/strategic-loop-contract.md`
- `/Users/apple/.agents/skills/implement/SKILL.md`
- `/Users/apple/.agents/skills/tdd/SKILL.md`
- `/Users/apple/.agents/skills/tdd/tests.md`
- `/Users/apple/.agents/skills/tdd/mocking.md`
- `/Users/apple/.codex/skills/frontend-architecture-rules/SKILL.md`（此前本任务已读取）
- `/Users/apple/.codex/skills/rtk-token-optimizer/SKILL.md`（此前本任务已读取）

## Strategic Loop Contract

```yaml
strategy:
  loop_id: thesis-architecture-hardening-20260714
  goal: 让评分、修复建议、PDF 证据和真实论文效果使用同一套可验证事实，同时保持现有前端样式与交互。
  end_state: 规则语义无漂移；错误 PDF 不可形成版式结论；真实样本可以阻止效果回归；核心模块不再继续增加隐藏全局依赖。
  good_enough: 当前已证实的 P1 缺陷修复并有 RED/GREEN 证据；真实样本门禁可用或因隐私授权明确停在检查点；全量测试、桌面浏览器和发布检查通过；独立双审查无未处理 P0/P1。
  non_goals: React/Vue 迁移；状态库；DI 容器；新规则 DSL；机械拆 CSS；删除大型测试；恢复自动 Word 导出为默认路径。
  user_value: 学生看到的分数、雷达、修复范围和 PDF 标注不会因内部元数据漂移或传错 PDF 而误导。
  evidence_of_success: targeted RED/GREEN；full pytest；错误/正确 PDF 行为测试；桌面浏览器控制台与关键流程；Windows bundle/release smoke；独立审查与仲裁记录。
  stop_condition: 完成证据齐全并提交；若需要读取、派生或提交用户论文内容，先停在隐私/数据归属检查点；若真实样本门禁未建立，不进入大范围 service-locator 重构。
  user_checkpoints: 用户已确认推荐架构路线；真实论文样本的读取、脱敏与提交仍需单独的数据授权证据。
operation:
  route_tier: T3
  route_justification: 同时改变规则数据归属、前后端 PDF 结论和发布证据，需要独立规划/审查；单一清单不足以控制语义回归。
  change_level: C2
  spec_scope: master_spec_addendum
  prd_spec_alignment:
    prd:
      target_user: 使用网页工作台优化辽宁大学本科论文格式的学生
      problem: 当前内部事实漂移和证据门禁不足可能造成错误评分或错误 PDF 结论
      final_effect: 修复建议真实、PDF 来源可核对、发布效果有样本证据
      user_value: 少走人工排查弯路且不会被界面误导
      mvp_boundary: LNU-only、人工导出 PDF、现有静态前端与 FastAPI/CLI 主链
      non_goals: 多学校规则平台、在线 Office、自动替代最终人工验收
      success_signals: 语义 parity、PDF mismatch 阻断、真实样本回归、Windows 验收证据
    master_spec:
      overall_route: 事实校准 -> 效果门禁 -> 渐进解耦
      architecture_boundaries: profile 元数据；audit/plan；render evidence；frontend view；fix orchestration
      data_or_adapter_strategy: 复用现有 YAML、content matcher、manifest 和测试 harness
      connector_or_backend_levels: 本地只读/本地文件处理；不调用外部 provider
      sequencing: 产品正确性先于内部重构
      project_risks: 私人论文数据、Word/WPS 差异、OOXML 行为回归
    slice_spec:
      primary_flow: DOCX upload -> plan -> scoped apply -> manual PDF upload -> render review -> result
      state_contracts: profile metadata 与 canonical PDF summary 是唯一业务事实
      data_or_adapter_contracts: YAML LNU metadata；existing content matcher；existing job/result schema
      ui_surfaces: format radar、scope plan、PDF review；现有视觉不变
      integration_level: local guarded mutation
      technical_risks: score drift、wrong-PDF eligibility、global dependency initialization
      verification: public runtime/API/module seams plus full/browser/release gates
  six_interfaces:
    goal: 修复已证实缺陷并在效果门禁后渐进解耦
    state: git HEAD/status、本计划、测试输出、执行/审查报告
    context: AGENTS、代码路径、Claude/Codex审查证据、用户已确认路线
    act: 修改仓库源码/测试/文档；运行本地测试浏览器和打包检查；不得读取或提交未授权论文正文
    capture: RED/GREEN命令、diff、浏览器证据、full suite、review artifacts、commit SHA
    stop: completion criteria 全部满足；真实数据授权或破坏性/外部操作前停
  lanes:
    - name: main-execution
      role: execution/integration
      decision_rights: 计划内最小实现与集成
      write_scope: 当前仓库计划、源码、测试、文档
      output_artifact: 2026-07-14-architecture-hardening-codex-execution-report.md
    - name: codex-review
      role: fresh independent review
      decision_rights: 只读 findings
      write_scope: review artifact only
      output_artifact: 2026-07-14-architecture-hardening-codex-subagent-review.md
    - name: claude-review
      role: fresh independent review
      decision_rights: 只读 findings
      write_scope: review artifact and done marker only
      output_artifact: 2026-07-14-architecture-hardening-claude-review.md
  state_sources: git、本文、后续 execution/review/arbitration artifacts
  context_pack: 本计划 + 精确 diff + 关键完整函数 + 测试输出
  allowed_actions: plan内编辑、测试、浏览器验证、独立审查、提交
  capture_required: 命令真实输出、文件行号、截图/控制台、git状态
  expected_artifacts: merged plan、execution report、两份 review、arbitration、final report
  claude_policy: required
  required_claude_artifact: fresh Claude review artifact
  fallback_if_claude_unavailable: 记录 unavailable 并停在用户检查点，不把旧 planning session 当独立 review
  check_after: 5-8 minutes for review; targeted checks after every TDD slice
  deadline: 15 minutes for each bounded review; active execution may continue while producing evidence
  blocker_signal: plan-gap、真实样本需数据授权、P0/P1 review finding、destructive/external action
```

`checkpoint_resolved_by: manager`：用户已在上一轮看到推荐路线，并明确要求列出完整计划后执行；本轮不改变该路线。

## Change Level / Spec Scope

- C2：收紧现有持久业务契约和架构边界，不改变 LNU-only 产品方向。
- 以本计划作为 Master Spec bounded addendum；不重写历史 PRD/路线文档。

## PRD / Master Spec / Slice Spec Alignment

- 产品主线保持：DOCX 审查/修复，学生用 Word/WPS 人工导出 PDF，再在网页查看真实页面证据。
- 正确性事实由后端提供；前端只展示，不重算评分或证据可信度。
- 深层解耦必须有行为保持门禁，不能以文件行数作为完成标准。

## MVP Boundary

- 只支持 `lnu-checker-2026`。
- 保留 Vanilla JS、FastAPI、现有 CLI 和 OOXML 引擎。
- 封面是显式选择的固定模板能力，不宣称可自动审查合规。
- PDF 仍由用户人工从 Word/WPS 导出。

## Core Mainline

```text
DOCX
  -> profile-backed audit/score
  -> scope plan / format radar
  -> selected apply
  -> user exports PDF
  -> user confirms + content matcher
  -> canonical render evidence
  -> PDF review UI / result
```

## Accepted From Claude

- 真实 LNU 效果 corpus 必须先于大范围 `_DEPS` 重构。
- React、状态库、DI 容器、机械拆 CSS 和删除大型测试都不需要。
- 封面问题是审查/修复/文档口径冲突，不是“完全未实现”。

## Accepted From Codex

- 规则 metadata drift 是最高优先的当前产品缺陷。
- PDF trust 必须复用已有 content matcher，不能仅信 checkbox。
- 格式雷达模块本身不需要重写；前端只需收回重复业务推导和统一 module identity。
- Windows 打包结构基本健康，缺口是实际 Word/WPS 效果证据。

## Rejected

- 重写为 React/Vue。
- 引入 Redux/Zustand、DI container、operation factory 或第二套 schema/rule DSL。
- 为行数拆 `layout.css` 或删除大型测试文件。
- 把未经内容匹配的纯白 PDF smoke 当作真实版式证明。

## Third Path Decisions

- YAML profile 成为 LNU 的规范 metadata 权威源；Python 继续拥有 checker 绑定和必要的稳定短名称，避免把执行函数塞入 YAML。
- runtime 和 capability matrix 保持快速、可读的本地镜像，但必须被全字段 parity 测试约束；不增加运行时 YAML I/O 或代码生成器。
- service locator 不一次性消灭：先建立效果门禁，再逐模块删除 key；不新增替代容器。
- 真实样本使用现有 intake/manifest 路径；没有授权数据时不制造“看起来像真实”的占位 corpus。

## Final Tasks

### Slice A — 规则事实统一

1. RED：增加 runtime severity、profile check_level、capability action 的语义 parity 测试。
2. GREEN：按 profile 规范值校准 LNU runtime/action 镜像，保留现有 checker 映射；parity gate 阻止以后静默漂移。
3. 更新能力矩阵的漂移项并验证 rule ID/scope/autofix 契约。

### Slice B — PDF 可信度闭环

1. RED：错误 PDF 即使用户确认也不能 `layout_decision_eligible`。
2. GREEN：在 manual PDF canonical summary 前复用已有 DOCX/PDF content matcher。
3. 保持正确 PDF、Word authoritative render 和未确认 PDF 的既有语义。
4. 前端只消费 canonical status + eligibility；历史 payload 兼容集中在现有 adapter。

### Slice C — 口径与小型前端风险

1. scope plan 明确区分“规则未发现问题”和“该范围不自动审查”，封面不得暗示 clean compliance。
2. 根 `CLAUDE.md` 只指向权威 `AGENTS.md`，删除重复架构事实。
3. 移除内部 ES module import query，顶层资源版本策略保持现状。
4. 保留现有视觉、交互、format radar 和 CSS。

### Slice D — 效果与发布门禁

1. 复用 `tests/real_docx_samples` intake/manifest，不新建 corpus 框架。
2. 最少 3 个经授权、脱敏、可提交的 LNU 最小样本：Word目录/封面、WPS图表/分节、公式/页码。
3. 每个样本记录 audit -> apply -> verify -> PDF 的已知预期和不应改变项。
4. release smoke 使用与 DOCX 内容一致的 PDF；Windows 人工检查覆盖 `.bat`、Word/WPS 导出和网页复核。
5. 若需要使用用户论文数据，先停在授权检查点；可以继续与数据无关的验证。

### Slice E — 渐进式解耦

1. 只有 Slice D 效果门禁可用后开始。
2. 从 `thesis_fix/page_footer.py` 开始直接 import 已有 helper，删除对应 `_DEPS` key。
3. 逐模块处理 `toc.py`、`tables_figures.py`、`lnu_postpasses.py`；每轮都运行 focused + full tests。
4. 最终目标是 `fix_docx` 只编排；不以本轮强行删除全部 registry 为完成条件，若继续删除会扩大风险则停止并记录剩余 key。

### Slice F — 验证、审查、仲裁和提交

1. focused tests、全量 pytest、coverage（项目现有方式可用时）、py_compile/静态检查。
2. 1440x900 和 1366x768 桌面浏览器流程与控制台检查；显式清理自动化浏览器进程。
3. Windows bundle/release verifier 与可运行 smoke。
4. fresh Codex review 与 fresh Claude review 独立进行。
5. 仲裁全部 P0/P1；修复后重跑相关验证。
6. 提交当前分支，不自动推送，除非用户另行要求。

## Verification

```bash
python3 -m pytest -q <focused tests>
python3 -m pytest -q
python3 -m pytest --cov=scripts --cov-report=term-missing
python3 scripts/verify_release_artifact.py dist/lnu-thesis-local-windows.zip
```

浏览器验证使用现有 Browser/Playwright 路径；必须关闭本轮创建的 page/context/browser 并确认无 headless Chromium 残留。

## Optional / Skip Rules

- 没有经授权的真实论文样本：Slice D 标记 `data-checkpoint`，不得提交私人正文或伪造真实门禁。
- 现有 coverage 命令/依赖不可用：记录未验证，不新增 coverage 依赖。
- `_DEPS` 某模块直接 import 会形成新循环：停止该模块，保留 registry key 并记录具体 import cycle；不得新增容器绕过。
- CSS token 迁移没有用户可见收益且不是当前缺陷，本轮跳过。

## Completion Criteria

- 规则 semantic parity 无漂移，现有 6+1 项全部被测试捕获。
- 传错 PDF 不能形成版式结论；正确人工 PDF 和 authoritative render 保持工作。
- 格式雷达、scope plan、PDF review 只展示 canonical backend facts。
- 封面明确为显式人工选择的模板修复能力，不显示为已自动审查合格。
- LNU corpus 门禁通过，或因缺少明确数据授权在独立检查点诚实停住且不进入高风险深重构。
- 所有可执行验证通过；独立双审查无未处理 P0/P1。
- 工作树只有计划内改动；提交成功并报告 commit SHA。
