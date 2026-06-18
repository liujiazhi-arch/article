from __future__ import annotations

import os
from typing import Any, Callable

from article_api.route_error_handlers import call_with_http_error
from article_api.schemas import UploadApplyRequest, UploadNormalizeRequest, UploadRenderReviewRequest, UploadVerifyRequest


def _upload_payload(upload: Any, *, runtime_root: str | None, utcnow_fn: Callable[[], str]) -> dict[str, Any]:
    return {
        "upload_id": upload.upload_id,
        "file_name": upload.file_name,
        "stored_path": upload.stored_path,
        "workspace_dir": upload.workspace_dir,
        "runtime_root": runtime_root,
        "size_bytes": upload.size_bytes,
        "created_at": utcnow_fn(),
    }


def register_upload_routes(
    app: Any,
    *,
    file_param: Any,
    maybe_autorun_retention: Callable[[], None],
    store_uploaded_docx_fn: Callable[..., Any],
    store_uploaded_pdf_fn: Callable[..., Any],
    upsert_upload_fn: Callable[[dict[str, Any]], None],
    list_uploads_fn: Callable[[], list[dict[str, Any]]],
    get_upload_fn: Callable[[str], dict[str, Any] | None],
    upload_view_fn: Callable[[dict[str, Any]], dict[str, Any]],
    cleanup_upload_fn: Callable[[str], dict[str, Any]],
    create_job_fn: Callable[[str, dict[str, Any]], dict[str, Any]],
    verify_upload_job_kwargs_fn: Callable[[str, UploadVerifyRequest], dict[str, Any]],
    normalize_upload_job_kwargs_fn: Callable[[str, UploadNormalizeRequest], dict[str, Any]],
    apply_upload_job_kwargs_fn: Callable[[str, UploadApplyRequest], dict[str, Any]],
    render_review_job_kwargs_fn: Callable[[str, UploadRenderReviewRequest], dict[str, Any]],
    raise_job_http_error: Callable[[Exception], None],
    utcnow_fn: Callable[[], str],
) -> None:
    @app.post("/uploads/docx", status_code=201)
    def upload_docx(file: Any = file_param, runtime_root: str | None = None) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            upload = store_uploaded_docx_fn(file, runtime_root=runtime_root)
            payload = _upload_payload(upload, runtime_root=runtime_root, utcnow_fn=utcnow_fn)
            try:
                upsert_upload_fn(payload)
            except Exception:
                stored_path = payload.get("stored_path")
                if stored_path and os.path.exists(stored_path):
                    os.unlink(stored_path)
                raise
            return upload_view_fn(payload)

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/uploads/pdf", status_code=201)
    def upload_pdf(file: Any = file_param, runtime_root: str | None = None) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            upload = store_uploaded_pdf_fn(file, runtime_root=runtime_root)
            payload = _upload_payload(upload, runtime_root=runtime_root, utcnow_fn=utcnow_fn)
            upsert_upload_fn(payload)
            return upload_view_fn(payload)

        return call_with_http_error(action, raise_job_http_error)

    @app.get("/uploads")
    def list_uploaded_docx() -> list[dict[str, Any]]:
        return call_with_http_error(
            lambda: [upload_view_fn(item) for item in list_uploads_fn()],
            raise_job_http_error,
        )

    @app.get("/uploads/{upload_id}")
    def get_uploaded_docx(upload_id: str) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            payload = get_upload_fn(upload_id)
            if payload is None:
                raise LookupError(f"Upload not found: {upload_id}")
            return upload_view_fn(payload)

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/uploads/{upload_id}/cleanup")
    def cleanup_uploaded_docx(upload_id: str) -> dict[str, Any]:
        return call_with_http_error(lambda: cleanup_upload_fn(upload_id), raise_job_http_error)

    @app.post("/uploads/{upload_id}/jobs/verify", status_code=201)
    def create_verify_job_from_upload(upload_id: str, request: UploadVerifyRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("verify", verify_upload_job_kwargs_fn(upload_id, request))

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/uploads/{upload_id}/jobs/normalize", status_code=201)
    def create_normalize_job_from_upload(upload_id: str, request: UploadNormalizeRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("normalize", normalize_upload_job_kwargs_fn(upload_id, request))

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/uploads/{upload_id}/jobs/apply", status_code=201)
    def create_apply_job_from_upload(upload_id: str, request: UploadApplyRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("apply", apply_upload_job_kwargs_fn(upload_id, request))

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/uploads/{docx_upload_id}/render-review-jobs", status_code=201)
    def create_render_review_job(docx_upload_id: str, request: UploadRenderReviewRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("render-verify", render_review_job_kwargs_fn(docx_upload_id, request))

        return call_with_http_error(action, raise_job_http_error)
