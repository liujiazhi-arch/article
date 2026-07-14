from __future__ import annotations


READINESS_STRUCTURE_READY = "structure-ready"
READINESS_RENDER_CHECK_REQUIRED = "render-check-required"
READINESS_MANUAL_REVIEW_REQUIRED = "manual-review-required"
READINESS_UNSUPPORTED = "unsupported"
READINESS_NEEDS_FIX = "needs-fix"


def classify_scope_readiness(*, autofixable: int, manual_review: int, unsupported: int) -> str:
    if unsupported > 0:
        return READINESS_UNSUPPORTED
    if manual_review > 0:
        return READINESS_MANUAL_REVIEW_REQUIRED
    if autofixable > 0:
        return READINESS_NEEDS_FIX
    return READINESS_STRUCTURE_READY


def classify_overall_status(*, autofixable: int, manual_review: int, unsupported: int, has_failures: bool) -> str:
    if not has_failures:
        return "verified"
    if autofixable > 0:
        return "needs_fix"
    if manual_review > 0 and unsupported == 0:
        return "manual_review"
    if unsupported > 0 and manual_review == 0:
        return "unsupported"
    return "mixed"


def _selected_scope_ids(plan: dict) -> set[str]:
    return set(plan["selected_scopes"] or [scope["id"] for scope in plan["scopes"]])


def _collect_render_check_rules(plan: dict, diagnostics: dict) -> list[dict]:
    if "toc" not in _selected_scope_ids(plan):
        return []
    if str((diagnostics.get("toc") or {}).get("status") or "") != "field_only":
        return []

    toc_scope = next((scope for scope in plan["scopes"] if scope["id"] == "toc"), None)
    return [
        {
            "id": "TOC_REFRESH_REQUIRED",
            "name": "目录只有域指令，缺少脚本预填的可见目录结果",
            "check_level": "Rendered",
            "scope_id": "toc",
            "scope_title": toc_scope["title"] if toc_scope is not None else "目录",
            "action": "render_check",
        }
    ]


def _verification_rule_summary(scope: dict, item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "check_level": item.get("check_level", "Unknown"),
        "scope_id": scope["id"],
        "scope_title": scope["title"],
        "action": item.get("action", "unknown"),
    }


def _collect_verification_rules(selected_scopes: list[dict]) -> tuple[list[dict], list[dict]]:
    summaries = [
        _verification_rule_summary(scope, item)
        for scope in selected_scopes
        for item in scope.get("failed_items", [])
        if item.get("action") in {"manual_review", "unsupported"}
    ]
    manual_review_rules = sorted(
        (item for item in summaries if item["action"] == "manual_review"),
        key=lambda item: item["id"],
    )
    unsupported_rules = sorted(
        (item for item in summaries if item["action"] == "unsupported"),
        key=lambda item: item["id"],
    )
    return manual_review_rules, unsupported_rules


def _build_scope_verify_payload(
    plan: dict,
    *,
    counts: dict[str, int],
    readiness: str,
    overall_status: str,
    manual_review_rules: list[dict],
    unsupported_rules: list[dict],
    render_check_rules: list[dict],
) -> dict:
    return {
        "file_path": plan["file_path"],
        "profile_path": plan["profile_path"],
        "profile_id": plan.get("profile_id"),
        "requested_profile": plan.get("requested_profile"),
        "fallback_used": bool(plan.get("fallback_used")),
        "profile_display": plan.get("profile_display"),
        "score": plan["score"],
        "failed_count": plan["failed_count"],
        "selected_scopes": plan["selected_scopes"],
        "scopes": plan["scopes"],
        "readiness": readiness,
        "overall_status": overall_status,
        "manual_review_count": counts["manual_review"],
        "unsupported_count": counts["unsupported"],
        "autofixable_count": counts["autofixable"],
        "manual_review_rules": manual_review_rules,
        "unsupported_rules": unsupported_rules,
        "manual_review_rule_ids": [item["id"] for item in manual_review_rules],
        "unsupported_rule_ids": [item["id"] for item in unsupported_rules],
        "render_check_count": len(render_check_rules),
        "render_check_rules": render_check_rules,
        "render_check_rule_ids": [item["id"] for item in render_check_rules],
    }


def _scope_verify_statuses(
    counts: dict[str, int],
    *,
    has_failures: bool,
    has_render_checks: bool,
) -> tuple[str, str]:
    readiness = classify_scope_readiness(
        autofixable=counts["autofixable"],
        manual_review=counts["manual_review"],
        unsupported=counts["unsupported"],
    )
    if readiness == READINESS_STRUCTURE_READY and has_render_checks:
        readiness = READINESS_RENDER_CHECK_REQUIRED
    overall_status = classify_overall_status(
        autofixable=counts["autofixable"],
        manual_review=counts["manual_review"],
        unsupported=counts["unsupported"],
        has_failures=has_failures,
    )
    return readiness, overall_status


def build_scope_verify_from_plan(plan: dict, *, diagnostics: dict) -> dict:
    selected_scopes = [scope for scope in plan["scopes"] if scope["failed_count"] > 0]
    counts = {
        "manual_review": sum(scope["manual_review_count"] for scope in selected_scopes),
        "unsupported": sum(scope["unsupported_count"] for scope in selected_scopes),
        "autofixable": sum(scope["autofixable_count"] for scope in selected_scopes),
    }
    manual_review_rules, unsupported_rules = _collect_verification_rules(selected_scopes)
    render_check_rules = _collect_render_check_rules(plan, diagnostics)
    readiness, overall_status = _scope_verify_statuses(
        counts,
        has_failures=bool(selected_scopes),
        has_render_checks=bool(render_check_rules),
    )
    return _build_scope_verify_payload(
        plan,
        counts=counts,
        readiness=readiness,
        overall_status=overall_status,
        manual_review_rules=manual_review_rules,
        unsupported_rules=unsupported_rules,
        render_check_rules=render_check_rules,
    )
