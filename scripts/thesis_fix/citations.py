from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

from citation_text_utils import (
    CITATION_TOKEN_RE,
    CITATION_TOKEN_SPLIT_RE,
    citation_numbers_from_token as _citation_run_numbers,
    format_citation_numbers as _format_citation_numbers,
)
from _thesis_utils import NSMAP, W_NS
from sections._xml_helpers import ensure_rfonts, get_run_text, is_superscript, set_attr


XML_SPACE_NS = "http://www.w3.org/XML/1998/namespace"
CITATION_RUN_RE = CITATION_TOKEN_RE


def fix_superscript_fonts(p_elem):
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if not is_superscript(run_elem):
            continue
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "ascii", "Times New Roman")
        set_attr(r_fonts, "hAnsi", "Times New Roman")
        set_attr(r_fonts, "eastAsia", "Times New Roman")


def split_inline_citations(p_elem):
    """将正文 run 中混入的 [N] 引用拆分为独立上标 run。"""
    parent_map = {child: parent for parent in p_elem.iter() for child in parent}

    for run_elem in list(p_elem.findall(".//w:r", NSMAP)):
        run_text = get_run_text(run_elem)
        if is_superscript(run_elem):
            continue
        if not CITATION_RUN_RE.search(run_text):
            continue
        parts = CITATION_TOKEN_SPLIT_RE.split(run_text)
        if len(parts) <= 1:
            continue

        parent = parent_map.get(run_elem)
        if parent is None:
            continue
        idx = list(parent).index(run_elem)

        base_rpr = run_elem.find("w:rPr", NSMAP)
        new_runs = []
        for part in parts:
            if not part:
                continue
            new_run = ET.Element(f"{{{W_NS}}}r")
            new_rpr = copy.deepcopy(base_rpr) if base_rpr is not None else ET.Element(f"{{{W_NS}}}rPr")
            if CITATION_RUN_RE.fullmatch(part):
                for va in list(new_rpr.findall("w:vertAlign", NSMAP)):
                    new_rpr.remove(va)
                vert = ET.SubElement(new_rpr, f"{{{W_NS}}}vertAlign")
                vert.set(f"{{{W_NS}}}val", "superscript")
                r_fonts = new_rpr.find("w:rFonts", NSMAP)
                if r_fonts is None:
                    r_fonts = ET.SubElement(new_rpr, f"{{{W_NS}}}rFonts")
                for attr in ("ascii", "hAnsi", "eastAsia"):
                    r_fonts.set(f"{{{W_NS}}}{attr}", "Times New Roman")
            new_run.insert(0, new_rpr)
            t_elem = ET.SubElement(new_run, f"{{{W_NS}}}t")
            t_elem.text = part
            if part.startswith(" ") or part.endswith(" "):
                t_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
            new_runs.append(new_run)

        parent.remove(run_elem)
        for offset, new_run in enumerate(new_runs):
            parent.insert(idx + offset, new_run)


def _set_run_text(run_elem, text):
    text_elems = run_elem.findall(".//w:t", NSMAP)
    if not text_elems:
        text_elem = ET.SubElement(run_elem, f"{{{W_NS}}}t")
        text_elem.text = text
        return
    text_elems[0].text = text
    for extra_text in text_elems[1:]:
        extra_text.text = ""


def _merge_adjacent_superscript_citation_runs(p_elem):
    changed = False
    children = list(p_elem)
    index = 0
    while index < len(children):
        run_elem = children[index]
        if run_elem.tag != f"{{{W_NS}}}r" or not is_superscript(run_elem):
            index += 1
            continue
        run_text = get_run_text(run_elem)
        if not CITATION_RUN_RE.fullmatch(run_text or ""):
            index += 1
            continue

        numbers = _citation_run_numbers(run_text)
        group_end = index
        while group_end + 1 < len(children):
            next_run = children[group_end + 1]
            next_text = get_run_text(next_run)
            if (
                next_run.tag != f"{{{W_NS}}}r"
                or not is_superscript(next_run)
                or not CITATION_RUN_RE.fullmatch(next_text or "")
            ):
                break
            numbers.extend(_citation_run_numbers(next_text))
            group_end += 1

        normalized = _format_citation_numbers(numbers)
        if normalized != run_text:
            _set_run_text(run_elem, normalized)
            changed = True
        for remove_index in range(group_end, index, -1):
            p_elem.remove(children[remove_index])
            changed = True
        children = list(p_elem)
        index += 1
    return changed


def move_superscript_citations_before_terminal_punct(p_elem):
    children = list(p_elem)
    idx = 0
    while idx < len(children):
        run_elem = children[idx]
        if run_elem.tag != f"{{{W_NS}}}r":
            idx += 1
            continue
        if not is_superscript(run_elem):
            idx += 1
            continue
        run_text = get_run_text(run_elem)
        if not CITATION_RUN_RE.fullmatch(run_text or ""):
            idx += 1
            continue
        prev_idx = idx - 1
        if prev_idx < 0:
            idx += 1
            continue
        prev_run = children[prev_idx]
        if prev_run.tag != f"{{{W_NS}}}r":
            idx += 1
            continue
        prev_text_elems = [t for t in prev_run.findall(f".//{{{W_NS}}}t") if t.text]
        if not prev_text_elems:
            idx += 1
            continue
        prev_text = prev_text_elems[-1].text or ""
        if not prev_text or prev_text[-1] not in "。！？!?":
            idx += 1
            continue

        punct = prev_text[-1]
        prev_text_elems[-1].text = prev_text[:-1]

        insert_at = idx + 1
        while insert_at < len(children):
            next_run = children[insert_at]
            if next_run.tag != f"{{{W_NS}}}r":
                break
            if not is_superscript(next_run):
                break
            next_text = get_run_text(next_run)
            if not CITATION_RUN_RE.fullmatch(next_text or ""):
                break
            insert_at += 1

        punct_run = ET.Element(f"{{{W_NS}}}r")
        prev_rpr = prev_run.find(f"{{{W_NS}}}rPr")
        if prev_rpr is not None:
            punct_run.append(copy.deepcopy(prev_rpr))
        t_elem = ET.SubElement(punct_run, f"{{{W_NS}}}t")
        t_elem.text = punct
        p_elem.insert(insert_at, punct_run)
        children = list(p_elem)
        idx = insert_at + 1
    _merge_adjacent_superscript_citation_runs(p_elem)
