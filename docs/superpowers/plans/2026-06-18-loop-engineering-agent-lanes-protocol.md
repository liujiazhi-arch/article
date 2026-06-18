# Loop Engineering Agent Lanes Protocol

## Source

- User request in current Codex thread on 2026-06-18.
- Existing skill: `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.
- Current Codex app callable tools discovered in this session: `list_projects`, `create_thread`, `set_thread_title`, `set_thread_pinned`, `send_message_to_thread`, `read_thread`, `fork_thread`, `handoff_thread`, `get_handoff_status`, `set_thread_archived`, `automation_update`.
- Official OpenAI docs checked on 2026-06-18:
  - `https://developers.openai.com/codex/app/worktrees`
  - `https://developers.openai.com/codex/subagents`
  - `https://developers.openai.com/codex/app/automations`

Note: the OpenAI docs manual helper failed with HTTP 403 in this session. The source links above were opened directly from the official OpenAI Developers site, and the current thread-management tool boundaries came from callable tool schemas exposed in this Codex app session.

## Goal

Turn `loop-engineering` into a reusable multi-thread and cross-model engineering workflow:

- Each phase runs in a clearly named agent lane.
- Every agent-to-agent message is traceable by loop id and message id.
- Artifacts, not chat history, are the source of truth.
- Codex thread tools provide delivery and coordination.
- Claude CLI and Codex subagent review remain first-class parts of the workflow.
- The protocol stays dynamic: small loops use fewer lanes; risky loops add more lanes.

## Design Judgment

The model should be a lane-to-lane workflow with optional project-level status and recovery support, not a centralized dispatcher.

Each agent lane owns its phase and hands off directly to the next lane when its work is complete. The first thread is only the bootstrap thread unless it is explicitly acting as a named lane. It is not a main agent by default.

`经理Agent` is not a normal workflow lane and not a "boss model" that overrides evidence. It is an optional project-level status and recovery role:

- look up historical loops and thread ids
- inspect current task state
- identify coordination problems
- maintain or repair the project registry
- help the user recover the right thread
- escalate blockers or missing user decisions

The `经理Agent` should be project-level, not loop-level, when it exists. A project can run many loops over time, such as frontend optimization today and backend optimization tomorrow. The manager keeps or repairs a project registry so old agent threads can be found, resumed, or audited without relying on memory or sidebar search alone.

Primary handoff ownership belongs to the lane that just finished work:

```text
计划Agent -> 执行Agent
执行Agent -> 审查Agent
审查Agent -> 仲裁Agent
仲裁Agent -> 执行Agent when repair is needed
执行Agent -> 计划Agent when the plan is contradicted by implementation evidence
审查Agent -> 计划Agent when the review finds a plan-level flaw
any lane -> 经理Agent only when historical lookup, status audit, registry repair, blocker escalation, or recovery is needed
```

## Core Concepts

### Loop

A loop is one bounded engineering effort.

Example:

```text
loop_id: LOOP-20260618-001-agent-lanes
slug: 2026-06-18-agent-lanes
```

The `loop_id` should be readable and stable. It may match the artifact slug.

### Agent Lane

An agent lane is a named role backed by one Codex thread or by an external tool invocation.

Default lane names are Chinese:

| lane_id | thread title suffix | purpose |
|---|---|---|
| planning | 计划Agent | write brief, run dual planning, merge plans |
| execution | 执行Agent | implement only the merged plan |
| review | 审查Agent | run read-only review, including Claude CLI and Codex subagent review |
| arbitration | 仲裁Agent | decide review findings, repair accepted issues, write final report |
| status | 经理Agent | optional project-level history lookup, status audit, and recovery |

These lanes are not mandatory for every task. A small task may use only the current thread as `执行Agent`; a risky feature may use planning, execution, review, and arbitration lanes.

### Thread Title

Use `set_thread_title` so the sidebar is human-readable.

Recommended pattern:

```text
计划Agent / 前端优化-2026-06-18
执行Agent / 前端优化-2026-06-18
审查Agent / 前端优化-2026-06-18
仲裁Agent / 前端优化-2026-06-18
计划Agent / 后端优化-2026-06-19
经理Agent / 论文格式工具
```

Thread titles are for humans. The durable id remains the actual Codex `threadId` recorded in `agent-lanes.md`.

Rules:

- Worker thread titles should start with the agent name, then task name and date. This makes the sidebar immediately show which agent is speaking.
- The project status/recovery thread title should be stable across loops if a `经理Agent` exists.
- Avoid generic titles like `Planning` or `Execution`; they are hard to recover later.
- If a lane is reused for follow-up work, keep the original title unless the scope materially changes.

### Message

A message is a structured handoff sent with `send_message_to_thread`.

The message carries:

- `loop_id`
- `message_id`
- source lane and target lane
- source thread and target thread when known
- source artifacts
- task
- allowed reads and writes
- forbidden actions
- required output
- exit criteria

The message should include a compact summary, but full content should live in artifact files.

## Required Artifacts

For this project, prefer `docs/superpowers/plans/`.

Project-level registry:

```text
docs/superpowers/agent-registry.md
```

Minimum durable files for a multi-lane loop:

```text
docs/superpowers/plans/YYYY-MM-DD-slug-brief.md
docs/superpowers/plans/YYYY-MM-DD-slug-agent-lanes.md
docs/superpowers/plans/YYYY-MM-DD-slug-thread-ledger.md
docs/superpowers/plans/YYYY-MM-DD-slug-decision-log.md
docs/superpowers/plans/YYYY-MM-DD-slug-worklog.md
```

Then add phase artifacts as needed:

```text
docs/superpowers/plans/YYYY-MM-DD-slug-claude-plan.md
docs/superpowers/plans/YYYY-MM-DD-slug-codex-plan.md
docs/superpowers/plans/YYYY-MM-DD-slug-merged-plan.md
docs/superpowers/plans/YYYY-MM-DD-slug-codex-execution-report.md
docs/superpowers/plans/YYYY-MM-DD-slug-claude-review.md
docs/superpowers/plans/YYYY-MM-DD-slug-codex-subagent-review.md
docs/superpowers/plans/YYYY-MM-DD-slug-arbitration.md
docs/superpowers/plans/YYYY-MM-DD-slug-final-report.md
```

## Worklog

`worklog.md` records what each agent actually did, what it learned, and pitfalls for future loops.

It is different from `thread-ledger.md`:

- `thread-ledger.md` records cross-agent messages.
- `worklog.md` records agent work, decisions during work, commands, mistakes, and reusable lessons.

Template:

```markdown
# Worklog

loop_id: LOOP-YYYYMMDD-001-slug

## Entries

| seq | time | lane | thread_id | action | evidence | lesson_or_risk |
|---:|---|---|---|---|---|---|
| 1 | 2026-06-18T14:30:12+08:00 | planning | codex... | compared Claude/Codex plans | merged-plan.md | keep rejected ideas in decision-log |
```

Rules:

- Every lane appends a short worklog entry before handing off.
- Record commands only when they matter; do not dump noisy output.
- Record mistakes and near-misses explicitly so later agents do not repeat them.
- The `经理Agent` reads the worklog to understand progress and recurring risks.

## Project Agent Registry

`docs/superpowers/agent-registry.md` is the long-lived index for the project.

It answers:

- Is there a current project `经理Agent` status/recovery thread?
- Which loops have existed?
- Which agent threads belonged to each loop?
- Which branch or worktree did execution use?
- Which thread should receive a follow-up if the user wants to resume an old topic?

Template:

```markdown
# Project Agent Registry

project: article
manager_agent_thread: codex...
manager_agent_title: 论文格式工具 / 经理Agent
updated_at: 2026-06-18T14:30:12+08:00

## Active Loops

| loop_id | task_name | status | branch_or_worktree | manager_thread | plan_thread | execution_thread | review_thread | arbitration_thread | main_artifacts |
|---|---|---|---|---|---|---|---|---|---|
| LOOP-20260618-001-agent-lanes | agent lanes protocol | active | local | codex... | current-thread | not-created | not-created | not-created | docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md |

## Historical Loops

| loop_id | task_name | final_status | finished_at | key_threads | final_report |
|---|---|---|---|---|---|
| LOOP-YYYYMMDD-001-example | frontend optimization | completed | 2026-06-18T18:20:00+08:00 | planning=codex..., execution=codex... | docs/superpowers/plans/YYYY-MM-DD-slug-final-report.md |
```

Rules:

- The registry is project-level and survives across loops.
- It should be updated when a lane thread is created, renamed, completed, blocked, or superseded.
- It should point to loop artifacts instead of duplicating full reports.
- It should record enough thread ids to recover old conversations with `read_thread` or `send_message_to_thread`.
- If the manager cannot update the registry immediately, the message must say so and the next manager turn must repair it.

## Agent Lanes File

`agent-lanes.md` is the current map of the loop.

Template:

```markdown
# Agent Lanes

loop_id: LOOP-YYYYMMDD-001-slug
slug: YYYY-MM-DD-slug
status: active

| lane_id | name | thread_id | thread_title | purpose | read_scope | write_scope | worklog | status |
|---|---|---|---|---|---|---|---|---|
| planning | 计划Agent | codex... | 计划Agent / 任务名-日期 | planning | brief repo evidence | plan artifacts | worklog.md | active |
| execution | 执行Agent | codex... | 执行Agent / 任务名-日期 | implementation | brief merged plan decision log | code tests execution report | worklog.md | waiting |
| review | 审查Agent | codex... | 审查Agent / 任务名-日期 | read-only review | merged plan execution report diff tests | review artifacts | worklog.md | waiting |
| arbitration | 仲裁Agent | codex... | 仲裁Agent / 任务名-日期 | arbitration and repair | plan report reviews | arbitration final report repairs | worklog.md | waiting |
| status | 经理Agent | codex... | 经理Agent / 项目名 | history lookup and recovery | registry loop artifacts | registry repair notes | worklog.md | optional |
```

Rules:

- If a lane has no thread yet, set `thread_id: not-created`.
- If Claude CLI is used, record it as a tool-backed lane entry with `thread_id: external-claude-cli`.
- If a Codex subagent is used inside a review phase, record it as `thread_id: codex-subagent:<local-id-if-known>` or `not exposed`.

## Thread Ledger

`thread-ledger.md` records cross-agent communication.

Template:

```markdown
# Thread Ledger

loop_id: LOOP-YYYYMMDD-001-slug

| seq | message_id | time | from_lane | to_lane | tool | target_thread | source_artifacts | purpose | status |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | MSG-001-planning-to-execution | 2026-06-18T14:30:12+08:00 | planning | execution | send_message_to_thread | codex... | merged-plan.md | start execution | sent |
```

Status values:

```text
draft
sent
acknowledged
blocked
completed
superseded
cancelled
```

Rules:

- Every `send_message_to_thread` call must have a ledger row.
- Direct lane-to-lane messages are the default after a phase completes.
- If an agent sends a direct message to another agent, it must update the ledger and worklog, or explicitly ask `经理Agent` to repair the records.
- If a message is replaced, do not delete it. Mark it `superseded` and create a new message id.

## Decision Log

`decision-log.md` records settled decisions so later agents do not reopen old debates.

Template:

```markdown
# Decision Log

loop_id: LOOP-YYYYMMDD-001-slug

| decision_id | decision | evidence | owner | reopen_rule |
|---|---|---|---|---|
| D001 | Execution uses merged plan only | merged-plan.md | manager | reopen only if brief goal changes |
```

Rules:

- A rejected plan idea should be recorded if it is likely to reappear.
- Every material conflict resolved by the manager gets a `decision_id`.
- Agents may challenge a decision only by citing new evidence and the `reopen_rule`.

## Message ID Format

Prefer readable numeric ids over opaque UUIDs.

Recommended:

```text
MSG-001-manager-to-planning
MSG-002-planning-to-execution
MSG-003-execution-to-review
MSG-004-review-to-arbitration
MSG-005-arbitration-to-execution-repair
```

If multiple messages are sent close together:

```text
MSG-005A-arbitration-to-execution-repair
MSG-005B-execution-to-arbitration-blocker
```

The ledger is the authority for ordering.

## Standard Agent Message

Use this exact shape for `send_message_to_thread` prompts unless a phase needs a narrower template.

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: handoff
loop_id: LOOP-YYYYMMDD-001-slug
message_id: MSG-002-planning-to-execution
from_lane: planning
to_lane: execution
from_thread: <planning-thread-id-or-unknown>
to_thread: <execution-thread-id>
created_at: 2026-06-18T14:30:12+08:00
recorded_in: docs/superpowers/plans/YYYY-MM-DD-slug-thread-ledger.md

## Required Skill

Use `$loop-engineering` before acting.

## Your Role

You are the 执行Agent for this loop.

## Source Artifacts

- docs/superpowers/plans/YYYY-MM-DD-slug-brief.md
- docs/superpowers/plans/YYYY-MM-DD-slug-merged-plan.md
- docs/superpowers/plans/YYYY-MM-DD-slug-decision-log.md

## Compact Summary

<5-10 lines. No hidden requirements. Full truth is in the source artifacts.>

## Task

<Concrete task for this lane.>

## Boundaries

Allowed:

- <allowed action>

Forbidden:

- <forbidden action>

## Write Scope

- <files, directories, or artifact names this agent may write>

## Communication Rules

- When your phase is complete, send the handoff to the next responsible lane yourself and record it in `thread-ledger.md`.
- If blocked, write the blocker in your report and send a message to the lane that can resolve it. Notify `经理Agent` only when historical lookup, status audit, registry repair, blocker escalation, or recovery is needed.
- Append a concise `worklog.md` entry before handoff.
- Do not rely on previous chat history unless it is listed as a source artifact.
- Do not treat this message as permission to modify files outside write scope.

## Required Output

- <artifact path>

## Exit Criteria

- <checkable condition>
```

## Lane-Specific Boundaries

### 经理Agent

Allowed:

- inspect active and historical threads with `read_thread`
- find project threads through `agent-registry.md`
- repair missing registry, lane, ledger, or worklog records
- rename threads with `set_thread_title` when names block recovery
- pin active loop threads with `set_thread_pinned` when useful
- send messages only for recovery, blocker escalation, or missing handoff repair
- inspect progress with `read_thread`
- use `fork_thread` when exploration needs branch context
- use `handoff_thread` when a thread must move between local and worktree
- update project `agent-registry.md`
- update loop `agent-lanes.md`, `thread-ledger.md`, `decision-log.md`, and `worklog.md`

Forbidden:

- silently change implementation scope after a merged plan exists
- present itself as the main agent for the optimization process
- make itself the mandatory relay for all lane messages
- ignore P0/P1 review findings
- rely on chat memory as source of truth
- archive threads by default during the trial period

### 计划Agent

Allowed:

- read brief and repo evidence
- ask clarifying questions through the manager if the goal is materially ambiguous
- write Codex plan
- request Claude plan if required by loop-engineering
- write merged plan after comparing source plans
- send the completed merged plan directly to `执行Agent`
- append worklog entries for major planning decisions and rejected paths

Forbidden:

- modify production code
- execute an unmerged plan
- hide unresolved plan gaps

### 执行Agent

Allowed:

- read brief, merged plan, decision log, and files needed for implementation
- modify code and tests inside the merged plan scope
- write execution report
- send completed execution directly to `审查Agent`
- send plan contradictions back to `计划Agent` with evidence
- append worklog entries for commands, pitfalls, and implementation lessons
- work on a dedicated branch or Codex worktree when implementation changes code

Forbidden:

- reopen planning debates
- broaden scope without manager approval
- modify unrelated dirty files
- claim completion without verification command output

### 审查Agent

Allowed:

- review the execution branch or worktree produced by 执行Agent
- read merged plan, execution report, git diff, tests, screenshots, and relevant code
- run Claude CLI read-only review
- run Codex subagent review independently
- write review artifacts
- send review output directly to `仲裁Agent`
- send plan-level defects back to `计划Agent` when the merged plan itself is wrong
- append worklog entries for review lessons and repeated defect patterns

Forbidden:

- modify production code
- review a different branch than the one recorded in `agent-registry.md` unless the manager explicitly changes the target
- let Claude review read Codex subagent review or vice versa
- treat screenshots as inspected unless actually inspected
- collapse cross-model disagreement without evidence

### 仲裁Agent

Allowed:

- read plan, execution report, reviews, decision log, and evidence
- accept, reject, third-path, or defer findings
- repair accepted findings within scope
- request execution repair through `send_message_to_thread` if the fix is non-trivial
- write arbitration and final report
- send repair requests directly to `执行Agent` and record the disposition
- append worklog entries for accepted/rejected findings and recurring risks

Forbidden:

- reject P0/P1 without evidence
- ship unresolved P0
- bury P1/P2 findings without disposition
- exceed loop stop rules

## Dynamic Lane Selection

Use the smallest lane set that preserves quality.

| task type | recommended lanes |
|---|---|
| tiny docs/config change | current thread only |
| small local bug fix | current thread as 执行Agent, or separate 执行Agent |
| normal feature or risky fix | 计划Agent -> 执行Agent -> 审查Agent -> 仲裁Agent |
| frontend/backend linkage | full lane set, plus browser verification in execution |
| architecture refactor | full lane set, likely worktree execution |
| unclear requirements | current thread or 计划Agent first; create execution only after merged plan |

Default execution policy:

- If a lane will modify code, create or use a dedicated branch or Codex worktree.
- Record the branch or worktree in project `agent-registry.md` and loop `agent-lanes.md`.
- 审查Agent should review the same branch or worktree, not a stale local checkout.
- 仲裁Agent decides whether repairs happen in the same execution lane, a repair lane, or the arbitration lane itself.

## Cross-Model Review Model

This protocol keeps the current `loop-engineering` advantage:

```text
Claude + Codex both plan
Codex merges
Codex executes
Claude reviews read-only
Codex subagent reviews independently
Codex arbitrates and repairs
```

The difference from generic multi-agent lanes is that Claude and Codex subagent are not treated as interchangeable workers.

- Claude CLI is an external reviewer or planner with its own artifact.
- Codex subagent is an independent reviewer inside the Codex ecosystem.
- The 审查Agent coordinates both but must keep them independent.
- The 仲裁Agent resolves disagreement with evidence, not model authority.

## Tool Use Policy

### `list_projects`

Use before `create_thread` when creating project-scoped lanes.

### `create_thread`

Use only when the user explicitly wants a new or background thread, or when a loop phase requires a separate lane under this protocol.

The first prompt should be a standard agent message.

For execution lanes that write code, prefer a worktree target or a clearly recorded branch when available.

### `set_thread_title`

Use immediately after thread creation if the thread title is not already clear.

### `set_thread_pinned`

Pin active loop threads while the loop is in progress. This is optional but useful during trial use.

### `send_message_to_thread`

Primary cross-lane delivery mechanism.

Never send an unstructured "continue" message for loop work. Send a standard agent message with ids and boundaries.

### `read_thread`

Used for status and recovery checks without opening the thread.

Use it to answer:

- did the lane complete?
- is it blocked?
- did it write the expected artifact?
- does it need a follow-up message?

### `fork_thread`

Use when an existing thread's context should be preserved but a branch of reasoning or implementation is needed.

Prefer fork for exploration, not for routine phase handoff.

### `handoff_thread`

Use when a thread and its git state need to move between local checkout and worktree.

This is useful when execution starts in local but should be isolated, or when repair work needs to return to local.

### `set_thread_archived`

Do not archive automatically during the trial period. Add an explicit final cleanup step later if the workflow proves stable.

### `automation_update`

Use only for scheduled follow-up, heartbeat, reminders, or monitors.

Do not use automation as the normal cross-agent message bus.

## Automatic Communication Loop

The desired "automatic communication" should be a lane-to-lane cycle with manager observability:

1. The bootstrap thread identifies the needed lanes and writes the initial artifacts.
2. 计划Agent completes planning, appends worklog, updates ledger, and sends the merged plan to 执行Agent.
3. 执行Agent implements, appends worklog, updates ledger, and sends execution report to 审查Agent.
4. 审查Agent reviews, appends worklog, updates ledger, and sends review artifacts to 仲裁Agent.
5. 仲裁Agent arbitrates, appends worklog, and sends repair requests to 执行Agent or final status to the user-facing thread.
6. Any lane can send a reverse message to the lane that owns the defect, such as execution back to planning or review back to planning.
7. 经理Agent, if used, monitors with `read_thread`, repairs missing records, handles blockers, and keeps the registry recoverable.

Important: automatic does not mean agents can silently expand scope. It means the next correct message can be sent without the user copying context by hand.

## Concurrency Rules

Parallelism is useful for read-heavy tasks and risky for write-heavy tasks.

Safe parallel work:

- independent codebase exploration
- test inventory
- read-only review
- documentation synthesis
- independent plan drafting

Risky parallel work:

- two agents editing the same files
- one agent changing APIs while another writes frontend bindings
- review agent modifying code while execution agent is still running

Default rule:

- Multiple read-only lanes may run in parallel.
- Only one write lane may edit a given file set unless each lane uses an isolated worktree and the manager owns merge arbitration.

## Escalation Rules

An agent should message `经理Agent` only when:

- source artifacts are missing
- write scope is insufficient
- tests contradict the merged plan
- another lane appears to have changed the same files
- P0/P1 review findings block final report
- the task requires user intent not present in artifacts

An agent should message another lane directly when:

- execution finds the merged plan is impossible or contradicted by code evidence
- review finds a plan-level defect rather than an implementation defect
- arbitration accepts a finding that requires execution repair
- a downstream lane needs clarification from the upstream lane that produced the artifact

Blocker message format:

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: blocker
loop_id: LOOP-YYYYMMDD-001-slug
message_id: MSG-006-execution-to-manager-blocker
from_lane: execution
to_lane: manager

## Blocker

<one sentence>

## Evidence

- <path:line, command output, or artifact path>

## Needed Decision

<specific decision needed from manager or user>
```

## Trial Policy

For initial use in this project:

- Use Chinese thread names.
- Put the agent name first in thread titles, such as `计划Agent / 前端优化-2026-06-18`.
- Treat `经理Agent` as an optional project-level status and recovery thread, not a main workflow agent.
- Maintain `docs/superpowers/agent-registry.md` as the project-level thread index.
- Maintain `worklog.md` for what each agent actually did, learned, and wants future agents to avoid.
- Do not auto-archive completed phase threads.
- Keep messages readable, not overly formal.
- Use file paths as the main content channel and summaries as secondary.
- Prefer dynamic lane count over always creating all lanes.
- Prefer direct lane-to-lane handoffs; `经理Agent` observes and intervenes rather than relaying every message.
- Keep Claude review and Codex subagent review as separate artifacts.
- Prefer a dedicated branch or worktree for code-writing execution lanes.
- Review the same branch or worktree that execution used.

## Open Questions

These need real project use before being locked into the skill:

1. Should the optional project-level `经理Agent` be created once manually, or should the first loop create it only when status/recovery is needed?
2. Should code-writing execution lanes default to Codex worktrees, or is a named branch in the local checkout enough for smaller work?
3. Should every agent be allowed to call `send_message_to_thread`, or should direct agent-to-agent messaging always copy 经理Agent through a ledger update?
4. How strict should write scope be for emergency fixes found during execution?
5. Should successful loops include a cleanup phase that archives or unpins old lane threads after user approval?
6. Should the project registry include model/thinking settings per lane, or is thread id plus title enough?

## Suggested Next Step

Use this protocol on one real medium-sized task before editing `loop-engineering/SKILL.md`.

After one trial, merge the stable parts into the skill:

- lane naming
- optional project status/recovery role and project registry
- message format
- ledger rules
- manager responsibilities
- dynamic lane selection
- cross-model review boundaries
- Codex thread tool policy
