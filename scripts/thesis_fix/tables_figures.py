from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

from sections._xml_helpers import (
    get_paragraph_spacing_twips as _get_paragraph_spacing_twips,
    set_paragraph_pagination_flags as _set_paragraph_pagination_flags,
    set_paragraph_spacing_attrs as _set_paragraph_spacing_attrs,
    set_table_row_cant_split as _set_table_row_cant_split,
)
from thesis_fix.dependencies import require


def rebalance_figure_blocks_for_layout(document_root, style_map=None, cfg=None, runtime=None):
    (
        NSMAP,
        W_NS,
        _caption_reference_candidates,
        _is_generic_caption_lead_text,
        _paragraph_outline_level,
        build_document_model,
        collect_figure_blocks,
        get_paragraph_text,
    ) = require(
        "NSMAP",
        "W_NS",
        "_caption_reference_candidates",
        "_is_generic_caption_lead_text",
        "_paragraph_outline_level",
        "build_document_model",
        "collect_figure_blocks",
        "get_paragraph_text",
    )
    """按同小节内已有图号引用，前移图块以减少跨页大空白。

    这是显式开启的启发式流程，只处理正文图块，默认关闭。
    """
    if runtime is not None and not runtime.layout_rebalance:
        return 0

    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    paragraph_tag = f"{{{W_NS}}}p"
    changed = 0

    while True:
        moved = False
        model = build_document_model(document_root, style_map or {})
        node_by_id = {id(node.elem): node for node in model.paragraphs}
        body_children = list(body)
        child_index = {id(elem): idx for idx, elem in enumerate(body_children)}

        for block in collect_figure_blocks(document_root, style_map or {}):
            if block.get("section") != "body":
                continue

            caption_text = (block["caption"].text or "").strip()
            match = re.match(r"^(图)\s*(\d+(?:[.\-]\d+)*)", caption_text)
            if match is None:
                continue

            prefix, number = match.groups()
            candidates = _caption_reference_candidates(prefix, number)
            image_elem = block["image"]
            caption_elem = block["caption"].elem
            last_elem = block["last_elem"]
            image_idx = child_index.get(id(image_elem))
            end_idx = child_index.get(id(last_elem))
            if image_idx is None or end_idx is None:
                continue

            anchor_elem = None
            scan_idx = image_idx - 1
            while scan_idx >= 0:
                candidate_elem = body_children[scan_idx]
                if candidate_elem.tag != paragraph_tag:
                    scan_idx -= 1
                    continue
                candidate_node = node_by_id.get(id(candidate_elem))
                candidate_text = get_paragraph_text(candidate_elem).strip()
                if not candidate_text:
                    scan_idx -= 1
                    continue
                compact_text = re.sub(r"[\s\u3000]+", "", candidate_text)
                matched_reference = any(token in compact_text for token in candidates)
                if matched_reference:
                    if not _is_generic_caption_lead_text(candidate_text, prefix, number):
                        anchor_elem = candidate_elem
                outline_lvl = _paragraph_outline_level(candidate_elem, style_map or {})
                if outline_lvl in {0, 1} and not matched_reference:
                    break
                scan_idx -= 1

            if anchor_elem is None:
                continue

            anchor_idx = child_index[id(anchor_elem)]
            if anchor_idx + 1 >= image_idx:
                continue

            block_elems = body_children[image_idx : end_idx + 1]
            for elem in block_elems:
                body.remove(elem)
            body_children = list(body)
            anchor_idx = body_children.index(anchor_elem)
            insert_idx = anchor_idx + 1
            for offset, elem in enumerate(block_elems):
                body.insert(insert_idx + offset, elem)

            changed += 1
            moved = True
            break

        if not moved:
            break

    return changed

def rebalance_table_blocks_for_layout(document_root, style_map=None, cfg=None, runtime=None):
    (
        NSMAP,
        W_NS,
        _caption_reference_candidates,
        _is_generic_caption_lead_text,
        _paragraph_outline_level,
        build_document_model,
        collect_table_blocks,
        get_paragraph_text,
    ) = require(
        "NSMAP",
        "W_NS",
        "_caption_reference_candidates",
        "_is_generic_caption_lead_text",
        "_paragraph_outline_level",
        "build_document_model",
        "collect_table_blocks",
        "get_paragraph_text",
    )
    """按同小节内已有表号引用，前移表块以减少跨页大空白。"""
    if runtime is not None and not runtime.layout_rebalance:
        return 0

    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    paragraph_tag = f"{{{W_NS}}}p"
    changed = 0

    while True:
        moved = False
        model = build_document_model(document_root, style_map or {})
        node_by_id = {id(node.elem): node for node in model.paragraphs}
        body_children = list(body)
        child_index = {id(elem): idx for idx, elem in enumerate(body_children)}

        for block in collect_table_blocks(document_root, style_map or {}):
            if block.get("section") != "body":
                continue

            caption_text = (block["caption"].text or "").strip()
            match = re.match(r"^(表)\s*(\d+(?:[.\-]\d+)*)", caption_text)
            if match is None:
                continue

            prefix, number = match.groups()
            candidates = _caption_reference_candidates(prefix, number)
            caption_elem = block["caption"].elem
            last_elem = block["last_elem"]
            caption_idx = child_index.get(id(caption_elem))
            end_idx = child_index.get(id(last_elem))
            if caption_idx is None or end_idx is None:
                continue

            anchor_elem = None
            scan_idx = caption_idx - 1
            while scan_idx >= 0:
                candidate_elem = body_children[scan_idx]
                if candidate_elem.tag != paragraph_tag:
                    scan_idx -= 1
                    continue
                candidate_node = node_by_id.get(id(candidate_elem))
                candidate_text = get_paragraph_text(candidate_elem).strip()
                if not candidate_text:
                    scan_idx -= 1
                    continue
                compact_text = re.sub(r"[\s\u3000]+", "", candidate_text)
                matched_reference = any(token in compact_text for token in candidates)
                if matched_reference:
                    if not _is_generic_caption_lead_text(candidate_text, prefix, number):
                        anchor_elem = candidate_elem
                outline_lvl = _paragraph_outline_level(candidate_elem, style_map or {})
                if outline_lvl in {0, 1} and not matched_reference:
                    break
                scan_idx -= 1

            if anchor_elem is None:
                continue

            anchor_idx = child_index[id(anchor_elem)]
            if anchor_idx + 1 >= caption_idx:
                continue

            block_elems = body_children[caption_idx : end_idx + 1]
            for elem in block_elems:
                body.remove(elem)
            body_children = list(body)
            anchor_idx = body_children.index(anchor_elem)
            insert_idx = anchor_idx + 1
            for offset, elem in enumerate(block_elems):
                body.insert(insert_idx + offset, elem)

            changed += 1
            moved = True
            break

        if not moved:
            break

    return changed

def normalize_object_wrapping(document_root, cfg=None, runtime=None):
    NAMESPACES, NSMAP = require("NAMESPACES", "NSMAP")
    """统一对象定位：图片改为嵌入型，表格移除浮动环绕。"""
    wp_ns = NAMESPACES["wp"]
    changed = 0

    for drawing in document_root.findall(".//w:drawing", NSMAP):
        anchor = drawing.find(f"{{{wp_ns}}}anchor")
        if anchor is None:
            continue
        inline = ET.Element(f"{{{wp_ns}}}inline")
        for attr_name in ("distT", "distB", "distL", "distR"):
            inline.set(attr_name, anchor.get(attr_name, "0"))
        for child_name in ("extent", "effectExtent", "docPr", "cNvGraphicFramePr"):
            child = anchor.find(f"{{{wp_ns}}}{child_name}")
            if child is not None:
                inline.append(copy.deepcopy(child))
        graphic = anchor.find(f"{{{NAMESPACES['a']}}}graphic")
        if graphic is not None:
            inline.append(copy.deepcopy(graphic))
        anchor_idx = list(drawing).index(anchor)
        drawing.remove(anchor)
        drawing.insert(anchor_idx, inline)
        changed += 1

    for table in document_root.findall(".//w:tbl", NSMAP):
        tbl_pr = table.find("w:tblPr", NSMAP)
        if tbl_pr is None:
            continue
        tblp_pr = tbl_pr.find("w:tblpPr", NSMAP)
        if tblp_pr is None:
            continue
        tbl_pr.remove(tblp_pr)
        changed += 1

    return changed

def normalize_lnu_figure_block_layout(document_root, style_map=None, cfg=None, runtime=None):
    (
        CAPTION_EN_MODULES,
        CAPTION_NOTE_MODULES,
        NSMAP,
        W_NS,
        build_document_model,
        get_paragraph_text,
        resolve_fix_cfg,
    ) = require(
        "CAPTION_EN_MODULES",
        "CAPTION_NOTE_MODULES",
        "NSMAP",
        "W_NS",
        "build_document_model",
        "get_paragraph_text",
        "resolve_fix_cfg",
    )
    """统一图块上下留白与图名/图注行距，避免主链修复后仍出现图前后空白不一致。"""
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    gap_twips = int(cfg.get("figure_blank_line_twips", cfg.get("body_line", 360) or 360))
    body_paragraph_tag = f"{{{W_NS}}}p"

    def _has_drawing(p_elem):
        return p_elem.find(".//w:drawing", NSMAP) is not None

    def _is_blank_paragraph(p_elem):
        return not _has_drawing(p_elem) and not get_paragraph_text(p_elem).strip()

    changed = 0
    while True:
        model = build_document_model(document_root, style_map or {})
        body_paragraphs = [child for child in list(body) if child.tag == body_paragraph_tag]
        paragraph_index = {id(p_elem): idx for idx, p_elem in enumerate(body_paragraphs)}
        node_by_elem_id = {id(node.elem): node for node in model.paragraphs}
        blocks = []

        for p_elem in body_paragraphs:
            node = node_by_elem_id.get(id(p_elem))
            if node is None or node.module not in {"body_caption", "appendix_caption"}:
                continue
            caption_idx = paragraph_index[id(p_elem)]
            anchor_idx = caption_idx
            if caption_idx > 0 and _has_drawing(body_paragraphs[caption_idx - 1]):
                anchor_idx = caption_idx - 1

            end_idx = caption_idx
            note_indices = []
            scan_idx = caption_idx + 1
            while scan_idx < len(body_paragraphs):
                next_node = node_by_elem_id.get(id(body_paragraphs[scan_idx]))
                if next_node is None or next_node.module not in CAPTION_EN_MODULES | CAPTION_NOTE_MODULES:
                    break
                note_indices.append(scan_idx)
                end_idx = scan_idx
                scan_idx += 1

            blocks.append(
                {
                    "caption_idx": caption_idx,
                    "anchor_idx": anchor_idx,
                    "end_idx": end_idx,
                    "note_indices": note_indices,
                }
            )

        if not blocks:
            break

        moved = False
        for block in sorted(blocks, key=lambda item: item["anchor_idx"], reverse=True):
            anchor_idx = block["anchor_idx"]
            caption_idx = block["caption_idx"]
            end_idx = block["end_idx"]

            while anchor_idx > 0 and _is_blank_paragraph(body_paragraphs[anchor_idx - 1]):
                body.remove(body_paragraphs[anchor_idx - 1])
                del body_paragraphs[anchor_idx - 1]
                anchor_idx -= 1
                caption_idx -= 1
                end_idx -= 1
                changed += 1
                moved = True

            while end_idx + 1 < len(body_paragraphs) and _is_blank_paragraph(body_paragraphs[end_idx + 1]):
                body.remove(body_paragraphs[end_idx + 1])
                del body_paragraphs[end_idx + 1]
                changed += 1
                moved = True

            prev_idx = anchor_idx - 1
            while prev_idx >= 0 and _is_blank_paragraph(body_paragraphs[prev_idx]):
                prev_idx -= 1
            next_idx = end_idx + 1
            while next_idx < len(body_paragraphs) and _is_blank_paragraph(body_paragraphs[next_idx]):
                next_idx += 1

            anchor_elem = body_paragraphs[anchor_idx]
            caption_elem = body_paragraphs[caption_idx]
            end_elem = body_paragraphs[end_idx]

            prev_after = _get_paragraph_spacing_twips(body_paragraphs[prev_idx], "after") if prev_idx >= 0 else 0
            next_before = _get_paragraph_spacing_twips(body_paragraphs[next_idx], "before") if next_idx < len(body_paragraphs) else 0
            target_before = max(0, gap_twips - prev_after) if prev_idx >= 0 else 0
            target_after = max(0, gap_twips - next_before) if next_idx < len(body_paragraphs) else 0

            current_before = _get_paragraph_spacing_twips(anchor_elem, "before")
            if current_before != target_before:
                _set_paragraph_spacing_attrs(anchor_elem, before=target_before)
                changed += 1

            current_anchor_after = _get_paragraph_spacing_twips(anchor_elem, "after")
            if current_anchor_after != 0:
                _set_paragraph_spacing_attrs(anchor_elem, after=0)
                changed += 1

            current_caption_before = _get_paragraph_spacing_twips(caption_elem, "before")
            current_caption_after = _get_paragraph_spacing_twips(caption_elem, "after")
            if current_caption_before != 0 or (caption_elem is not end_elem and current_caption_after != 0):
                _set_paragraph_spacing_attrs(caption_elem, before=0, after=0 if caption_elem is not end_elem else None)
                changed += 1

            if caption_elem is end_elem and current_caption_after != target_after:
                _set_paragraph_spacing_attrs(caption_elem, after=target_after)
                changed += 1

            if end_elem is not caption_elem:
                current_end_after = _get_paragraph_spacing_twips(end_elem, "after")
                if current_end_after != target_after:
                    _set_paragraph_spacing_attrs(end_elem, after=target_after)
                    changed += 1

            note_scan_idx = caption_idx + 1
            while note_scan_idx <= end_idx:
                note_elem = body_paragraphs[note_scan_idx]
                note_before = _get_paragraph_spacing_twips(note_elem, "before")
                desired_after = target_after if note_scan_idx == end_idx else 0
                note_after = _get_paragraph_spacing_twips(note_elem, "after")
                if note_before != 0 or note_after != desired_after:
                    _set_paragraph_spacing_attrs(note_elem, before=0, after=desired_after)
                    changed += 1
                note_scan_idx += 1

        if not moved:
            break

    return changed

def normalize_lnu_table_block_layout(document_root, style_map=None, cfg=None, runtime=None):
    (
        NSMAP,
        W_NS,
        collect_table_blocks,
        ensure_ppr,
        get_or_create,
        get_paragraph_text,
        resolve_fix_cfg,
        set_attr,
    ) = require(
        "NSMAP",
        "W_NS",
        "collect_table_blocks",
        "ensure_ppr",
        "get_or_create",
        "get_paragraph_text",
        "resolve_fix_cfg",
        "set_attr",
    )
    """统一表块上下留白，并保证表题紧贴表体。"""
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    gap_twips = int(
        cfg.get("table_blank_line_twips", cfg.get("figure_blank_line_twips", cfg.get("body_line", 360) or 360))
    )
    blank_line_mode = str(cfg.get("table_blank_line_mode", "spacing") or "spacing")
    paragraph_tag = f"{{{W_NS}}}p"
    changed = 0

    def _is_blank_paragraph(elem):
        return (
            elem.tag == paragraph_tag
            and elem.find(".//w:drawing", NSMAP) is None
            and not get_paragraph_text(elem).strip()
        )

    def _make_blank_gap_paragraph():
        p_elem = ET.Element(paragraph_tag)
        p_pr = ensure_ppr(p_elem)
        spacing = get_or_create(p_pr, "w:spacing")
        set_attr(spacing, "before", "0")
        set_attr(spacing, "after", "0")
        set_attr(spacing, "line", str(gap_twips))
        set_attr(spacing, "lineRule", "auto")
        return p_elem

    while True:
        blocks = [block for block in collect_table_blocks(document_root, style_map or {}) if block.get("section") == "body"]
        if not blocks:
            break

        moved = False
        for block in reversed(blocks):
            body_children = list(body)
            child_index = {id(elem): idx for idx, elem in enumerate(body_children)}
            caption_elem = block["caption"].elem
            table_elem = block["table"]
            last_elem = block["last_elem"]
            caption_idx = child_index.get(id(caption_elem))
            table_idx = child_index.get(id(table_elem))
            end_idx = child_index.get(id(last_elem))
            if caption_idx is None or table_idx is None or end_idx is None:
                continue

            while caption_idx > 0 and _is_blank_paragraph(body_children[caption_idx - 1]):
                body.remove(body_children[caption_idx - 1])
                del body_children[caption_idx - 1]
                caption_idx -= 1
                table_idx -= 1
                end_idx -= 1
                changed += 1
                moved = True

            while caption_idx + 1 < table_idx and _is_blank_paragraph(body_children[caption_idx + 1]):
                body.remove(body_children[caption_idx + 1])
                del body_children[caption_idx + 1]
                table_idx -= 1
                end_idx -= 1
                changed += 1
                moved = True

            if blank_line_mode == "blank_paragraph":
                blank_after_count = 0
                scan_idx = end_idx + 1
                while scan_idx < len(body_children) and _is_blank_paragraph(body_children[scan_idx]):
                    blank_after_count += 1
                    scan_idx += 1
                while blank_after_count > 1:
                    body.remove(body_children[end_idx + 2])
                    del body_children[end_idx + 2]
                    blank_after_count -= 1
                    changed += 1
                    moved = True
            else:
                while end_idx + 1 < len(body_children) and _is_blank_paragraph(body_children[end_idx + 1]):
                    body.remove(body_children[end_idx + 1])
                    del body_children[end_idx + 1]
                    changed += 1
                    moved = True

            prev_idx = caption_idx - 1
            while prev_idx >= 0 and _is_blank_paragraph(body_children[prev_idx]):
                prev_idx -= 1
            next_idx = end_idx + 1
            if blank_line_mode != "blank_paragraph":
                while next_idx < len(body_children) and _is_blank_paragraph(body_children[next_idx]):
                    next_idx += 1

            prev_elem = body_children[prev_idx] if prev_idx >= 0 else None
            next_elem = body_children[next_idx] if next_idx < len(body_children) else None

            prev_after = _get_paragraph_spacing_twips(prev_elem, "after") if prev_elem is not None and prev_elem.tag == paragraph_tag else 0
            target_before = max(0, gap_twips - prev_after) if prev_elem is not None else 0

            current_caption_before = _get_paragraph_spacing_twips(caption_elem, "before")
            current_caption_after = _get_paragraph_spacing_twips(caption_elem, "after")
            if current_caption_before != target_before or current_caption_after != 0:
                _set_paragraph_spacing_attrs(caption_elem, before=target_before, after=0)
                changed += 1

            if block["notes"]:
                next_before = (
                    _get_paragraph_spacing_twips(next_elem, "before")
                    if next_elem is not None and next_elem.tag == paragraph_tag
                    else 0
                )
                target_note_after = max(0, gap_twips - next_before) if next_elem is not None else 0
                for offset, note in enumerate(block["notes"]):
                    note_elem = note.elem
                    desired_after = target_note_after if offset == len(block["notes"]) - 1 else 0
                    note_before = _get_paragraph_spacing_twips(note_elem, "before")
                    note_after = _get_paragraph_spacing_twips(note_elem, "after")
                    if note_before != 0 or note_after != desired_after:
                        _set_paragraph_spacing_attrs(note_elem, before=0, after=desired_after)
                        changed += 1
            elif next_elem is not None and next_elem.tag == paragraph_tag:
                next_before = _get_paragraph_spacing_twips(next_elem, "before")
                if blank_line_mode == "blank_paragraph":
                    if _is_blank_paragraph(next_elem):
                        gap_spacing = next_elem.find("w:pPr/w:spacing", NSMAP)
                        gap_line = gap_spacing.get(f"{{{W_NS}}}line") if gap_spacing is not None else None
                        if gap_line != str(gap_twips):
                            _set_paragraph_spacing_attrs(next_elem, before=0, after=0, line=gap_twips)
                            changed += 1
                    else:
                        body.insert(next_idx, _make_blank_gap_paragraph())
                        changed += 1
                        moved = True
                        break
                else:
                    desired_before = max(next_before, gap_twips)
                    if next_before != desired_before:
                        _set_paragraph_spacing_attrs(next_elem, before=desired_before)
                        changed += 1

        if not moved:
            break

    return changed

def protect_object_blocks_from_pagination(document_root, style_map=None, cfg=None, runtime=None):
    (
        NSMAP,
        collect_figure_blocks,
        collect_table_blocks,
        resolve_fix_cfg,
    ) = require(
        "NSMAP",
        "collect_figure_blocks",
        "collect_table_blocks",
        "resolve_fix_cfg",
    )
    """为普通图块和短表块补齐分页保护属性，尽量避免题注与对象或短表主体跨页拆开。"""
    cfg = resolve_fix_cfg(cfg=cfg, runtime=runtime)
    changed = 0
    continuation_min_rows = int(cfg.get("table_continuation_min_rows", 6) or 6)

    for block in collect_figure_blocks(document_root, style_map or {}):
        if block.get("section") not in {"body", "appendix"}:
            continue
        block_paragraphs = [
            block["image"],
            block["caption"].elem,
            *[caption.elem for caption in block.get("english_captions", [])],
            *[note.elem for note in block["notes"]],
        ]
        for idx, p_elem in enumerate(block_paragraphs):
            changed += _set_paragraph_pagination_flags(
                p_elem,
                keep_next=idx < len(block_paragraphs) - 1,
                keep_lines=True,
                page_break_before=False,
            )

    for block in collect_table_blocks(document_root, style_map or {}):
        if block.get("section") not in {"body", "appendix"}:
            continue
        caption_chain = [block["caption"].elem, *[caption.elem for caption in block.get("english_captions", [])]]
        for p_elem in caption_chain:
            changed += _set_paragraph_pagination_flags(
                p_elem,
                keep_next=True,
                keep_lines=True,
                page_break_before=False,
            )
        row_elems = block["table"].findall("w:tr", NSMAP)
        short_table = len(row_elems) < continuation_min_rows
        for row_idx, tr_elem in enumerate(row_elems):
            changed += _set_table_row_cant_split(tr_elem, True)
            row_paragraphs = tr_elem.findall(".//w:p", NSMAP)
            row_keep_next = short_table and (row_idx < len(row_elems) - 1 or bool(block["notes"]))
            for p_elem in row_paragraphs:
                changed += _set_paragraph_pagination_flags(
                    p_elem,
                    keep_next=row_keep_next,
                    keep_lines=True,
                    page_break_before=False,
                )
        note_paragraphs = [note.elem for note in block["notes"]]
        for idx, p_elem in enumerate(note_paragraphs):
            changed += _set_paragraph_pagination_flags(
                p_elem,
                keep_next=idx < len(note_paragraphs) - 1,
                keep_lines=True,
                page_break_before=False,
            )

    return changed

def rebalance_lnu_result_object_flow(document_root, style_map=None, cfg=None, runtime=None):
    (
        NSMAP,
        W_NS,
        _caption_reference_candidates,
        build_document_model,
        collect_figure_blocks,
        collect_table_blocks,
        get_paragraph_text,
    ) = require(
        "NSMAP",
        "W_NS",
        "_caption_reference_candidates",
        "build_document_model",
        "collect_figure_blocks",
        "collect_table_blocks",
        "get_paragraph_text",
    )
    """按同小节内已存在的图表引用，前移对象块以减少跨页留白。默认关闭，仅显式启用。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return 0

    paragraph_tag = f"{{{W_NS}}}p"
    table_tag = f"{{{W_NS}}}tbl"
    caption_pattern = re.compile(r"^(图|表)\s*(\d+(?:[.\-]\d+)+)")
    heading_kinds = {"h1", "h2", "h3", "h4"}
    changed = 0

    def _caption_candidates(text: str) -> set[str]:
        match = caption_pattern.match((text or "").strip())
        if match is None:
            return set()
        prefix, number = match.groups()
        return _caption_reference_candidates(prefix, number)

    def _paragraph_is_heading(elem, node_by_elem_id) -> bool:
        node = node_by_elem_id.get(id(elem))
        return bool(node is not None and node.section == "body" and node.kind in heading_kinds)

    def _paragraph_is_body(elem, node_by_elem_id) -> bool:
        node = node_by_elem_id.get(id(elem))
        return bool(node is not None and node.section == "body" and node.kind == "body")

    def _collect_blocks(current_style_map):
        body_children = list(body)
        child_index = {id(elem): idx for idx, elem in enumerate(body_children)}
        figure_blocks = []
        for block in collect_figure_blocks(document_root, current_style_map):
            if block.get("section") != "body":
                continue
            start_idx = child_index.get(id(block["image"]))
            end_idx = child_index.get(id(block["last_elem"]))
            if start_idx is None or end_idx is None:
                continue
            candidates = _caption_candidates(block["caption"].text)
            if not candidates:
                continue
            figure_blocks.append(
                {
                    "kind": "figure",
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "caption_text": block["caption"].text,
                    "candidates": candidates,
                }
            )
        table_blocks = []
        for block in collect_table_blocks(document_root, current_style_map):
            if block.get("section") != "body":
                continue
            start_idx = child_index.get(id(block["caption"].elem))
            end_idx = child_index.get(id(block["last_elem"]))
            if start_idx is None or end_idx is None:
                continue
            candidates = _caption_candidates(block["caption"].text)
            if not candidates:
                continue
            table_blocks.append(
                {
                    "kind": "table",
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "caption_text": block["caption"].text,
                    "candidates": candidates,
                }
            )
        return sorted(figure_blocks + table_blocks, key=lambda item: item["start_idx"])

    while True:
        model = build_document_model(document_root, style_map or {})
        node_by_elem_id = {id(node.elem): node for node in model.paragraphs}
        body_children = list(body)
        blocks = _collect_blocks(style_map or {})
        moved = False

        for block in blocks:
            start_idx = block["start_idx"]
            end_idx = block["end_idx"]
            candidates = block["candidates"]

            section_start = 0
            for idx in range(start_idx - 1, -1, -1):
                elem = body_children[idx]
                if elem.tag == paragraph_tag and _paragraph_is_heading(elem, node_by_elem_id):
                    section_start = idx + 1
                    break

            section_end = len(body_children)
            for idx in range(end_idx + 1, len(body_children)):
                elem = body_children[idx]
                if elem.tag == paragraph_tag and _paragraph_is_heading(elem, node_by_elem_id):
                    section_end = idx
                    break

            last_ref_idx = None
            for idx in range(section_start, start_idx):
                elem = body_children[idx]
                if elem.tag != paragraph_tag or not _paragraph_is_body(elem, node_by_elem_id):
                    continue
                node = node_by_elem_id.get(id(elem))
                compact_text = getattr(node, "compact_text", re.sub(r"[\s\u3000]+", "", get_paragraph_text(elem)))
                if any(candidate in compact_text for candidate in candidates):
                    last_ref_idx = idx

            if last_ref_idx is None or last_ref_idx + 1 >= start_idx:
                continue

            intervening = body_children[last_ref_idx + 1 : start_idx]
            if not any(elem.tag == table_tag or (elem.tag == paragraph_tag and elem.find(".//w:drawing", NSMAP) is not None) for elem in intervening):
                continue

            move_slice = body_children[start_idx : end_idx + 1]
            anchor_elem = body_children[last_ref_idx]
            for elem in move_slice:
                body.remove(elem)

            insert_pos = list(body).index(anchor_elem) + 1
            for offset, elem in enumerate(move_slice):
                body.insert(insert_pos + offset, elem)

            changed += 1
            moved = True
            break

        if not moved:
            break

    return changed
