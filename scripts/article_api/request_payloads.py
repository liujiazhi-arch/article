from __future__ import annotations

from typing import Any

from article_api.output_naming import scoped_output_path
from article_api.schemas import (
    ApplyRequest,
    AuditRequest,
    NormalizeJobRequest,
    NormalizeRequest,
    PlanRequest,
    PreflightRequest,
    RenderVerifyRequest,
    VerifyRequest,
)


def audit_kwargs(request: AuditRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
    }


def plan_kwargs(request: PlanRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
    }


def preflight_kwargs(request: PreflightRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
    }


def normalize_kwargs(request: NormalizeRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "output_path": request.output_path,
        "profile_path": request.profile,
        "strict_profile": request.strict_profile,
    }


def normalize_job_kwargs(request: NormalizeJobRequest) -> dict[str, Any]:
    payload = normalize_kwargs(request)
    payload.update(worker_kwargs(request))
    return payload


def render_verify_kwargs(request: RenderVerifyRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "output_dir": request.output_dir,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
        "rendered_pdf": request.rendered_pdf,
        "pdf_matches_docx_confirmed": request.pdf_matches_docx_confirmed,
        "generate_static_toc": request.generate_static_toc,
        "workflow_mode": request.workflow_mode,
    }


def verify_kwargs(request: VerifyRequest) -> dict[str, Any]:
    return {
        "file_path": request.file_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "strict_profile": request.strict_profile,
    }


def verify_job_kwargs(request: VerifyRequest) -> dict[str, Any]:
    payload = verify_kwargs(request)
    payload.update(worker_kwargs(request))
    return payload


def apply_kwargs(request: ApplyRequest) -> dict[str, Any]:
    output_path = request.output_path
    if output_path is None and request.source_display_name:
        output_path = scoped_output_path(
            source_file_path=request.file_path,
            scopes=request.scopes,
            source_display_name=request.source_display_name,
        )
    payload = {
        "file_path": request.file_path,
        "output_path": output_path,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "toc": request.toc,
        "renumber_headings": request.renumber_headings,
        "layout_rebalance": request.layout_rebalance,
        "candidate_mode": request.candidate_mode,
        "strict_profile": request.strict_profile,
        "dry_run": request.dry_run,
        "force": request.force,
    }
    if request.cover_fields:
        payload["cover_fields"] = request.cover_fields.model_dump()
    return payload


def apply_job_kwargs(request: ApplyRequest) -> dict[str, Any]:
    payload = {
        "file_path": request.file_path,
        "output_path": request.output_path,
        "source_display_name": request.source_display_name,
        "profile_path": request.profile,
        "scopes": request.scopes,
        "toc": request.toc,
        "renumber_headings": request.renumber_headings,
        "layout_rebalance": request.layout_rebalance,
        "candidate_mode": request.candidate_mode,
        "strict_profile": request.strict_profile,
        "dry_run": request.dry_run,
        "force": request.force,
    }
    if request.cover_fields:
        payload["cover_fields"] = request.cover_fields.model_dump()
    payload.update(worker_kwargs(request))
    return payload


def worker_kwargs(request) -> dict[str, Any]:
    return {
        "stage_input": request.stage_input,
        "runtime_root": request.runtime_root,
        "max_attempts": request.max_attempts,
        "retry_delay_seconds": request.retry_delay_seconds,
        "timeout_seconds": request.timeout_seconds,
    }
