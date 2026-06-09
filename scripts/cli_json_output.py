from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence, TextIO


def _command_parts(command: Any) -> list[str]:
    if command is None:
        return []
    if isinstance(command, (str, bytes, Path)):
        return [str(command)]
    try:
        return [str(item) for item in command]
    except TypeError:
        return [str(command)]


def build_failed_json_payload(
    exc: Exception,
    *,
    next_steps: Sequence[str],
    timeout_type: str | None = None,
    timeout_message: str | None = None,
    called_process_type: str | None = None,
    called_process_message: str | None = None,
) -> dict[str, Any]:
    error = {
        "type": exc.__class__.__name__,
        "message": str(exc),
    }
    if isinstance(exc, subprocess.TimeoutExpired):
        if timeout_type is not None:
            error["type"] = timeout_type
        if timeout_message is not None:
            error["message"] = timeout_message
        error["command"] = _command_parts(exc.cmd)
        if exc.timeout is not None:
            error["timeout_seconds"] = float(exc.timeout)
    elif isinstance(exc, subprocess.CalledProcessError):
        if called_process_type is not None:
            error["type"] = called_process_type
        if called_process_message is not None:
            error["message"] = called_process_message
        error.update(
            {
                "command": _command_parts(exc.cmd),
                "returncode": exc.returncode,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            }
        )
    return {
        "status": "failed",
        "error": error,
        "next_steps": list(next_steps),
    }


def emit_json_payload(payload: dict[str, Any], *, json_output: Path | None = None, stdout: TextIO | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if json_output is not None:
        json_output = json_output.expanduser().resolve()
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(text, encoding="utf-8")

    stream = stdout or sys.stdout
    try:
        stream.write(text)
        stream.flush()
    except UnicodeEncodeError:
        stdout_buffer = getattr(stream, "buffer", None)
        if stdout_buffer is None:
            raise
        stdout_buffer.write(text.encode("utf-8"))
        stdout_buffer.flush()
