# GitHub Project Polish Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current GitHub Beta repository from "source code plus Windows zip" into a credible, student-facing open-source project with clear download flow, screenshots, release evidence, and a staged macOS packaging roadmap.

**Architecture:** Keep the existing runtime and packaging architecture intact. This plan only changes project presentation, release metadata, update-check behavior, documentation, and distribution evidence; implementation changes are scoped to the current `article_api` update-check path and release/build docs.

**Tech Stack:** Python 3.11/3.12, FastAPI local web app, GitHub Actions, GitHub Releases, Markdown docs, existing `scripts/*smoke*.py` release verification tools.

---

## Current Evidence

- Repository: `https://github.com/liujiazhi-arch/article`
- Local checkout: `/Users/apple/Desktop/article`
- Release found: `v0.1.0-beta`, prerelease, assets `article-local-windows.zip` and `article-local-windows.zip.sha256`
- Latest main CI: success
- GitHub community profile health: 85
- Repository gaps: no homepage URL, no topics, no README screenshots, no root `SECURITY.md`, no PR template, no macOS package
- Important bug/risk: `https://api.github.com/repos/liujiazhi-arch/article/releases/latest` returns 404 while the only release is a prerelease; current Beta update checking cannot depend only on `/releases/latest`

## File Map

- Modify: `README.md` - GitHub front page, download path, screenshots, badges, platform table
- Modify: `docs/USER_GUIDE.md` - student-oriented step-by-step flow with screenshots
- Modify: `docs/GITHUB_RELEASE_TEMPLATE.md` - release body that matches the improved README and screenshots
- Modify: `docs/RELEASE_CHECKLIST.md` - add screenshot, metadata, prerelease update-check, and GitHub About checks
- Modify: `docs/DEVELOPMENT.md` - document update-check behavior and macOS packaging boundaries
- Modify: `.github/workflows/ci.yml` - only if update-check packaging env var changes
- Create: `docs/assets/README.md` - explain safe screenshot rules
- Create: `docs/assets/local-console-home.png` - sanitized home screenshot from browser smoke
- Create: `docs/assets/local-console-repaired.png` - sanitized repaired/download screenshot from browser smoke
- Create: `docs/ROADMAP.md` - Windows, macOS, packaging, profile support roadmap
- Create: `docs/TROUBLESHOOTING.md` - common student failure modes
- Create: `SECURITY.md` - root security policy discoverable by GitHub
- Create: `.github/PULL_REQUEST_TEMPLATE.md` - contribution checklist
- Modify: `scripts/article_api/app_ops.py` - if supporting prerelease/tag update checks
- Modify: `scripts/build_windows_local_bundle.py` - if launcher env var changes
- Modify: `scripts/verify_release_artifact.py` - if allowed release API URLs change
- Modify: `tests/test_article_api.py` - update-check tests
- Modify: `tests/test_windows_local_bundle.py` - launcher URL tests
- Modify: `tests/test_release_artifact_verifier.py` - artifact URL validation tests
- Modify: `tests/test_release_readiness.py` - docs/workflow readiness assertions

---

## Phase 0: Freeze Scope And Protect Current Worktree

### Task 0.1: Record Baseline

- [ ] Run: `git status --short --branch`
  Expected: show current branch and existing modified files; do not revert unrelated changes.
- [ ] Run: `gh release view v0.1.0-beta --repo liujiazhi-arch/article --json tagName,isPrerelease,assets,url`
  Expected: release exists, `isPrerelease=true`, assets include Windows zip and sha256.
- [ ] Run: `python3 scripts/github_release_status.py --repo liujiazhi-arch/article --branch main --tag v0.1.0-beta`
  Expected: `"status": "ok"`.
- [ ] Commit only if needed after later tasks; do not commit the user's unrelated current modifications.

---

## Phase 1: Fix Beta Update-Check Strategy

### Task 1.1: Decide Beta Update Endpoint

Recommended decision: support a configured release tag endpoint during Beta:

```text
https://api.github.com/repos/liujiazhi-arch/article/releases/tags/v0.1.0-beta
```

Keep `/releases/latest` support for future stable releases.

- [ ] Confirm that `/releases/latest` returns 404 while only prerelease exists:
  Run: `gh api repos/liujiazhi-arch/article/releases/latest`
  Expected: HTTP 404.
- [ ] Confirm that tag endpoint works:
  Run: `gh api repos/liujiazhi-arch/article/releases/tags/v0.1.0-beta --jq '{tag_name, prerelease, assets: [.assets[].name]}'`
  Expected: `tag_name=v0.1.0-beta`, assets include Windows zip and sha256.

### Task 1.2: Add Tests For Tag Endpoint

- [ ] Modify `tests/test_article_api.py` to accept both:
  - `https://api.github.com/repos/example/article/releases/latest`
  - `https://api.github.com/repos/example/article/releases/tags/v0.1.0-beta`
- [ ] Add a test named `test_update_check_payload_accepts_github_release_tag_api_url`.
- [ ] Run: `python3 -m pytest tests/test_article_api.py -q`
  Expected before implementation: the new test fails.

### Task 1.3: Implement URL Validation

- [ ] Modify `scripts/article_api/app_ops.py`:
  - Rename `_is_github_latest_release_api_url` to `_is_github_release_api_url`
  - Accept path shapes:
    - `/repos/<owner>/<repo>/releases/latest`
    - `/repos/<owner>/<repo>/releases/tags/<tag>`
  - Keep rejecting non-GitHub hosts and unrelated paths.
- [ ] Update user-facing `next_action` text to mention both latest and tag endpoint.
- [ ] Run: `python3 -m pytest tests/test_article_api.py -q`
  Expected: pass.

### Task 1.4: Update Bundle Verifier And Build Tests

- [ ] Modify `scripts/verify_release_artifact.py` with the same URL validator.
- [ ] Modify `tests/test_release_artifact_verifier.py` to cover release tag endpoint.
- [ ] Modify `tests/test_windows_local_bundle.py` to allow passing the tag endpoint.
- [ ] Run: `python3 -m pytest tests/test_release_artifact_verifier.py tests/test_windows_local_bundle.py -q`
  Expected: pass.

### Task 1.5: Update CI Bundle URL

- [ ] Modify `.github/workflows/ci.yml` release build command to use the tag endpoint for prerelease builds if the release event exposes a tag:
  `https://api.github.com/repos/${{ github.repository }}/releases/tags/${{ github.event.release.tag_name }}`
- [ ] Keep non-release/manual workflow behavior either unconfigured or documented as stable-only.
- [ ] Run: `python3 -m pytest tests/test_release_readiness.py -q`
  Expected: pass after updating readiness assertions.

---

## Phase 2: Upgrade README Into A GitHub-Quality Front Page

### Task 2.1: Add Badges And Download Block

- [ ] Modify `README.md` top section to include:
  - CI badge
  - Release badge
  - License badge
  - Python version badge
  - Direct link to `v0.1.0-beta` Release
- [ ] Replace the current opening with:
  - Chinese product name
  - one-sentence value proposition
  - clear audience: 辽宁大学本科毕业论文学生
  - privacy promise: 本地处理，不上传论文
- [ ] Run: `python3 -m pytest tests/test_release_readiness.py -q`
  Expected: pass or update tests to match new README assertions.

### Task 2.2: Add Three-Step Student Quick Start

- [ ] Modify `README.md` with a first-screen "普通学生怎么用" section:
  1. Download `article-local-windows.zip` from GitHub Release
  2. Extract and double-click `启动论文格式检查.bat`
  3. Upload `.docx`, generate plan/fix, download repaired copy, verify in Word/WPS
- [ ] Keep Python install after the student flow, labeled "开发者安装".
- [ ] Run: `python3 -m pytest tests/test_release_readiness.py -q`
  Expected: pass.

### Task 2.3: Add Platform Status Table

- [ ] Modify `README.md` with:

```markdown
| Platform | Current status | User entry |
| --- | --- | --- |
| Windows | Beta supported | `article-local-windows.zip` |
| macOS | Planned experimental package | Not yet released |
| Linux | Developer/source use only | `pip install '.[api]'` |
```

- [ ] Explicitly state: no DMG yet, no MSI yet, no automatic updater yet.

### Task 2.4: Add Screenshot Slots

- [ ] Add Markdown image references:
  - `docs/assets/local-console-home.png`
  - `docs/assets/local-console-repaired.png`
- [ ] If screenshots are not generated yet, create `docs/assets/README.md` first and leave README image links for the generated files only after assets exist.
- [ ] Run a Markdown link check manually with:
  `python3 - <<'PY'\nfrom pathlib import Path\nfor p in ['README.md','docs/assets/README.md']:\n    assert Path(p).exists(), p\nprint('docs ok')\nPY`
  Expected: `docs ok`.

---

## Phase 3: Generate Safe Screenshots

### Task 3.1: Generate Browser Smoke Screenshots

- [ ] Run:

```bash
python3 scripts/local_browser_smoke.py \
  --work-dir /tmp/article-local-browser-smoke \
  --json-output /tmp/article-browser-smoke.json
```

Expected: JSON status `ok`, screenshot paths for `home` and `repaired`.

### Task 3.2: Copy Sanitized Screenshots

- [ ] Verify screenshots do not show real thesis content, real names, local private paths, API keys, logs, or feedback packages.
- [ ] Copy:
  - `/tmp/article-local-browser-smoke/local-console-home.png` to `docs/assets/local-console-home.png`
  - `/tmp/article-local-browser-smoke/local-console-repaired.png` to `docs/assets/local-console-repaired.png`
- [ ] Add `docs/assets/README.md`:

```markdown
# Public Demo Assets

Only sanitized demo screenshots may be committed here.

Allowed:
- Generated smoke-test `.docx` screenshots
- Local web UI screenshots without real student content
- Release/download screenshots without private account data

Forbidden:
- Real thesis text
- Student names, IDs, titles, local paths, logs, API keys
- Feedback packages or screenshots of sensitive file lists
```

### Task 3.3: Verify Assets

- [ ] Run: `file docs/assets/local-console-home.png docs/assets/local-console-repaired.png`
  Expected: both are PNG images.
- [ ] Run: `git status --short docs/assets README.md`
  Expected: only intended README/assets changes.

---

## Phase 4: Add Missing Community And Support Files

### Task 4.1: Add Root Security Policy

- [ ] Create `SECURITY.md` at repository root.
- [ ] Reuse and shorten `docs/SECURITY.md`, keeping:
  - do not upload thesis, repaired drafts, API keys, logs
  - report security/privacy issues without sensitive files
  - feedback package must be checked before sharing
- [ ] Keep `docs/SECURITY.md` as the detailed version, linking to root `SECURITY.md` if useful.

### Task 4.2: Add Pull Request Template

- [ ] Create `.github/PULL_REQUEST_TEMPLATE.md` with checklist:
  - tests run
  - docs updated if user-facing
  - no thesis/API key/log/runtime/state files
  - capability matrix updated for runtime rules
  - release docs updated if packaging changed
- [ ] Run: `git status --short .github/PULL_REQUEST_TEMPLATE.md SECURITY.md`
  Expected: both new files listed.

### Task 4.3: Add Troubleshooting Guide

- [ ] Create `docs/TROUBLESHOOTING.md` covering:
  - ZIP not extracted
  - Windows SmartScreen warning
  - port 8000 occupied
  - invalid `.docx`
  - Word/WPS directory fields need refresh
  - repaired copy opens differently in WPS vs Word
  - feedback package privacy check
- [ ] Link it from `README.md` and `docs/USER_GUIDE.md`.

### Task 4.4: Add Roadmap

- [ ] Create `docs/ROADMAP.md` with:
  - Windows zip Beta stabilization
  - GitHub presentation polish
  - macOS `.app` experimental package
  - macOS DMG with signing/notarization
  - future school profiles only after runtime rules and tests exist
- [ ] Link it from `README.md`.

---

## Phase 5: Improve Release And Repository Metadata

### Task 5.1: Update Release Template

- [ ] Modify `docs/GITHUB_RELEASE_TEMPLATE.md`:
  - add screenshot links
  - add direct "download this asset" wording
  - add platform table
  - add prerelease update-check note if Beta still uses tag endpoint
- [ ] Run: `python3 -m pytest tests/test_release_readiness.py -q`
  Expected: pass after updating assertions.

### Task 5.2: Update Release Checklist

- [ ] Modify `docs/RELEASE_CHECKLIST.md` to require:
  - GitHub About description
  - homepage URL
  - topics
  - README screenshots exist
  - Release assets exist
  - update-check endpoint works for current release type
  - Windows clean-machine smoke report exists
- [ ] Run: `python3 -m pytest tests/test_release_readiness.py -q`
  Expected: pass.

### Task 5.3: Set GitHub Repository Metadata

- [ ] Run:

```bash
gh repo edit liujiazhi-arch/article \
  --description "Local-first .docx thesis format checker for LNU undergraduate theses" \
  --homepage "https://github.com/liujiazhi-arch/article/releases" \
  --add-topic docx \
  --add-topic ooxml \
  --add-topic thesis \
  --add-topic python \
  --add-topic fastapi \
  --add-topic local-first \
  --add-topic privacy \
  --add-topic windows \
  --add-topic chinese-thesis \
  --add-topic lnu
```

- [ ] Verify:
  `gh repo view liujiazhi-arch/article --json description,homepageUrl,repositoryTopics`
  Expected: description, homepage, and topics are present.

---

## Phase 6: macOS Package Roadmap, Not Full DMG Yet

### Task 6.1: Document macOS Decision

- [ ] In `docs/ROADMAP.md`, document three levels:
  1. Source install for developers
  2. Experimental `.app` that starts local server and opens browser
  3. Signed/notarized `.dmg`
- [ ] Add constraints:
  - Apple Silicon first
  - Intel later only if needed
  - no "formal Mac app" wording until signing and notarization pass

### Task 6.2: Add macOS Smoke Checklist

- [ ] Create `docs/MACOS_SMOKE_CHECKLIST.md` with:
  - clean macOS version
  - Apple Silicon/Intel architecture
  - first launch behavior
  - Gatekeeper warning text
  - local server starts and stops
  - browser opens
  - upload/audit/plan/apply/download
  - WPS/Word opens repaired copy
  - no thesis/log/API key in public evidence
- [ ] Link it from `docs/RELEASE_CHECKLIST.md`.

### Task 6.3: Defer DMG Implementation

- [ ] Do not add Electron/Tauri/PyInstaller until Windows Beta presentation and update-check issue are fixed.
- [ ] Create a GitHub issue or `docs/ROADMAP.md` item for macOS packaging instead of implementing immediately.

---

## Phase 7: Final Verification

### Task 7.1: Run Targeted Tests

- [ ] Run:

```bash
python3 -m pytest \
  tests/test_article_api.py \
  tests/test_windows_local_bundle.py \
  tests/test_release_artifact_verifier.py \
  tests/test_release_readiness.py \
  -q
```

Expected: all pass.

### Task 7.2: Run Full Tests

- [ ] Run: `python3 -m pytest -q`
  Expected: all pass.

### Task 7.3: Run Release Status Check

- [ ] Run:

```bash
python3 scripts/github_release_status.py \
  --repo liujiazhi-arch/article \
  --branch main \
  --tag v0.1.0-beta
```

Expected: `"status": "ok"`.

### Task 7.4: Review Diff

- [ ] Run: `git diff --stat`
  Expected: changes limited to README, docs, update-check implementation/tests, and optional workflow metadata.
- [ ] Run: `git diff -- README.md docs .github scripts/article_api/app_ops.py scripts/build_windows_local_bundle.py scripts/verify_release_artifact.py tests/test_article_api.py tests/test_windows_local_bundle.py tests/test_release_artifact_verifier.py tests/test_release_readiness.py`
  Expected: no unrelated runtime rule or thesis formatting changes.

### Task 7.5: Commit In Small Batches

Recommended commits:

```bash
git add scripts/article_api/app_ops.py scripts/build_windows_local_bundle.py scripts/verify_release_artifact.py tests/test_article_api.py tests/test_windows_local_bundle.py tests/test_release_artifact_verifier.py tests/test_release_readiness.py .github/workflows/ci.yml
git commit -m "fix: support beta release update checks"

git add README.md docs/USER_GUIDE.md docs/GITHUB_RELEASE_TEMPLATE.md docs/RELEASE_CHECKLIST.md docs/DEVELOPMENT.md docs/assets
git commit -m "docs: improve GitHub project presentation"

git add SECURITY.md .github/PULL_REQUEST_TEMPLATE.md docs/TROUBLESHOOTING.md docs/ROADMAP.md docs/MACOS_SMOKE_CHECKLIST.md
git commit -m "docs: add project support and packaging roadmap"
```

Do not stage unrelated existing worktree changes.

---

## Execution Recommendation

Execute in this order:

1. Phase 1: update-check strategy, because it is a real Beta release bug.
2. Phase 2 and 3: README plus screenshots, because this directly improves GitHub perception.
3. Phase 4 and 5: community files, release template, metadata.
4. Phase 6: macOS roadmap documentation only.
5. Phase 7: full verification and clean commits.

Do not start macOS DMG implementation until the Windows Beta page, screenshots, update-check behavior, and release evidence are clean.
