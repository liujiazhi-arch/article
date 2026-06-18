# Agent Lanes

loop_id: LOOP-20260618-002-lane-test-v2
slug: 2026-06-18-loop-lane-test-v2
status: bootstrap

| lane_id | name | thread_id | thread_title | purpose | read_scope | write_scope | status |
|---|---|---|---|---|---|---|---|
| bootstrap | bootstrap thread | 019ed67e-ab7c-7861-ba85-ddd12cc745c7 | current thread | start test only | brief skill protocol | initial artifacts only | active |
| planning | 计划Agent | not-created | 计划Agent / loop-lane-test-v2-2026-06-18 | plan the skill adjustment and hand off to execution | brief skill protocol | plan artifact worklog ledger next-lane message | pending |
| execution | 执行Agent | created-by-planning | 执行Agent / loop-lane-test-v2-2026-06-18 | execute merged plan or record no-op | merged plan skill | execution report worklog ledger next-lane message | pending |
| review | 审查Agent | created-by-execution | 审查Agent / loop-lane-test-v2-2026-06-18 | review execution and lane evidence | execution report skill artifacts | review artifact worklog ledger | pending |
| status | 经理Agent | optional | 经理Agent / 论文格式工具 | status/history/recovery only | registry and loop artifacts | recovery notes only | not-used |

## Notes

- `bootstrap` is not a main agent.
- Do not pin lane threads.
- The lane that finishes a phase must message the next lane directly.
