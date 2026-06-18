# Lane-Owned Claude Plan Revision

loop_id: LOOP-20260618-001-loop-skill
lane: planning
thread_id: 019ed6f3-e0a3-74d1-9271-fe83bb648206
created_at: 2026-06-18T21:38:53+08:00

## Source

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-planning-owned-claude-analysis.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-review-owned-claude-plan-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-user-addendum.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-retrospective-brief.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Review Findings Addressed

- P1 execution scope ambiguity: resolved. Execution is authorized to make only the narrow Claude path-access fallback edit in or near `Claude Bridge`.
- P1 missing pressure gate: resolved. Execution must run fresh-agent baseline and post-edit pressure checks for scenario 2 and scenario 5, or record why direct multi-agent tooling was unavailable and run the strongest substitute.
- P2 Claude decision discipline: resolved. Planning accepts Claude's "one cross-project change" recommendation and defers the lane decision block and named Claude modes table from global `SKILL.md`.
- P3 Dispatcher sentence redundancy: resolved. Execution should verify existing Dispatcher boundary wording and must not duplicate it unless it finds a concrete contradiction.

## User Addendum Incorporated

The user's architecture decision is accepted:

- PlanningAgent, ExecutionAgent, ReviewAgent, and ArbitrationAgent may independently call Claude CLI when their lane needs it.
- Dispatcher must not centralize Claude communication.
- Each lane owns its inputs, Claude call, Claude output artifact, Codex evidence judgment, lane conclusion, and handoff.
- Claude output is evidence, not a command.

This revision does not put the full Claude modes table into the global skill yet. Instead, it uses the user addendum as project protocol for this loop and authorizes only the global rule that prevents Dispatcher from becoming a Claude content bridge when Claude cannot read required paths.

## Revised Execution Scope

Decision: **Option 1, narrow global skill edit only.**

ExecutionAgent may edit only `/Users/apple/.codex/skills/loop-engineering/SKILL.md`, and only in or near `Claude Bridge`.

Required skill behavior to encode:

- The lane that needs Claude is responsible for invoking Claude.
- If Claude cannot read a required live path, that lane must try an access fix such as `--add-dir` or create a temporary context artifact.
- If Claude still cannot access the path, the lane must record `partial: <path> unreadable` or the appropriate `review-unavailable` marker.
- Codex must verify the live path directly before accepting Claude claims about that path.
- Dispatcher must not become the content bridge for Claude path failures.

ExecutionAgent must not add:

- a global named Claude modes table
- a global lane decision block template
- `claude_debate` workflow text
- route matrices beyond the current lane selection table
- trial narratives or current loop ids
- extra Dispatcher or Manager authority wording

ExecutionAgent should verify the existing Dispatcher boundary already says Dispatcher is physical delivery only and not workflow authority.

## Deferred From Global Skill

Keep these in project protocol/worklog until pressure tests justify global inclusion:

- `independent_claude_plan`
- `claude_plan_critique`
- `claude_execution_consult`
- `claude_review`
- `claude_debate`
- the full lane artifact decision block:
  - `Claude said:`
  - `Codex accepts:`
  - `Codex rejects:`
  - `needs evidence:`
  - `final lane decision:`
- detailed route presets
- ledger timestamp ordering and close-out ownership rules
- examples from this trial

The execution report should still use the decision block as a project artifact pattern when discussing any Claude output.

## Pressure Verification Plan

ExecutionAgent must run baseline and post-edit pressure checks for at least scenarios 2 and 5.

Preferred method:

- Use direct multi-agent tooling if available in ExecutionAgent's tool list.
- Spawn a fresh agent or equivalent isolated context with a prompt that asks for route/role behavior.
- Record the exact prompt summary, tool used, artifact path, and pass/fail result in the execution report.

Fallback if direct multi-agent tooling is unavailable:

- Record `fresh-agent-pressure-unavailable: <reason>`.
- Use the strongest available substitute, in this order:
  1. Claude CLI isolated prompt with the current skill content or path access.
  2. A separate Codex subagent if available.
  3. A bounded self-check only if no isolated agent tooling exists, explicitly marked as weak evidence.

Scenario 2 baseline and post-edit:

- Prompt: a future task asks to edit `loop-engineering` or another skill/process document in a way that changes future agent behavior.
- Expected route: `Planning -> Plan Review -> Execution -> Review`.
- Expected failure if baseline lacks the rule: agent treats it as tiny docs or skips Plan Review.
- Post-edit pass: agent identifies it as process-changing and requires Plan Review before Execution.

Scenario 5 baseline and post-edit:

- Prompt: a lane needs Claude for review, but Claude cannot read `/Users/apple/.codex/skills/...`.
- Expected behavior: the lane using Claude tries `--add-dir` or creates a temporary context artifact; if still blocked, records `partial: <path> unreadable` or `review-unavailable`; Codex verifies the live path directly; Dispatcher does not summarize or bridge content.
- Post-edit pass: agent keeps Claude responsibility inside the lane and refuses to let Dispatcher become the Claude content bridge.

ExecutionAgent must include:

- baseline result
- edit made
- post-edit result
- whether evidence is strong or weak
- any residual risk

## Lane Decision

Claude said:

- The live skill already contains most route, Dispatcher, same-loop, metadata, and arbitration behavior.
- The one clearly missing global rule is Claude path-access fallback.
- Lane decision block and Claude modes table need evidence before global inclusion.

Codex accepts:

- Authorize only the lane-owned Claude path-access fallback edit in `Claude Bridge`.
- Require pressure verification for scenarios 2 and 5 in this execution cycle.
- Keep Dispatcher infrastructure-only.
- Keep lane-owned Claude independence as project protocol now, with only the access-fallback rule moving into the global skill.

Codex rejects:

- Adding a broad Claude modes section now.
- Adding the decision block template globally now.
- Adding `claude_debate` globally now.
- Duplicating Dispatcher boundary text unless execution finds a contradiction.
- Letting ExecutionAgent choose between narrow and broad scope.

needs evidence:

- Whether named Claude modes and the lane decision block materially improve fresh-agent behavior.
- Whether direct multi-agent pressure tooling is available to ExecutionAgent.

final lane decision:

- Send this revised plan to execution after Plan Review acceptance. Execution scope is unambiguous: edit only the Claude path-access fallback rule, run required pressure checks, and report evidence.

## Execution Handoff Draft

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: handoff
loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-026-planning-to-execution-lane-owned-claude-fallback
from_lane: planning
to_lane: execution
from_thread: 019ed6f3-e0a3-74d1-9271-fe83bb648206
to_thread: 019ed72a-2c15-7fa2-86df-d755c7728abd
delivered_by_lane: dispatcher
delivered_by_thread: 019ed67e-ab7c-7861-ba85-ddd12cc745c7
delivery_reason: PlanningAgent revised the plan after Plan Review; Dispatcher has physical thread-tool access
recorded_in: docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md

## Required Skill

Use `$loop-engineering` before acting. This is the same active loop.

## Your Role

You are the existing `执行Agent / loop-skill打磨-2026-06-18` lane.

## Source Artifacts

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan-revision.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-review-owned-claude-plan-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-user-addendum.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`

## Task

Apply only the narrow Claude path-access fallback edit in or near `Claude Bridge`. Do not add a broad Claude modes table, decision block template, `claude_debate`, route matrix, or trial narrative.

Run required pressure verification for scenario 2 and scenario 5 with baseline and post-edit results, using direct multi-agent tooling if available or recording the strongest substitute if unavailable.

## Boundaries

Allowed:

- Edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md` only in or near `Claude Bridge`.
- Write an execution report.
- Append one execution worklog row.

Forbidden:

- Do not edit business code.
- Do not create, pin, archive, fork, rename, or create threads.
- Do not broaden the global skill edit beyond the revised plan.
- Do not treat Dispatcher or Manager as workflow authority.

## Required Output

- execution report with changed text, verification commands, baseline/post-edit pressure evidence, and residual risk
- worklog row
- handoff to ReviewAgent for post-execution review

## Exit Criteria

- Skill edit is limited to Claude path-access fallback.
- Scenario 2 and scenario 5 pressure checks are recorded.
- Dispatcher remains infrastructure-only.
- ReviewAgent can inspect exact evidence.
```
