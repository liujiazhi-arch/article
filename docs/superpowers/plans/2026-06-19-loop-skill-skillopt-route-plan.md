# SkillOpt Route Plan For Loop Engineering

loop_id: LOOP-20260618-001-loop-skill
lane: planning
thread_id: 019ed6f3-e0a3-74d1-9271-fe83bb648206
created_at: 2026-06-19T04:44:21+08:00
claude_policy: conditional

## Source

- `docs/superpowers/plans/2026-06-19-loop-skill-skillopt-comparison.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`
- `/Users/apple/.codex/skills/loop-engineering/references/forward-tests.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- `/tmp/SkillOpt-main/README.md`
- `/tmp/SkillOpt-main/docs/guide/training-loop.md`
- `/tmp/SkillOpt-main/docs/guide/skill-document.md`
- `/tmp/SkillOpt-main/docs/sleep/README.md`
- `/tmp/SkillOpt-main/plugins/codex/README.md`

PlanningAgent skipped a fresh Claude call. Reason: this is a route decision, not an execution spec; the SkillOpt comparison is already source-backed; the safest decision is to avoid a global skill edit until the sleep/optimization layer has a dedicated design loop and review.

## SkillOpt Lessons Accepted

- Treat skill documents as trainable state, but only through bounded proposals and validation gates. SkillOpt describes rollout, reflection, aggregation, selected edits, update, and gate as the core training loop.
- Preserve the held-out gate idea: a process-skill edit should not be accepted only because a model proposes it; it should pass pressure scenarios or real replay evidence first.
- Use sleep-cycle thinking for offline improvement: mine past sessions, replay recurring tasks, consolidate lessons, stage proposals, and require explicit adoption.
- Keep zero inference-time overhead as a design goal. Runtime loop behavior should remain governed by the current lane protocol; offline optimization can propose better protocol text later.
- Treat loop artifacts as candidate training data: worklog for pitfalls, ledger for handoff topology, review artifacts for labeled defects, arbitration for dispositions, and baton for recovery failures.

## SkillOpt Lessons Rejected Or Deferred

- Do not replace the current lane protocol with SkillOpt. SkillOpt does not model named Codex lane threads, artifact-first handoffs, Dispatcher physical delivery, or thread-ledger accounting.
- Do not auto-edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md` from mined history. Skill changes must be staged, reviewed, and explicitly adopted.
- Do not put long SkillOpt or sleep-cycle descriptions into `SKILL.md`. The live skill is already a compact runtime protocol entrypoint.
- Defer route-graph generation as a product/system design topic. Dynamic lane graphs for video editing, research, frontend/backend linkage, or release work need their own route-design artifact and tests.

## Current Skill Impact

No current global skill edit is warranted now.

Reason:

- The current `loop-engineering` skill already covers dynamic route selection, artifact-first messages, lane-owned Claude, Dispatcher boundaries, worklog/ledger/artifact/baton separation, review/arbitration, and forward-test references.
- SkillOpt adds an offline optimization discipline, not a missing runtime handoff rule.
- Adding SkillOpt now would either bloat `SKILL.md` or create references without a validated adoption workflow.

If a future edit is approved, it should be a tiny `SKILL.md` pointer plus a reference file, not inline expansion. Candidate future file:

- `/Users/apple/.codex/skills/loop-engineering/references/offline-optimization.md`

That future reference should define staged proposals, held-out pressure gates, adoption rules, and what loop artifacts can be mined. It should not implement a SkillOpt runner inside the skill text.

## Future Orchestration Project Direction

SkillOpt belongs mainly to a future standalone agent-orchestration project, not the current skill hardening loop.

Proposed project shape:

```text
Task Intake
-> Route Designer
   -> choose lane graph, required artifacts, Claude policy, review depth
-> Dispatcher
   -> create/find threads, deliver artifact-first envelopes, poll, ledger
-> Lane Agents
   -> own tools, Claude consultation, artifacts, worklog
-> Review / Arbitration
   -> evidence-based dispositions
-> Sleep / Optimization Layer
   -> mine prior loops, replay recurring tasks, stage skill/protocol proposals, gate, adopt
```

Boundaries:

- `loop-engineering` remains the runtime protocol for substantial coding loops.
- A future orchestration system designs lane graphs across domains.
- A sleep/optimization layer learns from prior loops and proposes changes; it does not directly own runtime execution.

## Pressure Scenarios

Use these to test dynamic route design across domains before adding SkillOpt-derived references to the global skill:

1. Frontend/backend linkage
   - User asks to verify whether an existing frontend matches backend capabilities.
   - Expected route: `计划Agent -> Plan Review -> 执行Agent or 验证Agent -> 审查Agent -> 仲裁Agent` when defects affect behavior.
   - Failure signal: treats as a simple docs review or skips browser/API evidence.

2. Skill/process edit
   - User asks to change a skill in a way that affects future agent behavior.
   - Expected route: `计划Agent -> Plan Review -> 执行Agent -> 审查Agent`; require evidence and pressure checks.
   - Failure signal: direct edit from Dispatcher or current thread without review.

3. Video-editing workflow
   - User asks for a researched edited video with script, assets, cuts, factual checks, and publication package.
   - Expected route: dynamic graph such as `计划Agent -> 检索Agent -> 文案Agent -> 剪辑Agent -> 事实/版权审查Agent -> 成片审查Agent -> 仲裁Agent`.
   - Failure signal: forces the default coding route or creates all standard lanes without domain-specific ownership.

4. Tiny docs/config task
   - User asks for a spelling fix or mechanical ledger repair.
   - Expected route: current thread or `执行Agent` only, compact `claude_policy: not_needed`.
   - Failure signal: spawns multi-agent lanes or ceremonial Claude calls.

5. Offline sleep proposal
   - Prior worklogs show repeated Dispatcher overreach or premature Claude timeout.
   - Expected route: offline optimizer stages a proposal, then current workflow reviews and adopts or rejects it.
   - Failure signal: mined history directly edits live skills without Plan Review and held-out pressure gates.

6. Route change after new evidence
   - Execution finds the plan impossible or riskier than planned.
   - Expected route: reverse handoff to PlanningAgent or escalation to Review/Arbitration, with ledger/worklog evidence.
   - Failure signal: ExecutionAgent silently changes the plan and continues.

## Codex Decision

Claude said:

- Not called for this planning pass.

Codex accepts:

- SkillOpt's validation-gated optimization model is relevant for long-term improvement of skills and protocols.
- Sleep-cycle ideas fit a future offline layer that mines worklogs, ledgers, reviews, arbitration, and batons.
- Dynamic route design should be pressure-tested across task domains before being encoded globally.

Codex rejects:

- No current global `loop-engineering` skill edit.
- No ExecutionAgent handoff for SkillOpt-derived changes.
- No import of SkillOpt's training loop into the runtime lane protocol.
- No Dispatcher or Manager authority expansion.

needs evidence:

- A separate design loop should prove that route-design patterns generalize across at least frontend/backend linkage, skill/process edits, video-editing workflows, tiny docs/config tasks, and offline sleep proposals.
- A future offline-optimization reference should be gated by held-out scenarios and ReviewAgent approval before editing the global skill.

final lane decision:

- Stop with this PlanningAgent artifact for the current loop.
- Treat SkillOpt as input for a future standalone orchestration/sleep-design project.
- If the user asks to proceed, start a separate design loop or a new planning artifact for `offline-optimization.md`; do not route to ExecutionAgent from this artifact.

## Next Lane Recommendation

Current loop next lane: none.

Recommended status: planning artifact only, no ReviewAgent or ExecutionAgent handoff required now.

If the user wants to pursue SkillOpt integration, recommended new route:

```text
PlanningAgent -> Plan Review -> ExecutionAgent -> ReviewAgent
```

Only after a dedicated design artifact approves either:

- a tiny pointer from `SKILL.md` to `references/offline-optimization.md`; or
- a standalone orchestration project outside the current `loop-engineering` skill.

## Handoff Draft

No active handoff for this loop.

Optional future artifact-first Plan Review draft if the user asks to proceed:

```markdown
<!-- LOOP:AGENT_MESSAGE v1 -->

message_type: plan_review
loop_id: <new-or-current-loop-id>
message_id: <next-readable-id>
from_lane: planning
to_lane: review
claude_policy: conditional
source_artifacts:
- docs/superpowers/plans/2026-06-19-loop-skill-skillopt-route-plan.md
- docs/superpowers/plans/2026-06-19-loop-skill-skillopt-comparison.md
- /Users/apple/.codex/skills/loop-engineering/SKILL.md
- /Users/apple/.codex/skills/loop-engineering/references/forward-tests.md

task:
Read the route plan directly and review whether SkillOpt-derived offline optimization should become a future reference or standalone orchestration project.

boundaries:
- Do not edit the skill.
- Do not modify SkillOpt source.
- Do not create threads unless explicitly authorized.

required_output:
- Review artifact approving or rejecting the proposed future route.

exit_criteria:
- Clear decision: no current edit, future reference, or standalone project.
```

## Worklog Entry

Planned row:

```text
| 51 | 2026-06-19T04:44:21+08:00 | planning | 019ed6f3-e0a3-74d1-9271-fe83bb648206 | compared SkillOpt lessons against loop-engineering and recommended no current skill edit | `2026-06-19-loop-skill-skillopt-route-plan.md`; `2026-06-19-loop-skill-skillopt-comparison.md`; `/tmp/SkillOpt-main` | SkillOpt is best treated as a future offline optimization/orchestration project, not a runtime lane-protocol replacement |
```
