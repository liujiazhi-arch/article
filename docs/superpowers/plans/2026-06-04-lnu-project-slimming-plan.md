# LNU Project Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the thesis tool a clear Liaoning University-only product by removing multi-profile product surface, reducing duplicated rule metadata, and splitting the largest rule/fix files into maintainable modules.

**Architecture:** Keep the current stable chain (`thesis_workbench.py -> workflow.py -> audit_thesis.py/fix_thesis.py -> _thesis_utils.py`) while changing product defaults and public interfaces to a single LNU profile. Then move rule metadata and LNU-specific audit/fix passes behind focused modules without changing behavior.

**Tech Stack:** Python 3.11+, python-docx, PyYAML, FastAPI optional API, pytest.

---

## Scan Evidence

- `README.md:77` still documents three support scenarios, including `cn-common` course papers and reviews. This conflicts with the current goal that the project only serves LNU.
- `_profile_utils.py:8` exposes `cn-common` aliases, and `_profile_utils.py:74` defaults missing profile to `cn-common`.
- `article_api/profiles.py:49` returns `list_profile_catalog()`, and `article_api/profiles.py:59` reports `default_profile_id: "cn-common"`.
- `thesis_workbench.py profiles` currently lists both `cn-common` and `lnu-checker-2026`.
- `audit_thesis.py:135` keeps generic `RULE_DEFINITIONS`, `audit_thesis.py:187` adds `LNU_RULE_DEFINITIONS`, and `audit_thesis.py:4006` builds runtime by appending LNU rules then filtering `disabled_rules`.
- `scopes.py:63`, `scopes.py:82`, and `scopes.py:108` still expose rules disabled by the LNU profile: `SP01`, `SP02`, `SP_CJK_LATIN`, `SP_NUM_CJK`, `F03`, `F04`, `R02`, `REF01`.
- `fix_thesis.py` is 6510 lines, with LNU postpasses concentrated at `fix_thesis.py:6130` but still mixed with generic fixes and CLI concerns.
- `audit_thesis.py` is 4191 lines with 182 functions and 86 quoted rule-like IDs.
- `local_console.html` is 2488 lines. The visible UI is LNU-only, but it hardcodes `profile: 'lnu'` while the backend still exposes a multi-profile catalog.

Verification already run:

```bash
/Users/apple/.codex/skills/rtk-token-optimizer/scripts/rtk-exec.sh "python3 -m pytest tests/test_profile_metadata_sync.py tests/test_product_boundary.py tests/test_article_api_boundaries.py -q"
# 18 passed in 0.45s

PYTHONPATH=scripts python3 - <<'PY'
import audit_thesis
for profile in (None, 'lnu'):
    rt = audit_thesis.build_audit_runtime(profile)
    print(profile or 'default', rt.profile_id, len(rt.rule_definitions))
PY
# default cn-common 49
# lnu lnu-checker-2026 74

PYTHONPATH=scripts python3 - <<'PY'
from _profile_utils import list_profile_catalog
items = list_profile_catalog()
print('profile_count', len(items))
for item in items:
    print(item['id'], item['is_default'])
PY
# profile_count 2
# cn-common True
# lnu-checker-2026 False

PYTHONPATH=scripts python3 -m pytest -q
# 618 passed, 1 xfailed in 83.17s
```

## Recommended Direction

Use a staged slimming approach:

1. **Product boundary first:** Make LNU the only public/default profile. Do this before moving files so tests express the intended product.
2. **Metadata consolidation second:** Generate capability/scope views from the LNU runtime instead of keeping disabled CN rules visible.
3. **Module extraction third:** Split `audit_thesis.py` and `fix_thesis.py` along rule groups and passes after behavior is locked down.

Do not delete generic checker logic in the first pass. LNU still depends on many generic body, heading, page, figure/table, citation, and reference checks. The first deletion target is public multi-profile exposure, not every generic function.

## Keep

- LNU profile file and aliases: `lnu`, `lnu-checker`, `lnu-checker-2026`.
- Generic base rule implementations used by LNU runtime: `P01`, `T01-T06`, `H01-H04`, `C01-C04`, `R01`, `R03-R05`, `F01-F02`, `F05-F07`, `TB01-TB03`, `KW01-KW02`, `EQ01-EQ03`, `PU01-PU02`, `FN01`, `PG01`, `P03`, `S01-S03`.
- The single-document local page flow: DOCX upload, apply, verify, PDF render-verify, job query.
- Upload/job/retention support if the local web page remains an end-user tool.
- `config/profiles/CN-Common.yaml` temporarily as an internal source-of-truth/reference while LNU still says `extends: CN-Common`.

## Remove Or Hide First

- Public `cn-common` catalog entry and support scenarios from API/CLI/README.
- Runtime fallback to `cn-common` for user-facing paths. Missing/unknown profile should resolve to LNU or fail clearly.
- Disabled LNU rules from scope/capability output: `SP01`, `SP02`, `SP_CJK_LATIN`, `SP_NUM_CJK`, `F03`, `F04`, `R02`, `REF01`.
- Old wording that advertises course assignments, general reviews, multiple schools, or first-stage multi-scenario support.
- `architecture-flow.html` if it is not opened by the app or tests. If kept, regenerate it after the boundary change so it does not document stale architecture.

## Task 1: Freeze LNU-Only Product Contract

**Files:**
- Modify: `tests/test_product_boundary.py`
- Modify: `tests/test_article_http_smoke.py`
- Modify: `tests/test_profile_metadata_sync.py`
- Modify: `tests/test_workbench_cli.py`

- [x] **Step 1: Add failing tests for public profile catalog**

Add assertions that `/profiles` returns one profile, `default_profile_id == "lnu-checker-2026"`, and no `cn-common` scenario appears.

Expected failing command:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_article_http_smoke.py::test_live_http_upload_apply_result_download_and_cleanup -q
```

Expected failure before implementation: profile count/default still references `cn-common`.

- [x] **Step 2: Add failing CLI tests**

Assert `python3 scripts/thesis_workbench.py profiles` prints only `lnu-checker-2026` and does not print `cn-common`, `课程作业`, or `综述`.

Expected failing command:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_workbench_cli.py -q
```

- [x] **Step 3: Add runtime default test**

Assert `audit_thesis.build_audit_runtime(None).profile_id == "lnu-checker-2026"` and `fix_thesis.build_fix_runtime(None).profile_id == "lnu-checker-2026"`.

Expected failing command:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_profile_metadata_sync.py -q
```

## Task 2: Make LNU The Default And Only Public Profile

**Files:**
- Modify: `scripts/_profile_utils.py`
- Modify: `scripts/article_api/profiles.py`
- Modify: `scripts/thesis_workbench.py`
- Modify: `scripts/article_api/schemas.py`
- Modify: `scripts/article_engine/service.py`

- [x] **Step 1: Introduce constants**

Add constants in `_profile_utils.py`:

```python
DEFAULT_PROFILE_ALIAS = "lnu"
DEFAULT_PROFILE_ID = "lnu-checker-2026"
LNU_PROFILE_PATH = os.path.join(PROFILE_DIR, "lnu-checker-2026.yaml")
```

Use these constants in `PROFILE_ALIASES` instead of repeating the path.

- [x] **Step 2: Change missing profile resolution**

Change `load_profile_bundle(None, ...)` to load the LNU YAML and return `profile_id="lnu-checker-2026"`, `requested_profile=None`, `fallback_used=False`.

Do not make unknown profiles silently become LNU. For unknown explicit profiles, keep strict failure behavior and make non-strict fallback a deprecation target.

- [x] **Step 3: Filter public catalog**

Add a `public_only=True` path in `list_profile_catalog()` or a new `list_public_profile_catalog()` that returns only LNU. Update `article_api/profiles.py` to report:

```python
"profile_count": 1
"default_profile_id": "lnu-checker-2026"
```

- [x] **Step 4: Keep API request defaults simple**

Keep schema defaults at `profile="lnu"` for backwards compatibility, but stop exposing profile as a meaningful product choice in responses. Existing callers can still send `lnu`.

- [x] **Step 5: Verify**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_profile_metadata_sync.py tests/test_product_boundary.py tests/test_article_http_smoke.py tests/test_workbench_cli.py -q
```

Expected: all pass.

## Task 3: Make Scopes Runtime-Aware For LNU

**Files:**
- Modify: `scripts/thesis_tool/scopes.py`
- Modify: `scripts/thesis_tool/workflow.py`
- Modify: `tests/test_profile_metadata_sync.py`
- Modify: `config/capability_matrix.md`

- [x] **Step 1: Add a runtime filter helper**

Add helper:

```python
def filter_scope_definitions(rule_ids: set[str]) -> tuple[ScopeDefinition, ...]:
    filtered = []
    for scope in SCOPE_DEFINITIONS:
        kept = tuple(rule_id for rule_id in scope.rule_ids if rule_id in rule_ids)
        filtered.append(ScopeDefinition(scope.id, scope.title, scope.description, kept, scope.aliases))
    return tuple(filtered)
```

- [x] **Step 2: Use runtime-aware scopes in plans**

In `build_scope_plan`, derive runtime rule ids from `runtime.rule_definitions` and iterate filtered scope definitions. This removes disabled rules from scope views without deleting their implementation yet.

- [x] **Step 3: Align capability matrix with public LNU runtime**

Either remove disabled CN rows from the public matrix or mark them as internal/non-LNU. Recommended: rename the current file to an LNU runtime matrix in content, keeping only the 74 LNU runtime rules.

- [x] **Step 4: Verify**

Run:

```bash
PYTHONPATH=scripts python3 - <<'PY'
from thesis_tool.scopes import list_scope_definitions
import audit_thesis
rt = audit_thesis.build_audit_runtime('lnu')
ids = {rule_id for rule_id, _, _ in rt.rule_definitions}
for scope in list_scope_definitions():
    disabled = [rule_id for rule_id in scope.rule_ids if rule_id not in ids]
    assert not disabled, (scope.id, disabled)
PY
```

Then run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_profile_metadata_sync.py tests/test_scope_workflow.py -q
```

## Task 4: Consolidate Rule Metadata

**Files:**
- Create: `scripts/thesis_rules/__init__.py`
- Create: `scripts/thesis_rules/lnu_runtime.py`
- Modify: `scripts/audit_thesis.py`
- Modify: `scripts/thesis_tool/capabilities.py`
- Modify: `config/profiles/lnu-checker-2026.yaml`
- Modify: `tests/test_profile_metadata_sync.py`

- [x] **Step 1: Move rule definitions to a module**

Create `scripts/thesis_rules/lnu_runtime.py` with:

```python
BASE_RULE_DEFINITIONS = (...)
LNU_RULE_DEFINITIONS = (...)
LNU_DISABLED_RULE_IDS = frozenset({...})
```

Keep exact existing tuples first. Do not rename rule IDs in the move.

- [x] **Step 2: Build one effective LNU list**

Add:

```python
def effective_lnu_rule_definitions() -> tuple[tuple[str, str, str], ...]:
    return tuple(
        item for item in (*BASE_RULE_DEFINITIONS, *LNU_RULE_DEFINITIONS)
        if item[0] not in LNU_DISABLED_RULE_IDS
    )
```

- [x] **Step 3: Make profile additions metadata non-authoritative**

Keep `config/profiles/lnu-checker-2026.yaml` for settings and source notes, but stop treating `additions` as the runtime truth. Tests should assert runtime definitions, checker registry, capability matrix, and profile metadata agree.

- [x] **Step 4: Verify**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_audit_runtime.py tests/test_profile_metadata_sync.py -q
```

## Task 5: Split Audit Checkers By Domain

**Files:**
- Create: `scripts/thesis_rules/audit_common.py`
- Create: `scripts/thesis_rules/audit_lnu.py`
- Modify: `scripts/audit_thesis.py`
- Modify: targeted audit tests under `tests/test_*audit*.py`

- [x] **Step 1: Move pure helper groups first**

Move low-risk text/punctuation helper functions before moving checkers. Keep imports explicit.

- [x] **Step 2: Move LNU checker functions**

Move `check_lnu_*` functions and `LNU_RULE_CHECKERS` into `audit_lnu.py`.

- [x] **Step 3: Move common checker functions**

Move generic `check_*` functions and `RULE_CHECKERS` into `audit_common.py`.

- [x] **Step 4: Keep `audit_thesis.py` as orchestration**

After extraction, `audit_thesis.py` should mainly own IO, runtime building, scoring, report rendering, and CLI.

- [x] **Step 5: Verify**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_audit_runtime.py tests/test_lnu_checker_2026_audit.py tests/test_lnu_v2_audit.py tests/test_audit_rules.py -q
```

## Task 6: Split Fix Passes By Domain

**Files:**
- Create: `scripts/thesis_fix/__init__.py`
- Create: `scripts/thesis_fix/common_passes.py`
- Create: `scripts/thesis_fix/lnu_postpasses.py`
- Create: `scripts/thesis_fix/page_footer.py`
- Create: `scripts/thesis_fix/toc.py`
- Create: `scripts/thesis_fix/tables_figures.py`
- Modify: `scripts/fix_thesis.py`
- Modify: targeted fix tests under `tests/test_*fix*.py`

- [x] **Step 1: Extract LNU postpass dispatcher**

Move `_apply_lnu_postpasses`, `_postprocess_lnu_reference_order`, and related LNU-only small helpers into `thesis_fix/lnu_postpasses.py`.

- [x] **Step 2: Extract large page footer logic**

Move `fix_footer_page_number`, `configure_lnu_section_page_footers`, `center_existing_footer_page_numbers`, and `append_hidden_page_field_marker` into `thesis_fix/page_footer.py`.

- [x] **Step 3: Extract TOC logic**

Move `fix_insert_toc`, TOC title normalization, and TOC entry normalization into `thesis_fix/toc.py`.

- [x] **Step 4: Extract figures/tables layout logic**

Move `normalize_lnu_figure_block_layout`, `normalize_lnu_table_block_layout`, object wrapping, caption numbering, and result object rebalance functions into `thesis_fix/tables_figures.py`.

- [x] **Step 5: Keep `fix_thesis.py` as orchestration**

Target shape: runtime building, `FixExecutionContext`, `normalize_docx`, `fix_docx`, CLI, and imports from focused modules.

- [x] **Step 6: Verify**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_lnu_checker_2026_fix.py tests/test_lnu_v2_fix.py tests/test_fix_workflow_improvements.py tests/test_fix_roundtrip.py tests/test_scope_workflow.py -q
```

## Task 7: Simplify Local Console/API Coupling

**Files:**
- Modify: `scripts/article_api/local_console.html`
- Modify: `scripts/article_api/schemas.py`
- Modify: `scripts/article_api/request_payloads.py`
- Modify: `scripts/article_engine/service.py`
- Modify: `tests/test_article_http_smoke.py`

- [x] **Step 1: Remove profile from page payloads**

Change `requestBase()` so it no longer sends `profile: 'lnu'`. Backend defaults should be LNU.

- [x] **Step 2: Remove user-facing profile payload noise**

Keep profile in API result for debugging if needed, but the page should not depend on it.

- [x] **Step 3: Evaluate candidate modes**

Keep `fast_candidate` if it is used after PDF review. Move `compact_candidate` behind an internal constant or remove it if current users do not choose it. This will shrink both frontend state and job summary branches.

- [x] **Step 4: Verify**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_article_http_smoke.py tests/test_article_api.py tests/test_article_jobs.py -q
```

## Task 8: Documentation Cleanup

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `architecture-flow.html` or delete it if not part of product/docs
- Modify: `config/sources.yaml`

- [x] **Step 1: Rewrite support section**

Replace the three-scenario section with one supported scenario:

```text
当前只支持辽宁大学本科毕业论文（lnu-checker-2026）。
```

- [x] **Step 2: Clarify CN-Common status**

Document `CN-Common.yaml` as internal baseline only, not public product profile.

- [x] **Step 3: Update rule counts**

Public docs should state one active runtime count: LNU 74 rules. Internal docs can mention the baseline count only if needed for maintainers.

- [x] **Step 4: Verify docs do not advertise removed surfaces**

Run:

```bash
rg -n "课程作业|普通论文|综述|cn-common|CN-Common|多校|profile catalog" README.md architecture-flow.html scripts/article_api/local_console.html
```

Expected: only internal-baseline mentions remain, not product-support claims.

## Task 9: Final Verification

- [x] **Step 1: Full test suite**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest -q
```

Expected: no unexpected failures.

- [x] **Step 2: Public catalog smoke**

Run:

```bash
PYTHONPATH=scripts python3 - <<'PY'
from _profile_utils import list_profile_catalog
profiles = list_profile_catalog()
assert [item["id"] for item in profiles] == ["lnu-checker-2026"]
print(profiles[0]["id"], profiles[0]["aliases"])
PY
```

- [x] **Step 3: Runtime rule smoke**

Run:

```bash
PYTHONPATH=scripts python3 - <<'PY'
import audit_thesis
rt = audit_thesis.build_audit_runtime(None)
ids = [rule_id for rule_id, _, _ in rt.rule_definitions]
assert rt.profile_id == "lnu-checker-2026"
assert len(ids) == 74
for disabled in ("SP01", "SP02", "SP_CJK_LATIN", "SP_NUM_CJK", "F03", "F04", "R02", "REF01"):
    assert disabled not in ids
print(rt.profile_id, len(ids))
PY
```

## Expected Outcome

- Public product has one school, one default profile, one support scenario.
- API, CLI, docs, and frontend agree on LNU-only behavior.
- Disabled CN-common rules no longer appear as LNU scope/capability noise.
- `audit_thesis.py` and `fix_thesis.py` become orchestration files rather than rule warehouses.
- Future rule changes land in a single domain module and one metadata source, reducing contradiction risk.
