from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from pydantic import BaseModel, Field

from article_engine import apply_fix, audit_document, normalize_document, plan_document, preflight_document, render_verify_document, verify_document
from article_api import storage
from article_api.profiles import build_profile_catalog
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

RENDER_WORKFLOW_MODES: tuple[dict[str, Any], ...] = (
    {
        "id": "default_user",
        "title": "默认用户模式",
        "subtitle": "用户用 Word/WPS 导出 PDF，工具只分析真实 PDF。",
        "stability": "high",
        "button_label": "用已导出的 PDF 复核",
        "requires_manual_pdf": True,
        "uses_automation": False,
        "creates_candidate_docx": False,
        "backend_action": "render-verify with rendered_pdf or page_images_dir",
        "why": "Word/WPS 自动化容易被恢复弹窗、权限和超时打断；手动 PDF 最适合普通用户。",
        "best_for": "普通用户、最终提交前复核、多人使用场景。",
    },
    {
        "id": "advanced_word",
        "title": "高级模式",
        "subtitle": "尝试连接 Microsoft Word 自动导出 PDF。",
        "stability": "medium",
        "button_label": "尝试 Word 自动复核",
        "requires_manual_pdf": False,
        "uses_automation": True,
        "creates_candidate_docx": False,
        "backend_action": "render-verify with renderer=word-pdf",
        "why": "适合本机 Word 状态稳定时快速复核；失败时应改用默认用户模式。",
        "best_for": "开发者、本机调试、已确认 Word 不会弹恢复框的环境。",
    },
    {
        "id": "agent_candidate",
        "title": "Agent 候选稿模式",
        "subtitle": "复核后排障工具，只在 PDF 版式复核发现可行动问题后使用。",
        "stability": "assisted",
        "button_label": "生成候选修复稿",
        "requires_manual_pdf": False,
        "uses_automation": False,
        "creates_candidate_docx": True,
        "backend_action": "apply candidate with headings + figures_tables + layout_rebalance",
        "why": "它不是常规修复模式；渲染层问题需要先看 Word/WPS PDF 证据，候选稿不能直接覆盖原文，也不能跳过再次 PDF 复核。",
        "best_for": "PDF 复核已经确认的复杂图表挤页、标题孤页、大块空白等排版排障。",
    },
)


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
    renderer: str = Field(default="auto", pattern="^(auto|word-pdf)$")
    rendered_pdf: str | None = None
    page_images_dir: str | None = None
    workflow_mode: str | None = Field(default=None, pattern="^(default_user|advanced_word|agent_candidate)$")


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
        "rendered_pdf": request.rendered_pdf,
        "page_images_dir": request.page_images_dir,
        "workflow_mode": request.workflow_mode,
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
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
    workflow_mode: str | None = None,
) -> dict[str, Any]:
    render_workflow_mode = resolve_render_workflow_mode(
        workflow_mode=workflow_mode,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )
    payload = render_verify_document(
        file_path,
        output_dir=output_dir,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )
    render_summary = payload.get("render_summary") or {}
    layout_score = payload.get("layout_score") or {}
    render_text_summary = payload.get("render_text_summary") or {}
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": _utcnow(),
            "operation": "render-verify",
            "status": "ok",
            "render_workflow_mode": render_workflow_mode,
            "summary": {
                "page_count": payload.get("page_count", 0),
                "render_engine": payload.get("render_engine"),
                "evidence_source": payload.get("evidence_source"),
                "evidence_trust": payload.get("evidence_trust"),
                "evidence_authoritative": bool(payload.get("evidence_authoritative")),
                "layout_decision_eligible": bool(payload.get("layout_decision_eligible")),
                "render_fallback_used": bool(payload.get("render_fallback_used")),
                "render_finding_count": len(payload.get("render_findings") or []),
                "render_highest_severity": render_summary.get("highest_severity"),
                "layout_score": layout_score.get("score"),
                "layout_penalty": layout_score.get("penalty"),
                "actionable_finding_count": int(render_summary.get("actionable_finding_count") or 0),
                "expected_blank_count": int(render_summary.get("expected_blank_count") or 0),
                "object_flow_issue_count": int(render_summary.get("object_flow_issue_count") or 0),
                "heading_break_issue_count": int(render_summary.get("heading_break_issue_count") or 0),
                "page_text_available_count": int(render_text_summary.get("page_text_available_count") or 0),
                "page_text_extraction_warning_count": int(render_text_summary.get("page_text_extraction_warning_count") or 0),
                "review_item_count": len(payload.get("review_items") or []),
                "manual_review_rule_count": len(payload.get("manual_review_rule_ids") or []),
                "unsupported_rule_count": len(payload.get("unsupported_rule_ids") or []),
                "render_workflow_mode": render_workflow_mode["id"],
            },
        }
    )
    return payload


def build_render_workflow_modes_payload() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "recommended_mode": "default_user",
        "render_layer_issues": [
            "Word/WPS 才是最终版式证据，但它们不是稳定后端服务。",
            "自动连接 Word 可能遇到权限、恢复弹窗、会员弹窗或导出 PDF 超时。",
            "候选稿修复必须回到 DOCX，且需要再次导出 PDF 对比分数，不能直接改 PDF。",
        ],
        "modes": [dict(item) for item in RENDER_WORKFLOW_MODES],
    }


def resolve_render_workflow_mode(
    *,
    workflow_mode: str | None,
    renderer: str,
    rendered_pdf: str | None,
    page_images_dir: str | None,
) -> dict[str, Any]:
    mode_id = workflow_mode
    if mode_id is None:
        mode_id = "default_user" if rendered_pdf or page_images_dir else "advanced_word"
    mode = next((dict(item) for item in RENDER_WORKFLOW_MODES if item["id"] == mode_id), None)
    if mode is None:
        valid = ", ".join(item["id"] for item in RENDER_WORKFLOW_MODES)
        raise ValueError(f"未知渲染工作流模式: {workflow_mode}。可选: {valid}")
    if mode_id == "default_user" and not (rendered_pdf or page_images_dir):
        raise ValueError("默认用户模式需要先用 Word/WPS 导出 PDF，或提供页图目录。")
    if mode_id == "advanced_word" and renderer not in {"auto", "word-pdf"}:
        raise ValueError("高级模式只能使用 Word PDF 渲染。")
    if mode_id == "agent_candidate":
        raise ValueError("Agent 候选稿模式不直接执行 render-verify；请先生成候选 DOCX，再用默认用户模式复核 PDF。")
    return mode


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
