# Dispatcher Iteration Brief

loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-014-dispatcher-to-planning-dispatcher-iteration
created_at: 2026-06-18T03:51:19+08:00
dispatcher_thread: 019ed67e-ab7c-7861-ba85-ddd12cc745c7

## Goal

Optimize `/Users/apple/.codex/skills/loop-engineering/SKILL.md` so future substantial work can use a practical, traceable multi-agent workflow.

The user wants the current thread to act as `Dispatcher / 调度Agent`: it can create threads, deliver messages, poll progress, and maintain ledger/worklog. It must not become a main workflow agent or decide plan/review/arbitration content by authority.

## User Requirements To Preserve

- Different task types need different lane routes. Do not force every task into the same full path.
- Some tasks should run `Planning -> Plan Review -> Execution`.
- Some tasks may run `Planning -> Execution -> Review`.
- Some lightweight skill/documentation tasks may not need heavy implementation testing, but still need evidence and review proportional to risk.
- Execution-stage work that changes code or behavior needs review after execution.
- Claude is important and must participate as a strong independent model for planning and review where useful.
- Codex must arbitrate objectively by project evidence, not mechanically merge Claude and Codex outputs.
- Arbitration should explicitly classify disagreements: accept Claude, accept Codex, reject with evidence, third path, or needs more evidence.
- If a lane lacks thread-tool access, a `Dispatcher / 调度Agent` may physically deliver the message.
- Ledger must distinguish logical sender/receiver from physical delivery:
  - `from_lane`
  - `to_lane`
  - `delivered_by_lane`
  - `delivered_by_thread`
  - `delivery_reason`
- `经理Agent` remains project-level status/history/recovery, not the dispatcher and not the workflow owner.

## Scope

Allowed for this iteration:

- Produce independent planning artifacts from Codex planning lane and Claude CLI.
- Ask the existing review lane to review the plan before skill execution.
- Edit only `/Users/apple/.codex/skills/loop-engineering/SKILL.md` after plan review accepts a route.
- Update loop artifacts under `docs/superpowers/plans/`.

Forbidden:

- Do not create a new planning/review thread set for this same loop.
- Do not pin threads.
- Do not modify project business code.
- Do not treat the dispatcher as the planner, reviewer, or arbitrator.

## Expected Plan Output

The plan should propose a concise skill edit that covers:

- dynamic route selection by task risk and artifact type
- optional plan review before execution
- Dispatcher role and delivery metadata
- stronger Claude planning/review role
- objective arbitration rules for Claude/Codex disagreement
- proportional verification expectations for docs/skill/code/frontend/backend tasks

## Completion Criteria

- Existing `计划Agent` receives this brief and writes a plan artifact.
- Claude CLI writes an independent plan artifact.
- Existing `审查Agent` reviews the proposed route before execution.
- Skill edit is performed only after plan review.
- Worklog and ledger preserve every handoff.
