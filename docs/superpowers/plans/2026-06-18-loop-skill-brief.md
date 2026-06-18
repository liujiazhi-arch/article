# Loop Skill 打磨试跑 Brief

## Source

- User request in current thread on 2026-06-18.
- Existing skill: `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.
- Design draft: `docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md`.
- Current project registry: `docs/superpowers/agent-registry.md`.

## Goal

Use the proposed Agent Lanes workflow to improve the `loop-engineering` skill itself and prove that Codex can create a new thread and communicate with it through a traceable message.

## User Constraints

- Default agent names should be Chinese.
- `经理Agent` should be project-level and able to recover previous task threads.
- Execution lanes that change code should preferably use a branch or worktree.
- Review must preserve Claude CLI review and Codex subagent review as distinct inputs.
- Cross-thread communication should use readable ids and durable artifacts.
- Full content should live in files; messages should carry paths, summaries, boundaries, and exit criteria.
- Do not auto-archive threads during the trial period.

## In Scope

- Create/update protocol artifacts under `docs/superpowers/`.
- Create a planning agent thread and send it a standard `LOOP:AGENT_MESSAGE v1` prompt.
- Ask Claude CLI for an independent plan if available.
- Produce a Codex plan, compare plans, and write a merged plan for updating `loop-engineering`.
- If the merged plan is safe, update `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.
- Write evidence of the thread communication and verification.

## Out Of Scope

- Modifying project business code.
- Creating commits or PRs.
- Archiving old threads.
- Rewriting unrelated skills.
- Resolving unrelated dirty worktree changes.

## Expected Verification

- `codex_app.create_thread` returns a new thread id or pending worktree id.
- `codex_app.set_thread_title` succeeds for the new planning thread.
- `codex_app.send_message_to_thread` succeeds with the standard message.
- `codex_app.read_thread` can inspect the planning thread after dispatch.
- The updated skill file, if edited, contains the agreed Agent Lanes rules.
- Artifacts record command/tool evidence and current git state.

## Known Risk

- Claude CLI may be unavailable or return malformed output.
- New background thread may not finish within this turn.
- Cross-thread communication tools can deliver prompts, but durable memory still depends on files.
- Updating a global skill path is outside the repository, so the project git state will not capture that change.
