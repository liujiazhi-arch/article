from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from thesis_tool.scopes import get_scope_definition


_COVER_SCOPE_TOKENS = frozenset(("cover", *get_scope_definition("cover").aliases))


class CoverFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    thesis_title: str = Field(..., min_length=1, max_length=200)
    college: str = Field(..., min_length=1, max_length=100)
    major: str = Field(..., min_length=1, max_length=100)
    student_name: str = Field(..., min_length=1, max_length=50)
    advisor: str = Field(..., min_length=1, max_length=50)
    completion_date: str = Field(..., min_length=1, max_length=30)

    @field_validator("*")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("封面信息不能包含换行或控制字符")
        return value


def _validate_cover_selection(scopes: list[str] | None, cover_fields: CoverFields | None) -> None:
    tokens = {
        token.strip().lower()
        for scope in scopes or ()
        for token in str(scope).split(",")
        if token.strip()
    }
    cover_selected = "all" not in tokens and bool(tokens & _COVER_SCOPE_TOKENS)
    if cover_selected and cover_fields is None:
        raise ValueError("选择固定封面时必须填写完整封面信息")
    if cover_fields is not None and not cover_selected:
        raise ValueError("填写封面信息前请明确选择固定封面范围")


class AuditRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None


class PlanRequest(BaseModel):
    file_path: str = Field(..., min_length=1)
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None


class UploadPlanRequest(BaseModel):
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
    pdf_matches_docx_confirmed: bool = False
    generate_static_toc: bool = False
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
    cover_fields: CoverFields | None = None
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

    @model_validator(mode="after")
    def validate_cover_fields(self):
        _validate_cover_selection(self.scopes, self.cover_fields)
        return self


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
    cover_fields: CoverFields | None = None
    toc: bool = False
    renumber_headings: bool = False
    layout_rebalance: bool = False
    candidate_mode: str | None = Field(default=None, pattern="^(fast_candidate|compact_candidate)$")
    dry_run: bool = False
    force: bool = False
    stage_input: bool = True
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_cover_fields(self):
        _validate_cover_selection(self.scopes, self.cover_fields)
        return self


class UploadNormalizeRequest(BaseModel):
    output_path: str | None = None
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    stage_input: bool = False
    runtime_root: str | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class UploadRenderReviewRequest(BaseModel):
    pdf_upload_id: str = Field(..., min_length=1)
    pdf_matches_docx_confirmed: bool = False
    generate_static_toc: bool = True
    profile: str = Field(default="lnu")
    strict_profile: bool | None = None
    scopes: list[str] | None = None
    max_attempts: int = Field(default=1, ge=1)
    retry_delay_seconds: float = Field(default=0.0, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)


class RetentionSweepRequest(BaseModel):
    job_max_age_seconds: float | None = Field(default=None, gt=0)
    upload_max_age_seconds: float | None = Field(default=None, gt=0)
    dry_run: bool = False


class RetentionDefaultsRunRequest(BaseModel):
    dry_run: bool = False
