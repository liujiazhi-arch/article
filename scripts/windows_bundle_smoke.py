from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence
import zipfile

from cli_json_output import build_failed_json_payload as _build_failed_payload
from cli_json_output import emit_json_payload as _emit_payload
from smoke_workdir_utils import prepare_work_dir
from windows_bundle_contract import PYTHON_ENTRY as BUNDLE_PYTHON_ENTRY


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_smoke


DEFAULT_WORK_DIR = Path(".windows_bundle_smoke")
DEFAULT_COMMAND_TIMEOUT_SECONDS = 300.0


def _json_run(
    command: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    return release_smoke._json_run(command, cwd=cwd, timeout=timeout)


def _locate_bundle_root(extracted_root: Path) -> Path:
    candidates = sorted(path.parent.parent.parent for path in extracted_root.rglob(BUNDLE_PYTHON_ENTRY))
    unique_candidates = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(candidate)
    if len(unique_candidates) != 1:
        locations = [str(candidate) for candidate in unique_candidates]
        raise RuntimeError(
            f"Expected exactly one Windows bundle root containing {BUNDLE_PYTHON_ENTRY}; "
            f"found {len(unique_candidates)}: {locations}"
        )
    return unique_candidates[0]


def run_windows_bundle_smoke(
    *,
    bundle_zip: str | Path,
    work_dir: str | Path = DEFAULT_WORK_DIR,
    command_timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    bundle_zip_path = Path(bundle_zip).expanduser().resolve()
    smoke_dir = Path(work_dir).expanduser().resolve()
    command_timeout = float(command_timeout_seconds)

    if not bundle_zip_path.exists():
        raise RuntimeError(f"Windows bundle zip does not exist: {bundle_zip_path}")

    prepare_work_dir(smoke_dir)
    with zipfile.ZipFile(bundle_zip_path) as archive:
        archive.extractall(smoke_dir)

    bundle_root = _locate_bundle_root(smoke_dir)
    python_exe = bundle_root / "app" / "Scripts" / "python.exe"
    state_root = bundle_root / "data" / "state"
    runtime_root = bundle_root / "data" / "runtime"
    state_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    doctor = _json_run(
        [
            python_exe,
            "-m",
            "article_api.local_app",
            "doctor",
            "--state-root",
            state_root,
            "--runtime-root",
            runtime_root,
        ],
        cwd=bundle_root,
        timeout=command_timeout,
    )
    http_smoke = release_smoke._run_http_smoke(
        article_local=python_exe,
        venv_python=python_exe,
        state_root=state_root,
        runtime_root=runtime_root,
        smoke_dir=smoke_dir,
    )
    return {
        "status": "ok",
        "bundle_zip": str(bundle_zip_path),
        "work_dir": str(smoke_dir),
        "bundle_root": str(bundle_root),
        "python": str(python_exe),
        "roots": {
            "state_root": str(state_root),
            "runtime_root": str(runtime_root),
        },
        "checks": {
            "doctor": {
                "status": doctor.get("status") or doctor.get("summary", {}).get("status") or "ok",
                "headline": doctor.get("summary", {}).get("headline"),
            },
            "http_smoke": http_smoke,
        },
        "download_bytes": http_smoke.get("download_bytes"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="windows_bundle_smoke.py")
    parser.add_argument("bundle_zip")
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    parser.add_argument("--command-timeout-seconds", type=float, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    parser.add_argument("--json-output", type=Path, help="Write the final JSON payload to this path")
    return parser


_WINDOWS_TIMEOUT_NEXT_STEPS = [
    "Retry with a larger --command-timeout-seconds value if the Windows runner is slow.",
    "Inspect the bundled article_api.local_app doctor or serve command output in CI.",
]

_WINDOWS_COMMAND_FAILED_NEXT_STEPS = [
    "Inspect the failed bundled Python command and rebuild the Windows bundle after fixing packaging or runtime issues.",
]

_WINDOWS_GENERAL_ERROR_NEXT_STEPS = [
    "Inspect the extracted bundle layout and rerun the Windows bundle smoke after fixing the artifact.",
]


def _format_windows_bundle_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, subprocess.TimeoutExpired):
        return _build_failed_payload(
            exc,
            next_steps=_WINDOWS_TIMEOUT_NEXT_STEPS,
            timeout_type="command_timeout",
            timeout_message="Windows bundle smoke command timed out.",
        )
    if isinstance(exc, subprocess.CalledProcessError):
        return _build_failed_payload(
            exc,
            next_steps=_WINDOWS_COMMAND_FAILED_NEXT_STEPS,
            called_process_type="command_failed",
        )
    return _build_failed_payload(exc, next_steps=_WINDOWS_GENERAL_ERROR_NEXT_STEPS)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = run_windows_bundle_smoke(
            bundle_zip=args.bundle_zip,
            work_dir=args.work_dir,
            command_timeout_seconds=float(args.command_timeout_seconds),
        )
    except Exception as exc:
        _emit_payload(_format_windows_bundle_error(exc), json_output=args.json_output)
        return 1
    _emit_payload(payload, json_output=args.json_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
