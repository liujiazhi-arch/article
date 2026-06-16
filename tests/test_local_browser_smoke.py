from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "local_browser_smoke.py"


def _load_local_browser_smoke():
    spec = importlib.util.spec_from_file_location("local_browser_smoke", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_browser_smoke_drives_real_browser_flow(monkeypatch, tmp_path):
    local_browser_smoke = _load_local_browser_smoke()
    commands: list[list[str]] = []
    popen_calls: list[list[str]] = []
    popen_envs: list[dict[str, str]] = []
    waited_for: list[str] = []
    download_path = tmp_path / "browser-smoke" / "downloaded-repaired.docx"
    playwright_cli = tmp_path / "pwcli"
    playwright_cli.write_text("#!/bin/sh\n", encoding="utf-8")

    class FakeProcess:
        def __init__(self, command, **kwargs):
            popen_calls.append([str(item) for item in command])
            popen_envs.append(dict(kwargs.get("env") or {}))
            self.stdout = None
            self.stderr = None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    def fake_run(command, *, cwd=None, capture_output=True, text=True, check=True, timeout=None):
        command = [str(item) for item in command]
        commands.append(command)
        if command[1:3] == ["click", "#report-output"]:
            browser_download = tmp_path / "browser-smoke" / ".playwright-cli" / "downloaded.docx"
            browser_download.parent.mkdir(parents=True, exist_ok=True)
            browser_download.write_bytes(b"docx")
            return type(
                "Completed",
                (),
                {"stdout": f'Downloaded file downloaded.docx to "{browser_download}"', "stderr": ""},
            )()
        return type("Completed", (), {"stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(local_browser_smoke.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(local_browser_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(local_browser_smoke, "_available_port", lambda: 54321)
    monkeypatch.setattr(local_browser_smoke, "_wait_for_ready", lambda base_url: {"status": "ready"})
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke.zipfile, "is_zipfile", lambda path: True)
    monkeypatch.setattr(
        local_browser_smoke,
        "_wait_for_snapshot_text",
        lambda playwright_cli, expected_text, **kwargs: waited_for.append(expected_text) or "ok",
    )

    payload = local_browser_smoke.run_local_browser_smoke(
        work_dir=tmp_path / "browser-smoke",
        python_executable=Path("/opt/python"),
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        playwright_cli=playwright_cli,
        command_timeout_seconds=30.0,
    )

    assert payload["status"] == "ok"
    assert payload["base_url"] == "http://127.0.0.1:54321"
    assert payload["download_bytes"] == 4
    assert payload["screenshots"]["home"].endswith("local-console-home.png")
    assert payload["screenshots"]["repaired"].endswith("local-console-repaired.png")
    assert popen_calls == [
        [
            "/opt/python",
            "-m",
            "article_api.local_app",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "54321",
            "--state-root",
            str(tmp_path / "state"),
            "--runtime-root",
            str(tmp_path / "runtime"),
        ]
    ]
    assert str(PROJECT_ROOT / "scripts") in popen_envs[0]["PYTHONPATH"]
    assert [str(playwright_cli), "open", "http://127.0.0.1:54321"] in commands
    assert any(
        command[1] == "screenshot" and any("local-console-home.png" in part for part in command)
        for command in commands
    )
    assert [str(playwright_cli), "click", "label[for='paper-file']"] in commands
    assert [str(playwright_cli), "upload", str(tmp_path / "browser-smoke" / "browser_smoke.docx")] in commands
    assert [str(playwright_cli), "click", "#run-all-button"] in commands
    assert [str(playwright_cli), "click", "#report-action-button"] in commands
    assert [str(playwright_cli), "click", "#report-output"] in commands
    assert waited_for == ["已上传", "方案已生成", "修复完成"]
    assert commands[-1] == [str(playwright_cli), "close"]


def test_local_browser_smoke_preserves_python_symlink(monkeypatch, tmp_path):
    local_browser_smoke = _load_local_browser_smoke()
    commands: list[list[str]] = []
    popen_calls: list[list[str]] = []
    playwright_cli = tmp_path / "pwcli"
    playwright_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    venv_python = tmp_path / "venv" / "bin" / "python"
    real_python = tmp_path / "python-real"
    venv_python.parent.mkdir(parents=True)
    real_python.write_text("#!/bin/sh\n", encoding="utf-8")
    venv_python.symlink_to(real_python)

    class FakeProcess:
        def __init__(self, command, **_kwargs):
            popen_calls.append([str(item) for item in command])

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    def fake_run(command, *, cwd=None, capture_output=True, text=True, check=True, timeout=None):
        command = [str(item) for item in command]
        commands.append(command)
        if command[1:3] == ["click", "#report-output"]:
            browser_download = tmp_path / "browser-smoke" / ".playwright-cli" / "downloaded.docx"
            browser_download.parent.mkdir(parents=True, exist_ok=True)
            browser_download.write_bytes(b"docx")
            return type(
                "Completed",
                (),
                {"stdout": f'Downloaded file downloaded.docx to "{browser_download}"', "stderr": ""},
            )()
        return type("Completed", (), {"stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(local_browser_smoke.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(local_browser_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(local_browser_smoke, "_available_port", lambda: 54321)
    monkeypatch.setattr(local_browser_smoke, "_wait_for_ready", lambda base_url: {"status": "ready"})
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke.zipfile, "is_zipfile", lambda path: True)
    monkeypatch.setattr(
        local_browser_smoke,
        "_wait_for_snapshot_text",
        lambda playwright_cli, expected_text, **kwargs: "ok",
    )

    local_browser_smoke.run_local_browser_smoke(
        work_dir=tmp_path / "browser-smoke",
        python_executable=venv_python,
        playwright_cli=playwright_cli,
    )

    assert popen_calls[0][0] == str(venv_python.absolute())


def test_local_browser_smoke_cli_reports_missing_playwright_as_json(monkeypatch, capsys, tmp_path):
    local_browser_smoke = _load_local_browser_smoke()

    def fake_run_local_browser_smoke(**kwargs):
        raise RuntimeError("Playwright CLI wrapper does not exist: /missing/pwcli")

    monkeypatch.setattr(local_browser_smoke, "run_local_browser_smoke", fake_run_local_browser_smoke)

    exit_code = local_browser_smoke.main(["--work-dir", str(tmp_path)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "RuntimeError"
    assert "Playwright CLI wrapper" in payload["error"]["message"]
    assert "next_steps" in payload


def test_local_browser_smoke_cli_writes_json_output(monkeypatch, capsys, tmp_path):
    local_browser_smoke = _load_local_browser_smoke()
    output_path = tmp_path / "browser-smoke.json"

    monkeypatch.setattr(
        local_browser_smoke,
        "run_local_browser_smoke",
        lambda **kwargs: {"status": "ok", "download_bytes": 456},
    )

    exit_code = local_browser_smoke.main(["--work-dir", str(tmp_path / "work"), "--json-output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert written == payload
