# Thesis Tool Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the external audit report into a verified, prioritized set of fixes that improves audit accuracy without widening the product scope beyond the current LNU thesis workflow.

**Architecture:** Keep the current `thesis_workbench.py -> workflow.py -> audit_thesis.py / fix_thesis.py` pipeline. Fix false positives/false negatives in rule checkers first, then align fixers where they can safely preserve existing OOXML runs, then update scope/capability metadata to reflect what remains manual.

**Tech Stack:** Python 3, `xml.etree.ElementTree`, OOXML `.docx` package XML, pytest, existing `scripts/thesis_rules/*`, `scripts/fix_thesis.py`, and `scripts/thesis_fix/*`.

---

## Evidence Summary

### Verified True

- `scripts/fix_thesis.py:1723-1738` and `scripts/fix_thesis.py:3875-3880` collapse paragraph text into the first `w:t` node and blank later nodes. This can destroy run-level formatting when caption numbering or reference type markers are fixed.
- `scripts/thesis_rules/audit_lnu.py:292-345` uses a local `in_ref` scanner for `LNU_REF01` and `LNU_REF02`. It does not terminate on blank paragraphs, but it does terminate on wrapped or continuation paragraphs that do not begin with `[`.
- `scripts/thesis_rules/audit_common.py:187-189` checks body run size through direct `w:rPr/w:sz`, not `get_effective_run_size`, causing false positives when size is inherited from style.
- `scripts/thesis_rules/audit_common.py:210-211` checks body line spacing through direct `w:pPr/w:spacing` string attributes, not `get_paragraph_line_spacing`, causing false positives when spacing is inherited.
- `scripts/thesis_rules/audit_lnu.py:989-991` treats missing table-level `w:tblBorders` as broken, even though three-line tables can be implemented with cell-level borders.
- `scripts/fix_thesis.py:3652-3674` does not center the Chinese abstract title despite the docstring saying it should.
- `scripts/thesis_rules/audit_lnu.py:766-790` resolves reference line spacing and size effectively, but reads `jc` and `suppressAutoHyphens` directly from paragraph properties.
- `scripts/fix_thesis.py:3334-3365` sets top/bottom/left/right/insideV and first-row bottom borders, but does not set table-level `insideH`.
- `scripts/thesis_rules/audit_lnu.py:160-186` scans every context for figure/table caption numbering instead of restricting to caption modules.
- `scripts/thesis_rules/audit_lnu.py:111-148` checks acknowledgement `eastAsia` font only, while the fixer applies font axes, size, and spacing.
- `scripts/thesis_rules/audit_lnu.py:439-464` hardcodes English abstract body size and font instead of using `abstract_en_body_*` config.
- `scripts/thesis_rules/audit_common.py:952-1010` can re-open footer XML multiple times in one `PG01` check.
- `scripts/fix_thesis.py:3574` only fixes double-spaced section titles when the title is in one run.
- `scripts/thesis_fix/toc.py:203-207` falls back to page number `"1"` when no old TOC page number exists.
- `scripts/fix_thesis.py:4320-4322` applies full body formatting to body-section paragraphs classified as `"other"`.
- `config/profiles/lnu-checker-2026.yaml` loads `check_snap_to_grid`, `frontmatter_page_number_format`, `body_page_number_wrap`, and `abstract_body_*`, but matching audits are missing or incomplete.
- `scripts/thesis_tool/scopes.py:121-124` defines appendix scope with no rule ids.

### Partly True / Severity Needs Adjustment

- `LNU_ABS02` creates `visible_runs` and then iterates `runs`, but empty runs are skipped before checks. The visible-run variable is not itself the bug; the remaining issue is that inherited font values can still be skipped when no effective font is resolved.
- `LNU_TITLE01` audit does not actually require single-run titles because it reads context text. The single-run limitation is in the fixer.
- `FN01`, `EQ02`, `EQ03`, `LNU_REF06`, and `LNU_CONC01` are audit-only/manual in `config/capability_matrix.md`; this is not a hidden implementation bug. The metadata should stay explicit.
- Figure/table same-page checks are property-based proxies. That is a known OOXML limitation, not a direct defect unless the product claims render-level pagination certainty.
- Cover-page automation is intentionally outside the current mainline per `AGENTS.md`; it should remain documented as out of scope unless product scope changes.

### Rejected As False

- The report's `LNU_TB02` namespace claim is false for the current Python XML model. `w:val` is namespace-qualified in ElementTree, and `sz.get(f"{{{W}}}val")` is correct. Evidence command:

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
root=ET.fromstring(f'<w:sz xmlns:w="{W}" w:val="24"/>')
print(root.attrib)
print(root.get(f'{{{W}}}val'))
print(root.get('val'))
PY
```

Observed output:

```text
{'{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val': '24'}
24
None
```

The existing focused test also passes:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py::test_lnu_tb02_rejects_table_text_not_in_fifth_size -q
```

Observed output:

```text
1 passed in 0.05s
```

## File Structure

- Modify `scripts/thesis_rules/audit_common.py`: body size/line-spacing inheritance, `PG01` footer cache, optional snap-to-grid audit.
- Modify `scripts/thesis_rules/audit_lnu.py`: reference scanner reuse, abstract checks, acknowledgement checks, table border audit, caption scope filtering, reference paragraph effective properties.
- Modify `scripts/fix_thesis.py`: preserve run formatting in caption/reference fixes, center Chinese abstract title, set `insideH`, narrow `"other"` paragraph body formatting.
- Modify `scripts/thesis_fix/toc.py`: avoid silently writing fake page `1`.
- Modify `scripts/thesis_tool/scopes.py`: add rule ids only for newly implemented appendix/body/abstract audits.
- Modify `config/capability_matrix.md`: reflect any new audit rules and keep manual-only rules explicit.
- Modify tests in `tests/test_lnu_v2_audit.py`, `tests/test_lnu_v2_fix.py`, `tests/test_lnu_checker_2026_audit.py`, and `tests/test_fix_workflow_improvements.py`.

## Task 1: Body Audit Inheritance

**Files:**
- Modify: `scripts/thesis_rules/audit_common.py`
- Test: `tests/test_lnu_v2_audit.py`

- [ ] **Step 1: Add failing tests for inherited body size and line spacing**

Create two tests with a style map containing body paragraph properties:

```python
def test_t03_accepts_body_size_inherited_from_paragraph_style(lnu_cfg):
    p = _make_paragraph("正文内容")
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "BodyText")
    contexts = [_ctx(1, p, "正文内容", "body", "body")]
    style_map = {"BodyText": {"sz": 24}}

    passed, issues, _ = audit_thesis.check_t03(_doc_with_paragraphs(p), contexts, style_map, lnu_cfg)

    assert passed, issues


def test_t04_accepts_body_line_spacing_inherited_from_paragraph_style(lnu_cfg):
    p = _make_paragraph("正文内容")
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "BodyText")
    contexts = [_ctx(1, p, "正文内容", "body", "body")]
    style_map = {"BodyText": {"spacing_line": 360}}

    passed, issues, _ = audit_thesis.check_t04(_doc_with_paragraphs(p), contexts, style_map, lnu_cfg)

    assert passed, issues
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py::test_t03_accepts_body_size_inherited_from_paragraph_style tests/test_lnu_v2_audit.py::test_t04_accepts_body_line_spacing_inherited_from_paragraph_style -q
```

Expected: both fail before implementation.

- [ ] **Step 3: Update `check_t03` and `check_t04`**

Use `get_effective_run_size(run_elem, style_map, ctx["elem"])` in `check_t03`. Use `get_paragraph_line_spacing(ctx["elem"], style_map)` and direct `lineRule` only when direct spacing exists in `check_t04`; inherited `360` should pass.

- [ ] **Step 4: Run focused and existing body tests**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py -q
```

Expected: pass.

## Task 2: Reference Section Scanning

**Files:**
- Modify: `scripts/thesis_rules/audit_lnu.py`
- Test: `tests/test_lnu_v2_audit.py`

- [ ] **Step 1: Add failing tests for wrapped references**

```python
def test_lnu_ref01_checks_wrapped_reference_continuation(lnu_cfg):
    title = _make_paragraph("参考文献")
    ref1 = _make_paragraph("[1]\tAuthor. Title[J].")
    continuation = _make_paragraph("continued，with fullwidth comma.")
    ref2 = _make_paragraph("[2]\tAuthor. Title[M].")
    contexts = [
        _ctx(1, title, "参考文献", "h1", "references"),
        _ctx(2, ref1, "[1]\tAuthor. Title[J].", "reference", "references"),
        _ctx(3, continuation, "continued，with fullwidth comma.", "reference", "references"),
        _ctx(4, ref2, "[2]\tAuthor. Title[M].", "reference", "references"),
    ]

    passed, issues, _ = audit_thesis.check_lnu_ref01(_doc_with_paragraphs(title, ref1, continuation, ref2), contexts, {}, lnu_cfg)

    assert not passed
    assert any("，" in issue for issue in issues)
```

- [ ] **Step 2: Replace local scanner**

Use `iter_reference_section_contexts(contexts, skip_empty=True)` in `check_lnu_ref01` and `check_lnu_ref02`. For `LNU_REF02`, only enforce number-prefix format on paragraphs whose stripped text begins with `[`, and do not end scanning on continuation paragraphs.

- [ ] **Step 3: Verify**

Run:

```bash
python3 -m pytest tests/test_reference_section_utils.py tests/test_lnu_v2_audit.py -q
```

Expected: pass.

## Task 3: Run-Preserving Text Fixes

**Files:**
- Modify: `scripts/fix_thesis.py`
- Test: `tests/test_lnu_v2_fix.py`

- [ ] **Step 1: Add failing tests that preserve formatting runs**

Add a caption test where the prefix is in the first run and the title is bold in the second run; after renumbering, the second run must still contain the title and `w:b`.

Add a reference test where a title or journal run has formatting; after adding `[J]`, existing non-prefix runs must remain non-empty.

- [ ] **Step 2: Implement prefix-only replacement**

For `renumber_lnu_captions`, replace only the text span containing the old caption prefix. If the full prefix is in the first visible `w:t`, update that node only. If the prefix spans runs, merge only the prefix span and leave title runs intact.

For `fix_lnu_ref04`, append or insert the marker into the last non-empty text node instead of rewriting the full paragraph into `text_nodes[0]`.

- [ ] **Step 3: Verify**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_fix.py -q
```

Expected: pass.

## Task 4: Abstract And Acknowledgement Completeness

**Files:**
- Modify: `scripts/thesis_rules/audit_lnu.py`
- Modify: `scripts/fix_thesis.py`
- Test: `tests/test_lnu_v2_audit.py`
- Test: `tests/test_lnu_v2_fix.py`

- [ ] **Step 1: Add failing tests**

Test that `LNU_ABS01` rejects a left-aligned Chinese abstract title and that `fix_lnu_abs01` centers it.

Test that Chinese abstract body checks `abstract_body_font`, `abstract_body_ascii_font`, `abstract_body_size`, `abstract_body_line`, and `abstract_body_indent`.

Test that `LNU_ABS03` reads `abstract_en_body_size` and `abstract_en_body_ascii_font` from config.

Test that `LNU_ACK01` rejects wrong acknowledgement size and line spacing, not just wrong `eastAsia`.

- [ ] **Step 2: Implement**

Use existing helpers: `get_paragraph_alignment`, `get_paragraph_line_spacing`, `get_paragraph_spacing_after`, `get_effective_run_size`, and `get_effective_run_font`.

In `fix_lnu_abs01`, call `ensure_alignment_and_indent(p, "center", no_indent=True)` after `p_pr = ensure_ppr(p)`.

- [ ] **Step 3: Verify**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py tests/test_lnu_v2_fix.py -q
```

Expected: pass.

## Task 5: Table Border Audit And Fix Alignment

**Files:**
- Modify: `scripts/thesis_rules/audit_lnu.py`
- Modify: `scripts/fix_thesis.py`
- Test: `tests/test_lnu_v2_audit.py`
- Test: `tests/test_lnu_v2_fix.py`

- [ ] **Step 1: Add failing tests**

Add an audit test for a three-line table implemented through first-row cell `top`/`bottom` and last-row cell `bottom` borders with no `tblBorders`. It should pass.

Add a fix test confirming `fix_table_borders` sets `insideH` to `single` with `sz="6"` or another deliberately chosen representation documented in the test name.

- [ ] **Step 2: Implement cell-level fallback**

When `tblBorders` is missing, inspect row/cell borders before reporting a missing border definition. Treat valid cell-level top, header separator, and bottom borders as passing.

- [ ] **Step 3: Decide `insideH` semantics**

If the desired renderer behavior is a table-level inner horizontal separator, set `insideH` in `fix_table_borders`. If first-row cell bottom is the canonical representation, do not set `insideH`; instead update `LNU_TB01` and the capability matrix to say the rule accepts first-row separator, not data-row `insideH`.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py tests/test_lnu_v2_fix.py -q
```

Expected: pass.

## Task 6: Page Number Audit Accuracy

**Files:**
- Modify: `scripts/thesis_rules/audit_common.py`
- Test: `tests/test_lnu_checker_2026_audit.py`

- [ ] **Step 1: Cache footer page paragraphs**

Refactor `_iter_footer_page_paragraphs` in `check_pg01` so it computes footer paragraphs once per `check_pg01` call and reuses the list.

- [ ] **Step 2: Add tests for body page wrap**

Create a minimal `.docx` fixture with footer `— PAGE —` and one with plain `PAGE`; assert LNU config with `body_page_number_wrap: hyphen_wrap` checks the body footer wrap instead of ignoring it because `pg01_format` is `"plain"`.

- [ ] **Step 3: Add frontmatter Roman audit only if section XML exists**

Inspect `w:sectPr/w:pgNumType` for frontmatter and body sections when available. If section separation cannot be detected, return a non-failing affected message instead of guessing.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_lnu_checker_2026_audit.py tests/test_audit_runtime.py -q
```

Expected: pass.

## Task 7: Scope And Metadata Hygiene

**Files:**
- Modify: `scripts/thesis_tool/scopes.py`
- Modify: `config/capability_matrix.md`
- Test: `tests/test_scope_workflow.py`
- Test: `tests/test_profile_metadata_sync.py`

- [ ] **Step 1: Decide new rule ids**

Prefer extending existing LNU rules where behavior is the same user-facing requirement:

- Extend `LNU_ABS01` for Chinese abstract title alignment.
- Add `LNU_ABS05` only if Chinese abstract body needs separate reporting from the existing abstract title/body rules.
- Extend `LNU_ACK01` for acknowledgement font size and line spacing.
- Add `LNU_BODY_GRID01` only if snap-to-grid deserves separate reporting.
- Add appendix audit rules only if appendix is promoted from optional repair-only scope.

- [ ] **Step 2: Update capability matrix**

Keep audit-only/manual rules explicit. Do not mark `FN01`, `EQ02`, `EQ03`, `LNU_REF06`, or `LNU_CONC01` as auto-fix unless a real fixer is implemented and tested.

- [ ] **Step 3: Verify**

Run:

```bash
python3 -m pytest tests/test_scope_workflow.py tests/test_profile_metadata_sync.py tests/test_release_readiness.py -q
```

Expected: pass.

## Task 8: Safer Fix Boundaries

**Files:**
- Modify: `scripts/fix_thesis.py`
- Modify: `scripts/thesis_fix/toc.py`
- Test: `tests/test_lnu_v2_fix.py`

- [ ] **Step 1: Add tests for body `"other"` preservation**

Create a paragraph classified as `"other"` in the body section with equation-adjacent or special-block style and verify body scope does not clear its intended style unless the classifier identifies it as a body paragraph.

- [ ] **Step 2: Narrow `_apply_paragraph_fix`**

Change the `paragraph_type == "other" and section_name == "body"` branch to run only when `paragraph_node.module == "body_other"` and the paragraph has clear body text signals. If uncertain, skip and report through audit rather than formatting destructively.

- [ ] **Step 3: Replace fake TOC page fallback**

Change `make_toc_result_entry` so missing page numbers are blank or use a field result placeholder that Word can update, not hardcoded `"1"`.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_fix.py tests/test_toc_keyword_fallback.py -q
```

Expected: pass.

## Final Verification

- [ ] Run focused audit/fix suites:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py tests/test_lnu_v2_fix.py tests/test_lnu_checker_2026_audit.py tests/test_lnu_checker_2026_fix.py -q
```

- [ ] Run workflow and metadata suites:

```bash
python3 -m pytest tests/test_scope_workflow.py tests/test_audit_runtime.py tests/test_profile_metadata_sync.py tests/test_release_readiness.py -q
```

- [ ] Run full suite before claiming completion:

```bash
python3 -m pytest -q
```

## Recommended Execution Order

1. Task 1 and Task 2 first: they fix clear false positives/false negatives in core audit output.
2. Task 3 next: it prevents user-visible formatting damage during fixes.
3. Task 4 and Task 5 next: they close high-value LNU requirement gaps.
4. Task 6 next: page-number checks touch package-level `.docx` structure and should be isolated.
5. Task 7 after rule behavior stabilizes: metadata should describe actual runtime behavior.
6. Task 8 last: it is a product-safety cleanup and may require judgment from real sample docs.
