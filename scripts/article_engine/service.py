from __future__ import annotations

from pathlib import Path
from typing import Any

import audit_thesis
import fix_thesis
from thesis_tool.apply_guard import assess_apply_risk, render_post_verify_notice as _render_post_verify_notice
from thesis_tool.capabilities import load_rule_capabilities
from thesis_tool.render_verify import build_render_verify_report
from thesis_tool.scopes import normalize_scope_names
from thesis_tool.workflow import (
    apply_scoped_fix,
    build_document_diagnostics,
    build_document_normalize,
    build_document_preflight,
    build_scope_plan,
    build_scope_verify,
    build_scoped_fix_preview,
    classify_apply_readiness,
    classify_audit_result_action,
)


class ApplyGuardBlockedError(RuntimeError):
    def __init__(self, message: str, *, guard: dict[str, Any]):
        super().__init__(message)
        self.guard = guard


def _serialize_result(result: dict[str, Any]) -> dict[str, Any]:
    capability = load_rule_capabilities().get(result["id"], {})
    return {
        "id": result["id"],
        "name": result["name"],
        "severity": result.get("severity"),
        "passed": bool(result.get("passed")),
        "issues": list(result.get("issues") or []),
        "affected": list(result.get("affected") or []),
        "check_level": capability.get("check_level", "Unknown"),
        "autofix": capability.get("autofix", "?"),
        "action": classify_audit_result_action(result),
    }


def _serialize_scope(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scope["id"],
        "title": scope["title"],
        "description": scope["description"],
        "status": scope["status"],
        "failed_count": scope["failed_count"],
        "failed_rules": list(scope["failed_rules"]),
        "autofixable_count": scope["autofixable_count"],
        "manual_review_count": scope["manual_review_count"],
        "unsupported_count": scope["unsupported_count"],
        "unknown_count": scope["unknown_count"],
    }


def _profile_payload(*, profile_id: str, requested_profile: str | None, fallback_used: bool) -> dict[str, Any]:
    return {
        "id": profile_id,
        "requested": requested_profile,
        "fallback_used": fallback_used,
        "display": audit_thesis.format_profile_resolution(profile_id, requested_profile, fallback_used),
    }


def _serialize_rule_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["name"],
        "check_level": item.get("check_level", "Unknown"),
        "scope_id": item.get("scope_id"),
        "scope_title": item.get("scope_title"),
        "action": item.get("action", "unknown"),
    }


def _serialize_verification(verification: dict[str, Any], *, requested_profile: str | None) -> dict[str, Any]:
    return {
        "document": {
            "path": verification["file_path"],
            "name": Path(verification["file_path"]).name,
        },
        "profile": {
            "id": verification.get("profile_id"),
            "requested": verification.get("requested_profile", requested_profile),
            "fallback_used": bool(verification.get("fallback_used")),
            "display": verification.get("profile_display"),
        },
        "score": verification["score"],
        "summary": {
            "failed_rules": verification["failed_count"],
            "autofixable_rules": verification["autofixable_count"],
            "manual_review_rules": verification["manual_review_count"],
            "unsupported_rules": verification["unsupported_count"],
            "render_check_rules": verification.get("render_check_count", 0),
            "readiness": verification["readiness"],
        },
        "readiness": verification["readiness"],
        "overall_status": verification["overall_status"],
        "selected_scopes": verification["selected_scopes"],
        "scopes": [_serialize_scope(scope) for scope in verification["scopes"]],
        "manual_review_rules": [_serialize_rule_summary(item) for item in verification["manual_review_rules"]],
        "unsupported_rules": [_serialize_rule_summary(item) for item in verification["unsupported_rules"]],
        "render_check_rules": [_serialize_rule_summary(item) for item in verification.get("render_check_rules", [])],
        "manual_review_rule_ids": list(verification["manual_review_rule_ids"]),
        "unsupported_rule_ids": list(verification["unsupported_rule_ids"]),
        "render_check_rule_ids": list(verification.get("render_check_rule_ids") or []),
    }


def _serialize_preflight(preflight: dict[str, Any], *, requested_profile: str | None) -> dict[str, Any]:
    diagnostics = preflight.get("diagnostics") or {}
    return {
        "document": {
            "path": preflight["file_path"],
            "name": Path(preflight["file_path"]).name,
        },
        "profile": {
            "id": preflight.get("profile_id"),
            "requested": preflight.get("requested_profile", requested_profile),
            "fallback_used": bool(preflight.get("fallback_used")),
            "display": preflight.get("profile_display"),
        },
        "summary": {
            "headline": preflight["headline"],
            "preflight_status": preflight["preflight_status"],
            "toc_status": preflight.get("toc_status"),
            "preface_status": preflight.get("preface_status"),
            "table_heading_risk_count": preflight.get("table_heading_risk_count", 0),
            "style_conflict_count": preflight.get("style_conflict_count", 0),
            "recommended_action_count": len(preflight.get("recommended_actions") or []),
        },
        "preflight_status": preflight["preflight_status"],
        "heading_renumber_guard": dict(preflight.get("heading_renumber_guard") or {}),
        "recommended_actions": list(preflight.get("recommended_actions") or []),
        "diagnostics": {
            "toc": dict(diagnostics.get("toc") or {}),
            "headings": list(diagnostics.get("headings") or []),
            "table_heading_candidates": list(diagnostics.get("table_heading_candidates") or []),
            "table_heading_candidate_summary": dict(diagnostics.get("table_heading_candidate_summary") or {}),
            "style_text_conflicts": list(diagnostics.get("style_text_conflicts") or []),
        },
    }


def _serialize_normalize(normalize: dict[str, Any], *, requested_profile: str | None) -> dict[str, Any]:
    summary = dict(normalize.get("summary") or {})
    return {
        "document": {
            "path": normalize["file_path"],
            "name": Path(normalize["file_path"]).name,
        },
        "output": {
            "path": normalize["output_path"],
            "name": Path(normalize["output_path"]).name,
        },
        "profile": {
            "id": normalize.get("profile_id"),
            "requested": normalize.get("requested_profile", requested_profile),
            "fallback_used": bool(normalize.get("fallback_used")),
            "display": normalize.get("profile_display"),
        },
        "changed": bool(normalize.get("changed")),
        "operations": [dict(item) for item in normalize.get("operations") or []],
        "summary": summary,
        "before": {
            "preflight_status": normalize.get("before", {}).get("preflight_status"),
            "toc_status": normalize.get("before", {}).get("toc_status"),
            "style_conflict_count": normalize.get("before", {}).get("style_conflict_count", 0),
            "table_heading_risk_count": normalize.get("before", {}).get("table_heading_risk_count", 0),
        },
        "after": {
            "preflight_status": normalize.get("after", {}).get("preflight_status"),
            "toc_status": normalize.get("after", {}).get("toc_status"),
            "style_conflict_count": normalize.get("after", {}).get("style_conflict_count", 0),
            "table_heading_risk_count": normalize.get("after", {}).get("table_heading_risk_count", 0),
        },
        "next_steps": list(normalize.get("next_steps") or []),
    }


def _render_apply_risk_warning(
    diagnostics: dict[str, Any],
    *,
    renumber_headings: bool,
    selected_scopes: set[str] | None,
) -> tuple[list[str], bool]:
    assessment = assess_apply_risk(
        diagnostics,
        renumber_headings=renumber_headings,
        selected_scopes=selected_scopes,
    )
    lines: list[str] = []

    if assessment.has_table_heading_risk:
        lines.append(
            f"表格伪标题候选: {assessment.table_heading_risk_count} "
            f"个（阈值 {assessment.table_heading_risk_threshold}）"
        )
        lines.append("建议: 先运行 preflight 核对表格内容，避免化合物名或数值误入标题重编号链。")

    if assessment.has_style_text_conflict:
        lines.append(f"样式/文本层级冲突: {assessment.style_text_conflict_count} 个")
        if assessment.affects_heading_renumber:
            lines.append("建议: 先检查 headings 相关冲突，再执行标题重编号。")
        else:
            lines.append("建议: 可先运行 preflight 查看冲突详情，必要时再处理 headings scope。")

    return lines, assessment.should_block


def _serialize_apply_guard(
    diagnostics: dict[str, Any] | None,
    *,
    checked: bool,
    blocked: bool,
    force_used: bool,
    warning_lines: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "checked": checked,
        "blocked": blocked,
        "force_used": force_used,
        "warnings": list(warning_lines),
    }
    if diagnostics is None:
        payload["diagnostics"] = None
        return payload

    payload["diagnostics"] = {
        "heading_renumber_guard": dict(diagnostics["heading_renumber_guard"]),
        "table_heading_risk_count": len(diagnostics["table_heading_candidates"]),
        "style_conflict_count": len(diagnostics["style_text_conflicts"]),
        "recommended_actions": list(diagnostics.get("recommended_actions") or []),
    }
    return payload


def _blocked_apply_message(warning_lines: list[str]) -> str:
    lines = ["Apply blocked by structural risk."]
    lines.extend(warning_lines)
    lines.append("Pass force=True to bypass this guard.")
    return "\n".join(lines)


def _default_output_path(input_path: str, scopes) -> str:
    normalized_scopes = normalize_scope_names(scopes)
    if not normalized_scopes:
        return fix_thesis.default_output_path(input_path)

    source = Path(input_path)
    scope_suffix = "_".join(sorted(normalized_scopes))
    return str(source.with_name(f"{source.stem}_{scope_suffix}{source.suffix or '.docx'}"))


def audit_document(file_path: str, profile_path: str | None = None, strict_profile: bool | None = None) -> dict[str, Any]:
    results, score, report, runtime = audit_thesis.audit_docx_with_runtime(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    plan = build_scope_plan(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    serialized_results = [_serialize_result(result) for result in results]
    failed_results = [result for result in serialized_results if not result["passed"]]
    failed_scopes = [scope for scope in plan["scopes"] if scope["failed_count"] > 0]

    return {
        "document": {
            "path": str(Path(file_path)),
            "name": Path(file_path).name,
        },
        "profile": _profile_payload(
            profile_id=runtime.profile_id,
            requested_profile=runtime.requested_profile,
            fallback_used=runtime.fallback_used,
        ),
        "score": score,
        "report": report,
        "summary": {
            "total_rules": len(serialized_results),
            "passed_rules": len(serialized_results) - len(failed_results),
            "failed_rules": len(failed_results),
        },
        "results": serialized_results,
        "failed_results": failed_results,
        "scope_overview": [_serialize_scope(scope) for scope in plan["scopes"]],
        "recommended_scope_order": [scope["id"] for scope in failed_scopes],
    }


def plan_document(file_path: str, profile_path: str | None = None, scopes=None, strict_profile: bool | None = None) -> dict[str, Any]:
    plan = build_scope_plan(
        file_path,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
    )
    visible_scopes = [_serialize_scope(scope) for scope in plan["scopes"]]
    recommended_scope_order = [scope["id"] for scope in plan["scopes"] if scope["failed_count"] > 0]

    return {
        "document": {
            "path": plan["file_path"],
            "name": Path(plan["file_path"]).name,
        },
        "profile": {
            "id": plan.get("profile_id"),
            "requested": plan.get("requested_profile", profile_path),
            "fallback_used": bool(plan.get("fallback_used")),
            "display": plan.get("profile_display"),
        },
        "score": plan["score"],
        "summary": {
            "failed_rules": plan["failed_count"],
            "total_failed_rules": plan["total_failed_count"],
        },
        "selected_scopes": plan["selected_scopes"],
        "recommended_scope_order": recommended_scope_order,
        "scopes": visible_scopes,
        "unscoped_failed": [
            {
                "id": item["id"],
                "name": item["name"],
                "check_level": item.get("check_level", "Unknown"),
                "action": item.get("action", "unknown"),
            }
            for item in plan["unscoped_failed"]
        ],
    }


def render_verify_document(
    file_path: str,
    *,
    output_dir: str | None = None,
    profile_path: str | None = None,
    scopes=None,
    strict_profile: bool | None = None,
    renderer: str = "auto",
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
) -> dict[str, Any]:
    return build_render_verify_report(
        file_path,
        output_dir=output_dir,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )


def preflight_document(file_path: str, profile_path: str | None = None, strict_profile: bool | None = None) -> dict[str, Any]:
    preflight = build_document_preflight(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    return _serialize_preflight(preflight, requested_profile=profile_path)


def normalize_document(
    file_path: str,
    *,
    output_path: str | None = None,
    profile_path: str | None = None,
    strict_profile: bool | None = None,
) -> dict[str, Any]:
    normalize = build_document_normalize(
        file_path,
        output_path=output_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    return _serialize_normalize(normalize, requested_profile=profile_path)


def verify_document(file_path: str, profile_path: str | None = None, scopes=None, strict_profile: bool | None = None) -> dict[str, Any]:
    verification = build_scope_verify(
        file_path,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
    )
    return _serialize_verification(verification, requested_profile=profile_path)


def apply_fix(
    file_path: str,
    *,
    output_path: str | None = None,
    profile_path: str | None = None,
    scopes=None,
    toc: bool = False,
    renumber_headings: bool = False,
    layout_rebalance: bool = False,
    candidate_mode: str | None = None,
    strict_profile: bool | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    resolved_output_path = output_path or _default_output_path(file_path, scopes)
    Path(resolved_output_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    selected_scopes = normalize_scope_names(scopes)
    effective_candidate_mode = candidate_mode
    degraded_from_compact = False
    degrade_reason: str | None = None

    if candidate_mode == "compact_candidate":
        preview = build_scoped_fix_preview(
            file_path,
            output_path=resolved_output_path,
            profile_path=profile_path,
            scopes=scopes,
            toc=toc,
            renumber_headings=renumber_headings,
            layout_rebalance=True,
            strict_profile=strict_profile,
        )
        paragraph_count = int(preview.get("paragraph_count") or 0)
        table_count = int(preview.get("table_count") or 0)
        heading_style_candidates = int(preview.get("heading_style_candidates") or 0)
        if paragraph_count >= 450 or table_count >= 20 or heading_style_candidates >= 25:
            layout_rebalance = False
            effective_candidate_mode = "fast_candidate"
            degraded_from_compact = True
            degrade_reason = "文档对象流复杂，已自动降级为快速候选稿，未启用慢速重排。"
    elif candidate_mode == "fast_candidate":
        layout_rebalance = False

    if dry_run:
        preview = build_scoped_fix_preview(
            file_path,
            output_path=resolved_output_path,
            profile_path=profile_path,
            scopes=scopes,
            toc=toc,
            renumber_headings=renumber_headings,
            layout_rebalance=layout_rebalance,
            strict_profile=strict_profile,
        )
        return {
            "mode": "preview",
            "document": {
                "path": preview["file_path"],
                "name": Path(preview["file_path"]).name,
            },
            "output": {
                "path": preview.get("output_path"),
            },
            "profile": {
                "id": preview.get("profile_id"),
                "requested": preview.get("requested_profile", profile_path),
                "fallback_used": bool(preview.get("fallback_used")),
                "display": preview.get("profile_display"),
            },
            "selected_scopes": preview.get("selected_scopes"),
            "toc_enabled": bool(preview.get("toc_enabled")),
            "renumber_headings": bool(preview.get("renumber_headings")),
            "layout_rebalance": bool(preview.get("layout_rebalance")),
            "candidate_mode": effective_candidate_mode,
            "candidate_request_mode": candidate_mode,
            "degraded_from_compact": degraded_from_compact,
            "degrade_reason": degrade_reason,
            "paragraph_count": preview.get("paragraph_count"),
            "table_count": preview.get("table_count"),
            "heading_style_candidates": preview.get("heading_style_candidates"),
            "targeted_modules": dict(preview.get("targeted_modules") or {}),
            "notes": list(preview.get("notes") or []),
        }

    diagnostics: dict[str, Any] | None = None
    warning_lines: list[str] = []
    should_block = False
    if not force:
        diagnostics = build_document_diagnostics(
            file_path,
            profile_path=profile_path,
            strict_profile=strict_profile,
        )
        warning_lines, should_block = _render_apply_risk_warning(
            diagnostics,
            renumber_headings=renumber_headings,
            selected_scopes=set(selected_scopes) if selected_scopes else None,
        )
        if should_block:
            raise ApplyGuardBlockedError(
                _blocked_apply_message(warning_lines),
                guard=_serialize_apply_guard(
                    diagnostics,
                    checked=True,
                    blocked=True,
                    force_used=False,
                    warning_lines=warning_lines,
                ),
            )

    written_output_path = apply_scoped_fix(
        file_path,
        resolved_output_path,
        profile_path=profile_path,
        scopes=scopes,
        toc=toc,
        renumber_headings=renumber_headings,
        layout_rebalance=layout_rebalance,
        strict_profile=strict_profile,
    )
    verification_payload = verify_document(
        str(written_output_path),
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
    )
    post_verify_notices = _render_post_verify_notice(verification_payload)
    return {
        "mode": "apply",
        "document": {
            "path": str(Path(file_path)),
            "name": Path(file_path).name,
        },
        "output": {
            "path": str(written_output_path),
            "name": Path(str(written_output_path)).name,
        },
        "selected_scopes": verification_payload["selected_scopes"],
        "readiness": classify_apply_readiness(verification_payload),
        "candidate_mode": effective_candidate_mode,
        "candidate_request_mode": candidate_mode,
        "degraded_from_compact": degraded_from_compact,
        "degrade_reason": degrade_reason,
        "layout_rebalance": bool(layout_rebalance),
        "guard": _serialize_apply_guard(
            diagnostics,
            checked=not force,
            blocked=False,
            force_used=force,
            warning_lines=warning_lines,
        ),
        "post_verify_notices": post_verify_notices,
        "verification": verification_payload,
    }
