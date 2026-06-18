# Dispatcher Iteration Codex Plan

## Source

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-brief.md`
- `docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- Skill-writing guidance: keep the skill concise, avoid process bloat, and verify with pressure scenarios before treating the edit as deployed.

## Goal

Make `loop-engineering` practical for real tasks by adding a small route-selection model and a `Dispatcher / 调度Agent` delivery role without making Dispatcher, Manager, Claude, or Codex subagents workflow authorities. Planning, execution, review, and arbitration remain evidence-owned phase roles.

## Proposed Route Model

Add a compact route table under `Agent Lanes` or replace the current `Lane Selection` table:

| task type / risk | route | reason |
|---|---|---|
| tiny docs/config/no behavior change | current thread or `执行Agent` only, with evidence | avoid ceremony when review would add little signal |
| small skill/docs wording change | `Planning -> Plan Review -> Execution` when wording changes future agent behavior; otherwise current thread with proportional verification | process docs fail through ambiguity, so review the plan before editing |
| normal code change | `Planning -> Execution -> Review -> Arbitration` | execution evidence matters more than pre-review once scope is clear |
| risky architecture, migrations, public APIs, auth/data loss, frontend/backend linkage | `Planning -> Plan Review -> Execution -> Review -> Arbitration` | catch plan defects before expensive or risky implementation |
| unclear requirements | `Planning` only until plan-gap is resolved | avoid executing an ambiguous plan |
| repair after review | `Arbitration -> Execution Repair -> Review` when fix is non-trivial; arbitration may repair tiny documentation issues | keep repair ownership proportional |

Define `Plan Review` as review of planning artifacts before execution. It is not the same as post-execution code review.

## Proposed Skill Changes

1. Add a short `Route Selection` subsection that explicitly distinguishes:
   - `Planning -> Plan Review -> Execution` for risky plans, process docs, skill edits, unclear scope, or any task where executing the wrong plan is the main risk.
   - `Planning -> Execution -> Review` for ordinary implementation where the plan is clear and the main risk is implementation quality.
   - lightweight docs/skill routes where verification is proportional: file inspection, targeted `rg`, word/line count, and one fresh-agent pressure scenario if the edit changes agent behavior.

2. Add `Plan Review` as an optional lane state or review mode:
   - It can be performed by `审查Agent`, Claude CLI, Codex subagent, or both, depending on risk.
   - It reads only brief, plans, protocol, and relevant source files.
   - It must not edit code or the skill.
   - It should approve, reject, or require plan changes before execution.

3. Add `Dispatcher / 调度Agent` as a physical delivery role, not a workflow lane:
   - allowed: `send_message_to_thread`, progress polling, ledger/worklog maintenance, tool-mediated delivery when the logical sender lacks thread tools
   - forbidden: changing plan content, deciding review findings, arbitrating disagreements, acting as `经理Agent`, or becoming the main agent
   - rule: the logical `from_lane` and `to_lane` remain the phase owners even when Dispatcher physically sends the message

4. Extend ledger rules with delivery metadata:
   - `delivered_by_lane`
   - `delivered_by_thread`
   - `delivery_reason`
   - Keep `from_lane` and `to_lane` as logical ownership fields.
   - Existing ledgers without these fields remain valid, but new dispatcher-mediated messages should include them.

5. Strengthen Claude usage without making Claude authoritative:
   - For risky planning, ask Claude for independent plan critique or plan review before execution.
   - For risky execution, ask Claude for read-only review after execution.
   - If Claude CLI fails, record the failure and continue only if the route allows a Codex-only fallback; otherwise mark the review unavailable and escalate.

6. Tighten arbitration language:
   - Dispositions must classify disagreements as `accept Claude`, `accept Codex`, `reject both`, `third path`, `defer`, or `needs more evidence`.
   - A model wins only when its claim has stronger artifact evidence.
   - If evidence is insufficient, arbitration must gather evidence or stop; it must not average opinions.

## Claude Role

Claude should be a strong independent participant at two points:

- Planning: independent plan or plan-review critique for risky tasks, process changes, architecture, public contracts, and ambiguous requirements.
- Review: read-only post-execution review for risky code, behavior changes, user-facing flows, and skill/process edits with lasting impact.

Claude output remains an artifact, not an instruction override. Codex arbitration accepts or rejects Claude claims by evidence, citing source files, command output, screenshots, or explicit `not verified`.

## Dispatcher Boundaries

Dispatcher exists because some physical thread-tool actions are available only from specific threads. It should be described as a courier plus recorder:

- It can create or send to threads only when a logical lane asks or when the route requires delivery.
- It can poll progress and update ledger/worklog status.
- It must preserve logical ownership fields in every message.
- It must not decide route content after a plan is accepted.
- It must not replace `计划Agent`, `审查Agent`, `仲裁Agent`, or `经理Agent`.
- `经理Agent` remains status/history/recovery only and should not become Dispatcher by default.

## Verification / Plan Review

Before execution of this skill edit:

- Existing `审查Agent` should review this plan and any Claude plan/critique.
- Review should check whether the route model is minimal, whether Dispatcher is non-authoritative, and whether Claude is strong but evidence-bound.

After execution:

- Inspect skill text with `sed -n`.
- Search required terms:
  - `rg "Plan Review|调度Agent|delivered_by_lane|delivery_reason|accept Claude|needs more evidence" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- Search for unwanted authority wording:
  - `rg "Dispatcher.*decide|调度Agent.*仲裁|经理Agent.*owner|manager.*authority" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- Run `wc -l` or `wc -w` and keep growth modest.
- For the skill-writing bar, run at least one pressure scenario or review prompt that asks a fresh agent how it routes:
  - a tiny docs typo
  - a skill-process edit
  - a risky code migration
  - a dispatcher-mediated handoff where physical sender differs from logical sender

## Risks

- Adding route options may make the skill feel vague. Mitigate with a small table and concrete task examples.
- Dispatcher can become a hidden manager if the skill says it can decide routes. Keep it physical-delivery-only.
- Plan review can become mandatory ceremony for ordinary code. Limit it to risky, ambiguous, or process-shaping work.
- Claude can be over-weighted by model identity. Require artifact evidence for every accepted claim.
- Lightweight verification can become no verification. Require at least file inspection and targeted search for docs/skill edits.

## Not Doing

- Do not rewrite the whole skill.
- Do not change the current five-step workflow except by adding route selection around it.
- Do not make Dispatcher or Manager a workflow authority.
- Do not require full tests for every documentation-only edit.
- Do not remove post-execution review for behavior-changing code.
- Do not create new lane threads or pin threads for this planning artifact.
