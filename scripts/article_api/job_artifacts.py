from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from article_api import storage


REPORT_ARTIFACT_ROLE = "report"
REPORT_FILE_NAME = "job_report.md"
REPORT_SCHEMA_VERSION = 2


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

    if operation == "render-verify":
        report_path = (result or {}).get("report_path")
        if status == "succeeded" and report_path:
            artifacts.append(
                {
                    "kind": "markdown",
                    "role": REPORT_ARTIFACT_ROLE,
                    "path": report_path,
                    "download_name": os.path.basename(report_path),
                    "workspace": os.path.dirname(report_path),
                    "written": True,
                    "exists_at_completion": os.path.exists(report_path),
                }
            )
        toc_finalization = (result or {}).get("toc_finalization") or {}
        output_path = toc_finalization.get("output_path")
        if status == "succeeded" and toc_finalization.get("available") and output_path:
            artifacts.append(
                {
                    "kind": "docx",
                    "role": "toc-output",
                    "path": output_path,
                    "download_name": os.path.basename(output_path),
                    "workspace": os.path.dirname(output_path),
                    "written": True,
                    "exists_at_completion": os.path.exists(output_path),
                }
            )
        return artifacts

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


def refresh_artifact_availability(artifacts: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if artifacts is None:
        return None
    refreshed: list[dict[str, Any]] = []
    for artifact in artifacts:
        item = dict(artifact)
        path_value = item.get("path")
        item["available"] = bool(path_value and os.path.exists(path_value) and not os.path.isdir(path_value))
        refreshed.append(item)
    return refreshed


def _report_path(job_id: str) -> Path:
    report_dir = storage.resolve_state_root() / "job_reports" / job_id
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir / REPORT_FILE_NAME


def _format_value(value: Any) -> str:
    if value in (None, ""):
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _artifact_path(artifacts: list[dict[str, Any]] | None, role: str) -> str:
    for artifact in artifacts or []:
        if artifact.get("role") == role:
            return str(artifact.get("source_path") or artifact.get("path") or "")
    return ""


def _summary_lines(summary: dict[str, Any] | None, error: dict[str, Any] | None) -> list[str]:
    summary = summary or {}
    lines = [
        f"- 业务结论: {_format_value(summary.get('business_status') or summary.get('readiness') or summary.get('error_code'))}",
        f"- 文档名称: {_format_value(summary.get('document_name'))}",
        f"- 处理范围: {_format_value(', '.join(summary.get('selected_scopes') or []) if summary.get('selected_scopes') else None)}",
    ]
    if summary.get("failed_rules") is not None:
        lines.append(f"- 未通过规则: {_format_value(summary.get('failed_rules'))}")
    if summary.get("post_verify_notice_count") is not None:
        lines.append(f"- 修复后提示: {_format_value(summary.get('post_verify_notice_count'))}")
    if summary.get("operation_count") is not None:
        lines.append(f"- 整理动作: {_format_value(summary.get('operation_count'))}")
    if summary.get("guard_blocked"):
        lines.append("- 修复保护: 已拦截写出")
    if error:
        lines.append(f"- 错误信息: {_format_value(error.get('user_message') or error.get('message'))}")
    return lines


def render_job_report(
    *,
    job_id: str,
    operation: str,
    status: str,
    created_at: str,
    started_at: str | None,
    finished_at: str | None,
    summary: dict[str, Any] | None,
    resolved_request: dict[str, Any] | None,
    runtime: dict[str, Any] | None,
    artifacts: list[dict[str, Any]] | None,
    error: dict[str, Any] | None,
) -> str:
    summary = summary or {}
    resolved_request = resolved_request or {}
    runtime = runtime or {}
    input_path = (
        _artifact_path(artifacts, "input")
        or summary.get("input_path")
        or runtime.get("source_file_path")
        or runtime.get("input_path")
        or resolved_request.get("source_file_path")
        or resolved_request.get("file_path")
        or summary.get("document_name")
    )
    output_path = (
        _artifact_path(artifacts, "output")
        or summary.get("output_path")
        or runtime.get("output_path")
        or resolved_request.get("output_path")
    )
    lines = [
        "# 任务审查报告",
        "",
        f"任务编号: {job_id}",
        f"任务类型: {operation}",
        f"当前状态: {status}",
        f"创建时间: {_format_value(created_at)}",
        f"开始时间: {_format_value(started_at)}",
        f"完成时间: {_format_value(finished_at)}",
        "",
        "## 对应文件",
        "",
        f"- 输入文件: {_format_value(input_path)}",
        f"- 输出文件: {_format_value(output_path)}",
        "",
        "## 任务结论",
        "",
        *_summary_lines(summary, error),
        "",
    ]
    return "\n".join(lines)


def ensure_report_artifact(
    artifacts: list[dict[str, Any]] | None,
    *,
    job_id: str,
    operation: str,
    status: str,
    created_at: str,
    started_at: str | None,
    finished_at: str | None,
    summary: dict[str, Any] | None,
    resolved_request: dict[str, Any] | None,
    runtime: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    if operation not in {"apply", "normalize"}:
        return artifacts

    current_artifacts = [dict(item) for item in artifacts or [] if item.get("role") != REPORT_ARTIFACT_ROLE]
    report_path = _report_path(job_id)
    report_path.write_text(
        render_job_report(
            job_id=job_id,
            operation=operation,
            status=status,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary,
            resolved_request=resolved_request,
            runtime=runtime,
            artifacts=current_artifacts,
            error=error,
        ),
        encoding="utf-8",
    )
    current_artifacts.append(
        {
            "kind": "markdown",
            "role": REPORT_ARTIFACT_ROLE,
            "report_version": REPORT_SCHEMA_VERSION,
            "path": str(report_path),
            "download_name": REPORT_FILE_NAME,
            "workspace": None,
            "written": True,
            "exists_at_completion": report_path.exists(),
        }
    )
    return refresh_artifact_availability(current_artifacts)


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
        if artifact.get("role") == REPORT_ARTIFACT_ROLE:
            continue
        add_candidate(artifact.get("path"), kind=f"artifact:{artifact.get('role') or 'unknown'}")
    return candidates, skipped_paths
