from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import audit_thesis

from thesis_tool.workflow import (
    PREFLIGHT_BLOCKED,
    PREFLIGHT_WARNING,
    READINESS_RENDER_CHECK_REQUIRED,
    READINESS_STRUCTURE_READY,
    build_document_diagnostics,
    build_document_preflight,
    build_scope_verify,
)


_RENDER_DOCX_SCRIPT_GLOBS = [
    "~/.codex/plugins/cache/openai-primary-runtime/documents/*/skills/documents/render_docx.py",
]
_RENDER_PYTHON_GLOBS = [
    "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
    "~/.cache/codex-runtimes/codex-primary-runtime-*/dependencies/python/bin/python3",
]
RENDERER_AUTO = "auto"
RENDERER_WORD_PDF = "word-pdf"
RENDERER_ARTIFACT_TOOL = "artifact-tool"
SUPPORTED_RENDERERS = {RENDERER_AUTO, RENDERER_WORD_PDF, RENDERER_ARTIFACT_TOOL}


def find_render_docx_script() -> str:
    env_path = os.environ.get("ARTICLE_RENDER_DOCX_SCRIPT")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)

    for pattern in _RENDER_DOCX_SCRIPT_GLOBS:
        for candidate in sorted(glob.glob(os.path.expanduser(pattern))):
            resolved = Path(candidate).expanduser().resolve()
            if resolved.exists():
                return str(resolved)

    raise RuntimeError(
        "未找到 render_docx.py。请确认当前 Codex 文档运行时已安装，"
        "或通过 ARTICLE_RENDER_DOCX_SCRIPT 指定渲染脚本路径。"
    )


def default_render_output_dir(input_docx: str) -> str:
    source = Path(input_docx).expanduser().resolve()
    return str(source.with_name(f"{source.stem}_render_verify"))


def find_render_python() -> str:
    env_path = os.environ.get("ARTICLE_RENDER_PYTHON")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)

    for pattern in _RENDER_PYTHON_GLOBS:
        for candidate in sorted(glob.glob(os.path.expanduser(pattern))):
            resolved = Path(candidate).expanduser().resolve()
            if resolved.exists():
                return str(resolved)

    return sys.executable


def _page_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"page-(\d+)\.png$", path.name)
    if match:
        return int(match.group(1)), path.name
    return sys.maxsize, path.name


def _collect_page_images(output_dir: str | Path) -> list[str]:
    directory = Path(output_dir).expanduser().resolve()
    return [str(path) for path in sorted(directory.glob("page-*.png"), key=_page_sort_key)]


def _run_render_docx(input_docx: str, output_dir: str) -> dict:
    script_path = find_render_docx_script()
    python_path = find_render_python()
    command = [
        python_path,
        script_path,
        input_docx,
        "--output_dir",
        output_dir,
        "--renderer",
        "artifact-tool",
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "DOCX 渲染失败。"
        if details:
            message = f"{message}\n{details}"
        raise RuntimeError(message) from exc
    return {
        "engine": RENDERER_ARTIFACT_TOOL,
        "page_dir": str(Path(output_dir).expanduser().resolve()),
        "pdf_path": None,
        "fallback_used": False,
        "warnings": [],
    }


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
  tell application "Microsoft Word"
    open inputPath
    set activePath to POSIX path of (full name of active document as alias)
    if activePath is not expectedPath then
      error "Microsoft Word opened a different active document: " & activePath
    end if
    save as active document file name outputPath file format format PDF
  end tell
end run
"""
    try:
        subprocess.run(
            ["osascript", "-e", script, str(Path(input_docx).expanduser().resolve()), str(Path(output_pdf).expanduser().resolve())],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Microsoft Word 导出 PDF 超时。") from exc
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
    if renderer == RENDERER_WORD_PDF:
        return _run_word_pdf_render(input_docx, output_dir)
    if renderer == RENDERER_ARTIFACT_TOOL:
        return _run_render_docx(input_docx, output_dir)

    try:
        return _run_word_pdf_render(input_docx, output_dir)
    except RuntimeError as exc:
        metadata = _run_render_docx(input_docx, output_dir)
        metadata["fallback_used"] = True
        metadata["requested_engine"] = RENDERER_AUTO
        metadata["warnings"] = [f"Word PDF 渲染不可用，已回退 artifact-tool: {exc}"]
        return metadata


def _build_render_review_items(diagnostics: dict, verification: dict) -> list[str]:
    items = [
        "逐页检查是否出现异常大块空白、孤页或空白段。",
        "逐页检查图表是否与题注分离，是否被挤到单独页面。",
        "逐页检查公式区域是否出现粗横线、编号偏移或解释项错位。",
    ]

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


def _classify_render_evidence_status(*, page_count: int, preflight: dict, verification: dict) -> str:
    if page_count <= 0:
        return "render-failed"
    if preflight.get("preflight_status") == PREFLIGHT_BLOCKED:
        return "blocked-by-wild-doc"
    if verification.get("readiness") != READINESS_STRUCTURE_READY:
        return "structure-not-ready"
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
) -> dict:
    validated_input = audit_thesis.validate_docx_path(input_docx)
    resolved_output_dir = Path(output_dir or default_render_output_dir(validated_input)).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    render_metadata = _run_render_engine(validated_input, str(resolved_output_dir), renderer)
    page_images = _collect_page_images(render_metadata["page_dir"])
    if not page_images:
        raise RuntimeError(f"渲染未产出页图: {render_metadata['page_dir']}")

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
    )
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
        "requested_render_engine": renderer,
        "render_fallback_used": bool(render_metadata.get("fallback_used")),
        "render_warnings": list(render_metadata.get("warnings") or []),
        "render_pdf_path": render_metadata.get("pdf_path"),
        "render_page_dir": render_metadata.get("page_dir"),
        "page_count": len(page_images),
        "page_images": page_images,
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
            "render_fallback_used": bool(render_metadata.get("fallback_used")),
            "preflight_status": preflight.get("preflight_status"),
            "wild_doc_detected": wild_doc["detected"],
            "wild_doc_signal_count": len(wild_doc["signals"]),
            "structure_readiness": verification.get("readiness"),
            "render_evidence_status": render_evidence_status,
            "manual_review_rule_count": len(verification.get("manual_review_rule_ids") or []),
            "unsupported_rule_count": len(verification.get("unsupported_rule_ids") or []),
        },
        "manual_review_rule_ids": list(verification.get("manual_review_rule_ids") or []),
        "unsupported_rule_ids": list(verification.get("unsupported_rule_ids") or []),
        "review_items": _build_render_review_items(diagnostics, verification),
        "report_path": str(resolved_output_dir / "render_verify_report.json"),
    }
    Path(report["report_path"]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def render_render_verify_report(report: dict) -> str:
    lines = [
        f"文件: {report['document']['name']}",
        f"Profile: {report['profile'].get('display') or report['profile'].get('id') or 'default'}",
        f"渲染引擎: {report.get('render_engine')}",
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
        lines.append(f"Word PDF: {report['render_pdf_path']}")
    if report.get("render_fallback_used"):
        lines.append("提示: Word PDF 渲染不可用，本次已回退 artifact-tool。")
    for warning in report.get("render_warnings") or []:
        lines.append(f"渲染提示: {warning}")
    selected_scopes = report.get("selected_scopes")
    if selected_scopes:
        lines.append(f"复核范围: {', '.join(selected_scopes)}")

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
