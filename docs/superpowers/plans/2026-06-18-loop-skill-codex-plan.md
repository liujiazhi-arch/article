# Codex Plan: Loop Skill Agent Lanes Update

## Source

- `docs/superpowers/plans/2026-06-18-loop-skill-brief.md`
- `docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-agent-lanes.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-decision-log.md`
- `docs/superpowers/agent-registry.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`

## Goal

Update `/Users/apple/.codex/skills/loop-engineering/SKILL.md` so it teaches the stable Agent Lanes workflow while staying concise and reusable. The skill should make future agents create traceable lanes, preserve artifact-first coordination, and keep Claude CLI review separate from Codex subagent review.

## Scope

The skill edit should cover only reusable loop rules:

- project-level `经理Agent` as the durable coordinator
- Chinese default lane names
- project-level agent registry
- loop lane map, thread ledger, and decision log
- readable `loop_id` and `message_id`
- standard cross-thread message requirements
- dedicated branch or worktree expectation for code-writing execution lanes
- independence boundaries for Claude CLI and Codex subagent review
- dynamic lane selection so small work does not always create every lane

## Proposed Skill Changes

1. Add a compact `Agent Lanes` section after the purpose or five-step workflow. It should state that the classic five-step loop can run inside lanes and that the `经理Agent` owns coordination, traceability, and escalation.

2. Add a short lane table with default Chinese names:

   - `manager` / `经理Agent`: project-level coordinator and recovery point
   - `planning` / `计划Agent`: brief, dual plans, merged plan
   - `execution` / `执行Agent`: implements only the merged plan
   - `review` / `审查Agent`: read-only review, Claude CLI review, Codex subagent review
   - `arbitration` / `仲裁Agent`: dispositions, repairs, final report

3. Replace or extend the artifact protocol with three durable coordination files:

   - `docs/superpowers/agent-registry.md` for project-level recovery
   - `*-agent-lanes.md` for current loop lane ownership and thread ids
   - `*-thread-ledger.md` for every `send_message_to_thread` handoff
   - `*-decision-log.md` for resolved conflicts and reopen rules

4. Add message-id rules without embedding the full protocol template. The skill should require readable ids such as `MSG-001-manager-to-planning`, source and target lanes, source artifacts, boundaries, write scope, required output, and exit criteria. It can point agents to the project protocol artifact for the full template when present.

5. Add execution isolation rules:

   - If a lane writes code, prefer a dedicated Codex worktree or named branch.
   - Record branch or worktree in the registry and lane map.
   - Review must target the same branch or worktree execution used.
   - Only one write lane may edit the same file set unless worktrees isolate the work and the manager owns merge arbitration.

6. Add cross-model review boundaries to the review phase:

   - Claude CLI remains an external read-only planner or reviewer with its own artifact.
   - Codex subagent review remains a separate independent artifact.
   - Neither review may read the other before both are complete.
   - Arbitration decides by evidence, not by model authority.

7. Add dynamic lane selection guidance:

   - tiny docs/config work can stay in the manager/current thread
   - small local fixes can use manager plus execution
   - risky features, architecture changes, and frontend/backend linkage use full lanes
   - unclear requirements start with manager plus planning only

8. Keep the existing stop rules, evidence standards, arbitration labels, Claude bridge failure handling, and final report requirements. They are already concise and still valid.

## What To Keep Out Of The Skill

- Full copied templates for registry, lane map, ledger, blocker messages, and standard handoff messages. The skill should require the fields and refer to supporting project docs when available.
- Trial-specific policy such as not auto-archiving threads forever. Keep this in project docs unless it proves universal.
- Current thread ids, current loop ids, exact titles from this trial, and `article` project details.
- The full OpenAI tool inventory and official-doc notes from the protocol artifact.
- Open questions from the protocol draft. They should remain in project docs until resolved by real use.
- Long examples of every lane message. One compact example id is enough.
- Broad skill-writing TDD procedure. This edit can mention verification scenarios, but the skill should not import the whole skill-authoring methodology.

## Tests / Verification

- Run `wc -w /Users/apple/.codex/skills/loop-engineering/SKILL.md` before and after the edit and keep growth modest.
- Run `sed -n '1,260p' /Users/apple/.codex/skills/loop-engineering/SKILL.md` and inspect that the new rules are findable without scrolling through long templates.
- Search for required terms:
  - `rg "经理Agent|计划Agent|执行Agent|审查Agent|仲裁Agent" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
  - `rg "agent-registry|thread-ledger|decision-log|message_id|worktree|Claude CLI|Codex subagent" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- Verify no trial thread ids or project-specific loop ids were copied into the skill:
  - `rg "019ed|LOOP-20260618-001-loop-skill|article" /Users/apple/.codex/skills/loop-engineering/SKILL.md`
- If time allows, run one pressure scenario in a fresh agent: ask it to start a medium code-writing loop and check that it creates or records manager, registry, readable message ids, execution branch/worktree policy, and separate Claude/Codex review artifacts.

## Risks

- The skill may bloat if the entire protocol artifact is copied in. Keep the skill to invariants and small examples.
- If dynamic lane selection is too loose, future agents may skip review on risky work. Use explicit task-type guidance.
- If the project-level `经理Agent` is described as a model authority, agents may override evidence. Define it as a coordination role only.
- Worktree requirements may be too heavy for docs-only or global-skill edits. Phrase as required for code-writing execution lanes, not every loop.
- Cross-model review can collapse if the `审查Agent` feeds one review into the other. State independence directly.

## Not Doing

- Do not edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md` in this planning lane.
- Do not modify business code.
- Do not create commits, PRs, broad tests, or new automation.
- Do not move all project protocol content into the skill.
- Do not remove the existing five-step workflow; integrate Agent Lanes around it.
