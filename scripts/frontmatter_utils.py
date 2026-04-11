from __future__ import annotations

import re
from collections.abc import Callable, Sequence


ENGLISH_KEYWORDS_RE = re.compile(r"^key(?:\s*words?|words?)\b", re.IGNORECASE)
TOC_FIELD_TOKEN_RE = re.compile(
    r'(?:\bTOC\s+\\o\b|\bHYPERLINK\s+\\l\s+"?_Toc|\bPAGEREF\s+_Toc)',
    re.IGNORECASE,
)
TOC_GENERATED_STYLE_IDS = frozenset(
    {"TOCHeading", "TOCField", "TOC1", "TOC2", "TOC3", "TOCEnd", "TOCPageBreak"}
)
TOC_STRUCTURAL_STYLE_IDS = frozenset({"TOCField", "TOCEnd", "TOCPageBreak"})
TOC_HEADING_STYLE_NAMES = frozenset({"tocheading", "目录标题"})
TOC_ENTRY_STYLE_NAMES = frozenset({"toc1", "toc2", "toc3", "目录1", "目录2", "目录3"})
TOC_RELATED_STYLE_NAMES = TOC_HEADING_STYLE_NAMES | TOC_ENTRY_STYLE_NAMES | frozenset(
    {"tocfield", "tocend", "tocpagebreak"}
)


def is_cn_keywords_paragraph_text(text: str | None) -> bool:
    return str(text or "").strip().startswith("关键词")


def is_en_keywords_paragraph_text(text: str | None) -> bool:
    return ENGLISH_KEYWORDS_RE.match(str(text or "").strip()) is not None


def is_keyword_paragraph_text(text: str | None) -> bool:
    return is_cn_keywords_paragraph_text(text) or is_en_keywords_paragraph_text(text)


def is_keywords_text(text: str | None, section_name: str | None = None) -> bool:
    if section_name == "abstract_cn":
        return is_cn_keywords_paragraph_text(text)
    if section_name == "abstract_en":
        return is_en_keywords_paragraph_text(text)
    return is_keyword_paragraph_text(text)


def has_toc_field_instr(paragraph_elem, nsmap) -> bool:
    return any(
        TOC_FIELD_TOKEN_RE.search(instr_text.text or "")
        for instr_text in paragraph_elem.findall(".//w:instrText", nsmap)
    )


def paragraph_has_toc_field_instr(paragraph_elem, *, nsmap) -> bool:
    return has_toc_field_instr(paragraph_elem, nsmap)


def contains_toc_field_text(text: str | None) -> bool:
    return TOC_FIELD_TOKEN_RE.search(str(text or "")) is not None


def is_toc_generated_style_id(style_id: str | None) -> bool:
    return str(style_id or "").strip() in TOC_GENERATED_STYLE_IDS


def is_toc_structural_style_id(style_id: str | None) -> bool:
    return str(style_id or "").strip() in TOC_STRUCTURAL_STYLE_IDS


def normalize_style_semantic_name(style_id: str | None, style_map: dict | None) -> str:
    if not style_id:
        return ""
    props = (style_map or {}).get(style_id, {}) or {}
    raw_name = props.get("name") or style_id or ""
    return re.sub(r"[\s_-]+", "", str(raw_name).strip().lower())


def is_toc_heading_style(style_id: str | None, style_map: dict | None) -> bool:
    return normalize_style_semantic_name(style_id, style_map) in TOC_HEADING_STYLE_NAMES


def is_toc_entry_style(style_id: str | None, style_map: dict | None) -> bool:
    return normalize_style_semantic_name(style_id, style_map) in TOC_ENTRY_STYLE_NAMES


def is_toc_related_style(style_id: str | None, style_map: dict | None) -> bool:
    return normalize_style_semantic_name(style_id, style_map) in TOC_RELATED_STYLE_NAMES


def find_contiguous_toc_block_range(
    items: Sequence[object],
    *,
    is_candidate: Callable[[object], bool],
    get_text: Callable[[object], str | None],
    is_tocish: Callable[[object, str], bool],
) -> tuple[int | None, int | None]:
    block_start_idx: int | None = None
    block_end_idx: int | None = None

    for idx, item in enumerate(items):
        if not is_candidate(item):
            if block_start_idx is not None:
                break
            continue

        text = str(get_text(item) or "").strip()
        tocish = bool(is_tocish(item, text))
        if block_start_idx is None:
            if tocish:
                block_start_idx = idx
                block_end_idx = idx
            continue

        if not text or tocish:
            block_end_idx = idx
            continue

        break

    return block_start_idx, block_end_idx
