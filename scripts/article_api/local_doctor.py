from __future__ import annotations

from pathlib import Path

from . import app as app_module
from . import app_ops
from . import storage
from .local_env import command_with_roots, resolved_roots, root_env_scope, utcnow


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
    serve_cmd = command_with_roots("lnu-thesis-local serve", state_root=state_root, runtime_root=runtime_root)
    doctor_cmd = command_with_roots("lnu-thesis-local doctor", state_root=state_root, runtime_root=runtime_root)
    maintain_cmd = command_with_roots("lnu-thesis-local maintain", state_root=state_root, runtime_root=runtime_root)
    backup_cmd = command_with_roots("lnu-thesis-local backup ~/Desktop/article-backup.zip", state_root=state_root, runtime_root=runtime_root)
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
    with root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
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
        "service": app_ops.SERVICE_NAME,
        "stage": app_ops.SERVICE_STAGE,
        "version": app_ops.SERVICE_VERSION,
        "api_version": app_ops.API_VERSION,
        "observed_at": utcnow(),
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
            "doctor": command_with_roots("lnu-thesis-local doctor", state_root=resolved_state_root, runtime_root=resolved_runtime_root),
            "serve": command_with_roots("lnu-thesis-local serve", state_root=resolved_state_root, runtime_root=resolved_runtime_root),
            "maintain": command_with_roots("lnu-thesis-local maintain", state_root=resolved_state_root, runtime_root=resolved_runtime_root),
            "backup": command_with_roots(
                "lnu-thesis-local backup ~/Desktop/article-backup.zip",
                state_root=resolved_state_root,
                runtime_root=resolved_runtime_root,
            ),
            "restore": command_with_roots(
                "lnu-thesis-local restore ~/Desktop/article-backup.zip --force",
                state_root=resolved_state_root,
                runtime_root=resolved_runtime_root,
            ),
        },
    }
