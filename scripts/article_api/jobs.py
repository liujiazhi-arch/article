from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Lock
import tempfile
from time import monotonic, sleep
from typing import Any, Callable
from uuid import uuid4

import audit_thesis
from article_engine import apply_fix, normalize_document, verify_document
from article_engine.service import _default_output_path
from article_api import storage
from article_api.profile_batch import run_batch_workflow
from article_api.uploads import build_job_workspace, infer_uploaded_docx_name, stage_job_input_docx
from fix_thesis import default_normalize_output_path
from thesis_tool.scopes import normalize_scope_names


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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


@dataclass
class JobRecord:
    job_id: str
    operation: str
    request: dict[str, Any]
    resolved_request: dict[str, Any]
    workspace: dict[str, str] | None
    runtime: dict[str, Any] | None
    status: str
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    summary: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    mode: str = "background"


_BATCH_JOB_SERVICE_NAME = "article-api"
_BATCH_JOB_STAGE = "local-shell-alpha"
_BATCH_JOB_VERSION = "0.1.0"
_BATCH_JOB_API_VERSION = "v0"


def _run_batch_job(**request) -> dict[str, Any]:
    return run_batch_workflow(
        request["operation"],
        request["input_path"],
        profile=request.get("profile", "lnu"),
        strict_profile=request.get("strict_profile"),
        scopes=request.get("scopes"),
        output_dir=request.get("output_dir"),
        summary_file=request.get("summary_file"),
        pattern=request.get("pattern", "*.docx"),
        recursive=bool(request.get("recursive", False)),
        toc=bool(request.get("toc", False)),
        dry_run=bool(request.get("dry_run", False)),
        renumber_headings=bool(request.get("renumber_headings", False)),
        layout_rebalance=bool(request.get("layout_rebalance", False)),
        force=bool(request.get("force", False)),
        fail_fast=bool(request.get("fail_fast", False)),
        service_name=_BATCH_JOB_SERVICE_NAME,
        stage=_BATCH_JOB_STAGE,
        version=_BATCH_JOB_VERSION,
        api_version=_BATCH_JOB_API_VERSION,
    )


_JOB_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "verify": verify_document,
    "apply": apply_fix,
    "normalize": normalize_document,
    "batch": _run_batch_job,
}
HEARTBEAT_STALE_SECONDS_ENV = "ARTICLE_API_JOB_HEARTBEAT_STALE_SECONDS"
RECOVERY_GRACE_SECONDS_ENV = "ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS"
_JOB_LOCK = Lock()
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="article-job-worker")
_ACTIVE_FUTURES: dict[str, Future[Any]] = {}
_FINISHED_STATUSES = {"succeeded", "failed"}
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_ROOT = _PROJECT_ROOT / "scripts"


def _clone_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(payload)


def _coerce_positive_int(value: Any, *, field_name: str, default: int) -> int:
    if value is None:
        return default
    normalized = int(value)
    if normalized < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return normalized


def _coerce_nonnegative_float(value: Any, *, field_name: str, default: float) -> float:
    if value is None:
        return default
    normalized = float(value)
    if normalized < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return normalized


def _coerce_positive_float(value: Any, *, field_name: str) -> float:
    normalized = float(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return normalized


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
    payload = {
        "job_id": record.job_id,
        "operation": record.operation,
        "status": record.status,
        "mode": record.mode,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "request": _clone_dict(record.request),
        "resolved_request": _clone_dict(record.resolved_request),
        "workspace": deepcopy(record.workspace),
        "runtime": deepcopy(record.runtime),
        "result_available": record.status in _FINISHED_STATUSES,
        "summary": deepcopy(record.summary),
        "artifacts": deepcopy(record.artifacts),
        "error": deepcopy(record.error),
    }
    if include_result:
        payload["result"] = deepcopy(record.result)
    return payload


def _inspection_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": payload["job_id"],
        "operation": payload["operation"],
        "status": payload["status"],
        "created_at": payload["created_at"],
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "summary": deepcopy(payload.get("summary")),
        "runtime": deepcopy(payload.get("runtime")),
        "artifacts": deepcopy(payload.get("artifacts")),
        "error": deepcopy(payload.get("error")),
        "cleanup": deepcopy(payload.get("cleanup")),
        "result_available": payload.get("status") in _FINISHED_STATUSES,
    }


def _get_handler(operation: str) -> Callable[..., dict[str, Any]]:
    try:
        return _JOB_HANDLERS[operation]
    except KeyError as exc:
        supported = ", ".join(sorted(_JOB_HANDLERS))
        raise ValueError(f"Unsupported job operation: {operation}. Supported operations: {supported}") from exc


def _resolve_request(operation: str, request: dict[str, Any]) -> dict[str, Any]:
    resolved = _clone_dict(request)
    if operation == "batch":
        resolved["input_path"] = os.path.abspath(os.path.expanduser(str(resolved["input_path"])))
        if not os.path.exists(resolved["input_path"]):
            raise ValueError(f"Batch input path not found: {resolved['input_path']}")
        resolved.setdefault("profile", "lnu")
        normalized_scopes = normalize_scope_names(resolved.get("scopes"))
        resolved["scopes"] = sorted(normalized_scopes) if normalized_scopes else None
        resolved.setdefault("strict_profile", None)
        resolved.setdefault("output_dir", None)
        if resolved["output_dir"] is not None:
            resolved["output_dir"] = os.path.abspath(os.path.expanduser(str(resolved["output_dir"])))
        resolved.setdefault("summary_file", None)
        if resolved["summary_file"] is not None:
            resolved["summary_file"] = os.path.abspath(os.path.expanduser(str(resolved["summary_file"])))
        resolved.setdefault("pattern", "*.docx")
        resolved.setdefault("recursive", False)
        resolved.setdefault("toc", False)
        resolved.setdefault("dry_run", False)
        resolved.setdefault("renumber_headings", False)
        resolved.setdefault("layout_rebalance", False)
        resolved.setdefault("force", False)
        resolved.setdefault("fail_fast", False)
        resolved.setdefault("stage_input", False)
        resolved.setdefault("runtime_root", None)
        if resolved.get("stage_input"):
            raise ValueError("Batch jobs do not support stage_input")
    else:
        resolved["file_path"] = audit_thesis.validate_docx_path(resolved["file_path"])
        resolved["source_display_name"] = resolved.get("source_display_name") or infer_uploaded_docx_name(
            resolved["file_path"]
        )
        resolved.setdefault("stage_input", False)
        resolved.setdefault("runtime_root", None)
        resolved["_explicit_output_path"] = resolved.get("output_path") is not None
    if operation == "apply":
        normalized_scopes = normalize_scope_names(resolved.get("scopes"))
        resolved["scopes"] = sorted(normalized_scopes) if normalized_scopes else None
        resolved.setdefault("output_path", None)
        resolved.setdefault("scopes", None)
        resolved.setdefault("toc", False)
        resolved.setdefault("renumber_headings", False)
        resolved.setdefault("layout_rebalance", False)
        resolved.setdefault("strict_profile", None)
        resolved.setdefault("dry_run", False)
        resolved.setdefault("force", False)
        if resolved["output_path"] is None:
            resolved["output_path"] = _resolve_default_output_path(
                resolved["file_path"],
                resolved["scopes"],
                source_display_name=resolved.get("source_display_name"),
            )
        else:
            resolved["output_path"] = os.path.abspath(os.path.expanduser(str(resolved["output_path"])))
    elif operation == "normalize":
        resolved.setdefault("output_path", None)
        resolved.setdefault("strict_profile", None)
        if resolved["output_path"] is None:
            resolved["output_path"] = _resolve_default_normalize_output_path(
                resolved["file_path"],
                source_display_name=resolved.get("source_display_name"),
            )
        else:
            resolved["output_path"] = os.path.abspath(os.path.expanduser(str(resolved["output_path"])))
    elif operation == "verify":
        normalized_scopes = normalize_scope_names(resolved.get("scopes"))
        resolved["scopes"] = sorted(normalized_scopes) if normalized_scopes else None
        resolved.setdefault("strict_profile", None)
    resolved["max_attempts"] = _coerce_positive_int(
        resolved.get("max_attempts"),
        field_name="max_attempts",
        default=1,
    )
    resolved["retry_delay_seconds"] = _coerce_nonnegative_float(
        resolved.get("retry_delay_seconds"),
        field_name="retry_delay_seconds",
        default=0.0,
    )
    timeout_value = resolved.get("timeout_seconds")
    resolved["timeout_seconds"] = None if timeout_value in (None, "") else _coerce_positive_float(
        timeout_value,
        field_name="timeout_seconds",
    )
    resolved.setdefault("retry_of_job_id", None)
    return resolved


def _result_summary(operation: str, result: dict[str, Any], resolved_request: dict[str, Any]) -> dict[str, Any]:
    source_display_name = resolved_request.get("source_display_name")
    source_file_path = resolved_request.get("source_file_path") or result.get("document", {}).get("path")
    profile_value = result.get("profile")
    profile_id = profile_value.get("id") if isinstance(profile_value, dict) else profile_value
    summary: dict[str, Any] = {
        "document_name": source_display_name
        or (os.path.basename(source_file_path) if source_file_path else result.get("document", {}).get("name")),
        "selected_scopes": deepcopy(result.get("selected_scopes")),
        "profile_id": profile_id,
    }
    if operation == "verify":
        summary["business_status"] = result.get("overall_status")
        summary["readiness"] = result.get("readiness")
        summary["failed_rules"] = result.get("summary", {}).get("failed_rules")
    elif operation == "apply":
        summary["result_mode"] = result.get("mode")
        summary["output_path"] = result.get("output", {}).get("path")
        if result.get("mode") == "preview":
            summary["business_status"] = "preview"
        else:
            summary["business_status"] = result.get("verification", {}).get("overall_status")
            summary["readiness"] = result.get("readiness") or result.get("verification", {}).get("readiness")
            summary["post_verify_notice_count"] = len(result.get("post_verify_notices") or [])
            summary["guard_blocked"] = bool(result.get("guard", {}).get("blocked"))
    elif operation == "normalize":
        summary["output_path"] = result.get("output", {}).get("path")
        summary["business_status"] = result.get("after", {}).get("preflight_status")
        summary["changed"] = bool(result.get("changed"))
        summary["operation_count"] = len(result.get("operations") or [])
    elif operation == "batch":
        batch_summary = result.get("summary") or {}
        summary["document_name"] = os.path.basename(result.get("input_root") or resolved_request.get("input_path") or "batch")
        summary["batch_operation"] = result.get("operation")
        summary["input_path"] = result.get("input_root")
        summary["succeeded_items"] = batch_summary.get("succeeded")
        summary["failed_items"] = batch_summary.get("failed")
        summary["total_items"] = batch_summary.get("total")
        summary["status_counts"] = deepcopy(batch_summary.get("status_counts"))
        summary["readiness_counts"] = deepcopy(batch_summary.get("readiness_counts"))
        summary["output_dir"] = result.get("output_dir")
        summary["summary_file"] = result.get("summary_file")
        summary["business_status"] = "completed"
    if resolved_request.get("dry_run") is not None:
        summary["dry_run"] = bool(resolved_request.get("dry_run"))
    summary["attempt_count"] = int(resolved_request.get("attempt_count") or 1)
    summary["max_attempts"] = int(resolved_request.get("max_attempts") or 1)
    return summary


def _failure_summary(operation: str, resolved_request: dict[str, Any], error: dict[str, Any]) -> dict[str, Any]:
    source_display_name = resolved_request.get("source_display_name")
    source_file_path = resolved_request.get("source_file_path") or resolved_request.get("file_path")
    if operation == "batch":
        source_file_path = resolved_request.get("input_path")
    summary: dict[str, Any] = {
        "document_name": source_display_name or os.path.basename(source_file_path),
        "selected_scopes": deepcopy(resolved_request.get("scopes")),
        "error_code": error["code"],
    }
    if operation == "batch":
        input_path = resolved_request.get("input_path")
        summary["document_name"] = os.path.basename(input_path) if input_path else "batch"
        summary["input_path"] = input_path
        summary["output_dir"] = resolved_request.get("output_dir")
        summary["summary_file"] = resolved_request.get("summary_file")
    if operation in {"apply", "normalize"}:
        summary["output_path"] = resolved_request.get("output_path")
        if operation == "apply":
            guard = error.get("guard") or {}
            summary["guard_blocked"] = bool(guard.get("blocked"))
            summary["guard_warning_count"] = len(guard.get("warnings") or [])
    summary["attempt_count"] = int(resolved_request.get("attempt_count") or 1)
    summary["max_attempts"] = int(resolved_request.get("max_attempts") or 1)
    return summary


def _merge_recovery_summary(
    operation: str,
    resolved_request: dict[str, Any],
    error: dict[str, Any],
    *,
    existing_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    base = _failure_summary(operation, resolved_request, error)
    if not existing_summary:
        return base

    merged = deepcopy(existing_summary)
    merged.setdefault("document_name", base["document_name"])
    merged.setdefault("selected_scopes", base["selected_scopes"])
    if operation == "apply" and base.get("output_path") is not None:
        merged.setdefault("output_path", base["output_path"])
    merged["error_code"] = error["code"]
    merged["attempt_count"] = int(resolved_request.get("attempt_count") or merged.get("attempt_count") or 1)
    merged["max_attempts"] = int(resolved_request.get("max_attempts") or merged.get("max_attempts") or 1)
    return merged


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
    artifacts: list[dict[str, Any]] = []
    input_source_path = resolved_request.get("source_file_path")
    if input_source_path and workspace is not None:
        artifacts.append(
            {
                "kind": "docx",
                "role": "input",
                "path": resolved_request["file_path"],
                "source_path": input_source_path,
                "download_name": resolved_request.get("source_display_name") or os.path.basename(input_source_path),
                "workspace": workspace["inputs"],
                "staged": True,
                "exists_at_completion": os.path.exists(resolved_request["file_path"]),
            }
        )

    if operation not in {"apply", "normalize"}:
        if operation == "batch":
            summary_file = resolved_request.get("summary_file")
            if summary_file:
                artifacts.append(
                    {
                        "kind": "json",
                        "role": "summary",
                        "path": summary_file,
                        "download_name": os.path.basename(summary_file),
                        "workspace": workspace["outputs"] if workspace is not None else None,
                        "exists_at_completion": os.path.exists(summary_file),
                    }
                )
        return artifacts

    output_path = resolved_request.get("output_path")
    if not output_path:
        return artifacts

    mode = result.get("mode") if result else ("normalize" if operation == "normalize" else None)
    wrote_file = bool(status == "succeeded" and mode != "preview")
    artifacts.append(
        {
            "kind": "docx",
            "role": "output",
            "path": output_path,
            "download_name": os.path.basename(output_path),
            "workspace": workspace["outputs"] if workspace is not None else None,
            "result_mode": mode or "failed",
            "written": wrote_file,
            "exists_at_completion": os.path.exists(output_path),
        }
    )
    return artifacts


def _normalize_result_payload(result: dict[str, Any], resolved_request: dict[str, Any]) -> dict[str, Any]:
    source_file_path = resolved_request.get("source_file_path")
    source_display_name = resolved_request.get("source_display_name")
    if not source_file_path and not source_display_name:
        return result
    normalized = deepcopy(result)
    if "document" in normalized and isinstance(normalized["document"], dict):
        if source_file_path:
            normalized["document"]["path"] = source_file_path
        if source_display_name:
            normalized["document"]["name"] = source_display_name
        elif source_file_path:
            normalized["document"]["name"] = os.path.basename(source_file_path)
    return normalized


def _build_runtime_metadata(
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
) -> dict[str, Any]:
    runtime_root = resolved_request.get("runtime_root")
    source_upload_id = resolved_request.get("upload_id")
    source_file_path = resolved_request.get("source_file_path")
    staged_input_path = resolved_request["file_path"] if source_file_path else None
    output_path = resolved_request.get("output_path")
    return {
        "cleanup_policy": "manual",
        "runtime_root": runtime_root,
        "source_upload_id": source_upload_id,
        "input_path": resolved_request.get("input_path"),
        "stage_input_enabled": bool(resolved_request.get("stage_input")),
        "workspace_present": workspace is not None,
        "workspace_root": workspace["root"] if workspace else None,
        "workspace_inputs": workspace["inputs"] if workspace else None,
        "workspace_outputs": workspace["outputs"] if workspace else None,
        "source_file_path": source_file_path,
        "staged_input_path": staged_input_path,
        "output_path": output_path,
        "output_dir": resolved_request.get("output_dir"),
        "summary_file": resolved_request.get("summary_file"),
        "retry_of_job_id": resolved_request.get("retry_of_job_id"),
        "max_attempts": int(resolved_request.get("max_attempts") or 1),
        "retry_delay_seconds": float(resolved_request.get("retry_delay_seconds") or 0.0),
        "timeout_seconds": resolved_request.get("timeout_seconds"),
        "attempt_count": 0,
        "attempts": [],
        "events": [],
        "worker_model": "single",
        "lease_state": "pending",
        "last_heartbeat_at": None,
        "heartbeat_count": 0,
    }


def _normalize_runtime_metadata(
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = _build_runtime_metadata(resolved_request, workspace)
    if runtime:
        normalized.update(deepcopy(runtime))
    return normalized


def _finalize_runtime_metadata(runtime: dict[str, Any]) -> dict[str, Any]:
    finalized = deepcopy(runtime)
    workspace_root = finalized.get("workspace_root")
    staged_input_path = finalized.get("staged_input_path")
    output_path = finalized.get("output_path")
    finalized["workspace_exists_at_completion"] = bool(workspace_root and os.path.exists(workspace_root))
    finalized["staged_input_exists_at_completion"] = bool(staged_input_path and os.path.exists(staged_input_path))
    finalized["output_exists_at_completion"] = bool(output_path and os.path.exists(output_path))
    return finalized


def _handler_request(resolved_request: dict[str, Any]) -> dict[str, Any]:
    payload = _clone_dict(resolved_request)
    payload.pop("stage_input", None)
    payload.pop("runtime_root", None)
    payload.pop("upload_id", None)
    payload.pop("source_file_path", None)
    payload.pop("source_display_name", None)
    payload.pop("max_attempts", None)
    payload.pop("retry_delay_seconds", None)
    payload.pop("timeout_seconds", None)
    payload.pop("retry_of_job_id", None)
    payload.pop("attempt_count", None)
    return payload


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(_SCRIPTS_ROOT) if not python_path else f"{_SCRIPTS_ROOT}{os.pathsep}{python_path}"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _timeout_error_payload(timeout_seconds: float | None) -> dict[str, Any]:
    return {
        "code": "worker_timeout",
        "type": "TimeoutExpired",
        "message": f"Job attempt exceeded timeout of {timeout_seconds} seconds",
        "http_status": 504,
    }


def _transient_internal_error_payload(message: str) -> dict[str, Any]:
    return {
        "code": "internal_error",
        "type": "RuntimeError",
        "message": message,
        "http_status": 500,
    }


def _run_handler_subprocess(operation: str, handler_request: dict[str, Any], *, timeout_seconds: float | None) -> dict[str, Any]:
    request_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump({"operation": operation, "request": handler_request}, handle, ensure_ascii=False, sort_keys=True)
            request_path = handle.name
        completed = subprocess.run(
            [sys.executable, "-m", "article_api.job_runner", request_path],
            cwd=str(_PROJECT_ROOT),
            env=_subprocess_env(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    finally:
        if request_path:
            try:
                os.unlink(request_path)
            except FileNotFoundError:
                pass

    stdout = completed.stdout.strip()
    if not stdout:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"Job runner returned no payload for {operation}: {stderr or 'empty stdout'}")
    payload = json.loads(stdout)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Job runner returned invalid payload type for {operation}")
    return payload


def _execute_job_attempt(operation: str, resolved_request: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = _run_handler_subprocess(
            operation,
            _handler_request(resolved_request),
            timeout_seconds=resolved_request.get("timeout_seconds"),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": _timeout_error_payload(resolved_request.get("timeout_seconds"))}
    except Exception as exc:
        return {"ok": False, "error": _transient_internal_error_payload(str(exc))}
    if not isinstance(payload, dict) or "ok" not in payload:
        return {
            "ok": False,
            "error": _transient_internal_error_payload(f"Malformed job runner payload for {operation}"),
        }
    return payload


def _is_retryable_error(error: dict[str, Any]) -> bool:
    return error.get("code") in {"internal_error", "worker_timeout"}


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
    if lease_state is not None:
        runtime["lease_state"] = lease_state


def _resolve_default_output_path(file_path: str, scopes, *, source_display_name: str | None) -> str:
    if not source_display_name:
        return _default_output_path(file_path, scopes)
    source = Path(file_path)
    display_path = Path(source_display_name)
    normalized_scopes = normalize_scope_names(scopes)
    if normalized_scopes:
        output_name = f"{display_path.stem}_{'_'.join(sorted(normalized_scopes))}{display_path.suffix or '.docx'}"
    else:
        output_name = display_path.name
    return str(source.with_name(output_name))


def _resolve_default_normalize_output_path(file_path: str, *, source_display_name: str | None) -> str:
    if not source_display_name:
        return default_normalize_output_path(file_path)
    source = Path(file_path)
    display_path = Path(source_display_name)
    output_name = f"{display_path.stem}_normalized{display_path.suffix or '.docx'}"
    return str(source.with_name(output_name))


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
    now_dt = _parse_timestamp(_utcnow())
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
        runtime = payload.get("runtime") or {}
        last_seen = (
            runtime.get("last_heartbeat_at")
            or payload.get("updated_at")
            or payload.get("started_at")
            or payload.get("created_at")
        )
        last_seen_dt = _parse_timestamp(last_seen)
        if now_dt is not None and last_seen_dt is not None:
            age_seconds = max((now_dt - last_seen_dt).total_seconds(), 0.0)
            if age_seconds < grace_seconds:
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
    now_dt = _parse_timestamp(_utcnow())
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
            last_seen = (
                runtime.get("last_heartbeat_at")
                or payload.get("updated_at")
                or payload.get("started_at")
                or payload.get("created_at")
            )
            last_seen_dt = _parse_timestamp(last_seen)
            if last_seen_dt is not None and now_dt is not None:
                age_seconds = max((now_dt - last_seen_dt).total_seconds(), 0.0)
                if age_seconds < recovery_grace_seconds:
                    recovery_pending_job_ids.append(payload["job_id"])
            continue
        if payload["status"] != "running" or payload["job_id"] not in active_future_job_id_set:
            continue
        heartbeat_dt = _parse_timestamp(runtime.get("last_heartbeat_at"))
        if heartbeat_dt is None or now_dt is None:
            continue
        heartbeat_age_seconds = max((now_dt - heartbeat_dt).total_seconds(), 0.0)
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
    return [_inspection_from_payload(payload) for payload in payloads]


def _resolved_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    return Path(path_value).expanduser().resolve()


def _is_within(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _cleanup_candidate_map(payload: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    runtime = payload.get("runtime") or {}
    runtime_root = _resolved_path(runtime.get("runtime_root"))
    workspace_root = _resolved_path(runtime.get("workspace_root"))
    candidates: dict[str, dict[str, str]] = {}
    skipped_paths: list[str] = []

    def add_candidate(path_value: str | None, *, kind: str) -> None:
        candidate_path = _resolved_path(path_value)
        if candidate_path is None:
            return
        candidate_key = str(candidate_path)
        if workspace_root is not None and candidate_path != workspace_root and _is_within(candidate_path, workspace_root):
            return
        if workspace_root is not None and candidate_path == workspace_root:
            candidates[candidate_key] = {"path": candidate_key, "kind": kind}
            return
        if _is_within(candidate_path, runtime_root):
            candidates.setdefault(candidate_key, {"path": candidate_key, "kind": kind})
            return
        skipped_paths.append(candidate_key)

    add_candidate(runtime.get("workspace_root"), kind="workspace")
    # Upload lifecycle is managed by the upload registry/cleanup endpoints.
    # Job cleanup only removes per-job runtime data and materialized artifacts.
    for artifact in payload.get("artifacts") or []:
        add_candidate(artifact.get("path"), kind=f"artifact:{artifact.get('role') or 'unknown'}")
    return candidates, skipped_paths


def cleanup_job(job_id: str, *, policy: str = "manual") -> dict[str, Any]:
    payload = storage.get_job(job_id, include_result=True)
    if payload is None:
        raise LookupError(f"Job not found: {job_id}")
    if payload["status"] not in _FINISHED_STATUSES:
        raise RuntimeError(f"Job cleanup is only available after completion: {job_id}")

    candidates, skipped_paths = _cleanup_candidate_map(payload)
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
        "cleaned_at": _utcnow(),
        "attempt_count": int(previous_cleanup.get("attempt_count") or 0) + 1,
        "removed_paths": removed_paths,
        "missing_paths": missing_paths,
        "skipped_paths": sorted(set(skipped_paths)),
    }
    storage.upsert_job_cleanup(job_id, cleanup_payload)
    return get_job(job_id)


def sweep_job_retention(max_age_seconds: float, *, now: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    threshold_seconds = _coerce_positive_float(max_age_seconds, field_name="job_max_age_seconds")
    reference_time = now or _utcnow()
    reference_dt = _parse_timestamp(reference_time)
    if reference_dt is None:
        raise ValueError("Retention reference time is required")

    _reconcile_incomplete_jobs()
    payloads = storage.list_jobs(include_result=True)
    report = {
        "policy": "retention",
        "dry_run": bool(dry_run),
        "max_age_seconds": threshold_seconds,
        "reference_time": reference_time,
        "inspected_count": len(payloads),
        "eligible_count": 0,
        "cleaned_count": 0,
        "noop_count": 0,
        "skipped_count": 0,
        "items": [],
    }

    for payload in payloads:
        if payload["status"] not in _FINISHED_STATUSES:
            report["skipped_count"] += 1
            continue
        if payload.get("cleanup") is not None:
            report["skipped_count"] += 1
            continue
        finished_at = payload.get("finished_at")
        finished_dt = _parse_timestamp(finished_at)
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

        cleaned_payload = cleanup_job(payload["job_id"], policy="retention")
        cleanup = deepcopy(cleaned_payload.get("cleanup")) or {}
        item["action"] = "cleaned"
        item["cleanup"] = cleanup
        if cleanup.get("state") == "cleaned":
            report["cleaned_count"] += 1
        else:
            report["noop_count"] += 1
        report["items"].append(item)

    return report


def _finalize_record(record: JobRecord) -> None:
    if record.runtime is not None:
        record.runtime = _finalize_runtime_metadata(record.runtime)
    record.finished_at = _utcnow()
    record.updated_at = record.finished_at
    storage.upsert_job(_serialize_job(record, include_result=True))


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
    _append_runtime_event(record.runtime, event="worker_started", operation=record.operation, job_status=record.status)
    storage.upsert_job(_serialize_job(record, include_result=True))
    max_attempts = int(record.resolved_request.get("max_attempts") or 1)
    retry_delay_seconds = float(record.resolved_request.get("retry_delay_seconds") or 0.0)
    current_attempt: int | None = None
    try:
        for attempt in range(1, max_attempts + 1):
            current_attempt = attempt
            _heartbeat_runtime(record.runtime)
            _append_runtime_event(
                record.runtime,
                event="attempt_started",
                operation=record.operation,
                job_status=record.status,
                attempt=attempt,
            )
            record.updated_at = _utcnow()
            storage.upsert_job(_serialize_job(record, include_result=True))
            attempt_payload = _execute_job_attempt(record.operation, record.resolved_request)
            record.resolved_request["attempt_count"] = attempt
            if attempt_payload.get("ok"):
                record.result = _normalize_result_payload(
                    attempt_payload["result"],
                    record.resolved_request,
                )
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
                record.artifacts = _build_artifacts(
                    record.operation,
                    record.resolved_request,
                    record.workspace,
                    result=record.result,
                    status=record.status,
                )
                break

            error = deepcopy(attempt_payload.get("error") or _transient_internal_error_payload("Unknown job runner failure"))
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
            _append_runtime_event(
                record.runtime,
                event="job_failed",
                operation=record.operation,
                job_status=record.status,
                attempt=attempt,
                error=error,
            )
            record.summary = _failure_summary(record.operation, record.resolved_request, record.error)
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
    if payload["operation"] == "batch":
        execution_request["input_path"] = resolved_request.get("input_path") or request.get("input_path")
    elif upload_id:
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
    return payload


def inspect_job(job_id: str) -> dict[str, Any]:
    payload = get_job(job_id)
    return _inspection_from_payload(payload)


def get_job_result(job_id: str) -> dict[str, Any]:
    _reconcile_incomplete_jobs()
    payload = storage.get_job(job_id, include_result=True)
    if payload is None:
        raise LookupError(f"Job not found: {job_id}")
    if payload["status"] not in _FINISHED_STATUSES:
        raise RuntimeError(f"Job result is not ready yet: {job_id}")
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
