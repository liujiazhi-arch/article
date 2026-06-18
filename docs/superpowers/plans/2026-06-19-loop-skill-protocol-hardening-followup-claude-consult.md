# Protocol Hardening Follow-up Claude Consult

loop_id: LOOP-20260618-001-loop-skill
lane: execution
thread_id: 019ed72a-2c15-7fa2-86df-d755c7728abd
created_at: 2026-06-19T01:32:12+0800
claude_policy: required
claude_mode: claude_execution_consult

## Source

- `/Users/apple/Desktop/article/docs/superpowers/plans/2026-06-19-loop-skill-protocol-hardening-followup.md`
- `/Users/apple/.codex/skills/loop-engineering/SKILL.md`
- `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`

## Invocation

Probe:

```text
command -v claude -> /Users/apple/.local/bin/claude
claude --version -> 2.1.178 (Claude Code)
```

First attempt:

- command shape: `claude -p --permission-mode dontAsk --add-dir ... --disallowedTools Edit,Write,MultiEdit <prompt>`
- result: non-zero due to CLI parsing/unknown deny-tool issue; prompt was not accepted correctly.
- action: retried through stdin as allowed by the skill.

Retry:

- command shape: `printf <prompt> | claude -p --permission-mode dontAsk --add-dir /Users/apple/Desktop/article --add-dir /Users/apple/.codex/skills/loop-engineering --disallowedTools 'Edit,Write,MultiEdit'`
- exit status: `0`
- elapsed wait: `83` seconds
- note: CLI printed `Permission deny rule "MultiEdit" matches no known tool`, but still returned a valid read-only consult and exit status 0.

## Claude Said

```markdown
## Findings

The scope is sound and maps cleanly onto existing anchors. The edits are reword-in-place candidates, not new sections, so compactness is achievable.

- **Edit 1 (cross-model debate trigger):** Pure description keyword. `references/claude-policy.md:19` already uses "bounded debate input," so the trigger is grounded. No workflow summary needed — drop it into the `description:` frontmatter list. Sufficient and trivially compact.
- **Edit 2 (artifact-first hard rule):** The concept already exists twice — `SKILL.md:85` ("send paths and compact summaries instead of re-expanding") and `SKILL.md:221` ("Full content belongs in artifacts; messages carry paths, compact summary..."). Both are currently *soft preference* phrasing. To make it a hard rule you must harden **both** or they read inconsistently. The real subtlety: line 221 explicitly *permits* a "compact summary," while the follow-up forbids "compress... or paraphrase." These are not in conflict only if the wording distinguishes a short orienting pointer (allowed) from reproducing/paraphrasing the artifact body (forbidden). If the implementer bans all summarizing, it contradicts the existing intent and over-constrains. Also add the new element the follow-up wants: a **read requirement** on the receiver.
- **Edit 3 (mandatory `claude_policy`):** Currently `SKILL.md:207` says "claude_policy / claude_mode / claude_reason **when applicable**." Making `claude_policy` itself mandatory is consistent with `claude-policy.md:11`, which already says `not_needed` is "compact `claude_policy: not_needed` plus a short reason. Do not require mode/artifact/fallback." So `not_needed` lightweight behavior **is preserved** *as long as* only `claude_policy` is promoted to mandatory and the tier fields (`claude_mode`, `required_claude_artifact`, `fallback_if_claude_unavailable`) stay conditional-on-tier. The follow-up wording (edit 3) gets this right. Watch the "lane artifacts" half — Artifact Protocol Rules (`SKILL.md:80-85`) has no `claude_policy` line today; add one compact bullet rather than a block.
- **Edit 4 (required close-out gate):** New, but belongs in the reference file per scope. It is lane-scoped ("a lane with `claude_policy: required` cannot close out"), which is correct and does not touch `not_needed`. Make sure it names *who* closes out (the lane) and that Dispatcher/经理Agent can only *flag*, not satisfy, the gate — otherwise it leaks authority.
- **Edit 5 (Common Mistakes):** Five bullets append to the existing list (`SKILL.md:445-466`). ~5 lines, no structural change.

## Suggested Wording

Description (`SKILL.md:3`):
> ...cross-model Claude/Codex planning, review, **or debate**, named Codex agent threads...

Artifact-first hard rule — harden `SKILL.md:221` (canonical) and align `SKILL.md:85`:
> When a complete plan or formal artifact already exists, the handoff **must** carry the artifact path, a read requirement, boundaries, and exit criteria, plus at most a short orienting pointer. Do not rewrite, split, compress, or paraphrase the artifact body into the message. A compact pointer is allowed; reproducing artifact content is not.

Mandatory policy — `SKILL.md:207` block:
> `claude_policy` (required in every loop message)
> `claude_mode` / `claude_reason` / `required_claude_artifact` / `fallback_if_claude_unavailable` per the selected policy tier

Artifact Protocol Rules — add one bullet near `SKILL.md:85`:
> - Every lane artifact states its `claude_policy`; tier fields follow `references/claude-policy.md`. `not_needed` stays one line.

Close-out gate — new subsection in `claude-policy.md` under the tier table:
> ## Required Close-Out Gate
> A lane with `claude_policy: required` cannot close out (final lane conclusion, execution report, or final report) without either the `required_claude_artifact`, or a recorded `claude-unavailable: <reason>` with elapsed wait and an explicit block-or-degrade decision. `Dispatcher` and `经理Agent` may flag a missing gate but cannot satisfy it for the lane.

## Risks

- **Compact-summary vs no-paraphrase contradiction (most likely defect).** If edit 2 bans summaries outright it collides with the existing "compact summary" allowance at line 221. Wording must permit a short pointer and forbid only full-body reproduction/paraphrase. Verify both line 85 and line 221 end up consistent.
- **`not_needed` regression.** Low, but real if the implementer promotes tier fields (not just `claude_policy`) to mandatory in the message block. The fix: only `claude_policy` is unconditional; everything else stays "per tier." The verification grep should confirm `not_needed` still reads as one-line.
- **Authority leak.** Low. None of the edits inherently elevate Dispatcher/Manager, and edit 5 + the close-out gate wording actively reinforce the opposite. Only risk is sloppy phrasing like "Dispatcher sets claude_policy" or "Dispatcher closes the gate" — keep policy ownership with the logical lane (`SKILL.md:161,223` already do).
- **Length.** Low. Current file is 467 lines; +5 bullets and in-place rewording lands ~475, under the 500 target. Keep edit 4's detail in `claude-policy.md` (allowed) rather than `SKILL.md`. Avoid adding any new SKILL.md subsection for edit 2 — reword existing lines only.
- **Duplication drift.** Two artifact-first locations must not diverge. Treat line 221 as canonical hard rule and make line 85 a one-clause echo, or it will read as two slightly different rules.

## Verdict

No blocker. The scope is sufficient, compact-compatible, and preserves `not_needed` lightweight behavior as written. Proceed, with two must-dos for the implementer: (1) thread edit 2 so a short pointer stays allowed while full-body rewrite/paraphrase is forbidden, and harden both line 85 and line 221 consistently; (2) promote only `claude_policy` to mandatory, keeping tier fields conditional. The artifact-first handoff should be a hard rule (the follow-up is right to require this) — just scoped to "when a complete artifact exists," not every trivial message.
```

## Codex Accepts

- Accept: make `cross-model debate` a trigger-only description addition.
- Accept: harden artifact-first wording in both Artifact Protocol and Standard Agent Messages, while preserving a short orienting pointer.
- Accept: make only `claude_policy` mandatory everywhere; keep tier-specific fields conditional so `not_needed` remains lightweight.
- Accept: add required-Claude close-out gate to `references/claude-policy.md`, lane-owned and not satisfiable by Dispatcher or `经理Agent`.
- Accept: add compact Common Mistakes bullets.

## Codex Rejects

- Reject any wording that bans all compact orientation in handoffs. The rule should forbid rewriting, splitting, compressing, or paraphrasing artifact bodies.

## Needs Evidence

- Final line count and targeted `rg` verification after the patch.

## Final Lane Decision

Proceed with the bounded edit in `/Users/apple/.codex/skills/loop-engineering/SKILL.md` and `/Users/apple/.codex/skills/loop-engineering/references/claude-policy.md`.
