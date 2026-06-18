from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import inspect
import os
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from typing import Any, Callable
from uuid import uuid4

import audit_thesis
from article_engine import apply_fix, normalize_document, render_verify_document, verify_document
from article_engine.service import _default_output_path
from article_api import storage
from article_api import errors as api_errors
from article_api import job_artifacts, job_execution
from article_api import job_retention
from article_api import job_payloads
from article_api.render_evidence import register_render_evidence_screenshots
from article_api.uploads import build_job_workspace, stage_job_input_docx

JobRecord = job_payloads.JobRecord


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _last_seen_timestamp(payload: dict[str, Any]) -> str | None:
    runtime = payload.get("runtime") or {}
    return (
        runtime.get("last_heartbeat_at")
        or payload.get("updated_at")
        or payload.get("started_at")
        or payload.get("created_at")
    )


def _seconds_since(now: str, then: str | None) -> float | None:
    now_dt = _parse_timestamp(now)
    then_dt = _parse_timestamp(then)
    if now_dt is None or then_dt is None:
        return None
    return max((now_dt - then_dt).total_seconds(), 0.0)


def _recovery_error_payload(status: str) -> dict[str, Any]:
    return {
        "code": "worker_recovery_failed",
        "type": "RuntimeError",
        "message": (
            f"Recovered unfinished job from persistent store without an active worker: {status}. "
            "Marked as failed for manual resubmission."
        ),
        "http_status": 409,
    }


_JOB_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "verify": verify_document,
    "apply": apply_fix,
    "normalize": normalize_document,
    "render-verify": render_verify_document,
}
HEARTBEAT_STALE_SECONDS_ENV = "ARTICLE_API_JOB_HEARTBEAT_STALE_SECONDS"
RECOVERY_GRACE_SECONDS_ENV = "ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS"
_JOB_LOCK = Lock()
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="article-job-worker")
_ACTIVE_FUTURES: dict[str, Future[Any]] = {}
_FINISHED_STATUSES = {"succeeded", "failed"}
_PROJECT_ROOT = job_execution.PROJECT_ROOT
_SCRIPTS_ROOT = job_execution.SCRIPTS_ROOT


def _clone_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.clone_dict(payload)


def _coerce_positive_int(value: Any, *, field_name: str, default: int) -> int:
    return job_payloads.coerce_positive_int(value, field_name=field_name, default=default)


def _coerce_nonnegative_float(value: Any, *, field_name: str, default: float) -> float:
    return job_payloads.coerce_nonnegative_float(value, field_name=field_name, default=default)


def _coerce_positive_float(value: Any, *, field_name: str) -> float:
    return job_payloads.coerce_positive_float(value, field_name=field_name)


def _heartbeat_stale_after_seconds() -> float:
    raw = os.environ.get(HEARTBEAT_STALE_SECONDS_ENV)
    if raw in (None, ""):
        return 300.0
    return _coerce_positive_float(raw, field_name=HEARTBEAT_STALE_SECONDS_ENV)


def _recovery_grace_seconds() -> float:
    raw = os.environ.get(RECOVERY_GRACE_SECONDS_ENV)
    if raw in (None, ""):
        return 30.0
    return _coerce_positive_float(raw, field_name=RECOVERY_GRACE_SECONDS_ENV)


def _serialize_job(record: JobRecord, *, include_result: bool) -> dict[str, Any]:
    return job_payloads.serialize_job(record, include_result=include_result, finished_statuses=_FINISHED_STATUSES)


def _inspection_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.inspection_from_payload(payload, finished_statuses=_FINISHED_STATUSES)


def _list_item_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.list_item_from_payload(payload, finished_statuses=_FINISHED_STATUSES)


def _with_current_artifact_availability(payload: dict[str, Any]) -> dict[str, Any]:
    refreshed = _clone_dict(payload)
    refreshed["artifacts"] = job_artifacts.refresh_artifact_availability(refreshed.get("artifacts"))
    return refreshed


def _ensure_report_artifact(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return job_artifacts.ensure_report_artifact(
        payload.get("artifacts"),
        job_id=payload["job_id"],
        operation=payload["operation"],
        status=payload["status"],
        created_at=payload["created_at"],
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        summary=payload.get("summary"),
        resolved_request=payload.get("resolved_request"),
        runtime=payload.get("runtime"),
        error=payload.get("error"),
    )


def _ensure_finished_report_artifact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") not in _FINISHED_STATUSES:
        return payload
    if payload.get("operation") not in {"apply", "normalize"}:
        return payload
    report_artifact = next(
        ((artifact or {}) for artifact in payload.get("artifacts") or [] if (artifact or {}).get("role") == job_artifacts.REPORT_ARTIFACT_ROLE),
        None,
    )
    if (
        report_artifact
        and report_artifact.get("report_version") == job_artifacts.REPORT_SCHEMA_VERSION
        and report_artifact.get("path")
        and os.path.exists(report_artifact["path"])
    ):
        return payload

    includes_result = "result" in payload
    stored_payload = storage.get_job(payload["job_id"], include_result=True) or payload
    persisted = _clone_dict(stored_payload)
    persisted["artifacts"] = _ensure_report_artifact(persisted)
    storage.upsert_job(persisted)
    if includes_result:
        return persisted
    without_result = _clone_dict(persisted)
    without_result.pop("result", None)
    return without_result


def _get_handler(operation: str) -> Callable[..., dict[str, Any]]:
    try:
        return _JOB_HANDLERS[operation]
    except KeyError as exc:
        supported = ", ".join(sorted(_JOB_HANDLERS))
        raise ValueError(f"Unsupported job operation: {operation}. Supported operations: {supported}") from exc


def _resolve_request(operation: str, request: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.resolve_request(
        operation,
        request,
        default_output_path=_default_output_path,
    )


def _result_summary(operation: str, result: dict[str, Any], resolved_request: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.build_result_summary(operation, result, resolved_request)


def _failure_summary(operation: str, resolved_request: dict[str, Any], error: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.build_failure_summary(operation, resolved_request, error)


def _normalize_error_payload(error: dict[str, Any]) -> dict[str, Any]:
    return api_errors.normalize_error_payload(error)


def _merge_recovery_summary(
    operation: str,
    resolved_request: dict[str, Any],
    error: dict[str, Any],
    *,
    existing_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return job_payloads.merge_recovery_summary(
        operation,
        resolved_request,
        error,
        existing_summary=existing_summary,
    )


def _build_failed_record_from_payload(payload: dict[str, Any], *, error: dict[str, Any]) -> JobRecord:
    record = JobRecord(
        job_id=payload["job_id"],
        operation=payload["operation"],
        request=_clone_dict(payload["request"]),
        resolved_request=_clone_dict(payload["resolved_request"]),
        workspace=deepcopy(payload.get("workspace")),
        runtime=None,
        status="failed",
        created_at=payload["created_at"],
        updated_at=_utcnow(),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        summary=None,
        artifacts=deepcopy(payload.get("artifacts")),
        result=deepcopy(payload.get("result")),
        error=error,
        mode=payload.get("mode", "background"),
    )
    record.runtime = _normalize_runtime_metadata(
        record.resolved_request,
        record.workspace,
        deepcopy(payload.get("runtime")),
    )
    record.summary = _merge_recovery_summary(
        record.operation,
        record.resolved_request,
        error,
        existing_summary=deepcopy(payload.get("summary")),
    )
    if record.runtime is not None:
        record.runtime["lease_state"] = "released"
        _append_runtime_event(
            record.runtime,
            event="recovered_as_failed",
            operation=record.operation,
            job_status=record.status,
            error=error,
        )
    if payload.get("artifacts"):
        record.artifacts = deepcopy(payload.get("artifacts"))
    else:
        record.artifacts = _build_artifacts(
            record.operation,
            record.resolved_request,
            record.workspace,
            result=record.result,
            status="succeeded" if record.result is not None else record.status,
        )
    return record


def _build_artifacts(
    operation: str,
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
    *,
    result: dict[str, Any] | None,
    status: str,
) -> list[dict[str, Any]]:
    return job_artifacts.build_artifacts(
        operation,
        resolved_request,
        workspace,
        result=result,
        status=status,
    )


def _normalize_result_payload(result: dict[str, Any], resolved_request: dict[str, Any]) -> dict[str, Any]:
    return job_payloads.normalize_result_payload(result, resolved_request)


def _build_runtime_metadata(
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
) -> dict[str, Any]:
    return job_payloads.build_runtime_metadata(resolved_request, workspace)


def _normalize_runtime_metadata(
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    return job_payloads.normalize_runtime_metadata(resolved_request, workspace, runtime)


def _finalize_runtime_metadata(runtime: dict[str, Any]) -> dict[str, Any]:
    return job_artifacts.finalize_runtime_metadata(runtime)


def _handler_request(resolved_request: dict[str, Any]) -> dict[str, Any]:
    return job_execution.handler_request(resolved_request)


def _subprocess_env() -> dict[str, str]:
    return job_execution.subprocess_env(scripts_root=_SCRIPTS_ROOT)


def _timeout_error_payload(timeout_seconds: float | None) -> dict[str, Any]:
    return job_execution.timeout_error_payload(timeout_seconds)


def _transient_internal_error_payload(message: str) -> dict[str, Any]:
    return job_execution.transient_internal_error_payload(message)


def _run_handler_subprocess(
    operation: str,
    handler_request: dict[str, Any],
    *,
    timeout_seconds: float | None,
    on_heartbeat=None,
    on_phase=None,
) -> dict[str, Any]:
    return job_execution.run_handler_subprocess(
        operation,
        handler_request,
        timeout_seconds=timeout_seconds,
        on_heartbeat=on_heartbeat,
        on_phase=on_phase,
        project_root=_PROJECT_ROOT,
        scripts_root=_SCRIPTS_ROOT,
    )


def _execute_job_attempt(operation: str, resolved_request: dict[str, Any], *, on_heartbeat=None, on_phase=None) -> dict[str, Any]:
    return job_execution.execute_job_attempt(
        operation,
        resolved_request,
        run_subprocess=_run_handler_subprocess,
        on_heartbeat=on_heartbeat,
        on_phase=on_phase,
    )


def _is_retryable_error(error: dict[str, Any]) -> bool:
    return job_execution.is_retryable_error(error)


def _append_attempt(runtime: dict[str, Any] | None, *, attempt: int, status: str, error: dict[str, Any] | None = None) -> None:
    if runtime is None:
        return
    attempts = runtime.setdefault("attempts", [])
    entry = {
        "attempt": attempt,
        "status": status,
        "retryable": bool(error and _is_retryable_error(error)),
    }
    if error is not None:
        entry["error_code"] = error.get("code")
        entry["error_type"] = error.get("type")
    attempts.append(entry)
    runtime["attempt_count"] = attempt


def _append_runtime_event(
    runtime: dict[str, Any] | None,
    *,
    event: str,
    operation: str,
    job_status: str,
    attempt: int | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    if runtime is None:
        return
    events = runtime.setdefault("events", [])
    entry: dict[str, Any] = {
        "at": _utcnow(),
        "event": event,
        "operation": operation,
        "job_status": job_status,
    }
    if attempt is not None:
        entry["attempt"] = int(attempt)
    if error is not None:
        entry["error_code"] = error.get("code")
        entry["error_type"] = error.get("type")
    events.append(entry)


def _last_runtime_event_name(runtime: dict[str, Any] | None) -> str | None:
    if runtime is None:
        return None
    events = runtime.get("events") or []
    if not events:
        return None
    last_event = events[-1]
    if not isinstance(last_event, dict):
        return None
    return last_event.get("event")


def _heartbeat_runtime(runtime: dict[str, Any] | None, *, lease_state: str | None = None) -> None:
    if runtime is None:
        return
    runtime["last_heartbeat_at"] = _utcnow()
    runtime["heartbeat_count"] = int(runtime.get("heartbeat_count") or 0) + 1
    runtime["heartbeat_age_seconds"] = 0.0
    if lease_state is not None:
        runtime["lease_state"] = lease_state


def _set_runtime_phase(runtime: dict[str, Any] | None, phase: str) -> None:
    if runtime is None:
        return
    runtime["phase"] = phase


def _persist_attempt_runtime_heartbeat(
    record: JobRecord,
    *,
    attempt_lock: Lock,
) -> None:
    with attempt_lock:
        if record.status != "running" or record.runtime is None:
            return
        _heartbeat_runtime(record.runtime)
        if record.runtime.get("phase") not in {"finalizing", "completed"}:
            _set_runtime_phase(record.runtime, "processing")
        record.updated_at = _utcnow()
        storage.upsert_job(_serialize_job(record, include_result=True))


def _persist_attempt_runtime_phase(
    record: JobRecord,
    attempt_lock: Lock,
    phase: str,
) -> None:
    with attempt_lock:
        if record.status != "running" or record.runtime is None:
            return
        _set_runtime_phase(record.runtime, phase)
        _heartbeat_runtime(record.runtime)
        record.updated_at = _utcnow()
        storage.upsert_job(_serialize_job(record, include_result=True))


def _execute_job_attempt_with_callbacks(
    operation: str,
    resolved_request: dict[str, Any],
    *,
    on_heartbeat=None,
    on_phase=None,
) -> dict[str, Any]:
    try:
        parameters = inspect.signature(_execute_job_attempt).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_kwargs = any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters.values())
    accepts_callbacks = accepts_kwargs or "on_heartbeat" in parameters or "on_phase" in parameters
    if accepts_callbacks:
        return _execute_job_attempt(
            operation,
            resolved_request,
            on_heartbeat=on_heartbeat,
            on_phase=on_phase,
        )
    return _execute_job_attempt(operation, resolved_request)


def _resolve_default_output_path(file_path: str, scopes, *, source_display_name: str | None) -> str:
    return job_payloads.resolve_default_output_path(
        file_path,
        scopes,
        source_display_name=source_display_name,
        default_output_path=_default_output_path,
    )


def _resolve_default_normalize_output_path(file_path: str, *, source_display_name: str | None) -> str:
    return job_payloads.resolve_default_normalize_output_path(
        file_path,
        source_display_name=source_display_name,
    )


def clear_jobs() -> None:
    with _JOB_LOCK:
        futures = list(_ACTIVE_FUTURES.values())
    for future in futures:
        try:
            future.result(timeout=10)
        except Exception:
            continue
    storage.clear_jobs()
    with _JOB_LOCK:
        _ACTIVE_FUTURES.clear()


def job_count() -> int:
    return storage.job_count()


def _reconcile_incomplete_jobs() -> None:
    payloads = storage.list_jobs(include_result=True)
    if not payloads:
        return
    grace_seconds = _recovery_grace_seconds()
    now = _utcnow()
    with _JOB_LOCK:
        active_job_ids = {job_id for job_id, future in _ACTIVE_FUTURES.items() if not future.done()}
        finished_job_ids = {job_id for job_id, future in _ACTIVE_FUTURES.items() if future.done()}
        for job_id in finished_job_ids:
            _ACTIVE_FUTURES.pop(job_id, None)
    for payload in payloads:
        if payload["status"] in _FINISHED_STATUSES:
            continue
        if payload["job_id"] in active_job_ids:
            continue
        age_seconds = _seconds_since(now, _last_seen_timestamp(payload))
        if age_seconds is not None and age_seconds < grace_seconds:
            continue
        record = _build_failed_record_from_payload(payload, error=_recovery_error_payload(payload["status"]))
        _finalize_record(record)


def runtime_snapshot() -> dict[str, Any]:
    _reconcile_incomplete_jobs()
    payloads = storage.list_jobs(include_result=False)
    queued_job_ids = sorted(payload["job_id"] for payload in payloads if payload["status"] == "queued")
    running_job_ids = sorted(payload["job_id"] for payload in payloads if payload["status"] == "running")
    finished_job_ids = sorted(payload["job_id"] for payload in payloads if payload["status"] in _FINISHED_STATUSES)
    recovered_failed_job_ids: list[str] = []
    stale_heartbeat_job_ids: list[str] = []
    recovery_pending_job_ids: list[str] = []
    heartbeat_stale_after_seconds = _heartbeat_stale_after_seconds()
    recovery_grace_seconds = _recovery_grace_seconds()
    now = _utcnow()
    with _JOB_LOCK:
        active_future_job_ids = sorted(job_id for job_id, future in _ACTIVE_FUTURES.items() if not future.done())
    active_future_job_id_set = set(active_future_job_ids)
    for payload in payloads:
        runtime = payload.get("runtime") or {}
        events = runtime.get("events") or []
        if any(isinstance(event, dict) and event.get("event") == "recovered_as_failed" for event in events):
            recovered_failed_job_ids.append(payload["job_id"])
        if payload["status"] in _FINISHED_STATUSES:
            continue
        if payload["job_id"] not in active_future_job_id_set:
            age_seconds = _seconds_since(now, _last_seen_timestamp(payload))
            if age_seconds is not None and age_seconds < recovery_grace_seconds:
                recovery_pending_job_ids.append(payload["job_id"])
            continue
        if payload["status"] != "running" or payload["job_id"] not in active_future_job_id_set:
            continue
        heartbeat_age_seconds = _seconds_since(now, runtime.get("last_heartbeat_at"))
        if heartbeat_age_seconds is None:
            continue
        if heartbeat_age_seconds >= heartbeat_stale_after_seconds:
            stale_heartbeat_job_ids.append(payload["job_id"])
    return {
        "worker_model": "single",
        "executor": {
            "kind": "thread_pool",
            "max_workers": 1,
        },
        "operations": sorted(_JOB_HANDLERS),
        "lifecycle_statuses": ["queued", "running", "succeeded", "failed"],
        "non_goals": [
            "cancel",
            "priority",
            "queue_backpressure",
            "multi_worker_scheduling",
        ],
        "jobs": {
            "queued_job_ids": queued_job_ids,
            "running_job_ids": running_job_ids,
            "finished_job_ids": finished_job_ids,
            "unfinished_count": len(queued_job_ids) + len(running_job_ids),
        },
        "recovery": {
            "strategy": "fail_unfinished_without_active_worker_future",
            "recovered_failed_job_ids": sorted(recovered_failed_job_ids),
            "recovered_failed_count": len(recovered_failed_job_ids),
            "heartbeat_stale_after_seconds": heartbeat_stale_after_seconds,
            "grace_seconds": recovery_grace_seconds,
            "pending_recovery_job_ids": sorted(recovery_pending_job_ids),
            "pending_recovery_count": len(recovery_pending_job_ids),
        },
        "health": {
            "stale_heartbeat_job_ids": sorted(stale_heartbeat_job_ids),
            "stale_heartbeat_count": len(stale_heartbeat_job_ids),
        },
        "active_future_job_ids": active_future_job_ids,
        "active_future_count": len(active_future_job_ids),
    }


def list_jobs() -> list[dict[str, Any]]:
    _reconcile_incomplete_jobs()
    payloads = storage.list_jobs(include_result=False)
    return [_list_item_from_payload(_with_current_artifact_availability(_ensure_finished_report_artifact_payload(payload))) for payload in payloads]


def _resolved_path(path_value: str | None) -> Path | None:
    return job_artifacts.resolved_path(path_value)


def _is_within(path: Path, root: Path | None) -> bool:
    return job_artifacts.is_within(path, root)


def _cleanup_candidate_map(payload: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    return job_artifacts.cleanup_candidate_map(payload)


def cleanup_job(job_id: str, *, policy: str = "manual") -> dict[str, Any]:
    return job_retention.cleanup_job(
        job_id,
        policy=policy,
        finished_statuses=_FINISHED_STATUSES,
        get_job_payload_fn=lambda job_id: storage.get_job(job_id, include_result=True),
        upsert_job_cleanup_fn=lambda job_id, payload: storage.upsert_job_cleanup(job_id, payload),
        get_job_fn=lambda job_id: get_job(job_id),
        cleanup_candidate_map_fn=lambda payload: _cleanup_candidate_map(payload),
        utcnow_fn=lambda: _utcnow(),
    )


def sweep_job_retention(max_age_seconds: float, *, now: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return job_retention.sweep_job_retention(
        max_age_seconds,
        now=now,
        dry_run=dry_run,
        finished_statuses=_FINISHED_STATUSES,
        utcnow_fn=lambda: _utcnow(),
        coerce_positive_float_fn=lambda value, field_name: _coerce_positive_float(value, field_name=field_name),
        parse_timestamp_fn=lambda value: _parse_timestamp(value),
        reconcile_incomplete_jobs_fn=lambda: _reconcile_incomplete_jobs(),
        list_jobs_fn=lambda: storage.list_jobs(include_result=True),
        cleanup_job_fn=lambda job_id, policy="retention": cleanup_job(job_id, policy=policy),
    )


def _finalize_record(record: JobRecord) -> None:
    if record.runtime is not None:
        record.runtime = _finalize_runtime_metadata(record.runtime)
    record.finished_at = _utcnow()
    record.updated_at = record.finished_at
    payload = _serialize_job(record, include_result=True)
    payload["artifacts"] = _ensure_report_artifact(payload)
    record.artifacts = payload["artifacts"]
    storage.upsert_job(payload)


def _mark_record_failed_from_exception(
    record: JobRecord,
    exc: Exception,
    *,
    attempt: int | None,
) -> None:
    error = _transient_internal_error_payload(f"Unexpected job orchestration failure: {exc}")
    error["type"] = type(exc).__name__
    record.status = "failed"
    record.error = error
    record.result = None
    if record.runtime is not None and _last_runtime_event_name(record.runtime) != "job_failed":
        _append_runtime_event(
            record.runtime,
            event="job_failed",
            operation=record.operation,
            job_status=record.status,
            attempt=attempt,
            error=error,
        )
    record.summary = _failure_summary(record.operation, record.resolved_request, error)
    record.artifacts = _build_artifacts(
        record.operation,
        record.resolved_request,
        record.workspace,
        result=None,
        status=record.status,
    )


def _run_job(job_id: str) -> None:
    payload = storage.get_job(job_id, include_result=True)
    if payload is None:
        return

    record = JobRecord(
        job_id=payload["job_id"],
        operation=payload["operation"],
        request=_clone_dict(payload["request"]),
        resolved_request=_clone_dict(payload["resolved_request"]),
        workspace=deepcopy(payload.get("workspace")),
        runtime=deepcopy(payload.get("runtime")),
        status="running",
        created_at=payload["created_at"],
        updated_at=_utcnow(),
        started_at=_utcnow(),
        finished_at=payload.get("finished_at"),
        summary=deepcopy(payload.get("summary")),
        artifacts=deepcopy(payload.get("artifacts")),
        result=deepcopy(payload.get("result")),
        error=deepcopy(payload.get("error")),
        mode=payload.get("mode", "background"),
    )
    record.updated_at = record.started_at
    _heartbeat_runtime(record.runtime, lease_state="active")
    _set_runtime_phase(record.runtime, "submitted")
    _append_runtime_event(record.runtime, event="worker_started", operation=record.operation, job_status=record.status)
    _heartbeat_runtime(record.runtime)
    storage.upsert_job(_serialize_job(record, include_result=True))
    max_attempts = int(record.resolved_request.get("max_attempts") or 1)
    retry_delay_seconds = float(record.resolved_request.get("retry_delay_seconds") or 0.0)
    current_attempt: int | None = None
    attempt_lock = Lock()
    try:
        for attempt in range(1, max_attempts + 1):
            current_attempt = attempt
            with attempt_lock:
                _heartbeat_runtime(record.runtime)
                _set_runtime_phase(record.runtime, "processing")
                _append_runtime_event(
                    record.runtime,
                    event="attempt_started",
                    operation=record.operation,
                    job_status=record.status,
                    attempt=attempt,
                )
                record.updated_at = _utcnow()
                storage.upsert_job(_serialize_job(record, include_result=True))
            try:
                attempt_payload = _execute_job_attempt_with_callbacks(
                    record.operation,
                    record.resolved_request,
                    on_heartbeat=lambda: _persist_attempt_runtime_heartbeat(record, attempt_lock=attempt_lock),
                    on_phase=lambda phase: _persist_attempt_runtime_phase(record, attempt_lock, phase),
                )
            finally:
                pass
            record.resolved_request["attempt_count"] = attempt
            if attempt_payload.get("ok"):
                with attempt_lock:
                    _set_runtime_phase(record.runtime, "finalizing")
                    _heartbeat_runtime(record.runtime)
                    record.result = _normalize_result_payload(
                        attempt_payload["result"],
                        record.resolved_request,
                    )
                    if record.runtime is not None and isinstance(record.result, dict):
                        record.runtime["candidate_mode"] = record.result.get("candidate_mode") or record.runtime.get("candidate_mode")
                        record.runtime["candidate_request_mode"] = record.result.get("candidate_request_mode") or record.runtime.get("candidate_request_mode")
                        record.runtime["degraded_from_compact"] = bool(record.result.get("degraded_from_compact"))
                        record.runtime["degrade_reason"] = record.result.get("degrade_reason")
                record.status = "succeeded"
                _append_attempt(record.runtime, attempt=attempt, status="succeeded")
                _append_runtime_event(
                    record.runtime,
                    event="attempt_succeeded",
                    operation=record.operation,
                    job_status=record.status,
                    attempt=attempt,
                )
                record.summary = _result_summary(record.operation, record.result, record.resolved_request)
                if record.summary is not None and record.runtime is not None:
                    record.summary["phase"] = record.runtime.get("phase")
                    record.summary["heartbeat_age_seconds"] = record.runtime.get("heartbeat_age_seconds")
                record.artifacts = _build_artifacts(
                    record.operation,
                    record.resolved_request,
                    record.workspace,
                    result=record.result,
                    status=record.status,
                )
                break

            error = _normalize_error_payload(
                deepcopy(attempt_payload.get("error") or _transient_internal_error_payload("Unknown job runner failure"))
            )
            _append_attempt(record.runtime, attempt=attempt, status="failed", error=error)
            _append_runtime_event(
                record.runtime,
                event="attempt_failed",
                operation=record.operation,
                job_status=record.status,
                attempt=attempt,
                error=error,
            )
            should_retry = attempt < max_attempts and _is_retryable_error(error)
            if should_retry:
                _append_runtime_event(
                    record.runtime,
                    event="retry_scheduled",
                    operation=record.operation,
                    job_status=record.status,
                    attempt=attempt,
                    error=error,
                )
                record.updated_at = _utcnow()
                storage.upsert_job(_serialize_job(record, include_result=True))
                if retry_delay_seconds:
                    sleep(retry_delay_seconds)
                continue

            record.status = "failed"
            record.error = error
            with attempt_lock:
                _set_runtime_phase(record.runtime, "finalizing")
                _heartbeat_runtime(record.runtime)
            _append_runtime_event(
                record.runtime,
                event="job_failed",
                operation=record.operation,
                job_status=record.status,
                attempt=attempt,
                error=error,
            )
            record.summary = _failure_summary(record.operation, record.resolved_request, record.error)
            if record.summary is not None and record.runtime is not None:
                record.summary["phase"] = record.runtime.get("phase")
                record.summary["heartbeat_age_seconds"] = record.runtime.get("heartbeat_age_seconds")
            record.artifacts = _build_artifacts(
                record.operation,
                record.resolved_request,
                record.workspace,
                result=None,
                status=record.status,
            )
            break
    except Exception as exc:
        _mark_record_failed_from_exception(record, exc, attempt=current_attempt)
    finally:
        if record.runtime is not None:
            record.runtime["lease_state"] = "released"
            if record.status in _FINISHED_STATUSES:
                record.runtime["phase"] = "completed"
                if record.summary is not None:
                    record.summary["phase"] = "completed"
                    record.summary["heartbeat_age_seconds"] = record.runtime.get("heartbeat_age_seconds")
            if record.status == "succeeded":
                _append_runtime_event(
                    record.runtime,
                    event="job_succeeded",
                    operation=record.operation,
                    job_status=record.status,
                    attempt=record.resolved_request.get("attempt_count"),
                )
        _finalize_record(record)
        with _JOB_LOCK:
            _ACTIVE_FUTURES.pop(job_id, None)


def _submit_job(job_id: str) -> None:
    future = _JOB_EXECUTOR.submit(_run_job, job_id)
    with _JOB_LOCK:
        _ACTIVE_FUTURES[job_id] = future


def retry_job(job_id: str) -> dict[str, Any]:
    payload = storage.get_job(job_id, include_result=True)
    if payload is None:
        raise LookupError(f"Job not found: {job_id}")
    if payload["status"] not in _FINISHED_STATUSES:
        raise RuntimeError(f"Job retry is only available after completion: {job_id}")

    request = _clone_dict(payload["request"])
    execution_request = _clone_dict(request)
    runtime = payload.get("runtime") or {}
    resolved_request = payload.get("resolved_request") or {}
    upload_id = runtime.get("source_upload_id") or request.get("upload_id") or resolved_request.get("upload_id")
    if upload_id:
        upload = storage.get_upload(upload_id)
        if upload is None:
            raise RuntimeError(f"Upload not found for retry: {upload_id}")
        stored_path = upload.get("stored_path")
        if not stored_path or not os.path.exists(stored_path):
            raise RuntimeError(f"Uploaded file is unavailable for retry: {upload_id}")
        execution_request["file_path"] = stored_path
        execution_request["upload_id"] = upload_id
        execution_request["source_display_name"] = upload["file_name"]
    else:
        source_file_path = runtime.get("source_file_path") or request.get("file_path") or resolved_request.get("file_path")
        execution_request["file_path"] = audit_thesis.validate_docx_path(source_file_path)
        if resolved_request.get("source_display_name"):
            execution_request["source_display_name"] = resolved_request["source_display_name"]

    request["retry_of_job_id"] = job_id
    execution_request["retry_of_job_id"] = job_id
    execution_request["_public_request"] = request
    return create_job(payload["operation"], execution_request)


def create_job(operation: str, request: dict[str, Any]) -> dict[str, Any]:
    _reconcile_incomplete_jobs()
    _get_handler(operation)
    job_id = uuid4().hex
    public_request = _clone_dict(request.get("_public_request") or request)
    execution_request = _clone_dict(request)
    execution_request.pop("_public_request", None)
    resolved_request = _resolve_request(operation, execution_request)
    workspace = None
    if resolved_request.get("stage_input"):
        workspace = build_job_workspace(job_id, runtime_root=resolved_request.get("runtime_root"))
        staged = stage_job_input_docx(
            resolved_request["file_path"],
            job_id=job_id,
            runtime_root=resolved_request.get("runtime_root"),
        )
        resolved_request["source_file_path"] = resolved_request["file_path"]
        resolved_request["file_path"] = staged.staged_path
        if operation in {"apply", "normalize"} and not resolved_request.get("_explicit_output_path"):
            if operation == "apply":
                default_output_name = os.path.basename(
                    _resolve_default_output_path(
                        resolved_request["source_file_path"],
                        resolved_request.get("scopes"),
                        source_display_name=resolved_request.get("source_display_name"),
                    )
                )
            else:
                default_output_name = os.path.basename(
                    _resolve_default_normalize_output_path(
                        resolved_request["source_file_path"],
                        source_display_name=resolved_request.get("source_display_name"),
                    )
                )
            resolved_request["output_path"] = os.path.join(workspace["outputs"], default_output_name)
    resolved_request.pop("_explicit_output_path", None)

    now = _utcnow()
    record = JobRecord(
        job_id=job_id,
        operation=operation,
        request=public_request,
        resolved_request=resolved_request,
        workspace=workspace,
        runtime=_normalize_runtime_metadata(resolved_request, workspace, None),
        status="queued",
        created_at=now,
        updated_at=now,
    )
    _append_runtime_event(record.runtime, event="job_queued", operation=operation, job_status=record.status)
    storage.upsert_job(_serialize_job(record, include_result=True))
    _submit_job(record.job_id)
    return _serialize_job(record, include_result=False)


def get_job(job_id: str) -> dict[str, Any]:
    _reconcile_incomplete_jobs()
    payload = storage.get_job(job_id, include_result=False)
    if payload is None:
        raise LookupError(f"Job not found: {job_id}")
    payload = _ensure_finished_report_artifact_payload(payload)
    payload = _with_current_artifact_availability(payload)
    if payload["status"] in _FINISHED_STATUSES:
        return payload
    runtime = payload.get("runtime") or {}
    heartbeat_at = runtime.get("last_heartbeat_at")
    if heartbeat_at:
        heartbeat_age_seconds = _seconds_since(_utcnow(), heartbeat_at)
        if heartbeat_age_seconds is not None:
            runtime["heartbeat_age_seconds"] = heartbeat_age_seconds
            payload["runtime"] = runtime
    return payload


def inspect_job(job_id: str) -> dict[str, Any]:
    payload = get_job(job_id)
    return _inspection_from_payload(payload)


def get_job_result(job_id: str) -> dict[str, Any]:
    _reconcile_incomplete_jobs()
    payload = storage.get_job(job_id, include_result=True)
    if payload is None:
        raise LookupError(f"Job not found: {job_id}")
    payload = _ensure_finished_report_artifact_payload(payload)
    payload = _with_current_artifact_availability(payload)
    if payload["status"] not in _FINISHED_STATUSES:
        raise RuntimeError(f"Job result is not ready yet: {job_id}")
    if payload.get("operation") == "render-verify" and isinstance(payload.get("result"), dict):
        payload = _clone_dict(payload)
        payload["result"] = register_render_evidence_screenshots(dict(payload["result"]))
    return payload


def get_job_artifact(job_id: str, artifact_role: str) -> dict[str, Any]:
    payload = get_job_result(job_id)
    for artifact in payload.get("artifacts") or []:
        if artifact.get("role") == artifact_role:
            return artifact
    raise LookupError(f"Artifact not found for job {job_id}: {artifact_role}")


def wait_for_job(job_id: str, *, timeout: float = 10.0, poll_interval: float = 0.01) -> dict[str, Any]:
    deadline = monotonic() + timeout
    while True:
        try:
            payload = get_job(job_id)
        except LookupError:
            with _JOB_LOCK:
                future = _ACTIVE_FUTURES.get(job_id)
            if future is None:
                raise
            if monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for job completion: {job_id}")
            sleep(poll_interval)
            continue
        if payload["status"] in _FINISHED_STATUSES:
            return payload
        if monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for job completion: {job_id}")
        sleep(poll_interval)
