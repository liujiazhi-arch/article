from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS
from reference_numbering_utils import paragraph_has_reference_tab, parse_reference_number_prefix
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


def _inject_tab_after_ref_number(p_elem):
    """
    将参考文献编号 [N] 后紧跟的空格替换为 <w:tab/>，实现精确对齐。
    注意：只检查文本 run 中的 <w:tab/>（不包括 pPr 里的制表位定义）。
    """
    for run in p_elem.findall(f".//{{{W_NS}}}r"):
        if run.find(f"{{{W_NS}}}tab") is not None:
            return

    runs = p_elem.findall(f".//{{{W_NS}}}r")
    if not runs:
        return

    for run in runs:
        t_elems = run.findall(f"{{{W_NS}}}t")
        text = "".join(t.text or "" for t in t_elems)
        if not text.strip():
            continue

        match = re.match(r"^(\[\d+\])([ \u00a0]+)(.*)", text, re.DOTALL)
        if not match:
            break

        num_part = match.group(1)
        rest_part = match.group(3)

        if len(t_elems) == 1:
            t_elems[0].text = num_part
            t_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
        else:
            t_elems[0].text = num_part
            for text_elem in t_elems[1:]:
                run.remove(text_elem)

        children = list(p_elem)
        if run not in children:
            break

        rpr = run.find(f"{{{W_NS}}}rPr")
        idx = children.index(run)

        tab_run = ET.Element(f"{{{W_NS}}}r")
        if rpr is not None:
            tab_run.append(copy.deepcopy(rpr))
        ET.SubElement(tab_run, f"{{{W_NS}}}tab")
        p_elem.insert(idx + 1, tab_run)

        if rest_part:
            text_run = ET.Element(f"{{{W_NS}}}r")
            if rpr is not None:
                text_run.append(copy.deepcopy(rpr))
            t_new = ET.SubElement(text_run, f"{{{W_NS}}}t")
            t_new.text = rest_part
            t_new.set(f"{{{XML_SPACE_NS}}}space", "preserve")
            p_elem.insert(idx + 2, text_run)
        break
