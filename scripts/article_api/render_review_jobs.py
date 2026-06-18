from __future__ import annotations

from typing import Any, Callable


def build_render_review_job_kwargs(
    docx_upload_id: str,
    request: Any,
    *,
    resolve_upload_fn: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    docx_upload = resolve_upload_fn(docx_upload_id)
    try:
        pdf_upload = resolve_upload_fn(request.pdf_upload_id)
    except LookupError as exc:
        raise LookupError("Render review PDF upload not found") from exc

    if not str(docx_upload.get("file_name", "")).lower().endswith(".docx"):
        raise ValueError("请选择 Word 论文文件。")
    if not str(pdf_upload.get("file_name", "")).lower().endswith(".pdf"):
        raise ValueError("请选择从 Word 或 WPS 导出的 PDF 文件。")

    return {
        "file_path": docx_upload["stored_path"],
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
        "scopes": request.scopes,
        "workflow_mode": "default_user",
        "rendered_pdf": pdf_upload["stored_path"],
        "source_display_name": docx_upload.get("file_name"),
        "pdf_display_name": pdf_upload.get("file_name"),
        "runtime_root": docx_upload.get("runtime_root") or pdf_upload.get("runtime_root"),
        "stage_input": False,
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
        "_public_request": {
            "docx_upload_id": docx_upload_id,
            "pdf_upload_id": request.pdf_upload_id,
        },
    }
