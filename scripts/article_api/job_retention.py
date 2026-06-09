from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import Any, Callable

from article_api.retention_reports import build_retention_sweep_report, with_cleanup_result


def cleanup_job(
    job_id: str,
    *,
    policy: str,
    finished_statuses: set[str],
    get_job_payload_fn: Callable[[str], dict[str, Any] | None],
    upsert_job_cleanup_fn: Callable[[str, dict[str, Any]], None],
    get_job_fn: Callable[[str], dict[str, Any]],
    cleanup_candidate_map_fn: Callable[[dict[str, Any]], tuple[dict[str, dict[str, str]], list[str]]],
    utcnow_fn: Callable[[], str],
) -> dict[str, Any]:
    payload = get_job_payload_fn(job_id)
    if payload is None:
        raise LookupError(f"Job not found: {job_id}")
    if payload["status"] not in finished_statuses:
        raise RuntimeError(f"Job cleanup is only available after completion: {job_id}")

    candidates, skipped_paths = cleanup_candidate_map_fn(payload)
    removed_paths: list[str] = []
    missing_paths: list[str] = []
    for item in candidates.values():
        candidate_path = Path(item["path"])
        if not candidate_path.exists():
            missing_paths.append(str(candidate_path))
            continue
        if candidate_path.is_dir():
            shutil.rmtree(candidate_path)
        else:
            candidate_path.unlink()
        removed_paths.append(str(candidate_path))

    previous_cleanup = payload.get("cleanup") or {}
    cleanup_payload = {
        "policy": policy,
        "state": "cleaned" if removed_paths else "noop",
        "cleaned_at": utcnow_fn(),
        "attempt_count": int(previous_cleanup.get("attempt_count") or 0) + 1,
        "removed_paths": removed_paths,
        "missing_paths": missing_paths,
        "skipped_paths": sorted(set(skipped_paths)),
    }
    upsert_job_cleanup_fn(job_id, cleanup_payload)
    return get_job_fn(job_id)


def sweep_job_retention(
    max_age_seconds: float,
    *,
    now: str | None,
    dry_run: bool,
    finished_statuses: set[str],
    utcnow_fn: Callable[[], str],
    coerce_positive_float_fn: Callable[..., float],
    parse_timestamp_fn: Callable[[str | None], datetime | None],
    reconcile_incomplete_jobs_fn: Callable[[], None],
    list_jobs_fn: Callable[[], list[dict[str, Any]]],
    cleanup_job_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    threshold_seconds = coerce_positive_float_fn(max_age_seconds, field_name="job_max_age_seconds")
    reference_time = now or utcnow_fn()
    reference_dt = parse_timestamp_fn(reference_time)
    if reference_dt is None:
        raise ValueError("Retention reference time is required")

    reconcile_incomplete_jobs_fn()
    payloads = list_jobs_fn()
    report = build_retention_sweep_report(
        max_age_seconds=threshold_seconds,
        reference_time=reference_time,
        dry_run=dry_run,
        inspected_count=len(payloads),
    )

    for payload in payloads:
        if payload["status"] not in finished_statuses:
            report["skipped_count"] += 1
            continue
        if payload.get("cleanup") is not None:
            report["skipped_count"] += 1
            continue
        finished_at = payload.get("finished_at")
        finished_dt = parse_timestamp_fn(finished_at)
        if finished_dt is None:
            report["skipped_count"] += 1
            continue
        age_seconds = max((reference_dt - finished_dt).total_seconds(), 0.0)
        if age_seconds < threshold_seconds:
            report["skipped_count"] += 1
            continue

        report["eligible_count"] += 1
        item = {
            "job_id": payload["job_id"],
            "status": payload["status"],
            "finished_at": finished_at,
            "age_seconds": round(age_seconds, 3),
        }
        if dry_run:
            item["action"] = "would_clean"
            report["items"].append(item)
            continue

        cleaned_payload = cleanup_job_fn(payload["job_id"], policy="retention")
        report = with_cleanup_result(report, item, cleaned_payload.get("cleanup"))

    return report
