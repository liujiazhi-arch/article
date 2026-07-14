from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from math import isfinite
from pathlib import Path

from thesis_tool.render_analyzer import ISOLATED_PUNCTUATION_RE


DEFAULT_RENDER_EVIDENCE_NEXT_ACTION = "回到 DOCX 调整对应版式问题后重新导出 PDF。"
RENDER_EVIDENCE_RULE_BY_CLASSIFICATION = {
    "suspicious_object_flow": "render.object_flow",
    "suspicious_heading_break": "render.heading_break",
    "expected_chapter_break": "render.expected_chapter_break",
    "render_integrity": "render.integrity",
}
TEXT_TARGET_FIELD_BY_RULE = {
    "render.isolated_punctuation": "punctuation",
    "render.formula_number_split_page": "formula_number",
    "render.heading_orphan_at_page_bottom": "heading_text",
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


def normalized_text_spans(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    spans = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        bbox = normalized_evidence_bbox(item.get("bbox"))
        if text and bbox is not None:
            spans.append({"text": text, "bbox": bbox})
    return spans


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


def _compact_match_text(value) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", normalized).strip()


def _text_target(finding: dict) -> tuple[int, str, str] | None:
    field = TEXT_TARGET_FIELD_BY_RULE.get(str(finding.get("rule_id") or ""))
    page = _coerce_positive_page(finding.get("page") or finding.get("page_number"))
    text = str(finding.get(field) or "").strip() if field else ""
    compact = _compact_match_text(text)
    return (page, compact, text) if page is not None and compact else None


def _line_candidates(line_boxes_by_page: dict[int, list[dict]]) -> dict[tuple[int, str], list[dict]]:
    candidates: dict[tuple[int, str], list[dict]] = {}
    for page, lines in line_boxes_by_page.items():
        for line in lines if isinstance(lines, list) else []:
            if not isinstance(line, dict):
                continue
            compact = _compact_match_text(line.get("text"))
            bbox = normalized_evidence_bbox(line.get("bbox"))
            if compact and bbox is not None and bbox not in candidates.setdefault((int(page), compact), []):
                candidates[(int(page), compact)].append(bbox)
    return candidates


def attach_text_line_spans(findings: list[dict], line_boxes_by_page: dict[int, list[dict]]) -> list[dict]:
    resolved = [dict(finding) for finding in findings]
    groups: dict[tuple[int, str], list[tuple[int, str]]] = {}
    for index, finding in enumerate(resolved):
        target = _text_target(finding)
        if target is not None:
            page, compact, text = target
            groups.setdefault((page, compact), []).append((index, text))
    candidates = _line_candidates(line_boxes_by_page)
    for key, targets in groups.items():
        boxes = candidates.get(key, [])
        for index, text in targets:
            resolved[index]["bbox"] = None
            resolved[index].pop("text_spans", None)
        if len(boxes) != 1 or len(targets) != 1:
            continue
        index, text = targets[0]
        bbox = boxes[0]
        resolved[index]["bbox"] = dict(bbox)
        resolved[index]["text_spans"] = [{"text": text, "bbox": dict(bbox)}]
    return resolved


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
        item = {
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
        text_spans = normalized_text_spans(finding.get("text_spans"))
        if text_spans:
            item["text_spans"] = text_spans
        evidence_items.append(item)
    return evidence_items
