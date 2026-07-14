from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from article_api.render_evidence import register_render_evidence_screenshots
from article_engine import normalize_document, preflight_document, render_verify_document


SERVICE_NAME = "article-api"
SERVICE_STAGE = "local-shell-alpha"
SERVICE_VERSION = "0.1.2"
API_VERSION = "v0"

RENDER_WORKFLOW_MODES: tuple[dict[str, Any], ...] = (
    {
        "id": "default_user",
        "title": "PDF 版式复核",
        "subtitle": "用户用 Word/WPS 导出 PDF，工具分析真实 PDF 页面。",
        "stability": "high",
        "button_label": "导入 PDF 并复核",
        "requires_manual_pdf": True,
        "uses_automation": False,
        "creates_candidate_docx": False,
        "backend_action": "render-verify with rendered_pdf",
        "why": "Word/WPS 自动化容易被恢复弹窗、权限和超时打断；手动导出的 PDF 才是稳定版式证据。",
        "best_for": "普通用户、最终提交前复核、多人使用场景。",
    },
    {
        "id": "agent_candidate",
        "title": "Agent 候选稿模式",
        "subtitle": "复核后排障工具，只在 PDF 版式复核发现可行动问题后使用。",
        "stability": "assisted",
        "button_label": "生成候选修复稿",
        "candidate_modes": ["fast_candidate", "compact_candidate"],
        "requires_manual_pdf": False,
        "uses_automation": False,
        "creates_candidate_docx": True,
        "backend_action": "apply candidate with headings + figures_tables; fast mode by default, compact mode opt-in",
        "why": "它不是常规修复模式；渲染层问题需要先看 PDF 证据，候选稿不能直接覆盖原文，也不能跳过再次 PDF 复核。",
        "best_for": "PDF 复核已经确认的复杂图表挤页、标题孤页和公式编号跨页等排版排障。",
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
    pdf_matches_docx_confirmed: bool = False,
    generate_static_toc: bool = False,
    workflow_mode: str | None = None,
    render_verify_fn: Callable[..., dict[str, Any]] = render_verify_document,
) -> dict[str, Any]:
    render_workflow_mode = resolve_render_workflow_mode(
        workflow_mode=workflow_mode,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )
    engine_payload = render_verify_fn(
        file_path,
        output_dir=output_dir,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
        renderer=renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
        pdf_matches_docx_confirmed=pdf_matches_docx_confirmed,
        generate_static_toc=generate_static_toc,
    )
    payload = register_render_evidence_screenshots(dict(engine_payload))
    summary = {
        **dict(payload.get("summary") or {}),
        "render_workflow_mode": render_workflow_mode["id"],
    }
    return {
        **payload,
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "observed_at": utcnow(),
        "operation": "render-verify",
        "status": "ok",
        "render_workflow_mode": render_workflow_mode,
        "summary": summary,
    }


def build_render_workflow_modes_payload() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "stage": SERVICE_STAGE,
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "recommended_mode": "default_user",
        "render_layer_issues": [
            "Word/WPS 才是最终版式证据，但它们不是稳定后端服务。",
            "自动连接 Word/WPS 已从产品入口移除；用户导出的 PDF 是当前稳定证据。",
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
        mode_id = "default_user"
    mode = next((dict(item) for item in RENDER_WORKFLOW_MODES if item["id"] == mode_id), None)
    if mode is None:
        valid = ", ".join(item["id"] for item in RENDER_WORKFLOW_MODES)
        raise ValueError(f"未知渲染工作流模式: {workflow_mode}。可选: {valid}")
    if mode_id == "default_user" and not rendered_pdf:
        raise ValueError("PDF 版式复核需要先用 Word/WPS 导出 PDF。")
    if mode_id == "agent_candidate":
        raise ValueError("Agent 候选稿模式不直接执行 render-verify；请先生成候选 DOCX，再用 PDF 版式复核。")
    return mode
