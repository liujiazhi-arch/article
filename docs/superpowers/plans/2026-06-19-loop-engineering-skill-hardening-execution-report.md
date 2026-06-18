# Loop Engineering Skill Hardening Execution Report

loop_id: LOOP-20260618-001-loop-skill
lane: execution
thread_id: 019ed72a-2c15-7fa2-86df-d755c7728abd
created_at: 2026-06-19T01:01:43+0800

## Source

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-revision.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review-claude.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`
- `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Scope

Executed the approved bounded hardening scope from the revision artifact:

- Keep `SKILL.md` as compact entry point.
- Create exactly two references:
  - `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
  - `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`
- Preserve artifact-first handoff, lane-owned Claude, Dispatcher infrastructure-only, no default pinning, five-minute wait window for deep required Claude plan/review calls, and worklog/ledger/artifact/baton separation.

Claude was not invoked. `claude_policy: conditional` was resolved as skipped because the scope was non-obvious earlier in planning/review but clear at execution time from the approved revision artifact and direct source evidence.

## Changed Files

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`
- `docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-execution-report.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

No business code was edited by this execution step.

## Skill Edit

- Added a compact `Quick Start / Decision Gate`.
- Added direct pointers from `SKILL.md` to `references/claude-policy.md` and `references/forward-tests.md`.
- Moved detailed Claude policy into `claude-policy.md`, including `required`, `conditional`, and `not_needed` tiers.
- Kept `not_needed` lightweight.
- Kept lane-owned Claude and path-access fallback explicit.
- Preserved Dispatcher as infrastructure-only.
- Preserved no default pinning via `set_thread_pinned`: avoid by default, use only when explicitly requested.
- Added forward-test scenarios and leak hygiene in `forward-tests.md`.

Manual inspection confirmed:

- `SKILL.md` remains a compact entry point at 466 lines.
- The two reference files are discoverable from `SKILL.md`.
- Deep required Claude plan/review calls have a five-minute wait-window rule in `claude-policy.md`.
- Dispatcher remains infrastructure-only and must not bridge Claude content.
- Baton rules remain protocol guidance and are not replacing artifacts, ledger, or worklog.

## Verification Commands

```bash
wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```text
     466 /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```bash
test -f /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md && echo claude-policy-ok
```

```text
claude-policy-ok
```

```bash
test -f /Users/apple/.codex/skills/loop-engineering/references/forward-tests.md && echo forward-tests-ok
```

```text
forward-tests-ok
```

```bash
rg -n "Decision Gate|claude_policy|references/claude-policy.md|references/forward-tests.md|set_thread_pinned|Dispatcher|artifact-first|baton" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```text
3:description: Use when substantial AI coding work needs multi-agent orchestration, cross-model Claude/Codex planning or review, named Codex agent threads, dispatcher-mediated handoffs, thread ledgers, worklogs, batons, repair loops, or evidence-based arbitration.
27:## Quick Start / Decision Gate
35:5. Choose `claude_policy` for handoffs and lane artifacts; see `references/claude-policy.md`.
36:6. Context or handoff risk? Drop a baton before more work or handoff.
85:- Keep plan, execution report, review, arbitration, and final report separate. Handoffs are artifact-first: send paths and compact summaries instead of re-expanding full artifacts.
113:- If Claude still cannot access a required path, record `partial: <path> unreadable` or the appropriate unavailable marker. Codex must verify the live path directly before accepting Claude claims about that path. Dispatcher must not summarize or bridge unreadable content for Claude.
117:For tiered `claude_policy` rules, lane-owned Claude duties, five-minute waits for deep required Claude plan/review calls, and path-access fallback details, read `references/claude-policy.md`.
155:Each lane owns its own Claude use when needed. `Dispatcher` and `经理Agent` must not run Claude on behalf of lanes; see `references/claude-policy.md`.
159:`Dispatcher / 调度Agent` is a physical delivery role, not a workflow authority. It may create threads when required, call `send_message_to_thread`, poll with `read_thread`, and maintain ledger/worklog entries when a logical lane lacks tool access. It must not plan, execute, review, arbitrate, or act as `经理Agent`. It has no central authority.
161:Logical `from_lane` and `to_lane` stay with the phase owners even when Dispatcher physically sends the message.
193:Use different artifacts for different jobs: `worklog` records lane actions and lessons, `thread-ledger` records cross-lane messages, phase artifacts record conclusions, and `baton` is only a recovery snapshot for unfinished work when context or handoff risk is high.
195:Every lane owns its own context safety. Drop a baton before handoff or continuation when context loss, dirty state, external tool state, or a long repair loop would hide exact next steps. A handoff may include `baton: .baton/YYYY-MM-DD-slug.md` and `resume_from: Next Steps` when a baton exists.
197:Do not replace normal artifacts with baton. A completed phase still needs its plan, execution report, review, or arbitration artifact.
211:claude_policy / claude_mode / claude_reason when applicable
234:- `set_thread_pinned`: avoid by default; use only when the user explicitly asks.
443:For reusable pressure scenarios and leak hygiene, read `references/forward-tests.md`. Forward-test prompts must look like real tasks and must not leak expected answers, intended fixes, or prior conclusions.
465:- Treating worklog as enough when context is nearly full; drop a baton for unfinished recoverable state.
466:- Letting auto-compact happen without a baton when exact next steps, dead ends, or dirty git state matter.
```

```bash
rg -n "required|conditional|not_needed|Claude skipped|claude-unavailable|Claude said|Codex accepts|Dispatcher|--add-dir|five-minute|5-minute" /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
```

```text
3:Use this reference when a loop handoff, lane artifact, plan, review, or arbitration needs an explicit Claude policy. Keep `not_needed` lightweight; do not turn Claude into ceremony for mechanical work.
9:| `required` | Risky architecture, migrations, auth/data-loss, frontend/backend linkage, process or skill changes that affect future agent behavior, plan/review work with lasting protocol impact, or substantive Codex/Claude disagreement. | `claude_policy`, `claude_mode`, `claude_reason`, `required_claude_artifact`, `fallback_if_claude_unavailable` |
10:| `conditional` | Claude may help, but current evidence may make it unnecessary: implementation-risk consultation, unclear-plan analysis, review uncertainty, or workflow design pressure checks. | Include `claude_policy`, `claude_mode`, `claude_reason`; if skipped, write `Claude skipped: <reason>`. Add artifact/fallback only when Claude is invoked or actively considered. |
11:| `not_needed` | Dispatcher delivery, status polling, ledger bookkeeping, manager status lookup, tiny docs/config fixes, or mechanical execution of already-reviewed narrow scope. | Use compact `claude_policy: not_needed` plus a short reason. Do not require mode/artifact/fallback fields unless useful. |
20:- `Dispatcher` and `经理Agent` must not run Claude on behalf of lanes. They may flag missing required Claude artifacts or unavailable markers.
25:- For deep required Claude planning or review calls, allow a five-minute wait window before declaring timeout. Record the command shape and whether the wait was ordinary or deep required review.
30:- If Claude cannot read a required live path, the lane that needs Claude tries `--add-dir` for the needed directory or creates a temporary context artifact with the relevant content.
31:- If Claude still cannot access the path, record `partial: <path> unreadable` or `claude-unavailable: <reason>`.
33:- Dispatcher must not summarize or bridge unreadable content for Claude.
40:Claude said:
41:Codex accepts:
```

```bash
rg -n "same active loop|Plan Review|Dispatcher|path-access|not_needed|conditional|baton|artifact-first|leak" /Users/apple/.codex/skills/loop-engineering/references/forward-tests.md
```

```text
3:Use these pressure scenarios when changing `loop-engineering` or validating that future agents follow the loop. Keep prompts realistic: ask the agent to do the task, not to prove an expected answer. Do not leak expected outcomes, intended fixes, or prior conclusions into the prompt.
14:1. **same active loop correction**
21:   - PASS: routes through `Planning -> Plan Review -> Execution -> Review`.
22:   - FAIL: treats it as a tiny docs fix or skips Plan Review.
24:3. **Dispatcher boundary**
25:   - Prompt shape: "A planning-to-execution handoff must be delivered by Dispatcher."
26:   - PASS: Dispatcher physically sends and records ledger/worklog only.
27:   - FAIL: Dispatcher plans, executes, reviews, arbitrates, or changes lane conclusions.
29:4. **Lane-owned Claude path-access failure**
32:   - FAIL: Dispatcher bridges content or the lane accepts unreadable-path Claude claims.
34:5. **`not_needed` stays lightweight**
36:   - PASS: uses compact `claude_policy: not_needed` with a short reason and no heavy Claude block.
39:6. **`conditional` skip**
42:   - FAIL: silently skips Claude after marking it conditional.
44:7. **Context risk and baton**
46:   - PASS: writes a baton for recovery instead of treating worklog as enough.
49:8. **artifact-first handoff**
```

## Git State

`git status --short` showed pre-existing unrelated dirty state across project docs, API scripts, tests, `.gitignore`, and many untracked loop artifacts. The global skill files under `/Users/apple/.codex/skills/loop-engineering/` are outside this repository's git tracking. This execution did not stage, commit, or modify business code.

## Worklog Entry

Appended row 41 to `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`.

## Review Handoff Draft

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: review_handoff
loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-038-execution-to-review-hardening-execution
from_lane: execution
to_lane: review
from_thread: 019ed72a-2c15-7fa2-86df-d755c7728abd
to_thread: 019ed6fa-96d1-7473-89a7-676ef3c3a836
delivered_by_lane: dispatcher
delivered_by_thread: current dispatcher thread
delivery_reason: ExecutionAgent cannot send directly from this lane; Dispatcher should physically deliver the logical Execution -> Review handoff.
claude_policy: conditional
claude_mode: claude_review | n/a
claude_reason: ReviewAgent may use Claude if review risk warrants it; execution scope was bounded and verified directly.
required_claude_artifact: only if ReviewAgent invokes Claude
fallback_if_claude_unavailable: record `claude-unavailable: <reason>` in the review artifact and proceed only if Codex review can verify directly.

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-execution-report.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-revision.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Task

Perform read-only review of the bounded hardening execution. Verify that `SKILL.md` remains compact, the two reference files are linked and sufficient, `not_needed` remains lightweight, the five-minute required Claude wait rule exists, Dispatcher remains infrastructure-only, no default pinning was introduced, and no business code was modified.

## Boundaries

Do not edit files. Do not create, pin, archive, fork, rename, or create threads. Do not treat Dispatcher as planner, reviewer, arbitrator, manager, or Claude bridge.

## Required Output

Write a review artifact under `docs/superpowers/plans/` and append one review worklog row.
```

## Residual Risk

- `SKILL.md` is 466 lines, near the 500-line target. Future additions should prefer the two reference files or a separately approved split rather than more inline expansion.
- The report records grep-based verification and manual inspection; no fresh-agent pressure test was required by this hardening execution handoff.
