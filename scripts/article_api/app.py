from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from article_engine import apply_fix, audit_document, normalize_document, plan_document, preflight_document, render_verify_document, verify_document
from article_api import app_ops, app_uploads, storage
from article_api.profiles import build_profile_catalog
from article_api.job_queries import filter_jobs
from article_api.request_payloads import (
    apply_job_kwargs,
    apply_kwargs,
    audit_kwargs,
    normalize_job_kwargs,
    normalize_kwargs,
    plan_kwargs,
    preflight_kwargs,
    render_verify_kwargs,
    verify_job_kwargs,
    verify_kwargs,
)
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
from article_api.uploads import resolve_runtime_root, store_uploaded_docx
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


JOB_RETENTION_SECONDS_ENV = "ARTICLE_API_JOB_RETENTION_SECONDS"
UPLOAD_RETENTION_SECONDS_ENV = "ARTICLE_API_UPLOAD_RETENTION_SECONDS"
RETENTION_AUTORUN_ENV = "ARTICLE_API_RETENTION_AUTORUN"
RETENTION_AUTORUN_INTERVAL_ENV = "ARTICLE_API_RETENTION_AUTORUN_INTERVAL_SECONDS"
_RETENTION_STATE_LOCK = Lock()
_RETENTION_STATE: dict[str, Any] = {
    "last_run_at": None,
    "last_trigger": None,
    "last_result": None,
    "last_error": None,
    "last_monotonic": None,
}

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
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_optional_positive_float_env(env_name: str) -> float | None:
    raw = os.environ.get(env_name)
    if raw in (None, ""):
        return None
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{env_name} must be > 0")
    return value


def _parse_bool_env(env_name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _upload_view(payload: dict[str, Any]) -> dict[str, Any]:
    return app_uploads.upload_view(payload)


def _health_payload() -> dict[str, Any]:
    return app_ops.build_health_payload()


def _version_payload() -> dict[str, Any]:
    return app_ops.build_version_payload()


def _readiness_payload() -> dict[str, Any]:
    return app_ops.build_readiness_payload()


def _retention_defaults_payload() -> dict[str, Any]:
    return app_ops.build_retention_defaults_payload(
        parse_optional_positive_float_env=_parse_optional_positive_float_env,
        parse_bool_env=lambda env_name: _parse_bool_env(env_name, default=False),
        job_retention_seconds_env=JOB_RETENTION_SECONDS_ENV,
        upload_retention_seconds_env=UPLOAD_RETENTION_SECONDS_ENV,
        retention_autorun_env=RETENTION_AUTORUN_ENV,
        retention_autorun_interval_env=RETENTION_AUTORUN_INTERVAL_ENV,
    )


def _retention_state_payload() -> dict[str, Any]:
    with _RETENTION_STATE_LOCK:
        return {
            "last_run_at": _RETENTION_STATE["last_run_at"],
            "last_trigger": _RETENTION_STATE["last_trigger"],
            "last_result": _RETENTION_STATE["last_result"],
            "last_error": _RETENTION_STATE["last_error"],
        }


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


def _raise_job_http_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


def _cleanup_upload(upload_id: str, *, policy: str = "manual") -> dict[str, Any]:
    return app_uploads.cleanup_upload(upload_id, policy=policy, now_iso=_utcnow())


def _sweep_upload_retention(max_age_seconds: float, *, now: str, dry_run: bool) -> dict[str, Any]:
    return app_uploads.sweep_upload_retention(
        max_age_seconds,
        now=now,
        dry_run=dry_run,
        parse_timestamp=_parse_timestamp,
        cleanup_upload_fn=lambda upload_id, policy="retention": _cleanup_upload(upload_id, policy=policy),
    )


def _sweep_retention(request: RetentionSweepRequest) -> dict[str, Any]:
    return app_uploads.sweep_retention(
        request,
        utcnow_fn=_utcnow,
        sweep_job_retention_fn=sweep_job_retention,
        sweep_upload_retention_fn=_sweep_upload_retention,
    )


def _record_retention_success(*, trigger: str, result: dict[str, Any]) -> None:
    with _RETENTION_STATE_LOCK:
        app_uploads.record_retention_success(
            _RETENTION_STATE,
            trigger=trigger,
            result={**result, "triggered_at": result.get("triggered_at") or _utcnow()},
        )


def _record_retention_error(*, trigger: str, error: Exception) -> None:
    with _RETENTION_STATE_LOCK:
        app_uploads.record_retention_error(
            _RETENTION_STATE,
            trigger=trigger,
            error=error,
            now_iso=_utcnow(),
        )


def _run_default_retention_sweep(*, dry_run: bool, trigger: str) -> dict[str, Any]:
    defaults = _retention_defaults_payload()
    request = RetentionSweepRequest(
        job_max_age_seconds=defaults["job_max_age_seconds"],
        upload_max_age_seconds=defaults["upload_max_age_seconds"],
        dry_run=dry_run,
    )
    result = _sweep_retention(request)
    _record_retention_success(trigger=trigger, result=result)
    return result


def _maybe_autorun_retention() -> None:
    defaults = _retention_defaults_payload()
    with _RETENTION_STATE_LOCK:
        if not app_uploads.should_autorun_retention(defaults=defaults, retention_state=_RETENTION_STATE):
            return
    try:
        _run_default_retention_sweep(dry_run=False, trigger="autorun")
    except Exception as exc:
        _record_retention_error(trigger="autorun", error=exc)


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

    @app.get("/")
    def local_console():
        return _html_response(_local_console_html())

    @app.get("/health")
    def health() -> dict[str, Any]:
        return _health_payload()

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        try:
            return _readiness_payload()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Readiness check failed: {exc}") from exc

    @app.get("/version")
    def version() -> dict[str, Any]:
        return _version_payload()

    @app.get("/profiles")
    def profiles() -> dict[str, Any]:
        try:
            return build_profile_catalog(
                service_name=SERVICE_NAME,
                stage=SERVICE_STAGE,
                version=SERVICE_VERSION,
                api_version=API_VERSION,
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.get("/render-workflow-modes")
    def render_workflow_modes() -> dict[str, Any]:
        return build_render_workflow_modes_payload()

    @app.get("/ops/summary")
    def ops_summary() -> dict[str, Any]:
        try:
            return _ops_summary_payload()
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/ops/storage")
    def ops_storage() -> dict[str, Any]:
        try:
            return _ops_storage_payload()
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/ops/runtime")
    def ops_runtime() -> dict[str, Any]:
        try:
            return _ops_runtime_payload()
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/audit")
    def audit_endpoint(request: AuditRequest) -> dict[str, Any]:
        try:
            return audit_document(
                **audit_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/plan")
    def plan_endpoint(request: PlanRequest) -> dict[str, Any]:
        try:
            return plan_document(
                **plan_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/preflight")
    def preflight_endpoint(request: PreflightRequest) -> dict[str, Any]:
        try:
            return build_preflight_payload(
                **preflight_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/normalize")
    def normalize_endpoint(request: NormalizeRequest) -> dict[str, Any]:
        try:
            return build_normalize_payload(
                **normalize_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/render-verify")
    def render_verify_endpoint(request: RenderVerifyRequest) -> dict[str, Any]:
        try:
            return build_render_verify_payload(
                **render_verify_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/verify")
    def verify_endpoint(request: VerifyRequest) -> dict[str, Any]:
        try:
            return verify_document(
                **verify_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/apply")
    def apply_endpoint(request: ApplyRequest) -> dict[str, Any]:
        try:
            return apply_fix(
                **apply_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/jobs/verify", status_code=201)
    def create_verify_job(request: VerifyRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("verify", verify_job_kwargs(request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/normalize", status_code=201)
    def create_normalize_job(request: NormalizeJobRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("normalize", normalize_job_kwargs(request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/apply", status_code=201)
    def create_apply_job(request: ApplyRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("apply", apply_job_kwargs(request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/uploads/docx", status_code=201)
    def upload_docx(file: UploadFile = File(...), runtime_root: str | None = None) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            upload = store_uploaded_docx(file, runtime_root=runtime_root)
            payload = {
                "upload_id": upload.upload_id,
                "file_name": upload.file_name,
                "stored_path": upload.stored_path,
                "workspace_dir": upload.workspace_dir,
                "runtime_root": runtime_root,
                "size_bytes": upload.size_bytes,
                "created_at": _utcnow(),
            }
            try:
                storage.upsert_upload(payload)
            except Exception:
                stored_path = payload.get("stored_path")
                if stored_path and os.path.exists(stored_path):
                    os.unlink(stored_path)
                raise
            return _upload_view(payload)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/uploads")
    def list_uploaded_docx() -> list[dict[str, Any]]:
        try:
            return [_upload_view(item) for item in storage.list_uploads()]
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/uploads/{upload_id}")
    def get_uploaded_docx(upload_id: str) -> dict[str, Any]:
        try:
            payload = storage.get_upload(upload_id)
            if payload is None:
                raise LookupError(f"Upload not found: {upload_id}")
            return _upload_view(payload)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/uploads/{upload_id}/cleanup")
    def cleanup_uploaded_docx(upload_id: str) -> dict[str, Any]:
        try:
            return _cleanup_upload(upload_id)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/ops/retention/run-defaults")
    def run_default_retention(request: RetentionDefaultsRunRequest) -> dict[str, Any]:
        try:
            return _run_default_retention_sweep(dry_run=request.dry_run, trigger="manual-defaults")
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/ops/retention/sweep")
    def sweep_retention(request: RetentionSweepRequest) -> dict[str, Any]:
        try:
            return _sweep_retention(request)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/uploads/{upload_id}/jobs/verify", status_code=201)
    def create_verify_job_from_upload(upload_id: str, request: UploadVerifyRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("verify", _verify_upload_job_kwargs(upload_id, request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/uploads/{upload_id}/jobs/normalize", status_code=201)
    def create_normalize_job_from_upload(upload_id: str, request: UploadNormalizeRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("normalize", _normalize_upload_job_kwargs(upload_id, request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/uploads/{upload_id}/jobs/apply", status_code=201)
    def create_apply_job_from_upload(upload_id: str, request: UploadApplyRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("apply", _apply_upload_job_kwargs(upload_id, request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/jobs")
    def list_job_statuses(
        operation: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        try:
            return filter_jobs(list_jobs(), operation=operation, status=status, limit=limit)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/jobs/{job_id}")
    def get_job_status(job_id: str) -> dict[str, Any]:
        try:
            return get_job(job_id)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/jobs/{job_id}/inspect")
    def inspect_job_status(job_id: str) -> dict[str, Any]:
        try:
            return inspect_job(job_id)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/jobs/{job_id}/result")
    def get_job_output(job_id: str) -> dict[str, Any]:
        try:
            return get_job_result(job_id)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/{job_id}/cleanup")
    def cleanup_job_runtime(job_id: str) -> dict[str, Any]:
        try:
            return cleanup_job(job_id)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/{job_id}/retry", status_code=201)
    def retry_job_runtime(job_id: str) -> dict[str, Any]:
        try:
            return retry_job(job_id)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/jobs/{job_id}/artifacts/{artifact_role}/download")
    def download_job_artifact(job_id: str, artifact_role: str):
        try:
            return _build_download_response(job_id, artifact_role)
        except Exception as exc:
            _raise_job_http_error(exc)

    return app
