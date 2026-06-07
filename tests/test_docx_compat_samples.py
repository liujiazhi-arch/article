from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import audit_thesis
from article_api.jobs import clear_jobs, create_job, get_job_result, list_jobs, wait_for_job
from article_api.uploads import store_uploaded_docx, validate_docx_package

from .compat_samples import COMPAT_SAMPLES, build_compat_sample


def test_compat_sample_catalog_covers_dirty_docx_structures():
    assert {sample.id for sample in COMPAT_SAMPLES} == {
        "wps_basic",
        "word_toc_field",
        "footnote",
        "comments",
        "revision",
        "floating_image",
        "formula",
        "nested_table",
        "section_break",
        "mixed_dirty_stress",
    }


def test_generated_compat_samples_are_complete_docx_packages_and_uploadable(tmp_path):
    for sample in COMPAT_SAMPLES:
        docx_path = build_compat_sample(sample, tmp_path / "samples")

        assert Path(validate_docx_package(docx_path)) == docx_path.resolve()
        with zipfile.ZipFile(docx_path, "r") as docx_file:
            names = set(docx_file.namelist())
            payload = "\n".join(
                docx_file.read(name).decode("utf-8", errors="ignore")
                for name in names
                if name.endswith(".xml")
            )

        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= names
        for part_name in sample.required_parts:
            assert part_name in names, sample.id
        for marker in sample.required_markers:
            assert marker in payload, sample.id

        class FakeUpload:
            filename = docx_path.name

            def __init__(self):
                self.file = BytesIO(docx_path.read_bytes())

        stored = store_uploaded_docx(FakeUpload(), runtime_root=tmp_path / "runtime")
        assert stored.file_name == docx_path.name
        assert Path(stored.stored_path).exists()


def test_generated_compat_samples_can_run_audit_runtime(tmp_path):
    for sample in COMPAT_SAMPLES:
        docx_path = build_compat_sample(sample, tmp_path / "samples")

        results, score, report, runtime = audit_thesis.audit_docx_with_runtime(str(docx_path), profile_path="lnu")

        assert runtime.profile_id == "lnu-checker-2026"
        assert len(results) == len(runtime.rule_definitions)
        assert isinstance(score, int)
        assert docx_path.name in report


def test_complex_compat_sample_upload_verify_job_and_recent_summary_contract(tmp_path):
    clear_jobs()
    sample = next(item for item in COMPAT_SAMPLES if item.id == "mixed_dirty_stress")
    docx_path = build_compat_sample(sample, tmp_path / "samples")

    class FakeUpload:
        filename = docx_path.name

        def __init__(self):
            self.file = BytesIO(docx_path.read_bytes())

    stored = store_uploaded_docx(FakeUpload(), runtime_root=tmp_path / "runtime")
    job = create_job(
        "verify",
        {
            "file_path": stored.stored_path,
            "upload_id": stored.upload_id,
            "source_display_name": stored.file_name,
            "scopes": ["headings"],
            "stage_input": True,
            "runtime_root": str(tmp_path / "runtime"),
            "_public_request": {
                "upload_id": stored.upload_id,
                "scopes": ["headings"],
                "stage_input": True,
            },
        },
    )
    wait_for_job(job["job_id"])
    result = get_job_result(job["job_id"])
    recent = list_jobs()[0]

    assert result["status"] == "succeeded"
    assert result["summary"]["document_name"] == "mixed_dirty_stress.docx"
    assert result["result"]["document"]["name"] == "mixed_dirty_stress.docx"
    assert "request" not in recent
    assert "resolved_request" not in recent
    assert "runtime" not in recent
    assert recent["summary"]["document_name"] == "mixed_dirty_stress.docx"
    assert recent["display"]["document_name"] == "mixed_dirty_stress.docx"
