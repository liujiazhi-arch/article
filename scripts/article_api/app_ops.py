from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from article_api import storage
from article_api.jobs import runtime_snapshot
from article_api.response_payloads import API_VERSION, SERVICE_NAME, SERVICE_STAGE, SERVICE_VERSION, utcnow
from article_api.uploads import resolve_runtime_root


_RUNTIME_DIR_NAMES = ("jobs", "uploads", "staging")


def build_health_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
    }


def build_version_payload() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
    }


def build_readiness_payload() -> dict[str, Any]:
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


def build_retention_defaults_payload(
    *,
    parse_optional_positive_float_env: Callable[[str], float | None],
    parse_bool_env: Callable[[str], bool],
    job_retention_seconds_env: str,
    upload_retention_seconds_env: str,
    retention_autorun_env: str,
    retention_autorun_interval_env: str,
) -> dict[str, Any]:
    return {
        "job_max_age_seconds": parse_optional_positive_float_env(job_retention_seconds_env),
        "upload_max_age_seconds": parse_optional_positive_float_env(upload_retention_seconds_env),
        "autorun_enabled": parse_bool_env(retention_autorun_env),
        "autorun_interval_seconds": parse_optional_positive_float_env(retention_autorun_interval_env) or 300.0,
    }


def build_runtime_root_inventory_payload(runtime_root: str | Path | None = None) -> dict[str, Any]:
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


def build_storage_summary_payload(storage_view: dict[str, Any]) -> dict[str, Any]:
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


def build_runtime_summary_payload(runtime_view: dict[str, Any]) -> dict[str, Any]:
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


def build_retention_summary_payload(defaults: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
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


def build_ops_status_payload(*, storage_status: str, runtime_root_writable: bool, runtime_status: str, retention_status: str) -> str:
    if storage_status != "ok" or not runtime_root_writable:
        return "degraded"
    if runtime_status != "ok" or retention_status == "warn":
        return "warn"
    return "ok"


def build_ops_summary_payload(*, retention_defaults: dict[str, Any], retention_state: dict[str, Any]) -> dict[str, Any]:
    jobs = storage.list_jobs(include_result=False)
    uploads = storage.list_uploads()
    storage_snapshot = storage.inspect_storage(include_integrity_check=False)
    runtime_view = runtime_snapshot()
    runtime_root = build_runtime_root_inventory_payload()
    storage_summary = build_storage_summary_payload(storage_snapshot)
    runtime_summary = build_runtime_summary_payload(runtime_view)
    retention_summary = build_retention_summary_payload(retention_defaults, retention_state)
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
    overall_status = build_ops_status_payload(
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
        "observed_at": utcnow(),
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


def build_ops_storage_payload() -> dict[str, Any]:
    storage_view = storage.inspect_storage()
    runtime_root = build_runtime_root_inventory_payload()
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": utcnow(),
        "status": "ok" if storage_view["status"] == "ok" and runtime_root["writable"] else "degraded",
        "summary": build_storage_summary_payload(storage_view),
        "storage": storage_view,
        "runtime_root": runtime_root,
    }


def build_ops_runtime_payload() -> dict[str, Any]:
    runtime_view = runtime_snapshot()
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": utcnow(),
        "status": build_runtime_summary_payload(runtime_view)["status"],
        "summary": build_runtime_summary_payload(runtime_view),
        "runtime": runtime_view,
    }
