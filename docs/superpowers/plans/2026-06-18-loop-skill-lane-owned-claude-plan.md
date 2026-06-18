# Lane-Owned Claude Workflow Plan

loop_id: LOOP-20260618-001-loop-skill
lane: planning
thread_id: 019ed6f3-e0a3-74d1-9271-fe83bb648206
created_at: 2026-06-18T21:27:41+08:00

## Source

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/plugins/cache/github-superpowers/github-superpowers/5.1.0/skills/writing-skills/SKILL.md`
- `/Users/apple/.codex/plugins/cache/github-superpowers/github-superpowers/5.1.0/skills/test-driven-development/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-retrospective-brief.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-claude-retrospective-reference.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-ledger-metadata-repair-review.md`
- Planning-owned Claude artifact: `docs/superpowers/plans/2026-06-18-loop-skill-planning-owned-claude-analysis.md`

## Planning-Owned Claude Analysis

Claude said:

- The live skill already covers route selection, Plan Review, Dispatcher as courier, `经理Agent` as status/recovery, same-loop reuse, delivery metadata, and evidence-based arbitration.
- The most important missing reusable rule is Claude path-access fallback.
- Lane-owned Claude modes and the `Claude said / Codex accepts / Codex rejects / needs evidence / final lane decision` shape are useful, but should be compact and pressure-tested before adding more text.
- Plan Review should happen before execution because this is a process/skill edit.

Codex accepts:

- Add a narrow Claude path-access fallback rule to the skill.
- Keep Dispatcher as infrastructure only.
- Require each lane to own its Claude call and lane decision.
- Use Plan Review before execution.
- Route any edit through the existing active loop and existing lanes.

Codex rejects:

- Adding a full route-preset matrix, long Claude-mode guide, or detailed per-loop lessons to the skill.
- Treating Dispatcher-owned Claude retrospective as the future pattern.
- Treating this as lightweight docs-only work with no Plan Review.

needs evidence:

- Whether a compact lane-owned Claude mode list belongs in `SKILL.md` or only in project protocol.
- Whether `claude_debate` should be an explicit supported mode before a real disagreement requires it.

final lane decision:

- Plan a minimal skill refinement centered on lane-owned Claude responsibility and path-access fallback. Keep most retrospective detail in project artifacts.

## Trial Lessons Accepted

- Same active loop corrections must reuse existing `loop_id` and owner lanes.
- Dispatcher may physically deliver messages, poll, and maintain ledger/worklog, but must not own plan, review, execution, arbitration, or Claude content.
- Claude output is evidence; each lane must judge it against Codex-visible artifacts.
- Ledger metadata must separate logical `from_lane` / `to_lane` from physical `delivered_by_lane` / `delivered_by_thread` / `delivery_reason`.
- Claude path access is not guaranteed, even when CLI is available.
- Skill edits that change future agent behavior need Plan Review and pressure scenarios.

## Trial Lessons Rejected Or Deferred

- Do not move all route presets and trial narratives into the skill. Keep them in protocol/worklog unless repeated failures show agents need the detail inline.
- Defer a mandatory `route_decision` artifact. A brief or lane map field is enough for now.
- Defer a full `claude_debate` workflow. Mention only if needed after a real Claude/Codex disagreement.
- Do not make ledger timestamp ordering a major skill section. If encoded at all, it should be a short protocol/worklog rule: `seq` is authoritative; wall-clock can be non-monotonic.

## Proposed Skill Changes

Make a small edit, preferably by replacing or extending existing text rather than adding a new long section:

1. In `Claude Bridge`, add lane ownership and path-access fallback:
   - The lane that needs Claude calls Claude itself.
   - If Claude cannot read a required live path, the lane must try `--add-dir` or create a temporary context artifact.
   - If access still fails, the Claude artifact must say `partial: <path> unreadable`.
   - Codex must verify the live path directly before accepting Claude claims about it.
   - On routes where Claude is required, unavailable Claude blocks close-out or triggers user escalation; it is not silently replaced by Codex.

2. Add a compact lane-owned Claude decision block requirement:
   - `Claude said:`
   - `Codex accepts:`
   - `Codex rejects:`
   - `needs evidence:`
   - `final lane decision:`

3. Add a compact Claude modes list only if it can replace existing wording without bloat:
   - `independent_claude_plan`: PlanningAgent
   - `claude_plan_critique`: PlanningAgent
   - `claude_execution_consult`: ExecutionAgent
   - `claude_review`: ReviewAgent
   - `claude_debate`: PlanningAgent or ArbitrationAgent, max 1-2 bounded rounds, only for substantive disagreement

4. Add one Dispatcher boundary sentence if current wording is not considered strong enough:
   - Dispatcher may deliver Claude-related prompts only as infrastructure; it must not select Claude mode, summarize Claude for another lane, or become the content bridge.

## Project-Artifact-Only Rules

Keep these out of `SKILL.md` unless future failures repeat:

- Full route preset matrix with examples.
- The detailed MSG-019 to MSG-021 repair narrative.
- Concrete thread ids, timestamps, and current loop names.
- Current project registry details.
- Full pressure scenario scripts and results.
- Detailed ledger close-out ownership policy beyond a concise rule.
- Non-monotonic timestamp examples.
- The transitional Dispatcher-owned Claude retrospective.

## Route Presets

For this iteration:

- Route: `Planning -> Plan Review -> Execution -> Review`.
- Reason: this is a process/skill edit that changes future agent behavior.
- Use existing lanes. Do not create new threads.
- Arbitration is only needed if Plan Review or post-execution Review finds disputed P0/P1/P2 issues.

Future route guidance should remain risk-based:

- Tiny docs/config: current thread or `执行Agent` only with evidence.
- Skill/process edit: `Planning -> Plan Review -> Execution -> Review`.
- Normal clear-scope code: `Planning -> Execution -> Review -> Arbitration`.
- Risky architecture/frontend-backend/auth/data-loss: `Planning -> Plan Review -> Execution -> Review -> Arbitration`.
- Unclear requirements: `Planning` only until `plan-gap` is resolved.
- Post-review repair: `Arbitration -> Execution repair -> Review` unless the fix is tiny docs.

## Lane-Owned Claude Modes

Claude modes should be owned by the lane that needs them:

- `independent_claude_plan`: PlanningAgent asks Claude for an independent plan before Codex merges.
- `claude_plan_critique`: PlanningAgent asks Claude to critique a Codex plan before execution.
- `claude_execution_consult`: ExecutionAgent asks Claude for read-only implementation-risk analysis; ExecutionAgent still decides and writes the report.
- `claude_review`: ReviewAgent asks Claude for read-only findings; ReviewAgent keeps Claude and Codex review artifacts independent.
- `claude_debate`: PlanningAgent or ArbitrationAgent uses bounded debate only for substantive unresolved disagreement.

Dispatcher must not own any of these modes.

## Dispatcher Boundary

Dispatcher is infrastructure:

- allowed: create/find threads when asked by route, physically send standard messages, poll status, maintain ledger/worklog, nudge missing artifacts
- forbidden: write plan content, run Claude analysis for another lane, summarize Claude as the lane decision, decide execution scope, review findings, arbitrate disagreements, or act as `经理Agent`

If Dispatcher physically sends a message, ledger must preserve:

- logical owner: `from_lane` / `to_lane`
- physical sender: `delivered_by_lane` / `delivered_by_thread` / `delivery_reason`

## Ledger / Worklog Close-Out Rules

Minimal skill-level rule:

- Every `send_message_to_thread` row should eventually move from `sent` to `completed`, `blocked`, `retry-needed`, or `superseded`.

Project protocol/worklog detail:

- Use `seq` as primary ordering when timestamps are non-monotonic.
- Receiving lane normally closes its inbound row when it produces the required artifact.
- Dispatcher may reconcile stale statuses after polling.
- Every lane appends one worklog row before handoff or close-out.

## Pressure Scenarios

Future skill edits should be verified with fresh-agent pressure scenarios, not only self-checks:

1. Tiny README typo.
   - Expected: no lane chain, no Plan Review.

2. Edit to `loop-engineering` behavior.
   - Expected: existing loop route uses `Planning -> Plan Review -> Execution -> Review`.

3. Dispatcher-mediated message where physical sender differs from logical sender.
   - Expected: `from_lane` and `to_lane` stay logical; delivery metadata records Dispatcher.

4. User says to retest or refine the same active loop.
   - Expected: reuse existing `loop_id` and owner lane.

5. Claude cannot read a required live path.
   - Expected: lane tries access fix or context artifact; Claude artifact says `partial`; Codex verifies live path before accepting claims.

6. Claude and Codex disagree on severity.
   - Expected: lane or arbitration records accepts/rejects/needs evidence by artifact evidence, not model identity.

## Execution Recommendation

ExecutionAgent is needed after Plan Review because the target is a global skill file. Execution should:

- edit only `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- keep the edit small
- write an execution report
- record verification output
- append one worklog row
- hand off to existing ReviewAgent

## Plan Review Recommendation

Plan Review should happen before execution.

Review should check:

- the plan keeps Dispatcher infrastructure-only
- Claude is lane-owned
- Claude path-access failure is handled by the lane that needs Claude
- the proposed skill change is minimal
- project-only details are not moved into the skill
- pressure scenarios are clear enough for execution/review
