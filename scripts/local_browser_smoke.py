from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Sequence
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_smoke


DEFAULT_WORK_DIR = Path(".local_browser_smoke")
DEFAULT_COMMAND_TIMEOUT_SECONDS = 300.0
DEFAULT_PLAYWRIGHT_CLI = Path.home() / ".codex" / "skills" / "playwright" / "scripts" / "playwright_cli.sh"

_available_port = release_smoke._available_port
_build_smoke_docx = release_smoke._build_smoke_docx
_wait_for_ready = release_smoke._wait_for_ready


def _run(
    command: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(item) for item in command],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    if "### Error" in completed.stdout or "### Error" in completed.stderr:
        raise RuntimeError(
            "Command reported an error: "
            + " ".join(str(item) for item in command)
            + "\n"
            + completed.stdout
            + completed.stderr
        )
    return completed


def _run_playwright(
    playwright_cli: Path,
    *args: str | Path,
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    return _run([playwright_cli, *args], cwd=cwd, timeout=timeout)


def _js_string(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _prepare_work_dir(work_dir: Path) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)


def _server_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    scripts_path = str(SCRIPT_DIR)
    env["PYTHONPATH"] = scripts_path if not existing else os.pathsep.join([scripts_path, existing])
    return env


def _wait_for_snapshot_text(
    playwright_cli: Path,
    expected_text: str,
    *,
    cwd: Path,
    timeout: float,
) -> str:
    deadline = release_smoke.time.monotonic() + timeout
    last_output = ""
    while release_smoke.time.monotonic() < deadline:
        completed = _run_playwright(playwright_cli, "snapshot", cwd=cwd, timeout=min(30.0, timeout))
        last_output = completed.stdout
        if expected_text in completed.stdout:
            return completed.stdout
        release_smoke.time.sleep(1.0)
    raise RuntimeError(f"Timed out waiting for browser text {expected_text!r}. Last snapshot:\n{last_output}")


def _download_path_from_output(output: str, *, cwd: Path) -> Path | None:
    match = re.search(r'Downloaded file .+ to "([^"]+)"', output)
    if not match:
        return None
    path = Path(match.group(1))
    return path if path.is_absolute() else cwd / path


def run_local_browser_smoke(
    *,
    work_dir: str | Path = DEFAULT_WORK_DIR,
    python_executable: str | Path = sys.executable,
    state_root: str | Path | None = None,
    runtime_root: str | Path | None = None,
    playwright_cli: str | Path = DEFAULT_PLAYWRIGHT_CLI,
    command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    smoke_dir = Path(work_dir).expanduser().resolve()
    python_path = Path(python_executable).expanduser().resolve()
    pwcli_path = Path(playwright_cli).expanduser().resolve()
    timeout = float(command_timeout_seconds)

    if not pwcli_path.exists():
        raise RuntimeError(f"Playwright CLI wrapper does not exist: {pwcli_path}")

    _prepare_work_dir(smoke_dir)
    state_root_path = Path(state_root).expanduser().resolve() if state_root is not None else smoke_dir / "state"
    runtime_root_path = Path(runtime_root).expanduser().resolve() if runtime_root is not None else smoke_dir / "runtime"
    state_root_path.mkdir(parents=True, exist_ok=True)
    runtime_root_path.mkdir(parents=True, exist_ok=True)

    docx_path = smoke_dir / "browser_smoke.docx"
    _build_smoke_docx(docx_path, python_executable=python_path)

    port = _available_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            str(python_path),
            "-m",
            "article_api.local_app",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--state-root",
            str(state_root_path),
            "--runtime-root",
            str(runtime_root_path),
        ],
        cwd=str(smoke_dir),
        env=_server_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    home_screenshot = smoke_dir / "local-console-home.png"
    repaired_screenshot = smoke_dir / "local-console-repaired.png"
    download_path = smoke_dir / "downloaded-repaired.docx"
    payload: dict[str, Any] | None = None
    try:
        ready = _wait_for_ready(base_url)
        _run_playwright(pwcli_path, "open", base_url, cwd=smoke_dir, timeout=timeout)
        _run_playwright(
            pwcli_path,
            "screenshot",
            "--filename",
            home_screenshot,
            "--full-page",
            cwd=smoke_dir,
            timeout=timeout,
        )
        _run_playwright(pwcli_path, "click", "label[for='paper-file']", cwd=smoke_dir, timeout=timeout)
        _run_playwright(pwcli_path, "upload", docx_path, cwd=smoke_dir, timeout=timeout)
        _wait_for_snapshot_text(pwcli_path, "已上传", cwd=smoke_dir, timeout=timeout)
        _run_playwright(pwcli_path, "click", "#run-all-button", cwd=smoke_dir, timeout=timeout)
        _wait_for_snapshot_text(pwcli_path, "方案已生成", cwd=smoke_dir, timeout=timeout)
        _run_playwright(pwcli_path, "click", "#report-action-button", cwd=smoke_dir, timeout=timeout)
        _wait_for_snapshot_text(pwcli_path, "修复完成", cwd=smoke_dir, timeout=timeout)
        _run_playwright(
            pwcli_path,
            "screenshot",
            "--filename",
            repaired_screenshot,
            "--full-page",
            cwd=smoke_dir,
            timeout=timeout,
        )
        download_result = _run_playwright(pwcli_path, "click", "#report-output", cwd=smoke_dir, timeout=timeout)
        downloaded_by_browser = _download_path_from_output(download_result.stdout, cwd=smoke_dir)
        if downloaded_by_browser and downloaded_by_browser.exists():
            shutil.copy2(downloaded_by_browser, download_path)
        if not download_path.exists():
            raise RuntimeError("Browser smoke did not download a repaired docx")
        if not zipfile.is_zipfile(download_path):
            raise RuntimeError(f"Downloaded repaired docx is not a valid docx package: {download_path}")
        payload = {
            "status": "ok",
            "base_url": base_url,
            "ready": ready.get("status"),
            "work_dir": str(smoke_dir),
            "source_docx": str(docx_path),
            "downloaded_docx": str(download_path),
            "download_bytes": download_path.stat().st_size,
            "screenshots": {
                "home": str(home_screenshot),
                "repaired": str(repaired_screenshot),
            },
        }
    finally:
        try:
            _run_playwright(pwcli_path, "close", cwd=smoke_dir, timeout=30.0)
        except Exception:
            pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    assert payload is not None
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local_browser_smoke.py")
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--state-root")
    parser.add_argument("--runtime-root")
    parser.add_argument("--playwright-cli", default=str(DEFAULT_PLAYWRIGHT_CLI))
    parser.add_argument("--command-timeout-seconds", type=float, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    parser.add_argument("--json-output", type=Path, help="Write the final JSON payload to this path")
    return parser


def _format_error(exc: Exception) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
        "next_steps": [
            "Install Node.js/npm and Playwright browsers if the Playwright CLI wrapper cannot start.",
            "Inspect the local service output and screenshots under the smoke work directory.",
        ],
    }
    if isinstance(exc, subprocess.CalledProcessError):
        payload["error"].update(
            {
                "command": [str(item) for item in (exc.cmd or [])],
                "returncode": exc.returncode,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            }
        )
    if isinstance(exc, subprocess.TimeoutExpired):
        payload["error"].update(
            {
                "command": [str(item) for item in (exc.cmd or [])],
                "timeout_seconds": float(exc.timeout),
            }
        )
    return payload


def _emit_payload(payload: dict[str, Any], *, json_output: Path | None = None) -> None:
    if json_output is not None:
        json_output = json_output.expanduser().resolve()
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = run_local_browser_smoke(
            work_dir=args.work_dir,
            python_executable=args.python_executable,
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            playwright_cli=args.playwright_cli,
            command_timeout_seconds=float(args.command_timeout_seconds),
        )
    except Exception as exc:
        _emit_payload(_format_error(exc), json_output=args.json_output)
        return 1
    _emit_payload(payload, json_output=args.json_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
