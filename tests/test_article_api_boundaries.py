from pathlib import Path

import inspect

from article_api.app import ApplyRequest
from article_api import app_ops, app_uploads, job_queries, request_payloads, response_payloads, upload_job_payloads
from article_api import job_artifacts, job_execution, job_payloads, storage
import article_api.app as app_module
import article_api.jobs as jobs_module
from article_api.schemas import AuditRequest, UploadVerifyRequest, VerifyRequest


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


def test_upload_job_payload_builders_share_worker_field_mapping():
    source = (PROJECT_ROOT / "scripts" / "article_api" / "upload_job_payloads.py").read_text(encoding="utf-8")
    upload = {
        "upload_id": "upload-1",
        "stored_path": "/runtime-a/uploads/upload-1.docx",
        "file_name": "paper.docx",
        "runtime_root": "/runtime-a",
    }
    request = UploadVerifyRequest(
        scopes=["headings"],
        stage_input=True,
        runtime_root="/runtime-a",
        max_attempts=3,
        retry_delay_seconds=0.25,
        timeout_seconds=9.0,
    )

    payload = upload_job_payloads.build_verify_upload_job_kwargs(
        "upload-1",
        request,
        resolve_upload_fn=lambda upload_id: upload,
    )

    assert hasattr(upload_job_payloads, "_build_upload_job_kwargs")
    assert source.count('"max_attempts": request.max_attempts') <= 1
    assert source.count('"retry_delay_seconds": request.retry_delay_seconds') <= 1
    assert source.count('"timeout_seconds": request.timeout_seconds') <= 1
    assert payload["_public_request"]["runtime_root"] == "/runtime-a"
    assert payload["runtime_root"] == "/runtime-a"
    assert payload["_public_request"]["max_attempts"] == 3
    assert payload["max_attempts"] == 3


def test_upload_cleanup_and_retention_builders_live_outside_app_module():
    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert "blocking_job_ids = [" not in app_source
    assert '"policy": "retention"' not in app_source
    assert hasattr(app_uploads, "cleanup_upload")


def test_app_retention_orchestration_lives_outside_app_module():
    import article_api.app_retention as app_retention

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert "from threading import Lock" not in app_source
    assert "from time import monotonic" not in app_source
    assert "app_uploads.record_retention_success" not in app_source
    assert "app_uploads.record_retention_error" not in app_source
    assert "app_uploads.should_autorun_retention" not in app_source
    assert hasattr(app_retention, "maybe_autorun_retention")
    assert hasattr(app_retention, "run_default_retention_sweep")
    assert app_module._RETENTION_STATE is app_retention.RETENTION_STATE


def test_app_retention_compatibility_wrappers_use_app_module_injection_points(monkeypatch):
    calls = []

    def fake_sweep_job_retention(max_age_seconds, *, now, dry_run):
        calls.append(("job", max_age_seconds, now, dry_run))
        return {"kind": "job"}

    def fake_sweep_upload_retention(max_age_seconds, *, now, dry_run):
        calls.append(("upload", max_age_seconds, now, dry_run))
        return {"kind": "upload"}

    monkeypatch.setattr(app_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")
    monkeypatch.setattr(app_module, "sweep_job_retention", fake_sweep_job_retention)
    monkeypatch.setattr(app_module, "_sweep_upload_retention", fake_sweep_upload_retention)

    result = app_module._sweep_retention(
        app_module.RetentionSweepRequest(job_max_age_seconds=1, upload_max_age_seconds=2, dry_run=True)
    )

    assert calls == [
        ("job", 1.0, "2099-01-01T00:00:00Z", True),
        ("upload", 2.0, "2099-01-01T00:00:00Z", True),
    ]
    assert result["job_retention"] == {"kind": "job"}
    assert result["upload_retention"] == {"kind": "upload"}


def test_default_retention_compatibility_wrapper_uses_app_module_helpers(monkeypatch):
    calls = []

    monkeypatch.setattr(
        app_module,
        "_retention_defaults_payload",
        lambda: {
            "job_max_age_seconds": 3.0,
            "upload_max_age_seconds": 4.0,
            "autorun_enabled": False,
            "autorun_interval_seconds": 300.0,
        },
    )
    monkeypatch.setattr(
        app_module,
        "_sweep_retention",
        lambda request: calls.append(("sweep", request.job_max_age_seconds, request.upload_max_age_seconds, request.dry_run))
        or {"triggered_at": "2099-01-01T00:00:00Z"},
    )
    monkeypatch.setattr(
        app_module,
        "_record_retention_success",
        lambda *, trigger, result: calls.append(("record", trigger, result["triggered_at"])),
    )

    result = app_module._run_default_retention_sweep(dry_run=True, trigger="test")

    assert result == {"triggered_at": "2099-01-01T00:00:00Z"}
    assert calls == [
        ("sweep", 3.0, 4.0, True),
        ("record", "test", "2099-01-01T00:00:00Z"),
    ]


def test_feedback_download_route_registration_lives_outside_app_module():
    import article_api.routes_feedback as routes_feedback

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.get("/feedback/download")' not in app_source
    assert "def download_feedback_archive" not in app_source
    assert "create_feedback_archive" not in app_source
    assert hasattr(routes_feedback, "register_feedback_routes")


def test_metadata_route_registration_lives_outside_app_module():
    import article_api.routes_metadata as routes_metadata

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.get("/")' not in app_source
    assert '@app.get("/assets/lnu-emblem.jpg")' not in app_source
    assert '@app.get("/health")' not in app_source
    assert '@app.get("/ready")' not in app_source
    assert '@app.get("/version")' not in app_source
    assert '@app.get("/updates/latest")' not in app_source
    assert '@app.get("/profiles")' not in app_source
    assert '@app.get("/render-workflow-modes")' not in app_source
    assert hasattr(routes_metadata, "register_metadata_routes")


def test_sync_engine_route_registration_lives_outside_app_module():
    import article_api.routes_sync as routes_sync

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.post("/audit")' not in app_source
    assert '@app.post("/plan")' not in app_source
    assert '@app.post("/preflight")' not in app_source
    assert '@app.post("/normalize")' not in app_source
    assert '@app.post("/render-verify")' not in app_source
    assert '@app.post("/verify")' not in app_source
    assert '@app.post("/apply")' not in app_source
    assert hasattr(routes_sync, "register_sync_engine_routes")


def test_job_status_route_registration_lives_outside_app_module():
    import article_api.routes_jobs as routes_jobs

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.get("/jobs")' not in app_source
    assert '@app.get("/jobs/{job_id}")' not in app_source
    assert '@app.get("/jobs/{job_id}/inspect")' not in app_source
    assert '@app.get("/jobs/{job_id}/result")' not in app_source
    assert '@app.post("/jobs/{job_id}/cleanup")' not in app_source
    assert '@app.post("/jobs/{job_id}/retry", status_code=201)' not in app_source
    assert '@app.get("/jobs/{job_id}/artifacts/{artifact_role}/download")' not in app_source
    assert hasattr(routes_jobs, "register_job_status_routes")


def test_job_submit_route_registration_lives_outside_app_module():
    import article_api.routes_job_submit as routes_job_submit

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.post("/jobs/verify", status_code=201)' not in app_source
    assert '@app.post("/jobs/normalize", status_code=201)' not in app_source
    assert '@app.post("/jobs/apply", status_code=201)' not in app_source
    assert hasattr(routes_job_submit, "register_job_submit_routes")


def test_upload_route_registration_lives_outside_app_module():
    import article_api.routes_uploads as routes_uploads

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.post("/uploads/docx", status_code=201)' not in app_source
    assert '@app.post("/uploads/pdf", status_code=201)' not in app_source
    assert '@app.get("/uploads")' not in app_source
    assert '@app.get("/uploads/{upload_id}")' not in app_source
    assert '@app.post("/uploads/{upload_id}/cleanup")' not in app_source
    assert '@app.post("/uploads/{upload_id}/jobs/verify", status_code=201)' not in app_source
    assert '@app.post("/uploads/{upload_id}/jobs/normalize", status_code=201)' not in app_source
    assert '@app.post("/uploads/{upload_id}/jobs/apply", status_code=201)' not in app_source
    assert hasattr(routes_uploads, "register_upload_routes")


def test_ops_route_registration_lives_outside_app_module():
    import article_api.routes_ops as routes_ops

    app_source = (PROJECT_ROOT / "scripts" / "article_api" / "app.py").read_text(encoding="utf-8")

    assert '@app.get("/ops/summary")' not in app_source
    assert '@app.get("/ops/storage")' not in app_source
    assert '@app.get("/ops/runtime")' not in app_source
    assert '@app.post("/ops/retention/run-defaults")' not in app_source
    assert '@app.post("/ops/retention/sweep")' not in app_source
    assert hasattr(routes_ops, "register_ops_routes")


def test_route_exception_mapping_uses_shared_helper():
    import article_api.routes_feedback as routes_feedback
    import article_api.routes_job_submit as routes_job_submit
    import article_api.routes_jobs as routes_jobs
    import article_api.routes_ops as routes_ops
    import article_api.routes_sync as routes_sync
    import article_api.routes_uploads as routes_uploads
    from article_api import route_error_handlers

    for module in (
        routes_feedback,
        routes_job_submit,
        routes_jobs,
        routes_ops,
        routes_sync,
        routes_uploads,
    ):
        source = inspect.getsource(module)
        assert "call_with_http_error" in source
        assert "raise_job_http_error(exc)" not in source
        assert "raise_sync_http_error(exc)" not in source

    assert hasattr(route_error_handlers, "call_with_http_error")


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


def test_report_artifact_argument_mapping_is_centralized_in_jobs_module():
    backfill_source = inspect.getsource(jobs_module._ensure_finished_report_artifact_payload)
    finalize_source = inspect.getsource(jobs_module._finalize_record)

    assert hasattr(jobs_module, "_ensure_report_artifact")
    helper_source = inspect.getsource(jobs_module._ensure_report_artifact)
    assert "job_artifacts.ensure_report_artifact" in helper_source
    assert "job_artifacts.ensure_report_artifact" not in backfill_source
    assert "job_artifacts.ensure_report_artifact" not in finalize_source
    assert backfill_source.count("_ensure_report_artifact(") == 1
    assert finalize_source.count("_ensure_report_artifact(") == 1


def test_job_lifecycle_time_helpers_centralize_recovery_and_heartbeat_age_logic():
    reconcile_source = inspect.getsource(jobs_module._reconcile_incomplete_jobs)
    snapshot_source = inspect.getsource(jobs_module.runtime_snapshot)
    get_job_source = inspect.getsource(jobs_module.get_job)
    payload = {
        "created_at": "2099-01-01T00:00:00Z",
        "started_at": "2099-01-01T00:00:01Z",
        "updated_at": "2099-01-01T00:00:02Z",
        "runtime": {"last_heartbeat_at": "2099-01-01T00:00:03Z"},
    }

    assert jobs_module._last_seen_timestamp(payload) == "2099-01-01T00:00:03Z"
    assert jobs_module._last_seen_timestamp({**payload, "runtime": {}}) == "2099-01-01T00:00:02Z"
    assert jobs_module._seconds_since("2099-01-01T00:00:05Z", "2099-01-01T00:00:03Z") == 2.0
    assert jobs_module._seconds_since("2099-01-01T00:00:03Z", "2099-01-01T00:00:05Z") == 0.0
    assert jobs_module._seconds_since("2099-01-01T00:00:05Z", None) is None
    assert "last_heartbeat_at\") or payload.get(\"updated_at\"" not in reconcile_source
    assert "last_heartbeat_at\") or payload.get(\"updated_at\"" not in snapshot_source
    assert "runtime[\"heartbeat_age_seconds\"] = max(" not in get_job_source


def test_job_retention_logic_lives_outside_jobs_lifecycle_module():
    from article_api import job_retention

    cleanup_source = inspect.getsource(jobs_module.cleanup_job)
    sweep_source = inspect.getsource(jobs_module.sweep_job_retention)

    assert "job_retention.cleanup_job" in cleanup_source
    assert "job_retention.sweep_job_retention" in sweep_source
    assert "removed_paths: list[str]" not in cleanup_source
    assert '"eligible_count"' not in sweep_source
    assert hasattr(job_retention, "cleanup_job")
    assert hasattr(job_retention, "sweep_job_retention")


def test_job_retention_wrappers_keep_jobs_module_injection_points(monkeypatch):
    from article_api import job_retention

    calls = []

    def fake_cleanup_job(job_id, **deps):
        calls.append(("cleanup", job_id, deps["policy"], deps["finished_statuses"]))
        payload = deps["get_job_payload_fn"](job_id)
        candidates = deps["cleanup_candidate_map_fn"](payload)
        deps["upsert_job_cleanup_fn"](job_id, {"cleaned_at": deps["utcnow_fn"](), "candidates": candidates})
        return deps["get_job_fn"](job_id)

    monkeypatch.setattr(job_retention, "cleanup_job", fake_cleanup_job)
    monkeypatch.setattr(
        jobs_module.storage,
        "get_job",
        lambda job_id, *, include_result: calls.append(("get_job", job_id, include_result)) or {"job_id": job_id},
    )
    monkeypatch.setattr(
        jobs_module.storage,
        "upsert_job_cleanup",
        lambda job_id, payload: calls.append(("upsert_cleanup", job_id, payload)),
    )
    monkeypatch.setattr(jobs_module, "_cleanup_candidate_map", lambda payload: calls.append(("candidate_map", payload)) or ({}, []))
    monkeypatch.setattr(jobs_module, "_utcnow", lambda: "2099-01-01T00:00:00Z")
    monkeypatch.setattr(jobs_module, "get_job", lambda job_id: calls.append(("public_get_job", job_id)) or {"job_id": job_id, "wrapped": True})

    cleanup_result = jobs_module.cleanup_job("job-1", policy="contract")

    assert cleanup_result == {"job_id": "job-1", "wrapped": True}
    assert calls == [
        ("cleanup", "job-1", "contract", {"succeeded", "failed"}),
        ("get_job", "job-1", True),
        ("candidate_map", {"job_id": "job-1"}),
        ("upsert_cleanup", "job-1", {"cleaned_at": "2099-01-01T00:00:00Z", "candidates": ({}, [])}),
        ("public_get_job", "job-1"),
    ]


def test_job_retention_sweep_wrapper_keeps_jobs_module_injection_points(monkeypatch):
    from article_api import job_retention

    calls = []

    def fake_sweep_job_retention(max_age_seconds, **deps):
        calls.append(("sweep", max_age_seconds, deps["now"], deps["dry_run"], deps["finished_statuses"]))
        coerced = deps["coerce_positive_float_fn"](max_age_seconds, field_name="job_max_age_seconds")
        parsed = deps["parse_timestamp_fn"]("2099-01-01T00:00:00Z")
        deps["reconcile_incomplete_jobs_fn"]()
        payloads = deps["list_jobs_fn"]()
        cleaned = deps["cleanup_job_fn"]("job-1", policy="retention")
        return {"coerced": coerced, "parsed": parsed, "payloads": payloads, "cleaned": cleaned, "now": deps["utcnow_fn"]()}

    monkeypatch.setattr(job_retention, "sweep_job_retention", fake_sweep_job_retention)
    monkeypatch.setattr(jobs_module, "_utcnow", lambda: "2100-01-01T00:00:00Z")
    monkeypatch.setattr(
        jobs_module,
        "_coerce_positive_float",
        lambda value, *, field_name: calls.append(("coerce", value, field_name)) or 12.5,
    )
    monkeypatch.setattr(
        jobs_module,
        "_parse_timestamp",
        lambda value: calls.append(("parse", value)) or f"parsed:{value}",
    )
    monkeypatch.setattr(jobs_module, "_reconcile_incomplete_jobs", lambda: calls.append(("reconcile",)))
    monkeypatch.setattr(jobs_module.storage, "list_jobs", lambda *, include_result: calls.append(("list_jobs", include_result)) or [{"job_id": "job-1"}])
    monkeypatch.setattr(
        jobs_module,
        "cleanup_job",
        lambda job_id, *, policy: calls.append(("cleanup_job", job_id, policy)) or {"job_id": job_id, "policy": policy},
    )

    report = jobs_module.sweep_job_retention(5, now="2099-01-01T00:00:00Z", dry_run=True)

    assert report == {
        "coerced": 12.5,
        "parsed": "parsed:2099-01-01T00:00:00Z",
        "payloads": [{"job_id": "job-1"}],
        "cleaned": {"job_id": "job-1", "policy": "retention"},
        "now": "2100-01-01T00:00:00Z",
    }
    assert calls == [
        ("sweep", 5, "2099-01-01T00:00:00Z", True, {"succeeded", "failed"}),
        ("coerce", 5, "job_max_age_seconds"),
        ("parse", "2099-01-01T00:00:00Z"),
        ("reconcile",),
        ("list_jobs", True),
        ("cleanup_job", "job-1", "retention"),
    ]


def test_storage_cleanup_payload_sql_uses_shared_helpers():
    upsert_job_source = inspect.getsource(storage.upsert_job_cleanup)
    get_job_source = inspect.getsource(storage.get_job_cleanup)
    load_job_source = inspect.getsource(storage._load_job_cleanup)
    upsert_upload_source = inspect.getsource(storage.upsert_upload_cleanup)
    get_upload_source = inspect.getsource(storage.get_upload_cleanup)

    assert "_upsert_cleanup_payload" in upsert_job_source
    assert "_get_cleanup_payload" in get_job_source
    assert "_load_cleanup_payload" in load_job_source
    assert "_upsert_cleanup_payload" in upsert_upload_source
    assert "_get_cleanup_payload" in get_upload_source
    assert "INSERT INTO job_cleanup" not in upsert_job_source
    assert "SELECT payload_json FROM job_cleanup" not in get_job_source
    assert "INSERT INTO upload_cleanup" not in upsert_upload_source
    assert "SELECT payload_json FROM upload_cleanup" not in get_upload_source
    assert hasattr(storage, "_upsert_cleanup_payload")
    assert hasattr(storage, "_get_cleanup_payload")
    assert hasattr(storage, "_load_cleanup_payload")
