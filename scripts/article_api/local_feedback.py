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
MAX_DIAGNOSTIC_FILE_BYTES = 8 * 1024 * 1024
_DOCUMENT_ARTIFACT_NAME_RE = re.compile(
    r"(^|[/\\\r\n\"'])([^/\\\r\n\"']+\.(?:docx|doc|pdf|png|jpeg|jpg|webp))",
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
    return _DOCUMENT_ARTIFACT_NAME_RE.sub(
        lambda match: f"{match.group(1)}{_DOCUMENT_FILE_PLACEHOLDER}",
        value,
    )


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
            value = _sanitize_path(value, state_root=state_root, runtime_root=runtime_root)
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


def _feedback_snapshot(state_root: str | None, runtime_root: str | None) -> tuple[Path, Path, dict[str, Any]]:
    with root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
        snapshot = {
            "storage": storage.inspect_storage(resolved_state_root, include_integrity_check=False),
            "doctor": build_doctor_report(
                state_root=str(resolved_state_root),
                runtime_root=str(resolved_runtime_root),
            ),
            "jobs": storage.list_jobs(include_result=True, state_root=resolved_state_root),
            "uploads": storage.list_uploads(state_root=resolved_state_root),
        }
    return resolved_state_root, resolved_runtime_root, snapshot


def _inspect_feedback_file(
    path: Path,
    *,
    root: Path,
    label: str,
    archive_prefix: str,
) -> tuple[dict[str, Any], tuple[Path, str] | None, bool] | None:
    try:
        size_bytes = path.stat().st_size
    except FileNotFoundError:
        return None
    is_document = _is_document_artifact(path)
    has_diagnostic_suffix = _is_diagnostic_file(path)
    is_too_large = has_diagnostic_suffix and size_bytes > MAX_DIAGNOSTIC_FILE_BYTES
    is_diagnostic = not is_document and has_diagnostic_suffix and not is_too_large
    if is_document:
        reason = "document_artifact_excluded"
    elif is_too_large:
        reason = "diagnostic_text_too_large"
    else:
        reason = "diagnostic_text" if is_diagnostic else "not_diagnostic_text"
    entry = {
        "root": label,
        "path": str(Path(label) / path.relative_to(root)),
        "size_bytes": size_bytes,
        "included": is_diagnostic,
        "reason": reason,
    }
    included_file = (path, _safe_arcname(archive_prefix, path, root)) if is_diagnostic else None
    return entry, included_file, is_document


def _collect_feedback_files(
    state_root: Path,
    runtime_root: Path,
) -> tuple[list[tuple[Path, str]], list[tuple[dict[str, Any], Path | None]], int]:
    included_files: list[tuple[Path, str]] = []
    inventory: list[tuple[dict[str, Any], Path | None]] = []
    excluded_count = 0
    for root, label, archive_prefix in (
        (state_root, "<state_root>", "logs/state_root"),
        (runtime_root, "<runtime_root>", "logs/runtime_root"),
    ):
        for path in _iter_files(root):
            inspected = _inspect_feedback_file(path, root=root, label=label, archive_prefix=archive_prefix)
            if inspected is None:
                continue
            entry, included_file, is_document = inspected
            inventory.append((entry, path if included_file else None))
            if included_file:
                included_files.append(included_file)
            excluded_count += int(is_document)
    return included_files, inventory, excluded_count


def _write_diagnostic_files(
    zf: zipfile.ZipFile,
    included_files: list[tuple[Path, str]],
    *,
    state_root: Path,
    runtime_root: Path,
) -> set[Path]:
    written_paths: set[Path] = set()
    for file_path, arcname in included_files:
        try:
            content = _read_sanitized_diagnostic_bytes(
                file_path,
                state_root=state_root,
                runtime_root=runtime_root,
            )
        except FileNotFoundError:
            continue
        zf.writestr(arcname, content)
        written_paths.add(file_path)
    return written_paths


def _feedback_manifest(
    snapshot: dict[str, Any],
    *,
    state_root: Path,
    runtime_root: Path,
    included_count: int,
    excluded_count: int,
) -> dict[str, Any]:
    return {
        "kind": "article-local-feedback",
        "created_at": utcnow(),
        "service": app_module.SERVICE_NAME,
        "version": app_module.SERVICE_VERSION,
        "api_version": app_module.API_VERSION,
        "roots": {
            "state_root": "<state_root>",
            "runtime_root": "<runtime_root>",
            "shared_root": state_root == runtime_root,
        },
        "privacy": {
            "includes_document_artifacts": False,
            "excluded_suffixes": sorted(_DOCUMENT_ARTIFACT_SUFFIXES),
            "path_redaction": "state_root and runtime_root are replaced with placeholders; document filenames are redacted",
        },
        "counts": {
            "jobs": len(snapshot["jobs"]),
            "uploads": len(snapshot["uploads"]),
            "included_files": included_count,
            "excluded_document_artifacts": excluded_count,
        },
    }


def _write_feedback_metadata(
    zf: zipfile.ZipFile,
    snapshot: dict[str, Any],
    inventory: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    state_root: Path,
    runtime_root: Path,
) -> None:
    payloads = {
        "doctor.json": snapshot["doctor"],
        "jobs.json": snapshot["jobs"],
        "uploads.json": snapshot["uploads"],
        "storage.json": snapshot["storage"],
        "runtime_files.json": inventory,
    }
    zf.writestr("manifest.json", _json_bytes(manifest))
    for filename, payload in payloads.items():
        sanitized = _sanitize_value(payload, state_root=state_root, runtime_root=runtime_root)
        zf.writestr(filename, _json_bytes(sanitized))


def _build_feedback_archive(
    archive_path: Path,
    snapshot: dict[str, Any],
    *,
    state_root: Path,
    runtime_root: Path,
) -> tuple[dict[str, Any], int, int]:
    included_files, inventory, excluded_count = _collect_feedback_files(state_root, runtime_root)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        written_paths = _write_diagnostic_files(
            zf,
            included_files,
            state_root=state_root,
            runtime_root=runtime_root,
        )
        final_inventory = [entry for entry, diagnostic_path in inventory if diagnostic_path is None or diagnostic_path in written_paths]
        manifest = _feedback_manifest(
            snapshot,
            state_root=state_root,
            runtime_root=runtime_root,
            included_count=len(written_paths),
            excluded_count=excluded_count,
        )
        _write_feedback_metadata(
            zf,
            snapshot,
            final_inventory,
            manifest,
            state_root=state_root,
            runtime_root=runtime_root,
        )
    return manifest, len(written_paths), excluded_count


def create_feedback_archive(
    output_path: str,
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
) -> dict:
    resolved_state_root, resolved_runtime_root, snapshot = _feedback_snapshot(state_root, runtime_root)

    archive_path = Path(output_path).expanduser().resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()
    manifest, included_count, excluded_count = _build_feedback_archive(
        archive_path,
        snapshot,
        state_root=resolved_state_root,
        runtime_root=resolved_runtime_root,
    )

    return {
        "status": "ok",
        "archive_path": str(archive_path),
        "created_at": manifest["created_at"],
        "state_root": str(resolved_state_root),
        "runtime_root": str(resolved_runtime_root),
        "included_file_count": included_count,
        "excluded_document_artifact_count": excluded_count,
        "size_bytes": archive_path.stat().st_size,
    }
