from __future__ import annotations

import copy
import os
import xml.etree.ElementTree as ET

from thesis_fix.dependencies import require


def fix_footer_page_number(temp_dir, document_root, cfg=None, runtime=None):
    (
        CONTENT_TYPES_NS,
        FOOTER_REL_TYPES,
        NSMAP,
        PACKAGE_REL_NS,
        REL_NS,
        W_NS,
        _is_frontmatter_title_text,
        ensure_ppr,
        ensure_rfonts,
        ensure_rpr,
        ensure_size,
        get_or_create,
        get_paragraph_text,
        get_run_text,
        resolve_fix_cfg,
        set_attr,
    ) = require(
        "CONTENT_TYPES_NS",
        "FOOTER_REL_TYPES",
        "NSMAP",
        "PACKAGE_REL_NS",
        "REL_NS",
        "W_NS",
        "_is_frontmatter_title_text",
        "ensure_ppr",
        "ensure_rfonts",
        "ensure_rpr",
        "ensure_size",
        "get_or_create",
        "get_paragraph_text",
        "get_run_text",
        "resolve_fix_cfg",
        "set_attr",
    )
    active_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    cfg = active_cfg
    rels_path = os.path.join(temp_dir, "word", "_rels", "document.xml.rels")
    content_types_path = os.path.join(temp_dir, "[Content_Types].xml")

    def _page_wrap_chars(active_cfg):
        page_style = (active_cfg or {}).get("pg01_format")
        if page_style == "hyphen_wrap":
            return "-", "-"
        if page_style == "em_dash":
            return "—", "—"
        return None, None

    def _apply_page_number_run_style(run_elem, *, hidden=False):
        r_pr = ensure_rpr(run_elem)
        if hidden:
            vanish = get_or_create(r_pr, "w:vanish")
            set_attr(vanish, "val", "1")
        expected_font = cfg.get("page_number_font")
        expected_size = cfg.get("page_number_size")
        if expected_font:
            r_fonts = ensure_rfonts(run_elem)
            set_attr(r_fonts, "eastAsia", expected_font)
            set_attr(r_fonts, "ascii", "Times New Roman")
            set_attr(r_fonts, "hAnsi", "Times New Roman")
        if expected_size is not None:
            ensure_size(run_elem, str(expected_size))

    def build_footer_xml(cfg=None):
        footer_root = ET.Element(f"{{{W_NS}}}ftr")
        footer_p = ET.SubElement(footer_root, f"{{{W_NS}}}p")
        footer_ppr = ET.SubElement(footer_p, f"{{{W_NS}}}pPr")
        footer_jc = ET.SubElement(footer_ppr, f"{{{W_NS}}}jc")
        set_attr(footer_jc, "val", "center")

        def append_page_run(text=None, field_type=None, instr=None):
            run_elem = ET.SubElement(footer_p, f"{{{W_NS}}}r")
            _apply_page_number_run_style(run_elem)

            if text is not None:
                text_elem = ET.SubElement(run_elem, f"{{{W_NS}}}t")
                text_elem.text = text
            elif field_type is not None:
                fld_char = ET.SubElement(run_elem, f"{{{W_NS}}}fldChar")
                set_attr(fld_char, "fldCharType", field_type)
            else:
                instr_text = ET.SubElement(run_elem, f"{{{W_NS}}}instrText")
                instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                instr_text.text = instr

        left_wrap, right_wrap = _page_wrap_chars(cfg)
        if left_wrap is not None:
            append_page_run(text=left_wrap)
            append_page_run(field_type="begin")
            append_page_run(instr=" PAGE ")
            append_page_run(field_type="end")
            append_page_run(text=right_wrap)
        else:
            append_page_run(field_type="begin")
            append_page_run(instr=" PAGE ")
            append_page_run(field_type="end")

        return ET.tostring(footer_root, encoding="utf-8", xml_declaration=True)

    def append_hidden_page_field_marker():
        body = document_root.find("w:body", NSMAP)
        if body is None:
            raise ValueError("document.xml missing w:body")

        target_p = None
        for paragraph in body.findall("w:p", NSMAP):
            has_hidden_page_field = any(
                "PAGE" in (instr_text.text or "").upper()
                and any(
                    run.find("w:rPr/w:vanish", NSMAP) is not None
                    for run in paragraph.findall(".//w:r", NSMAP)
                )
                for instr_text in paragraph.findall(".//w:instrText", NSMAP)
            )
            if has_hidden_page_field:
                target_p = paragraph
                break
        if target_p is None:
            target_p = ET.Element(f"{{{W_NS}}}p")
            sect_pr = body.find("w:sectPr", NSMAP)
            if sect_pr is None:
                body.append(target_p)
            else:
                body.insert(list(body).index(sect_pr), target_p)

        target_p_pr = ensure_ppr(target_p)
        target_spacing = get_or_create(target_p_pr, "w:spacing")
        set_attr(target_spacing, "line", str(active_cfg.get("body_line", 360)))
        set_attr(target_spacing, "lineRule", "auto")
        target_ind = get_or_create(target_p_pr, "w:ind")
        set_attr(target_ind, "firstLine", "480")
        target_jc = get_or_create(target_p_pr, "w:jc")
        set_attr(target_jc, "val", "both")
        target_auto_de = get_or_create(target_p_pr, "w:autoSpaceDE")
        set_attr(target_auto_de, "val", "0")
        target_auto_dn = get_or_create(target_p_pr, "w:autoSpaceDN")
        set_attr(target_auto_dn, "val", "0")
        target_snap = target_p_pr.find("w:snapToGrid", NSMAP)
        if target_snap is None:
            target_snap = ET.SubElement(target_p_pr, f"{{{W_NS}}}snapToGrid")
        target_snap.set(f"{{{W_NS}}}val", "0")

        has_page_field = any(
            "PAGE" in (instr_text.text or "").upper()
            for instr_text in document_root.findall(".//w:instrText", NSMAP)
        )
        left_wrap, right_wrap = _page_wrap_chars(cfg)
        needs_wrap = left_wrap is not None
        has_wrap = any((left_wrap or "") in (text_elem.text or "") for text_elem in document_root.findall(".//w:t", NSMAP))

        def new_hidden_run():
            run_elem = ET.SubElement(target_p, f"{{{W_NS}}}r")
            _apply_page_number_run_style(run_elem, hidden=True)
            return run_elem

        if has_page_field and (not needs_wrap or has_wrap):
            return

        if needs_wrap and not has_wrap:
            run_left_dash = new_hidden_run()
            text_left_dash = ET.SubElement(run_left_dash, f"{{{W_NS}}}t")
            text_left_dash.text = left_wrap

        if has_page_field:
            if needs_wrap and not has_wrap:
                run_right_dash = new_hidden_run()
                text_right_dash = ET.SubElement(run_right_dash, f"{{{W_NS}}}t")
                text_right_dash.text = right_wrap
            return

        run_begin = new_hidden_run()
        fld_begin = ET.SubElement(run_begin, f"{{{W_NS}}}fldChar")
        set_attr(fld_begin, "fldCharType", "begin")

        run_instr = new_hidden_run()
        instr_text = ET.SubElement(run_instr, f"{{{W_NS}}}instrText")
        instr_text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instr_text.text = " PAGE "

        run_end = new_hidden_run()
        fld_end = ET.SubElement(run_end, f"{{{W_NS}}}fldChar")
        set_attr(fld_end, "fldCharType", "end")

        if needs_wrap:
            run_right_dash = new_hidden_run()
            text_right_dash = ET.SubElement(run_right_dash, f"{{{W_NS}}}t")
            text_right_dash.text = right_wrap

    def center_existing_footer_page_numbers(rels_root):
        def make_text_run(text, template_run=None):
            run_elem = ET.Element(f"{{{W_NS}}}r")
            if template_run is not None:
                r_pr = template_run.find("w:rPr", NSMAP)
                if r_pr is not None:
                    run_elem.append(copy.deepcopy(r_pr))
            _apply_page_number_run_style(run_elem)
            text_elem = ET.SubElement(run_elem, f"{{{W_NS}}}t")
            text_elem.text = text
            return run_elem

        def ensure_em_dash_wrapper(paragraph):
            left_wrap, right_wrap = _page_wrap_chars(cfg)

            direct_runs = [child for child in list(paragraph) if child.tag == f"{{{W_NS}}}r"]
            if not direct_runs:
                return False

            changed = False
            while direct_runs:
                first_text = get_run_text(direct_runs[0])
                if first_text not in {"-", "—"}:
                    break
                paragraph.remove(direct_runs[0])
                direct_runs = [child for child in list(paragraph) if child.tag == f"{{{W_NS}}}r"]
                changed = True
            while direct_runs:
                last_text = get_run_text(direct_runs[-1])
                if last_text not in {"-", "—"}:
                    break
                paragraph.remove(direct_runs[-1])
                direct_runs = [child for child in list(paragraph) if child.tag == f"{{{W_NS}}}r"]
                changed = True
            if not direct_runs:
                return changed
            if left_wrap is None:
                return changed

            begin_run = None
            end_run = None
            for run_elem in direct_runs:
                fld_char = run_elem.find("w:fldChar", NSMAP)
                if fld_char is not None and fld_char.get(f"{{{W_NS}}}fldCharType") == "begin":
                    begin_run = run_elem
                    break
            for run_elem in reversed(direct_runs):
                fld_char = run_elem.find("w:fldChar", NSMAP)
                if fld_char is not None and fld_char.get(f"{{{W_NS}}}fldCharType") == "end":
                    end_run = run_elem
                    break
            if begin_run is None or end_run is None:
                return changed

            children = list(paragraph)
            paragraph.insert(children.index(begin_run), make_text_run(left_wrap, template_run=direct_runs[0]))
            children = list(paragraph)
            paragraph.insert(children.index(end_run) + 1, make_text_run(right_wrap, template_run=end_run))
            return True

        updated = {}
        footer_rels = [
            rel for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
            if rel.get("Type") in FOOTER_REL_TYPES
        ]
        for rel in footer_rels:
            target = rel.get("Target") or ""
            footer_rel_path = os.path.normpath(os.path.join(temp_dir, "word", "_rels", target))
            footer_path = os.path.normpath(os.path.join(temp_dir, "word", target))
            if not footer_path.startswith(os.path.join(temp_dir, "word")):
                continue
            if target.startswith("/"):
                footer_rel_path = os.path.normpath(os.path.join(temp_dir, target.lstrip("/")))
                footer_path = footer_rel_path
            if not os.path.exists(footer_path):
                continue
            footer_root = ET.parse(footer_path).getroot()
            changed = False
            for paragraph in footer_root.findall(".//w:p", NSMAP):
                has_page_field = any(
                    "PAGE" in (instr_text.text or "").upper()
                    for instr_text in paragraph.findall(".//w:instrText", NSMAP)
                )
                if not has_page_field:
                    continue
                p_pr = paragraph.find("w:pPr", NSMAP)
                if p_pr is None:
                    p_pr = ET.Element(f"{{{W_NS}}}pPr")
                    paragraph.insert(0, p_pr)
                jc = p_pr.find("w:jc", NSMAP)
                if jc is None:
                    jc = ET.SubElement(p_pr, f"{{{W_NS}}}jc")
                if jc.get(f"{{{W_NS}}}val") != "center":
                    jc.set(f"{{{W_NS}}}val", "center")
                    changed = True
                for run_elem in paragraph.findall(".//w:r", NSMAP):
                    if not (
                        run_elem.find("w:fldChar", NSMAP) is not None
                        or run_elem.find("w:instrText", NSMAP) is not None
                        or get_run_text(run_elem).strip()
                    ):
                        continue
                    before = ET.tostring(run_elem, encoding="unicode")
                    _apply_page_number_run_style(run_elem)
                    after = ET.tostring(run_elem, encoding="unicode")
                    if before != after:
                        changed = True
                if ensure_em_dash_wrapper(paragraph):
                    changed = True
            if changed:
                rel_dir = os.path.dirname(rels_path)
                part_name = os.path.relpath(footer_path, temp_dir).replace(os.sep, "/")
                updated[part_name] = ET.tostring(footer_root, encoding="utf-8", xml_declaration=True)
        return updated

    def configure_lnu_section_page_footers(rels_root):
        section_page_numbering_enabled = (
            active_cfg.get("cover_page_number", True) is False
            or (
                active_cfg.get("pg01_format") == "hyphen_wrap"
                and active_cfg.get("page_number_font") == "宋体"
            )
        )
        if not section_page_numbering_enabled:
            return None
        body = document_root.find("w:body", NSMAP)
        if body is None:
            return None
        paragraphs = body.findall("w:p", NSMAP)
        body_sect_pr = body.find("w:sectPr", NSMAP)
        if body_sect_pr is None:
            return None

        def collect_inline_sections():
            sections = []
            for idx, paragraph in enumerate(paragraphs):
                sect_pr = paragraph.find("w:pPr/w:sectPr", NSMAP)
                if sect_pr is not None:
                    sections.append((idx, paragraph, sect_pr))
            return sections

        def remove_footer_references(sect_pr):
            for footer_reference in list(sect_pr.findall("w:footerReference", NSMAP)):
                sect_pr.remove(footer_reference)

        def remove_page_number_type(sect_pr):
            pg_num_type = sect_pr.find("w:pgNumType", NSMAP)
            if pg_num_type is not None:
                sect_pr.remove(pg_num_type)

        def ensure_cover_section_break(inline_sections):
            if active_cfg.get("cover_page_number", True) is not False:
                return False
            if len(inline_sections) != 1:
                return False

            frontmatter_end_idx, _frontmatter_end_para, frontmatter_end_sect_pr = inline_sections[0]
            first_frontmatter_idx = None
            for idx, paragraph in enumerate(paragraphs[: frontmatter_end_idx + 1]):
                if _is_frontmatter_title_text(get_paragraph_text(paragraph).strip()):
                    first_frontmatter_idx = idx
                    break
            if first_frontmatter_idx is None or first_frontmatter_idx <= 0:
                return False

            cover_break_para = paragraphs[first_frontmatter_idx - 1]
            cover_break_p_pr = ensure_ppr(cover_break_para)
            if cover_break_p_pr.find("w:sectPr", NSMAP) is not None:
                return False

            cover_sect_pr = copy.deepcopy(frontmatter_end_sect_pr)
            remove_footer_references(cover_sect_pr)
            remove_page_number_type(cover_sect_pr)
            cover_break_p_pr.append(cover_sect_pr)
            return True

        inline_sections = collect_inline_sections()
        if len(inline_sections) < 2 and ensure_cover_section_break(inline_sections):
            inline_sections = collect_inline_sections()
        if len(inline_sections) < 2:
            return None
        inline_sects = [sect_pr for _idx, _paragraph, sect_pr in inline_sections]

        content_types_root = ET.parse(content_types_path).getroot()
        updated = {}
        existing_rel_ids = {
            rel.get("Id")
            for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        }
        existing_targets = {
            rel.get("Target")
            for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
        }

        def next_rel_id():
            suffix = 1
            while f"rIdFooter{suffix}" in existing_rel_ids:
                suffix += 1
            rel_id = f"rIdFooter{suffix}"
            existing_rel_ids.add(rel_id)
            return rel_id

        def next_footer_target():
            suffix = 1
            while f"footer{suffix}.xml" in existing_targets:
                suffix += 1
            target = f"footer{suffix}.xml"
            existing_targets.add(target)
            return target

        def ensure_footer_content_type(target):
            part_name = f"/word/{target}"
            has_override = any(
                override.get("PartName") == part_name
                for override in content_types_root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
            )
            if has_override:
                return
            footer_override = ET.SubElement(content_types_root, f"{{{CONTENT_TYPES_NS}}}Override")
            footer_override.set("PartName", part_name)
            footer_override.set(
                "ContentType",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
            )

        def attach_footer(sect_pr, *, footer_cfg):
            remove_footer_references(sect_pr)
            rel_id = next_rel_id()
            target = next_footer_target()
            footer_rel = ET.SubElement(rels_root, f"{{{PACKAGE_REL_NS}}}Relationship")
            footer_rel.set("Id", rel_id)
            footer_rel.set("Type", f"{REL_NS}/footer")
            footer_rel.set("Target", target)

            footer_reference = ET.SubElement(sect_pr, f"{{{W_NS}}}footerReference")
            set_attr(footer_reference, "type", "default")
            footer_reference.set(f"{{{REL_NS}}}id", rel_id)
            ensure_footer_content_type(target)
            updated[f"word/{target}"] = build_footer_xml(footer_cfg)

        cover_sect_pr = inline_sects[0]
        frontmatter_sect_pr = inline_sects[-1]
        remove_footer_references(cover_sect_pr)

        front_pg_num_type = get_or_create(frontmatter_sect_pr, "w:pgNumType")
        set_attr(front_pg_num_type, "fmt", str(active_cfg.get("frontmatter_page_number_format") or "upperRoman"))
        set_attr(front_pg_num_type, "start", str(active_cfg.get("frontmatter_page_number_start") or 1))
        body_pg_num_type = get_or_create(body_sect_pr, "w:pgNumType")
        set_attr(body_pg_num_type, "fmt", str(active_cfg.get("body_page_number_format") or "decimal"))
        set_attr(body_pg_num_type, "start", str(active_cfg.get("body_page_number_start") or 1))

        front_cfg = dict(active_cfg)
        front_cfg["pg01_format"] = str(active_cfg.get("frontmatter_page_number_wrap") or "plain")
        body_cfg = dict(active_cfg)
        body_cfg["pg01_format"] = str(active_cfg.get("body_page_number_wrap") or active_cfg.get("pg01_format") or "plain")
        attach_footer(frontmatter_sect_pr, footer_cfg=front_cfg)
        attach_footer(body_sect_pr, footer_cfg=body_cfg)
        updated["word/_rels/document.xml.rels"] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)
        updated["[Content_Types].xml"] = ET.tostring(content_types_root, encoding="utf-8", xml_declaration=True)
        return updated

    rels_root = ET.parse(rels_path).getroot()
    section_footer_parts = configure_lnu_section_page_footers(rels_root)
    if section_footer_parts is not None:
        return section_footer_parts

    sect_pr = document_root.find("w:body/w:sectPr", NSMAP)
    if sect_pr is None:
        sect_pr_list = document_root.findall(".//w:sectPr", NSMAP)
        sect_pr = sect_pr_list[-1] if sect_pr_list else None
    if sect_pr is None:
        body = document_root.find("w:body", NSMAP)
        if body is None:
            raise ValueError("document.xml missing w:body")
        sect_pr = ET.SubElement(body, f"{{{W_NS}}}sectPr")

    has_footer_reference = sect_pr.find("w:footerReference", NSMAP) is not None
    has_footer_relationship = any(
        rel.get("Type") in FOOTER_REL_TYPES
        for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    )
    if has_footer_reference or has_footer_relationship:
        updated_footer_parts = center_existing_footer_page_numbers(rels_root)
        append_hidden_page_field_marker()
        return updated_footer_parts

    footer_rel_id = "rIdFooter1"
    existing_rel_ids = {rel.get("Id") for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")}
    if footer_rel_id in existing_rel_ids:
        suffix = 2
        while f"rIdFooter{suffix}" in existing_rel_ids:
            suffix += 1
        footer_rel_id = f"rIdFooter{suffix}"

    footer_rel = ET.SubElement(rels_root, f"{{{PACKAGE_REL_NS}}}Relationship")
    footer_rel.set("Id", footer_rel_id)
    footer_rel.set("Type", f"{REL_NS}/footer")
    footer_rel.set("Target", "footer1.xml")

    footer_reference = ET.SubElement(sect_pr, f"{{{W_NS}}}footerReference")
    set_attr(footer_reference, "type", "default")
    footer_reference.set(f"{{{REL_NS}}}id", footer_rel_id)

    content_types_root = ET.parse(content_types_path).getroot()
    footer_override_part = "/word/footer1.xml"
    has_footer_override = any(
        override.get("PartName") == footer_override_part
        for override in content_types_root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
    )
    if not has_footer_override:
        footer_override = ET.SubElement(content_types_root, f"{{{CONTENT_TYPES_NS}}}Override")
        footer_override.set("PartName", footer_override_part)
        footer_override.set(
            "ContentType",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
        )

    append_hidden_page_field_marker()

    return {
        "word/footer1.xml": build_footer_xml(active_cfg),
        "word/_rels/document.xml.rels": ET.tostring(rels_root, encoding="utf-8", xml_declaration=True),
        "[Content_Types].xml": ET.tostring(content_types_root, encoding="utf-8", xml_declaration=True),
    }
