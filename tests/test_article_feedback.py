from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

import article_api.local_app as local_app
import article_api.local_feedback as local_feedback
import article_api.storage as storage


def test_feedback_redaction_handles_a_long_line_without_document_names_quickly():
    line = "x" * (128 * 1024)

    started = time.perf_counter()
    sanitized = local_feedback._redact_document_artifact_names(line)

    assert sanitized == line
    assert time.perf_counter() - started < 1.0


def test_create_feedback_archive_skips_oversized_diagnostic_file(tmp_path):
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    output_zip = tmp_path / "article-feedback.zip"
    storage.init_storage(state_root)
    oversized_log = state_root / "oversized.log"
    with oversized_log.open("wb") as handle:
        handle.truncate(local_feedback.MAX_DIAGNOSTIC_FILE_BYTES + 1)

    payload = local_app.create_feedback_archive(
        str(output_zip),
        state_root=str(state_root),
        runtime_root=str(runtime_root),
    )

    assert payload["included_file_count"] == 0
    with zipfile.ZipFile(output_zip) as archive:
        inventory = json.loads(archive.read("runtime_files.json"))
        assert "logs/state_root/oversized.log" not in archive.namelist()
    oversized_entry = next(item for item in inventory if item["path"].endswith("oversized.log"))
    assert oversized_entry["reason"] == "diagnostic_text_too_large"


def test_create_feedback_archive_excludes_document_artifacts_by_default(tmp_path):
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    output_zip = tmp_path / "article-feedback.zip"
    storage.init_storage(state_root)
    (state_root / "article_api.log").write_text("任务失败：端口占用，文件 paper.docx\n", encoding="utf-8")
    source_docx = runtime_root / "uploads" / "20221303306-学生姓名-论文题目.docx"
    source_docx.parent.mkdir(parents=True)
    source_docx.write_bytes(b"docx-bytes")
    output_docx = runtime_root / "jobs" / "job-1" / "outputs" / "20221303306-学生姓名-论文题目_格式修复.docx"
    output_docx.parent.mkdir(parents=True)
    output_docx.write_bytes(b"fixed-docx")
    rendered_pdf = runtime_root / "jobs" / "job-1" / "render" / "page.pdf"
    rendered_pdf.parent.mkdir(parents=True)
    rendered_pdf.write_bytes(b"%PDF")
    rendered_png = runtime_root / "jobs" / "job-1" / "render" / "page-1.png"
    rendered_png.write_bytes(b"png")
    runtime_log = runtime_root / "jobs" / "job-1" / "logs" / "worker.log"
    runtime_log.parent.mkdir(parents=True)
    runtime_log.write_text("worker failed for 20221303306-学生姓名-论文题目.docx\n", encoding="utf-8")

    storage.upsert_upload(
        {
            "upload_id": "upload-1",
            "file_name": source_docx.name,
            "stored_path": str(source_docx),
            "workspace_dir": str(source_docx.parent),
            "runtime_root": str(runtime_root),
            "size_bytes": source_docx.stat().st_size,
            "created_at": "2026-04-22T00:00:00Z",
        },
        state_root=state_root,
    )
    storage.upsert_job(
        {
            "job_id": "job-1",
            "operation": "apply",
            "status": "failed",
            "mode": "worker",
            "created_at": "2026-04-22T00:00:01Z",
            "updated_at": "2026-04-22T00:00:02Z",
            "request": {"file_path": str(source_docx)},
            "resolved_request": {"file_path": str(source_docx), "output_path": str(output_docx)},
            "workspace": {"workspace_root": str(runtime_root / "jobs" / "job-1")},
            "runtime": {"runtime_root": str(runtime_root)},
            "summary": {"headline": "apply failed"},
            "error": {
                "message": f"Invalid package at {source_docx}: missing Content Types",
                "path": str(output_docx),
            },
            "result": {"output": {"path": str(output_docx)}},
            "result_available": True,
            "artifacts": [
                {"role": "output", "path": str(output_docx), "kind": "file"},
                {"role": "report", "path": str(runtime_log), "kind": "file"},
            ],
        },
        state_root=state_root,
    )

    payload = local_app.create_feedback_archive(
        str(output_zip),
        state_root=str(state_root),
        runtime_root=str(runtime_root),
    )

    assert payload["status"] == "ok"
    assert payload["excluded_document_artifact_count"] == 4
    assert payload["included_file_count"] >= 1
    with zipfile.ZipFile(output_zip) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        jobs = json.loads(archive.read("jobs.json").decode("utf-8"))
        uploads = json.loads(archive.read("uploads.json").decode("utf-8"))
        runtime_files = json.loads(archive.read("runtime_files.json").decode("utf-8"))
        state_log = archive.read("logs/state_root/article_api.log").decode("utf-8")
        worker_log = archive.read("logs/runtime_root/jobs/job-1/logs/worker.log").decode("utf-8")

    assert "manifest.json" in names
    assert "doctor.json" in names
    assert "jobs.json" in names
    assert "uploads.json" in names
    assert "runtime_files.json" in names
    assert "logs/state_root/article_api.log" in names
    assert "logs/runtime_root/jobs/job-1/logs/worker.log" in names
    assert not any(name.endswith((".docx", ".pdf", ".png")) for name in names)
    assert str(tmp_path) not in json.dumps(manifest, ensure_ascii=False)
    assert str(tmp_path) not in json.dumps(jobs, ensure_ascii=False)
    assert uploads[0]["file_name"] == "<document-name>"
    assert uploads[0]["stored_path"] == "<runtime_root>/uploads/<document-file>"
    assert jobs[0]["request"]["file_path"] == "<runtime_root>/uploads/<document-file>"
    assert jobs[0]["resolved_request"]["output_path"] == "<runtime_root>/jobs/job-1/outputs/<document-file>"
    assert runtime_files[0]["path"].startswith("<state_root>/")
    assert "20221303306" not in json.dumps((jobs, uploads, runtime_files), ensure_ascii=False)
    assert "学生姓名" not in json.dumps((jobs, uploads, runtime_files), ensure_ascii=False)
    assert "论文题目" not in state_log
    assert "论文题目" not in worker_log
    assert "paper.docx" not in state_log
    assert "<document-file>x" not in state_log
    assert "<document-file>" in worker_log
    assert "学生姓名" not in jobs[0]["error"]["message"]
    assert "<document-file>: missing Content Types" in jobs[0]["error"]["message"]


def test_create_feedback_archive_skips_files_removed_during_inventory(monkeypatch, tmp_path):
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    output_zip = tmp_path / "article-feedback.zip"
    storage.init_storage(state_root)
    vanished_file = state_root / "vanished.tmp"

    def fake_iter_files(root: Path) -> list[Path]:
        return [vanished_file] if root == state_root else []

    monkeypatch.setattr(local_feedback, "_iter_files", fake_iter_files)

    payload = local_app.create_feedback_archive(
        str(output_zip),
        state_root=str(state_root),
        runtime_root=str(runtime_root),
    )

    assert payload["status"] == "ok"
    with zipfile.ZipFile(output_zip) as archive:
        runtime_files = json.loads(archive.read("runtime_files.json").decode("utf-8"))

    assert runtime_files == []


def test_create_feedback_archive_streams_diagnostic_files_into_zip(monkeypatch, tmp_path):
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    output_zip = tmp_path / "article-feedback.zip"
    storage.init_storage(state_root)
    (state_root / "article_api.log").write_text("diagnostic\n", encoding="utf-8")
    archive_open = False
    real_zip_file = local_feedback.zipfile.ZipFile
    real_read = local_feedback._read_sanitized_diagnostic_bytes

    class TrackingZipFile(real_zip_file):
        def __enter__(self):
            nonlocal archive_open
            archive_open = True
            return super().__enter__()

    def guarded_read(*args, **kwargs):
        assert archive_open
        return real_read(*args, **kwargs)

    monkeypatch.setattr(local_feedback.zipfile, "ZipFile", TrackingZipFile)
    monkeypatch.setattr(local_feedback, "_read_sanitized_diagnostic_bytes", guarded_read)

    payload = local_app.create_feedback_archive(
        str(output_zip),
        state_root=str(state_root),
        runtime_root=str(runtime_root),
    )

    assert payload["included_file_count"] == 1


def test_create_feedback_archive_skips_log_removed_before_zip_write(monkeypatch, tmp_path):
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    output_zip = tmp_path / "article-feedback.zip"
    storage.init_storage(state_root)
    log_path = state_root / "article_api.log"
    log_path.write_text("diagnostic\n", encoding="utf-8")

    def remove_before_read(path: Path, **_kwargs):
        path.unlink()
        raise FileNotFoundError(path)

    monkeypatch.setattr(local_feedback, "_read_sanitized_diagnostic_bytes", remove_before_read)

    payload = local_app.create_feedback_archive(
        str(output_zip),
        state_root=str(state_root),
        runtime_root=str(runtime_root),
    )

    assert payload["included_file_count"] == 0
    with zipfile.ZipFile(output_zip) as archive:
        assert "logs/state_root/article_api.log" not in archive.namelist()
        runtime_files = json.loads(archive.read("runtime_files.json"))
        assert not any(item["path"].endswith("article_api.log") for item in runtime_files)


def test_article_local_feedback_cli_writes_manifest_and_doctor_payload(capsys, tmp_path):
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    output_zip = tmp_path / "feedback.zip"

    exit_code = local_app.main(
        [
            "feedback",
            str(output_zip),
            "--state-root",
            str(state_root),
            "--runtime-root",
            str(runtime_root),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "ok"' in captured.out
    assert output_zip.exists()
    with zipfile.ZipFile(output_zip) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        doctor = json.loads(archive.read("doctor.json").decode("utf-8"))

    assert manifest["kind"] == "article-local-feedback"
    assert manifest["privacy"]["includes_document_artifacts"] is False
    assert doctor["status"] == "ok"
