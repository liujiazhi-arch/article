from __future__ import annotations

from pathlib import Path


def _truncate_text(text: str, *, limit: int = 80) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


def _render_limited_items(lines: list[str], items: list[dict], renderer, *, limit: int = 12):
    for item in items[:limit]:
        lines.append(renderer(item))
    if len(items) > limit:
        lines.append(f"- 其余 {len(items) - limit} 项已省略。")


def render_scope_plan(plan: dict) -> str:
    lines = [
        f"文件: {Path(plan['file_path']).name}",
        f"Profile: {plan.get('profile_display') or plan.get('profile_id') or plan['profile_path'] or 'default'}",
        f"评分: {plan['score']}/100",
        f"未通过规则: {plan['failed_count']}",
        "",
        "建议按范围处理：",
    ]

    ranked_scopes = [scope for scope in plan["scopes"] if scope["failed_count"] > 0]
    not_checked_scopes = [scope for scope in plan["scopes"] if scope["status"] == "not_checked"]
    if not ranked_scopes:
        lines.append("1. 所有已定义范围当前均未发现规则问题。")
    else:
        for index, scope in enumerate(ranked_scopes, start=1):
            failed_rules = ", ".join(scope["failed_rules"])
            lines.append(
                f"{index}. {scope['title']}（{scope['id']}）: {scope['failed_count']} 条规则未通过，状态 {scope['status']}"
            )
            lines.append(f"   规则: {failed_rules}")
            lines.append(
                "   处理建议: "
                f"可自动修复 {scope['autofixable_count']} / "
                f"人工确认 {scope['manual_review_count']} / "
                f"当前不支持 {scope['unsupported_count']}"
            )
            lines.append(f"   说明: {scope['description']}")

    if not_checked_scopes:
        lines.extend(["", "未自动审查范围:"])
        for scope in not_checked_scopes:
            lines.append(f"- {scope['title']}（{scope['id']}）: 未自动审查 需要显式选择并人工复核")

    if plan["unscoped_failed"]:
        lines.append("")
        lines.append("未归类规则:")
        for result in plan["unscoped_failed"]:
            lines.append(f"- {result['id']} {result['name']}")

    return "\n".join(lines)


def render_scope_verify(verification: dict) -> str:
    lines = [
        f"文件: {Path(verification['file_path']).name}",
        f"Profile: {verification.get('profile_display') or verification.get('profile_id') or verification['profile_path'] or 'default'}",
        f"评分: {verification['score']}/100",
        f"验证状态: {verification['overall_status']}",
        f"可提交状态: {verification['readiness']}",
        f"未通过规则: {verification['failed_count']}",
    ]

    if verification["selected_scopes"]:
        lines.append(f"复查范围: {', '.join(verification['selected_scopes'])}")

    failed_scopes = [scope for scope in verification["scopes"] if scope["failed_count"] > 0]
    render_check_rules = verification.get("render_check_rules") or []
    if not failed_scopes and not render_check_rules:
        lines.append("结果: 所选范围当前未发现规则问题。")
        return "\n".join(lines)
    if not failed_scopes:
        lines.append("结果: 所选范围结构规则已通过，但仍需做渲染复核。")

    if failed_scopes:
        lines.append("")
        lines.append("范围复查结果：")
        for scope in failed_scopes:
            lines.append(
                f"- {scope['title']}（{scope['id']}）: "
                f"自动修复 {scope['autofixable_count']}，"
                f"人工确认 {scope['manual_review_count']}，"
                f"当前不支持 {scope['unsupported_count']}"
            )

    manual_review_rules = verification.get("manual_review_rules") or []
    unsupported_rules = verification.get("unsupported_rules") or []
    if manual_review_rules or unsupported_rules:
        lines.append("")
        lines.append("仍需人工复核：")
        lines.append("提示: 评分较高不等于可直接提交，以下规则仍需人工确认。")
        for item in manual_review_rules:
            lines.append(
                f"- {item['id']} ({item['check_level']}) {item['name']} "
                f"[scope={item['scope_id']}]"
            )
        for item in unsupported_rules:
            lines.append(
                f"- {item['id']} (unsupported/{item['check_level']}) {item['name']} "
                f"[scope={item['scope_id']}]"
            )
    if render_check_rules:
        lines.append("")
        lines.append("仍需渲染复核：")
        lines.append("提示: 结构层已处理到位，但最终 Word/WPS 显示仍需确认。")
        for item in render_check_rules:
            lines.append(
                f"- {item['id']} ({item['check_level']}) {item['name']} "
                f"[scope={item['scope_id']}]"
            )
    return "\n".join(lines)


def render_document_diagnostics(diagnostics: dict) -> str:
    toc = diagnostics["toc"]
    lines = [
        f"文件: {Path(diagnostics['file_path']).name}",
        f"Profile: {diagnostics.get('profile_display') or diagnostics.get('profile_id') or diagnostics['profile_path'] or 'default'}",
        f"目录状态: {toc['status']}",
        (
            "目录摘要: "
            f"标题 {toc['title_count']}，"
            f"目录域 {toc['field_count']}，"
            f"目录条目 {toc['entry_count']}，"
            f"结构段落 {toc['structural_count']}"
        ),
        f"辽大序言编号: {diagnostics['preface_status']}",
        (
            "正文重编号守卫: "
            f"{diagnostics['heading_renumber_guard']['status']}"
            f" ({diagnostics['heading_renumber_guard']['reason']})"
        ),
        "",
        "正文标题链：",
    ]

    if diagnostics["headings"]:
        for heading in diagnostics["headings"]:
            lines.append(f"- 第{heading['index']}段 {heading['kind']} {heading['text']}")
    else:
        lines.append("- 未检测到正文标题。")

    lines.extend(["", "表格内伪标题候选："])
    if diagnostics["table_heading_candidates"]:
        summary = diagnostics.get("table_heading_candidate_summary") or {}
        if summary:
            summary_text = "，".join(f"{reason} {count}" for reason, count in summary.items())
            lines.append(f"- 风险摘要: {summary_text}")
        _render_limited_items(
            lines,
            diagnostics["table_heading_candidates"],
            lambda candidate: (
                f"- 第{candidate['index']}段 {candidate['kind']} "
                f"reason={candidate['reason']} "
                f"style={candidate['style_id'] or '-'} "
                f"text_level={candidate['text_level'] or '-'} "
                f"{_truncate_text(candidate['text'])}"
            ),
            limit=8,
        )
    else:
        lines.append("- 未发现。")

    lines.extend(["", "样式/文本层级冲突："])
    if diagnostics["style_text_conflicts"]:
        _render_limited_items(
            lines,
            diagnostics["style_text_conflicts"],
            lambda conflict: (
                f"- 第{conflict['index']}段 "
                f"style={conflict['style_id'] or '-'}(h{conflict['style_level']}) "
                f"text=h{conflict['text_level']} "
                f"{_truncate_text(conflict['text'])}"
            ),
        )
    else:
        lines.append("- 未发现。")

    lines.extend(["", "建议动作："])
    for action in diagnostics.get("recommended_actions") or []:
        lines.append(f"- {action}")

    return "\n".join(lines)


def render_document_diagnostics_compact(diagnostics: dict) -> str:
    toc = diagnostics["toc"]
    summary = diagnostics.get("table_heading_candidate_summary") or {}
    summary_text = ",".join(f"{reason}:{count}" for reason, count in summary.items()) or "-"
    renumber_guard = diagnostics["heading_renumber_guard"]
    values = [
        ("file", Path(diagnostics["file_path"]).name),
        ("profile", diagnostics.get("profile_display") or diagnostics.get("profile_id") or diagnostics["profile_path"] or "default"),
        ("toc_status", toc["status"]),
        ("toc_title_count", str(toc["title_count"])),
        ("toc_field_count", str(toc["field_count"])),
        ("toc_entry_count", str(toc["entry_count"])),
        ("preface_status", diagnostics["preface_status"]),
        ("heading_renumber_guard_status", renumber_guard["status"]),
        ("heading_renumber_guard_reason", renumber_guard["reason"]),
        ("heading_count", str(len(diagnostics["headings"]))),
        ("table_heading_risk_count", str(len(diagnostics["table_heading_candidates"]))),
        ("table_heading_risk_summary", summary_text),
        ("style_conflict_count", str(len(diagnostics["style_text_conflicts"]))),
        ("recommended_action_count", str(len(diagnostics.get("recommended_actions") or []))),
    ]
    return "\n".join(f"{key}={value}" for key, value in values)


def render_document_preflight(preflight: dict) -> str:
    lines = [
        f"文件: {Path(preflight['file_path']).name}",
        f"Profile: {preflight.get('profile_display') or preflight.get('profile_id') or preflight['profile_path'] or 'default'}",
        f"预检状态: {preflight['preflight_status']}",
        f"结论: {preflight['headline']}",
        (
            "风险摘要: "
            f"toc={preflight.get('toc_status') or '-'}; "
            f"preface={preflight.get('preface_status') or '-'}; "
            f"heading_guard={(preflight.get('heading_renumber_guard') or {}).get('status') or '-'}; "
            f"table_risk={preflight.get('table_heading_risk_count', 0)}; "
            f"style_conflict={preflight.get('style_conflict_count', 0)}"
        ),
        "",
        "建议动作：",
    ]
    for action in preflight.get("recommended_actions") or []:
        lines.append(f"- {action}")
    return "\n".join(lines)


def render_document_normalize(normalize: dict) -> str:
    summary = normalize.get("summary") or {}
    lines = [
        f"文件: {Path(normalize['file_path']).name}",
        f"Profile: {normalize.get('profile_display') or normalize.get('profile_id') or normalize.get('profile_path') or 'default'}",
        f"输出文件: {normalize['output_path']}",
        f"预规整改动: {'有' if normalize.get('changed') else '无'}",
        (
            "预检变化: "
            f"{summary.get('before_preflight_status')} -> {summary.get('after_preflight_status')}; "
            f"toc {summary.get('before_toc_status')} -> {summary.get('after_toc_status')}; "
            f"style_conflict {summary.get('before_style_conflict_count', 0)} -> {summary.get('after_style_conflict_count', 0)}; "
            f"table_risk {summary.get('before_table_heading_risk_count', 0)} -> {summary.get('after_table_heading_risk_count', 0)}"
        ),
        "",
        "已执行动作：",
    ]
    operations = normalize.get("operations") or []
    if not operations:
        lines.append("- 未发现需要安全预规整的对象。")
    else:
        for item in operations:
            lines.append(f"- {item['label']} × {item['count']}")

    lines.append("")
    lines.append("下一步：")
    for item in normalize.get("next_steps") or []:
        lines.append(f"- {item}")
    return "\n".join(lines)


def render_document_normalize_compact(normalize: dict) -> str:
    summary = normalize.get("summary") or {}
    parts = [
        ("file", Path(normalize["file_path"]).name),
        ("profile", normalize.get("profile_display") or normalize.get("profile_id") or normalize.get("profile_path") or "default"),
        ("changed", str(bool(normalize.get("changed"))).lower()),
        ("operation_count", str(summary.get("operation_count", 0))),
        ("before_preflight_status", str(summary.get("before_preflight_status") or "-")),
        ("after_preflight_status", str(summary.get("after_preflight_status") or "-")),
        ("before_toc_status", str(summary.get("before_toc_status") or "-")),
        ("after_toc_status", str(summary.get("after_toc_status") or "-")),
        ("before_style_conflict_count", str(summary.get("before_style_conflict_count", 0))),
        ("after_style_conflict_count", str(summary.get("after_style_conflict_count", 0))),
        ("before_table_heading_risk_count", str(summary.get("before_table_heading_risk_count", 0))),
        ("after_table_heading_risk_count", str(summary.get("after_table_heading_risk_count", 0))),
    ]
    return "; ".join(f"{key}={value}" for key, value in parts)


def render_document_preflight_compact(preflight: dict) -> str:
    values = [
        ("file", Path(preflight["file_path"]).name),
        ("profile", preflight.get("profile_display") or preflight.get("profile_id") or preflight["profile_path"] or "default"),
        ("preflight_status", preflight["preflight_status"]),
        ("toc_status", str(preflight.get("toc_status") or "-")),
        ("preface_status", str(preflight.get("preface_status") or "-")),
        ("heading_renumber_guard_status", str((preflight.get("heading_renumber_guard") or {}).get("status") or "-")),
        ("heading_renumber_guard_reason", str((preflight.get("heading_renumber_guard") or {}).get("reason") or "-")),
        ("table_heading_risk_count", str(preflight.get("table_heading_risk_count", 0))),
        ("style_conflict_count", str(preflight.get("style_conflict_count", 0))),
        ("recommended_action_count", str(len(preflight.get("recommended_actions") or []))),
    ]
    return "\n".join(f"{key}={value}" for key, value in values)
