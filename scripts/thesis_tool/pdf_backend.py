from __future__ import annotations

import logging
from math import isfinite
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def _load_pdfium():
    try:
        import pypdfium2
    except ImportError as exc:
        raise RuntimeError("缺少内置 PDF 运行组件，请重新安装论文格式检查工具。") from exc
    return pypdfium2


def convert_pdf_with_pdfium(input_pdf: str, output_dir: Path) -> None:
    document = _load_pdfium().PdfDocument(str(Path(input_pdf).expanduser().resolve()))
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = None
            image = None
            try:
                bitmap = page.render(scale=120 / 72)
                image = bitmap.to_pil()
                image.save(output_dir / f"page-{index + 1}.png", "PNG")
            finally:
                if image is not None:
                    image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
    finally:
        document.close()


def extract_pdf_text_pages_with_pdfium(pdf_path: Path) -> list[str]:
    document = _load_pdfium().PdfDocument(str(pdf_path))
    page_texts: list[str] = []
    try:
        for index in range(len(document)):
            page = document[index]
            text_page = None
            try:
                text_page = page.get_textpage()
                page_texts.append(text_page.get_text_bounded())
            finally:
                if text_page is not None:
                    text_page.close()
                page.close()
    finally:
        document.close()
    return page_texts


def _rotate_box(box: tuple[float, float, float, float], width: float, height: float, rotation: int):
    x0, y0, x1, y1 = box
    if rotation == 0:
        return box
    if rotation == 90:
        return height - y1, x0, height - y0, x1
    if rotation == 180:
        return width - x1, height - y1, width - x0, height - y0
    if rotation == 270:
        return y0, width - x1, y1, width - x0
    return None


def _normalized_charbox(raw_box, page_bbox, page_size, rotation: int) -> dict[str, float] | None:
    values = tuple(float(value) for value in (*raw_box, *page_bbox, *page_size))
    if not all(isfinite(value) for value in values):
        return None
    left, bottom, right, top, crop_left, crop_bottom, crop_right, crop_top, visible_w, visible_h = values
    crop_w, crop_h = crop_right - crop_left, crop_top - crop_bottom
    if right <= left or top <= bottom or min(crop_w, crop_h, visible_w, visible_h) <= 0:
        return None
    unrotated = left - crop_left, crop_top - top, right - crop_left, crop_top - bottom
    rotated = _rotate_box(unrotated, crop_w, crop_h, rotation % 360)
    if rotated is None:
        return None
    x0, y0, x1, y1 = rotated
    x0, x1 = max(0.0, x0), min(visible_w, x1)
    y0, y1 = max(0.0, y0), min(visible_h, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return {
        "x": round(x0 / visible_w, 6),
        "y": round(y0 / visible_h, 6),
        "w": round((x1 - x0) / visible_w, 6),
        "h": round((y1 - y0) / visible_h, 6),
    }


def _line_payload(text_parts: list[str], boxes: list[dict[str, float]], valid: bool) -> dict | None:
    text = "".join(text_parts).strip()
    if not text or not boxes or not valid:
        return None
    left = min(box["x"] for box in boxes)
    top = min(box["y"] for box in boxes)
    right = max(box["x"] + box["w"] for box in boxes)
    bottom = max(box["y"] + box["h"] for box in boxes)
    return {
        "text": text,
        "bbox": {"x": left, "y": top, "w": round(right - left, 6), "h": round(bottom - top, 6)},
    }


def _pdfium_page_lines(page, text_page) -> list[dict]:
    page_bbox = page.get_bbox()
    page_size = page.get_size()
    rotation = int(page.get_rotation() or 0)
    lines: list[dict] = []
    text_parts: list[str] = []
    boxes: list[dict[str, float]] = []
    valid = True
    for index in range(text_page.count_chars()):
        char = text_page.get_text_range(index, 1)
        if char in {"\r", "\n"}:
            if payload := _line_payload(text_parts, boxes, valid):
                lines.append(payload)
            text_parts, boxes, valid = [], [], True
            continue
        text_parts.append(char)
        if not char or char.isspace():
            continue
        box = _normalized_charbox(text_page.get_charbox(index), page_bbox, page_size, rotation)
        if box is None:
            valid = False
        else:
            boxes.append(box)
    if payload := _line_payload(text_parts, boxes, valid):
        lines.append(payload)
    return lines


def extract_pdf_line_boxes_with_pdfium(pdf_path: Path) -> dict[int, list[dict]]:
    document = _load_pdfium().PdfDocument(str(Path(pdf_path).expanduser().resolve()))
    pages: dict[int, list[dict]] = {}
    try:
        for index in range(len(document)):
            page = document[index]
            text_page = None
            try:
                text_page = page.get_textpage()
                pages[index + 1] = _pdfium_page_lines(page, text_page)
            except Exception:
                LOGGER.warning(
                    "PDFium 无法读取第 %d 页文字坐标 已降级为整页证据",
                    index + 1,
                    exc_info=True,
                )
                pages[index + 1] = []
            finally:
                if text_page is not None:
                    text_page.close()
                page.close()
    finally:
        document.close()
    return pages
