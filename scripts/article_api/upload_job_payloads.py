from __future__ import annotations

import os
from typing import Any

from article_api import storage


def resolve_upload(upload_id: str) -> dict[str, Any]:
    payload = storage.get_upload(upload_id)
    if payload is None:
        raise LookupError(f"Upload not found: {upload_id}")
    stored_path = payload.get("stored_path")
    if not stored_path or not os.path.exists(stored_path):
        raise RuntimeError(f"Uploaded file is unavailable: {upload_id}")
    return payload


def resolve_upload_runtime_root(upload: dict[str, Any], requested_runtime_root: str | None) -> str | None:
    upload_runtime_root = upload.get("runtime_root")
    if requested_runtime_root and upload_runtime_root:
        requested = os.path.abspath(os.path.expanduser(requested_runtime_root))
        existing = os.path.abspath(os.path.expanduser(upload_runtime_root))
        if requested != existing:
            raise ValueError(
                f"Upload {upload['upload_id']} is bound to runtime_root {existing}, got conflicting runtime_root {requested}"
            )
    return upload_runtime_root or requested_runtime_root


def build_verify_upload_job_kwargs(upload_id: str, request, *, resolve_upload_fn=resolve_upload) -> dict[str, Any]:
    upload = resolve_upload_fn(upload_id)
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
    return {
        "file_path": upload["stored_path"],
        "upload_id": upload_id,
        "source_display_name": upload["file_name"],
        "_public_request": public_request,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
        "stage_input": request.stage_input,
        "runtime_root": resolve_upload_runtime_root(upload, request.runtime_root),
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }


def build_apply_upload_job_kwargs(upload_id: str, request, *, resolve_upload_fn=resolve_upload) -> dict[str, Any]:
    upload = resolve_upload_fn(upload_id)
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
    return {
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
        "runtime_root": resolve_upload_runtime_root(upload, request.runtime_root),
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }


def build_normalize_upload_job_kwargs(upload_id: str, request, *, resolve_upload_fn=resolve_upload) -> dict[str, Any]:
    upload = resolve_upload_fn(upload_id)
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
    return {
        "file_path": upload["stored_path"],
        "upload_id": upload_id,
        "source_display_name": upload["file_name"],
        "_public_request": public_request,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
        "stage_input": request.stage_input,
        "runtime_root": resolve_upload_runtime_root(upload, request.runtime_root),
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
