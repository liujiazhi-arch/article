from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
import zipfile

from . import app as app_module
from . import storage
from .local_doctor import build_doctor_report
from .local_env import resolved_roots, root_env_scope, utcnow


_DOCUMENT_ARTIFACT_SUFFIXES = {
    ".doc",
    ".docx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
_DIAGNOSTIC_FILE_SUFFIXES = {".log", ".txt"}
_DOCUMENT_ARTIFACT_NAME_RE = re.compile(
    r"[^/\\\r\n\"']+\.(?:doc|docx|pdf|png|jpg|jpeg|webp)",
    re.IGNORECASE,
)
_DOCUMENT_FILE_PLACEHOLDER = "<document-file>"
_DOCUMENT_NAME_PLACEHOLDER = "<document-name>"


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _is_document_artifact(path: Path) -> bool:
    return path.suffix.lower() in _DOCUMENT_ARTIFACT_SUFFIXES


def _is_diagnostic_file(path: Path) -> bool:
    return path.suffix.lower() in _DIAGNOSTIC_FILE_SUFFIXES


def _sanitize_path(value: str, *, state_root: Path, runtime_root: Path) -> str:
    redacted = value
    normalized_value = value.replace("\\", "/")
    if normalized_value.startswith(("<state_root>/", "<runtime_root>/")):
        return _redact_document_artifact_path(normalized_value)
    for root, label in ((state_root, "<state_root>"), (runtime_root, "<runtime_root>")):
        redacted = redacted.replace(str(root), label)
    if redacted != value:
        return _redact_document_artifact_path(redacted)
    expanded = Path(value).expanduser()
    try:
        resolved = expanded.resolve()
    except OSError:
        resolved = expanded.absolute()
    for root, label in ((state_root, "<state_root>"), (runtime_root, "<runtime_root>")):
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        return _redact_document_artifact_path(str(Path(label) / relative))
    return _redact_document_artifact_path(Path(value).name) if Path(value).name else "<redacted-path>"


def _redact_document_artifact_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.suffix.lower() not in _DOCUMENT_ARTIFACT_SUFFIXES:
        return normalized
    parent = path.parent.as_posix()
    return _DOCUMENT_FILE_PLACEHOLDER if parent == "." else f"{parent}/{_DOCUMENT_FILE_PLACEHOLDER}"


def _redact_document_artifact_names(value: str) -> str:
    return _DOCUMENT_ARTIFACT_NAME_RE.sub(_DOCUMENT_FILE_PLACEHOLDER, value)


def _sanitize_text(value: str, *, state_root: Path, runtime_root: Path) -> str:
    redacted = value
    for root, label in ((state_root, "<state_root>"), (runtime_root, "<runtime_root>")):
        redacted = redacted.replace(str(root), label)
    return _redact_document_artifact_names(redacted)


def _sanitize_value(value: Any, *, state_root: Path, runtime_root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                _DOCUMENT_NAME_PLACEHOLDER
                if key == "file_name" and isinstance(item, str) and Path(item).suffix.lower() in _DOCUMENT_ARTIFACT_SUFFIXES
                else _sanitize_value(item, state_root=state_root, runtime_root=runtime_root)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item, state_root=state_root, runtime_root=runtime_root) for item in value]
    if isinstance(value, str):
        if "/" in value or "\\" in value:
            return _sanitize_path(value, state_root=state_root, runtime_root=runtime_root)
        return _redact_document_artifact_names(value)
    return value


def _read_sanitized_diagnostic_bytes(path: Path, *, state_root: Path, runtime_root: Path) -> bytes:
    text = path.read_text(encoding="utf-8", errors="replace")
    return _sanitize_text(text, state_root=state_root, runtime_root=runtime_root).encode("utf-8")


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _safe_arcname(prefix: str, path: Path, root: Path) -> str:
    return (Path(prefix) / path.relative_to(root)).as_posix()


def create_feedback_archive(
    output_path: str,
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
) -> dict:
    with root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
        storage_snapshot = storage.inspect_storage(resolved_state_root, include_integrity_check=False)
        doctor_report = build_doctor_report(
            state_root=str(resolved_state_root),
            runtime_root=str(resolved_runtime_root),
        )
        jobs = storage.list_jobs(include_result=True, state_root=resolved_state_root)
        uploads = storage.list_uploads(state_root=resolved_state_root)

    archive_path = Path(output_path).expanduser().resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()

    sanitized_jobs = _sanitize_value(jobs, state_root=resolved_state_root, runtime_root=resolved_runtime_root)
    sanitized_uploads = _sanitize_value(uploads, state_root=resolved_state_root, runtime_root=resolved_runtime_root)
    sanitized_storage = _sanitize_value(storage_snapshot, state_root=resolved_state_root, runtime_root=resolved_runtime_root)
    sanitized_doctor = _sanitize_value(doctor_report, state_root=resolved_state_root, runtime_root=resolved_runtime_root)

    included_files: list[tuple[Path, str]] = []
    excluded_document_artifact_count = 0
    file_inventory: list[dict[str, Any]] = []
    for root, label, archive_prefix in (
        (resolved_state_root, "<state_root>", "logs/state_root"),
        (resolved_runtime_root, "<runtime_root>", "logs/runtime_root"),
    ):
        for path in _iter_files(root):
            relative = path.relative_to(root).as_posix()
            entry = {
                "root": label,
                "path": str(Path(label) / relative),
                "size_bytes": path.stat().st_size,
                "included": False,
                "reason": "not_diagnostic_text",
            }
            if _is_document_artifact(path):
                excluded_document_artifact_count += 1
                entry["reason"] = "document_artifact_excluded"
            elif _is_diagnostic_file(path):
                entry["included"] = True
                entry["reason"] = "diagnostic_text"
                included_files.append((path, _safe_arcname(archive_prefix, path, root)))
            file_inventory.append(entry)
    sanitized_file_inventory = _sanitize_value(
        file_inventory,
        state_root=resolved_state_root,
        runtime_root=resolved_runtime_root,
    )

    manifest = {
        "kind": "article-local-feedback",
        "created_at": utcnow(),
        "service": app_module.SERVICE_NAME,
        "version": app_module.SERVICE_VERSION,
        "api_version": app_module.API_VERSION,
        "roots": {
            "state_root": "<state_root>",
            "runtime_root": "<runtime_root>",
            "shared_root": resolved_state_root == resolved_runtime_root,
        },
        "privacy": {
            "includes_document_artifacts": False,
            "excluded_suffixes": sorted(_DOCUMENT_ARTIFACT_SUFFIXES),
            "path_redaction": "state_root and runtime_root are replaced with placeholders; document filenames are redacted",
        },
        "counts": {
            "jobs": len(jobs),
            "uploads": len(uploads),
            "included_files": len(included_files),
            "excluded_document_artifacts": excluded_document_artifact_count,
        },
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", _json_bytes(manifest))
        zf.writestr("doctor.json", _json_bytes(sanitized_doctor))
        zf.writestr("jobs.json", _json_bytes(sanitized_jobs))
        zf.writestr("uploads.json", _json_bytes(sanitized_uploads))
        zf.writestr("storage.json", _json_bytes(sanitized_storage))
        zf.writestr("runtime_files.json", _json_bytes(sanitized_file_inventory))
        for file_path, arcname in included_files:
            zf.writestr(
                arcname,
                _read_sanitized_diagnostic_bytes(
                    file_path,
                    state_root=resolved_state_root,
                    runtime_root=resolved_runtime_root,
                ),
            )

    return {
        "status": "ok",
        "archive_path": str(archive_path),
        "created_at": manifest["created_at"],
        "state_root": str(resolved_state_root),
        "runtime_root": str(resolved_runtime_root),
        "included_file_count": len(included_files),
        "excluded_document_artifact_count": excluded_document_artifact_count,
        "size_bytes": archive_path.stat().st_size,
    }
