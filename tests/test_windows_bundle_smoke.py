from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "windows_bundle_smoke.py"


def _load_windows_bundle_smoke():
    spec = importlib.util.spec_from_file_location("windows_bundle_smoke", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_bundle_zip(zip_path: Path, *, bundle_name: str = "论文格式检查本地版") -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{bundle_name}/app/Scripts/python.exe", b"python")
        archive.writestr(f"{bundle_name}/data/state/.keep", b"")
        archive.writestr(f"{bundle_name}/data/runtime/.keep", b"")
        archive.writestr(f"{bundle_name}/启动论文格式检查.bat", "@echo off\r\n")


def test_windows_bundle_smoke_extracts_bundle_runs_doctor_and_http_smoke(monkeypatch, tmp_path):
    windows_bundle_smoke = _load_windows_bundle_smoke()
    bundle_zip = tmp_path / "article-local-windows.zip"
    work_dir = tmp_path / "smoke-work"
    work_dir.mkdir()
    stale_file = work_dir / "stale.txt"
    stale_file.write_text("old", encoding="utf-8")
    _write_bundle_zip(bundle_zip)
    doctor_calls: list[tuple[list[str], Path | None, float | None]] = []
    http_calls: list[dict] = []

    def fake_json_run(command, *, cwd=None, timeout=None):
        doctor_calls.append(([str(item) for item in command], cwd, timeout))
        return {"status": "ok", "summary": {"headline": "ready"}}

    def fake_http_smoke(**kwargs):
        http_calls.append(kwargs)
        return {"status": "ok", "job_id": "job-1", "download_bytes": 456}

    monkeypatch.setattr(windows_bundle_smoke, "_json_run", fake_json_run)
    monkeypatch.setattr(windows_bundle_smoke.release_smoke, "_run_http_smoke", fake_http_smoke)

    payload = windows_bundle_smoke.run_windows_bundle_smoke(
        bundle_zip=bundle_zip,
        work_dir=work_dir,
        command_timeout_seconds=12.0,
    )

    bundle_root = work_dir / "论文格式检查本地版"
    python_exe = bundle_root / "app" / "Scripts" / "python.exe"
    state_root = bundle_root / "data" / "state"
    runtime_root = bundle_root / "data" / "runtime"
    assert payload["status"] == "ok"
    assert payload["bundle_root"] == str(bundle_root)
    assert payload["python"] == str(python_exe)
    assert payload["roots"] == {"state_root": str(state_root), "runtime_root": str(runtime_root)}
    assert payload["checks"]["doctor"] == {"status": "ok", "headline": "ready"}
    assert payload["checks"]["http_smoke"]["status"] == "ok"
    assert payload["download_bytes"] == 456
    assert not stale_file.exists()
    assert doctor_calls == [
        (
            [
                str(python_exe),
                "-m",
                "article_api.local_app",
                "doctor",
                "--state-root",
                str(state_root),
                "--runtime-root",
                str(runtime_root),
            ],
            bundle_root,
            12.0,
        )
    ]
    assert http_calls == [
        {
            "article_local": python_exe,
            "venv_python": python_exe,
            "state_root": state_root,
            "runtime_root": runtime_root,
            "smoke_dir": work_dir,
        }
    ]


def test_windows_bundle_smoke_rejects_ambiguous_bundle_roots(monkeypatch, tmp_path):
    windows_bundle_smoke = _load_windows_bundle_smoke()
    bundle_zip = tmp_path / "article-local-windows.zip"
    with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("one/app/Scripts/python.exe", b"python")
        archive.writestr("two/app/Scripts/python.exe", b"python")

    def fail_json_run(*args, **kwargs):
        raise AssertionError("doctor should not run for ambiguous bundles")

    monkeypatch.setattr(windows_bundle_smoke, "_json_run", fail_json_run)

    with pytest.raises(RuntimeError, match="Expected exactly one Windows bundle root"):
        windows_bundle_smoke.run_windows_bundle_smoke(
            bundle_zip=bundle_zip,
            work_dir=tmp_path / "work",
        )


def test_windows_bundle_smoke_cli_reports_command_timeout_as_json(monkeypatch, capsys, tmp_path):
    windows_bundle_smoke = _load_windows_bundle_smoke()
    bundle_zip = tmp_path / "article-local-windows.zip"
    _write_bundle_zip(bundle_zip)

    def fake_run_windows_bundle_smoke(**kwargs):
        raise subprocess.TimeoutExpired(["python.exe", "-m", "article_api.local_app", "doctor"], 7.0)

    monkeypatch.setattr(windows_bundle_smoke, "run_windows_bundle_smoke", fake_run_windows_bundle_smoke)

    exit_code = windows_bundle_smoke.main([str(bundle_zip), "--command-timeout-seconds", "7"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "command_timeout"
    assert payload["error"]["timeout_seconds"] == 7.0
    assert payload["error"]["command"] == ["python.exe", "-m", "article_api.local_app", "doctor"]
    assert payload["next_steps"]


def test_windows_bundle_smoke_cli_writes_json_output(monkeypatch, capsys, tmp_path):
    windows_bundle_smoke = _load_windows_bundle_smoke()
    bundle_zip = tmp_path / "article-local-windows.zip"
    output_path = tmp_path / "windows-bundle-smoke.json"
    _write_bundle_zip(bundle_zip)

    monkeypatch.setattr(
        windows_bundle_smoke,
        "run_windows_bundle_smoke",
        lambda **kwargs: {"status": "ok", "download_bytes": 789},
    )

    exit_code = windows_bundle_smoke.main([str(bundle_zip), "--json-output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert written == payload


def test_windows_bundle_smoke_emits_utf8_when_stdout_encoding_rejects_chinese(monkeypatch):
    windows_bundle_smoke = _load_windows_bundle_smoke()
    output = io.BytesIO()
    cp1252_stdout = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)

    windows_bundle_smoke._emit_payload({"status": "ok", "bundle_root": "论文格式检查本地版"})

    cp1252_stdout.flush()
    payload = json.loads(output.getvalue().decode("utf-8"))
    assert payload == {"status": "ok", "bundle_root": "论文格式检查本地版"}
