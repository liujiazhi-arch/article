# SkillOpt Comparison For Loop Engineering

loop_id: LOOP-20260618-001-loop-skill
lane: dispatcher
thread_id: current dispatcher thread
created_at: 2026-06-19T04:41:13+08:00
claude_policy: not_needed
claude_reason: Dispatcher is doing source collection and delivery only. Any future planning lane may choose its own Claude consultation.

## Source

- SkillOpt source zip downloaded from `https://github.com/microsoft/SkillOpt/archive/refs/heads/main.zip`.
- Local analysis path: `/tmp/SkillOpt-main`.
- SkillOpt README: `/tmp/SkillOpt-main/README.md`.
- Training loop reference: `/tmp/SkillOpt-main/docs/guide/training-loop.md`.
- Skill document reference: `/tmp/SkillOpt-main/docs/guide/skill-document.md`.
- SkillOpt-Sleep reference: `/tmp/SkillOpt-main/docs/sleep/README.md`.
- Codex integration reference: `/tmp/SkillOpt-main/plugins/codex/README.md`.
- Sleep engine code:
  - `/tmp/SkillOpt-main/skillopt_sleep/cycle.py`
  - `/tmp/SkillOpt-main/skillopt_sleep/consolidate.py`
  - `/tmp/SkillOpt-main/skillopt_sleep/gate.py`
  - `/tmp/SkillOpt-main/skillopt_sleep/staging.py`
  - `/tmp/SkillOpt-main/skillopt_sleep/harvest_codex.py`

## Verification

Git clone failed twice with GitHub HTTP2 framing errors, so Dispatcher used source zip:

```text
curl -L --retry 3 --retry-delay 2 -o /tmp/skillopt-main.zip https://github.com/microsoft/SkillOpt/archive/refs/heads/main.zip
```

Local smoke test:

```text
python3 -m pytest tests/test_sleep_engine.py tests/test_json_utils.py tests/test_scoring.py -q
66 passed, 1 skipped in 0.12s
```

## What SkillOpt Actually Adds

SkillOpt treats a skill document as trainable state. Its normal loop is:

```text
rollout -> reflect -> aggregate -> select -> update -> gate
```

Important mechanisms:

- Rollout: run tasks under the current skill and score trajectories.
- Reflect: analyze failed and successful trajectories into bounded edit patches.
- Aggregate/select: merge similar patches and limit the edit budget, similar to a learning rate.
- Gate: accept a candidate skill only if validation score improves.
- Slow update/meta skill: carry compact longitudinal guidance across epochs.

SkillOpt-Sleep adapts this to local coding agents:

```text
harvest Codex/Claude transcripts
-> mine recurring tasks
-> replay offline
-> consolidate bounded edits
-> gate on held-out tasks
-> stage proposal
-> user adopt
```

This is close to the user's desired long-term direction: the agent system should learn from prior loop failures instead of relying only on chat memory.

## What It Does Not Solve For Us

SkillOpt does not directly provide our current cross-thread lane topology:

- It does not model named Codex threads as `计划Agent / 执行Agent / 审查Agent / 仲裁Agent / 经理Agent`.
- It does not provide a `send_message_to_thread` ledger protocol.
- It does not solve artifact-first handoffs between active Codex threads.
- It does not decide per-task lane routes such as video editing requiring retrieval, script extraction, editing, review, and publishing lanes.

So SkillOpt is not a replacement for `loop-engineering`. It is an optimization layer that can sit above or beside it.

## Direct Lessons For Loop Engineering

1. Keep the current lane protocol as the runtime communication layer.
2. Add a future offline improvement layer that mines ledger/worklog/review artifacts for recurring failures.
3. Never auto-edit the live skill from mined history. Stage proposals first, then require explicit adopt or lane-reviewed execution.
4. Use validation gates before accepting process-skill edits, especially because bad protocol rules can degrade many future tasks.
5. Treat worklog/ledger/artifact/baton as training data candidates:
   - worklog gives repeated pitfalls.
   - ledger gives message topology and delivery failures.
   - review artifacts give labeled defects.
   - baton gives recovery-state failure modes.
6. Separate task-route selection from skill optimization:
   - Route selection decides which lanes are needed for a user task.
   - Skill optimization decides whether protocol text should change after evidence accumulates.

## Future Project Direction

The user is asking for more than a single skill: a flexible agent orchestration system that can design lane topologies for different work domains while preserving cross-agent verification.

Possible architecture:

```text
Task Intake
-> Route Designer
   -> choose lane graph and required artifacts
-> Dispatcher
   -> create/find threads, send artifact-first envelopes, poll, ledger
-> Lane Agents
   -> own tools, Claude consultation, worklog, artifacts
-> Review/Arbitration
   -> evidence-based disposition
-> Sleep/Optimization Layer
   -> mine prior loops, propose skill/protocol edits, gate, stage, adopt
```

Example video-editing route:

```text
计划Agent
-> 检索Agent
-> 文案Agent
-> 剪辑Agent
-> 事实/版权审查Agent
-> 成片审查Agent
-> 仲裁Agent
```

Example frontend/backend linkage route:

```text
计划Agent
-> Plan Review
-> 执行Agent
-> 浏览器验证Agent or 审查Agent
-> 仲裁Agent
```

## Candidate Additions To Discuss, Not Yet Execute

- Add a reference file for `route-design-patterns.md`, not a long section in `SKILL.md`.
- Add a reference file for `loop-optimization-sleep.md`, explaining how to mine worklogs and stage skill proposals.
- Add a rule that process-skill edits may use SkillOpt-style gates: pressure prompts, held-out scenarios, and review approval before adoption.
- Keep `SKILL.md` lean; put long route examples and sleep-cycle policy in references.

## Planning Request

PlanningAgent should decide:

1. Whether SkillOpt-derived ideas should enter the current `loop-engineering` skill now or wait for a separate design loop.
2. If now, whether the edit should be a tiny pointer in `SKILL.md` plus one reference file, not a large inline expansion.
3. Which pressure scenarios would prove route-design flexibility:
   - frontend/backend linkage
   - skill/process edit
   - video editing with retrieval/script/edit/review lanes
   - small docs-only task that should not spawn lanes
4. Whether a future standalone project is warranted for dynamic agent orchestration.

## Dispatcher Recommendation

Do not edit the global skill directly from Dispatcher.

Recommended next route:

```text
Dispatcher -> PlanningAgent
```

Ask PlanningAgent for a route/design decision. Because this is architecture-level process design and may affect future loops, PlanningAgent should use lane-owned Claude if it decides the design is ready for skill changes. If PlanningAgent recommends a skill edit, send it to ReviewAgent before ExecutionAgent.
