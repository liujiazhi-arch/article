from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


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
    eval_waits: list[str] = []
    download_path = tmp_path / "browser-smoke" / "downloaded-repaired.docx"
    pdf_path = tmp_path / "browser-smoke" / "browser_smoke.pdf"
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
        if command[1:3] == ["click", "[data-download-role='output']"]:
            browser_download = tmp_path / "browser-smoke" / ".playwright-cli" / "downloaded.docx"
            browser_download.parent.mkdir(parents=True, exist_ok=True)
            browser_download.write_bytes(b"docx")
            return type(
                "Completed",
                (),
                {"stdout": f'Downloaded file downloaded.docx to "{browser_download}"', "stderr": ""},
            )()
        if command[1:3] == ["console", "error"]:
            return type(
                "Completed",
                (),
                {
                    "stdout": "### Result\nTotal messages: 0 (Errors: 0, Warnings: 0)\n",
                    "stderr": "",
                },
            )()
        return type("Completed", (), {"stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(local_browser_smoke.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(local_browser_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(local_browser_smoke, "_available_port", lambda: 54321)
    monkeypatch.setattr(local_browser_smoke, "_wait_for_ready", lambda base_url: {"status": "ready"})
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_pdf", lambda path, **kwargs: path.write_bytes(b"%PDF"))
    monkeypatch.setattr(local_browser_smoke.zipfile, "is_zipfile", lambda path: True)
    monkeypatch.setattr(
        local_browser_smoke,
        "_wait_for_snapshot_text",
        lambda playwright_cli, expected_text, **kwargs: waited_for.append(expected_text) or "ok",
    )
    monkeypatch.setattr(
        local_browser_smoke,
        "_wait_for_eval_truthy",
        lambda playwright_cli, expression, **kwargs: eval_waits.append(expression) or "true",
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
    assert payload["render_evidence_trust"] == "user-confirmed"
    assert payload["render_evidence_status"] == "render-review-required"
    assert payload["render_layout_decision_eligible"] is True
    assert payload["render_pdf_content_match_status"] == "matched"
    assert payload["browser_evidence"]["history_pdf"] == {
        "document_name": "downloaded-repaired.docx",
        "pdf_name": "browser_smoke.pdf",
        "completed": True,
        "old_docx_reuse_blocked": True,
    }
    assert payload["browser_evidence"]["mobile"] == {
        "width": 390,
        "height": 844,
        "no_horizontal_overflow": True,
        "rule_spectrum_labels_visible": True,
    }
    assert payload["browser_evidence"]["desktop_compact"] == {
        "width": 1366,
        "height": 768,
        "no_horizontal_overflow": True,
        "rule_spectrum_labels_visible": True,
    }
    assert payload["browser_evidence"]["console_errors"] == {
        "automated": True,
        "command": "console error",
        "error_count": 0,
        "passed": True,
    }
    assert payload["screenshots"]["home"].endswith("local-console-home.png")
    assert payload["screenshots"]["repaired"].endswith("local-console-repaired.png")
    assert payload["screenshots"]["mobile"].endswith("local-console-mobile-result.png")
    assert payload["screenshots"]["desktop_compact"].endswith("local-console-1366-result.png")
    assert payload["screenshots"]["pdf_review"].endswith("local-console-pdf-review.png")
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
    assert [
        str(playwright_cli),
        "click",
        "[data-screen='workbench'] [data-action='choose-docx']",
    ] in commands
    assert [str(playwright_cli), "upload", str(tmp_path / "browser-smoke" / "browser_smoke.docx")] in commands
    assert [str(playwright_cli), "click", "[data-action='create-apply-job']"] in commands
    mobile_resize = commands.index([str(playwright_cli), "resize", "390", "844"])
    mobile_screenshot = next(
        index
        for index, command in enumerate(commands)
        if command[1] == "screenshot" and any("local-console-mobile-result.png" in part for part in command)
    )
    compact_resize = commands.index([str(playwright_cli), "resize", "1366", "768"], mobile_screenshot + 1)
    compact_screenshot = next(
        index
        for index, command in enumerate(commands)
        if command[1] == "screenshot" and any("local-console-1366-result.png" in part for part in command)
    )
    desktop_resize = commands.index([str(playwright_cli), "resize", "1440", "900"], compact_screenshot + 1)
    assert mobile_resize < mobile_screenshot < compact_resize < compact_screenshot < desktop_resize
    assert [str(playwright_cli), "click", "[data-download-role='output']"] in commands
    gate_nav = commands.index([str(playwright_cli), "click", ".scene-nav [data-screen-target='pdf-review']"])
    gate_attempt = commands.index([str(playwright_cli), "click", "[data-action='choose-pdf']"], gate_nav + 1)
    download = commands.index([str(playwright_cli), "click", "[data-download-role='output']"], gate_attempt + 1)
    repaired_upload = commands.index([str(playwright_cli), "upload", str(download_path)], download + 1)
    confirmation = commands.index([str(playwright_cli), "click", "#pdf-match-confirmation"], repaired_upload + 1)
    assert [str(playwright_cli), "click", ".scene-nav [data-screen-target='pdf-review']"] not in commands[
        repaired_upload + 1 : confirmation
    ]
    pdf_choice = commands.index([str(playwright_cli), "click", "[data-action='choose-pdf']"], confirmation + 1)
    commands.index([str(playwright_cli), "upload", str(pdf_path)], pdf_choice + 1)
    assert [
        str(playwright_cli),
        "click",
        "[data-pdf-issues] [data-issue-index='1']",
    ] in commands
    assert any(
        command[1] == "screenshot" and any("local-console-pdf-review.png" in part for part in command)
        for command in commands
    )
    history_after_review = commands.index(
        [str(playwright_cli), "click", ".scene-nav [data-screen-target='history']"],
        commands.index([str(playwright_cli), "upload", str(pdf_path)], pdf_choice + 1) + 1,
    )
    history_retry = commands.index(
        [str(playwright_cli), "click", "[data-action='choose-pdf']"],
        history_after_review + 1,
    )
    assert history_retry > history_after_review
    assert waited_for == [
        "上传论文开始修正",
        "修复方案已生成",
        "发现 ",
        "项需要你确认",
        "browser_smoke",
        "browser_smoke",
    ]
    for expected_eval in (
        "() => document.querySelectorAll('[data-result-heatmap] .pass, [data-result-heatmap] .warn').length > 0",
        "() => document.querySelector('[data-screen=\"result\"]')?.classList.contains('active') === true "
        "&& document.querySelector('[data-status-title]')?.textContent.trim() === '先上传修复稿'",
        "() => document.querySelector('[data-screen=\"pdf-review\"]')?.classList.contains('active') === true "
        "&& document.querySelector('[data-pdf-docx-file]')?.textContent.trim() === 'downloaded-repaired.docx' "
        "&& document.querySelector('[data-status-title]')?.textContent.trim() === '请导入修复稿 PDF'",
        "() => document.querySelector('[data-render-state]')?.textContent.trim() === '已完成' "
        "&& document.querySelector('[data-pdf-metric=\"issues\"]')?.textContent.trim() !== '--'",
    ):
        assert expected_eval in eval_waits
    assert (
        "async () => { const jobs = await fetch('/jobs?operation=render-verify&status=succeeded&limit=1')"
        ".then((response) => response.json()); if (!jobs.length) return false; "
        "const payload = await fetch(`/jobs/${encodeURIComponent(jobs[0].job_id)}/result`)"
        ".then((response) => response.json()); const result = payload.result || {}; "
        "const summary = result.summary || {}; "
        "const evidenceStatus = summary.render_evidence_status ?? result.render_evidence_status; "
        "return ['render-evidence-ready', 'render-review-required'].includes(evidenceStatus) "
        "&& (summary.layout_decision_eligible ?? result.layout_decision_eligible) === true "
        "&& (summary.pdf_content_match_status ?? result.pdf_content_match_status) === 'matched'; }"
    ) in eval_waits
    assert any(
        ".pdf-page-frame" in expression
        and "querySelector('img')" in expression
        and ".evidence-highlight" in expression
        and "naturalWidth" in expression
        for expression in eval_waits
    )
    assert any(
        "PDF复核" in expression and "data-history-job-id" in expression
        for expression in eval_waits
    )
    assert any(
        "downloaded-repaired.docx" in expression
        and "browser_smoke.pdf" in expression
        and "data-render-state" in expression
        for expression in eval_waits
    )
    assert any(
        "__renderJobIdsBeforeHistoryRetry" in expression
        and "先上传修复稿" in expression
        for expression in eval_waits
    )
    assert any(
        "document.documentElement.scrollWidth" in expression
        and "document.body.scrollWidth" in expression
        for expression in eval_waits
    )
    assert any(
        "data-result-heatmap" in expression
        and "querySelector('b')" in expression
        and "querySelector('small')" in expression
        and "getBoundingClientRect" in expression
        for expression in eval_waits
    )
    assert commands[-2:] == [
        [str(playwright_cli), "console", "error"],
        [str(playwright_cli), "close"],
    ]


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
        if command[1:3] == ["click", "[data-download-role='output']"]:
            browser_download = tmp_path / "browser-smoke" / ".playwright-cli" / "downloaded.docx"
            browser_download.parent.mkdir(parents=True, exist_ok=True)
            browser_download.write_bytes(b"docx")
            return type(
                "Completed",
                (),
                {"stdout": f'Downloaded file downloaded.docx to "{browser_download}"', "stderr": ""},
            )()
        if command[1:3] == ["console", "error"]:
            return type(
                "Completed",
                (),
                {
                    "stdout": "### Result\nTotal messages: 0 (Errors: 0, Warnings: 0)\n",
                    "stderr": "",
                },
            )()
        return type("Completed", (), {"stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(local_browser_smoke.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(local_browser_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(local_browser_smoke, "_available_port", lambda: 54321)
    monkeypatch.setattr(local_browser_smoke, "_wait_for_ready", lambda base_url: {"status": "ready"})
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_pdf", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke.zipfile, "is_zipfile", lambda path: True)
    monkeypatch.setattr(
        local_browser_smoke,
        "_wait_for_snapshot_text",
        lambda playwright_cli, expected_text, **kwargs: "ok",
    )
    monkeypatch.setattr(
        local_browser_smoke,
        "_wait_for_eval_truthy",
        lambda playwright_cli, expression, **kwargs: "true",
    )

    local_browser_smoke.run_local_browser_smoke(
        work_dir=tmp_path / "browser-smoke",
        python_executable=venv_python,
        playwright_cli=playwright_cli,
    )

    assert popen_calls[0][0] == str(venv_python.absolute())


def test_local_browser_smoke_close_failure_fails_after_server_cleanup(monkeypatch, tmp_path):
    local_browser_smoke = _load_local_browser_smoke()
    server_events: list[str] = []
    playwright_cli = tmp_path / "pwcli"
    playwright_cli.write_text("#!/bin/sh\n", encoding="utf-8")

    class FakeProcess:
        def terminate(self):
            server_events.append("terminate")

        def wait(self, timeout=None):
            server_events.append("wait")
            return 0

        def kill(self):
            server_events.append("kill")

    def fake_run(command, **_kwargs):
        command = [str(item) for item in command]
        if command[1:3] == ["click", "[data-download-role='output']"]:
            download = tmp_path / "browser-smoke" / ".playwright-cli" / "downloaded.docx"
            download.parent.mkdir(parents=True, exist_ok=True)
            download.write_bytes(b"docx")
            return type("Completed", (), {"stdout": f'Downloaded file downloaded.docx to "{download}"', "stderr": ""})()
        if command[1:3] == ["console", "error"]:
            return type("Completed", (), {"stdout": "Total messages: 0 (Errors: 0, Warnings: 0)", "stderr": ""})()
        if command[1:] == ["close"]:
            raise RuntimeError("pwcli close failed")
        return type("Completed", (), {"stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(local_browser_smoke.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())
    monkeypatch.setattr(local_browser_smoke.subprocess, "run", fake_run)
    monkeypatch.setattr(local_browser_smoke, "_available_port", lambda: 54321)
    monkeypatch.setattr(local_browser_smoke, "_wait_for_ready", lambda _base_url: {"status": "ready"})
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_docx", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke, "_build_smoke_pdf", lambda *args, **kwargs: None)
    monkeypatch.setattr(local_browser_smoke.zipfile, "is_zipfile", lambda _path: True)
    monkeypatch.setattr(local_browser_smoke, "_wait_for_snapshot_text", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(local_browser_smoke, "_wait_for_eval_truthy", lambda *args, **kwargs: "true")

    with pytest.raises(RuntimeError, match="close"):
        local_browser_smoke.run_local_browser_smoke(
            work_dir=tmp_path / "browser-smoke",
            playwright_cli=playwright_cli,
        )

    assert server_events == ["terminate", "wait"]


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
