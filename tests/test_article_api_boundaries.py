from pathlib import Path

import inspect

from article_api.app import ApplyRequest
from article_api import app_ops, app_uploads, job_queries, request_payloads, response_payloads, upload_job_payloads
from article_api import job_artifacts, job_execution, job_payloads
import article_api.jobs as jobs_module
from article_api.schemas import AuditRequest, VerifyRequest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_api_request_models_live_in_schemas_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert "from pydantic import BaseModel" not in app_source
    assert "class AuditRequest" not in app_source
    assert AuditRequest.__module__ == "article_api.schemas"
    assert ApplyRequest.__module__ == "article_api.schemas"


def test_api_request_payload_builders_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")
    request = VerifyRequest(file_path="demo.docx", profile="lnu", scopes=["toc"], strict_profile=True)

    assert "def _verify_kwargs" not in app_source
    assert request_payloads.verify_kwargs(request) == {
        "file_path": "demo.docx",
        "profile_path": "lnu",
        "scopes": ["toc"],
        "strict_profile": True,
    }


def test_api_response_payload_builders_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '"operation": "normalize"' not in app_source
    assert "render_workflow_mode = resolve_render_workflow_mode" not in app_source
    assert response_payloads.SERVICE_NAME == "article-api"


def test_job_query_helpers_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")
    jobs = [
        {"job_id": "1", "operation": "verify", "status": "succeeded"},
        {"job_id": "2", "operation": "apply", "status": "failed"},
    ]

    assert "def _filtered_job_list" not in app_source
    assert job_queries.filter_jobs(jobs, operation="verify") == [jobs[0]]


def test_ops_summary_builders_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert "jobs = storage.list_jobs(include_result=False)" not in app_source
    assert "storage_snapshot = storage.inspect_storage(include_integrity_check=False)" not in app_source
    assert "runtime_view = runtime_snapshot()" not in app_source
    assert hasattr(app_ops, "build_ops_summary_payload")


def test_upload_job_payload_builders_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '"source_display_name": upload["file_name"]' not in app_source
    assert '"_public_request": public_request' not in app_source
    assert hasattr(upload_job_payloads, "build_verify_upload_job_kwargs")


def test_upload_cleanup_and_retention_builders_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert "blocking_job_ids = [" not in app_source
    assert '"policy": "retention"' not in app_source
    assert hasattr(app_uploads, "cleanup_upload")


def test_job_pure_helpers_live_outside_jobs_lifecycle_module():
    resolve_source = inspect.getsource(jobs_module._resolve_request)
    summary_source = inspect.getsource(jobs_module._result_summary)
    execution_source = inspect.getsource(jobs_module._run_handler_subprocess)
    artifact_source = inspect.getsource(jobs_module._build_artifacts)
    cleanup_source = inspect.getsource(jobs_module._cleanup_candidate_map)

    assert "job_payloads.resolve_request" in resolve_source
    assert "job_payloads.build_result_summary" in summary_source
    assert "job_execution.run_handler_subprocess" in execution_source
    assert "job_artifacts.build_artifacts" in artifact_source
    assert "job_artifacts.cleanup_candidate_map" in cleanup_source
    assert hasattr(job_payloads, "resolve_request")
    assert hasattr(job_payloads, "build_result_summary")
    assert hasattr(job_execution, "run_handler_subprocess")
    assert hasattr(job_artifacts, "build_artifacts")
    assert hasattr(job_artifacts, "cleanup_candidate_map")
