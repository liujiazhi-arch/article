from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import subprocess

from cli_json_output import build_failed_json_payload, emit_json_payload


class _Utf8FallbackStdout:
    def __init__(self) -> None:
        self.buffer = BytesIO()

    def write(self, text: str) -> int:
        raise UnicodeEncodeError("ascii", text, 0, 1, "not encodable")

    def flush(self) -> None:
        pass


def test_emit_json_payload_writes_stdout_and_optional_file(tmp_path, capsys):
    output_path = tmp_path / "payload.json"

    emit_json_payload({"status": "ok", "message": "论文"}, json_output=output_path)

    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == {"message": "论文", "status": "ok"}
    assert file_payload == stdout_payload


def test_emit_json_payload_falls_back_to_utf8_buffer_for_restricted_stdout():
    stdout = _Utf8FallbackStdout()

    emit_json_payload({"message": "论文"}, stdout=stdout)

    assert json.loads(stdout.buffer.getvalue().decode("utf-8")) == {"message": "论文"}


def test_build_failed_json_payload_adds_timeout_command_context():
    exc = subprocess.TimeoutExpired([Path("/opt/python"), "-m", "pip"], 9.5)

    payload = build_failed_json_payload(
        exc,
        next_steps=["Retry with a larger timeout."],
        timeout_type="command_timeout",
        timeout_message="Command timed out before smoke checks finished.",
    )

    assert payload == {
        "status": "failed",
        "error": {
            "type": "command_timeout",
            "message": "Command timed out before smoke checks finished.",
            "command": ["/opt/python", "-m", "pip"],
            "timeout_seconds": 9.5,
        },
        "next_steps": ["Retry with a larger timeout."],
    }


def test_build_failed_json_payload_adds_called_process_context():
    exc = subprocess.CalledProcessError(
        2,
        ["python", "-m", "article_api.local_app", "doctor"],
        output="stdout text",
        stderr="stderr text",
    )

    payload = build_failed_json_payload(
        exc,
        next_steps=["Inspect the failed command."],
        called_process_type="command_failed",
    )

    assert payload["status"] == "failed"
    assert payload["error"] == {
        "type": "command_failed",
        "message": str(exc),
        "command": ["python", "-m", "article_api.local_app", "doctor"],
        "returncode": 2,
        "stdout": "stdout text",
        "stderr": "stderr text",
    }
    assert payload["next_steps"] == ["Inspect the failed command."]
