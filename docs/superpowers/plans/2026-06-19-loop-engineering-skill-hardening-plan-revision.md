# Loop Engineering Skill Hardening Plan Revision

loop_id: LOOP-20260618-001-loop-skill
lane: planning
thread_id: 019ed6f3-e0a3-74d1-9271-fe83bb648206
created_at: 2026-06-19T00:54:27+08:00
approved_for_execution: yes

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review-claude.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`
- `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

PlanningAgent did not run a new Claude call for this revision. ReviewAgent already ran ReviewAgent-owned Claude critique on the exact plan, and the remaining work is a bounded scope decision grounded in that critique and line-count evidence.

## P1 Resolution

### P1: File-Length Scope

Resolution: choose `SKILL.md` plus two references.

Evidence:

- Live `SKILL.md` is already 461 lines by `wc -l`.
- `skill-creator` says to keep `SKILL.md` under 500 lines and split content when approaching that limit.
- ReviewAgent and ReviewAgent-owned Claude both found the original `SKILL.md`-only scope likely to exceed the progressive-disclosure guidance.

Decision:

- ExecutionAgent may keep only routing, hard boundaries, and reference pointers in `SKILL.md`.
- ExecutionAgent may create exactly:
  - `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
  - `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`
- This is not a broad documentation split. It is the minimum split needed to keep the live skill lean while preserving the user lessons.

### P1: Claude Policy Formalism

Resolution: tier the policy.

ExecutionAgent must not require the full Claude-policy block for mechanical messages. Use this rule:

- `required`: include `claude_policy`, `claude_mode`, `claude_reason`, `required_claude_artifact`, and `fallback_if_claude_unavailable`. Lane cannot close unless it writes the Claude artifact or records `claude-unavailable: <reason>` and whether that blocks the lane.
- `conditional`: include `claude_policy`, `claude_mode`, `claude_reason`, and fallback only when Claude is actually invoked or the risk is actively considered. If skipped, write `Claude skipped: <reason>`.
- `not_needed`: for Dispatcher delivery, status polling, ledger bookkeeping, manager status lookup, tiny docs/config fixes, or mechanical execution of already-reviewed narrow scope, allow compact `claude_policy: not_needed` plus short reason. Do not require mode/artifact/fallback fields unless useful.

If Claude is used in any lane artifact, include:

```text
Claude said:
Codex accepts:
Codex rejects:
needs evidence:
final lane decision:
```

## Exact Execution Scope

ExecutionAgent may edit:

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`

ExecutionAgent may create:

- `/Users/apple/.codex/skills/loop-engineering/references/` if absent.

ExecutionAgent must not edit:

- business code under `/Users/apple/Desktop/article`
- unrelated skill files
- `agents/openai.yaml`
- any reference file other than the two named above
- thread, pin, archive, fork, branch, commit, or PR state

`SKILL.md` edit requirements:

- Keep the description as trigger-focused, not a workflow summary.
- Add or tighten a short Decision Gate before the full workflow so tiny work does not default to the full loop.
- Add concise pointers to `references/claude-policy.md` and `references/forward-tests.md`, with clear when-to-read guidance.
- Preserve: artifact-first handoff, no default pinning, Dispatcher infrastructure-only, lane-owned Claude, five-minute wait window for deep required Claude plan/review calls, and worklog/ledger/artifact/baton separation.
- Change `set_thread_pinned` guidance to avoid by default and use only when the user explicitly asks.
- Keep `SKILL.md` near or under 500 lines after the edit. If it cannot stay under 500 while preserving the approved scope, stop and return to PlanningAgent with evidence instead of adding more inline text.

`references/claude-policy.md` requirements:

- Define `required`, `conditional`, and `not_needed`.
- Include lane-owned Claude responsibilities.
- State that Dispatcher and `经理Agent` must not run Claude on behalf of lanes.
- Include the five-minute wait window for deep required Claude plan/review calls, while keeping the default hard timeout for ordinary calls as already stated in `SKILL.md`.
- Include path-access fallback: the lane that needs Claude handles `--add-dir` or a temporary context artifact; Dispatcher does not bridge content.
- Include the lane decision block shown above.

`references/forward-tests.md` requirements:

- Include compact pressure scenarios for:
  - same active loop correction reuses existing owner lane
  - skill/process edits route through Planning -> Plan Review -> Execution -> Review
  - Dispatcher physically delivers but does not plan/review/arbitrate
  - lane-owned Claude path-access failure is handled by the lane
  - `not_needed` tiny docs/config work stays lightweight
  - `conditional` Claude skip records a reason
  - context risk writes baton instead of treating worklog as recovery state
  - artifact-first handoff sends artifact paths instead of re-expanding full plans
- Include leak hygiene: forward-test prompts must look like real user tasks and must not leak expected answers, intended fixes, or prior conclusions.

## Verification Expectations

ExecutionAgent must record exact output in its execution report:

```bash
wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md
test -f /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
test -f /Users/apple/.codex/skills/loop-engineering/references/forward-tests.md
rg -n "Decision Gate|claude_policy|references/claude-policy.md|references/forward-tests.md|set_thread_pinned|Dispatcher|artifact-first|baton" /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "required|conditional|not_needed|Claude skipped|claude-unavailable|Claude said|Codex accepts|Dispatcher|--add-dir|five-minute|5-minute" /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
rg -n "same active loop|Plan Review|Dispatcher|path-access|not_needed|conditional|baton|artifact-first|leak" /Users/apple/.codex/skills/loop-engineering/references/forward-tests.md
```

ExecutionAgent should also inspect the edited files manually enough to confirm:

- `SKILL.md` remains the compact entry point.
- Reference files are directly discoverable from `SKILL.md`.
- `not_needed` does not impose heavy formalism.
- Deep required Claude calls have a five-minute wait-window rule.
- Dispatcher remains infrastructure only.

## Next Step

Next lane: existing `执行Agent`.

Thread id: `019ed72a-2c15-7fa2-86df-d755c7728abd`.

No additional Plan Review is required before execution because this revision selects one of the two scopes ReviewAgent explicitly requested and resolves both P1 blockers. If ExecutionAgent finds the scope cannot be implemented without violating the 500-line rule or expanding beyond the two reference files, it must stop and return to PlanningAgent.

## Artifact-First ExecutionAgent Handoff Draft

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: execution_handoff
loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-037-planning-to-execution-hardening-revision
from_lane: planning
to_lane: execution
from_thread: 019ed6f3-e0a3-74d1-9271-fe83bb648206
to_thread: 019ed72a-2c15-7fa2-86df-d755c7728abd
delivered_by_lane: dispatcher
delivered_by_thread: current dispatcher thread
delivery_reason: PlanningAgent resolved ReviewAgent P1 blockers and approved bounded execution scope
recorded_in: docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md
claude_policy: conditional
claude_mode: claude_execution_consult | n/a
claude_reason: ExecutionAgent may consult Claude only if implementation scope or reference split becomes non-obvious; otherwise this is a bounded, reviewed skill edit.
required_claude_artifact: only if ExecutionAgent invokes Claude
fallback_if_claude_unavailable: record `claude-unavailable: <reason>` in the execution report and proceed only if Codex can complete the bounded edit with source evidence.

## Required Skill

Use `$loop-engineering` before acting. Use skill-writing guidance because this edits a skill.

## Your Role

You are the existing `执行Agent / loop-skill打磨-2026-06-18` lane. Dispatcher is only physical delivery and bookkeeping.

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-revision.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review-claude.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`
- `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Compact Summary

Read the revision artifact directly. It approves a narrow skill hardening edit using `SKILL.md` plus exactly two reference files to resolve the prior file-length and Claude-policy formalism blockers.

## Task

Execute only the approved scope in the revision artifact. Then write an execution report under `docs/superpowers/plans/` and append one execution worklog row.

## Boundaries

Allowed:

- Edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.
- Create or edit `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`.
- Create or edit `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`.

Forbidden:

- Do not edit business code.
- Do not edit unrelated skills or other reference files.
- Do not create, pin, archive, fork, rename, or create threads.
- Do not create commits or PRs.
- Do not let Claude edit files directly.

## Required Output

- Skill edit completed within approved files.
- Execution report with exact verification output.
- Worklog row.

## Exit Criteria

- `SKILL.md` remains compact and near/under 500 lines.
- The two references exist and are linked from `SKILL.md`.
- Claude policy is tiered so `not_needed` remains lightweight.
- Dispatcher remains infrastructure only.
- No default pinning is introduced.
- Handoff can go to existing ReviewAgent for read-only review.
```
