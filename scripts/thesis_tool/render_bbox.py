from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from math import isfinite
from pathlib import Path
from typing import Callable

from thesis_tool.render_analyzer import ISOLATED_PUNCTUATION_RE


DEFAULT_RENDER_EVIDENCE_NEXT_ACTION = "回到 DOCX 调整对应版式问题后重新导出 PDF。"
RENDER_EVIDENCE_RULE_BY_CLASSIFICATION = {
    "suspicious_object_flow": "render.object_flow",
    "suspicious_heading_break": "render.heading_break",
    "expected_chapter_break": "render.expected_chapter_break",
    "render_integrity": "render.integrity",
}


def _same_visual_baseline(punctuation: dict, candidate: dict) -> bool:
    overlap = min(punctuation["y_max"], candidate["y_max"]) - max(punctuation["y_min"], candidate["y_min"])
    min_height = min(
        punctuation["y_max"] - punctuation["y_min"],
        candidate["y_max"] - candidate["y_min"],
    )
    candidate_is_left = candidate["x_min"] < punctuation["x_min"] and candidate["x_max"] <= punctuation["x_max"] + 2.0
    horizontal_gap = max(punctuation["x_min"] - candidate["x_max"], 0.0)
    punctuation_width = punctuation["x_max"] - punctuation["x_min"]
    return (
        candidate_is_left
        and min_height > 0
        and overlap / min_height >= 0.5
        and horizontal_gap <= max(2.0, punctuation_width)
    )


def _raw_bbox_page_lines(raw_bbox: str) -> list[list[dict]]:
    root = ET.fromstring(raw_bbox)
    pages: list[list[dict]] = []
    for page in (element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "page"):
        try:
            page_width = float(page.attrib["width"])
            page_height = float(page.attrib["height"])
        except (KeyError, ValueError):
            pages.append([])
            continue
        if page_width <= 0 or page_height <= 0:
            pages.append([])
            continue

        lines = []
        for element in page.iter():
            if element.tag.rsplit("}", 1)[-1] != "line":
                continue
            try:
                x_min = float(element.attrib["xMin"])
                x_max = float(element.attrib["xMax"])
                y_min = float(element.attrib["yMin"])
                y_max = float(element.attrib["yMax"])
            except (KeyError, ValueError):
                continue
            if x_max <= x_min or y_max <= y_min:
                continue
            lines.append(
                {
                    "text": "".join(part.strip() for part in element.itertext() if part.strip()),
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_min,
                    "y_max": y_max,
                    "bbox": {
                        "x": x_min / page_width,
                        "y": y_min / page_height,
                        "w": (x_max - x_min) / page_width,
                        "h": (y_max - y_min) / page_height,
                    },
                }
            )
        lines.sort(key=lambda line: (line["y_min"], line["x_min"]))
        pages.append(lines)
    return pages


def bbox_page_lines(raw_bbox: str) -> dict[int, list[dict]]:
    return {
        page_number: [{"text": line["text"], "bbox": line["bbox"]} for line in lines]
        for page_number, lines in enumerate(_raw_bbox_page_lines(raw_bbox), start=1)
    }


def bbox_punctuation_lines(raw_bbox: str) -> list[list[tuple[str, bool]]]:
    pages: list[list[tuple[str, bool]]] = []
    for lines in _raw_bbox_page_lines(raw_bbox):
        punctuation_lines = []
        for line in lines:
            if not ISOLATED_PUNCTUATION_RE.fullmatch(line["text"]):
                continue
            attached = any(
                other is not line
                and not ISOLATED_PUNCTUATION_RE.fullmatch(other["text"])
                and _same_visual_baseline(line, other)
                for other in lines
            )
            punctuation_lines.append((line["text"], attached))
        pages.append(punctuation_lines)
    return pages


def extract_pdf_line_boxes(
    pdf_path: str | None,
    *,
    find_pdftotext: Callable[[], str],
    run: Callable = subprocess.run,
) -> dict[int, list[dict]]:
    if not pdf_path:
        return {}
    resolved_pdf = Path(pdf_path).expanduser().resolve()
    if not resolved_pdf.exists():
        return {}
    try:
        completed = run(
            [find_pdftotext(), "-bbox-layout", str(resolved_pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return bbox_page_lines(str(completed.stdout or ""))
    except (RuntimeError, subprocess.CalledProcessError, ET.ParseError):
        return {}


def merge_same_baseline_punctuation(page_text: str, bbox_lines: list[tuple[str, bool]]) -> str:
    merged_lines: list[str] = []
    punctuation_index = 0
    for raw_line in str(page_text or "").splitlines():
        punctuation = raw_line.strip()
        if ISOLATED_PUNCTUATION_RE.fullmatch(punctuation):
            bbox_line = bbox_lines[punctuation_index] if punctuation_index < len(bbox_lines) else None
            punctuation_index += 1
            if bbox_line == (punctuation, True):
                for previous_index in range(len(merged_lines) - 1, -1, -1):
                    if merged_lines[previous_index].strip():
                        merged_lines[previous_index] = merged_lines[previous_index].rstrip() + punctuation
                        break
                else:
                    merged_lines.append(raw_line)
                continue
        merged_lines.append(raw_line)
    return "\n".join(merged_lines)


def normalized_evidence_bbox(value) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, float] = {}
    for key in ("x", "y", "w", "h"):
        raw_value = value.get(key)
        if isinstance(raw_value, bool):
            return None
        try:
            number = float(raw_value)
        except (TypeError, ValueError):
            return None
        if not isfinite(number) or number < 0 or number > 1:
            return None
        normalized[key] = number
    if normalized["w"] <= 0 or normalized["h"] <= 0:
        return None
    if normalized["x"] + normalized["w"] > 1.000001 or normalized["y"] + normalized["h"] > 1.000001:
        return None
    return normalized


def _coerce_positive_page(value) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def _render_evidence_rule_id(finding: dict) -> str:
    explicit_rule_id = str(finding.get("rule_id") or "").strip()
    if explicit_rule_id:
        return explicit_rule_id
    classification = str(finding.get("classification") or "").strip()
    if classification in RENDER_EVIDENCE_RULE_BY_CLASSIFICATION:
        return RENDER_EVIDENCE_RULE_BY_CLASSIFICATION[classification]
    finding_id = str(finding.get("id") or finding.get("type") or "finding").strip() or "finding"
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", finding_id).strip("_.-") or "finding"
    return safe_id if safe_id.startswith("render.") else f"render.{safe_id}"


def _resolved_screenshot_path(finding: dict, page_images_by_page: dict[int, str]) -> str | None:
    screenshot_path = finding.get("screenshot_path") or finding.get("image_path")
    if not screenshot_path:
        page = _coerce_positive_page(finding.get("page") or finding.get("page_number"))
        screenshot_path = page_images_by_page.get(page) if page is not None else None
    if not screenshot_path:
        return None
    resolved = Path(str(screenshot_path)).expanduser().resolve()
    if not resolved.is_file() or resolved.suffix.lower() != ".png":
        return None
    return str(resolved)


def build_evidence_items(render_findings: list[dict], *, page_images: list[str]) -> list[dict]:
    page_images_by_page = {index: image_path for index, image_path in enumerate(page_images, start=1)}
    evidence_items: list[dict] = []
    for finding in render_findings:
        if not isinstance(finding, dict):
            continue
        page = _coerce_positive_page(finding.get("page") or finding.get("page_number"))
        evidence_items.append(
            {
                "page": page,
                "screenshot_path": _resolved_screenshot_path(finding, page_images_by_page),
                "rule_id": _render_evidence_rule_id(finding),
                "bbox": normalized_evidence_bbox(finding.get("bbox")),
                "message": str(finding.get("message") or finding.get("detail") or "需要打开 PDF 对照页面确认。"),
                "severity": str(finding.get("severity") or "info"),
                "next_action": str(
                    finding.get("next_action")
                    or finding.get("suggested_action")
                    or DEFAULT_RENDER_EVIDENCE_NEXT_ACTION
                ),
                "suggested_scope": finding.get("suggested_scope"),
                "fix_mode": str(finding.get("fix_mode") or "manual"),
            }
        )
    return evidence_items
