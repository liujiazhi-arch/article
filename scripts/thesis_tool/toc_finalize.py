from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Mapping

from fix_docx_io import write_docx_atomically
from ooxml_namespaces import declare_ignorable_namespaces


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W_NS}
W = f"{{{W_NS}}}"
TOC_STYLES = {"TOC1": 1, "TOC2": 2, "TOC3": 3}
HEADING_STYLE_RE = re.compile(r"^(?:heading|标题)\s*([1-3])$", re.IGNORECASE)
TOC_STYLE_RE = re.compile(r"^(?:toc|目录)\s*([1-3])$", re.IGNORECASE)
PAGE_HYPHENS = "\u002d\u2010\u2011\u2012\u2013\u2014\u2212"
PAGE_RE = re.compile(rf"^(?P<mark>[{PAGE_HYPHENS}])\s*(?P<page>\d{{1,4}})\s*(?P=mark)$")
TOC_LINE_RE = re.compile(rf"[\s.．·•…_\u2010-\u2014\u2212]{{2,}}\d{{1,4}}\s*$")


def _read_part(input_docx: str | Path, part_name: str) -> bytes:
    path = Path(input_docx).expanduser()
    with zipfile.ZipFile(path, "r") as package:
        return package.read(part_name)


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for element in paragraph.iter():
        if element.tag == f"{W}t" and element.text:
            parts.append(element.text)
        elif element.tag == f"{W}tab":
            parts.append("\t")
    return "".join(parts).strip()


def _entry_title(text: str) -> str:
    tab_match = re.match(r"^(.*?)\t\s*\d{1,4}\s*$", text)
    if tab_match:
        return tab_match.group(1).strip()
    leader_match = re.match(r"^(.*?)[.．·•…]{2,}\s*\d{1,4}\s*$", text)
    if leader_match:
        return leader_match.group(1).strip()
    return text.strip()


def _style_levels(styles_root: ET.Element, pattern: re.Pattern, defaults: Mapping[str, int] | None = None) -> dict[str, int]:
    levels = dict(defaults or {})
    for style in styles_root.findall("w:style", NSMAP):
        if style.get(f"{W}type") != "paragraph":
            continue
        name = style.find("w:name", NSMAP)
        match = pattern.fullmatch(name.get(f"{W}val", "").strip()) if name is not None else None
        if match:
            levels[style.get(f"{W}styleId", "")] = int(match.group(1))
    return levels


def _toc_entries(document_root: ET.Element, toc_style_levels: Mapping[str, int]) -> list[dict]:
    entries: list[dict] = []
    for paragraph in document_root.iter(f"{W}p"):
        style = paragraph.find("w:pPr/w:pStyle", NSMAP)
        style_id = style.get(f"{W}val") if style is not None else None
        if style_id not in toc_style_levels:
            continue
        title = _entry_title(_paragraph_text(paragraph))
        if title:
            entries.append({"title": title, "level": toc_style_levels[style_id], "element": paragraph})
    return entries


def _body_heading_entries(document_root: ET.Element, heading_style_levels: Mapping[str, int]) -> list[dict]:
    paragraphs = list(document_root.iter(f"{W}p"))
    has_toc_field = any(_starts_toc_field(paragraph) for paragraph in paragraphs)
    after_toc = False
    tracking_field = False
    field_depth = 0
    entries: list[dict] = []
    for paragraph in paragraphs:
        if has_toc_field and not after_toc:
            if not tracking_field and _starts_toc_field(paragraph):
                tracking_field = True
            if tracking_field:
                for field_type in _field_types(paragraph):
                    field_depth += 1 if field_type == "begin" else -1 if field_type == "end" else 0
                if field_depth == 0:
                    after_toc = True
            continue
        if not has_toc_field and not after_toc:
            if _compact(_paragraph_text(paragraph)) in {"目录", "contents"}:
                after_toc = True
            continue
        style_id = _paragraph_style(paragraph)
        title = _paragraph_text(paragraph)
        if style_id in heading_style_levels and title:
            entries.append({"title": title, "level": heading_style_levels[style_id], "element": paragraph})
    return entries


def _source_entries(document_root: ET.Element, styles_root: ET.Element) -> list[dict]:
    heading_levels = _style_levels(styles_root, HEADING_STYLE_RE)
    body_entries = _body_heading_entries(document_root, heading_levels)
    toc_levels = _style_levels(styles_root, TOC_STYLE_RE, TOC_STYLES)
    toc_entries = _toc_entries(document_root, toc_levels)
    merged = list(toc_entries)
    remaining_toc_titles = Counter(_compact(entry["title"]) for entry in toc_entries)
    for entry in body_entries:
        key = _compact(entry["title"])
        if remaining_toc_titles[key] > 0:
            remaining_toc_titles[key] -= 1
            continue
        merged.append(entry)
    return merged


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[\s\u3000.．·•…_\-\u2010-\u2014\u2212]+", "", normalized)


def _is_toc_page(text: str) -> bool:
    head = _compact("\n".join(str(text or "").splitlines()[:5]))
    return "目录" in head or "contents" in head


def _printed_page_number(text: str) -> int | None:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in reversed(lines[-5:]):
        match = PAGE_RE.fullmatch(line)
        if match:
            return int(match.group("page"))
    return None


def _pdf_lines(page_texts: Mapping[int, str]) -> list[tuple[int, int, str]]:
    pages = sorted((int(page), str(text or "")) for page, text in page_texts.items())
    return [
        (page, line_index, line.strip())
        for page, text in pages
        if not _is_toc_page(text)
        for line_index, line in enumerate(text.splitlines())
        if line.strip()
    ]


def _matches_heading(line: str, title: str) -> bool:
    if TOC_LINE_RE.search(line):
        return False
    candidate = _compact(line)
    target = _compact(title)
    return bool(target and candidate == target)


def _map_entries(entries: list[dict], page_texts: Mapping[int, str]) -> list[dict]:
    lines = _pdf_lines(page_texts)
    cursor = -1
    mapped: list[dict] = []
    for entry in entries:
        match_index = next(
            (index for index in range(cursor + 1, len(lines)) if _matches_heading(lines[index][2], entry["title"])),
            None,
        )
        pdf_page = lines[match_index][0] if match_index is not None else None
        page = _printed_page_number(page_texts[pdf_page]) if pdf_page is not None else None
        mapped.append({"title": entry["title"], "level": entry["level"], "pdf_page": pdf_page, "page": page})
        if match_index is not None:
            cursor = match_index
    return mapped


def analyze_static_toc(input_docx: str | Path, page_texts: Mapping[int, str]) -> dict:
    document_root = ET.fromstring(_read_part(input_docx, "word/document.xml"))
    styles_root = ET.fromstring(_read_part(input_docx, "word/styles.xml"))
    entries = _map_entries(_source_entries(document_root, styles_root), page_texts)
    unmatched = [entry["title"] for entry in entries if entry["page"] is None]
    complete = bool(entries) and not unmatched
    return {
        "status": "ready" if complete else "incomplete",
        "complete": complete,
        "entry_count": len(entries),
        "mapped_count": len(entries) - len(unmatched),
        "entries": entries,
        "unmatched_titles": unmatched,
    }


def _first_text_run_properties(paragraph: ET.Element | None) -> ET.Element | None:
    if paragraph is None:
        return None
    for run in paragraph.findall(".//w:r", NSMAP):
        if run.find("w:t", NSMAP) is None:
            continue
        properties = run.find("w:rPr", NSMAP)
        if properties is not None:
            return properties
    return None


def _append_text_run(paragraph: ET.Element, text: str, run_properties: ET.Element | None = None) -> None:
    run = ET.SubElement(paragraph, f"{W}r")
    if run_properties is not None:
        run.append(deepcopy(run_properties))
    text_element = ET.SubElement(run, f"{W}t")
    text_element.text = text


def _rewrite_entry(paragraph: ET.Element, title: str, page: int) -> None:
    paragraph_properties = paragraph.find("w:pPr", NSMAP)
    run_properties = _first_text_run_properties(paragraph)
    for child in list(paragraph):
        if child is not paragraph_properties:
            paragraph.remove(child)
    _append_text_run(paragraph, title, run_properties)
    tab_run = ET.SubElement(paragraph, f"{W}r")
    if run_properties is not None:
        tab_run.append(deepcopy(run_properties))
    ET.SubElement(tab_run, f"{W}tab")
    _append_text_run(paragraph, str(page), run_properties)


def _paragraph_style(paragraph: ET.Element) -> str | None:
    style = paragraph.find("w:pPr/w:pStyle", NSMAP)
    return style.get(f"{W}val") if style is not None else None


def _field_types(paragraph: ET.Element) -> list[str | None]:
    return [field.get(f"{W}fldCharType") for field in paragraph.findall(".//w:fldChar", NSMAP)]


def _starts_toc_field(paragraph: ET.Element) -> bool:
    field_types = _field_types(paragraph)
    instructions = " ".join(element.text or "" for element in paragraph.findall(".//w:instrText", NSMAP))
    style_id = _paragraph_style(paragraph)
    return "begin" in field_types and bool(style_id == "TOCField" or re.search(r"\bTOC\b", instructions, re.I))


def _toc_field_marker_ids(document_root: ET.Element) -> set[int]:
    marker_ids: set[int] = set()
    depth = 0
    tracking = False
    for paragraph in document_root.iter(f"{W}p"):
        if not tracking and _starts_toc_field(paragraph):
            tracking = True
            marker_ids.add(id(paragraph))
        if tracking:
            for field_type in _field_types(paragraph):
                depth += 1 if field_type == "begin" else -1 if field_type == "end" else 0
            if depth == 0:
                marker_ids.add(id(paragraph))
                tracking = False
        if _paragraph_style(paragraph) == "TOCEnd" and "end" in _field_types(paragraph):
            marker_ids.add(id(paragraph))
    return marker_ids


def _remove_toc_field_markers(document_root: ET.Element) -> None:
    marker_ids = _toc_field_marker_ids(document_root)
    for parent in document_root.iter():
        for child in list(parent):
            if child.tag == f"{W}p" and id(child) in marker_ids:
                parent.remove(child)


def _remove_paragraphs(document_root: ET.Element, paragraphs: list[dict]) -> None:
    paragraph_ids = {id(entry["element"]) for entry in paragraphs}
    for parent in document_root.iter():
        for child in list(parent):
            if child.tag == f"{W}p" and id(child) in paragraph_ids:
                parent.remove(child)


def _toc_insertion_index(document_root: ET.Element, toc_entries: list[dict]) -> tuple[ET.Element, int]:
    body = document_root.find("w:body", NSMAP)
    if body is None:
        raise ValueError("DOCX 缺少正文容器")
    children = list(body)
    direct_indices = {id(child): index for index, child in enumerate(children)}
    if toc_entries and id(toc_entries[0]["element"]) in direct_indices:
        return body, direct_indices[id(toc_entries[0]["element"])]
    for index, child in enumerate(children):
        if child.tag == f"{W}p" and _starts_toc_field(child):
            return body, index
    for index, child in enumerate(children):
        if child.tag == f"{W}p" and _compact(_paragraph_text(child)) in {"目录", "contents"}:
            return body, index + 1
    raise ValueError("DOCX 中未找到目录位置")


def _toc_style_id(level: int, toc_style_levels: Mapping[str, int]) -> str:
    preferred = f"TOC{level}"
    if toc_style_levels.get(preferred) == level:
        return preferred
    return next((style_id for style_id, style_level in toc_style_levels.items() if style_level == level), preferred)


def _new_toc_paragraph(
    title: str,
    page: int,
    level: int,
    toc_style_levels: Mapping[str, int],
    template: ET.Element | None,
) -> ET.Element:
    paragraph = ET.Element(f"{W}p")
    template_properties = template.find("w:pPr", NSMAP) if template is not None else None
    if template_properties is not None:
        paragraph.append(deepcopy(template_properties))
    else:
        properties = ET.SubElement(paragraph, f"{W}pPr")
        style = ET.SubElement(properties, f"{W}pStyle")
        style.set(f"{W}val", _toc_style_id(level, toc_style_levels))
    run_properties = _first_text_run_properties(template)
    _append_text_run(paragraph, title, run_properties)
    tab_run = ET.SubElement(paragraph, f"{W}r")
    if run_properties is not None:
        tab_run.append(deepcopy(run_properties))
    ET.SubElement(tab_run, f"{W}tab")
    _append_text_run(paragraph, str(page), run_properties)
    return paragraph


def _insert_toc_entries(
    document_root: ET.Element,
    toc_entries: list[dict],
    mapped_entries: list[dict],
    toc_style_levels: Mapping[str, int],
) -> None:
    body, insertion_index = _toc_insertion_index(document_root, toc_entries)
    templates = {entry["level"]: entry["element"] for entry in reversed(toc_entries)}
    for offset, entry in enumerate(mapped_entries):
        body.insert(
            insertion_index + offset,
            _new_toc_paragraph(
                entry["title"],
                entry["page"],
                entry["level"],
                toc_style_levels,
                templates.get(entry["level"]),
            ),
        )
    _remove_paragraphs(document_root, toc_entries)


def _serialized_parts(input_docx: str | Path, mapped_entries: list[dict]) -> dict[str, bytes]:
    document_root = ET.fromstring(_read_part(input_docx, "word/document.xml"))
    styles_root = ET.fromstring(_read_part(input_docx, "word/styles.xml"))
    toc_style_levels = _style_levels(styles_root, TOC_STYLE_RE, TOC_STYLES)
    toc_entries = _toc_entries(document_root, toc_style_levels)
    if toc_entries and len(toc_entries) == len(mapped_entries):
        for toc_entry, mapped_entry in zip(toc_entries, mapped_entries, strict=True):
            _rewrite_entry(toc_entry["element"], mapped_entry["title"], mapped_entry["page"])
    else:
        _insert_toc_entries(document_root, toc_entries, mapped_entries, toc_style_levels)
    _remove_toc_field_markers(document_root)
    declare_ignorable_namespaces(document_root)
    return {
        "word/document.xml": ET.tostring(document_root, encoding="utf-8", xml_declaration=True),
    }


def finalize_static_toc(
    input_docx: str | Path,
    output_path: str | Path,
    page_texts: Mapping[int, str],
) -> dict:
    if Path(input_docx).expanduser().resolve() == Path(output_path).expanduser().resolve():
        raise ValueError("输入路径与输出路径不能相同")

    analysis = analyze_static_toc(input_docx, page_texts)
    if not analysis["complete"]:
        return {**analysis, "written": False, "output_path": None}

    write_docx_atomically(
        str(input_docx),
        str(output_path),
        _serialized_parts(input_docx, analysis["entries"]),
    )
    return {**analysis, "status": "finalized", "written": True, "output_path": str(output_path)}
