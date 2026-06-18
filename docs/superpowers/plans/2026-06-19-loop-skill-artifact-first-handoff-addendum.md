# Artifact-First Handoff Addendum

loop_id: LOOP-20260618-001-loop-skill
created_at: 2026-06-19T00:17:41+08:00
source: user correction in Dispatcher thread

## Rule

When a complete artifact already exists, such as a `plan.md`, cross-lane messages should be artifact-first.

The structured `LOOP:AGENT_MESSAGE` is the envelope. It should carry:

- artifact path
- why the receiving lane should read it
- boundaries
- required output
- exit criteria

It should not replace the artifact by re-expanding, summarizing, or decomposing the full plan content unless the artifact is unavailable.

## Reason

Rewriting a complete plan inside the handoff can lose detail, introduce interpretation drift, or make the receiving lane rely on Dispatcher's summary instead of the source artifact.

## Preferred Pattern

```text
source_artifacts:
- docs/.../plan.md

task:
Read the artifact directly and decide the next lane action.

compact_summary:
One or two sentences only, for orientation.
```

## Boundary

Dispatcher may format the envelope, but the content source remains the artifact owner. If the receiving lane needs the full plan, it must read the path directly.
