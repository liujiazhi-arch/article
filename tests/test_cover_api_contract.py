from __future__ import annotations

import pytest
from pydantic import ValidationError

from article_api.job_execution import handler_request
from article_api.request_payloads import apply_kwargs
from article_api.schemas import ApplyRequest, CoverFields, UploadApplyRequest
from article_api.upload_job_payloads import build_apply_upload_job_kwargs


COVER_FIELDS = {
    "thesis_title": "基于免疫信息学的疫苗设计",
    "college": "生命科学院",
    "major": "生物技术",
    "student_name": "测试学生",
    "advisor": "测试教师",
    "completion_date": "2026年6月",
}


def test_cover_fields_are_complete_and_stripped() -> None:
    fields = CoverFields(**{**COVER_FIELDS, "student_name": "  测试学生  "})

    assert fields.student_name == "测试学生"
    assert fields.model_dump() == COVER_FIELDS


@pytest.mark.parametrize("missing_field", sorted(COVER_FIELDS))
def test_cover_fields_reject_missing_values(missing_field: str) -> None:
    payload = {key: value for key, value in COVER_FIELDS.items() if key != missing_field}

    with pytest.raises(ValidationError):
        CoverFields(**payload)


def test_cover_fields_reject_empty_or_extra_values() -> None:
    with pytest.raises(ValidationError):
        CoverFields(**{**COVER_FIELDS, "advisor": "   "})
    with pytest.raises(ValidationError):
        CoverFields(**COVER_FIELDS, unexpected="不能进入正式论文")


def test_apply_request_requires_explicit_cover_scope_and_complete_fields() -> None:
    with pytest.raises(ValidationError):
        ApplyRequest(file_path="demo.docx", scopes=["cover"])
    with pytest.raises(ValidationError):
        ApplyRequest(file_path="demo.docx", scopes=["page"], cover_fields=COVER_FIELDS)

    request = ApplyRequest(
        file_path="demo.docx",
        scopes=["cover"],
        cover_fields=COVER_FIELDS,
    )

    assert apply_kwargs(request)["cover_fields"] == COVER_FIELDS


@pytest.mark.parametrize("scopes", [["title_page"], ["cover, page"], ["page", "title_page"]])
def test_apply_request_accepts_cover_scope_aliases_and_comma_lists(scopes: list[str]) -> None:
    request = ApplyRequest(file_path="demo.docx", scopes=scopes, cover_fields=COVER_FIELDS)

    assert request.cover_fields is not None


def test_apply_request_does_not_treat_all_as_explicit_cover_scope() -> None:
    with pytest.raises(ValidationError, match="明确选择固定封面"):
        ApplyRequest(file_path="demo.docx", scopes=["all"], cover_fields=COVER_FIELDS)


def test_upload_apply_serializes_cover_fields_into_public_and_worker_requests() -> None:
    request = UploadApplyRequest(scopes=["cover"], cover_fields=COVER_FIELDS)
    upload = {
        "upload_id": "upload-1",
        "stored_path": "/tmp/demo.docx",
        "file_name": "demo.docx",
        "runtime_root": "/tmp/runtime",
    }

    payload = build_apply_upload_job_kwargs(
        "upload-1",
        request,
        resolve_upload_fn=lambda _upload_id: upload,
    )

    assert payload["cover_fields"] == COVER_FIELDS
    assert payload["_public_request"]["cover_fields"] == COVER_FIELDS
    assert handler_request(payload)["cover_fields"] == COVER_FIELDS
