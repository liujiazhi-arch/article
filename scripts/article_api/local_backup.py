from __future__ import annotations

import json
from pathlib import Path
import shutil
import zipfile

from . import storage
from . import app as app_module
from .local_env import RUNTIME_DIR_NAMES, resolved_roots, root_env_scope, utcnow


def _iter_state_files(state_root: Path) -> list[Path]:
    if not state_root.exists():
        return []
    files: list[Path] = []
    for path in sorted(state_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in RUNTIME_DIR_NAMES for part in path.relative_to(state_root).parts):
            continue
        files.append(path)
    return files


def _iter_runtime_files(runtime_root: Path) -> list[Path]:
    if not runtime_root.exists():
        return []
    files: list[Path] = []
    for dir_name in sorted(RUNTIME_DIR_NAMES):
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
    with root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
        archive_path = Path(output_path).expanduser().resolve()
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.exists():
            archive_path.unlink()

        storage_snapshot = storage.inspect_storage(resolved_state_root, include_integrity_check=False)
        state_files = _iter_state_files(resolved_state_root)
        runtime_files = _iter_runtime_files(resolved_runtime_root)
        manifest = {
            "created_at": utcnow(),
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

    with root_env_scope(state_root=state_root, runtime_root=runtime_root):
        with zipfile.ZipFile(archive) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            manifest_schema_version = manifest.get("schema_version")
            if manifest_schema_version is not None and int(manifest_schema_version) > storage.SCHEMA_VERSION:
                raise RuntimeError(
                    f"Backup archive schema version {manifest_schema_version} is newer than supported version {storage.SCHEMA_VERSION}"
                )
            resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
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
        "restored_at": utcnow(),
        "state_root": str(resolved_state_root),
        "runtime_root": str(resolved_runtime_root),
        "force": bool(force),
        "manifest": manifest,
        "restored_state_files": restored_state_files,
        "restored_runtime_files": restored_runtime_files,
    }
