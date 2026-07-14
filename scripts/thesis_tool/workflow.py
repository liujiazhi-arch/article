from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

import audit_thesis
import fix_thesis
from _thesis_utils import NSMAP, W_NS, HeadingCandidateFilter, build_document_model, build_style_map, match_heading_by_text
from backmatter_title_utils import is_preface_heading_title
from frontmatter_utils import has_toc_field_instr, is_toc_structural_style_id

from thesis_tool.scopes import build_rule_scope_map, filter_scope_definitions, normalize_scope_names
from thesis_tool import workflow_renderers
from thesis_tool.conclusion_report import render_ai_review_context, render_student_conclusion_report
from thesis_tool.issue_evidence import build_issue_groups
from thesis_tool.scope_plan import (
    build_scope_plan,
    classify_audit_result_action,
)
from thesis_tool.scope_verify import (
    READINESS_MANUAL_REVIEW_REQUIRED,
    READINESS_NEEDS_FIX,
    READINESS_RENDER_CHECK_REQUIRED,
    READINESS_STRUCTURE_READY,
    READINESS_UNSUPPORTED,
    build_scope_verify_from_plan,
    classify_overall_status,
    classify_scope_readiness,
)

_HEADING_KIND_TO_LEVEL = {
    "h1": 1,
    "h2": 2,
    "h3": 3,
    "h4": 4,
}

PREFLIGHT_READY = "ready"
PREFLIGHT_WARNING = "warning"
PREFLIGHT_BLOCKED = "blocked"


def classify_apply_readiness(verification: dict) -> str:
    readiness = verification.get("readiness") or READINESS_STRUCTURE_READY
    if readiness == READINESS_STRUCTURE_READY:
        return READINESS_RENDER_CHECK_REQUIRED
    return readiness


def build_audit_human_reports(
    file_path: str,
    *,
    profile_path: str | None = None,
    strict_profile: bool | None = None,
    output_dir: str,
) -> dict:
    results, score, report, runtime = audit_thesis.audit_docx_with_runtime(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    document_xml, styles_xml, _footnotes_xml = audit_thesis.load_docx_xml(file_path)
    document_root = ET.fromstring(document_xml)
    styles_root = ET.fromstring(styles_xml)
    style_map = build_style_map(styles_root)
    document_model = build_document_model(document_root, style_map)
    # Keep original paragraph indexes for evidence; skip cover nodes only so
    # nearest-heading enrichment does not attach cover text to body findings.
    contexts = [
        {
            "index": node.index,
            "text": node.text,
            "kind": node.kind,
            "section": node.container_section,
            "module": node.module,
        }
        for node in document_model.paragraphs
        if node.container_section != "cover"
    ]
    runtime_rule_ids = {rule_id for rule_id, _, _ in runtime.rule_definitions}
    scope_definitions = filter_scope_definitions(runtime_rule_ids)
    rule_to_scope = build_rule_scope_map(scope_definitions)
    actions = {result["id"]: classify_audit_result_action(result) for result in results if not result.get("passed")}
    groups = build_issue_groups(
        results,
        contexts,
        actions=actions,
        rule_to_scope=rule_to_scope,
        source_docx=str(Path(file_path)),
    )
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    audit_report_path = target_dir / "audit_report.md"
    student_report_path = target_dir / "结论报告.md"
    ai_report_path = target_dir / "ai_review_context.md"
    audit_report_path.write_text(report, encoding="utf-8")
    student_report_path.write_text(render_student_conclusion_report(groups), encoding="utf-8")
    ai_report_path.write_text(render_ai_review_context(groups), encoding="utf-8")
    return {
        "results": results,
        "score": score,
        "groups": groups,
        "report_paths": {
            "audit_report": str(audit_report_path),
            "student_report": str(student_report_path),
            "ai_review_context": str(ai_report_path),
        },
    }


def render_scope_plan(plan: dict) -> str:
    return workflow_renderers.render_scope_plan(plan)


def build_scope_verify(
    file_path: str,
    profile_path: str | None = None,
    scopes=None,
    strict_profile: bool | None = None,
    *,
    diagnostics: dict | None = None,
) -> dict:
    plan = build_scope_plan(file_path, profile_path=profile_path, scopes=scopes, strict_profile=strict_profile)
    selected_scope_ids = set(plan["selected_scopes"] or [scope["id"] for scope in plan["scopes"]])
    if diagnostics is None and "toc" in selected_scope_ids:
        diagnostics = build_document_diagnostics(
            file_path,
            profile_path=profile_path,
            strict_profile=strict_profile,
        )
    return build_scope_verify_from_plan(plan, diagnostics=diagnostics or {})


def render_scope_verify(verification: dict) -> str:
    return workflow_renderers.render_scope_verify(verification)


def _load_document_model(file_path: str):
    document_xml, styles_xml, _footnotes_xml = audit_thesis.load_docx_xml(file_path)
    document_root = ET.fromstring(document_xml)
    styles_root = ET.fromstring(styles_xml)
    style_map = build_style_map(styles_root)
    document_model = build_document_model(document_root, style_map)
    return document_root, style_map, document_model


def _node_style_id(node) -> str | None:
    style_elem = node.elem.find("w:pPr/w:pStyle", NSMAP)
    if style_elem is None:
        return None
    return style_elem.get(f"{{{W_NS}}}val")


def _style_heading_level(style_id: str | None, style_map: dict) -> int | None:
    if not style_id:
        return None
    style_props = style_map.get(style_id, {})
    outline_level = style_props.get("outlineLvl")
    if isinstance(outline_level, int) and 0 <= outline_level <= 3:
        return outline_level + 1
    return None


def _normalize_preface_heading_title(text: str) -> str:
    return "序言" if is_preface_heading_title(text) else ""


def _build_toc_diagnostics(document_model, style_map: dict) -> dict:
    title_count = 0
    entry_count = 0
    field_count = 0
    structural_count = 0

    for node in document_model.paragraphs:
        style_id = _node_style_id(node)
        has_toc_field = has_toc_field_instr(node.elem, NSMAP)

        if node.module == "toc_title":
            title_count += 1
        if node.module == "toc_entry":
            entry_count += 1
        if is_toc_structural_style_id(style_id):
            structural_count += 1
        if str(style_id or "").strip() == "TOCField" or has_toc_field:
            field_count += 1

    if title_count > 1:
        status = "duplicate_toc"
    elif title_count == 0 and entry_count == 0 and field_count == 0 and structural_count == 0:
        status = "no_toc"
    elif field_count > 0 and entry_count == 0:
        status = "field_only"
    elif field_count > 0:
        status = "generated_toc"
    else:
        status = "manual_toc"

    return {
        "status": status,
        "title_count": title_count,
        "entry_count": entry_count,
        "field_count": field_count,
        "structural_count": structural_count,
    }


def _build_diagnostic_actions(toc: dict, preface_status: str, style_text_conflicts: list[dict], table_heading_candidates: list[dict]) -> list[str]:
    actions: list[str] = []

    toc_status = toc.get("status")
    if toc_status in {"manual_toc", "duplicate_toc", "no_toc"}:
        actions.append("优先处理目录：建议执行 toc scope 补全或规范可见目录，完成后人工核对页码。")
    elif toc_status == "field_only":
        actions.append("目录结构已存在但缺少可见结果：重新执行 toc scope 生成可见目录，再复核页码。")

    if preface_status == "zero_based_mismatch":
        actions.append("辽大序言编号异常：建议执行 headings scope，并启用 --renumber-headings。")
    elif preface_status == "preface_without_children":
        actions.append("检测到序言但未发现子标题：先人工确认是否需要 0.1 / 0.1.1 体系。")

    if style_text_conflicts:
        actions.append("存在样式/文本层级冲突：优先检查 headings scope，确认错样式标题是否需要自动扶正。")

    if table_heading_candidates:
        actions.append("表格中存在伪标题风险：重编号前先核对表格内容，避免将化合物名或数值误算进标题链。")

    if not actions:
        actions.append("当前未发现明显结构风险，可直接按目标 scope 执行修复或复查。")
    return actions


def _build_heading_renumber_guard(style_text_conflicts: list[dict], table_heading_candidates: list[dict]) -> dict:
    if style_text_conflicts:
        return {
            "status": "block",
            "reason": "style_conflict",
            "style_conflict_count": len(style_text_conflicts),
            "table_risk_count": len(table_heading_candidates),
        }
    if table_heading_candidates:
        return {
            "status": "warn",
            "reason": "table_risk",
            "style_conflict_count": 0,
            "table_risk_count": len(table_heading_candidates),
        }
    return {
        "status": "clear",
        "reason": "none",
        "style_conflict_count": 0,
        "table_risk_count": 0,
    }


def classify_document_preflight_status(diagnostics: dict) -> str:
    renumber_guard = (diagnostics.get("heading_renumber_guard") or {}).get("status")
    if renumber_guard == "block":
        return PREFLIGHT_BLOCKED

    toc_status = str((diagnostics.get("toc") or {}).get("status") or "")
    preface_status = str(diagnostics.get("preface_status") or "")
    if (
        renumber_guard == "warn"
        or toc_status in {"manual_toc", "duplicate_toc", "field_only", "no_toc"}
        or preface_status in {"zero_based_mismatch", "preface_without_children"}
    ):
        return PREFLIGHT_WARNING

    return PREFLIGHT_READY


def build_document_diagnostics(file_path: str, profile_path: str | None = None, strict_profile: bool | None = None) -> dict:
    runtime = audit_thesis.build_audit_runtime(profile_path, strict_profile=strict_profile)
    _document_root, style_map, document_model = _load_document_model(file_path)
    toc = _build_toc_diagnostics(document_model, style_map)

    headings = []
    table_heading_candidates = []
    style_text_conflicts = []

    for node in document_model.section_nodes("body"):
        style_id = _node_style_id(node)
        style_level = _style_heading_level(style_id, style_map)
        text_level = match_heading_by_text(node.text)

        if node.kind in _HEADING_KIND_TO_LEVEL and not node.in_table:
            headings.append(
                {
                    "index": node.index,
                    "kind": node.kind,
                    "style_id": style_id,
                    "text": node.text.strip(),
                }
            )

        if HeadingCandidateFilter.is_table_heading_risk(node, style_level, text_level):
            candidate_reason = HeadingCandidateFilter.candidate_reason(node.text)
            table_heading_candidates.append(
                {
                    "index": node.index,
                    "kind": node.kind,
                    "style_id": style_id,
                    "style_level": style_level,
                    "text_level": text_level,
                    "reason": candidate_reason or "table_heading_like",
                    "text": node.text.strip(),
                }
            )

        if not node.in_table and style_level is not None and text_level is not None and style_level != text_level:
            style_text_conflicts.append(
                {
                    "index": node.index,
                    "kind": node.kind,
                    "style_id": style_id,
                    "style_level": style_level,
                    "text_level": text_level,
                    "text": node.text.strip(),
                }
            )

    preface_status = "not_detected"
    first_h1_index = next((idx for idx, item in enumerate(headings) if item["kind"] == "h1"), None)
    if first_h1_index is not None and _normalize_preface_heading_title(headings[first_h1_index]["text"]) == "序言":
        preface_children = []
        for item in headings[first_h1_index + 1 :]:
            if item["kind"] == "h1":
                break
            preface_children.append(item)
        numbered_children = [item for item in preface_children if item["kind"] in {"h2", "h3", "h4"}]
        if not numbered_children:
            preface_status = "preface_without_children"
        elif all(item["text"].startswith("0.") for item in numbered_children):
            preface_status = "zero_based_ok"
        else:
            preface_status = "zero_based_mismatch"

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
        "toc": toc,
        "headings": headings,
        "table_heading_candidates": table_heading_candidates,
        "table_heading_candidate_summary": {
            reason: sum(1 for item in table_heading_candidates if item["reason"] == reason)
            for reason in sorted({item["reason"] for item in table_heading_candidates})
        },
        "style_text_conflicts": style_text_conflicts,
        "preface_status": preface_status,
        "heading_renumber_guard": _build_heading_renumber_guard(
            style_text_conflicts,
            table_heading_candidates,
        ),
        "recommended_actions": _build_diagnostic_actions(
            toc,
            preface_status,
            style_text_conflicts,
            table_heading_candidates,
        ),
    }


def build_document_preflight(file_path: str, profile_path: str | None = None, strict_profile: bool | None = None) -> dict:
    diagnostics = build_document_diagnostics(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    preflight_status = classify_document_preflight_status(diagnostics)

    if preflight_status == PREFLIGHT_BLOCKED:
        headline = "发现高风险结构冲突，建议先处理后再执行 apply。"
    elif preflight_status == PREFLIGHT_WARNING:
        headline = "发现若干结构风险，建议先完成预检关注项。"
    else:
        headline = "未发现明显结构风险，可继续按目标 scope 执行修复。"

    return {
        "file_path": diagnostics["file_path"],
        "profile_path": diagnostics["profile_path"],
        "profile_id": diagnostics.get("profile_id"),
        "requested_profile": diagnostics.get("requested_profile"),
        "fallback_used": bool(diagnostics.get("fallback_used")),
        "profile_display": diagnostics.get("profile_display"),
        "preflight_status": preflight_status,
        "headline": headline,
        "toc_status": (diagnostics.get("toc") or {}).get("status"),
        "preface_status": diagnostics.get("preface_status"),
        "heading_renumber_guard": dict(diagnostics.get("heading_renumber_guard") or {}),
        "table_heading_risk_count": len(diagnostics.get("table_heading_candidates") or []),
        "style_conflict_count": len(diagnostics.get("style_text_conflicts") or []),
        "recommended_actions": list(diagnostics.get("recommended_actions") or []),
        "diagnostics": diagnostics,
    }


def build_document_normalize(
    file_path: str,
    *,
    output_path: str | None = None,
    profile_path: str | None = None,
    strict_profile: bool | None = None,
) -> dict:
    validated_input = audit_thesis.validate_docx_path(file_path)
    resolved_output_path = output_path or fix_thesis.default_normalize_output_path(validated_input)
    before = build_document_preflight(
        validated_input,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    normalized = fix_thesis.normalize_docx(
        validated_input,
        resolved_output_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    after = build_document_preflight(
        resolved_output_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )

    next_steps: list[str] = []
    if after.get("preflight_status") == PREFLIGHT_BLOCKED:
        next_steps.append("仍存在结构阻断，先重新查看 preflight 结果，再决定是否进入 apply。")
    elif after.get("preflight_status") == PREFLIGHT_WARNING:
        next_steps.append("结构风险已下降但未清零，建议先 verify 关键 scope，再决定是否 apply。")
    else:
        next_steps.append("预规整后未见明显结构阻断，可继续进入 verify 或 apply。")

    if after.get("toc_status") == "field_only":
        next_steps.append("目录仍只有域指令，需重新执行 toc scope 生成可见目录结果，再做渲染复核。")

    return {
        "file_path": str(Path(validated_input)),
        "output_path": str(Path(resolved_output_path)),
        "profile_path": profile_path,
        "profile_id": normalized.get("profile_id"),
        "requested_profile": normalized.get("requested_profile"),
        "fallback_used": bool(normalized.get("fallback_used")),
        "profile_display": normalized.get("profile_display"),
        "changed": bool(normalized.get("changed")),
        "operations": list(normalized.get("operations") or []),
        "summary": {
            "operation_count": len(normalized.get("operations") or []),
            "before_preflight_status": before.get("preflight_status"),
            "after_preflight_status": after.get("preflight_status"),
            "before_toc_status": before.get("toc_status"),
            "after_toc_status": after.get("toc_status"),
            "before_style_conflict_count": before.get("style_conflict_count", 0),
            "after_style_conflict_count": after.get("style_conflict_count", 0),
            "before_table_heading_risk_count": before.get("table_heading_risk_count", 0),
            "after_table_heading_risk_count": after.get("table_heading_risk_count", 0),
        },
        "before": before,
        "after": after,
        "next_steps": next_steps,
    }


def render_document_diagnostics(diagnostics: dict) -> str:
    return workflow_renderers.render_document_diagnostics(diagnostics)


def render_document_diagnostics_compact(diagnostics: dict) -> str:
    return workflow_renderers.render_document_diagnostics_compact(diagnostics)


def render_document_preflight(preflight: dict) -> str:
    return workflow_renderers.render_document_preflight(preflight)


def render_document_normalize(normalize: dict) -> str:
    return workflow_renderers.render_document_normalize(normalize)


def render_document_normalize_compact(normalize: dict) -> str:
    return workflow_renderers.render_document_normalize_compact(normalize)


def render_document_preflight_compact(preflight: dict) -> str:
    return workflow_renderers.render_document_preflight_compact(preflight)


def apply_scoped_fix(
    input_path: str,
    output_path: str,
    profile_path: str | None = None,
    scopes=None,
    toc: bool = False,
    renumber_headings: bool = False,
    layout_rebalance: bool = False,
    dry_run: bool = False,
    strict_profile: bool | None = None,
    cover_fields=None,
) -> str | dict:
    normalized_scopes = normalize_scope_names(scopes)
    runtime = fix_thesis.build_fix_runtime(
        profile_path=profile_path,
        toc=toc,
        scopes=normalized_scopes,
        renumber_headings=renumber_headings,
        layout_rebalance=layout_rebalance,
        dry_run=dry_run,
        strict_profile=strict_profile,
        cover_fields=cover_fields,
    )
    if dry_run:
        return fix_thesis.describe_fix_docx(
            input_path,
            output_path=output_path,
            runtime=runtime,
        )
    return fix_thesis.fix_docx(
        input_path,
        output_path,
        runtime=runtime,
    )


def build_scoped_fix_preview(
    input_path: str,
    output_path: str | None = None,
    profile_path: str | None = None,
    scopes=None,
    toc: bool = False,
    renumber_headings: bool = False,
    layout_rebalance: bool = False,
    strict_profile: bool | None = None,
    cover_fields=None,
) -> dict:
    preview = apply_scoped_fix(
        input_path,
        output_path or "",
        profile_path=profile_path,
        scopes=scopes,
        toc=toc,
        renumber_headings=renumber_headings,
        layout_rebalance=layout_rebalance,
        strict_profile=strict_profile,
        cover_fields=cover_fields,
        dry_run=True,
    )
    assert isinstance(preview, dict)
    if not output_path:
        preview["output_path"] = None
    return preview


def render_scoped_fix_preview(preview: dict) -> str:
    return fix_thesis.render_fix_preview(preview)
