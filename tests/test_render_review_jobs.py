from types import SimpleNamespace
import time
from pathlib import Path

from fastapi.testclient import TestClient
from docx import Document
from PIL import Image
import pytest

from article_api.app import create_app
from article_api.job_execution import handler_request
from article_api.render_review_jobs import build_render_review_job_kwargs


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _write_docx(path):
    doc = Document()
    doc.add_paragraph("demo")
    doc.save(path)


def _write_pdf(path, page_count):
    pages = [Image.new("RGB", (120, 160), "white") for _ in range(page_count)]
    pages[0].save(path, "PDF", save_all=True, append_images=pages[1:], resolution=72)
    for page in pages:
        page.close()


def _wait_for_job(client, job_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        payload = client.get(f"/jobs/{job_id}").json()
        if payload["status"] in {"succeeded", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {job_id}")


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
    assert payload["workspace"] is not None
    assert f"jobs/{payload['job_id']}/inputs" in payload["resolved_request"]["file_path"]


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
    assert payload["stage_input"] is True
    assert payload["_public_request"] == {
        "docx_upload_id": "docx-1",
        "pdf_upload_id": "pdf-1",
    }


def test_render_review_worker_request_omits_display_metadata():
    request = handler_request(
        {
            "file_path": "/tmp/paper.docx",
            "rendered_pdf": "/tmp/paper.pdf",
            "docx_upload_id": "docx-1",
            "pdf_upload_id": "pdf-1",
            "workflow_mode": "default_user",
            "pdf_display_name": "论文.pdf",
        }
    )

    assert request == {
        "file_path": "/tmp/paper.docx",
        "rendered_pdf": "/tmp/paper.pdf",
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


def test_render_review_jobs_keep_page_evidence_in_separate_workspaces(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_RUNTIME_ROOT", str(tmp_path / "runtime"))
    docx_path = tmp_path / "paper.docx"
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    _write_docx(docx_path)
    _write_pdf(first_pdf, 2)
    _write_pdf(second_pdf, 1)

    with TestClient(create_app()) as client:
        docx_upload = client.post(
            "/uploads/docx",
            files={"file": (docx_path.name, docx_path.read_bytes(), DOCX_MEDIA_TYPE)},
        ).json()
        results = []
        for pdf_path in (first_pdf, second_pdf):
            pdf_upload = client.post(
                "/uploads/pdf",
                files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
            ).json()
            job = client.post(
                f"/uploads/{docx_upload['upload_id']}/render-review-jobs",
                json={"pdf_upload_id": pdf_upload["upload_id"]},
            ).json()
            assert _wait_for_job(client, job["job_id"])["status"] == "succeeded"
            results.append(client.get(f"/jobs/{job['job_id']}/result").json()["result"])

    assert results[0]["page_count"] == 2
    assert results[1]["page_count"] == 1
    assert results[0]["output_dir"] != results[1]["output_dir"]
    assert all(Path(page_path).exists() for page_path in results[0]["page_images"])


def test_render_review_job_retry_restores_both_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_RUNTIME_ROOT", str(tmp_path / "runtime"))
    docx_path = tmp_path / "paper.docx"
    pdf_path = tmp_path / "paper.pdf"
    _write_docx(docx_path)
    _write_pdf(pdf_path, 1)

    with TestClient(create_app()) as client:
        docx_upload = client.post(
            "/uploads/docx",
            files={"file": (docx_path.name, docx_path.read_bytes(), DOCX_MEDIA_TYPE)},
        ).json()
        pdf_upload = client.post(
            "/uploads/pdf",
            files={"file": (pdf_path.name, pdf_path.read_bytes(), "application/pdf")},
        ).json()
        first = client.post(
            f"/uploads/{docx_upload['upload_id']}/render-review-jobs",
            json={"pdf_upload_id": pdf_upload["upload_id"], "scopes": ["toc"]},
        ).json()
        assert _wait_for_job(client, first["job_id"])["status"] == "succeeded"
        first_result = client.get(f"/jobs/{first['job_id']}/result").json()["result"]

        retry_response = client.post(f"/jobs/{first['job_id']}/retry")

        assert retry_response.status_code == 201
        retried = retry_response.json()
        retried_status = _wait_for_job(client, retried["job_id"])
        assert retried_status["status"] == "succeeded", client.get(
            f"/jobs/{retried['job_id']}/result"
        ).json()
        assert retried["request"]["docx_upload_id"] == docx_upload["upload_id"]
        assert retried["request"]["pdf_upload_id"] == pdf_upload["upload_id"]
        assert retried["workspace"] is not None
        assert retried["resolved_request"]["stage_input"] is True
        assert retried["resolved_request"]["scopes"] == ["toc"]
        retried_result = client.get(f"/jobs/{retried['job_id']}/result").json()["result"]
        assert retried_result["output_dir"] != first_result["output_dir"]
