from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from typing import Any, Callable

import audit_thesis
from article_api.output_naming import normalize_output_path, scoped_output_path
from article_api.uploads import infer_uploaded_docx_name
from fix_thesis import default_normalize_output_path
from thesis_tool.scopes import normalize_scope_names


def clone_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(payload)


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


def serialize_job(record: JobRecord, *, include_result: bool, finished_statuses: set[str]) -> dict[str, Any]:
    payload = {
        "job_id": record.job_id,
        "operation": record.operation,
        "status": record.status,
        "mode": record.mode,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "request": clone_dict(record.request),
        "resolved_request": clone_dict(record.resolved_request),
        "workspace": deepcopy(record.workspace),
        "runtime": deepcopy(record.runtime),
        "result_available": record.status in finished_statuses,
        "summary": deepcopy(record.summary),
        "artifacts": deepcopy(record.artifacts),
        "error": deepcopy(record.error),
    }
    if include_result:
        payload["result"] = deepcopy(record.result)
    return payload


def inspection_from_payload(payload: dict[str, Any], *, finished_statuses: set[str]) -> dict[str, Any]:
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
        "result_available": payload.get("status") in finished_statuses,
    }


def coerce_positive_int(value: Any, *, field_name: str, default: int) -> int:
    if value is None:
        return default
    normalized = int(value)
    if normalized < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return normalized


def coerce_nonnegative_float(value: Any, *, field_name: str, default: float) -> float:
    if value is None:
        return default
    normalized = float(value)
    if normalized < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return normalized


def coerce_positive_float(value: Any, *, field_name: str) -> float:
    normalized = float(value)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return normalized


def resolve_default_output_path(
    file_path: str,
    scopes,
    *,
    source_display_name: str | None,
    default_output_path: Callable[[str, Any], str],
) -> str:
    if not source_display_name:
        return default_output_path(file_path, scopes)
    return scoped_output_path(source_file_path=file_path, scopes=scopes, source_display_name=source_display_name)


def resolve_default_normalize_output_path(file_path: str, *, source_display_name: str | None) -> str:
    if not source_display_name:
        return default_normalize_output_path(file_path)
    return normalize_output_path(source_file_path=file_path, source_display_name=source_display_name)


def resolve_request(
    operation: str,
    request: dict[str, Any],
    *,
    default_output_path: Callable[[str, Any], str],
) -> dict[str, Any]:
    resolved = clone_dict(request)
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
            resolved["output_path"] = resolve_default_output_path(
                resolved["file_path"],
                resolved["scopes"],
                source_display_name=resolved.get("source_display_name"),
                default_output_path=default_output_path,
            )
        else:
            resolved["output_path"] = os.path.abspath(os.path.expanduser(str(resolved["output_path"])))
    elif operation == "normalize":
        resolved.setdefault("output_path", None)
        resolved.setdefault("strict_profile", None)
        if resolved["output_path"] is None:
            resolved["output_path"] = resolve_default_normalize_output_path(
                resolved["file_path"],
                source_display_name=resolved.get("source_display_name"),
            )
        else:
            resolved["output_path"] = os.path.abspath(os.path.expanduser(str(resolved["output_path"])))
    elif operation == "verify":
        normalized_scopes = normalize_scope_names(resolved.get("scopes"))
        resolved["scopes"] = sorted(normalized_scopes) if normalized_scopes else None
        resolved.setdefault("strict_profile", None)
    resolved["max_attempts"] = coerce_positive_int(
        resolved.get("max_attempts"),
        field_name="max_attempts",
        default=1,
    )
    resolved["retry_delay_seconds"] = coerce_nonnegative_float(
        resolved.get("retry_delay_seconds"),
        field_name="retry_delay_seconds",
        default=0.0,
    )
    timeout_value = resolved.get("timeout_seconds")
    resolved["timeout_seconds"] = None if timeout_value in (None, "") else coerce_positive_float(
        timeout_value,
        field_name="timeout_seconds",
    )
    resolved.setdefault("retry_of_job_id", None)
    return resolved


def build_result_summary(operation: str, result: dict[str, Any], resolved_request: dict[str, Any]) -> dict[str, Any]:
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
    if resolved_request.get("dry_run") is not None:
        summary["dry_run"] = bool(resolved_request.get("dry_run"))
    summary["attempt_count"] = int(resolved_request.get("attempt_count") or 1)
    summary["max_attempts"] = int(resolved_request.get("max_attempts") or 1)
    return summary


def build_failure_summary(operation: str, resolved_request: dict[str, Any], error: dict[str, Any]) -> dict[str, Any]:
    source_display_name = resolved_request.get("source_display_name")
    source_file_path = resolved_request.get("source_file_path") or resolved_request.get("file_path")
    summary: dict[str, Any] = {
        "document_name": source_display_name or os.path.basename(source_file_path),
        "selected_scopes": deepcopy(resolved_request.get("scopes")),
        "error_code": error["code"],
    }
    if operation in {"apply", "normalize"}:
        summary["output_path"] = resolved_request.get("output_path")
        if operation == "apply":
            guard = error.get("guard") or {}
            summary["guard_blocked"] = bool(guard.get("blocked"))
            summary["guard_warning_count"] = len(guard.get("warnings") or [])
    summary["attempt_count"] = int(resolved_request.get("attempt_count") or 1)
    summary["max_attempts"] = int(resolved_request.get("max_attempts") or 1)
    return summary


def merge_recovery_summary(
    operation: str,
    resolved_request: dict[str, Any],
    error: dict[str, Any],
    *,
    existing_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    base = build_failure_summary(operation, resolved_request, error)
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


def normalize_result_payload(result: dict[str, Any], resolved_request: dict[str, Any]) -> dict[str, Any]:
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


def build_runtime_metadata(
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


def normalize_runtime_metadata(
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = build_runtime_metadata(resolved_request, workspace)
    if runtime:
        normalized.update(deepcopy(runtime))
    return normalized
