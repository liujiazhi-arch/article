# Frontend Backend Contract

Date: 2026-06-16

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

- `POST /uploads/{upload_id}/jobs/apply`
  - Creates a DOCX repair job from a DOCX upload.

- `POST /uploads/{docx_upload_id}/render-review-jobs`
  - Body: `{ "pdf_upload_id": "..." }`
  - Creates a background `render-verify` job.
  - Resolves `file_path` from the DOCX upload.
  - Resolves `rendered_pdf` from the PDF upload.

- `GET /jobs/{job_id}`
  - Returns `status`, `summary`, `artifacts`, and student-safe job metadata.

- `GET /jobs/{job_id}/result`
  - Returns the final operation result after success.

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
  "next_action": "回到 Word 调整段落后重新导出 PDF。"
}
```

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

## PDF Review V1 Boundary

- Supported: page screenshot, problem list, bbox overlay, page fallback, zoom, previous/next issue.
- Not supported: text-span highlighting, single-character highlighting, direct PDF editing.
