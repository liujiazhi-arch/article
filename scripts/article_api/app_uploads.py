from __future__ import annotations

import os
from datetime import datetime
from time import monotonic
from typing import Any

from article_api import storage
from article_api.retention_reports import build_retention_sweep_report, with_cleanup_result
from article_api.uploads import resolve_runtime_root


def upload_view(payload: dict[str, Any]) -> dict[str, Any]:
    view = dict(payload)
    view["cleanup"] = storage.get_upload_cleanup(payload["upload_id"])
    view["available"] = bool(payload.get("stored_path") and os.path.exists(payload["stored_path"]))
    return view


def is_within(path: str, root: str | None) -> bool:
    if root is None:
        return False
    path_obj = os.path.abspath(os.path.expanduser(path))
    root_obj = os.path.abspath(os.path.expanduser(root))
    try:
        return os.path.commonpath([path_obj, root_obj]) == root_obj
    except ValueError:
        return False


def cleanup_upload(
    upload_id: str,
    *,
    policy: str = "manual",
    now_iso: str,
) -> dict[str, Any]:
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

    if is_within(stored_path, runtime_root):
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
        "cleaned_at": now_iso,
        "attempt_count": int(previous_cleanup.get("attempt_count") or 0) + 1,
        "removed_paths": removed_paths,
        "missing_paths": missing_paths,
        "skipped_paths": skipped_paths,
    }
    storage.upsert_upload_cleanup(upload_id, cleanup_payload)
    refreshed = storage.get_upload(upload_id)
    if refreshed is None:
        raise LookupError(f"Upload not found: {upload_id}")
    return upload_view(refreshed)


def sweep_upload_retention(
    max_age_seconds: float,
    *,
    now: str,
    dry_run: bool,
    parse_timestamp,
    cleanup_upload_fn,
) -> dict[str, Any]:
    reference_dt = parse_timestamp(now)
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
    report = build_retention_sweep_report(
        max_age_seconds=max_age_seconds,
        reference_time=now,
        dry_run=dry_run,
        inspected_count=len(uploads),
        include_blocked_count=True,
    )

    for payload in uploads:
        if storage.get_upload_cleanup(payload["upload_id"]) is not None:
            report["skipped_count"] += 1
            continue
        created_dt = parse_timestamp(payload.get("created_at"))
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

        cleaned_payload = cleanup_upload_fn(payload["upload_id"], policy="retention")
        cleanup = cleaned_payload.get("cleanup") or {}
        report = with_cleanup_result(report, item, cleanup)

    return report


def sweep_retention(
    request,
    *,
    utcnow_fn,
    sweep_job_retention_fn,
    sweep_upload_retention_fn,
) -> dict[str, Any]:
    if request.job_max_age_seconds is None and request.upload_max_age_seconds is None:
        raise ValueError("At least one retention threshold is required")
    reference_time = utcnow_fn()
    response: dict[str, Any] = {
        "policy": "retention",
        "dry_run": request.dry_run,
        "triggered_at": reference_time,
    }
    if request.job_max_age_seconds is not None:
        response["job_retention"] = sweep_job_retention_fn(
            request.job_max_age_seconds,
            now=reference_time,
            dry_run=request.dry_run,
        )
    if request.upload_max_age_seconds is not None:
        response["upload_retention"] = sweep_upload_retention_fn(
            request.upload_max_age_seconds,
            now=reference_time,
            dry_run=request.dry_run,
        )
    return response


def record_retention_success(retention_state: dict[str, Any], *, trigger: str, result: dict[str, Any]) -> None:
    retention_state["last_run_at"] = result.get("triggered_at")
    retention_state["last_trigger"] = trigger
    retention_state["last_result"] = result
    retention_state["last_error"] = None
    retention_state["last_monotonic"] = monotonic()


def record_retention_error(retention_state: dict[str, Any], *, trigger: str, error: Exception, now_iso: str) -> None:
    retention_state["last_run_at"] = now_iso
    retention_state["last_trigger"] = trigger
    retention_state["last_result"] = None
    retention_state["last_error"] = str(error)
    retention_state["last_monotonic"] = monotonic()


def should_autorun_retention(
    *,
    defaults: dict[str, Any],
    retention_state: dict[str, Any],
) -> bool:
    if not defaults["autorun_enabled"]:
        return False
    if defaults["job_max_age_seconds"] is None and defaults["upload_max_age_seconds"] is None:
        return False
    interval_seconds = float(defaults["autorun_interval_seconds"])
    now_mono = monotonic()
    last_mono = retention_state["last_monotonic"]
    if last_mono is not None and now_mono - last_mono < interval_seconds:
        return False
    retention_state["last_monotonic"] = now_mono
    return True
