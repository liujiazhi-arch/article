from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any

from article_engine import apply_fix, audit_document, normalize_document, plan_document, preflight_document, render_verify_document, verify_document
from article_api import (
    app_ops,
    app_retention,
    app_uploads,
    errors as api_errors,
    routes_feedback,
    routes_job_submit,
    routes_jobs,
    routes_metadata,
    routes_ops,
    routes_sync,
    routes_uploads,
    storage,
)
from article_api.profiles import build_profile_catalog
from article_api.schemas import (
    ApplyRequest,
    AuditRequest,
    NormalizeJobRequest,
    NormalizeRequest,
    PlanRequest,
    PreflightRequest,
    RenderVerifyRequest,
    RetentionDefaultsRunRequest,
    RetentionSweepRequest,
    UploadApplyRequest,
    UploadNormalizeRequest,
    UploadVerifyRequest,
    VerifyRequest,
)
from article_api.response_payloads import (
    API_VERSION,
    RENDER_WORKFLOW_MODES,
    SERVICE_NAME,
    SERVICE_STAGE,
    SERVICE_VERSION,
    build_normalize_payload as _build_normalize_payload,
    build_preflight_payload as _build_preflight_payload,
    build_render_verify_payload as _build_render_verify_payload,
    build_render_workflow_modes_payload,
    utcnow,
)
from article_api.upload_job_payloads import (
    build_apply_upload_job_kwargs,
    build_normalize_upload_job_kwargs,
    build_verify_upload_job_kwargs,
    resolve_upload,
    resolve_upload_runtime_root,
)
from article_api.jobs import (
    cleanup_job,
    create_job,
    get_job,
    get_job_artifact,
    get_job_result,
    inspect_job,
    list_jobs,
    retry_job,
    sweep_job_retention,
)
from article_api.uploads import resolve_runtime_root, store_uploaded_docx, store_uploaded_pdf
try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import FileResponse, HTMLResponse
except ImportError as exc:  # pragma: no cover
    FastAPI = None
    HTTPException = None
    UploadFile = Any
    FileResponse = None
    HTMLResponse = None

    def File(*_args, **_kwargs):
        return None

    _FASTAPI_IMPORT_ERROR = exc
else:
    _FASTAPI_IMPORT_ERROR = None


JOB_RETENTION_SECONDS_ENV = app_retention.JOB_RETENTION_SECONDS_ENV
UPLOAD_RETENTION_SECONDS_ENV = app_retention.UPLOAD_RETENTION_SECONDS_ENV
RETENTION_AUTORUN_ENV = app_retention.RETENTION_AUTORUN_ENV
RETENTION_AUTORUN_INTERVAL_ENV = app_retention.RETENTION_AUTORUN_INTERVAL_ENV
_RETENTION_STATE_LOCK = app_retention.RETENTION_STATE_LOCK
_RETENTION_STATE = app_retention.RETENTION_STATE

class _InlineHTMLResponse:
    def __init__(self, content: str, *, status_code: int = 200):
        self.status_code = status_code
        self.media_type = "text/html; charset=utf-8"
        self.body = content.encode("utf-8")


def _html_response(content: str):
    if HTMLResponse is not None:
        return HTMLResponse(content)
    return _InlineHTMLResponse(content)


def _utcnow() -> str:
    return utcnow()


def _parse_timestamp(value: str | None) -> datetime | None:
    return app_retention.parse_timestamp(value)


def _parse_optional_positive_float_env(env_name: str) -> float | None:
    return app_retention.parse_optional_positive_float_env(env_name)


def _parse_bool_env(env_name: str, *, default: bool = False) -> bool:
    return app_retention.parse_bool_env(env_name, default=default)


def _upload_view(payload: dict[str, Any]) -> dict[str, Any]:
    return app_uploads.upload_view(payload)


def _health_payload() -> dict[str, Any]:
    return app_ops.build_health_payload()


def _version_payload() -> dict[str, Any]:
    return app_ops.build_version_payload()


def _latest_update_payload() -> dict[str, Any]:
    return app_ops.build_latest_update_payload()


def _readiness_payload() -> dict[str, Any]:
    return app_ops.build_readiness_payload()


def _retention_defaults_payload() -> dict[str, Any]:
    return app_retention.retention_defaults_payload()


def _retention_state_payload() -> dict[str, Any]:
    return app_retention.retention_state_payload()


def _ops_summary_payload() -> dict[str, Any]:
    return app_ops.build_ops_summary_payload(
        retention_defaults=_retention_defaults_payload(),
        retention_state=_retention_state_payload(),
    )


def _ops_storage_payload() -> dict[str, Any]:
    return app_ops.build_ops_storage_payload()


def _ops_runtime_payload() -> dict[str, Any]:
    return app_ops.build_ops_runtime_payload()


def _is_within(path: str, root: str | None) -> bool:
    return app_uploads.is_within(path, root)


def _verify_upload_job_kwargs(upload_id: str, request: UploadVerifyRequest) -> dict[str, Any]:
    return build_verify_upload_job_kwargs(upload_id, request, resolve_upload_fn=resolve_upload)


def _apply_upload_job_kwargs(upload_id: str, request: UploadApplyRequest) -> dict[str, Any]:
    return build_apply_upload_job_kwargs(upload_id, request, resolve_upload_fn=resolve_upload)


def _normalize_upload_job_kwargs(upload_id: str, request: UploadNormalizeRequest) -> dict[str, Any]:
    return build_normalize_upload_job_kwargs(upload_id, request, resolve_upload_fn=resolve_upload)


def _raise_sync_http_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        payload = api_errors.value_error_payload(exc)
        raise HTTPException(status_code=payload["http_status"], detail=payload) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


def _raise_job_http_error(exc: Exception) -> None:
    upload_payload = api_errors.upload_error_payload(exc)
    if upload_payload is not None:
        raise HTTPException(status_code=upload_payload["http_status"], detail=upload_payload) from exc
    artifact_payload = api_errors.artifact_download_error_payload(exc)
    if artifact_payload is not None:
        raise HTTPException(status_code=artifact_payload["http_status"], detail=artifact_payload) from exc
    if isinstance(exc, ValueError):
        payload = api_errors.value_error_payload(exc)
        raise HTTPException(status_code=payload["http_status"], detail=payload) from exc
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


def _cleanup_upload(upload_id: str, *, policy: str = "manual") -> dict[str, Any]:
    return app_retention.cleanup_upload(upload_id, policy=policy, utcnow_fn=_utcnow)


def _sweep_upload_retention(max_age_seconds: float, *, now: str, dry_run: bool) -> dict[str, Any]:
    return app_retention.sweep_upload_retention(
        max_age_seconds,
        now=now,
        dry_run=dry_run,
        utcnow_fn=_utcnow,
        parse_timestamp_fn=_parse_timestamp,
        cleanup_upload_fn=lambda upload_id, policy="retention": _cleanup_upload(upload_id, policy=policy),
    )


def _sweep_retention(request: RetentionSweepRequest) -> dict[str, Any]:
    return app_retention.sweep_retention(
        request,
        utcnow_fn=_utcnow,
        sweep_job_retention_fn=sweep_job_retention,
        sweep_upload_retention_fn=_sweep_upload_retention,
    )


def _record_retention_success(*, trigger: str, result: dict[str, Any]) -> None:
    app_retention.record_retention_success(trigger=trigger, result=result, utcnow_fn=_utcnow)


def _record_retention_error(*, trigger: str, error: Exception) -> None:
    app_retention.record_retention_error(trigger=trigger, error=error, utcnow_fn=_utcnow)


def _run_default_retention_sweep(*, dry_run: bool, trigger: str) -> dict[str, Any]:
    return app_retention.run_default_retention_sweep(
        dry_run=dry_run,
        trigger=trigger,
        utcnow_fn=_utcnow,
        retention_defaults_payload_fn=_retention_defaults_payload,
        sweep_retention_fn=_sweep_retention,
        record_retention_success_fn=_record_retention_success,
    )


def _maybe_autorun_retention() -> None:
    app_retention.maybe_autorun_retention(
        utcnow_fn=_utcnow,
        retention_defaults_payload_fn=_retention_defaults_payload,
        run_default_retention_sweep_fn=_run_default_retention_sweep,
        record_retention_error_fn=_record_retention_error,
    )


def _build_download_response(job_id: str, artifact_role: str):
    artifact = get_job_artifact(job_id, artifact_role)
    artifact_path = artifact.get("path")
    artifact_name = artifact.get("download_name") or os.path.basename(artifact_path or "")
    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if not artifact_path:
        raise LookupError(f"Artifact not found for job {job_id}: {artifact_role}")
    if not os.path.exists(artifact_path):
        raise RuntimeError(f"Artifact file is unavailable for job {job_id}: {artifact_role}")
    if os.path.isdir(artifact_path):
        raise RuntimeError(f"Artifact download is only available for files: {job_id}:{artifact_role}")
    if str(artifact_path).lower().endswith(".json"):
        media_type = "application/json"
    elif str(artifact_path).lower().endswith(".md"):
        media_type = "text/markdown; charset=utf-8"
    if FileResponse is None:  # pragma: no cover
        return {
            "job_id": job_id,
            "artifact_role": artifact_role,
            "path": artifact_path,
            "filename": artifact_name,
            "media_type": media_type,
        }
    return FileResponse(
        artifact_path,
        filename=artifact_name,
        media_type=media_type,
    )


def _build_feedback_download_response():
    return routes_feedback.build_feedback_download_response(file_response_cls=FileResponse)


def build_preflight_payload(**kwargs) -> dict[str, Any]:
    return _build_preflight_payload(
        **kwargs,
        preflight_fn=preflight_document,
    )


def build_normalize_payload(**kwargs) -> dict[str, Any]:
    return _build_normalize_payload(
        **kwargs,
        normalize_fn=normalize_document,
    )


def build_render_verify_payload(**kwargs) -> dict[str, Any]:
    return _build_render_verify_payload(
        **kwargs,
        render_verify_fn=render_verify_document,
    )


def _legacy_local_console_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>论文格式本地控制台</title>
</head>
<body>
  <main>
    <h1>论文格式本地控制台</h1>
    <section>
      <h2>单篇论文处理</h2>
      <p>选择 Word 论文后，可以使用审查、修复、规范化和 Word 版式复核。</p>
    </section>
    <section>
      <h2>历史与排障</h2>
      <p>任务历史、备份恢复和维护接口仍通过 JSON API 提供。</p>
    </section>
  </main>
</body>
</html>"""


def _local_console_html() -> str:
    html_path = Path(__file__).with_name("local_console.html")
    try:
        return html_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _legacy_local_console_html()


def fastapi_available() -> bool:
    return FastAPI is not None


def _dependency_error_message() -> str:
    detail = str(_FASTAPI_IMPORT_ERROR) if _FASTAPI_IMPORT_ERROR else "fastapi is not installed"
    return f"FastAPI API prototype is unavailable: {detail}. Install the optional 'api' dependencies first."


def create_app():
    if FastAPI is None:
        raise RuntimeError(_dependency_error_message())

    app = FastAPI(
        title="Article API",
        version=SERVICE_VERSION,
        description="Local API prototype for Article thesis audit and planning.",
    )

    routes_metadata.register_metadata_routes(
        app,
        file_response_cls=FileResponse,
        http_exception_cls=HTTPException,
        html_response_fn=_html_response,
        local_console_html_fn=_local_console_html,
        health_payload_fn=_health_payload,
        readiness_payload_fn=_readiness_payload,
        version_payload_fn=_version_payload,
        latest_update_payload_fn=_latest_update_payload,
        render_workflow_modes_payload_fn=build_render_workflow_modes_payload,
        profile_catalog_fn=lambda: build_profile_catalog(
            service_name=SERVICE_NAME,
            stage=SERVICE_STAGE,
            version=SERVICE_VERSION,
            api_version=API_VERSION,
        ),
        raise_sync_http_error=lambda exc: _raise_sync_http_error(exc),
        package_file=__file__,
    )

    routes_ops.register_ops_routes(
        app,
        ops_summary_payload_fn=lambda: _ops_summary_payload(),
        ops_storage_payload_fn=lambda: _ops_storage_payload(),
        ops_runtime_payload_fn=lambda: _ops_runtime_payload(),
        run_default_retention_sweep_fn=lambda **kwargs: _run_default_retention_sweep(**kwargs),
        sweep_retention_fn=lambda request: _sweep_retention(request),
        raise_job_http_error=lambda exc: _raise_job_http_error(exc),
    )

    routes_sync.register_sync_engine_routes(
        app,
        audit_document_fn=lambda **kwargs: audit_document(**kwargs),
        plan_document_fn=lambda **kwargs: plan_document(**kwargs),
        build_preflight_payload_fn=lambda **kwargs: build_preflight_payload(**kwargs),
        build_normalize_payload_fn=lambda **kwargs: build_normalize_payload(**kwargs),
        build_render_verify_payload_fn=lambda **kwargs: build_render_verify_payload(**kwargs),
        verify_document_fn=lambda **kwargs: verify_document(**kwargs),
        apply_fix_fn=lambda **kwargs: apply_fix(**kwargs),
        raise_sync_http_error=lambda exc: _raise_sync_http_error(exc),
    )

    routes_job_submit.register_job_submit_routes(
        app,
        create_job_fn=lambda operation, payload: create_job(operation, payload),
        maybe_autorun_retention=lambda: _maybe_autorun_retention(),
        raise_job_http_error=lambda exc: _raise_job_http_error(exc),
    )

    routes_uploads.register_upload_routes(
        app,
        file_param=File(...),
        maybe_autorun_retention=lambda: _maybe_autorun_retention(),
        store_uploaded_docx_fn=lambda *args, **kwargs: store_uploaded_docx(*args, **kwargs),
        store_uploaded_pdf_fn=lambda *args, **kwargs: store_uploaded_pdf(*args, **kwargs),
        upsert_upload_fn=lambda payload: storage.upsert_upload(payload),
        list_uploads_fn=lambda: storage.list_uploads(),
        get_upload_fn=lambda upload_id: storage.get_upload(upload_id),
        upload_view_fn=lambda payload: _upload_view(payload),
        cleanup_upload_fn=lambda upload_id: _cleanup_upload(upload_id),
        create_job_fn=lambda operation, payload: create_job(operation, payload),
        verify_upload_job_kwargs_fn=lambda upload_id, request: _verify_upload_job_kwargs(upload_id, request),
        normalize_upload_job_kwargs_fn=lambda upload_id, request: _normalize_upload_job_kwargs(upload_id, request),
        apply_upload_job_kwargs_fn=lambda upload_id, request: _apply_upload_job_kwargs(upload_id, request),
        raise_job_http_error=lambda exc: _raise_job_http_error(exc),
        utcnow_fn=_utcnow,
    )

    routes_jobs.register_job_status_routes(
        app,
        list_jobs_fn=lambda: list_jobs(),
        get_job_fn=lambda job_id: get_job(job_id),
        inspect_job_fn=lambda job_id: inspect_job(job_id),
        get_job_result_fn=lambda job_id: get_job_result(job_id),
        cleanup_job_fn=lambda job_id: cleanup_job(job_id),
        retry_job_fn=lambda job_id: retry_job(job_id),
        build_download_response_fn=lambda job_id, artifact_role: _build_download_response(job_id, artifact_role),
        raise_job_http_error=lambda exc: _raise_job_http_error(exc),
    )

    routes_feedback.register_feedback_routes(
        app,
        build_feedback_download_response_fn=lambda: _build_feedback_download_response(),
        raise_job_http_error=lambda exc: _raise_job_http_error(exc),
    )

    return app
