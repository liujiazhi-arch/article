from __future__ import annotations

from datetime import datetime
import os
from threading import Lock
from typing import Any, Callable

from article_api import app_ops, app_uploads
from article_api.jobs import sweep_job_retention
from article_api.schemas import RetentionSweepRequest


JOB_RETENTION_SECONDS_ENV = "ARTICLE_API_JOB_RETENTION_SECONDS"
UPLOAD_RETENTION_SECONDS_ENV = "ARTICLE_API_UPLOAD_RETENTION_SECONDS"
RETENTION_AUTORUN_ENV = "ARTICLE_API_RETENTION_AUTORUN"
RETENTION_AUTORUN_INTERVAL_ENV = "ARTICLE_API_RETENTION_AUTORUN_INTERVAL_SECONDS"

RETENTION_STATE_LOCK = Lock()
RETENTION_STATE: dict[str, Any] = {
    "last_run_at": None,
    "last_trigger": None,
    "last_result": None,
    "last_error": None,
    "last_monotonic": None,
}


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_optional_positive_float_env(env_name: str) -> float | None:
    raw = os.environ.get(env_name)
    if raw in (None, ""):
        return None
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{env_name} must be > 0")
    return value


def parse_bool_env(env_name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def retention_defaults_payload() -> dict[str, Any]:
    return app_ops.build_retention_defaults_payload(
        parse_optional_positive_float_env=parse_optional_positive_float_env,
        parse_bool_env=lambda env_name: parse_bool_env(env_name, default=False),
        job_retention_seconds_env=JOB_RETENTION_SECONDS_ENV,
        upload_retention_seconds_env=UPLOAD_RETENTION_SECONDS_ENV,
        retention_autorun_env=RETENTION_AUTORUN_ENV,
        retention_autorun_interval_env=RETENTION_AUTORUN_INTERVAL_ENV,
    )


def retention_state_payload() -> dict[str, Any]:
    with RETENTION_STATE_LOCK:
        return {
            "last_run_at": RETENTION_STATE["last_run_at"],
            "last_trigger": RETENTION_STATE["last_trigger"],
            "last_result": RETENTION_STATE["last_result"],
            "last_error": RETENTION_STATE["last_error"],
        }


def cleanup_upload(upload_id: str, *, policy: str, utcnow_fn: Callable[[], str]) -> dict[str, Any]:
    return app_uploads.cleanup_upload(upload_id, policy=policy, now_iso=utcnow_fn())


def sweep_upload_retention(
    max_age_seconds: float,
    *,
    now: str,
    dry_run: bool,
    utcnow_fn: Callable[[], str],
    parse_timestamp_fn: Callable[[str | None], datetime | None] = parse_timestamp,
    cleanup_upload_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if cleanup_upload_fn is None:
        cleanup_upload_fn = lambda upload_id, policy="retention": cleanup_upload(
            upload_id,
            policy=policy,
            utcnow_fn=utcnow_fn,
        )
    return app_uploads.sweep_upload_retention(
        max_age_seconds,
        now=now,
        dry_run=dry_run,
        parse_timestamp=parse_timestamp_fn,
        cleanup_upload_fn=cleanup_upload_fn,
    )


def sweep_retention(
    request: RetentionSweepRequest,
    *,
    utcnow_fn: Callable[[], str],
    sweep_job_retention_fn: Callable[..., dict[str, Any]] = sweep_job_retention,
    sweep_upload_retention_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if sweep_upload_retention_fn is None:
        sweep_upload_retention_fn = lambda max_age_seconds, now, dry_run: sweep_upload_retention(
            max_age_seconds,
            now=now,
            dry_run=dry_run,
            utcnow_fn=utcnow_fn,
        )
    return app_uploads.sweep_retention(
        request,
        utcnow_fn=utcnow_fn,
        sweep_job_retention_fn=sweep_job_retention_fn,
        sweep_upload_retention_fn=sweep_upload_retention_fn,
    )


def record_retention_success(*, trigger: str, result: dict[str, Any], utcnow_fn: Callable[[], str]) -> None:
    with RETENTION_STATE_LOCK:
        app_uploads.record_retention_success(
            RETENTION_STATE,
            trigger=trigger,
            result={**result, "triggered_at": result.get("triggered_at") or utcnow_fn()},
        )


def record_retention_error(*, trigger: str, error: Exception, utcnow_fn: Callable[[], str]) -> None:
    with RETENTION_STATE_LOCK:
        app_uploads.record_retention_error(
            RETENTION_STATE,
            trigger=trigger,
            error=error,
            now_iso=utcnow_fn(),
        )


def run_default_retention_sweep(
    *,
    dry_run: bool,
    trigger: str,
    utcnow_fn: Callable[[], str],
    retention_defaults_payload_fn: Callable[[], dict[str, Any]] = retention_defaults_payload,
    sweep_retention_fn: Callable[[RetentionSweepRequest], dict[str, Any]] | None = None,
    record_retention_success_fn: Callable[..., None] | None = None,
) -> dict[str, Any]:
    defaults = retention_defaults_payload_fn()
    request = RetentionSweepRequest(
        job_max_age_seconds=defaults["job_max_age_seconds"],
        upload_max_age_seconds=defaults["upload_max_age_seconds"],
        dry_run=dry_run,
    )
    if sweep_retention_fn is None:
        result = sweep_retention(request, utcnow_fn=utcnow_fn)
    else:
        result = sweep_retention_fn(request)
    if record_retention_success_fn is None:
        record_retention_success(trigger=trigger, result=result, utcnow_fn=utcnow_fn)
    else:
        record_retention_success_fn(trigger=trigger, result=result)
    return result


def maybe_autorun_retention(
    *,
    utcnow_fn: Callable[[], str],
    retention_defaults_payload_fn: Callable[[], dict[str, Any]] = retention_defaults_payload,
    should_autorun_retention_fn: Callable[..., bool] = app_uploads.should_autorun_retention,
    run_default_retention_sweep_fn: Callable[..., dict[str, Any]] | None = None,
    record_retention_error_fn: Callable[..., None] | None = None,
) -> None:
    defaults = retention_defaults_payload_fn()
    with RETENTION_STATE_LOCK:
        if not should_autorun_retention_fn(defaults=defaults, retention_state=RETENTION_STATE):
            return
    try:
        if run_default_retention_sweep_fn is None:
            run_default_retention_sweep(dry_run=False, trigger="autorun", utcnow_fn=utcnow_fn)
        else:
            run_default_retention_sweep_fn(dry_run=False, trigger="autorun")
    except Exception as exc:
        if record_retention_error_fn is None:
            record_retention_error(trigger="autorun", error=exc, utcnow_fn=utcnow_fn)
        else:
            record_retention_error_fn(trigger="autorun", error=exc)
