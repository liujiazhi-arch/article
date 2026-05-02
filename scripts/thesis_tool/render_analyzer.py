from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib
import re


SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2, "blocker": 3}
WHITE_LUMA_THRESHOLD = 245


@dataclass(frozen=True)
class PageImageMetrics:
    width: int
    height: int
    ink_count: int
    row_ink_counts: tuple[int, ...]
    bbox: tuple[int, int, int, int] | None

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def ink_ratio(self) -> float:
        if self.pixel_count <= 0:
            return 0.0
        return self.ink_count / self.pixel_count

    @property
    def content_area_ratio(self) -> float:
        if self.pixel_count <= 0 or self.bbox is None:
            return 0.0
        left, top, right, bottom = self.bbox
        return ((right - left + 1) * (bottom - top + 1)) / self.pixel_count


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

    for page_number, image_path in enumerate(page_images, start=1):
        try:
            metrics = _read_page_image_metrics(image_path)
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
        for finding in raw_findings:
            findings.append(
                _classify_finding_context(
                    finding,
                    page_text=page_texts.get(page_number, ""),
                    next_page_text=page_texts.get(page_number + 1, ""),
                )
            )

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
    if finding.get("id") != "large_blank_region":
        finding.setdefault("classification", "render_integrity")
        finding.setdefault("confidence", 0.9)
        finding.setdefault("actionable", True)
        finding.setdefault("reason", finding.get("message") or "")
        finding.setdefault("suggested_action", "检查渲染器输出或重新导出 PDF/页图。")
        return finding

    page_role = _classify_page_role(page_text)
    next_page_role = _classify_page_role(next_page_text)
    finding["page_role"] = page_role
    finding["next_page_role"] = next_page_role

    if next_page_role == "chapter_start":
        finding.update(
            {
                "classification": "expected_chapter_break",
                "confidence": 0.86,
                "actionable": False,
                "reason": "下一页为章节起始页，当前页留白符合章节强制分页习惯。",
                "suggested_scope": None,
                "suggested_action": None,
            }
        )
        return finding

    if next_page_role == "figure_table_heavy":
        finding.update(
            {
                "classification": "suspicious_object_flow",
                "confidence": 0.78,
                "actionable": True,
                "reason": "下一页顶部疑似图表/题注，当前页剩余空间不足导致对象块被挤到下一页。",
                "suggested_scope": "figures_tables",
                "suggested_action": "基于 Word/WPS PDF 证据尝试 figures_tables + --layout-rebalance，并比较修前/修后 layout score。",
            }
        )
        return finding

    if page_role == "isolated_heading":
        finding.update(
            {
                "classification": "suspicious_heading_break",
                "confidence": 0.74,
                "actionable": True,
                "reason": "当前页文本疑似只有小节标题，正文被推到下一页。",
                "suggested_scope": "headings",
                "suggested_action": "检查并清理非一级标题附近的 pageBreakBefore/keepNext/空段，再用 Word/WPS PDF 复核。",
            }
        )
        return finding

    finding.update(
        {
            "classification": "suspicious_blank_region",
            "confidence": 0.58,
            "actionable": True,
            "reason": "未识别到章节分页等合理结构理由，需要结合页面截图或人工复核判断。",
            "suggested_action": "优先检查该页前后标题、图表锚点、空段和对象保护属性。",
        }
    )
    return finding


def _classify_page_role(page_text: str) -> str:
    normalized = _normalize_page_text(page_text)
    if not normalized:
        return "blank_or_image_only"
    if _starts_with_chapter_heading(normalized):
        return "chapter_start"
    if _starts_with_figure_or_table(normalized):
        return "figure_table_heavy"
    if _looks_like_isolated_heading(normalized):
        return "isolated_heading"
    if "目 录" in normalized or "目录" == normalized.strip():
        return "toc"
    if "参考文献" in normalized[:20]:
        return "references"
    return "normal_body"


def _normalize_page_text(page_text: str) -> str:
    lines = [line.strip() for line in str(page_text or "").replace("\u3000", " ").splitlines()]
    return "\n".join(line for line in lines if line)


def _starts_with_chapter_heading(text: str) -> bool:
    first_line = text.splitlines()[0] if text.splitlines() else text
    return bool(re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*[章节篇]\b", first_line))


def _starts_with_figure_or_table(text: str) -> bool:
    first_lines = "\n".join(text.splitlines()[:3])
    return bool(re.search(r"(^|\n)\s*[图表]\s*\d+(?:[.\-]\d+)+", first_lines))


def _looks_like_isolated_heading(text: str) -> bool:
    lines = text.splitlines()
    compact = re.sub(r"\s+", "", text)
    if len(lines) > 3 or len(compact) > 48:
        return False
    return bool(re.match(r"^\d+(?:\.\d+){1,3}[\s、.．]+", lines[0] if lines else compact))


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

    if not render_suspect:
        findings.extend(_detect_large_blank_regions(metrics, page_number, image_path, evidence_source))

    return findings


def _detect_large_blank_regions(
    metrics: PageImageMetrics,
    page_number: int,
    image_path: str,
    evidence_source: str | None,
) -> list[dict]:
    findings: list[dict] = []
    content_row_threshold = max(3, int(metrics.width * 0.003))
    content_rows = [index for index, count in enumerate(metrics.row_ink_counts) if count >= content_row_threshold]
    if not content_rows:
        return findings

    first_row = content_rows[0]
    last_row = content_rows[-1]
    bottom_blank_start = last_row + 1
    bottom_blank_height = metrics.height - bottom_blank_start
    if first_row < int(metrics.height * 0.55) and bottom_blank_height >= int(metrics.height * 0.25):
        findings.append(
            _finding(
                "large_blank_region",
                "warning",
                page_number,
                _region(0.08, bottom_blank_start / metrics.height, 0.84, bottom_blank_height / metrics.height),
                "页底存在大块连续空白，疑似图表块、标题分页或对象保护导致。",
                "figures_tables",
                evidence_source,
                image_path,
            )
        )

    middle_run = _largest_middle_blank_run(metrics.row_ink_counts, metrics.width, metrics.height)
    if middle_run is not None:
        start, height = middle_run
        has_content_above = any(count >= content_row_threshold for count in metrics.row_ink_counts[:start])
        has_content_below = any(count >= content_row_threshold for count in metrics.row_ink_counts[start + height :])
        if has_content_above and has_content_below:
            findings.append(
                _finding(
                    "large_blank_region",
                    "warning",
                    page_number,
                    _region(0.08, start / metrics.height, 0.84, height / metrics.height),
                    "页面中部存在大块连续空白，疑似分页或对象占位异常。",
                    "headings",
                    evidence_source,
                    image_path,
                )
            )

    return findings


def _largest_middle_blank_run(row_ink_counts: tuple[int, ...], width: int, height: int) -> tuple[int, int] | None:
    blank_row_threshold = max(2, int(width * 0.0015))
    min_run_height = int(height * 0.22)
    middle_start = int(height * 0.12)
    middle_end = int(height * 0.88)
    best: tuple[int, int] | None = None
    run_start: int | None = None

    for row in range(middle_start, middle_end):
        is_blank = row_ink_counts[row] <= blank_row_threshold
        if is_blank and run_start is None:
            run_start = row
        if (not is_blank or row == middle_end - 1) and run_start is not None:
            run_end = row if not is_blank else row + 1
            run_height = run_end - run_start
            if run_height >= min_run_height and (best is None or run_height > best[1]):
                best = (run_start, run_height)
            run_start = None

    return best


def _summarize_findings(findings: list[dict]) -> dict:
    summary = {
        "finding_count": len(findings),
        "highest_severity": None,
        "blank_page_count": 0,
        "large_blank_count": 0,
        "large_blank_bottom_count": 0,
        "large_blank_middle_count": 0,
        "render_suspect_count": 0,
        "object_caption_split_count": 0,
        "toc_visual_issue_count": 0,
        "actionable_finding_count": 0,
        "expected_blank_count": 0,
        "object_flow_issue_count": 0,
        "heading_break_issue_count": 0,
        "suspicious_blank_count": 0,
    }
    highest = None
    for finding in findings:
        finding_id = finding.get("id")
        severity = finding.get("severity")
        if highest is None or SEVERITY_ORDER.get(str(severity), -1) > SEVERITY_ORDER.get(str(highest), -1):
            highest = severity
        if finding_id == "blank_page":
            summary["blank_page_count"] += 1
        elif finding_id == "large_blank_region":
            summary["large_blank_count"] += 1
            region_y = float((finding.get("region") or {}).get("y") or 0.0)
            if region_y >= 0.55:
                summary["large_blank_bottom_count"] += 1
            else:
                summary["large_blank_middle_count"] += 1
        elif finding_id == "render_suspect":
            summary["render_suspect_count"] += 1
        elif finding_id == "object_caption_split":
            summary["object_caption_split_count"] += 1
        if finding.get("actionable"):
            summary["actionable_finding_count"] += 1
        classification = finding.get("classification")
        if classification == "expected_chapter_break":
            summary["expected_blank_count"] += 1
        elif classification == "suspicious_object_flow":
            summary["object_flow_issue_count"] += 1
        elif classification == "suspicious_heading_break":
            summary["heading_break_issue_count"] += 1
        elif classification == "suspicious_blank_region":
            summary["suspicious_blank_count"] += 1
    summary["highest_severity"] = highest
    return summary


def _build_layout_score(summary: dict) -> dict:
    render_integrity_issue_count = int(summary.get("blank_page_count") or 0) + int(summary.get("render_suspect_count") or 0)
    penalty = (
        int(summary.get("blank_page_count") or 0) * 20
        + int(summary.get("render_suspect_count") or 0) * 20
        + int(summary.get("object_flow_issue_count") or 0) * 12
        + int(summary.get("heading_break_issue_count") or 0) * 8
        + int(summary.get("suspicious_blank_count") or 0) * 5
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
    try:
        return _read_with_pillow(image_path)
    except ImportError:
        return _read_png_metrics(image_path)
    except Exception:
        return _read_png_metrics(image_path)


def _read_with_pillow(image_path: str) -> PageImageMetrics:
    from PIL import Image

    with Image.open(image_path) as image:
        rgba_image = image.convert("RGBA")
        width, height = rgba_image.size
        rows = [0] * height
        ink_count = 0
        bbox = _Bbox()
        for y in range(height):
            for x in range(width):
                r, g, b, alpha = rgba_image.getpixel((x, y))
                if _is_ink(r, g, b, alpha):
                    rows[y] += 1
                    ink_count += 1
                    bbox.add(x, y)
    return PageImageMetrics(width, height, ink_count, tuple(rows), bbox.as_tuple())


def _read_png_metrics(image_path: str) -> PageImageMetrics:
    width, height, color_type, bit_depth, raw_rows, palette = _decode_png(Path(image_path).read_bytes())
    rows = [0] * height
    ink_count = 0
    bbox = _Bbox()

    for y, row in enumerate(raw_rows):
        for x, pixel in enumerate(_iter_png_pixels(row, width, color_type, bit_depth, palette)):
            r, g, b, alpha = pixel
            if _is_ink(r, g, b, alpha):
                rows[y] += 1
                ink_count += 1
                bbox.add(x, y)

    return PageImageMetrics(width, height, ink_count, tuple(rows), bbox.as_tuple())


def _decode_png(data: bytes) -> tuple[int, int, int, int, list[bytes], list[tuple[int, int, int]]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG file")

    offset = 8
    width = height = color_type = bit_depth = None
    interlace = 0
    palette: list[tuple[int, int, int]] = []
    idat_parts: list[bytes] = []

    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated PNG chunk")
        chunk_length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + chunk_length]
        offset += 12 + chunk_length

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"PLTE":
            palette = [
                tuple(chunk_data[index : index + 3])  # type: ignore[arg-type]
                for index in range(0, len(chunk_data), 3)
                if len(chunk_data[index : index + 3]) == 3
            ]
        elif chunk_type == b"IDAT":
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None or bit_depth is None:
        raise ValueError("missing PNG header")
    if interlace:
        raise ValueError("interlaced PNG is not supported")
    if bit_depth not in {8, 16}:
        raise ValueError(f"unsupported PNG bit depth: {bit_depth}")

    channel_count = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channel_count is None:
        raise ValueError(f"unsupported PNG color type: {color_type}")

    bytes_per_sample = 2 if bit_depth == 16 else 1
    bytes_per_pixel = channel_count * bytes_per_sample
    stride = width * bytes_per_pixel
    inflated = zlib.decompress(b"".join(idat_parts))
    expected = height * (stride + 1)
    if len(inflated) < expected:
        raise ValueError("truncated PNG image data")

    rows: list[bytes] = []
    previous = bytes(stride)
    position = 0
    for _row_index in range(height):
        filter_type = inflated[position]
        encoded = inflated[position + 1 : position + 1 + stride]
        decoded = _unfilter_png_row(filter_type, encoded, previous, bytes_per_pixel)
        rows.append(decoded)
        previous = decoded
        position += stride + 1

    return width, height, color_type, bit_depth, rows, palette


def _unfilter_png_row(filter_type: int, row: bytes, previous: bytes, bytes_per_pixel: int) -> bytes:
    result = bytearray(row)
    for index, value in enumerate(result):
        left = result[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index]
        up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        if filter_type == 0:
            continue
        if filter_type == 1:
            result[index] = (value + left) & 0xFF
        elif filter_type == 2:
            result[index] = (value + up) & 0xFF
        elif filter_type == 3:
            result[index] = (value + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            result[index] = (value + _paeth(left, up, up_left)) & 0xFF
        else:
            raise ValueError(f"unsupported PNG filter type: {filter_type}")
    return bytes(result)


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left


def _iter_png_pixels(
    row: bytes,
    width: int,
    color_type: int,
    bit_depth: int,
    palette: list[tuple[int, int, int]],
):
    sample_size = 2 if bit_depth == 16 else 1
    step = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type] * sample_size
    for x in range(width):
        offset = x * step
        values = [_sample_to_byte(row[offset + index : offset + index + sample_size]) for index in range(0, step, sample_size)]
        if color_type == 0:
            gray = values[0]
            yield gray, gray, gray, 255
        elif color_type == 2:
            yield values[0], values[1], values[2], 255
        elif color_type == 3:
            palette_index = values[0]
            r, g, b = palette[palette_index] if palette_index < len(palette) else (255, 255, 255)
            yield r, g, b, 255
        elif color_type == 4:
            gray, alpha = values
            yield gray, gray, gray, alpha
        elif color_type == 6:
            yield values[0], values[1], values[2], values[3]


def _sample_to_byte(sample: bytes) -> int:
    if len(sample) == 2:
        return sample[0]
    return sample[0]


def _is_ink(r: int, g: int, b: int, alpha: int) -> bool:
    if alpha < 16:
        return False
    luma = (299 * r + 587 * g + 114 * b) // 1000
    return luma < WHITE_LUMA_THRESHOLD


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


class _Bbox:
    def __init__(self) -> None:
        self.left: int | None = None
        self.top: int | None = None
        self.right: int | None = None
        self.bottom: int | None = None

    def add(self, x: int, y: int) -> None:
        self.left = x if self.left is None else min(self.left, x)
        self.top = y if self.top is None else min(self.top, y)
        self.right = x if self.right is None else max(self.right, x)
        self.bottom = y if self.bottom is None else max(self.bottom, y)

    def as_tuple(self) -> tuple[int, int, int, int] | None:
        if self.left is None or self.top is None or self.right is None or self.bottom is None:
            return None
        return self.left, self.top, self.right, self.bottom
