from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "release_evidence_gate.py"
TEST_BUNDLE_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _load_release_evidence_gate():
    spec = importlib.util.spec_from_file_location("release_evidence_gate", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_windows_report(
    path: Path,
    *,
    tag: str = "v0.1.0",
    conclusion: str = "通过",
    bundle_sha256: str = TEST_BUNDLE_SHA256,
) -> None:
    path.write_text(
        "\n".join(
            [
                "# Windows 实机 smoke 证据报告",
                f"- Release tag: {tag}",
                f"- `lnu-thesis-local-windows.zip.sha256` 内容: {bundle_sha256}  lnu-thesis-local-windows.zip",
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
                        "present": ["lnu-thesis-local-windows.zip", "lnu-thesis-local-windows.zip.sha256"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _write_release_smoke(
    path: Path,
    *,
    status: str = "ok",
    service_version: str = "0.1.0",
) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "service_version": service_version,
                "checks": {
                    "doctor": {"status": "ok"},
                    "profiles": {"status": "ok"},
                    "http_smoke": {
                        "status": "ok",
                        "ready": "ready",
                        "job_status": "succeeded",
                        "download_bytes": 1234,
                        "render_job_status": "succeeded",
                        "render_page_count": 1,
                        "render_evidence_trust": "user-confirmed",
                        "render_pdf_matches_docx_confirmed": True,
                        "render_pdf_content_match_status": "matched",
                        "render_layout_decision_eligible": True,
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _write_windows_bundle_smoke(
    path: Path,
    *,
    status: str = "ok",
    job_status: str = "succeeded",
    bundle_sha256: str = TEST_BUNDLE_SHA256,
    service_version: str = "0.1.0",
) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "service_version": service_version,
                "bundle_sha256": bundle_sha256,
                "bundle_zip": "dist/lnu-thesis-local-windows.zip",
                "bundle_root": "dist/windows-bundle-http-smoke/论文格式检查本地版",
                "download_bytes": 2345 if job_status == "succeeded" else 0,
                "checks": {
                    "doctor": {"status": "ok"},
                    "http_smoke": {
                        "status": "ok" if job_status == "succeeded" else "failed",
                        "ready": "ready",
                        "job_status": job_status,
                        "download_bytes": 2345 if job_status == "succeeded" else 0,
                        "render_job_status": job_status,
                        "render_page_count": 1 if job_status == "succeeded" else 0,
                        "render_evidence_trust": "user-confirmed",
                        "render_pdf_matches_docx_confirmed": True,
                        "render_pdf_content_match_status": "matched",
                        "render_layout_decision_eligible": True,
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


def test_release_evidence_gate_http_smoke_failure_mapping_is_centralized():
    release_evidence_gate = _load_release_evidence_gate()

    download_bytes, missing_or_failed = release_evidence_gate._check_http_smoke_payload(
        payload_status="failed",
        http_smoke={"status": "failed", "ready": "starting", "job_status": "failed", "download_bytes": 0},
        source_status_label="release smoke status",
        http_status_label="http_smoke",
        ready_label="http_smoke ready",
        job_status_label="http_smoke apply job",
        download_label="http_smoke output download",
        render_status_label="http_smoke render-review job",
        render_page_label="http_smoke render-review pages",
    )

    release_source = inspect.getsource(release_evidence_gate._check_release_smoke)
    windows_source = inspect.getsource(release_evidence_gate._check_windows_bundle_smoke)

    assert download_bytes == 0
    assert missing_or_failed == [
        "release smoke status",
        "http_smoke",
        "http_smoke ready",
        "http_smoke apply job",
        "http_smoke output download",
        "http_smoke render-review job",
        "http_smoke render-review pages",
        "render-review evidence trust",
        "render-review document confirmation",
        "render-review content match",
        "render-review layout eligibility",
    ]
    assert "_check_http_smoke_payload(" in release_source
    assert "_check_http_smoke_payload(" in windows_source
    assert 'http_smoke.get("ready")' not in release_source
    assert 'http_smoke.get("ready")' not in windows_source


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


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected_failure"),
    [
        ("render_evidence_trust", "unverified", "render-review evidence trust"),
        ("render_pdf_matches_docx_confirmed", False, "render-review document confirmation"),
        ("render_pdf_content_match_status", "mismatch", "render-review content match"),
        ("render_layout_decision_eligible", False, "render-review layout eligibility"),
    ],
)
def test_release_evidence_gate_blocks_untrusted_pdf_evidence(
    tmp_path,
    field,
    invalid_value,
    expected_failure,
):
    release_evidence_gate = _load_release_evidence_gate()
    release_smoke_path = tmp_path / "release-smoke.json"
    _write_release_smoke(release_smoke_path)
    payload = json.loads(release_smoke_path.read_text(encoding="utf-8"))
    payload["checks"]["http_smoke"][field] = invalid_value
    release_smoke_path.write_text(json.dumps(payload), encoding="utf-8")

    result = release_evidence_gate._check_release_smoke(release_smoke_path)

    assert result["status"] == "failed"
    assert expected_failure in result["missing_or_failed"]


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


def test_release_evidence_gate_rejects_unselected_windows_report_placeholders(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    report_path = tmp_path / "windows-report.md"
    report_path.write_text(
        "\n".join(
            [
                "# Windows 实机 smoke 证据报告",
                "- Release tag: v0.1.0",
                *[
                    f"- {phrase} / 不通过"
                    for phrase in release_evidence_gate.WINDOWS_REQUIRED_PASS_PHRASES
                ],
            ]
        ),
        encoding="utf-8",
    )

    result = release_evidence_gate._check_windows_report(report_path)

    assert result["status"] == "failed"
    assert result["missing_or_failed"]


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
                        "missing": ["lnu-thesis-local-windows.zip.sha256"],
                        "present": ["lnu-thesis-local-windows.zip"],
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
    assert payload["checks"]["github_release_status"]["missing_assets"] == ["lnu-thesis-local-windows.zip.sha256"]


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
                        "present": ["lnu-thesis-local-windows.zip", "lnu-thesis-local-windows.zip.sha256"],
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


def test_release_evidence_gate_blocks_release_tag_service_version_mismatch(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    release_smoke_path = tmp_path / "release-smoke.json"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    _write_github_status(github_status_path, tag="v0.1.2-beta")
    _write_windows_report(windows_report_path, tag="v0.1.2-beta")
    _write_release_smoke(release_smoke_path, service_version="0.1.1")
    _write_windows_bundle_smoke(windows_bundle_smoke_path)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        release_smoke_path=release_smoke_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["service_version_match"] == {
        "status": "failed",
        "release_tag": "v0.1.2-beta",
        "release_tag_version": "0.1.2",
        "release_smoke_service_version": "0.1.1",
        "windows_bundle_service_version": "0.1.0",
    }


def test_release_evidence_gate_blocks_old_bundle_relabelled_for_new_release(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    release_smoke_path = tmp_path / "release-smoke.json"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    _write_github_status(github_status_path, tag="v0.1.2-beta")
    _write_windows_report(windows_report_path, tag="v0.1.2-beta")
    _write_release_smoke(release_smoke_path, service_version="0.1.2")
    _write_windows_bundle_smoke(windows_bundle_smoke_path, service_version="0.1.0")

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        release_smoke_path=release_smoke_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["service_version_match"] == {
        "status": "failed",
        "release_tag": "v0.1.2-beta",
        "release_tag_version": "0.1.2",
        "release_smoke_service_version": "0.1.2",
        "windows_bundle_service_version": "0.1.0",
    }


def test_release_evidence_gate_blocks_windows_bundle_sha256_mismatch(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    release_smoke_path = tmp_path / "release-smoke.json"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path)
    _write_release_smoke(release_smoke_path)
    _write_windows_bundle_smoke(windows_bundle_smoke_path, bundle_sha256="f" * 64)

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        release_smoke_path=release_smoke_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
    )

    assert payload["status"] == "not_ready"
    assert payload["checks"]["bundle_sha256_match"] == {
        "status": "failed",
        "windows_report_sha256": TEST_BUNDLE_SHA256,
        "windows_bundle_sha256": "f" * 64,
    }


def test_release_evidence_gate_rejects_legacy_unbound_evidence(tmp_path):
    release_evidence_gate = _load_release_evidence_gate()
    github_status_path = tmp_path / "github-status.json"
    windows_report_path = tmp_path / "windows-report.md"
    release_smoke_path = tmp_path / "release-smoke.json"
    windows_bundle_smoke_path = tmp_path / "windows-bundle-smoke.json"
    _write_github_status(github_status_path)
    _write_windows_report(windows_report_path, bundle_sha256="")
    _write_release_smoke(release_smoke_path, service_version="")
    _write_windows_bundle_smoke(windows_bundle_smoke_path, bundle_sha256="", service_version="")

    payload = release_evidence_gate.check_release_evidence(
        github_status_path=github_status_path,
        windows_report_path=windows_report_path,
        release_smoke_path=release_smoke_path,
        windows_bundle_smoke_path=windows_bundle_smoke_path,
    )

    assert payload["status"] == "not_ready"
    assert "release smoke service version" in payload["checks"]["release_smoke"]["missing_or_failed"]
    assert "windows report bundle sha256" in payload["checks"]["windows_smoke_report"]["missing_or_failed"]
    assert "windows bundle service version" in payload["checks"]["windows_bundle_smoke"]["missing_or_failed"]
    assert "windows bundle sha256" in payload["checks"]["windows_bundle_smoke"]["missing_or_failed"]


def test_release_evidence_gate_cli_outputs_json_error_for_missing_inputs(capsys):
    release_evidence_gate = _load_release_evidence_gate()

    exit_code = release_evidence_gate.main([])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_ready"
    assert "--github-status-json" in payload["next_steps"][0]
