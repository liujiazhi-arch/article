# Loop Skill Retrospective Brief

loop_id: LOOP-20260618-001-loop-skill
message_id: MSG-022-dispatcher-retrospective-brief
created_at: 2026-06-18T21:18:26+08:00
dispatcher_thread: 019ed67e-ab7c-7861-ba85-ddd12cc745c7

## Goal

Use the completed `loop-engineering` lane trial to improve the future workflow rules in `/Users/apple/.codex/skills/loop-engineering/SKILL.md`.

This brief is input for independent Claude analysis and the existing PlanningAgent. It is not an execution plan and does not authorize direct skill edits.

## What Was Practiced

The active loop tested real multi-thread coordination across:

- `计划Agent`: `019ed6f3-e0a3-74d1-9271-fe83bb648206`
- `执行Agent`: `019ed72a-2c15-7fa2-86df-d755c7728abd`
- `审查Agent`: `019ed6fa-96d1-7473-89a7-676ef3c3a836`
- `Dispatcher / 调度Agent`: `019ed67e-ab7c-7861-ba85-ddd12cc745c7`
- Claude CLI as independent planning/critique input

The useful final chain was:

```text
Dispatcher creates or physically delivers when needed
Planning owns plan content
Execution owns skill edit / repair
Review owns findings
Execution repairs accepted narrow defect
Review verifies repair
```

## Latest User Boundary Correction

The next skill iteration must encode a stronger rule: Claude assistance is owned by each lane, not by Dispatcher.

`Dispatcher / 调度Agent` should only:

- create or find threads
- deliver standard messages
- poll thread status
- maintain `thread-ledger.md`
- remind lanes about missing required artifacts when necessary

Each lane owns its own external-model analysis:

- read its own inputs
- call Claude CLI when the route or risk requires it
- record raw or summarized Claude output
- judge Claude suggestions with Codex evidence
- write the lane decision artifact
- hand artifact paths to the next lane

Future lane artifacts should use this decision shape when Claude is involved:

```text
Claude said:
Codex accepts:
Codex rejects:
needs evidence:
final lane decision:
```

Claude modes to consider:

- `independent_claude_plan`: PlanningAgent asks Claude for an independent plan before showing Codex's plan.
- `claude_plan_critique`: PlanningAgent asks Claude to critique a Codex plan.
- `claude_execution_consult`: ExecutionAgent asks Claude for read-only implementation-risk analysis when the plan or technical path is unclear.
- `claude_review`: ReviewAgent asks Claude for read-only review, then combines it with Codex review judgment.
- `claude_debate`: PlanningAgent or ArbitrationAgent uses 1-2 bounded debate rounds only for substantive Claude/Codex disagreement.

Claude output is evidence, not a command. A lane must not outsource its final decision to Claude.

If Claude cannot read `/Users/apple/.codex/skills/...` or another required live path, the lane that needs Claude must handle it by adjusting access, using `--add-dir`, or writing a temporary context artifact. Dispatcher must not become the content bridge that fills in missing context for Claude.

The Dispatcher-triggered Claude retrospective that happened during this turn is a transitional reference only. It should not define the future communication path; the next PlanningAgent must perform its own lane-owned Claude analysis.

The concrete repair loop was:

```text
MSG-019 execution -> review
  Review found P2 ledger metadata gap
MSG-020 review -> execution
  Execution repaired ledger schema
MSG-021 execution -> review
  Review found no remaining P0/P1/P2
```

## Evidence Artifacts

- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-thread-ledger.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-worklog.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-brief.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-codex-plan.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-claude-plan.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-execution-report.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-dispatcher-review.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-ledger-metadata-repair-report.md`
- `docs/superpowers/plans/2026-06-18-loop-skill-ledger-metadata-repair-review.md`

## Observed Pitfalls

1. `经理Agent`, `Dispatcher`, and bootstrap roles were initially blurred.
   - The user clarified that `经理Agent` is project-level status/history/recovery, not a central workflow owner.
   - The current thread should be physical `Dispatcher` when delivering messages, not planner/reviewer/arbitrator.

2. Same-loop continuation was initially mishandled as if it needed a new lane set.
   - User correction required reusing the existing planning/review scene for the same skill-refinement task.
   - Skill now says same active loop corrections reuse existing `loop_id` and owner lane threads.

3. Physical delivery and logical ownership were initially mixed.
   - Dispatcher may call `send_message_to_thread`, but `from_lane` / `to_lane` must stay with the phase owners.
   - The repair review confirmed rows 17, 19, 20, and 21 preserve logical ownership while recording dispatcher delivery metadata.

4. Ledger schema lagged behind the new message protocol.
   - Review found P2 because active ledger rows lacked `delivered_by_lane`, `delivered_by_thread`, and `delivery_reason`.
   - Execution repaired the ledger and review accepted the fix.

5. Worklog is necessary, not optional.
   - Ledger records messages.
   - Worklog records what each lane did, what it learned, and what later lanes should avoid.

6. Timestamps can become non-monotonic across thread/tool records.
   - The sequence number and message id are more reliable for ordering than wall-clock time.
   - Future protocol may need to say ledgers are ordered by `seq` first, timestamp second.

7. Claude path access can be incomplete.
   - Claude CLI could not read the live `.codex` skill path in this run.
   - This must be recorded as an artifact limitation, and Codex execution/review must verify the live file directly when Claude cannot.

8. Plan Review was talked about but not cleanly represented as a durable stage in this trial.
   - Planning and Claude critique happened.
   - The route would be clearer if future tasks explicitly name whether pre-execution plan review is required, skipped, or merged into planning, with reason.

9. Status rows stayed stale until Dispatcher updated them.
   - `MSG-019`, `MSG-020`, and `MSG-021` were later marked completed.
   - The workflow needs a clear close-out rule for updating ledger status.

10. Skill-writing guidance wants pressure tests.
    - The execution report used a written self-check rather than a fresh-agent pressure scenario.
    - Future skill changes should include pressure scenarios for route selection and role-boundary failures.

## Questions For Claude And PlanningAgent

1. Which of these pitfalls should become explicit rules in `SKILL.md`, and which should stay in project worklog/protocol artifacts?
2. Should `Dispatcher` be listed as a lane, a tool role, or a message-delivery role only?
3. Should every active loop have a required `route_decision` artifact before creating lanes?
4. Should ledgers require `seq`-first ordering and allow non-monotonic timestamps?
5. Should every `send_message_to_thread` require a close-out status update, and who owns it?
6. How should Claude be used when it cannot read global skill paths?
7. What route presets should the skill define for common task families:
   - tiny docs/config
   - process/skill edits
   - normal implementation
   - frontend/backend linkage
   - risky architecture/migration
   - post-review repair
   - user exploration / unclear requirements
8. What is the smallest practical pressure-test suite for future edits to this skill?

## Desired Planning Output

The next PlanningAgent artifact should propose:

- What to add to `SKILL.md`
- What not to add because it belongs in project artifacts
- A compact route preset model
- Durable close-out rules for ledger/worklog
- Claude fallback rules when file access is limited
- Pressure scenarios for verifying the skill
- Whether another execution/review cycle is warranted

## Boundaries

Do not edit `/Users/apple/.codex/skills/loop-engineering/SKILL.md` from this retrospective brief.
Do not create a new lane set for this same loop.
Use the existing PlanningAgent and ReviewAgent if further planning or review is needed.
