import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS


def get_or_create(parent, tag):
    child = parent.find(tag, NSMAP)
    if child is None:
        child = ET.SubElement(parent, f"{{{W_NS}}}{tag.split(':', 1)[1]}")
    return child


def set_attr(elem, attr, value):
    elem.set(f"{{{W_NS}}}{attr}", value)


def get_run_text(run_elem):
    return "".join(t_elem.text or "" for t_elem in run_elem.findall(".//w:t", NSMAP))


def is_superscript(run_elem):
    vert_align = run_elem.find("w:rPr/w:vertAlign", NSMAP)
    return vert_align is not None and vert_align.get(f"{{{W_NS}}}val") == "superscript"


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


def get_paragraph_spacing_twips(p_elem, attr_name: str) -> int:
    spacing = p_elem.find("w:pPr/w:spacing", NSMAP)
    value = spacing.get(f"{{{W_NS}}}{attr_name}") if spacing is not None else None
    return int(value) if value and value.isdigit() else 0


def set_paragraph_spacing_attrs(p_elem, *, before=None, after=None, line=None):
    p_pr = ensure_ppr(p_elem)
    spacing = get_or_create(p_pr, "w:spacing")
    if before is not None:
        set_attr(spacing, "before", str(before))
    if after is not None:
        set_attr(spacing, "after", str(after))
    if line is not None:
        set_attr(spacing, "line", str(line))
        set_attr(spacing, "lineRule", "auto")


def set_onoff_property(parent_elem, tag_name: str, enabled: bool, *, insert_index: int | None = None) -> int:
    elem = parent_elem.find(f"w:{tag_name}", NSMAP)
    created = elem is None
    if elem is None:
        elem = ET.SubElement(parent_elem, f"{{{W_NS}}}{tag_name}")
    desired = "1" if enabled else "0"
    value_changed = elem.get(f"{{{W_NS}}}val") != desired
    if value_changed:
        set_attr(elem, "val", desired)
    order_changed = False
    if insert_index is not None and list(parent_elem).index(elem) != insert_index:
        parent_elem.remove(elem)
        parent_elem.insert(insert_index, elem)
        order_changed = True
    return int(created or value_changed or order_changed)


def is_onoff_enabled(elem) -> bool:
    if elem is None:
        return False
    val = elem.get(f"{{{W_NS}}}val")
    return val not in ("0", "false", "False", "off", "none")


def paragraph_onoff_enabled(p_elem, tag_name: str) -> bool:
    return is_onoff_enabled(p_elem.find(f"w:pPr/w:{tag_name}", NSMAP))


def table_row_cant_split_enabled(tr_elem) -> bool:
    return is_onoff_enabled(tr_elem.find("w:trPr/w:cantSplit", NSMAP))


def set_paragraph_pagination_flags(p_elem, *, keep_next: bool, keep_lines: bool, page_break_before: bool = False) -> int:
    p_pr = ensure_ppr(p_elem)
    p_style = p_pr.find("w:pStyle", NSMAP)
    insert_index = list(p_pr).index(p_style) + 1 if p_style is not None else 0
    changed = 0
    changed += set_onoff_property(p_pr, "keepNext", keep_next, insert_index=insert_index)
    changed += set_onoff_property(p_pr, "keepLines", keep_lines, insert_index=insert_index + 1)
    changed += set_onoff_property(p_pr, "pageBreakBefore", page_break_before, insert_index=insert_index + 2)
    return changed


def set_table_row_cant_split(tr_elem, enabled: bool = True) -> int:
    tr_pr = tr_elem.find("w:trPr", NSMAP)
    if tr_pr is None:
        tr_pr = ET.SubElement(tr_elem, f"{{{W_NS}}}trPr")
    return set_onoff_property(tr_pr, "cantSplit", enabled)


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
