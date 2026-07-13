from __future__ import annotations

import math
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Mapping

from _thesis_utils import build_document_model, build_style_map
from thesis_tool.render_bbox import normalized_evidence_bbox


MAX_ANCHORS = 5
MIN_ANCHOR_LENGTH = 12
ANCHOR_LENGTH = 48
TOC_ENTRY_END_RE = re.compile(r"(?:\t|[.．·•…_\-\u2010-\u2014\u2212]{2,})\s*\d{1,4}\s*$")
PAGE_HYPHENS = "\u002d\u2010\u2011\u2012\u2013\u2014\u2212"
PRINTED_PAGE_RE = re.compile(rf"^(?P<mark>[{PAGE_HYPHENS}])\s*(?P<page>\d{{1,4}})\s*(?P=mark)$")
TOC_PAGE_RE = re.compile(r"^(?P<title>.+?)[\s.．·•…_\-\u2010-\u2014\u2212]{2,}(?P<page>\d+)\s*$")


def _normalized_content(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[\W_]+", "", normalized)


def _document_paragraphs(input_docx: str | Path) -> list[str]:
    with zipfile.ZipFile(Path(input_docx).expanduser(), "r") as package:
        document_root = ET.fromstring(package.read("word/document.xml"))
        styles_root = ET.fromstring(package.read("word/styles.xml"))
    model = build_document_model(document_root, build_style_map(styles_root))
    return [
        node.text
        for node in model.paragraphs
        if node.container_section in {"abstract_cn", "abstract_en", "body", "backmatter"}
        and node.kind not in {"h1", "h2", "h3", "h4"}
    ]


def _anchor_candidates(input_docx: str | Path) -> list[str]:
    candidates = []
    seen = set()
    for paragraph in _document_paragraphs(input_docx):
        if TOC_ENTRY_END_RE.search(paragraph):
            continue
        normalized = _normalized_content(paragraph)
        if len(normalized) < MIN_ANCHOR_LENGTH:
            continue
        start = max(0, (len(normalized) - ANCHOR_LENGTH) // 2)
        anchor = normalized[start : start + ANCHOR_LENGTH]
        if anchor not in seen:
            candidates.append(anchor)
            seen.add(anchor)
    return candidates


def _distributed_anchors(candidates: list[str]) -> list[str]:
    if len(candidates) <= MAX_ANCHORS:
        return candidates
    last = len(candidates) - 1
    indices = [round(index * last / (MAX_ANCHORS - 1)) for index in range(MAX_ANCHORS)]
    return [candidates[index] for index in indices]


def verify_docx_pdf_content_match(
    input_docx: str | Path,
    page_texts: Mapping[int, str],
) -> dict:
    anchors = _distributed_anchors(_anchor_candidates(input_docx))
    pdf_content = _normalized_content("\n".join(str(text or "") for _, text in sorted(page_texts.items())))
    matched_count = sum(anchor in pdf_content for anchor in anchors)
    required_count = max(2, math.ceil(len(anchors) * 0.6)) if anchors else 2
    enough_evidence = len(anchors) >= 2 and bool(pdf_content)
    matched = enough_evidence and matched_count >= required_count
    status = "matched" if matched else "mismatch" if enough_evidence else "insufficient-evidence"
    return {
        "status": status,
        "matched": matched,
        "anchor_count": len(anchors),
        "matched_anchor_count": matched_count,
        "required_anchor_count": required_count,
    }


def _compact_heading_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[\s\u3000.．·•…_\-\u2010-\u2014\u2212]+", "", normalized).strip()


def _is_probable_toc_page(text: str) -> bool:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return False
    head = _compact_heading_text("\n".join(lines[:5]))
    return "目录" in head or "contents" in head


def _looks_like_toc_entry_title(title: str) -> bool:
    normalized = str(title or "").strip()
    compact = _compact_heading_text(normalized)
    if not compact or compact in {"目录", "contents"}:
        return False
    matchable = re.sub(r"[\s\u3000]+", "", normalized)
    return bool(
        re.match(r"^(第?\d+|[一二三四五六七八九十]+[、.．]|绪论|结论|参考文献|致谢|附录)", matchable, re.IGNORECASE)
    )


def _parse_toc_line(line: str) -> dict | None:
    normalized = re.sub(r"\s+", " ", str(line or "").strip())
    if not normalized:
        return None
    match = TOC_PAGE_RE.match(normalized)
    if match:
        title = match.group("title").strip()
        return {"title": title, "declared_page": int(match.group("page"))} if _looks_like_toc_entry_title(title) else None
    return {"title": normalized, "declared_page": None} if _looks_like_toc_entry_title(normalized) else None


def _extract_toc_entries_from_page_texts(page_texts: Mapping[int, str]) -> list[dict]:
    entries: list[dict] = []
    in_toc = False
    for page_number, text in sorted(page_texts.items()):
        probable_toc_page = _is_probable_toc_page(text)
        page_entries = [
            entry
            for line in str(text or "").splitlines()
            if (entry := _parse_toc_line(line)) is not None
        ]
        if probable_toc_page:
            in_toc = True
        elif not in_toc:
            continue
        elif not any(entry.get("declared_page") is not None for entry in page_entries):
            break
        entries.extend({"toc_page": int(page_number), **entry} for entry in page_entries)
    return entries


def _find_heading_page(page_texts: Mapping[int, str], title: str, *, after_page: int) -> int | None:
    target = _compact_heading_text(title)
    if not target:
        return None
    for page_number, text in sorted(page_texts.items()):
        if int(page_number) <= after_page:
            continue
        if any(_compact_heading_text(line) == target for line in str(text or "").splitlines()):
            return int(page_number)
    return None


def _extract_printed_page_number(page_text: str) -> int | None:
    lines = [line.strip() for line in str(page_text or "").splitlines() if line.strip()]
    for line in reversed(lines[-5:]):
        match = PRINTED_PAGE_RE.fullmatch(line)
        if match:
            return int(match.group("page"))
    return None


def _toc_entry_line_bbox(entry: dict, line_boxes_by_page: Mapping[int, list[dict]]) -> dict | None:
    target = _compact_heading_text(entry.get("title"))
    declared_page = entry.get("declared_page")
    matches = []
    for line in line_boxes_by_page.get(int(entry["toc_page"]), []):
        parsed_line = _parse_toc_line(line.get("text"))
        if parsed_line is None or _compact_heading_text(parsed_line["title"]) != target:
            continue
        if declared_page is not None and parsed_line.get("declared_page") != declared_page:
            continue
        bbox = normalized_evidence_bbox(line.get("bbox"))
        if bbox is not None:
            matches.append(bbox)
    return matches[0] if len(matches) == 1 else None


def _unconfirmed_finding(entry: dict, *, actual_pdf_page: int | None, actual_page: int | None) -> dict:
    title = entry["title"]
    declared_page = entry.get("declared_page")
    if declared_page is None:
        message = f"目录条目“{title}”缺少页码，需人工复核。"
        action = "回到 DOCX 检查目录条目的页码显示后重新导出 PDF。"
    else:
        message = (
            f"目录条目“{title}”已定位到 PDF 第 {actual_pdf_page} 页，但未读取到该页显示页码，需人工复核。"
            if actual_pdf_page is not None
            else f"目录条目“{title}”未能在后续 PDF 页面中确认对应标题，需人工复核。"
        )
        action = "打开 PDF 对照目录和正文标题页码。"
    return {
        "id": "toc_page_number_unconfirmed",
        "rule_id": "render.toc_page_number_unconfirmed",
        "classification": "render_integrity",
        "severity": "warning",
        "page": entry["toc_page"],
        "toc_entry": title,
        "declared_page": declared_page,
        "actual_page": actual_page,
        "message": message,
        "actionable": False,
        "suggested_scope": "toc",
        "suggested_action": action,
    }


def build_toc_page_number_findings(
    page_texts: Mapping[int, str],
    *,
    line_boxes_by_page: Mapping[int, list[dict]] | None = None,
) -> list[dict]:
    findings: list[dict] = []
    for entry in _extract_toc_entries_from_page_texts(page_texts):
        actual_pdf_page = _find_heading_page(page_texts, entry["title"], after_page=int(entry["toc_page"]))
        actual_page = _extract_printed_page_number(page_texts.get(actual_pdf_page, "")) if actual_pdf_page else None
        if entry.get("declared_page") is None or actual_page is None:
            finding = _unconfirmed_finding(entry, actual_pdf_page=actual_pdf_page, actual_page=actual_page)
        elif entry["declared_page"] != actual_page:
            finding = {
                "id": "toc_page_number_mismatch",
                "rule_id": "render.toc_page_number_mismatch",
                "classification": "render_integrity",
                "severity": "warning",
                "page": entry["toc_page"],
                "toc_entry": entry["title"],
                "declared_page": entry["declared_page"],
                "actual_page": actual_page,
                "message": f"目录页码不一致：目录条目“{entry['title']}”标为第 {entry['declared_page']} 页，正文标题位于第 {actual_page} 页。",
                "actionable": True,
                "suggested_scope": "toc",
                "suggested_action": "回到 DOCX 更新目录页码后重新导出 PDF。",
            }
        else:
            continue
        line_bbox = _toc_entry_line_bbox(entry, line_boxes_by_page or {})
        if line_bbox is not None:
            finding["bbox"] = line_bbox
        findings.append(finding)
    return findings


def render_summary_with_findings(render_summary: dict, render_findings: list[dict]) -> dict:
    summary = dict(render_summary or {})
    for obsolete_key in ("large_blank_count", "large_blank_bottom_count", "large_blank_middle_count"):
        summary.pop(obsolete_key, None)
    summary["finding_count"] = len(render_findings)
    severity_rank = {"info": 0, "warning": 1, "error": 2, "blocker": 3}
    highest = max(
        (str(finding.get("severity") or "info") for finding in render_findings),
        key=lambda severity: severity_rank.get(severity, 0),
        default=None,
    )
    summary["highest_severity"] = highest
    summary["actionable_finding_count"] = sum(1 for finding in render_findings if finding.get("actionable"))
    for finding_id in ("toc_page_number_mismatch", "toc_page_number_unconfirmed", "isolated_punctuation"):
        summary[f"{finding_id}_count"] = sum(1 for finding in render_findings if finding.get("id") == finding_id)
    return summary
