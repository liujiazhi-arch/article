# TOC Page Render Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep student-supplied TOC page numbers during TOC formatting, remove the visible `待核对` fallback, and add PDF-render based checks that compare TOC page numbers against actual heading pages.

**Architecture:** DOCX structure repair remains responsible for TOC appearance only. PDF render verification becomes responsible for TOC page-number consistency using extracted PDF page text, without requiring Word automation by default.

**Tech Stack:** Python, OOXML parsing through existing helpers, `pdftotext` text extraction, pytest.

---

### Task 1: Preserve TOC Page Numbers Without Placeholder

**Files:**
- Modify: `scripts/thesis_fix/toc.py`
- Test: `tests/test_fix_workflow_improvements.py`

- [ ] Update the TOC scope test so generated visible TOC entries do not contain `待核对`.
- [ ] Add coverage that existing visible TOC page numbers are preserved when regenerating TOC entries.
- [ ] Change `make_toc_result_entry()` so missing inherited/existing page numbers produce an empty final page-number run instead of `待核对`.
- [ ] Run targeted TOC tests.

### Task 2: Add PDF TOC Page Match Analysis

**Files:**
- Modify: `scripts/thesis_tool/render_verify.py`
- Test: `tests/test_render_verify.py`

- [ ] Add a focused helper that extracts TOC entries and declared page numbers from PDF page text.
- [ ] Add a focused helper that locates heading text on later PDF pages.
- [ ] Add render findings for mismatches and unconfirmed entries.
- [ ] Include TOC page-match findings in `render_findings`, `evidence_items`, `summary`, and the Markdown report.
- [ ] Run targeted render verification tests.

### Task 3: Integration Verification

**Files:**
- Test: existing pytest suite subset

- [ ] Run TOC and render verification tests together.
- [ ] Run full pytest if targeted tests pass.
- [ ] Report changed files and verification output.
