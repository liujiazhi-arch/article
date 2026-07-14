from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from thesis_tool.render_toc_evidence import verify_docx_pdf_content_match
from thesis_tool.render_verify import _extract_pdf_page_texts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "release_smoke.py"


def _load_release_smoke():
    spec = importlib.util.spec_from_file_location("release_smoke", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_smoke_files_have_matching_extractable_content(tmp_path):
    release_smoke = _load_release_smoke()
    docx_path = tmp_path / "smoke.docx"
    pdf_path = tmp_path / "smoke.pdf"
    release_smoke._build_smoke_docx(docx_path, python_executable=Path(sys.executable))
    release_smoke._build_smoke_pdf(pdf_path, python_executable=Path(sys.executable))

    page_texts, text_summary = _extract_pdf_page_texts(str(pdf_path), page_count=1)
    content_match = verify_docx_pdf_content_match(docx_path, page_texts)

    assert text_summary["available"] is True
    assert content_match["matched"] is True
    assert content_match["matched_anchor_count"] >= 2


def test_browser_smoke_pdf_has_extractable_formula_split_evidence(tmp_path):
    release_smoke = _load_release_smoke()
    pdf_path = tmp_path / "browser-smoke.pdf"

    release_smoke._build_smoke_pdf(
        pdf_path,
        python_executable=Path(sys.executable),
        include_layout_issue=True,
    )
    page_texts, text_summary = _extract_pdf_page_texts(str(pdf_path), page_count=2)

    assert text_summary["available"] is True
    assert page_texts[1].splitlines()[-1] == "x=y+z"
    assert page_texts[2].splitlines()[0] == "(1)"


def test_release_smoke_builds_wheel_installs_clean_venv_and_runs_http_flow(monkeypatch, tmp_path):
    release_smoke = _load_release_smoke()
    calls: list[tuple[list[str], float | None]] = []
    venv_dir = tmp_path / "venv"
    wheel_dir = tmp_path / "wheelhouse"
    state_root = tmp_path / "state"
    runtime_root = tmp_path / "runtime"
    wheel_path = wheel_dir / "thesis_format_tool-0.1.0-py3-none-any.whl"

    def fake_run(
        command,
        *,
        cwd=None,
        env=None,
        capture_output=False,
        text=True,
        check=True,
        timeout=None,
        encoding=None,
        errors=None,
    ):
        command = [str(item) for item in command]
        calls.append((command, timeout))
        if command[1:3] == ["-m", "venv"]:
            bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
            bin_dir.mkdir(parents=True, exist_ok=True)
            (bin_dir / ("python.exe" if sys.platform == "win32" else "python")).write_text("", encoding="utf-8")
            for script_name in ("lnu-thesis-local", "thesis-workbench"):
                suffix = ".exe" if sys.platform == "win32" else ""
                (bin_dir / f"{script_name}{suffix}").write_text("", encoding="utf-8")
        if len(command) >= 4 and command[1:4] == ["-m", "pip", "wheel"]:
            wheel_dir.mkdir(parents=True, exist_ok=True)
            wheel_path.write_bytes(b"wheel")
        if command[0].endswith("thesis-workbench"):
            return type("Completed", (), {"stdout": "lnu-checker-2026\n", "stderr": ""})()
        return type(
            "Completed",
            (),
            {"stdout": '{"status": "ok", "version": "0.1.2"}', "stderr": ""},
        )()

    monkeypatch.setattr(release_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(release_smoke, "_run_http_smoke", lambda **kwargs: {"status": "ok", "job_id": "job-1"})

    payload = release_smoke.run_release_smoke(
        work_dir=tmp_path,
        python_executable=sys.executable,
        state_root=state_root,
        runtime_root=runtime_root,
        command_timeout_seconds=123.0,
    )

    assert payload["status"] == "ok"
    assert payload["service_version"] == "0.1.2"
    assert payload["install"]["mode"] == "wheel"
    assert payload["distribution"]["wheel_path"] == str(wheel_path)
    assert payload["checks"]["doctor"]["status"] == "ok"
    assert payload["checks"]["profiles"]["status"] == "ok"
    assert payload["checks"]["http_smoke"]["status"] == "ok"
    assert any(
        command[1:4] == ["-m", "pip", "wheel"] and timeout == 123.0
        for command, timeout in calls
    )
    assert any(
        command[1:4] == ["-m", "pip", "wheel"]
        and "--wheel-dir" in command
        and ".[api]" in command
        and "--no-deps" not in command
        for command, _timeout in calls
    )
    assert any(
        command[1:4] == ["-m", "pip", "install"]
        and "--no-index" in command
        and "--find-links" in command
        and str(wheel_dir) in command
        and f"{wheel_path}[api]" in command
        for command, _timeout in calls
    )
    assert any(command[0].endswith("lnu-thesis-local") and "doctor" in command for command, _timeout in calls)
    assert any(command[0].endswith("thesis-workbench") and "profiles" in command for command, _timeout in calls)


def test_release_smoke_can_reuse_existing_wheelhouse_without_downloading_dependencies(monkeypatch, tmp_path):
    release_smoke = _load_release_smoke()
    calls: list[list[str]] = []
    work_dir = tmp_path / "work"
    venv_dir = work_dir / "venv"
    wheelhouse = tmp_path / "prebuilt-wheelhouse"
    wheelhouse.mkdir()
    wheel_path = wheelhouse / "thesis_format_tool-0.1.0-py3-none-any.whl"
    wheel_path.write_bytes(b"wheel")

    def fake_run(
        command,
        *,
        cwd=None,
        env=None,
        capture_output=False,
        text=True,
        check=True,
        timeout=None,
        encoding=None,
        errors=None,
    ):
        command = [str(item) for item in command]
        calls.append(command)
        if command[1:3] == ["-m", "venv"]:
            bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
            bin_dir.mkdir(parents=True, exist_ok=True)
            (bin_dir / ("python.exe" if sys.platform == "win32" else "python")).write_text("", encoding="utf-8")
            for script_name in ("lnu-thesis-local", "thesis-workbench"):
                suffix = ".exe" if sys.platform == "win32" else ""
                (bin_dir / f"{script_name}{suffix}").write_text("", encoding="utf-8")
        if command[0].endswith("thesis-workbench"):
            return type("Completed", (), {"stdout": "lnu-checker-2026\n", "stderr": ""})()
        return type("Completed", (), {"stdout": '{"status": "ok"}', "stderr": ""})()

    monkeypatch.setattr(release_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(release_smoke, "_run_http_smoke", lambda **kwargs: {"status": "ok", "job_id": "job-1"})

    payload = release_smoke.run_release_smoke(
        work_dir=work_dir,
        python_executable=sys.executable,
        wheelhouse=wheelhouse,
    )

    assert payload["distribution"]["wheel_path"] == str(wheel_path)
    assert payload["distribution"]["wheelhouse"] == str(wheelhouse.resolve())
    assert not any(command[1:4] == ["-m", "pip", "wheel"] for command in calls)
    assert any(
        command[1:4] == ["-m", "pip", "install"]
        and "--no-index" in command
        and "--find-links" in command
        and str(wheelhouse.resolve()) in command
        and f"{wheel_path}[api]" in command
        for command in calls
    )


def test_release_smoke_json_run_decodes_stdout_as_utf8(monkeypatch):
    release_smoke = _load_release_smoke()
    captured: dict[str, object] = {}

    def fake_run(
        command,
        *,
        cwd=None,
        env=None,
        capture_output=False,
        text=True,
        check=True,
        timeout=None,
        encoding=None,
        errors=None,
    ):
        captured["encoding"] = encoding
        captured["errors"] = errors
        return subprocess.CompletedProcess(command, 0, stdout='{"message": "论文格式检查"}', stderr="")

    monkeypatch.setattr(release_smoke.subprocess, "run", fake_run)

    payload = release_smoke._json_run(["python", "-m", "article_api.local_app", "doctor"])

    assert payload["message"] == "论文格式检查"
    assert captured == {"encoding": "utf-8", "errors": "replace"}


def test_release_smoke_rejects_prebuilt_wheelhouse_inside_cleaned_work_dir(monkeypatch, tmp_path):
    release_smoke = _load_release_smoke()
    work_dir = tmp_path / "work"
    wheelhouse = work_dir / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    wheel_path = wheelhouse / "thesis_format_tool-0.1.0-py3-none-any.whl"
    wheel_path.write_bytes(b"wheel")

    def fail_run(*args, **kwargs):
        raise AssertionError("release smoke should reject before running commands")

    monkeypatch.setattr(release_smoke.subprocess, "run", fail_run)

    with pytest.raises(RuntimeError, match="Prebuilt wheelhouse must be outside work-dir"):
        release_smoke.run_release_smoke(
            work_dir=work_dir,
            python_executable=sys.executable,
            wheelhouse=wheelhouse,
        )

    assert wheel_path.exists()


def test_release_smoke_http_flow_reuploads_repaired_docx_before_confirmed_pdf_review(monkeypatch, tmp_path):
    release_smoke = _load_release_smoke()
    popen_calls: list[list[str]] = []
    events: list[tuple[object, ...]] = []

    class FakeProcess:
        def __init__(self, command, **kwargs):
            popen_calls.append([str(item) for item in command])
            self.stdout = None
            self.stderr = None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(release_smoke.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(release_smoke, "_build_smoke_docx", lambda path, **_kwargs: path.write_bytes(b"source-docx"))
    monkeypatch.setattr(release_smoke, "_build_smoke_pdf", lambda path, **_kwargs: path.write_bytes(b"pdf"))
    monkeypatch.setattr(release_smoke, "_available_port", lambda: 49231)
    monkeypatch.setattr(release_smoke, "_wait_for_ready", lambda base_url: {"status": "ready"})

    def fake_upload(url, **kwargs):
        content = kwargs["file_path"].read_bytes()
        events.append(("upload", url, content))
        if url.endswith("/uploads/pdf"):
            return {"upload_id": "pdf-1"}
        return {"upload_id": "fixed-docx-2" if content == b"fixed-docx" else "source-docx-1"}

    def fake_request(url, **kwargs):
        events.append(("json", url, kwargs.get("method", "GET"), kwargs.get("payload")))
        if url.endswith("/render-review-jobs"):
            return {"job_id": "render-job"}
        if url.endswith("/jobs/render-job/result"):
            return {
                "result": {
                    "page_count": 1,
                    "evidence_trust": "user-confirmed",
                    "layout_decision_eligible": True,
                    "pdf_matches_docx_confirmed": True,
                    "summary": {
                        "pdf_matches_docx_confirmed": True,
                        "pdf_content_match_status": "matched",
                        "pdf_content_matched": True,
                    },
                }
            }
        if url.endswith("/jobs/apply-job/result"):
            return {"summary": {}}
        return {"job_id": "apply-job"}

    def fake_download(url, **_kwargs):
        events.append(("download", url))
        return b"fixed-docx"

    monkeypatch.setattr(release_smoke, "_post_multipart_file", fake_upload)
    monkeypatch.setattr(release_smoke, "_request_json", fake_request)
    monkeypatch.setattr(release_smoke, "_wait_for_job", lambda *args, **kwargs: {"status": "succeeded"})
    monkeypatch.setattr(release_smoke, "_request_bytes", fake_download)

    payload = release_smoke._run_http_smoke(
        venv_python=Path(sys.executable),
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        smoke_dir=tmp_path,
    )

    assert payload["status"] == "ok"
    assert payload["output_upload_id"] == "fixed-docx-2"
    assert payload["render_job_status"] == "succeeded"
    assert payload["render_page_count"] == 1
    assert payload["render_evidence_trust"] == "user-confirmed"
    assert payload["render_pdf_matches_docx_confirmed"] is True
    assert payload["render_pdf_content_match_status"] == "matched"
    assert payload["render_layout_decision_eligible"] is True
    assert events == [
        ("upload", "http://127.0.0.1:49231/uploads/docx", b"source-docx"),
        (
            "json",
            "http://127.0.0.1:49231/uploads/source-docx-1/jobs/apply",
            "POST",
            {"scopes": ["headings"], "runtime_root": str(tmp_path / "runtime"), "stage_input": True},
        ),
        ("json", "http://127.0.0.1:49231/jobs/apply-job/result", "GET", None),
        ("download", "http://127.0.0.1:49231/jobs/apply-job/artifacts/output/download"),
        ("upload", "http://127.0.0.1:49231/uploads/docx", b"fixed-docx"),
        ("upload", "http://127.0.0.1:49231/uploads/pdf", b"pdf"),
        (
            "json",
            "http://127.0.0.1:49231/uploads/fixed-docx-2/render-review-jobs",
            "POST",
            {"pdf_upload_id": "pdf-1", "pdf_matches_docx_confirmed": True},
        ),
        ("json", "http://127.0.0.1:49231/jobs/render-job/result", "GET", None),
    ]
    assert popen_calls == [
        [
            str(Path(sys.executable)),
            "-m",
            "article_api.local_app",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "49231",
            "--state-root",
            str(tmp_path / "state"),
            "--runtime-root",
            str(tmp_path / "runtime"),
        ]
    ]


def test_release_smoke_cli_reports_command_timeout_as_json(monkeypatch, capsys):
    release_smoke = _load_release_smoke()

    def fake_run_release_smoke(**kwargs):
        raise subprocess.TimeoutExpired(["python", "-m", "pip", "wheel"], 12.0)

    monkeypatch.setattr(release_smoke, "run_release_smoke", fake_run_release_smoke)

    exit_code = release_smoke.main(["--command-timeout-seconds", "12"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "command_timeout"
    assert payload["error"]["timeout_seconds"] == 12.0
    assert payload["error"]["command"] == ["python", "-m", "pip", "wheel"]
    assert payload["next_steps"]


def test_release_smoke_cli_writes_json_output(monkeypatch, capsys, tmp_path):
    release_smoke = _load_release_smoke()
    output_path = tmp_path / "release-smoke.json"

    monkeypatch.setattr(
        release_smoke,
        "run_release_smoke",
        lambda **kwargs: {"status": "ok", "checks": {"http_smoke": {"download_bytes": 123}}},
    )

    exit_code = release_smoke.main(["--json-output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert written == payload
