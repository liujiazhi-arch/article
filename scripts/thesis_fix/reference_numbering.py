from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS
from reference_numbering_utils import (
    paragraph_has_reference_number_tab,
    paragraph_has_reference_tab,
    parse_reference_number_prefix,
)
from sections._xml_helpers import get_run_text


XML_SPACE_NS = "http://www.w3.org/XML/1998/namespace"


def ensure_reference_number_spacing(p_elem):
    runs = [run_elem for run_elem in p_elem.findall(".//w:r", NSMAP) if get_run_text(run_elem)]
    for idx, run_elem in enumerate(runs):
        text = get_run_text(run_elem)
        text_elems = [t_elem for t_elem in run_elem.findall(".//w:t", NSMAP) if t_elem.text is not None]
        if not text_elems:
            continue

        updated = re.sub(r"^(\[\d{1,3}\])(?=\S)", r"\1 ", text_elems[0].text or "", count=1)
        if updated != (text_elems[0].text or ""):
            text_elems[0].text = updated
            text_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
            return

        if not re.fullmatch(r"\s*\[\d{1,3}\]\s*", text):
            continue

        next_text = ""
        for next_run in runs[idx + 1 :]:
            next_text = get_run_text(next_run)
            if next_text:
                break

        if next_text.startswith((" ", "\u00a0")):
            return

        text_elems[-1].text = (text_elems[-1].text or "") + " "
        text_elems[-1].set(f"{{{XML_SPACE_NS}}}space", "preserve")
        return


def normalize_reference_number_leading_zeros(p_elem):
    """将参考文献编号规范为 [N] 内容，禁止前导零和多余空格。"""
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        text_elems = [t_elem for t_elem in run_elem.findall(".//w:t", NSMAP) if t_elem.text is not None]
        if not text_elems:
            continue
        original = text_elems[0].text or ""
        prefix = parse_reference_number_prefix(original)
        if prefix is None:
            return
        suffix = f" {prefix.remainder}" if prefix.remainder else ""
        updated = f"{prefix.leading}[{prefix.number}]{suffix}"
        if updated != original:
            text_elems[0].text = updated
            text_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
        return


def _remove_tab_after_ref_number(p_elem):
    runs = p_elem.findall(f".//{{{W_NS}}}r")
    for run in list(runs):
        if run.find(f"{{{W_NS}}}tab") is not None:
            parent = p_elem if run in list(p_elem) else None
            if parent is None:
                continue
            idx = list(parent).index(run)
            parent.remove(run)
            if idx > 0:
                prev_run = list(parent)[idx - 1]
                prev_texts = prev_run.findall(f".//{{{W_NS}}}t")
                if prev_texts:
                    prev_texts[-1].text = (prev_texts[-1].text or "") + " "
                    prev_texts[-1].set(f"{{{XML_SPACE_NS}}}space", "preserve")
            break

    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is None:
        return
    tabs = p_pr.find("w:tabs", NSMAP)
    if tabs is None:
        return
    for tab in list(tabs.findall("w:tab", NSMAP)):
        tabs.remove(tab)
    if not list(tabs):
        p_pr.remove(tabs)


def _remove_reference_tabs(p_elem):
    parent_map = {child: parent for parent in p_elem.iter() for child in parent}
    for run in list(p_elem.findall(".//w:r", NSMAP)):
        tabs = list(run.findall("w:tab", NSMAP))
        if not tabs:
            continue
        for tab in tabs:
            run.remove(tab)
        non_properties = [child for child in run if child.tag != f"{{{W_NS}}}rPr"]
        parent = parent_map.get(run)
        if not non_properties and parent is not None:
            parent.remove(run)


def _inject_tab_after_ref_number(p_elem):
    inline_tabs = p_elem.findall(".//w:r/w:tab", NSMAP)
    if paragraph_has_reference_number_tab(p_elem) and len(inline_tabs) == 1:
        return
    target = None
    for run in p_elem.findall(".//w:r", NSMAP):
        text_elems = run.findall(".//w:t", NSMAP)
        text = "".join(elem.text or "" for elem in text_elems)
        match = re.match(r"^(\[\d+\])[ \u00a0]*(.*)$", text, re.DOTALL)
        if match:
            target = (run, text_elems, match.group(1), match.group(2))
            break
        if text.strip():
            return
    if target is None:
        return

    run, text_elems, number_text, remainder = target
    _remove_reference_tabs(p_elem)
    parent_map = {child: parent for parent in p_elem.iter() for child in parent}
    parent = parent_map.get(run)
    if parent is None:
        return
    text_elems[0].text = number_text
    text_elems[0].attrib.pop(f"{{{XML_SPACE_NS}}}space", None)
    for extra in text_elems[1:]:
        extra.text = ""

    insert_at = list(parent).index(run) + 1
    rpr = run.find("w:rPr", NSMAP)
    tab_run = ET.Element(f"{{{W_NS}}}r")
    if rpr is not None:
        tab_run.append(copy.deepcopy(rpr))
    ET.SubElement(tab_run, f"{{{W_NS}}}tab")
    parent.insert(insert_at, tab_run)
    if remainder:
        text_run = ET.Element(f"{{{W_NS}}}r")
        if rpr is not None:
            text_run.append(copy.deepcopy(rpr))
        ET.SubElement(text_run, f"{{{W_NS}}}t").text = remainder
        parent.insert(insert_at + 1, text_run)
