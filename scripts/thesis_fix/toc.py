from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from thesis_fix.dependencies import require


BODY_TOC_BOOKMARK_NAME = "BodyTocRange"


def fix_insert_toc(document_root, cfg=None, style_map=None, runtime=None, repair_keywords=True):
    (
        NSMAP,
        W_NS,
        _is_any_keywords_text,
        _is_frontmatter_title_text,
        _toc_level_from_style_id,
        _toc_title_for_runtime,
        classify_paragraph,
        detect_backmatter_bucket,
        get_paragraph_text,
        match_heading_by_text,
        remove_existing_toc_artifacts,
        repair_misplaced_abstract_keywords,
        set_attr,
    ) = require(
        "NSMAP",
        "W_NS",
        "_is_any_keywords_text",
        "_is_frontmatter_title_text",
        "_toc_level_from_style_id",
        "_toc_title_for_runtime",
        "classify_paragraph",
        "detect_backmatter_bucket",
        "get_paragraph_text",
        "match_heading_by_text",
        "remove_existing_toc_artifacts",
        "repair_misplaced_abstract_keywords",
        "set_attr",
    )
    """
    在文档顶部插入辽大格式目录。
    目录标题：黑体，三号（32 half-pts），居中。
    目录条目：一级黑体四号（28 half-pts），二三级宋体小四（24 half-pts）。

    返回值：dict，key为docx内文件路径，value为bytes。
    如果 cfg 为 None 或 toc_auto 为 False，返回空 dict。
    """
    if cfg is None or not cfg.get("toc_auto"):
        return {}

    body = document_root.find("w:body", NSMAP)
    if body is None:
        return {}

    if repair_keywords:
        repair_misplaced_abstract_keywords(document_root, style_map=style_map)
    existing_page_numbers = _collect_existing_toc_page_numbers(body, get_paragraph_text, W_NS)
    remove_existing_toc_artifacts(document_root)
    _remove_bookmark_range(document_root, BODY_TOC_BOOKMARK_NAME, NSMAP, W_NS)
    body_children = list(body)

    def paragraph_toc_level(p_elem):
        level = None
        if style_map is not None:
            paragraph_type = classify_paragraph(p_elem, style_map)
            if paragraph_type in {"h1", "h2", "h3"}:
                level = int(paragraph_type[1])

        if level is None:
            p_pr = p_elem.find("w:pPr", NSMAP)
            if p_pr is None:
                p_pr = None
            else:
                outline_lvl = p_pr.find("w:outlineLvl", NSMAP)
                if outline_lvl is not None:
                    lvl_val = outline_lvl.get(f"{{{W_NS}}}val")
                    if lvl_val in {"0", "1", "2"}:
                        level = int(lvl_val) + 1

                if level is None:
                    p_style = p_pr.find("w:pStyle", NSMAP)
                    style_val = p_style.get(f"{{{W_NS}}}val", "") if p_style is not None else ""
                    level = _toc_level_from_style_id(style_val)

        text = get_paragraph_text(p_elem).strip()
        if level is None:
            text_level = match_heading_by_text(text)
            if text_level in {1, 2, 3}:
                level = text_level
        return level

    max_level = max(1, min(int(cfg.get("toc_max_level", 3) or 3), 3))
    toc_title = _toc_title_for_runtime(cfg, runtime=runtime)

    def add_run(parent, text=None, east_asia="宋体", ascii_font="Times New Roman", size="24", bold=False):
        run_elem = ET.SubElement(parent, f"{{{W_NS}}}r")
        r_pr = ET.SubElement(run_elem, f"{{{W_NS}}}rPr")
        r_fonts = ET.SubElement(r_pr, f"{{{W_NS}}}rFonts")
        set_attr(r_fonts, "eastAsia", east_asia)
        set_attr(r_fonts, "ascii", ascii_font)
        set_attr(r_fonts, "hAnsi", ascii_font)
        sz = ET.SubElement(r_pr, f"{{{W_NS}}}sz")
        set_attr(sz, "val", size)
        sz_cs = ET.SubElement(r_pr, f"{{{W_NS}}}szCs")
        set_attr(sz_cs, "val", size)
        if bold:
            b_elem = ET.SubElement(r_pr, f"{{{W_NS}}}b")
            set_attr(b_elem, "val", "1")
        if text is not None:
            text_elem = ET.SubElement(run_elem, f"{{{W_NS}}}t")
            text_elem.text = text
            if text.startswith(" ") or text.endswith(" "):
                text_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        return run_elem

    def add_tab_run(parent, east_asia="宋体", ascii_font="Times New Roman", size="24", bold=False):
        run_elem = add_run(parent, east_asia=east_asia, ascii_font=ascii_font, size=size, bold=bold)
        ET.SubElement(run_elem, f"{{{W_NS}}}tab")
        return run_elem

    def make_toc_title_para():
        p_elem = ET.Element(f"{{{W_NS}}}p")
        p_pr = ET.SubElement(p_elem, f"{{{W_NS}}}pPr")
        p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        set_attr(p_style, "val", "TOCHeading")
        page_break_before = ET.SubElement(p_pr, f"{{{W_NS}}}pageBreakBefore")
        set_attr(page_break_before, "val", "1")
        jc = ET.SubElement(p_pr, f"{{{W_NS}}}jc")
        set_attr(jc, "val", "center")
        spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
        set_attr(spacing, "before", "0")
        set_attr(spacing, "after", str(int(float(cfg.get("toc_title_after_pt", 5) or 5) * 20)))
        set_attr(spacing, "line", str(int(cfg.get("toc_title_line", cfg.get("toc_entry_line", 276)) or 276)))
        set_attr(spacing, "lineRule", "auto")
        add_run(
            p_elem,
            text=toc_title,
            east_asia=str(cfg.get("toc_title_font", "黑体") or "黑体"),
            size=str(cfg.get("toc_title_size", 32) or 32),
            bold=False,
        )
        return p_elem

    def make_toc_field_begin():
        p_elem = ET.Element(f"{{{W_NS}}}p")
        p_pr = ET.SubElement(p_elem, f"{{{W_NS}}}pPr")
        p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        set_attr(p_style, "val", "TOCField")
        spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
        set_attr(spacing, "before", "0")
        set_attr(spacing, "after", "0")

        run_begin = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        fld_begin = ET.SubElement(run_begin, f"{{{W_NS}}}fldChar")
        set_attr(fld_begin, "fldCharType", "begin")

        run_instr = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        instr_text = ET.SubElement(run_instr, f"{{{W_NS}}}instrText")
        instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instr_text.text = f' TOC \\o "1-{max_level}" \\h \\z \\u \\b {BODY_TOC_BOOKMARK_NAME} '

        run_sep = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        fld_sep = ET.SubElement(run_sep, f"{{{W_NS}}}fldChar")
        set_attr(fld_sep, "fldCharType", "separate")
        return p_elem

    def make_toc_result_entry(text, level):
        level = max(1, min(int(level or 1), max_level))
        p_elem = ET.Element(f"{{{W_NS}}}p")
        p_pr = ET.SubElement(p_elem, f"{{{W_NS}}}pPr")
        p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        set_attr(p_style, "val", f"TOC{level}")

        if level > 1:
            ind = ET.SubElement(p_pr, f"{{{W_NS}}}ind")
            set_attr(ind, "left", str((level - 1) * int(cfg.get("toc_indent_step", 420) or 420)))
            set_attr(ind, "firstLine", "0")

        tabs = ET.SubElement(p_pr, f"{{{W_NS}}}tabs")
        tab = ET.SubElement(tabs, f"{{{W_NS}}}tab")
        set_attr(tab, "val", "right")
        set_attr(tab, "leader", "dot")
        set_attr(tab, "pos", str(int(cfg.get("toc_tab_pos", 9000) or 9000)))

        spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
        set_attr(spacing, "before", "0")
        after_pt = float(cfg.get(f"toc_level{level}_after_pt", cfg.get("toc_level1_after_pt", 5)) or 5)
        set_attr(spacing, "after", str(int(after_pt * 20)))
        set_attr(spacing, "line", str(int(cfg.get("toc_entry_line", 276) or 276)))
        set_attr(spacing, "lineRule", "auto")

        if level == 1:
            entry_font = str(cfg.get("toc_level1_font", cfg.get("toc_entry_font", "黑体")) or "黑体")
            entry_size = str(int(cfg.get("toc_level1_size", cfg.get("toc_entry_size", 28)) or 28))
            entry_bold = False
        else:
            entry_font = str(cfg.get("toc_entry_font", "宋体") or "宋体")
            entry_size = str(int(cfg.get("toc_entry_size", 22) or 22))
            entry_bold = False

        clean_text, inherited_page_number = _strip_toc_entry_page_number(text)
        page_number = existing_page_numbers.get(
            _toc_page_lookup_key(clean_text),
            inherited_page_number or "",
        )
        add_run(p_elem, text=clean_text, east_asia=entry_font, size=entry_size, bold=entry_bold)
        if page_number:
            add_tab_run(p_elem, east_asia=entry_font, size=entry_size, bold=entry_bold)
            add_run(p_elem, text=page_number, east_asia=entry_font, size=entry_size, bold=entry_bold)
        return p_elem

    def make_toc_field_end():
        p_elem = ET.Element(f"{{{W_NS}}}p")
        p_pr = ET.SubElement(p_elem, f"{{{W_NS}}}pPr")
        p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        set_attr(p_style, "val", "TOCEnd")
        spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
        set_attr(spacing, "before", "0")
        set_attr(spacing, "after", "0")
        run_end = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        fld_end = ET.SubElement(run_end, f"{{{W_NS}}}fldChar")
        set_attr(fld_end, "fldCharType", "end")
        return p_elem

    def make_page_break_para():
        p_elem = ET.Element(f"{{{W_NS}}}p")
        p_pr = ET.SubElement(p_elem, f"{{{W_NS}}}pPr")
        p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        set_attr(p_style, "val", "TOCPageBreak")
        spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
        set_attr(spacing, "before", "0")
        set_attr(spacing, "after", "0")
        run_elem = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        br_elem = ET.SubElement(run_elem, f"{{{W_NS}}}br")
        set_attr(br_elem, "type", "page")
        return p_elem

    insert_index = None

    for idx, child in enumerate(body_children):
        if child.tag != f"{{{W_NS}}}p":
            continue
        text = get_paragraph_text(child).strip()
        if not text:
            continue
        if _is_any_keywords_text(text):
            continue
        if paragraph_toc_level(child) != 1:
            continue
        if _is_frontmatter_title_text(text):
            continue
        if detect_backmatter_bucket(text, "h1") is not None:
            continue
        insert_index = idx
        break
    if insert_index is None:
        return {}

    toc_headings = []
    for child in body_children[insert_index:]:
        if child.tag != f"{{{W_NS}}}p":
            continue
        text = get_paragraph_text(child).strip()
        if not text:
            continue
        level = paragraph_toc_level(child)
        if level is None or level > max_level:
            continue
        toc_headings.append((text, level))

    if not toc_headings:
        return {}

    new_paragraphs = [
        make_toc_title_para(),
        make_toc_field_begin(),
        *(make_toc_result_entry(text, level) for text, level in toc_headings),
        make_toc_field_end(),
        make_page_break_para(),
    ]

    bookmark_added = _add_body_toc_bookmark(
        document_root,
        body_children,
        insert_index,
        BODY_TOC_BOOKMARK_NAME,
        NSMAP,
        W_NS,
        set_attr,
    )
    if not bookmark_added:
        return {}

    for offset, para in enumerate(new_paragraphs):
        body.insert(insert_index + offset, para)

    return {}


def _toc_page_lookup_key(text):
    return re.sub(r"[\s\u3000]+", "", str(text or "")).strip().lower()


def _extract_visible_toc_entry_text_and_page(text):
    stripped = str(text or "").strip()
    if not stripped:
        return None
    tab_match = re.match(r"^(.*?)\t\s*([0-9A-Za-zivxlcdmIVXLCDM]+)\s*$", stripped)
    if tab_match is not None:
        return tab_match.group(1).strip(), tab_match.group(2).strip()
    leader_match = re.match(r"^(.*?)[\.·•…]{2,}\s*([0-9A-Za-zivxlcdmIVXLCDM]+)\s*$", stripped)
    if leader_match is not None:
        return leader_match.group(1).strip(), leader_match.group(2).strip()
    return None


def _strip_toc_entry_page_number(text):
    extracted = _extract_visible_toc_entry_text_and_page(text)
    if extracted is None:
        return str(text or "").strip(), None
    return extracted


def _collect_existing_toc_page_numbers(body, get_paragraph_text, w_ns):
    page_numbers = {}
    in_toc = False
    for child in list(body):
        if child.tag != f"{{{w_ns}}}p":
            if in_toc:
                break
            continue
        text = str(get_paragraph_text(child) or "").strip()
        normalized = _toc_page_lookup_key(text)
        if normalized == "目录":
            in_toc = True
            continue
        if not in_toc:
            continue
        if not text:
            continue
        extracted = _extract_visible_toc_entry_text_and_page(text)
        if extracted is None:
            break
        entry_text, page_number = extracted
        if entry_text:
            page_numbers.setdefault(_toc_page_lookup_key(entry_text), page_number)
    return page_numbers


def _remove_bookmark_range(document_root, bookmark_name, nsmap, w_ns):
    bookmark_start_tag = f"{{{w_ns}}}bookmarkStart"
    bookmark_end_tag = f"{{{w_ns}}}bookmarkEnd"
    target_ids = {
        elem.get(f"{{{w_ns}}}id")
        for elem in document_root.findall(".//w:bookmarkStart", nsmap)
        if elem.get(f"{{{w_ns}}}name") == bookmark_name
    }
    if not target_ids:
        return 0

    removed = 0
    for parent in document_root.iter():
        for child in list(parent):
            if child.tag == bookmark_start_tag and child.get(f"{{{w_ns}}}name") == bookmark_name:
                parent.remove(child)
                removed += 1
            elif child.tag == bookmark_end_tag and child.get(f"{{{w_ns}}}id") in target_ids:
                parent.remove(child)
                removed += 1
    return removed


def _next_bookmark_id(document_root, w_ns):
    used_ids = []
    for elem in document_root.iter():
        if elem.tag not in {f"{{{w_ns}}}bookmarkStart", f"{{{w_ns}}}bookmarkEnd"}:
            continue
        raw_id = elem.get(f"{{{w_ns}}}id")
        if raw_id is None:
            continue
        try:
            used_ids.append(int(raw_id))
        except ValueError:
            continue
    return str(max(used_ids, default=-1) + 1)


def _insert_bookmark_start(paragraph, bookmark_id, bookmark_name, nsmap, w_ns, set_attr):
    bookmark_start = ET.Element(f"{{{w_ns}}}bookmarkStart")
    set_attr(bookmark_start, "id", bookmark_id)
    set_attr(bookmark_start, "name", bookmark_name)

    p_pr = paragraph.find("w:pPr", nsmap)
    if p_pr is None:
        paragraph.insert(0, bookmark_start)
        return

    paragraph.insert(list(paragraph).index(p_pr) + 1, bookmark_start)


def _add_body_toc_bookmark(document_root, body_children, insert_index, bookmark_name, nsmap, w_ns, set_attr):
    if insert_index >= len(body_children):
        return False

    start_paragraph = body_children[insert_index]
    if start_paragraph.tag != f"{{{w_ns}}}p":
        return False

    end_paragraph = None
    for child in reversed(body_children[insert_index:]):
        if child.tag == f"{{{w_ns}}}p":
            end_paragraph = child
            break
    if end_paragraph is None:
        return False

    bookmark_id = _next_bookmark_id(document_root, w_ns)
    _insert_bookmark_start(start_paragraph, bookmark_id, bookmark_name, nsmap, w_ns, set_attr)

    bookmark_end = ET.Element(f"{{{w_ns}}}bookmarkEnd")
    set_attr(bookmark_end, "id", bookmark_id)
    end_paragraph.append(bookmark_end)
    return True
