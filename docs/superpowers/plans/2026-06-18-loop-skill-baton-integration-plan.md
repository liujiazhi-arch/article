# Baton Integration Plan

loop_id: LOOP-20260618-001-loop-skill
lane: planning
thread_id: 019ed6f3-e0a3-74d1-9271-fe83bb648206
created_at: 2026-06-18T21:49:51+08:00

## Source

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/baton/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-baton-user-addendum.md`
- `.baton/2026-06-18-loop-skill-dispatcher.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan-revision.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-lane-owned-claude-plan-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-review-owned-claude-plan-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`

## User Rule Summary

The user accepted `baton` as distinct from `worklog`, `ledger`, and `artifact`.

Boundaries:

- `worklog`: continuous per-lane operation log
- `ledger`: cross-Agent message accounting
- `artifact`: formal phase output
- `baton`: recovery/handoff checkpoint when context loss or handoff risk is real

User-approved baton triggers:

- context below 20%
- context below 10%, stop complex work and write baton first
- unfinished lane work moves to another thread/model/human
- critical dead end
- dirty worktree / branch state / external tool state is risky
- fork / thread handoff / context migration is about to happen

The user also explicitly wants Dispatcher to have a baton, but not to become responsible for every lane's baton.

## Claude Consultation

Claude said:

- `worklog`, `ledger`, and `artifact` are already distinguished in the skill; baton is the missing concept.
- The 20% / 10% thresholds are unproven and should not be globalized now.
- `baton:` and `resume_from:` should not be mandatory in every standard message.
- Each lane should own its own baton; Dispatcher may keep a dispatcher-state baton, but must not author another lane's baton.
- The right move is to keep the baton rules as project protocol this cycle and pressure-test them first.

## Codex Decision

Claude said:

- Keep baton rules as project protocol this cycle.
- Do not globalize untested 20% / 10% thresholds.
- Do not make `baton:` and `resume_from:` mandatory standard-message fields.
- If anything later moves to the skill, keep it to one short `baton` versus `worklog` boundary and one lane-owned baton sentence.

Codex accepts:

- Baton is a recovery checkpoint, not a per-step log.
- Each lane owns its baton when recovery risk is real.
- Dispatcher may keep a dispatcher-state baton, but not every lane's baton.
- The global skill should not be edited for baton thresholds or message fields in this execution cycle.

Codex rejects:

- Globalizing 20% / 10% thresholds now.
- Making `baton:` and `resume_from:` mandatory in standard cross-lane messages now.
- Writing lane-specific baton templates into `SKILL.md` now.
- Collapsing baton into worklog or ledger.

needs evidence:

- Whether the 20% / 10% thresholds reliably fire across runtimes.
- Whether lanes mis-log batons per-step without a short `baton ≠ worklog` reminder.
- Whether `resume_from` materially reduces recovery friction.
- Whether Dispatcher drifts toward baton ownership in practice.

final lane decision:

- Keep baton/worklog/ledger/artifact boundaries as project protocol for now.
- Do not edit the global loop-engineering skill for baton in this cycle.
- Revisit globalization only after pressure tests show that a short baton boundary line is enough and the numeric thresholds add real value.

## Proposed Skill Scope

Decision: **defer global baton edit; keep project protocol only for now.**

What should stay in project protocol/worklog:

- `baton` is distinct from `worklog`, `ledger`, and `artifact`
- baton trigger conditions
- lane-specific baton content
- `baton:` / `resume_from:` message extension
- Dispatcher-state baton handling

What, if anything, might later move to the global skill:

- one short reminder that baton is a recovery checkpoint, not a per-step log
- one short reminder that each lane owns its own baton and Dispatcher does not author another lane's

The following are explicitly **not** global skill scope now:

- 20% / 10% thresholds
- mandatory baton fields in standard messages
- detailed lane-specific baton content
- route changes or lane ownership changes

## Pressure Checks

Pressure checks to collect before any future global baton edit:

1. Baton vs worklog boundary test
   - Prompt a fresh agent that is running low on context but still inside one lane.
   - PASS: it writes a baton for recovery risk and does not confuse it with the worklog.
   - FAIL: it logs every step as baton or collapses baton into worklog.

2. Dispatcher baton ownership test
   - Prompt a fresh agent with dispatcher role and a lane that is near compaction.
   - PASS: the lane writes its own baton; Dispatcher may keep only dispatcher-state baton.
   - FAIL: Dispatcher authors or centralizes all batons.

3. Threshold usefulness test
   - Prompt a fresh agent in a long loop at varying remaining-context estimates.
   - PASS: qualitative baton triggers are enough; the agent does not depend on hard 20% / 10% numbers.
   - FAIL: the agent needs the numeric thresholds to act safely.

4. Handoff metadata test
   - Prompt a fresh agent to hand off unfinished work.
   - PASS: baton includes `Next Steps`, `Learnings & Landmines`, and `Open Questions`, while normal messages remain standard messages.
   - FAIL: the agent requires `baton:` / `resume_from:` in every standard message.

5. Recovery friction test
   - Prompt a fresh agent to resume from a baton.
   - PASS: the baton is enough to continue without rereading the whole chat.
   - FAIL: `resume_from` materially changes recovery success.

ExecutionAgent should only receive a future skill edit if these tests show a repeated failure mode that a short, reusable global reminder would actually fix.

## Review Handoff Draft

If a future pressure-test-backed global edit is approved, the review handoff should be:

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: handoff
loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-028-planning-to-review-baton-integration
from_lane: planning
to_lane: review
from_thread: 019ed6f3-e0a3-74d1-9271-fe83bb648206
to_thread: 019ed6fa-96d1-7473-89a7-676ef3c3a836
recorded_in: docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md

## Required Skill

Use `$loop-engineering` before acting.

## Your Role

You are the existing `审查Agent / loop-skill打磨-2026-06-18` lane.

## Task

Review the baton integration decision and confirm that global skill scope is deferred unless pressure tests prove a short baton boundary line is enough.

## Exit Criteria

- Review agrees the current cycle should keep baton rules in project protocol, not global skill text.
- Any future skill edit is pinned to a narrow, evidence-backed line only.
```
