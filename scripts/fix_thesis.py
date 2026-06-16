import argparse
import copy
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import replace

import audit_thesis
import fix_docx_io
import fix_output_parts
from docx import Document
from reorder_references_by_appearance import reorder_references_in_document
from _profile_utils import format_profile_resolution
from backmatter_title_utils import (
    is_abstract_cn_title,
    is_abstract_en_title,
    is_acknowledgement_title,
    is_frontmatter_title,
    is_toc_title,
    is_preface_heading_title,
    is_backmatter_pagebreak_title,
    matches_allowed_titles,
    resolve_lnu_double_spaced_title,
)
from frontmatter_utils import (
    contains_toc_field_text,
    find_contiguous_toc_block_range,
    is_keywords_text,
    is_toc_generated_style_id,
    paragraph_has_toc_field_instr,
)
from _thesis_utils import (
    HeadingCandidateFilter,
    NSMAP,
    W_NS,
    _looks_like_toc_entry,
    build_document_model,
    build_style_map,
    classify_paragraph,
    collect_figure_blocks,
    collect_table_blocks,
    detect_backmatter_bucket,
    get_paragraph_text,
    match_heading_by_text,
    paragraph_has_math,
)
from reference_section_utils import iter_reference_section_paragraphs
from sections._xml_helpers import (
    ensure_alignment_and_indent,
    ensure_bold,
    ensure_ppr,
    ensure_rfonts,
    ensure_rpr,
    ensure_size,
    ensure_spacing,
    get_run_text,
    get_paragraph_spacing_twips as _get_paragraph_spacing_twips,
    get_or_create,
    insert_tabs_before_spacing,
    is_superscript,
    remove_bold,
    set_attr,
    set_onoff_property as _set_onoff_property,
    set_paragraph_pagination_flags as _set_paragraph_pagination_flags,
    set_paragraph_spacing_attrs as _set_paragraph_spacing_attrs,
    set_table_row_cant_split as _set_table_row_cant_split,
)
from text_spacing_utils import (
    CJK_CHAR_RE,
    DIGIT_CHAR_RE,
    NUM_CJK_EXCEPTIONS,
    NUM_CJK_LEFT_EXCEPTIONS,
    needs_num_cjk_space as _needs_num_cjk_space,
    starts_with_num_cjk_exception as _starts_with_num_cjk_exception,
)
from thesis_fix.dependencies import configure as configure_thesis_fix_dependencies
from thesis_fix.runtime import (
    DEFAULT_CFG,
    DEFAULT_HEADING_STYLE_IDS,
    FixExecutionContext,
    FixRuntime,
    KNOWN_SCOPES,
    SAFE_NORMALIZE_OPERATION_LABELS,
    SAFE_NORMALIZE_SCOPE_IDS,
    ScopeFlags,
    build_fix_runtime,
    build_scope_flags,
    is_lnu_profile,
    is_scope_enabled,
    load_profile,
    normalize_scopes,
    resolve_fix_cfg,
    resolve_fix_heading_style_ids,
    resolve_fix_profile_id,
    should_fix_heading_in_scope,
)
from thesis_fix.reference_numbering import (
    _inject_tab_after_ref_number,
    _remove_tab_after_ref_number,
    ensure_reference_number_spacing,
    normalize_reference_number_leading_zeros,
    paragraph_has_reference_tab,
)
from thesis_fix.citations import (
    _citation_run_numbers,
    _format_citation_numbers,
    _merge_adjacent_superscript_citation_runs,
    _set_run_text,
    fix_superscript_fonts,
    move_superscript_citations_before_terminal_punct,
    split_inline_citations,
)

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MNSMAP = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "m": M_NS}

NAMESPACES = {
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "aink": "http://schemas.microsoft.com/office/drawing/2016/ink",
    "am3d": "http://schemas.microsoft.com/office/drawing/2017/model3d",
    "o": "urn:schemas-microsoft-com:office:office",
    "oel": "http://schemas.microsoft.com/office/2019/extlst",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v": "urn:schemas-microsoft-com:vml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w10": "urn:schemas-microsoft-com:office:word",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "w16": "http://schemas.microsoft.com/office/word/2018/wordml",
    "w16sdtdh": "http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash",
    "w16se": "http://schemas.microsoft.com/office/word/2015/wordml/symex",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
}

REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
FOOTER_REL_TYPES = (f"{REL_NS}/footer", f"{PACKAGE_REL_NS}/footer")
TOOL_ROOT = fix_docx_io.TOOL_ROOT
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)
ET.register_namespace("m", M_NS)

_TEXT_CLEANUP_SKIP_MODULES = {
    "body_caption",
    "appendix_caption",
    "body_caption_en",
    "appendix_caption_en",
    "body_caption_note",
    "appendix_caption_note",
}
_SOFT_LINE_BREAK_PRESERVE_MODULES = set(_TEXT_CLEANUP_SKIP_MODULES)
CAPTION_EN_MODULES = {"body_caption_en", "appendix_caption_en"}
CAPTION_NOTE_MODULES = {"body_caption_note", "appendix_caption_note"}
_HALF_WIDTH_PUNCT_MAPPING = {
    ",": "，",
    ";": "；",
    ":": "：",
    ".": "。",
}


def _configure_thesis_fix_dependencies():
    configure_thesis_fix_dependencies(
        {
            "CAPTION_EN_MODULES": CAPTION_EN_MODULES,
            "CAPTION_NOTE_MODULES": CAPTION_NOTE_MODULES,
            "CONTENT_TYPES_NS": CONTENT_TYPES_NS,
            "FOOTER_REL_TYPES": FOOTER_REL_TYPES,
            "NAMESPACES": NAMESPACES,
            "NSMAP": NSMAP,
            "PACKAGE_REL_NS": PACKAGE_REL_NS,
            "REL_NS": REL_NS,
            "W_NS": W_NS,
            "_caption_reference_candidates": _caption_reference_candidates,
            "_cleanup_docx_hidden_page_number_artifacts": _cleanup_docx_hidden_page_number_artifacts,
            "_is_any_keywords_text": _is_any_keywords_text,
            "_is_frontmatter_title_text": _is_frontmatter_title_text,
            "_is_generic_caption_lead_text": _is_generic_caption_lead_text,
            "_paragraph_outline_level": _paragraph_outline_level,
            "_toc_level_from_style_id": _toc_level_from_style_id,
            "_toc_title_for_runtime": _toc_title_for_runtime,
            "build_document_model": build_document_model,
            "build_settings_with_update_fields": build_settings_with_update_fields,
            "classify_paragraph": classify_paragraph,
            "collect_figure_blocks": collect_figure_blocks,
            "collect_table_blocks": collect_table_blocks,
            "detect_backmatter_bucket": detect_backmatter_bucket,
            "ensure_ppr": ensure_ppr,
            "ensure_rfonts": ensure_rfonts,
            "ensure_rpr": ensure_rpr,
            "ensure_size": ensure_size,
            "fix_lnu_abs01": fix_lnu_abs01,
            "fix_lnu_abs02": fix_lnu_abs02,
            "fix_lnu_abs03": fix_lnu_abs03,
            "fix_lnu_ack01": fix_lnu_ack01,
            "fix_lnu_conc01": fix_lnu_conc01,
            "fix_lnu_ref01": fix_lnu_ref01,
            "fix_lnu_ref02": fix_lnu_ref02,
            "fix_lnu_ref04": fix_lnu_ref04,
            "fix_lnu_s03": fix_lnu_s03,
            "fix_lnu_tb03": fix_lnu_tb03,
            "fix_lnu_title01": fix_lnu_title01,
            "get_or_create": get_or_create,
            "get_paragraph_text": get_paragraph_text,
            "get_run_text": get_run_text,
            "insert_missing_caption_reference_leads": insert_missing_caption_reference_leads,
            "is_lnu_profile": is_lnu_profile,
            "is_scope_enabled": is_scope_enabled,
            "match_heading_by_text": match_heading_by_text,
            "normalize_lnu_figure_block_layout": normalize_lnu_figure_block_layout,
            "normalize_lnu_table_block_layout": normalize_lnu_table_block_layout,
            "normalize_toc_entry_paragraphs": normalize_toc_entry_paragraphs,
            "normalize_toc_title_paragraph": normalize_toc_title_paragraph,
            "promote_post_caption_reference_blocks": promote_post_caption_reference_blocks,
            "protect_object_blocks_from_pagination": protect_object_blocks_from_pagination,
            "rebalance_figure_blocks_for_layout": rebalance_figure_blocks_for_layout,
            "rebalance_table_blocks_for_layout": rebalance_table_blocks_for_layout,
            "remove_duplicate_body_toc_title": remove_duplicate_body_toc_title,
            "remove_existing_toc_artifacts": remove_existing_toc_artifacts,
            "remove_synthetic_caption_reference_leads": remove_synthetic_caption_reference_leads,
            "renumber_lnu_captions": renumber_lnu_captions,
            "reorder_references_in_document": reorder_references_in_document,
            "repair_misplaced_abstract_keywords": repair_misplaced_abstract_keywords,
            "resolve_fix_cfg": resolve_fix_cfg,
            "set_attr": set_attr,
        }
    )
_HALF_WIDTH_PUNCT_CJK_RE = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_HALF_WIDTH_PUNCT_PATTERN = re.compile(
    rf"(?<={_HALF_WIDTH_PUNCT_CJK_RE})[,;:]|[,;:](?={_HALF_WIDTH_PUNCT_CJK_RE})|"
    rf"(?<={_HALF_WIDTH_PUNCT_CJK_RE})\.(?!\d)|\.(?={_HALF_WIDTH_PUNCT_CJK_RE})"
)
HEADING_SPACING_DEFAULTS = {
    "h1": {"before": 120, "after": 120},
    "h2": {"before": 120, "after": 120},
    "h3": {"before": 120, "after": 120},
    "h4": {"before": 120, "after": 120},
}
EMU_PER_CM = 360000
COVER_IMAGE_MAX_CX = int(5.5 * EMU_PER_CM)
COVER_IMAGE_MAX_CY = int(5.5 * EMU_PER_CM)
def resolve_heading_style_ids(style_map, runtime=None):
    base = resolve_fix_heading_style_ids(runtime=runtime)
    resolved = dict(base)
    for style_id, props in (style_map or {}).items():
        if not style_id:
            continue
        outline_lvl = props.get("outlineLvl")
        if outline_lvl not in (0, 1, 2, 3):
            continue
        heading_level = f"h{outline_lvl + 1}"
        current_style_id = resolved.get(heading_level)
        if current_style_id == f"Heading{outline_lvl + 1}":
            resolved[heading_level] = style_id
    return resolved


def _get_paragraph_style_id(p_elem):
    style_elem = p_elem.find("w:pPr/w:pStyle", NSMAP)
    if style_elem is None:
        return None
    return style_elem.get(f"{{{W_NS}}}val")


def _clear_heading_style_for_body_paragraph(p_elem, style_map=None):
    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is None:
        return
    p_style = p_pr.find("w:pStyle", NSMAP)
    if p_style is None:
        return
    style_id = p_style.get(f"{{{W_NS}}}val")
    if style_id is None:
        return
    outline_lvl = (style_map or {}).get(style_id, {}).get("outlineLvl")
    if outline_lvl in {0, 1, 2, 3}:
        p_pr.remove(p_style)


def _rebuild_fix_context(document_root, style_map, runtime, temp_dir=None):
    document_model = build_document_model(document_root, style_map)
    return FixExecutionContext(
        document_root=document_root,
        style_map=style_map,
        runtime=runtime,
        cfg=runtime.cfg,
        temp_dir=temp_dir,
        document_model=document_model,
        sections=document_model.sections,
        paragraph_sections=document_model.paragraph_sections,
        protected_ids=document_model.protected_ids,
        editable_text_ids=document_model.editable_text_ids(),
        scope_flags=build_scope_flags(runtime.requested_scopes),
    )


def _node_targets_active_scope(node, scope_flags: ScopeFlags) -> bool:
    section_name = node.section
    kind = node.kind
    module = node.module

    if node.container_section == "cover":
        return scope_flags.page
    if node.container_section == "toc":
        return scope_flags.toc
    if section_name in {"abstract_cn", "abstract_en"}:
        return scope_flags.abstract
    if module == "references_entry":
        return scope_flags.references
    if module == "acknowledgement_paragraph":
        return scope_flags.acknowledgement or scope_flags.body
    if module == "appendix_paragraph":
        return scope_flags.appendix
    if module in {"body_caption", "appendix_caption"} | CAPTION_EN_MODULES | CAPTION_NOTE_MODULES:
        return scope_flags.figures
    if module == "body_paragraph":
        return scope_flags.body
    if kind in {"h1", "h2", "h3", "h4"}:
        enabled_heading_scopes = {
            scope_id
            for scope_id, enabled in (
                ("headings", scope_flags.headings),
                ("appendix", scope_flags.appendix),
                ("references", scope_flags.references),
                ("acknowledgement", scope_flags.acknowledgement),
            )
            if enabled
        }
        if not enabled_heading_scopes:
            return False
        return should_fix_heading_in_scope(enabled_heading_scopes, section_name)
    return False


def _iter_heading_prepass_candidates(document_model, style_map, runtime):
    for node in document_model.paragraphs:
        if HeadingCandidateFilter.should_skip_for_renumber(node) or node.kind not in {"h1", "h2", "h3", "h4"}:
            continue
        if node.container_section in {"cover", "toc"}:
            continue
        if node.section not in {"body", "appendix", "references", "acknowledgement"}:
            continue
        if not should_fix_heading_in_scope(runtime.requested_scopes, node.section):
            continue
        target_style_id = runtime.heading_style_ids.get(node.kind)
        if not target_style_id:
            continue
        current_style_id = _get_paragraph_style_id(node.elem)
        if current_style_id == target_style_id:
            continue
        current_outline = (style_map or {}).get(current_style_id, {}).get("outlineLvl")
        if current_outline == int(node.kind[1]) - 1:
            continue
        yield node


def normalize_heading_styles(document_model, style_map, runtime):
    normalized = 0
    for node in _iter_heading_prepass_candidates(document_model, style_map, runtime):
        p_pr = ensure_ppr(node.elem)
        p_style, _created = ensure_pstyle_first(p_pr)
        set_attr(p_style, "val", runtime.heading_style_ids[node.kind])
        normalized += 1
    return normalized


def _summarize_fix_targets(document_model, scope_flags: ScopeFlags):
    module_counts = Counter()
    for node in document_model.paragraphs:
        if _node_targets_active_scope(node, scope_flags):
            module_counts[node.module] += 1
    return dict(sorted(module_counts.items()))


def _collect_text_cleanup_allowed_ids(ctx: FixExecutionContext, *, include_abstract_cn_punct: bool, include_toc_punct: bool = False) -> set[int]:
    allowed_ids: set[int] = set()
    for node in ctx.document_model.paragraphs:
        if node.kind == "reference" or node.module in _TEXT_CLEANUP_SKIP_MODULES:
            continue
        if include_toc_punct and node.section == "toc" and ctx.scope_flags.toc:
            allowed_ids.add(id(node.elem))
            continue
        if node.section == "body" and ctx.scope_flags.body:
            allowed_ids.add(id(node.elem))
            continue
        if node.section == "appendix" and ctx.scope_flags.appendix:
            allowed_ids.add(id(node.elem))
            continue
        if include_abstract_cn_punct and node.module == "abstract_cn_body" and ctx.scope_flags.abstract:
            allowed_ids.add(id(node.elem))
    return allowed_ids


def _apply_lnu_compact_text_passes(ctx: FixExecutionContext):
    if not is_lnu_profile(ctx.runtime):
        return
    for node in ctx.document_model.paragraphs:
        if node.protected or node.in_table:
            continue
        if is_generated_toc_paragraph(node.elem):
            continue
        if ctx.scope_flags.abstract and node.module in {"abstract_cn_body", "abstract_cn_keywords"}:
            fix_lnu_compact_text(node.elem, restore_unit_gap=True)
            continue
        if ctx.scope_flags.toc and node.module in {"toc_entry", "toc_body"}:
            fix_lnu_compact_text(node.elem, restore_heading_gap=True, restore_unit_gap=True)
            continue
        if ctx.scope_flags.body and node.module == "body_paragraph":
            fix_lnu_compact_text(node.elem, restore_unit_gap=True)
            continue
        if (ctx.scope_flags.body or ctx.scope_flags.headings) and node.module == "body_heading":
            fix_lnu_compact_text(node.elem, restore_heading_gap=True)


def describe_fix_docx(
    input_path,
    output_path=None,
    profile_path=None,
    toc=False,
    scopes=None,
    renumber_headings=False,
    layout_rebalance=False,
    runtime=None,
):
    input_path = audit_thesis.validate_docx_path(input_path)
    runtime = runtime or build_fix_runtime(
        profile_path=profile_path,
        toc=toc,
        scopes=scopes,
        renumber_headings=renumber_headings,
        layout_rebalance=layout_rebalance,
        dry_run=True,
    )
    document_xml, styles_xml, _footnotes_xml = audit_thesis.load_docx_xml(input_path)
    document_root = ET.fromstring(document_xml)
    styles_root = ET.fromstring(styles_xml)
    style_map = build_style_map(styles_root)
    runtime = replace(runtime, heading_style_ids=resolve_heading_style_ids(style_map, runtime=runtime))
    ctx = _rebuild_fix_context(document_root, style_map, runtime)
    heading_style_candidates = sum(1 for _ in _iter_heading_prepass_candidates(ctx.document_model, style_map, runtime))
    table_count = len(document_root.findall(".//w:tbl", NSMAP))
    return {
        "file_path": input_path,
        "output_path": output_path,
        "profile_id": runtime.profile_id,
        "requested_profile": runtime.requested_profile,
        "fallback_used": runtime.fallback_used,
        "profile_display": format_profile_resolution(runtime.profile_id, runtime.requested_profile, runtime.fallback_used),
        "selected_scopes": sorted(runtime.requested_scopes) if runtime.requested_scopes else None,
        "toc_enabled": bool(runtime.cfg.get("toc_auto")),
        "renumber_headings": runtime.renumber_headings,
        "layout_rebalance": runtime.layout_rebalance,
        "paragraph_count": len(ctx.document_model.paragraphs),
        "table_count": table_count,
        "heading_style_candidates": heading_style_candidates,
        "targeted_modules": _summarize_fix_targets(ctx.document_model, ctx.scope_flags),
        "notes": [
            "本次为 dry-run，未写入任何文件。",
            "标题预处理会先为高置信度标题补齐 Heading 样式，再进入格式修复。",
            "若启用目录重建，脚本会预填可见自动目录结果；后续改动正文分页后需复核目录页码。",
        ],
    }


def render_fix_preview(preview: dict) -> str:
    lines = [
        f"文件: {os.path.basename(preview['file_path'])}",
        f"Profile: {preview.get('profile_display') or preview['profile_id']}",
        f"dry-run: 是",
    ]
    if preview.get("output_path"):
        lines.append(f"输出文件: {preview['output_path']}")
    if preview.get("selected_scopes"):
        lines.append(f"修复范围: {', '.join(preview['selected_scopes'])}")
    else:
        lines.append("修复范围: 全部 scope")
    if preview["toc_enabled"]:
        lines.append("目录处理: 自动域目录重建")
    elif preview.get("selected_scopes") and "toc" in preview["selected_scopes"]:
        lines.append("目录处理: 可见目录补全/规范")
    else:
        lines.append("目录处理: 否")
    lines.append(f"标题重编号: {'是' if preview['renumber_headings'] else '否'}")
    lines.append(f"图表跨页重排: {'是' if preview.get('layout_rebalance') else '否'}")
    lines.append(f"段落总数: {preview['paragraph_count']}")
    lines.append(f"表格总数: {preview['table_count']}")
    lines.append(f"待补 Heading 样式段落: {preview['heading_style_candidates']}")
    lines.append("")
    lines.append("预计会触达的模块：")
    if not preview["targeted_modules"]:
        lines.append("- 当前所选 scope 未命中可修复模块。")
    else:
        for module_name, count in preview["targeted_modules"].items():
            lines.append(f"- {module_name}: {count}")
    lines.append("")
    lines.append("说明：")
    for note in preview["notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


def rewrite_paragraph_text_preserve_runs(p_elem, new_text):
    text_elems = p_elem.findall(".//w:t", NSMAP)
    if not text_elems:
        return False
    text_elems[0].text = new_text
    text_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
    for text_elem in text_elems[1:]:
        text_elem.text = ""
    return True


def rebuild_plain_runs(p_elem, run_specs):
    for child in list(p_elem):
        if child.tag == f"{{{W_NS}}}r":
            p_elem.remove(child)
    insert_at = len(list(p_elem))
    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is not None:
        insert_at = 1
    for offset, spec in enumerate(run_specs):
        run_elem = ET.Element(f"{{{W_NS}}}r")
        r_pr = ET.SubElement(run_elem, f"{{{W_NS}}}rPr")
        r_fonts = ET.SubElement(r_pr, f"{{{W_NS}}}rFonts")
        set_attr(r_fonts, "eastAsia", spec.get("east_asia", "Times New Roman"))
        set_attr(r_fonts, "ascii", spec.get("ascii_font", "Times New Roman"))
        set_attr(r_fonts, "hAnsi", spec.get("ascii_font", "Times New Roman"))
        sz = ET.SubElement(r_pr, f"{{{W_NS}}}sz")
        set_attr(sz, "val", str(spec.get("size", 24)))
        sz_cs = ET.SubElement(r_pr, f"{{{W_NS}}}szCs")
        set_attr(sz_cs, "val", str(spec.get("size", 24)))
        if spec.get("bold"):
            b_elem = ET.SubElement(r_pr, f"{{{W_NS}}}b")
            set_attr(b_elem, "val", "1")
        if "italic" in spec:
            i_elem = ET.SubElement(r_pr, f"{{{W_NS}}}i")
            set_attr(i_elem, "val", "1" if spec.get("italic") else "0")
        text_elem = ET.SubElement(run_elem, f"{{{W_NS}}}t")
        text_elem.text = spec.get("text", "")
        if (text_elem.text or "").startswith(" ") or (text_elem.text or "").endswith(" "):
            text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
        p_elem.insert(insert_at + offset, run_elem)


def remove_bold(run_elem):
    rpr = ensure_rpr(run_elem)
    for tag in ("w:b", "w:bCs"):
        el = rpr.find(tag, NSMAP)
        if el is not None:
            rpr.remove(el)


def set_run_italic(run_elem, italic):
    r_pr = ensure_rpr(run_elem)
    for tag in ("w:i", "w:iCs"):
        elem = r_pr.find(tag, NSMAP)
        if italic is None:
            continue
        if elem is None:
            elem = ET.SubElement(r_pr, f"{{{W_NS}}}{tag.split(':', 1)[1]}")
        set_attr(elem, "val", "1" if italic else "0")


def _remove_run_props(run_elem, names):
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is None:
        return
    for name in names:
        for elem in list(r_pr.findall(f"w:{name}", NSMAP)):
            r_pr.remove(elem)


def set_run_font(run_elem, east_asia, ascii_font=None, size=None, bold=None, italic=None):
    if ascii_font is None:
        ascii_font = east_asia
    r_fonts = ensure_rfonts(run_elem)
    set_attr(r_fonts, "eastAsia", east_asia)
    set_attr(r_fonts, "ascii", ascii_font)
    set_attr(r_fonts, "hAnsi", ascii_font)
    if size is not None:
        ensure_size(run_elem, str(size))
    if bold is True:
        ensure_bold(run_elem)
    elif bold is False:
        remove_bold(run_elem)
    if italic is not None:
        set_run_italic(run_elem, italic)


def fix_run_font(p_elem, east_asia, size, ascii_font=None, bold=None, italic=None):
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if get_run_text(run_elem) == "":
            continue
        set_run_font(run_elem, east_asia, ascii_font=ascii_font, size=size, bold=bold, italic=italic)


def resolve_body_format(cfg=None, runtime=None):
    active_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    return {
        "east_asia": active_cfg.get("body_font", "宋体") or "宋体",
        "ascii_font": active_cfg.get("body_ascii_font", "Times New Roman") or "Times New Roman",
        "size": active_cfg.get("body_size", 24) or 24,
        "line": active_cfg.get("body_line", 360) or 360,
        "indent": active_cfg.get("body_indent", 480) or 0,
        "alignment": active_cfg.get("body_alignment", "both") or "both",
    }


def resolve_abstract_title_format(cfg, section_name):
    if section_name == "abstract_en":
        font = cfg.get("abstract_en_title_font", "Times New Roman") or "Times New Roman"
        size = cfg.get("abstract_en_title_size", 32) or 32
        bold = True
    else:
        font = cfg.get("abstract_title_font", "黑体") or "黑体"
        size = cfg.get("abstract_title_size", 32) or 32
        bold = False
    return {"font": font, "ascii_font": font, "size": size, "bold": bold}


def resolve_abstract_body_format(cfg, section_name):
    body_spec = resolve_body_format(cfg)
    if section_name == "abstract_en":
        return {
            "east_asia": cfg.get("abstract_en_body_font", "Times New Roman") or "Times New Roman",
            "ascii_font": cfg.get("abstract_en_body_ascii_font", "Times New Roman") or "Times New Roman",
            "size": cfg.get("abstract_en_body_size", body_spec["size"]) or body_spec["size"],
            "line": cfg.get("abstract_en_body_line", 240) or 240,
            "indent": cfg.get("abstract_en_body_indent", body_spec["indent"]) or 0,
            "alignment": "both",
        }
    return {
        "east_asia": cfg.get("abstract_body_font", body_spec["east_asia"]) or body_spec["east_asia"],
        "ascii_font": cfg.get("abstract_body_ascii_font", body_spec["ascii_font"]) or body_spec["ascii_font"],
        "size": cfg.get("abstract_body_size", body_spec["size"]) or body_spec["size"],
        "line": cfg.get("abstract_body_line", body_spec["line"]) or body_spec["line"],
        "indent": cfg.get("abstract_body_indent", body_spec["indent"]) or 0,
        "alignment": "both",
    }


_SCIENTIFIC_NAME_RE = re.compile(r"\b(?:[A-Z][a-z]{2,}|[A-Z]\.)\s+[a-z][a-z-]{2,}\b")


def _rebuild_abstract_cn_body_runs(p_elem, body_spec):
    text = get_paragraph_text(p_elem)
    if not text.strip():
        fix_run_font(
            p_elem,
            body_spec["east_asia"],
            body_spec["size"],
            ascii_font=body_spec["ascii_font"],
            bold=False,
            italic=False,
        )
        return

    run_specs = []
    cursor = 0
    for match in _SCIENTIFIC_NAME_RE.finditer(text):
        start, end = match.span()
        if start > cursor:
            run_specs.append(
                {
                    "text": text[cursor:start],
                    "east_asia": body_spec["east_asia"],
                    "ascii_font": body_spec["ascii_font"],
                    "size": body_spec["size"],
                    "bold": False,
                    "italic": False,
                }
            )
        run_specs.append(
            {
                "text": match.group(0),
                "east_asia": body_spec["east_asia"],
                "ascii_font": body_spec["ascii_font"],
                "size": body_spec["size"],
                "bold": False,
                "italic": True,
            }
        )
        cursor = end
    if cursor < len(text):
        run_specs.append(
            {
                "text": text[cursor:],
                "east_asia": body_spec["east_asia"],
                "ascii_font": body_spec["ascii_font"],
                "size": body_spec["size"],
                "bold": False,
                "italic": False,
            }
        )

    if run_specs:
        rebuild_plain_runs(p_elem, run_specs)
    else:
        fix_run_font(
            p_elem,
            body_spec["east_asia"],
            body_spec["size"],
            ascii_font=body_spec["ascii_font"],
            bold=False,
            italic=False,
        )


def ensure_pstyle_first(p_pr):
    p_style = p_pr.find("w:pStyle", NSMAP)
    created = False
    if p_style is None:
        p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        p_pr.remove(p_style)
        p_pr.insert(0, p_style)
        created = True
    return p_style, created


def is_mostly_cjk(text):
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return False
    cjk_count = sum(1 for char in compact if "\u4e00" <= char <= "\u9fff")
    return cjk_count / len(compact) > 0.3


def set_terminal_punctuation(text, expected):
    if text is None:
        return text
    stripped = text.rstrip()
    if not stripped:
        return text
    trailing = text[len(stripped):]
    if stripped.endswith(expected):
        return text
    if stripped[-1] in "。.;；,，":
        stripped = stripped[:-1] + expected
    else:
        stripped = stripped + expected
    return stripped + trailing


LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
TEXT_COMPACT_SPACE_RE = re.compile(
    r"(?<=[\u4e00-\u9fff])[\u0020\u00a0\u3000]+(?=[A-Za-z0-9])|"
    r"(?<=[A-Za-z0-9])[\u0020\u00a0\u3000]+(?=[\u4e00-\u9fff])"
)
TEXT_PUNCT_SPACE_RE = re.compile(r"[\u0020\u00a0\u3000]+(?=[，。；：！？、])|(?<=[，。；：！？、])[\u0020\u00a0\u3000]+")
TEXT_SPACE_CHARS = " \u00a0\u3000"
XML_SPACE_NS = "http://www.w3.org/XML/1998/namespace"
EQ_EXPLANATION_PREFIXES = ("其中", "式中")
EQ_EXPLANATION_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9/])([A-Za-zΑ-Ωα-ωφΦ](?:\d+|[tr]))(?![A-Za-z0-9])")


def _is_plain_text_run(run_elem):
    for child in list(run_elem):
        if child.tag not in {f"{{{W_NS}}}rPr", f"{{{W_NS}}}t"}:
            return False
    return True


def _make_text_run_like(template_run, text):
    new_run = ET.Element(f"{{{W_NS}}}r")
    template_rpr = template_run.find("w:rPr", NSMAP)
    if template_rpr is not None:
        new_run.append(copy.deepcopy(template_rpr))
    text_elem = ET.SubElement(new_run, f"{{{W_NS}}}t")
    text_elem.text = text
    if text.startswith(" ") or text.endswith(" "):
        text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
    return new_run


def _normalize_equation_explanation_rpr(r_pr, *, keep_east_asia=True):
    normalized = copy.deepcopy(r_pr) if r_pr is not None else ET.Element(f"{{{W_NS}}}rPr")
    r_fonts = normalized.find("w:rFonts", NSMAP)
    if r_fonts is None:
        r_fonts = ET.SubElement(normalized, f"{{{W_NS}}}rFonts")
    set_attr(r_fonts, "ascii", "Times New Roman")
    set_attr(r_fonts, "hAnsi", "Times New Roman")
    set_attr(r_fonts, "cs", "Times New Roman")
    if keep_east_asia and not r_fonts.get(f"{{{W_NS}}}eastAsia"):
        set_attr(r_fonts, "eastAsia", "宋体")
    for tag in ("w:b", "w:i"):
        elem = normalized.find(tag, NSMAP)
        if elem is None:
            elem = ET.SubElement(normalized, f"{{{W_NS}}}{tag.split(':', 1)[1]}")
        set_attr(elem, "val", "0")
    return normalized


def _make_equation_explanation_run(text, base_rpr=None, *, subscript=False, superscript=False):
    new_run = ET.Element(f"{{{W_NS}}}r")
    new_rpr = _normalize_equation_explanation_rpr(base_rpr)
    for vert in list(new_rpr.findall("w:vertAlign", NSMAP)):
        new_rpr.remove(vert)
    if subscript or superscript:
        vert = ET.SubElement(new_rpr, f"{{{W_NS}}}vertAlign")
        set_attr(vert, "val", "subscript" if subscript else "superscript")
    new_run.append(new_rpr)
    text_elem = ET.SubElement(new_run, f"{{{W_NS}}}t")
    text_elem.text = text
    if text.startswith(" ") or text.endswith(" "):
        text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
    return new_run


def _split_equation_explanation_text(text):
    parts = []
    last = 0
    for match in EQ_EXPLANATION_TOKEN_RE.finditer(text or ""):
        start, end = match.span()
        if start > last:
            parts.append((text[last:start], None))
        token = match.group(1)
        parts.append((token[0], None))
        parts.append((token[1:], "sub"))
        last = end
    if last < len(text or ""):
        parts.append((text[last:], None))
    return [(piece_text, piece_kind) for piece_text, piece_kind in parts if piece_text]


def _collect_equation_explanation_math_text(elem):
    parts = []
    for child in elem.iter():
        if child.tag == f"{{{M_NS}}}t" and child.text:
            parts.append(child.text)
    return "".join(parts)


def _flatten_equation_explanation_math(elem):
    tag = elem.tag.split("}", 1)[-1]
    if tag in {"oMath", "oMathPara"}:
        pieces = []
        for child in list(elem):
            pieces.extend(_flatten_equation_explanation_math(child))
        return pieces
    if tag == "sSub":
        base = _collect_equation_explanation_math_text(elem.find("m:e", MNSMAP))
        sub = _collect_equation_explanation_math_text(elem.find("m:sub", MNSMAP))
        pieces = []
        if base:
            pieces.append((base, None))
        if sub:
            pieces.append((sub, "sub"))
        return pieces
    if tag == "sSup":
        base = _collect_equation_explanation_math_text(elem.find("m:e", MNSMAP))
        sup = _collect_equation_explanation_math_text(elem.find("m:sup", MNSMAP))
        pieces = []
        if base:
            pieces.append((base, None))
        if sup:
            pieces.append((sup, "sup"))
        return pieces
    if tag == "r":
        return _split_equation_explanation_text(_collect_equation_explanation_math_text(elem))
    pieces = []
    for child in list(elem):
        pieces.extend(_flatten_equation_explanation_math(child))
    return pieces


def normalize_equation_explanation_symbols(p_elem):
    paragraph_text = get_paragraph_text(p_elem).strip()
    if not paragraph_text.startswith(EQ_EXPLANATION_PREFIXES):
        return False
    has_math = p_elem.find("m:oMath", MNSMAP) is not None or p_elem.find("m:oMathPara", MNSMAP) is not None
    has_inline_symbols = EQ_EXPLANATION_TOKEN_RE.search(paragraph_text) is not None
    if not has_math and not has_inline_symbols:
        return False

    original_children = list(p_elem)
    base_rpr = None
    for child in original_children:
        if child.tag == f"{{{W_NS}}}r":
            candidate_rpr = child.find("w:rPr", NSMAP)
            if candidate_rpr is not None:
                base_rpr = candidate_rpr
                break

    rebuilt_children = []
    changed = False
    for child in original_children:
        if child.tag == f"{{{W_NS}}}pPr":
            rebuilt_children.append(child)
            continue
        if child.tag in {f"{{{M_NS}}}oMath", f"{{{M_NS}}}oMathPara"}:
            for piece_text, piece_kind in _flatten_equation_explanation_math(child):
                rebuilt_children.append(
                    _make_equation_explanation_run(
                        piece_text,
                        base_rpr=base_rpr,
                        subscript=(piece_kind == "sub"),
                        superscript=(piece_kind == "sup"),
                    )
                )
            changed = True
            continue
        if child.tag == f"{{{W_NS}}}r":
            run_text = get_run_text(child)
            run_rpr = child.find("w:rPr", NSMAP)
            if run_rpr is None:
                run_rpr = base_rpr
            if EQ_EXPLANATION_TOKEN_RE.search(run_text or ""):
                for piece_text, piece_kind in _split_equation_explanation_text(run_text):
                    rebuilt_children.append(
                        _make_equation_explanation_run(
                            piece_text,
                            base_rpr=run_rpr,
                            subscript=(piece_kind == "sub"),
                        )
                    )
                changed = True
                continue
            cloned = copy.deepcopy(child)
            cloned_rpr = cloned.find("w:rPr", NSMAP)
            if cloned_rpr is not None:
                cloned.remove(cloned_rpr)
                cloned.insert(0, _normalize_equation_explanation_rpr(cloned_rpr))
                changed = True
            rebuilt_children.append(cloned)
            continue
        rebuilt_children.append(copy.deepcopy(child))

    if not changed:
        return False

    for child in list(p_elem):
        p_elem.remove(child)
    for child in rebuilt_children:
        p_elem.append(child)
    return True


def _replace_run_with_tokens(parent_elem, run_elem, tokens):
    insert_at = list(parent_elem).index(run_elem)
    parent_elem.remove(run_elem)
    for offset, token in enumerate(tokens):
        parent_elem.insert(insert_at + offset, _make_text_run_like(run_elem, token))


def _compact_lnu_text_value(text):
    if not text:
        return text
    text = TEXT_COMPACT_SPACE_RE.sub("", text)
    text = TEXT_PUNCT_SPACE_RE.sub("", text)
    return _HALF_WIDTH_PUNCT_PATTERN.sub(lambda match: _HALF_WIDTH_PUNCT_MAPPING[match.group(0)], text)


def _plain_text_nodes_in_paragraph(p_elem):
    nodes = []
    for run_elem in p_elem.findall("w:r", NSMAP):
        if is_superscript(run_elem) or not _is_plain_text_run(run_elem):
            continue
        for text_elem in run_elem.findall("w:t", NSMAP):
            nodes.append(text_elem)
    return nodes


def _last_non_space_char(text):
    stripped = (text or "").rstrip(TEXT_SPACE_CHARS)
    return stripped[-1] if stripped else ""


def _first_non_space_char(text):
    stripped = (text or "").lstrip(TEXT_SPACE_CHARS)
    return stripped[0] if stripped else ""


def _is_lnu_compact_boundary(left_char, right_char):
    if not left_char or not right_char:
        return False
    return bool(
        (CJK_CHAR_RE.match(left_char) and (LATIN_CHAR_RE.match(right_char) or DIGIT_CHAR_RE.match(right_char)))
        or ((LATIN_CHAR_RE.match(left_char) or DIGIT_CHAR_RE.match(left_char)) and CJK_CHAR_RE.match(right_char))
        or right_char in "，。；：！？、"
        or left_char in "，。；：！？、"
    )


def _compact_lnu_text_between_runs(p_elem):
    changed = False
    while True:
        text_nodes = _plain_text_nodes_in_paragraph(p_elem)
        updated = False
        for index in range(1, len(text_nodes)):
            left_elem = text_nodes[index - 1]
            right_elem = text_nodes[index]
            left_text = left_elem.text or ""
            right_text = right_elem.text or ""
            if not left_text or not right_text:
                continue
            if not (left_text[-1].isspace() or right_text[0].isspace()):
                continue
            left_char = _last_non_space_char(left_text)
            right_char = _first_non_space_char(right_text)
            if not left_char:
                prev_index = index - 2
                while prev_index >= 0 and not left_char:
                    left_char = _last_non_space_char(text_nodes[prev_index].text or "")
                    prev_index -= 1
            if not right_char:
                next_index = index + 1
                while next_index < len(text_nodes) and not right_char:
                    right_char = _first_non_space_char(text_nodes[next_index].text or "")
                    next_index += 1
            if not _is_lnu_compact_boundary(left_char, right_char):
                continue
            new_left = left_text.rstrip(TEXT_SPACE_CHARS)
            new_right = right_text.lstrip(TEXT_SPACE_CHARS)
            if new_left != left_text or new_right != right_text:
                left_elem.text = new_left
                right_elem.text = new_right
                changed = True
                updated = True
                break
        if not updated:
            return changed


def fix_lnu_compact_text(p_elem, *, restore_heading_gap=False, restore_unit_gap=False):
    """压紧辽大摘要/目录/正文混排空格，并按场景恢复允许的标题/单位空格。"""
    changed = False
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        original = text_elem.text
        updated = _compact_lnu_text_value(original)
        if updated != original:
            text_elem.text = updated
            changed = True
    changed = _compact_lnu_text_between_runs(p_elem) or changed
    if restore_heading_gap:
        before = get_paragraph_text(p_elem)
        fix_heading_num_space(p_elem)
        changed = changed or get_paragraph_text(p_elem) != before
    if restore_unit_gap:
        changed = fix_lnu_unit_spacing(p_elem) or changed
    return changed


def _needs_cjk_latin_space(text, index, left_char, right_char):
    if audit_thesis.is_relaxed_strain_suffix_t_excerpt((text or "")[max(0, index - 16): index + 16]):
        return False
    return bool(
        (CJK_CHAR_RE.match(left_char) and LATIN_CHAR_RE.match(right_char))
        or (LATIN_CHAR_RE.match(left_char) and CJK_CHAR_RE.match(right_char))
    )


def _tokenize_with_boundary_spaces(text, boundary_checker):
    if not text:
        return [text]
    tokens = []
    chunk = [text[0]]
    for index in range(len(text) - 1):
        left_char = text[index]
        right_char = text[index + 1]
        if boundary_checker(text, index, left_char, right_char):
            tokens.append("".join(chunk))
            tokens.append(" ")
            chunk = [right_char]
        else:
            chunk.append(right_char)
    tokens.append("".join(chunk))
    return [token for token in tokens if token != ""]


def _fix_spacing_inside_runs(p_elem, boundary_checker):
    changed = False
    for run_elem in list(p_elem.findall("w:r", NSMAP)):
        if is_superscript(run_elem) or not _is_plain_text_run(run_elem):
            continue
        run_text = get_run_text(run_elem)
        if not run_text or " " in run_text:
            if not run_text:
                continue
        tokens = _tokenize_with_boundary_spaces(run_text, boundary_checker)
        if len(tokens) <= 1:
            continue
        _replace_run_with_tokens(p_elem, run_elem, tokens)
        changed = True
    return changed


def _fix_spacing_between_runs(p_elem, boundary_checker):
    changed = False
    while True:
        direct_runs = [child for child in list(p_elem) if child.tag == f"{{{W_NS}}}r"]
        non_empty_runs = [(run_elem, get_run_text(run_elem)) for run_elem in direct_runs if get_run_text(run_elem)]
        inserted = False
        for index in range(len(non_empty_runs) - 1):
            left_run, left_text = non_empty_runs[index]
            right_run, right_text = non_empty_runs[index + 1]
            if is_superscript(left_run) or is_superscript(right_run):
                continue
            if left_text[-1].isspace() or right_text[0].isspace():
                continue
            if not boundary_checker(left_text + right_text, len(left_text) - 1, left_text[-1], right_text[0]):
                continue
            parent_children = list(p_elem)
            insert_at = parent_children.index(right_run)
            p_elem.insert(insert_at, _make_text_run_like(left_run, " "))
            changed = True
            inserted = True
            break
        if not inserted:
            return changed


def _make_cjk_latin_boundary_checker(cfg=None, runtime=None):
    active_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    if active_cfg.get("mixed_spacing_policy") == "compact":
        return lambda _text, _index, _left_char, _right_char: False
    relax_strain_suffix_t_spacing = bool(active_cfg.get("relax_strain_suffix_t_spacing"))

    def _checker(text, index, left_char, right_char):
        if relax_strain_suffix_t_spacing:
            excerpt = (text or "")[max(0, index - 16): index + 16]
            if audit_thesis.is_relaxed_strain_suffix_t_excerpt(excerpt):
                return False
        return _needs_cjk_latin_space(text, index, left_char, right_char)

    return _checker


def fix_sp_cjk_latin(p_elem, cfg=None, runtime=None):
    checker = _make_cjk_latin_boundary_checker(cfg=cfg, runtime=runtime)
    changed = _fix_spacing_inside_runs(p_elem, checker)
    return _fix_spacing_between_runs(p_elem, checker) or changed


def fix_sp_num_cjk(p_elem, cfg=None, runtime=None):
    active_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    if active_cfg.get("mixed_spacing_policy") == "compact":
        return False
    changed = _fix_spacing_inside_runs(p_elem, _needs_num_cjk_space)
    return _fix_spacing_between_runs(p_elem, _needs_num_cjk_space) or changed


_UNIT_SPACE_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)([A-Za-z]{1,5}|℃)(?![A-Za-z])")
_PERCENT_UNIT_RE = re.compile(r"(?<![0-9A-Za-z])(\d+(?:\.\d+)?)([%％])")
_UNIT_SPACE_SKIP = {"e", "E", "x", "X"}


def _needs_num_unit_space(left_text, right_text):
    if not left_text or not right_text:
        return False
    if not left_text[-1].isdigit():
        return False
    match = re.match(r"([A-Za-z]{1,5}|℃)", right_text)
    if match is None:
        return False
    return match.group(1) not in _UNIT_SPACE_SKIP


def _restore_space_before_percent_between_runs(p_elem):
    changed = False
    while True:
        text_nodes = _plain_text_nodes_in_paragraph(p_elem)
        inserted = False
        for index in range(1, len(text_nodes)):
            right_text = text_nodes[index].text or ""
            if not (right_text and right_text[0] in "%％"):
                continue
            left_text = text_nodes[index - 1].text or ""
            if not re.search(r"(?<![0-9A-Za-z])\d+(?:\.\d+)?$", left_text):
                continue
            text_nodes[index].text = f" {right_text}"
            changed = True
            inserted = True
            break
        if not inserted:
            return changed


def fix_lnu_unit_spacing(p_elem):
    """在正文中为“数字+单位/百分号”补一个空格。"""
    changed = False
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        original = text_elem.text
        if not original:
            continue

        def _repl(match):
            unit = match.group(2)
            if unit in _UNIT_SPACE_SKIP:
                return match.group(0)
            return f"{match.group(1)} {unit}"

        updated = _UNIT_SPACE_RE.sub(_repl, original)
        updated = _PERCENT_UNIT_RE.sub(r"\1 \2", updated)
        if updated != original:
            text_elem.text = updated
            changed = True
    while True:
        inserted = False
        non_empty_runs = [run for run in p_elem.findall(".//w:r", NSMAP) if get_run_text(run)]
        for left_run, right_run in zip(non_empty_runs, non_empty_runs[1:]):
            left_text = get_run_text(left_run)
            right_text = get_run_text(right_run)
            if not _needs_num_unit_space(left_text, right_text):
                continue
            if left_text[-1].isspace() or right_text[0].isspace():
                continue
            parent_children = list(p_elem)
            insert_at = parent_children.index(right_run)
            p_elem.insert(insert_at, _make_text_run_like(left_run, " "))
            changed = True
            inserted = True
            break
        if not inserted:
            break
    changed = _restore_space_before_percent_between_runs(p_elem) or changed
    return changed


def fix_kw02_trailing_punct(p_elem):
    text = get_paragraph_text(p_elem).strip()
    if not text.startswith("关键词"):
        return
    for text_elem in reversed(p_elem.findall(".//w:t", NSMAP)):
        if not text_elem.text:
            continue
        updated = re.sub(r"[。，；：！？\.,:;!?]+\s*$", "", text_elem.text)
        if updated != text_elem.text:
            text_elem.text = updated
        return


def fix_kw01_keyword_count(p_elem, cfg=None):
    cfg = cfg or {}
    text = get_paragraph_text(p_elem).strip()
    if not text:
        return 0

    max_keywords = cfg.get("kw_max")
    if max_keywords is None:
        return 0

    if text.startswith("关键词"):
        prefix_re = re.compile(r"^(关键词\s*[：:]\s*)")
        separator = str(cfg.get("kw_cn_separator", "；") or "；")
    elif re.match(r"^key\s*words?\b", text, re.IGNORECASE):
        prefix_re = re.compile(r"^(key\s*words?\s*[：:]\s*)", re.IGNORECASE)
        separator = str(cfg.get("kw_en_separator", "; ") or "; ")
    else:
        return 0

    match = prefix_re.match(text)
    if match is None:
        return 0

    prefix = match.group(1)
    payload = text[match.end():].strip()
    keywords = [item.strip() for item in re.split(r"[；;]", payload) if item.strip()]
    normalized_text = prefix + separator.join(keywords[:max_keywords]) if keywords else prefix.rstrip()
    if normalized_text == text:
        return 0
    first_text = None
    remaining = []
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        if first_text is None:
            first_text = text_elem
        else:
            remaining.append(text_elem)
    if first_text is None:
        return 0

    first_text.text = normalized_text
    if first_text.get(f"{{{XML_SPACE_NS}}}space") is not None and not (normalized_text.startswith(" ") or normalized_text.endswith(" ")):
        del first_text.attrib[f"{{{XML_SPACE_NS}}}space"]
    for text_elem in remaining:
        text_elem.text = ""
    return max(len(keywords) - max_keywords, 1)


def _style_name_map(style_map):
    return {
        style_id: re.sub(r"[\s_-]+", "", str(props.get("name") or style_id).strip().lower())
        for style_id, props in (style_map or {}).items()
    }


def _parse_heading_chapter_number(text):
    stripped = (text or "").strip()
    if not stripped:
        return None
    match = re.match(r"^第\s*(\d+)\s*章", stripped)
    if match is not None:
        return int(match.group(1))
    match = re.match(r"^(\d+)\s*章", stripped)
    if match is not None:
        return int(match.group(1))
    match = re.match(r"^(\d+)\s*$", stripped)
    if match is not None:
        return int(match.group(1))
    match = re.match(r"^(\d+)\s+[\u4e00-\u9fff（(【\[]", stripped)
    if match is not None:
        return int(match.group(1))
    return None


def normalize_toc_title_paragraph(document_root, style_map=None, cfg=None):
    model = build_document_model(document_root, style_map or {})
    toc_title = next((node for node in model.paragraphs if node.module == "toc_title"), None)
    if toc_title is None:
        return 0

    p_elem = toc_title.elem
    before_xml = ET.tostring(p_elem, encoding="unicode")
    p_pr = ensure_ppr(p_elem)
    p_style = get_or_create(p_pr, "w:pStyle")
    changed = 0
    if p_style.get(f"{{{W_NS}}}val") != "TOCHeading":
        set_attr(p_style, "val", "TOCHeading")
        changed += 1

    jc = get_or_create(p_pr, "w:jc")
    if jc.get(f"{{{W_NS}}}val") != "center":
        set_attr(jc, "val", "center")
        changed += 1

    spacing = get_or_create(p_pr, "w:spacing")
    for attr, value in (("before", "0"), ("after", "0"), ("line", "360"), ("lineRule", "auto")):
        if spacing.get(f"{{{W_NS}}}{attr}") != value:
            set_attr(spacing, attr, value)
            changed += 1

    active_cfg = cfg or {}
    title_font = str(active_cfg.get("toc_title_font", "黑体") or "黑体")
    title_size = int(active_cfg.get("toc_title_size", 32) or 32)
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if not get_run_text(run_elem).strip():
            continue
        set_run_font(run_elem, title_font, ascii_font="Times New Roman", size=title_size, bold=False)
    if changed == 0 and ET.tostring(p_elem, encoding="unicode") != before_xml:
        changed = 1
    return changed


def normalize_toc_entry_paragraphs(document_root, style_map=None, cfg=None):
    model = build_document_model(document_root, style_map or {})
    changed = 0
    active_cfg = cfg or {}
    name_map = _style_name_map(style_map or {})
    for node in model.paragraphs:
        if node.module != "toc_entry":
            continue

        p_elem = node.elem
        before_xml = ET.tostring(p_elem, encoding="unicode")
        p_pr = ensure_ppr(p_elem)
        style_val = audit_thesis.get_w_attr(p_pr.find("w:pStyle", NSMAP), "val")
        normalized_name = name_map.get(style_val, "")
        if style_val == "TOC1" or normalized_name.endswith("toc1") or normalized_name.endswith("toc1char") or "toc1" in normalized_name:
            entry_font = str(active_cfg.get("toc_level1_font", active_cfg.get("toc_entry_font", "宋体")) or "宋体")
            entry_size = int(active_cfg.get("toc_level1_size", active_cfg.get("toc_entry_size", 22)) or 22)
            expected_after = int((active_cfg.get("toc_level1_after_pt", 5) or 5) * 20)
            entry_bold = False
        elif style_val == "TOC2" or "toc2" in normalized_name:
            entry_font = str(active_cfg.get("toc_entry_font", "宋体") or "宋体")
            entry_size = int(active_cfg.get("toc_entry_size", 22) or 22)
            expected_after = int((active_cfg.get("toc_level2_after_pt", 5) or 5) * 20)
            entry_bold = False
        else:
            entry_font = str(active_cfg.get("toc_entry_font", "宋体") or "宋体")
            entry_size = int(active_cfg.get("toc_entry_size", 22) or 22)
            expected_after = int((active_cfg.get("toc_level3_after_pt", 5) or 5) * 20)
            entry_bold = False
        ind = p_pr.find("w:ind", NSMAP)
        if style_val == "TOC1" or normalized_name.endswith("toc1") or normalized_name.endswith("toc1char") or "toc1" in normalized_name:
            if ind is not None:
                p_pr.remove(ind)
                changed += 1
        spacing = get_or_create(p_pr, "w:spacing")
        expected_line = int(active_cfg.get("toc_entry_line", 276) or 276)
        if spacing.get(f"{{{W_NS}}}before") != "0":
            set_attr(spacing, "before", "0")
            changed += 1
        if spacing.get(f"{{{W_NS}}}after") != str(expected_after):
            set_attr(spacing, "after", str(expected_after))
            changed += 1
        if spacing.get(f"{{{W_NS}}}line") != str(expected_line):
            set_attr(spacing, "line", str(expected_line))
            changed += 1
        if spacing.get(f"{{{W_NS}}}lineRule") != "auto":
            set_attr(spacing, "lineRule", "auto")
            changed += 1

        tabs = insert_tabs_before_spacing(p_pr)
        right_tab = None
        for tab in tabs.findall("w:tab", NSMAP):
            if tab.get(f"{{{W_NS}}}val") == "right":
                right_tab = tab
                break
        if right_tab is None:
            right_tab = ET.SubElement(tabs, f"{{{W_NS}}}tab")
            changed += 1
        expected_tab_pos = str(int(active_cfg.get("toc_tab_pos", 9000) or 9000))
        for attr, value in (("val", "right"), ("leader", "dot"), ("pos", expected_tab_pos)):
            if right_tab.get(f"{{{W_NS}}}{attr}") != value:
                set_attr(right_tab, attr, value)
                changed += 1

        for run_elem in p_elem.findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            set_run_font(run_elem, entry_font, ascii_font="Times New Roman", size=entry_size, bold=entry_bold)
        if ET.tostring(p_elem, encoding="unicode") != before_xml:
            changed += 1
    return changed


def remove_duplicate_body_toc_title(document_root, style_map=None):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    model = build_document_model(document_root, style_map or {})
    toc_nodes = [node for node in model.paragraphs if node.container_section == "toc"]
    if not toc_nodes:
        return 0

    removed = 0
    toc_title_nodes = [node for node in toc_nodes if node.module == "toc_title"]
    for node in toc_title_nodes[1:]:
        if node.elem in body:
            body.remove(node.elem)
            removed += 1
    if removed:
        return removed

    body_paragraphs = [child for child in body if child.tag == f"{{{W_NS}}}p"]
    body_indexes = {id(p_elem): idx for idx, p_elem in enumerate(body_paragraphs)}
    toc_indexes = [body_indexes[id(node.elem)] for node in toc_nodes if id(node.elem) in body_indexes]
    if not toc_indexes:
        return 0

    for idx in range(max(toc_indexes) + 1, len(body_paragraphs)):
        p_elem = body_paragraphs[idx]
        text = get_paragraph_text(p_elem).strip()
        if not text:
            continue
        if re.sub(r"[\s\u3000]+", "", text) == "目录":
            body.remove(p_elem)
            return 1
        break
    return 0


def _caption_reference_candidates(prefix, number):
    normalized = re.sub(r"[．-]", ".", number)
    return {
        f"{prefix}{normalized}",
        f"{prefix}{normalized.replace('.', '-')}",
    }


def _contains_caption_reference(text: str, candidates: set[str]) -> bool:
    compact_text = re.sub(r"[\s\u3000]+", "", text or "")
    return any(candidate in compact_text for candidate in candidates)


def _paragraph_outline_level(p_elem, style_map) -> int | None:
    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is None:
        return None
    style_elem = p_pr.find("w:pStyle", NSMAP)
    if style_elem is None:
        return None
    style_id = style_elem.get(f"{{{W_NS}}}val")
    if not style_id:
        return None
    return (style_map or {}).get(style_id, {}).get("outlineLvl")


def _is_generic_caption_lead_text(text: str, prefix: str, number: str) -> bool:
    compact = re.sub(r"[\s\u3000]+", "", text or "")
    if not compact:
        return False
    compact = re.sub(r"[。．；;，,:：]+$", "", compact)
    normalized_number = re.sub(r"[．-]", ".", number)
    number_variants = {
        normalized_number,
        normalized_number.replace(".", "-"),
    }
    patterns = {
        f"如{prefix}{variant}所示"
        for variant in number_variants
    }
    patterns.update(
        {
            f"见{prefix}{variant}"
            for variant in number_variants
        }
    )
    patterns.update(
        {
            f"相关结果如{prefix}{variant}所示"
            for variant in number_variants
        }
    )
    return compact in patterns


def remove_synthetic_caption_reference_leads(document_root, style_map=None):
    """删除旧版工具生成的独立“相关结果如图/表X.X所示。”模板句。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    paragraph_tag = f"{{{W_NS}}}p"
    body_children = list(body)
    changed = 0
    index = 0
    while index < len(body_children):
        child = body_children[index]
        if child.tag != paragraph_tag:
            index += 1
            continue
        text = get_paragraph_text(child).strip()
        match = re.match(r"^相关结果如(图|表)(\d+(?:[.\-]\d+)*)所示[。.]?$", text)
        if match is None:
            index += 1
            continue
        prefix, number = match.groups()
        next_idx = index + 1
        while next_idx < len(body_children):
            next_child = body_children[next_idx]
            if next_child.tag != paragraph_tag:
                break
            next_text = get_paragraph_text(next_child).strip()
            if next_text:
                break
            next_idx += 1
        if next_idx >= len(body_children):
            index += 1
            continue
        next_text = get_paragraph_text(body_children[next_idx]).strip()
        if re.match(rf"^{prefix}\s*{re.escape(number)}\b", next_text):
            body.remove(child)
            del body_children[index]
            changed += 1
            continue
        index += 1
    return changed


def rebalance_figure_blocks_for_layout(document_root, style_map=None, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import rebalance_figure_blocks_for_layout as _impl

    return _impl(document_root, style_map, cfg, runtime)

def rebalance_table_blocks_for_layout(document_root, style_map=None, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import rebalance_table_blocks_for_layout as _impl

    return _impl(document_root, style_map, cfg, runtime)

def promote_post_caption_reference_blocks(document_root, cfg=None, style_map=None, runtime=None):
    """将图后已有的说明性正文整体前移到图块前，避免生成生硬的独立“见图/见表”段。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    caption_pattern = re.compile(r"^(图|表)\s*(\d+(?:[.\-]\d+)+)")
    changed = 0

    def _has_drawing(p_elem):
        return p_elem.find(".//w:drawing", NSMAP) is not None

    while True:
        model = build_document_model(document_root, style_map or {})
        body_paragraphs = [child for child in list(body) if child.tag == f"{{{W_NS}}}p"]
        body_index = {id(p_elem): idx for idx, p_elem in enumerate(body_paragraphs)}
        node_by_elem_id = {
            id(node.elem): node
            for node in model.paragraphs
            if id(node.elem) in body_index
        }
        moved = False

        for p_elem in body_paragraphs:
            node = node_by_elem_id.get(id(p_elem))
            if node is None or node.module != "body_caption" or node.section != "body":
                continue

            match = caption_pattern.match((node.text or "").strip())
            if match is None:
                continue

            prefix, number = match.groups()
            candidates = _caption_reference_candidates(prefix, number)
            caption_idx = body_index[id(p_elem)]
            anchor_idx = caption_idx

            if caption_idx > 0:
                prev_elem = body_paragraphs[caption_idx - 1]
                if _has_drawing(prev_elem):
                    anchor_idx = caption_idx - 1

            if any(
                any(candidate in prior_node.compact_text for candidate in candidates)
                for prior_elem in body_paragraphs[:anchor_idx]
                if (prior_node := node_by_elem_id.get(id(prior_elem))) is not None
                and prior_node.section == "body"
                and prior_node.kind == "body"
            ):
                continue

            block_end_idx = caption_idx
            while block_end_idx + 1 < len(body_paragraphs):
                next_node = node_by_elem_id.get(id(body_paragraphs[block_end_idx + 1]))
                if next_node is None or next_node.module not in CAPTION_EN_MODULES | CAPTION_NOTE_MODULES:
                    break
                block_end_idx += 1

            scan_idx = block_end_idx + 1
            last_reference_idx = None
            while scan_idx < len(body_paragraphs):
                if _has_drawing(body_paragraphs[scan_idx]):
                    break
                scan_node = node_by_elem_id.get(id(body_paragraphs[scan_idx]))
                if scan_node is None or scan_node.section != "body":
                    break
                if scan_node.kind in {"caption", "figure", "drawing", "reference", "h1", "h2"}:
                    break
                if scan_node.kind == "body" and any(
                    candidate in scan_node.compact_text for candidate in candidates
                ):
                    last_reference_idx = scan_idx
                scan_idx += 1

            if last_reference_idx is None:
                continue

            move_slice = body_paragraphs[block_end_idx + 1 : last_reference_idx + 1]
            if not move_slice:
                continue

            anchor_elem = body_paragraphs[anchor_idx]
            for moving_elem in move_slice:
                body.remove(moving_elem)

            insert_pos = list(body).index(anchor_elem)
            for offset, moving_elem in enumerate(move_slice):
                body.insert(insert_pos + offset, moving_elem)

            changed += 1
            moved = True
            break

        if not moved:
            break

    return changed


def insert_missing_caption_reference_leads(document_root, cfg=None, style_map=None, runtime=None):
    """Compatibility no-op: do not invent prose references before figure/table captions."""
    return 0


def renumber_lnu_captions(document_root, style_map=None):
    model = build_document_model(document_root, style_map or {})
    chapter_no = None
    counters = Counter()
    changed = 0
    preface_active = False

    for node in model.paragraphs:
        if node.section != "body":
            continue

        if node.kind == "h1":
            heading_text = (node.text or "").strip()
            if is_preface_heading_title(heading_text):
                chapter_no = 0
                preface_active = True
            else:
                parsed = _parse_heading_chapter_number(heading_text)
                if parsed is not None:
                    chapter_no = parsed
                elif preface_active:
                    chapter_no = 1 if chapter_no in (None, 0) else chapter_no + 1
                preface_active = False
            continue

        if node.module != "body_caption" or chapter_no is None:
            continue

        text = node.text.strip()
        match = re.match(r"^(图|表)\s*\d+(?:[.\-]\d+)?", text)
        if match is None:
            continue

        prefix = match.group(1)
        counters[(chapter_no, prefix)] += 1
        target_number = f"{chapter_no}.{counters[(chapter_no, prefix)]}"
        target_prefix = f"{prefix}{target_number}"

        paragraph_text = "".join((text_elem.text or "") for text_elem in node.elem.findall(".//w:t", NSMAP))
        updated_paragraph_text = re.sub(rf"^{prefix}\s*\d+(?:[.\-]\d+)?", target_prefix, paragraph_text, count=1)
        english_label = "Table" if prefix == "表" else "Fig."
        updated_paragraph_text = re.sub(
            r"^(Table|Fig\.?)\s*\d+(?:[.\-]\d+)?",
            f"{english_label}{target_number}" if english_label == "Fig." else f"{english_label} {target_number}",
            updated_paragraph_text,
            count=1,
        )

        if updated_paragraph_text != paragraph_text:
            text_elems = node.elem.findall(".//w:t", NSMAP)
            if not text_elems:
                continue

            original_prefix_match = re.match(r"^(图|表)\s*\d+(?:[.\-]\d+)?", paragraph_text)
            if original_prefix_match:
                prefix_len = original_prefix_match.end()
                new_prefix_match = re.match(r"^(图|表)\d+\.\d+", updated_paragraph_text)
                if new_prefix_match:
                    new_prefix = new_prefix_match.group(0)
                    _replace_caption_prefix_across_text_nodes(text_elems, prefix_len, new_prefix)
            else:
                text_elems[0].text = updated_paragraph_text
                for text_elem in text_elems[1:]:
                    text_elem.text = ""
            changed += 1

    return changed


def _replace_caption_prefix_across_text_nodes(text_elems, original_prefix_len, new_prefix):
    remaining = original_prefix_len
    inserted = False
    for text_elem in text_elems:
        text = text_elem.text or ""
        if remaining <= 0:
            break
        if len(text) <= remaining:
            text_elem.text = new_prefix if not inserted else ""
            inserted = True
            remaining -= len(text)
            continue
        text_elem.text = (new_prefix if not inserted else "") + text[remaining:]
        inserted = True
        remaining = 0


def _run_has_soft_break(run_elem):
    for child in list(run_elem):
        if child.tag == f"{{{W_NS}}}cr":
            return True
        if child.tag == f"{{{W_NS}}}br":
            br_type = child.get(f"{{{W_NS}}}type")
            if br_type not in {"page", "column"}:
                return True
    return False


def _split_run_segments_on_soft_breaks(run_elem):
    segments: list[list[ET.Element]] = [[]]
    for child in list(run_elem):
        is_soft_break = child.tag == f"{{{W_NS}}}cr"
        if child.tag == f"{{{W_NS}}}br":
            br_type = child.get(f"{{{W_NS}}}type")
            is_soft_break = br_type not in {"page", "column"}
        if is_soft_break:
            segments.append([])
            continue
        segments[-1].append(copy.deepcopy(child))
    return segments


def _soft_line_break_preserve_paragraph_ids(document_root, cfg=None, runtime=None, style_map=None):
    resolved_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    if not bool(resolved_cfg.get("preserve_caption_soft_line_breaks")):
        return set()
    model = build_document_model(document_root, style_map or {})
    return {
        id(node.elem)
        for node in model.paragraphs
        if node.module in _SOFT_LINE_BREAK_PRESERVE_MODULES or node.kind == "caption"
    }


def fix_soft_line_breaks(document_root, cfg=None, runtime=None, style_map=None):
    """将软回车拆分为新段落，避免用 Shift+Enter 伪造段落布局。"""
    parent_map = {child: parent for parent in document_root.iter() for child in list(parent)}
    preserve_paragraph_ids = _soft_line_break_preserve_paragraph_ids(
        document_root,
        cfg=cfg,
        runtime=runtime,
        style_map=style_map,
    )
    changed = 0

    for p_elem in list(document_root.findall(".//w:p", NSMAP)):
        if id(p_elem) in preserve_paragraph_ids:
            continue
        run_elems = [child for child in list(p_elem) if child.tag == f"{{{W_NS}}}r"]
        if not any(_run_has_soft_break(run_elem) for run_elem in run_elems):
            continue

        original_ppr = p_elem.find("w:pPr", NSMAP)
        segments: list[list[ET.Element]] = [[]]
        for child in list(p_elem):
            if child.tag == f"{{{W_NS}}}pPr":
                continue
            if child.tag != f"{{{W_NS}}}r" or not _run_has_soft_break(child):
                segments[-1].append(copy.deepcopy(child))
                continue
            run_segments = _split_run_segments_on_soft_breaks(child)
            for seg_index, run_children in enumerate(run_segments):
                if run_children:
                    new_run = ET.Element(f"{{{W_NS}}}r")
                    for run_child in run_children:
                        new_run.append(run_child)
                    segments[-1].append(new_run)
                if seg_index < len(run_segments) - 1:
                    segments.append([])

        if len(segments) <= 1:
            continue

        parent = parent_map.get(p_elem)
        if parent is None:
            continue

        insert_idx = list(parent).index(p_elem) + 1
        for child in list(p_elem):
            p_elem.remove(child)
        if original_ppr is not None:
            p_elem.append(copy.deepcopy(original_ppr))
        for child in segments[0]:
            p_elem.append(child)

        for segment in segments[1:]:
            new_p = ET.Element(f"{{{W_NS}}}p")
            if original_ppr is not None:
                new_p.append(copy.deepcopy(original_ppr))
            for child in segment:
                new_p.append(child)
            parent.insert(insert_idx, new_p)
            insert_idx += 1

        changed += 1

    return changed


def normalize_object_wrapping(document_root, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import normalize_object_wrapping as _impl

    return _impl(document_root, cfg, runtime)

def fix_page_margins(document_root, cfg=None, runtime=None):
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    top_margin = str(cfg.get("margin_fix_top", cfg.get("margin_fix", 1440)))
    bottom_margin = str(cfg.get("margin_fix_bottom", cfg.get("margin_fix", 1440)))
    left_margin = str(cfg.get("margin_fix_left", cfg.get("margin_fix", 1440)))
    right_margin = str(cfg.get("margin_fix_right", cfg.get("margin_fix", 1440)))
    gutter = str(cfg.get("margin_gutter", 0))
    # 只修改正文节（w:body/w:sectPr），跳过封面等前置节（w:p/w:pPr/w:sectPr）
    body = document_root.find("w:body", NSMAP)
    body_sect_prs = []
    if body is not None:
        # 正文末尾的主节
        main_sect = body.find("w:sectPr", NSMAP)
        if main_sect is not None:
            body_sect_prs.append(main_sect)
        # 段落内的分节符中，跳过第一节（封面节），保留其余
        inline_sects = [
            p.find("w:pPr/w:sectPr", NSMAP)
            for p in body.findall("w:p", NSMAP)
        ]
        inline_sects = [s for s in inline_sects if s is not None]
        # 第一个 inline sectPr 通常是封面节，跳过；其余正常修改
        body_sect_prs.extend(inline_sects[1:])
    for sect_pr in body_sect_prs:
        pg_mar = sect_pr.find("w:pgMar", NSMAP)
        if pg_mar is None:
            pg_mar = ET.SubElement(sect_pr, f"{{{W_NS}}}pgMar")
        set_attr(pg_mar, "left", left_margin)
        set_attr(pg_mar, "right", right_margin)
        set_attr(pg_mar, "top", top_margin)
        set_attr(pg_mar, "bottom", bottom_margin)
        if gutter != "0":
            set_attr(pg_mar, "gutter", gutter)

    if not is_lnu_profile(runtime):
        return

    for sect_pr in body_sect_prs:
        pg_sz = get_or_create(sect_pr, "w:pgSz")
        set_attr(pg_sz, "w", "11906")
        set_attr(pg_sz, "h", "16838")


def fix_body_paragraph(p_elem, cfg=None, runtime=None, style_map=None):
    spec = resolve_body_format(cfg=cfg, runtime=runtime)
    p_pr = ensure_ppr(p_elem)
    _clear_heading_style_for_body_paragraph(p_elem, style_map=style_map)
    for tag_name in ("pageBreakBefore", "keepNext", "keepLines", "outlineLvl"):
        _clear_paragraph_property(p_pr, tag_name)
    spacing = get_or_create(p_pr, "w:spacing")
    set_attr(spacing, "line", str(spec["line"]))
    set_attr(spacing, "lineRule", "auto")
    set_attr(spacing, "before", "0")
    set_attr(spacing, "after", "0")

    ind = get_or_create(p_pr, "w:ind")
    set_attr(ind, "firstLine", str(spec["indent"]))

    jc = get_or_create(p_pr, "w:jc")
    set_attr(jc, "val", spec["alignment"])
    auto_de = get_or_create(p_pr, "w:autoSpaceDE")
    set_attr(auto_de, "val", "0")
    auto_dn = get_or_create(p_pr, "w:autoSpaceDN")
    set_attr(auto_dn, "val", "0")

    for run_elem in p_elem.findall(".//w:r", NSMAP):
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", spec["east_asia"])
        set_attr(r_fonts, "ascii", spec["ascii_font"])
        set_attr(r_fonts, "hAnsi", spec["ascii_font"])
        ensure_size(run_elem, str(spec["size"]))

    snap = p_pr.find("w:snapToGrid", NSMAP)
    if snap is None:
        snap = ET.SubElement(p_pr, f"{{{W_NS}}}snapToGrid")
    snap.set(f"{{{W_NS}}}val", "0")


def normalize_heading_paragraph_layout(p_pr, first_line="0"):
    ind = get_or_create(p_pr, "w:ind")
    set_attr(ind, "firstLine", str(first_line))
    for attr_name in ("firstLineChars", "left", "leftChars", "hanging", "hangingChars"):
        namespaced = f"{{{W_NS}}}{attr_name}"
        if namespaced in ind.attrib:
            del ind.attrib[namespaced]
    num_pr = p_pr.find("w:numPr", NSMAP)
    if num_pr is not None:
        p_pr.remove(num_pr)
    for tag_name in ("pageBreakBefore", "keepNext", "keepLines"):
        elem = p_pr.find(f"w:{tag_name}", NSMAP)
        if tag_name == "pageBreakBefore":
            if elem is not None:
                p_pr.remove(elem)
            continue
        if elem is None:
            elem = ET.SubElement(p_pr, f"{{{W_NS}}}{tag_name}")
        set_attr(elem, "val", "0")


def fix_heading_paragraph(p_elem, alignment, set_size, cfg=None, heading_style_ids=None, runtime=None):
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    active_heading_style_ids = resolve_fix_heading_style_ids(
        heading_style_ids=heading_style_ids,
        runtime=runtime,
    )
    p_pr = ensure_ppr(p_elem)
    heading_level = "h1" if alignment == "center" else ("h3" if set_size else "h2")
    p_style, created = ensure_pstyle_first(p_pr)
    set_attr(p_style, "val", active_heading_style_ids.get(heading_level, f"Heading{heading_level[1]}"))
    # 清除段落级 rPr 中可能残留的 bold（来自样式继承）
    ppr_rpr = p_pr.find("w:rPr", NSMAP)
    if ppr_rpr is not None:
        for bold_tag in ppr_rpr.findall("w:b", NSMAP) + ppr_rpr.findall("w:bCs", NSMAP):
            ppr_rpr.remove(bold_tag)

    ensure_alignment_and_indent(p_elem, alignment)
    normalize_heading_paragraph_layout(p_pr)
    heading_size = None
    if alignment == "center":
        heading_size = cfg.get("h1_size", 30)
    elif set_size:
        heading_size = cfg.get("h3_size", 24)
    else:
        heading_size = cfg.get("h2_size", 30)
    h_font = cfg.get(f"{heading_level}_font", cfg.get("h_font", "黑体")) or cfg.get("h_font") or "黑体"

    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if not get_run_text(run_elem).strip():
            continue
        set_run_font(run_elem, h_font, ascii_font="Times New Roman", size=heading_size, bold=False)


def fix_heading_num_space(p_elem):
    """确保标题编号与标题文字之间保留一个半角空格，同时不重写后续 run。
    处理编号跨多个 run 的情况（如 run1='1. ' / run2='1 研究背景'）。
    """
    run_elems = p_elem.findall(".//w:r", NSMAP)
    if not run_elems:
        return

    # 收集全段文本，找到完整编号前缀
    full_text = get_paragraph_text(p_elem)
    num_match = re.match(r"^((?:\d+\s*[\.．]\s*)+\d+[\.．]?)([\s\S]*)$", full_text)
    if not num_match:
        return

    raw_prefix = num_match.group(1)   # e.g. "1. 1" or "1.1. 1"
    rest_full = num_match.group(2)    # e.g. " 研究背景"

    # 清理编号内部多余空格：1. 1 → 1.1
    clean_prefix = re.sub(r"\s*[\.．]\s*", ".", raw_prefix)
    # 确保编号与标题文字之间有且仅有一个空格
    clean_text = clean_prefix + " " + rest_full.lstrip(" \t\u3000") if rest_full.strip() else clean_prefix

    if clean_text == full_text:
        return  # 已合规，无需修改

    # 将清理后的完整文本写回第一个 run，清空其余 run 的文本
    first_text_elem = None
    for run_elem in run_elems:
        text_elem = run_elem.find("w:t", NSMAP)
        if text_elem is not None and text_elem.text:
            first_text_elem = text_elem
            break
    if first_text_elem is None:
        return

    first_text_elem.text = clean_text
    first_text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")

    # 清空后续 run 中原来属于"编号+标题"部分的文本（保留格式标签）
    chars_written = len(clean_text)
    chars_from_orig = len(full_text)
    if chars_written != chars_from_orig:
        # 原文本已被第一个 run 完全替换，清除其余 run 中重复的文本
        skip_chars = len(full_text) - len(first_text_elem.text or "")
        remaining = skip_chars
        for run_elem in run_elems[1:]:
            if remaining <= 0:
                break
            text_elem = run_elem.find("w:t", NSMAP)
            if text_elem is not None and text_elem.text:
                if len(text_elem.text) <= remaining:
                    remaining -= len(text_elem.text)
                    text_elem.text = ""
                else:
                    text_elem.text = text_elem.text[remaining:]
                    remaining = 0


def fix_run_fonts(p_elem, east_asia, ascii_font):
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", east_asia)
        set_attr(r_fonts, "ascii", ascii_font)
        set_attr(r_fonts, "hAnsi", ascii_font)


def fix_heading_spacing(p_elem, heading_level, cfg=None, after_twip=None, runtime=None):
    p_pr = ensure_ppr(p_elem)
    spacing = get_or_create(p_pr, "w:spacing")
    if isinstance(heading_level, str):
        active_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
        level = heading_level
        if level not in HEADING_SPACING_DEFAULTS:
            return
        before = active_cfg.get(f"{level}_spacing_before", HEADING_SPACING_DEFAULTS[level]["before"])
        after = active_cfg.get(f"{level}_spacing_after", HEADING_SPACING_DEFAULTS[level]["after"])
        set_attr(spacing, "before", str(before))
        set_attr(spacing, "after", str(after))
    else:
        set_attr(spacing, "before", str(heading_level))
        if after_twip is not None:
            set_attr(spacing, "after", str(after_twip))
    set_attr(spacing, "line", "360")
    set_attr(spacing, "lineRule", "auto")


def fix_heading_page_break(p_elem):
    p_pr = ensure_ppr(p_elem)
    page_break_before = get_or_create(p_pr, "w:pageBreakBefore")
    set_attr(page_break_before, "val", "1")


def fix_remove_empty_before_headings(document_root, style_map, body_para_ids):
    """删除 body 节中紧接在标题前的空段落（无意义空行）。
    直接用文本正则判断标题，不依赖加粗信号，防止加粗被移除后识别失效。
    """
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return

    def _is_heading_by_text(p_elem):
        return match_heading_by_text(get_paragraph_text(p_elem)) is not None

    children = list(body)
    to_remove = []
    for i, elem in enumerate(children):
        if elem.tag != f"{{{W_NS}}}p":
            continue
        if id(elem) not in body_para_ids:
            continue
        if get_paragraph_text(elem).strip():
            continue
        prev_non_empty = None
        for prev_idx in range(i - 1, -1, -1):
            prev_elem = children[prev_idx]
            if prev_elem.tag == f"{{{W_NS}}}p" and not get_paragraph_text(prev_elem).strip():
                continue
            prev_non_empty = prev_elem
            break
        if prev_non_empty is not None and prev_non_empty.tag == f"{{{W_NS}}}tbl":
            continue
        # 向后跳过所有空段，看是否紧跟着一个标题
        for j in range(i + 1, len(children)):
            if children[j].tag != f"{{{W_NS}}}p":
                break
            next_text = get_paragraph_text(children[j]).strip()
            if not next_text:
                continue  # 跳过空段，继续往后找
            if _is_heading_by_text(children[j]):
                to_remove.append(elem)
            break
    for elem in to_remove:
        body.remove(elem)


def fix_remove_trailing_empty_before_refs(document_root, style_map, body_para_ids):
    """删除 body 节中紧接在参考文献列表前的连续空段落。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return
    children = list(body)
    to_remove = []
    for i, elem in enumerate(children):
        if elem.tag != f"{{{W_NS}}}p":
            continue
        if id(elem) not in body_para_ids:
            continue
        if get_paragraph_text(elem).strip():
            continue
        # 向后跳过所有空段，看是否紧跟着参考文献段落
        followed_by_refs = False
        for j in range(i + 1, len(children)):
            if children[j].tag != f"{{{W_NS}}}p":
                break
            next_text = get_paragraph_text(children[j]).strip()
            if not next_text:
                continue
            if classify_paragraph(children[j], style_map) == "reference":
                followed_by_refs = True
            break
        if followed_by_refs:
            to_remove.append(elem)
    for elem in to_remove:
        body.remove(elem)


def _run_is_hidden(run_elem):
    r_pr = run_elem.find("w:rPr", NSMAP)
    return r_pr is not None and r_pr.find("w:vanish", NSMAP) is not None


def _is_hidden_page_number_artifact_paragraph(p_elem):
    instr_texts = [
        (instr.text or "").upper()
        for instr in p_elem.findall(".//w:instrText", NSMAP)
        if (instr.text or "").strip()
    ]
    if not any("PAGE" in text for text in instr_texts):
        return False

    visible_text = get_paragraph_text(p_elem).strip()
    if not visible_text or not re.fullmatch(r"[-—–\d\s]+", visible_text):
        return False

    text_runs = []
    for run_elem in p_elem.findall("w:r", NSMAP):
        run_text = get_run_text(run_elem)
        has_field = (
            run_elem.find("w:instrText", NSMAP) is not None
            or run_elem.find("w:fldChar", NSMAP) is not None
        )
        if has_field or not run_text.strip():
            continue
        text_runs.append(run_elem)

    return bool(text_runs) and all(_run_is_hidden(run_elem) for run_elem in text_runs)


def fix_remove_hidden_page_number_artifacts(document_root):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    removed = 0
    for p_elem in list(body.findall("w:p", NSMAP)):
        if not _is_hidden_page_number_artifact_paragraph(p_elem):
            continue
        body.remove(p_elem)
        removed += 1
    return removed


def build_settings_with_update_fields(settings_xml=None):
    return fix_output_parts.build_settings_with_update_fields(
        settings_xml,
        w_ns=W_NS,
        nsmap=NSMAP,
        set_attr=set_attr,
    )


def _has_toc_field_instr(p_elem):
    return paragraph_has_toc_field_instr(p_elem, nsmap=NSMAP)


def is_generated_toc_paragraph(p_elem):
    p_pr = p_elem.find("w:pPr", NSMAP)
    if p_pr is not None:
        p_style = p_pr.find("w:pStyle", NSMAP)
        if p_style is not None:
            style_id = p_style.get(f"{{{W_NS}}}val", "")
            if is_toc_generated_style_id(style_id):
                return True

    return _has_toc_field_instr(p_elem)


def _is_toc_title_text(text: str) -> bool:
    return is_toc_title(text)


def _looks_like_visible_toc_entry(text: str) -> bool:
    compact = (text or "").strip()
    if not compact:
        return False
    if _looks_like_toc_entry(compact):
        return True
    return bool(re.search(r"\t\s*\d+\s*$", compact))


def _toc_level_from_style_id(style_id):
    normalized = (style_id or "").strip().lower().replace(" ", "").replace("\u3000", "")
    # WPS / Word 文档里的数字 styleId（如 "3"）是任意分配的，不能直接映射为标题等级，
    # 否则会把 Body Text 之类的正文样式误判成 TOC3，从而把整段正文灌进目录。
    if normalized.isdigit():
        return None
    match = re.fullmatch(r"(?:heading|标题|h)([123])", normalized)
    if match is not None:
        return int(match.group(1))
    return None


def _is_frontmatter_title_text(text: str) -> bool:
    return is_frontmatter_title(text)


def _is_any_keywords_text(text: str) -> bool:
    return is_keywords_text(text)


def _clear_paragraph_property(p_pr, tag_name: str) -> None:
    elem = p_pr.find(f"w:{tag_name}", NSMAP)
    if elem is not None:
        p_pr.remove(elem)


def _normalize_misplaced_keywords_paragraph(p_elem, style_id=None):
    p_pr = ensure_ppr(p_elem)
    p_style = p_pr.find("w:pStyle", NSMAP)
    if style_id:
        if p_style is None:
            p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
        set_attr(p_style, "val", style_id)
    elif p_style is not None:
        p_pr.remove(p_style)

    for tag_name in ("pageBreakBefore", "keepNext", "keepLines", "outlineLvl"):
        _clear_paragraph_property(p_pr, tag_name)


def repair_misplaced_abstract_keywords(document_root, style_map=None):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    paragraphs = [child for child in list(body) if child.tag == f"{{{W_NS}}}p"]
    if not paragraphs:
        return 0

    model = build_document_model(document_root, style_map or {})
    paragraph_sections = model.paragraph_sections
    toc_nodes = [node for node in model.paragraphs if node.container_section == "toc"]
    paragraph_indexes = {id(p_elem): idx for idx, p_elem in enumerate(paragraphs)}
    toc_node_indexes = [paragraph_indexes[id(node.elem)] for node in toc_nodes if id(node.elem) in paragraph_indexes]
    if toc_node_indexes:
        toc_start_idx = min(toc_node_indexes)
        toc_end_idx = max(toc_node_indexes)
    else:
        toc_start_idx, toc_end_idx = find_contiguous_toc_block_range(
            paragraphs,
            is_candidate=lambda _p_elem: True,
            get_text=get_paragraph_text,
            is_tocish=lambda p_elem, text: (
                contains_toc_field_text(text)
                or is_generated_toc_paragraph(p_elem)
                or _is_toc_title_text(text)
                or _looks_like_visible_toc_entry(text)
            ),
        )
        if toc_start_idx is None or toc_end_idx is None:
            return 0

    placeholder_idx = None
    placeholder_style_id = None
    for idx in range(toc_start_idx - 1, -1, -1):
        p_elem = paragraphs[idx]
        if paragraph_sections.get(id(p_elem)) != "abstract_en":
            break
        text = get_paragraph_text(p_elem).strip()
        if text:
            continue
        placeholder_idx = idx
        p_style = p_elem.find("w:pPr/w:pStyle", NSMAP)
        placeholder_style_id = p_style.get(f"{{{W_NS}}}val") if p_style is not None else None
        break

    misplaced_idx = None
    for idx in range(toc_end_idx + 1, len(paragraphs)):
        p_elem = paragraphs[idx]
        text = get_paragraph_text(p_elem).strip()
        if not text:
            continue
        if _is_any_keywords_text(text):
            misplaced_idx = idx
            break
        if classify_paragraph(p_elem, style_map or {}) == "h1" and not _is_frontmatter_title_text(text):
            break

    if misplaced_idx is None:
        return 0

    misplaced_para = paragraphs[misplaced_idx]
    _normalize_misplaced_keywords_paragraph(misplaced_para, style_id=placeholder_style_id)

    if placeholder_idx is not None:
        placeholder_para = paragraphs[placeholder_idx]
        body.remove(placeholder_para)
        insert_idx = placeholder_idx
    else:
        insert_idx = toc_start_idx

    body.remove(misplaced_para)
    body.insert(insert_idx, misplaced_para)
    return 1


def normalize_frontmatter_page_sections(document_root, style_map=None):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    paragraphs = [child for child in list(body) if child.tag == f"{{{W_NS}}}p"]
    if not paragraphs:
        return 0

    document_model = build_document_model(document_root, style_map or {})
    body_nodes = document_model.section_nodes("body", effective=False)
    if not body_nodes:
        return 0

    paragraph_indexes = {id(p_elem): idx for idx, p_elem in enumerate(paragraphs)}
    first_body_idx = paragraph_indexes.get(id(body_nodes[0].elem))
    if first_body_idx is None or first_body_idx <= 0:
        return 0

    final_sect_pr = body.find("w:sectPr", NSMAP)
    if final_sect_pr is None:
        return 0

    changed = 0
    final_pg_num_type = get_or_create(final_sect_pr, "w:pgNumType")
    if final_pg_num_type.get(f"{{{W_NS}}}fmt") != "decimal":
        set_attr(final_pg_num_type, "fmt", "decimal")
        changed += 1
    if final_pg_num_type.get(f"{{{W_NS}}}start") != "1":
        set_attr(final_pg_num_type, "start", "1")
        changed += 1

    target_para = paragraphs[first_body_idx - 1]
    target_p_pr = ensure_ppr(target_para)
    target_sect_pr = target_p_pr.find("w:sectPr", NSMAP)

    candidate_para = None
    candidate_sect_pr = None
    for idx in range(first_body_idx - 1, -1, -1):
        sect_pr = paragraphs[idx].find("w:pPr/w:sectPr", NSMAP)
        if sect_pr is None:
            continue
        candidate_para = paragraphs[idx]
        candidate_sect_pr = sect_pr
        break

    if candidate_sect_pr is None:
        candidate_sect_pr = copy.deepcopy(final_sect_pr)
        candidate_para = None
    elif candidate_para is not target_para:
        source_p_pr = ensure_ppr(candidate_para)
        source_p_pr.remove(candidate_sect_pr)
        changed += 1

    if target_sect_pr is not None:
        target_p_pr.remove(target_sect_pr)
        changed += 1

    if candidate_para is target_para and target_sect_pr is None:
        target_sect_pr = candidate_sect_pr
    else:
        target_p_pr.append(candidate_sect_pr)
        target_sect_pr = candidate_sect_pr
        if candidate_para is not target_para:
            changed += 1

    target_pg_num_type = get_or_create(target_sect_pr, "w:pgNumType")
    if target_pg_num_type.get(f"{{{W_NS}}}fmt") != "upperRoman":
        set_attr(target_pg_num_type, "fmt", "upperRoman")
        changed += 1
    if target_pg_num_type.get(f"{{{W_NS}}}start") != "1":
        set_attr(target_pg_num_type, "start", "1")
        changed += 1

    return changed


def _paragraph_has_manual_page_break(p_elem):
    return any(
        br.get(f"{{{W_NS}}}type") == "page"
        for br in p_elem.findall(".//w:br", NSMAP)
    )


def _is_toc_placeholder_text(text: str | None) -> bool:
    normalized = re.sub(r"\s+", "", str(text or ""))
    return "目录页占位" in normalized or "目录在WPS中自动生成后更新" in normalized


def cleanup_frontmatter_redundant_page_breaks(document_root, style_map=None):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    changed = 0

    while True:
        paragraphs = [child for child in list(body) if child.tag == f"{{{W_NS}}}p"]
        if len(paragraphs) < 2:
            return changed

        document_model = build_document_model(document_root, style_map or {})
        body_nodes = document_model.section_nodes("body", effective=False)
        paragraph_indexes = {id(p_elem): idx for idx, p_elem in enumerate(paragraphs)}
        first_body_idx = paragraph_indexes.get(id(body_nodes[0].elem)) if body_nodes else None
        upper_bound = len(paragraphs) if first_body_idx is None else min(first_body_idx + 1, len(paragraphs))

        local_change = False
        for idx in range(1, upper_bound):
            prev_para = paragraphs[idx - 1]
            curr_para = paragraphs[idx]

            if not _paragraph_has_manual_page_break(prev_para):
                continue
            if get_paragraph_text(prev_para).strip():
                continue

            curr_text = get_paragraph_text(curr_para).strip()
            if not curr_text:
                continue

            curr_p_pr = curr_para.find("w:pPr", NSMAP)
            if curr_p_pr is None or curr_p_pr.find("w:pageBreakBefore", NSMAP) is None:
                continue

            curr_type = classify_paragraph(curr_para, style_map or {})
            is_boundary_heading = (
                _is_frontmatter_title_text(curr_text)
                or is_preface_heading_title(curr_text)
                or match_heading_by_text(curr_text) is not None
                or curr_type == "h1"
            )
            if first_body_idx is not None and idx == first_body_idx:
                is_boundary_heading = True
            if not is_boundary_heading:
                continue

            prev_sect_pr = prev_para.find("w:pPr/w:sectPr", NSMAP)
            if prev_sect_pr is not None:
                _clear_paragraph_property(curr_p_pr, "pageBreakBefore")
            else:
                body.remove(prev_para)
            changed += 1
            local_change = True
            break

        if not local_change:
            return changed


def _strip_trailing_toc_title(paragraph_elem):
    text = get_paragraph_text(paragraph_elem)
    updated = re.sub(r"(?:目[\s\u3000]*录|目录)\s*$", "", text or "")
    updated = updated.rstrip()
    if updated != (text or ""):
        rewrite_paragraph_text_preserve_runs(paragraph_elem, updated)
        return True
    return False


def remove_existing_toc_artifacts(document_root):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    removed = 0
    children = list(body)
    block_indexes: list[int] = []
    block_start_idx, block_end_idx = find_contiguous_toc_block_range(
        children,
        is_candidate=lambda child: child.tag == f"{{{W_NS}}}p",
        get_text=get_paragraph_text,
        is_tocish=lambda child, text: (
            contains_toc_field_text(text)
            or _has_toc_field_instr(child)
            or is_generated_toc_paragraph(child)
            or _is_toc_title_text(text)
            or _looks_like_visible_toc_entry(text)
        ),
    )

    if block_start_idx is not None and block_end_idx is not None:
        prev_idx = block_start_idx - 1
        if prev_idx >= 0 and children[prev_idx].tag == f"{{{W_NS}}}p":
            prev_text = get_paragraph_text(children[prev_idx]).strip()
            if _is_toc_title_text(prev_text):
                block_indexes.append(prev_idx)
            elif prev_text and re.search(r"(?:目[\s\u3000]*录|目录)\s*$", prev_text):
                _strip_trailing_toc_title(children[prev_idx])
        block_indexes.extend(range(block_start_idx, block_end_idx + 1))

    for idx in sorted(set(block_indexes), reverse=True):
        child = children[idx]
        body.remove(child)
        removed += 1

    for child in list(body):
        if child.tag != f"{{{W_NS}}}p":
            continue
        if _is_toc_placeholder_text(get_paragraph_text(child)):
            body.remove(child)
            removed += 1
            continue
        if not is_generated_toc_paragraph(child):
            continue
        body.remove(child)
        removed += 1

    return removed


def _toc_title_for_runtime(cfg, runtime=None) -> str:
    toc_title = str((cfg or {}).get("toc_title", "目录") or "目录")
    if is_lnu_profile(runtime) and toc_title == "目录":
        return "目  录"
    return toc_title


def _add_plain_run(parent, text, *, east_asia="宋体", ascii_font="Times New Roman", size=24, bold=False):
    run_elem = ET.SubElement(parent, f"{{{W_NS}}}r")
    r_pr = ET.SubElement(run_elem, f"{{{W_NS}}}rPr")
    r_fonts = ET.SubElement(r_pr, f"{{{W_NS}}}rFonts")
    set_attr(r_fonts, "eastAsia", east_asia)
    set_attr(r_fonts, "ascii", ascii_font)
    set_attr(r_fonts, "hAnsi", ascii_font)
    sz = ET.SubElement(r_pr, f"{{{W_NS}}}sz")
    set_attr(sz, "val", str(size))
    sz_cs = ET.SubElement(r_pr, f"{{{W_NS}}}szCs")
    set_attr(sz_cs, "val", str(size))
    if bold:
        b_elem = ET.SubElement(r_pr, f"{{{W_NS}}}b")
        set_attr(b_elem, "val", "1")
    text_elem = ET.SubElement(run_elem, f"{{{W_NS}}}t")
    text_elem.text = text
    if str(text or "").startswith(" ") or str(text or "").endswith(" "):
        text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
    return run_elem


def _make_visible_toc_title_para(cfg, runtime=None):
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
    set_attr(spacing, "line", "360")
    set_attr(spacing, "lineRule", "auto")
    _add_plain_run(
        p_elem,
        _toc_title_for_runtime(cfg, runtime=runtime),
        east_asia=str((cfg or {}).get("toc_title_font", "黑体") or "黑体"),
        size=int((cfg or {}).get("toc_title_size", 32) or 32),
        bold=False,
    )
    return p_elem


def _make_visible_toc_entry_para(text, level, cfg):
    active_cfg = cfg or {}
    level = max(1, min(int(level or 1), 3))
    p_elem = ET.Element(f"{{{W_NS}}}p")
    p_pr = ET.SubElement(p_elem, f"{{{W_NS}}}pPr")
    p_style = ET.SubElement(p_pr, f"{{{W_NS}}}pStyle")
    set_attr(p_style, "val", f"TOC{level}")

    tabs = ET.SubElement(p_pr, f"{{{W_NS}}}tabs")
    tab = ET.SubElement(tabs, f"{{{W_NS}}}tab")
    set_attr(tab, "val", "right")
    set_attr(tab, "leader", "dot")
    set_attr(tab, "pos", str(int(active_cfg.get("toc_tab_pos", 9000) or 9000)))

    if level > 1:
        ind = ET.SubElement(p_pr, f"{{{W_NS}}}ind")
        set_attr(ind, "left", str((level - 1) * int(active_cfg.get("toc_indent_step", 420) or 420)))
        set_attr(ind, "firstLine", "0")

    spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
    set_attr(spacing, "before", "0")
    after_pt = float(active_cfg.get(f"toc_level{level}_after_pt", active_cfg.get("toc_level1_after_pt", 5)) or 5)
    set_attr(spacing, "after", str(int(after_pt * 20)))
    set_attr(spacing, "line", str(int(active_cfg.get("toc_entry_line", 276) or 276)))
    set_attr(spacing, "lineRule", "auto")

    if level == 1:
        entry_font = str(active_cfg.get("toc_level1_font", active_cfg.get("toc_entry_font", "宋体")) or "宋体")
        entry_size = int(active_cfg.get("toc_level1_size", active_cfg.get("toc_entry_size", 22)) or 22)
        entry_bold = False
    else:
        entry_font = str(active_cfg.get("toc_entry_font", "宋体") or "宋体")
        entry_size = int(active_cfg.get("toc_entry_size", 22) or 22)
        entry_bold = False
    _add_plain_run(p_elem, text, east_asia=entry_font, size=entry_size, bold=entry_bold)
    return p_elem


def _make_visible_toc_page_break_para():
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


def _collect_visible_toc_headings(document_root, style_map=None, cfg=None):
    max_level = max(1, min(int((cfg or {}).get("toc_max_level", 3) or 3), 3))
    model = build_document_model(document_root, style_map or {})
    headings = []
    for node in model.paragraphs:
        if node.section != "body":
            continue
        text = (node.text or "").strip()
        if not text:
            continue
        level = None
        if node.kind in {"h1", "h2", "h3"}:
            level = int(node.kind[1])
        if level is None:
            level = match_heading_by_text(text)
        if level is None or level > max_level:
            continue
        headings.append((node.elem, text, level))
    return headings


def ensure_visible_toc(document_root, cfg=None, style_map=None, runtime=None):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    model = build_document_model(document_root, style_map or {})
    if any(node.container_section == "toc" for node in model.paragraphs):
        return 0

    headings = _collect_visible_toc_headings(document_root, style_map=style_map, cfg=cfg)
    if not headings:
        return 0

    first_heading_elem = headings[0][0]
    children = list(body)
    try:
        insert_index = children.index(first_heading_elem)
    except ValueError:
        return 0

    new_paragraphs = [_make_visible_toc_title_para(cfg or {}, runtime=runtime)]
    new_paragraphs.extend(_make_visible_toc_entry_para(text, level, cfg or {}) for _, text, level in headings)
    new_paragraphs.append(_make_visible_toc_page_break_para())
    for offset, paragraph in enumerate(new_paragraphs):
        body.insert(insert_index + offset, paragraph)
    return 1


def fix_insert_toc(document_root, cfg=None, style_map=None, runtime=None, repair_keywords=True):
    _configure_thesis_fix_dependencies()
    from thesis_fix.toc import fix_insert_toc as _impl

    return _impl(document_root, cfg, style_map, runtime, repair_keywords)

def _split_keyword_label_boundary(p_elem, label_len):
    if label_len <= 0:
        return

    direct_runs = [child for child in list(p_elem) if child.tag == f"{{{W_NS}}}r"]
    consumed = 0
    for run_elem in direct_runs:
        run_text = get_run_text(run_elem)
        if not run_text:
            continue
        next_consumed = consumed + len(run_text)
        if consumed < label_len < next_consumed and _is_plain_text_run(run_elem):
            split_at = label_len - consumed
            _replace_run_with_tokens(p_elem, run_elem, [run_text[:split_at], run_text[split_at:]])
            return
        consumed = next_consumed


def _set_keyword_content_eastasia(p_elem, label_len, east_asia):
    _split_keyword_label_boundary(p_elem, label_len)
    consumed = 0
    for run_elem in p_elem.findall("w:r", NSMAP):
        run_text = get_run_text(run_elem)
        if not run_text:
            continue
        consumed += len(run_text)
        if consumed <= label_len:
            continue
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", east_asia)


def _rebuild_cn_keyword_runs(p_elem, cfg):
    raw_text = get_paragraph_text(p_elem).strip()
    if not raw_text.startswith("关键词"):
        return False

    kw_font = cfg.get("kw_font", "黑体") or "黑体"
    kw_size = cfg.get("kw_half_points", 24) or 24
    kw_bold = cfg.get("kw_bold", False)
    body_spec = resolve_abstract_body_format(cfg, "abstract_cn")
    suffix = raw_text[len("关键词"):]

    run_specs = [
        {
            "text": "关键词",
            "east_asia": kw_font,
            "ascii_font": body_spec["ascii_font"],
            "size": kw_size,
            "bold": kw_bold,
        }
    ]
    if suffix:
        run_specs.append(
            {
                "text": suffix,
                "east_asia": body_spec["east_asia"],
                "ascii_font": body_spec["ascii_font"],
                "size": kw_size,
                "bold": False,
            }
        )

    rebuild_plain_runs(p_elem, run_specs)
    return True


def _normalize_en_keyword_payload(payload: str, cfg: dict) -> str:
    separator = str(cfg.get("kw_en_separator", "; ") or "; ")
    compact = (payload or "").strip()
    compact = re.sub(r"[。.;；]+\s*$", "", compact)
    keywords = [item.strip() for item in re.split(r"[；;]", compact) if item.strip()]
    if not keywords:
        return compact
    return separator.join(keywords)


def fix_abstract_section(document_root, cfg=None, runtime=None):
    """修复摘要/Abstract标题及关键词行的字体字号格式（辽大专用）"""
    active_cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    if active_cfg.get("ack_font") is None:
        return

    body = document_root.find("w:body", NSMAP)
    if body is None:
        return

    for p_elem in body.findall("w:p", NSMAP):
        raw_text = get_paragraph_text(p_elem).strip()
        if not raw_text:
            continue

        p_pr = ensure_ppr(p_elem)

        if is_abstract_cn_title(raw_text):
            ensure_alignment_and_indent(p_elem, "center")
            title_spec = resolve_abstract_title_format(active_cfg, "abstract_cn")
            abs_title_after_pt = active_cfg.get("abstract_title_after_pt", 0)
            abs_title_after_twips = int(abs_title_after_pt * 20)
            ensure_spacing(p_pr, before=0, after=abs_title_after_twips)
            spacing = get_or_create(p_pr, "w:spacing")
            set_attr(spacing, "line", str(active_cfg.get("abstract_title_line", 360) or 360))
            set_attr(spacing, "lineRule", "auto")
            for run_elem in p_elem.findall(".//w:r", NSMAP):
                r_fonts = ensure_rfonts(run_elem)
                set_attr(r_fonts, "eastAsia", title_spec["font"])
                set_attr(r_fonts, "ascii", title_spec["ascii_font"])
                set_attr(r_fonts, "hAnsi", title_spec["ascii_font"])
                ensure_size(run_elem, str(title_spec["size"]))
                if title_spec["bold"]:
                    ensure_bold(run_elem)
                else:
                    remove_bold(run_elem)
        elif is_abstract_en_title(raw_text):
            title_spec = resolve_abstract_title_format(active_cfg, "abstract_en")
            ensure_alignment_and_indent(p_elem, "center")
            spacing = get_or_create(p_pr, "w:spacing")
            set_attr(spacing, "before", "0")
            set_attr(spacing, "after", str(int(active_cfg.get("abstract_title_after_pt", 0) * 20)))
            set_attr(spacing, "line", str(active_cfg.get("abstract_title_line", 360) or 360))
            set_attr(spacing, "lineRule", "auto")
            for run_elem in p_elem.findall(".//w:r", NSMAP):
                r_fonts = ensure_rfonts(run_elem)
                set_attr(r_fonts, "eastAsia", title_spec["font"])
                set_attr(r_fonts, "ascii", title_spec["ascii_font"])
                set_attr(r_fonts, "hAnsi", title_spec["ascii_font"])
                ensure_size(run_elem, str(title_spec["size"]))
                if title_spec["bold"]:
                    ensure_bold(run_elem)
                else:
                    remove_bold(run_elem)
        elif raw_text.startswith("关键词"):
            _rebuild_cn_keyword_runs(p_elem, active_cfg)
        elif re.match(r"^key(?:\s*words?|words?)\b", raw_text, re.IGNORECASE):
            match = re.match(r"^(key\s*words?\s*[:：])\s*(.*)$", raw_text, re.IGNORECASE)
            p_pr = ensure_ppr(p_elem)
            ensure_alignment_and_indent(p_elem, "center")
            ensure_spacing(p_pr, before=0, after=0)
            spacing = get_or_create(p_pr, "w:spacing")
            set_attr(spacing, "line", "240")
            set_attr(spacing, "lineRule", "auto")
            if match is not None:
                normalized_payload = _normalize_en_keyword_payload(match.group(2), active_cfg)
                rebuild_plain_runs(
                    p_elem,
                    [
                        {
                            "text": match.group(1),
                            "east_asia": "Times New Roman",
                            "ascii_font": "Times New Roman",
                            "size": 28,
                            "bold": True,
                        },
                        {
                            "text": " ",
                            "east_asia": "Times New Roman",
                            "ascii_font": "Times New Roman",
                            "size": 28,
                            "bold": False,
                        },
                        {
                            "text": normalized_payload,
                            "east_asia": "Times New Roman",
                            "ascii_font": "Times New Roman",
                            "size": 24,
                            "bold": False,
                        },
                    ],
                )
            else:
                for run_elem in p_elem.findall(".//w:r", NSMAP):
                    r_fonts = ensure_rfonts(run_elem)
                    set_attr(r_fonts, "eastAsia", "Times New Roman")
                    set_attr(r_fonts, "ascii", "Times New Roman")
                    set_attr(r_fonts, "hAnsi", "Times New Roman")
                    ensure_size(run_elem, "24")


def fix_abstract_heading(p_elem, cfg, section_name):
    """修复摘要区标题格式。"""
    title_spec = resolve_abstract_title_format(cfg, section_name)
    fix_run_font(
        p_elem,
        title_spec["font"],
        title_spec["size"],
        ascii_font=title_spec["ascii_font"],
        bold=title_spec["bold"],
    )
    ensure_alignment_and_indent(p_elem, "center", no_indent=True)
    p_pr = ensure_ppr(p_elem)
    spacing = p_pr.find("w:spacing", NSMAP)
    if spacing is None:
        spacing = ET.SubElement(p_pr, f"{{{W_NS}}}spacing")
    after_pt = cfg.get("abstract_title_after_pt", 0)
    set_attr(spacing, "before", "0")
    set_attr(spacing, "after", str(int(after_pt * 20)))
    set_attr(spacing, "line", str(cfg.get("abstract_title_line", 360) or 360))
    set_attr(spacing, "lineRule", "auto")


def fix_abstract_body(p_elem, cfg, section_name):
    """修复摘要区正文格式。"""
    body_spec = resolve_abstract_body_format(cfg, section_name)
    if section_name == "abstract_cn":
        _rebuild_abstract_cn_body_runs(p_elem, body_spec)
    else:
        fix_run_font(
            p_elem,
            body_spec["east_asia"],
            body_spec["size"],
            ascii_font=body_spec["ascii_font"],
            bold=False,
            italic=False,
        )
    ensure_alignment_and_indent(p_elem, body_spec["alignment"], indent=body_spec["indent"])
    p_pr = ensure_ppr(p_elem)
    spacing = get_or_create(p_pr, "w:spacing")
    set_attr(spacing, "before", "0")
    set_attr(spacing, "after", "0")
    set_attr(spacing, "line", str(body_spec["line"]))
    set_attr(spacing, "lineRule", "auto")


def fix_caption_paragraph(p_elem, cfg=None, runtime=None):
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    ensure_alignment_and_indent(p_elem, "center")
    p_pr = ensure_ppr(p_elem)
    for elem in list(p_pr.findall("w:numPr", NSMAP)):
        p_pr.remove(elem)
    ensure_spacing(p_pr, before=0, after=0)
    spacing = get_or_create(p_pr, "w:spacing")
    set_attr(spacing, "line", str(cfg.get("figure_caption_line", 240)))
    set_attr(spacing, "lineRule", "auto")
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        ensure_size(run_elem, str(cfg.get("caption_size", 21)))
        remove_bold(run_elem)
        _remove_run_props(run_elem, ("bCs",))
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", "宋体")
        set_attr(r_fonts, "ascii", "Times New Roman")
        set_attr(r_fonts, "hAnsi", "Times New Roman")


def _normalize_subfigure_letter_references(text: str) -> str:
    def replace_cn(match):
        return f"{match.group(1)}({match.group(2)})"

    def replace_en(match):
        return f"{match.group(1)}({match.group(2)})"

    normalized = re.sub(r"((?:图|表)\s*\d+(?:[.\-]\d+)+)\s*([A-Z])\b", replace_cn, text or "")
    normalized = re.sub(r"((?:Fig\.?|Figure|Table)\s*\d+(?:[.\-]\d+)+)\s*([A-Z])\b", replace_en, normalized, flags=re.IGNORECASE)
    return normalized


def _normalize_note_prefix(text: str) -> str:
    return re.sub(r"^\s*注[\s\u3000]*[:：][\s\u3000]*", "注：", text or "", count=1)


def _fix_caption_like_runs(p_elem, cfg):
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        ensure_size(run_elem, str(cfg.get("caption_size", 21)))
        remove_bold(run_elem)
        _remove_run_props(run_elem, ("bCs",))
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", "宋体")
        set_attr(r_fonts, "ascii", "Times New Roman")
        set_attr(r_fonts, "hAnsi", "Times New Roman")


def fix_english_caption_paragraph(p_elem, cfg=None, runtime=None):
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    ensure_alignment_and_indent(p_elem, "center")
    p_pr = ensure_ppr(p_elem)
    for elem in list(p_pr.findall("w:numPr", NSMAP)):
        p_pr.remove(elem)
    ensure_spacing(p_pr, before=0, after=0)
    spacing = get_or_create(p_pr, "w:spacing")
    set_attr(spacing, "line", str(cfg.get("figure_note_line", 240)))
    set_attr(spacing, "lineRule", "auto")
    _fix_caption_like_runs(p_elem, cfg)
    original_text = get_paragraph_text(p_elem).strip()
    normalized_text = _normalize_subfigure_letter_references(original_text)
    if normalized_text != original_text:
        rewrite_paragraph_text_preserve_runs(p_elem, normalized_text)


def fix_caption_note_paragraph(p_elem, cfg=None, runtime=None):
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    ensure_alignment_and_indent(p_elem, "center", no_indent=True)
    p_pr = ensure_ppr(p_elem)
    for elem in list(p_pr.findall("w:numPr", NSMAP)):
        p_pr.remove(elem)
    ensure_spacing(p_pr, before=0, after=0)
    spacing = get_or_create(p_pr, "w:spacing")
    set_attr(spacing, "line", str(cfg.get("figure_note_line", 240)))
    set_attr(spacing, "lineRule", "auto")
    _fix_caption_like_runs(p_elem, cfg)
    original_text = get_paragraph_text(p_elem).strip()
    normalized_text = _normalize_subfigure_letter_references(_normalize_note_prefix(original_text))
    if normalized_text != original_text:
        rewrite_paragraph_text_preserve_runs(p_elem, normalized_text)


def fix_equation_paragraph(p_elem, runtime=None):
    """将含公式（m:oMath）的段落设为居中、首行缩进0。"""
    ensure_alignment_and_indent(p_elem, "center")
    if not is_lnu_profile(runtime):
        return

    math_run_ids = set()
    for math_elem in p_elem.findall(".//m:oMath", MNSMAP):
        for run_elem in math_elem.findall(".//w:r", NSMAP):
            math_run_ids.add(id(run_elem))

    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if id(run_elem) in math_run_ids:
            continue
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", "宋体")
        set_attr(r_fonts, "ascii", "Times New Roman")
        set_attr(r_fonts, "hAnsi", "Times New Roman")
        ensure_size(run_elem, "24")


def _equation_number_patterns(cfg):
    sep = re.escape((cfg or {}).get("eq_number_sep", "-"))
    strict = re.compile(rf"^[（(]\s*(\d+){sep}(\d+)\s*[)）]$")
    inline = re.compile(rf"[（(]\s*(\d+){sep}(\d+)\s*[)）]")
    return strict, inline


def _compact_paragraph_text(p_elem):
    return re.sub(r"\s+", "", get_paragraph_text(p_elem) or "")


def _right_align_equation_number_paragraph(p_elem) -> int:
    before = ET.tostring(p_elem, encoding="unicode")
    ensure_alignment_and_indent(p_elem, "right")
    return 1 if ET.tostring(p_elem, encoding="unicode") != before else 0


def _right_align_equation_layout_table_number(tbl_elem) -> int:
    cells = tbl_elem.findall("w:tr/w:tc", NSMAP)
    if not cells:
        return 0
    changed = 0
    for p_elem in cells[-1].findall("w:p", NSMAP):
        if _compact_paragraph_text(p_elem):
            changed += _right_align_equation_number_paragraph(p_elem)
    return 1 if changed else 0


def fix_equation_number_alignment(document_root, cfg=None) -> int:
    """EQ02: align existing equation number paragraphs to the right without moving formulas."""
    strict_num_re, inline_num_re = _equation_number_patterns(cfg)
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    changed = 0
    table_paragraph_ids = set()
    for tbl_elem in document_root.findall(".//w:tbl", NSMAP):
        if not audit_thesis.is_equation_layout_table(tbl_elem):
            continue
        for p_elem in tbl_elem.findall(".//w:p", NSMAP):
            table_paragraph_ids.add(id(p_elem))
        changed += _right_align_equation_layout_table_number(tbl_elem)

    paragraphs = body.findall(".//w:p", NSMAP)
    for index, p_elem in enumerate(paragraphs):
        if id(p_elem) in table_paragraph_ids:
            continue
        if not paragraph_has_math(p_elem):
            continue

        text = _compact_paragraph_text(p_elem)
        if inline_num_re.search(text):
            changed += _right_align_equation_number_paragraph(p_elem)
            continue

        if index + 1 >= len(paragraphs):
            continue
        next_p = paragraphs[index + 1]
        if id(next_p) in table_paragraph_ids:
            continue
        next_text = _compact_paragraph_text(next_p)
        if strict_num_re.fullmatch(next_text):
            changed += _right_align_equation_number_paragraph(next_p)
    return changed


def fix_equation_reference_text(p_elem, cfg=None) -> int:
    """EQ03: conservatively normalize same-run formula references such as 式2.1."""
    sep = (cfg or {}).get("eq_number_sep", "-")
    if sep not in {".", "-"}:
        sep = "-"
    changed = 0
    pattern = re.compile(r"(式|公式)(?![（(])(\d+)[.-](\d+)")
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        original = text_elem.text
        if not original:
            continue

        def _replace(match):
            left, first, second = match.groups()
            return f"{left}({first}{sep}{second})"

        updated = pattern.sub(_replace, original)
        if updated != original:
            text_elem.text = updated
            changed += 1
    return changed


def is_display_equation_paragraph(p_elem):
    """仅将纯公式段判定为公式段，避免把含行内公式的正文整段居中。"""
    if not paragraph_has_math(p_elem):
        return False
    compact_text = re.sub(r"\s+", "", get_paragraph_text(p_elem) or "")
    if not compact_text:
        return True
    if re.fullmatch(r"[（(]?\d+(?:[.\-]\d+)*[)）]?", compact_text):
        return True
    return False


def fix_figure_paragraph(p_elem):
    """将含图片（w:drawing）的段落设为居中、首行缩进0。"""
    ensure_alignment_and_indent(p_elem, "center")


def normalize_lnu_figure_block_layout(document_root, style_map=None, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import normalize_lnu_figure_block_layout as _impl

    return _impl(document_root, style_map, cfg, runtime)

def normalize_lnu_table_block_layout(document_root, style_map=None, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import normalize_lnu_table_block_layout as _impl

    return _impl(document_root, style_map, cfg, runtime)

def protect_object_blocks_from_pagination(document_root, style_map=None, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import protect_object_blocks_from_pagination as _impl

    return _impl(document_root, style_map, cfg, runtime)

def rebalance_lnu_result_object_flow(document_root, style_map=None, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.tables_figures import rebalance_lnu_result_object_flow as _impl

    return _impl(document_root, style_map, cfg, runtime)

def fix_heading4(p_elem, cfg=None, heading_style_ids=None, runtime=None):
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    active_heading_style_ids = resolve_fix_heading_style_ids(
        heading_style_ids=heading_style_ids,
        runtime=runtime,
    )
    p_pr = ensure_ppr(p_elem)
    p_style, created = ensure_pstyle_first(p_pr)
    set_attr(p_style, "val", active_heading_style_ids.get("h4", "Heading4"))
    ppr_rpr = p_pr.find("w:rPr", NSMAP)
    if ppr_rpr is not None:
        for bold_tag in ppr_rpr.findall("w:b", NSMAP) + ppr_rpr.findall("w:bCs", NSMAP):
            ppr_rpr.remove(bold_tag)

    h4_indent = cfg.get("h4_indent")
    if h4_indent is None:
        h4_indent = 0
    ensure_alignment_and_indent(p_elem, "left", indent=h4_indent)
    normalize_heading_paragraph_layout(p_pr, first_line=h4_indent)
    h_font = cfg.get("h4_font") or "宋体"
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if not get_run_text(run_elem).strip():
            continue
        set_run_font(run_elem, h_font, ascii_font="Times New Roman", size=cfg.get("h4_size", 24), bold=False)


def _scale_drawing_extents(p_elem, max_cx=COVER_IMAGE_MAX_CX, max_cy=COVER_IMAGE_MAX_CY):
    changed = False
    for drawing in p_elem.findall(".//w:drawing", NSMAP):
        extent = drawing.find(".//wp:extent", NAMESPACES)
        if extent is None:
            continue
        try:
            cx = int(extent.get("cx", "0"))
            cy = int(extent.get("cy", "0"))
        except ValueError:
            continue
        if cx <= 0 or cy <= 0:
            continue
        scale = min(max_cx / cx, max_cy / cy, 1.0)
        if scale >= 1.0:
            continue
        new_cx = str(max(1, int(cx * scale)))
        new_cy = str(max(1, int(cy * scale)))
        extent.set("cx", new_cx)
        extent.set("cy", new_cy)
        for xfrm_ext in drawing.findall(".//a:xfrm/a:ext", NAMESPACES):
            xfrm_ext.set("cx", new_cx)
            xfrm_ext.set("cy", new_cy)
        changed = True
    return changed


def fix_cover_layout(document_root, paragraph_sections, runtime=None):
    """默认保留现有封面，不自动修改封面文字或布局。"""
    return


def remove_paragraphs_from_body(document_root, paragraphs):
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return
    targets = {id(p) for p in paragraphs}
    for child in list(body):
        child_paragraph_ids = {
            id(p_elem)
            for p_elem in child.findall(".//w:p", NSMAP)
        }
        if child.tag == f"{{{W_NS}}}p":
            child_paragraph_ids.add(id(child))
        if child_paragraph_ids & targets:
            body.remove(child)


def _extract_heading_title(paragraph_text, paragraph_type):
    patterns = {
        "h1": re.compile(r"^\s*(?:(?:\d+(?:\.\d+)*)\s+)?(.+?)\s*$"),
        "h2": re.compile(r"^\s*\d+\.\d+\s+(.+?)\s*$"),
        "h3": re.compile(r"^\s*\d+\.\d+\.\d+\s+(.+?)\s*$"),
        "h4": re.compile(r"^\s*\d+\.\d+\.\d+\.\d+\s+(.+?)\s*$"),
    }
    match = patterns[paragraph_type].match(paragraph_text or "")
    if match is None:
        return None
    title = match.group(1).strip()
    return title or None


def renumber_body_headings(body_paragraphs, style_map, table_para_ids=None):
    chapter = 0
    level2 = 0
    level3 = 0
    level4 = 0
    table_para_ids = table_para_ids or set()

    for p_elem in body_paragraphs:
        if id(p_elem) in table_para_ids:
            continue
        paragraph_type = classify_paragraph(p_elem, style_map)
        paragraph_text = get_paragraph_text(p_elem).strip()
        if paragraph_type not in {"h1", "h2", "h3", "h4"}:
            continue
        title = _extract_heading_title(paragraph_text, paragraph_type)
        if title is None:
            continue
        if paragraph_type == "h1":
            chapter += 1
            level2 = 0
            level3 = 0
            level4 = 0
            new_text = title if re.match(r"^第\s*\d+\s*章", title) else f"{chapter} {title}"
        elif paragraph_type == "h2":
            if chapter <= 0:
                continue
            level2 += 1
            level3 = 0
            level4 = 0
            new_text = f"{chapter}.{level2} {title}"
        elif paragraph_type == "h3":
            if chapter <= 0:
                continue
            if level2 <= 0:
                level2 = 1
            level3 += 1
            level4 = 0
            new_text = f"{chapter}.{level2}.{level3} {title}"
        else:
            if chapter <= 0:
                continue
            if level2 <= 0:
                level2 = 1
            if level3 <= 0:
                level3 = 1
            level4 += 1
            new_text = f"{chapter}.{level2}.{level3}.{level4} {title}"
        if new_text != paragraph_text:
            rewrite_paragraph_text_preserve_runs(p_elem, new_text)


def normalize_lnu_preface_heading_numbering(body_paragraphs, style_map, table_para_ids=None):
    table_para_ids = table_para_ids or set()
    first_h1_index = None
    first_h1_title = None

    for idx, p_elem in enumerate(body_paragraphs):
        if id(p_elem) in table_para_ids:
            continue
        if classify_paragraph(p_elem, style_map) != "h1":
            continue
        raw_text = get_paragraph_text(p_elem).strip()
        if not raw_text:
            continue
        first_h1_index = idx
        first_h1_title = "序言" if is_preface_heading_title(raw_text) else None
        break

    if first_h1_index is None or first_h1_title != "序言":
        return 0

    chapter = 0
    level2 = 0
    level3 = 0
    level4 = 0
    changed = 0
    preface_active = False

    for p_elem in body_paragraphs:
        if id(p_elem) in table_para_ids:
            continue
        paragraph_type = classify_paragraph(p_elem, style_map)
        paragraph_text = get_paragraph_text(p_elem).strip()
        if paragraph_type not in {"h1", "h2", "h3", "h4"} or not paragraph_text:
            continue
        title = _extract_heading_title(paragraph_text, paragraph_type) or paragraph_text
        if not title:
            continue

        if paragraph_type == "h1":
            if is_preface_heading_title(title) and chapter == 0:
                preface_active = True
                level2 = 0
                level3 = 0
                level4 = 0
                new_text = "序  言"
            else:
                preface_active = False
                chapter += 1
                level2 = 0
                level3 = 0
                level4 = 0
                new_text = title if re.match(r"^第\s*\d+\s*章", title) else f"第{chapter}章 {title}"
        elif paragraph_type == "h2":
            level2 += 1
            level3 = 0
            level4 = 0
            new_text = f"{0 if preface_active else chapter}.{level2} {title}"
        elif paragraph_type == "h3":
            if level2 <= 0:
                level2 = 1
            level3 += 1
            level4 = 0
            new_text = f"{0 if preface_active else chapter}.{level2}.{level3} {title}"
        else:
            if level2 <= 0:
                level2 = 1
            if level3 <= 0:
                level3 = 1
            level4 += 1
            new_text = f"{0 if preface_active else chapter}.{level2}.{level3}.{level4} {title}"

        if new_text != paragraph_text:
            rewrite_paragraph_text_preserve_runs(p_elem, new_text)
            changed += 1

    return changed


def trim_caption_terminal_punctuation(p_elem):
    paragraph_text = get_paragraph_text(p_elem).rstrip()
    if not paragraph_text.startswith(("图", "表")) or not paragraph_text.endswith(("。", ".")):
        return

    runs = [run_elem for run_elem in p_elem.findall(".//w:r", NSMAP) if get_run_text(run_elem).strip()]
    for run_elem in reversed(runs):
        text_elems = [t_elem for t_elem in run_elem.findall(".//w:t", NSMAP) if t_elem.text]
        if not text_elems:
            continue
        text_elems[-1].text = re.sub(r"[。.]\s*$", "", text_elems[-1].text)
        return


def fix_caption_number_sep(p_elem, cfg=None):
    """将图/表题中的横线编号替换为点号，如 图2-1 → 图2.1（辽大专用）"""
    if cfg is None:
        return
    gap_spaces = int(cfg.get("caption_label_gap_spaces", 1) or 1)
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        if not text_elem.text:
            continue
        updated = text_elem.text
        if cfg.get("caption_number_sep") == ".":
            updated = re.sub(r"(图|表)(\d+)-(\d+)", r"\1\2.\3", updated)
        updated = re.sub(r"^(图|表)\s*(\d+\.\d+)\s*(.+)$", lambda m: f"{m.group(1)}{m.group(2)}{' ' * gap_spaces}{m.group(3).lstrip()}", updated, count=1)
        if updated != text_elem.text:
            text_elem.text = updated


def fix_table_borders(tbl_elem):
    tbl_pr = get_or_create(tbl_elem, "w:tblPr")
    tbl_borders = get_or_create(tbl_pr, "w:tblBorders")
    for border_name in ("top", "bottom"):
        border = get_or_create(tbl_borders, f"w:{border_name}")
        set_attr(border, "val", "single")
        set_attr(border, "sz", "18")
        set_attr(border, "color", "000000")
    for border_name in ("left", "right"):
        border = get_or_create(tbl_borders, f"w:{border_name}")
        set_attr(border, "val", "none")
        set_attr(border, "sz", "0")

    inside_v = tbl_borders.find("w:insideV", NSMAP)
    if inside_v is None:
        inside_v = ET.SubElement(tbl_borders, f"{{{W_NS}}}insideV")
    inside_v.set(f"{{{W_NS}}}val", "none")
    inside_v.set(f"{{{W_NS}}}sz", "0")
    inside_v.set(f"{{{W_NS}}}space", "0")
    inside_v.set(f"{{{W_NS}}}color", "auto")

    inside_h = tbl_borders.find("w:insideH", NSMAP)
    if inside_h is None:
        inside_h = ET.SubElement(tbl_borders, f"{{{W_NS}}}insideH")
    inside_h.set(f"{{{W_NS}}}val", "single")
    inside_h.set(f"{{{W_NS}}}sz", "6")
    inside_h.set(f"{{{W_NS}}}color", "auto")

    first_row = tbl_elem.find(".//w:tr", NSMAP)
    if first_row is None:
        return

    for tc_elem in first_row.findall("w:tc", NSMAP):
        tc_pr = get_or_create(tc_elem, "w:tcPr")
        tc_borders = get_or_create(tc_pr, "w:tcBorders")
        bottom = get_or_create(tc_borders, "w:bottom")
        set_attr(bottom, "val", "single")
        set_attr(bottom, "sz", "6")
        set_attr(bottom, "color", "000000")


def fix_equation_layout_table_borders(tbl_elem):
    """清除公式布局表边框，避免 WPS 渲染出错误横线。"""
    tbl_pr = get_or_create(tbl_elem, "w:tblPr")
    tbl_borders = get_or_create(tbl_pr, "w:tblBorders")
    for border_name in ("top", "bottom", "left", "right", "insideH", "insideV"):
        border = get_or_create(tbl_borders, f"w:{border_name}")
        set_attr(border, "val", "nil")
        set_attr(border, "sz", "0")
        set_attr(border, "color", "auto")

    for tc_pr in tbl_elem.findall(".//w:tcPr", NSMAP):
        tc_borders = tc_pr.find("w:tcBorders", NSMAP)
        if tc_borders is None:
            continue
        for border_name in ("top", "bottom", "left", "right", "insideH", "insideV"):
            border = tc_borders.find(f"w:{border_name}", NSMAP)
            if border is None:
                continue
            set_attr(border, "val", "nil")
            set_attr(border, "sz", "0")
            set_attr(border, "color", "auto")


def fix_table_cell_font(tbl_elem, cfg=None):
    """修复表格单元格内文字字体字号（辽大：宋体五号）"""
    if cfg is None:
        cfg = {}

    table_font = cfg.get("table_cell_font", "宋体") or "宋体"
    table_size = cfg.get("table_cell_size", 21) or 21
    for tc_elem in tbl_elem.findall(".//w:tc", NSMAP):
        for p_elem in tc_elem.findall(".//w:p", NSMAP):
            for run_elem in p_elem.findall("w:r", NSMAP):
                r_fonts = ensure_rfonts(run_elem)
                set_attr(r_fonts, "eastAsia", table_font)
                set_attr(r_fonts, "ascii", "Times New Roman")
                set_attr(r_fonts, "hAnsi", "Times New Roman")
                ensure_size(run_elem, str(table_size))


def fix_ellipsis(document_root, style_map=None, allowed_ids=None, protected_ids=None):
    """PU02: 将 ...... / ... 替换为 …… / …，但跳过参考文献段落。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return
    for p_elem in body.findall("w:p", NSMAP):
        if allowed_ids is not None and id(p_elem) not in allowed_ids:
            continue
        if protected_ids is not None and id(p_elem) in protected_ids:
            continue
        if style_map is not None and classify_paragraph(p_elem, style_map) == "reference":
            continue
        for t_elem in p_elem.findall(".//w:t", NSMAP):
            if t_elem.text and re.search(r"\.{3,}", t_elem.text):
                t_elem.text = re.sub(r"\.{6,}", "……", t_elem.text)
                t_elem.text = re.sub(r"\.{3}", "…", t_elem.text)


def fix_half_width_punct_in_cjk(document_root, style_map=None, allowed_ids=None, protected_ids=None):
    """PU01/LNU_ABS04: 将中文语境下的英文半角标点替换为全角标点，但跳过参考文献和题注段落。"""
    for p_elem in document_root.findall(".//w:p", NSMAP):
        if allowed_ids is not None and id(p_elem) not in allowed_ids:
            continue
        if protected_ids is not None and id(p_elem) in protected_ids:
            continue
        if style_map is not None and classify_paragraph(p_elem, style_map) in {"reference", "caption"}:
            continue
        for t_elem in p_elem.findall(".//w:t", NSMAP):
            if t_elem.text and _HALF_WIDTH_PUNCT_PATTERN.search(t_elem.text):
                t_elem.text = _HALF_WIDTH_PUNCT_PATTERN.sub(
                    lambda match: _HALF_WIDTH_PUNCT_MAPPING[match.group(0)],
                    t_elem.text,
                )


def fix_reference_paragraph(p_elem, cfg=None, runtime=None):
    """修复参考文献段落：悬挂缩进 + 辽大/通用两套编号分隔逻辑。"""
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    p_pr = ensure_ppr(p_elem)
    normalize_reference_number_leading_zeros(p_elem)

    hanging_val = str(cfg.get("ref_hanging", 420))
    ind = get_or_create(p_pr, "w:ind")
    set_attr(ind, "hanging", hanging_val)
    set_attr(ind, "left", hanging_val)
    if f"{{{W_NS}}}firstLine" in ind.attrib:
        del ind.attrib[f"{{{W_NS}}}firstLine"]

    spacing = get_or_create(p_pr, "w:spacing")
    ref_line = str(cfg.get("ref_line_spacing", 240))
    set_attr(spacing, "before", "0")
    set_attr(spacing, "after", "0")
    set_attr(spacing, "line", ref_line)
    set_attr(spacing, "lineRule", "auto")
    ref_size = str(cfg.get("ref_font_size", 24))
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        _remove_run_props(run_elem, ("vertAlign",))
        ensure_size(run_elem, ref_size)
    jc = get_or_create(p_pr, "w:jc")
    set_attr(jc, "val", "both")
    suppress_auto_hyphens = get_or_create(p_pr, "w:suppressAutoHyphens")
    set_attr(suppress_auto_hyphens, "val", "1")

    if cfg.get("ref_use_tab", True):
        tabs = insert_tabs_before_spacing(p_pr)
        target_pos = str(max(cfg.get("ref_tab_min", 420), cfg.get("ref_hanging", 420)))
        left_tab = None
        for tab in tabs.findall("w:tab", NSMAP):
            if tab.get(f"{{{W_NS}}}val") == "left":
                left_tab = tab
                break
        if left_tab is None:
            left_tab = ET.SubElement(tabs, f"{{{W_NS}}}tab")
        set_attr(left_tab, "val", "left")
        set_attr(left_tab, "pos", target_pos)
        _inject_tab_after_ref_number(p_elem)
    else:
        _remove_tab_after_ref_number(p_elem)
        if cfg.get("ref_number_trailing_space", True):
            ensure_reference_number_spacing(p_elem)
        else:
            for run_elem in p_elem.findall(".//w:r", NSMAP):
                text_elem = run_elem.find("w:t", NSMAP)
                if text_elem is None or text_elem.text is None:
                    continue
                updated = re.sub(r"^(\[\d+\])\s+", r"\1", text_elem.text, count=1)
                if updated != text_elem.text:
                    text_elem.text = updated
                    text_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                break


def fix_ack_paragraph(p_elem, cfg):
    ack_font = (cfg or {}).get("ack_font", "仿宋") or "仿宋"
    ack_size = (cfg or {}).get("ack_size", 24) or 24
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if not get_run_text(run_elem).strip():
            continue
        set_run_font(run_elem, ack_font, ascii_font="Times New Roman", size=ack_size, bold=False)


def fix_acknowledgement_font(p_elem, cfg):
    ack_font = cfg.get("ack_font")
    if not ack_font:
        return
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if not get_run_text(run_elem).strip():
            continue
        r_fonts = ensure_rfonts(run_elem)
        set_attr(r_fonts, "eastAsia", ack_font)


def fix_ref_punctuation(p_elem):
    """LNU_REF01: 将参考文献段落中的全角标点替换为英文半角。"""
    punct_map = {
        "。": ".",
        "，": ",",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
    }
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        if not text_elem.text:
            continue
        updated = text_elem.text
        for full_width, half_width in punct_map.items():
            updated = updated.replace(full_width, half_width)
        if updated != text_elem.text:
            text_elem.text = updated


def fix_ref_numbering_space(p_elem):
    """Legacy helper: 将参考文献编号后的 Tab 替换为一个半角空格。"""
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        text_elem = run_elem.find("w:t", NSMAP)
        if text_elem is None or text_elem.text is None:
            continue
        updated = re.sub(r"^(\[\d+\])\t", r"\1 ", text_elem.text)
        if updated != text_elem.text:
            text_elem.text = updated
            text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
        break


def fix_lnu_conc01(document_root, cfg):
    """LNU_CONC01: 末章命名需人工判断，不自动修复"""
    return 0


def fix_lnu_title01(document_root, cfg, allowed_titles=None):
    """LNU_TITLE01: 将摘要/目录/序言/致谢单字标题改为双格式"""
    fixed = 0
    local_nsmap = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for p in document_root.findall(".//w:p", local_nsmap):
        runs = p.findall(".//w:r", local_nsmap)
        if not runs:
            continue
        texts = []
        for r in runs:
            t = r.find("w:t", local_nsmap)
            texts.append(t.text if t is not None and t.text else "")
        full_text = "".join(texts).strip()
        if not matches_allowed_titles(full_text, allowed_titles):
            continue
        spaced_title = resolve_lnu_double_spaced_title(full_text)
        if spaced_title is not None and len(runs) == 1:
            t_elem = runs[0].find("w:t", local_nsmap)
            if t_elem is not None:
                t_elem.text = spaced_title
                fixed += 1
    return fixed


def fix_lnu_tb03(document_root, cfg):
    """LNU_TB03: 修复表格内容为单倍行距"""
    fixed = 0
    local_nsmap = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    expected_line = str((cfg or {}).get("table_cell_line") or 240)
    for tbl in document_root.findall(".//w:tbl", local_nsmap):
        if audit_thesis.is_equation_layout_table(tbl):
            continue
        for cell in tbl.findall(".//w:tc", local_nsmap):
            for p in cell.findall(".//w:p", local_nsmap):
                p_pr = ensure_ppr(p)
                spacing = get_or_create(p_pr, "w:spacing")
                current_line = spacing.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}line")
                current_rule = spacing.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lineRule")
                if current_line != expected_line or current_rule != "auto":
                    spacing.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}line", expected_line)
                    spacing.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lineRule", "auto")
                    fixed += 1
    return fixed


def fix_tb03_repeat_header(document_root):
    """TB03: 为较长表格首行补齐 repeat header 标记。"""
    fixed = 0
    for tbl in document_root.findall(".//w:tbl", NSMAP):
        rows = tbl.findall("w:tr", NSMAP)
        if len(rows) < 6:
            continue
        first_row = rows[0]
        tr_pr = get_or_create(first_row, "w:trPr")
        if tr_pr.find("w:tblHeader", NSMAP) is not None:
            continue
        ET.SubElement(tr_pr, f"{{{W_NS}}}tblHeader")
        fixed += 1
    return fixed


def clear_direct_run_format(p_elem, clear_font=False, clear_size=False, clear_bold=False):
    """清除run级直接格式覆盖，让段落样式生效"""
    for run in p_elem.findall(".//w:r", NSMAP):
        rpr = run.find("w:rPr", NSMAP)
        if rpr is None:
            continue
        if clear_font:
            for tag in ("w:rFonts",):
                el = rpr.find(tag, NSMAP)
                if el is not None:
                    rpr.remove(el)
        if clear_size:
            for tag in ("w:sz", "w:szCs"):
                el = rpr.find(tag, NSMAP)
                if el is not None:
                    rpr.remove(el)
        if clear_bold:
            for tag in ("w:b", "w:bCs"):
                el = rpr.find(tag, NSMAP)
                if el is not None:
                    rpr.remove(el)


def ensure_first_line_indent(p_pr, twips):
    """设置段落首行缩进（twips单位）"""
    import xml.etree.ElementTree as ET

    ind = p_pr.find("w:ind", NSMAP)
    if ind is None:
        ind = ET.SubElement(p_pr, f"{{{W_NS}}}ind")
    set_attr(ind, "firstLine", str(twips))


def fix_lnu_abs01(document_root, cfg):
    """LNU_ABS01: 修复中文摘要标题——黑体三号(32)，居中，段后按 profile 配置。"""
    fixed = 0
    title_spec = resolve_abstract_title_format(cfg, "abstract_cn")
    after_twips = int(cfg.get("abstract_title_after_pt", 0) * 20)
    for p in document_root.findall(".//w:p", NSMAP):
        text = get_paragraph_text(p).strip()
        if not is_abstract_cn_title(text):
            continue
        p_pr = ensure_ppr(p)
        ensure_spacing(p_pr, before=0, after=after_twips)
        ensure_alignment_and_indent(p, "center", no_indent=True)
        for run in p.findall(".//w:r", NSMAP):
            if not get_run_text(run).strip():
                continue
            set_run_font(
                run,
                title_spec["font"],
                ascii_font=title_spec["ascii_font"],
                size=title_spec["size"],
                bold=title_spec["bold"],
            )
        fixed += 1
    return fixed


def fix_lnu_abs02(document_root, cfg):
    """LNU_ABS02: 修复 Abstract 标题——Times New Roman 三号，加粗，段后按 profile 配置。"""
    fixed = 0
    for p in document_root.findall(".//w:p", NSMAP):
        text = get_paragraph_text(p).strip()
        if not is_abstract_en_title(text):
            continue
        fix_abstract_heading(p, cfg, "abstract_en")
        fixed += 1
    return fixed


def fix_lnu_abs03(document_root, cfg):
    """LNU_ABS03: 修复英文摘要正文——Times New Roman 12pt，行距按 profile 配置。"""
    fixed = 0
    body_spec = resolve_abstract_body_format(cfg, "abstract_en")
    document_model = build_document_model(document_root, {})
    for node in document_model.section_nodes("abstract_en"):
        if node.module != "abstract_en_body":
            continue
        text = node.text.strip()
        if not text:
            continue
        p = node.elem
        p_pr = ensure_ppr(p)
        ensure_spacing(p_pr, before=0, after=0)
        spacing_elem = get_or_create(p_pr, "w:spacing")
        set_attr(spacing_elem, "line", str(body_spec["line"]))
        set_attr(spacing_elem, "lineRule", "auto")
        ind = get_or_create(p_pr, "w:ind")
        set_attr(ind, "firstLine", str(body_spec["indent"]))
        for run in p.findall(".//w:r", NSMAP):
            if get_run_text(run) == "":
                continue
            set_run_font(
                run,
                body_spec["east_asia"],
                ascii_font=body_spec["ascii_font"],
                size=body_spec["size"],
                bold=False,
            )
        fixed += 1
    return fixed


def fix_lnu_s03(document_root, cfg, allowed_titles=None):
    """LNU_S03: 在参考文献/附录/致谢段落前插入分页符(pageBreakBefore)"""
    import xml.etree.ElementTree as ET

    fixed = 0
    for p in document_root.findall(".//w:p", NSMAP):
        text = get_paragraph_text(p).strip()
        if not is_backmatter_pagebreak_title(text):
            continue
        if not matches_allowed_titles(text, allowed_titles):
            continue
        p_pr = ensure_ppr(p)
        pb = p_pr.find("w:pageBreakBefore", NSMAP)
        if pb is None:
            pb = ET.SubElement(p_pr, f"{{{W_NS}}}pageBreakBefore")
        set_attr(pb, "val", "true")
        fixed += 1
    return fixed


def fix_lnu_ack01(document_root, cfg):
    """LNU_ACK01: 修复致谢正文——宋体小四(24)，1.5倍行距，首行缩进2字符"""
    fixed = 0
    body = document_root.find("w:body", NSMAP)
    if body is not None and bool(cfg.get("acknowledgement_required")):
        has_ack_title = any(
            elem.tag == f"{{{W_NS}}}p" and is_acknowledgement_title(get_paragraph_text(elem).strip())
            for elem in list(body)
        )
        if not has_ack_title:
            heading = ET.Element(f"{{{W_NS}}}p")
            fix_heading_paragraph(heading, "center", False, cfg=cfg)
            fix_heading_page_break(heading)
            fix_heading_spacing(heading, "h1", cfg=cfg)
            title_text = resolve_lnu_double_spaced_title("致谢") or "致  谢"
            title_run = ET.SubElement(heading, f"{{{W_NS}}}r")
            title_text_elem = ET.SubElement(title_run, f"{{{W_NS}}}t")
            title_text_elem.text = title_text
            set_run_font(title_run, cfg.get("h1_font", cfg.get("h_font", "黑体")) or "黑体", ascii_font="Times New Roman", size=cfg.get("h1_size", 30), bold=False)

            body_para = ET.Element(f"{{{W_NS}}}p")
            body_ppr = ensure_ppr(body_para)
            ensure_spacing(body_ppr, before=0, after=0)
            spacing = get_or_create(body_ppr, "w:spacing")
            set_attr(spacing, "line", "360")
            set_attr(spacing, "lineRule", "auto")
            ensure_first_line_indent(body_ppr, 480)
            body_run = ET.SubElement(body_para, f"{{{W_NS}}}r")
            placeholder_text = str(cfg.get("acknowledgement_placeholder_text", "") or "")
            body_text_elem = ET.SubElement(body_run, f"{{{W_NS}}}t")
            body_text_elem.text = placeholder_text
            if placeholder_text.startswith(" ") or placeholder_text.endswith(" "):
                body_text_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            set_run_font(body_run, cfg.get("ack_font", "仿宋"), ascii_font="Times New Roman", size=24, bold=False)

            sect_pr = body.find("w:sectPr", NSMAP)
            insert_at = len(list(body)) if sect_pr is None else list(body).index(sect_pr)
            body.insert(insert_at, heading)
            body.insert(insert_at + 1, body_para)
            fixed += 2

    document_model = build_document_model(document_root, {})
    for node in document_model.section_nodes("acknowledgement"):
        if node.module != "acknowledgement_paragraph":
            continue
        text = node.text.strip()
        if not text:
            continue
        p = node.elem
        p_pr = ensure_ppr(p)
        ensure_spacing(p_pr, before=0, after=0)
        ensure_first_line_indent(p_pr, 480)
        for run in p.findall(".//w:r", NSMAP):
            if get_run_text(run) == "":
                continue
            set_run_font(run, cfg.get("ack_font", "仿宋"), ascii_font="Times New Roman", size=24, bold=False)
        fixed += 1
    return fixed


def fix_lnu_ref01(document_root, cfg):
    """LNU_REF01: 参考文献段落调用fix_reference_paragraph统一修复"""
    fixed = 0
    for p, _text in iter_reference_section_paragraphs(
        document_root,
        nsmap=NSMAP,
        get_paragraph_text=get_paragraph_text,
        skip_empty=True,
    ):
        fix_reference_paragraph(p, cfg=cfg)
        fixed += 1
    return fixed


def fix_lnu_ref02(document_root, cfg):
    """LNU_REF02: 按 profile 统一参考文献编号后分隔符。"""
    fixed = 0
    for p, _text in iter_reference_section_paragraphs(
        document_root,
        nsmap=NSMAP,
        get_paragraph_text=get_paragraph_text,
        skip_empty=True,
    ):
        before = get_paragraph_text(p)
        had_tab = paragraph_has_reference_tab(p)
        fix_reference_paragraph(p, cfg=cfg)
        after = get_paragraph_text(p)
        if after != before or paragraph_has_reference_tab(p) != had_tab:
            fixed += 1
    return fixed


_REF_TYPE_MARKER_RE = re.compile(r"\[[A-Z]\]")


def _infer_reference_type_marker(text):
    compact = str(text or "")
    lowered = compact.lower()
    if _REF_TYPE_MARKER_RE.search(compact):
        return None
    if any(token in lowered for token in ("学位论文", " thesis", " dissertation")):
        return "D"
    if "//" in compact or any(token in lowered for token in ("proceedings", "conference", "symposium", "workshop")):
        return "C"
    if any(token in lowered for token in ("出版社", " press", " publisher")) and re.search(r"\b\d{4}\b", compact):
        return "M"
    if re.search(r"\b\d{4}\b.*\b\d+\s*(?:\(\d+\))?\s*:\s*[A-Za-z0-9-]", compact):
        return "J"
    if any(token in lowered for token in ("journal", "research", "microbiology", "bioinformatics", "reports", "letters")):
        return "J"
    return None


def fix_lnu_ref04(document_root, cfg):
    """LNU_REF04: 为明显缺失类型标识的参考文献补齐推断出的文献类型。"""
    fixed = 0
    for p, text in iter_reference_section_paragraphs(
        document_root,
        nsmap=NSMAP,
        get_paragraph_text=get_paragraph_text,
        skip_empty=True,
    ):
        if _REF_TYPE_MARKER_RE.search(text):
            continue
        marker = _infer_reference_type_marker(text)
        if marker is None:
            continue
        marker_text = f"[{marker}]"
        text_nodes = p.findall(".//w:t", NSMAP)
        if not text_nodes:
            continue
        last_non_empty = None
        for text_node in reversed(text_nodes):
            if text_node.text and text_node.text.strip():
                last_non_empty = text_node
                break
        if last_non_empty is None:
            continue

        original = last_non_empty.text.rstrip()
        if original.endswith((".", "。")):
            last_non_empty.text = original[:-1] + marker_text + original[-1]
        else:
            last_non_empty.text = original + marker_text
        fixed += 1
    return fixed


def fix_reference_full_width_punct(p_elem, cfg=None):
    """将参考文献段落中的全角标点替换为英文半角（辽大专用）"""
    if cfg is None or cfg.get("ref_terminal_punct") != ".":
        return

    punct_map = {
        "。": ".",
        "，": ",",
        "：": ":",
        "；": ";",
        "！": "!",
        "？": "?",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
    }
    for text_elem in p_elem.findall(".//w:t", NSMAP):
        if not text_elem.text:
            continue
        updated = text_elem.text
        for full_width, half_width in punct_map.items():
            updated = updated.replace(full_width, half_width)
        if updated != text_elem.text:
            text_elem.text = updated


def fix_reference_punctuation(p_elem, cfg=None):
    paragraph_text = get_paragraph_text(p_elem)
    body_text = re.sub(r"^\[\d+\]\s*", "", paragraph_text).strip()
    if not body_text:
        return

    forced = (cfg or {}).get("ref_terminal_punct")
    if forced:
        expected = forced
    else:
        expected = "。" if is_mostly_cjk(body_text) else "."
    if body_text.endswith(expected):
        return

    runs = [run_elem for run_elem in p_elem.findall(".//w:r", NSMAP) if get_run_text(run_elem).strip()]
    target_run = None
    for run_elem in reversed(runs):
        if not is_superscript(run_elem):
            target_run = run_elem
            break
    if target_run is None and runs:
        target_run = runs[-1]
    if target_run is None:
        return

    text_elems = [t_elem for t_elem in target_run.findall(".//w:t", NSMAP) if t_elem.text]
    if not text_elems:
        return
    text_elems[-1].text = set_terminal_punctuation(text_elems[-1].text, expected)


def default_output_path(input_path):
    directory = os.path.dirname(input_path)
    basename = os.path.basename(input_path)
    stem, ext = os.path.splitext(basename)
    return os.path.join(directory, f"{stem}_已修正{ext}")


def default_normalize_output_path(input_path):
    directory = os.path.dirname(input_path)
    basename = os.path.basename(input_path)
    stem, ext = os.path.splitext(basename)
    return os.path.join(directory, f"{stem}_normalized{ext or '.docx'}")


def fix_footer_page_number(temp_dir, document_root, cfg=None, runtime=None):
    _configure_thesis_fix_dependencies()
    from thesis_fix.page_footer import fix_footer_page_number as _impl

    return _impl(temp_dir, document_root, cfg, runtime)

def inject_template_components(temp_dir, profile_id):
    fix_docx_io.TOOL_ROOT = TOOL_ROOT
    return fix_docx_io.inject_template_components(temp_dir, profile_id)


def write_docx_atomically(input_path: str, output_path: str, updated_parts: dict[str, bytes]) -> None:
    fix_docx_io.Document = Document
    return fix_docx_io.write_docx_atomically(input_path, output_path, updated_parts)


def _refresh_fix_context(ctx: FixExecutionContext) -> FixExecutionContext:
    return _rebuild_fix_context(ctx.document_root, ctx.style_map, ctx.runtime, temp_dir=ctx.temp_dir)


def _apply_shared_document_prepasses(ctx: FixExecutionContext) -> FixExecutionContext:
    structural_changed = False
    if (
        ctx.scope_flags.body
        or ctx.scope_flags.abstract
        or ctx.scope_flags.headings
        or ctx.scope_flags.references
        or ctx.scope_flags.acknowledgement
        or ctx.scope_flags.appendix
    ):
        structural_changed = bool(
            fix_soft_line_breaks(ctx.document_root, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
        ) or structural_changed
    if ctx.scope_flags.figures:
        structural_changed = bool(normalize_object_wrapping(ctx.document_root)) or structural_changed
    if structural_changed:
        ctx = _refresh_fix_context(ctx)
    return ctx


def _apply_heading_style_prepass(ctx: FixExecutionContext) -> FixExecutionContext:
    normalized_headings = normalize_heading_styles(ctx.document_model, ctx.style_map, ctx.runtime)
    if normalized_headings:
        return _refresh_fix_context(ctx)
    return ctx


def _apply_abstract_prepasses(ctx: FixExecutionContext) -> FixExecutionContext:
    if not ctx.scope_flags.abstract:
        return ctx
    if repair_misplaced_abstract_keywords(ctx.document_root, ctx.style_map):
        ctx = _refresh_fix_context(ctx)
    fix_abstract_section(ctx.document_root, ctx.cfg, runtime=ctx.runtime)
    return ctx


def _apply_heading_numbering_prepasses(ctx: FixExecutionContext) -> None:
    if ctx.scope_flags.headings and ctx.runtime.renumber_headings:
        renumber_body_headings(ctx.sections.get("body", []), ctx.style_map, ctx.document_model.table_para_ids)
    if ctx.scope_flags.headings and is_lnu_profile(ctx.runtime):
        normalize_lnu_preface_heading_numbering(ctx.sections.get("body", []), ctx.style_map, ctx.document_model.table_para_ids)
        if not ctx.runtime.renumber_headings:
            for p_elem in ctx.sections.get("body", []):
                if id(p_elem) in ctx.document_model.table_para_ids:
                    continue
                if classify_paragraph(p_elem, ctx.style_map) != "h1":
                    continue
                heading_text = get_paragraph_text(p_elem).strip()
                if not heading_text or is_preface_heading_title(heading_text) or re.match(r"^第\s*\d+\s*章", heading_text):
                    continue
                title = _extract_heading_title(heading_text, "h1") or heading_text
                chapter_no = _parse_heading_chapter_number(heading_text)
                if chapter_no is None:
                    continue
                rewrite_paragraph_text_preserve_runs(p_elem, f"第{chapter_no}章 {title}")


def _apply_equation_prepasses(ctx: FixExecutionContext) -> FixExecutionContext:
    if not (ctx.scope_flags.body or ctx.scope_flags.appendix):
        return ctx
    if fix_equation_number_alignment(ctx.document_root, ctx.cfg):
        return _refresh_fix_context(ctx)
    return ctx


def _apply_toc_prepasses(ctx: FixExecutionContext) -> tuple[FixExecutionContext, dict]:
    if not ctx.scope_flags.toc:
        return ctx, {}
    if ctx.cfg.get("toc_auto"):
        toc_parts = fix_insert_toc(
            ctx.document_root,
            ctx.cfg,
            style_map=ctx.style_map,
            runtime=ctx.runtime,
            repair_keywords=ctx.scope_flags.abstract,
        )
        return _refresh_fix_context(ctx), toc_parts
    inserted_visible_toc = ensure_visible_toc(
        ctx.document_root,
        ctx.cfg,
        style_map=ctx.style_map,
        runtime=ctx.runtime,
    )
    if inserted_visible_toc:
        return _refresh_fix_context(ctx), {}
    return ctx, {}


def _apply_frontmatter_pagination_prepasses(ctx: FixExecutionContext) -> FixExecutionContext:
    if not ctx.scope_flags.page:
        return ctx
    normalized_sections = normalize_frontmatter_page_sections(ctx.document_root, ctx.style_map)
    cleaned_breaks = cleanup_frontmatter_redundant_page_breaks(ctx.document_root, ctx.style_map)
    if normalized_sections or cleaned_breaks:
        return _refresh_fix_context(ctx)
    return ctx


def _apply_document_level_prepasses(ctx: FixExecutionContext):
    ctx = _apply_shared_document_prepasses(ctx)
    ctx = _apply_heading_style_prepass(ctx)

    if ctx.scope_flags.page:
        fix_page_margins(ctx.document_root, ctx.cfg, runtime=ctx.runtime)
        fix_cover_layout(ctx.document_root, ctx.paragraph_sections, runtime=ctx.runtime)
    ctx = _apply_abstract_prepasses(ctx)
    _apply_heading_numbering_prepasses(ctx)
    ctx = _apply_equation_prepasses(ctx)
    ctx, toc_parts = _apply_toc_prepasses(ctx)
    ctx = _apply_frontmatter_pagination_prepasses(ctx)
    return ctx, toc_parts


def _apply_protected_paragraph_fix(p_elem, paragraph_type, section_name, ctx: FixExecutionContext):
    if paragraph_has_math(p_elem) and section_name == "body":
        if ctx.scope_flags.body:
            if is_display_equation_paragraph(p_elem):
                fix_equation_paragraph(p_elem, runtime=ctx.runtime)
            else:
                split_inline_citations(p_elem)
                fix_body_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
                normalize_equation_explanation_symbols(p_elem)
                fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
                fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
                fix_lnu_unit_spacing(p_elem)
                move_superscript_citations_before_terminal_punct(p_elem)
            fix_superscript_fonts(p_elem)
        return
    if paragraph_type == "body" and section_name == "body":
        if ctx.scope_flags.body:
            split_inline_citations(p_elem)
            fix_body_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
            normalize_equation_explanation_symbols(p_elem)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
            move_superscript_citations_before_terminal_punct(p_elem)
            fix_superscript_fonts(p_elem)
        return
    if paragraph_type == "body" and section_name == "appendix":
        if ctx.scope_flags.appendix:
            split_inline_citations(p_elem)
            fix_body_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
            normalize_equation_explanation_symbols(p_elem)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
            move_superscript_citations_before_terminal_punct(p_elem)
            fix_superscript_fonts(p_elem)
        return
    if paragraph_type == "body" and section_name == "acknowledgement":
        if ctx.scope_flags.body:
            split_inline_citations(p_elem)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
            move_superscript_citations_before_terminal_punct(p_elem)
        if ctx.scope_flags.acknowledgement:
            fix_ack_paragraph(p_elem, ctx.cfg)
        if ctx.scope_flags.body or ctx.scope_flags.acknowledgement:
            fix_superscript_fonts(p_elem)
        return
    if paragraph_type == "h1":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading_paragraph(
                p_elem,
                "center",
                False,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            if section_name in {"body", "appendix", "references", "acknowledgement"}:
                fix_heading_page_break(p_elem)
            fix_heading_spacing(p_elem, "h1", cfg=ctx.cfg, runtime=ctx.runtime)
        return
    if paragraph_type == "h2":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading_paragraph(
                p_elem,
                "left",
                False,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            fix_heading_num_space(p_elem)
            fix_heading_spacing(p_elem, "h2", cfg=ctx.cfg, runtime=ctx.runtime)
        return
    if paragraph_type == "h3":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading_paragraph(
                p_elem,
                "left",
                True,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            fix_heading_num_space(p_elem)
            fix_heading_spacing(p_elem, "h3", cfg=ctx.cfg, runtime=ctx.runtime)
        return
    if paragraph_type == "h4" and should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
        fix_heading4(
            p_elem,
            cfg=ctx.cfg,
            heading_style_ids=ctx.runtime.heading_style_ids,
            runtime=ctx.runtime,
        )
        fix_heading_num_space(p_elem)
        fix_heading_spacing(p_elem, "h4", cfg=ctx.cfg, runtime=ctx.runtime)


def _apply_paragraph_fix(paragraph_node, ctx: FixExecutionContext):
    p_elem = paragraph_node.elem
    if paragraph_node.in_table:
        if paragraph_node.section == "body" and ctx.scope_flags.body:
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
        return
    if is_generated_toc_paragraph(p_elem):
        return

    paragraph_text = paragraph_node.text.strip()
    section_name = paragraph_node.section
    paragraph_type = paragraph_node.kind

    if paragraph_type == "reference":
        if ctx.scope_flags.references:
            fix_reference_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_reference_punctuation(p_elem, ctx.cfg)
            if is_lnu_profile(ctx.runtime):
                fix_ref_punctuation(p_elem)
                fix_ref_numbering_space(p_elem)
            fix_superscript_fonts(p_elem)
        return

    if paragraph_node.container_section in {"cover", "toc"} or section_name == "backmatter":
        return
    if id(p_elem) in ctx.protected_ids:
        _apply_protected_paragraph_fix(p_elem, paragraph_type, section_name, ctx)
        return
    if ctx.scope_flags.abstract and paragraph_node.module == "abstract_cn_keywords":
        fix_kw02_trailing_punct(p_elem)
        fix_kw01_keyword_count(p_elem, ctx.cfg)
    if section_name in {"abstract_cn", "abstract_en"}:
        if not ctx.scope_flags.abstract:
            return
        if is_lnu_profile(ctx.runtime):
            if paragraph_node.module in {"abstract_cn_keywords", "abstract_en_keywords"}:
                fix_kw01_keyword_count(p_elem, ctx.cfg)
                fix_superscript_fonts(p_elem)
                return
            if paragraph_node.module == f"{section_name}_title":
                fix_abstract_heading(p_elem, ctx.cfg, section_name)
            else:
                fix_abstract_body(p_elem, ctx.cfg, section_name)
        fix_superscript_fonts(p_elem)
        return
    if paragraph_node.module == "acknowledgement_paragraph":
        if ctx.scope_flags.body:
            split_inline_citations(p_elem)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
            move_superscript_citations_before_terminal_punct(p_elem)
        if ctx.scope_flags.acknowledgement:
            fix_ack_paragraph(p_elem, ctx.cfg)
        if ctx.scope_flags.body or ctx.scope_flags.acknowledgement:
            fix_superscript_fonts(p_elem)
        return
    if paragraph_node.module == "appendix_paragraph":
        if ctx.scope_flags.appendix:
            split_inline_citations(p_elem)
            fix_body_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
            normalize_equation_explanation_symbols(p_elem)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
            move_superscript_citations_before_terminal_punct(p_elem)
            fix_superscript_fonts(p_elem)
        return
    if paragraph_node.module == "body_paragraph":
        if ctx.scope_flags.body:
            split_inline_citations(p_elem)
            fix_body_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
            normalize_equation_explanation_symbols(p_elem)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_lnu_unit_spacing(p_elem)
            move_superscript_citations_before_terminal_punct(p_elem)
    elif paragraph_node.module in {"body_caption", "appendix_caption"}:
        if ctx.scope_flags.figures:
            fix_caption_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_caption_number_sep(p_elem, ctx.cfg)
            trim_caption_terminal_punctuation(p_elem)
    elif paragraph_node.module in CAPTION_EN_MODULES:
        if ctx.scope_flags.figures:
            fix_english_caption_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
    elif paragraph_node.module in CAPTION_NOTE_MODULES:
        if ctx.scope_flags.figures:
            fix_caption_note_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_cjk_latin(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
            fix_sp_num_cjk(p_elem, cfg=ctx.cfg, runtime=ctx.runtime)
    elif paragraph_type == "h1":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading_paragraph(
                p_elem,
                "center",
                False,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            if section_name in {"body", "appendix", "references", "acknowledgement"}:
                fix_heading_page_break(p_elem)
            fix_heading_spacing(p_elem, "h1", cfg=ctx.cfg, runtime=ctx.runtime)
    elif paragraph_type == "h2":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading_paragraph(
                p_elem,
                "left",
                False,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            fix_heading_num_space(p_elem)
            fix_heading_spacing(p_elem, "h2", cfg=ctx.cfg, runtime=ctx.runtime)
    elif paragraph_type == "h3":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading_paragraph(
                p_elem,
                "left",
                True,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            fix_heading_num_space(p_elem)
            fix_heading_spacing(p_elem, "h3", cfg=ctx.cfg, runtime=ctx.runtime)
    elif paragraph_type == "h4":
        if should_fix_heading_in_scope(ctx.runtime.requested_scopes, section_name):
            fix_heading4(
                p_elem,
                cfg=ctx.cfg,
                heading_style_ids=ctx.runtime.heading_style_ids,
                runtime=ctx.runtime,
            )
            fix_heading_num_space(p_elem)
            fix_heading_spacing(p_elem, "h4", cfg=ctx.cfg, runtime=ctx.runtime)
    elif paragraph_type == "other" and section_name == "body":
        if ctx.scope_flags.body:
            text = get_paragraph_text(p_elem).strip()
            if text and not text.isdigit() and len(text) > 10:
                fix_body_paragraph(p_elem, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
                fix_equation_reference_text(p_elem, cfg=ctx.cfg)
    if ctx.scope_flags.figures and p_elem.find(".//w:drawing", NSMAP) is not None:
        fix_figure_paragraph(p_elem)
    if (
        (ctx.scope_flags.body and section_name == "body")
        or (ctx.scope_flags.appendix and section_name == "appendix")
    ):
        fix_superscript_fonts(p_elem)


def _apply_table_passes(ctx: FixExecutionContext):
    if not ctx.scope_flags.figures:
        return
    fix_tb03_repeat_header(ctx.document_root)
    for tbl in ctx.document_root.findall(".//w:tbl", NSMAP):
        if audit_thesis.is_equation_layout_table(tbl):
            fix_equation_layout_table_borders(tbl)
            continue
        fix_table_borders(tbl)
        if is_lnu_profile(ctx.runtime):
            fix_table_cell_font(tbl, ctx.cfg)


def _apply_lnu_postpasses(ctx: FixExecutionContext):
    _configure_thesis_fix_dependencies()
    from thesis_fix.lnu_postpasses import _apply_lnu_postpasses as _impl

    return _impl(ctx)

def _apply_text_cleanup_passes(ctx: FixExecutionContext):
    _apply_lnu_compact_text_passes(ctx)
    ellipsis_ids = _collect_text_cleanup_allowed_ids(ctx, include_abstract_cn_punct=False)
    if ellipsis_ids:
        fix_ellipsis(
            ctx.document_root,
            style_map=ctx.style_map,
            allowed_ids=ellipsis_ids,
            protected_ids=ctx.protected_ids,
        )
    punct_ids = _collect_text_cleanup_allowed_ids(
        ctx,
        include_abstract_cn_punct=True,
        include_toc_punct=is_lnu_profile(ctx.runtime),
    )
    if punct_ids:
        fix_half_width_punct_in_cjk(
            ctx.document_root,
            style_map=ctx.style_map,
            allowed_ids=punct_ids,
            protected_ids=ctx.protected_ids,
        )


def _apply_post_cleanup(ctx: FixExecutionContext):
    body_para_ids = {id(node.elem) for node in ctx.document_model.section_nodes("body")}
    if ctx.scope_flags.headings:
        fix_remove_empty_before_headings(ctx.document_root, ctx.style_map, body_para_ids)
    if ctx.scope_flags.references:
        fix_remove_hidden_page_number_artifacts(ctx.document_root)
        fix_remove_trailing_empty_before_refs(ctx.document_root, ctx.style_map, body_para_ids)


def fix_footnote_size_part(temp_dir: str | None, cfg: dict) -> bytes | None:
    if temp_dir is None:
        return None
    footnotes_path = os.path.join(temp_dir, "word", "footnotes.xml")
    if not os.path.isfile(footnotes_path):
        return None

    footnotes_root = ET.parse(footnotes_path).getroot()
    expected_size = str(cfg.get("footnote_size", 16) or 16)
    changed = False
    for footnote_elem in footnotes_root.findall(".//w:footnote", NSMAP):
        footnote_id = footnote_elem.get(f"{{{W_NS}}}id")
        if footnote_id in {"-1", "0"}:
            continue
        for run_elem in footnote_elem.findall(".//w:r", NSMAP):
            if not get_run_text(run_elem).strip():
                continue
            ensure_size(run_elem, expected_size)
            changed = True
    if not changed:
        return None
    return ET.tostring(footnotes_root, encoding="utf-8", xml_declaration=True)


def _cleanup_docx_hidden_page_number_artifacts(docx_path: str) -> int:
    with zipfile.ZipFile(docx_path, "r") as zf:
        parts = {name: zf.read(name) for name in zf.namelist()}

    document_xml = parts.get("word/document.xml")
    if document_xml is None:
        return 0

    document_root = ET.fromstring(document_xml)
    removed = fix_remove_hidden_page_number_artifacts(document_root)
    if not removed:
        return 0

    parts["word/document.xml"] = ET.tostring(document_root, encoding="utf-8", xml_declaration=True)
    temp_output = tempfile.NamedTemporaryFile(prefix="lnu_pagefield_cleanup_", suffix=".docx", delete=False)
    temp_output.close()
    try:
        with zipfile.ZipFile(temp_output.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, payload in parts.items():
                zf.writestr(name, payload)
        shutil.move(temp_output.name, docx_path)
    finally:
        if os.path.exists(temp_output.name):
            os.remove(temp_output.name)
    return removed


def _postprocess_lnu_reference_order(output_path, runtime, cfg):
    _configure_thesis_fix_dependencies()
    from thesis_fix.lnu_postpasses import _postprocess_lnu_reference_order as _impl

    return _impl(output_path, runtime, cfg)


def normalize_docx(input_path, output_path, profile_path=None, strict_profile=None):
    input_path = audit_thesis.validate_docx_path(input_path)
    runtime = build_fix_runtime(
        profile_path=profile_path,
        scopes=list(SAFE_NORMALIZE_SCOPE_IDS),
        strict_profile=strict_profile,
    )

    document_xml, styles_xml, _footnotes_xml = audit_thesis.load_docx_xml(input_path)
    document_root = ET.fromstring(document_xml)
    styles_root = ET.fromstring(styles_xml)
    style_map = build_style_map(styles_root)
    runtime = replace(runtime, heading_style_ids=resolve_heading_style_ids(style_map, runtime=runtime))
    ctx = _rebuild_fix_context(document_root, style_map, runtime)
    operations: dict[str, int] = {}

    def _record(operation_id: str, count) -> None:
        normalized_count = int(count or 0)
        if normalized_count > 0:
            operations[operation_id] = normalized_count

    soft_line_breaks_changed = fix_soft_line_breaks(ctx.document_root, cfg=ctx.cfg, runtime=ctx.runtime, style_map=ctx.style_map)
    _record("soft_line_breaks", soft_line_breaks_changed)

    object_wrapping_changed = normalize_object_wrapping(ctx.document_root)
    _record("object_wrapping", object_wrapping_changed)
    if soft_line_breaks_changed or object_wrapping_changed:
        ctx = _refresh_fix_context(ctx)

    heading_style_changed = normalize_heading_styles(ctx.document_model, ctx.style_map, ctx.runtime)
    _record("heading_styles", heading_style_changed)
    if heading_style_changed:
        ctx = _refresh_fix_context(ctx)

    abstract_keywords_changed = repair_misplaced_abstract_keywords(ctx.document_root, ctx.style_map)
    _record("abstract_keywords", abstract_keywords_changed)
    if abstract_keywords_changed:
        ctx = _refresh_fix_context(ctx)

    frontmatter_sections_changed = normalize_frontmatter_page_sections(ctx.document_root, ctx.style_map)
    _record("frontmatter_sections", frontmatter_sections_changed)
    if frontmatter_sections_changed:
        ctx = _refresh_fix_context(ctx)

    frontmatter_breaks_changed = cleanup_frontmatter_redundant_page_breaks(ctx.document_root, ctx.style_map)
    _record("frontmatter_breaks", frontmatter_breaks_changed)
    if frontmatter_breaks_changed:
        ctx = _refresh_fix_context(ctx)

    duplicate_toc_title_changed = remove_duplicate_body_toc_title(ctx.document_root, ctx.style_map)
    _record("duplicate_toc_title", duplicate_toc_title_changed)
    if duplicate_toc_title_changed:
        ctx = _refresh_fix_context(ctx)

    toc_title_changed = normalize_toc_title_paragraph(ctx.document_root, ctx.style_map, ctx.cfg)
    _record("toc_title", toc_title_changed)
    if toc_title_changed:
        ctx = _refresh_fix_context(ctx)

    toc_entries_changed = normalize_toc_entry_paragraphs(ctx.document_root, ctx.style_map, ctx.cfg)
    _record("toc_entries", toc_entries_changed)

    updated_parts = {
        "word/document.xml": ET.tostring(ctx.document_root, encoding="utf-8", xml_declaration=True),
    }
    write_docx_atomically(input_path, output_path, updated_parts)

    return {
        "input_path": str(Path(input_path)),
        "output_path": str(Path(output_path)),
        "profile_id": runtime.profile_id,
        "requested_profile": runtime.requested_profile,
        "fallback_used": runtime.fallback_used,
        "profile_display": format_profile_resolution(runtime.profile_id, runtime.requested_profile, runtime.fallback_used),
        "changed": bool(operations),
        "operations": [
            {
                "id": operation_id,
                "label": SAFE_NORMALIZE_OPERATION_LABELS.get(operation_id, operation_id),
                "count": count,
            }
            for operation_id, count in operations.items()
        ],
    }


def fix_docx(input_path, output_path, profile_path=None, toc=False, scopes=None, runtime=None):
    input_path = audit_thesis.validate_docx_path(input_path)
    runtime = runtime or build_fix_runtime(profile_path=profile_path, toc=toc, scopes=scopes)

    temp_dir = tempfile.mkdtemp(prefix="thesis_fix_")
    try:
        with zipfile.ZipFile(input_path, "r") as source_zip:
            source_zip.extractall(temp_dir)

        inject_template_components(temp_dir, runtime.template_profile_id)

        document_path = os.path.join(temp_dir, "word", "document.xml")
        styles_path = os.path.join(temp_dir, "word", "styles.xml")
        if not os.path.isfile(styles_path):
            os.makedirs(os.path.dirname(styles_path), exist_ok=True)
            with open(styles_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<w:styles xmlns:w="{W_NS}"/>'
                )

        with open(document_path, "r", encoding="utf-8") as handle:
            document_xml = handle.read()
        with open(styles_path, "r", encoding="utf-8") as handle:
            styles_xml = handle.read()

        document_root = ET.fromstring(document_xml)
        styles_root = ET.fromstring(styles_xml)
        style_map = build_style_map(styles_root)
        runtime = replace(runtime, heading_style_ids=resolve_heading_style_ids(style_map, runtime=runtime))
        ctx = _rebuild_fix_context(document_root, style_map, runtime, temp_dir=temp_dir)
        ctx, toc_parts = _apply_document_level_prepasses(ctx)

        for paragraph_node in ctx.document_model.paragraphs:
            _apply_paragraph_fix(paragraph_node, ctx)

        _apply_table_passes(ctx)
        _apply_lnu_postpasses(ctx)
        ctx = _rebuild_fix_context(ctx.document_root, ctx.style_map, ctx.runtime, temp_dir=temp_dir)
        _apply_text_cleanup_passes(ctx)
        ctx = _rebuild_fix_context(ctx.document_root, ctx.style_map, ctx.runtime, temp_dir=temp_dir)
        _apply_post_cleanup(ctx)
        ctx = _apply_equation_prepasses(ctx)

        updated_parts = fix_output_parts.build_updated_parts(
            ctx=ctx,
            toc_parts=toc_parts,
            footer_builder=fix_footer_page_number,
            settings_builder=build_settings_with_update_fields,
        )
        if ctx.scope_flags.page:
            footnotes_part = fix_footnote_size_part(ctx.temp_dir, ctx.cfg)
            if footnotes_part is not None:
                updated_parts["word/footnotes.xml"] = footnotes_part
        write_docx_atomically(input_path, output_path, updated_parts)
        _postprocess_lnu_reference_order(output_path, runtime, ctx.cfg)

        return output_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="修复 DOCX 论文格式")
    parser.add_argument("input", help="输入 .docx 文件路径")
    parser.add_argument("--output", help="输出 .docx 文件路径")
    parser.add_argument("--profile", default=None, help="学校Profile路径或简称（默认 lnu）")
    parser.add_argument(
        "--strict-profile",
        dest="strict_profile",
        action="store_true",
        default=None,
        help="profile 加载失败时直接报错，不回退默认配置",
    )
    parser.add_argument(
        "--allow-profile-fallback",
        dest="strict_profile",
        action="store_false",
        help="profile 加载失败时回退到默认 LNU 配置",
    )
    parser.add_argument("--toc", action="store_true", default=False, help="在文档开头自动插入辽大格式目录（脚本预填可见目录结果）")
    parser.add_argument("--dry-run", action="store_true", default=False, help="仅预览将触达的修复范围，不写入文件")
    parser.add_argument("--renumber-headings", action="store_true", default=False, help="显式启用正文标题重编号")
    parser.add_argument("--layout-rebalance", action="store_true", default=False, help="显式启用图表跨页排布优化，仅在 figures_tables scope 下生效")
    parser.add_argument(
        "--scope",
        action="append",
        default=None,
        help="仅修复指定 scope，可重复传入或使用逗号分隔多个值",
    )
    args = parser.parse_args()

    output_path = args.output or default_output_path(args.input)
    runtime = build_fix_runtime(
        profile_path=args.profile,
        toc=args.toc,
        scopes=args.scope,
        renumber_headings=args.renumber_headings,
        layout_rebalance=args.layout_rebalance,
        dry_run=args.dry_run,
        strict_profile=args.strict_profile,
    )
    if args.dry_run:
        preview = describe_fix_docx(
            args.input,
            output_path=output_path,
            runtime=runtime,
        )
        print(render_fix_preview(preview))
        return
    fixed_path = fix_docx(
        args.input,
        output_path,
        runtime=runtime,
    )
    results, score, report, audit_runtime = audit_thesis.audit_docx_with_runtime(
        fixed_path,
        profile_path=args.profile,
        strict_profile=args.strict_profile,
    )
    print(f"Profile: {format_profile_resolution(audit_runtime.profile_id, audit_runtime.requested_profile, audit_runtime.fallback_used)}")
    print(report)
    if args.toc:
        print("提示: 已写入可见自动目录域结果；如后续继续改正文分页，可在 Word/WPS 中更新域后复核页码。")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc))
