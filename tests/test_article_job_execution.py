from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from article_api import job_execution


def test_run_handler_subprocess_decodes_runner_stdout_as_utf8(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakeProcess:
        args = ["python", "-m", "article_api.job_runner", "request.json"]

        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured["encoding"] = kwargs.get("encoding")
            captured["errors"] = kwargs.get("errors")
            captured["text"] = kwargs.get("text")
            self._communicated = False

        def poll(self):
            return 0

        def communicate(self, timeout=None):
            self._communicated = True
            return json.dumps({"ok": True, "result": {"message": "论文格式检查"}}, ensure_ascii=False), ""

    monkeypatch.setattr(job_execution.subprocess, "Popen", FakeProcess)

    payload = job_execution.run_handler_subprocess(
        "apply",
        {"file_path": "demo.docx"},
        timeout_seconds=None,
        project_root=tmp_path,
        scripts_root=Path("scripts"),
    )

    assert payload == {"ok": True, "result": {"message": "论文格式检查"}}
    assert captured["text"] is True
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_run_handler_subprocess_drains_large_runner_output(monkeypatch, tmp_path):
    real_popen = subprocess.Popen

    def start_large_output(_command, **kwargs):
        script = 'import json; print(json.dumps({"ok": True, "result": {"text": "x" * 262144}}))'
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(job_execution.subprocess, "Popen", start_large_output)

    payload = job_execution.run_handler_subprocess(
        "render-verify",
        {"file_path": "demo.docx"},
        timeout_seconds=3.0,
        project_root=tmp_path,
        scripts_root=Path("scripts"),
    )

    assert len(payload["result"]["text"]) == 262144
