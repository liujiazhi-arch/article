from __future__ import annotations

import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:
    yaml = None

from citation_text_utils import is_citation_token
from _profile_utils import PROFILE_ALIASES, load_profile_bundle
from _thesis_utils import (
    NSMAP,
    W_NS,
    build_document_model,
    build_style_map,
    get_paragraph_text,
    parse_int,
)
from frontmatter_utils import is_keyword_paragraph_text as is_keyword_paragraph_text_shared, is_keywords_text
from sections._xml_helpers import get_run_text, is_superscript
from text_spacing_utils import (
    CJK_CHAR_RE,
    DIGIT_CHAR_RE,
    NUM_CJK_EXCEPTIONS,
    NUM_CJK_LEFT_EXCEPTIONS,
    needs_num_cjk_space as _needs_num_cjk_space,
    starts_with_num_cjk_exception as _starts_with_num_cjk_exception,
)
from thesis_rules.lnu_runtime import BASE_RULE_DEFINITIONS


M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MNSMAP = {"w": W_NS, "m": M_NS}

DEFAULT_CFG = {
    "margin_range": (1390, 1460),
    "margin_fix": 1440,        # fix_thesis 修复时写入的边距值（CN-Common: 2.54cm）
    "margin_fix_top": 1440,
    "margin_fix_bottom": 1440,
    "margin_fix_left": 1440,
    "margin_fix_right": 1440,
    "margin_gutter": 0,        # 装订线（DXA），CN-Common 不设装订线
    "body_size_range": (22, 26),
    "body_font": "宋体",
    "body_ascii_font": "Times New Roman",
    "body_line": 360,
    "body_size": 24,
    "body_indent": 480,
    "body_alignment": "both",
    "h1_size": 30,
    "h2_size": 30,
    "h3_size": 24,
    "h4_size": 24,
    "h1_bold": False,
    "h2_bold": False,
    "h3_bold": False,
    "h4_bold": False,
    "h4_indent": None,
    "h_font": None,
    "caption_size_range": (20, 22),
    "caption_size": 21,
    "figure_blank_line_twips": 360,
    "table_blank_line_twips": 360,
    "table_cell_line": 360,
    "figure_caption_line": 360,
    "figure_note_line": 240,
    "ref_hanging": 560,
    "ref_tab_min": 480,
    "ref_use_tab": True,
    "kw_min": 3,
    "kw_max": 8,
    "caption_number_sep": "-",
    "caption_label_gap_spaces": 1,
    "ack_font": None,
    "eq_number_sep": "-",        # 公式编号分隔符，辽大为"."
    "ref_terminal_punct": None,  # None=按CJK自动判断；辽大为"."
    "pg01_format": "plain",      # 辽大为'em_dash"即—N—格式
    "cover_page_number": True,
    "frontmatter_page_number_format": "upperRoman",
    "frontmatter_page_number_start": 1,
    "frontmatter_page_number_wrap": "plain",
    "body_page_number_format": "decimal",
    "body_page_number_start": 1,
    "body_page_number_wrap": "plain",
    "page_number_font": None,
    "page_number_size": None,
    "kw_font": None,             # 关键词字体，辽大为"黑体"
    "kw_bold": None,             # 关键词是否加粗，辽大为True
    "kw_half_points": None,      # 关键词字号，辽大为24（小四）
    "kw_cn_separator": "；",
    "kw_en_separator": "; ",
    "abstract_title_font": None,
    "abstract_title_size": None,
    "abstract_title_line": None,
    "abstract_body_font": None,
    "abstract_body_ascii_font": None,
    "abstract_body_size": None,
    "abstract_body_line": None,
    "abstract_body_indent": None,
    "abstract_en_title_font": None,
    "abstract_en_title_size": None,
    "abstract_en_body_font": None,
    "abstract_en_body_ascii_font": None,
    "abstract_en_body_size": None,
    "abstract_en_body_line": None,
    "abstract_en_body_indent": None,
    "toc_entry_line": 276,
    "check_snap_to_grid": False,
    "relax_strain_suffix_t_spacing": False,
    "mixed_spacing_policy": "spaced",
    "table_blank_line_mode": "spacing",
    "acknowledgement_placeholder_text": "",
    "ref_require_type_marker": False,
}

RULE_DEFINITIONS = BASE_RULE_DEFINITIONS

SEVERITY_LABELS = {
    "critical": "严重问题（Critical）",
    "important": "重要问题（Important）",
    "minor": "轻微问题（Minor）",
}

SEVERITY_SCORES = {
    "critical": 10,
    "important": 5,
    "minor": 2,
}

FRONTMATTER_SECTIONS = {"abstract_cn", "abstract_en", "toc"}
CAPTION_EN_MODULES = {"body_caption_en", "appendix_caption_en"}
CAPTION_NOTE_MODULES = {"body_caption_note", "appendix_caption_note"}
LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
TEXT_COMPACT_SPACE_RE = re.compile(
    r"(?<=[\u4e00-\u9fff])[\u0020\u00a0\u3000]+(?=[A-Za-z0-9])|"
    r"(?<=[A-Za-z0-9])[\u0020\u00a0\u3000]+(?=[\u4e00-\u9fff])"
)
TEXT_PUNCT_SPACE_RE = re.compile(r"[\u0020\u00a0\u3000]+(?=[，。；：！？、])|(?<=[，。；：！？、])[\u0020\u00a0\u3000]+")

_STRAIN_SUFFIX_T_RE = re.compile(r"\b\d+\s*T[\u4e00-\u9fff]")
_EQ_LAYOUT_NUM_RE = re.compile(r"^[（(]\s*\d+(?:[.\-]\d+)*\s*[)）]$")
_EQ_LAYOUT_TEXT_OP_RE = re.compile(r"[=+\-−×*/÷±<>≤≥≈∝∑∫]")
_EQ_LAYOUT_TEXT_SYMBOL_RE = re.compile(r"[A-Za-zα-ωΑ-Ω]\d*|\d+[A-Za-zα-ωΑ-Ω]|[%‰]")



def clone_default_cfg():
    return dict(DEFAULT_CFG)

def is_frontmatter_context(ctx):
    return ctx.get("section") in FRONTMATTER_SECTIONS

def is_main_body_context(ctx):
    section = ctx.get("section") or ctx.get("kind")
    if section == "cover":
        return False
    if is_keyword_paragraph_text(ctx.get("text", "")):
        return False
    if ctx.get("module") in CAPTION_EN_MODULES | CAPTION_NOTE_MODULES:
        return False
    return ctx.get("kind") == "body" and ctx.get("section") == "body" and not ctx.get("in_table", False)

def is_heading_audit_context(ctx, heading_kind):
    return ctx.get("kind") == heading_kind and not is_frontmatter_context(ctx) and not ctx.get("in_table", False)

def is_keyword_paragraph_text(text):
    return is_keyword_paragraph_text_shared(text)

def _needs_cjk_latin_space(text, index, left_char, right_char):
    return bool(
        (CJK_CHAR_RE.match(left_char) and LATIN_CHAR_RE.match(right_char))
        or (LATIN_CHAR_RE.match(left_char) and CJK_CHAR_RE.match(right_char))
    )

def find_missing_spacing_pairs(text, boundary_checker):
    matches = []
    compact_text = text or ""
    for index in range(len(compact_text) - 1):
        left_char = compact_text[index]
        right_char = compact_text[index + 1]
        if left_char.isspace() or right_char.isspace():
            continue
        if boundary_checker(compact_text, index, left_char, right_char):
            start = max(0, index - 6)
            end = min(len(compact_text), index + 8)
            matches.append(compact_text[start:end])
    return matches

def is_relaxed_strain_suffix_t_excerpt(text: str | None) -> bool:
    return bool(_STRAIN_SUFFIX_T_RE.search(text or ""))

def warn_profile(message):
    print(f"[WARN] {message}", file=sys.stderr)

def load_profile_data(profile_path, strict_profile=None):
    return load_profile_bundle(
        profile_path,
        yaml_lib=yaml,
        warn=warn_profile,
        aliases=PROFILE_ALIASES,
        strict=strict_profile,
    )

def build_profile_cfg(profile_id, profile_data, settings):
    cfg = clone_default_cfg()
    if any(key in settings for key in ("margin_top", "margin_bottom", "margin_left", "margin_right")):
        mn = settings.get("margin_range_min", 1390)
        mx = settings.get("margin_range_max", 1460)
        cfg["margin_range"] = (mn, mx)
        fallback = (
            settings.get("margin_top")
            or settings.get("margin_bottom")
            or settings.get("margin_left")
            or settings.get("margin_right")
            or cfg["margin_fix"]
        )
        cfg["margin_fix"] = fallback
        cfg["margin_fix_top"] = settings.get("margin_top", fallback)
        cfg["margin_fix_bottom"] = settings.get("margin_bottom", fallback)
        cfg["margin_fix_left"] = settings.get("margin_left", fallback)
        cfg["margin_fix_right"] = settings.get("margin_right", fallback)
    if "margin_gutter" in settings:
        cfg["margin_gutter"] = settings["margin_gutter"]

    for key in ("h1_size", "h2_size", "h3_size", "h4_size", "h4_indent"):
        if key in settings:
            cfg[key] = settings[key]

    for key in ("h_font", "h1_font", "h2_font", "h3_font", "h4_font"):
        if key in settings:
            cfg[key] = settings[key]

    for key in ("h1_bold", "h2_bold", "h3_bold", "h4_bold"):
        if key in settings:
            cfg[key] = settings[key]

    for key in ("kw_min", "kw_max", "kw_font", "kw_bold", "kw_half_points", "kw_cn_separator", "kw_en_separator"):
        if key in settings:
            cfg[key] = settings[key]
    for key in (
        "body_font",
        "body_ascii_font",
        "body_line",
        "body_size",
        "body_indent",
        "body_alignment",
        "abstract_title_font",
        "abstract_title_size",
        "abstract_title_line",
        "abstract_body_font",
        "abstract_body_ascii_font",
        "abstract_body_size",
        "abstract_body_line",
        "abstract_body_indent",
        "abstract_en_title_font",
        "abstract_en_title_size",
        "abstract_en_body_font",
        "abstract_en_body_ascii_font",
        "abstract_en_body_size",
        "abstract_en_body_line",
        "abstract_en_body_indent",
    ):
        if key in settings:
            cfg[key] = settings[key]

    for key in (
        "ref_use_tab",
        "ack_font",
        "caption_number_sep",
        "figure_blank_line_twips",
        "table_cell_line",
        "figure_caption_line",
        "figure_note_line",
        "eq_number_sep",
        "ref_terminal_punct",
        "pg01_format",
        "cover_page_number",
        "frontmatter_page_number_format",
        "frontmatter_page_number_start",
        "frontmatter_page_number_wrap",
        "body_page_number_format",
        "body_page_number_start",
        "body_page_number_wrap",
        "page_number_font",
        "page_number_size",
        "ref_number_trailing_space",
        "ref_require_type_marker",
        "acknowledgement_required",
    ):
        if key in settings:
            cfg[key] = settings[key]
    for key in ("check_snap_to_grid", "relax_body_spacing_rules"):
        if key in settings:
            cfg[key] = settings[key]
    for key in (
        "relax_strain_suffix_t_spacing",
        "mixed_spacing_policy",
        "table_blank_line_mode",
        "acknowledgement_placeholder_text",
        "preserve_caption_soft_line_breaks",
    ):
        if key in settings:
            cfg[key] = settings[key]

    for key in ("ref_hanging", "ref_tab_min", "ref_line_spacing", "ref_font_size",
                "abstract_title_after_pt",
                "caption_label_gap_spaces",
                "toc_title_font", "toc_title_size", "toc_entry_font", "toc_entry_size",
                "toc_entry_line",
                "toc_level1_font", "toc_level1_size",
                "toc_level1_after_pt", "toc_level2_after_pt", "toc_level3_after_pt",
                "h1_spacing_before", "h1_spacing_after",
                "h2_spacing_before", "h2_spacing_after",
                "h3_spacing_before", "h3_spacing_after",
                "h4_spacing_before", "h4_spacing_after"):
        if key in settings:
            cfg[key] = settings[key]

    for override in profile_data.get("overrides") or []:
        rule_id = str(override.get("id") or "").strip()
        expected = override.get("expected") or {}
        if not isinstance(expected, dict):
            continue
        bold = expected.get("bold")
        if bold is None:
            continue
        if rule_id == "H01":
            cfg["h1_bold"] = bool(bold)
        elif rule_id == "H02":
            cfg["h2_bold"] = bool(bold)
        elif rule_id == "H03":
            cfg["h3_bold"] = bool(bold)
        elif rule_id == "H04":
            cfg["h4_bold"] = bool(bold)

    if profile_id.startswith("lnu-"):
        cfg["check_snap_to_grid"] = settings.get("check_snap_to_grid", True)

    return cfg

def get_w_attr(elem, attr_name):
    if elem is None:
        return None
    return elem.get(f"{{{W_NS}}}{attr_name}")

def is_bold(run_elem):
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is None:
        return False
    bold_elem = r_pr.find("w:b", NSMAP)
    if bold_elem is None:
        return False
    val = get_w_attr(bold_elem, "val")
    return val not in ("0", "false", "False", "off")

def paragraph_has_math(p_elem):
    return (
        p_elem is not None
        and (
            p_elem.find(".//m:oMath", MNSMAP) is not None
            or p_elem.find(".//m:oMathPara", MNSMAP) is not None
        )
    )

def is_formula_related_body_context(ctx):
    elem = ctx.get("elem")
    if elem is None:
        return False
    if ctx.get("module") in {"body_equation", "appendix_equation"}:
        return True
    return paragraph_has_math(elem)

def _compact_table_cell_text(tc_elem):
    parts = []
    for p_elem in tc_elem.findall(".//w:p", NSMAP):
        text = get_paragraph_text(p_elem)
        if text:
            parts.append(text)
    return re.sub(r"\s+", "", "".join(parts))

def _looks_like_text_equation_cell(text):
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < 4:
        return False
    if "://" in compact:
        return False
    if not _EQ_LAYOUT_TEXT_OP_RE.search(compact):
        return False
    return _EQ_LAYOUT_TEXT_SYMBOL_RE.search(compact) is not None

def is_equation_layout_table(tbl_elem):
    if tbl_elem is None:
        return False

    rows = tbl_elem.findall("w:tr", NSMAP)
    if len(rows) != 1:
        return False
    cells = rows[0].findall("w:tc", NSMAP)
    if len(cells) not in (2, 3):
        return False

    has_math_object = tbl_elem.find(".//m:oMath", MNSMAP) is not None or tbl_elem.find(".//m:oMathPara", MNSMAP) is not None
    has_text_equation = any(_looks_like_text_equation_cell(_compact_table_cell_text(tc_elem)) for tc_elem in cells[:-1])
    if not has_math_object and not has_text_equation:
        return False

    right_text = _compact_table_cell_text(cells[-1])
    if not _EQ_LAYOUT_NUM_RE.fullmatch(right_text):
        return False

    if len(cells) == 3:
        left_text = _compact_table_cell_text(cells[0])
        if left_text:
            return False

    return True

def get_non_equation_layout_tables(document_root):
    tables = document_root.findall(".//w:tbl", NSMAP)
    return [tbl_elem for tbl_elem in tables if not is_equation_layout_table(tbl_elem)]

def paragraph_in_table(p_elem, tbl_elem):
    return any(id(candidate) == id(p_elem) for candidate in tbl_elem.findall(".//w:p", NSMAP))

def paragraph_in_equation_layout_table(document_root, p_elem):
    if p_elem is None:
        return False
    for tbl_elem in document_root.findall(".//w:tbl", NSMAP):
        if is_equation_layout_table(tbl_elem) and paragraph_in_table(p_elem, tbl_elem):
            return True
    return False

def is_run_effectively_bold(run_elem, style_map, paragraph_elem=None):
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is not None:
        bold_elem = r_pr.find("w:b", NSMAP)
        if bold_elem is not None:
            val = get_w_attr(bold_elem, "val")
            return val not in ("0", "false", "False", "off")
        run_style = get_w_attr(r_pr.find("w:rStyle", NSMAP), "val")
        if run_style:
            run_style_props = style_map.get(run_style, {})
            if run_style_props.get("bold") is not None:
                return run_style_props.get("bold") is True

    if paragraph_elem is not None:
        paragraph_style = get_w_attr(paragraph_elem.find("w:pPr/w:pStyle", NSMAP), "val")
        if paragraph_style:
            paragraph_style_props = style_map.get(paragraph_style, {})
            if paragraph_style_props.get("bold") is not None:
                return paragraph_style_props.get("bold") is True

    return False

def is_citation_run_text(text):
    compact = re.sub(r"\s+", "", text or "")
    return is_citation_token(compact)

def get_non_empty_runs(p_elem):
    runs = []
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        if get_run_text(run_elem).strip():
            runs.append(run_elem)
    return runs

def _default_paragraph_style_props(style_map):
    return style_map.get("__default_paragraph__", {}) if style_map else {}

def _doc_default_style_props(style_map):
    return style_map.get("__doc_defaults__", {}) if style_map else {}

def _paragraph_style_props(p_elem, style_map):
    style_id = get_w_attr(p_elem.find("w:pPr/w:pStyle", NSMAP), "val")
    return style_map.get(style_id, {}) if style_map and style_id else {}

def _run_style_props(run_elem, style_map):
    style_id = get_w_attr(run_elem.find("w:rPr/w:rStyle", NSMAP), "val")
    return style_map.get(style_id, {}) if style_map and style_id else {}

def _resolve_effective_prop(direct_value, paragraph_props, default_props, doc_defaults, key, *, zero_when_missing=False):
    if direct_value is not None:
        return direct_value
    for props in (paragraph_props, default_props, doc_defaults):
        value = props.get(key)
        if value is not None:
            return value
    return 0 if zero_when_missing else None

def get_run_size(run_elem):
    size_elem = run_elem.find("w:rPr/w:sz", NSMAP)
    return parse_int(get_w_attr(size_elem, "val"))

def get_effective_run_size(run_elem, style_map=None, paragraph_elem=None):
    direct_value = get_run_size(run_elem)
    if direct_value is not None or style_map is None:
        return direct_value
    for props in (
        _run_style_props(run_elem, style_map),
        _paragraph_style_props(paragraph_elem, style_map) if paragraph_elem is not None else {},
        _default_paragraph_style_props(style_map),
        _doc_default_style_props(style_map),
    ):
        value = props.get("sz")
        if value is not None:
            return value
    return None

def get_effective_run_font(run_elem, style_map=None, paragraph_elem=None, attr_name="eastAsia"):
    r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
    direct_value = get_w_attr(r_fonts, attr_name)
    if direct_value is not None or style_map is None:
        return direct_value
    for props in (
        _run_style_props(run_elem, style_map),
        _paragraph_style_props(paragraph_elem, style_map) if paragraph_elem is not None else {},
        _default_paragraph_style_props(style_map),
        _doc_default_style_props(style_map),
    ):
        value = props.get(attr_name)
        if value is not None:
            return value
    return None

def get_paragraph_alignment(p_elem, style_map=None):
    if style_map is None:
        jc = p_elem.find("w:pPr/w:jc", NSMAP)
        return get_w_attr(jc, "val")
    return _resolve_effective_prop(
        get_w_attr(p_elem.find("w:pPr/w:jc", NSMAP), "val"),
        _paragraph_style_props(p_elem, style_map),
        _default_paragraph_style_props(style_map),
        _doc_default_style_props(style_map),
        "jc",
    )

def get_paragraph_first_line(p_elem):
    ind = p_elem.find("w:pPr/w:ind", NSMAP)
    return get_w_attr(ind, "firstLine")

def _get_effective_paragraph_spacing(p_elem, style_map, attr_name):
    spacing = p_elem.find("w:pPr/w:spacing", NSMAP)
    direct_value = parse_int(get_w_attr(spacing, attr_name))
    return _resolve_effective_prop(
        direct_value,
        _paragraph_style_props(p_elem, style_map),
        _default_paragraph_style_props(style_map),
        _doc_default_style_props(style_map),
        f"spacing_{attr_name}",
        zero_when_missing=attr_name in {"before", "after"},
    )

def get_paragraph_spacing_before(p_elem, style_map=None):
    if style_map is None:
        spacing = p_elem.find("w:pPr/w:spacing", NSMAP)
        return parse_int(get_w_attr(spacing, "before"))
    return _get_effective_paragraph_spacing(p_elem, style_map, "before")

def get_paragraph_spacing_after(p_elem, style_map=None):
    if style_map is None:
        spacing = p_elem.find("w:pPr/w:spacing", NSMAP)
        return parse_int(get_w_attr(spacing, "after"))
    return _get_effective_paragraph_spacing(p_elem, style_map, "after")

def get_paragraph_line_spacing(p_elem, style_map=None):
    if style_map is None:
        spacing = p_elem.find("w:pPr/w:spacing", NSMAP)
        return parse_int(get_w_attr(spacing, "line"))
    return _get_effective_paragraph_spacing(p_elem, style_map, "line")

def count_cjk_chars(text):
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")

def is_mostly_cjk(text):
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return False
    return count_cjk_chars(compact) / len(compact) > 0.3

def summarize_table_positions(indices):
    if not indices:
        return "无"
    ordered = sorted(set(indices))
    preview = ordered[:5]
    text = "、".join([f"第{num}个表" for num in preview])
    if len(ordered) > len(preview):
        text += f" 等{len(ordered)}个表"
    return text

def summarize_positions(positions):
    if not positions:
        return "无"
    ordered = sorted(set(positions))
    preview = ordered[:5]
    text = "、".join([f"第{num}段" for num in preview])
    if len(ordered) > len(preview):
        text += f" 等{len(ordered)}段"
    return text

def excerpt(text):
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) > 16:
        return compact[:16] + "..."
    return compact or "空文本"

def markdown_escape(text):
    return str(text).replace("|", "\\|").replace("\n", "<br>")

def validate_docx_path(file_path):
    path = os.path.abspath(os.path.expanduser(str(file_path)))
    if not os.path.isfile(path):
        raise ValueError(f"文件不存在：{path}")

    lower_path = path.lower()
    if lower_path.endswith(".doc") and not lower_path.endswith(".docx"):
        raise ValueError(f"仅支持 .docx 文件，当前收到 .doc：{path}。请先转换为 .docx 后再执行。")
    if not lower_path.endswith(".docx"):
        raise ValueError(f"仅支持 .docx 文件：{path}")
    return path

def load_docx_xml(file_path):
    file_path = validate_docx_path(file_path)
    try:
        with zipfile.ZipFile(file_path, "r") as docx_file:
            try:
                document_xml = docx_file.read("word/document.xml").decode("utf-8")
            except KeyError as exc:
                raise ValueError(f"不是有效的 .docx 文件，缺少核心部件 word/document.xml：{file_path}") from exc
            try:
                styles_xml = docx_file.read("word/styles.xml").decode("utf-8")
            except KeyError:
                styles_xml = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<w:styles xmlns:w="{W_NS}"/>'
                )
            footnotes_xml = None
            try:
                footnotes_xml = docx_file.read("word/footnotes.xml").decode("utf-8")
            except KeyError:
                footnotes_xml = None
    except zipfile.BadZipFile as exc:
        raise ValueError(f"不是有效的 .docx 压缩包：{file_path}") from exc
    try:
        document_root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise ValueError(f"不是有效的 .docx 文件，核心部件 word/document.xml 无法解析：{file_path}") from exc
    if document_root.find("w:body", NSMAP) is None:
        raise ValueError(f"不是有效的 .docx 文件，核心部件 word/document.xml 缺少主体结构 w:body：{file_path}")
    try:
        ET.fromstring(styles_xml)
    except ET.ParseError as exc:
        raise ValueError(f"不是有效的 .docx 文件，样式部件 word/styles.xml 无法解析：{file_path}") from exc
    if footnotes_xml:
        try:
            ET.fromstring(footnotes_xml)
        except ET.ParseError as exc:
            raise ValueError(f"不是有效的 .docx 文件，脚注部件 word/footnotes.xml 无法解析：{file_path}") from exc
    return document_xml, styles_xml, footnotes_xml

def build_paragraph_contexts(document_root, style_map):
    contexts = []
    document_model = build_document_model(document_root, style_map)
    for node in document_model.paragraphs:
        if node.container_section == "cover":
            continue
        contexts.append(
            {
                "index": node.index,
                "elem": node.elem,
                "text": node.text,
                "kind": node.kind,
                "section": node.container_section,
                "effective_section": node.section,
                "module": node.module,
                "protected": node.protected,
                "in_table": node.in_table,
            }
        )
    return contexts

def make_result(rule_id, rule_name, severity, passed, issues, affected):
    return {
        "id": rule_id,
        "name": rule_name,
        "severity": severity,
        "passed": passed,
        "issues": issues,
        "affected": affected,
    }
