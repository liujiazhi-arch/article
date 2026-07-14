from __future__ import annotations

from pathlib import Path
import re

import audit_thesis

from thesis_tool.capabilities import classify_rule_action, load_rule_capabilities
from thesis_tool.scopes import build_rule_scope_map, filter_scope_definitions, normalize_scope_names


def _filter_scopes(scopes: list[dict], requested_scope_ids: set[str] | None) -> list[dict]:
    if requested_scope_ids is None:
        return scopes
    return [scope for scope in scopes if scope["id"] in requested_scope_ids]


def _scope_status(scope_failed: list[dict]) -> str:
    if not scope_failed:
        return "clean"

    actions = {item["action"] for item in scope_failed}
    if actions <= {"autofix"}:
        return "autofix_ready"
    if actions <= {"manual_review"}:
        return "manual_review"
    if actions <= {"unsupported"}:
        return "unsupported"
    return "mixed"


def _build_scope_radar_summary(scopes: list[dict], *, unscoped_failed_count: int = 0) -> dict:
    status_counts: dict[str, int] = {}
    for scope in scopes:
        status = scope.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "scope_count": len(scopes),
        "failed_scope_count": sum(1 for scope in scopes if scope["failed_count"] > 0),
        "autofixable_scope_count": sum(1 for scope in scopes if scope["autofixable_count"] > 0),
        "manual_review_count": sum(scope["manual_review_count"] for scope in scopes),
        "unsupported_count": sum(scope["unsupported_count"] for scope in scopes),
        "manual_confirmation_count": sum(
            scope["manual_review_count"] + scope["unsupported_count"] for scope in scopes
        ),
        "unknown_count": sum(scope["unknown_count"] for scope in scopes) + unscoped_failed_count,
        "unscoped_count": unscoped_failed_count,
        "status_counts": status_counts,
    }


def classify_audit_result_action(result: dict) -> str:
    action = classify_rule_action(result["id"])
    issues = result.get("issues") or []

    # C01 can only be auto-fixed when bracket citations already exist and merely
    # need superscript normalization. Without bracket citations, the user must confirm them.
    if result["id"] == "C01" and any("全文未发现任何上标格式的方括号引用" in issue for issue in issues):
        return "manual_review"
    if result["id"] == "KW01":
        for issue in issues:
            match = re.search(r"关键词数量为\s*(\d+)", issue)
            if match and int(match.group(1)) < 3:
                return "manual_review"
    return action


def _group_scope_failures(results, rule_to_scope, capabilities):
    failed_results = [result for result in results if not result.get("passed")]
    failed_by_scope: dict[str, list[dict]] = {}
    unscoped_failed: list[dict] = []
    for result in failed_results:
        capability = capabilities.get(result["id"], {})
        enriched_result = {
            **result,
            "check_level": capability.get("check_level", "Unknown"),
            "autofix": capability.get("autofix", "?"),
            "action": classify_audit_result_action(result),
        }
        scope_id = rule_to_scope.get(result["id"])
        target = unscoped_failed if scope_id is None else failed_by_scope.setdefault(scope_id, [])
        target.append(enriched_result)
    return failed_results, failed_by_scope, unscoped_failed


def _build_scope_summary(definition, scope_failed):
    actions = ("autofix", "manual_review", "unsupported", "unknown")
    counts = {action: sum(item["action"] == action for item in scope_failed) for action in actions}
    return {
        "id": definition.id,
        "title": definition.title,
        "description": definition.description,
        "status": "not_checked" if not definition.rule_ids else _scope_status(scope_failed),
        "failed_count": len(scope_failed),
        "failed_rules": [item["id"] for item in scope_failed],
        "failed_items": scope_failed,
        "autofixable_count": counts["autofix"],
        "manual_review_count": counts["manual_review"],
        "unsupported_count": counts["unsupported"],
        "unknown_count": counts["unknown"],
    }


def _build_scope_summaries(scope_definitions, failed_by_scope):
    return [
        _build_scope_summary(definition, failed_by_scope.get(definition.id, []))
        for definition in scope_definitions
    ]


def _select_scopes(scope_summaries, requested_scope_ids, unscoped_failed_count):
    visible_scopes = sorted(
        _filter_scopes(scope_summaries, requested_scope_ids),
        key=lambda item: (item["failed_count"] == 0, item["title"]),
    )
    failed_count = sum(scope["failed_count"] for scope in visible_scopes)
    if requested_scope_ids is None:
        failed_count += unscoped_failed_count
    return visible_scopes, failed_count


def _build_plan_payload(
    *, file_path, profile_path, failed_results, score, report, runtime,
    visible_scopes, selected_failed_count, requested_scope_ids, unscoped_failed,
):
    return {
        "file_path": str(Path(file_path)),
        "profile_path": profile_path,
        "profile_id": runtime.profile_id,
        "requested_profile": runtime.requested_profile,
        "fallback_used": runtime.fallback_used,
        "profile_display": audit_thesis.format_profile_resolution(
            runtime.profile_id,
            runtime.requested_profile,
            runtime.fallback_used,
        ),
        "score": score,
        "failed_count": selected_failed_count,
        "total_failed_count": len(failed_results),
        "scopes": visible_scopes,
        "scope_radar_summary": _build_scope_radar_summary(
            visible_scopes,
            unscoped_failed_count=len(unscoped_failed) if requested_scope_ids is None else 0,
        ),
        "selected_scopes": sorted(requested_scope_ids) if requested_scope_ids else None,
        "unscoped_failed": unscoped_failed if requested_scope_ids is None else [],
        "report": report,
    }


def build_scope_plan_from_audit(
    file_path: str,
    *,
    results: list[dict],
    score: int,
    report: str,
    runtime: audit_thesis.AuditRuntime,
    profile_path: str | None = None,
    scopes=None,
) -> dict:
    requested_scope_ids = normalize_scope_names(scopes)
    runtime_rule_ids = {rule_id for rule_id, _, _ in runtime.rule_definitions}
    scope_definitions = filter_scope_definitions(runtime_rule_ids)
    failed_results, failed_by_scope, unscoped_failed = _group_scope_failures(
        results,
        build_rule_scope_map(scope_definitions),
        load_rule_capabilities(),
    )
    scope_summaries = _build_scope_summaries(scope_definitions, failed_by_scope)
    visible_scopes, selected_failed_count = _select_scopes(
        scope_summaries,
        requested_scope_ids,
        len(unscoped_failed),
    )
    return _build_plan_payload(
        file_path=file_path,
        profile_path=profile_path,
        failed_results=failed_results,
        score=score,
        report=report,
        runtime=runtime,
        visible_scopes=visible_scopes,
        selected_failed_count=selected_failed_count,
        requested_scope_ids=requested_scope_ids,
        unscoped_failed=unscoped_failed,
    )


def build_scope_plan(
    file_path: str,
    profile_path: str | None = None,
    scopes=None,
    strict_profile: bool | None = None,
) -> dict:
    requested_scope_ids = normalize_scope_names(scopes)
    results, score, report, runtime = audit_thesis.audit_docx_with_runtime(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    return build_scope_plan_from_audit(
        file_path,
        results=results,
        score=score,
        report=report,
        runtime=runtime,
        profile_path=profile_path,
        scopes=requested_scope_ids,
    )
