from io import BytesIO
from pathlib import Path
import pytest
from docx import Document

import article_api.app as app_module
import article_api.jobs as jobs_module
from article_api.app import (
    ApplyRequest,
    BatchRequest,
    BatchJobRequest,
    NormalizeRequest,
    NormalizeJobRequest,
    PreflightRequest,
    RenderVerifyRequest,
    RetentionSweepRequest,
    UploadApplyRequest,
    UploadNormalizeRequest,
    UploadVerifyRequest,
    VerifyRequest,
)
from article_api import create_app, fastapi_available
from article_api.jobs import clear_jobs, job_count, wait_for_job
from article_api.storage import clear_uploads, upload_count

from .conftest import RULE_MUTATORS, make_compliant_doc


class FakeHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FakeRoute:
    def __init__(self, path: str, endpoint, status_code: int):
        self.path = path
        self.endpoint = endpoint
        self.status_code = status_code


class FakeFastAPI:
    def __init__(self, **_kwargs):
        self.routes = []

    def get(self, path: str, **kwargs):
        status_code = kwargs.get("status_code", 200)

        def decorator(func):
            self.routes.append(FakeRoute(path, func, status_code))
            return func

        return decorator

    def post(self, path: str, **kwargs):
        status_code = kwargs.get("status_code", 200)

        def decorator(func):
            self.routes.append(FakeRoute(path, func, status_code))
            return func

        return decorator


def _build_fake_app(monkeypatch):
    app_module._RETENTION_STATE.update(
        {
            "last_run_at": None,
            "last_trigger": None,
            "last_result": None,
            "last_error": None,
            "last_monotonic": None,
        }
    )
    monkeypatch.setattr(app_module, "FastAPI", FakeFastAPI)
    monkeypatch.setattr(app_module, "HTTPException", FakeHTTPException)
    monkeypatch.setattr(app_module, "FileResponse", None)
    return app_module.create_app()


def _routes_by_path(app):
    return {route.path: route for route in app.routes}


def _make_style_conflict_lnu_doc(source_path):
    doc = Document()
    heading = doc.add_paragraph("1 绪论")
    heading.style = doc.styles["Heading 1"]
    conflict = doc.add_paragraph("3.6 分子对接验证结果")
    conflict.style = doc.styles["Heading 1"]
    doc.add_paragraph("这是正文示例。")
    doc.save(source_path)
    return source_path


def test_create_app_handles_missing_fastapi_dependency():
    if fastapi_available():
        app = create_app()
        route_paths = {route.path for route in app.routes}
        assert "/" in route_paths
        assert "/health" in route_paths
        assert "/ready" in route_paths
        assert "/version" in route_paths
        assert "/profiles" in route_paths
        assert "/audit" in route_paths
        assert "/plan" in route_paths
        assert "/preflight" in route_paths
        assert "/normalize" in route_paths
        assert "/render-verify" in route_paths
        assert "/verify" in route_paths
        assert "/apply" in route_paths
        assert "/batch" in route_paths
        assert "/jobs/normalize" in route_paths
        assert "/jobs/verify" in route_paths
        assert "/jobs/apply" in route_paths
        assert "/jobs/batch" in route_paths
        assert "/jobs/batches/recent" in route_paths
        assert "/uploads/docx" in route_paths
        assert "/uploads" in route_paths
        assert "/uploads/{upload_id}" in route_paths
        assert "/uploads/{upload_id}/cleanup" in route_paths
        assert "/uploads/{upload_id}/jobs/normalize" in route_paths
        assert "/uploads/{upload_id}/jobs/verify" in route_paths
        assert "/uploads/{upload_id}/jobs/apply" in route_paths
        assert "/jobs" in route_paths
        assert "/jobs/{job_id}" in route_paths
        assert "/jobs/{job_id}/inspect" in route_paths
        assert "/jobs/{job_id}/result" in route_paths
        assert "/jobs/{job_id}/cleanup" in route_paths
        assert "/jobs/{job_id}/retry" in route_paths
        assert "/jobs/{job_id}/artifacts/{artifact_role}/download" in route_paths
        assert "/ops/summary" in route_paths
        assert "/ops/storage" in route_paths
        assert "/ops/runtime" in route_paths
        assert "/ops/retention/run-defaults" in route_paths
        assert "/ops/retention/sweep" in route_paths
        return

    with pytest.raises(RuntimeError, match="FastAPI API prototype is unavailable"):
        create_app()


def test_apply_request_supports_force_flag():
    request = ApplyRequest(file_path="demo.docx", scopes=["headings"], force=True)

    assert request.force is True


def test_request_models_default_to_auto_strict_profile():
    apply_request = ApplyRequest(file_path="demo.docx")
    preflight_request = PreflightRequest(file_path="demo.docx")
    normalize_request = NormalizeRequest(file_path="demo.docx")
    normalize_job_request = NormalizeJobRequest(file_path="demo.docx")
    render_verify_request = RenderVerifyRequest(file_path="demo.docx")
    verify_request = VerifyRequest(file_path="demo.docx")
    batch_request = BatchRequest(operation="verify", input_path="/tmp/demo.docx")

    assert apply_request.strict_profile is None
    assert preflight_request.strict_profile is None
    assert normalize_request.strict_profile is None
    assert normalize_job_request.strict_profile is None
    assert render_verify_request.strict_profile is None
    assert verify_request.strict_profile is None
    assert batch_request.strict_profile is None


def test_verify_request_supports_staging_fields():
    request = VerifyRequest(file_path="demo.docx", stage_input=True, runtime_root="/tmp/article-runtime")

    assert request.stage_input is True
    assert request.runtime_root == "/tmp/article-runtime"


def test_verify_request_supports_worker_control_fields():
    request = VerifyRequest(
        file_path="demo.docx",
        max_attempts=3,
        retry_delay_seconds=0.25,
        timeout_seconds=4.0,
    )

    assert request.max_attempts == 3
    assert request.retry_delay_seconds == 0.25
    assert request.timeout_seconds == 4.0


def test_retention_sweep_request_supports_optional_thresholds():
    request = RetentionSweepRequest(job_max_age_seconds=60, upload_max_age_seconds=120, dry_run=True)

    assert request.job_max_age_seconds == 60
    assert request.upload_max_age_seconds == 120
    assert request.dry_run is True


def test_batch_request_supports_local_batch_fields():
    request = BatchRequest(
        operation="apply",
        input_path="/tmp/article-batch",
        profile="lnu",
        scopes=["headings"],
        recursive=True,
        output_dir="/tmp/article-output",
        summary_file="/tmp/article-summary.json",
        fail_fast=True,
    )

    assert request.operation == "apply"
    assert request.profile == "lnu"
    assert request.recursive is True
    assert request.output_dir == "/tmp/article-output"
    assert request.summary_file == "/tmp/article-summary.json"
    assert request.fail_fast is True


def test_batch_job_request_supports_worker_control_fields():
    request = BatchJobRequest(
        operation="audit",
        input_path="/tmp/article-batch",
        max_attempts=2,
        retry_delay_seconds=0.25,
        timeout_seconds=8.0,
    )

    assert request.max_attempts == 2
    assert request.retry_delay_seconds == 0.25
    assert request.timeout_seconds == 8.0


def test_fake_app_health_ready_version_and_summary_endpoints(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_summary.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    console_response = routes["/"].endpoint()
    health_payload = routes["/health"].endpoint()
    version_payload = routes["/version"].endpoint()
    profiles_payload = routes["/profiles"].endpoint()
    preflight_payload = routes["/preflight"].endpoint(
        PreflightRequest(
            file_path=str(source_path),
            profile="cn-common",
        )
    )
    ready_payload = routes["/ready"].endpoint()
    runtime_payload = routes["/ops/runtime"].endpoint()
    storage_payload = routes["/ops/storage"].endpoint()
    create_payload = routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(source_path),
            scopes=["headings"],
        )
    )
    wait_for_job(create_payload["job_id"])
    summary_payload = routes["/ops/summary"].endpoint()

    assert "论文格式本地控制台" in console_response.body.decode("utf-8")
    assert health_payload["service"] == "article-api"
    assert health_payload["status"] == "ok"
    assert version_payload["version"] == "0.1.0"
    assert version_payload["api_version"] == "v0"
    assert preflight_payload["operation"] == "preflight"
    assert preflight_payload["document"]["name"] == "article_api_summary.docx"
    assert preflight_payload["profile"]["id"] == "cn-common"
    assert preflight_payload["preflight_status"] in {"ready", "warning", "blocked"}
    assert "diagnostics" in preflight_payload
    assert preflight_payload["summary"]["wild_doc_signal_count"] >= 0
    assert profiles_payload["summary"]["default_profile_id"] == "cn-common"
    assert profiles_payload["summary"]["support_scenario_count"] >= 3
    assert any(item["id"] == "school_degree_thesis" for item in profiles_payload["summary"]["support_scenarios"])
    assert not any(item["id"] == "ams-graduate" for item in profiles_payload["profiles"])
    assert any(item["id"] == "lnu-checker-2026" for item in profiles_payload["profiles"])
    default_profile = next(item for item in profiles_payload["profiles"] if item["id"] == "cn-common")
    assert default_profile["support_level_label"] == "一等支持"
    assert any(item["label"] == "课程作业/基础论文" for item in default_profile["support_scenarios"])
    assert any(doc_type == "综述" for doc_type in default_profile["document_types"])
    assert ready_payload["status"] == "ready"
    assert ready_payload["checks"]["storage"]["status"] == "ok"
    assert ready_payload["checks"]["runtime_root"]["status"] == "ok"
    assert runtime_payload["status"] == "ok"
    assert runtime_payload["runtime"]["worker_model"] == "single"
    assert runtime_payload["summary"]["worker_model"] == "single"
    assert runtime_payload["summary"]["status"] == "ok"
    assert runtime_payload["runtime"]["executor"]["max_workers"] == 1
    assert runtime_payload["runtime"]["recovery"]["strategy"] == "fail_unfinished_without_active_worker_future"
    assert storage_payload["status"] == "ok"
    assert storage_payload["storage"]["status"] == "ok"
    assert storage_payload["storage"]["integrity_check"] == "ok"
    assert storage_payload["summary"]["schema_version"] >= 1
    assert storage_payload["summary"]["index_count"] >= 1
    assert storage_payload["runtime_root"]["managed_directory_count"] >= 0
    assert summary_payload["status"] == "ok"
    assert summary_payload["checks"]["storage"]["status"] == "ok"
    assert summary_payload["checks"]["runtime_worker"]["status"] == "ok"
    assert summary_payload["jobs"]["total"] >= 1
    assert summary_payload["jobs"]["succeeded"] >= 1
    assert summary_payload["uploads"]["total"] == 0
    assert summary_payload["storage"]["schema_version"] >= 1
    assert summary_payload["storage"]["index_count"] >= 1
    assert summary_payload["cleanup"]["jobs_cleaned"] == 0
    assert summary_payload["runtime"]["worker_model"] == "single"
    assert summary_payload["runtime"]["recovered_failed_count"] == 0
    assert summary_payload["runtime"]["pending_recovery_count"] == 0
    assert summary_payload["retention"]["defaults"]["autorun_enabled"] is False


def test_fake_app_preflight_endpoint_detects_wild_doc_signals(monkeypatch, tmp_path):
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = _make_style_conflict_lnu_doc(tmp_path / "article_api_preflight.docx")

    payload = routes["/preflight"].endpoint(
        PreflightRequest(
            file_path=str(source_path),
            profile="lnu",
        )
    )

    assert payload["status"] == "ok"
    assert payload["operation"] == "preflight"
    assert payload["preflight_status"] == "blocked"
    assert payload["summary"]["wild_doc_detected"] is True
    assert payload["summary"]["wild_doc_signal_count"] >= 1
    assert any(item["id"] == "style_text_conflicts" for item in payload["wild_doc"]["signals"])
    assert payload["diagnostics"]["style_text_conflicts"]


def test_build_normalize_payload_wraps_engine_result(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "normalize_document",
        lambda *args, **kwargs: {
            "document": {"path": "/tmp/demo.docx", "name": "demo.docx"},
            "output": {"path": "/tmp/demo_normalized.docx", "name": "demo_normalized.docx"},
            "profile": {"id": "lnu-checker-2026", "requested": "lnu", "fallback_used": False, "display": "lnu"},
            "changed": True,
            "operations": [{"id": "heading_styles", "label": "扶正高置信度标题样式", "count": 1}],
            "summary": {
                "operation_count": 1,
                "before_preflight_status": "blocked",
                "after_preflight_status": "warning",
            },
            "before": {
                "preflight_status": "blocked",
                "toc_status": "no_toc",
                "style_conflict_count": 1,
                "table_heading_risk_count": 0,
            },
            "after": {
                "preflight_status": "warning",
                "toc_status": "no_toc",
                "style_conflict_count": 0,
                "table_heading_risk_count": 0,
            },
            "next_steps": ["继续 verify。"],
        },
    )

    payload = app_module.build_normalize_payload(
        file_path="/tmp/demo.docx",
        output_path="/tmp/demo_normalized.docx",
        profile_path="lnu",
    )

    assert payload["status"] == "ok"
    assert payload["operation"] == "normalize"
    assert payload["changed"] is True
    assert payload["summary"]["before_preflight_status"] == "blocked"
    assert payload["wild_doc"]["after"]["style_conflict_count"] == 0


def test_fake_app_normalize_endpoint_returns_wild_doc_delta(monkeypatch):
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    monkeypatch.setattr(
        app_module,
        "normalize_document",
        lambda *args, **kwargs: {
            "document": {"path": "/tmp/demo.docx", "name": "demo.docx"},
            "output": {"path": "/tmp/demo_normalized.docx", "name": "demo_normalized.docx"},
            "profile": {"id": "lnu-checker-2026", "requested": "lnu", "fallback_used": False, "display": "lnu"},
            "changed": True,
            "operations": [{"id": "heading_styles", "label": "扶正高置信度标题样式", "count": 1}],
            "summary": {
                "operation_count": 1,
                "before_preflight_status": "blocked",
                "after_preflight_status": "warning",
            },
            "before": {
                "preflight_status": "blocked",
                "toc_status": "no_toc",
                "style_conflict_count": 1,
                "table_heading_risk_count": 0,
            },
            "after": {
                "preflight_status": "warning",
                "toc_status": "no_toc",
                "style_conflict_count": 0,
                "table_heading_risk_count": 0,
            },
            "next_steps": ["继续 verify。"],
        },
    )

    payload = routes["/normalize"].endpoint(
        NormalizeRequest(
            file_path="/tmp/demo.docx",
            profile="lnu",
        )
    )

    assert payload["status"] == "ok"
    assert payload["operation"] == "normalize"
    assert payload["changed"] is True
    assert payload["wild_doc"]["before"]["preflight_status"] == "blocked"
    assert payload["wild_doc"]["after"]["style_conflict_count"] == 0


def test_build_render_verify_payload_wraps_engine_result(monkeypatch, tmp_path):
    output_dir = tmp_path / "render-proof"

    monkeypatch.setattr(
        app_module,
        "render_verify_document",
        lambda *args, **kwargs: {
            "document": {"path": "/tmp/demo.docx", "name": "demo.docx"},
            "profile": {"id": "lnu-checker-2026", "requested": "lnu", "fallback_used": False, "display": "lnu"},
            "output_dir": str(output_dir),
            "render_engine": "artifact-tool",
            "page_count": 2,
            "page_images": [str(output_dir / "page-1.png"), str(output_dir / "page-2.png")],
            "selected_scopes": ["toc"],
            "overall_status": "verified",
            "readiness": "render-check-required",
            "manual_review_rule_ids": ["LNU_TOC03"],
            "unsupported_rule_ids": [],
            "review_items": ["目录需要刷新后复核页码。"],
            "report_path": str(output_dir / "render_verify_report.json"),
        },
    )

    payload = app_module.build_render_verify_payload(
        file_path="/tmp/demo.docx",
        output_dir=str(output_dir),
        profile_path="lnu",
        scopes=["toc"],
    )

    assert payload["status"] == "ok"
    assert payload["operation"] == "render-verify"
    assert payload["summary"]["page_count"] == 2
    assert payload["summary"]["review_item_count"] == 1
    assert payload["summary"]["manual_review_rule_count"] == 1
    assert payload["selected_scopes"] == ["toc"]


def test_fake_app_render_verify_endpoint_returns_proof_summary(monkeypatch):
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    monkeypatch.setattr(
        app_module,
        "render_verify_document",
        lambda *args, **kwargs: {
            "document": {"path": "/tmp/demo.docx", "name": "demo.docx"},
            "profile": {"id": "lnu-checker-2026", "requested": "lnu", "fallback_used": False, "display": "lnu"},
            "output_dir": "/tmp/render-proof",
            "render_engine": "artifact-tool",
            "page_count": 1,
            "page_images": ["/tmp/render-proof/page-1.png"],
            "selected_scopes": ["figures_tables"],
            "overall_status": "verified",
            "readiness": "render-check-required",
            "manual_review_rule_ids": [],
            "unsupported_rule_ids": [],
            "review_items": ["逐页检查图表是否与题注分离。"],
            "report_path": "/tmp/render-proof/render_verify_report.json",
        },
    )

    payload = routes["/render-verify"].endpoint(
        RenderVerifyRequest(
            file_path="/tmp/demo.docx",
            profile="lnu",
            scopes=["figures_tables"],
        )
    )

    assert payload["status"] == "ok"
    assert payload["operation"] == "render-verify"
    assert payload["page_count"] == 1
    assert payload["summary"]["review_item_count"] == 1
    assert payload["selected_scopes"] == ["figures_tables"]


def test_fake_app_batch_endpoint_returns_directory_summary(monkeypatch, tmp_docx, tmp_path):
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_dir = tmp_path / "batch-api"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_batch.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    copied_path = source_dir / "article_api_batch.docx"
    copied_path.write_bytes(source_path.read_bytes())

    payload = routes["/batch"].endpoint(
        BatchRequest(
            operation="audit",
            input_path=str(source_dir),
            profile="cn-common",
            recursive=True,
        )
    )

    assert payload["operation"] == "audit"
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["succeeded"] == 1
    assert payload["summary"]["readiness_counts"]["needs-fix"] == 1
    assert payload["items"][0]["relative_path"] == "article_api_batch.docx"
    assert payload["items"][0]["overall_status"] == "needs_fix"
    assert payload["items"][0]["readiness"] == "needs-fix"


def test_fake_app_batch_job_endpoint_returns_created_job(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_dir = tmp_path / "batch-job-api"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_batch_job.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    copied_path = source_dir / "article_api_batch_job.docx"
    copied_path.write_bytes(source_path.read_bytes())

    created = routes["/jobs/batch"].endpoint(
        BatchJobRequest(
            operation="audit",
            input_path=str(source_dir),
            profile="cn-common",
            recursive=True,
        )
    )
    waited = wait_for_job(created["job_id"])
    result = routes["/jobs/{job_id}/result"].endpoint(created["job_id"])

    assert created["operation"] == "batch"
    assert waited["status"] == "succeeded"
    assert result["summary"]["batch_operation"] == "audit"
    assert result["summary"]["total_items"] == 1
    assert result["summary"]["readiness_counts"]["needs-fix"] == 1


def test_fake_app_ready_maps_storage_failure_to_503(monkeypatch):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    monkeypatch.setattr(app_module.storage, "init_storage", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db offline")))

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/ready"].endpoint()

    assert exc_info.value.status_code == 503


def test_fake_app_apply_endpoint_maps_guard_block_to_409(monkeypatch, tmp_path):
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = _make_style_conflict_lnu_doc(tmp_path / "article_api_guard_block.docx")

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/apply"].endpoint(
            ApplyRequest(
                file_path=str(source_path),
                profile="lnu",
                scopes=["headings"],
                renumber_headings=True,
            )
        )

    assert exc_info.value.status_code == 409
    assert "Apply blocked by structural risk" in exc_info.value.detail


def test_fake_app_job_endpoints_return_created_status_and_lookup(monkeypatch, tmp_docx):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_job_verify.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    create_response = routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(source_path),
            scopes=["headings"],
        )
    )
    wait_for_job(create_response["job_id"])
    list_response = routes["/jobs"].endpoint()
    status_response = routes["/jobs/{job_id}"].endpoint(create_response["job_id"])
    inspect_response = routes["/jobs/{job_id}/inspect"].endpoint(create_response["job_id"])
    result_response = routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])

    assert routes["/jobs/verify"].status_code == 201
    assert create_response["status"] == "queued"
    assert any(item["job_id"] == create_response["job_id"] for item in list_response)
    assert status_response["status"] == "succeeded"
    assert status_response["summary"]["readiness"] == "manual-review-required"
    assert inspect_response["status"] == "succeeded"
    assert "request" not in inspect_response
    assert "result" not in inspect_response
    assert result_response["result"]["overall_status"] == "needs_fix"
    assert result_response["result"]["readiness"] == "manual-review-required"


def test_fake_app_normalize_job_endpoint_runs_and_returns_output(monkeypatch, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = _make_style_conflict_lnu_doc(tmp_path / "article_api_job_normalize.docx")
    output_path = tmp_path / "article_api_job_normalized.docx"

    create_response = routes["/jobs/normalize"].endpoint(
        NormalizeJobRequest(
            file_path=str(source_path),
            output_path=str(output_path),
            profile="lnu",
        )
    )
    wait_for_job(create_response["job_id"])
    result_response = routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])

    assert routes["/jobs/normalize"].status_code == 201
    assert result_response["status"] == "succeeded"
    assert result_response["summary"]["business_status"] == "warning"
    assert result_response["summary"]["output_path"] == str(output_path)
    assert result_response["result"]["changed"] is True
    assert result_response["result"]["after"]["preflight_status"] == "warning"


def test_fake_app_jobs_endpoint_supports_operation_status_and_limit_filters(monkeypatch, tmp_docx):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    verify_source = tmp_docx(make_compliant_doc, filename="article_api_jobs_filter_verify.docx")
    verify_doc = Document(verify_source)
    RULE_MUTATORS["H02"](verify_doc)
    verify_doc.save(verify_source)

    batch_dir = verify_source.parent / "article-api-jobs-filter-batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "article_api_jobs_filter_batch.docx").write_bytes(verify_source.read_bytes())

    verify_job = routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(verify_source),
            scopes=["headings"],
        )
    )
    batch_job = routes["/jobs/batch"].endpoint(
        BatchJobRequest(
            operation="audit",
            input_path=str(batch_dir),
            profile="cn-common",
            recursive=True,
        )
    )
    wait_for_job(verify_job["job_id"])
    wait_for_job(batch_job["job_id"])

    filtered = routes["/jobs"].endpoint(operation="batch", status="succeeded", limit=1)

    assert len(filtered) == 1
    assert filtered[0]["operation"] == "batch"
    assert filtered[0]["status"] == "succeeded"


def test_fake_app_recent_batch_jobs_returns_summary_view(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_recent_batch.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)
    batch_dir = tmp_path / "recent-batch"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "article_api_recent_batch.docx").write_bytes(source_path.read_bytes())

    created = routes["/jobs/batch"].endpoint(
        BatchJobRequest(
            operation="audit",
            input_path=str(batch_dir),
            profile="cn-common",
            recursive=True,
            summary_file=str(tmp_path / "recent-batch-summary.json"),
        )
    )
    wait_for_job(created["job_id"])

    payload = routes["/jobs/batches/recent"].endpoint(status="succeeded", limit=5)

    assert payload["filters"]["operation"] == "batch"
    assert payload["filters"]["status"] == "succeeded"
    assert payload["summary"]["total"] >= 1
    assert payload["items"][0]["batch_operation"] == "audit"
    assert payload["items"][0]["summary_file"].endswith("recent-batch-summary.json")


def test_fake_app_job_status_maps_missing_job_to_404(monkeypatch):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/{job_id}"].endpoint("missing-job")

    assert exc_info.value.status_code == 404


def test_fake_app_job_inspect_maps_missing_job_to_404(monkeypatch):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/{job_id}/inspect"].endpoint("missing-job")

    assert exc_info.value.status_code == 404


def test_fake_app_job_submit_invalid_path_maps_to_400_and_does_not_store(monkeypatch, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    missing_path = tmp_path / "missing.docx"

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/verify"].endpoint(VerifyRequest(file_path=str(missing_path)))

    assert exc_info.value.status_code == 400
    assert job_count() == 0


def test_fake_app_job_apply_returns_failed_job_payload_on_guard_block(monkeypatch, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = _make_style_conflict_lnu_doc(tmp_path / "article_api_job_apply_fail.docx")

    response = routes["/jobs/apply"].endpoint(
        ApplyRequest(
            file_path=str(source_path),
            profile="lnu",
            scopes=["headings"],
            renumber_headings=True,
        )
    )
    wait_for_job(response["job_id"])
    status = routes["/jobs/{job_id}"].endpoint(response["job_id"])

    assert routes["/jobs/apply"].status_code == 201
    assert response["status"] == "queued"
    assert status["status"] == "failed"
    assert status["summary"]["error_code"] == "apply_guard_blocked"
    assert status["error"]["code"] == "apply_guard_blocked"


def test_fake_app_job_result_maps_missing_job_to_404(monkeypatch):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/{job_id}/result"].endpoint("missing-job")

    assert exc_info.value.status_code == 404


def test_fake_app_job_verify_can_stage_input(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_job_stage_verify.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    response = routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(source_path),
            scopes=["headings"],
            stage_input=True,
            runtime_root=str(tmp_path / "runtime"),
        )
    )
    wait_for_job(response["job_id"])
    result = routes["/jobs/{job_id}/result"].endpoint(response["job_id"])

    assert response["resolved_request"]["file_path"].startswith(response["workspace"]["inputs"])
    assert result["result"]["document"]["name"] == "article_api_job_stage_verify.docx"


def test_fake_app_upload_endpoint_stores_docx_and_job_downloads_output(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_apply.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_upload_apply.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    uploads_response = routes["/uploads"].endpoint()
    upload_status = routes["/uploads/{upload_id}"].endpoint(upload_response["upload_id"])
    create_response = routes["/uploads/{upload_id}/jobs/apply"].endpoint(
        upload_response["upload_id"],
        UploadApplyRequest(
            scopes=["headings"],
        ),
    )
    wait_for_job(create_response["job_id"])
    status = routes["/jobs/{job_id}"].endpoint(create_response["job_id"])
    result = routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])
    download_response = routes["/jobs/{job_id}/artifacts/{artifact_role}/download"].endpoint(
        create_response["job_id"],
        "output",
    )

    assert routes["/uploads/docx"].status_code == 201
    assert upload_count() == 1
    assert uploads_response[0]["upload_id"] == upload_response["upload_id"]
    assert upload_status["available"] is True
    assert upload_response["file_name"] == "article_api_upload_apply.docx"
    assert Path(upload_response["stored_path"]).exists()
    assert create_response["status"] == "queued"
    assert create_response["request"]["upload_id"] == upload_response["upload_id"]
    assert "file_path" not in create_response["request"]
    assert status["summary"]["document_name"] == "article_api_upload_apply.docx"
    assert status["summary"]["output_path"].endswith("article_api_upload_apply_headings.docx")
    assert result["result"]["document"]["name"] == "article_api_upload_apply.docx"
    assert result["runtime"]["source_upload_id"] == upload_response["upload_id"]
    assert download_response["job_id"] == create_response["job_id"]
    assert download_response["artifact_role"] == "output"
    assert download_response["filename"] == "article_api_upload_apply_headings.docx"


def test_fake_app_upload_normalize_job_keeps_original_name(monkeypatch, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = _make_style_conflict_lnu_doc(tmp_path / "article_api_upload_normalize.docx")

    class FakeUpload:
        filename = "article_api_upload_normalize.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    create_response = routes["/uploads/{upload_id}/jobs/normalize"].endpoint(
        upload_response["upload_id"],
        UploadNormalizeRequest(),
    )
    wait_for_job(create_response["job_id"])
    result = routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])

    assert create_response["request"]["upload_id"] == upload_response["upload_id"]
    assert result["summary"]["output_path"].endswith("article_api_upload_normalize_normalized.docx")
    assert result["result"]["document"]["name"] == "article_api_upload_normalize.docx"
    assert result["runtime"]["source_upload_id"] == upload_response["upload_id"]


def test_fake_app_download_endpoint_maps_missing_artifact_file_to_409(monkeypatch, tmp_docx):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_download_missing.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    create_response = routes["/jobs/apply"].endpoint(
        ApplyRequest(
            file_path=str(source_path),
            scopes=["headings"],
        )
    )
    wait_for_job(create_response["job_id"])
    status = routes["/jobs/{job_id}"].endpoint(create_response["job_id"])
    output_path = Path(status["summary"]["output_path"])
    output_path.unlink()

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/{job_id}/artifacts/{artifact_role}/download"].endpoint(
            create_response["job_id"],
            "output",
        )

    assert exc_info.value.status_code == 409
    assert routes["/jobs/{job_id}"].endpoint(create_response["job_id"]) == status
    assert routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])["status"] == "succeeded"


def test_fake_app_upload_verify_job_supports_upload_id_and_stage_input(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_verify.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_upload_verify.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    create_response = routes["/uploads/{upload_id}/jobs/verify"].endpoint(
        upload_response["upload_id"],
        UploadVerifyRequest(
            scopes=["headings"],
            stage_input=True,
        ),
    )
    wait_for_job(create_response["job_id"])
    result = routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])

    assert create_response["request"]["upload_id"] == upload_response["upload_id"]
    assert "file_path" not in create_response["request"]
    assert create_response["resolved_request"]["file_path"].startswith(create_response["workspace"]["inputs"])
    assert create_response["resolved_request"]["source_display_name"] == "article_api_upload_verify.docx"
    assert result["result"]["document"]["name"] == "article_api_upload_verify.docx"
    assert result["runtime"]["source_upload_id"] == upload_response["upload_id"]


def test_fake_app_upload_job_missing_upload_id_maps_to_404(monkeypatch):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/uploads/{upload_id}/jobs/verify"].endpoint(
            "missing-upload",
            UploadVerifyRequest(scopes=["headings"]),
        )

    assert exc_info.value.status_code == 404
    assert job_count() == 0


def test_fake_app_upload_registry_marks_missing_file_unavailable(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_missing_source.docx")

    class FakeUpload:
        filename = "article_api_upload_missing_source.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    Path(upload_response["stored_path"]).unlink()

    upload_status = routes["/uploads/{upload_id}"].endpoint(upload_response["upload_id"])
    assert upload_status["available"] is False

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/uploads/{upload_id}/jobs/apply"].endpoint(
            upload_response["upload_id"],
            UploadApplyRequest(scopes=["headings"]),
        )

    assert exc_info.value.status_code == 409
    assert job_count() == 0


def test_fake_app_upload_cleanup_is_blocked_by_active_job(monkeypatch, tmp_docx, tmp_path):
    import time

    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_cleanup_guard.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_upload_cleanup_guard.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    def slow_attempt(operation: str, resolved_request: dict[str, object]) -> dict[str, object]:
        time.sleep(0.2)
        return {
            "ok": True,
            "result": jobs_module.verify_document(
                file_path=str(resolved_request["file_path"]),
                profile_path=resolved_request.get("profile_path"),
                scopes=resolved_request.get("scopes"),
                strict_profile=bool(resolved_request.get("strict_profile")),
            ),
        }

    monkeypatch.setattr(jobs_module, "_execute_job_attempt", slow_attempt)
    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    create_response = routes["/uploads/{upload_id}/jobs/verify"].endpoint(
        upload_response["upload_id"],
        UploadVerifyRequest(scopes=["headings"]),
    )

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/uploads/{upload_id}/cleanup"].endpoint(upload_response["upload_id"])

    assert exc_info.value.status_code == 409
    assert create_response["job_id"] in exc_info.value.detail
    wait_for_job(create_response["job_id"])


def test_fake_app_cleanup_endpoint_keeps_job_payload_readable_and_breaks_download(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_cleanup.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    response = routes["/jobs/apply"].endpoint(
        ApplyRequest(
            file_path=str(source_path),
            scopes=["headings"],
            stage_input=True,
            runtime_root=str(tmp_path / "runtime"),
        )
    )
    wait_for_job(response["job_id"])
    before = routes["/jobs/{job_id}/result"].endpoint(response["job_id"])
    cleanup_response = routes["/jobs/{job_id}/cleanup"].endpoint(response["job_id"])
    after = routes["/jobs/{job_id}/result"].endpoint(response["job_id"])

    assert cleanup_response["cleanup"]["state"] == "cleaned"
    assert after["summary"] == before["summary"]
    assert after["result"] == before["result"]

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/{job_id}/artifacts/{artifact_role}/download"].endpoint(
            response["job_id"],
            "output",
        )

    assert exc_info.value.status_code == 409


def test_fake_app_retry_endpoint_requeues_upload_backed_job_without_leaking_file_path(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_retry_upload.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_retry_upload.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    first_job = routes["/uploads/{upload_id}/jobs/verify"].endpoint(
        upload_response["upload_id"],
        UploadVerifyRequest(scopes=["headings"]),
    )
    wait_for_job(first_job["job_id"])

    retried_job = routes["/jobs/{job_id}/retry"].endpoint(first_job["job_id"])
    wait_for_job(retried_job["job_id"])
    retried_status = routes["/jobs/{job_id}"].endpoint(retried_job["job_id"])

    assert routes["/jobs/{job_id}/retry"].status_code == 201
    assert retried_job["request"]["upload_id"] == upload_response["upload_id"]
    assert retried_job["request"]["retry_of_job_id"] == first_job["job_id"]
    assert "file_path" not in retried_job["request"]
    assert retried_status["status"] == "succeeded"
    assert retried_status["runtime"]["retry_of_job_id"] == first_job["job_id"]


def test_fake_app_retry_endpoint_still_works_after_job_cleanup(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_retry_upload_after_cleanup.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_retry_upload_after_cleanup.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    first_job = routes["/uploads/{upload_id}/jobs/verify"].endpoint(
        upload_response["upload_id"],
        UploadVerifyRequest(scopes=["headings"]),
    )
    wait_for_job(first_job["job_id"])
    cleanup_response = routes["/jobs/{job_id}/cleanup"].endpoint(first_job["job_id"])

    retried_job = routes["/jobs/{job_id}/retry"].endpoint(first_job["job_id"])
    wait_for_job(retried_job["job_id"])
    retried_status = routes["/jobs/{job_id}"].endpoint(retried_job["job_id"])

    assert cleanup_response["cleanup"]["state"] in {"cleaned", "noop"}
    assert Path(upload_response["stored_path"]).exists()
    assert retried_job["request"]["upload_id"] == upload_response["upload_id"]
    assert retried_job["request"]["retry_of_job_id"] == first_job["job_id"]
    assert "file_path" not in retried_job["request"]
    assert retried_status["status"] == "succeeded"
    assert retried_status["runtime"]["retry_of_job_id"] == first_job["job_id"]


def test_fake_app_cleanup_breaks_input_download_but_result_stays_frozen(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_cleanup_input.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    response = routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(source_path),
            scopes=["headings"],
            stage_input=True,
            runtime_root=str(tmp_path / "runtime"),
        )
    )
    wait_for_job(response["job_id"])
    before = routes["/jobs/{job_id}/result"].endpoint(response["job_id"])
    routes["/jobs/{job_id}/cleanup"].endpoint(response["job_id"])
    after = routes["/jobs/{job_id}/result"].endpoint(response["job_id"])

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/jobs/{job_id}/artifacts/{artifact_role}/download"].endpoint(
            response["job_id"],
            "input",
        )

    assert exc_info.value.status_code == 409
    assert after["summary"] == before["summary"]
    assert after["result"] == before["result"]


def test_fake_app_upload_job_rejects_conflicting_runtime_root(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_runtime_conflict.docx")

    class FakeUpload:
        filename = "article_api_upload_runtime_conflict.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime-a"),
    )

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/uploads/{upload_id}/jobs/verify"].endpoint(
            upload_response["upload_id"],
            UploadVerifyRequest(
                scopes=["headings"],
                runtime_root=str(tmp_path / "runtime-b"),
            ),
        )

    assert exc_info.value.status_code == 400
    assert job_count() == 0


def test_fake_app_upload_registry_is_atomic_when_storage_write_fails(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_atomic.docx")
    stored_file = tmp_path / "runtime" / "uploads" / "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_article_api_upload_atomic.docx"
    stored_file.parent.mkdir(parents=True, exist_ok=True)
    stored_file.write_bytes(Path(source_path).read_bytes())

    class FakeUpload:
        filename = "article_api_upload_atomic.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    class FakeStoredUpload:
        upload_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        stored_path = str(stored_file)
        file_name = "article_api_upload_atomic.docx"
        workspace_dir = str(stored_file.parent)
        size_bytes = len(Path(source_path).read_bytes())

    monkeypatch.setattr(app_module, "store_uploaded_docx", lambda *_args, **_kwargs: FakeStoredUpload())
    monkeypatch.setattr(app_module.storage, "upsert_upload", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db write failed")))

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/uploads/docx"].endpoint(
            FakeUpload(Path(source_path).read_bytes()),
            runtime_root=str(tmp_path / "runtime"),
        )

    assert exc_info.value.status_code == 409
    assert upload_count() == 0


def test_fake_app_upload_cleanup_marks_upload_unavailable_and_blocks_future_jobs(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_upload_cleanup.docx")

    class FakeUpload:
        filename = "article_api_upload_cleanup.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    cleanup_response = routes["/uploads/{upload_id}/cleanup"].endpoint(upload_response["upload_id"])
    upload_status = routes["/uploads/{upload_id}"].endpoint(upload_response["upload_id"])

    assert cleanup_response["cleanup"]["state"] == "cleaned"
    assert cleanup_response["cleanup"]["attempt_count"] == 1
    assert upload_status["available"] is False

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/uploads/{upload_id}/jobs/verify"].endpoint(
            upload_response["upload_id"],
            UploadVerifyRequest(scopes=["headings"]),
        )

    assert exc_info.value.status_code == 409
    assert not Path(upload_response["stored_path"]).exists()


def test_fake_app_retention_sweep_cleans_expired_job_and_upload(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_retention.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_retention.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    create_response = routes["/uploads/{upload_id}/jobs/apply"].endpoint(
        upload_response["upload_id"],
        UploadApplyRequest(scopes=["headings"], stage_input=True),
    )
    wait_for_job(create_response["job_id"])
    monkeypatch.setattr(app_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")

    sweep_response = routes["/ops/retention/sweep"].endpoint(
        RetentionSweepRequest(job_max_age_seconds=1, upload_max_age_seconds=1),
    )
    job_payload = routes["/jobs/{job_id}/result"].endpoint(create_response["job_id"])
    upload_payload = routes["/uploads/{upload_id}"].endpoint(upload_response["upload_id"])

    assert sweep_response["policy"] == "retention"
    assert sweep_response["job_retention"]["cleaned_count"] == 1
    assert sweep_response["upload_retention"]["cleaned_count"] == 1
    assert sweep_response["job_retention"]["items"][0]["job_id"] == create_response["job_id"]
    assert sweep_response["job_retention"]["items"][0]["cleanup"]["policy"] == "retention"
    assert sweep_response["upload_retention"]["items"][0]["upload_id"] == upload_response["upload_id"]
    assert sweep_response["upload_retention"]["items"][0]["cleanup"]["policy"] == "retention"
    assert job_payload["cleanup"]["policy"] == "retention"
    assert upload_payload["cleanup"]["policy"] == "retention"
    assert upload_payload["available"] is False


def test_fake_app_run_default_retention_uses_env_thresholds(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    monkeypatch.setenv("ARTICLE_API_JOB_RETENTION_SECONDS", "1")
    monkeypatch.setenv("ARTICLE_API_UPLOAD_RETENTION_SECONDS", "1")
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_default_retention.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    class FakeUpload:
        filename = "article_api_default_retention.docx"

        def __init__(self, payload: bytes):
            self.file = BytesIO(payload)

    upload_response = routes["/uploads/docx"].endpoint(
        FakeUpload(Path(source_path).read_bytes()),
        runtime_root=str(tmp_path / "runtime"),
    )
    create_response = routes["/uploads/{upload_id}/jobs/apply"].endpoint(
        upload_response["upload_id"],
        UploadApplyRequest(scopes=["headings"], stage_input=True),
    )
    wait_for_job(create_response["job_id"])
    monkeypatch.setattr(app_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")

    sweep_response = routes["/ops/retention/run-defaults"].endpoint(app_module.RetentionDefaultsRunRequest())
    summary_payload = routes["/ops/summary"].endpoint()

    assert sweep_response["job_retention"]["cleaned_count"] == 1
    assert sweep_response["upload_retention"]["cleaned_count"] == 1
    assert summary_payload["retention"]["state"]["last_trigger"] == "manual-defaults"
    assert summary_payload["retention"]["defaults"]["job_max_age_seconds"] == 1.0
    assert summary_payload["retention"]["defaults"]["upload_max_age_seconds"] == 1.0


def test_fake_app_run_default_retention_requires_env_thresholds(monkeypatch):
    clear_jobs()
    clear_uploads()
    monkeypatch.delenv("ARTICLE_API_JOB_RETENTION_SECONDS", raising=False)
    monkeypatch.delenv("ARTICLE_API_UPLOAD_RETENTION_SECONDS", raising=False)
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/ops/retention/run-defaults"].endpoint(app_module.RetentionDefaultsRunRequest())

    assert exc_info.value.status_code == 400


def test_fake_app_autorun_retention_cleans_expired_job_on_next_write(monkeypatch, tmp_docx, tmp_path):
    clear_jobs()
    clear_uploads()
    monkeypatch.setenv("ARTICLE_API_JOB_RETENTION_SECONDS", "1")
    monkeypatch.setenv("ARTICLE_API_RETENTION_AUTORUN", "true")
    monkeypatch.setenv("ARTICLE_API_RETENTION_AUTORUN_INTERVAL_SECONDS", "1")
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)
    source_path = tmp_docx(make_compliant_doc, filename="article_api_autorun_retention.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    doc.save(source_path)

    first_job = routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(source_path),
            scopes=["headings"],
            stage_input=True,
            runtime_root=str(tmp_path / "runtime"),
        )
    )
    wait_for_job(first_job["job_id"])

    job_result = routes["/jobs/{job_id}/result"].endpoint(first_job["job_id"])
    monkeypatch.setattr(app_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")
    app_module._RETENTION_STATE["last_monotonic"] = 0.0
    routes["/jobs/verify"].endpoint(
        VerifyRequest(
            file_path=str(source_path),
            scopes=["headings"],
        )
    )
    retained_job = routes["/jobs/{job_id}/result"].endpoint(first_job["job_id"])
    summary_payload = routes["/ops/summary"].endpoint()

    assert job_result["cleanup"] is None
    assert retained_job["cleanup"]["policy"] == "retention"
    assert summary_payload["retention"]["state"]["last_trigger"] == "autorun"


def test_fake_app_retention_sweep_requires_threshold(monkeypatch):
    clear_jobs()
    clear_uploads()
    app = _build_fake_app(monkeypatch)
    routes = _routes_by_path(app)

    with pytest.raises(FakeHTTPException) as exc_info:
        routes["/ops/retention/sweep"].endpoint(RetentionSweepRequest())

    assert exc_info.value.status_code == 400
