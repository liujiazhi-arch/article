from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"


def handler_request(resolved_request: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(resolved_request)
    payload.pop("stage_input", None)
    payload.pop("runtime_root", None)
    payload.pop("upload_id", None)
    payload.pop("source_file_path", None)
    payload.pop("source_display_name", None)
    payload.pop("max_attempts", None)
    payload.pop("retry_delay_seconds", None)
    payload.pop("timeout_seconds", None)
    payload.pop("retry_of_job_id", None)
    payload.pop("attempt_count", None)
    return payload


def subprocess_env(*, scripts_root: Path = SCRIPTS_ROOT) -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(scripts_root) if not python_path else f"{scripts_root}{os.pathsep}{python_path}"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def timeout_error_payload(timeout_seconds: float | None) -> dict[str, Any]:
    return {
        "code": "worker_timeout",
        "type": "TimeoutExpired",
        "message": f"Job attempt exceeded timeout of {timeout_seconds} seconds",
        "http_status": 504,
    }


def transient_internal_error_payload(message: str) -> dict[str, Any]:
    return {
        "code": "internal_error",
        "type": "RuntimeError",
        "message": message,
        "http_status": 500,
    }


def run_handler_subprocess(
    operation: str,
    request: dict[str, Any],
    *,
    timeout_seconds: float | None,
    project_root: Path = PROJECT_ROOT,
    scripts_root: Path = SCRIPTS_ROOT,
) -> dict[str, Any]:
    request_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump({"operation": operation, "request": request}, handle, ensure_ascii=False, sort_keys=True)
            request_path = handle.name
        completed = subprocess.run(
            [sys.executable, "-m", "article_api.job_runner", request_path],
            cwd=str(project_root),
            env=subprocess_env(scripts_root=scripts_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    finally:
        if request_path:
            try:
                os.unlink(request_path)
            except FileNotFoundError:
                pass

    stdout = completed.stdout.strip()
    if not stdout:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"Job runner returned no payload for {operation}: {stderr or 'empty stdout'}")
    payload = json.loads(stdout)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Job runner returned invalid payload type for {operation}")
    return payload


def execute_job_attempt(
    operation: str,
    resolved_request: dict[str, Any],
    *,
    run_subprocess=run_handler_subprocess,
) -> dict[str, Any]:
    try:
        payload = run_subprocess(
            operation,
            handler_request(resolved_request),
            timeout_seconds=resolved_request.get("timeout_seconds"),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": timeout_error_payload(resolved_request.get("timeout_seconds"))}
    except Exception as exc:
        return {"ok": False, "error": transient_internal_error_payload(str(exc))}
    if not isinstance(payload, dict) or "ok" not in payload:
        return {
            "ok": False,
            "error": transient_internal_error_payload(f"Malformed job runner payload for {operation}"),
        }
    return payload


def is_retryable_error(error: dict[str, Any]) -> bool:
    return error.get("code") in {"internal_error", "worker_timeout"}
