from __future__ import annotations

from dataclasses import dataclass
import re

from _thesis_utils import NSMAP, W_NS, parse_int


@dataclass(frozen=True)
class ReferenceNumberPrefix:
    leading: str
    number_text: str
    separator: str
    remainder: str
    number: int
    has_leading_zero: bool


_REFERENCE_NUMBER_PREFIX_RE = re.compile(r"^(\s*)\[(\d+)\]([ \u00a0\t]*)(.*)$", re.DOTALL)


def parse_reference_number_prefix(text: str | None) -> ReferenceNumberPrefix | None:
    match = _REFERENCE_NUMBER_PREFIX_RE.match(str(text or ""))
    if not match:
        return None
    number_text = match.group(2)
    return ReferenceNumberPrefix(
        leading=match.group(1),
        number_text=number_text,
        separator=match.group(3),
        remainder=match.group(4),
        number=int(number_text),
        has_leading_zero=len(number_text) > 1 and number_text.startswith("0"),
    )


def _has_plain_reference_number(prefix: ReferenceNumberPrefix | None) -> bool:
    return (
        prefix is not None
        and prefix.leading == ""
        and not prefix.has_leading_zero
        and 1 <= prefix.number <= 999
        and len(prefix.number_text) <= 3
    )


def reference_number_has_tab_separator(text: str | None) -> bool:
    prefix = parse_reference_number_prefix(text)
    return bool(
        is_plain_reference_number_prefix(prefix)
        and prefix.separator == "\t"
        and prefix.remainder
        and not prefix.remainder[0].isspace()
    )


def reference_number_has_space_separator(text: str | None) -> bool:
    prefix = parse_reference_number_prefix(text)
    return bool(
        is_plain_reference_number_prefix(prefix)
        and prefix.separator == " "
        and prefix.remainder
        and not prefix.remainder[0].isspace()
    )


def reference_number_has_compact_separator(text: str | None) -> bool:
    prefix = parse_reference_number_prefix(text)
    return bool(
        is_plain_reference_number_prefix(prefix)
        and prefix.separator == ""
        and prefix.remainder
        and not prefix.remainder[0].isspace()
    )


def is_plain_reference_number_prefix(prefix: ReferenceNumberPrefix | None) -> bool:
    return _has_plain_reference_number(prefix)


def paragraph_has_reference_tab(p_elem) -> bool:
    if p_elem.find(".//w:tab", NSMAP) is not None:
        return True
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        if text_elem.text and "\t" in text_elem.text:
            return True
    return False


def reference_paragraph_text_with_tabs(p_elem) -> str:
    parts = []
    for child in p_elem:
        if child.tag == f"{{{W_NS}}}pPr":
            continue
        for elem in child.iter():
            if elem.tag == f"{{{W_NS}}}t":
                parts.append(elem.text or "")
            elif elem.tag == f"{{{W_NS}}}tab":
                parts.append("\t")
    return "".join(parts)


def paragraph_has_reference_number_tab(p_elem) -> bool:
    return reference_number_has_tab_separator(reference_paragraph_text_with_tabs(p_elem))


def _get_w_attr(elem, attr_name: str) -> str | None:
    return elem.get(f"{{{W_NS}}}{attr_name}") if elem is not None else None


def has_valid_reference_tab_stop(p_elem, min_pos: int) -> bool:
    tabs = p_elem.find("w:pPr/w:tabs", NSMAP)
    if tabs is None:
        return False
    for tab in tabs.findall("w:tab", NSMAP):
        pos = parse_int(_get_w_attr(tab, "pos"))
        if _get_w_attr(tab, "val") == "left" and pos is not None and pos >= min_pos:
            return True
    return False
