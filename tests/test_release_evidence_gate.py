from __future__ import annotations

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "release_evidence_gate.py"


def _load_release_evidence_gate():
    spec = importlib.util.spec_from_file_location("release_evidence_gate", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_windows_report(path: Path, *, tag: str = "v0.1.0", conclusion: str = "通过") -> None:
    path.write_text(
        "\n".join(
            [
                "# Windows 实机 smoke 证据报告",
                f"- Release tag: {tag}",
                "- sha256 校验结果: 通过",
                "- 是否 clean Windows 环境: 通过",
                "- 是否未预装 Python: 通过",
                "- 双击 `启动论文格式检查.bat`: 通过",
                "- 命令窗口无需用户输入命令: 通过",
                "- 浏览器自动打开本地网页: 通过",
                "- 上传 `.docx`: 通过",
                "- audit / plan / apply / download: 通过",
                "- 用 WPS/Word 打开修复稿: 通过",
                "- 人工复核目录、分页、图表、公式和参考文献: 通过",
                "- 未上传论文、修复稿、API key、本地日志或未检查的反馈包到 GitHub issue: 通过",
                f"- 发布结论: {conclusion}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_github_status(path: Path, *, tag: str = "v0.1.0") -> None:
    path.write_text(
        json.dumps(
            {
                "status": "ok",
                "tag": tag,
                "checks": {
                    "release": {"tagName": tag},
                    "latest_ci_run": {"status": "completed", "conclusion": "success"},
                    "release_assets": {
                        "missing": [],
                        "present": ["article-local-windows.zip", "article-local-windows.zip.sha256"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _write_release_smoke(path: Path, *, status: str = "ok") -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "checks": {
                    "doctor": {"status": "ok"},
                    "profiles": {"status": "ok"},
                    "http_smoke": {
                        "status": "ok",
                        "ready": "ready",
                        "job_status": "succeeded",
                        "download_bytes": 1234,
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _write_windows_bundle_smoke(path: Path, *, status: str = "ok", job_status: str = "succeeded") -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "bundle_zip": "dist/article-local-windows.zip",
                "bundle_root": "dist/windows-bundle-http-smoke/论文格式检查本地版",
                "download_bytes": 2345 if job_status == "succeeded" else 0,
                "checks": {
                    "doctor": {"status": "ok"},
                    "http_smoke": {
                        "status": "ok" if job_status == "succeeded" else "failed",
                        "ready": "ready",
                        "job_status": job_status,
                        "download_bytes": 2345 if job_status == "succeeded" else 0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _write_browser_smoke(path: Path, *, tmp_path: Path, valid_docx: bool = True) -> None:
    downloaded_docx = tmp_path / "downloaded-repaired.docx"
    home_screenshot = tmp_path / "local-console-home.png"
    repaired_screenshot = tmp_path / "local-console-repaired.png"
    if valid_docx:
        import zipfile

        with zipfile.ZipFile(downloaded_docx, "w") as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
    else:
        downloaded_docx.write_bytes(b"not-a-docx")
    home_screenshot.write_bytes(b"png")
    repaired_screenshot.write_bytes(b"png")
    path.write_text(
        json.dumps(
            {
                "status": "ok",
                "ready": "ready",
                "download_bytes": downloaded_docx.stat().st_size,
                "downloaded_docx": str(downloaded_docx),
                "screenshots": {
                    "home": str(home_screenshot),
                    "repaired": str(repaired_screenshot),
                },
            }
        ),
        encoding="utf-8",
    )


def test_release_evidence_gate_requires_remote_release_windows_report_and_smoke_json(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    release_smoke_path = tmp_path / "release-smoke.json"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path)
    _write_release_smoke(release_smoke_path)
    _write_windows_bundle_smoke(windows_bundle_smoke_path)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        release_smoke_path=release_smoke_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
    )

    assert payload["status"] == "ready"
    assert payload["checks"]["github_release_status"]["status"] == "ok"
    assert payload["checks"]["windows_smoke_report"]["status"] == "ok"
    assert payload["next_steps"] == []


def test_release_evidence_gate_accepts_optional_release_and_browser_smoke_json(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    release_smoke_path = tmp_path / "release-smoke.json"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    browser_smoke_path = tmp_path / "browser-smoke.json"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path)
    _write_release_smoke(release_smoke_path)
    _write_windows_bundle_smoke(windows_bundle_smoke_path)
    _write_browser_smoke(browser_smoke_path, tmp_path=tmp_path)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        release_smoke_path=release_smoke_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
        browser_smoke_path=browser_smoke_path,
    )

    assert payload["status"] == "ready"
    assert payload["checks"]["release_smoke"]["status"] == "ok"
    assert payload["checks"]["windows_bundle_smoke"]["status"] == "ok"
    assert payload["checks"]["browser_smoke"]["status"] == "ok"


def test_release_evidence_gate_blocks_missing_required_smoke_json(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["release_smoke"]["status"] == "missing_required"
    assert payload["checks"]["windows_bundle_smoke"]["status"] == "missing_required"
    assert "Run scripts/release_smoke.py" in payload["next_steps"][0]


def test_release_evidence_gate_blocks_failed_windows_bundle_smoke_json(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path)
    _write_windows_bundle_smoke(windows_bundle_smoke_path, job_status="failed")

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["windows_bundle_smoke"]["status"] == "failed"
    assert "windows bundle apply job" in payload["checks"]["windows_bundle_smoke"]["missing_or_failed"]


def test_release_evidence_gate_blocks_invalid_browser_smoke_download(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    browser_smoke_path = tmp_path / "browser-smoke.json"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path)
    _write_browser_smoke(browser_smoke_path, tmp_path=tmp_path, valid_docx=False)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        browser_smoke_path=browser_smoke_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["browser_smoke"]["status"] == "failed"
    assert "downloaded docx package" in payload["checks"]["browser_smoke"]["missing_or_failed"]


def test_release_evidence_gate_blocks_missing_windows_wps_proof(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    github_status_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    _write_windows_report(windows_report_path)
    windows_report_path.write_text(
        windows_report_path.read_text(encoding="utf-8").replace(
            "- 用 WPS/Word 打开修复稿: 通过",
            "- 用 WPS/Word 打开修复稿: 不通过",
        ),
        encoding="utf-8",
    )

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["windows_smoke_report"]["status"] == "failed"
    assert "用 WPS/Word 打开修复稿" in payload["checks"]["windows_smoke_report"]["missing_or_failed"][0]


def test_release_evidence_gate_blocks_missing_github_release_assets(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    github_status_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "tag": "v0.1.0",
                "checks": {
                    "release": {"tagName": "v0.1.0"},
                    "latest_ci_run": {"status": "completed", "conclusion": "success"},
                    "release_assets": {
                        "missing": ["article-local-windows.zip.sha256"],
                        "present": ["article-local-windows.zip"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    _write_windows_report(windows_report_path)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["github_release_status"]["status"] == "failed"
    assert payload["checks"]["github_release_status"]["missing_assets"] == ["article-local-windows.zip.sha256"]


def test_release_evidence_gate_blocks_mismatched_release_tags(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    github_status_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "tag": "v0.2.0",
                "checks": {
                    "release": {"tagName": "v0.2.0"},
                    "latest_ci_run": {"status": "completed", "conclusion": "success"},
                    "release_assets": {
                        "missing": [],
                        "present": ["article-local-windows.zip", "article-local-windows.zip.sha256"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    _write_windows_report(windows_report_path, tag="v0.1.0")

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["tag_match"]["status"] == "failed"
    assert payload["checks"]["tag_match"]["github_tag"] == "v0.2.0"
    assert payload["checks"]["tag_match"]["windows_report_tag"] == "v0.1.0"


def test_release_evidence_gate_cli_outputs_json_error_for_missing_inputs(capsys):
    release_evidence_gate = _load_release_evidence_gate()

    exit_code = release_evidence_gate.main([])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_ready"
    assert "--github-status-json" in payload["next_steps"][0]
