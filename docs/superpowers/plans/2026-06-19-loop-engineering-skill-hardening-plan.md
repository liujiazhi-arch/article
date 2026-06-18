# Loop Engineering Skill Hardening Plan

date: 2026-06-19
target_skill: `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
source_context:
- `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`
- `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`

## 1. 结论

当前 `loop-engineering` 的方向是对的。它已经不是普通的开发流程说明，而是在形成一套可复用的多智能体编排方法：

- 多 lane 分工
- Codex / Claude 跨模型计划和审查
- Dispatcher 物理投递
- 经理Agent做历史、状态和恢复
- thread ledger 记录跨线程消息
- worklog 记录每个 lane 的实际工作
- baton 处理上下文风险和恢复
- arbitration 用证据裁决模型或 lane 之间的分歧

但它还没有成熟到可以稳定约束未来 Agent 的程度。最大问题不是缺少内容，而是几个关键控制点仍是原则性描述，没有变成可验证协议：

- 入口判断不够快，Agent 容易直接套完整五步流程。
- Claude 使用没有显式策略字段，容易被跳过或形式主义调用。
- Dispatcher 和 lane 的 Claude 边界还不够硬，容易回到“调度Agent替所有 lane 跑 Claude”的模式。
- 已经踩过的失败模式没有变成 forward-test 场景。
- `SKILL.md` 当前约 461 行，继续堆模板会接近 `skill-creator` 建议的 500 行警戒线。

本轮建议做“小而关键的 hardening”，不是大重写。第一轮只改 `SKILL.md` 的核心控制点；模板、长示例、完整协议可以后续再拆到 `references/`。

## 2. 设计原则

### 2.1 不把 Claude 变成形式主义

Claude 很重要，但不能设计成“所有任务都必须 Claude”。否则会出现两个坏结果：

- 小任务也被迫跑 Claude，流程变重。
- Agent 为了满足流程而空跑 Claude，实际没有增加质量。

正确做法是让每个 handoff 或 lane artifact 显式声明：

```text
claude_policy: required | conditional | not_needed
claude_mode: independent_claude_plan | claude_plan_critique | claude_execution_consult | claude_review | claude_debate | n/a
reason:
required_artifact:
fallback_if_unavailable:
```

这样每一步都可以被追问：

- 这一步到底需不需要 Claude？
- 如果需要，证据 artifact 在哪里？
- 如果不需要，理由是什么？
- 如果 Claude 不可用，是阻塞还是可降级？

### 2.2 Dispatcher 不是中央大脑

Dispatcher 的职责是物理投递和记录，不是计划、执行、审查或仲裁。

需要明确：

- Dispatcher 可以创建线程、发送消息、轮询状态、补 ledger。
- Dispatcher 可以提醒某个 lane 缺少 required Claude artifact。
- Dispatcher 不能替 lane 跑 Claude。
- Dispatcher 不能代替计划Agent判断计划质量。
- Dispatcher 不能代替审查Agent做 review。
- Dispatcher 不能代替仲裁Agent裁决争议。

这能避免调度Agent上下文爆炸，也能保留每个 lane 的独立判断能力。

### 2.3 经理Agent只做项目级状态和恢复

经理Agent不是工作流 boss。它的定位应该是：

- 项目级历史检索
- 当前 loop 状态检查
- 找回旧线程
- 检查 ledger / worklog / registry 是否断裂
- 帮用户回答“现在做到哪一步”
- 发现缺口后提醒对应 lane 或 Dispatcher

经理Agent不能接管计划、执行、审查、仲裁。它也不能替 lane 补跑 Claude。

### 2.4 先决策路线，再启动流程

当前 skill 一上来写五步流程，容易让 Agent 默认“全流程走一遍”。应该先做 Decision Gate：

1. 这是 tiny docs/config/local fix 吗？如果是，留在当前线程，记录证据即可。
2. 这是高风险、跨模块、架构、迁移、认证、数据、前后端联通任务吗？如果是，使用 loop。
3. 这次需要可追溯、上下文隔离、并行模型或多线程 lane 吗？如果是，创建 named lanes。
4. 这是同一个 active loop 的修正或继续吗？如果是，复用已有 `loop_id` 和 owner lane。
5. 当前上下文有风险吗？如果是，先写 baton，再继续或 handoff。

这个入口能防止两个常见错误：

- 小任务过度编排。
- 同一个任务修正时错误新开一套 lanes。

### 2.5 artifacts 是事实来源，chat history 不是

后续所有关键状态都应该落到文件：

- 计划落到 plan artifact
- 执行落到 execution report
- 审查落到 review artifact
- 分歧落到 arbitration
- 跨线程消息落到 thread ledger
- 每个 lane 的动作和经验落到 worklog
- 上下文恢复状态落到 baton

chat history 只能作为临时沟通，不作为长期事实来源。

## 3. 当前问题清单

### P1-1. `description` 触发词不够覆盖当前设计

当前 description：

```yaml
description: Use when a substantial AI coding task needs loop engineering, dual Claude/Codex planning, named Codex agent threads, cross-model review, repair iterations, or durable plan/review/arbitration artifacts.
```

它可以触发，但缺少已经明确成为核心的关键词：

- multi-agent orchestration
- dispatcher-mediated handoffs
- thread ledgers
- worklogs
- batons
- cross-model debate
- evidence-based arbitration

风险：

- 用户提“多智能体编排”“调度Agent”“线程台账”“baton”时，skill 触发不稳定。
- description 仍偏向早期“五步双模型流程”，对现在的 lane 工作流表达不足。

建议改为：

```yaml
description: Use when substantial AI coding work needs multi-agent orchestration, cross-model Claude/Codex planning or review, named Codex agent threads, dispatcher-mediated handoffs, thread ledgers, worklogs, batons, repair loops, cross-model debate, or evidence-based arbitration.
```

注意：

- 不要把完整流程写进 description。
- description 只写“什么时候用”，不要写“怎么做”。
- 这是 `writing-skills` 明确要求，避免模型只看 description 走捷径。

### P1-2. 缺少 Quick Start / Decision Gate

当前 `Purpose` 后面直接进入默认 ownership 和五步流程。

问题：

- Agent 读到五步流程后容易直接全量执行。
- 没有先判断是否 tiny、是否需要 lanes、是否是同一个 loop 的修正。
- baton 虽然后面写了，但入口没有提醒。

建议在 `Purpose` 后加一个短节：

```markdown
## Quick Start / Decision Gate

First decide:

1. Tiny docs/config/local fix? Stay in the current thread and record evidence.
2. Risky, cross-module, architecture, migration, auth/data, or frontend/backend linkage? Use the loop.
3. Need traceability, context isolation, parallel read work, or cross-thread handoff? Create named lanes.
4. Same active loop correction or continuation? Reuse the existing `loop_id` and owner lane.
5. Choose the smallest route that controls risk; do not create all lanes by habit.
6. Set `claude_policy` for every handoff and lane artifact.
7. Context at risk? Drop a baton before more work or handoff.
```

验收标准：

- Agent 能在入口先做任务分类。
- 同一个 loop 的修正不会默认新开 lane set。
- 小任务不会自动变成完整多Agent流程。

### P1-3. Claude 参与缺少显式协议字段

当前 Claude Bridge 已写：

- lane that needs Claude invokes Claude
- Dispatcher must not summarize or bridge unreadable content for Claude
- Claude output is evidence, not authority

这些方向正确，但不够可追溯。需要把 Claude 是否参与变成每个 handoff / lane artifact 的硬字段。

建议新增 `Claude Participation Policy` 小节，放在 `Claude Bridge` 后面。

字段：

```text
claude_policy: required | conditional | not_needed
claude_mode: independent_claude_plan | claude_plan_critique | claude_execution_consult | claude_review | claude_debate | n/a
reason:
required_artifact:
fallback_if_unavailable:
```

字段解释：

- `claude_policy`: 本阶段是否必须、可选或不需要 Claude。
- `claude_mode`: Claude 参与方式。
- `reason`: 为什么这个阶段需要或不需要 Claude。
- `required_artifact`: 如果需要 Claude，Claude 输出应该落到哪个文件。
- `fallback_if_unavailable`: Claude 不可用时怎么处理，是否阻塞。

必须写入的 close-out 规则：

```text
If `claude_policy: required`, the lane must not close out unless it writes the required Claude artifact or records `claude-unavailable: <reason>` and whether that blocks the lane.

If `claude_policy: conditional` and Claude is not used, write `Claude skipped: <why not needed now>`.

If Claude is used, the lane must write:

Claude said:
Codex accepts:
Codex rejects:
needs evidence:
final lane decision:
```

风险控制：

- 防止“流程说要 Claude，实际没人跑”。
- 防止“Claude 跑了，但 Codex 不做证据仲裁”。
- 防止“conditional 变成空字段，没有任何解释”。

### P1-4. Claude required / conditional / not_needed 的判断矩阵缺失

建议写入以下规则。

`claude_policy: required` 的场景：

- process / skill 修改，会影响未来 Agent 行为。
- 架构、迁移、前后端联通、数据丢失、认证权限等高风险任务。
- 计划阶段存在多条可行路线，需要外部视角比较。
- 审查阶段涉及行为变更或长期协议变更。
- Codex 和 Claude 或两个 lane 出现实质分歧，需要仲裁。

`claude_policy: conditional` 的场景：

- 执行Agent遇到计划不清、实现风险、技术分歧。
- 审查Agent发现 P1/P2，但证据不足。
- 计划Agent需要压力测试某个 workflow 设计。

`claude_policy: not_needed` 的场景：

- Dispatcher 投递、轮询、补 ledger 状态。
- 经理Agent查状态、恢复线程、回答当前进度。
- 很小的文档修正、格式整理、纯记录修复。
- 机械性执行已审过的窄 scope，且没有新风险。

关键约束：

- 不能把 required 扩大成所有任务默认。
- 不能把 conditional 当成不用写理由的跳过。
- not_needed 也要有 `reason`，否则未来无法判断是否误跳过。

### P1-5. lane 内部调用 Claude 的边界不够明确

当前写了 lane owns Claude，但还需要明确每个 lane 可以怎么用 Claude。

建议放在 `Lane Roles` 后：

```markdown
### Lane-Owned Claude Use

- `计划Agent`: may use Claude for independent plans, plan critique, route comparison, and workflow pressure testing.
- `执行Agent`: may use Claude for implementation-risk consultation or unclear-plan analysis; Claude must not directly edit code unless the user explicitly asks.
- `审查Agent`: may use Claude for read-only review and evidence-seeking critique.
- `仲裁Agent`: may use Claude only as evidence or a debate participant; arbitration decisions cite evidence, not model identity.
- `Dispatcher`: must not run Claude on behalf of lanes. It may only flag missing required Claude artifacts or unavailable markers.
- `经理Agent`: must not run Claude on behalf of lanes. It may inspect status/history and identify missing evidence.
```

这样能把用户最关心的点写死：

- 每个 lane 可以独立和 Claude 复盘、争论、咨询。
- 调度Agent不替所有 lane 和 Claude 大量交流。
- Codex 最终仍要客观分析 Claude 的观点，不盲从。

### P1-6. Standard Agent Messages 缺 Claude policy 字段

当前标准消息包含：

```text
message_type
loop_id
message_id
from_lane / to_lane
from_thread / to_thread when known
delivered_by_lane / delivered_by_thread / delivery_reason when physical sender differs from logical sender
source artifacts
task
boundaries
write scope
required output
exit criteria
```

建议增加：

```text
claude_policy
claude_mode
claude_reason
required_claude_artifact when applicable
fallback_if_claude_unavailable
baton / resume_from when applicable
```

作用：

- 每个 handoff 都能提前声明 Claude 策略。
- 接收 lane 不需要猜“我要不要跑 Claude”。
- Dispatcher 或经理Agent能检查字段缺失。
- ledger 里可以追溯为什么这次跑或没跑 Claude。

### P1-7. `set_thread_pinned` 默认行为不符合用户偏好

当前写法：

```text
set_thread_pinned: optional for active loop threads.
```

建议改成：

```text
set_thread_pinned: avoid by default; use only when the user explicitly asks.
```

原因：

- 用户明确说不要置顶。
- 置顶不是 loop 成功的必要条件。
- active/trial loop 期间频繁置顶会污染用户线程管理。

### P2-1. Forward Test Scenarios 没有制度化

`writing-skills` 的核心要求是：skill 修改要有压力场景。

当前 `SKILL.md` 只有 Common Mistakes，没有正式写：

- 如何测试这个 skill
- 用哪些场景测试
- 哪些行为算失败

建议加一个短节 `Forward Test Scenarios`，放在 `Common Mistakes` 前或后。

最小场景：

1. Same loop correction reuse
   - 输入：用户说“还是这个 skill 打磨任务，继续改，不要新开线程”
   - 应该：复用现有 `loop_id` 和 owner lane
   - 失败：新建 `LOOP-...-002` 或新 lane set

2. Dispatcher boundary
   - 输入：planning-to-execution handoff 需要由 Dispatcher 物理发送
   - 应该：Dispatcher 只投递、记 ledger
   - 失败：Dispatcher 自己补计划、执行或审查判断

3. Claude required for skill/process change
   - 输入：修改 `loop-engineering` 这种会影响未来 Agent 行为的 skill
   - 应该：`claude_policy: required`
   - 失败：没有 Claude artifact，也没有 `claude-unavailable`

4. Claude not needed for tiny docs fix
   - 输入：纯格式修正、错别字、小记录修复
   - 应该：`claude_policy: not_needed` 并写 reason
   - 失败：形式主义跑 Claude 或不写 policy

5. Conditional Claude skip
   - 输入：执行Agent遇到一个低风险但略有不确定的实现点
   - 应该：要么咨询 Claude，要么写 `Claude skipped: <reason>`
   - 失败：无声跳过

6. Reverse handoff
   - 输入：执行发现计划不可行
   - 应该：执行Agent带证据反向发 planning lane
   - 失败：执行Agent私自改计划并继续

7. Context risk
   - 输入：上下文接近 20% 或长 repair loop 前
   - 应该：写 baton
   - 失败：只写 worklog 或等自动 compact

8. Claude path access failure
   - 输入：Claude 读不到路径
   - 应该：当前 lane 自己处理 `--add-dir` 或临时 artifact fallback
   - 失败：Dispatcher 总结内容给 Claude

### P2-2. route 表需要强调“按风险动态选择”

当前 `Lane Selection` 已有表，但应补强：

- route 是动态选择，不是模板。
- Plan Review 不必每次都有。
- Review / Arbitration 也按风险决定是否独立开 lane。
- 不要为了体现多Agent而创建所有 agent。

建议加一句：

```text
Routes are selected per task and may change after evidence appears. Do not preserve a route just because it was chosen earlier; add, skip, or re-enter lanes when risk changes, and record the reason in the worklog and ledger.
```

### P2-3. 文件长度接近拆分阈值

当前 `SKILL.md` 约 461 行。加入本轮内容后可能超过 500 行。

建议：

- 第一轮仍然只改 `SKILL.md`，因为这些是核心协议，不适合一开始就拆散。
- 不要加入大段完整模板示例。
- 如果改完明显超过 500 行，下一轮拆 references。

候选拆分：

```text
/Users/apple/.codex/skills/loop-engineering/references/message-protocol.md
/Users/apple/.codex/skills/loop-engineering/references/artifact-templates.md
/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md
```

拆分原则：

- `SKILL.md` 保留判断、边界、硬规则。
- `references/` 放模板、长示例、场景库。
- `SKILL.md` 必须明确什么时候读哪个 reference。

### P3-1. `agents/openai.yaml` 缺失

`skill-creator` 推荐有 `agents/openai.yaml`，用于 UI 元数据。

这是低优先级，因为它不影响 workflow correctness。

建议后续加：

- `display_name`: Loop Engineering
- `short_description`: Multi-agent engineering loops with Claude/Codex review, lane handoffs, ledgers, worklogs, and evidence arbitration.
- `default_prompt`: Use this skill to plan, execute, review, and arbitrate substantial coding work with traceable agent lanes and cross-model evidence.

## 4. 第一轮执行计划

第一轮目标：只做核心 hardening，不大拆文件，不创建复杂脚本。

允许修改：

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`

暂不修改：

- 业务代码
- 现有项目实现
- git 分支
- agents/openai.yaml
- references 拆分文件

### Step 1. 基线检查

执行：

```bash
wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "claude_policy|claude_mode|Claude skipped|claude-unavailable|Forward Test|Decision Gate|set_thread_pinned" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

预期：

- 能看到当前行数。
- 可能找不到 `claude_policy` 等新字段。
- 能看到 `set_thread_pinned` 仍是 optional。

### Step 2. 修改 description

把 frontmatter description 改成：

```yaml
description: Use when substantial AI coding work needs multi-agent orchestration, cross-model Claude/Codex planning or review, named Codex agent threads, dispatcher-mediated handoffs, thread ledgers, worklogs, batons, repair loops, cross-model debate, or evidence-based arbitration.
```

验收：

```bash
rg -n "multi-agent orchestration|dispatcher-mediated handoffs|thread ledgers|worklogs|batons|cross-model debate" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 3. 增加 Quick Start / Decision Gate

位置：`Purpose` 之后，`The User's Five-Step Workflow` 之前。

内容应短，不写长模板。

必须包含：

- tiny 任务留当前线程
- risky / cross-module 用 loop
- 需要追溯或上下文隔离才开 lanes
- 同一个 active loop 修正要复用已有 lanes
- 每个 handoff / artifact 设置 `claude_policy`
- 上下文有风险先 baton

验收：

```bash
rg -n "Quick Start|Decision Gate|Same active loop|claude_policy|Context at risk" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 4. 增加 Claude Participation Policy

位置：`Claude Bridge` 后，`Agent Lanes` 前。

必须包含：

- 字段定义
- required / conditional / not_needed 判断规则
- required close-out gate
- conditional skip 记录
- Claude 输出结构
- Dispatcher 不代跑 Claude 的约束

验收：

```bash
rg -n "Claude Participation Policy|claude_policy|claude_mode|Claude skipped|claude-unavailable|Claude said|Codex accepts|final lane decision" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 5. 增加 Lane-Owned Claude Use

位置：`Lane Roles` 后。

必须包含：

- 计划Agent可用 Claude 做独立计划、批判、路线比较。
- 执行Agent可用 Claude 做实现风险咨询，不能让 Claude 直接改代码。
- 审查Agent可用 Claude 做只读 review。
- 仲裁Agent只把 Claude 当证据。
- Dispatcher 不替 lane 跑 Claude。
- 经理Agent 不替 lane 跑 Claude。

验收：

```bash
rg -n "Lane-Owned Claude|计划Agent.*Claude|执行Agent.*Claude|审查Agent.*Claude|仲裁Agent.*Claude|Dispatcher.*Claude|经理Agent.*Claude" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 6. 更新 Standard Agent Messages

位置：`Standard Agent Messages` 字段列表。

新增：

```text
claude_policy
claude_mode
claude_reason
required_claude_artifact when applicable
fallback_if_claude_unavailable
baton / resume_from when applicable
```

验收：

```bash
rg -n "claude_reason|required_claude_artifact|fallback_if_claude_unavailable|baton / resume_from" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 7. 修改 pinning 规则

把：

```text
set_thread_pinned: optional for active loop threads.
```

改成：

```text
set_thread_pinned: avoid by default; use only when the user explicitly asks.
```

验收：

```bash
rg -n "set_thread_pinned" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 8. 增加 Forward Test Scenarios

位置：`Common Mistakes` 前或后。

建议先放在 `Common Mistakes` 前，这样测试先于错误列表。

必须包含至少 6 个：

- same loop correction reuse
- Dispatcher boundary
- Claude required for skill/process change
- Claude not needed for tiny docs fix
- conditional Claude skip
- reverse handoff
- context risk baton
- Claude path access failure

验收：

```bash
rg -n "Forward Test Scenarios|same loop|Dispatcher boundary|skill/process|tiny docs|conditional|reverse handoff|context risk|path access" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### Step 9. 更新 Common Mistakes

新增：

- Missing `claude_policy` in a handoff or lane artifact.
- Closing a `claude_policy: required` lane without Claude artifact or `claude-unavailable`.
- Running Claude from Dispatcher on behalf of a lane.
- Treating `conditional` as silent skip instead of writing `Claude skipped`.
- Adding long templates to `SKILL.md` instead of moving them to references when the file grows.

验收：

```bash
rg -n "Missing `claude_policy`|required.*claude-unavailable|Dispatcher.*on behalf|conditional.*Claude skipped|long templates" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

## 5. 第二轮拆分计划

如果第一轮后 `SKILL.md` 明显超过 500 行，或者阅读成本继续上升，再执行拆分。

### 5.1 `references/message-protocol.md`

内容：

- 标准 handoff 完整模板
- ledger row 示例
- `message_id` 命名规则
- `delivered_by_lane` 字段说明
- `claude_policy` 字段说明
- baton / resume_from 的 handoff 写法

`SKILL.md` 只保留最小字段列表和引用：

```text
For full message and ledger examples, read `references/message-protocol.md` when creating or auditing handoffs.
```

### 5.2 `references/artifact-templates.md`

内容：

- `00-brief.md`
- `10-plan-claude.md`
- `11-plan-codex.md`
- `12-plan-merged.md`
- `20-execution-report.md`
- `30-review-claude.md`
- `31-review-codex-subagent.md`
- `40-arbitration.md`
- `50-final-report.md`

`SKILL.md` 保留 artifact 目的和硬规则，不保留完整模板。

### 5.3 `references/claude-policy.md`

内容：

- required / conditional / not_needed 矩阵
- 各 lane 的 Claude prompt 方向
- unavailable 处理示例
- Claude said / Codex accepts / rejects / needs evidence 示例

如果 `SKILL.md` 的 Claude policy 节变长，可以拆到这里。

### 5.4 `references/forward-tests.md`

内容：

- 压力测试场景库
- 每个场景的输入、期望行为、失败信号
- 后续真实任务复盘结果

注意：

- forward-test prompt 不能泄露预期答案。
- 应该像真实用户请求一样触发 skill。

## 6. 验证计划

### 6.1 静态验证

```bash
wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "multi-agent orchestration|dispatcher-mediated handoffs|thread ledgers|worklogs|batons|cross-model debate" /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "Quick Start|Decision Gate|claude_policy|Claude Participation Policy|Claude skipped|claude-unavailable" /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "Lane-Owned Claude|Dispatcher.*Claude|set_thread_pinned|Forward Test Scenarios" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

### 6.2 内容验收

执行Agent应人工确认：

- description 没有写完整流程。
- Quick Gate 在五步流程之前。
- Claude policy 写成策略字段，而不是泛泛说“要用 Claude”。
- Dispatcher 被明确禁止替 lane 跑 Claude。
- `set_thread_pinned` 默认不用。
- forward tests 覆盖已踩坑场景。
- 新增内容没有把 `SKILL.md` 变成模板堆积。

### 6.3 场景验收

后续可以用一个真实任务做 forward-test，例如：

```text
使用 loop-engineering，检查当前项目的前后端联通差异：前端界面已经固定，找出后端哪些功能没有对应上，给出计划、执行和审查工作流。
```

观察点：

- 是否先通过 Decision Gate 判断路线。
- 是否按风险选择 Planning / Plan Review / Execution / Review / Arbitration。
- 是否为每个 handoff 写 `claude_policy`。
- 是否让计划Agent或审查Agent自己调用 Claude，而不是 Dispatcher 替跑。
- 是否写 ledger / worklog。
- 是否在上下文风险时写 baton。

## 7. 不做事项

第一轮不做：

- 不重写整个 `SKILL.md`。
- 不创建新的 lane 线程。
- 不修改业务代码。
- 不把所有任务都强制 Claude。
- 不把经理Agent变成主控Agent。
- 不让 Dispatcher 变成中央代理。
- 不添加大量完整模板到 `SKILL.md`。
- 不创建 commit 或 PR。

## 8. 推荐交给执行Agent的任务描述

可以把下面这段作为后续 handoff：

```text
Use `$loop-engineering` and update `/Users/apple/.codex/skills/loop-engineering/SKILL.md` according to `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`.

This is a skill hardening task, not a business-code task. Make a narrow edit only to `SKILL.md`.

Required changes:
- update description trigger terms;
- add Quick Start / Decision Gate;
- add Claude Participation Policy with `claude_policy`;
- add lane-owned Claude boundaries;
- add Claude policy fields to Standard Agent Messages;
- change `set_thread_pinned` to avoid by default;
- add Forward Test Scenarios;
- add Common Mistakes for missing Claude policy and Dispatcher overreach.

Do not create new lane threads unless explicitly asked. Do not pin threads. Do not edit business code. Do not split references in this pass unless the file becomes too large to read safely.

Verify with `rg` and `wc -l`, then record exact output in the execution report or worklog.
```

## 9. 完成标准

这份 hardening 完成后，未来 Agent 应该能做到：

- 先判断任务路线，而不是机械启动完整 loop。
- 同一个 active loop 的修正会复用已有 lane。
- 每个 handoff 都能说明 Claude 是否需要、为什么、证据在哪里。
- Claude required 时不会无 artifact 正常结束。
- conditional Claude 不跑时会写明跳过原因。
- 各 lane 能独立咨询 Claude，Dispatcher 不再成为 Claude 中央代理。
- 经理Agent维持状态和恢复定位，不接管工作流。
- 上下文风险时写 baton，而不是等自动 compact。
- 已踩过的坑能通过 forward-test 被重新检查。
