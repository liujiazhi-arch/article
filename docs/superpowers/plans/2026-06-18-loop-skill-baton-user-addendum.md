# Baton / Worklog / Ledger / Artifact User Addendum

loop_id: LOOP-20260618-001-loop-skill
source_lane: user
recorded_by_lane: dispatcher
recorded_by_thread: 019ed67e-ab7c-7861-ba85-ddd12cc745c7
created_at: 2026-06-18T21:43:25+08:00

## User Decision

The user accepted using `baton`, but explicitly separated it from `worklog`.

Durable boundaries:

- `worklog`: every Agent's continuous operation log. It records what the lane did, where evidence lives, what failed, and what should be remembered. It is used by `经理Agent`, `Dispatcher`, later ReviewAgents, and future lane recovery.
- `baton`: context-loss or handoff recovery package. It is an emergency checkpoint that lets a new lane/session continue without reading the entire chat. It should not be written for every step.
- `ledger`: cross-Agent message ledger.
- `artifact`: formal phase output, such as plan, execution report, review, arbitration, or final report.

## Required Baton Triggers

Each lane should write a baton when:

- context remaining is below 20%
- lane work is unfinished and control is moving to another thread, model, or human
- execution hits a critical dead end
- dirty worktree, branch state, or external tool state becomes complex enough that recovery risk is high
- fork, thread handoff, or other context migration is about to happen

If context remaining is below 10%, the lane should stop complex task work and write the baton first.

## Lane-Specific Baton Content

PlanningAgent baton should preserve:

- why this workflow route was chosen
- which routes were excluded
- Claude/Codex disagreements
- current plan gaps or unresolved questions
- who should receive the next handoff

ExecutionAgent baton should preserve:

- files changed so far
- verification already run
- pitfalls already hit
- areas not to touch
- the literal next command if interrupted

ReviewAgent baton should preserve:

- artifacts already read
- confirmed findings
- suspected findings
- areas not yet reviewed
- whether the next message should go back to ExecutionAgent or PlanningAgent

Dispatcher baton should preserve:

- active loop id and thread ids
- latest ledger rows and whether they were actually delivered
- lane statuses known from `read_thread`
- missing artifacts or blockers
- the exact next delivery or polling action

## Handoff Message Extension

When a baton exists, a standard cross-lane message should include:

```text
baton: <path>
resume_from: <section, usually Next Steps>
```

This lets the next lane recover from the baton without making Dispatcher carry content in its own context.

## Planning Question

PlanningAgent should decide whether these baton trigger rules are ready for the global `loop-engineering` skill now, or whether they should first remain as project protocol and be pressure-tested.

PlanningAgent must not let Dispatcher become responsible for every lane's baton. Each lane owns its own baton when its context or handoff risk requires it.
