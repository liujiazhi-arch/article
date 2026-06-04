from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any


def build_artifacts(
    operation: str,
    resolved_request: dict[str, Any],
    workspace: dict[str, str] | None,
    *,
    result: dict[str, Any] | None,
    status: str,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    input_source_path = resolved_request.get("source_file_path")
    if input_source_path and workspace is not None:
        artifacts.append(
            {
                "kind": "docx",
                "role": "input",
                "path": resolved_request["file_path"],
                "source_path": input_source_path,
                "download_name": resolved_request.get("source_display_name") or os.path.basename(input_source_path),
                "workspace": workspace["inputs"],
                "staged": True,
                "exists_at_completion": os.path.exists(resolved_request["file_path"]),
            }
        )

    if operation not in {"apply", "normalize"}:
        return artifacts

    output_path = resolved_request.get("output_path")
    if not output_path:
        return artifacts

    mode = result.get("mode") if result else ("normalize" if operation == "normalize" else None)
    wrote_file = bool(status == "succeeded" and mode != "preview")
    artifacts.append(
        {
            "kind": "docx",
            "role": "output",
            "path": output_path,
            "download_name": os.path.basename(output_path),
            "workspace": workspace["outputs"] if workspace is not None else None,
            "result_mode": mode or "failed",
            "written": wrote_file,
            "exists_at_completion": os.path.exists(output_path),
        }
    )
    return artifacts


def finalize_runtime_metadata(runtime: dict[str, Any]) -> dict[str, Any]:
    finalized = dict(runtime)
    workspace_root = finalized.get("workspace_root")
    staged_input_path = finalized.get("staged_input_path")
    output_path = finalized.get("output_path")
    finalized["workspace_exists_at_completion"] = bool(workspace_root and os.path.exists(workspace_root))
    finalized["staged_input_exists_at_completion"] = bool(staged_input_path and os.path.exists(staged_input_path))
    finalized["output_exists_at_completion"] = bool(output_path and os.path.exists(output_path))
    heartbeat_at = finalized.get("last_heartbeat_at")
    if heartbeat_at:
        try:
            heartbeat_dt = datetime.fromisoformat(str(heartbeat_at).replace("Z", "+00:00"))
            finalized["heartbeat_age_seconds"] = max((datetime.now(timezone.utc) - heartbeat_dt).total_seconds(), 0.0)
        except ValueError:
            finalized["heartbeat_age_seconds"] = None
    else:
        finalized["heartbeat_age_seconds"] = None
    return finalized


def resolved_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    return Path(path_value).expanduser().resolve()


def is_within(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def cleanup_candidate_map(payload: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    runtime = payload.get("runtime") or {}
    runtime_root = resolved_path(runtime.get("runtime_root"))
    workspace_root = resolved_path(runtime.get("workspace_root"))
    candidates: dict[str, dict[str, str]] = {}
    skipped_paths: list[str] = []

    def add_candidate(path_value: str | None, *, kind: str) -> None:
        candidate_path = resolved_path(path_value)
        if candidate_path is None:
            return
        candidate_key = str(candidate_path)
        if workspace_root is not None and candidate_path != workspace_root and is_within(candidate_path, workspace_root):
            return
        if workspace_root is not None and candidate_path == workspace_root:
            candidates[candidate_key] = {"path": candidate_key, "kind": kind}
            return
        if is_within(candidate_path, runtime_root):
            candidates.setdefault(candidate_key, {"path": candidate_key, "kind": kind})
            return
        skipped_paths.append(candidate_key)

    add_candidate(runtime.get("workspace_root"), kind="workspace")
    # Upload lifecycle is managed by the upload registry/cleanup endpoints.
    # Job cleanup only removes per-job runtime data and materialized artifacts.
    for artifact in payload.get("artifacts") or []:
        add_candidate(artifact.get("path"), kind=f"artifact:{artifact.get('role') or 'unknown'}")
    return candidates, skipped_paths
