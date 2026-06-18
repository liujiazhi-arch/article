# Loop Engineering Skill Hardening Plan Review

loop_id: LOOP-20260618-001-loop-skill
lane: review
thread_id: 019ed6fa-96d1-7473-89a7-676ef3c3a836
created_at: 2026-06-19T00:47:39+08:00
claude_policy: required
claude_mode: claude_plan_critique

## Source

- Hardening plan: `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- Live skill: `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- Writing-skills guidance: `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`
- Skill-creator guidance: `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`
- Claude critique: `docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan-review-claude.md`
- Thread ledger: `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- Worklog: `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- Commands run:
  - `nl -ba /Users/apple/.codex/skills/loop-engineering/SKILL.md | sed -n '1,520p'`
  - `nl -ba /Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md | sed -n '1,360p'`
  - `nl -ba /Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md | sed -n '360,760p'`
  - `nl -ba /Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md | sed -n '760,900p'`
  - `nl -ba /Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md | sed -n '1,560p'`
  - `nl -ba /Users/apple/.codex/skills/.system/skill-creator/SKILL.md | sed -n '1,620p'`
  - `wc -l /Users/apple/.codex/skills/loop-engineering/SKILL.md /Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
  - `rg -n "claude_policy|claude_mode|Claude skipped|claude-unavailable|Forward Test|Decision Gate|set_thread_pinned|Quick Start|Lane-Owned Claude" /Users/apple/.codex/skills/loop-engineering/SKILL.md`

## Review-Owned Claude Analysis

Claude said:

- The hardening direction is sound, but execution should not proceed until two issues are resolved.
- The plan's first-pass `SKILL.md`-only scope is likely incompatible with the 500-line progressive-disclosure guidance.
- The proposed full Claude policy block on every handoff risks becoming formalistic ceremony.

Codex accepts:

- Accept both blocking concerns. They are grounded in the plan and guidance, and they materially affect ExecutionAgent scope.
- Accept Claude's suggested direction: either authorize a limited references split now, or compress the inline edit and require a line-count ceiling.
- Accept tiering the Claude policy fields so `not_needed` does not require heavy boilerplate on routine Dispatcher/status handoffs.

Codex rejects:

- Do not approve execution of the current plan exactly as written.
- Do not ask ExecutionAgent to choose unilaterally between references split and compressed inline edit; that is a planning/user scope decision.

needs evidence:

- PlanningAgent or user must decide whether first-pass execution may create `references/claude-policy.md` and `references/forward-tests.md`, or must stay `SKILL.md`-only with compression and a near/under-500-line target.

final lane decision:

- Plan Review blocks execution pending revision. Return to PlanningAgent/user with the exact scope decision needed.

## Findings

- P1: execution scope is underspecified for the file-length constraint
  Claim:
  The plan says first pass should only edit `SKILL.md`, while also warning that the live skill is already near the 500-line progressive-disclosure threshold and proposing enough new material to likely exceed it.
  Evidence:
  The plan reports current `SKILL.md` at about 461 lines and says if it clearly exceeds 500 lines a later round should split references (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:417-425`). It also says first round should only edit `SKILL.md` and not split references (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:454-469`, `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:739-749`). The live skill is 461 lines by `wc -l` output. Skill-creator says keep `SKILL.md` under 500 lines and split content when approaching that limit (`/Users/apple/.codex/skills/.system/skill-creator/SKILL.md:143-146`).
  Why it matters:
  ExecutionAgent would have to choose between violating the line-count guidance, creating references outside the approved scope, or compressing the plan beyond what was explicitly reviewed.
  Suggested action:
  Revise the plan before execution. Either authorize a narrow references split in this pass, or require a compressed `SKILL.md`-only edit with a line-count target near/under 500 and no long templates.

- P1: Claude policy fields are too broad as a mandatory every-message block
  Claim:
  The plan's proposed Claude policy fields are useful, but requiring the full field block on every handoff/lane artifact risks the formalism the plan explicitly tries to avoid.
  Evidence:
  The plan warns against forcing Claude or creating formality for small tasks (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:35-58`). It then proposes every handoff or lane artifact declare `claude_policy`, `claude_mode`, `reason`, `required_artifact`, and `fallback_if_unavailable` (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:42-50`, `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:185-229`), and adds those fields to Standard Agent Messages (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:291-327`). It also says Dispatcher/status/tiny docs can be `not_needed` (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:255-260`) but still requires a reason for `not_needed` (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:262-266`).
  Why it matters:
  If every mechanical Dispatcher delivery must carry a full Claude-policy block, agents may comply ceremonially without improving review quality, and messages become heavier.
  Suggested action:
  Revise the plan to tier the policy: full fields for `required` and `conditional`; compact `claude_policy: not_needed` plus short reason for mechanical delivery/status/tiny docs; require `Claude skipped` only when `conditional` was considered but not used.

## Criteria Check

- Description trigger update: direction is mostly acceptable, but should trim mechanisms and avoid workflow summary. Writing-skills says descriptions should start with "Use when", include triggering conditions, and never summarize process/workflow (`/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md:95-103`, `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md:140-180`). The plan correctly notes this requirement (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:147-151`), but the proposed description includes several mechanism nouns (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:141-145`).
- Quick Start / Decision Gate: placement before the five-step workflow is appropriate and addresses overuse. It should be concise and should not make `claude_policy` ceremony apply to tiny current-thread work (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:153-184`).
- Claude Participation Policy: concept is useful, but must be tiered to avoid formalistic fields for `not_needed` cases.
- Lane-owned Claude boundaries: ready. The proposed boundaries keep Dispatcher and Manager from running Claude on behalf of lanes (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:268-290`) and reinforce existing Dispatcher limits in the live skill (`/Users/apple/.codex/skills/loop-engineering/SKILL.md:101-104`, `/Users/apple/.codex/skills/loop-engineering/SKILL.md:140-144`).
- Standard Agent Messages: field set is directionally complete but should mark Claude fields as conditional/tiered, not always heavy (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:291-327`).
- Pinning default: ready. The plan changes `set_thread_pinned` from optional to avoid by default unless the user asks (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:328-347`), matching the live optional wording at `/Users/apple/.codex/skills/loop-engineering/SKILL.md:233`.
- Forward Test Scenarios: useful coverage of observed failures (`/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md:348-401`), but execution should keep them compact and add a note not to leak expected/fail answers into subagent prompts. Skill-creator warns forward-test prompts should look like real user tasks and avoid leaking intended fixes or expected answers (`/Users/apple/.codex/skills/.system/skill-creator/SKILL.md:386-416`).
- File-length risk: not acceptable without a scope decision. This is the main blocker.

## Execution Recommendation

Not approved for execution yet.

Return to PlanningAgent/user for a narrow revision that chooses one of these scopes:

1. `SKILL.md` plus two references: allow ExecutionAgent to create only `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md` and `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`, keeping `SKILL.md` lean with direct pointers.
2. `SKILL.md` only: require a compressed edit that keeps the final file near/under 500 lines, uses a compact Claude policy table, one-line forward scenarios, and no long templates.

After that revision, ExecutionAgent can proceed if the revised plan also tiers Claude policy fields and keeps no-pin, lane-owned Claude, route-dynamic, and forward-test leak-hygiene rules.

## Artifact-First ExecutionAgent Handoff Draft

Not applicable yet. Because this review blocks execution, no ExecutionAgent handoff should be sent until PlanningAgent/user resolves the scope and Claude-policy tiering gaps.

If revised and approved later, the next logical lane remains existing ExecutionAgent `019ed72a-2c15-7fa2-86df-d755c7728abd`.
