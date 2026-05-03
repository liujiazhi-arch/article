from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from article_engine import normalize_document, preflight_document, render_verify_document


SERVICE_NAME = "article-api"
SERVICE_STAGE = "local-shell-alpha"
SERVICE_VERSION = "0.1.0"
API_VERSION = "v0"

RENDER_WORKFLOW_MODES: tuple[dict[str, Any], ...] = (
    {
        "id": "default_user",
        "title": "默认用户模式",
        "subtitle": "用户用 Word/WPS 导出 PDF，工具只分析真实 PDF。",
        "stability": "high",
        "button_label": "用已导出的 PDF 复核",
        "requires_manual_pdf": True,
        "uses_automation": False,
        "creates_candidate_docx": False,
        "backend_action": "render-verify with rendered_pdf or page_images_dir",
        "why": "Word/WPS 自动化容易被恢复弹窗、权限和超时打断；手动 PDF 最适合普通用户。",
        "best_for": "普通用户、最终提交前复核、多人使用场景。",
    },
    {
        "id": "advanced_word",
        "title": "高级模式",
        "subtitle": "尝试连接 Microsoft Word 自动导出 PDF。",
        "stability": "medium",
        "button_label": "尝试 Word 自动复核",
        "requires_manual_pdf": False,
        "uses_automation": True,
        "creates_candidate_docx": False,
        "backend_action": "render-verify with renderer=word-pdf",
        "why": "适合本机 Word 状态稳定时快速复核；失败时应改用默认用户模式。",
        "best_for": "开发者、本机调试、已确认 Word 不会弹恢复框的环境。",
    },
    {
        "id": "agent_candidate",
        "title": "Agent 候选稿模式",
        "subtitle": "复核后排障工具，只在 PDF 版式复核发现可行动问题后使用。",
        "stability": "assisted",
        "button_label": "生成候选修复稿",
        "requires_manual_pdf": False,
        "uses_automation": False,
        "creates_candidate_docx": True,
        "backend_action": "apply candidate with headings + figures_tables + layout_rebalance",
        "why": "它不是常规修复模式；渲染层问题需要先看 Word/WPS PDF 证据，候选稿不能直接覆盖原文，也不能跳过再次 PDF 复核。",
        "best_for": "PDF 复核已经确认的复杂图表挤页、标题孤页、大块空白等排版排障。",
    },
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def wild_doc_signals(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    toc = diagnostics.get("toc") or {}
    toc_status = str(toc.get("status") or "")
    if toc_status in {"manual_toc", "duplicate_toc", "field_only", "no_toc"}:
        signals.append(
            {
                "id": "toc_structure",
                "label": "目录结构异常",
                "count": 1,
                "status": toc_status,
            }
        )
    table_heading_candidates = diagnostics.get("table_heading_candidates") or []
    if table_heading_candidates:
        signals.append(
            {
                "id": "table_heading_candidates",
                "label": "表格内伪标题候选",
                "count": len(table_heading_candidates),
            }
        )
    style_text_conflicts = diagnostics.get("style_text_conflicts") or []
    if style_text_conflicts:
        signals.append(
            {
                "id": "style_text_conflicts",
                "label": "样式/文本层级冲突",
                "count": len(style_text_conflicts),
            }
        )
    return signals


def build_preflight_payload(
    *,
    file_path: str,
    profile_path: str = "lnu",
    strict_profile: bool | None = None,
    preflight_fn: Callable[..., dict[str, Any]] = preflight_document,
) -> dict[str, Any]:
    payload = preflight_fn(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    diagnostics = payload.get("diagnostics") or {}
    signals = wild_doc_signals(diagnostics)
    summary = dict(payload.get("summary") or {})
    summary.update(
        {
            "heading_count": len(diagnostics.get("headings") or []),
            "wild_doc_detected": bool(signals),
            "wild_doc_signal_count": len(signals),
        }
    )
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": utcnow(),
            "operation": "preflight",
            "status": "ok",
            "summary": summary,
            "wild_doc": {
                "detected": bool(signals),
                "signals": signals,
            },
        }
    )
    return payload


def build_normalize_payload(
    *,
    file_path: str,
    output_path: str | None = None,
    profile_path: str = "lnu",
    strict_profile: bool | None = None,
    normalize_fn: Callable[..., dict[str, Any]] = normalize_document,
) -> dict[str, Any]:
    payload = normalize_fn(
        file_path,
        output_path=output_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    before = payload.get("before") or {}
    after = payload.get("after") or {}
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": utcnow(),
            "operation": "normalize",
            "status": "ok",
            "wild_doc": {
                "before": {
                    "preflight_status": before.get("preflight_status"),
                    "toc_status": before.get("toc_status"),
                    "style_conflict_count": before.get("style_conflict_count", 0),
                    "table_heading_risk_count": before.get("table_heading_risk_count", 0),
                },
                "after": {
                    "preflight_status": after.get("preflight_status"),
                    "toc_status": after.get("toc_status"),
                    "style_conflict_count": after.get("style_conflict_count", 0),
                    "table_heading_risk_count": after.get("table_heading_risk_count", 0),
                },
            },
        }
    )
    return payload


def build_render_verify_payload(
    *,
    file_path: str,
    output_dir: str | None = None,
    profile_path: str = "lnu",
    scopes: list[str] | None = None,
    strict_profile: bool | None = None,
    renderer: str = "auto",
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
    workflow_mode: str | None = None,
    render_verify_fn: Callable[..., dict[str, Any]] = render_verify_document,
) -> dict[str, Any]:
    render_workflow_mode = resolve_render_workflow_mode(
        workflow_mode=workflow_mode,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )
    payload = render_verify_fn(
        file_path,
        output_dir=output_dir,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )
    render_summary = payload.get("render_summary") or {}
    layout_score = payload.get("layout_score") or {}
    render_text_summary = payload.get("render_text_summary") or {}
    payload.update(
        {
            "service": SERVICE_NAME,
            "stage": SERVICE_STAGE,
            "version": SERVICE_VERSION,
            "api_version": API_VERSION,
            "observed_at": utcnow(),
            "operation": "render-verify",
            "status": "ok",
            "render_workflow_mode": render_workflow_mode,
            "summary": {
                "page_count": payload.get("page_count", 0),
                "render_engine": payload.get("render_engine"),
                "evidence_source": payload.get("evidence_source"),
                "evidence_trust": payload.get("evidence_trust"),
                "evidence_authoritative": bool(payload.get("evidence_authoritative")),
                "layout_decision_eligible": bool(payload.get("layout_decision_eligible")),
                "render_fallback_used": bool(payload.get("render_fallback_used")),
                "render_finding_count": len(payload.get("render_findings") or []),
                "render_highest_severity": render_summary.get("highest_severity"),
                "layout_score": layout_score.get("score"),
                "layout_penalty": layout_score.get("penalty"),
                "actionable_finding_count": int(render_summary.get("actionable_finding_count") or 0),
                "expected_blank_count": int(render_summary.get("expected_blank_count") or 0),
                "object_flow_issue_count": int(render_summary.get("object_flow_issue_count") or 0),
                "heading_break_issue_count": int(render_summary.get("heading_break_issue_count") or 0),
                "page_text_available_count": int(render_text_summary.get("page_text_available_count") or 0),
                "page_text_extraction_warning_count": int(render_text_summary.get("page_text_extraction_warning_count") or 0),
                "review_item_count": len(payload.get("review_items") or []),
                "manual_review_rule_count": len(payload.get("manual_review_rule_ids") or []),
                "unsupported_rule_count": len(payload.get("unsupported_rule_ids") or []),
                "render_workflow_mode": render_workflow_mode["id"],
            },
        }
    )
    return payload


def build_render_workflow_modes_payload() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "recommended_mode": "default_user",
        "render_layer_issues": [
            "Word/WPS 才是最终版式证据，但它们不是稳定后端服务。",
            "自动连接 Word 可能遇到权限、恢复弹窗、会员弹窗或导出 PDF 超时。",
            "候选稿修复必须回到 DOCX，且需要再次导出 PDF 对比分数，不能直接改 PDF。",
        ],
        "modes": [dict(item) for item in RENDER_WORKFLOW_MODES],
    }


def resolve_render_workflow_mode(
    *,
    workflow_mode: str | None,
    renderer: str,
    rendered_pdf: str | None,
    page_images_dir: str | None,
) -> dict[str, Any]:
    mode_id = workflow_mode
    if mode_id is None:
        mode_id = "default_user" if rendered_pdf or page_images_dir else "advanced_word"
    mode = next((dict(item) for item in RENDER_WORKFLOW_MODES if item["id"] == mode_id), None)
    if mode is None:
        valid = ", ".join(item["id"] for item in RENDER_WORKFLOW_MODES)
        raise ValueError(f"未知渲染工作流模式: {workflow_mode}。可选: {valid}")
    if mode_id == "default_user" and not (rendered_pdf or page_images_dir):
        raise ValueError("默认用户模式需要先用 Word/WPS 导出 PDF，或提供页图目录。")
    if mode_id == "advanced_word" and renderer not in {"auto", "word-pdf"}:
        raise ValueError("高级模式只能使用 Word PDF 渲染。")
    if mode_id == "agent_candidate":
        raise ValueError("Agent 候选稿模式不直接执行 render-verify；请先生成候选 DOCX，再用默认用户模式复核 PDF。")
    return mode
