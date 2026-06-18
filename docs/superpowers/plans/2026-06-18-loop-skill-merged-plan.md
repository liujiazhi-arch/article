# Merged Plan: Loop Skill Agent Lanes Update

## Source Plans

- Claude: `docs/superpowers/plans/2026-06-18-loop-skill-claude-plan.md`
- Codex planning lane: `docs/superpowers/plans/2026-06-18-loop-skill-codex-plan.md`
- Brief: `docs/superpowers/plans/2026-06-18-loop-skill-brief.md`
- Protocol draft: `docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md`

## Accepted From Claude

- Treat Agent Lanes as an optional multi-thread scale-up layer, not a replacement for the existing 7-phase loop.
- Keep the existing 7 phases, Claude Bridge, stop rules, evidence standards, and final report rules intact.
- Add one compact section rather than copying the long protocol document into the skill.
- Keep the skill portable; use `docs/superpowers/` as a project convention example, not a global requirement.
- Include Codex thread tool policy directly in concise bullets.
- Add lane-specific common mistakes.

## Accepted From Codex

- Include the stable invariants: project-level `经理Agent`, Chinese lane names, project registry, lane map, thread ledger, decision log, readable message ids, write-scope boundaries, execution branch/worktree policy, and cross-model review independence.
- Make `agent-registry.md`, `*-agent-lanes.md`, `*-thread-ledger.md`, and `*-decision-log.md` visible in the skill.
- Require every `send_message_to_thread` handoff to have a ledger row.
- State that review must target the same branch or worktree used by execution.
- Keep full templates, trial policy, exact thread ids, and open questions out of the skill.

## Rejected

- Copying the full 600+ line protocol document into `SKILL.md`: rejected as too bulky and less portable.
- Making all five lanes mandatory for every loop: rejected because both plans preserve dynamic lane selection.
- Treating `经理Agent` as a model authority: rejected; it is only a coordination and traceability role.
- Auto-archiving phase threads by default: rejected for this trial and not made a permanent rule.

## Third Path Decisions

- `docs/superpowers/agent-registry.md` is named as the current project convention, while the skill also allows equivalent project-specific locations.
- Execution isolation is phrased as "prefer a dedicated branch or Codex worktree for code-writing lanes" rather than a hard rule for docs-only or global skill edits.
- The standard message template in the skill will list required fields and include only a tiny id example; the full template remains in the protocol artifact.
- No pressure-test subagent will be created in this first trial because we already created a real planning thread and the user asked to see that cross-thread communication works. The final report will record this as a residual testing gap.

## Final Tasks

- T1: Edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md` only.
- T2: Extend the frontmatter description to include named Codex agent threads without over-describing workflow.
- T3: Add a short Purpose paragraph: single-thread by default, scale to lanes when coordination/tracing justifies it, artifacts are source of truth.
- T4: Add `## Agent Lanes (Optional Multi-Thread Scale-Up)` after `Claude Bridge`.
- T5: Include compact subsections for lane selection, lane roles, project-level manager, durable coordination artifacts, standard message requirements, thread tool policy, execution isolation, and cross-model review boundary.
- T6: Add lane-specific `Common Mistakes`.
- T7: Verify structure, required terms, absence of trial ids, and line count.

## Verification

- `wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `sed -n '1,360p' /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `rg "经理Agent|计划Agent|执行Agent|审查Agent|仲裁Agent" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `rg "agent-registry|thread-ledger|decision-log|message_id|worktree|Claude CLI|Codex subagent" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `rg "019ed|LOOP-20260618-001-loop-skill|article" /Users/apple/.codex/skills/loop-engineering/SKILL.md` should return no matches.
- Check `git status --short` and record that the global skill edit is outside project git.

## Optional / Skip Rules

- SKIP pressure scenario if this first trial already demonstrates real `create_thread`, `set_thread_title`, `send_message_to_thread`, and `read_thread`; record it as a gap rather than pretending full skill TDD is complete.
- SKIP worktree execution because the actual edit target is a global skill file outside the project repo and no business code is modified.

## Completion Criteria

- The skill includes the stable Agent Lanes rules in concise form.
- The skill does not include trial-specific ids, exact project paths as global requirements, or unresolved open questions as fixed rules.
- Verification commands run and outputs are recorded in the execution report.
