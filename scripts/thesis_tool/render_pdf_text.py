from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from thesis_tool.render_bbox import bbox_punctuation_lines, merge_same_baseline_punctuation


def _empty_render_text_summary(*, source: str | None = None, warnings: list[str] | None = None) -> dict:
    warning_list = list(warnings or [])
    return {
        "source": source,
        "available": False,
        "page_text_available_count": 0,
        "page_text_extraction_warning_count": len(warning_list),
        "warnings": warning_list,
    }


def extract_pdf_page_texts(
    pdf_path: str | None,
    *,
    page_count: int | None = None,
    find_pdftotext: Callable[[], str],
    extract_with_pdfium: Callable,
    run: Callable = subprocess.run,
) -> tuple[dict[int, str], dict]:
    if not pdf_path:
        return {}, _empty_render_text_summary(source=None)
    resolved_pdf = Path(pdf_path).expanduser().resolve()
    if not resolved_pdf.exists():
        return {}, _empty_render_text_summary(source="pdf", warnings=[f"PDF 不存在，未抽取页文本: {resolved_pdf}"])

    try:
        pdftotext = find_pdftotext()
        completed = run(
            [pdftotext, "-layout", str(resolved_pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (RuntimeError, subprocess.CalledProcessError) as poppler_error:
        try:
            raw_pages = extract_with_pdfium(resolved_pdf)
        except Exception as pdfium_error:
            return {}, _empty_render_text_summary(
                source="pdf",
                warnings=[str(poppler_error), str(pdfium_error)],
            )
    else:
        raw_pages = str(completed.stdout or "").split("\f")
        if raw_pages and raw_pages[-1] == "":
            raw_pages = raw_pages[:-1]
        try:
            bbox_completed = run(
                [pdftotext, "-bbox-layout", str(resolved_pdf), "-"],
                check=True,
                capture_output=True,
                text=True,
            )
            bbox_pages = bbox_punctuation_lines(str(bbox_completed.stdout or ""))
        except (subprocess.CalledProcessError, ET.ParseError):
            bbox_pages = []
        raw_pages = [
            merge_same_baseline_punctuation(text, bbox_pages[index] if index < len(bbox_pages) else [])
            for index, text in enumerate(raw_pages)
        ]

    selected_pages = raw_pages[:page_count] if page_count is not None else raw_pages
    page_texts = {index: text.strip() for index, text in enumerate(selected_pages, start=1) if text.strip()}
    warnings: list[str] = []
    if page_count is not None and page_count > 0 and len(raw_pages) != page_count:
        warnings.append(f"PDF 文本页数 {len(raw_pages)} 与页图页数 {page_count} 不一致，已按可用页文本继续。")
    return page_texts, {
        "source": "pdf",
        "available": bool(page_texts),
        "page_text_available_count": len(page_texts),
        "page_text_extraction_warning_count": len(warnings),
        "warnings": warnings,
    }
