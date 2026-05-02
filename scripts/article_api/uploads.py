from __future__ import annotations

import base64
import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

import audit_thesis


RUNTIME_DIR_NAME = ".article_runtime"
RUNTIME_ROOT_ENV_VAR = "ARTICLE_API_RUNTIME_ROOT"
UPLOADED_DOCX_NAME_RE = re.compile(r"^(?P<upload_id>[0-9a-f]{32})_(?P<file_name>.+\.docx)$", re.IGNORECASE)


@dataclass(frozen=True)
class StagedDocument:
    source_path: str
    staged_path: str
    workspace_dir: str
    file_name: str


@dataclass(frozen=True)
class UploadedDocument:
    upload_id: str
    stored_path: str
    file_name: str
    workspace_dir: str
    size_bytes: int


def resolve_runtime_root(runtime_root: str | Path | None = None) -> Path:
    if runtime_root is not None:
        root = Path(runtime_root).expanduser().resolve()
    else:
        env_root = os.environ.get(RUNTIME_ROOT_ENV_VAR)
        root = Path(env_root).expanduser().resolve() if env_root else Path(__file__).resolve().parents[2] / RUNTIME_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_job_workspace(job_id: str, *, runtime_root: str | Path | None = None) -> dict[str, str]:
    root = resolve_runtime_root(runtime_root)
    job_root = root / "jobs" / job_id
    inputs_dir = job_root / "inputs"
    outputs_dir = job_root / "outputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return {
        "root": str(job_root),
        "inputs": str(inputs_dir),
        "outputs": str(outputs_dir),
    }


def stage_local_docx(file_path: str, *, runtime_root: str | Path | None = None) -> StagedDocument:
    source_path = Path(audit_thesis.validate_docx_path(file_path))
    root = resolve_runtime_root(runtime_root)
    staging_dir = root / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_name = f"{uuid4().hex}_{source_path.name}"
    staged_path = staging_dir / staged_name
    shutil.copy2(source_path, staged_path)
    return StagedDocument(
        source_path=str(source_path),
        staged_path=str(staged_path),
        workspace_dir=str(staging_dir),
        file_name=source_path.name,
    )


def stage_job_input_docx(
    file_path: str,
    *,
    job_id: str,
    runtime_root: str | Path | None = None,
) -> StagedDocument:
    source_path = Path(audit_thesis.validate_docx_path(file_path))
    workspace = build_job_workspace(job_id, runtime_root=runtime_root)
    inputs_dir = Path(workspace["inputs"])
    staged_path = inputs_dir / source_path.name
    shutil.copy2(source_path, staged_path)
    return StagedDocument(
        source_path=str(source_path),
        staged_path=str(staged_path),
        workspace_dir=str(inputs_dir),
        file_name=source_path.name,
    )


def _safe_upload_name(file_name: str) -> str:
    raw_name = str(file_name or "upload.docx").replace("\\", "/")
    cleaned = Path(raw_name).name
    cleaned = re.sub(r"[\x00-\x1f:]+", "_", cleaned).strip(" ._")
    if not cleaned.lower().endswith(".docx"):
        raise ValueError("Only .docx uploads are supported")
    return cleaned or "upload.docx"


def _read_upload_bytes(upload: Any) -> tuple[str, bytes]:
    file_name = _safe_upload_name(getattr(upload, "filename", "upload.docx"))
    if hasattr(upload, "file"):
        file_obj = upload.file
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        payload = file_obj.read()
    elif hasattr(upload, "read"):
        payload = upload.read()
    elif isinstance(upload, (bytes, bytearray)):
        payload = bytes(upload)
    else:
        raise ValueError("Unsupported upload payload")
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("Upload payload must resolve to bytes")
    return file_name, bytes(payload)


def store_uploaded_docx(upload: Any, *, runtime_root: str | Path | None = None) -> UploadedDocument:
    file_name, payload = _read_upload_bytes(upload)
    if not payload:
        raise ValueError("Uploaded .docx file is empty")
    root = resolve_runtime_root(runtime_root)
    uploads_dir = root / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    upload_id = uuid4().hex
    stored_path = uploads_dir / f"{upload_id}_{file_name}"
    with stored_path.open("wb") as handle:
        shutil.copyfileobj(io.BytesIO(payload), handle)
    return UploadedDocument(
        upload_id=upload_id,
        stored_path=str(stored_path),
        file_name=file_name,
        workspace_dir=str(uploads_dir),
        size_bytes=len(payload),
    )


def infer_uploaded_docx_name(file_path: str | Path) -> str | None:
    path = Path(file_path).expanduser().resolve()
    if path.parent.name != "uploads":
        return None
    match = UPLOADED_DOCX_NAME_RE.match(path.name)
    if match is None:
        return None
    return _safe_upload_name(match.group("file_name"))


def build_download_payload(file_path: str, *, file_name: str | None = None) -> dict[str, str | int]:
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"下载产物不存在: {path}")
    return {
        "file_name": file_name or path.name,
        "path": str(path),
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": path.stat().st_size,
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }
