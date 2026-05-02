# LNU Cover Page Table Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LNU checker/fixer preserve the cover page and implement the school rules for table line spacing, frontmatter page numbers, body page numbers, and body-only TOC insertion.

**Architecture:** Keep the existing XML-preserving main chain in `scripts/fix_thesis.py` and `scripts/audit_thesis.py`. Add targeted tests first, then make the smallest changes to rule metadata, table spacing, section page-size handling, and footer generation.

**Tech Stack:** Python 3, `xml.etree.ElementTree`, existing OOXML helpers in `_thesis_utils.py`, pytest.

---

### Task 1: Correct LNU_TB03 Table Line Spacing Rule

**Files:**
- Modify: `tests/test_lnu_v2_audit.py`
- Modify: `tests/test_lnu_v2_fix.py`
- Modify: `scripts/audit_thesis.py`
- Modify: `scripts/fix_thesis.py`
- Modify: `config/profiles/lnu-checker-2026.yaml`
- Modify: `config/capability_matrix.md`

- [ ] **Step 1: Write failing audit tests**

Change the existing LNU_TB03 audit test so `line=360` passes and `line=240` fails:

```python
def test_lnu_tb03_accepts_table_line_spacing_one_point_five():
    # table cell paragraph spacing line=360 must pass

def test_lnu_tb03_rejects_table_line_spacing_single():
    # table cell paragraph spacing line=240 must fail with "1.5倍"
```

- [ ] **Step 2: Write failing fix test**

Change the existing fix test so a table cell with `line=240` is repaired to `line=360` and `lineRule=auto`.

- [ ] **Step 3: Run RED**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py::test_lnu_tb03_accepts_table_line_spacing_one_point_five tests/test_lnu_v2_audit.py::test_lnu_tb03_rejects_table_line_spacing_single tests/test_lnu_v2_fix.py::test_fix_lnu_tb03_fixes_spacing -q
```

Expected: fail under the current single-spacing implementation.

- [ ] **Step 4: Implement minimal production change**

Update `check_lnu_tb03()` and `fix_lnu_tb03()` to use `table_cell_line` from config, defaulting to `360`, and update all user-facing rule names from “单倍行距” to “1.5倍行距”.

- [ ] **Step 5: Run GREEN**

Run the same pytest command. Expected: all pass.

### Task 2: Preserve Cover Section During Page Layout Fix

**Files:**
- Modify: `tests/test_lnu_v2_fix.py`
- Modify: `scripts/fix_thesis.py`

- [ ] **Step 1: Write failing test**

Add a test that creates three `sectPr` nodes: first inline cover section with custom `pgSz`, second inline frontmatter section, final body section. After `fix_page_margins(..., runtime=lnu_runtime)`, assert the cover `pgSz` is unchanged and only non-cover sections are normalized to A4.

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_fix.py::test_fix_page_margins_preserves_cover_page_size_for_lnu -q
```

Expected: fail because the current LNU `pgSz` loop touches all sections.

- [ ] **Step 3: Implement minimal production change**

Reuse the existing `body_sect_prs` list for LNU page-size normalization instead of scanning `document_root.findall(".//w:sectPr")`.

- [ ] **Step 4: Run GREEN**

Run the same pytest command. Expected: pass.

### Task 3: Add Section-Specific Page Number Footers

**Files:**
- Modify: `tests/test_lnu_checker_2026_fix.py`
- Modify: `scripts/fix_thesis.py`

- [ ] **Step 1: Write failing test**

Add a test with three sections: cover inline `sectPr`, frontmatter inline `sectPr`, and final body `sectPr`. After `fix_footer_page_number()`, assert:

```python
assert cover_sect_pr.find("w:footerReference", NSMAP) is None
assert front_pg_num_type.get(_w("fmt")) == "upperRoman"
assert front_pg_num_type.get(_w("start")) == "1"
assert body_pg_num_type.get(_w("fmt")) == "decimal"
assert body_pg_num_type.get(_w("start")) == "1"
assert front_footer_texts.count("-") == 0
assert body_footer_texts.count("-") == 2
```

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m pytest tests/test_lnu_checker_2026_fix.py::test_fix_footer_page_number_uses_cover_frontmatter_body_sections -q
```

Expected: fail because the current implementation creates one global wrapped footer.

- [ ] **Step 3: Implement minimal production change**

For LNU profiles with at least two section properties, create a plain PAGE footer for the frontmatter section and a hyphen-wrapped PAGE footer for the body section. Do not attach any footer reference to the first inline cover section.

- [ ] **Step 4: Run GREEN**

Run the same pytest command. Expected: pass.

### Task 4: Harden Body-Only TOC Insertion

**Files:**
- Modify: `tests/test_lnu_v2_fix.py`
- Modify: `scripts/fix_thesis.py` only if the test exposes a gap

- [ ] **Step 1: Write regression test**

Add a test with cover, Chinese abstract, English abstract, keywords, and `序言`/body headings. After `fix_insert_toc()`, assert the TOC field is inserted immediately before `序言` and no abstract heading is used as the insertion anchor.

- [ ] **Step 2: Run test**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_fix.py::test_fix_insert_toc_starts_at_preface_not_abstracts -q
```

Expected: pass if current body-only logic is already correct; otherwise fail and then fix only the insertion anchor logic.

### Task 5: Verification

**Files:**
- No production files unless a regression appears.

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
python3 -m pytest tests/test_lnu_v2_audit.py tests/test_lnu_v2_fix.py tests/test_lnu_checker_2026_fix.py tests/test_fix_workflow_improvements.py -q
```

- [ ] **Step 2: Run metadata sync**

Run:

```bash
python3 -m pytest tests/test_profile_metadata_sync.py -q
```

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git diff -- scripts/audit_thesis.py scripts/fix_thesis.py config/profiles/lnu-checker-2026.yaml config/capability_matrix.md tests/test_lnu_v2_audit.py tests/test_lnu_v2_fix.py tests/test_lnu_checker_2026_fix.py
```

Confirm the patch does not touch the original `/Users/apple/Desktop/论文格式检查工具` project and does not edit any user thesis DOCX.
