import importlib
from pathlib import Path
import sqlite3

import article_api.storage as job_storage
import pytest
from article_api.jobs import clear_jobs, create_job, get_job, wait_for_job
from article_api.storage import clear_uploads
from article_api.uploads import store_uploaded_docx

from .conftest import make_compliant_doc


def test_jobs_are_persisted_into_sqlite_store(monkeypatch, tmp_docx, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    clear_jobs()
    source_path = tmp_docx(make_compliant_doc, filename="article_storage_verify.docx")

    job = create_job(
        "verify",
        {
            "file_path": str(source_path),
            "scopes": ["headings"],
        },
    )
    wait_for_job(job["job_id"])
    stored = job_storage.get_job(job["job_id"], include_result=True)
    payload = get_job(job["job_id"])

    assert Path(job_storage.resolve_db_path()).exists()
    assert stored is not None
    assert stored["job_id"] == job["job_id"]
    assert stored["status"] == "succeeded"
    assert payload["job_id"] == job["job_id"]


def test_init_storage_sets_schema_version(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    db_path = job_storage.resolve_db_path()

    job_storage.init_storage()

    assert db_path.exists()
    assert job_storage.get_schema_version() == job_storage.SCHEMA_VERSION


def test_inspect_storage_reports_paths_counts_and_integrity(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))

    snapshot = job_storage.inspect_storage()

    assert snapshot["status"] == "ok"
    assert snapshot["state_root"] == str(job_storage.resolve_state_root())
    assert snapshot["db_path"] == str(job_storage.resolve_db_path())
    assert snapshot["db_exists"] is True
    assert snapshot["schema_version"] == job_storage.SCHEMA_VERSION
    assert snapshot["integrity_check"] == "ok"
    assert snapshot["tables"]["jobs"]["rows"] == 0
    assert snapshot["tables"]["upload_cleanup"]["rows"] == 0
    assert all(item["present"] is True for item in snapshot["indexes"].values())


def test_inspect_storage_can_skip_integrity_check(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))

    snapshot = job_storage.inspect_storage(include_integrity_check=False)

    assert snapshot["status"] == "ok"
    assert snapshot["integrity_check"] is None


def test_init_storage_migrates_legacy_schema_version_zero(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    db_path = job_storage.resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA user_version = 0")

    job_storage.init_storage()

    with sqlite3.connect(db_path) as connection:
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        jobs_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        ).fetchone()

    assert user_version == job_storage.SCHEMA_VERSION
    assert jobs_table is not None


def test_init_storage_migrates_previous_schema_version_one(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    db_path = job_storage.resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA user_version = 1")

    job_storage.init_storage()
    snapshot = job_storage.inspect_storage()

    assert snapshot["schema_version"] == job_storage.SCHEMA_VERSION
    assert all(item["present"] is True for item in snapshot["indexes"].values())


def test_init_storage_rejects_newer_schema_version(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    db_path = job_storage.resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(f"PRAGMA user_version = {job_storage.SCHEMA_VERSION + 1}")

    with pytest.raises(RuntimeError, match="newer than supported version"):
        job_storage.init_storage()


def test_maintain_storage_reports_actions_and_keeps_indexes_present(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    job_storage.init_storage()

    report = job_storage.maintain_storage(run_analyze=True, run_vacuum=False)

    assert report["status"] == "ok"
    assert report["actions"] == ["analyze"]
    assert report["analyze"] is True
    assert report["vacuum"] is False
    assert report["storage"]["schema_version"] == job_storage.SCHEMA_VERSION
    assert all(item["present"] is True for item in report["storage"]["indexes"].values())


def test_uploads_are_persisted_into_sqlite_store(monkeypatch, tmp_docx, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    clear_jobs()
    clear_uploads()
    source_path = tmp_docx(make_compliant_doc, filename="article_storage_upload.docx")

    class FakeUpload:
        filename = "article_storage_upload.docx"

        def __init__(self, payload: bytes):
            from io import BytesIO

            self.file = BytesIO(payload)

    stored_upload = store_uploaded_docx(FakeUpload(Path(source_path).read_bytes()), runtime_root=tmp_path / "runtime")
    payload = {
        "upload_id": stored_upload.upload_id,
        "file_name": stored_upload.file_name,
        "stored_path": stored_upload.stored_path,
        "workspace_dir": stored_upload.workspace_dir,
        "runtime_root": str(tmp_path / "runtime"),
        "size_bytes": stored_upload.size_bytes,
        "created_at": "2026-04-19T00:00:00Z",
    }
    job_storage.upsert_upload(payload)

    stored = job_storage.get_upload(stored_upload.upload_id)
    uploads = job_storage.list_uploads()

    assert stored is not None
    assert stored["upload_id"] == stored_upload.upload_id
    assert stored["file_name"] == "article_storage_upload.docx"
    assert uploads[0]["upload_id"] == stored_upload.upload_id


def test_stale_queued_job_is_reconciled_to_failed(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS", "1")
    clear_jobs()
    payload = {
        "job_id": "stale-queued-job",
        "operation": "verify",
        "status": "queued",
        "mode": "background",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:00:00Z",
        "started_at": None,
        "finished_at": None,
        "request": {"file_path": "/tmp/stale.docx", "scopes": ["headings"]},
        "resolved_request": {"file_path": "/tmp/stale.docx", "scopes": ["headings"], "strict_profile": False},
        "workspace": None,
        "runtime": {
            "cleanup_policy": "manual",
            "runtime_root": None,
            "source_upload_id": None,
            "stage_input_enabled": False,
            "workspace_present": False,
            "workspace_root": None,
            "workspace_inputs": None,
            "workspace_outputs": None,
            "source_file_path": None,
            "staged_input_path": None,
            "output_path": None,
        },
        "result_available": False,
        "summary": None,
        "artifacts": [],
        "error": None,
        "result": None,
    }
    job_storage.upsert_job(payload)

    recovered = get_job("stale-queued-job")
    stored = job_storage.get_job("stale-queued-job", include_result=True)

    assert recovered["status"] == "failed"
    assert recovered["summary"]["error_code"] == "worker_recovery_failed"
    assert stored["error"]["code"] == "worker_recovery_failed"
    assert stored["finished_at"] is not None


def test_recent_unfinished_job_within_recovery_grace_is_not_failed(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS", "3600")
    clear_jobs()
    payload = {
        "job_id": "recent-running-job",
        "operation": "verify",
        "status": "running",
        "mode": "background",
        "created_at": "2099-01-01T00:00:00Z",
        "updated_at": "2099-01-01T00:00:00Z",
        "started_at": "2099-01-01T00:00:00Z",
        "finished_at": None,
        "request": {"file_path": "/tmp/recent.docx", "scopes": ["headings"]},
        "resolved_request": {"file_path": "/tmp/recent.docx", "scopes": ["headings"], "strict_profile": False},
        "workspace": None,
        "runtime": {
            "cleanup_policy": "manual",
            "runtime_root": None,
            "source_upload_id": None,
            "stage_input_enabled": False,
            "workspace_present": False,
            "workspace_root": None,
            "workspace_inputs": None,
            "workspace_outputs": None,
            "source_file_path": None,
            "staged_input_path": None,
            "output_path": None,
            "attempt_count": 0,
            "attempts": [],
            "events": [],
            "worker_model": "single",
            "lease_state": "pending",
            "last_heartbeat_at": "2099-01-01T00:00:00Z",
            "heartbeat_count": 0,
        },
        "result_available": False,
        "summary": None,
        "artifacts": [],
        "error": None,
        "result": None,
    }
    job_storage.upsert_job(payload)

    recovered = get_job("recent-running-job")
    stored = job_storage.get_job("recent-running-job", include_result=True)

    assert recovered["status"] == "running"
    assert stored["error"] is None
    assert stored["finished_at"] is None


def test_stale_running_job_preserves_frozen_snapshot_when_reconciled(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS", "1")
    clear_jobs()
    payload = {
        "job_id": "stale-running-job",
        "operation": "apply",
        "status": "running",
        "mode": "background",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:05:00Z",
        "started_at": "2026-04-19T00:01:00Z",
        "finished_at": None,
        "request": {"file_path": "/tmp/stale.docx", "scopes": ["headings"]},
        "resolved_request": {
            "file_path": "/tmp/stale.docx",
            "scopes": ["headings"],
            "strict_profile": False,
            "output_path": "/tmp/stale_headings.docx",
        },
        "workspace": None,
        "runtime": {
            "cleanup_policy": "manual",
            "runtime_root": None,
            "source_upload_id": None,
            "stage_input_enabled": False,
            "workspace_present": False,
            "workspace_root": None,
            "workspace_inputs": None,
            "workspace_outputs": None,
            "source_file_path": "/tmp/stale.docx",
            "staged_input_path": None,
            "output_path": "/tmp/stale_headings.docx",
            "attempt_count": 1,
            "attempts": [{"attempt": 1, "status": "succeeded", "retryable": False}],
        },
        "result_available": False,
        "summary": {
            "document_name": "stale.docx",
            "business_status": "verified",
            "output_path": "/tmp/stale_headings.docx",
            "attempt_count": 1,
            "max_attempts": 1,
        },
        "artifacts": [
            {
                "kind": "docx",
                "role": "output",
                "path": "/tmp/stale_headings.docx",
                "download_name": "stale_headings.docx",
                "written": True,
                "exists_at_completion": True,
            }
        ],
        "error": None,
        "result": {
            "mode": "write",
            "document": {"path": "/tmp/stale.docx", "name": "stale.docx"},
            "output": {"path": "/tmp/stale_headings.docx"},
            "verification": {"overall_status": "verified"},
        },
    }
    job_storage.upsert_job(payload)

    recovered = get_job("stale-running-job")
    stored = job_storage.get_job("stale-running-job", include_result=True)

    assert recovered["status"] == "failed"
    assert recovered["summary"]["error_code"] == "worker_recovery_failed"
    assert recovered["summary"]["business_status"] == "verified"
    assert stored["result"] == payload["result"]
    assert stored["artifacts"] == payload["artifacts"]
    assert stored["error"]["code"] == "worker_recovery_failed"
    assert stored["finished_at"] is not None


def test_stale_running_job_backfills_runtime_contract_when_runtime_is_incomplete(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS", "1")
    clear_jobs()
    payload = {
        "job_id": "stale-runtime-incomplete-job",
        "operation": "apply",
        "status": "running",
        "mode": "background",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:05:00Z",
        "started_at": "2026-04-19T00:01:00Z",
        "finished_at": None,
        "request": {"file_path": "/tmp/stale-runtime.docx", "scopes": ["headings"]},
        "resolved_request": {
            "file_path": "/tmp/stale-runtime.docx",
            "scopes": ["headings"],
            "strict_profile": False,
            "output_path": "/tmp/stale-runtime_headings.docx",
            "max_attempts": 2,
            "retry_delay_seconds": 0.25,
            "retry_of_job_id": "origin-job",
        },
        "workspace": None,
        "runtime": {
            "cleanup_policy": "manual",
            "runtime_root": None,
        },
        "result_available": False,
        "summary": None,
        "artifacts": [],
        "error": None,
        "result": None,
    }
    job_storage.upsert_job(payload)

    recovered = get_job(payload["job_id"])
    stored = job_storage.get_job(payload["job_id"], include_result=True)

    assert recovered["status"] == "failed"
    assert recovered["runtime"]["worker_model"] == "single"
    assert recovered["runtime"]["lease_state"] == "released"
    assert recovered["runtime"]["max_attempts"] == 2
    assert recovered["runtime"]["retry_delay_seconds"] == 0.25
    assert recovered["runtime"]["retry_of_job_id"] == "origin-job"
    assert recovered["runtime"]["output_path"] == "/tmp/stale-runtime_headings.docx"
    assert stored["runtime"]["attempts"] == []
    assert stored["runtime"]["heartbeat_count"] == 0
    assert stored["runtime"]["events"][-1]["event"] == "recovered_as_failed"


def test_stale_running_job_rebuilds_missing_artifacts_from_frozen_result(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS", "1")
    clear_jobs()
    payload = {
        "job_id": "stale-missing-artifacts-job",
        "operation": "apply",
        "status": "running",
        "mode": "background",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:05:00Z",
        "started_at": "2026-04-19T00:01:00Z",
        "finished_at": None,
        "request": {"file_path": "/tmp/stale-missing-artifacts.docx", "scopes": ["headings"]},
        "resolved_request": {
            "file_path": "/tmp/stale-missing-artifacts.docx",
            "scopes": ["headings"],
            "strict_profile": False,
            "output_path": "/tmp/stale-missing-artifacts_headings.docx",
        },
        "workspace": None,
        "runtime": {
            "cleanup_policy": "manual",
            "runtime_root": None,
        },
        "result_available": False,
        "summary": {
            "document_name": "stale-missing-artifacts.docx",
            "business_status": "verified",
            "output_path": "/tmp/stale-missing-artifacts_headings.docx",
            "attempt_count": 1,
            "max_attempts": 1,
        },
        "artifacts": [],
        "error": None,
        "result": {
            "mode": "write",
            "document": {"path": "/tmp/stale-missing-artifacts.docx", "name": "stale-missing-artifacts.docx"},
            "output": {"path": "/tmp/stale-missing-artifacts_headings.docx"},
            "verification": {"overall_status": "verified"},
        },
    }
    job_storage.upsert_job(payload)

    recovered = get_job(payload["job_id"])
    stored = job_storage.get_job(payload["job_id"], include_result=True)

    assert recovered["status"] == "failed"
    assert stored["status"] == "failed"
    assert len(stored["artifacts"]) == 1
    assert stored["artifacts"][0]["role"] == "output"
    assert stored["artifacts"][0]["result_mode"] == "write"
    assert stored["artifacts"][0]["written"] is True
    assert stored["summary"]["business_status"] == "verified"


def test_job_cleanup_payload_is_persisted_and_reloaded(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    clear_jobs()
    payload = {
        "job_id": "cleanup-job",
        "operation": "verify",
        "status": "succeeded",
        "mode": "background",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:05:00Z",
        "started_at": "2026-04-19T00:01:00Z",
        "finished_at": "2026-04-19T00:02:00Z",
        "request": {"file_path": "/tmp/cleanup.docx", "scopes": ["headings"]},
        "resolved_request": {"file_path": "/tmp/cleanup.docx", "scopes": ["headings"], "strict_profile": False},
        "workspace": None,
        "runtime": {
            "cleanup_policy": "manual",
            "runtime_root": str(tmp_path / "runtime"),
            "source_upload_id": None,
            "stage_input_enabled": False,
            "workspace_present": False,
            "workspace_root": None,
            "workspace_inputs": None,
            "workspace_outputs": None,
            "source_file_path": "/tmp/cleanup.docx",
            "staged_input_path": None,
            "output_path": None,
        },
        "result_available": True,
        "summary": {"business_status": "verified"},
        "artifacts": [],
        "error": None,
        "result": {"verification": {"overall_status": "verified"}},
    }
    first_cleanup = {
        "policy": "manual",
        "state": "cleaned",
        "cleaned_at": "2026-04-19T00:03:00Z",
        "attempt_count": 1,
        "removed_paths": ["/tmp/runtime/jobs/cleanup-job"],
        "missing_paths": [],
        "skipped_paths": [],
    }
    second_cleanup = {
        "policy": "manual",
        "state": "noop",
        "cleaned_at": "2026-04-19T00:04:00Z",
        "attempt_count": 2,
        "removed_paths": [],
        "missing_paths": ["/tmp/runtime/jobs/cleanup-job"],
        "skipped_paths": [],
    }

    job_storage.upsert_job(payload)
    job_storage.upsert_job_cleanup(payload["job_id"], first_cleanup)

    stored_job = job_storage.get_job(payload["job_id"], include_result=True)
    stored_list = job_storage.list_jobs(include_result=True)

    assert job_storage.get_job_cleanup(payload["job_id"]) == first_cleanup
    assert stored_job["cleanup"] == first_cleanup
    assert stored_list[0]["cleanup"] == first_cleanup

    job_storage.upsert_job_cleanup(payload["job_id"], second_cleanup)
    reloaded_storage = importlib.reload(job_storage)

    assert reloaded_storage.get_job_cleanup(payload["job_id"]) == second_cleanup
    assert reloaded_storage.get_job(payload["job_id"], include_result=True)["cleanup"] == second_cleanup
    assert reloaded_storage.list_jobs(include_result=True)[0]["cleanup"]["attempt_count"] == 2


def test_upload_cleanup_payload_is_persisted_and_reloaded(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTICLE_API_STATE_ROOT", str(tmp_path / "state"))
    clear_uploads()
    upload_payload = {
        "upload_id": "cleanup-upload",
        "file_name": "cleanup-upload.docx",
        "stored_path": str(tmp_path / "runtime" / "uploads" / "cleanup-upload.docx"),
        "workspace_dir": str(tmp_path / "runtime" / "uploads"),
        "runtime_root": str(tmp_path / "runtime"),
        "size_bytes": 128,
        "created_at": "2026-04-19T00:00:00Z",
    }
    first_cleanup = {
        "policy": "manual",
        "state": "cleaned",
        "cleaned_at": "2026-04-19T00:01:00Z",
        "attempt_count": 1,
        "removed_paths": [upload_payload["stored_path"]],
        "missing_paths": [],
        "skipped_paths": [],
    }
    second_cleanup = {
        "policy": "manual",
        "state": "noop",
        "cleaned_at": "2026-04-19T00:02:00Z",
        "attempt_count": 2,
        "removed_paths": [],
        "missing_paths": [upload_payload["stored_path"]],
        "skipped_paths": [],
    }

    job_storage.upsert_upload(upload_payload)
    job_storage.upsert_upload_cleanup(upload_payload["upload_id"], first_cleanup)

    assert job_storage.get_upload_cleanup(upload_payload["upload_id"]) == first_cleanup
    assert job_storage.get_upload(upload_payload["upload_id"]) == upload_payload

    job_storage.upsert_upload_cleanup(upload_payload["upload_id"], second_cleanup)
    reloaded_storage = importlib.reload(job_storage)

    assert reloaded_storage.get_upload_cleanup(upload_payload["upload_id"]) == second_cleanup
    assert reloaded_storage.get_upload(upload_payload["upload_id"]) == upload_payload
    assert reloaded_storage.list_uploads()[0]["upload_id"] == upload_payload["upload_id"]
