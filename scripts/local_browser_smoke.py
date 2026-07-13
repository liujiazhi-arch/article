from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, NamedTuple, Sequence
import zipfile

from cli_json_output import build_failed_json_payload as _build_failed_payload
from cli_json_output import emit_json_payload as _emit_payload
from smoke_workdir_utils import prepare_work_dir


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_smoke


DEFAULT_WORK_DIR = Path(".local_browser_smoke")
DEFAULT_COMMAND_TIMEOUT_SECONDS = 300.0
DEFAULT_PLAYWRIGHT_CLI = Path.home() / ".codex" / "skills" / "playwright" / "scripts" / "playwright_cli.sh"

_available_port = release_smoke._available_port
_build_smoke_docx = release_smoke._build_smoke_docx
_build_smoke_pdf = release_smoke._build_smoke_pdf
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


def _wait_for_eval_truthy(
    playwright_cli: Path,
    expression: str,
    *,
    cwd: Path,
    timeout: float,
) -> str:
    deadline = release_smoke.time.monotonic() + timeout
    last_output = ""
    while release_smoke.time.monotonic() < deadline:
        completed = _run_playwright(playwright_cli, "eval", expression, cwd=cwd, timeout=min(30.0, timeout))
        last_output = completed.stdout.strip()
        if re.search(r"^true$", last_output, flags=re.MULTILINE):
            return last_output
        release_smoke.time.sleep(1.0)
    raise RuntimeError(f"Timed out waiting for browser expression {expression!r}. Last output:\n{last_output}")


def _download_path_from_output(output: str, *, cwd: Path) -> Path | None:
    match = re.search(r'Downloaded file .+ to "([^"]+)"', output)
    if not match:
        return None
    path = Path(match.group(1))
    return path if path.is_absolute() else cwd / path


def _console_error_count(output: str) -> int:
    match = re.search(r"Total messages:\s*\d+\s*\(Errors:\s*(\d+),\s*Warnings:\s*\d+\)", output)
    if not match:
        raise RuntimeError("Playwright console error output could not be verified.")
    return int(match.group(1))


class _SmokeFiles(NamedTuple):
    source_docx: Path
    pdf: Path
    downloaded_docx: Path
    home_screenshot: Path
    repaired_screenshot: Path
    mobile_screenshot: Path


_HEATMAP_READY = "() => document.querySelectorAll('[data-result-heatmap] .pass, [data-result-heatmap] .warn').length > 0"
_MOBILE_NO_OVERFLOW = (
    "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1 "
    "&& document.body.scrollWidth <= document.documentElement.clientWidth + 1"
)
_MOBILE_LABELS_VISIBLE = (
    "() => { const items = Array.from(document.querySelectorAll('[data-result-heatmap] > span')); "
    "return items.length > 0 && items.every((item) => { "
    "const label = item.querySelector('b'); const status = item.querySelector('small'); "
    "if (!label?.textContent.trim() || !status?.textContent.trim()) return false; "
    "const labelRect = label.getBoundingClientRect(); const statusRect = status.getBoundingClientRect(); "
    "return labelRect.width > 0 && labelRect.height > 0 "
    "&& statusRect.width > 0 && statusRect.height > 0 "
    "&& getComputedStyle(label).visibility !== 'hidden' "
    "&& getComputedStyle(status).visibility !== 'hidden'; }); }"
)
_FRESH_DOCX_GATE = (
    "() => document.querySelector('[data-screen=\"result\"]')?.classList.contains('active') === true "
    "&& document.querySelector('[data-status-title]')?.textContent.trim() === '先上传修复稿'"
)
_REPAIRED_DOCX_READY = (
    "() => document.querySelector('[data-docx-file]')?.textContent.trim() === 'downloaded-repaired.docx' "
    "&& document.querySelector('[data-status-title]')?.textContent.trim() === '修复方案已生成'"
)
_PDF_REVIEW_READY = (
    "() => document.querySelector('[data-render-state]')?.textContent.trim() === '已完成' "
    "&& document.querySelector('[data-pdf-metric=\"issues\"]')?.textContent.trim() !== '--'"
)
_PDF_EVIDENCE_GEOMETRY_READY = (
    "() => { const stage = document.querySelector('[data-pdf-stage]'); "
    "const frame = stage?.querySelector('.pdf-page-frame'); "
    "const image = frame?.querySelector('img'); "
    "const highlight = frame?.querySelector('.evidence-highlight'); "
    "if (!stage || !frame || !image || !highlight || !image.complete || image.naturalWidth <= 0) return false; "
    "const stageRect = stage.getBoundingClientRect(); const frameRect = frame.getBoundingClientRect(); "
    "const imageRect = image.getBoundingClientRect(); const highlightRect = highlight.getBoundingClientRect(); "
    "return getComputedStyle(highlight).position === 'absolute' "
    "&& frameRect.width > 0 && frameRect.height > 0 "
    "&& frameRect.left >= stageRect.left - 1 && frameRect.right <= stageRect.right + 1 "
    "&& frameRect.top >= stageRect.top - 1 && frameRect.bottom <= stageRect.bottom + 1 "
    "&& Math.abs(frameRect.width - imageRect.width) <= 1 "
    "&& Math.abs(frameRect.height - imageRect.height) <= 1 "
    "&& highlightRect.left >= frameRect.left - 1 && highlightRect.right <= frameRect.right + 1 "
    "&& highlightRect.top >= frameRect.top - 1 && highlightRect.bottom <= frameRect.bottom + 1; }"
)
_PDF_TRUST_READY = (
    "async () => { const jobs = await fetch('/jobs?operation=render-verify&status=succeeded&limit=1')"
    ".then((response) => response.json()); if (!jobs.length) return false; "
    "const payload = await fetch(`/jobs/${encodeURIComponent(jobs[0].job_id)}/result`)"
    ".then((response) => response.json()); const result = payload.result || {}; "
    "return (result.summary?.evidence_trust ?? result.evidence_trust) === 'user-confirmed' "
    "&& (result.summary?.pdf_matches_docx_confirmed ?? result.pdf_matches_docx_confirmed) === true; }"
)
_REMEMBER_RENDER_JOBS = (
    "async () => { const jobs = await fetch('/jobs?operation=render-verify&status=succeeded')"
    ".then((response) => response.json()); "
    "window.__renderJobIdsBeforeHistoryRetry = jobs.map((job) => job.job_id).sort(); "
    "return jobs.length > 0; }"
)
_OPEN_PDF_HISTORY = (
    "() => { const button = Array.from(document.querySelectorAll('[data-history-job-id]'))"
    ".find((item) => item.textContent.includes('PDF复核')); "
    "if (!button) return false; button.click(); return true; }"
)
_HISTORY_RETRY_BLOCKED = (
    "async () => { const jobs = await fetch('/jobs?operation=render-verify&status=succeeded')"
    ".then((response) => response.json()); "
    "const ids = jobs.map((job) => job.job_id).sort(); "
    "return JSON.stringify(ids) === JSON.stringify(window.__renderJobIdsBeforeHistoryRetry) "
    "&& document.querySelector('[data-screen=\"result\"]')?.classList.contains('active') === true "
    "&& document.querySelector('[data-status-title]')?.textContent.trim() === '先上传修复稿'; }"
)


def _capture_screenshot(playwright_cli: Path, path: Path, *, cwd: Path, timeout: float) -> None:
    _run_playwright(
        playwright_cli,
        "screenshot",
        "--filename",
        path,
        "--full-page",
        cwd=cwd,
        timeout=timeout,
    )


def _run_upload_repair_flow(
    playwright_cli: Path,
    files: _SmokeFiles,
    *,
    base_url: str,
    cwd: Path,
    timeout: float,
) -> None:
    _run_playwright(playwright_cli, "open", base_url, cwd=cwd, timeout=timeout)
    _capture_screenshot(playwright_cli, files.home_screenshot, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", ".cover-actions [data-action='enter-workbench']", cwd=cwd, timeout=timeout)
    _wait_for_snapshot_text(playwright_cli, "上传论文开始修正", cwd=cwd, timeout=timeout)
    _run_playwright(
        playwright_cli,
        "click",
        "[data-screen='workbench'] [data-action='choose-docx']",
        cwd=cwd,
        timeout=timeout,
    )
    _run_playwright(playwright_cli, "upload", files.source_docx, cwd=cwd, timeout=timeout)
    for text in ("修复方案已生成", "发现 ", "项需要你确认"):
        _wait_for_snapshot_text(playwright_cli, text, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-action='create-apply-job']", cwd=cwd, timeout=timeout)
    result_snapshot = _wait_for_snapshot_text(playwright_cli, "browser_smoke", cwd=cwd, timeout=timeout)
    if "等待修复结果" in result_snapshot:
        raise RuntimeError("Result panel did not replace the placeholder file name")
    _wait_for_eval_truthy(playwright_cli, _HEATMAP_READY, cwd=cwd, timeout=timeout)


def _verify_mobile_result(playwright_cli: Path, files: _SmokeFiles, *, cwd: Path, timeout: float) -> None:
    _run_playwright(playwright_cli, "resize", "390", "844", cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _MOBILE_NO_OVERFLOW, cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _MOBILE_LABELS_VISIBLE, cwd=cwd, timeout=timeout)
    _capture_screenshot(playwright_cli, files.mobile_screenshot, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "resize", "1440", "900", cwd=cwd, timeout=timeout)
    _capture_screenshot(playwright_cli, files.repaired_screenshot, cwd=cwd, timeout=timeout)


def _store_downloaded_docx(output: str, *, cwd: Path, target: Path) -> None:
    browser_path = _download_path_from_output(output, cwd=cwd)
    if browser_path and browser_path.exists():
        shutil.copy2(browser_path, target)
    if not target.exists():
        raise RuntimeError("Browser smoke did not download a repaired docx")
    if not zipfile.is_zipfile(target):
        raise RuntimeError(f"Downloaded repaired docx is not a valid docx package: {target}")


def _run_pdf_review(playwright_cli: Path, files: _SmokeFiles, *, cwd: Path, timeout: float) -> None:
    _run_playwright(playwright_cli, "click", "[data-screen-target='pdf-review']", cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-action='choose-pdf']", cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _FRESH_DOCX_GATE, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-screen-target='history']", cwd=cwd, timeout=timeout)
    _wait_for_snapshot_text(playwright_cli, "browser_smoke", cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-screen-target='result']", cwd=cwd, timeout=timeout)
    download = _run_playwright(playwright_cli, "click", "[data-download-role='output']", cwd=cwd, timeout=timeout)
    _store_downloaded_docx(download.stdout, cwd=cwd, target=files.downloaded_docx)
    _run_playwright(
        playwright_cli,
        "click",
        "[data-screen='result'] [data-action='choose-docx']",
        cwd=cwd,
        timeout=timeout,
    )
    _run_playwright(playwright_cli, "upload", files.downloaded_docx, cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _REPAIRED_DOCX_READY, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-screen-target='pdf-review']", cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "#pdf-match-confirmation", cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-action='choose-pdf']", cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "upload", files.pdf, cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _PDF_REVIEW_READY, cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _PDF_EVIDENCE_GEOMETRY_READY, cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _PDF_TRUST_READY, cwd=cwd, timeout=timeout)


def _verify_history_restore(playwright_cli: Path, files: _SmokeFiles, *, cwd: Path, timeout: float) -> None:
    _wait_for_eval_truthy(playwright_cli, _REMEMBER_RENDER_JOBS, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-screen-target='history']", cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _OPEN_PDF_HISTORY, cwd=cwd, timeout=timeout)
    detail_ready = (
        "() => document.querySelector('[data-screen=\"pdf-review\"]')?.classList.contains('active') === true "
        f"&& document.querySelector('[data-pdf-docx-file]')?.textContent.trim() === {_js_string(files.downloaded_docx.name)} "
        f"&& document.querySelector('[data-pdf-file]')?.textContent.trim() === {_js_string(files.pdf.name)} "
        "&& document.querySelector('[data-render-state]')?.textContent.trim() === '已完成'"
    )
    _wait_for_eval_truthy(playwright_cli, detail_ready, cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "#pdf-match-confirmation", cwd=cwd, timeout=timeout)
    _run_playwright(playwright_cli, "click", "[data-action='choose-pdf']", cwd=cwd, timeout=timeout)
    _wait_for_eval_truthy(playwright_cli, _HISTORY_RETRY_BLOCKED, cwd=cwd, timeout=timeout)


def _verify_console_errors(playwright_cli: Path, *, cwd: Path, timeout: float) -> int:
    result = _run_playwright(playwright_cli, "console", "error", cwd=cwd, timeout=timeout)
    error_count = _console_error_count(result.stdout)
    if error_count:
        raise RuntimeError(f"Browser console reported {error_count} error(s).")
    return error_count


def _build_success_payload(
    *,
    base_url: str,
    ready: dict[str, Any],
    cwd: Path,
    files: _SmokeFiles,
    console_error_count: int,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "base_url": base_url,
        "ready": ready.get("status"),
        "work_dir": str(cwd),
        "source_docx": str(files.source_docx),
        "downloaded_docx": str(files.downloaded_docx),
        "download_bytes": files.downloaded_docx.stat().st_size,
        "render_evidence_trust": "user-confirmed",
        "browser_evidence": {
            "history_pdf": {
                "document_name": files.downloaded_docx.name,
                "pdf_name": files.pdf.name,
                "completed": True,
                "old_docx_reuse_blocked": True,
            },
            "mobile": {
                "width": 390,
                "height": 844,
                "no_horizontal_overflow": True,
                "rule_spectrum_labels_visible": True,
            },
            "console_errors": {
                "automated": True,
                "command": "console error",
                "error_count": console_error_count,
                "passed": True,
            },
        },
        "screenshots": {
            "home": str(files.home_screenshot),
            "repaired": str(files.repaired_screenshot),
            "mobile": str(files.mobile_screenshot),
        },
    }


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
    python_path = Path(python_executable).expanduser().absolute()
    pwcli_path = Path(playwright_cli).expanduser().resolve()
    timeout = float(command_timeout_seconds)

    if not pwcli_path.exists():
        raise RuntimeError(f"Playwright CLI wrapper does not exist: {pwcli_path}")

    prepare_work_dir(smoke_dir)
    state_root_path = Path(state_root).expanduser().resolve() if state_root is not None else smoke_dir / "state"
    runtime_root_path = Path(runtime_root).expanduser().resolve() if runtime_root is not None else smoke_dir / "runtime"
    state_root_path.mkdir(parents=True, exist_ok=True)
    runtime_root_path.mkdir(parents=True, exist_ok=True)

    files = _SmokeFiles(
        source_docx=smoke_dir / "browser_smoke.docx",
        pdf=smoke_dir / "browser_smoke.pdf",
        downloaded_docx=smoke_dir / "downloaded-repaired.docx",
        home_screenshot=smoke_dir / "local-console-home.png",
        repaired_screenshot=smoke_dir / "local-console-repaired.png",
        mobile_screenshot=smoke_dir / "local-console-mobile-result.png",
    )
    _build_smoke_docx(files.source_docx, python_executable=python_path)
    _build_smoke_pdf(files.pdf, python_executable=python_path)

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

    payload: dict[str, Any] | None = None
    try:
        ready = _wait_for_ready(base_url)
        _run_upload_repair_flow(pwcli_path, files, base_url=base_url, cwd=smoke_dir, timeout=timeout)
        _verify_mobile_result(pwcli_path, files, cwd=smoke_dir, timeout=timeout)
        _run_pdf_review(pwcli_path, files, cwd=smoke_dir, timeout=timeout)
        _verify_history_restore(pwcli_path, files, cwd=smoke_dir, timeout=timeout)
        console_error_count = _verify_console_errors(pwcli_path, cwd=smoke_dir, timeout=timeout)
        payload = _build_success_payload(
            base_url=base_url,
            ready=ready,
            cwd=smoke_dir,
            files=files,
            console_error_count=console_error_count,
        )
    finally:
        close_error: Exception | None = None
        try:
            _run_playwright(pwcli_path, "close", cwd=smoke_dir, timeout=30.0)
        except Exception as exc:
            close_error = exc
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if close_error is not None:
            raise RuntimeError("Playwright browser close failed.") from close_error
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


_LOCAL_BROWSER_SMOKE_ERROR_NEXT_STEPS = [
    "Install Node.js/npm and Playwright browsers if the Playwright CLI wrapper cannot start.",
    "Inspect the local service output and screenshots under the smoke work directory.",
]


def _format_error(exc: Exception) -> dict[str, Any]:
    return _build_failed_payload(exc, next_steps=_LOCAL_BROWSER_SMOKE_ERROR_NEXT_STEPS)


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
