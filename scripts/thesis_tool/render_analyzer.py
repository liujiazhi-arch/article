from __future__ import annotations

import re

from thesis_tool import render_image_metrics

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "blocker": 3}
WHITE_LUMA_THRESHOLD = render_image_metrics.WHITE_LUMA_THRESHOLD
PageImageMetrics = render_image_metrics.PageImageMetrics
ISOLATED_PUNCTUATION_RE = re.compile(r"^[，。；、：！？]+$")
FORMULA_NUMBER_LINE_RE = re.compile(r"^[（(]\s*\d+(?:[.\-]\d+)*\s*[)）]$")
FORMULA_CONTEXT_RE = re.compile(r"(=|×|÷|≤|≥|≈|∑|∫|[A-Za-zΑ-Ωα-ω]\w*\s*[+\-*/=])")
HEADING_LINE_RE = re.compile(r"^(?:第\s*\d+\s*[章节]|[1-9]\d*(?:\.\d+){0,3})\s+\S+")

_read_with_pillow = render_image_metrics.read_with_pillow
_read_png_metrics = render_image_metrics.read_png_metrics
_white_png_row = render_image_metrics.white_png_row
_decode_png = render_image_metrics.decode_png
_unfilter_png_row = render_image_metrics.unfilter_png_row
_paeth = render_image_metrics.paeth
_iter_png_pixels = render_image_metrics.iter_png_pixels
_sample_to_byte = render_image_metrics.sample_to_byte
_is_ink = render_image_metrics.is_ink
_Bbox = render_image_metrics._Bbox


def analyze_page_images(
    page_images: list[str],
    *,
    evidence_source: str | None = None,
    page_texts: dict[int, str] | None = None,
) -> dict:
    return analyze_render_pages(page_images, evidence_source=evidence_source, page_texts=page_texts)


def analyze_render_pages(
    page_images: list[str],
    *,
    evidence_source: str | None = None,
    page_texts: dict[int, str] | None = None,
) -> dict:
    findings: list[dict] = []
    failed_page_count = 0
    page_texts = page_texts or {}
    page_metrics: dict[int, PageImageMetrics] = {}
    page_image_by_number: dict[int, str] = {}

    for page_number, image_path in enumerate(page_images, start=1):
        page_image_by_number[page_number] = image_path
        try:
            metrics = _read_page_image_metrics(image_path)
            page_metrics[page_number] = metrics
        except Exception as exc:
            failed_page_count += 1
            findings.append(
                _finding(
                    "render_suspect",
                    "error",
                    page_number,
                    {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
                    f"页图无法解析，疑似渲染输出异常: {exc}",
                    "rendering",
                    evidence_source,
                    image_path,
                )
            )
            continue

        raw_findings = _analyze_page_metrics(metrics, page_number, image_path, evidence_source)
        raw_findings.extend(
            _detect_isolated_punctuation_lines(
                page_texts.get(page_number, ""),
                page_number,
                image_path,
                evidence_source,
            )
        )
        for finding in raw_findings:
            if finding.get("id") == "large_blank_region":
                continue
            findings.append(
                _classify_finding_context(
                    finding,
                    page_text=page_texts.get(page_number, ""),
                    next_page_text=page_texts.get(page_number + 1, ""),
                )
            )

    findings.extend(_detect_formula_number_split_pages(page_texts, page_image_by_number, evidence_source))
    findings.extend(_detect_heading_orphan_pages(page_texts, page_metrics, page_image_by_number, evidence_source))

    summary = _summarize_findings(findings)
    layout_score = _build_layout_score(summary)
    summary.update(
        {
            "page_count": len(page_images),
            "analyzed_page_count": len(page_images) - failed_page_count,
            "failed_page_count": failed_page_count,
            "evidence_source": evidence_source,
        }
    )
    return {"findings": findings, "summary": summary, "layout_score": layout_score}


def _classify_finding_context(finding: dict, *, page_text: str, next_page_text: str) -> dict:
    finding.setdefault("classification", "render_integrity")
    finding.setdefault("confidence", 0.9)
    finding.setdefault("actionable", True)
    finding.setdefault("reason", finding.get("message") or "")
    finding.setdefault("suggested_action", "检查渲染器输出或重新导出 PDF/页图。")
    return finding


def _analyze_page_metrics(
    metrics: PageImageMetrics,
    page_number: int,
    image_path: str,
    evidence_source: str | None,
) -> list[dict]:
    findings: list[dict] = []

    if metrics.ink_ratio <= 0.0005:
        return [
            _finding(
                "blank_page",
                "warning",
                page_number,
                {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
                "页面几乎为空白，疑似空白页或渲染失败。",
                "rendering",
                evidence_source,
                image_path,
            )
        ]

    render_suspect = metrics.ink_ratio <= 0.003 or metrics.content_area_ratio <= 0.02
    if render_suspect:
        findings.append(
            _finding(
                "render_suspect",
                "warning",
                page_number,
                _bbox_region(metrics),
                "页面内容区域极小，疑似渲染失败或只有孤立内容。",
                "rendering",
                evidence_source,
                image_path,
            )
        )

    return findings


def _detect_isolated_punctuation_lines(
    page_text: str,
    page_number: int,
    image_path: str,
    evidence_source: str | None,
) -> list[dict]:
    findings: list[dict] = []
    for line_number, raw_line in enumerate(str(page_text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not ISOLATED_PUNCTUATION_RE.match(line):
            continue
        finding = _finding(
            "isolated_punctuation",
            "warning",
            page_number,
            {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
            "页面文本存在单独成行的标点，疑似换行或排版挤压导致。",
            "formatting",
            evidence_source,
            image_path,
        )
        finding.update(
            {
                "rule_id": "render.isolated_punctuation",
                "classification": "render_text_flow",
                "confidence": 0.86,
                "actionable": True,
                "reason": "PDF 文本层出现单独成行的中文标点。",
                "suggested_action": "回到 WPS/Word 检查该处换行、字距和段落排版，调整后重新导出 PDF。",
                "line_number": line_number,
                "punctuation": line,
            }
        )
        findings.append(finding)
    return findings


def _nonempty_lines(page_text: str) -> list[str]:
    return [line.strip() for line in str(page_text or "").splitlines() if line.strip()]


def _detect_formula_number_split_pages(
    page_texts: dict[int, str],
    page_image_by_number: dict[int, str],
    evidence_source: str | None,
) -> list[dict]:
    findings = []
    for page_number in sorted(page_texts):
        if page_number <= 1:
            continue
        lines = _nonempty_lines(page_texts.get(page_number, ""))
        prev_lines = _nonempty_lines(page_texts.get(page_number - 1, ""))
        if not lines or not prev_lines:
            continue
        formula_number = lines[0]
        previous_line = prev_lines[-1]
        if not FORMULA_NUMBER_LINE_RE.match(formula_number):
            continue
        if not FORMULA_CONTEXT_RE.search(previous_line):
            continue
        finding = _finding(
            "formula_number_split_page",
            "warning",
            page_number,
            {"x": 0.0, "y": 0.0, "w": 1.0, "h": 0.12},
            "PDF 文本层显示公式编号出现在下一页页首，疑似公式与编号跨页。",
            "body_paragraphs",
            evidence_source,
            page_image_by_number.get(page_number, ""),
        )
        finding.update(
            {
                "rule_id": "render.formula_number_split_page",
                "classification": "render_text_flow",
                "confidence": 0.82,
                "actionable": True,
                "reason": "上一页末行像公式，下一页首行只有公式编号。",
                "suggested_action": "回到 Word/WPS 检查该公式段分页，确保公式和编号留在同一页。",
                "previous_page": page_number - 1,
                "previous_line": previous_line,
                "formula_number": formula_number,
            }
        )
        findings.append(finding)
    return findings


def _content_bottom_ratio(metrics: PageImageMetrics) -> float | None:
    if not metrics.bbox or not metrics.height:
        return None
    return metrics.bbox[3] / metrics.height


def _detect_heading_orphan_pages(
    page_texts: dict[int, str],
    page_metrics: dict[int, PageImageMetrics],
    page_image_by_number: dict[int, str],
    evidence_source: str | None,
) -> list[dict]:
    findings = []
    for page_number in sorted(page_texts):
        next_text = page_texts.get(page_number + 1)
        if not next_text:
            continue
        lines = _nonempty_lines(page_texts.get(page_number, ""))
        next_lines = _nonempty_lines(next_text)
        if not lines or not next_lines:
            continue
        heading = lines[-1]
        if not HEADING_LINE_RE.match(heading):
            continue
        if HEADING_LINE_RE.match(next_lines[0]):
            continue
        bottom_ratio = _content_bottom_ratio(page_metrics.get(page_number))
        if bottom_ratio is None or bottom_ratio > 0.525:
            continue
        finding = _finding(
            "heading_orphan_at_page_bottom",
            "warning",
            page_number,
            {"x": 0.0, "y": max(0.0, bottom_ratio - 0.08), "w": 1.0, "h": 0.12},
            "PDF 文本层显示标题单独留在页末，正文从下一页开始。",
            "headings",
            evidence_source,
            page_image_by_number.get(page_number, ""),
        )
        finding.update(
            {
                "rule_id": "render.heading_orphan_at_page_bottom",
                "classification": "render_heading_flow",
                "confidence": 0.8,
                "actionable": True,
                "reason": "页末最后一行是标题，下一页首行是正文，且页图下方留白明显。",
                "suggested_action": "回到 Word/WPS 检查该标题分页，避免标题单独留在页末。",
                "heading_text": heading,
                "next_page": page_number + 1,
                "next_page_first_line": next_lines[0],
                "content_bottom_ratio": bottom_ratio,
            }
        )
        findings.append(finding)
    return findings


def _summarize_findings(findings: list[dict]) -> dict:
    summary = {
        "finding_count": len(findings),
        "highest_severity": None,
        "blank_page_count": 0,
        "render_suspect_count": 0,
        "object_caption_split_count": 0,
        "toc_visual_issue_count": 0,
        "actionable_finding_count": 0,
        "expected_blank_count": 0,
        "object_flow_issue_count": 0,
        "heading_break_issue_count": 0,
        "suspicious_blank_count": 0,
        "isolated_punctuation_count": 0,
    }
    highest = None
    for finding in findings:
        finding_id = finding.get("id")
        severity = finding.get("severity")
        if highest is None or SEVERITY_ORDER.get(str(severity), -1) > SEVERITY_ORDER.get(str(highest), -1):
            highest = severity
        if finding_id == "blank_page":
            summary["blank_page_count"] += 1
        elif finding_id == "render_suspect":
            summary["render_suspect_count"] += 1
        elif finding_id == "isolated_punctuation":
            summary["isolated_punctuation_count"] += 1
        elif finding_id == "formula_number_split_page":
            summary["formula_number_split_count"] = summary.get("formula_number_split_count", 0) + 1
        elif finding_id == "heading_orphan_at_page_bottom":
            summary["heading_break_issue_count"] += 1
        if finding.get("actionable"):
            summary["actionable_finding_count"] += 1
    summary.setdefault("formula_number_split_count", 0)
    summary["highest_severity"] = highest
    return summary


def _build_layout_score(summary: dict) -> dict:
    render_integrity_issue_count = int(summary.get("blank_page_count") or 0) + int(summary.get("render_suspect_count") or 0)
    penalty = (
        int(summary.get("blank_page_count") or 0) * 20
        + int(summary.get("render_suspect_count") or 0) * 20
    )
    return {
        "score": max(0, 100 - penalty),
        "penalty": penalty,
        "expected_blank_count": int(summary.get("expected_blank_count") or 0),
        "actionable_finding_count": int(summary.get("actionable_finding_count") or 0),
        "object_flow_issue_count": int(summary.get("object_flow_issue_count") or 0),
        "heading_break_issue_count": int(summary.get("heading_break_issue_count") or 0),
        "render_integrity_issue_count": render_integrity_issue_count,
    }


def _read_page_image_metrics(image_path: str) -> PageImageMetrics:
    return render_image_metrics.read_page_image_metrics(
        image_path,
        read_with_pillow_fn=lambda path: _read_with_pillow(path),
        read_png_metrics_fn=lambda path: _read_png_metrics(path),
    )


def _finding(
    finding_id: str,
    severity: str,
    page: int,
    region: dict[str, float],
    message: str,
    suggested_scope: str,
    evidence_source: str | None,
    image_path: str,
) -> dict:
    payload = {
        "id": finding_id,
        "severity": severity,
        "page": page,
        "region": region,
        "bbox": dict(region),
        "message": message,
        "suggested_scope": suggested_scope,
        "image_path": image_path,
    }
    if evidence_source:
        payload["evidence_source"] = evidence_source
    return payload


def _bbox_region(metrics: PageImageMetrics) -> dict[str, float]:
    if metrics.bbox is None:
        return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
    left, top, right, bottom = metrics.bbox
    return _region(left / metrics.width, top / metrics.height, (right - left + 1) / metrics.width, (bottom - top + 1) / metrics.height)


def _region(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {
        "x": round(max(0.0, min(1.0, x)), 3),
        "y": round(max(0.0, min(1.0, y)), 3),
        "w": round(max(0.0, min(1.0, w)), 3),
        "h": round(max(0.0, min(1.0, h)), 3),
    }
