from __future__ import annotations

from dataclasses import dataclass
import re
import zipfile
import xml.etree.ElementTree as ET

from citation_text_utils import (
    CITATION_NUMBER_GROUP_RE as _CITATION_NUM_RE,
    citation_numbers_from_group as _expand_citation_numbers,
)
from _thesis_utils import (
    M_NS,
    NSMAP,
    W_NS,
    _looks_like_toc_entry,
    build_document_sections,
    collect_figure_blocks,
    collect_table_blocks,
    get_paragraph_text,
    paragraph_has_drawing,
)
from backmatter_title_utils import (
    detect_backmatter_bucket,
    heading_title_contains_conclusion,
    is_abstract_cn_title,
    is_abstract_en_title,
    is_acknowledgement_title,
    is_backmatter_pagebreak_title,
    is_lnu_title01_single_form,
    is_toc_title,
)
from frontmatter_utils import (
    has_toc_field_instr,
    is_cn_keywords_paragraph_text,
    is_keywords_text,
    is_toc_entry_style as is_toc_entry_style_shared,
    is_toc_generated_style_id,
    is_toc_heading_style as is_toc_heading_style_shared,
    is_toc_structural_style_id,
)
from reference_numbering_utils import (
    has_valid_reference_tab_stop,
    is_plain_reference_number_prefix,
    paragraph_has_reference_number_tab,
    paragraph_has_reference_tab,
    parse_reference_number_prefix,
    reference_paragraph_text_with_tabs,
    reference_number_has_compact_separator,
    reference_number_has_space_separator,
    reference_number_has_tab_separator,
)
from reference_section_utils import iter_reference_section_contexts
from sections._xml_helpers import (
    paragraph_onoff_enabled as _paragraph_onoff_enabled,
    table_row_cant_split_enabled as _table_row_cant_split_enabled,
)
from thesis_rules.audit_checkers import *
from thesis_rules.audit_common import _caption_title_runs, _is_toc_entry_style, _is_toc_heading_style, check_heading_num_space
from thesis_rules.audit_common import _has_half_width_punct_in_cjk_context
from thesis_rules.audit_checkers import (
    _needs_cjk_latin_space,
    _needs_num_cjk_space,
)

WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_CAPTION_SOFT_BREAK_ALLOWED_MODULES = {
    "body_caption",
    "appendix_caption",
    "body_caption_en",
    "appendix_caption_en",
    "body_caption_note",
    "appendix_caption_note",
}
_UNIT_RE = re.compile(r"(?<![0-9A-Za-z])(\d+(?:\.\d+)?)([A-Za-z]{1,4})(?![0-9A-Za-z])")
_CELSIUS_RE = re.compile(r"(?<![0-9A-Za-z])(\d+(?:\.\d+)?)(℃|°C)")
_PERCENT_RE = re.compile(r"(?<![0-9A-Za-z])(\d+(?:\.\d+)?)([%％])")
KNOWN_UNITS = frozenset({
    "g", "mg", "kg",
    "L", "mL",
    "m", "cm", "mm", "nm",
    "s", "min", "h",
    "V",
    "mol", "mmol",
    "Pa", "kPa", "MPa",
    "Hz", "kHz", "MHz",
    "kJ", "kDa", "Da",
    "rpm",
    "℃", "°C",
})
_ENGLISH_DECADE_RE = re.compile(r"(?:18|19|20)\d{2}")
_PANEL_LABEL_PREFIX_RE = re.compile(r"(?:图|表)\s*$|(?:fig(?:ure)?|table)\.?\s*$", re.IGNORECASE)


def is_lnu_unit_suffix(number: str, unit: str, *, prefix: str = "") -> bool:
    return (
        unit in KNOWN_UNITS
        and not (unit == "s" and _ENGLISH_DECADE_RE.fullmatch(number))
        and not (len(unit) == 1 and _PANEL_LABEL_PREFIX_RE.search(prefix))
    )


def is_lnu_identifier_position(text: str, index: int) -> bool:
    prefix = re.split(r"\s", text[:index])[-1].lower()
    return (
        "://" in prefix
        or "doi.org/" in prefix
        or prefix.startswith("doi:")
        or re.match(r"10\.\d{4,9}/", prefix) is not None
    )


def iter_lnu_unit_text_runs(paragraph):
    simple_field_runs = {
        id(run)
        for field in paragraph.findall(".//w:fldSimple", NSMAP)
        for run in field.findall(".//w:r", NSMAP)
    }
    field_depth = 0
    for run in paragraph.findall(".//w:r", NSMAP):
        field_kinds = [get_w_attr(field, "fldCharType") for field in run.findall("w:fldChar", NSMAP)]
        field_depth += field_kinds.count("begin")
        vert_align = run.find("w:rPr/w:vertAlign", NSMAP)
        protected = (
            id(run) in simple_field_runs
            or field_depth > 0
            or get_w_attr(vert_align, "val") == "superscript"
        )
        if not protected:
            yield run
        field_depth = max(0, field_depth - field_kinds.count("end"))


def _iter_lnu_unit_flow(element, safe_run_ids):
    for child in list(element):
        if child.tag in {
            f"{{{M_NS}}}oMath",
            f"{{{M_NS}}}oMathPara",
            f"{{{W_NS}}}fldSimple",
        }:
            yield None
        elif child.tag == f"{{{W_NS}}}r":
            yield child if id(child) in safe_run_ids and child.find("w:t", NSMAP) is not None else None
        else:
            yield from _iter_lnu_unit_flow(child, safe_run_ids)


def lnu_unit_run_groups(paragraph):
    safe_run_ids = {id(run) for run in iter_lnu_unit_text_runs(paragraph)}
    groups = {}
    group_index = 0
    for run in _iter_lnu_unit_flow(paragraph, safe_run_ids):
        if run is None:
            group_index += 1
        else:
            groups[id(run)] = group_index
    return groups


def _lnu_unit_check_text(paragraph, fallback_text):
    if paragraph is None:
        return fallback_text
    run_groups = lnu_unit_run_groups(paragraph)
    parts = []
    previous_group = None
    for run in paragraph.findall(".//w:r", NSMAP):
        group = run_groups.get(id(run))
        if group is None:
            continue
        run_text = "".join(text.text or "" for text in run.findall("w:t", NSMAP))
        if run_text:
            if previous_group is not None and group != previous_group:
                parts.append(" ")
            parts.append(run_text)
            previous_group = group
    return "".join(parts)


_EQ_EXPLANATION_PREFIXES = ("其中", "式中")
_EQ_EXPLANATION_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9/])([A-Za-zΑ-Ωα-ωφΦ](?:\d+|[tr]))(?![A-Za-z0-9])")
_TITLE_CASE_SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "nor",
    "of",
    "on",
    "or",
    "over",
    "per",
    "the",
    "to",
    "vs",
    "via",
    "with",
    "without",
}

def _run_is_subscript(run_elem):
    vert = run_elem.find("w:rPr/w:vertAlign", NSMAP)
    return vert is not None and get_w_attr(vert, "val") == "subscript"


def _equation_explanation_run_items(p_elem):
    items = []
    offset = 0
    for run_elem in p_elem.findall("w:r", NSMAP):
        text = get_run_text(run_elem)
        if not text:
            continue
        items.append(
            {
                "run": run_elem,
                "text": text,
                "start": offset,
                "end": offset + len(text),
            }
        )
        offset += len(text)
    return items


def _run_item_at_offset(items, offset):
    for item in items:
        if item["start"] <= offset < item["end"]:
            return item
    return None


def _paragraph_evidence(ctx, tokens):
    return {
        "paragraph_index": ctx["index"],
        "section": ctx.get("section"),
        "module": ctx.get("module"),
        "kind": ctx.get("kind"),
        "text": ctx.get("text", ""),
        "tokens": tokens,
    }


def _equation_explanation_bad_tokens(p_elem):
    paragraph_text = get_paragraph_text(p_elem).strip()
    if not paragraph_text.startswith(_EQ_EXPLANATION_PREFIXES):
        return []
    items = _equation_explanation_run_items(p_elem)
    if not items:
        return []
    bad_tokens = []
    compact = "".join(item["text"] for item in items)
    for match in _EQ_EXPLANATION_TOKEN_RE.finditer(compact):
        token = match.group(1)
        suffix_start = match.start(1) + 1
        suffix_end = match.end(1)
        suffix_items = []
        for offset in range(suffix_start, suffix_end):
            item = _run_item_at_offset(items, offset)
            if item is not None and item not in suffix_items:
                suffix_items.append(item)
        if not suffix_items or any(not _run_is_subscript(item["run"]) for item in suffix_items):
            bad_tokens.append(
                {
                    "text": token,
                    "bad_part": token[1:],
                    "actual": "baseline",
                    "expected": "subscript",
                    "start": match.start(1),
                    "end": match.end(1),
                }
            )
    return bad_tokens


def check_lnu_eq05(document_root, contexts, style_map, cfg):
    """LNU_EQ05: 公式说明段中的变量后缀应使用下标。"""
    bad_positions = []
    samples = []
    evidence = []
    for ctx in contexts:
        if ctx.get("in_table") or ctx.get("kind") != "body":
            continue
        elem = ctx.get("elem")
        if elem is None:
            continue
        bad_tokens = _equation_explanation_bad_tokens(elem)
        if not bad_tokens:
            continue
        bad_positions.append(ctx["index"])
        if len(samples) < 5:
            shown = "、".join(token["text"] for token in bad_tokens[:4])
            samples.append(f"第{ctx['index']}段公式说明变量后缀未设为下标：{shown}")
        evidence.append(_paragraph_evidence(ctx, bad_tokens))
    if bad_positions:
        issues = [f"{len(bad_positions)} 个公式说明段存在变量下标格式问题。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions), evidence
    return True, [], "全部公式说明变量下标"

def check_lnu_ack(document_root, contexts, style_map, cfg):
    ack_font = cfg.get("ack_font")
    ack_size = cfg.get("ack_size", 24) or 24
    ack_line = cfg.get("ack_line", 360) or 360
    ack_required = bool(cfg.get("acknowledgement_required"))
    if not ack_font and not ack_required:
        return True, [], ""

    in_ack_section = False
    found_ack_heading = False
    bad_positions = []
    samples = []

    for ctx in contexts:
        text = ctx["text"].strip()
        if is_acknowledgement_title(text):
            found_ack_heading = True
            in_ack_section = True
            continue

        if not in_ack_section:
            continue

        if ctx["kind"] in {"h1", "h2", "h3", "h4", "reference"}:
            break
        if ctx["kind"] != "body":
            continue

        para_issues = []
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            east_asia = get_effective_run_font(run_elem, style_map, ctx["elem"], "eastAsia")
            ascii_font = get_effective_run_font(run_elem, style_map, ctx["elem"], "ascii")
            hansi_font = get_effective_run_font(run_elem, style_map, ctx["elem"], "hAnsi")
            size_val = get_effective_run_size(run_elem, style_map, ctx["elem"])
            if east_asia != ack_font:
                para_issues.append(f"eastAsia字体={east_asia}，应为{ack_font}")
            if ascii_font and ascii_font != "Times New Roman":
                para_issues.append(f"ascii字体={ascii_font}")
            if hansi_font and hansi_font != "Times New Roman":
                para_issues.append(f"hAnsi字体={hansi_font}")
            if size_val is not None and size_val != ack_size:
                para_issues.append(f"字号={size_val}，应为{ack_size}")
            if para_issues:
                break

        line_val = get_paragraph_line_spacing(ctx["elem"], style_map)
        if line_val is not None and abs(line_val - ack_line) > 20:
            para_issues.append(f"行距={line_val}，应为{ack_line}")

        if para_issues:
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段 {'; '.join(para_issues[:2])}")

    if not found_ack_heading:
        if ack_required:
            return False, ["文档缺少致谢章节。"], "致谢"
        return True, [], "未发现致谢章节"
    if bad_positions:
        issues = [f"{len(bad_positions)} 个致谢正文段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部致谢正文"

def check_lnu_f01(document_root, contexts, style_map, cfg):
    """LNU_F01: 图题编号格式应为 图X.X 后接两个半角空格。"""
    gap_spaces = int((cfg or {}).get("caption_label_gap_spaces", 2) or 2)
    pattern = re.compile(rf"^图\s*\d+\.\d+{' ' * gap_spaces}.+")
    issues = []
    for ctx in contexts:
        text = ctx.get("text", "").strip()
        if text.startswith("图") and re.search(r"\d", text):
            if not pattern.match(text):
                issues.append(text[:40])
    passed = len(issues) == 0
    affected = "; ".join(issues[:3]) if issues else ""
    return passed, issues, affected

def check_lnu_f02(document_root, contexts, style_map, cfg):
    """LNU_F02: 表题编号格式应为 表X.X 后接两个半角空格。"""
    gap_spaces = int((cfg or {}).get("caption_label_gap_spaces", 2) or 2)
    pattern = re.compile(rf"^表\s*\d+\.\d+{' ' * gap_spaces}.+")
    issues = []
    for ctx in contexts:
        text = ctx.get("text", "").strip()
        if text.startswith("表") and re.search(r"\d", text):
            if not pattern.match(text):
                issues.append(text[:40])
    passed = len(issues) == 0
    affected = "; ".join(issues[:3]) if issues else ""
    return passed, issues, affected

def check_lnu_f03(document_root, contexts, style_map, cfg):
    """LNU_F03: 图块前后应与正文留一空行。"""

    def _is_blank_layout_paragraph(p_elem):
        return p_elem is not None and not paragraph_has_drawing(p_elem) and not get_paragraph_text(p_elem).strip()

    gap_twips = cfg.get("figure_blank_line_twips") or cfg.get("body_line") or 360
    blocks = [block for block in collect_figure_blocks(document_root, style_map) if block.get("section") == "body"]
    if not blocks:
        return True, [], "文档无正文图块"

    issues = []
    affected_positions = []
    for block in blocks:
        body_paragraphs = block["body_paragraphs"]
        prev_elem = body_paragraphs[block["image_index"] - 1] if block["image_index"] > 0 else None
        next_elem = body_paragraphs[block["end_index"] + 1] if block["end_index"] + 1 < len(body_paragraphs) else None

        total_before = (0 if _is_blank_layout_paragraph(prev_elem) else (get_paragraph_spacing_after(prev_elem) or 0)) + (get_paragraph_spacing_before(block["image"]) or 0)
        total_after = (get_paragraph_spacing_after(block["last_elem"]) or 0) + (0 if _is_blank_layout_paragraph(next_elem) else (get_paragraph_spacing_before(next_elem) or 0))
        before_ok = _is_blank_layout_paragraph(prev_elem) or total_before >= gap_twips
        after_ok = _is_blank_layout_paragraph(next_elem) or total_after >= gap_twips
        if before_ok and after_ok:
            continue

        caption_index = block["caption"].index
        if not before_ok:
            issues.append(f"第{caption_index}段对应图片与上文留白为 {total_before} twips，未满足一空行。")
        if not after_ok:
            issues.append(f"第{caption_index}段图块结束后与下文留白为 {total_after} twips，未满足一空行。")
        affected_positions.append(caption_index)

    if issues:
        header = f"{len(affected_positions)} 个图块前后留白不符合辽大要求。"
        return False, [header] + issues[:6], summarize_positions(affected_positions)
    return True, [], "全部正文图块前后留白正常"

def check_lnu_f05(document_root, contexts, style_map, cfg):
    """Compatibility no-op: LNU no longer forces prose references before captions."""
    return True, [], "图表题注前不强制补写“如图/如表所示”类正文引用"

def check_lnu_f06(document_root, contexts, style_map, cfg):
    """LNU_F06: 图题/表题、英文题名、说明性图注/表注版式。"""
    expected_caption_line = cfg.get("figure_caption_line") or 240
    expected_note_line = cfg.get("figure_note_line") or 240
    expected_size = cfg.get("caption_size") or 21

    issues = []
    affected_positions = []

    def _check_caption_like_paragraph(ctx, label, expected_line, expected_alignment, *, title_only=False):
        problems = []
        p_elem = ctx["elem"]
        if p_elem.find("w:pPr/w:numPr", NSMAP) is not None:
            problems.append("存在项目符号/编号")
        alignment = get_paragraph_alignment(p_elem, style_map)
        if expected_alignment == "center" and alignment != "center":
            problems.append("应居中")
        elif expected_alignment == "left":
            first_line = get_paragraph_first_line(p_elem)
            if alignment not in {"left", None}:
                problems.append("应顶格左对齐")
            if first_line not in {None, "0"}:
                problems.append(f"首行缩进应为0，实际={first_line}")
        line_val = get_paragraph_line_spacing(p_elem, style_map)
        if line_val != expected_line:
            problems.append(f"行距应为{expected_line}，实际={line_val}")
        run_elems = _caption_title_runs(p_elem) if title_only else get_non_empty_runs(p_elem)
        for run_elem in run_elems:
            if not get_run_text(run_elem).strip():
                continue
            east_asia = get_effective_run_font(run_elem, style_map, p_elem, attr_name="eastAsia")
            ascii_font = get_effective_run_font(run_elem, style_map, p_elem, attr_name="ascii")
            size = get_effective_run_size(run_elem, style_map, p_elem)
            if east_asia not in ("宋体", "SimSun") or ascii_font != "Times New Roman" or size != expected_size:
                problems.append(
                    f"字体/字号应为宋体+Times New Roman、五号，实际 eastAsia={east_asia} ascii={ascii_font} size={size}"
                )
                break
        if problems:
            issues.append(f"第{ctx['index']}段{label}版式异常：{'，'.join(problems)}。")
            affected_positions.append(ctx["index"])

    for ctx in contexts:
        if ctx.get("module") not in {"body_caption", "appendix_caption"}:
            continue
        _check_caption_like_paragraph(ctx, "图题/表题", expected_caption_line, "center", title_only=True)

    for ctx in contexts:
        if ctx.get("module") not in CAPTION_EN_MODULES:
            continue
        _check_caption_like_paragraph(ctx, "英文图题/表题", expected_note_line, "center")

    for ctx in contexts:
        if ctx.get("module") not in CAPTION_NOTE_MODULES:
            continue
        _check_caption_like_paragraph(ctx, "图注/表注", expected_note_line, "center")

    if issues:
        header = f"{len(affected_positions)} 个图题、英文题名或图注版式不符合辽大要求。"
        return False, [header] + issues[:6], summarize_positions(affected_positions)
    return True, [], "全部图题、英文题名与图注版式正常"

def check_lnu_ref01(document_root, contexts, style_map, cfg):
    """LNU_REF01: 参考文献标点应全用英文半角（不含全角标点）"""
    fullwidth = re.compile(r"[。，：；！？]")
    issues = []
    evidence = []
    for ctx in iter_reference_section_contexts(contexts, skip_empty=True):
        text = ctx.get("text", "").strip()
        matches = list(fullwidth.finditer(text))
        if matches:
            issues.append(text[:50])
            evidence.append(
                _paragraph_evidence(
                    ctx,
                    [
                        {
                            "text": match.group(0),
                            "bad_part": match.group(0),
                            "actual": "fullwidth_punctuation",
                            "expected": "halfwidth_punctuation",
                            "start": match.start(),
                            "end": match.end(),
                        }
                        for match in matches
                    ],
                )
            )
    passed = len(issues) == 0
    affected = "; ".join(issues[:3]) if issues else ""
    if passed:
        return passed, issues, affected
    return passed, issues, affected, evidence

def check_lnu_ref02(document_root, contexts, style_map, cfg):
    """LNU_REF02: 参考文献编号格式按 profile 要求处理。"""
    use_tab = bool(cfg.get("ref_use_tab", False))
    expect_space = bool(cfg.get("ref_number_trailing_space", not use_tab))
    issues = []
    evidence = []
    for ctx in iter_reference_section_contexts(contexts, skip_empty=True):
        text = ctx.get("text", "").strip()
        # 仅对以 [ 开头的条目校验编号格式，续行段落跳过
        if not re.match(r"^\[", text):
            continue
        number_prefix = parse_reference_number_prefix(text)
        token = None
        if number_prefix is None:
            issues.append(f"格式异常: {text[:40]}")
            token = {
                "text": text[: min(len(text), 8)],
                "bad_part": text[: min(len(text), 8)],
                "actual": "invalid_reference_number",
                "expected": "plain_reference_number",
                "start": 0,
                "end": min(len(text), 8),
            }
        elif number_prefix.has_leading_zero:
            issues.append(f"编号补零: {text[:40]}")
            number_text = f"[{number_prefix.number_text}]"
            token = {
                "text": number_text,
                "bad_part": number_prefix.number_text,
                "actual": "leading_zero",
                "expected": "plain_reference_number",
                "start": len(number_prefix.leading),
                "end": len(number_prefix.leading) + len(number_text),
            }
        elif not is_plain_reference_number_prefix(number_prefix):
            issues.append(f"格式异常: {text[:40]}")
            number_text = f"[{number_prefix.number_text}]"
            token = {
                "text": number_text,
                "bad_part": number_text,
                "actual": "invalid_reference_number",
                "expected": "plain_reference_number",
                "start": len(number_prefix.leading),
                "end": len(number_prefix.leading) + len(number_text),
            }
        elif use_tab:
            tab_min = cfg.get("ref_tab_min", cfg.get("ref_hanging", 420))
            has_valid_tab_stop = has_valid_reference_tab_stop(ctx["elem"], tab_min)
            has_number_tab = reference_number_has_tab_separator(text) or paragraph_has_reference_number_tab(ctx["elem"])
            inline_tab_count = reference_paragraph_text_with_tabs(ctx["elem"]).count("\t")
            if not has_number_tab:
                issues.append(f"编号后应使用制表符: {text[:40]}")
                number_text = f"[{number_prefix.number_text}]"
                token = {
                    "text": number_text + number_prefix.separator,
                    "bad_part": number_prefix.separator or "",
                    "actual": "missing_tab_after_reference_number",
                    "expected": "tab_after_reference_number",
                    "start": len(number_prefix.leading),
                    "end": len(number_prefix.leading) + len(number_text) + len(number_prefix.separator),
                }
            elif inline_tab_count != 1:
                issues.append(f"存在多余制表符: {text[:40]}")
                number_text = f"[{number_prefix.number_text}]"
                token = {
                    "text": number_text,
                    "bad_part": str(inline_tab_count),
                    "actual": "extra_reference_tabs",
                    "expected": "single_tab_after_reference_number",
                    "start": len(number_prefix.leading),
                    "end": len(number_prefix.leading) + len(number_text),
                }
            elif not has_valid_tab_stop:
                issues.append(f"缺少有效制表位: {text[:40]}")
                number_text = f"[{number_prefix.number_text}]"
                token = {
                    "text": number_text,
                    "bad_part": number_text,
                    "actual": "missing_valid_tab_stop",
                    "expected": "valid_reference_tab_stop",
                    "start": len(number_prefix.leading),
                    "end": len(number_prefix.leading) + len(number_text),
                }
        elif expect_space:
            if not reference_number_has_space_separator(text):
                issues.append(f"格式异常: {text[:40]}")
                number_text = f"[{number_prefix.number_text}]"
                token = {
                    "text": number_text + number_prefix.separator,
                    "bad_part": number_prefix.separator or "",
                    "actual": "invalid_reference_separator",
                    "expected": "space_after_reference_number",
                    "start": len(number_prefix.leading),
                    "end": len(number_prefix.leading) + len(number_text) + len(number_prefix.separator),
                }
        elif not reference_number_has_compact_separator(text):
            issues.append(f"格式异常: {text[:40]}")
            number_text = f"[{number_prefix.number_text}]"
            token = {
                "text": number_text + number_prefix.separator,
                "bad_part": number_prefix.separator,
                "actual": "invalid_reference_separator",
                "expected": "compact_reference_number",
                "start": len(number_prefix.leading),
                "end": len(number_prefix.leading) + len(number_text) + len(number_prefix.separator),
            }
        if token:
            evidence.append(_paragraph_evidence(ctx, [token]))
    passed = len(issues) == 0
    affected = "; ".join(issues[:3]) if issues else ""
    if passed:
        return passed, issues, affected
    return passed, issues, affected, evidence

def check_lnu_tb02(document_root, contexts, style_map, cfg):
    """LNU_TB02: 表格内容字号应为宋体五号（21 half-points）"""
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    issues = []
    tables = document_root.findall(f".//{{{W}}}tbl")
    for tbl in tables:
        for cell in tbl.findall(f".//{{{W}}}tc"):
            for p in cell.findall(f".//{{{W}}}p"):
                for r in p.findall(f".//{{{W}}}r"):
                    sz = r.find(f".//{{{W}}}rPr/{{{W}}}sz")
                    if sz is not None:
                        val = sz.get(f"{{{W}}}val")
                        if val and int(val) != 21:
                            t_elems = r.findall(f".//{{{W}}}t")
                            txt = "".join(t.text or "" for t in t_elems).strip()
                            if txt:
                                issues.append(f"字号{val} half-pts: {txt[:20]}")
    issues = issues[:5]
    passed = len(issues) == 0
    affected = "; ".join(issues) if issues else ""
    return passed, issues, affected

def check_lnu_abs01(document_root, contexts, style_map, cfg):
    """LNU_ABS01: 摘要标题格式。"""
    paras = document_root.findall(".//w:p", NSMAP)
    issues = []
    expected_sz = cfg.get("abstract_title_size") or 32
    expected_line = cfg.get("abstract_title_line") or 360
    expected_after = int((cfg.get("abstract_title_after_pt", 0) or 0) * 20)
    for p in paras:
        runs = p.findall(".//w:r", NSMAP)
        txt = "".join(get_run_text(r) for r in runs).strip()
        if is_abstract_cn_title(txt):
            for r in runs:
                if not get_run_text(r).strip():
                    continue
                sz_val = get_effective_run_size(r, style_map, p)
                if sz_val is not None and sz_val != expected_sz:
                    issues.append(f"「摘要」标题字号应为三号({expected_sz} half-pts)，实际={sz_val}")
                east_asia = get_effective_run_font(r, style_map, p, "eastAsia")
                expected_font = cfg.get("abstract_title_font", "黑体") or "黑体"
                if east_asia is not None and east_asia != expected_font:
                    issues.append(f"「摘要」标题字体应为{expected_font}，实际={east_asia}")
                break
            after_val = get_paragraph_spacing_after(p, style_map)
            if abs((after_val or 0) - expected_after) > 10:
                issues.append(f"「摘要」段后间距应为{expected_after} twips，实际={after_val or 0}")
            line_val = get_paragraph_line_spacing(p, style_map)
            if line_val is not None and abs(line_val - expected_line) > 20:
                issues.append(f"「摘要」标题行距应为{expected_line}，实际={line_val}")
            align = get_paragraph_alignment(p, style_map)
            if align != "center":
                issues.append(f"摘要标题应居中，实际={align or 'left(默认)'}")
    if not issues:
        return True, [], "摘要标题"
    return False, issues, "摘要标题段落"

def check_lnu_abs02(document_root, contexts, style_map, cfg):
    """LNU_ABS02: Abstract标题格式（TNR三号=32 half-pts，加粗，1.5倍行距）"""
    paras = document_root.findall(".//w:p", NSMAP)
    issues = []
    expected_line = cfg.get("abstract_title_line") or 360
    expected_after = int((cfg.get("abstract_title_after_pt", 0) or 0) * 20)
    expected_size = cfg.get("abstract_en_title_size", 32) or 32
    expected_font = cfg.get("abstract_en_title_font", "Times New Roman") or "Times New Roman"
    for p in paras:
        runs = p.findall(".//w:r", NSMAP)
        txt = "".join(get_run_text(r) for r in runs).strip()
        if txt.lower() == "abstract":
            visible_runs = [r for r in runs if get_run_text(r).strip()]
            for r in runs:
                if not get_run_text(r).strip():
                    continue
                sz_val = get_effective_run_size(r, style_map, p)
                if sz_val is not None and sz_val != expected_size:
                    issues.append(f"Abstract标题字号应为三号({expected_size} half-pts)，实际={sz_val}")
                ascii_font = get_effective_run_font(r, style_map, p, "ascii")
                if ascii_font is not None and ascii_font != expected_font:
                    issues.append(f"Abstract标题字体应为 {expected_font}，实际={ascii_font}")
            if visible_runs and not any(is_run_effectively_bold(r, style_map, p) for r in visible_runs):
                issues.append("Abstract标题应加粗")
            after_val = get_paragraph_spacing_after(p, style_map)
            if abs((after_val or 0) - expected_after) > 10:
                issues.append(f"Abstract标题段后间距应为{expected_after} twips，实际={after_val or 0}")
            line_val = get_paragraph_line_spacing(p, style_map)
            if line_val is not None and abs(line_val - expected_line) > 20:
                issues.append(f"Abstract标题行距应为{expected_line}(1.5倍)，实际={line_val}")
            break
    if not issues:
        return True, [], "Abstract标题"
    return False, issues, "Abstract标题段落"

def check_lnu_abs03(document_root, contexts, style_map, cfg):
    """LNU_ABS03: 英文摘要正文格式（TNR小四=24 half-pts）"""
    sections = build_document_sections(document_root, style_map)
    paras = sections.get("abstract_en", [])
    if not paras:
        return True, [], "英文摘要区段缺失，已跳过"

    issues = []
    expected_size = cfg.get("abstract_en_body_size", 24) or 24
    expected_font = cfg.get("abstract_en_body_ascii_font", "Times New Roman") or "Times New Roman"
    expected_line = cfg.get("abstract_en_body_line") or 240
    for p in paras:
        runs = p.findall(".//w:r", NSMAP)
        txt = "".join(get_run_text(r) for r in runs).strip()
        if is_abstract_en_title(txt):
            continue
        if not txt or is_keywords_text(txt, "abstract_en"):
            continue
        for r in runs:
            if not get_run_text(r).strip():
                continue
            sz_val = get_effective_run_size(r, style_map, p)
            if sz_val is not None and sz_val != expected_size:
                issues.append(f"英文摘要正文字号应为小四({expected_size} half-pts)，实际={sz_val}，段落：{txt[:30]}")
                break
            ascii_font = get_effective_run_font(r, style_map, p, "ascii")
            if ascii_font is not None and ascii_font != expected_font:
                issues.append(f"英文摘要正文字体应为 {expected_font}，实际={ascii_font}，段落：{txt[:30]}")
                break
        line_val = get_paragraph_line_spacing(p, style_map)
        if line_val is not None and abs(line_val - expected_line) > 20:
            issues.append(f"英文摘要正文行距应为{expected_line}，实际line={line_val}")
        if len(issues) >= 3:
            break
    if not issues:
        return True, [], "英文摘要正文"
    return False, issues, "Abstract正文段落"

def check_lnu_conc01(document_root, contexts, style_map, cfg):
    """LNU_CONC01: 末章标题必须包含'结论'"""
    h1_headings = [ctx for ctx in contexts if ctx.get("kind") == "h1"]
    if not h1_headings:
        return True, [], "无一级标题"
    body_chapters = [
        heading
        for heading in h1_headings
        if detect_backmatter_bucket(heading.get("text", ""), "h1") is None
    ]
    if not body_chapters:
        return True, [], "无正文章节"
    last_chapter = body_chapters[-1].get("text", "")
    if not heading_title_contains_conclusion(last_chapter):
        return False, [f"末章标题应含'结论与展望'，实际：{last_chapter}"], last_chapter
    return True, [], last_chapter

def check_lnu_s03(document_root, contexts, style_map, cfg):
    """LNU_S03: 参考文献/附录/致谢段落前必须有分页符。"""
    issues = []
    for i, ctx in enumerate(contexts):
        cur_elem = ctx.get("elem")
        p_style = cur_elem.find("w:pPr/w:pStyle", NSMAP) if cur_elem is not None else None
        if p_style is not None and is_toc_generated_style_id(get_w_attr(p_style, "val")):
            continue
        text = ctx.get("text", "").strip()
        if not is_backmatter_pagebreak_title(text):
            continue
        has_break = False
        # 方式1：本段设置了 pageBreakBefore
        if cur_elem is not None:
            ppr = cur_elem.find("w:pPr", NSMAP)
            if ppr is not None:
                pb = ppr.find("w:pageBreakBefore", NSMAP)
                if pb is not None:
                    val = get_w_attr(pb, "val")
                    if val not in ("0", "false", "False", "off"):
                        has_break = True
        # 方式2：前一段末尾有显式分页符 <w:br type="page">
        if not has_break and i > 0:
            prev_elem = contexts[i - 1].get("elem")
            if prev_elem is not None:
                for br in prev_elem.findall(".//w:br", NSMAP):
                    if get_w_attr(br, "type") == "page":
                        has_break = True
                        break
        if not has_break:
            issues.append(f"{text}前缺少分页符")
    return (len(issues) == 0), issues, "检查后置章节分页符"

def check_lnu_title01(document_root, contexts, style_map, cfg):
    """LNU_TITLE01: 摘要/目录/序言/致谢标题两字间应有两格"""
    issues = []
    evidence = []
    for ctx in contexts:
        paragraph_kind = ctx.get("kind")
        if paragraph_kind not in ("h1", "h2", "h3", "h4"):
            continue
        text = (ctx.get("text") or "").strip()
        if is_lnu_title01_single_form(text):
            issues.append(f"「{text}」标题两字间应有两个空格，如「摘  要」")
            evidence.append(
                _paragraph_evidence(
                    ctx,
                    [
                        {
                            "text": text,
                            "bad_part": text,
                            "actual": "single_form_title",
                            "expected": "two_spaces_between_title_chars",
                            "start": 0,
                            "end": len(text),
                        }
                    ],
                )
            )
    if not issues:
        return True, issues, "发现0处"
    return False, issues, f"发现{len(issues)}处", evidence

def check_lnu_tb03(document_root, contexts, style_map, cfg):
    """LNU_TB03: 表格内容应为单倍行距"""
    issues = []
    expected_line = parse_int((cfg or {}).get("table_cell_line")) or 240
    for tbl in get_non_equation_layout_tables(document_root):
        for cell in tbl.findall(".//w:tc", NSMAP):
            for p in cell.findall(".//w:p", NSMAP):
                line_val = get_paragraph_line_spacing(p, style_map)
                if line_val and line_val != expected_line:
                    issues.append(f"表格内容行距应为单倍({expected_line})，实际 line={line_val}")
    return (len(issues) == 0), issues, f"发现{len(issues)}处"

def check_lnu_tb04(document_root, contexts, style_map, cfg):
    """LNU_TB04: 表块与上下文应留一空行，表题需紧贴表体。"""

    def _is_blank_layout_paragraph(elem):
        return (
            elem is not None
            and elem.tag == f"{{{W_NS}}}p"
            and not paragraph_has_drawing(elem)
            and not get_paragraph_text(elem).strip()
        )

    gap_twips = cfg.get("table_blank_line_twips") or cfg.get("figure_blank_line_twips") or cfg.get("body_line") or 360
    blank_line_mode = str(cfg.get("table_blank_line_mode", "spacing") or "spacing")
    blocks = [block for block in collect_table_blocks(document_root, style_map) if block.get("section") == "body"]
    if not blocks:
        return True, [], "文档无正文表块"

    issues = []
    affected_positions = []
    for block in blocks:
        body_children = block["body_children"]
        caption_elem = block["caption"].elem
        caption_index = block["caption"].index
        caption_child_idx = block["caption_index"]
        end_child_idx = block["end_index"]
        prev_elem = body_children[caption_child_idx - 1] if caption_child_idx > 0 else None
        next_elem = None
        for scan_idx in range(end_child_idx + 1, len(body_children)):
            candidate = body_children[scan_idx]
            if candidate.tag == f"{{{W_NS}}}p" or candidate.tag == f"{{{W_NS}}}tbl":
                next_elem = candidate
                break

        prev_after = (get_paragraph_spacing_after(prev_elem) or 0) if prev_elem is not None and prev_elem.tag == f"{{{W_NS}}}p" else 0
        caption_before = get_paragraph_spacing_before(caption_elem) or 0
        total_before = (0 if _is_blank_layout_paragraph(prev_elem) else prev_after) + caption_before
        before_ok = _is_blank_layout_paragraph(prev_elem) or total_before >= gap_twips

        blank_between = block.get("blank_between", 0)
        caption_after = get_paragraph_spacing_after(caption_elem) or 0
        tight_ok = blank_between == 0 and caption_after == 0

        if next_elem is None:
            total_after = 0
            after_ok = True
        elif block["notes"]:
            last_note = block["notes"][-1].elem
            next_before = (get_paragraph_spacing_before(next_elem) or 0) if next_elem is not None and next_elem.tag == f"{{{W_NS}}}p" else 0
            note_after = get_paragraph_spacing_after(last_note) or 0
            total_after = note_after + (0 if _is_blank_layout_paragraph(next_elem) else next_before)
            after_ok = _is_blank_layout_paragraph(next_elem) or total_after >= gap_twips
        else:
            next_before = (get_paragraph_spacing_before(next_elem) or 0) if next_elem is not None and next_elem.tag == f"{{{W_NS}}}p" else 0
            total_after = 0 if _is_blank_layout_paragraph(next_elem) else next_before
            after_ok = _is_blank_layout_paragraph(next_elem) or total_after >= gap_twips

        if blank_line_mode == "blank_paragraph":
            before_ok = _is_blank_layout_paragraph(prev_elem) or total_before >= gap_twips
            after_ok = next_elem is None or _is_blank_layout_paragraph(next_elem) or total_after >= gap_twips

        if before_ok and tight_ok and after_ok:
            continue

        if not before_ok:
            issues.append(f"第{caption_index}段对应表块与上文留白为 {total_before} twips，未满足一空行。")
        if not tight_ok:
            if blank_between:
                issues.append(f"第{caption_index}段表题与表体之间存在 {blank_between} 个空白段，应紧贴表格。")
            elif caption_after:
                issues.append(f"第{caption_index}段表题段后为 {caption_after} twips，应为 0 以紧贴表格。")
        if not after_ok:
            issues.append(f"第{caption_index}段表块结束后与下文留白为 {total_after} twips，未满足一空行。")
        affected_positions.append(caption_index)

    if issues:
        header = f"{len(affected_positions)} 个表块版式不符合辽大要求。"
        return False, [header] + issues[:6], summarize_positions(affected_positions)
    return True, [], "全部正文表块留白与表题贴表正常"

def check_lnu_object_pagination(document_root, contexts, style_map, cfg):
    """LNU_F07: 图、图名、图注以及短表块应设置同页保护，降低跨页断裂风险。"""
    issues = []
    affected_positions = []
    continuation_min_rows = int((cfg or {}).get("table_continuation_min_rows", 6) or 6)

    for block in collect_figure_blocks(document_root, style_map):
        if block.get("section") not in {"body", "appendix"}:
            continue
        caption_index = block["caption"].index
        block_paragraphs = [
            block["image"],
            block["caption"].elem,
            *[caption.elem for caption in block.get("english_captions", [])],
            *[note.elem for note in block["notes"]],
        ]
        for idx, p_elem in enumerate(block_paragraphs):
            should_keep_next = idx < len(block_paragraphs) - 1
            if should_keep_next and not _paragraph_onoff_enabled(p_elem, "keepNext"):
                issues.append(f"第{caption_index}段对应图块缺少同页保护，图与图名/图注可能跨页断开。")
                affected_positions.append(caption_index)
                break
            if not _paragraph_onoff_enabled(p_elem, "keepLines"):
                issues.append(f"第{caption_index}段对应图块缺少段内不分页保护。")
                affected_positions.append(caption_index)
                break

    for block in collect_table_blocks(document_root, style_map):
        if block.get("section") not in {"body", "appendix"}:
            continue
        caption_index = block["caption"].index
        caption_chain = [block["caption"].elem, *[caption.elem for caption in block.get("english_captions", [])]]
        if any(not _paragraph_onoff_enabled(p_elem, "keepNext") for p_elem in caption_chain):
            issues.append(f"第{caption_index}段表题缺少同页保护，表题与表格可能跨页断开。")
            affected_positions.append(caption_index)
            continue

        rows = block["table"].findall("w:tr", NSMAP)
        short_table = len(rows) < continuation_min_rows
        for row_idx, tr_elem in enumerate(rows):
            if not _table_row_cant_split_enabled(tr_elem):
                issues.append(f"第{caption_index}段对应表格行缺少不跨页断行保护。")
                affected_positions.append(caption_index)
                break
            if not short_table:
                continue
            row_keep_next = row_idx < len(rows) - 1 or bool(block["notes"])
            if not row_keep_next:
                continue
            if any(not _paragraph_onoff_enabled(p, "keepNext") for p in tr_elem.findall(".//w:p", NSMAP)):
                issues.append(f"第{caption_index}段对应短表缺少同页保护，短表可能被拆到两页。")
                affected_positions.append(caption_index)
                break

    if issues:
        header = f"{len(set(affected_positions))} 个图表块缺少同页/跨页保护。"
        return False, [header] + issues[:6], summarize_positions(affected_positions)
    return True, [], "全部图表块已有同页/跨页保护"

def _paragraph_has_soft_break(p_elem):
    for br in p_elem.findall(".//w:br", NSMAP):
        br_type = get_w_attr(br, "type")
        if br_type not in {"page", "column"}:
            return True
    return p_elem.find(".//w:cr", NSMAP) is not None

def _is_allowed_caption_soft_break(ctx, cfg):
    if not bool((cfg or {}).get("preserve_caption_soft_line_breaks")):
        return False
    return ctx.get("module") in _CAPTION_SOFT_BREAK_ALLOWED_MODULES or ctx.get("kind") == "caption"

def check_lnu_fmt01(document_root, contexts, style_map, cfg):
    """LNU_FMT01: 正文不应使用软回车；图题/图注可用软回车分隔题名与分组说明。"""
    issues = []
    affected_positions = []
    for ctx in contexts:
        p_elem = ctx.get("elem")
        if p_elem is None:
            continue
        if ctx.get("section") in {"cover", "toc"}:
            continue
        if not _paragraph_has_soft_break(p_elem):
            continue
        if _is_allowed_caption_soft_break(ctx, cfg):
            continue
        issues.append(f"第{ctx['index']}段包含软回车，应用 Enter 分段而非 Shift+Enter 换行。")
        affected_positions.append(ctx["index"])
        if len(issues) >= 6:
            break

    if issues:
        header = f"{len(affected_positions)} 个段落使用了软回车。"
        return False, [header] + issues, summarize_positions(affected_positions)
    return True, [], "未发现软回车"

def check_lnu_fmt02(document_root, contexts, style_map, cfg):
    """LNU_FMT02: 图片应为嵌入型，表格应为无环绕。"""
    issues = []
    affected_positions = []

    for ctx in contexts:
        p_elem = ctx.get("elem")
        if p_elem is None:
            continue
        for drawing in p_elem.findall(".//w:drawing", NSMAP):
            if drawing.find(f"{{{WP_NS}}}anchor") is not None:
                issues.append(f"第{ctx['index']}段图片使用了浮动/环绕定位，应改为嵌入型。")
                affected_positions.append(ctx["index"])
                break
        if len(issues) >= 6:
            break

    if len(issues) < 6:
        for table_idx, table in enumerate(document_root.findall(".//w:tbl", NSMAP), start=1):
            tbl_pr = table.find("w:tblPr", NSMAP)
            if tbl_pr is None or tbl_pr.find("w:tblpPr", NSMAP) is None:
                continue
            issues.append(f"第{table_idx}个表格使用了环绕/浮动定位，应为无环绕。")
            affected_positions.append(table_idx)
            if len(issues) >= 6:
                break

    if issues:
        header = f"发现 {len(issues)} 处图片/表格环绕方式不符合辽大 checker 要求。"
        return False, [header] + issues, summarize_positions(affected_positions)
    return True, [], "图片均为嵌入型且表格无环绕"

def check_lnu_unit01(document_root, contexts, style_map, cfg):
    """LNU_UNIT01: 正文数字与单位、摄氏度、百分号之间应有半角空格。"""
    issues = []
    for ctx in contexts:
        if ctx.get("kind") != "body":
            continue
        text = _lnu_unit_check_text(ctx.get("elem"), ctx.get("text", ""))
        for m in list(_UNIT_RE.finditer(text)) + list(_CELSIUS_RE.finditer(text)):
            unit = m.group(2)
            valid_unit = is_lnu_unit_suffix(m.group(1), unit, prefix=text[:m.start()])
            if valid_unit and not is_lnu_identifier_position(text, m.start()):
                snippet = text[max(0, m.start() - 5):m.end() + 5]
                issues.append(f"数字后紧跟单位「{unit}」应加空格，上下文：{snippet}")
        for m in _PERCENT_RE.finditer(text):
            if is_lnu_identifier_position(text, m.start()):
                continue
            snippet = text[max(0, m.start() - 5):m.end() + 5]
            issues.append(f"数字后紧跟百分号「{m.group(2)}」应加空格，上下文：{snippet}")
    return (len(issues) == 0), issues, f"发现{len(issues)}处"

def check_lnu_ref03(document_root, contexts, style_map, cfg):
    """LNU_REF03: 参考文献字号五号(21)，行距1.5倍(360)，段前后0"""
    issues = []
    expected_size = cfg.get("ref_font_size") or 21
    expected_line = cfg.get("ref_line_spacing") or 360
    for ctx in iter_reference_section_contexts(contexts, skip_empty=True):
        p = ctx.get("elem")
        if p is None:
            continue
        line_val = get_paragraph_line_spacing(p, style_map)
        if line_val is not None and abs(line_val - expected_line) > 30:
            issues.append(f"参考文献行距应为{expected_line}(1.5倍)，实际={line_val}")
        before_val = get_paragraph_spacing_before(p, style_map)
        after_val = get_paragraph_spacing_after(p, style_map)
        if before_val not in (None, 0):
            issues.append(f"参考文献段前应为0，实际={before_val}")
        if after_val not in (None, 0):
            issues.append(f"参考文献段后应为0，实际={after_val}")
        jc_val = get_paragraph_alignment(p, style_map)
        if jc_val != "both":
            issues.append("参考文献条目应设置为两端对齐。")
        suppress_auto_hyphens = p.find("w:pPr/w:suppressAutoHyphens", NSMAP)
        suppress_val = get_w_attr(suppress_auto_hyphens, "val") if suppress_auto_hyphens is not None else None
        if suppress_auto_hyphens is None:
            p_style = get_w_attr(p.find("w:pPr/w:pStyle", NSMAP), "val")
            if p_style and p_style in style_map:
                suppress_val = style_map[p_style].get("suppressAutoHyphens")
        if (suppress_auto_hyphens is None and suppress_val is None) or suppress_val in {"0", "false", "False", "off"}:
            issues.append("参考文献条目应禁用自动断字。")
        for run in p.findall(".//w:r", NSMAP):
            if not get_run_text(run).strip():
                continue
            sz_val = get_effective_run_size(run, style_map, p)
            if sz_val is not None and sz_val != expected_size:
                issues.append(f"参考文献字号应为{expected_size}(五号)，实际={sz_val}")
                break
        if len(issues) >= 5:
            break
    return (len(issues) == 0), issues, f"发现{len(issues)}处"

def check_lnu_ref04(document_root, contexts, style_map, cfg):
    """LNU_REF04: 参考文献应带文献类型标识，如 [J]/[M]/[D]。"""
    if not cfg.get("ref_require_type_marker", False):
        return True, [], "当前 profile 不要求文献类型标识"
    issues = []
    pat = re.compile(r"\[[A-Z]\]")
    for ctx in iter_reference_section_contexts(contexts, skip_empty=True):
        text = ctx.get("text", "").strip()
        if text and not pat.search(text):
            issues.append(f"缺少文献类型标识: {text[:60]}")
        if len(issues) >= 5:
            break
    return (len(issues) == 0), issues, f"发现{len(issues)}处"

@dataclass(frozen=True)
class ReferenceStyleFinding:
    index: int
    number: str
    title: str
    title_style: str | None
    journal: str | None
    journal_style: str | None

_REFERENCE_PREFIX_RE = re.compile(r"^\s*\[(\d+)\]\s*(.+)$")

_REFERENCE_TYPE_RE = re.compile(r"\[([JMDCP])\]")

def _split_reference_title_and_journal(text):
    match = _REFERENCE_PREFIX_RE.match(text or "")
    if match is None:
        return None
    number, payload = match.groups()
    type_match = _REFERENCE_TYPE_RE.search(payload)
    if type_match is None:
        return None
    before_type = payload[: type_match.start()].strip(" .")
    after_type = payload[type_match.end() :].strip()
    after_type = re.sub(r"^[.。]\s*", "", after_type)
    title_match = re.search(r"\.\s*([^.;。；]+)$", before_type)
    title = title_match.group(1).strip(" .") if title_match is not None else before_type
    if not title or not re.search(r"[A-Za-z]", title):
        return None
    journal = None
    if type_match.group(1) == "J":
        journal = re.split(r",\s*\d{4}\b|,\s*\d+\b", after_type, maxsplit=1)[0].strip(" ,")
        journal = journal or None
    return number, title, journal

def _classify_reference_title_style(title):
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", title or "")
    words = [word for word in words if len(word) > 1]
    if len(words) < 3:
        return None
    content_words = [word for word in words if word.lower() not in _TITLE_CASE_SMALL_WORDS]
    if not content_words:
        return None
    capitalized_content = sum(1 for word in content_words if word[0].isupper())
    lowercase_later_words = sum(1 for word in words[1:] if word[0].islower())
    if capitalized_content >= max(3, len(content_words) - 1):
        return "Title Case"
    if words[0][0].isupper() and lowercase_later_words >= max(2, len(words[1:]) - 1):
        return "sentence case"
    return None

def _classify_journal_name_style(journal):
    if not journal or not re.search(r"[A-Za-z]", journal):
        return None
    if "." in journal:
        return "缩写"
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", journal)
    if len(words) >= 2:
        return "全称"
    return None

def _collect_reference_style_findings(contexts):
    findings = []
    for ctx in iter_reference_section_contexts(contexts, skip_empty=True):
        parsed = _split_reference_title_and_journal(ctx.get("text", ""))
        if parsed is None:
            continue
        number, title, journal = parsed
        findings.append(
            ReferenceStyleFinding(
                index=ctx["index"],
                number=number,
                title=title,
                title_style=_classify_reference_title_style(title),
                journal=journal,
                journal_style=_classify_journal_name_style(journal),
            )
        )
    return findings

def check_lnu_ref06(document_root, contexts, style_map, cfg):
    """LNU_REF06: 参考文献英文题名大小写和期刊名全称/缩写风格应统一，报告人工确认清单。"""
    findings = _collect_reference_style_findings(contexts)
    title_styles = {finding.title_style for finding in findings if finding.title_style is not None}
    journal_styles = {finding.journal_style for finding in findings if finding.journal_style is not None}
    target_title_style = (cfg or {}).get("reference_title_case_style")
    target_journal_style = (cfg or {}).get("reference_journal_name_style")
    issues = []
    affected_positions = set()

    if target_title_style in {"sentence_case", "title_case"}:
        expected_style = "sentence case" if target_title_style == "sentence_case" else "Title Case"
        mismatches = [
            finding
            for finding in findings
            if finding.title_style is not None and finding.title_style != expected_style
        ]
        if mismatches:
            issues.append(
                f"题名大小写目标风格为 {expected_style}，发现不符合目标风格的英文题名。"
                "本工具只报告，不自动改写专有名词、缩写、物种名或化学名。"
            )
            for finding in mismatches[:6]:
                affected_positions.add(finding.index)
                issues.append(
                    f"  [{finding.number}] 题名「{finding.title}」；当前判断：{finding.title_style}。"
                )

    if len(title_styles) > 1:
        title_items = [finding for finding in findings if finding.title_style is not None]
        issues.append(
            "题名大小写风格不统一：同一参考文献列表中同时出现 Title Case 和 sentence case。"
            "建议统一为其中一种；本工具只报告，不自动改写专有名词、缩写、物种名或化学名。"
        )
        for finding in title_items[:6]:
            affected_positions.add(finding.index)
            issues.append(
                f"  [{finding.number}] 题名「{finding.title}」；当前判断：{finding.title_style}。"
            )

    if target_journal_style in {"full", "abbreviated"}:
        expected_journal_style = "全称" if target_journal_style == "full" else "缩写"
        mismatches = [
            finding
            for finding in findings
            if finding.journal_style is not None and finding.journal_style != expected_journal_style
        ]
        if mismatches:
            issues.append(
                f"期刊名目标风格为{expected_journal_style}，发现不符合目标风格的期刊名。"
                "期刊名全称/缩写转换需人工或可靠缩写库确认。"
            )
            for finding in mismatches[:6]:
                affected_positions.add(finding.index)
                issues.append(
                    f"  [{finding.number}] 期刊名「{finding.journal}」；当前判断：{finding.journal_style}。"
                )

    if len(journal_styles) > 1:
        journal_items = [finding for finding in findings if finding.journal_style is not None]
        issues.append(
            "期刊名全称/缩写风格不统一：同一参考文献列表中同时出现期刊全称和缩写。"
            "建议统一使用全称或统一使用规范缩写。"
        )
        for finding in journal_items[:6]:
            affected_positions.add(finding.index)
            issues.append(
                f"  [{finding.number}] 期刊名「{finding.journal}」；当前判断：{finding.journal_style}。"
            )

    if issues:
        return False, issues, summarize_positions(sorted(affected_positions))
    return True, [], "参考文献题名大小写与期刊名风格未发现明显混用"

def _collect_body_citation_numbers(contexts):
    ordered = []
    seen = set()
    for ctx in contexts:
        if ctx.get("effective_section") not in {"body", "appendix"}:
            continue
        for match in _CITATION_NUM_RE.finditer(ctx.get("text", "")):
            for number in _expand_citation_numbers(match.group(1)):
                if number not in seen:
                    seen.add(number)
                    ordered.append(number)
    return ordered

def check_lnu_ref05(document_root, contexts, style_map, cfg):
    """LNU_REF05: 参考文献序号应连续。"""
    seen = []
    for ctx in iter_reference_section_contexts(contexts, skip_empty=True):
        text = ctx.get("text", "").strip()
        match = re.match(r"^\[(\d+)\]", text)
        if match:
            seen.append((int(match.group(1)), text[:60]))
    if not seen:
        return True, [], "未检测到参考文献条目"
    issues = []
    body_numbers = _collect_body_citation_numbers(contexts)
    missing_reference_numbers = [num for num in body_numbers if num not in {item[0] for item in seen}]
    if missing_reference_numbers:
        first_missing = missing_reference_numbers[0]
        issues.append(f"正文引用存在参考文献编号 {first_missing}，但参考文献列表缺少对应条目")
        return False, issues, f"[{first_missing}]"
    expected = 1
    for num, text in seen:
        if num != expected:
            issues.append(f"参考文献序号不连续：当前为{num}，规范应为{expected}，条目={text}")
            break
        expected += 1
    if not issues and body_numbers:
        ref_numbers = [num for num, _ in seen]
        canonical_order = body_numbers + [num for num in ref_numbers if num not in body_numbers]
        if canonical_order != ref_numbers:
            mismatch_index = next(
                index
                for index, (expected_num, current_num) in enumerate(zip(canonical_order, ref_numbers), start=1)
                if expected_num != current_num
            )
            issues.append(
                f"参考文献顺序与正文首次引用顺序不一致：第{mismatch_index}条当前为[{ref_numbers[mismatch_index - 1]}]，应对应[{canonical_order[mismatch_index - 1]}]"
            )
    return (len(issues) == 0), issues, f"共检查{len(seen)}条"

def check_lnu_tb01(document_root, contexts, style_map, cfg):
    """LNU_TB01: 表格外框线1.5pt(18)，内线0.5pt(6)"""
    issues = []
    OUTER_MIN, OUTER_MAX = 14, 22
    INNER_MIN, INNER_MAX = 4, 10

    def _cell_border_ok(cell, side, min_size, max_size):
        border = cell.find(f"w:tcPr/w:tcBorders/w:{side}", NSMAP)
        if border is None:
            return False
        val = get_w_attr(border, "val")
        if val in (None, "none", "nil"):
            return False
        sz_val = parse_int(get_w_attr(border, "sz"))
        return sz_val is None or min_size <= sz_val <= max_size

    def _any_cell_border_ok(cells, side, min_size, max_size):
        return any(_cell_border_ok(cell, side, min_size, max_size) for cell in cells)

    tbl_count = 0
    for tbl in get_non_equation_layout_tables(document_root):
        tbl_count += 1
        tbl_borders = tbl.find("w:tblPr/w:tblBorders", NSMAP)
        if tbl_borders is None:
            rows = tbl.findall(".//w:tr", NSMAP)
            if not rows:
                issues.append(f"第{tbl_count}个表格无行")
                continue

            first_row_cells = rows[0].findall(".//w:tc", NSMAP)
            last_row_cells = rows[-1].findall(".//w:tc", NSMAP) if len(rows) > 1 else first_row_cells

            has_top = _any_cell_border_ok(first_row_cells, "top", OUTER_MIN, OUTER_MAX)
            has_header_separator = _any_cell_border_ok(first_row_cells, "bottom", INNER_MIN, INNER_MAX)
            has_bottom = _any_cell_border_ok(last_row_cells, "bottom", OUTER_MIN, OUTER_MAX)

            if has_top and has_header_separator and has_bottom:
                continue

            issues.append(f"第{tbl_count}个表格缺少有效 cell-level 三线表横线")
            continue
        for side in ("top", "bottom"):
            border = tbl_borders.find(f"w:{side}", NSMAP)
            if border is None:
                continue
            val = get_w_attr(border, "val")
            if val in (None, "none"):
                continue  # 无边框定义，跳过（可能在单元格级别设置）
            sz_val = parse_int(get_w_attr(border, "sz"))
            if sz_val is not None and not (OUTER_MIN <= sz_val <= OUTER_MAX):
                issues.append(f"第{tbl_count}个表格外框{side}线宽={sz_val}，应约为18(1.5pt)")
        for side in ("left", "right"):
            border = tbl_borders.find(f"w:{side}", NSMAP)
            if border is None:
                continue
            val = get_w_attr(border, "val")
            if val not in (None, "none"):
                issues.append(f"第{tbl_count}个表格外框{side}线应为none（三线表无左右边框，当前val={val}）")
        for side in ("insideH", "insideV"):
            border = tbl_borders.find(f"w:{side}", NSMAP)
            if border is None:
                continue
            val = get_w_attr(border, "val")
            if val in (None, "none"):
                continue  # none 表示无内线（三线表通过单元格级边框实现分隔线）
            sz_val = parse_int(get_w_attr(border, "sz"))
            if sz_val is not None and not (INNER_MIN <= sz_val <= INNER_MAX):
                issues.append(f"第{tbl_count}个表格内线{side}线宽={sz_val}，应约为6(0.5pt)")
        if len(issues) >= 6:
            break
    return (len(issues) == 0), issues, f"检查了{tbl_count}个表格"

def check_lnu_toc02(document_root, contexts, style_map, cfg):
    def _toc_level(style_val, p_elem):
        if style_val in {"TOC1", "TOC2", "TOC3"}:
            return int(style_val[-1])
        style_name = (style_map.get(style_val or "", {}) or {}).get("name") or ""
        match = re.search(r"toc\s*([123])", style_name, re.IGNORECASE)
        if match:
            return int(match.group(1))
        if _looks_like_toc_entry(get_paragraph_text(p_elem)):
            return 1
        return None

    issues = []
    in_toc = False
    toc_count = 0
    toc_has_field = False
    for ctx in contexts:
        text = ctx.get("text", "").strip()
        if is_toc_title(text):
            in_toc = True
            continue
        if in_toc and ctx.get("kind") == "h1":
            break
        if not in_toc:
            continue
        p_elem = ctx.get("elem")
        if p_elem is None:
            continue
        p_pr = p_elem.find("w:pPr", NSMAP)
        if p_pr is None:
            continue
        p_style = p_pr.find("w:pStyle", NSMAP)
        style_val = get_w_attr(p_style, "val") if p_style is not None else None
        if is_toc_structural_style_id(style_val) or has_toc_field_instr(p_elem, NSMAP):
            toc_has_field = True
        if is_toc_structural_style_id(style_val):
            continue
        if style_val not in {"TOC1", "TOC2", "TOC3"} and not _looks_like_toc_entry(text):
            continue

        toc_count += 1
        level = _toc_level(style_val, p_elem)
        expected_after = 100
        if level == 1:
            expected_after = int((cfg.get("toc_level1_after_pt", 5) or 5) * 20)
        elif level == 2:
            expected_after = int((cfg.get("toc_level2_after_pt", 5) or 5) * 20)
        elif level == 3:
            expected_after = int((cfg.get("toc_level3_after_pt", 5) or 5) * 20)
        after_val = get_paragraph_spacing_after(p_elem, style_map)
        if abs((after_val or 0) - expected_after) > 20:
            issues.append(f"目录条目段后应为{expected_after} twips，当前为{after_val or 0}")
        expected_line = int((cfg.get("toc_entry_line", 276) if cfg else 276) or 276)
        line_val = get_paragraph_line_spacing(p_elem, style_map)
        if line_val is not None and abs(line_val - expected_line) > 20:
            issues.append(f"目录条目行距应为{expected_line}，当前为{line_val}")
        if len(issues) >= 5:
            break
    if toc_count == 0 and toc_has_field:
        return True, [], "目录为 TOC 域，但缺少脚本预填的可见目录结果"
    return (len(issues) == 0), issues, f"检查了{toc_count}个目录条目"

def check_lnu_toc01(document_root, contexts, style_map, cfg):
    def _toc_level(style_val):
        if style_val in {"TOC1", "TOC2", "TOC3"}:
            return int(style_val[-1])
        style_name = (style_map.get(style_val or "", {}) or {}).get("name") or ""
        match = re.search(r"toc\s*([123])", style_name, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    toc_contexts = [ctx for ctx in contexts if ctx.get("effective_section") == "toc"]
    if not toc_contexts:
        return True, [], "文档无目录区段"

    issues = []
    toc_title = next((ctx for ctx in toc_contexts if ctx.get("module") == "toc_title"), None)
    if toc_title is None:
        return False, ["未检测到目录标题段落。"], "目录区段"

    title_elem = toc_title["elem"]
    title_style = get_w_attr(title_elem.find("w:pPr/w:pStyle", NSMAP), "val")
    if not _is_toc_heading_style(title_style, style_map):
        issues.append(f"目录标题段落样式应为 TOCHeading，实际={title_style}")
    title_align = get_paragraph_alignment(title_elem, style_map)
    if title_align != "center":
        issues.append(f"目录标题应居中，实际对齐={title_align or '默认'}")

    title_runs = get_non_empty_runs(title_elem)
    if not title_runs:
        issues.append("目录标题缺少可见文字 run。")
    else:
        expected_title_size = cfg.get("toc_title_size", 32) if cfg else 32
        for run_elem in title_runs:
            size_val = get_effective_run_size(run_elem, style_map, title_elem)
            if size_val is not None and size_val != expected_title_size:
                issues.append(f"目录标题字号应为{expected_title_size} half-pts，实际={size_val}")
                break
        for run_elem in title_runs:
            east_asia = get_effective_run_font(run_elem, style_map, title_elem, "eastAsia")
            expected_title_font = (cfg.get("toc_title_font", "黑体") if cfg else "黑体")
            if east_asia is not None and east_asia != expected_title_font:
                issues.append(f"目录标题字体应为黑体，实际={east_asia}")
                break
        for run_elem in title_runs:
            if is_run_effectively_bold(run_elem, style_map, title_elem):
                issues.append("目录标题黑体不应加粗。")
                break

    toc_entries = [ctx for ctx in toc_contexts if ctx.get("module") == "toc_entry"]
    toc_has_field = any(
        is_toc_structural_style_id(get_w_attr(ctx.get("elem", ET.Element("p")).find("w:pPr/w:pStyle", NSMAP), "val"))
        or has_toc_field_instr(ctx.get("elem"), NSMAP)
        for ctx in toc_contexts
        if ctx.get("elem") is not None
    )
    if not toc_entries:
        if not toc_has_field:
            issues.append("未检测到目录条目段落。")
    else:
        for ctx in toc_entries:
            p_elem = ctx["elem"]
            p_style = get_w_attr(p_elem.find("w:pPr/w:pStyle", NSMAP), "val")
            if not _is_toc_entry_style(p_style, style_map):
                issues.append(f"第{ctx['index']}段目录条目样式应为 TOC1/TOC2/TOC3，实际={p_style}")
                break
            tabs = p_elem.find("w:pPr/w:tabs", NSMAP)
            has_right_tab = False
            if tabs is not None:
                for tab in tabs.findall("w:tab", NSMAP):
                    if get_w_attr(tab, "val") == "right" and parse_int(get_w_attr(tab, "pos")):
                        has_right_tab = True
                        break
            if not has_right_tab:
                issues.append(f"第{ctx['index']}段目录条目缺少页码右对齐制表位")
                break
            level = _toc_level(p_style)
            if level == 1:
                expected_entry_size = cfg.get("toc_level1_size", cfg.get("toc_entry_size", 22)) if cfg else 22
                expected_entry_font = cfg.get("toc_level1_font", cfg.get("toc_entry_font", "宋体")) if cfg else "宋体"
            else:
                expected_entry_size = cfg.get("toc_entry_size", 22) if cfg else 22
                expected_entry_font = cfg.get("toc_entry_font", "宋体") if cfg else "宋体"
            for run_elem in get_non_empty_runs(p_elem):
                if is_run_effectively_bold(run_elem, style_map, p_elem):
                    issues.append(f"第{ctx['index']}段目录条目不应加粗。")
                    break
                size_val = get_effective_run_size(run_elem, style_map, p_elem)
                if size_val is not None and size_val != expected_entry_size:
                    issues.append(f"第{ctx['index']}段目录条目字号应为{expected_entry_size} half-pts，实际={size_val}")
                    break
                east_asia = get_effective_run_font(run_elem, style_map, p_elem, "eastAsia")
                ascii_font = get_effective_run_font(run_elem, style_map, p_elem, "ascii")
                hansi_font = get_effective_run_font(run_elem, style_map, p_elem, "hAnsi")
                if east_asia not in (None, "", expected_entry_font, "SimSun"):
                    issues.append(f"第{ctx['index']}段目录条目中文字体应为{expected_entry_font}，实际={east_asia}")
                    break
                if ascii_font not in (None, "", "Times New Roman") or hansi_font not in (None, "", "Times New Roman"):
                    issues.append(
                        f"第{ctx['index']}段目录条目西文字体应为 Times New Roman，实际 ascii={ascii_font} hAnsi={hansi_font}"
                    )
                    break
            if issues:
                break

    return (len(issues) == 0), issues, f"检查了{len(toc_entries)}个目录条目"

def check_lnu_toc03(document_root, contexts, style_map, cfg):
    """LNU_TOC03: 目录应存在；可为可见普通目录或 Word TOC 域。"""
    toc_found = False

    for p_elem in document_root.findall(".//w:p", NSMAP):
        text = get_paragraph_text(p_elem).strip()
        if is_toc_title(text) or _looks_like_toc_entry(text):
            toc_found = True
            break

        p_style = p_elem.find("w:pPr/w:pStyle", NSMAP)
        style_val = (get_w_attr(p_style, "val") or "").strip()
        if is_toc_generated_style_id(style_val) or _is_toc_entry_style(style_val, style_map):
            toc_found = True
            break

        if has_toc_field_instr(p_elem, NSMAP):
            toc_found = True
            break

    if toc_found:
        return True, [], "已检测到目录区段"
    return False, ["未检测到目录区段；请按论文标题结构生成或补全目录，并人工核对页码。"], "目录区段"

def check_lnu_abs04(document_root, contexts, style_map, cfg):
    """LNU_ABS04: 中文摘要正文不应出现中文语境下的英文半角标点。"""
    issues = []
    for ctx in contexts:
        if ctx.get("module") != "abstract_cn_body":
            continue
        elem = ctx.get("elem")
        if elem is not None and elem.find(".//m:oMath", MNSMAP) is not None:
            continue
        txt = ctx.get("text", "")
        if _has_half_width_punct_in_cjk_context(txt):
            snippet = txt.strip()[:50]
            issues.append(f"第{ctx['index']}段中文摘要中存在英文半角标点夹在中文字符中：{snippet}")
        if len(issues) >= 5:
            break
    if not issues:
        return True, [], "中文摘要正文"
    return False, issues, f"{len(issues)} 处"

_LNU_TEXT_SCOPE_MODULES = {
    "abstract": {"abstract_cn_body", "abstract_cn_keywords"},
    "toc": {"toc_entry", "toc_body"},
    "body": {"body_heading", "body_paragraph"},
}

_LNU_TEXT_SCOPE_LABELS = {
    "abstract": "中文摘要",
    "toc": "目录条目",
    "body": "正文",
}

def _iter_lnu_text_contexts(contexts, text_scope):
    modules = _LNU_TEXT_SCOPE_MODULES[text_scope]
    for ctx in contexts:
        if ctx.get("protected") or ctx.get("in_table"):
            continue
        if ctx.get("kind") == "reference":
            continue
        if ctx.get("module") not in modules:
            continue
        elem = ctx.get("elem")
        if elem is not None and elem.find(".//m:oMath", MNSMAP) is not None:
            continue
        yield ctx

def _find_lnu_compact_text_issues(text):
    text = text or ""
    issues = []
    for match in TEXT_COMPACT_SPACE_RE.finditer(text):
        issues.append(("混排空格", text[max(0, match.start() - 8): min(len(text), match.end() + 8)]))
        if len(issues) >= 3:
            return issues
    for match in TEXT_PUNCT_SPACE_RE.finditer(text):
        issues.append(("标点空格", text[max(0, match.start() - 8): min(len(text), match.end() + 8)]))
        if len(issues) >= 3:
            return issues
    if _has_half_width_punct_in_cjk_context(text):
        issues.append(("半角标点", text.strip()[:50]))
    return issues

def _mask_lnu_allowed_heading_gap(text):
    return re.sub(r"^((?:\d+\s*[\.．]\s*)+\d+[\.．]?)[\u0020\u00a0\u3000]+(?=[^\s])", r"\1", text or "", count=1)

def _mask_lnu_allowed_unit_spaces(text):
    def _replace(match):
        unit = match.group(2)
        if unit in KNOWN_UNITS:
            return f"{match.group(1)}{unit}"
        return match.group(0)

    return re.sub(r"(?<![0-9A-Za-z])(\d+(?:\.\d+)?)[\u0020\u00a0\u3000]+([A-Za-z]{1,4})(?![0-9A-Za-z])", _replace, text or "")

def check_lnu_text_compact(document_root, contexts, style_map, cfg, text_scope):
    """LNU_TEXT01/02/03: 摘要、目录、正文采用紧凑混排空格策略。"""
    bad_positions = []
    samples = []
    label = _LNU_TEXT_SCOPE_LABELS[text_scope]
    for ctx in _iter_lnu_text_contexts(contexts, text_scope):
        text = ctx.get("text", "")
        if ctx.get("module") in {"body_heading", "toc_entry"}:
            text = _mask_lnu_allowed_heading_gap(text)
        text = _mask_lnu_allowed_unit_spaces(text)
        findings = _find_lnu_compact_text_issues(text)
        if not findings:
            continue
        bad_positions.append(ctx["index"])
        if len(samples) < 5:
            issue_type, snippet = findings[0]
            samples.append(f"第{ctx['index']}段{label}存在{issue_type}：{excerpt(snippet)}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个{label}段落存在混排空格或中文语境标点问题。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], f"{label}混排空格与中文标点正常"

LNU_RULE_CHECKERS = {
    "LNU_ACK01": lambda doc, ctxs, sm, cfg: check_lnu_ack(doc, ctxs, sm, cfg),
    "LNU_FMT01": lambda doc, ctxs, sm, cfg: check_lnu_fmt01(doc, ctxs, sm, cfg),
    "LNU_FMT02": lambda doc, ctxs, sm, cfg: check_lnu_fmt02(doc, ctxs, sm, cfg),
    "LNU_F01": lambda doc, ctxs, sm, cfg: check_lnu_f01(doc, ctxs, sm, cfg),
    "LNU_F02": lambda doc, ctxs, sm, cfg: check_lnu_f02(doc, ctxs, sm, cfg),
    "LNU_F03": lambda doc, ctxs, sm, cfg: check_lnu_f03(doc, ctxs, sm, cfg),
    "LNU_F06": lambda doc, ctxs, sm, cfg: check_lnu_f06(doc, ctxs, sm, cfg),
    "LNU_REF01": lambda doc, ctxs, sm, cfg: check_lnu_ref01(doc, ctxs, sm, cfg),
    "LNU_REF02": lambda doc, ctxs, sm, cfg: check_lnu_ref02(doc, ctxs, sm, cfg),
    "LNU_REF03": check_lnu_ref03,
    "LNU_REF04": check_lnu_ref04,
    "LNU_REF05": check_lnu_ref05,
    "LNU_REF06": check_lnu_ref06,
    "LNU_TB01": check_lnu_tb01,
    "LNU_TOC01": check_lnu_toc01,
    "LNU_TOC02": check_lnu_toc02,
    "LNU_TOC03": check_lnu_toc03,
    "LNU_TB02": lambda doc, ctxs, sm, cfg: check_lnu_tb02(doc, ctxs, sm, cfg),
    "LNU_TB04": lambda doc, ctxs, sm, cfg: check_lnu_tb04(doc, ctxs, sm, cfg),
    "LNU_F07": lambda doc, ctxs, sm, cfg: check_lnu_object_pagination(doc, ctxs, sm, cfg),
    "LNU_ABS01": lambda doc, ctxs, sm, cfg: check_lnu_abs01(doc, ctxs, sm, cfg),
    "LNU_ABS02": lambda doc, ctxs, sm, cfg: check_lnu_abs02(doc, ctxs, sm, cfg),
    "LNU_ABS03": lambda doc, ctxs, sm, cfg: check_lnu_abs03(doc, ctxs, sm, cfg),
    "LNU_ABS04": lambda doc, ctxs, sm, cfg: check_lnu_abs04(doc, ctxs, sm, cfg),
    "LNU_TEXT01": lambda doc, ctxs, sm, cfg: check_lnu_text_compact(doc, ctxs, sm, cfg, "abstract"),
    "LNU_TEXT02": lambda doc, ctxs, sm, cfg: check_lnu_text_compact(doc, ctxs, sm, cfg, "toc"),
    "LNU_TEXT03": lambda doc, ctxs, sm, cfg: check_lnu_text_compact(doc, ctxs, sm, cfg, "body"),
    "LNU_EQ05": lambda doc, ctxs, sm, cfg: check_lnu_eq05(doc, ctxs, sm, cfg),
    "LNU_H01": lambda doc, ctxs, sm, cfg: check_heading_num_space(ctxs),
    "LNU_CONC01": lambda doc, ctxs, sm, cfg: check_lnu_conc01(doc, ctxs, sm, cfg),
    "LNU_S03": lambda doc, ctxs, sm, cfg: check_lnu_s03(doc, ctxs, sm, cfg),
    "LNU_TITLE01": lambda doc, ctxs, sm, cfg: check_lnu_title01(doc, ctxs, sm, cfg),
    "LNU_TB03": lambda doc, ctxs, sm, cfg: check_lnu_tb03(doc, ctxs, sm, cfg),
    "LNU_UNIT01": lambda doc, ctxs, sm, cfg: check_lnu_unit01(doc, ctxs, sm, cfg),
}
