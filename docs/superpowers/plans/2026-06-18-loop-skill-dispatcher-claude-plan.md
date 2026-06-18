# Claude Plan: Dispatcher-Aware Loop Skill Update

## Source

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md` was requested, but Claude reported that it could not read the live `.codex` path in its session.
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-brief.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-codex-plan.md`
- `docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Goal

Make `loop-engineering` route work by risk instead of forcing one full lane path, and add a `Dispatcher / 调度Agent` that is purely a courier and recorder. Do this as a small additive edit to the existing skill, not a rewrite.

## What To Add To SKILL.md

1. Fold route selection into the existing lane selection table. Avoid adding a parallel route table if the current table can be extended.
2. Define `Plan Review` as distinct from plan merge. Merge synthesizes drafts; Plan Review gives an independent accept, reject, or require-changes verdict before execution.
3. Add `Dispatcher / 调度Agent` as a delivery-only role. Allowed actions are `send_message_to_thread`, `read_thread` progress polling, ledger/worklog maintenance, and tool-mediated delivery when the logical sender lacks thread tools.
4. Extend ledger guidance with optional delivery metadata: `delivered_by_lane`, `delivered_by_thread`, and `delivery_reason`. Keep `from_lane` and `to_lane` as logical ownership fields.
5. Encode Claude CLI failure handling from this loop's evidence: record failure, retry through stdin when useful, and mark Claude unavailable instead of silently fabricating or ignoring the artifact.
6. Tighten arbitration labels to `accept Claude`, `accept Codex`, `reject both`, `third path`, `defer`, and `needs more evidence`.

## What To Avoid

- A second route table that duplicates the existing lane selection table.
- Making `Plan Review` mandatory for ordinary clear-scope code changes.
- Any wording that lets Dispatcher decide route content, plan content, review findings, or arbitration outcomes.
- Making `经理Agent` the Dispatcher by default.
- Requiring full test suites for documentation-only or skill-text edits.

## Suggested Route Rules

| task type / risk | lanes | plan_review before execution? |
|---|---|---|
| tiny docs/config, no behavior change | current thread or `执行Agent` only | no |
| skill/process/doc edit that changes future agent behavior | `计划Agent -> 审查Agent(plan) -> 执行Agent -> 审查Agent` | yes |
| normal code change, clear scope | `计划Agent -> 执行Agent -> 审查Agent -> 仲裁Agent` | no |
| risky architecture, migration, public API, auth/data-loss, frontend/backend linkage | full lane set | yes |
| unclear requirements | `计划Agent` only until `plan-gap` resolved | gate, do not execute |
| repair after review | `仲裁Agent -> 执行Agent repair -> 审查Agent`; tiny docs fixes may be repaired in arbitration | n/a |

Principle: plan review guards against executing the wrong plan; post-execution review guards against bad implementation.

## Dispatcher Boundary

Dispatcher exists only because some physical thread-tool actions are available from specific threads.

- Dispatcher may create/send to threads when a logical lane requests it or the route requires delivery.
- Dispatcher may poll progress and maintain ledger/worklog.
- Dispatcher-delivered messages keep the originating phase lane in `from_lane` and `to_lane`.
- Dispatcher records itself only in `delivered_by_lane`, `delivered_by_thread`, and `delivery_reason`.
- Dispatcher must not change accepted plan content, decide findings, arbitrate, or stand in for `计划Agent`, `审查Agent`, `仲裁Agent`, or `经理Agent`.
- `经理Agent` remains project-level status/history/recovery and does not become Dispatcher by default.

## Claude/Codex Disagreement Handling

- Claude is a strong independent participant for plan critique/plan review on risky, ambiguous, or process-changing work, and for read-only post-execution review on behavior-changing or lasting-impact work.
- Claude output is an artifact, never an instruction override.
- Codex arbitration judges by artifact evidence, not model identity.
- No-evidence claim becomes `needs more evidence`; arbitration then gathers evidence or stops.

## Verification

Execution should verify the live skill from Codex, because Claude could not read the `.codex` path:

- `rg "Plan Review|调度Agent|delivered_by_lane|delivery_reason|accept Claude|accept Codex|needs more evidence" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `rg "Dispatcher.*decide|调度Agent.*仲裁|经理Agent.*(owner|dispatcher)|Dispatcher.*main agent" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- Confirm the route guidance is not duplicated into multiple conflicting tables.
- `wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md` before and after; keep growth modest.
- Run a pressure scenario or self-check covering a one-line docs typo, a skill-process edit, a risky migration, and dispatcher-mediated handoff fields.
- Verify the same-active-loop reuse rule and cross-model section remain intact.

## Risks

- Route vagueness if the skill adds many prose options instead of a compact table.
- Dispatcher drifting into hidden manager.
- Plan Review becoming ceremony.
- Ledger schema churn if every row is widened unnecessarily.
- Model-identity bias if Claude or Codex claims are accepted without evidence.
- Verification gap from Claude path permissions; record this limitation in worklog and have Codex execution/review verify the live skill.
