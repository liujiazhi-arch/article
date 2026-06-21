from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest


def test_github_release_api_url_check_is_shared_by_ops_and_bundle_verifier():
    import verify_release_artifact as verifier
    from article_api import app_ops
    from release_url_utils import is_github_release_api_url

    assert verifier._is_github_release_api_url is is_github_release_api_url
    assert app_ops._is_github_release_api_url is is_github_release_api_url


def test_cli_json_emitters_share_stdout_and_file_writer():
    import build_windows_local_bundle
    import github_release_status
    import local_browser_smoke
    import release_smoke
    import windows_bundle_smoke
    from article_api import local_app
    from cli_json_output import emit_json_payload

    assert release_smoke._emit_payload is emit_json_payload
    assert windows_bundle_smoke._emit_payload is emit_json_payload
    assert local_browser_smoke._emit_payload is emit_json_payload
    assert github_release_status._emit_payload is emit_json_payload
    assert build_windows_local_bundle._emit_json is emit_json_payload
    assert local_app._emit_json is emit_json_payload


def test_release_sha256_helpers_share_file_digest_implementation():
    import release_evidence_bundle
    import verify_release_artifact as verifier
    from file_hash_utils import sha256_file

    assert release_evidence_bundle._sha256_file is sha256_file
    assert verifier._sha256_file is sha256_file


def _write_bundle_zip(
    path: Path,
    extra_entries: dict[str, bytes] | None = None,
    *,
    include_defaults: bool = True,
) -> None:
    entries = {
        "论文格式检查本地版/启动论文格式检查.bat": (
            'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"\r\n'
            'set "ARTICLE_LOCAL_RELEASE_API_URL=https://api.github.com/repos/example/article/releases/latest"\r\n'
            '"%ARTICLE_PYTHON%" -m article_api.local_app doctor\r\n'
            '"%ARTICLE_PYTHON%" -m article_api.local_app serve\r\n'
        ).encode("utf-8-sig"),
        "论文格式检查本地版/导出反馈包.bat": (
            'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"\r\n'
            '"%ARTICLE_PYTHON%" -m article_api.local_app feedback "%~dp0反馈包.zip"\r\n'
        ).encode("utf-8-sig"),
        "论文格式检查本地版/快速开始.txt": (
            "不需要安装 Python\r\n"
            "不需要输入命令\r\n"
            "论文默认只在本机处理\r\n"
            "GitHub 只用于下载软件版本\r\n"
            "检查新版本只检查软件版本，不上传论文，也不会自动下载或安装更新\r\n"
            "反馈包默认不包含论文原文、修复稿或 API key\r\n"
        ).encode("utf-8-sig"),
        "论文格式检查本地版/app/Scripts/python.exe": b"python",
        "论文格式检查本地版/app/Scripts/lnu-thesis-local.exe": b"article-local",
        "论文格式检查本地版/data/state/.keep": b"",
        "论文格式检查本地版/data/runtime/.keep": b"",
    }
    entries = entries if include_defaults else {}
    entries.update(extra_entries or {})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def test_verify_windows_bundle_artifact_writes_sha256(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    sha256_path = tmp_path / "lnu-thesis-local-windows.zip.sha256"
    _write_bundle_zip(bundle_zip)

    payload = verifier.verify_windows_bundle_artifact(
        bundle_zip,
        sha256_output=sha256_path,
    )

    expected_digest = hashlib.sha256(bundle_zip.read_bytes()).hexdigest()
    assert payload["status"] == "ok"
    assert payload["sha256"] == expected_digest
    assert payload["sha256_output"] == str(sha256_path.resolve())
    assert sha256_path.read_text(encoding="utf-8") == f"{expected_digest}  lnu-thesis-local-windows.zip\n"
    assert payload["entry_count"] >= 7


def test_verify_windows_bundle_artifact_allows_github_release_tag_api_url(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/启动论文格式检查.bat": (
                'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"\r\n'
                'set "ARTICLE_LOCAL_RELEASE_API_URL=https://api.github.com/repos/example/article/releases/tags/v0.1.0-beta"\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app doctor\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app serve\r\n'
            ).encode("utf-8-sig"),
        },
    )

    payload = verifier.verify_windows_bundle_artifact(bundle_zip)

    assert payload["status"] == "ok"


def test_verify_windows_bundle_artifact_rejects_extra_top_level_entries(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "README.txt": b"confusing root file",
            "extra/启动论文格式检查.bat": b"wrong launcher",
        },
    )

    with pytest.raises(RuntimeError, match="single top-level folder"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_unexpected_top_level_folder(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "wrong-root/启动论文格式检查.bat": (
                'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app doctor\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app serve\r\n'
            ).encode("utf-8-sig"),
            "wrong-root/导出反馈包.bat": (
                'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app feedback "%~dp0反馈包.zip"\r\n'
            ).encode("utf-8-sig"),
            "wrong-root/快速开始.txt": (
                "不需要安装 Python\r\n"
                "不需要输入命令\r\n"
                "论文默认只在本机处理\r\n"
                "GitHub 只用于下载软件版本\r\n"
                "检查新版本只检查软件版本，不上传论文，也不会自动下载或安装更新\r\n"
            ).encode("utf-8-sig"),
            "wrong-root/app/Scripts/python.exe": b"python",
            "wrong-root/app/Scripts/lnu-thesis-local.exe": b"article-local",
            "wrong-root/data/state/.keep": b"",
            "wrong-root/data/runtime/.keep": b"",
        },
        include_defaults=False,
    )

    with pytest.raises(RuntimeError, match="top-level folder"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_release_artifact_cli_prints_json_and_writes_sha256(capsys, tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    sha256_path = tmp_path / "lnu-thesis-local-windows.zip.sha256"
    _write_bundle_zip(bundle_zip)

    exit_code = verifier.main(
        [
            str(bundle_zip),
            "--sha256-output",
            str(sha256_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["sha256_output"] == str(sha256_path.resolve())
    assert sha256_path.exists()


def test_verify_windows_bundle_artifact_rejects_privacy_artifacts(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/data/runtime/uploads/学生论文.docx": b"docx",
            "论文格式检查本地版/反馈包.zip": b"feedback",
            "论文格式检查本地版/.env": b"API_KEY=secret",
        },
    )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_non_placeholder_local_data(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/data/state/tasks.json": b'{"job_id":"local"}',
            "论文格式检查本地版/data/runtime/cache.bin": b"runtime cache",
        },
    )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_keep_files_under_user_data_dirs(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/uploads/data/state/.keep": b"",
        },
    )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_feedback_zip_name_variants(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/article-feedback-20260606.zip": b"feedback",
        },
    )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


@pytest.mark.parametrize(
    "entry_name",
    [
        "论文格式检查本地版/data/cache/tasks.json",
        "论文格式检查本地版/.cache/tasks.json",
        "论文格式检查本地版/cache/tasks.json",
        "论文格式检查本地版/state/tasks.json",
        "论文格式检查本地版/runtime/tasks.json",
        "论文格式检查本地版/article-local.env.bak",
    ],
)
def test_verify_windows_bundle_artifact_rejects_local_state_runtime_cache_and_env_variants(
    tmp_path,
    entry_name,
):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(bundle_zip, {entry_name: b"local-data"})

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_document_artifacts_directly_under_app(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/app/学生论文.docx": b"docx",
        },
    )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_non_github_release_api_url(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/启动论文格式检查.bat": (
                'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"\r\n'
                'set "ARTICLE_LOCAL_RELEASE_API_URL=https://example.com/releases/latest"\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app doctor\r\n'
                '"%ARTICLE_PYTHON%" -m article_api.local_app serve\r\n'
            ).encode("utf-8-sig"),
        },
    )

    with pytest.raises(RuntimeError, match="GitHub Release API"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_rejects_root_document_artifacts(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/学生论文.docx": b"docx",
        },
    )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        verifier.verify_windows_bundle_artifact(bundle_zip)


def test_verify_windows_bundle_artifact_allows_dependency_document_resources(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/app/Lib/site-packages/example/template.docx": b"template",
            "论文格式检查本地版/app/Lib/site-packages/example/manual.pdf": b"%PDF-1.7",
        },
    )

    payload = verifier.verify_windows_bundle_artifact(bundle_zip)

    assert payload["status"] == "ok"


def test_verify_windows_bundle_artifact_allows_python_venv_dependency_document_resources(tmp_path):
    import verify_release_artifact as verifier

    bundle_zip = tmp_path / "lnu-thesis-local-windows.zip"
    _write_bundle_zip(
        bundle_zip,
        {
            "论文格式检查本地版/app/lib/python3.13/site-packages/docx/templates/default.docx": b"template",
        },
    )

    payload = verifier.verify_windows_bundle_artifact(bundle_zip)

    assert payload["status"] == "ok"
