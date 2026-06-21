from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import site
import subprocess
import sys
import sysconfig
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VENV_DIR = Path("~/.article/venv")
DEFAULT_STATE_ROOT = Path("~/.article/state")
DEFAULT_RUNTIME_ROOT = Path("~/.article/runtime")
DEFAULT_ENV_FILE = Path("~/.article/article-local.env")
DEFAULT_ARTIFACT_DIR = Path("~/.article/dist")
SUPPORTED_INSTALL_MODES = {"editable", "wheel"}
INSTALL_HISTORY_FILENAME = "install-history.json"
DEFAULT_LOCAL_URL = "http://127.0.0.1:8000"


def _resolve_path(path_value: str | Path) -> Path:
    return Path(path_value).expanduser().resolve()


def _resolve_python_executable(path_value: str | Path) -> Path:
    raw_value = str(path_value)
    expanded = Path(raw_value).expanduser()
    has_path_separator = any(separator and separator in raw_value for separator in (os.sep, os.altsep))
    if expanded.is_absolute() or has_path_separator:
        resolved = expanded.resolve()
        if not resolved.exists():
            raise RuntimeError(f"Python executable not found: {raw_value}")
        return resolved

    discovered = shutil.which(raw_value)
    if discovered:
        return Path(discovered).resolve()

    resolved = expanded.resolve()
    if resolved.exists():
        return resolved
    raise RuntimeError(f"Python executable not found: {raw_value}")


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, script_name: str) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / f"{script_name}.exe"
    return venv_dir / "bin" / script_name


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=capture_output,
        env=env,
        check=True,
    )


def _with_roots(command: str | Path, *, state_root: Path, runtime_root: Path) -> str:
    return (
        f"{shlex.quote(str(command))} --state-root {shlex.quote(str(state_root))} "
        f"--runtime-root {shlex.quote(str(runtime_root))}"
    )


def _article_local_command(
    command_prefix: str,
    subcommand: str,
    *,
    state_root: Path,
    runtime_root: Path,
) -> str:
    return (
        f"{command_prefix} {subcommand} "
        f"--state-root {shlex.quote(str(state_root))} "
        f"--runtime-root {shlex.quote(str(runtime_root))}"
    )


def _normalize_install_mode(value: str) -> str:
    mode = str(value).strip().lower()
    if mode not in SUPPORTED_INSTALL_MODES:
        supported = ", ".join(sorted(SUPPORTED_INSTALL_MODES))
        raise RuntimeError(f"Unsupported install mode: {value}. Supported modes: {supported}")
    return mode


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _direct_url_requirement(
    wheel_path: Path,
    *,
    extras: str,
) -> str:
    extras_suffix = f"[{extras}]" if extras else ""
    return f"thesis-format-tool{extras_suffix} @ {wheel_path.resolve().as_uri()}"


def _resolve_built_wheel(artifact_dir: Path) -> Path:
    candidates = sorted(artifact_dir.glob("*.whl"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"No wheel artifact was produced in {artifact_dir}")
    return candidates[0]


def _install_history_path(artifact_dir: Path) -> Path:
    return artifact_dir / INSTALL_HISTORY_FILENAME


def _load_install_history(artifact_dir: Path) -> dict:
    history_path = _install_history_path(artifact_dir)
    if not history_path.exists():
        return {"current_index": -1, "entries": []}
    return json.loads(history_path.read_text(encoding="utf-8"))


def _write_install_history(artifact_dir: Path, payload: dict) -> Path:
    history_path = _install_history_path(artifact_dir)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return history_path


def _find_previous_wheel_entry(artifact_dir: Path) -> dict | None:
    history = _load_install_history(artifact_dir)
    entries = list(history.get("entries") or [])
    current_index = int(history.get("current_index", len(entries) - 1))
    for index in range(current_index - 1, -1, -1):
        entry = entries[index]
        wheel_path = entry.get("wheel_path")
        if wheel_path and Path(wheel_path).exists():
            return entry
    return None


def _record_wheel_install(
    artifact_dir: Path,
    *,
    wheel_path: Path,
    extras: str,
    venv_dir: Path,
    operation: str,
) -> dict:
    history = _load_install_history(artifact_dir)
    entries = list(history.get("entries") or [])
    entries.append(
        {
            "installed_at": _utcnow(),
            "operation": operation,
            "wheel_path": str(wheel_path.resolve()),
            "extras": extras,
            "venv_dir": str(venv_dir.resolve()),
        }
    )
    updated = {
        "current_index": len(entries) - 1,
        "entries": entries,
    }
    _write_install_history(artifact_dir, updated)
    return updated


def _no_deps_build_env() -> dict[str, str]:
    env = os.environ.copy()
    site_paths: list[str] = []
    for candidate in site.getsitepackages():
        if candidate and candidate not in site_paths:
            site_paths.append(candidate)
    for key in ("purelib", "platlib"):
        candidate = sysconfig.get_paths().get(key)
        if candidate and candidate not in site_paths:
            site_paths.append(candidate)
    existing = env.get("PYTHONPATH")
    if existing:
        site_paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(site_paths)
    return env


def _batch_path_from_launcher(launcher_path: Path, target_path: Path) -> str:
    try:
        relative_path = os.path.relpath(target_path, launcher_path.parent)
    except ValueError:
        return str(target_path)
    return "%~dp0" + relative_path.replace("/", "\\")


def _write_windows_launcher(
    launcher_path: Path,
    *,
    article_local: Path,
    state_root: Path,
    runtime_root: Path,
    url: str = DEFAULT_LOCAL_URL,
) -> Path:
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    article_local_path = _batch_path_from_launcher(launcher_path, article_local)
    state_root_path = _batch_path_from_launcher(launcher_path, state_root)
    runtime_root_path = _batch_path_from_launcher(launcher_path, runtime_root)
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "title 论文格式检查",
        "setlocal",
        f'set "ARTICLE_LOCAL={article_local_path}"',
        "",
        "echo 正在检查本地运行环境...",
        f'"%ARTICLE_LOCAL%" doctor --state-root "{state_root_path}" --runtime-root "{runtime_root_path}"',
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
        f'"%ARTICLE_LOCAL%" serve --host 127.0.0.1 --port 8000 --state-root "{state_root_path}" --runtime-root "{runtime_root_path}"',
        "if errorlevel 1 (",
        "  echo.",
        "  echo 本地服务启动失败。常见原因：端口 8000 被占用，或安装文件不完整。",
        "  pause",
        "  exit /b 1",
        ")",
    ]
    launcher_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")
    return launcher_path


def install_local_app(
    *,
    python_executable: str | Path = sys.executable,
    venv_dir: str | Path = DEFAULT_VENV_DIR,
    state_root: str | Path = DEFAULT_STATE_ROOT,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    write_env: str | Path | None = DEFAULT_ENV_FILE,
    dev: bool = False,
    no_deps: bool = False,
    skip_init: bool = False,
    overwrite_env: bool = False,
    install_mode: str = "editable",
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    upgrade: bool = False,
    rollback: bool = False,
    launcher_path: str | Path | None = None,
) -> dict:
    resolved_python = _resolve_python_executable(python_executable)
    resolved_venv_dir = _resolve_path(venv_dir)
    resolved_state_root = _resolve_path(state_root)
    resolved_runtime_root = _resolve_path(runtime_root)
    resolved_env_file = _resolve_path(write_env) if write_env is not None else None
    resolved_artifact_dir = _resolve_path(artifact_dir)
    resolved_launcher_path = _resolve_path(launcher_path) if launcher_path is not None else None
    resolved_install_mode = _normalize_install_mode(install_mode)

    if upgrade and rollback:
        raise RuntimeError("`--upgrade` and `--rollback` cannot be used together.")
    if upgrade or rollback:
        resolved_install_mode = "wheel"

    if no_deps and not skip_init:
        raise RuntimeError("`--no-deps` requires `--skip-init` because `lnu-thesis-local init` needs installed runtime dependencies.")

    venv_existed = resolved_venv_dir.exists()
    venv_command = [str(resolved_python), "-m", "venv"]
    if no_deps:
        venv_command.append("--system-site-packages")
    venv_command.append(str(resolved_venv_dir))
    _run(venv_command, cwd=PROJECT_ROOT)

    venv_python = _venv_python(resolved_venv_dir)
    extras = "api,dev" if dev else "api"
    install_target = f".[{extras}]"
    wheel_path: Path | None = None
    build_command: list[str] | None = None
    install_operation = "upgrade" if upgrade else "install"

    if rollback:
        previous_entry = _find_previous_wheel_entry(resolved_artifact_dir)
        if previous_entry is None:
            raise RuntimeError(f"No previous wheel install is available for rollback in {resolved_artifact_dir}")
        wheel_path = Path(previous_entry["wheel_path"]).resolve()
        extras = str(previous_entry.get("extras") or extras)
        install_target = f".[{extras}]"
        install_command = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "--force-reinstall",
            _direct_url_requirement(wheel_path, extras=extras),
        ]
        install_operation = "rollback"
        if no_deps:
            install_command.insert(4, "--no-deps")
    elif resolved_install_mode == "editable":
        install_command = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "-e",
            install_target,
        ]
        if no_deps:
            install_command.insert(4, "--no-deps")
    else:
        resolved_artifact_dir.mkdir(parents=True, exist_ok=True)
        build_command = [
            str(venv_python),
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(resolved_artifact_dir),
            ".",
        ]
        _run(build_command, cwd=PROJECT_ROOT)
        wheel_path = _resolve_built_wheel(resolved_artifact_dir)
        install_command = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-build-isolation",
            "--force-reinstall",
            _direct_url_requirement(wheel_path, extras=extras),
        ]
        if no_deps:
            install_command.insert(4, "--no-deps")
    try:
        _run(
            install_command,
            cwd=PROJECT_ROOT,
            env=_no_deps_build_env() if no_deps else None,
        )
    except subprocess.CalledProcessError as exc:
        hint = (
            "Install failed while preparing the local editable package. "
            "If you are using `--no-deps`, make sure build backend tools such as setuptools are available "
            "in the selected interpreter or rerun without `--no-deps`."
        )
        raise RuntimeError(hint) from exc

    install_history = None
    if resolved_install_mode == "wheel" and wheel_path is not None:
        install_history = _record_wheel_install(
            resolved_artifact_dir,
            wheel_path=wheel_path,
            extras=extras,
            venv_dir=resolved_venv_dir,
            operation=install_operation,
        )

    lnu_thesis_local = _venv_script(resolved_venv_dir, "lnu-thesis-local")
    article_local = lnu_thesis_local
    init_payload = None
    quickstart_prefix = (
        "lnu-thesis-local"
        if resolved_env_file is not None and not skip_init
        else shlex.quote(str(lnu_thesis_local))
    )
    quickstart = {
        "activate_env": f"source {shlex.quote(str(resolved_env_file))}" if resolved_env_file is not None else None,
        "doctor": _article_local_command(
            quickstart_prefix,
            "doctor",
            state_root=resolved_state_root,
            runtime_root=resolved_runtime_root,
        ),
        "serve": _article_local_command(
            quickstart_prefix,
            "serve",
            state_root=resolved_state_root,
            runtime_root=resolved_runtime_root,
        ),
        "maintain": _article_local_command(
            quickstart_prefix,
            "maintain",
            state_root=resolved_state_root,
            runtime_root=resolved_runtime_root,
        ),
        "backup": (
            f"{quickstart_prefix} backup ~/Desktop/article-backup.zip "
            f"--state-root {shlex.quote(str(resolved_state_root))} "
            f"--runtime-root {shlex.quote(str(resolved_runtime_root))}"
        ),
        "restore": (
            f"{quickstart_prefix} restore ~/Desktop/article-backup.zip "
            f"--state-root {shlex.quote(str(resolved_state_root))} "
            f"--runtime-root {shlex.quote(str(resolved_runtime_root))} --force"
        ),
        "launcher": str(resolved_launcher_path) if resolved_launcher_path is not None else None,
    }
    if not skip_init:
        init_command = [
            str(article_local),
            "init",
            "--state-root",
            str(resolved_state_root),
            "--runtime-root",
            str(resolved_runtime_root),
        ]
        if resolved_env_file is not None:
            init_command.extend(["--write-env", str(resolved_env_file)])
            if overwrite_env:
                init_command.append("--overwrite-env")
        completed = _run(init_command, cwd=PROJECT_ROOT, capture_output=True)
        try:
            init_payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("`lnu-thesis-local init` did not return valid JSON output.") from exc

    written_launcher_path = None
    if resolved_launcher_path is not None:
        written_launcher_path = _write_windows_launcher(
            resolved_launcher_path,
            article_local=article_local,
            state_root=resolved_state_root,
            runtime_root=resolved_runtime_root,
        )

    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "python": str(resolved_python),
        "venv": {
            "path": str(resolved_venv_dir),
            "existed": venv_existed,
            "system_site_packages": bool(no_deps),
            "python": str(venv_python),
            "article_local": str(article_local),
        },
        "install": {
            "operation": install_operation,
            "mode": resolved_install_mode,
            "editable_target": install_target,
            "dev": bool(dev),
            "no_deps": bool(no_deps),
            "skip_init": bool(skip_init),
            "build_command": build_command,
            "command": install_command,
        },
        "distribution": {
            "artifact_dir": str(resolved_artifact_dir),
            "wheel_path": str(wheel_path) if wheel_path is not None else None,
            "install_history_path": str(_install_history_path(resolved_artifact_dir)),
            "rollback_available": _find_previous_wheel_entry(resolved_artifact_dir) is not None,
            "history": install_history,
        },
        "roots": {
            "state_root": str(resolved_state_root),
            "runtime_root": str(resolved_runtime_root),
        },
        "env_file": str(resolved_env_file) if resolved_env_file is not None else None,
        "launcher": {
            "path": str(written_launcher_path) if written_launcher_path is not None else None,
            "url": DEFAULT_LOCAL_URL,
        },
        "quickstart": quickstart,
        "init": init_payload,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="install_article_local.py")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--venv", default=str(DEFAULT_VENV_DIR))
    parser.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT))
    parser.add_argument("--write-env", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--no-deps", action="store_true")
    parser.add_argument("--skip-init", action="store_true")
    parser.add_argument("--overwrite-env", action="store_true")
    parser.add_argument("--install-mode", choices=sorted(SUPPORTED_INSTALL_MODES), default="editable")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--launcher-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = install_local_app(
        python_executable=args.python,
        venv_dir=args.venv,
        state_root=args.state_root,
        runtime_root=args.runtime_root,
        write_env=args.write_env,
        dev=bool(args.dev),
        no_deps=bool(args.no_deps),
        skip_init=bool(args.skip_init),
        overwrite_env=bool(args.overwrite_env),
        install_mode=args.install_mode,
        artifact_dir=args.artifact_dir,
        upgrade=bool(args.upgrade),
        rollback=bool(args.rollback),
        launcher_path=args.launcher_path,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
