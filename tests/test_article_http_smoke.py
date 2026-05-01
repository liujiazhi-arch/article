from __future__ import annotations

import importlib.util
from pathlib import Path
import time

from docx import Document
import pytest

from .conftest import RULE_MUTATORS, make_compliant_doc


_HTTP_RUNTIME_READY = (
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None
)
pytestmark = pytest.mark.skipif(
    not _HTTP_RUNTIME_READY,
    reason="requires fastapi + httpx in the active interpreter",
)

if _HTTP_RUNTIME_READY:  # pragma: no branch
    from fastapi.testclient import TestClient
    import article_api.app as app_module
    from article_api.app import create_app


def _make_style_conflict_lnu_doc(source_path: Path) -> Path:
    doc = Document()
    heading = doc.add_paragraph("1 绪论")
    heading.style = doc.styles["Heading 1"]
    conflict = doc.add_paragraph("3.6 分子对接验证结果")
    conflict.style = doc.styles["Heading 1"]
    doc.add_paragraph("这是正文示例。")
    doc.save(source_path)
    return source_path


def _make_client(monkeypatch, state_root: Path) -> TestClient:
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(state_root))
    return TestClient(create_app())


def _wait_for_job_completion(client: TestClient, job_id: str) -> dict[str, object]:
    for _ in range(150):
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        if status_payload["status"] in {"succeeded", "failed"}:
            return status_payload
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for HTTP job completion: {job_id}")


def _upload_docx(client: TestClient, source_path: Path, runtime_root: Path) -> dict[str, object]:
    with open(source_path, "rb") as handle:
        upload_response = client.post(
            "/uploads/docx",
            params={"runtime_root": str(runtime_root)},
            files={
                "file": (
                    source_path.name,
                    handle,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert upload_response.status_code == 201
    return upload_response.json()


def test_live_http_upload_apply_result_download_and_cleanup(monkeypatch, tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="article_http_smoke.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    runtime_root = tmp_path / "runtime"
    client = _make_client(monkeypatch, tmp_path / "state")

    health_response = client.get("/health")
    console_response = client.get("/")
    ready_response = client.get("/ready")
    version_response = client.get("/version")
    profiles_response = client.get("/profiles")
    runtime_response = client.get("/ops/runtime")
    storage_response = client.get("/ops/storage")
    assert console_response.status_code == 200
    assert health_response.status_code == 200
    assert ready_response.status_code == 200
    assert version_response.status_code == 200
    assert profiles_response.status_code == 200
    assert runtime_response.status_code == 200
    assert storage_response.status_code == 200
    assert "论文格式本地控制台" in console_response.text
    assert health_response.json()["service"] == "article-api"
    assert ready_response.json()["status"] == "ready"
    assert ready_response.json()["checks"]["runtime_root"]["status"] == "ok"
    assert version_response.json()["api_version"] == "v0"
    profiles_payload = profiles_response.json()
    assert any(item["id"] == "lnu-checker-2026" for item in profiles_payload["profiles"])
    assert any(item["id"] == "school_degree_thesis" for item in profiles_payload["summary"]["support_scenarios"])
    lnu_profile = next(item for item in profiles_payload["profiles"] if item["id"] == "lnu-checker-2026")
    assert any(item["label"] == "学校学位论文" for item in lnu_profile["support_scenarios"])
    assert runtime_response.json()["runtime"]["worker_model"] == "single"
    assert runtime_response.json()["runtime"]["recovery"]["strategy"] == "fail_unfinished_without_active_worker_future"
    assert storage_response.json()["storage"]["integrity_check"] == "ok"

    preflight_source = _make_style_conflict_lnu_doc(tmp_path / "article_http_preflight.docx")
    preflight_response = client.post(
        "/preflight",
        json={
            "file_path": str(preflight_source),
            "profile": "lnu",
        },
    )
    assert preflight_response.status_code == 200
    preflight_payload = preflight_response.json()
    assert preflight_payload["operation"] == "preflight"
    assert preflight_payload["preflight_status"] == "blocked"
    assert preflight_payload["summary"]["wild_doc_detected"] is True
    assert any(item["id"] == "style_text_conflicts" for item in preflight_payload["wild_doc"]["signals"])

    normalize_response = client.post(
        "/normalize",
        json={
            "file_path": str(preflight_source),
            "output_path": str(tmp_path / "article_http_preflight_normalized.docx"),
            "profile": "lnu",
        },
    )
    assert normalize_response.status_code == 200
    normalize_payload = normalize_response.json()
    assert normalize_payload["operation"] == "normalize"
    assert normalize_payload["changed"] is True
    assert normalize_payload["summary"]["before_preflight_status"] == "blocked"
    assert normalize_payload["summary"]["after_preflight_status"] == "warning"
    assert normalize_payload["wild_doc"]["after"]["style_conflict_count"] == 0

    normalize_job_response = client.post(
        "/jobs/normalize",
        json={
            "file_path": str(preflight_source),
            "output_path": str(tmp_path / "article_http_preflight_job_normalized.docx"),
            "profile": "lnu",
        },
    )
    assert normalize_job_response.status_code == 201
    normalize_job_payload = normalize_job_response.json()
    normalize_job_status = _wait_for_job_completion(client, normalize_job_payload["job_id"])
    assert normalize_job_status["status"] == "succeeded"
    normalize_job_result = client.get(f"/jobs/{normalize_job_payload['job_id']}/result")
    assert normalize_job_result.status_code == 200
    assert normalize_job_result.json()["summary"]["business_status"] == "warning"
    assert normalize_job_result.json()["result"]["after"]["preflight_status"] == "warning"

    monkeypatch.setattr(
        app_module,
        "render_verify_document",
        lambda *args, **kwargs: {
            "document": {"path": str(source_path), "name": source_path.name},
            "profile": {"id": "lnu-checker-2026", "requested": "lnu", "fallback_used": False, "display": "lnu"},
            "output_dir": str(tmp_path / "http-render-proof"),
            "render_engine": "artifact-tool",
            "page_count": 1,
            "page_images": [str(tmp_path / "http-render-proof" / "page-1.png")],
            "selected_scopes": ["toc"],
            "overall_status": "verified",
            "readiness": "render-check-required",
            "manual_review_rule_ids": ["LNU_TOC03"],
            "unsupported_rule_ids": [],
            "review_items": ["目录需要刷新后复核页码。"],
            "report_path": str(tmp_path / "http-render-proof" / "render_verify_report.json"),
        },
    )
    render_verify_response = client.post(
        "/render-verify",
        json={
            "file_path": str(source_path),
            "profile": "lnu",
            "scopes": ["toc"],
        },
    )
    assert render_verify_response.status_code == 200
    render_verify_payload = render_verify_response.json()
    assert render_verify_payload["operation"] == "render-verify"
    assert render_verify_payload["page_count"] == 1
    assert render_verify_payload["summary"]["manual_review_rule_count"] == 1
    assert render_verify_payload["selected_scopes"] == ["toc"]

    batch_dir = tmp_path / "http-batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_source = batch_dir / source_path.name
    batch_source.write_bytes(source_path.read_bytes())
    batch_response = client.post(
        "/batch",
        json={
            "operation": "audit",
            "input_path": str(batch_dir),
            "profile": "cn-common",
            "recursive": True,
        },
    )
    assert batch_response.status_code == 200
    batch_payload = batch_response.json()
    assert batch_payload["summary"]["total"] == 1
    assert batch_payload["summary"]["readiness_counts"]["needs-fix"] == 1
    assert batch_payload["items"][0]["relative_path"] == source_path.name
    assert batch_payload["items"][0]["readiness"] == "needs-fix"

    batch_job_response = client.post(
        "/jobs/batch",
        json={
            "operation": "audit",
            "input_path": str(batch_dir),
            "profile": "cn-common",
            "recursive": True,
            "summary_file": str(tmp_path / "http-batch-summary.json"),
        },
    )
    assert batch_job_response.status_code == 201
    batch_job_payload = batch_job_response.json()
    batch_job_status = _wait_for_job_completion(client, batch_job_payload["job_id"])
    assert batch_job_status["status"] == "succeeded"
    batch_job_result = client.get(f"/jobs/{batch_job_payload['job_id']}/result")
    assert batch_job_result.status_code == 200
    assert batch_job_result.json()["summary"]["batch_operation"] == "audit"
    assert batch_job_result.json()["summary"]["readiness_counts"]["needs-fix"] == 1
    batch_summary_download = client.get(f"/jobs/{batch_job_payload['job_id']}/artifacts/summary/download")
    assert batch_summary_download.status_code == 200
    assert batch_summary_download.json()["summary"]["total"] == 1
    filtered_jobs_response = client.get("/jobs", params={"operation": "batch", "status": "succeeded", "limit": 1})
    assert filtered_jobs_response.status_code == 200
    filtered_jobs_payload = filtered_jobs_response.json()
    assert len(filtered_jobs_payload) == 1
    assert filtered_jobs_payload[0]["operation"] == "batch"
    recent_batches_response = client.get("/jobs/batches/recent", params={"status": "succeeded", "limit": 5})
    assert recent_batches_response.status_code == 200
    recent_batches_payload = recent_batches_response.json()
    assert recent_batches_payload["filters"]["operation"] == "batch"
    assert recent_batches_payload["items"][0]["job_id"] == batch_job_payload["job_id"]

    upload_payload = _upload_docx(client, source_path, runtime_root)
    assert upload_payload["file_name"] == "article_http_smoke.docx"

    uploads_response = client.get("/uploads")
    upload_view_response = client.get(f"/uploads/{upload_payload['upload_id']}")
    assert uploads_response.status_code == 200
    assert upload_view_response.status_code == 200
    assert uploads_response.json()[0]["upload_id"] == upload_payload["upload_id"]
    assert upload_view_response.json()["available"] is True

    normalize_upload_response = client.post(
        f"/uploads/{upload_payload['upload_id']}/jobs/normalize",
        json={},
    )
    assert normalize_upload_response.status_code == 201
    normalize_upload_payload = normalize_upload_response.json()
    normalize_upload_status = _wait_for_job_completion(client, normalize_upload_payload["job_id"])
    assert normalize_upload_status["status"] == "succeeded"
    normalize_upload_result = client.get(f"/jobs/{normalize_upload_payload['job_id']}/result")
    assert normalize_upload_result.status_code == 200
    assert normalize_upload_result.json()["result"]["document"]["name"] == "article_http_smoke.docx"
    assert normalize_upload_result.json()["runtime"]["source_upload_id"] == upload_payload["upload_id"]

    create_response = client.post(
        f"/uploads/{upload_payload['upload_id']}/jobs/apply",
        json={
            "scopes": ["headings"],
            "stage_input": True,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["request"]["upload_id"] == upload_payload["upload_id"]
    assert "file_path" not in create_payload["request"]

    job_id = create_payload["job_id"]
    status_payload = _wait_for_job_completion(client, job_id)
    assert status_payload["status"] == "succeeded"

    result_response = client.get(f"/jobs/{job_id}/result")
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["result"]["document"]["name"] == "article_http_smoke.docx"
    assert result_payload["runtime"]["source_upload_id"] == upload_payload["upload_id"]

    download_response = client.get(f"/jobs/{job_id}/artifacts/output/download")
    assert download_response.status_code == 200
    assert download_response.content
    assert "article_http_smoke_headings.docx" in download_response.headers.get("content-disposition", "")

    cleanup_response = client.post(f"/jobs/{job_id}/cleanup")
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["cleanup"]["state"] == "cleaned"

    after_response = client.get(f"/jobs/{job_id}/result")
    assert after_response.status_code == 200
    after_payload = after_response.json()
    assert after_payload["summary"] == result_payload["summary"]
    assert after_payload["result"] == result_payload["result"]

    missing_download_response = client.get(f"/jobs/{job_id}/artifacts/output/download")
    assert missing_download_response.status_code == 409
    assert "Artifact file is unavailable" in missing_download_response.json()["detail"]

    summary_response = client.get("/ops/summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["jobs"]["total"] >= 1
    assert summary_payload["jobs"]["succeeded"] >= 1
    assert summary_payload["runtime"]["worker_model"] == "single"
    assert summary_payload["storage"]["index_count"] >= 1
    assert summary_payload["runtime"]["pending_recovery_count"] == 0


def test_live_http_inspect_and_retry_upload_backed_job(monkeypatch, tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="article_http_retry.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    runtime_root = tmp_path / "runtime"
    client = _make_client(monkeypatch, tmp_path / "state")
    upload_payload = _upload_docx(client, source_path, runtime_root)

    create_response = client.post(
        f"/uploads/{upload_payload['upload_id']}/jobs/verify",
        json={
            "scopes": ["headings"],
            "stage_input": True,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    first_job_id = create_payload["job_id"]
    first_status = _wait_for_job_completion(client, first_job_id)
    assert first_status["status"] == "succeeded"

    inspect_response = client.get(f"/jobs/{first_job_id}/inspect")
    assert inspect_response.status_code == 200
    inspect_payload = inspect_response.json()
    assert inspect_payload["job_id"] == first_job_id
    assert inspect_payload["status"] == "succeeded"
    assert inspect_payload["result_available"] is True
    assert inspect_payload["runtime"]["source_upload_id"] == upload_payload["upload_id"]
    assert "request" not in inspect_payload
    assert "result" not in inspect_payload

    retry_response = client.post(f"/jobs/{first_job_id}/retry")
    assert retry_response.status_code == 201
    retry_payload = retry_response.json()
    assert retry_payload["request"]["upload_id"] == upload_payload["upload_id"]
    assert retry_payload["request"]["retry_of_job_id"] == first_job_id
    assert "file_path" not in retry_payload["request"]

    retried_status = _wait_for_job_completion(client, retry_payload["job_id"])
    assert retried_status["status"] == "succeeded"
    assert retried_status["runtime"]["retry_of_job_id"] == first_job_id

    missing_retry_response = client.post("/jobs/missing-job/retry")
    assert missing_retry_response.status_code == 404
    assert "Job not found" in missing_retry_response.json()["detail"]


def test_live_http_upload_cleanup_and_missing_upload_mapping(monkeypatch, tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="article_http_upload_cleanup.docx")
    runtime_root = tmp_path / "runtime"
    client = _make_client(monkeypatch, tmp_path / "state")
    upload_payload = _upload_docx(client, source_path, runtime_root)

    cleanup_response = client.post(f"/uploads/{upload_payload['upload_id']}/cleanup")
    assert cleanup_response.status_code == 200
    cleanup_payload = cleanup_response.json()
    assert cleanup_payload["upload_id"] == upload_payload["upload_id"]
    assert cleanup_payload["cleanup"]["state"] == "cleaned"
    assert cleanup_payload["cleanup"]["attempt_count"] == 1
    assert cleanup_payload["available"] is False

    upload_status_response = client.get(f"/uploads/{upload_payload['upload_id']}")
    assert upload_status_response.status_code == 200
    assert upload_status_response.json()["available"] is False

    blocked_job_response = client.post(
        f"/uploads/{upload_payload['upload_id']}/jobs/verify",
        json={"scopes": ["headings"]},
    )
    assert blocked_job_response.status_code == 409
    assert "Uploaded file is unavailable" in blocked_job_response.json()["detail"]

    missing_upload_cleanup_response = client.post("/uploads/missing-upload/cleanup")
    assert missing_upload_cleanup_response.status_code == 404
    assert "Upload not found" in missing_upload_cleanup_response.json()["detail"]


def test_live_http_retention_sweep_cleans_expired_job_and_upload(monkeypatch, tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="article_http_retention.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    runtime_root = tmp_path / "runtime"
    client = _make_client(monkeypatch, tmp_path / "state")
    upload_payload = _upload_docx(client, source_path, runtime_root)

    create_response = client.post(
        f"/uploads/{upload_payload['upload_id']}/jobs/apply",
        json={
            "scopes": ["headings"],
            "stage_input": True,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    job_id = create_payload["job_id"]

    status_payload = _wait_for_job_completion(client, job_id)
    assert status_payload["status"] == "succeeded"

    monkeypatch.setattr(app_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")
    sweep_response = client.post(
        "/ops/retention/sweep",
        json={
            "job_max_age_seconds": 1,
            "upload_max_age_seconds": 1,
        },
    )
    assert sweep_response.status_code == 200
    sweep_payload = sweep_response.json()
    assert sweep_payload["job_retention"]["cleaned_count"] == 1
    assert sweep_payload["upload_retention"]["cleaned_count"] == 1

    result_response = client.get(f"/jobs/{job_id}/result")
    upload_response = client.get(f"/uploads/{upload_payload['upload_id']}")
    assert result_response.status_code == 200
    assert upload_response.status_code == 200
    assert result_response.json()["cleanup"]["policy"] == "retention"
    assert upload_response.json()["cleanup"]["policy"] == "retention"
    assert upload_response.json()["available"] is False


def test_live_http_run_default_retention_uses_env_thresholds(monkeypatch, tmp_docx, tmp_path):
    monkeypatch.setenv("ARTICLE_API_JOB_RETENTION_SECONDS", "1")
    monkeypatch.setenv("ARTICLE_API_UPLOAD_RETENTION_SECONDS", "1")
    source_path = tmp_docx(make_compliant_doc, filename="article_http_default_retention.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    runtime_root = tmp_path / "runtime"
    client = _make_client(monkeypatch, tmp_path / "state")
    upload_payload = _upload_docx(client, source_path, runtime_root)

    create_response = client.post(
        f"/uploads/{upload_payload['upload_id']}/jobs/apply",
        json={
            "scopes": ["headings"],
            "stage_input": True,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    job_id = create_payload["job_id"]
    status_payload = _wait_for_job_completion(client, job_id)
    assert status_payload["status"] == "succeeded"

    monkeypatch.setattr(app_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")
    sweep_response = client.post("/ops/retention/run-defaults", json={})
    assert sweep_response.status_code == 200
    sweep_payload = sweep_response.json()
    assert sweep_payload["job_retention"]["cleaned_count"] == 1
    assert sweep_payload["upload_retention"]["cleaned_count"] == 1

    summary_response = client.get("/ops/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["retention"]["state"]["last_trigger"] == "manual-defaults"


def test_live_http_download_missing_artifact_maps_to_404(monkeypatch, tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="article_http_missing_artifact.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    client = _make_client(monkeypatch, tmp_path / "state")

    create_response = client.post(
        "/jobs/verify",
        json={
            "file_path": str(source_path),
            "scopes": ["headings"],
            "stage_input": True,
            "runtime_root": str(tmp_path / "runtime"),
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    status_payload = _wait_for_job_completion(client, create_payload["job_id"])
    assert status_payload["status"] == "succeeded"

    missing_artifact_response = client.get(
        f"/jobs/{create_payload['job_id']}/artifacts/missing/download"
    )
    assert missing_artifact_response.status_code == 404
    assert "Artifact not found" in missing_artifact_response.json()["detail"]
