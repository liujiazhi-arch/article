# Claude Plan Critique: Loop Engineering Skill Hardening

loop_id: LOOP-20260618-001-loop-skill
lane: review
thread_id: 019ed6fa-96d1-7473-89a7-676ef3c3a836
created_at: 2026-06-19T00:47:39+08:00
claude_policy: required
claude_mode: claude_plan_critique

## Source

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-engineering-skill-hardening-plan.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/plugins/cache/openai-curated/superpowers/43313cc9/skills/writing-skills/SKILL.md`
- `/Users/apple/.codex/skills/.system/skill-creator/SKILL.md`

## Invocation Notes

- First Claude CLI invocation with long prompt argument produced no output and was terminated after the user corrected the wait policy and requested a retry.
- Second invocation used stdin and returned successfully after an extended wait.

## Verdict

Approve the direction with two issues to resolve before execution. The hardening targets are real and the proposed controls are well matched to observed failures. But the round-1 scope as written collides with the 500-line progressive-disclosure constraint, and the Claude policy fields are broad enough to recreate the form-filling the plan warns against.

## Blocking Findings

**B1. Only-`SKILL.md` scope is incompatible with the cited 500-line limit.**

Claude estimated the current skill at roughly 462 lines and the proposed additions at roughly +115 lines, which would push the file to about 580 lines. This conflicts with the plan's own file-length concern and the skill-creator guidance to keep `SKILL.md` under 500 lines. Claude recommends either authorizing `references/claude-policy.md` and `references/forward-tests.md` in this pass, or compressing the inline changes enough to stay near/under 500 lines.

**B2. Mandatory full Claude-policy block recreates the formalism the plan forbids.**

Claude found that requiring the full five-field Claude block on every handoff and lane artifact, including routine Dispatcher polls, risks becoming empty form-filling. It recommends tiering the policy: full fields only for `required` or `conditional`; for `not_needed`, allow a compact inline marker with a reason appropriate to the lane or phase.

## Nonblocking Findings

- The proposed description lists mechanisms such as ledgers, worklogs, batons, and dispatcher-mediated handoffs. This is useful keyword coverage but should be trimmed toward triggering conditions to better match writing-skills guidance.
- The Decision Gate duplicates existing Purpose content. It should be folded into or immediately after Purpose, and tiny tasks should not be pushed toward Claude-policy ceremony.
- The Five-Step section still reads like the default path; consider relabeling it as the full-scale path.
- Forward-test scenarios should warn future agents to pass only the input line to subagents, not expected/fail behavior.
- The plan has a forward-test suite but no fresh RED baseline in this cycle; the execution report should state that honestly if no baseline is run.
- Pinning, lane-owned Claude boundaries, and the route-dynamic note are good as proposed.

## Execution Scope Advice

Claude recommends resolving file-length scope before execution. Preferred option: authorize two references files in this pass for Claude policy and forward tests. If the user insists on `SKILL.md` only, ExecutionAgent should compress the policy matrix and forward-test scenarios and verify with `wc -l` that the file stays near/under 500 lines.

Execution should also tier the Claude policy fields, keep lane-owned and no-pin changes, add a forward-test leak-hygiene note, and record exact `wc -l` and `rg` output.
