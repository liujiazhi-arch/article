# Frontend Backend Contract

Date: 2026-07-12

## Frontend Entry

- `GET /` returns the student frontend.
- `GET /static/{path}` returns frontend assets.

## Uploads

- `POST /uploads/docx`
  - Form field: `file`
  - Returns: `upload_id`, `file_name`, `stored_path`, `workspace_dir`, `runtime_root`, `size_bytes`, `created_at`

- `POST /uploads/pdf`
  - Form field: `file`
  - Returns: `upload_id`, `file_name`, `stored_path`, `workspace_dir`, `runtime_root`, `size_bytes`, `created_at`

## Jobs

- `POST /plan`
  - Body: `{ "file_path": "..." }`
  - Returns the backend format score, summary, and per-scope counts used by the workbench.

- `POST /uploads/{upload_id}/jobs/apply`
  - Body: `{ "scopes": ["..."] }`
  - Creates a DOCX repair job from a DOCX upload.

- `POST /uploads/{docx_upload_id}/render-review-jobs`
  - Body: `{ "pdf_upload_id": "...", "pdf_matches_docx_confirmed": true, "generate_static_toc": true }`
  - `pdf_matches_docx_confirmed` is true only after the user confirms the PDF came from the current DOCX.
  - Upload-based review defaults `generate_static_toc` to true. The generic render API and CLI keep it false unless explicitly requested.
  - Creates a background `render-verify` job.
  - Resolves `file_path` from the DOCX upload.
  - Resolves `rendered_pdf` from the PDF upload.

- `GET /jobs/{job_id}`
  - Returns `status`, `summary`, `artifacts`, and student-safe job metadata.

- `GET /jobs/{job_id}/result`
  - Returns the final operation result after success.

- `GET /jobs?limit={count}`
  - Returns local job history with student-safe display metadata.

- `GET /jobs/{job_id}/artifacts/{role}/download`
  - Downloads an available `output`, `report`, or `toc-output` artifact from a completed job.

## Feature Support Matrix

| Student-facing feature | Backend source | Frontend rule |
| --- | --- | --- |
| Format radar | `POST /plan` -> `score` | Show the backend score directly. Do not recompute it from findings. |
| Thesis structure index | `POST /plan` -> `scopes[].failed_count` | Sum only the scope IDs declared by each structure group. These are issue counts, not paragraph counts. |
| Repair scope selection | `POST /plan` -> per-scope autofixable, manual-review, and unsupported counts | Enable only scopes with real automatic fixes. Keep mixed scopes selected while clearly marking that confirmation is still required. |
| Processing flow | Upload response, plan response, job status, result availability | Mark upload, plan, apply, verify, and download stages from completed backend events. Do not advance stages on a timer or static markup. |
| Result status | Apply result `summary`, `readiness`, and `business_status` | Distinguish generated, needs-fix, and needs-confirmation states. Do not call an unchecked result compliant. |
| Rule spectrum | Apply result `verification.scopes[]` | Render one labelled item per returned scope. `failed_count = 0` is pass; a positive count is shown as the real remaining issue count. |
| Downloads | Job `artifacts[]` and artifact download endpoint | Enable only artifacts marked available. Keep the original file untouched. |
| PDF issue evidence | Render-review result `summary` and `evidence_items[]` | Show only backend-provided page images, page numbers, messages, and optional boxes. Never invent a page or precise location. |
| Static TOC finalization | Render-review result `toc_finalization` and the `toc-output` artifact | Offer the download only after complete heading-to-page mapping against a confirmed same-version PDF. Then ask the student to export and review the PDF again. |
| History | Job list and job result endpoints | A completed apply job restores its result. A completed render-review job restores its document name, PDF name, completion state, and evidence. Historical PDF evidence is view-only until the student uploads the matching DOCX again. |

## Render Evidence Item

Each PDF review evidence item uses backend field names:

```json
{
  "page": 12,
  "screenshot_url": "/render-evidence/screenshot/...",
  "rule_id": "render.isolated_punctuation",
  "bbox": { "x": 0.12, "y": 0.74, "w": 0.72, "h": 0.06 },
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
- `x`, `y`, `w`, and `h` are numbers from `0` to `1`.
- Frontend overlays use percentage positioning.
- `bbox = null` means the frontend must show an entire-page notice and must not draw a fake precise box.

## Screenshot Lifetime

- Screenshot URLs used by the frontend must survive process restart while the job artifact exists.
- If a screenshot is missing, the frontend shows a student-facing message: `页面截图已不可用 请重新复核 PDF`.

## Student Copy Ownership

- Backend owns factual fields: page, rule_id, message, severity, next_action.
- Frontend owns short display labels through `copy.js`.
- The UI must never display raw `rule_id`, `bbox`, job lifecycle words, endpoint paths, or contract terms in student-facing screens.

## PDF Evidence Viewer Boundary

- Supported: backend-provided problem list, page screenshot, optional normalized bounding-box overlay, whole-page fallback, and switching between returned evidence items.
- The viewer shows issue evidence pages only. It is not a full PDF reader and does not promise arbitrary page browsing, zoom controls, search, text selection, or printing.
- Not supported: text-span highlighting, single-character highlighting, direct PDF editing, or claiming a layout problem that the backend did not return.

## Cross-Layer Acceptance

- Empty and loading states must remain explicit until a real backend response arrives.
- Uploading a new DOCX clears stale plan, result, and PDF evidence state.
- Starting a new PDF review clears the previous review before upload and polling.
- A history response must not replace a newer document or PDF flow.
- Opening historical PDF evidence invalidates older PDF polling and requires a fresh matching DOCX before another review.
- Desktop and 390 px browser checks must cover upload, plan, apply, result, history, PDF evidence image loading, and evidence-box geometry with no console errors.
