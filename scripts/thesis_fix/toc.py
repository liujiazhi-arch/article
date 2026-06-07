from __future__ import annotations

import xml.etree.ElementTree as ET

from thesis_fix.dependencies import require


def fix_insert_toc(document_root, cfg=None, style_map=None, runtime=None, repair_keywords=True):
    (
        NSMAP,
        W_NS,
        _is_any_keywords_text,
        _is_frontmatter_title_text,
        _toc_level_from_style_id,
        _toc_title_for_runtime,
        build_settings_with_update_fields,
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
        "build_settings_with_update_fields",
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
    目录条目：宋体，小四（24 half-pts），H1不缩进，H2缩进2字符，H3缩进4字符。

    返回值：dict，key为docx内文件路径，value为bytes（用于写入settings.xml的updateFields）。
    如果 cfg 为 None 或 toc_auto 为 False，返回空 dict。
    """
    if cfg is None or not cfg.get("toc_auto"):
        return {}

    body = document_root.find("w:body", NSMAP)
    if body is None:
        return {}

    if repair_keywords:
        repair_misplaced_abstract_keywords(document_root, style_map=style_map)
    remove_existing_toc_artifacts(document_root)

    has_heading = False

    for p_elem in body.findall("w:p", NSMAP):
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
        if level is None:
            continue
        if text:
            has_heading = True
            break

    if not has_heading:
        return {}

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
        set_attr(spacing, "after", "0")
        add_run(
            p_elem,
            text=toc_title,
            east_asia=str(cfg.get("toc_title_font", "黑体") or "黑体"),
            size=str(cfg.get("toc_title_size", 32) or 32),
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
        set_attr(fld_begin, "dirty", "true")

        run_instr = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        instr_text = ET.SubElement(run_instr, f"{{{W_NS}}}instrText")
        instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instr_text.text = f' TOC \\o "1-{max_level}" \\h \\z \\u '

        run_sep = ET.SubElement(p_elem, f"{{{W_NS}}}r")
        fld_sep = ET.SubElement(run_sep, f"{{{W_NS}}}fldChar")
        set_attr(fld_sep, "fldCharType", "separate")
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

    new_paragraphs = [
        make_toc_title_para(),
        make_toc_field_begin(),
        make_toc_field_end(),
        make_page_break_para(),
    ]

    body_children = list(body)
    insert_index = None

    for idx, child in enumerate(body_children):
        if child.tag != f"{{{W_NS}}}p":
            continue
        text = get_paragraph_text(child).strip()
        if not text:
            continue
        if _is_any_keywords_text(text):
            continue
        if classify_paragraph(child, style_map or {}) != "h1":
            continue
        if _is_frontmatter_title_text(text):
            continue
        if detect_backmatter_bucket(text, "h1") is not None:
            continue
        insert_index = idx
        break
    if insert_index is None:
        sect_pr = body.find("w:sectPr", NSMAP)
        insert_index = list(body).index(sect_pr) if sect_pr is not None else len(body_children)

    for offset, para in enumerate(new_paragraphs):
        body.insert(insert_index + offset, para)

    return {"word/settings.xml": build_settings_with_update_fields()}
