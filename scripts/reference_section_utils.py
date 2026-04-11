from __future__ import annotations

import re
from typing import Callable, Iterator


_REFERENCE_HEADING = "参考文献"
_REFERENCE_STOP_TITLES = {"致谢", "附录", "abstract"}
_CHAPTER_HEADING_RE = re.compile(r"^第.+[章节篇]")


def normalize_reference_section_text(text: str | None) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or "")).lower()


def is_reference_heading_text(text: str | None) -> bool:
    return normalize_reference_section_text(text) == _REFERENCE_HEADING


def is_reference_section_stop_text(text: str | None) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    normalized = normalize_reference_section_text(stripped)
    return normalized in _REFERENCE_STOP_TITLES or bool(_CHAPTER_HEADING_RE.match(stripped))


def iter_reference_section_contexts(contexts, *, skip_empty: bool = False) -> Iterator[dict]:
    in_references = False
    for ctx in contexts:
        text = str(ctx.get("text") or "").strip()
        if is_reference_heading_text(text):
            in_references = True
            continue
        if in_references and ctx.get("kind") == "h1":
            break
        if not in_references:
            continue
        if skip_empty and not text:
            continue
        yield ctx


def iter_reference_section_paragraphs(
    document_root,
    *,
    nsmap,
    get_paragraph_text: Callable,
    skip_empty: bool = False,
) -> Iterator[tuple[object, str]]:
    in_references = False
    for paragraph in document_root.findall(".//w:p", nsmap):
        text = str(get_paragraph_text(paragraph) or "").strip()
        if is_reference_heading_text(text):
            in_references = True
            continue
        if not in_references:
            continue
        if text and is_reference_section_stop_text(text):
            break
        if skip_empty and not text:
            continue
        yield paragraph, text
