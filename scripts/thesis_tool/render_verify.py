from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import audit_thesis

from thesis_tool.render_analyzer import analyze_page_images
from thesis_tool.workflow import (
    PREFLIGHT_BLOCKED,
    PREFLIGHT_WARNING,
    READINESS_RENDER_CHECK_REQUIRED,
    READINESS_STRUCTURE_READY,
    build_document_diagnostics,
    build_document_preflight,
    build_scope_verify,
)


RENDERER_AUTO = "auto"
RENDERER_WORD_PDF = "word-pdf"
RENDERER_MANUAL_PDF = "manual-pdf"
RENDERER_WPS_MANUAL_IMAGES = "wps-manual-images"
SUPPORTED_RENDERERS = {RENDERER_AUTO, RENDERER_WORD_PDF}
AUTHORITATIVE_EVIDENCE_SOURCES = {RENDERER_WORD_PDF, RENDERER_MANUAL_PDF, RENDERER_WPS_MANUAL_IMAGES}


def default_render_output_dir(input_docx: str) -> str:
    source = Path(input_docx).expanduser().resolve()
    return str(source.with_name(f"{source.stem}_render_verify"))


def _page_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"page-(\d+)\.png$", path.name)
    if match:
        return int(match.group(1)), path.name
    return sys.maxsize, path.name


def _collect_page_images(output_dir: str | Path) -> list[str]:
    directory = Path(output_dir).expanduser().resolve()
    return [str(path) for path in sorted(directory.glob("page-*.png"), key=_page_sort_key)]


def _collect_png_images(output_dir: str | Path) -> list[str]:
    directory = Path(output_dir).expanduser().resolve()
    page_images = _collect_page_images(directory)
    if page_images:
        return page_images
    return [str(path) for path in sorted(directory.glob("*.png"), key=_page_sort_key)]


def _find_pdftoppm() -> str:
    env_path = os.environ.get("ARTICLE_PDFTOPPM")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)
    found = shutil.which("pdftoppm")
    if found:
        return found
    raise RuntimeError("未找到 pdftoppm，无法将 Word PDF 转为页图。请安装 poppler 或设置 ARTICLE_PDFTOPPM。")


def _find_pdftotext() -> str:
    env_path = os.environ.get("ARTICLE_PDFTOTEXT")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)
    found = shutil.which("pdftotext")
    if found:
        return found
    raise RuntimeError("未找到 pdftotext，无法抽取 PDF 每页文本。请安装 poppler 或设置 ARTICLE_PDFTOTEXT。")


def _export_docx_to_pdf_with_word(input_docx: str, output_pdf: str) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("word-pdf 渲染目前仅支持 macOS 上的 Microsoft Word。")
    if shutil.which("osascript") is None:
        raise RuntimeError("未找到 osascript，无法调用 Microsoft Word 导出 PDF。")

    script = """
on run argv
  set inputPath to POSIX file (item 1 of argv)
  set outputPath to POSIX file (item 2 of argv)
  set expectedPath to item 1 of argv
  set targetName to item 3 of argv
  tell application "Microsoft Word"
    try
      close every document saving no
    end try
    open inputPath
    set docRef to missing value
    set observedDocuments to {}
    repeat with attempt from 1 to 30
      set observedDocuments to {}
      repeat with candidate in documents
        set candidateName to ""
        set candidatePath to ""
        try
          set candidateName to name of candidate as text
        end try
        try
          set candidatePath to POSIX path of (full name of candidate as alias)
        end try
        if candidateName is not "" or candidatePath is not "" then
          set end of observedDocuments to candidateName & "|" & candidatePath
        end if
        if candidatePath is expectedPath or candidateName is targetName then
          set docRef to candidate
          exit repeat
        end if
      end repeat
      if docRef is not missing value then exit repeat
      delay 1
    end repeat
    if docRef is missing value then
      error "Microsoft Word did not expose the opened DOCX; observed=" & observedDocuments
    end if
    save as docRef file name outputPath file format format PDF
    close docRef saving no
  end tell
end run
"""
    try:
        input_path = Path(input_docx).expanduser().resolve()
        output_path = Path(output_pdf).expanduser().resolve()
        subprocess.run(
            ["osascript", "-e", script, str(input_path), str(output_path), input_path.name],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Microsoft Word 自动化没有完成，未能导出 PDF。通常是 Word 没有暴露已打开的 DOCX，"
            "或正在等待权限、恢复文档、允许访问文件、保存确认等弹窗。请先处理 Word 弹窗；仍失败时改用手动导出 PDF。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "Microsoft Word 导出 PDF 失败。"
        if details:
            message = f"{message}\n{details}"
        raise RuntimeError(message) from exc

    if not Path(output_pdf).exists():
        raise RuntimeError(f"Microsoft Word 未生成 PDF: {output_pdf}")


def _convert_pdf_to_page_images(input_pdf: str, output_dir: str) -> None:
    pdftoppm = _find_pdftoppm()
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    prefix = str(resolved_output_dir / "page")
    try:
        subprocess.run(
            [pdftoppm, "-png", "-r", "120", str(Path(input_pdf).expanduser().resolve()), prefix],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "PDF 转页图失败。"
        if details:
            message = f"{message}\n{details}"
        raise RuntimeError(message) from exc


def _run_word_pdf_render(input_docx: str, output_dir: str) -> dict:
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = resolved_output_dir / "render_verify_word.pdf"
    page_dir = resolved_output_dir / "word_pdf_pages"
    _export_docx_to_pdf_with_word(input_docx, str(pdf_path))
    _convert_pdf_to_page_images(str(pdf_path), str(page_dir))
    return {
        "engine": RENDERER_WORD_PDF,
        "page_dir": str(page_dir),
        "pdf_path": str(pdf_path),
        "fallback_used": False,
        "warnings": [],
    }


def _run_render_engine(input_docx: str, output_dir: str, renderer: str) -> dict:
    if renderer not in SUPPORTED_RENDERERS:
        supported = ", ".join(sorted(SUPPORTED_RENDERERS))
        raise ValueError(f"未知渲染器: {renderer}。可选: {supported}")
    return _run_word_pdf_render(input_docx, output_dir)


def _run_external_pdf_render(rendered_pdf: str, output_dir: str) -> dict:
    resolved_pdf = Path(rendered_pdf).expanduser().resolve()
    if not resolved_pdf.exists():
        raise RuntimeError(f"用户提供的渲染 PDF 不存在: {resolved_pdf}")
    if resolved_pdf.suffix.lower() != ".pdf":
        raise RuntimeError(f"--rendered-pdf 需要 PDF 文件: {resolved_pdf}")
    page_dir = Path(output_dir).expanduser().resolve() / "manual_pdf_pages"
    _convert_pdf_to_page_images(str(resolved_pdf), str(page_dir))
    return {
        "engine": RENDERER_MANUAL_PDF,
        "page_dir": str(page_dir),
        "pdf_path": str(resolved_pdf),
        "fallback_used": False,
        "warnings": [],
    }


def _run_external_page_images(page_images_dir: str) -> dict:
    resolved_dir = Path(page_images_dir).expanduser().resolve()
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        raise RuntimeError(f"用户提供的页图目录不存在: {resolved_dir}")
    if not _collect_png_images(resolved_dir):
        raise RuntimeError(f"用户提供的页图目录未发现 PNG 页图: {resolved_dir}")
    return {
        "engine": RENDERER_WPS_MANUAL_IMAGES,
        "page_dir": str(resolved_dir),
        "pdf_path": None,
        "fallback_used": False,
        "warnings": [],
    }


def _resolve_render_metadata(
    input_docx: str,
    output_dir: str,
    renderer: str,
    *,
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
) -> dict:
    if rendered_pdf and page_images_dir:
        raise ValueError("--rendered-pdf 和 --page-images-dir 只能选择一个。")
    if rendered_pdf:
        return _run_external_pdf_render(rendered_pdf, output_dir)
    if page_images_dir:
        return _run_external_page_images(page_images_dir)
    return _run_render_engine(input_docx, output_dir, renderer)


def _classify_evidence_trust(evidence_source: str) -> dict:
    authoritative = evidence_source in AUTHORITATIVE_EVIDENCE_SOURCES
    trust = "authoritative" if authoritative else "unsupported"
    warnings: list[str] = []
    return {
        "trust": trust,
        "is_authoritative": authoritative,
        "layout_decision_eligible": authoritative,
        "warnings": warnings,
    }


def _empty_render_text_summary(*, source: str | None = None, warnings: list[str] | None = None) -> dict:
    warning_list = list(warnings or [])
    return {
        "source": source,
        "available": False,
        "page_text_available_count": 0,
        "page_text_extraction_warning_count": len(warning_list),
        "warnings": warning_list,
    }


def _extract_pdf_page_texts(pdf_path: str | None, *, page_count: int) -> tuple[dict[int, str], dict]:
    if not pdf_path:
        return {}, _empty_render_text_summary(source=None)
    resolved_pdf = Path(pdf_path).expanduser().resolve()
    if not resolved_pdf.exists():
        return {}, _empty_render_text_summary(source="pdf", warnings=[f"PDF 不存在，未抽取页文本: {resolved_pdf}"])

    try:
        pdftotext = _find_pdftotext()
        completed = subprocess.run(
            [pdftotext, "-layout", str(resolved_pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        return {}, _empty_render_text_summary(source="pdf", warnings=[str(exc)])

    raw_pages = str(completed.stdout or "").split("\f")
    if raw_pages and raw_pages[-1] == "":
        raw_pages = raw_pages[:-1]
    page_texts = {index: text.strip() for index, text in enumerate(raw_pages[:page_count], start=1) if text.strip()}
    warnings: list[str] = []
    if page_count > 0 and len(raw_pages) != page_count:
        warnings.append(f"PDF 文本页数 {len(raw_pages)} 与页图页数 {page_count} 不一致，已按可用页文本继续。")
    return page_texts, {
        "source": "pdf",
        "available": bool(page_texts),
        "page_text_available_count": len(page_texts),
        "page_text_extraction_warning_count": len(warnings),
        "warnings": warnings,
    }


def _build_render_review_items(diagnostics: dict, verification: dict) -> list[str]:
    items = [
        "本次结果重点用于解释 PDF 版式问题为什么出现，以及应该继续主流程还是进入排障模式。",
        "本次只完成 PDF 版式复核，尚未修改 Word 文档。",
    ]

    render_findings = verification.get("render_findings") or []
    finding_ids = {str(item.get("id") or item.get("type") or "") for item in render_findings if isinstance(item, dict)}
    if "large_blank_region" in finding_ids or "blank_page" in finding_ids:
        items.append("大块空白常见于对象塞不进当前页、段前/段后距过大、分页符残留，或对象锚点位置不当。")
    if "object_overflow" in finding_ids or "object_near_page_edge" in finding_ids:
        items.append("图表挤页常见于首次引用位置过晚、对象块过大，或图题注整体绑定到后页。")
    if "heading_isolated" in finding_ids or "heading_near_page_bottom" in finding_ids:
        items.append("标题孤页常见于标题前后分页、标题后正文不足，或前序对象块把正文挤到下一页。")

    items.extend([
        "如果不进入候选稿排障，建议回 Word/WPS 检查图片环绕、分页符、段前/段后距和对象锚点设置。",
        "如果 PDF finding 已经明确影响紧凑性，再进入候选稿排障更合适；否则优先回主流程修正文档结构或版式设置。",
    ])

    toc_status = str((diagnostics.get("toc") or {}).get("status") or "")
    if toc_status in {"field_only", "generated_toc"}:
        items.append("目录可能仍需在 Word/WPS 中 Ctrl+A 后按 F9 刷新，再复核页码与缩进。")
    elif toc_status in {"manual_toc", "duplicate_toc", "no_toc"}:
        items.append("目录结构当前不稳定，重点复核目录页码、层级和是否需要自动目录。")

    guard_status = str((diagnostics.get("heading_renumber_guard") or {}).get("status") or "")
    if guard_status == "warn":
        items.append("标题链附近存在表格伪标题风险，重点查看章节编号是否误伤表内内容。")
    elif guard_status == "block":
        items.append("标题样式/文本层级冲突仍存在，重点查看标题层级与分页是否自然。")

    manual_review_rule_ids = verification.get("manual_review_rule_ids") or []
    unsupported_rule_ids = verification.get("unsupported_rule_ids") or []
    if manual_review_rule_ids:
        items.append(f"除页图外，还需人工确认规则: {', '.join(manual_review_rule_ids)}。")
    if unsupported_rule_ids:
        items.append(f"当前仍有未自动闭环规则: {', '.join(unsupported_rule_ids)}。")

    return items


def _summarize_wild_doc(preflight: dict) -> dict:
    diagnostics = preflight.get("diagnostics") or {}
    toc = diagnostics.get("toc") or {}
    guard = preflight.get("heading_renumber_guard") or diagnostics.get("heading_renumber_guard") or {}
    table_risk_count = int(preflight.get("table_heading_risk_count") or 0)
    style_conflict_count = int(preflight.get("style_conflict_count") or 0)
    toc_status = str(preflight.get("toc_status") or toc.get("status") or "")
    preflight_status = str(preflight.get("preflight_status") or "")

    signals = []
    if toc_status in {"manual_toc", "duplicate_toc", "field_only", "no_toc"}:
        signals.append(
            {
                "id": "toc_structure",
                "severity": "warning" if toc_status != "duplicate_toc" else "blocker",
                "message": f"目录结构状态为 {toc_status}，渲染后仍需复核目录页码、层级和域刷新。",
            }
        )
    if style_conflict_count > 0:
        signals.append(
            {
                "id": "style_text_conflicts",
                "severity": "blocker",
                "message": f"发现 {style_conflict_count} 个样式/文本层级冲突，标题重编号前需要先规整。",
            }
        )
    if table_risk_count > 0:
        signals.append(
            {
                "id": "table_heading_candidates",
                "severity": "warning",
                "message": f"发现 {table_risk_count} 个表格伪标题候选，需防止渲染或重编号误伤表内内容。",
            }
        )

    wild_doc_detected = bool(signals) or preflight_status in {PREFLIGHT_WARNING, PREFLIGHT_BLOCKED}
    return {
        "detected": wild_doc_detected,
        "preflight_status": preflight_status,
        "toc_status": toc_status,
        "preface_status": preflight.get("preface_status"),
        "heading_renumber_guard": dict(guard),
        "style_conflict_count": style_conflict_count,
        "table_heading_risk_count": table_risk_count,
        "signals": signals,
        "recommended_actions": list(preflight.get("recommended_actions") or []),
    }


def _classify_render_evidence_status(
    *,
    page_count: int,
    preflight: dict,
    verification: dict,
    render_summary: dict | None = None,
    evidence_trust: dict | None = None,
) -> str:
    if page_count <= 0:
        return "render-failed"
    if preflight.get("preflight_status") == PREFLIGHT_BLOCKED:
        return "blocked-by-wild-doc"
    if verification.get("readiness") != READINESS_STRUCTURE_READY:
        return "structure-not-ready"
    if evidence_trust and not evidence_trust.get("is_authoritative"):
        return "unsupported-evidence"
    if (render_summary or {}).get("finding_count", 0) > 0:
        return "render-review-required"
    if preflight.get("preflight_status") == PREFLIGHT_WARNING:
        return "render-review-required"
    return "render-evidence-ready"


def _classify_render_readiness(preflight: dict, verification: dict) -> str:
    if preflight.get("preflight_status") == PREFLIGHT_BLOCKED:
        return "manual-review-required"
    readiness = verification.get("readiness")
    if readiness == READINESS_STRUCTURE_READY:
        return READINESS_RENDER_CHECK_REQUIRED
    return readiness or READINESS_RENDER_CHECK_REQUIRED


def build_render_verify_report(
    input_docx: str,
    *,
    output_dir: str | None = None,
    profile_path: str | None = None,
    scopes=None,
    strict_profile: bool | None = None,
    renderer: str = RENDERER_AUTO,
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
) -> dict:
    validated_input = audit_thesis.validate_docx_path(input_docx)
    resolved_output_dir = Path(output_dir or default_render_output_dir(validated_input)).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    render_metadata = _resolve_render_metadata(
        validated_input,
        str(resolved_output_dir),
        renderer,
        rendered_pdf=rendered_pdf,
        page_images_dir=page_images_dir,
    )
    page_images = _collect_png_images(render_metadata["page_dir"])
    if not page_images:
        raise RuntimeError(f"渲染未产出页图: {render_metadata['page_dir']}")
    evidence_source = render_metadata["engine"]
    evidence_trust = _classify_evidence_trust(evidence_source)
    page_texts, render_text_summary = _extract_pdf_page_texts(render_metadata.get("pdf_path"), page_count=len(page_images))
    render_analysis = analyze_page_images(page_images, evidence_source=evidence_source, page_texts=page_texts)
    render_findings = list(render_analysis.get("findings") or [])
    render_summary = dict(render_analysis.get("summary") or {})
    layout_score = dict(render_analysis.get("layout_score") or {})

    preflight = build_document_preflight(
        validated_input,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    diagnostics = preflight.get("diagnostics") or build_document_diagnostics(
        validated_input,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    verification = build_scope_verify(
        validated_input,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
    )
    wild_doc = _summarize_wild_doc(preflight)
    render_evidence_status = _classify_render_evidence_status(
        page_count=len(page_images),
        preflight=preflight,
        verification=verification,
        render_summary=render_summary,
        evidence_trust=evidence_trust,
    )
    render_warnings = list(render_metadata.get("warnings") or [])
    render_warnings.extend(evidence_trust["warnings"])
    render_warnings.extend(render_text_summary.get("warnings") or [])
    report = {
        "document": {
            "path": str(Path(validated_input)),
            "name": Path(validated_input).name,
        },
        "profile": {
            "id": verification.get("profile_id"),
            "requested": verification.get("requested_profile", profile_path),
            "fallback_used": bool(verification.get("fallback_used")),
            "display": verification.get("profile_display"),
        },
        "output_dir": str(resolved_output_dir),
        "render_engine": render_metadata["engine"],
        "evidence_source": evidence_source,
        "evidence_trust": evidence_trust["trust"],
        "evidence_authoritative": bool(evidence_trust["is_authoritative"]),
        "layout_decision_eligible": bool(evidence_trust["layout_decision_eligible"]),
        "requested_render_engine": renderer,
        "render_fallback_used": bool(render_metadata.get("fallback_used")),
        "render_warnings": render_warnings,
        "render_pdf_path": render_metadata.get("pdf_path"),
        "render_page_dir": render_metadata.get("page_dir"),
        "render_text_summary": render_text_summary,
        "page_count": len(page_images),
        "page_images": page_images,
        "render_findings": render_findings,
        "render_summary": render_summary,
        "layout_score": layout_score,
        "selected_scopes": verification.get("selected_scopes"),
        "overall_status": verification.get("overall_status"),
        "readiness": _classify_render_readiness(preflight, verification),
        "structure_readiness": verification.get("readiness"),
        "preflight_status": preflight.get("preflight_status"),
        "render_evidence_status": render_evidence_status,
        "wild_doc": wild_doc,
        "summary": {
            "page_count": len(page_images),
            "render_engine": render_metadata["engine"],
            "evidence_source": evidence_source,
            "evidence_trust": evidence_trust["trust"],
            "evidence_authoritative": bool(evidence_trust["is_authoritative"]),
            "layout_decision_eligible": bool(evidence_trust["layout_decision_eligible"]),
            "render_fallback_used": bool(render_metadata.get("fallback_used")),
            "preflight_status": preflight.get("preflight_status"),
            "wild_doc_detected": wild_doc["detected"],
            "wild_doc_signal_count": len(wild_doc["signals"]),
            "structure_readiness": verification.get("readiness"),
            "render_evidence_status": render_evidence_status,
            "render_finding_count": int(render_summary.get("finding_count") or 0),
            "render_highest_severity": render_summary.get("highest_severity"),
            "layout_score": layout_score.get("score"),
            "layout_penalty": layout_score.get("penalty"),
            "actionable_finding_count": int(render_summary.get("actionable_finding_count") or 0),
            "expected_blank_count": int(render_summary.get("expected_blank_count") or 0),
            "object_flow_issue_count": int(render_summary.get("object_flow_issue_count") or 0),
            "heading_break_issue_count": int(render_summary.get("heading_break_issue_count") or 0),
            "page_text_available_count": int(render_text_summary.get("page_text_available_count") or 0),
            "page_text_extraction_warning_count": int(render_text_summary.get("page_text_extraction_warning_count") or 0),
            "blank_page_count": int(render_summary.get("blank_page_count") or 0),
            "large_blank_count": int(render_summary.get("large_blank_count") or 0),
            "render_suspect_count": int(render_summary.get("render_suspect_count") or 0),
            "manual_review_rule_count": len(verification.get("manual_review_rule_ids") or []),
            "unsupported_rule_count": len(verification.get("unsupported_rule_ids") or []),
        },
        "manual_review_rule_ids": list(verification.get("manual_review_rule_ids") or []),
        "unsupported_rule_ids": list(verification.get("unsupported_rule_ids") or []),
        "review_items": _build_render_review_items(
            diagnostics,
            {
                **verification,
                "render_findings": render_findings,
            },
        ),
        "report_path": str(resolved_output_dir / "render_verify_report.json"),
    }
    Path(report["report_path"]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def render_render_verify_report(report: dict) -> str:
    lines = [
        f"文件: {report['document']['name']}",
        f"Profile: {report['profile'].get('display') or report['profile'].get('id') or 'default'}",
        f"渲染引擎: {report.get('render_engine')}",
        f"渲染证据来源: {report.get('evidence_source') or report.get('render_engine')}",
        f"渲染证据可信度: {report.get('evidence_trust') or 'unknown'}",
        f"版式决策可用: {'是' if report.get('layout_decision_eligible') else '否'}",
        f"结构状态: {report.get('overall_status')}",
        f"可提交状态: {report.get('readiness')}",
        f"预检状态: {report.get('preflight_status')}",
        f"渲染证据状态: {report.get('render_evidence_status')}",
        f"渲染证据目录: {report['output_dir']}",
        f"页图目录: {report.get('render_page_dir') or report['output_dir']}",
        f"生成页图: {report['page_count']} 页",
        f"报告文件: {report['report_path']}",
    ]
    if report.get("render_pdf_path"):
        lines.append(f"渲染 PDF: {report['render_pdf_path']}")
    layout_score = report.get("layout_score") or {}
    if layout_score.get("score") is not None:
        lines.append(f"Layout Score: {layout_score.get('score')} (penalty {layout_score.get('penalty', 0)})")
    render_text_summary = report.get("render_text_summary") or {}
    if render_text_summary.get("available"):
        lines.append(f"PDF文本页数: {render_text_summary.get('page_text_available_count', 0)}")
    if report.get("render_fallback_used"):
        lines.append("提示: Word PDF 渲染不可用，本次未获得可用于版式判断的权威证据。")
    for warning in report.get("render_warnings") or []:
        lines.append(f"渲染提示: {warning}")
    selected_scopes = report.get("selected_scopes")
    if selected_scopes:
        lines.append(f"复核范围: {', '.join(selected_scopes)}")

    render_findings = report.get("render_findings") or []
    if render_findings:
        lines.append("")
        lines.append("自动页图判读：")
        for finding in render_findings[:10]:
            region = finding.get("region") or {}
            region_text = f"x={region.get('x')}, y={region.get('y')}, w={region.get('w')}, h={region.get('h')}"
            lines.append(
                f"- 第 {finding.get('page')} 页 {finding.get('id')} [{finding.get('severity')}]: "
                f"{finding.get('message')} ({region_text})"
            )
        if len(render_findings) > 10:
            lines.append(f"- 另有 {len(render_findings) - 10} 条页图 finding，详见 JSON 报告。")

    wild_doc = report.get("wild_doc") or {}
    if wild_doc.get("detected"):
        lines.append("")
        lines.append("野生文档信号：")
        for signal in wild_doc.get("signals") or []:
            lines.append(f"- {signal['id']} [{signal['severity']}]: {signal['message']}")

    lines.append("")
    lines.append("复核清单：")
    for item in report.get("review_items") or []:
        lines.append(f"- {item}")
    return "\n".join(lines)
