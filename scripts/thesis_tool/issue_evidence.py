from __future__ import annotations

import shlex


HEADING_KINDS = {"h1", "h2", "h3", "h4"}

ACTION_LABELS = {
    "autofix": "auto_fixable",
    "manual_review": "needs_review",
    "unsupported": "manual_only",
    "unknown": "unknown",
}

STUDENT_TITLES = {
    "LNU_EQ05": "公式说明变量后缀没有设置为下标",
    "SP_CJK_LATIN": "中英文字符间距缺失",
    "SP_NUM_CJK": "中文与数字间距缺失",
    "LNU_REF01": "参考文献存在中文全角标点",
    "LNU_REF02": "参考文献编号格式不符合要求",
    "LNU_TITLE01": "标题两字之间缺少两个空格",
}


def _context_map(contexts: list[dict]) -> dict[int, dict]:
    return {int(ctx["index"]): ctx for ctx in contexts if ctx.get("index") is not None}


def _nearest_heading(contexts: list[dict], paragraph_index: int | None) -> str | None:
    if paragraph_index is None:
        return None
    nearest = None
    for ctx in contexts:
        index = ctx.get("index")
        if index is None:
            continue
        if int(index) >= paragraph_index:
            break
        if ctx.get("kind") in HEADING_KINDS and ctx.get("text"):
            nearest = str(ctx["text"]).strip()
    return nearest


def _action_label(action: str | None) -> str:
    return ACTION_LABELS.get(str(action or "unknown"), "unknown")


def _fallback_example(result: dict) -> dict:
    issues = result.get("issues") or []
    text = str(issues[0]) if issues else str(result.get("affected") or "")
    return {
        "paragraph_index": None,
        "nearest_heading": None,
        "text": text,
        "tokens": [],
        "source": "checker_message_fallback",
    }


def _evidence_example(item: dict, contexts: list[dict], by_index: dict[int, dict]) -> dict:
    paragraph_index = item.get("paragraph_index")
    ctx = by_index.get(paragraph_index) if paragraph_index is not None else {}
    return {
        "paragraph_index": paragraph_index,
        "nearest_heading": _nearest_heading(contexts, paragraph_index),
        "section": item.get("section") or ctx.get("section"),
        "module": item.get("module") or ctx.get("module"),
        "kind": item.get("kind") or ctx.get("kind"),
        "text": item.get("text") or ctx.get("text") or "",
        "tokens": item.get("tokens") or [],
        "source": "structured",
    }


def _suggested_command(source_docx: str, scope_id: str | None, action: str) -> str | None:
    if action != "auto_fixable" or not scope_id:
        return None
    quoted_source = shlex.quote(source_docx)
    return (
        "python3 scripts/thesis_workbench.py apply "
        f"{quoted_source} --profile lnu --scope {scope_id} --output thesis_修复.docx"
    )


def build_issue_groups(
    results: list[dict],
    contexts: list[dict],
    *,
    actions: dict[str, str],
    rule_to_scope: dict[str, str],
    source_docx: str,
    sample_limit: int = 3,
) -> list[dict]:
    by_index = _context_map(contexts)
    groups = []
    for result in results:
        if result.get("passed"):
            continue
        rule_id = result["id"]
        action = _action_label(actions.get(rule_id))
        scope_id = rule_to_scope.get(rule_id)
        raw_evidence = result.get("evidence") or []
        source = "structured" if raw_evidence else "checker_message_fallback"
        examples = (
            [_evidence_example(item, contexts, by_index) for item in raw_evidence]
            if raw_evidence
            else [_fallback_example(result)]
        )
        total_count = len(examples) if source == "structured" else None
        shown_examples = examples[:sample_limit]
        hidden_count = max(0, len(examples) - len(shown_examples)) if total_count is not None else 0
        groups.append(
            {
                "rule_id": rule_id,
                "rule_name": result.get("name", rule_id),
                "student_title": STUDENT_TITLES.get(rule_id, result.get("name", rule_id)),
                "action": action,
                "scope_id": scope_id,
                "total_count": total_count,
                "shown_count": len(shown_examples),
                "hidden_count": hidden_count,
                "examples": shown_examples,
                "source": source,
                "suggested_command": _suggested_command(source_docx, scope_id, action),
                "issues": result.get("issues") or [],
                "affected": result.get("affected"),
            }
        )
    return groups
