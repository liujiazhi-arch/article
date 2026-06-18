# Claude Plan: Loop Skill Agent Lanes Update

## Source

- Brief: `docs/superpowers/plans/2026-06-18-loop-skill-brief.md`
- Protocol draft: `docs/superpowers/plans/2026-06-18-loop-engineering-agent-lanes-protocol.md`
- Skill under edit: `/Users/apple/.codex/skills/loop-engineering/SKILL.md` (currently ~300 lines, single-thread 7-phase flow)
- Protocol "Suggested Next Step" names the 8 stable parts to merge after one trial: lane naming, project manager + registry, message format, ledger rules, manager responsibilities, dynamic lane selection, cross-model review boundaries, Codex thread tool policy.

## Goal

Fold the *stable* Agent Lanes concepts into `SKILL.md` as an **optional scale-up layer** on top of the existing single-thread loop, so the skill can coordinate multi-thread, manager-worker engineering without losing its current focus. The added material must stay compact: the 680-line protocol doc remains the authoritative detailed spec; the skill inlines only the minimum needed to run lanes correctly and to know when *not* to.

## Scope

In scope:
- Edit only `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.
- Add one new compact section for Agent Lanes plus small touch-ups to `description`, `Purpose`, and `Common Mistakes`.
- Keep the existing 7-phase single-thread workflow intact and as the default path.

Out of scope:
- Editing the protocol doc, the brief, or `docs/superpowers/agent-registry.md`.
- Running the loop, creating threads, or sending messages (that is the execution lane's job, separate from the skill edit).
- Project business code, commits, PRs, dirty-worktree cleanup.

## Proposed Skill Changes

1. **Frontmatter `description`** — extend the one-liner so the skill also triggers for multi-thread coordination. Add a clause like "…or when work must be split across named Codex agent threads (manager/plan/exec/review/arbitration lanes) with durable handoff artifacts." Keep it a single line.

2. **`Purpose`** — add 2–3 lines: the loop runs **single-thread by default**; it can **scale up to named agent lanes across Codex threads** when coordination, traceability, or parallel read work justifies it. State the governing principle up front: *artifacts are the source of truth, not chat history; use the smallest lane set that preserves quality.*

3. **New section `## Agent Lanes (Optional Multi-Thread Scale-Up)`** — placed after `Claude Bridge`, before `Phase 1`. Compact subsections:
   - **When to use** — a 5-row dynamic-selection table condensed from the protocol (tiny change → current thread only; small fix → manager + 执行; normal/risky → full lanes; unclear → 计划 first). One sentence: default to single thread; add lanes only when needed.
   - **Lane roles** — one compact table: `manager/经理`, `planning/计划`, `execution/执行`, `review/审查`, `arbitration/仲裁`, one-line purpose each. Note Chinese names are the default.
   - **Manager role (经理Agent)** — 4–5 bullets: project-level (survives across loops), owns lane creation, thread naming, status tracking, decision/ledger recording, stop-rule enforcement, registry upkeep. Explicit guardrail: the manager is a *protocol role*, not a "boss model" that overrides evidence.
   - **Durable coordination artifacts** — list four files with a one-line purpose each: `agent-registry.md` (project-level index, recovers old threads), `agent-lanes.md` (current loop map), `thread-ledger.md` (every cross-lane message), `decision-log.md` (settled decisions). Point to the protocol doc for full templates rather than inlining them. Use the project's `docs/superpowers/` convention as the example, mirroring how the skill already shows `ai-handoffs/` vs project paths — do not hardcode it as the only location (the skill is global/portable).
   - **Standard agent message** — a *minimal* skeleton (the `<!-- LOOP:AGENT_MESSAGE v1 -->` header plus the field list: loop_id, message_id, from/to lane, source artifacts, task, boundaries, write scope, required output, exit criteria) with the rule: full content lives in artifacts; messages carry paths + compact summary + boundaries. Plus two rules: readable ids (`MSG-001-planning-to-execution`), and **every `send_message_to_thread` gets a ledger row**.
   - **Codex thread tool policy** — compact bullet map: `create_thread` (only when a phase needs a separate lane; first prompt is a standard agent message), `set_thread_title` (human-readable `task / lane`), `set_thread_pinned` (optional, active loops), `send_message_to_thread` (never an unstructured "continue"), `read_thread` (manager inspects state), `fork_thread` (exploration branch), `handoff_thread` (move between local/worktree), **do not auto-archive**, `automation_update` only for scheduled follow-up — not as the message bus.
   - **Lane review boundary** — 2 lines reaffirming the existing cross-model rule inside lane mode: 审查Agent keeps Claude CLI review and Codex subagent review independent; 仲裁Agent resolves disagreement with evidence, not model authority.
   - **Execution isolation** — one line: lanes that change code prefer a dedicated branch or Codex worktree, recorded in registry/lanes; review targets that same branch.

4. **`Common Mistakes`** — append 3–4 lane-specific entries: relying on chat memory instead of artifacts; sending unstructured "continue" messages; skipping ledger rows; auto-archiving threads; creating all five lanes for small work.

Target: the new section stays roughly 60–90 lines so the skill lands well under ~400 lines total.

## What To Keep Out Of The Skill

- The full protocol detail: complete registry/lanes/ledger/decision-log markdown templates, the full standard-message body, message-collision id rules, the automatic-communication 10-step cycle, concurrency rules, escalation/blocker template. Reference the protocol doc instead.
- The protocol's **Open Questions** (6 unresolved items) — do not encode any as firm rules: auto-creating the manager, worktree-vs-branch default, every-agent-can-message, emergency-fix scope strictness, cleanup/archive phase, per-lane model settings stored in registry.
- **Trial Policy** as permanent rules — keep the "do not auto-archive" guidance (it is a safe default) but do not bake trial-only language as law.
- Hardcoding `docs/superpowers/` as the only artifact home — keep the skill portable across projects.
- Restating the entire existing 7-phase flow inside the lanes section — lanes map onto the phases that already exist; cross-reference, don't duplicate.

## Tests / Verification

The skill edit is a documentation change; verification is structural and content-completeness, not code execution.

- Re-read `SKILL.md` end to end; confirm the original 7 phases, stop rules, evidence standards, and Claude Bridge are unchanged.
- Confirm frontmatter is still valid (single `name`, single-line `description`).
- Confirm each of the 8 stable parts appears at least minimally in the new section.
- Size/bloat check: confirm total length stays within target (≈ under 400 lines) and the new section is compact.
- Markdown sanity: balanced code fences, consistent header levels, tables render.
- Confirm no project-specific absolute path replaced the generic default convention.
- Separately note (not part of the file check) the brief's *trial* runtime proof — `create_thread`, `set_thread_title`, `send_message_to_thread`, `read_thread` succeeding — which belongs to the execution lane's evidence, not to skill-file verification.

## Risks

- **Bloat / portability** — the protocol is large and tied to one project's `docs/superpowers/` layout; copying too much, or hardcoding that path, would both bloat the skill and break its reuse in other projects. Mitigate by reference + generic phrasing.
- **Premature lock-in** — the protocol explicitly flags 6 open questions and a trial period; encoding unresolved decisions as rules would harden choices that have only one trial behind them.
- **Out-of-repo target** — `SKILL.md` lives at a global path, so the project git state will not capture the edit; the change needs separate evidence and is not recoverable via project history.
- **Convention drift** — the skill already carries two artifact-path conventions (`ai-handoffs/` and `superpowers/plans/`); adding four lane artifacts could confuse owners unless presented as the same project-example pattern.
- **Two source plans diverging** — this Claude plan is one of a dual pair; the merge step must reconcile any conflict with the Codex plan before the skill is touched.

## Not Doing

- Not creating threads, sending messages, or executing the loop in this planning lane.
- Not editing the protocol doc, brief, or agent registry.
- Not resolving the 6 open questions or finalizing trial-only policy as permanent rules.
- Not adding automation/scheduling behavior beyond a one-line policy note.
- Not rewriting or reordering the existing phases, stop rules, or evidence standards.
- Not committing, branching, or opening a PR.
