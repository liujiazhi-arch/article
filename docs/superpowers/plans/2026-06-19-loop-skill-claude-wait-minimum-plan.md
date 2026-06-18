# Claude Wait Minimum Planning Note

loop_id: LOOP-20260618-001-loop-skill
lane: planning
thread_id: 019ed6f3-e0a3-74d1-9271-fe83bb648206
created_at: 2026-06-19T01:11:40+08:00
claude_policy: not_needed
claude_reason: User correction is narrow, source evidence is direct, and no model judgment is needed.

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-claude-wait-minimum-addendum.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Current Wording Evidence

- The user addendum states the required correction at `docs/superpowers/plans/2026-06-19-loop-skill-claude-wait-minimum-addendum.md:7-21`: deep required Claude plan/review calls should wait at least five minutes before declaring timeout, unless Claude returns earlier or the CLI exits/errors.
- The current reference says ordinary calls use the default timeout at `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md:24`.
- The current reference says deep required planning/review calls should "allow a five-minute wait window before declaring timeout" at `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md:25`.
- The live skill only points readers to the reference for "five-minute waits" at `/Users/apple/.codex/skills/loop-engineering/SKILL.md:117`; it does not define the detailed timeout semantics inline.

## User Correction Summary

The correction is semantic, not cosmetic:

- "allow a five-minute wait window" can be interpreted as a soft upper bound or permission to wait up to five minutes.
- The user wants a minimum wait rule: do not declare timeout for deep required Claude planning/review calls before five minutes have elapsed, unless Claude returns earlier or the CLI exits/errors.
- The correction must not become unlimited waiting. Ordinary Claude calls still use the normal timeout unless a lane records why a longer wait is required.

## Decision

No-op vs narrow edit: narrow edit required.

Reason:

- The current reference wording does not fully encode the minimum-wait rule.
- The live skill delegates this detail to `references/claude-policy.md`, so the narrowest correct edit is in that reference only.
- No PlanningAgent edit to the global skill or reference is allowed in this lane.

## Exact ExecutionAgent Scope

Approved next lane: existing `执行Agent`.

Thread id: `019ed72a-2c15-7fa2-86df-d755c7728abd`.

ExecutionAgent may edit only:

- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`

ExecutionAgent must not edit:

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`
- business code
- thread, pin, archive, fork, branch, commit, or PR state

Required wording change:

- Replace the deep required Claude wait bullet with wording equivalent to:

```text
For deep required Claude planning or review calls, wait at least five minutes before declaring timeout unless Claude returns earlier or the CLI exits/errors. Record the command shape, elapsed wait, and whether the wait was ordinary or deep required review.
```

Do not generalize this into unlimited waiting.

## Verification Expectations

ExecutionAgent should record exact output:

```bash
rg -n "wait at least five minutes|unless Claude returns earlier|elapsed wait|allow a five-minute wait window" /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
```

Expected:

- The new minimum-wait wording is present.
- The old ambiguous phrase `allow a five-minute wait window` is absent.

## Artifact-First ExecutionAgent Handoff Draft

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: execution_handoff
loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-040-planning-to-execution-claude-wait-minimum
from_lane: planning
to_lane: execution
from_thread: 019ed6f3-e0a3-74d1-9271-fe83bb648206
to_thread: 019ed72a-2c15-7fa2-86df-d755c7728abd
delivered_by_lane: dispatcher
delivered_by_thread: current dispatcher thread
delivery_reason: PlanningAgent found the user's five-minute minimum wait correction requires a narrow reference wording edit
recorded_in: docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md
claude_policy: not_needed
claude_reason: This is a narrow wording edit with direct source evidence.

## Required Skill

Use `$loop-engineering` before acting.

## Your Role

You are the existing `执行Agent / loop-skill打磨-2026-06-18` lane. Dispatcher is only physical delivery and bookkeeping.

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-claude-wait-minimum-plan.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-claude-wait-minimum-addendum.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Compact Summary

Read the planning artifact directly. The only approved edit is to strengthen `references/claude-policy.md` from a soft five-minute wait window to a minimum wait rule for deep required Claude plan/review calls.

## Task

Edit only `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md` as specified in the planning artifact, then write a brief execution report and append one execution worklog row.

## Boundaries

Forbidden:

- Do not edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.
- Do not edit other references.
- Do not edit business code.
- Do not create, pin, archive, fork, rename, or create threads.
- Do not create commits or PRs.

## Required Output

- Narrow reference wording edit.
- Execution report with exact `rg` verification output.
- Worklog row.

## Exit Criteria

- The reference says deep required Claude planning/review calls must wait at least five minutes before timeout unless Claude returns earlier or CLI exits/errors.
- The ambiguous phrase `allow a five-minute wait window` is absent.
- The rule does not imply unlimited waiting or alter ordinary Claude timeout behavior.
```
