from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import zipfile

from . import app as app_module
from .profile_batch import (
    BATCH_OPERATIONS,
    build_profile_catalog as build_profile_catalog_payload,
    run_batch_workflow as run_batch_workflow_payload,
)
from . import storage
from .uploads import RUNTIME_ROOT_ENV_VAR, resolve_runtime_root


_RUNTIME_DIR_NAMES = {"jobs", "uploads", "staging"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _emit_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _set_root_envs(*, state_root: str | None, runtime_root: str | None) -> None:
    if state_root:
        os.environ[storage.STATE_ROOT_ENV_VAR] = str(Path(state_root).expanduser().resolve())
    if runtime_root:
        os.environ[RUNTIME_ROOT_ENV_VAR] = str(Path(runtime_root).expanduser().resolve())


@contextmanager
def _root_env_scope(*, state_root: str | None, runtime_root: str | None):
    previous_state_root = os.environ.get(storage.STATE_ROOT_ENV_VAR)
    previous_runtime_root = os.environ.get(RUNTIME_ROOT_ENV_VAR)
    _set_root_envs(state_root=state_root, runtime_root=runtime_root)
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


def _resolved_roots(*, state_root: str | None, runtime_root: str | None) -> tuple[Path, Path]:
    return storage.resolve_state_root(state_root), resolve_runtime_root(runtime_root)


def build_profile_catalog() -> dict:
    return build_profile_catalog_payload(
        service_name=app_module.SERVICE_NAME,
        stage=app_module.SERVICE_STAGE,
        version=app_module.SERVICE_VERSION,
        api_version=app_module.API_VERSION,
    )


def run_preflight(
    file_path: str,
    *,
    profile: str = "lnu",
    strict_profile: bool | None = None,
) -> dict:
    return app_module.build_preflight_payload(
        file_path=file_path,
        profile_path=profile,
        strict_profile=strict_profile,
    )


def run_normalize(
    file_path: str,
    *,
    output_path: str | None = None,
    profile: str = "lnu",
    strict_profile: bool | None = None,
) -> dict:
    return app_module.build_normalize_payload(
        file_path=file_path,
        output_path=output_path,
        profile_path=profile,
        strict_profile=strict_profile,
    )


def run_render_verify(
    file_path: str,
    *,
    output_dir: str | None = None,
    profile: str = "lnu",
    strict_profile: bool | None = None,
    scopes=None,
    renderer: str = "auto",
) -> dict:
    return app_module.build_render_verify_payload(
        file_path=file_path,
        output_dir=output_dir,
        profile_path=profile,
        strict_profile=strict_profile,
        scopes=scopes,
        renderer=renderer,
    )


def _command_with_roots(command: str, *, state_root: Path, runtime_root: Path) -> str:
    return (
        f"{command} --state-root {shlex.quote(str(state_root))} "
        f"--runtime-root {shlex.quote(str(runtime_root))}"
    )


def _current_command_bin_dir() -> Path | None:
    candidate = Path(sys.executable).resolve().parent
    command_name = "article-local.exe" if sys.platform == "win32" else "article-local"
    if (candidate / command_name).exists():
        return candidate
    return None


def run_batch_workflow(
    operation: str,
    input_path: str,
    *,
    profile: str = "lnu",
    strict_profile: bool | None = None,
    scopes=None,
    output_dir: str | None = None,
    summary_file: str | None = None,
    pattern: str = "*.docx",
    recursive: bool = False,
    toc: bool = False,
    dry_run: bool = False,
    renumber_headings: bool = False,
    layout_rebalance: bool = False,
    force: bool = False,
    fail_fast: bool = False,
) -> dict:
    return run_batch_workflow_payload(
        operation,
        input_path,
        profile=profile,
        strict_profile=strict_profile,
        scopes=scopes,
        output_dir=output_dir,
        summary_file=summary_file,
        pattern=pattern,
        recursive=recursive,
        toc=toc,
        dry_run=dry_run,
        renumber_headings=renumber_headings,
        layout_rebalance=layout_rebalance,
        force=force,
        fail_fast=fail_fast,
        service_name=app_module.SERVICE_NAME,
        stage=app_module.SERVICE_STAGE,
        version=app_module.SERVICE_VERSION,
        api_version=app_module.API_VERSION,
    )


def _env_exports(*, state_root: Path, runtime_root: Path) -> str:
    lines = [
        f"export {storage.STATE_ROOT_ENV_VAR}={shlex.quote(str(state_root))}",
        f"export {RUNTIME_ROOT_ENV_VAR}={shlex.quote(str(runtime_root))}",
    ]
    command_bin_dir = _current_command_bin_dir()
    if command_bin_dir is not None:
        lines.append(f"export PATH={shlex.quote(str(command_bin_dir))}:$PATH")
    return "\n".join(lines) + "\n"


def _write_env_file(
    output_path: str,
    *,
    state_root: Path,
    runtime_root: Path,
    overwrite: bool = False,
) -> Path:
    env_path = Path(output_path).expanduser().resolve()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    expected_contents = _env_exports(state_root=state_root, runtime_root=runtime_root)
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
    resolved_state_root, resolved_runtime_root = _resolved_roots(state_root=state_root, runtime_root=runtime_root)
    storage.init_storage(resolved_state_root)
    runtime_directories: dict[str, dict[str, object]] = {}
    for dir_name in sorted(_RUNTIME_DIR_NAMES):
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
        env_file = _write_env_file(
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
        "observed_at": _utcnow(),
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


def _doctor_headline(status: str, issues: list[str]) -> str:
    if status == "ok":
        return "本地后端运行壳状态正常，可直接启动或继续处理论文任务。"
    if status == "warn":
        return "本地后端可运行，但存在需要尽快处理的运行告警。"
    if issues:
        return "本地后端存在阻断项，先处理 doctor 列出的告警再继续。"
    return "本地后端存在阻断项，暂不建议继续提交任务。"


def _doctor_issues(
    *,
    summary_view: dict,
    storage_view: dict,
    runtime_view: dict,
    runtime_root_view: dict,
) -> list[str]:
    issues: list[str] = []
    if storage_view["summary"]["status"] != "ok":
        issues.append(
            f"SQLite 状态库健康异常: integrity_check={storage_view['summary']['integrity_check'] or 'unknown'}。"
        )
    if not runtime_root_view["writable"]:
        issues.append(f"runtime_root 不可写: {runtime_root_view['path']}。")
    if runtime_view["summary"]["pending_recovery_count"] > 0:
        issues.append(
            f"有 {runtime_view['summary']['pending_recovery_count']} 个未完成任务处于 recovery grace window。"
        )
    if runtime_view["summary"]["recovered_failed_count"] > 0:
        issues.append(
            f"已有 {runtime_view['summary']['recovered_failed_count']} 个任务被恢复流程收口为 failed。"
        )
    if runtime_view["summary"]["stale_heartbeat_count"] > 0:
        issues.append(
            f"检测到 {runtime_view['summary']['stale_heartbeat_count']} 个活动任务 heartbeat 已过期。"
        )
    retention_summary = summary_view["retention"]["summary"]
    if retention_summary["last_error"]:
        issues.append(f"最近一次 retention 执行失败: {retention_summary['last_error']}")
    return issues


def _doctor_recommended_actions(
    *,
    summary_view: dict,
    state_root: Path,
    runtime_root: Path,
) -> list[str]:
    serve_cmd = _command_with_roots("article-local serve", state_root=state_root, runtime_root=runtime_root)
    doctor_cmd = _command_with_roots("article-local doctor", state_root=state_root, runtime_root=runtime_root)
    maintain_cmd = _command_with_roots("article-local maintain", state_root=state_root, runtime_root=runtime_root)
    backup_cmd = _command_with_roots("article-local backup ~/Desktop/article-backup.zip", state_root=state_root, runtime_root=runtime_root)
    actions: list[str] = []
    if summary_view["checks"]["storage"]["status"] != "ok":
        actions.append(f"先执行 `{maintain_cmd}`；若完整性仍异常，再从最近备份执行 restore。")
    if summary_view["checks"]["runtime_root"]["status"] != "ok":
        actions.append("修正 runtime_root 权限或切换到可写目录后，再重新运行 doctor。")
    if summary_view["checks"]["runtime_worker"]["pending_recovery_count"] > 0:
        actions.append(f"等待 recovery grace window 结束后重新执行 `{doctor_cmd}`，确认未完成任务是否已收口。")
    if summary_view["checks"]["runtime_worker"]["recovered_failed_count"] > 0:
        actions.append("检查 failed job，并按需通过 `/jobs/{job_id}/retry` 或 UI 重提任务。")
    if summary_view["checks"]["retention"]["status"] == "warn":
        actions.append("检查 retention 配置和最近一次 sweep 错误，必要时手动运行 retention sweep。")
    if not actions:
        actions.append(f"可以直接启动本地 API：`{serve_cmd}`")
    if summary_view["jobs"]["total"] > 0 or summary_view["uploads"]["total"] > 0:
        actions.append(f"在做破坏性维护前，先执行一次备份：`{backup_cmd}`")
    return actions


def build_doctor_report(*, state_root: str | None = None, runtime_root: str | None = None) -> dict:
    with _root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = _resolved_roots(state_root=state_root, runtime_root=runtime_root)
        summary_view = app_module._ops_summary_payload()
        storage_view = app_module._ops_storage_payload()
        runtime_view = app_module._ops_runtime_payload()
    runtime_root_view = storage_view["runtime_root"]
    roots_shared = resolved_state_root == resolved_runtime_root
    issues = _doctor_issues(
        summary_view=summary_view,
        storage_view=storage_view,
        runtime_view=runtime_view,
        runtime_root_view=runtime_root_view,
    )
    recommended_actions = _doctor_recommended_actions(
        summary_view=summary_view,
        state_root=resolved_state_root,
        runtime_root=resolved_runtime_root,
    )
    return {
        "service": app_module.SERVICE_NAME,
        "stage": app_module.SERVICE_STAGE,
        "version": app_module.SERVICE_VERSION,
        "api_version": app_module.API_VERSION,
        "observed_at": _utcnow(),
        "status": summary_view["status"],
        "summary": {
            "headline": _doctor_headline(summary_view["status"], issues),
            "issue_count": len(issues),
            "issues": issues,
            "recommended_actions": recommended_actions,
        },
        "roots": {
            "shared_root": roots_shared,
            "state_root": str(resolved_state_root),
            "runtime_root": str(resolved_runtime_root),
            "state_root_writable": storage_view["storage"]["state_root_writable"],
            "runtime_root_writable": runtime_root_view["writable"],
        },
        "checks": summary_view["checks"],
        "inventory": {
            "jobs": summary_view["jobs"],
            "uploads": summary_view["uploads"],
            "cleanup": summary_view["cleanup"],
            "runtime_root": {
                "managed_directory_count": runtime_root_view["managed_directory_count"],
                "managed_file_count": runtime_root_view["managed_file_count"],
                "directories": runtime_root_view["directories"],
            },
        },
        "storage": storage_view["summary"],
        "runtime": runtime_view["summary"],
        "retention": {
            "defaults": summary_view["retention"]["defaults"],
            "state": summary_view["retention"]["state"],
            "summary": summary_view["retention"]["summary"],
        },
        "workflow": {
            "doctor": _command_with_roots("article-local doctor", state_root=resolved_state_root, runtime_root=resolved_runtime_root),
            "serve": _command_with_roots("article-local serve", state_root=resolved_state_root, runtime_root=resolved_runtime_root),
            "maintain": _command_with_roots("article-local maintain", state_root=resolved_state_root, runtime_root=resolved_runtime_root),
            "backup": _command_with_roots(
                "article-local backup ~/Desktop/article-backup.zip",
                state_root=resolved_state_root,
                runtime_root=resolved_runtime_root,
            ),
            "restore": _command_with_roots(
                "article-local restore ~/Desktop/article-backup.zip --force",
                state_root=resolved_state_root,
                runtime_root=resolved_runtime_root,
            ),
        },
    }


def run_storage_maintenance(
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
    run_vacuum: bool = False,
    run_analyze: bool = True,
) -> dict:
    with _root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = _resolved_roots(state_root=state_root, runtime_root=runtime_root)
        maintenance = storage.maintain_storage(
            resolved_state_root,
            run_vacuum=run_vacuum,
            run_analyze=run_analyze,
        )
        storage_view = app_module._ops_storage_payload()
    return {
        "service": app_module.SERVICE_NAME,
        "stage": app_module.SERVICE_STAGE,
        "version": app_module.SERVICE_VERSION,
        "api_version": app_module.API_VERSION,
        "observed_at": _utcnow(),
        "roots": {
            "state_root": str(resolved_state_root),
            "runtime_root": str(resolved_runtime_root),
            "shared_root": resolved_state_root == resolved_runtime_root,
        },
        "summary": {
            "headline": "本地状态库维护完成。",
            "actions": maintenance["actions"],
            "size_bytes_before": maintenance["size_bytes_before"],
            "size_bytes_after": maintenance["size_bytes_after"],
            "size_delta_bytes": maintenance["size_delta_bytes"],
        },
        "maintenance": maintenance,
        "storage": storage_view["summary"],
    }


def _iter_state_files(state_root: Path) -> list[Path]:
    if not state_root.exists():
        return []
    files: list[Path] = []
    for path in sorted(state_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _RUNTIME_DIR_NAMES for part in path.relative_to(state_root).parts):
            continue
        files.append(path)
    return files


def _iter_runtime_files(runtime_root: Path) -> list[Path]:
    if not runtime_root.exists():
        return []
    files: list[Path] = []
    for dir_name in sorted(_RUNTIME_DIR_NAMES):
        root = runtime_root / dir_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append(path)
    return files


def create_backup_archive(
    output_path: str,
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
) -> dict:
    with _root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = _resolved_roots(state_root=state_root, runtime_root=runtime_root)
        archive_path = Path(output_path).expanduser().resolve()
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            archive_path.unlink()

        storage_snapshot = storage.inspect_storage(resolved_state_root, include_integrity_check=False)
        state_files = _iter_state_files(resolved_state_root)
        runtime_files = _iter_runtime_files(resolved_runtime_root)
        manifest = {
            "created_at": _utcnow(),
            "service": app_module.SERVICE_NAME,
            "version": app_module.SERVICE_VERSION,
            "schema_version": storage_snapshot["schema_version"],
            "supported_schema_versions": storage_snapshot["supported_schema_versions"],
            "state_root": str(resolved_state_root),
            "runtime_root": str(resolved_runtime_root),
            "shared_root": resolved_state_root == resolved_runtime_root,
            "state_files": len(state_files),
            "runtime_files": len(runtime_files),
        }

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            for file_path in state_files:
                zf.write(file_path, arcname=str(Path("state_root") / file_path.relative_to(resolved_state_root)))
            for file_path in runtime_files:
                zf.write(file_path, arcname=str(Path("runtime_root") / file_path.relative_to(resolved_runtime_root)))

    return {
        "archive_path": str(archive_path),
        "created_at": manifest["created_at"],
        "state_root": str(resolved_state_root),
        "runtime_root": str(resolved_runtime_root),
        "shared_root": manifest["shared_root"],
        "state_file_count": len(state_files),
        "runtime_file_count": len(runtime_files),
        "size_bytes": archive_path.stat().st_size,
    }


def _ensure_restorable_root(root: Path, *, force: bool) -> None:
    if force:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        return
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise RuntimeError(f"Restore target is not empty: {root}. Use --force to replace it.")


def _resolve_restore_target(root: Path, relative_path: Path) -> Path:
    resolved_root = root.resolve()
    target_path = (resolved_root / relative_path).resolve()
    try:
        target_path.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"Archive member escapes restore root: {relative_path}") from exc
    return target_path


def restore_backup_archive(
    archive_path: str,
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
    force: bool = False,
) -> dict:
    archive = Path(archive_path).expanduser().resolve()
    if not archive.exists():
        raise RuntimeError(f"Backup archive not found: {archive}")

    with _root_env_scope(state_root=state_root, runtime_root=runtime_root):
        with zipfile.ZipFile(archive) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            manifest_schema_version = manifest.get("schema_version")
            if manifest_schema_version is not None and int(manifest_schema_version) > storage.SCHEMA_VERSION:
                raise RuntimeError(
                    f"Backup archive schema version {manifest_schema_version} is newer than supported version {storage.SCHEMA_VERSION}"
                )
            resolved_state_root, resolved_runtime_root = _resolved_roots(state_root=state_root, runtime_root=runtime_root)
            _ensure_restorable_root(resolved_state_root, force=force)
            if resolved_runtime_root != resolved_state_root:
                _ensure_restorable_root(resolved_runtime_root, force=force)

            restored_state_files = 0
            restored_runtime_files = 0
            for member in zf.namelist():
                if member == "manifest.json" or member.endswith("/"):
                    continue
                if member.startswith("state_root/"):
                    relative_path = Path(member).relative_to("state_root")
                    target_path = _resolve_restore_target(resolved_state_root, relative_path)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, target_path.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    restored_state_files += 1
                elif member.startswith("runtime_root/"):
                    relative_path = Path(member).relative_to("runtime_root")
                    target_path = _resolve_restore_target(resolved_runtime_root, relative_path)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, target_path.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    restored_runtime_files += 1
        storage.inspect_storage(resolved_state_root, include_integrity_check=False)

    return {
        "archive_path": str(archive),
        "restored_at": _utcnow(),
        "state_root": str(resolved_state_root),
        "runtime_root": str(resolved_runtime_root),
        "force": bool(force),
        "manifest": manifest,
        "restored_state_files": restored_state_files,
        "restored_runtime_files": restored_runtime_files,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="article-local")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--state-root")
    init_parser.add_argument("--runtime-root")
    init_parser.add_argument("--write-env")
    init_parser.add_argument("--overwrite-env", action="store_true")
    init_parser.set_defaults(handler=_handle_init)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=8000, type=int)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--state-root")
    serve_parser.add_argument("--runtime-root")
    serve_parser.set_defaults(handler=_handle_serve)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--state-root")
    doctor_parser.add_argument("--runtime-root")
    doctor_parser.set_defaults(handler=_handle_doctor)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("input")
    preflight_parser.add_argument("--profile", default="lnu")
    preflight_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    preflight_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    preflight_parser.set_defaults(handler=_handle_preflight)

    normalize_parser = subparsers.add_parser("normalize")
    normalize_parser.add_argument("input")
    normalize_parser.add_argument("--output")
    normalize_parser.add_argument("--profile", default="lnu")
    normalize_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    normalize_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    normalize_parser.set_defaults(handler=_handle_normalize)

    render_verify_parser = subparsers.add_parser("render-verify")
    render_verify_parser.add_argument("input")
    render_verify_parser.add_argument("--profile", default="lnu")
    render_verify_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    render_verify_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    render_verify_parser.add_argument("--output-dir")
    render_verify_parser.add_argument("--scope", action="append", default=None)
    render_verify_parser.add_argument("--renderer", choices=["auto", "word-pdf", "artifact-tool"], default="auto")
    render_verify_parser.set_defaults(handler=_handle_render_verify)

    profiles_parser = subparsers.add_parser("profiles")
    profiles_parser.set_defaults(handler=_handle_profiles)

    batch_parser = subparsers.add_parser("batch")
    batch_parser.add_argument("operation", choices=BATCH_OPERATIONS)
    batch_parser.add_argument("input")
    batch_parser.add_argument("--profile", default="lnu")
    batch_parser.add_argument("--strict-profile", dest="strict_profile", action="store_true", default=None)
    batch_parser.add_argument("--allow-profile-fallback", dest="strict_profile", action="store_false")
    batch_parser.add_argument("--scope", action="append", default=None)
    batch_parser.add_argument("--output-dir")
    batch_parser.add_argument("--summary-file")
    batch_parser.add_argument("--pattern", default="*.docx")
    batch_parser.add_argument("--recursive", action="store_true")
    batch_parser.add_argument("--toc", action="store_true")
    batch_parser.add_argument("--dry-run", action="store_true")
    batch_parser.add_argument("--renumber-headings", action="store_true")
    batch_parser.add_argument("--layout-rebalance", action="store_true")
    batch_parser.add_argument("--force", action="store_true")
    batch_parser.add_argument("--fail-fast", action="store_true")
    batch_parser.set_defaults(handler=_handle_batch)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("output")
    backup_parser.add_argument("--state-root")
    backup_parser.add_argument("--runtime-root")
    backup_parser.set_defaults(handler=_handle_backup)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("archive")
    restore_parser.add_argument("--state-root")
    restore_parser.add_argument("--runtime-root")
    restore_parser.add_argument("--force", action="store_true")
    restore_parser.set_defaults(handler=_handle_restore)

    maintain_parser = subparsers.add_parser("maintain")
    maintain_parser.add_argument("--state-root")
    maintain_parser.add_argument("--runtime-root")
    maintain_parser.add_argument("--vacuum", action="store_true")
    maintain_parser.add_argument("--no-analyze", action="store_true")
    maintain_parser.set_defaults(handler=_handle_maintain)
    return parser


def _load_uvicorn():
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("uvicorn is required to run article-local serve. Install the optional api dependencies.") from exc
    return uvicorn


def _handle_serve(args: argparse.Namespace) -> int:
    with _root_env_scope(state_root=args.state_root, runtime_root=args.runtime_root):
        uvicorn = _load_uvicorn()
        uvicorn.run(
            "article_api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=bool(args.reload),
        )
    return 0


def _handle_init(args: argparse.Namespace) -> int:
    _emit_json(
        initialize_local_workspace(
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            write_env=args.write_env,
            overwrite_env=bool(args.overwrite_env),
        )
    )
    return 0


def _handle_doctor(args: argparse.Namespace) -> int:
    _emit_json(build_doctor_report(state_root=args.state_root, runtime_root=args.runtime_root))
    return 0


def _handle_preflight(args: argparse.Namespace) -> int:
    _emit_json(
        run_preflight(
            args.input,
            profile=args.profile,
            strict_profile=args.strict_profile,
        )
    )
    return 0


def _handle_normalize(args: argparse.Namespace) -> int:
    _emit_json(
        run_normalize(
            args.input,
            output_path=args.output,
            profile=args.profile,
            strict_profile=args.strict_profile,
        )
    )
    return 0


def _handle_render_verify(args: argparse.Namespace) -> int:
    _emit_json(
        run_render_verify(
            args.input,
            output_dir=args.output_dir,
            profile=args.profile,
            strict_profile=args.strict_profile,
            scopes=args.scope,
            renderer=args.renderer,
        )
    )
    return 0


def _handle_profiles(_args: argparse.Namespace) -> int:
    _emit_json(build_profile_catalog())
    return 0


def _handle_batch(args: argparse.Namespace) -> int:
    _emit_json(
        run_batch_workflow(
            args.operation,
            args.input,
            profile=args.profile,
            strict_profile=args.strict_profile,
            scopes=args.scope,
            output_dir=args.output_dir,
            summary_file=args.summary_file,
            pattern=args.pattern,
            recursive=bool(args.recursive),
            toc=bool(args.toc),
            dry_run=bool(args.dry_run),
            renumber_headings=bool(args.renumber_headings),
            layout_rebalance=bool(args.layout_rebalance),
            force=bool(args.force),
            fail_fast=bool(args.fail_fast),
        )
    )
    return 0


def _handle_backup(args: argparse.Namespace) -> int:
    _emit_json(
        create_backup_archive(
            args.output,
            state_root=args.state_root,
            runtime_root=args.runtime_root,
        )
    )
    return 0


def _handle_restore(args: argparse.Namespace) -> int:
    _emit_json(
        restore_backup_archive(
            args.archive,
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            force=bool(args.force),
        )
    )
    return 0


def _handle_maintain(args: argparse.Namespace) -> int:
    _emit_json(
        run_storage_maintenance(
            state_root=args.state_root,
            runtime_root=args.runtime_root,
            run_vacuum=bool(args.vacuum),
            run_analyze=not bool(args.no_analyze),
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


def serve_main() -> int:
    return main(["serve", *sys.argv[1:]])


def doctor_main() -> int:
    return main(["doctor", *sys.argv[1:]])


def backup_main() -> int:
    return main(["backup", *sys.argv[1:]])


def restore_main() -> int:
    return main(["restore", *sys.argv[1:]])


def maintain_main() -> int:
    return main(["maintain", *sys.argv[1:]])
