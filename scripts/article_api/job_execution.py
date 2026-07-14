from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

from article_api import errors as api_errors


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"


def handler_request(resolved_request: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(resolved_request)
    payload.pop("stage_input", None)
    payload.pop("runtime_root", None)
    payload.pop("upload_id", None)
    payload.pop("docx_upload_id", None)
    payload.pop("pdf_upload_id", None)
    payload.pop("source_file_path", None)
    payload.pop("source_display_name", None)
    payload.pop("pdf_display_name", None)
    payload.pop("workflow_mode", None)
    payload.pop("output_dir", None)
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
    return api_errors.error_payload(
        "worker_timeout",
        exc_type="TimeoutExpired",
        message=f"Job attempt exceeded timeout of {timeout_seconds} seconds",
        http_status=504,
    )


def transient_internal_error_payload(message: str) -> dict[str, Any]:
    return api_errors.error_payload("internal_error", exc_type="RuntimeError", message=message, http_status=500)


def _communicate_process(process, *, timeout_seconds: float | None, on_heartbeat=None) -> tuple[str, str]:
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if timeout_seconds is not None and elapsed >= float(timeout_seconds):
            process.kill()
            process.communicate()
            raise subprocess.TimeoutExpired(process.args, timeout=timeout_seconds)
        wait_seconds = 1.0
        if timeout_seconds is not None:
            wait_seconds = min(wait_seconds, max(float(timeout_seconds) - elapsed, 0.001))
        try:
            return process.communicate(timeout=wait_seconds)
        except subprocess.TimeoutExpired:
            if on_heartbeat is not None:
                on_heartbeat()


def run_handler_subprocess(
    operation: str,
    request: dict[str, Any],
    *,
    timeout_seconds: float | None,
    on_heartbeat=None,
    on_phase=None,
    project_root: Path = PROJECT_ROOT,
    scripts_root: Path = SCRIPTS_ROOT,
) -> dict[str, Any]:
    request_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump({"operation": operation, "request": request}, handle, ensure_ascii=False, sort_keys=True)
            request_path = handle.name
        process = subprocess.Popen(
            [sys.executable, "-m", "article_api.job_runner", request_path],
            cwd=str(project_root),
            env=subprocess_env(scripts_root=scripts_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if on_phase is not None:
            on_phase("processing")
        stdout, stderr = _communicate_process(
            process,
            timeout_seconds=timeout_seconds,
            on_heartbeat=on_heartbeat,
        )
    finally:
        if request_path:
            try:
                os.unlink(request_path)
            except FileNotFoundError:
                pass

    stdout = (stdout or "").strip()
    if not stdout:
        stderr = (stderr or "").strip()
        raise RuntimeError(f"Job runner returned no payload for {operation}: {stderr or 'empty stdout'}")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Job runner returned malformed JSON for {operation}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Job runner returned invalid payload type for {operation}")
    return payload


def execute_job_attempt(
    operation: str,
    resolved_request: dict[str, Any],
    *,
    run_subprocess=run_handler_subprocess,
    on_heartbeat=None,
    on_phase=None,
) -> dict[str, Any]:
    try:
        payload = run_subprocess(
            operation,
            handler_request(resolved_request),
            timeout_seconds=resolved_request.get("timeout_seconds"),
            on_heartbeat=on_heartbeat,
            on_phase=on_phase,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": timeout_error_payload(resolved_request.get("timeout_seconds"))}
    except ValueError as exc:
        return {"ok": False, "error": api_errors.value_error_payload(exc)}
    except Exception as exc:
        return {"ok": False, "error": transient_internal_error_payload(str(exc))}
    if not isinstance(payload, dict) or "ok" not in payload:
        return {
            "ok": False,
            "error": transient_internal_error_payload(f"Malformed job runner payload for {operation}"),
        }
    return payload


def is_retryable_error(error: dict[str, Any]) -> bool:
    return bool(api_errors.normalize_error_payload(error).get("retryable"))
