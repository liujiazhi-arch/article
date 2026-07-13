from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from thesis_tool.toc_finalize import finalize_static_toc
from thesis_tool.render_toc_evidence import verify_docx_pdf_content_match


TOC_ISSUE_IDS = {"toc_page_number_mismatch", "toc_page_number_unconfirmed"}


def _has_toc_issue(findings: list[dict]) -> bool:
    return any(finding.get("id") in TOC_ISSUE_IDS for finding in findings)


def build_static_toc_finalization(
    input_docx: str | Path,
    output_dir: str | Path,
    page_texts: Mapping[int, str],
    *,
    requested: bool,
    pdf_matches_docx_confirmed: bool,
    toc_findings: list[dict],
    finalize_fn: Callable = finalize_static_toc,
) -> dict:
    if not requested:
        return {
            "status": "not-requested",
            "available": False,
            "message": "本次只完成 PDF 复核",
            "next_action": "需要时再生成静态目录版",
        }
    if not pdf_matches_docx_confirmed:
        return {
            "status": "blocked",
            "available": False,
            "message": "请先确认 PDF 与当前论文来自同一版本",
            "next_action": "确认后重新复核 PDF",
        }
    if not _has_toc_issue(toc_findings):
        return {
            "status": "not-needed",
            "available": False,
            "message": "当前 PDF 没有发现目录页码问题",
            "next_action": "无需生成静态目录版",
        }

    try:
        content_match = verify_docx_pdf_content_match(input_docx, page_texts)
    except Exception as exc:
        return {
            "status": "unavailable",
            "available": False,
            "reason": "content-verification-error",
            "message": "无法确认 PDF 与当前论文内容对应 静态目录不可生成",
            "detail": str(exc),
            "next_action": "请确认文件可正常打开后重新复核 PDF",
        }
    if not content_match["matched"]:
        reason = "content-mismatch" if content_match["status"] == "mismatch" else "content-unverified"
        return {
            "status": "blocked",
            "available": False,
            "reason": reason,
            "content_match": content_match,
            "message": "PDF 与当前论文的正文证据不一致 静态目录不可生成",
            "next_action": "请重新选择由当前论文导出的 PDF",
        }

    output_path = (Path(output_dir).expanduser() / "static_toc.docx").resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = finalize_fn(input_docx, output_path, page_texts)
    except Exception as exc:
        return {
            "status": "unavailable",
            "available": False,
            "reason": "finalization-error",
            "content_match": content_match,
            "output_path": None,
            "message": "当前文档结构不支持自动生成 静态目录不可生成 PDF 复核结果仍可使用",
            "detail": str(exc),
            "next_action": "请在 Word 或 WPS 中人工确认目录",
        }
    if result.get("written") and result.get("complete"):
        return {
            **result,
            "content_match": content_match,
            "status": "generated",
            "available": True,
            "output_path": str(output_path),
            "message": "静态目录版已生成",
            "next_action": "下载后重新导出 PDF 并再次复核",
        }
    return {
        **result,
        "content_match": content_match,
        "status": "incomplete",
        "available": False,
        "output_path": None,
        "message": "目录与正文没有完整对应 本次不会写入文件",
        "next_action": "请在 Word 或 WPS 中人工确认目录",
    }
