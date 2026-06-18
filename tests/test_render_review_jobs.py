from types import SimpleNamespace

from fastapi.testclient import TestClient
from docx import Document
import pytest

from article_api.app import create_app
from article_api.render_review_jobs import build_render_review_job_kwargs


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _write_docx(path):
    doc = Document()
    doc.add_paragraph("demo")
    doc.save(path)


def test_render_review_job_requires_pdf_upload(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTICLE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    client = TestClient(create_app())
    docx_path = tmp_path / "demo.docx"
    _write_docx(docx_path)

    docx_response = client.post(
        "/uploads/docx",
        files={"file": ("demo.docx", docx_path.read_bytes(), DOCX_MEDIA_TYPE)},
    )
    docx_upload_id = docx_response.json()["upload_id"]

    response = client.post(
        f"/uploads/{docx_upload_id}/render-review-jobs",
        json={"pdf_upload_id": "missing-pdf"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["user_message"] == "没有找到这个 PDF 文件。"


def test_render_review_job_creates_background_render_verify_job(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTICLE_RUNTIME_ROOT", str(tmp_path / "runtime"))
    client = TestClient(create_app())
    docx_path = tmp_path / "demo.docx"
    pdf_path = tmp_path / "demo.pdf"
    _write_docx(docx_path)
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    docx_response = client.post(
        "/uploads/docx",
        files={"file": ("demo.docx", docx_path.read_bytes(), DOCX_MEDIA_TYPE)},
    )
    pdf_response = client.post(
        "/uploads/pdf",
        files={"file": ("demo.pdf", pdf_path.read_bytes(), "application/pdf")},
    )

    response = client.post(
        f"/uploads/{docx_response.json()['upload_id']}/render-review-jobs",
        json={"pdf_upload_id": pdf_response.json()["upload_id"]},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["operation"] == "render-verify"
    assert payload["status"] == "queued"
    assert payload["resolved_request"]["workflow_mode"] == "default_user"
    assert payload["resolved_request"]["rendered_pdf"].endswith(".pdf")


def test_build_render_review_job_kwargs_links_docx_and_pdf_uploads():
    uploads = {
        "docx-1": {
            "file_name": "论文.docx",
            "stored_path": "/tmp/runtime/uploads/paper.docx",
            "runtime_root": "/tmp/runtime",
        },
        "pdf-1": {
            "file_name": "论文.pdf",
            "stored_path": "/tmp/runtime/uploads/paper.pdf",
            "runtime_root": "/tmp/runtime",
        },
    }
    request = SimpleNamespace(
        pdf_upload_id="pdf-1",
        profile="lnu",
        strict_profile=None,
        scopes=None,
        max_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=None,
    )

    payload = build_render_review_job_kwargs(
        "docx-1",
        request,
        resolve_upload_fn=lambda upload_id: uploads[upload_id],
    )

    assert payload["file_path"] == "/tmp/runtime/uploads/paper.docx"
    assert payload["rendered_pdf"] == "/tmp/runtime/uploads/paper.pdf"
    assert payload["workflow_mode"] == "default_user"
    assert payload["source_display_name"] == "论文.docx"
    assert payload["pdf_display_name"] == "论文.pdf"
    assert payload["runtime_root"] == "/tmp/runtime"
    assert payload["_public_request"] == {
        "docx_upload_id": "docx-1",
        "pdf_upload_id": "pdf-1",
    }


def test_build_render_review_job_kwargs_rejects_non_pdf_upload():
    uploads = {
        "docx-1": {"file_name": "论文.docx", "stored_path": "/tmp/paper.docx"},
        "pdf-1": {"file_name": "截图.png", "stored_path": "/tmp/page.png"},
    }
    request = SimpleNamespace(
        pdf_upload_id="pdf-1",
        profile="lnu",
        strict_profile=None,
        scopes=None,
        max_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=None,
    )

    with pytest.raises(ValueError, match="PDF"):
        build_render_review_job_kwargs(
            "docx-1",
            request,
            resolve_upload_fn=lambda upload_id: uploads[upload_id],
        )
