from __future__ import annotations

from pydantic import BaseModel, Field


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
    workflow_mode: str | None = Field(default=None, pattern="^(default_user|agent_candidate)$")


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
    source_display_name: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    toc: bool = False
    renumber_headings: bool = False
    layout_rebalance: bool = False
    candidate_mode: str | None = Field(default=None, pattern="^(fast_candidate|compact_candidate)$")
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
    candidate_mode: str | None = Field(default=None, pattern="^(fast_candidate|compact_candidate)$")
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
