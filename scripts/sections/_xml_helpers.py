import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS


def get_or_create(parent, tag):
    child = parent.find(tag, NSMAP)
    if child is None:
        child = ET.SubElement(parent, f"{{{W_NS}}}{tag.split(':', 1)[1]}")
    return child


def set_attr(elem, attr, value):
    elem.set(f"{{{W_NS}}}{attr}", value)


def ensure_rpr(run_elem):
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is None:
        r_pr = ET.Element(f"{{{W_NS}}}rPr")
        run_elem.insert(0, r_pr)
    return r_pr


def ensure_ppr(p_elem):
    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is None:
        p_pr = ET.Element(f"{{{W_NS}}}pPr")
        p_elem.insert(0, p_pr)
    return p_pr


def ensure_rfonts(run_elem):
    r_pr = ensure_rpr(run_elem)
    return get_or_create(r_pr, "w:rFonts")


def ensure_size(run_elem, value):
    r_pr = ensure_rpr(run_elem)
    sz = get_or_create(r_pr, "w:sz")
    set_attr(sz, "val", value)
    sz_cs = get_or_create(r_pr, "w:szCs")
    set_attr(sz_cs, "val", value)


def ensure_bold(run_elem):
    r_pr = ensure_rpr(run_elem)
    bold = get_or_create(r_pr, "w:b")
    set_attr(bold, "val", "1")


def remove_bold(run_elem):
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is None:
        return
    for bold in list(r_pr.findall("w:b", NSMAP)):
        r_pr.remove(bold)


def ensure_alignment_and_indent(p_elem, alignment, indent=None, no_indent=False):
    p_pr = ensure_ppr(p_elem)
    jc = get_or_create(p_pr, "w:jc")
    set_attr(jc, "val", alignment)
    ind = get_or_create(p_pr, "w:ind")
    if no_indent:
        indent = 0
    if indent is None:
        indent = 0
    set_attr(ind, "firstLine", str(indent))


def ensure_spacing(p_pr, before=None, after=None):
    spacing = get_or_create(p_pr, "w:spacing")
    if before is not None:
        set_attr(spacing, "before", str(before))
    if after is not None:
        set_attr(spacing, "after", str(after))
    return spacing


def insert_tabs_before_spacing(p_pr):
    tabs = p_pr.find("w:tabs", NSMAP)
    if tabs is None:
        tabs = ET.Element(f"{{{W_NS}}}tabs")
        spacing = p_pr.find("w:spacing", NSMAP)
        if spacing is None:
            p_pr.append(tabs)
        else:
            insert_at = list(p_pr).index(spacing)
            p_pr.insert(insert_at, tabs)
    return tabs
