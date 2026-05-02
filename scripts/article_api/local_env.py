from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import sys

from . import app as app_module
from . import storage
from .uploads import RUNTIME_ROOT_ENV_VAR, resolve_runtime_root


RUNTIME_DIR_NAMES = {"jobs", "uploads", "staging"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def set_root_envs(*, state_root: str | None, runtime_root: str | None) -> None:
    if state_root:
        os.environ[storage.STATE_ROOT_ENV_VAR] = str(Path(state_root).expanduser().resolve())
    if runtime_root:
        os.environ[RUNTIME_ROOT_ENV_VAR] = str(Path(runtime_root).expanduser().resolve())


@contextmanager
def root_env_scope(*, state_root: str | None, runtime_root: str | None):
    previous_state_root = os.environ.get(storage.STATE_ROOT_ENV_VAR)
    previous_runtime_root = os.environ.get(RUNTIME_ROOT_ENV_VAR)
    set_root_envs(state_root=state_root, runtime_root=runtime_root)
    try:
        yield
    finally:
        if previous_state_root is None:
            os.environ.pop(storage.STATE_ROOT_ENV_VAR, None)
        else:
            os.environ[storage.STATE_ROOT_ENV_VAR] = previous_state_root
        if previous_runtime_root is None:
            os.environ.pop(RUNTIME_ROOT_ENV_VAR, None)
        else:
            os.environ[RUNTIME_ROOT_ENV_VAR] = previous_runtime_root


def resolved_roots(*, state_root: str | None, runtime_root: str | None) -> tuple[Path, Path]:
    return storage.resolve_state_root(state_root), resolve_runtime_root(runtime_root)


def command_with_roots(command: str, *, state_root: Path, runtime_root: Path) -> str:
    return (
        f"{command} --state-root {shlex.quote(str(state_root))} "
        f"--runtime-root {shlex.quote(str(runtime_root))}"
    )


def current_command_bin_dir() -> Path | None:
    candidate = Path(sys.executable).resolve().parent
    command_name = "article-local.exe" if sys.platform == "win32" else "article-local"
    if (candidate / command_name).exists():
        return candidate
    return None


def env_exports(*, state_root: Path, runtime_root: Path) -> str:
    lines = [
        f"export {storage.STATE_ROOT_ENV_VAR}={shlex.quote(str(state_root))}",
        f"export {RUNTIME_ROOT_ENV_VAR}={shlex.quote(str(runtime_root))}",
    ]
    command_bin_dir = current_command_bin_dir()
    if command_bin_dir is not None:
        lines.append(f"export PATH={shlex.quote(str(command_bin_dir))}:$PATH")
    return "\n".join(lines) + "\n"


def write_env_file(
    output_path: str,
    *,
    state_root: Path,
    runtime_root: Path,
    overwrite: bool = False,
) -> Path:
    env_path = Path(output_path).expanduser().resolve()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    expected_contents = env_exports(state_root=state_root, runtime_root=runtime_root)
    if env_path.exists() and not overwrite:
        if env_path.read_text(encoding="utf-8") == expected_contents:
            return env_path
        raise RuntimeError(f"Env file already exists: {env_path}. Pass --overwrite-env to replace it.")
    env_path.write_text(expected_contents, encoding="utf-8")
    return env_path


def initialize_local_workspace(
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
    write_env: str | None = None,
    overwrite_env: bool = False,
) -> dict:
    from .local_doctor import build_doctor_report

    resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
    storage.init_storage(resolved_state_root)
    runtime_directories: dict[str, dict[str, object]] = {}
    for dir_name in sorted(RUNTIME_DIR_NAMES):
        path = resolved_runtime_root / dir_name
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        runtime_directories[dir_name] = {
            "path": str(path),
            "created": not existed,
            "exists": True,
        }
    env_file = None
    if write_env:
        env_file = write_env_file(
            write_env,
            state_root=resolved_state_root,
            runtime_root=resolved_runtime_root,
            overwrite=overwrite_env,
        )
    doctor_report = build_doctor_report(
        state_root=str(resolved_state_root),
        runtime_root=str(resolved_runtime_root),
    )
    return {
        "service": app_module.SERVICE_NAME,
        "stage": app_module.SERVICE_STAGE,
        "version": app_module.SERVICE_VERSION,
        "api_version": app_module.API_VERSION,
        "observed_at": utcnow(),
        "status": "ok",
        "roots": {
            "state_root": str(resolved_state_root),
            "runtime_root": str(resolved_runtime_root),
            "shared_root": resolved_state_root == resolved_runtime_root,
        },
        "summary": {
            "headline": "本地运行壳初始化完成。",
            "next_steps": [
                doctor_report["workflow"]["doctor"],
                doctor_report["workflow"]["serve"],
            ],
        },
        "storage": {
            "schema_version": storage.get_schema_version(resolved_state_root),
            "db_path": str(storage.resolve_db_path(resolved_state_root)),
        },
        "runtime": {
            "directories": runtime_directories,
        },
        "env": {
            "file_path": str(env_file) if env_file is not None else None,
            "exports": {
                storage.STATE_ROOT_ENV_VAR: str(resolved_state_root),
                RUNTIME_ROOT_ENV_VAR: str(resolved_runtime_root),
            },
        },
        "doctor": {
            "status": doctor_report["status"],
            "headline": doctor_report["summary"]["headline"],
            "recommended_actions": doctor_report["summary"]["recommended_actions"],
        },
    }
