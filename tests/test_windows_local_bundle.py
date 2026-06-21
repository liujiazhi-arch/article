from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import build_windows_local_bundle as bundle_builder


def test_build_windows_local_bundle_packages_launcher_readme_runtime_and_data_dirs(tmp_path):
    runtime_dir = tmp_path / "prepared-runtime"
    scripts_dir = runtime_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lnu-thesis-local.exe").write_bytes(b"exe")
    (scripts_dir / "python.exe").write_bytes(b"python")
    (runtime_dir / "pyvenv.cfg").write_text("home = C:\\Python\n", encoding="utf-8")

    output_zip = tmp_path / "dist" / "lnu-thesis-local-windows.zip"

    payload = bundle_builder.build_windows_local_bundle(
        runtime_dir=runtime_dir,
        output_zip=output_zip,
        bundle_name="论文格式检查本地版",
        release_api_url="https://api.github.com/repos/example/article/releases/latest",
    )

    assert payload["status"] == "ok"
    assert payload["output_zip"] == str(output_zip.resolve())
    assert payload["launcher"] == "论文格式检查本地版/启动论文格式检查.bat"
    assert payload["quickstart"] == "论文格式检查本地版/快速开始.txt"

    with zipfile.ZipFile(output_zip) as archive:
        names = set(archive.namelist())
        launcher_text = archive.read("论文格式检查本地版/启动论文格式检查.bat").decode("utf-8-sig")
        feedback_text = archive.read("论文格式检查本地版/导出反馈包.bat").decode("utf-8-sig")
        quickstart_text = archive.read("论文格式检查本地版/快速开始.txt").decode("utf-8-sig")

    assert "论文格式检查本地版/app/Scripts/lnu-thesis-local.exe" in names
    assert "论文格式检查本地版/导出反馈包.bat" in names
    assert "论文格式检查本地版/app/pyvenv.cfg" in names
    assert "论文格式检查本地版/data/state/.keep" in names
    assert "论文格式检查本地版/data/runtime/.keep" in names
    assert 'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"' in launcher_text
    assert 'set "ARTICLE_LOCAL_RELEASE_API_URL=https://api.github.com/repos/example/article/releases/latest"' in launcher_text
    assert '"%ARTICLE_PYTHON%" -m article_api.local_app doctor' in launcher_text
    assert '"%ARTICLE_PYTHON%" -m article_api.local_app serve' in launcher_text
    assert '--state-root "%~dp0data\\state"' in launcher_text
    assert '--runtime-root "%~dp0data\\runtime"' in launcher_text
    assert "正在检查本地网页端口 8000..." in launcher_text
    assert "Test-NetConnection -ComputerName 127.0.0.1 -Port 8000" in launcher_text
    assert "端口 8000 已被占用" in launcher_text
    assert "请先关闭占用 8000 端口的程序" in launcher_text
    assert 'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"' in feedback_text
    assert '"%ARTICLE_PYTHON%" -m article_api.local_app feedback "%~dp0反馈包.zip"' in feedback_text
    assert '--state-root "%~dp0data\\state"' in feedback_text
    assert '--runtime-root "%~dp0data\\runtime"' in feedback_text
    assert str(tmp_path) not in feedback_text
    assert str(tmp_path) not in launcher_text
    assert "1. 双击 `启动论文格式检查.bat`。" in quickstart_text
    assert "不需要安装 Python" in quickstart_text
    assert "不需要输入命令" in quickstart_text
    assert "把 `.docx` 论文上传到本机网页" in quickstart_text
    assert "不要把整个文件夹拆散" in quickstart_text
    assert "启动失败" in quickstart_text
    assert "端口 8000 被占用" in quickstart_text
    assert "关闭占用端口的程序" in quickstart_text
    assert "把黑色窗口里的中文提示截图" in quickstart_text
    assert "导出反馈包.bat" in quickstart_text
    assert "反馈包默认不包含论文原文" in quickstart_text
    assert "论文默认只在本机处理" in quickstart_text
    assert "小程序不是首处理端" in quickstart_text
    assert "检查新版本" in quickstart_text
    assert "只检查软件版本" in quickstart_text
    assert "不会自动下载或安装更新" in quickstart_text


def test_build_windows_local_bundle_omits_release_api_url_when_unconfigured(tmp_path):
    runtime_dir = tmp_path / "prepared-runtime"
    scripts_dir = runtime_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lnu-thesis-local.exe").write_bytes(b"exe")
    (scripts_dir / "python.exe").write_bytes(b"python")

    output_zip = tmp_path / "dist" / "lnu-thesis-local-windows.zip"

    bundle_builder.build_windows_local_bundle(
        runtime_dir=runtime_dir,
        output_zip=output_zip,
        bundle_name="论文格式检查本地版",
    )

    with zipfile.ZipFile(output_zip) as archive:
        launcher_text = archive.read("论文格式检查本地版/启动论文格式检查.bat").decode("utf-8-sig")

    assert "ARTICLE_LOCAL_RELEASE_API_URL" not in launcher_text


def test_build_windows_local_bundle_accepts_release_tag_api_url(tmp_path):
    runtime_dir = tmp_path / "prepared-runtime"
    scripts_dir = runtime_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lnu-thesis-local.exe").write_bytes(b"exe")
    (scripts_dir / "python.exe").write_bytes(b"python")

    output_zip = tmp_path / "dist" / "lnu-thesis-local-windows.zip"
    release_api_url = "https://api.github.com/repos/example/article/releases/tags/v0.1.0-beta"

    bundle_builder.build_windows_local_bundle(
        runtime_dir=runtime_dir,
        output_zip=output_zip,
        bundle_name="论文格式检查本地版",
        release_api_url=release_api_url,
    )

    with zipfile.ZipFile(output_zip) as archive:
        launcher_text = archive.read("论文格式检查本地版/启动论文格式检查.bat").decode("utf-8-sig")

    assert f'set "ARTICLE_LOCAL_RELEASE_API_URL={release_api_url}"' in launcher_text


def test_build_windows_local_bundle_cli_prints_json(capsys, tmp_path):
    runtime_dir = tmp_path / "prepared-runtime"
    scripts_dir = runtime_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lnu-thesis-local.exe").write_bytes(b"exe")
    (scripts_dir / "python.exe").write_bytes(b"python")

    output_zip = tmp_path / "dist" / "lnu-thesis-local-windows.zip"

    exit_code = bundle_builder.main(
        [
            "--runtime-dir",
            str(runtime_dir),
            "--output-zip",
            str(output_zip),
            "--bundle-name",
            "论文格式检查本地版",
            "--release-api-url",
            "https://api.github.com/repos/example/article/releases/latest",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_zip.exists()
    assert '"status": "ok"' in captured.out
    assert '"release_api_url_configured": true' in captured.out
    assert "lnu-thesis-local-windows.zip" in captured.out


def test_build_windows_local_bundle_cli_emits_utf8_when_stdout_encoding_rejects_chinese(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "prepared-runtime"
    scripts_dir = runtime_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lnu-thesis-local.exe").write_bytes(b"exe")
    (scripts_dir / "python.exe").write_bytes(b"python")
    output_zip = tmp_path / "dist" / "lnu-thesis-local-windows.zip"
    output = io.BytesIO()
    cp1252_stdout = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)

    exit_code = bundle_builder.main(
        [
            "--runtime-dir",
            str(runtime_dir),
            "--output-zip",
            str(output_zip),
            "--bundle-name",
            "论文格式检查本地版",
        ]
    )

    cp1252_stdout.flush()
    payload = json.loads(output.getvalue().decode("utf-8"))
    assert exit_code == 0
    assert payload["bundle_name"] == "论文格式检查本地版"


def test_build_windows_local_bundle_rejects_runtime_without_python_exe(tmp_path):
    runtime_dir = tmp_path / "prepared-runtime"
    scripts_dir = runtime_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lnu-thesis-local.exe").write_bytes(b"exe")

    output_zip = tmp_path / "dist" / "lnu-thesis-local-windows.zip"

    try:
        bundle_builder.build_windows_local_bundle(
            runtime_dir=runtime_dir,
            output_zip=output_zip,
            bundle_name="论文格式检查本地版",
        )
    except RuntimeError as exc:
        assert "Scripts/python.exe" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing Scripts/python.exe")
