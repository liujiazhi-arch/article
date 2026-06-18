# Protocol Hardening Follow-up Execution Report

loop_id: LOOP-20260618-001-loop-skill
lane: execution
thread_id: 019ed72a-2c15-7fa2-86df-d755c7728abd
created_at: 2026-06-19T01:36:40+0800
claude_policy: required
claude_mode: claude_execution_consult

## Source

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-revision.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-review.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-artifact-first-handoff-addendum.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`
- `/Users/apple/.codex/plugins/cache/github-superpowers/github-superpowers/5.1.0/skills/writing-skills/SKILL.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Scope

Implemented the follow-up protocol hardening inside the approved files only:

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`

No business code, other references, thread state, pin/archive/fork state, commit, or PR state was modified.

## Claude Consult

Required consult artifact:

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup-claude-consult.md`

Claude CLI probe:

```text
command -v claude -> /Users/apple/.local/bin/claude
claude --version -> 2.1.178 (Claude Code)
```

First attempt failed because the prompt was parsed into `--disallowedTools` arguments. I retried through stdin. Retry result:

```text
__CLAUDE_EXIT_STATUS=0
__CLAUDE_ELAPSED_SECONDS=83
```

Codex accepted Claude's two main constraints:

- Permit a short orienting pointer in artifact-first handoffs, but forbid rewriting, splitting, compressing, or paraphrasing the artifact body.
- Make only `claude_policy` unconditional; keep `claude_mode`, `required_claude_artifact`, and `fallback_if_claude_unavailable` conditional by policy tier so `not_needed` remains lightweight.

## Skill Edit

- Added `cross-model debate` to the frontmatter trigger without summarizing workflow.
- Hardened artifact-first handoff wording in Artifact Protocol and Standard Agent Messages.
- Made `claude_policy` mandatory in standard loop messages.
- Added lane artifact `claude_policy` guidance while preserving one-line `not_needed`.
- Added a required-Claude close-out gate to `references/claude-policy.md`.
- Added Common Mistakes bullets for missing policy, required-Claude close-out without artifact/unavailable marker, Dispatcher running Claude for a lane, silent conditional skip, and handoff body rewriting.

## Verification

```bash
wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```text
     472 /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```bash
rg -n "cross-model debate|complete .*artifact|artifact path|claude_policy|required_claude_artifact|fallback_if_claude_unavailable|Common Mistakes" /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```text
3:description: Use when substantial AI coding work needs multi-agent orchestration, cross-model Claude/Codex planning or review, cross-model debate, named Codex agent threads, dispatcher-mediated handoffs, thread ledgers, worklogs, batons, repair loops, or evidence-based arbitration.
35:5. Choose `claude_policy` for handoffs and lane artifacts; see `references/claude-policy.md`.
85:- Keep plan, execution report, review, arbitration, and final report separate. Handoffs are artifact-first: when a complete plan or formal artifact exists, send its path, a read requirement, boundaries, and exit criteria; do not rewrite, split, compress, or paraphrase the artifact body into the message.
86:- Every lane artifact states its `claude_policy`; tier fields follow `references/claude-policy.md`. `not_needed` stays one line.
118:For tiered `claude_policy` rules, lane-owned Claude duties, five-minute waits for deep required Claude plan/review calls, and path-access fallback details, read `references/claude-policy.md`.
212:claude_policy (required in every loop message)
213:claude_mode / claude_reason / required_claude_artifact / fallback_if_claude_unavailable per the selected policy tier
222:Use readable ids such as `MSG-001-planning-to-execution`. Full content belongs in artifacts. When a complete plan or formal artifact already exists, the handoff must carry the artifact path, read requirement, boundaries, and exit criteria, plus at most a short orienting pointer. Do not rewrite, split, compress, or paraphrase the artifact body into the message. Every `send_message_to_thread` call needs a ledger row. Never send an unstructured "continue" for loop work.
404:- artifact paths
446:## Common Mistakes
468:- missing `claude_policy` in a loop message or lane artifact.
472:- Handoff rewrites or summarizes a complete artifact body instead of sending the artifact path and read requirement.
```

```bash
rg -n 'missing `claude_policy`|Dispatcher running Claude|conditional Claude|rewrites or summarizes|required Claude' /Users/apple/.codex/skills/loop-engineering/SKILL.md
```

```text
118:For tiered `claude_policy` rules, lane-owned Claude duties, five-minute waits for deep required Claude plan/review calls, and path-access fallback details, read `references/claude-policy.md`.
468:- missing `claude_policy` in a loop message or lane artifact.
469:- Closing out required Claude without the required artifact or a real `claude-unavailable` marker.
470:- Dispatcher running Claude for a lane instead of the lane owning its own Claude use.
471:- Silently skipping conditional Claude without `Claude skipped: <reason>`.
472:- Handoff rewrites or summarizes a complete artifact body instead of sending the artifact path and read requirement.
```

```bash
rg -n "cannot close out|claude-unavailable|block|degrade|required Claude artifact|Claude skipped" /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
```

```text
10:| `conditional` | Claude may help, but current evidence may make it unnecessary: implementation-risk consultation, unclear-plan analysis, review uncertainty, or workflow design pressure checks. | Include `claude_policy`, `claude_mode`, `claude_reason`; if skipped, write `Claude skipped: <reason>`. Add artifact/fallback only when Claude is invoked or actively considered. |
15:A lane with `claude_policy: required` cannot close out its final lane conclusion, execution report, review, or final report without either the `required_claude_artifact` or a recorded `claude-unavailable: <reason>` with elapsed wait and an explicit block-or-degrade decision. `Dispatcher` and `经理Agent` may flag a missing required Claude artifact or gate, but cannot satisfy it for the lane.
24:- `Dispatcher` and `经理Agent` must not run Claude on behalf of lanes. They may flag missing required Claude artifacts or unavailable markers.
35:- If Claude still cannot access the path, record `partial: <path> unreadable` or `claude-unavailable: <reason>`.
```

Manual criteria:

- `SKILL.md` remains compact at 472 lines.
- `claude_policy: not_needed` remains one-line in `references/claude-policy.md`.
- Artifact-first messaging is a hard rule when a complete artifact exists.
- Standard messages keep full plan content in artifacts, not prompt bodies.
- Required Claude close-out cannot pass silently.

## Worklog Entry

Appended row 48 to `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`.

## Review Handoff Draft

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

# Loop Agent Message

message_type: review_handoff
loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-043-execution-to-review-protocol-hardening-followup
from_lane: execution
to_lane: review
from_thread: 019ed72a-2c15-7fa2-86df-d755c7728abd
to_thread: 019ed6fa-96d1-7473-89a7-676ef3c3a836
delivered_by_lane: dispatcher
delivered_by_thread: current dispatcher thread
delivery_reason: ExecutionAgent completed the protocol-hardening follow-up and cannot send directly from this lane.
claude_policy: conditional
claude_mode: claude_review | n/a
claude_reason: ReviewAgent may use Claude if it finds ambiguity; execution already produced required Claude consult.
required_claude_artifact: only if ReviewAgent invokes Claude
fallback_if_claude_unavailable: record `claude-unavailable: <reason>`, elapsed wait, and whether review is blocked or degraded.

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup-execution-report.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup-claude-consult.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`

## Task

Perform read-only review of the protocol-hardening follow-up. Verify the edit stays in scope, `SKILL.md` remains compact, artifact-first handoff is a hard rule without banning short pointers, `claude_policy` is mandatory while tier fields remain conditional, required-Claude close-out cannot pass silently, Dispatcher/Manager do not gain authority, and no business code or thread state was modified.

## Boundaries

Do not edit files. Do not create, pin, archive, fork, rename, commit, or open PRs. Do not treat Dispatcher as planner, reviewer, arbitrator, manager, Claude bridge, or workflow authority.

## Required Output

Write a compact review artifact under `docs/superpowers/plans/` and append one review worklog row.
```

## Residual Risk

- The entrypoint skill is still near the 500-line threshold, though this edit leaves it at 472 lines.
- Future additions should preferentially go into references unless a reviewed plan explicitly approves more inline text.
