from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

from install_article_local import _batch_path_from_launcher


DEFAULT_BUNDLE_NAME = "论文格式检查本地版"
LAUNCHER_NAME = "启动论文格式检查.bat"
FEEDBACK_LAUNCHER_NAME = "导出反馈包.bat"
QUICKSTART_NAME = "快速开始.txt"


def _resolve_path(path_value: str | Path) -> Path:
    return Path(path_value).expanduser().resolve()


def _write_quickstart(path: Path) -> Path:
    lines = [
        "论文格式检查本地版 - 快速开始",
        "",
        "这个 zip 包已经带好本地运行环境：不需要安装 Python，不需要输入命令。",
        "请先完整解压 zip，再打开解压后的文件夹；不要把整个文件夹拆散，也不要只复制启动脚本。",
        "",
        "1. 双击 `启动论文格式检查.bat`。",
        "2. 浏览器打开后，把 `.docx` 论文上传到本机网页。",
        "3. 查看审查结果或修复计划。",
        "4. 选择需要修复的项目并等待任务完成。",
        "5. 下载修复副本。",
        "6. 用 WPS/Word 打开修复副本，人工复核目录、分页、图表、公式和参考文献。",
        "",
        "如果启动失败，请先看黑色窗口里的中文提示；反馈问题时，把黑色窗口里的中文提示截图发给维护者。",
        "如果提示端口 8000 被占用，请先关闭占用端口的程序，或重启电脑后再双击启动。",
        "需要反馈问题时，可以双击 `导出反馈包.bat`，再把生成的 `反馈包.zip` 发给维护者；反馈包默认不包含论文原文、修复稿或 API key，并会脱敏文档文件名。",
        "不要把论文原文、修复稿、API key 或未检查的反馈包上传到公开 GitHub issue。",
        "如果下载失败，请刷新任务结果；文件已被清理时，需要重新运行修复任务再下载。",
        "需要检查新版本时，点击网页顶部的“检查新版本”；它只检查软件版本，不上传论文，也不会自动下载或安装更新。",
        "",
        "隐私说明：论文默认只在本机处理，本工具不会主动上传论文到外部服务器。",
        "GitHub 只用于下载软件版本和提交脱敏问题反馈，不用于同步你的论文、本地日志、运行缓存或密钥。",
        "小程序不是首处理端；不要把论文上传到非官方或不明来源页面。",
        "Beta 提示：本工具不能保证最终提交版完全合规，学校、学院、导师或当年模板要求优先。",
    ]
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")
    return path


def _write_bundle_launcher(
    launcher_path: Path,
    *,
    python_executable: Path,
    state_root: Path,
    runtime_root: Path,
    release_api_url: str | None = None,
    url: str = "http://127.0.0.1:8000",
) -> Path:
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    python_path = _batch_path_from_launcher(launcher_path, python_executable)
    state_root_path = _batch_path_from_launcher(launcher_path, state_root)
    runtime_root_path = _batch_path_from_launcher(launcher_path, runtime_root)
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "title 论文格式检查",
        "setlocal",
        f'set "ARTICLE_PYTHON={python_path}"',
    ]
    if release_api_url:
        lines.append(f'set "ARTICLE_LOCAL_RELEASE_API_URL={release_api_url}"')
    lines.extend([
        "",
        "if not exist \"%ARTICLE_PYTHON%\" (",
        "  echo 没有找到本地 Python 运行环境，请确认没有拆散 zip 文件夹。",
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "echo 正在检查本地运行环境...",
        f'"%ARTICLE_PYTHON%" -m article_api.local_app doctor --state-root "{state_root_path}" --runtime-root "{runtime_root_path}"',
        "if errorlevel 1 (",
        "  echo.",
        "  echo 启动前检查失败。请截图此窗口并到反馈入口提交问题。",
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "echo 正在检查本地网页端口 8000...",
        (
            'powershell -NoProfile -Command '
            '"if ((Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet)) { exit 1 } else { exit 0 }"'
        ),
        "if errorlevel 1 (",
        "  echo.",
        "  echo 端口 8000 已被占用，本地网页暂时不能启动。",
        "  echo 请先关闭占用 8000 端口的程序，或重启电脑后再双击启动。",
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "echo 正在打开本地网页...",
        (
            'start "" powershell -NoProfile -WindowStyle Hidden -Command '
            f'"Start-Sleep -Seconds 2; Start-Process \'{url}\'"'
        ),
        "echo 如果浏览器没有自动打开，请手动访问：",
        f"echo {url}",
        "",
        f'"%ARTICLE_PYTHON%" -m article_api.local_app serve --host 127.0.0.1 --port 8000 --state-root "{state_root_path}" --runtime-root "{runtime_root_path}"',
        "if errorlevel 1 (",
        "  echo.",
        "  echo 本地服务启动失败。常见原因：端口 8000 被占用，或安装文件不完整。",
        "  pause",
        "  exit /b 1",
        ")",
    ])
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")
    return launcher_path


def _write_feedback_launcher(
    launcher_path: Path,
    *,
    python_executable: Path,
    state_root: Path,
    runtime_root: Path,
) -> Path:
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    python_path = _batch_path_from_launcher(launcher_path, python_executable)
    state_root_path = _batch_path_from_launcher(launcher_path, state_root)
    runtime_root_path = _batch_path_from_launcher(launcher_path, runtime_root)
    lines = [
        "@echo off",
        "setlocal",
        "chcp 65001 >nul",
        "title 导出论文格式检查反馈包",
        f'set "ARTICLE_PYTHON={python_path}"',
        "",
        "if not exist \"%ARTICLE_PYTHON%\" (",
        "  echo 没有找到本地 Python 运行环境，请确认没有拆散 zip 文件夹。",
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "echo 正在导出反馈包...",
        '"%ARTICLE_PYTHON%" -m article_api.local_app feedback "%~dp0反馈包.zip" '
        f'--state-root "{state_root_path}" --runtime-root "{runtime_root_path}"',
        "if errorlevel 1 (",
        "  echo 反馈包导出失败。请截图此窗口并发给维护者。",
        "  pause",
        "  exit /b 1",
        ")",
        "echo 反馈包已导出：%~dp0反馈包.zip",
        "echo 反馈包默认不包含论文原文、修复稿或 API key，并会脱敏文档文件名。",
        "echo 发送前仍建议先打开 zip 查看文件列表，不要上传论文或密钥到公开 GitHub issue。",
        "pause",
    ]
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")
    return launcher_path


def _add_tree_to_zip(archive: zipfile.ZipFile, root: Path) -> list[str]:
    written: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        arcname = path.relative_to(root.parent).as_posix()
        archive.write(path, arcname)
        written.append(arcname)
    return written


def build_windows_local_bundle(
    *,
    runtime_dir: str | Path,
    output_zip: str | Path,
    bundle_name: str = DEFAULT_BUNDLE_NAME,
    release_api_url: str | None = None,
) -> dict:
    resolved_runtime_dir = _resolve_path(runtime_dir)
    resolved_output_zip = _resolve_path(output_zip)
    article_local = resolved_runtime_dir / "Scripts" / "article-local.exe"
    python_exe = resolved_runtime_dir / "Scripts" / "python.exe"
    if not article_local.exists():
        raise RuntimeError(f"Windows runtime is missing Scripts/article-local.exe: {resolved_runtime_dir}")
    if not python_exe.exists():
        raise RuntimeError(f"Windows runtime is missing Scripts/python.exe: {resolved_runtime_dir}")

    resolved_output_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="article-windows-bundle-") as temp_dir:
        bundle_root = Path(temp_dir) / bundle_name
        app_dir = bundle_root / "app"
        state_root = bundle_root / "data" / "state"
        runtime_root = bundle_root / "data" / "runtime"
        shutil.copytree(resolved_runtime_dir, app_dir)
        state_root.mkdir(parents=True, exist_ok=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        (state_root / ".keep").write_text("", encoding="utf-8")
        (runtime_root / ".keep").write_text("", encoding="utf-8")

        launcher_path = bundle_root / LAUNCHER_NAME
        feedback_launcher_path = bundle_root / FEEDBACK_LAUNCHER_NAME
        quickstart_path = bundle_root / QUICKSTART_NAME
        _write_bundle_launcher(
            launcher_path,
            python_executable=app_dir / "Scripts" / "python.exe",
            state_root=state_root,
            runtime_root=runtime_root,
            release_api_url=release_api_url,
        )
        _write_feedback_launcher(
            feedback_launcher_path,
            python_executable=app_dir / "Scripts" / "python.exe",
            state_root=state_root,
            runtime_root=runtime_root,
        )
        _write_quickstart(quickstart_path)

        with zipfile.ZipFile(resolved_output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            entries = _add_tree_to_zip(archive, bundle_root)

    launcher_arcname = f"{bundle_name}/{LAUNCHER_NAME}"
    feedback_launcher_arcname = f"{bundle_name}/{FEEDBACK_LAUNCHER_NAME}"
    quickstart_arcname = f"{bundle_name}/{QUICKSTART_NAME}"
    return {
        "status": "ok",
        "bundle_name": bundle_name,
        "output_zip": str(resolved_output_zip),
        "runtime_dir": str(resolved_runtime_dir),
        "launcher": launcher_arcname,
        "feedback_launcher": feedback_launcher_arcname,
        "quickstart": quickstart_arcname,
        "entry_count": len(entries),
        "release_api_url_configured": bool(release_api_url),
        "entries": entries,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="build_windows_local_bundle.py")
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--output-zip", required=True)
    parser.add_argument("--bundle-name", default=DEFAULT_BUNDLE_NAME)
    parser.add_argument("--release-api-url", default="")
    return parser


def _emit_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is None:
            raise
        stdout_buffer.write(text.encode("utf-8"))
        stdout_buffer.flush()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = build_windows_local_bundle(
        runtime_dir=args.runtime_dir,
        output_zip=args.output_zip,
        bundle_name=args.bundle_name,
        release_api_url=args.release_api_url or None,
    )
    _emit_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
