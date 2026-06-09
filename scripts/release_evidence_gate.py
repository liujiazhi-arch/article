from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
import zipfile

from windows_bundle_contract import WINDOWS_BUNDLE_ASSET_NAME, WINDOWS_BUNDLE_SHA256_ASSET_NAME


REQUIRED_RELEASE_ASSETS = [
    WINDOWS_BUNDLE_ASSET_NAME,
    WINDOWS_BUNDLE_SHA256_ASSET_NAME,
]

WINDOWS_REQUIRED_PASS_PHRASES = [
    "sha256 校验结果: 通过",
    "是否 clean Windows 环境: 通过",
    "是否未预装 Python: 通过",
    "双击 `启动论文格式检查.bat`: 通过",
    "命令窗口无需用户输入命令: 通过",
    "浏览器自动打开本地网页: 通过",
    "上传 `.docx`: 通过",
    "audit / plan / apply / download: 通过",
    "用 WPS/Word 打开修复稿: 通过",
    "人工复核目录、分页、图表、公式和参考文献: 通过",
    "未上传论文、修复稿、API key、本地日志或未检查的反馈包到 GitHub issue: 通过",
    "发布结论: 通过",
]


def _read_json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _check_github_status(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    checks = dict(payload.get("checks", {}))
    release = dict(checks.get("release", {}))
    latest_ci_run = dict(checks.get("latest_ci_run", {}))
    release_assets = dict(checks.get("release_assets", {}))
    present_assets = set(str(name) for name in release_assets.get("present", []))
    missing_assets = [str(name) for name in release_assets.get("missing", [])]
    missing_required_assets = [
        name for name in REQUIRED_RELEASE_ASSETS if name not in present_assets and name not in missing_assets
    ]
    missing_assets = [*missing_assets, *missing_required_assets]
    ci_ok = latest_ci_run.get("status") == "completed" and latest_ci_run.get("conclusion") == "success"
    status = "ok" if payload.get("status") == "ok" and ci_ok and not missing_assets else "failed"
    return {
        "status": status,
        "path": str(path),
        "source_status": payload.get("status"),
        "tag": str(payload.get("tag") or release.get("tagName") or ""),
        "ci_ok": ci_ok,
        "missing_assets": missing_assets,
        "checks": checks,
    }


def _extract_report_tag(text: str) -> str:
    match = re.search(r"(?m)^\s*-\s*Release tag:\s*(\S+)\s*$", text)
    return match.group(1) if match else ""


def _check_windows_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    missing_or_failed = [phrase.removesuffix(": 通过") for phrase in WINDOWS_REQUIRED_PASS_PHRASES if phrase not in text]
    status = "ok" if not missing_or_failed else "failed"
    return {
        "status": status,
        "path": str(path),
        "tag": _extract_report_tag(text),
        "required": list(WINDOWS_REQUIRED_PASS_PHRASES),
        "missing_or_failed": missing_or_failed,
    }


def _check_http_smoke_payload(
    *,
    payload_status: str | None,
    http_smoke: dict[str, Any],
    source_status_label: str,
    http_status_label: str,
    ready_label: str,
    job_status_label: str,
    download_label: str,
    download_bytes: int | None = None,
) -> tuple[int, list[str]]:
    normalized_download_bytes = int(
        download_bytes if download_bytes is not None else http_smoke.get("download_bytes") or 0
    )
    missing_or_failed: list[str] = []
    if payload_status != "ok":
        missing_or_failed.append(source_status_label)
    if http_smoke.get("status") != "ok":
        missing_or_failed.append(http_status_label)
    if http_smoke.get("ready") != "ready":
        missing_or_failed.append(ready_label)
    if http_smoke.get("job_status") != "succeeded":
        missing_or_failed.append(job_status_label)
    if normalized_download_bytes <= 0:
        missing_or_failed.append(download_label)
    return normalized_download_bytes, missing_or_failed


def _check_release_smoke(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    checks = dict(payload.get("checks", {}))
    doctor = dict(checks.get("doctor", {}))
    profiles = dict(checks.get("profiles", {}))
    http_smoke = dict(checks.get("http_smoke", {}))
    download_bytes, missing_or_failed = _check_http_smoke_payload(
        payload_status=payload.get("status"),
        http_smoke=http_smoke,
        source_status_label="release smoke status",
        http_status_label="http_smoke",
        ready_label="http_smoke ready",
        job_status_label="http_smoke apply job",
        download_label="http_smoke output download",
    )
    if doctor.get("status") != "ok":
        missing_or_failed.append("doctor")
    if profiles.get("status") != "ok":
        missing_or_failed.append("profiles")
    return {
        "status": "ok" if not missing_or_failed else "failed",
        "path": str(path),
        "download_bytes": download_bytes,
        "missing_or_failed": missing_or_failed,
    }


def _check_windows_bundle_smoke(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    checks = dict(payload.get("checks", {}))
    doctor = dict(checks.get("doctor", {}))
    http_smoke = dict(checks.get("http_smoke", {}))
    download_bytes, missing_or_failed = _check_http_smoke_payload(
        payload_status=payload.get("status"),
        http_smoke=http_smoke,
        source_status_label="windows bundle smoke status",
        http_status_label="windows bundle http_smoke",
        ready_label="windows bundle http_smoke ready",
        job_status_label="windows bundle apply job",
        download_label="windows bundle output download",
        download_bytes=int(payload.get("download_bytes") or http_smoke.get("download_bytes") or 0),
    )
    if doctor.get("status") != "ok":
        missing_or_failed.append("windows bundle doctor")
    return {
        "status": "ok" if not missing_or_failed else "failed",
        "path": str(path),
        "download_bytes": download_bytes,
        "bundle_zip": str(payload.get("bundle_zip") or ""),
        "bundle_root": str(payload.get("bundle_root") or ""),
        "missing_or_failed": missing_or_failed,
    }


def _existing_file(path_value: str) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    return path if path.exists() and path.is_file() else None


def _check_browser_smoke(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    screenshots = dict(payload.get("screenshots", {}))
    downloaded_docx = _existing_file(str(payload.get("downloaded_docx") or ""))
    home_screenshot = _existing_file(str(screenshots.get("home") or ""))
    repaired_screenshot = _existing_file(str(screenshots.get("repaired") or ""))
    download_bytes = int(payload.get("download_bytes") or 0)
    missing_or_failed: list[str] = []
    if payload.get("status") != "ok":
        missing_or_failed.append("browser smoke status")
    if payload.get("ready") != "ready":
        missing_or_failed.append("browser smoke ready")
    if download_bytes <= 0:
        missing_or_failed.append("browser output download")
    if downloaded_docx is None:
        missing_or_failed.append("downloaded docx file")
    elif not zipfile.is_zipfile(downloaded_docx):
        missing_or_failed.append("downloaded docx package")
    if home_screenshot is None:
        missing_or_failed.append("home screenshot")
    if repaired_screenshot is None:
        missing_or_failed.append("repaired screenshot")
    return {
        "status": "ok" if not missing_or_failed else "failed",
        "path": str(path),
        "download_bytes": download_bytes,
        "downloaded_docx": str(downloaded_docx) if downloaded_docx is not None else "",
        "screenshots": {
            "home": str(home_screenshot) if home_screenshot is not None else "",
            "repaired": str(repaired_screenshot) if repaired_screenshot is not None else "",
        },
        "missing_or_failed": missing_or_failed,
    }


def _evidence_check(path: Path | None, checker, *, required: bool) -> dict[str, Any]:
    if path is None:
        return {"status": "missing_required" if required else "not_provided"}
    return checker(path)


def check_release_evidence(
    *,
    github_status_path: Path,
    windows_report_path: Path,
    release_smoke_path: Path | None = None,
    windows_bundle_smoke_path: Path | None = None,
    browser_smoke_path: Path | None = None,
) -> dict[str, Any]:
    github_check = _check_github_status(github_status_path)
    windows_check = _check_windows_report(windows_report_path)
    release_smoke_check = _evidence_check(release_smoke_path, _check_release_smoke, required=True)
    windows_bundle_smoke_check = _evidence_check(
        windows_bundle_smoke_path,
        _check_windows_bundle_smoke,
        required=True,
    )
    browser_smoke_check = _evidence_check(browser_smoke_path, _check_browser_smoke, required=False)
    tag_match = {
        "status": "ok"
        if github_check.get("tag") and github_check.get("tag") == windows_check.get("tag")
        else "failed",
        "github_tag": github_check.get("tag", ""),
        "windows_report_tag": windows_check.get("tag", ""),
    }
    required_smoke_checks_ok = all(
        check["status"] == "ok"
        for check in (release_smoke_check, windows_bundle_smoke_check)
    )
    optional_browser_check_ok = browser_smoke_check["status"] in {"ok", "not_provided"}
    ready = (
        github_check["status"] == "ok"
        and windows_check["status"] == "ok"
        and tag_match["status"] == "ok"
        and required_smoke_checks_ok
        and optional_browser_check_ok
    )
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "github_release_status": github_check,
            "windows_smoke_report": windows_check,
            "release_smoke": release_smoke_check,
            "windows_bundle_smoke": windows_bundle_smoke_check,
            "browser_smoke": browser_smoke_check,
            "tag_match": tag_match,
        },
        "next_steps": []
        if ready
        else [
            "Run scripts/release_smoke.py and scripts/windows_bundle_smoke.py with --json-output, then pass both JSON files to this gate.",
            "Run scripts/github_release_status.py and save its JSON output after the GitHub Release is published.",
            "Complete docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md on a clean Windows machine with WPS/Word proof.",
            "Do not call the beta ready until both remote release evidence and Windows smoke evidence pass.",
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="release_evidence_gate.py")
    parser.add_argument("--github-status-json", type=Path, help="JSON output saved from scripts/github_release_status.py")
    parser.add_argument("--windows-report", type=Path, help="Completed docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md copy")
    parser.add_argument("--release-smoke-json", type=Path, help="Optional JSON output saved from scripts/release_smoke.py")
    parser.add_argument("--windows-bundle-smoke-json", type=Path, help="Optional JSON output saved from scripts/windows_bundle_smoke.py")
    parser.add_argument("--browser-smoke-json", type=Path, help="Optional JSON output saved from scripts/local_browser_smoke.py")
    return parser


def _format_error(message: str) -> dict[str, Any]:
    return {
        "status": "not_ready",
        "error": message,
        "next_steps": [
            "Pass --github-status-json <path> after saving scripts/github_release_status.py output.",
            "Pass --windows-report <path> after completing clean Windows + WPS/Word smoke.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.github_status_json or not args.windows_report:
        print(json.dumps(_format_error("Missing required evidence paths."), ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    try:
        payload = check_release_evidence(
            github_status_path=args.github_status_json,
            windows_report_path=args.windows_report,
            release_smoke_path=args.release_smoke_json,
            windows_bundle_smoke_path=args.windows_bundle_smoke_json,
            browser_smoke_path=args.browser_smoke_json,
        )
    except Exception as exc:
        print(json.dumps(_format_error(str(exc)), ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("status") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
