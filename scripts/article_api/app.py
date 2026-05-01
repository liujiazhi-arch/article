from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, Literal

from pydantic import BaseModel, Field

from article_engine import apply_fix, audit_document, normalize_document, plan_document, preflight_document, render_verify_document, verify_document
from article_api import storage
from article_api.profile_batch import build_profile_catalog, run_batch_workflow
from article_api.jobs import (
    cleanup_job,
    create_job,
    get_job,
    get_job_artifact,
    get_job_result,
    inspect_job,
    list_jobs,
    runtime_snapshot,
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


SERVICE_NAME = "article-api"
SERVICE_STAGE = "local-shell-alpha"
SERVICE_VERSION = "0.1.0"
API_VERSION = "v0"
JOB_RETENTION_SECONDS_ENV = "ARTICLE_API_JOB_RETENTION_SECONDS"
UPLOAD_RETENTION_SECONDS_ENV = "ARTICLE_API_UPLOAD_RETENTION_SECONDS"
RETENTION_AUTORUN_ENV = "ARTICLE_API_RETENTION_AUTORUN"
RETENTION_AUTORUN_INTERVAL_ENV = "ARTICLE_API_RETENTION_AUTORUN_INTERVAL_SECONDS"
_RUNTIME_DIR_NAMES = ("jobs", "uploads", "staging")

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


class AuditRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None


class PlanRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None


class PreflightRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None


class NormalizeRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    output_path: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None


class NormalizeJobRequest(NormalizeRequest):
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class RenderVerifyRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    output_dir: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    renderer: str = Field(default="auto", pattern="^(auto|word-pdf|artifact-tool)$")


class VerifyRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class ApplyRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    output_path: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    toc: bool = False
    renumber_headings: bool = False
    layout_rebalance: bool = False
    dry_run: bool = False
    force: bool = False
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class BatchRequest(BaseModel):
    operation: Literal["audit", "plan", "verify", "apply"]
    input_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    output_dir: str | None = None
    summary_file: str | None = None
    pattern: str = Field(default="*.docx", min_length=1)
    recursive: bool = False
    toc: bool = False
    dry_run: bool = False
    renumber_headings: bool = False
    layout_rebalance: bool = False
    force: bool = False
    fail_fast: bool = False


class BatchJobRequest(BatchRequest):
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class UploadVerifyRequest(BaseModel):
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class UploadApplyRequest(BaseModel):
    output_path: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    toc: bool = False
    renumber_headings: bool = False
    layout_rebalance: bool = False
    dry_run: bool = False
    force: bool = False
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class UploadNormalizeRequest(BaseModel):
    output_path: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class RetentionSweepRequest(BaseModel):
    job_max_age_seconds: float | None = Field(default=None, gt=0)
    upload_max_age_seconds: float | None = Field(default=None, gt=0)
    dry_run: bool = False


class RetentionDefaultsRunRequest(BaseModel):
    dry_run: bool = False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    view = dict(payload)
    view["cleanup"] = storage.get_upload_cleanup(payload["upload_id"])
    view["available"] = bool(payload.get("stored_path") and os.path.exists(payload["stored_path"]))
    return view


def _health_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
    }


def _version_payload() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
    }


def _readiness_payload() -> dict[str, Any]:
    storage.init_storage()
    state_root = str(storage.resolve_state_root())
    schema_version = storage.get_schema_version()
    runtime_root = resolve_runtime_root()
    runtime_root_writable = os.access(runtime_root, os.W_OK)
    if not runtime_root_writable:
        raise RuntimeError(f"Runtime root is not writable: {runtime_root}")
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "checks": {
            "storage": {
                "status": "ok",
                "state_root": state_root,
                "schema_version": schema_version,
            },
            "runtime_root": {
                "status": "ok",
                "path": str(runtime_root),
                "writable": runtime_root_writable,
            },
        },
    }


def _retention_defaults_payload() -> dict[str, Any]:
    return {
        "job_max_age_seconds": _parse_optional_positive_float_env(JOB_RETENTION_SECONDS_ENV),
        "upload_max_age_seconds": _parse_optional_positive_float_env(UPLOAD_RETENTION_SECONDS_ENV),
        "autorun_enabled": _parse_bool_env(RETENTION_AUTORUN_ENV, default=False),
        "autorun_interval_seconds": _parse_optional_positive_float_env(RETENTION_AUTORUN_INTERVAL_ENV) or 300.0,
    }


def _retention_state_payload() -> dict[str, Any]:
    with _RETENTION_STATE_LOCK:
        return {
            "last_run_at": _RETENTION_STATE["last_run_at"],
            "last_trigger": _RETENTION_STATE["last_trigger"],
            "last_result": _RETENTION_STATE["last_result"],
            "last_error": _RETENTION_STATE["last_error"],
        }


def _runtime_root_inventory_payload(runtime_root: str | Path | None = None) -> dict[str, Any]:
    root = resolve_runtime_root(runtime_root)
    directories: dict[str, Any] = {}
    managed_file_count = 0
    existing_directory_count = 0
    for dir_name in _RUNTIME_DIR_NAMES:
        path = root / dir_name
        file_count = sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0
        directories[dir_name] = {
            "path": str(path),
            "exists": path.exists(),
            "file_count": file_count,
        }
        managed_file_count += file_count
        if path.exists():
            existing_directory_count += 1
    return {
        "path": str(root),
        "exists": root.exists(),
        "writable": os.access(root, os.W_OK),
        "shared_with_state_root": str(root) == str(storage.resolve_state_root()),
        "managed_directory_count": existing_directory_count,
        "managed_file_count": managed_file_count,
        "directories": directories,
    }


def _storage_summary_payload(storage_view: dict[str, Any]) -> dict[str, Any]:
    present_indexes = [name for name, item in storage_view["indexes"].items() if item["present"]]
    missing_indexes = [name for name, item in storage_view["indexes"].items() if not item["present"]]
    return {
        "status": storage_view["status"],
        "state_root": storage_view["state_root"],
        "db_path": storage_view["db_path"],
        "schema_version": storage_view["schema_version"],
        "supported_schema_versions": list(storage_view.get("supported_schema_versions") or []),
        "db_size_bytes": storage_view["db_size_bytes"],
        "journal_mode": storage_view["journal_mode"],
        "integrity_check": storage_view["integrity_check"],
        "table_row_counts": {name: item["rows"] for name, item in storage_view["tables"].items()},
        "index_count": len(present_indexes),
        "present_indexes": present_indexes,
        "missing_indexes": missing_indexes,
    }


def _runtime_summary_payload(runtime_view: dict[str, Any]) -> dict[str, Any]:
    stale_heartbeat_count = runtime_view["health"]["stale_heartbeat_count"]
    pending_recovery_count = runtime_view["recovery"]["pending_recovery_count"]
    recovered_failed_count = runtime_view["recovery"]["recovered_failed_count"]
    if stale_heartbeat_count > 0:
        status = "degraded"
    elif pending_recovery_count > 0 or recovered_failed_count > 0:
        status = "warn"
    else:
        status = "ok"
    return {
        "status": status,
        "worker_model": runtime_view["worker_model"],
        "max_workers": runtime_view["executor"]["max_workers"],
        "active_future_count": runtime_view["active_future_count"],
        "unfinished_count": runtime_view["jobs"]["unfinished_count"],
        "queued_count": len(runtime_view["jobs"]["queued_job_ids"]),
        "running_count": len(runtime_view["jobs"]["running_job_ids"]),
        "finished_count": len(runtime_view["jobs"]["finished_job_ids"]),
        "recovery_strategy": runtime_view["recovery"]["strategy"],
        "recovered_failed_count": recovered_failed_count,
        "pending_recovery_count": pending_recovery_count,
        "grace_seconds": runtime_view["recovery"]["grace_seconds"],
        "stale_heartbeat_count": stale_heartbeat_count,
        "heartbeat_stale_after_seconds": runtime_view["recovery"]["heartbeat_stale_after_seconds"],
        "non_goals": list(runtime_view["non_goals"]),
    }


def _retention_summary_payload(defaults: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    configured = defaults["job_max_age_seconds"] is not None or defaults["upload_max_age_seconds"] is not None
    if state["last_error"]:
        status = "warn"
    elif configured:
        status = "configured"
    else:
        status = "not_configured"
    return {
        "status": status,
        "configured": configured,
        "autorun_enabled": bool(defaults["autorun_enabled"]),
        "job_max_age_seconds": defaults["job_max_age_seconds"],
        "upload_max_age_seconds": defaults["upload_max_age_seconds"],
        "autorun_interval_seconds": defaults["autorun_interval_seconds"],
        "last_run_at": state["last_run_at"],
        "last_trigger": state["last_trigger"],
        "last_error": state["last_error"],
    }


def _ops_status_payload(*, storage_status: str, runtime_root_writable: bool, runtime_status: str, retention_status: str) -> str:
    if storage_status != "ok" or not runtime_root_writable:
        return "degraded"
    if runtime_status != "ok" or retention_status == "warn":
        return "warn"
    return "ok"


def _ops_summary_payload() -> dict[str, Any]:
    jobs = storage.list_jobs(include_result=False)
    uploads = storage.list_uploads()
    storage_snapshot = storage.inspect_storage(include_integrity_check=False)
    runtime_view = runtime_snapshot()
    runtime_root = _runtime_root_inventory_payload()
    storage_summary = _storage_summary_payload(storage_snapshot)
    runtime_summary = _runtime_summary_payload(runtime_view)
    retention_defaults = _retention_defaults_payload()
    retention_state = _retention_state_payload()
    retention_summary = _retention_summary_payload(retention_defaults, retention_state)
    job_counts = {status: 0 for status in ("queued", "running", "succeeded", "failed")}
    for payload in jobs:
        status = payload["status"]
        if status in job_counts:
            job_counts[status] += 1
    available_count = 0
    unavailable_count = 0
    for payload in uploads:
        if payload.get("stored_path") and os.path.exists(payload["stored_path"]):
            available_count += 1
        else:
            unavailable_count += 1
    overall_status = _ops_status_payload(
        storage_status=storage_snapshot["status"],
        runtime_root_writable=runtime_root["writable"],
        runtime_status=runtime_summary["status"],
        retention_status=retention_summary["status"],
    )
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": _utcnow(),
        "status": overall_status,
        "checks": {
            "storage": {
                "status": storage_snapshot["status"],
                "integrity_check": storage_snapshot["integrity_check"],
            },
            "runtime_root": {
                "status": "ok" if runtime_root["writable"] else "degraded",
                "path": runtime_root["path"],
                "writable": runtime_root["writable"],
            },
            "runtime_worker": {
                "status": runtime_summary["status"],
                "recovered_failed_count": runtime_summary["recovered_failed_count"],
                "pending_recovery_count": runtime_summary["pending_recovery_count"],
                "stale_heartbeat_count": runtime_summary["stale_heartbeat_count"],
            },
            "retention": {
                "status": retention_summary["status"],
                "last_error": retention_summary["last_error"],
            },
        },
        "roots": {
            "state_root": storage_snapshot["state_root"],
            "runtime_root": runtime_root["path"],
            "shared_root": runtime_root["shared_with_state_root"],
        },
        "storage": {
            **storage_summary,
        },
        "jobs": {
            "total": len(jobs),
            **job_counts,
        },
        "uploads": {
            "total": len(uploads),
            "available": available_count,
            "unavailable": unavailable_count,
        },
        "cleanup": {
            "jobs_cleaned": storage_snapshot["tables"]["job_cleanup"]["rows"],
            "uploads_cleaned": storage_snapshot["tables"]["upload_cleanup"]["rows"],
        },
        "runtime": {
            **runtime_summary,
        },
        "retention": {
            "defaults": retention_defaults,
            "state": retention_state,
            "summary": retention_summary,
        },
    }


def _ops_storage_payload() -> dict[str, Any]:
    storage_view = storage.inspect_storage()
    runtime_root = _runtime_root_inventory_payload()
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": _utcnow(),
        "status": "ok" if storage_view["status"] == "ok" and runtime_root["writable"] else "degraded",
        "summary": _storage_summary_payload(storage_view),
        "storage": storage_view,
        "runtime_root": runtime_root,
    }


def _ops_runtime_payload() -> dict[str, Any]:
    runtime_view = runtime_snapshot()
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": _utcnow(),
        "status": _runtime_summary_payload(runtime_view)["status"],
        "summary": _runtime_summary_payload(runtime_view),
        "runtime": runtime_view,
    }


def _resolve_upload(upload_id: str) -> dict[str, Any]:
    payload = storage.get_upload(upload_id)
    if payload is None:
        raise LookupError(f"Upload not found: {upload_id}")
    stored_path = payload.get("stored_path")
    if not stored_path or not os.path.exists(stored_path):
        raise RuntimeError(f"Uploaded file is unavailable: {upload_id}")
    return payload


def _is_within(path: str, root: str | None) -> bool:
    if root is None:
        return False
    path_obj = os.path.abspath(os.path.expanduser(path))
    root_obj = os.path.abspath(os.path.expanduser(root))
    try:
        return os.path.commonpath([path_obj, root_obj]) == root_obj
    except ValueError:
        return False


def _resolve_upload_runtime_root(upload: dict[str, Any], requested_runtime_root: str | None) -> str | None:
    upload_runtime_root = upload.get("runtime_root")
    if requested_runtime_root and upload_runtime_root:
        requested = os.path.abspath(os.path.expanduser(requested_runtime_root))
        existing = os.path.abspath(os.path.expanduser(upload_runtime_root))
        if requested != existing:
            raise ValueError(
                f"Upload {upload['upload_id']} is bound to runtime_root {existing}, got conflicting runtime_root {requested}"
            )
    return upload_runtime_root or requested_runtime_root


def _audit_kwargs(request: AuditRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
    }


def _plan_kwargs(request: PlanRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
    }


def _preflight_kwargs(request: PreflightRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
    }


def _normalize_kwargs(request: NormalizeRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
    }


def _normalize_job_kwargs(request: NormalizeJobRequest) -> dict[str, Any]:
    payload = _normalize_kwargs(request)
    payload.update(
        {
            "stage_input": request.stage_input,
            "runtime_root": request.runtime_root,
            "max_attempts": request.max_attempts,
            "retry_delay_seconds": request.retry_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
        }
    )
    return payload


def _render_verify_kwargs(request: RenderVerifyRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "output_dir": request.output_dir,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
        "renderer": request.renderer,
    }


def _verify_kwargs(request: VerifyRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
    }


def _verify_job_kwargs(request: VerifyRequest) -> dict[str, Any]:
    payload = _verify_kwargs(request)
    payload.update(
        {
            "stage_input": request.stage_input,
            "runtime_root": request.runtime_root,
            "max_attempts": request.max_attempts,
            "retry_delay_seconds": request.retry_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
        }
    )
    return payload


def _apply_kwargs(request: ApplyRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "toc": request.toc,
        "renumber_headings": request.renumber_headings,
        "layout_rebalance": request.layout_rebalance,
        "strict_profile": request.strict_profile,
        "dry_run": request.dry_run,
        "force": request.force,
    }


def _apply_job_kwargs(request: ApplyRequest) -> dict[str, Any]:
    payload = _apply_kwargs(request)
    payload.update(
        {
            "stage_input": request.stage_input,
            "runtime_root": request.runtime_root,
            "max_attempts": request.max_attempts,
            "retry_delay_seconds": request.retry_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
        }
    )
    return payload


def _batch_kwargs(request: BatchRequest) -> dict[str, Any]:
    return {
        "operation": request.operation,
        "input_path": request.input_path,
        "profile": request.profile,
        "strict_profile": request.strict_profile,
        "scopes": request.scopes,
        "output_dir": request.output_dir,
        "summary_file": request.summary_file,
        "pattern": request.pattern,
        "recursive": request.recursive,
        "toc": request.toc,
        "dry_run": request.dry_run,
        "renumber_headings": request.renumber_headings,
        "layout_rebalance": request.layout_rebalance,
        "force": request.force,
        "fail_fast": request.fail_fast,
        "service_name": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
    }


def _batch_job_kwargs(request: BatchJobRequest) -> dict[str, Any]:
    payload = _batch_kwargs(request)
    payload.update(
        {
            "max_attempts": request.max_attempts,
            "retry_delay_seconds": request.retry_delay_seconds,
            "timeout_seconds": request.timeout_seconds,
        }
    )
    return payload


def _verify_upload_job_kwargs(upload_id: str, request: UploadVerifyRequest) -> dict[str, Any]:
    upload = _resolve_upload(upload_id)
    public_request = {
        "upload_id": upload_id,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
        "stage_input": request.stage_input,
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
    if request.runtime_root is not None:
        public_request["runtime_root"] = request.runtime_root
    payload = {
        "file_path": upload["stored_path"],
        "upload_id": upload_id,
        "source_display_name": upload["file_name"],
        "_public_request": public_request,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
        "stage_input": request.stage_input,
        "runtime_root": _resolve_upload_runtime_root(upload, request.runtime_root),
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
    return payload


def _apply_upload_job_kwargs(upload_id: str, request: UploadApplyRequest) -> dict[str, Any]:
    upload = _resolve_upload(upload_id)
    public_request = {
        "upload_id": upload_id,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "toc": request.toc,
        "renumber_headings": request.renumber_headings,
        "layout_rebalance": request.layout_rebalance,
        "strict_profile": request.strict_profile,
        "dry_run": request.dry_run,
        "force": request.force,
        "stage_input": request.stage_input,
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
    if request.runtime_root is not None:
        public_request["runtime_root"] = request.runtime_root
    payload = {
        "file_path": upload["stored_path"],
        "upload_id": upload_id,
        "source_display_name": upload["file_name"],
        "_public_request": public_request,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "toc": request.toc,
        "renumber_headings": request.renumber_headings,
        "layout_rebalance": request.layout_rebalance,
        "strict_profile": request.strict_profile,
        "dry_run": request.dry_run,
        "force": request.force,
        "stage_input": request.stage_input,
        "runtime_root": _resolve_upload_runtime_root(upload, request.runtime_root),
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
    return payload


def _normalize_upload_job_kwargs(upload_id: str, request: UploadNormalizeRequest) -> dict[str, Any]:
    upload = _resolve_upload(upload_id)
    public_request = {
        "upload_id": upload_id,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
        "stage_input": request.stage_input,
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
    if request.runtime_root is not None:
        public_request["runtime_root"] = request.runtime_root
    payload = {
        "file_path": upload["stored_path"],
        "upload_id": upload_id,
        "source_display_name": upload["file_name"],
        "_public_request": public_request,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
        "stage_input": request.stage_input,
        "runtime_root": _resolve_upload_runtime_root(upload, request.runtime_root),
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
    return payload


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
    payload = storage.get_upload(upload_id)
    if payload is None:
        raise LookupError(f"Upload not found: {upload_id}")
    blocking_job_ids = [
        item["job_id"]
        for item in storage.list_jobs(include_result=False)
        if item["status"] not in {"succeeded", "failed"}
        and (
            (item.get("runtime") or {}).get("source_upload_id") == upload_id
            or (item.get("request") or {}).get("upload_id") == upload_id
            or (item.get("resolved_request") or {}).get("upload_id") == upload_id
        )
    ]
    if blocking_job_ids:
        raise RuntimeError(
            f"Upload cleanup is blocked by active jobs: {upload_id} ({', '.join(sorted(blocking_job_ids))})"
        )

    stored_path = payload["stored_path"]
    runtime_root = str(resolve_runtime_root(payload.get("runtime_root")))
    removed_paths: list[str] = []
    missing_paths: list[str] = []
    skipped_paths: list[str] = []

    if _is_within(stored_path, runtime_root):
        if os.path.exists(stored_path):
            os.unlink(stored_path)
            removed_paths.append(stored_path)
        else:
            missing_paths.append(stored_path)
    else:
        skipped_paths.append(stored_path)

    previous_cleanup = storage.get_upload_cleanup(upload_id) or {}
    cleanup_payload = {
        "policy": policy,
        "state": "cleaned" if removed_paths else "noop",
        "cleaned_at": _utcnow(),
        "attempt_count": int(previous_cleanup.get("attempt_count") or 0) + 1,
        "removed_paths": removed_paths,
        "missing_paths": missing_paths,
        "skipped_paths": skipped_paths,
    }
    storage.upsert_upload_cleanup(upload_id, cleanup_payload)
    refreshed = storage.get_upload(upload_id)
    if refreshed is None:
        raise LookupError(f"Upload not found: {upload_id}")
    return _upload_view(refreshed)


def _sweep_upload_retention(max_age_seconds: float, *, now: str, dry_run: bool) -> dict[str, Any]:
    reference_dt = _parse_timestamp(now)
    if reference_dt is None:
        raise ValueError("Retention reference time is required")
    uploads = storage.list_uploads()
    active_upload_ids = {
        upload_id
        for item in storage.list_jobs(include_result=False)
        if item["status"] not in {"succeeded", "failed"}
        for upload_id in {
            (item.get("runtime") or {}).get("source_upload_id"),
            (item.get("request") or {}).get("upload_id"),
            (item.get("resolved_request") or {}).get("upload_id"),
        }
        if upload_id
    }
    report = {
        "policy": "retention",
        "dry_run": bool(dry_run),
        "max_age_seconds": float(max_age_seconds),
        "reference_time": now,
        "inspected_count": len(uploads),
        "eligible_count": 0,
        "cleaned_count": 0,
        "noop_count": 0,
        "blocked_count": 0,
        "skipped_count": 0,
        "items": [],
    }

    for payload in uploads:
        if storage.get_upload_cleanup(payload["upload_id"]) is not None:
            report["skipped_count"] += 1
            continue
        created_dt = _parse_timestamp(payload.get("created_at"))
        if created_dt is None:
            report["skipped_count"] += 1
            continue
        age_seconds = max((reference_dt - created_dt).total_seconds(), 0.0)
        if age_seconds < max_age_seconds:
            report["skipped_count"] += 1
            continue

        report["eligible_count"] += 1
        item = {
            "upload_id": payload["upload_id"],
            "created_at": payload.get("created_at"),
            "age_seconds": round(age_seconds, 3),
        }
        if payload["upload_id"] in active_upload_ids:
            item["action"] = "blocked"
            item["reason"] = "active_job"
            report["blocked_count"] += 1
            report["items"].append(item)
            continue
        if dry_run:
            item["action"] = "would_clean"
            report["items"].append(item)
            continue

        cleaned_payload = _cleanup_upload(payload["upload_id"], policy="retention")
        cleanup = cleaned_payload.get("cleanup") or {}
        item["action"] = "cleaned"
        item["cleanup"] = cleanup
        if cleanup.get("state") == "cleaned":
            report["cleaned_count"] += 1
        else:
            report["noop_count"] += 1
        report["items"].append(item)

    return report


def _sweep_retention(request: RetentionSweepRequest) -> dict[str, Any]:
    if request.job_max_age_seconds is None and request.upload_max_age_seconds is None:
        raise ValueError("At least one retention threshold is required")
    reference_time = _utcnow()
    response: dict[str, Any] = {
        "policy": "retention",
        "dry_run": request.dry_run,
        "triggered_at": reference_time,
    }
    if request.job_max_age_seconds is not None:
        response["job_retention"] = sweep_job_retention(
            request.job_max_age_seconds,
            now=reference_time,
            dry_run=request.dry_run,
        )
    if request.upload_max_age_seconds is not None:
        response["upload_retention"] = _sweep_upload_retention(
            request.upload_max_age_seconds,
            now=reference_time,
            dry_run=request.dry_run,
        )
    return response


def _record_retention_success(*, trigger: str, result: dict[str, Any]) -> None:
    with _RETENTION_STATE_LOCK:
        _RETENTION_STATE["last_run_at"] = result.get("triggered_at") or _utcnow()
        _RETENTION_STATE["last_trigger"] = trigger
        _RETENTION_STATE["last_result"] = result
        _RETENTION_STATE["last_error"] = None
        _RETENTION_STATE["last_monotonic"] = monotonic()


def _record_retention_error(*, trigger: str, error: Exception) -> None:
    with _RETENTION_STATE_LOCK:
        _RETENTION_STATE["last_run_at"] = _utcnow()
        _RETENTION_STATE["last_trigger"] = trigger
        _RETENTION_STATE["last_result"] = None
        _RETENTION_STATE["last_error"] = str(error)
        _RETENTION_STATE["last_monotonic"] = monotonic()


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
    if not defaults["autorun_enabled"]:
        return
    if defaults["job_max_age_seconds"] is None and defaults["upload_max_age_seconds"] is None:
        return
    interval_seconds = float(defaults["autorun_interval_seconds"])
    now_mono = monotonic()
    with _RETENTION_STATE_LOCK:
        last_mono = _RETENTION_STATE["last_monotonic"]
        if last_mono is not None and now_mono - last_mono < interval_seconds:
            return
        _RETENTION_STATE["last_monotonic"] = now_mono
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


def _coerce_jobs_limit(limit: int) -> int:
    normalized = int(limit)
    if normalized < 1:
        raise ValueError("limit must be >= 1")
    return normalized


def _filtered_job_list(
    *,
    operation: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    jobs = list_jobs()
    if operation is not None:
        jobs = [item for item in jobs if item.get("operation") == operation]
    if status is not None:
        jobs = [item for item in jobs if item.get("status") == status]
    if limit is not None:
        jobs = jobs[:_coerce_jobs_limit(limit)]
    return jobs


def _wild_doc_signals(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    toc = diagnostics.get("toc") or {}
    toc_status = str(toc.get("status") or "")
    if toc_status in {"manual_toc", "duplicate_toc", "field_only", "no_toc"}:
        signals.append(
            {
                "id": "toc_structure",
                "label": "目录结构异常",
                "count": 1,
                "status": toc_status,
            }
        )
    table_heading_candidates = diagnostics.get("table_heading_candidates") or []
    if table_heading_candidates:
        signals.append(
            {
                "id": "table_heading_candidates",
                "label": "表格内伪标题候选",
                "count": len(table_heading_candidates),
            }
        )
    style_text_conflicts = diagnostics.get("style_text_conflicts") or []
    if style_text_conflicts:
        signals.append(
            {
                "id": "style_text_conflicts",
                "label": "样式/文本层级冲突",
                "count": len(style_text_conflicts),
            }
        )
    return signals


def build_preflight_payload(
    *,
    file_path: str,
    profile_path: str = "lnu",
    strict_profile: bool | None = None,
) -> dict[str, Any]:
    payload = preflight_document(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    diagnostics = payload.get("diagnostics") or {}
    wild_doc_signals = _wild_doc_signals(diagnostics)
    summary = dict(payload.get("summary") or {})
    summary.update(
        {
            "heading_count": len(diagnostics.get("headings") or []),
            "wild_doc_detected": bool(wild_doc_signals),
            "wild_doc_signal_count": len(wild_doc_signals),
        }
    )
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": _utcnow(),
            "operation": "preflight",
            "status": "ok",
            "summary": summary,
            "wild_doc": {
                "detected": bool(wild_doc_signals),
                "signals": wild_doc_signals,
            },
        }
    )
    return payload


def build_normalize_payload(
    *,
    file_path: str,
    output_path: str | None = None,
    profile_path: str = "lnu",
    strict_profile: bool | None = None,
) -> dict[str, Any]:
    payload = normalize_document(
        file_path,
        output_path=output_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    before = payload.get("before") or {}
    after = payload.get("after") or {}
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": _utcnow(),
            "operation": "normalize",
            "status": "ok",
            "wild_doc": {
                "before": {
                    "preflight_status": before.get("preflight_status"),
                    "toc_status": before.get("toc_status"),
                    "style_conflict_count": before.get("style_conflict_count", 0),
                    "table_heading_risk_count": before.get("table_heading_risk_count", 0),
                },
                "after": {
                    "preflight_status": after.get("preflight_status"),
                    "toc_status": after.get("toc_status"),
                    "style_conflict_count": after.get("style_conflict_count", 0),
                    "table_heading_risk_count": after.get("table_heading_risk_count", 0),
                },
            },
        }
    )
    return payload


def build_render_verify_payload(
    *,
    file_path: str,
    output_dir: str | None = None,
    profile_path: str = "lnu",
    scopes: list[str] | None = None,
    strict_profile: bool | None = None,
    renderer: str = "auto",
) -> dict[str, Any]:
    payload = render_verify_document(
        file_path,
        output_dir=output_dir,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
        renderer=renderer,
    )
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": _utcnow(),
            "operation": "render-verify",
            "status": "ok",
            "summary": {
                "page_count": payload.get("page_count", 0),
                "render_engine": payload.get("render_engine"),
                "render_fallback_used": bool(payload.get("render_fallback_used")),
                "review_item_count": len(payload.get("review_items") or []),
                "manual_review_rule_count": len(payload.get("manual_review_rule_ids") or []),
                "unsupported_rule_count": len(payload.get("unsupported_rule_ids") or []),
            },
        }
    )
    return payload


def _recent_batch_jobs_payload(*, status: str | None = None, limit: int = 10) -> dict[str, Any]:
    items = _filtered_job_list(operation="batch", status=status, limit=limit)
    view_items: list[dict[str, Any]] = []
    for item in items:
        summary = item.get("summary") or {}
        runtime = item.get("runtime") or {}
        error = item.get("error") or {}
        view_items.append(
            {
                "job_id": item["job_id"],
                "status": item["status"],
                "created_at": item.get("created_at"),
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
                "batch_operation": summary.get("batch_operation"),
                "document_name": summary.get("document_name"),
                "input_path": summary.get("input_path") or runtime.get("input_path"),
                "profile_id": summary.get("profile_id"),
                "selected_scopes": summary.get("selected_scopes"),
                "total_items": summary.get("total_items"),
                "succeeded_items": summary.get("succeeded_items"),
                "failed_items": summary.get("failed_items"),
                "status_counts": summary.get("status_counts"),
                "output_dir": summary.get("output_dir") or runtime.get("output_dir"),
                "summary_file": summary.get("summary_file") or runtime.get("summary_file"),
                "retry_of_job_id": runtime.get("retry_of_job_id"),
                "error_code": summary.get("error_code") or error.get("code"),
                "result_available": bool(item.get("result_available")),
            }
        )
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": _utcnow(),
        "filters": {
            "operation": "batch",
            "status": status,
            "limit": _coerce_jobs_limit(limit),
        },
        "summary": {
            "total": len(view_items),
            "succeeded": sum(1 for item in view_items if item["status"] == "succeeded"),
            "failed": sum(1 for item in view_items if item["status"] == "failed"),
            "running": sum(1 for item in view_items if item["status"] == "running"),
            "queued": sum(1 for item in view_items if item["status"] == "queued"),
        },
        "items": view_items,
    }


def _local_console_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>论文格式本地控制台</title>
  <style>
    :root { color-scheme: light; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f5f7fa; color: #1f2937; }
    main { max-width: 1200px; margin: 0 auto; padding: 20px; }
    h1, h2 { margin: 0 0 12px; }
    p { margin: 0 0 12px; line-height: 1.5; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 16px; align-items: start; }
    .panel { background: #fff; border: 1px solid #dbe3ec; border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
    .stack { display: grid; gap: 12px; }
    .row { display: grid; gap: 6px; }
    .row.inline { grid-template-columns: 1fr 1fr; gap: 10px; }
    label { font-size: 13px; font-weight: 600; color: #334155; }
    input, select, button, textarea { font: inherit; }
    input[type="text"], select, textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; background: #fff; }
    textarea { min-height: 110px; resize: vertical; }
    .checkbox { display: flex; align-items: center; gap: 8px; font-size: 14px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    button { border: 1px solid #cbd5e1; background: #0f172a; color: #fff; border-radius: 6px; padding: 8px 12px; cursor: pointer; }
    button.secondary { background: #fff; color: #0f172a; }
    button.link { background: transparent; color: #2563eb; border: none; padding: 0; }
    .muted { color: #64748b; font-size: 13px; }
    .status { font-weight: 700; }
    .status.ok { color: #15803d; }
    .status.failed { color: #b91c1c; }
    .status.running { color: #b45309; }
    .status.queued { color: #2563eb; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
    th { color: #475569; font-weight: 600; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.5; background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 6px; overflow: auto; }
    .toolbar { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
    .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #e2e8f0; font-size: 12px; color: #334155; }
    @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main class="stack">
    <section class="panel stack">
      <div class="toolbar">
        <div>
          <h1>论文格式本地控制台</h1>
          <p class="muted">本地批量任务、最近结果、任务详情和重试入口。</p>
        </div>
        <div class="actions">
          <a href="/docs"><button type="button" class="secondary">接口文档</button></a>
          <a href="/profiles"><button type="button" class="secondary">配置列表 JSON</button></a>
          <a href="/jobs/batches/recent"><button type="button" class="secondary">最近任务 JSON</button></a>
        </div>
      </div>
      <div id="health-line" class="muted">正在读取服务状态...</div>
    </section>

    <section class="grid">
      <div class="stack">
        <section class="panel stack">
          <h2>发起批量任务</h2>
          <form id="batch-job-form" class="stack">
            <div class="row inline">
              <div class="row">
                <label for="operation">批量操作</label>
                <select id="operation" name="operation">
                  <option value="audit">批量审查</option>
                  <option value="plan">生成计划</option>
                  <option value="verify">批量复查</option>
                  <option value="apply">批量修复</option>
                </select>
              </div>
              <div class="row">
                <label for="profile">配置方案</label>
                <select id="profile" name="profile"></select>
              </div>
            </div>
            <div class="row">
              <label for="input_path">输入目录或文件路径</label>
              <input id="input_path" name="input_path" type="text" placeholder="/Users/apple/Desktop/论文目录">
            </div>
            <div class="row inline">
              <div class="row">
                <label for="scopes">修复范围（逗号分隔，可空）</label>
                <input id="scopes" name="scopes" type="text" placeholder="headings,references">
              </div>
              <div class="row">
                <label for="summary_file">汇总文件路径</label>
                <input id="summary_file" name="summary_file" type="text" placeholder="/Users/apple/Desktop/article-batch-summary.json">
              </div>
            </div>
            <div class="row">
              <label for="output_dir">输出目录（批量修复时可填）</label>
              <input id="output_dir" name="output_dir" type="text" placeholder="/Users/apple/Desktop/article-batch-output">
            </div>
            <label class="checkbox"><input id="recursive" name="recursive" type="checkbox" checked>递归扫描目录</label>
            <div class="actions">
              <button type="submit">提交批量任务</button>
              <button type="button" class="secondary" id="refresh-button">刷新最近任务</button>
            </div>
          </form>
          <div class="muted">提交后会进入统一 job 历史，可在右侧查看状态、结果和重试。</div>
        </section>

        <section class="panel stack">
          <h2>按任务编号查询</h2>
          <div class="actions">
            <input id="job-id-input" type="text" placeholder="粘贴任务编号">
            <button type="button" id="load-job-button">查看任务</button>
          </div>
        </section>
      </div>

      <div class="stack">
        <section class="panel stack">
          <div class="toolbar">
            <h2>最近批量任务</h2>
            <span class="pill" id="recent-summary">-</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>任务编号</th>
                <th>状态</th>
                <th>操作</th>
                <th>输入</th>
                <th>结果</th>
                <th>动作</th>
              </tr>
            </thead>
            <tbody id="recent-batches-body">
              <tr><td colspan="6" class="muted">正在加载...</td></tr>
            </tbody>
          </table>
        </section>

        <section class="panel stack">
          <h2>任务摘要</h2>
          <pre id="job-detail">等待选择任务...</pre>
        </section>

        <section class="panel stack">
          <h2>任务结果摘要</h2>
          <pre id="job-result">等待选择任务...</pre>
        </section>
      </div>
    </section>
  </main>

  <script>
    const state = { activeJobId: null, pollTimer: null };
    const OPERATION_LABELS = { audit: '批量审查', plan: '生成计划', verify: '批量复查', apply: '批量修复', batch: '批量任务' };
    const STATUS_LABELS = { queued: '排队中', running: '执行中', succeeded: '已完成', failed: '失败', ok: '正常' };

    async function getJson(url, options) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status}`);
      }
      return response.json();
    }

    function setBlockText(targetId, text) {
      document.getElementById(targetId).textContent = text;
    }

    function setHealthLine(message, status) {
      const el = document.getElementById('health-line');
      el.innerHTML = `<span class="status ${status || ''}">${message}</span>`;
    }

    function labelOperation(value) {
      return OPERATION_LABELS[value] || value || '-';
    }

    function labelStatus(value) {
      return STATUS_LABELS[value] || value || '-';
    }

    function summarizeJobDetail(detail) {
      const summary = detail.summary || {};
      const runtime = detail.runtime || {};
      const lines = [
        `任务编号: ${detail.job_id || '-'}`,
        `任务类型: ${labelOperation(detail.operation)}`,
        `当前状态: ${labelStatus(detail.status)}`,
        `创建时间: ${detail.created_at || '-'}`,
        `开始时间: ${detail.started_at || '-'}`,
        `完成时间: ${detail.finished_at || '-'}`,
      ];
      if (summary.batch_operation) lines.push(`批量动作: ${labelOperation(summary.batch_operation)}`);
      if (summary.document_name) lines.push(`输入名称: ${summary.document_name}`);
      if (summary.input_path || runtime.input_path) lines.push(`输入路径: ${summary.input_path || runtime.input_path}`);
      if (summary.profile_id) lines.push(`配置方案: ${summary.profile_id}`);
      if (summary.total_items != null) lines.push(`文件总数: ${summary.total_items}`);
      if (summary.succeeded_items != null) lines.push(`成功文件: ${summary.succeeded_items}`);
      if (summary.failed_items != null) lines.push(`失败文件: ${summary.failed_items}`);
      if (summary.output_dir || runtime.output_dir) lines.push(`输出目录: ${summary.output_dir || runtime.output_dir}`);
      if (summary.summary_file || runtime.summary_file) lines.push(`汇总文件: ${summary.summary_file || runtime.summary_file}`);
      if (runtime.retry_of_job_id) lines.push(`重试来源: ${runtime.retry_of_job_id}`);
      if (summary.error_code || (detail.error || {}).code) lines.push(`错误代码: ${summary.error_code || detail.error.code}`);
      if ((detail.error || {}).message) lines.push(`错误信息: ${detail.error.message}`);
      return lines.join('\\n');
    }

    function summarizeJobResult(payload) {
      const summary = payload.summary || {};
      const result = payload.result || {};
      const lines = [
        `任务编号: ${payload.job_id || '-'}`,
        `最终状态: ${labelStatus(payload.status)}`,
      ];
      if (summary.batch_operation) lines.push(`批量动作: ${labelOperation(summary.batch_operation)}`);
      if (summary.total_items != null) lines.push(`文件总数: ${summary.total_items}`);
      if (summary.succeeded_items != null) lines.push(`成功文件: ${summary.succeeded_items}`);
      if (summary.failed_items != null) lines.push(`失败文件: ${summary.failed_items}`);
      if (summary.output_dir) lines.push(`输出目录: ${summary.output_dir}`);
      if (summary.summary_file) lines.push(`汇总文件: ${summary.summary_file}`);
      if (payload.error && payload.error.message) lines.push(`错误信息: ${payload.error.message}`);
      const items = Array.isArray(result.items) ? result.items.slice(0, 12) : [];
      if (items.length) {
        lines.push('', '文件明细:');
        items.forEach((item, index) => {
          lines.push(`${index + 1}. ${item.relative_path || item.input_path || '-'}`);
          lines.push(`   状态: ${labelStatus(item.status)} / 结果: ${labelStatus(item.overall_status)}`);
          if (item.failed_rules != null) lines.push(`   未通过规则: ${item.failed_rules}`);
          if (item.output_path) lines.push(`   输出文件: ${item.output_path}`);
          if (item.error) lines.push(`   错误: ${item.error}`);
        });
        if ((result.items || []).length > items.length) {
          lines.push(`... 其余 ${result.items.length - items.length} 个文件请看汇总文件或 JSON 接口。`);
        }
      }
      return lines.join('\\n');
    }

    async function loadProfiles() {
      const payload = await getJson('/profiles');
      const select = document.getElementById('profile');
      select.innerHTML = '';
      for (const item of payload.profiles) {
        const scenarioLabels = Array.isArray(item.support_scenarios)
          ? item.support_scenarios.map((scenario) => scenario.label).filter(Boolean)
          : [];
        const supportBadge = item.support_level_label || '';
        const option = document.createElement('option');
        option.value = item.id === 'cn-common' ? 'cn-common' : (item.aliases[0] || item.id);
        option.textContent = [
          item.id,
          item.school || '',
          scenarioLabels.join(' / '),
          supportBadge,
        ].filter(Boolean).join(' · ');
        if (option.value === 'lnu') option.selected = true;
        select.appendChild(option);
      }
    }

    function clearPolling() {
      if (state.pollTimer) {
        clearTimeout(state.pollTimer);
        state.pollTimer = null;
      }
    }

    async function loadJob(jobId, poll = false) {
      clearPolling();
      state.activeJobId = jobId;
      document.getElementById('job-id-input').value = jobId;
      try {
        const detail = await getJson(`/jobs/${jobId}`);
        setBlockText('job-detail', summarizeJobDetail(detail));
        if (detail.status === 'queued' || detail.status === 'running') {
          setBlockText('job-result', `任务仍在执行中...\\n任务编号: ${jobId}\\n当前状态: ${labelStatus(detail.status)}`);
          if (poll) {
            state.pollTimer = setTimeout(() => loadJob(jobId, true), 1500);
          }
          return;
        }
        const result = await getJson(`/jobs/${jobId}/result`);
        setBlockText('job-result', summarizeJobResult(result));
        await refreshRecentBatches();
      } catch (error) {
        setBlockText('job-result', `读取任务失败\\n${String(error)}`);
      }
    }

    async function retryJob(jobId) {
      try {
        const payload = await getJson(`/jobs/${jobId}/retry`, { method: 'POST' });
        await refreshRecentBatches();
        await loadJob(payload.job_id, true);
      } catch (error) {
        setBlockText('job-result', `重试任务失败\\n${String(error)}`);
      }
    }

    async function refreshRecentBatches() {
      const payload = await getJson('/jobs/batches/recent?limit=12');
      document.getElementById('recent-summary').textContent = `共 ${payload.summary.total} 个 / 成功 ${payload.summary.succeeded} / 失败 ${payload.summary.failed}`;
      const body = document.getElementById('recent-batches-body');
      body.innerHTML = '';
      if (!payload.items.length) {
        body.innerHTML = '<tr><td colspan="6" class="muted">暂无批量任务。</td></tr>';
        return;
      }
      for (const item of payload.items) {
        const tr = document.createElement('tr');
        const retryButton = item.status === 'failed'
          ? `<button type="button" class="link" data-retry="${item.job_id}">重试</button>`
          : '';
        tr.innerHTML = `
          <td><button type="button" class="link" data-job="${item.job_id}">${item.job_id.slice(0, 10)}</button></td>
          <td><span class="status ${item.status}">${labelStatus(item.status)}</span></td>
          <td>${labelOperation(item.batch_operation)}</td>
          <td>${item.document_name || '-'}</td>
          <td>成功 ${item.succeeded_items ?? '-'} / 失败 ${item.failed_items ?? '-'}</td>
        `;
        body.appendChild(tr);
        if (retryButton) {
          const actionTd = document.createElement('td');
          actionTd.innerHTML = retryButton;
          tr.appendChild(actionTd);
        } else {
          const actionTd = document.createElement('td');
          actionTd.textContent = '';
          tr.appendChild(actionTd);
        }
      }
      body.querySelectorAll('[data-job]').forEach((button) => {
        button.addEventListener('click', () => loadJob(button.dataset.job, false));
      });
      body.querySelectorAll('[data-retry]').forEach((button) => {
        button.addEventListener('click', () => retryJob(button.dataset.retry));
      });
    }

    async function refreshOverview() {
      const health = await getJson('/health');
      setHealthLine(`服务正常: ${health.service} ${health.version}`, 'ok');
      await refreshRecentBatches();
    }

    async function submitBatchJob(event) {
      event.preventDefault();
      const payload = {
        operation: document.getElementById('operation').value,
        input_path: document.getElementById('input_path').value.trim(),
        profile: document.getElementById('profile').value,
        recursive: document.getElementById('recursive').checked,
      };
      const scopesText = document.getElementById('scopes').value.trim();
      const summaryFile = document.getElementById('summary_file').value.trim();
      const outputDir = document.getElementById('output_dir').value.trim();
      if (scopesText) payload.scopes = scopesText.split(',').map((item) => item.trim()).filter(Boolean);
      if (summaryFile) payload.summary_file = summaryFile;
      if (outputDir) payload.output_dir = outputDir;
      try {
        const created = await getJson('/jobs/batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        setBlockText('job-detail', `批量任务已创建\\n任务编号: ${created.job_id}\\n当前状态: ${labelStatus(created.status)}`);
        setBlockText('job-result', `批量任务已创建，正在轮询结果...\\n任务编号: ${created.job_id}`);
        await refreshRecentBatches();
        await loadJob(created.job_id, true);
      } catch (error) {
        setBlockText('job-result', `提交批量任务失败\\n${String(error)}`);
      }
    }

    document.getElementById('batch-job-form').addEventListener('submit', submitBatchJob);
    document.getElementById('refresh-button').addEventListener('click', refreshOverview);
    document.getElementById('load-job-button').addEventListener('click', () => {
      const jobId = document.getElementById('job-id-input').value.trim();
      if (jobId) loadJob(jobId, false);
    });

    Promise.all([loadProfiles(), refreshOverview()]).catch((error) => {
      setHealthLine(`加载失败: ${error}`, 'failed');
      setBlockText('job-result', `加载失败\\n${String(error)}`);
    });
  </script>
</body>
</html>"""


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
                **_audit_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/plan")
    def plan_endpoint(request: PlanRequest) -> dict[str, Any]:
        try:
            return plan_document(
                **_plan_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/preflight")
    def preflight_endpoint(request: PreflightRequest) -> dict[str, Any]:
        try:
            return build_preflight_payload(
                **_preflight_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/normalize")
    def normalize_endpoint(request: NormalizeRequest) -> dict[str, Any]:
        try:
            return build_normalize_payload(
                **_normalize_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/render-verify")
    def render_verify_endpoint(request: RenderVerifyRequest) -> dict[str, Any]:
        try:
            return build_render_verify_payload(
                **_render_verify_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/verify")
    def verify_endpoint(request: VerifyRequest) -> dict[str, Any]:
        try:
            return verify_document(
                **_verify_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/apply")
    def apply_endpoint(request: ApplyRequest) -> dict[str, Any]:
        try:
            return apply_fix(
                **_apply_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/batch")
    def batch_endpoint(request: BatchRequest) -> dict[str, Any]:
        try:
            return run_batch_workflow(
                **_batch_kwargs(request),
            )
        except Exception as exc:
            _raise_sync_http_error(exc)

    @app.post("/jobs/verify", status_code=201)
    def create_verify_job(request: VerifyRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("verify", _verify_job_kwargs(request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/normalize", status_code=201)
    def create_normalize_job(request: NormalizeJobRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("normalize", _normalize_job_kwargs(request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/apply", status_code=201)
    def create_apply_job(request: ApplyRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("apply", _apply_job_kwargs(request))
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.post("/jobs/batch", status_code=201)
    def create_batch_job(request: BatchJobRequest) -> dict[str, Any]:
        try:
            _maybe_autorun_retention()
            return create_job("batch", _batch_job_kwargs(request))
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
            return _filtered_job_list(operation=operation, status=status, limit=limit)
        except Exception as exc:
            _raise_job_http_error(exc)

    @app.get("/jobs/batches/recent")
    def recent_batch_jobs(
        status: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        try:
            return _recent_batch_jobs_payload(status=status, limit=limit)
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
