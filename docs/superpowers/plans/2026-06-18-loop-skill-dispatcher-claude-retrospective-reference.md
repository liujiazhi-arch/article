# Dispatcher-Triggered Claude Retrospective Reference

NOTE: Transitional reference only. Future workflow should use lane-owned Claude calls inside PlanningAgent, ExecutionAgent, ReviewAgent, or ArbitrationAgent, not centralized Dispatcher-Claude analysis.

I have read all key artifacts plus the live SKILL.md. Here is the analysis.

# Claude Retrospective: Loop Skill Workflow

## Access Notes
- **Could read:** the live global skill `/Users/apple/.codex/skills/loop-engineering/SKILL.md` (431 lines), and all project artifacts — thread-ledger, worklog, retrospective-brief, dispatcher-brief, dispatcher-codex-plan, dispatcher-claude-plan, dispatcher-execution-report, dispatcher-review, ledger-metadata-repair-report, ledger-metadata-repair-review.
- **Note on Claude's own access during the trial:** the trial's `claude-planning` lane reported it *could not* read the `.codex` path (worklog seq 16; ledger MSG-016 marked `completed: Claude could not read live .codex path`). In *this* session I can read it. That inconsistency is itself a finding — Claude's global-path access is not guaranteed and must not be assumed by the skill.
- I edited nothing. This is analysis only.

## Diagnosis
The trial did not fail on tooling; every `send_message_to_thread`, `create_thread`, and Claude CLI call eventually worked. It failed, and then self-corrected, on **role and schema discipline**. Four concrete failure modes are proven by the artifacts:

1. **Role blur (proven, corrected).** `经理Agent`, `Dispatcher`, and the bootstrap thread were initially treated as a central relay (worklog seq 2, 7, 8). User correction forced the distinction: `经理Agent` = status/recovery, `Dispatcher` = physical courier, neither is a workflow authority. The skill now encodes this (SKILL.md:138, 140-142).
2. **Wrong continuation topology (proven, corrected).** A same-loop correction was first handled as if it needed a new lane set (retrospective pitfall #2; worklog seq 9-10). Fix: reuse existing `loop_id` and owner lanes (SKILL.md:125).
3. **Schema lag (proven, corrected via a real repair loop).** The skill text taught delivery metadata before the ledger schema carried the columns. Review caught it as the only P2 (dispatcher-review.md:37-45 → repair-report → repair-review found no remaining P0/P1/P2). This is the trial's strongest evidence that **review-then-narrow-repair works** — MSG-019 → MSG-020 → MSG-021 is a clean, evidence-bound iteration.
4. **Ordering and close-out gaps (proven, NOT yet encoded).** Timestamps are non-monotonic (e.g. worklog seq 19 at 04:41 precedes seq 20 at 04:25; ledger row 21 at 04:23 precedes row 19 at 04:32). Status fields stayed `sent` and were only later flipped to `completed` by the dispatcher. The trial *noticed* this (lessons, pitfalls #6, #9) but the skill text does not yet contain a seq-first rule or a close-out owner rule.

What the trial proved: the **lane model and the review→repair→review cycle are sound**; the durable-traceability layer (ledger ordering, status close-out, Claude-access fallback) is where rules are still missing.

## What Belongs In SKILL.md
Only cross-project, reusable rules. The skill already contains most; the genuinely missing reusable rules are the last three:

- Route-by-risk lane selection (already present, SKILL.md:108-123). Keep.
- `Plan Review` ≠ plan merge; optional, risk-gated (already present, :123). Keep.
- Dispatcher = physical delivery only; logical `from_lane`/`to_lane` stay with phase owners (already present, :140-142). Keep.
- `经理Agent` = status/recovery, not relay (already present, :138). Keep.
- Same-active-loop reuse (already present, :125). Keep.
- Delivery metadata fields and arbitration labels (already present, :183-194, :338-351). Keep.
- **MISSING — add:** ledgers order by `seq` first, timestamp second; non-monotonic wall-clock is allowed and expected across thread/tool records.
- **MISSING — add:** every `send_message_to_thread` row opens at `sent` and must be closed to `completed`/`blocked`/`retry-needed`; the **receiving lane** closes its own inbound row when it finishes, and status/recovery (`经理Agent`) may reconcile stale rows.
- **MISSING — add:** Claude-access fallback — if Claude cannot read a required live path, mark the artifact `partial: path-unreadable`, and Codex execution/review must verify that live file directly before acting on Claude's claims.

## What Belongs In Project Artifacts
Keep these out of the skill — they are instance data, not rules:

- Concrete thread IDs, message IDs, lane-name-to-thread mappings → `agent-registry.md`, `*-agent-lanes.md`, `*-thread-ledger.md`.
- Per-loop lessons and pitfall narratives (the worklog "Lessons" block) → `*-worklog.md`.
- The specific MSG-019/020/021 repair narrative → already correctly in the brief/worklog.
- Per-loop route_decision rationale → a one-line field in the brief or lane-map, not a new skill section.
- The full standard-message field list is borderline; it is already in the skill (:176-190) and should stay there as a template, but filled values stay in artifacts.

## Route Presets
Compact presets. "Claude?" = whether Claude is recommended as an independent participant; "Plan Review?" = pre-execution plan review required; "Post-exec review" = what must run after execution.

| route | preset | Claude? | Plan Review? | Post-exec review |
|---|---|---|---|---|
| tiny docs/config | current thread or `执行Agent` only | no | no | self-evidence only (`rg`/`wc`/file read) |
| process/skill edit | `计划Agent → Plan Review → 执行Agent → 审查Agent` | yes (critique; evidence-bound) | **yes** | `审查Agent` read-only + ≥1 fresh-agent route pressure test |
| normal implementation | `计划Agent → 执行Agent → 审查Agent → 仲裁Agent` | optional | no | `审查Agent` + Codex subagent |
| frontend/backend linkage | full set `计划Agent → Plan Review → 执行Agent → 审查Agent → 仲裁Agent` | **yes** | **yes** | dual review; DOM/network evidence required, not static copy |
| risky architecture/migration | full set, max 2 repair iters | **yes** | **yes** | dual review + arbitration; P0 blocks |
| unclear requirements | `计划Agent` only until `plan-gap` resolved | yes (surface alternatives) | gate (do not execute) | none until scope confirmed |
| post-review repair | `仲裁Agent → 执行Agent repair → 审查Agent` (non-trivial); arbitration repairs tiny docs inline | only if finding contested | no | `审查Agent` re-review of the narrow fix (the proven MSG-019→021 pattern) |
| user exploration | `fork_thread` for scratch; no lanes | yes (brainstorm) | no | none; promote to a real route before any edit |

This matches the skill's current table (:108-123) except it makes Claude-recommendation and post-exec-review explicit per row, which the current table omits.

## Dispatcher And Manager Boundaries
- **Dispatcher (`调度Agent`)** — a *verb*, not a phase. It physically moves messages and maintains ledger/worklog when a logical lane lacks thread-tool access. It may `create_thread`, `send_message_to_thread`, `read_thread`, and write delivery metadata. It may **not** author plan content, decide findings, arbitrate, or set routes after a plan is accepted. Its identity appears only in `delivered_by_lane`/`delivered_by_thread`/`delivery_reason`; never in `from_lane`/`to_lane`. (Live skill :140-142 is correct.)
- **Manager (`经理Agent`)** — a *read-mostly* project-level role: index loops, inspect state, find coordination gaps, repair the registry, reconcile stale ledger status, help the user recover the right thread. It owns no phase, overrides no evidence, and relays no messages. (Live skill :138 is correct.)
- **Crisp test:** if the action *changes a plan/finding/disposition*, it is a phase lane. If it *moves or records* a message, it is Dispatcher. If it *looks up or reconciles* state, it is Manager. The current thread in the trial was correctly Dispatcher only.

## Ledger And Worklog Rules
- **Order by `seq` first, timestamp second.** Wall-clock is non-monotonic across thread/tool records (proven above) — never use it as the primary sort key. `seq` and `message_id` are authoritative.
- **One ledger row per `send_message_to_thread`; rows open at `sent`.** Close-out is mandatory: the row must reach `completed`, `blocked`, or `retry-needed` with a reason (the trial used exactly these — see MSG-002 `retry-needed`, MSG-016 `completed: ...`).
- **Close-out owner:** the lane that *receives and acts on* the message closes its inbound row when it produces its artifact. `经理Agent` may reconcile rows left stale at handoff (this is what happened late in the trial and should be a rule, not an ad-hoc fix).
- **Worklog is mandatory, not optional.** One entry per lane *before* each handoff: action, evidence (`path:line`/command), and lesson/risk. Ledger records *that* a message moved; worklog records *what was learned*. If concurrent appends collide on `seq` (it happened — MSG-009 duplicate, worklog seq 9/10 swap), repair the numbering explicitly rather than leaving ambiguity.
- **Delivery metadata is append-compatible.** Older rows without `delivered_by_*` stay valid; only dispatcher-mediated rows must carry them (repair-review confirmed rows 1-13 `not-recorded` is acceptable).

## Claude Fallback Rules
- **Cannot read a required live path** (the trial's exact failure): Claude proceeds on the artifacts it *can* read, and must **label its output `partial: <path> unreadable`** at the top. It must not silently plan as if it saw the file. Codex execution and review then verify that live file directly before relying on any Claude claim about it. (This is what the trial did informally — make it a rule.)
- **CLI non-zero exit / prompt not received:** retry through stdin once (proven fix, MSG-002→002A); if still failing, write `review-unavailable: non-zero-exit` and do not fabricate Claude output.
- **Timeout (120s default):** `review-unavailable: timeout`.
- **Malformed (missing `## Findings`):** save raw output, mark `review-unavailable: malformed-output`.
- **Route interaction:** on a route where Claude review is *required* (frontend/backend, risky arch), an unavailable Claude review **blocks** close-out and escalates to the user — Codex-only review is not a silent substitute. On optional-Claude routes, continue with Codex review and record the gap.
- Claude output is always **evidence to arbitrate, never an instruction override** (skill :102). Disagreements resolve by `path:line`/command evidence, not model identity.

## Pressure Tests
Run these against any future skill version by asking a fresh agent (no loop context) to state its route and roles. Each has a pass criterion.

1. **One-line typo in a README.** PASS = current thread / `执行Agent` only, no lanes, no Plan Review. FAIL = spins up planning/review lanes.
2. **Edit to this very skill.** PASS = `计划Agent → Plan Review → 执行Agent → 审查Agent`, recognizes it changes future agent behavior. FAIL = treats it as "tiny docs."
3. **Dispatcher-mediated handoff where physical sender ≠ logical sender.** PASS = keeps `from_lane`/`to_lane` on phase owners, fills `delivered_by_*`. FAIL = writes `dispatcher` into `from_lane`.
4. **User says "test that same refinement again."** PASS = reuse existing `loop_id` + owner lanes. FAIL = creates a new lane set (the original trial bug).
5. **Claude CLI returns exit 1, then can't read a required path.** PASS = retry via stdin, then label `partial`/`review-unavailable`, Codex verifies the live file, no fabrication. FAIL = invents Claude findings or stalls.
6. **Two reviews split P0 (Claude says P0, Codex subagent says reject).** PASS = arbitration cites `path:line` counter-evidence or marks `needs more evidence` and gathers more; does not average. FAIL = "compromise" disposition or model-identity tiebreak.

The trial only ran a *written self-check* (execution-report:119-126), not fresh-agent runs — dispatcher-review:61 flagged this as residual risk. The skill should require at least scenarios 2, 3, and 4 as live fresh-agent runs for any future skill edit.

## Minimal Next Edit
**The skill does not need a structural rewrite — it is 431 lines and already encodes routes, Plan Review, Dispatcher, delivery metadata, and arbitration labels.** dispatcher-review.md:62 already warns against further protocol bloat. Make the smallest additive edit that closes the three proven-but-unencoded gaps, ideally replacing existing text rather than appending:

1. **One sentence in the ledger rules** (near :192-194): *"Order ledger rows by `seq` first; wall-clock `time` may be non-monotonic across threads. Every row opens at `sent` and must be closed to `completed`/`blocked`/`retry-needed`; the receiving lane closes its inbound row, and `经理Agent` may reconcile stale status."*
2. **One sentence in Claude Bridge** (near :94-102): *"If Claude cannot read a required live path, it labels its artifact `partial: path-unreadable`; Codex execution/review then verifies that live file directly before acting on Claude's claims about it."*
3. **One line in the process-skill route row or Common Mistakes:** require ≥1 *fresh-agent* route pressure test (not a written self-check) for edits that change future agent behavior.

Everything else from this retrospective (route Claude/review annotations, the detailed pressure suite, per-loop route_decision rationale) belongs in the project protocol/worklog, **not** in the skill. If even these three additions feel like creep, items 1 and 3 can live in `2026-06-18-loop-engineering-agent-lanes-protocol.md` instead, leaving only the Claude-fallback sentence as a true cross-project skill change — that one is the single edit I would prioritize, because Claude's path access is the one variable the skill currently assumes and the trial proved unreliable.
