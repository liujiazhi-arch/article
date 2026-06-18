# User Addendum: Lane-Owned Claude Independence

loop_id: LOOP-20260618-001-loop-skill
recorded_by_lane: dispatcher
thread_id: 019ed67e-ab7c-7861-ba85-ddd12cc745c7
created_at: 2026-06-18T21:35:27+08:00

## Source

- User message in the Dispatcher thread after ReviewAgent returned `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan-review.md`.
- Active loop remains `LOOP-20260618-001-loop-skill`.

## User Decision

The user confirmed the intended architecture:

- Each lane, including `计划Agent`, `执行Agent`, and `审查Agent`, should independently call Claude CLI when useful.
- Dispatcher must not be the place where all Claude communication happens.
- Dispatcher is communication infrastructure only:
  - create or find threads
  - deliver standard messages
  - poll thread status
  - maintain ledger/worklog
  - remind lanes when expected artifacts are missing
- Each lane owns its own Claude-supported reasoning:
  - read its own inputs
  - call Claude itself
  - save Claude raw or summarized output
  - judge Claude's suggestions with Codex-visible evidence
  - write its lane conclusion artifact
  - hand artifact paths to the next lane

## Claude Modes To Consider

The user wants the workflow to support lane-owned Claude communication patterns, such as:

- `independent_claude_plan`: PlanningAgent asks Claude for an independent plan before Codex plan synthesis.
- `claude_plan_critique`: PlanningAgent asks Claude to critique a Codex plan.
- `claude_execution_consult`: ExecutionAgent asks Claude for read-only implementation-risk analysis when plan or implementation risk is unclear.
- `claude_review`: ReviewAgent asks Claude for read-only review, then performs Codex review judgment.
- `claude_debate`: PlanningAgent or ArbitrationAgent uses bounded debate only when Codex and Claude have a substantive disagreement.

These modes are not Dispatcher-owned.

## Required Judgment Shape

When a lane uses Claude, the lane artifact should make the decision boundary visible:

```text
Claude said:
Codex accepts:
Codex rejects:
needs evidence:
final lane decision:
```

Claude output is evidence, not an instruction override.

## Path Access Pitfall

If Claude cannot read paths such as `/Users/apple/.codex/skills/...`, the lane that needs Claude must handle it itself:

- try an appropriate `--add-dir`
- or create a temporary context artifact with the needed content
- if still unavailable, record the unreadable path and make the Claude artifact partial

Dispatcher must not compensate by becoming the Claude bridge for that lane.

## Planning Revision Implication

PlanningAgent must reconcile this user addendum with the ReviewAgent Plan Review:

- ReviewAgent did not approve immediate execution.
- ReviewAgent required the plan to pin the global skill edit scope and wire pressure-test gates.
- The user addendum strengthens the requirement that Claude independence is lane-owned, not Dispatcher-owned.
- If PlanningAgent proposes adding more than the path-access fallback to `/Users/apple/.codex/skills/loop-engineering/SKILL.md`, it must justify why the extra text belongs in the global skill rather than only in protocol/worklog artifacts.
