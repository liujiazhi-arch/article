# Claude Wait Minimum Addendum

loop_id: LOOP-20260618-001-loop-skill
source: user correction in Dispatcher thread
created_at: 2026-06-19T01:09:47+08:00

## User Correction

For deep required Claude plan/review calls, the wait rule should be a minimum wait, not a soft allowance.

Current reference wording says:

```text
allow a five-minute wait window before declaring timeout
```

The user wants this strengthened to:

```text
wait at least five minutes before declaring timeout, unless Claude returns earlier or the CLI exits/errors.
```

## Why This Matters

The earlier hardening Plan Review almost closed out too early while Claude was still running. The corrected behavior was to wait longer, retry through stdin when useful, and record the real elapsed wait instead of treating a short Dispatcher nudge as `claude-unavailable`.

## Requested Route

This is still the same active loop:

```text
LOOP-20260618-001-loop-skill
```

Because the correction changes future agent behavior, route it through the existing lane workflow instead of editing the skill directly from Dispatcher.

Recommended next step:

- PlanningAgent checks whether this is a no-op clarification or a narrow edit.
- If edit is needed, PlanningAgent drafts a bounded ExecutionAgent handoff.
- ExecutionAgent should only touch the approved wait wording.
- ReviewAgent should confirm the minimum-wait behavior is clear and not over-broad.

## Boundary

Do not generalize this into unlimited Claude waiting. The minimum applies to deep required Claude planning/review calls. Ordinary Claude calls can still use the normal timeout unless a lane records why a longer wait is required.
