# Frontend Backend Contract

Date: 2026-07-14

## Frontend Entry

- `GET /` returns the student frontend.
- `GET /static/{path}` returns frontend assets.

## Uploads

- Public PDF review never converts DOCX to PDF. The student exports the repaired DOCX with Word/WPS and imports that PDF.
- A repaired DOCX upload must precede the repaired PDF upload because it is the content-matching source for the review.

- `POST /uploads/docx`
  - Form field: `file`
  - Returns: `upload_id`, `file_name`, `stored_path`, `workspace_dir`, `runtime_root`, `size_bytes`, `created_at`

- `POST /uploads/pdf`
  - Form field: `file`
  - Returns: `upload_id`, `file_name`, `stored_path`, `workspace_dir`, `runtime_root`, `size_bytes`, `created_at`

## Jobs

- `POST /uploads/{upload_id}/plan`
  - Body: `{ "profile": "lnu", "scopes": [] }`; both fields are optional.
  - Returns the backend format score, `scope_radar_summary`, summary, and per-scope counts used by the workbench.
  - This is the student frontend planning interface. The frontend keeps the `upload_id` and never depends on `stored_path`.

- `POST /plan`
  - Body: `{ "file_path": "..." }`
  - Compatibility interface for trusted local callers that already own a filesystem path.

- `POST /uploads/{upload_id}/jobs/apply`
  - Body: `{ "scopes": ["..."] }`
  - Creates a DOCX repair job from a DOCX upload.

- `POST /uploads/{docx_upload_id}/render-review-jobs`
  - Body: `{ "pdf_upload_id": "...", "pdf_matches_docx_confirmed": true, "generate_static_toc": true }`
  - `pdf_matches_docx_confirmed` records only the user's confirmation that the PDF came from the current DOCX; it is not sufficient evidence by itself.
  - The backend also compares extractable DOCX and PDF body content. Only user confirmation plus a content match can set `layout_decision_eligible = true` for a manual PDF.
  - The frontend consumes canonical `render_evidence_status` and `layout_decision_eligible`. It must not infer trust from the confirmation flag, file names, page count, or the presence of evidence items. `pdf_content_match_status` may be shown for diagnostics.
  - Upload-based review defaults `generate_static_toc` to true. The generic render API and CLI keep it false unless explicitly requested.
  - Creates a background `render-verify` job.
  - Resolves `file_path` from the DOCX upload.
  - Resolves `rendered_pdf` from the PDF upload.

- `POST /render-verify`
  - Compatibility interface for trusted local callers that already own filesystem paths.
  - Requires `rendered_pdf`; it does not accept renderer selection or a page-image directory.

- `GET /jobs/{job_id}`
  - Returns `status`, `summary`, `artifacts`, and student-safe job metadata.

- `GET /jobs/{job_id}/result`
  - Returns the final operation result after success.

- `GET /jobs?limit={count}`
  - Returns local job history with student-safe display metadata.
  - Legacy manual-PDF records that claimed layout evidence before content matching are downgraded in the response adapter only. The API returns `layout_decision_eligible = false`, `evidence_trust = "unverified"`, and `pdf_content_match_status = "not-verified"` without rewriting SQLite history.

- `GET /jobs/{job_id}/artifacts/{role}/download`
  - Downloads an available `output`, `report`, or `toc-output` artifact from a completed job.

## Feature Support Matrix

| Student-facing feature | Backend source | Frontend rule |
| --- | --- | --- |
| Format radar | Upload plan -> `score`, `scope_radar_summary`, and `scopes[]` fallback counts | Show the backend score directly. Keep affected scopes, automatic scope count, manual review, unsupported, and unknown counts separate. Do not recompute the score from findings or present it as proof that cover and PDF layout are compliant. |
| Thesis structure index | Upload plan -> `scopes[].failed_count` | Sum only the scope IDs declared by each structure group. These are issue counts, not paragraph counts. |
| Repair scope selection | Upload plan -> per-scope autofixable, manual-review, and unsupported counts | Enable only scopes with real automatic fixes. Keep mixed scopes selected while clearly marking that confirmation is still required. |
| Processing flow | Upload response, plan response, job status, result availability | Mark upload, plan, apply, verify, and download stages from completed backend events. Do not advance stages on a timer or static markup. |
| Result status | Apply result `summary`, `readiness`, and `business_status` | Distinguish generated, needs-fix, and needs-confirmation states. Do not call an unchecked result compliant. |
| Rule spectrum | Apply result `verification.scopes[]` | Render one labelled item per returned scope. `status = not_checked` is a warning labelled `未检查`; otherwise `failed_count = 0` is pass and a positive count is the real remaining issue count. An actual cover insertion or replacement may show that operation result, but must not imply automated cover compliance. |
| Downloads | Job `artifacts[]` and artifact download endpoint | Enable only artifacts marked available. Keep the original file untouched. |
| PDF issue evidence | Render-review result `summary` and `evidence_items[]` | Show only backend-provided page images, page numbers, messages, optional boxes, and uniquely matched text-line highlighting. Never invent a page or precise location. |
| Static TOC finalization | Render-review result `toc_finalization` and the `toc-output` artifact | Offer the download only when `layout_decision_eligible = true` and every heading has an exact page mapping. Then ask the student to export and review the PDF again. |
| History | Job list and job result endpoints | A completed apply job restores its result. A completed render-review job restores its document name, PDF name, completion state, and evidence. Historical PDF evidence is view-only until the student uploads the matching DOCX again. |

## Module Ownership

| Module | Owns | Must not own |
| --- | --- | --- |
| `static/js/app.js` | Screen composition, cross-feature workflow lifecycle, request ownership, and delegated page commands | Feature-specific markup, view-local selection state, score calculation, result formatting, or HTTP details |
| `static/js/api.js` | HTTP transport and terminal-job polling | DOM access or student copy |
| `static/js/state.js` | Cross-feature workflow facts and document/PDF request epochs | View-local selection state or DOM references |
| `static/js/workflowView.js` | Plan states, scope controls, structure counts, and Apply availability | Uploads, job polling, or result rendering |
| `static/js/formatRadar.js` | Radar model and radar rendering from plan facts | Recomputing the backend score |
| `static/js/resultView.js` | Apply result status, artifacts, and rule spectrum | Job execution |
| `static/js/historyView.js` | History list rendering | History fetching or active-result ownership |
| `static/js/pdfReview.js` | PDF shell context, evidence selection, real overlays, reset behavior, and review metrics | PDF analysis, cross-feature workflow state, or invented locations |
| `article_api/response_payloads.py` | HTTP serialization, artifact metadata, and transport-only workflow mode | Recomputing render evidence or TOC facts already present in the engine summary |
| `thesis_tool/scope_plan.py` | Audit result to scope-plan assembly | Apply or render orchestration |
| `thesis_tool/workflow.py` | Apply and verify I/O orchestration | Reimplementing plan assembly or render-source selection |
| `thesis_tool/render_sources.py` | Word PDF, supplied PDF, and supplied page-image resolution | Evidence analysis |
| `thesis_tool/render_verify.py` | Canonical render evidence, review, and TOC summary facts | HTTP serialization or frontend display labels |
| `thesis_tool/scope_verify.py` | Pure scope-verification assembly from a plan and diagnostics | File I/O |
| `thesis_tool/pdf_backend.py` | PDF conversion and text geometry backend | Workflow policy |

Every new student-facing feature must name one backend fact source, one frontend owner, and a behavior test through its public interface. New view logic does not go into `app.js`; new transport logic does not go into a view module; frontend code never derives server paths from upload responses.

## Profile Metadata Boundary

- Effective LNU metadata order is `CN-Common.yaml rules` -> same-ID LNU overrides -> LNU additions -> `disabled_rules`.
- Runtime definitions and `config/capability_matrix.md` are tested mirrors of that YAML source. They may keep local checker bindings and short names, but severity, check level, method, scope, and action metadata must not drift.
- `reference_additions` and `reference_overrides` document future or non-runtime rules only. The frontend, API, and capability matrix must not expose them as supported checks.

## Render Evidence Item

Each PDF review evidence item uses backend field names:

```json
{
  "page": 12,
  "screenshot_url": "/render-evidence/screenshot/...",
  "rule_id": "render.isolated_punctuation",
  "bbox": { "x": 0.12, "y": 0.74, "w": 0.72, "h": 0.06 },
  "text_spans": [
    { "text": "，", "bbox": { "x": 0.48, "y": 0.82, "w": 0.02, "h": 0.018 } }
  ],
  "message": "这一页底部有单独标点。",
  "severity": "warning",
  "suggested_scope": "body_paragraphs",
  "fix_mode": "manual",
  "next_action": "回到 Word 调整段落后重新导出 PDF。"
}
```

## Static TOC Boundary

- The backend derives TOC entries from the current DOCX headings and printed page numbers from the confirmed PDF.
- It writes a new `static_toc.docx`; it never overwrites the uploaded DOCX.
- It writes only when every heading maps exactly and in document order. Empty, incomplete, or ambiguous mapping exposes no download.
- The static TOC is valid only for the current DOCX content, fonts, renderer, and pagination. Any later edit requires a new PDF review.
- The generated copy removes the automatic TOC field markers but preserves the document-level field-update request for other fields, so Word/WPS does not silently replace the verified TOC page numbers.
- After download, the required next step is to export a new PDF with the same Word/WPS setup and run PDF review again.

## Coordinate System

- `bbox` is normalized to the page image.
- Every `text_spans[].bbox` uses the same normalized coordinate system and belongs to the evidence item's page.
- `x`, `y`, `w`, and `h` are numbers from `0` to `1`.
- Frontend overlays use percentage positioning.
- `bbox = null` means the frontend must show an entire-page notice and must not draw a fake precise box.
- Valid `text_spans` take precedence over the legacy `bbox`; invalid or ambiguous text matches are omitted.

## Screenshot Lifetime

- Screenshot URLs used by the frontend must survive process restart while the job artifact exists.
- If a screenshot is missing, the frontend shows a student-facing message: `页面截图已不可用 请重新复核 PDF`.

## Student Copy Ownership

- Backend owns factual fields: page, rule_id, message, severity, next_action.
- Frontend owns short display labels through `copy.js`.
- The UI must never display raw `rule_id`, `bbox`, job lifecycle words, endpoint paths, or contract terms in student-facing screens.

## PDF Evidence Viewer Boundary

- Supported: backend-provided problem list, page screenshot, optional normalized bounding-box overlay, uniquely matched text-line highlighting, whole-page fallback, and switching between returned evidence items.
- The viewer shows issue evidence pages only. It is not a full PDF reader and does not promise arbitrary page browsing, zoom controls, search, text selection, or printing.
- Not supported: arbitrary text-span highlighting inside a normal line, OCR guessing for scanned PDFs, direct PDF editing, or claiming a layout problem that the backend did not return. A standalone punctuation line may use its real character-sized line box.

## Cross-Layer Acceptance

- Empty and loading states must remain explicit until a real backend response arrives.
- A finite numeric format score of `0` is a real result, not an empty state. Missing or malformed scores keep the radar partial even when scope counts are present. A score of `100` still requires cover and PDF review.
- A partial radar does not invalidate complete per-scope facts. Scope selection remains available when the backend returns a complete scope plan with real automatic fixes.
- Format radar must not collapse `manual_review_count`, `unsupported_count`, and `unknown_count` into a false `无需处理` state.
- Uploading a new DOCX clears stale plan, result, and PDF evidence state.
- Starting a new PDF review clears the previous review before upload and polling.
- Resetting PDF review also returns evidence selection to the first issue inside `pdfReview.js`; callers do not manage its index.
- A history response must not replace a newer document or PDF flow.
- Opening historical PDF evidence invalidates older PDF polling and requires a fresh matching DOCX before another review.
- Desktop browser checks at 1440 x 900 and 1366 x 768 must cover upload, plan, apply, result, history, PDF evidence image loading, and evidence-box geometry with no console errors.
