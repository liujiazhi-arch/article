# Loop Skill Protocol Hardening Follow-up

loop_id: LOOP-20260618-001-loop-skill
created_at: 2026-06-19T01:28:22+08:00
created_by_lane: dispatcher
source: user correction after hardening review

## Purpose

Tighten the remaining protocol gaps in `$loop-engineering` without starting a new loop or rewriting the skill broadly.

This is a user-authorized follow-up inside the existing skill打磨 loop. Dispatcher is only delivering this scope to `执行Agent`; execution and review remain lane-owned.

## Source Artifacts

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-revision.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-review.md`
- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-artifact-first-handoff-addendum.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`

## Required Edits

Edit only:

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`

Make the smallest changes that cover these gaps:

1. Add `cross-model debate` to the skill description trigger without summarizing workflow.
2. Harden artifact-first handoff: when a complete `plan.md` or formal artifact exists, the handoff prompt must be a structured envelope plus artifact path and read requirement. Do not rewrite, split, compress, or paraphrase the artifact body into the message.
3. Make `claude_policy` mandatory in standard loop messages and lane artifacts. Tier-specific fields such as `claude_mode`, `required_claude_artifact`, and `fallback_if_claude_unavailable` depend on the selected policy tier.
4. Add a required-Claude close-out gate in `references/claude-policy.md`: a lane with `claude_policy: required` cannot close out without the required Claude artifact, or a recorded `claude-unavailable: <reason>` plus explicit block/degrade decision.
5. Add Common Mistakes bullets for:
   - missing `claude_policy`
   - required Claude close-out without artifact or unavailable marker
   - Dispatcher running Claude for a lane
   - conditional Claude silently skipped
   - complete artifact exists but the handoff rewrites or summarizes its body

## Scope Boundaries

Allowed:

- Keep `SKILL.md` compact and near or under 500 lines.
- Reword nearby existing bullets instead of adding long new sections.
- Use `references/claude-policy.md` for detailed close-out policy.
- Write an execution report under `docs/superpowers/plans/`.
- Append one execution worklog row.

Forbidden:

- Do not edit business code.
- Do not create new threads, pin, archive, fork, rename, commit, or open PRs.
- Do not edit unrelated skills or references unless execution stops and asks for a revised scope.
- Do not make Dispatcher, Manager, or the current bootstrap thread a workflow authority.
- Do not paste the full hardening plan into cross-lane messages; use artifact paths.

## Claude Policy For Execution

claude_policy: required
claude_mode: claude_execution_consult
claude_reason: This edit changes future multi-agent protocol behavior.
required_claude_artifact: `docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup-claude-consult.md`
fallback_if_claude_unavailable: record `claude-unavailable: <reason>`, elapsed wait, and whether execution is blocked or degraded; do not silently close out.

Claude must be read-only. It may critique the edit scope or proposed wording, but it must not edit files directly.

## Required Verification

Record exact command output in the execution report:

```bash
wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "cross-model debate|complete .*artifact|artifact path|claude_policy|required_claude_artifact|fallback_if_claude_unavailable|Common Mistakes" /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "missing `claude_policy`|Dispatcher running Claude|conditional Claude|rewrites or summarizes|required Claude" /Users/apple/.codex/skills/loop-engineering/SKILL.md
rg -n "cannot close out|claude-unavailable|block|degrade|required Claude artifact|Claude skipped" /Users/apple/.codex/skills/loop-engineering/references/claude-policy.md
```

Manual criteria:

- `SKILL.md` remains compact and discoverable.
- `claude_policy: not_needed` remains lightweight.
- Artifact-first messaging is a hard rule, not just a preference.
- Standard message structure allows full plan content to live in artifacts instead of the prompt body.
- Required Claude close-out cannot pass silently.

## Required Output

- Execution report, suggested path: `docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup-execution-report.md`
- Worklog row.
- Artifact-first ReviewAgent handoff draft or direct handoff request for existing ReviewAgent `019ed6fa-96d1-7473-89a7-676ef3c3a836`.

## Exit Criteria

- Required edits are implemented or blocked with evidence.
- Required Claude consult artifact exists, or unavailable marker and block/degrade decision exists.
- Execution report contains verification output.
- No new loop, lane set, thread pin, archive, commit, PR, or business-code edit is created.
