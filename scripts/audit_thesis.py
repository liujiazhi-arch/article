import argparse
import datetime
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

try:
    import yaml
except ImportError:
    yaml = None

from _profile_utils import PROFILE_ALIASES, PROFILE_DIR, format_profile_resolution, load_profile_bundle
from _thesis_utils import (
    NSMAP,
    W_NS,
    _looks_like_toc_entry,
    build_document_model,
    build_document_sections,
    build_style_map,
    classify_paragraph,
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
    is_keyword_paragraph_text as is_keyword_paragraph_text_shared,
    is_keywords_text,
    is_toc_entry_style as is_toc_entry_style_shared,
    is_toc_generated_style_id,
    is_toc_heading_style as is_toc_heading_style_shared,
    is_toc_structural_style_id,
)
from reference_section_utils import iter_reference_section_contexts

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
    "h_font": None,
    "caption_size_range": (20, 22),
    "caption_size": 21,
    "figure_blank_line_twips": 360,
    "table_blank_line_twips": 360,
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
    "check_snap_to_grid": False,
    "relax_strain_suffix_t_spacing": False,
    "table_blank_line_mode": "spacing",
    "acknowledgement_placeholder_text": "",
    "ref_require_type_marker": False,
}

RULE_DEFINITIONS = [
    ("P01", "页边距", "critical"),
    ("T01", "正文中文字体", "critical"),
    ("T02", "正文西文字体", "critical"),
    ("T03", "正文字号", "important"),
    ("T04", "正文行距", "critical"),
    ("T05", "正文首行缩进", "critical"),
    ("T06", "正文两端对齐", "critical"),
    ("H01", "一级标题格式", "critical"),
    ("H02", "二级标题格式", "critical"),
    ("H03", "三级标题格式", "critical"),
    ("C01", "存在上标引用", "minor"),
    ("C02", "上标引用字体", "important"),
    ("C03", "上标引用后句号", "minor"),
    ("C04", "正文嵌入引用未上标", "critical"),
    ("R01", "参考文献悬挂缩进", "critical"),
    ("R02", "参考文献制表位", "critical"),
    ("R03", "参考文献行距", "critical"),
    ("R04", "参考文献引用非上标", "important"),
    ("R05", "参考文献制表位宽度（两位数对齐）", "critical"),
    ("F01", "图题格式", "important"),
    ("F02", "表题格式", "important"),
    ("TB01", "三线表边框", "important"),
    ("H04", "四级标题格式", "important"),
    ("S01", "标题段前段后间距", "minor"),
    ("S02", "章节首页分页", "minor"),
    ("S03", "正文段前段后间距", "minor"),
    ("FN01", "脚注字号", "minor"),
    ("PG01", "页码存在性", "minor"),
    ("P03", "页码底端居中", "minor"),
    ("REF01", "参考文献标点规范", "important"),
    ("KW01", "关键词格式", "important"),
    ("EQ01", "公式段落居中", "important"),
    ("EQ02", "公式编号右对齐", "important"),
    ("EQ03", "公式引用格式", "minor"),
    ("F03", "图题章节编号格式", "important"),
    ("F04", "表题章节编号格式", "important"),
    ("F05", "图表题注字体", "important"),
    ("F06", "图片段落居中", "important"),
    ("F07", "图题末尾无句号", "minor"),
    ("TB03_LINE", "三线表栏目线", "important"),
    ("TB02", "三线表无多余竖线", "important"),
    ("TB03", "续表表头重复", "minor"),
    ("SP01", "中英文间距关闭", "important"),
    ("SP02", "中数字间距关闭", "important"),
    ("SP_CJK_LATIN", "中英文字符间距", "important"),
    ("SP_NUM_CJK", "中文与数字间距", "important"),
    ("KW02", "关键词末尾标点", "important"),
    ("PU02", "省略号规范（用……不用......）", "minor"),
    ("PU01", "中文正文不含英文半角标点", "minor"),
]

LNU_RULE_DEFINITIONS = (
    ("LNU_ACK01", "致谢字体（辽大专用）", "minor"),
    ("LNU_FMT01", "软回车换行（辽大）", "minor"),
    ("LNU_FMT02", "图片嵌入型与表格无环绕（辽大）", "minor"),
    ("LNU_F01", "图题点号编号格式（辽大）", "important"),
    ("LNU_F02", "表题点号编号格式（辽大）", "important"),
    ("LNU_F03", "图前图后空行（辽大）", "minor"),
    ("LNU_F06", "图题图注版式（辽大）", "minor"),
    ("LNU_REF01", "参考文献英文半角标点（辽大）", "important"),
    ("LNU_REF02", "参考文献编号空格格式（辽大）", "important"),
    ("LNU_REF03", "参考文献字号五号，1.5倍行距", "important"),
    ("LNU_REF04", "参考文献文献类型标识（辽大）", "important"),
    ("LNU_REF05", "参考文献序号连续性（辽大）", "important"),
    ("LNU_TB01", "表格外框1.5pt内线0.5pt", "important"),
    ("LNU_TOC01", "目录标题与条目样式（辽大）", "minor"),
    ("LNU_TOC02", "目录条目行距多倍1.15倍，段后5磅（辽大）", "minor"),
    ("LNU_TOC03", "目录必须自动生成（辽大）", "important"),
    ("LNU_F05", "图表需先文中引用", "important"),
    ("LNU_TB02", "表格内容宋体五号（辽大）", "minor"),
    ("LNU_TB04", "表块留白与表题贴表（辽大）", "minor"),
    ("LNU_ABS01", "摘要标题格式（辽大）", "important"),
    ("LNU_ABS02", "Abstract标题格式（辽大）", "important"),
    ("LNU_ABS03", "英文摘要正文格式（辽大）", "minor"),
    ("LNU_ABS04", "中文摘要不含英文半角标点（辽大）", "minor"),
    ("LNU_H01", "标题编号与文字间距", "important"),
    ("LNU_CONC01", "末章标题含结论（辽大）", "minor"),
    ("LNU_S03", "参考文献/致谢前分页符（辽大）", "minor"),
    ("LNU_TITLE01", "摘要等标题双空格格式（辽大）", "minor"),
    ("LNU_TB03", "表格内容单倍行距（辽大）", "minor"),
    ("LNU_UNIT01", "数字与单位间空格（辽大）", "minor"),
)

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
CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
DIGIT_CHAR_RE = re.compile(r"\d")
NUM_CJK_EXCEPTIONS = sorted(
    [
        "组件",
        "批次",
        "年月日",
        "年",
        "月",
        "日",
        "时",
        "分",
        "秒",
        "度",
        "℃",
        "个",
        "只",
        "件",
        "台",
        "条",
        "块",
        "片",
        "张",
        "幅",
        "套",
        "段",
        "页",
        "%",
        "％",
    ],
    key=len,
    reverse=True,
)
NUM_CJK_LEFT_EXCEPTIONS = {"第", "图", "表", "式"}


class DocumentRootProxy:
    def __init__(self, root, zip_path=None):
        self._root = root
        self._zip_path = zip_path

    def __getattr__(self, name):
        return getattr(self._root, name)

    def __iter__(self):
        return iter(self._root)


@dataclass(frozen=True)
class AuditRuntime:
    cfg: dict
    rule_definitions: tuple[tuple[str, str, str], ...]
    rule_checkers: dict
    profile_id: str
    requested_profile: str | None = None
    fallback_used: bool = False
    warning_message: str | None = None


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
    if ctx.get("module") in {"body_caption_note", "appendix_caption_note"}:
        return False
    return ctx.get("kind") == "body" and ctx.get("section") == "body" and not ctx.get("in_table", False)


def is_heading_audit_context(ctx, heading_kind):
    return ctx.get("kind") == heading_kind and not is_frontmatter_context(ctx) and not ctx.get("in_table", False)


def is_keyword_paragraph_text(text):
    return is_keyword_paragraph_text_shared(text)


def _starts_with_num_cjk_exception(text, index):
    if index < 0 or index >= len(text):
        return False
    return any(text.startswith(token, index) for token in NUM_CJK_EXCEPTIONS)


def _needs_cjk_latin_space(text, index, left_char, right_char):
    return bool(
        (CJK_CHAR_RE.match(left_char) and LATIN_CHAR_RE.match(right_char))
        or (LATIN_CHAR_RE.match(left_char) and CJK_CHAR_RE.match(right_char))
    )


def _needs_num_cjk_space(text, index, left_char, right_char):
    if DIGIT_CHAR_RE.match(left_char) and CJK_CHAR_RE.match(right_char):
        return not _starts_with_num_cjk_exception(text, index + 1)
    if CJK_CHAR_RE.match(left_char) and DIGIT_CHAR_RE.match(right_char):
        return left_char not in NUM_CJK_LEFT_EXCEPTIONS
    return False


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


_STRAIN_SUFFIX_T_RE = re.compile(r"\b\d+\s*T[\u4e00-\u9fff]")


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

    for key in ("h1_size", "h2_size", "h3_size", "h4_size"):
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
        "figure_caption_line",
        "figure_note_line",
        "eq_number_sep",
        "ref_terminal_punct",
        "pg01_format",
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
    for key in ("relax_strain_suffix_t_spacing", "table_blank_line_mode", "acknowledgement_placeholder_text"):
        if key in settings:
            cfg[key] = settings[key]

    for key in ("ref_hanging", "ref_tab_min", "ref_line_spacing", "ref_font_size",
                "abstract_title_after_pt",
                "caption_label_gap_spaces",
                "toc_title_font", "toc_title_size", "toc_entry_font", "toc_entry_size",
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


def load_profile(profile_path):
    runtime = build_audit_runtime(profile_path)
    return runtime.cfg


def get_w_attr(elem, attr_name):
    if elem is None:
        return None
    return elem.get(f"{{{W_NS}}}{attr_name}")


def get_run_text(run_elem):
    parts = []
    for t_elem in run_elem.findall(".//w:t", NSMAP):
        if t_elem.text:
            parts.append(t_elem.text)
    return "".join(parts)


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


_EQ_LAYOUT_NUM_RE = re.compile(r"^[（(]\s*\d+(?:[.\-]\d+)*\s*[)）]$")
_EQ_LAYOUT_TEXT_OP_RE = re.compile(r"[=+\-−×*/÷±<>≤≥≈∝∑∫]")
_EQ_LAYOUT_TEXT_SYMBOL_RE = re.compile(r"[A-Za-zα-ωΑ-Ω]\d*|\d+[A-Za-zα-ωΑ-Ω]|[%‰]")


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


def is_superscript(run_elem):
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is None:
        return False
    vert_align = r_pr.find("w:vertAlign", NSMAP)
    return get_w_attr(vert_align, "val") == "superscript"


def is_citation_run_text(text):
    compact = re.sub(r"\s+", "", text or "")
    return bool(re.fullmatch(r"\[\d{1,3}(?:[-,，、]\d{1,3})*\]", compact))


def parse_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def check_p01(document_root, contexts, style_map, cfg):
    invalid = []
    min_margin, max_margin = cfg["margin_range"]
    exact_expected = {
        "top": cfg.get("margin_fix_top"),
        "bottom": cfg.get("margin_fix_bottom"),
        "left": cfg.get("margin_fix_left"),
        "right": cfg.get("margin_fix_right"),
    }
    use_exact_by_side = len({value for value in exact_expected.values() if value is not None}) > 1
    # 只检查正文节页边距，跳过封面节（第一个 inline sectPr）
    body = document_root.find("w:body", NSMAP)
    sect_prs_to_check = []
    if body is not None:
        main_sect = body.find("w:sectPr", NSMAP)
        if main_sect is not None:
            pg_mar = main_sect.find("w:pgMar", NSMAP)
            if pg_mar is not None:
                sect_prs_to_check.append(pg_mar)
        inline_sects = [
            p.find("w:pPr/w:sectPr", NSMAP)
            for p in body.findall("w:p", NSMAP)
        ]
        inline_sects = [s for s in inline_sects if s is not None]
        for s in inline_sects[1:]:  # 跳过第一个（封面节）
            pg_mar = s.find("w:pgMar", NSMAP)
            if pg_mar is not None:
                sect_prs_to_check.append(pg_mar)
    else:
        sect_prs_to_check = document_root.findall(".//w:sectPr/w:pgMar", NSMAP)
    pg_margins = sect_prs_to_check
    for idx, pg_mar in enumerate(pg_margins, start=1):
        bad_attrs = []
        for attr_name in ("left", "right", "top", "bottom"):
            attr_val = parse_int(get_w_attr(pg_mar, attr_name))
            if attr_val is None:
                bad_attrs.append(f"{attr_name}={get_w_attr(pg_mar, attr_name)}")
                continue
            if use_exact_by_side:
                expected_val = exact_expected.get(attr_name)
                if expected_val is None or attr_val != expected_val:
                    bad_attrs.append(f"{attr_name}={get_w_attr(pg_mar, attr_name)}")
                continue
            if not (min_margin <= attr_val <= max_margin):
                bad_attrs.append(f"{attr_name}={get_w_attr(pg_mar, attr_name)}")
        if bad_attrs:
            invalid.append(f"第{idx}个节页边距异常：{', '.join(bad_attrs)}")

    if invalid:
        return False, invalid, f"节属性 {len(invalid)} 处"
    return True, [], "全部节属性"


def check_t01(document_root, contexts, style_map):
    _cjk_re = _re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
    bad_runs = []
    positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            if is_citation_run_text(run_text):
                continue
            if not _cjk_re.search(run_text):
                continue  # 纯ASCII run 无需检查 eastAsia
            r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
            east_asia = get_w_attr(r_fonts, "eastAsia")
            if east_asia not in ("宋体", "SimSun"):
                bad_runs.append(
                    f"第{ctx['index']}段存在 {len(bad_runs) + 1} 处正文 run 的 eastAsia 不是宋体/SimSun，示例{excerpt(run_text)}"
                )
                positions.append(ctx["index"])
                if len(bad_runs) >= 5:
                    break
        if len(bad_runs) >= 5:
            break

    total = 0
    affected_positions = set()
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            if is_citation_run_text(run_text):
                continue
            if not _cjk_re.search(run_text):
                continue
            r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
            east_asia = get_w_attr(r_fonts, "eastAsia")
            if east_asia not in ("宋体", "SimSun"):
                total += 1
                affected_positions.add(ctx["index"])

    if total:
        issues = [f"{total} 个正文 run 的 eastAsia 不是宋体/SimSun。"]
        issues.extend(bad_runs[:3])
        return False, issues, summarize_positions(sorted(affected_positions))
    return True, [], "全部正文段落"


def check_t02(document_root, contexts, style_map):
    total = 0
    samples = []
    positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
            ascii_font = get_w_attr(r_fonts, "ascii")
            hansi_font = get_w_attr(r_fonts, "hAnsi")
            if ascii_font != "Times New Roman" or hansi_font != "Times New Roman":
                total += 1
                positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(
                        f"第{ctx['index']}段 run '{excerpt(run_text)}' 的 ascii={ascii_font}、hAnsi={hansi_font}"
                    )

    if total:
        issues = [f"{total} 个正文 run 的西文字体不是 Times New Roman。"]
        issues.extend(samples)
        return False, issues, summarize_positions(positions)
    return True, [], "全部正文段落"


def check_t03(document_root, contexts, style_map, cfg):
    total = 0
    samples = []
    positions = []
    min_size, max_size = cfg["body_size_range"]
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            size_elem = run_elem.find("w:rPr/w:sz", NSMAP)
            size_val = parse_int(get_w_attr(size_elem, "val"))
            if size_val is None or not (min_size <= size_val <= max_size):
                total += 1
                positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段 run '{excerpt(run_text)}' 的字号为 {size_val}")

    if total:
        issues = [f"{total} 个正文 run 的字号不在 {min_size}~{max_size} 范围内。"]
        issues.extend(samples)
        return False, issues, summarize_positions(positions)
    return True, [], "全部正文段落"


def check_t04(document_root, contexts, style_map, cfg=None):
    bad_positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        if get_w_attr(spacing, "line") != "360" or get_w_attr(spacing, "lineRule") != "auto":
            bad_positions.append(ctx["index"])
            continue
        if cfg and cfg.get("check_snap_to_grid"):
            snap = ctx["elem"].find("w:pPr/w:snapToGrid", NSMAP)
            snap_val = get_w_attr(snap, "val") if snap is not None else None
            if snap_val != "0":
                bad_positions.append(ctx["index"])

    if bad_positions:
        return (
            False,
            [f"{len(bad_positions)} 个正文段落的行距不是 360 且 lineRule=auto。"],
            summarize_positions(bad_positions),
        )
    return True, [], "全部正文段落"


def check_t05(document_root, contexts, style_map):
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        jc_val = get_w_attr(ctx["elem"].find("w:pPr/w:jc", NSMAP), "val")
        if jc_val == "center":
            continue
        ind = ctx["elem"].find("w:pPr/w:ind", NSMAP)
        first_line = parse_int(get_w_attr(ind, "firstLine"))
        if first_line is None or not (420 <= first_line <= 480):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段首行缩进为 {get_w_attr(ind, 'firstLine')}")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落首行缩进不在 420~480 范围内。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部正文段落"


def check_t06(document_root, contexts, style_map):
    bad_positions = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        if ctx.get("protected"):
            continue
        if is_formula_related_body_context(ctx):
            continue
        jc_val = get_w_attr(ctx["elem"].find("w:pPr/w:jc", NSMAP), "val")
        if jc_val == "center":
            continue
        jc = ctx["elem"].find("w:pPr/w:jc", NSMAP)
        if get_w_attr(jc, "val") != "both":
            bad_positions.append(ctx["index"])

    if bad_positions:
        return False, [f"{len(bad_positions)} 个正文段落未设置两端对齐。"], summarize_positions(bad_positions)
    return True, [], "全部正文段落"


def check_sp01(document_root, contexts, style_map):
    bad = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        elem = ctx["elem"].find("w:pPr/w:autoSpaceDE", NSMAP)
        val = get_w_attr(elem, "val") if elem is not None else "1"
        if val != "0":
            bad.append(ctx["index"])
    if bad:
        return False, [f"{len(bad)} 个正文段落未关闭中英文自动间距（autoSpaceDE≠0）。"], summarize_positions(bad)
    return True, [], "全部正文段落"


def check_sp02(document_root, contexts, style_map):
    bad = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        elem = ctx["elem"].find("w:pPr/w:autoSpaceDN", NSMAP)
        val = get_w_attr(elem, "val") if elem is not None else "1"
        if val != "0":
            bad.append(ctx["index"])
    if bad:
        return False, [f"{len(bad)} 个正文段落未关闭中数字自动间距（autoSpaceDN≠0）。"], summarize_positions(bad)
    return True, [], "全部正文段落"


def check_sp_cjk_latin(document_root, contexts, style_map, cfg):
    bad_positions = []
    samples = []
    for ctx in contexts:
        if ctx.get("section") != "body":
            continue
        if ctx.get("protected") or ctx.get("kind") in {"reference", "caption", "h1", "h2", "h3", "h4"}:
            continue
        matches = find_missing_spacing_pairs(ctx.get("text", ""), _needs_cjk_latin_space)
        if cfg and cfg.get("relax_body_spacing_rules"):
            matches = [match for match in matches if not re.search(r"\b\d+\s*T\b", match)]
        if cfg and cfg.get("relax_strain_suffix_t_spacing"):
            matches = [match for match in matches if not is_relaxed_strain_suffix_t_excerpt(match)]
        if matches:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段存在中英文紧邻：{excerpt(matches[0])}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落存在中英文字符间距缺失。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "正文段落中英文间距正常"


def check_sp_num_cjk(document_root, contexts, style_map, cfg):
    bad_positions = []
    samples = []
    for ctx in contexts:
        if ctx.get("section") != "body":
            continue
        if ctx.get("protected") or ctx.get("kind") in {"reference", "caption", "h1", "h2", "h3", "h4"}:
            continue
        matches = find_missing_spacing_pairs(ctx.get("text", ""), _needs_num_cjk_space)
        if cfg and cfg.get("relax_body_spacing_rules"):
            matches = [match for match in matches if not re.search(r"(图|表|式)\d", match)]
        if matches:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段存在中文与数字紧邻：{excerpt(matches[0])}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落存在中文与数字间距缺失。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "正文段落中文与数字间距正常"


def check_heading(contexts, heading_kind, expected_jc, require_size, expected_font=None, require_bold=False):
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_heading_audit_context(ctx, heading_kind):
            continue
        jc = ctx["elem"].find("w:pPr/w:jc", NSMAP)
        ind = ctx["elem"].find("w:pPr/w:ind", NSMAP)
        first_line = get_w_attr(ind, "firstLine")
        jc_val = get_w_attr(jc, "val")
        if expected_jc == "left" and jc_val is None:
            jc_val = "left"
        heading_ok = jc_val == expected_jc and (first_line in (None, "0"))

        run_ok = True
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            if not get_run_text(run_elem).strip():
                continue
            if require_bold and not is_bold(run_elem):
                run_ok = False
                break
            if not require_bold and is_bold(run_elem):
                run_ok = False
                break
            if require_size is not None:
                sz = run_elem.find("w:rPr/w:sz", NSMAP)
                if get_w_attr(sz, "val") != str(require_size):
                    run_ok = False
                    break
            if expected_font is not None:
                r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
                ea_font = get_w_attr(r_fonts, "eastAsia") if r_fonts is not None else None
                if ea_font is not None and ea_font != expected_font:
                    run_ok = False
                    break

        if not (heading_ok and run_ok):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段标题'{excerpt(ctx['text'])}'格式不符合要求")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个 {heading_kind} 段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部对应标题"


def check_heading_num_space(contexts):
    bad_positions = []
    issues = []

    for ctx in contexts:
        if ctx.get("kind") not in {"h2", "h3", "h4"}:
            continue
        if not is_heading_audit_context(ctx, ctx.get("kind")):
            continue
        text = ctx.get("text", "") or ""
        # 贪婪提取编号部分（防止回溯误判），再检测后续字符
        num_match = re.match(r"^(\d+(?:\s*\.\s*\d+)+)(.*)", text, re.DOTALL)
        if not num_match:
            continue
        num_prefix = num_match.group(1)
        rest = num_match.group(2)
        # 编号内部有乱空格（如 "1.1 .2"）
        has_inner_dot_space = (
            re.search(r"\s+\.", num_prefix) is not None
            or re.search(r"\.\s+", num_prefix) is not None
        )
        # 编号后紧跟非空字符（缺少空格）
        has_missing_gap = bool(rest) and not rest[0].isspace()
        if not (has_missing_gap or has_inner_dot_space):
            continue
        bad_positions.append(ctx["index"])
        if len(issues) < 5:
            issues.append(f"第{ctx['index']}段标题「{excerpt(text)}」编号格式不规范")

    if bad_positions:
        issues.insert(0, f"{len(bad_positions)} 个标题段落编号格式不规范。")
        return False, issues, summarize_positions(bad_positions)
    return True, [], "二三四级标题编号与文字间距合规"


def check_c01(document_root, contexts, style_map):
    count = 0
    for run_elem in document_root.findall(".//w:r", NSMAP):
        if is_superscript(run_elem) and re.search(r"\[\d+\]", get_run_text(run_elem)):
            count += 1

    if count == 0:
        return False, ["全文未发现任何上标格式的方括号引用。"], "全文"
    return True, [], f"发现 {count} 处上标引用"


def check_c02(document_root, contexts, style_map):
    total = 0
    samples = []
    positions = []
    paragraph_lookup = {}
    for ctx in contexts:
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            paragraph_lookup[id(run_elem)] = ctx["index"]

    for run_elem in document_root.findall(".//w:r", NSMAP):
        run_text = get_run_text(run_elem)
        if not (is_superscript(run_elem) and re.search(r"\[\d+\]", run_text)):
            continue
        r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
        ascii_font = get_w_attr(r_fonts, "ascii")
        hansi_font = get_w_attr(r_fonts, "hAnsi")
        east_asia = get_w_attr(r_fonts, "eastAsia")
        if ascii_font != "Times New Roman" or hansi_font != "Times New Roman" or east_asia != "Times New Roman":
            total += 1
            para_index = paragraph_lookup.get(id(run_elem))
            if para_index is not None:
                positions.append(para_index)
            if len(samples) < 3:
                samples.append(
                    f"上标引用'{excerpt(run_text)}'字体为 ascii={ascii_font}、hAnsi={hansi_font}、eastAsia={east_asia}"
                )

    if total:
        issues = [f"{total} 个上标引用 run 的字体不是 Times New Roman。"]
        issues.extend(samples)
        return False, issues, summarize_positions(positions)
    return True, [], "全部上标引用"


def check_c03(document_root, contexts, style_map):
    bad_positions = []
    samples = []
    for ctx in contexts:
        merged_parts = []
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text:
                continue
            if is_superscript(run_elem):
                run_text = re.sub(r"\[(\d{1,3})\]", r"⟦\1⟧", run_text)
            merged_parts.append(run_text)

        merged_text = "".join(merged_parts)
        if re.search(r"[。！？]\s*(?:⟦\d{1,3}⟧|\[\d{1,3}\])", merged_text):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                preview = re.sub(r"⟦(\d{1,3})⟧", r"[\1]", merged_text)
                samples.append(f"第{ctx['index']}段'{excerpt(preview)}'中引用位于句末标点之后")

    if bad_positions:
        return (
            False,
            [f"{len(set(bad_positions))} 处上标引用出现在句末标点（。）之后，应移至标点之前。"] + samples,
            summarize_positions(bad_positions),
        )
    return True, [], "全部上标引用"


def check_r01(document_root, contexts, style_map, cfg):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    expected = cfg["ref_hanging"]
    for ctx in references:
        ind = ctx["elem"].find("w:pPr/w:ind", NSMAP)
        hanging = parse_int(get_w_attr(ind, "hanging"))
        left = parse_int(get_w_attr(ind, "left"))
        if hanging != expected or left != expected:
            bad_positions.append(ctx["index"])

    if bad_positions:
        return (
            False,
            [f"{len(bad_positions)} 个参考文献段落未设置对称悬挂缩进（hanging=left，应为{expected}）。"],
            summarize_positions(bad_positions),
        )
    return True, [], "全部参考文献段落"


def check_r02(document_root, contexts, style_map, cfg):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    for ctx in references:
        if cfg["ref_use_tab"]:
            tabs = ctx["elem"].find("w:pPr/w:tabs", NSMAP)
            found = False
            if tabs is not None:
                for tab in tabs.findall("w:tab", NSMAP):
                    pos = parse_int(get_w_attr(tab, "pos"))
                    if get_w_attr(tab, "val") == "left" and pos is not None and pos >= cfg["ref_tab_min"]:
                        found = True
                        break
            if found:
                continue
        else:
            text = ctx["text"].replace("\u00a0", " ")
            has_tab = ctx["elem"].find(".//w:tab", NSMAP) is not None
            if not has_tab and re.match(r"^\[\d{1,3}\]\s+\S", text):
                continue
        bad_positions.append(ctx["index"])

    if bad_positions:
        if cfg["ref_use_tab"]:
            return (
                False,
                [f"{len(bad_positions)} 个参考文献段落缺少有效的左对齐制表位（pos >= {cfg['ref_tab_min']}）。"],
                summarize_positions(bad_positions),
            )
        return (
            False,
            [f"{len(bad_positions)} 个参考文献段落缺少编号后空格分隔，或仍在使用制表位。"],
            summarize_positions(bad_positions),
        )
    return True, [], "全部参考文献段落"


def check_r03(document_root, contexts, style_map, cfg):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    expected_line = cfg.get("ref_line_spacing") or 240
    for ctx in references:
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        line_val = parse_int(get_w_attr(spacing, "line"))
        if line_val != expected_line:
            bad_positions.append(ctx["index"])

    if bad_positions:
        return False, [f"{len(bad_positions)} 个参考文献段落行距不是 {expected_line}。"], summarize_positions(bad_positions)
    return True, [], "全部参考文献段落"


def check_r04(document_root, contexts, style_map):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    samples = []
    for ctx in references:
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if re.search(r"\[\d+\]", run_text) and is_superscript(run_elem):
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段参考文献引用'{excerpt(run_text)}'仍为上标")
                break

    if bad_positions:
        issues = [f"{len(bad_positions)} 个参考文献段落中的 [N] 引用仍为上标。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部参考文献段落"


INLINE_CITATION_PAT = re.compile(r"\[\d{1,3}(?:[,，、\-]\d{1,3})*\]")


def check_c04(document_root, contexts, style_map):
    """检查正文中是否有 [N] 引用混在正文 run 里（未拆出单独上标 run）。"""
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not INLINE_CITATION_PAT.search(run_text):
                continue
            # 如果整个 run 是独立引用 run 且已是上标，跳过
            if is_citation_run_text(run_text) and is_superscript(run_elem):
                continue
            # 引用混在正文 run 中（非纯引用 run），或纯引用 run 但不是上标
            if not is_superscript(run_elem):
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(
                        f"第{ctx['index']}段 run [{excerpt(run_text)}] 含引用但未设上标"
                    )
                break

    if bad_positions:
        issues = [
            f"{len(bad_positions)} 个正文段落存在未上标的嵌入引用 [N]（引用混在正文 run 中，未拆出独立上标 run）。"
        ]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部正文段落"


def check_r05(document_root, contexts, style_map, cfg):
    """检查参考文献制表位是否足够宽以对齐两位数编号（[10]+）。
    [10] 占约4字符，需要制表位 >= 480 twips；建议 560。
    """
    if not cfg["ref_use_tab"]:
        return True, [], "当前 Profile 使用空格分隔参考文献编号"

    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    for ctx in references:
        tabs = ctx["elem"].find("w:pPr/w:tabs", NSMAP)
        ok = False
        if tabs is not None:
            for tab in tabs.findall("w:tab", NSMAP):
                pos = parse_int(get_w_attr(tab, "pos"))
                if get_w_attr(tab, "val") == "left" and pos is not None and pos >= cfg["ref_tab_min"]:
                    ok = True
                    break
        if not ok:
            bad_positions.append(ctx["index"])

    if bad_positions:
        return (
            False,
            [
                f"{len(bad_positions)} 个参考文献段落的制表位 pos < {cfg['ref_tab_min']}，导致 [10]+ 编号与 [1]-[9] 不对齐。"
                f" 建议制表位 pos={cfg['ref_hanging']}，hanging={cfg['ref_hanging']}，left={cfg['ref_hanging']}。"
            ],
            summarize_positions(bad_positions),
        )
    return True, [], "全部参考文献段落"


def check_caption_format(contexts, prefix, label, cfg):
    captions = [ctx for ctx in contexts if ctx["kind"] == "caption" and ctx["text"].strip().startswith(prefix)]
    bad_positions = []
    samples = []
    min_size, max_size = cfg["caption_size_range"]
    sep_pattern = re.escape(cfg["caption_number_sep"])
    text_pattern = re.compile(rf"^{prefix}\s*\d+(?:{sep_pattern}\d+)?")

    for ctx in captions:
        problems = []
        jc_val = get_paragraph_alignment(ctx["elem"])
        if jc_val != "center":
            problems.append(f"对齐={jc_val or 'left(default)'}")

        run_sizes = [get_run_size(run_elem) for run_elem in get_non_empty_runs(ctx["elem"])]
        if not run_sizes or any(size is None or not (min_size <= size <= max_size) for size in run_sizes):
            problems.append(f"字号不在 {min_size}~{max_size}")

        if not text_pattern.match(ctx["text"].strip()):
            problems.append("题注编号格式异常")

        if problems:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段{label}'{excerpt(ctx['text'])}'存在问题：{'，'.join(problems)}")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个{label}段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], f"全部{label}"


def check_f01(document_root, contexts, style_map, cfg):
    return check_caption_format(contexts, "图", "图题", cfg)


def check_f02(document_root, contexts, style_map, cfg):
    return check_caption_format(contexts, "表", "表题", cfg)


def check_tb01(document_root, contexts, style_map):
    tables = get_non_equation_layout_tables(document_root)
    if not tables:
        return True, [], "文档无表格或仅含公式布局表"

    bad_tables = []
    issues = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        tbl_borders = tbl_elem.find("w:tblPr/w:tblBorders", NSMAP)
        problems = []
        for border_name, label in (("top", "顶线"), ("bottom", "底线")):
            border_elem = tbl_borders.find(f"w:{border_name}", NSMAP) if tbl_borders is not None else None
            border_size = parse_int(get_w_attr(border_elem, "sz"))
            if border_size is None or border_size < 10:
                problems.append(f"{label}线宽={get_w_attr(border_elem, 'sz')}")
        for border_name, label in (("left", "左竖线"), ("right", "右竖线"), ("insideV", "内部竖线")):
            border_elem = tbl_borders.find(f"w:{border_name}", NSMAP) if tbl_borders is not None else None
            if border_elem is None:
                continue
            border_val = get_w_attr(border_elem, "val")
            if border_val not in ("nil", "none"):
                problems.append(f"{label}未关闭(val={border_val})")
        if problems:
            bad_tables.append(table_index)
            issues.append(f"第{table_index}个表存在问题：{'，'.join(problems)}")

    if bad_tables:
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], f"全部{len(tables)}个表"


def check_h04(document_root, contexts, style_map, cfg):
    headings = [ctx for ctx in contexts if is_heading_audit_context(ctx, "h4")]
    if not headings:
        return True, [], "文档无四级标题"

    bad_positions = []
    samples = []
    expected_size = cfg["h4_size"]
    for ctx in headings:
        jc_val = get_paragraph_alignment(ctx["elem"]) or "left"
        first_line = get_paragraph_first_line(ctx["elem"])
        run_sizes = [get_run_size(run_elem) for run_elem in get_non_empty_runs(ctx["elem"])]
        run_ok = bool(run_sizes)
        if run_ok:
            for run_elem in get_non_empty_runs(ctx["elem"]):
                if cfg.get("h4_bold", False):
                    if not is_bold(run_elem):
                        run_ok = False
                        break
                elif is_bold(run_elem):
                    run_ok = False
                    break
                if get_run_size(run_elem) != expected_size:
                    run_ok = False
                    break
                expected_h4_font = cfg.get("h4_font", "宋体") or "宋体"
                r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
                east_asia = get_w_attr(r_fonts, "eastAsia") if r_fonts is not None else None
                if east_asia and east_asia not in (expected_h4_font, "SimSun"):
                    run_ok = False
                    break
        if jc_val != "left" or first_line not in (None, "0") or not run_ok:
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段四级标题'{excerpt(ctx['text'])}'格式不符合要求")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个 h4 段落格式不符合要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部四级标题"


def check_s01(document_root, contexts, style_map, cfg=None):
    """检查各级标题的段前/段后间距是否合规。"""
    issues = []
    affected_positions = []
    paragraph_tag = f"{{{W_NS}}}p"
    table_tag = f"{{{W_NS}}}tbl"
    body = document_root.find("w:body", NSMAP)
    body_children = list(body) if body is not None else []
    child_index = {id(elem): idx for idx, elem in enumerate(body_children)}

    def _preceded_by_table_gap_budget(p_elem) -> bool:
        idx = child_index.get(id(p_elem))
        if idx is None:
            return False
        scan_idx = idx - 1
        while scan_idx >= 0:
            candidate = body_children[scan_idx]
            if candidate.tag == table_tag:
                return True
            if candidate.tag != paragraph_tag:
                scan_idx -= 1
                continue
            if get_paragraph_text(candidate).strip():
                return False
            scan_idx -= 1
        return False

    def _heading_spec(level, label):
        if cfg and any(key in cfg for key in (f"{level}_spacing_before", f"{level}_spacing_after")):
            expected_before = int(cfg.get(f"{level}_spacing_before", 0) or 0)
            expected_after = int(cfg.get(f"{level}_spacing_after", 0) or 0)
            return dict(label=label, exact_before=expected_before, exact_after=expected_after)
        return dict(label=label, before_min=80, before_max=200, after_min=80, after_max=200)

    HEADING_SPECS = {
        "h1": _heading_spec("h1", "一级标题"),
        "h2": _heading_spec("h2", "二级标题"),
        "h3": _heading_spec("h3", "三级标题"),
    }

    for kind, spec in HEADING_SPECS.items():
        headings = [ctx for ctx in contexts if is_heading_audit_context(ctx, kind)]
        if not headings:
            continue
        label = spec["label"]
        for ctx in headings:
            spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
            before = parse_int(get_w_attr(spacing, "before")) if spacing is not None else None
            after  = parse_int(get_w_attr(spacing, "after"))  if spacing is not None else None

            bad_msgs = []
            if "exact_before" in spec:
                if before != spec["exact_before"]:
                    bad_msgs.append(f"段前={before}，应为{spec['exact_before']}")
                if after != spec["exact_after"]:
                    bad_msgs.append(f"段后={after}，应为{spec['exact_after']}")
            else:
                if before is None:
                    bad_msgs.append("段前未设置（应≥{}twips）".format(spec["before_min"]))
                elif before < spec["before_min"]:
                    bad_msgs.append("段前={}，低于{}".format(before, spec["before_min"]))
                elif before > spec["before_max"] and not _preceded_by_table_gap_budget(ctx["elem"]):
                    bad_msgs.append("段前={}，过大（上限{}）".format(before, spec["before_max"]))

                if after is None:
                    bad_msgs.append("段后未设置（应≥{}twips）".format(spec["after_min"]))
                elif after < spec["after_min"]:
                    bad_msgs.append("段后={}，低于{}".format(after, spec["after_min"]))
                elif after > spec["after_max"]:
                    bad_msgs.append("段后={}，过大（上限{}）".format(after, spec["after_max"]))

            if bad_msgs:
                affected_positions.append(ctx["index"])
                if len(issues) < 4:
                    issues.append("第{}段{}：{}".format(ctx["index"], label, "；".join(bad_msgs)))

    if affected_positions:
        total = len(affected_positions)
        issues.insert(0, "{}个标题段落间距不符合规范。".format(total))
        return False, issues, summarize_positions(affected_positions)
    return True, [], "各级标题段前段后间距合规"


def check_s03(document_root, contexts, style_map):
    """检查正文段落的段前/段后是否为0（辽大：正文段前=0，段后=0）。"""
    bad = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        if spacing is None:
            continue
        before = parse_int(get_w_attr(spacing, "before"))
        after  = parse_int(get_w_attr(spacing, "after"))
        msgs = []
        if before is not None and before > 60:
            msgs.append("段前={}（应为0）".format(before))
        if after is not None and after > 60:
            msgs.append("段后={}（应为0）".format(after))
        if msgs:
            bad.append((ctx["index"], "；".join(msgs)))

    if bad:
        issues = ["{} 个正文段落段前/段后间距不为0。".format(len(bad))]
        issues.extend("第{}段：{}".format(i, m) for i, m in bad[:4])
        return False, issues, summarize_positions([i for i, _ in bad])
    return True, [], "正文段前段后均为0"


def check_s02(document_root, contexts, style_map):
    h1_contexts = [ctx for ctx in contexts if is_heading_audit_context(ctx, "h1")]
    if len(h1_contexts) <= 1:
        return True, [], "文档仅有一个一级标题"

    bad_positions = []
    for ctx in h1_contexts[1:]:
        page_break = ctx["elem"].find("w:pPr/w:pageBreakBefore", NSMAP)
        if page_break is None or get_w_attr(page_break, "val") == "0":
            bad_positions.append(ctx["index"])

    if bad_positions:
        return False, [f"{len(bad_positions)} 个非首个一级标题缺少章节首页分页设置。"], summarize_positions(bad_positions)
    return True, [], "全部非首个一级标题已分页"


def check_fn01(document_root, contexts, style_map, footnotes_root):
    if footnotes_root is None:
        return True, [], "文档无脚注文件"

    issues = []
    affected_ids = []
    for footnote_elem in footnotes_root.findall(".//w:footnote", NSMAP):
        footnote_id = get_w_attr(footnote_elem, "id")
        if footnote_id in ("-1", "0"):
            continue
        for run_elem in footnote_elem.findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            size_val = get_run_size(run_elem)
            if size_val is None or size_val < 16:
                affected_ids.append(footnote_id)
                if len(issues) < 5:
                    issues.append(f"脚注 {footnote_id} 中 run '{excerpt(run_text)}' 字号为 {size_val}，低于 16。")
                break

    if affected_ids:
        return False, issues, "脚注 " + "、".join(sorted(set(affected_ids))[:5])
    return True, [], "全部脚注字号正常"


def check_pg01(document_root, contexts, style_map, cfg=None):
    issues = []
    zip_path = getattr(document_root, "_zip_path", None)
    passed = False
    affected = "全文"

    def _iter_footer_page_paragraphs():
        if not zip_path:
            return []
        paragraphs = []
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                footer_files = [n for n in zf.namelist() if n.startswith("word/footer") and n.endswith(".xml")]
                for fname in footer_files:
                    with zf.open(fname) as f:
                        footer_root = ET.parse(f).getroot()
                    for p in footer_root.findall(".//w:p", NSMAP):
                        has_page = any("PAGE" in (it.text or "").upper() for it in p.findall(".//w:instrText", NSMAP))
                        if has_page:
                            paragraphs.append((fname, p))
        except Exception:
            return []
        return paragraphs

    for instr_text in document_root.findall(".//w:instrText", NSMAP):
        if "PAGE" in (instr_text.text or "").upper():
            passed = True
            affected = "发现 PAGE 域"
            break
    if not passed and zip_path:
        for fname, _ in _iter_footer_page_paragraphs():
            passed = True
            affected = f"{fname} 中发现 PAGE 域"
            break
    if not passed:
        return False, ["文档中未发现 PAGE 页码域。"], "全文"

    page_style = (cfg or {}).get("pg01_format")
    if page_style in {"em_dash", "hyphen_wrap"}:
        wrap_char = "—" if page_style == "em_dash" else "-"
        expected = "—N—" if page_style == "em_dash" else "-N-"
        found_wrapped = False
        if zip_path:
            footer_paragraphs = _iter_footer_page_paragraphs()
            for _, p in footer_paragraphs:
                all_text = "".join(t.text or "" for t in p.findall(".//w:t", NSMAP))
                if wrap_char in all_text:
                    found_wrapped = True
                    break
        else:
            found_wrapped = any(wrap_char in (t.text or "") for t in document_root.findall(f".//{{{W_NS}}}t"))
        if not found_wrapped:
            issues.append(f"页码格式应为 {expected}，页脚中未检测到包围符号")
            passed = False

    expected_font = (cfg or {}).get("page_number_font")
    expected_size = parse_int((cfg or {}).get("page_number_size"))
    if expected_font or expected_size:
        footer_paragraphs = _iter_footer_page_paragraphs()
        for fname, paragraph in footer_paragraphs:
            for run_elem in paragraph.findall(".//w:r", NSMAP):
                if not (
                    run_elem.find("w:fldChar", NSMAP) is not None
                    or run_elem.find("w:instrText", NSMAP) is not None
                    or get_run_text(run_elem).strip()
                ):
                    continue
                east_asia = get_effective_run_font(run_elem, style_map, attr_name="eastAsia")
                size_val = get_effective_run_size(run_elem, style_map)
                if expected_font and east_asia != expected_font:
                    issues.append(f"页码字体应为 {expected_font}，实际为 {east_asia or '未设置'} ({fname})")
                    passed = False
                    break
                if expected_size is not None and size_val not in (expected_size, None):
                    issues.append(f"页码字号应为 {expected_size} half-pts，实际为 {size_val} ({fname})")
                    passed = False
                    break
            if not passed and issues:
                break

    return passed, issues, affected


def check_p03(document_root, contexts, style_map, cfg):
    """P03: 页码段落必须居中对齐。"""
    zip_path = getattr(document_root, "_zip_path", None)
    if zip_path is None:
        return True, [], "无法访问页脚文件（跳过）"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            footer_files = [n for n in zf.namelist() if n.startswith("word/footer") and n.endswith(".xml")]
            if not footer_files:
                return True, [], "文档无页脚"
            issues = []
            for fname in footer_files:
                with zf.open(fname) as f:
                    footer_root = ET.parse(f).getroot()
                for p in footer_root.findall(".//w:p", NSMAP):
                    has_page = any(
                        "PAGE" in (it.text or "").upper()
                        for it in p.findall(".//w:instrText", NSMAP)
                    )
                    if not has_page:
                        continue
                    jc = p.find("w:pPr/w:jc", NSMAP)
                    jc_val = get_w_attr(jc, "val") if jc is not None else None
                    if jc_val != "center":
                        issues.append(f"页码段落对齐方式为 {jc_val or '默认（左对齐）'}，应为居中")
    except Exception as e:
        return True, [], f"页脚解析失败（{e}），跳过"
    if issues:
        return False, issues, "页脚页码段落"
    return True, [], "页码居中正常"


def check_ref01(document_root, contexts, style_map):
    references = [ctx for ctx in contexts if ctx["kind"] == "reference"]
    bad_positions = []
    samples = []

    for ctx in references:
        text = ctx["text"].replace("\u00a0", " ")
        body_text = re.sub(r"^\[\d+\]\s*", "", text).strip()
        if not body_text:
            continue
        expected = "。" if is_mostly_cjk(body_text) else "."
        if not body_text.rstrip().endswith(expected):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段参考文献'{excerpt(body_text)}'结尾应为'{expected}")

    if bad_positions:
        issues = [f"{len(bad_positions)} 个参考文献段落末尾标点不符合语言规范。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部参考文献标点正常"


def _get_run_text_local(run_elem, w_ns):
    parts = []
    for text_elem in run_elem.findall(f".//{{{w_ns}}}t"):
        if text_elem.text:
            parts.append(text_elem.text)
    return "".join(parts)


def _is_run_bold_active(rpr, w_ns):
    if rpr is None:
        return False
    bold_elem = rpr.find(f"{{{w_ns}}}b")
    if bold_elem is None:
        return False
    return bold_elem.get(f"{{{w_ns}}}val", "1") not in ("0", "false", "False", "off")


def _collect_cn_keyword_style_issues(p_elem, cfg):
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    label_len = len("关键词")
    kw_font = cfg.get("kw_font") if cfg else None
    kw_bold = cfg.get("kw_bold") if cfg else None
    kw_size = cfg.get("kw_half_points") if cfg else None
    content_font = (
        (cfg or {}).get("abstract_body_font")
        or (cfg or {}).get("body_font")
        or "宋体"
    )
    issues = []
    consumed = 0

    for run_elem in p_elem.findall(f".//{{{w_ns}}}r"):
        run_text = _get_run_text_local(run_elem, w_ns)
        if not run_text:
            continue

        start = consumed
        end = consumed + len(run_text)
        consumed = end

        rpr = run_elem.find(f"{{{w_ns}}}rPr")
        fonts = rpr.find(f"{{{w_ns}}}rFonts") if rpr is not None else None
        east_asia = fonts.get(f"{{{w_ns}}}eastAsia") if fonts is not None else None
        size_elem = rpr.find(f"{{{w_ns}}}sz") if rpr is not None else None
        size_val = size_elem.get(f"{{{w_ns}}}val") if size_elem is not None else None
        bold_active = _is_run_bold_active(rpr, w_ns)

        if start < label_len < end:
            issues.append(f"关键词标签与内容应分开设置：标签用{kw_font or '黑体'}，内容用{content_font}")
            continue

        in_label = end <= label_len
        if in_label:
            if kw_font and east_asia != kw_font:
                issues.append(f"关键词标签字体应为{kw_font}，实为{east_asia or '未设置'}")
            if kw_bold is True and not bold_active:
                issues.append("关键词标签应加粗")
            if kw_bold is False and bold_active:
                issues.append("关键词标签不应加粗")
            if kw_size and size_val and int(size_val) != kw_size:
                issues.append(f"关键词标签字号应为{kw_size} half-pts，实为{size_val}")
            continue

        if east_asia != content_font:
            issues.append(f"关键词内容字体应为{content_font}，实为{east_asia or '未设置'}")
        if bold_active:
            issues.append("关键词内容不应加粗")
        if kw_size and size_val and int(size_val) != kw_size:
            issues.append(f"关键词内容字号应为{kw_size} half-pts，实为{size_val}")

    return issues


def _expected_keyword_separator(text, cfg):
    if is_cn_keywords_paragraph_text(text):
        return str((cfg or {}).get("kw_cn_separator", "；") or "；")
    return str((cfg or {}).get("kw_en_separator", "; ") or "; ")


def check_kw01(document_root, contexts, style_map, cfg):
    keyword_contexts = []
    for ctx in contexts:
        stripped = ctx["text"].strip()
        if is_keyword_paragraph_text(stripped):
            keyword_contexts.append(ctx)

    if not keyword_contexts:
        return True, [], "未发现关键词段落"

    bad_positions = []
    samples = []
    for ctx in keyword_contexts:
        text = ctx["text"].strip()
        payload = re.sub(r"^(关键词|key\s*words?)\s*[：:]\s*", "", text, count=1, flags=re.IGNORECASE).strip()
        problems = []
        expected_separator = _expected_keyword_separator(text, cfg)
        if text.endswith(("。", ".")):
            problems.append("末尾带句号")
        keywords = [item.strip() for item in re.split(r"[；;]", payload) if item.strip()]
        if len(keywords) >= 2:
            if expected_separator.strip() == "；":
                if "；" not in payload or ";" in payload:
                    problems.append("分隔符应为中文分号“；”")
            elif ";" not in payload:
                problems.append(f"分隔符应为“{expected_separator.strip()}”")
        elif "；" not in payload and ";" not in payload:
            problems.append("缺少分号分隔")
        if not (cfg["kw_min"] <= len(keywords) <= cfg["kw_max"]):
            problems.append(f"关键词数量为 {len(keywords)}")
        if problems:
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段关键词'{excerpt(text)}'存在问题：{'，'.join(problems)}")
    issues = []
    affected_positions = list(bad_positions)
    kw_font = cfg.get("kw_font") if cfg else None
    kw_bold_req = cfg.get("kw_bold") if cfg else None
    kw_hp = cfg.get("kw_half_points") if cfg else None
    if kw_font or kw_hp or kw_bold_req is not None:
        for ctx in keyword_contexts:
            text = ctx.get("text", "")
            if is_keyword_paragraph_text(text):
                p_elem = ctx.get("elem")
                if p_elem is None:
                    continue
                is_cn_keywords = is_cn_keywords_paragraph_text(text)
                if is_cn_keywords:
                    issues.extend(_collect_cn_keyword_style_issues(p_elem, cfg))

    if bad_positions:
        issues = [f"{len(bad_positions)} 个关键词段落格式不符合要求。"] + samples + issues
    if issues:
        issues = list(dict.fromkeys(issues))
        if not affected_positions and keyword_contexts:
            affected_positions = [keyword_contexts[0]["index"]]
        return False, issues, summarize_positions(affected_positions)
    return True, [], "全部关键词段落"


def check_kw02(document_root, contexts, style_map, cfg):
    bad_positions = []
    samples = []
    for ctx in contexts:
        text = (ctx.get("text") or "").strip()
        if not is_cn_keywords_paragraph_text(text):
            continue
        if re.search(r"[。，；：！？\.,:;!?]\s*$", text):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段关键词末尾有标点：{excerpt(text)}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个关键词段落末尾存在多余标点。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "关键词段落末尾无多余标点"


def check_eq01(document_root, contexts, style_map):
    """公式段落（含 m:oMath）必须居中、无首行缩进。"""
    def is_display_equation_context(ctx):
        if ctx["elem"].find(".//m:oMath", MNSMAP) is None:
            return False
        compact_text = re.sub(r"\s+", "", ctx["text"] or "")
        if not compact_text:
            return True
        if re.fullmatch(r"[（(]?\d+(?:[.\-]\d+)*[)）]?", compact_text):
            return True
        return False

    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_display_equation_context(ctx):
            continue
        if paragraph_in_equation_layout_table(document_root, ctx.get("elem")):
            continue
        jc_val = get_paragraph_alignment(ctx["elem"]) or "left"
        first_line = get_paragraph_first_line(ctx["elem"])
        if jc_val != "center" or first_line not in (None, "0"):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段公式段落对齐={jc_val}，firstLine={first_line}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个公式段落未居中或有首行缩进。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部公式段落"


def check_eq02(document_root, contexts, style_map, cfg=None):
    """公式编号 (X-Y) 应右对齐（右制表位或段落右对齐）。"""
    sep = re.escape(cfg.get("eq_number_sep", "-") if cfg else "-")
    eq_num_re = re.compile(r"\(\d+" + sep + r"\d+\)")
    bad_positions = []
    samples = []
    for ctx in contexts:
        has_math = ctx["elem"].find(".//m:oMath", MNSMAP) is not None
        if not has_math:
            continue
        para_text = ctx["text"]
        if not eq_num_re.search(para_text):
            continue
        tabs = ctx["elem"].find("w:pPr/w:tabs", NSMAP)
        has_right_tab = False
        if tabs is not None:
            for tab in tabs.findall("w:tab", NSMAP):
                if get_w_attr(tab, "val") == "right":
                    has_right_tab = True
                    break
        jc_val = get_paragraph_alignment(ctx["elem"])
        if not has_right_tab and jc_val not in ("right", "distribute"):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段含公式编号但无右对齐制表位")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个含编号公式段落缺少右对齐制表位。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部含编号公式段落"


def check_eq03(document_root, contexts, style_map):
    """正文中引用公式应使用 '式(X-Y)' 或 '式（X-Y）' 格式。"""
    bad_pat = re.compile(r"式\d")
    good_pat = re.compile(r"式[（(]\d+-\d+[)）]")
    bad_positions = []
    samples = []
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        text = ctx["text"]
        if not bad_pat.search(text):
            continue
        if good_pat.search(text):
            continue
        bad_positions.append(ctx["index"])
        if len(samples) < 3:
            samples.append(f"第{ctx['index']}段公式引用格式异常：\"{excerpt(text)}\"")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个正文段落的公式引用格式不符合 '式(X-Y)' 规范。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部公式引用"


def _check_caption_numbering(contexts, prefix, label, cfg):
    """检查图/表题注是否使用章节编号格式（图X-Y / 表X-Y）。"""
    captions = [ctx for ctx in contexts if ctx["kind"] == "caption" and ctx["text"].strip().startswith(prefix)]
    if not captions:
        return True, [], f"文档无{label}"
    gap_spaces = int((cfg or {}).get("caption_label_gap_spaces", 1) or 1)
    gap_pattern = r" " * gap_spaces
    chapter_pat = re.compile(
        rf"^{prefix}\s*\d+{re.escape(cfg['caption_number_sep'])}\d+(?:{gap_pattern}).+"
    )
    bad_positions = []
    samples = []
    for ctx in captions:
        stripped = ctx["text"].strip()
        if not chapter_pat.match(stripped):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(
                    f"第{ctx['index']}段{label}\"{excerpt(stripped)}\"编号或题名空格不符合要求（应为{prefix}X{cfg['caption_number_sep']}Y后接{gap_spaces}个半角空格）"
                )
    if bad_positions:
        issues = [f"{len(bad_positions)} 个{label}编号或题名空格不是章节式（{prefix}X{cfg['caption_number_sep']}Y 后 {gap_spaces} 个半角空格）格式。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], f"全部{label}"


def _is_toc_heading_style(style_id, style_map):
    return is_toc_heading_style_shared(style_id, style_map)


def _is_toc_entry_style(style_id, style_map):
    return is_toc_entry_style_shared(style_id, style_map)


def check_f03(document_root, contexts, style_map, cfg):
    return _check_caption_numbering(contexts, "图", "图题", cfg)


def check_f04(document_root, contexts, style_map, cfg):
    return _check_caption_numbering(contexts, "表", "表题", cfg)


def check_lnu_ack(document_root, contexts, style_map, cfg):
    ack_font = cfg.get("ack_font")
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

        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
            east_asia = get_w_attr(r_fonts, "eastAsia")
            if east_asia != ack_font:
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(
                        f"第{ctx['index']}段致谢正文'{excerpt(ctx['text'])}'字体为 {east_asia}，应为 {ack_font}"
                    )
                break

    if not found_ack_heading:
        if ack_required:
            return False, ["文档缺少致谢章节。"], "致谢"
        return True, [], "未发现致谢章节"
    if bad_positions:
        issues = [f"{len(bad_positions)} 个致谢正文段落字体不是 {ack_font}。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部致谢正文"


def check_lnu_f01(document_root, contexts, style_map, cfg):
    """LNU_F01: 图题编号格式应为 图X.X（点号）"""
    gap_spaces = int((cfg or {}).get("caption_label_gap_spaces", 1) or 1)
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
    """LNU_F02: 表题编号格式应为 表X.X（点号）"""
    gap_spaces = int((cfg or {}).get("caption_label_gap_spaces", 1) or 1)
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
    """LNU_F05: 图表在出现前应先在正文中被引用。"""
    caption_pattern = re.compile(r"^(图|表)\s*(\d+(?:[\.．-]\d+)+)")

    def _normalized_candidates(prefix: str, number: str) -> set[str]:
        normalized_number = re.sub(r"[．-]", ".", number)
        return {
            f"{prefix}{normalized_number}",
            f"{prefix}{normalized_number.replace('.', '-')}",
        }

    prior_body_contexts = []
    issues = []
    affected_positions = []

    for ctx in contexts:
        if is_main_body_context(ctx):
            prior_body_contexts.append(ctx)

        if ctx.get("kind") != "caption":
            continue

        caption_text = (ctx.get("text") or "").strip()
        match = caption_pattern.match(caption_text)
        if not match:
            continue

        prefix, number = match.groups()
        candidates = _normalized_candidates(prefix, number)
        referenced = False
        for prev_ctx in prior_body_contexts:
            normalized_text = re.sub(r"[\s\u3000]+", "", prev_ctx.get("text") or "")
            if any(token in normalized_text for token in candidates):
                referenced = True
                break

        if referenced:
            continue

        canonical = f"{prefix}{re.sub(r'[．-]', '.', number)}"
        issues.append(
            f"第{ctx['index']}段{prefix}题'{excerpt(caption_text)}'前缺少正文引用，建议在前文加入“如{canonical}所示”或“见{canonical}”。"
        )
        affected_positions.append(ctx["index"])

    if issues:
        header = f"{len(issues)} 个图表题注在出现前未在正文中被引用。"
        return False, [header] + issues[:5], summarize_positions(affected_positions)
    return True, [], "全部图表题注均已先文中引用"


def check_lnu_f06(document_root, contexts, style_map, cfg):
    """LNU_F06: 图题 1.5 倍行距；图注五号、单倍行距。"""
    expected_caption_line = cfg.get("figure_caption_line") or cfg.get("body_line") or 360
    expected_note_line = cfg.get("figure_note_line") or 240
    expected_note_size = cfg.get("caption_size") or 21

    issues = []
    affected_positions = []

    for ctx in contexts:
        if ctx.get("module") not in {"body_caption", "appendix_caption"}:
            continue
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        line_val = parse_int(get_w_attr(spacing, "line"))
        if line_val != expected_caption_line:
            issues.append(f"第{ctx['index']}段图题行距应为1.5倍（{expected_caption_line}），实际={line_val}。")
            affected_positions.append(ctx["index"])

    for ctx in contexts:
        if ctx.get("module") not in {"body_caption_note", "appendix_caption_note"}:
            continue
        spacing = ctx["elem"].find("w:pPr/w:spacing", NSMAP)
        line_val = parse_int(get_w_attr(spacing, "line"))
        if line_val != expected_note_line:
            issues.append(f"第{ctx['index']}段图注行距应为单倍（{expected_note_line}），实际={line_val}。")
            affected_positions.append(ctx["index"])
            continue

        for run_elem in get_non_empty_runs(ctx["elem"]):
            r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
            east_asia = get_w_attr(r_fonts, "eastAsia")
            ascii_font = get_w_attr(r_fonts, "ascii")
            size = get_run_size(run_elem)
            if east_asia not in ("宋体", "SimSun") or ascii_font != "Times New Roman" or size != expected_note_size:
                issues.append(
                    f"第{ctx['index']}段图注字体/字号应为宋体+Times New Roman、五号，实际 eastAsia={east_asia} ascii={ascii_font} size={size}。"
                )
                affected_positions.append(ctx["index"])
                break

    if issues:
        header = f"{len(affected_positions)} 个图题或图注版式不符合辽大要求。"
        return False, [header] + issues[:6], summarize_positions(affected_positions)
    return True, [], "全部图题与图注版式正常"


def check_lnu_ref01(document_root, contexts, style_map, cfg):
    """LNU_REF01: 参考文献标点应全用英文半角（不含全角标点）"""
    fullwidth = re.compile(r"[。，：；！？]")
    issues = []
    in_ref = False
    for ctx in contexts:
        text = ctx.get("text", "").strip()
        if re.match(r"^参考文献\s*$", text):
            in_ref = True
            continue
        if in_ref and re.match(r"^\[", text):
            m = fullwidth.search(text)
            if m:
                issues.append(text[:50])
        elif in_ref and text and not re.match(r"^\[", text):
            in_ref = False
    passed = len(issues) == 0
    affected = "; ".join(issues[:3]) if issues else ""
    return passed, issues, affected


def check_lnu_ref02(document_root, contexts, style_map, cfg):
    """LNU_REF02: 参考文献编号格式按 profile 要求处理。"""
    expect_space = bool(cfg.get("ref_number_trailing_space", cfg.get("ref_use_tab", False)))
    pattern = re.compile(r"^\[[1-9]\d{0,2}\]\s+\S") if expect_space else re.compile(r"^\[[1-9]\d{0,2}\]\S")
    tab_pattern = re.compile(r"^\[\d+\]\t")
    issues = []
    in_ref = False
    for ctx in contexts:
        text = ctx.get("text", "").strip()
        if re.match(r"^参考文献\s*$", text):
            in_ref = True
            continue
        if in_ref and re.match(r"^\[", text):
            number_match = re.match(r"^\[(\d+)\]", text)
            if number_match and len(number_match.group(1)) > 1 and number_match.group(1).startswith("0"):
                issues.append(f"编号补零: {text[:40]}")
            elif tab_pattern.match(text):
                issues.append(f"用了Tab: {text[:40]}")
            elif not pattern.match(text):
                issues.append(f"格式异常: {text[:40]}")
        elif in_ref and text and not re.match(r"^\[", text):
            in_ref = False
    passed = len(issues) == 0
    affected = "; ".join(issues[:3]) if issues else ""
    return passed, issues, affected


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
            if sz_val is not None and sz_val != 24:
                issues.append(f"英文摘要正文字号应为小四(24 half-pts)，实际={sz_val}，段落：{txt[:30]}")
                break
            ascii_font = get_effective_run_font(r, style_map, p, "ascii")
            if ascii_font is not None and ascii_font != "Times New Roman":
                issues.append(f"英文摘要正文字体应为 Times New Roman，实际={ascii_font}，段落：{txt[:30]}")
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
        text = ctx.get("text", "").strip()
        if not is_backmatter_pagebreak_title(text):
            continue
        has_break = False
        # 方式1：本段设置了 pageBreakBefore
        cur_elem = ctx.get("elem")
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
    for ctx in contexts:
        paragraph_kind = ctx.get("kind")
        if paragraph_kind not in ("h1", "h2", "h3", "h4"):
            continue
        text = (ctx.get("text") or "").strip()
        if is_lnu_title01_single_form(text):
            issues.append(f"「{text}」标题两字间应有两个空格，如「摘  要」")
    return (len(issues) == 0), issues, f"发现{len(issues)}处"


def check_lnu_tb03(document_root, contexts, style_map, cfg):
    """LNU_TB03: 表格内容应为单倍行距"""
    issues = []
    for tbl in document_root.findall(".//w:tbl", NSMAP):
        for cell in tbl.findall(".//w:tc", NSMAP):
            for p in cell.findall(".//w:p", NSMAP):
                line_val = get_paragraph_line_spacing(p, style_map)
                if line_val and line_val > 260:
                    issues.append(f"表格内容行距过大(line={line_val})，应为单倍(240)")
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


import re as _re
_UNIT_RE = _re.compile(r"(?<![0-9A-Za-z])(\d+(?:\.\d+)?)([A-Za-z]{1,4})(?![0-9A-Za-z])")
# 仅检查已知物理单位，避免对 PI3K/Akt、2D/3D、图表编号(2A/3B)等误报
_KNOWN_UNITS = {
    "g", "mg", "kg",
    "L", "mL",
    "m", "cm", "mm", "nm",
    "mol", "mmol",
    "Pa", "kPa", "MPa",
    "Hz", "kHz", "MHz",
    "kJ", "kDa", "Da",
    "rpm",
}

WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


def _paragraph_has_soft_break(p_elem):
    for br in p_elem.findall(".//w:br", NSMAP):
        br_type = get_w_attr(br, "type")
        if br_type not in {"page", "column"}:
            return True
    return p_elem.find(".//w:cr", NSMAP) is not None


def check_lnu_fmt01(document_root, contexts, style_map, cfg):
    """LNU_FMT01: 正文不应使用软回车（Shift+Enter）充当段落换行。"""
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
    """LNU_UNIT01: 正文数字与单位间应有空格（%℃除外）"""
    issues = []
    for ctx in contexts:
        if ctx.get("kind") != "body":
            continue
        text = ctx.get("text", "")
        for m in _UNIT_RE.finditer(text):
            unit = m.group(2)
            if unit in _KNOWN_UNITS:
                snippet = text[max(0, m.start() - 5):m.end() + 5]
                issues.append(f"数字后紧跟单位「{unit}」应加空格，上下文：{snippet}")
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


_CITATION_NUM_RE = re.compile(r"\[(\d+(?:[-,，、]\d+)*)\]")


def _expand_citation_numbers(raw):
    normalized = str(raw or "").replace("，", ",").replace("、", ",")
    numbers = []
    for part in normalized.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError:
                continue
            if start <= end:
                numbers.extend(range(start, end + 1))
            else:
                numbers.extend(range(end, start + 1))
        else:
            try:
                numbers.append(int(part))
            except ValueError:
                continue
    return numbers


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
    tbl_count = 0
    for tbl in get_non_equation_layout_tables(document_root):
        tbl_count += 1
        tbl_borders = tbl.find("w:tblPr/w:tblBorders", NSMAP)
        if tbl_borders is None:
            issues.append(f"第{tbl_count}个表格缺少边框定义")
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
        if len(issues) >= 5:
            break
    if toc_count == 0 and toc_has_field:
        return True, [], "目录为 TOC 域，待 Word 刷新可见条目"
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
                expected_entry_size = cfg.get("toc_level1_size", cfg.get("toc_entry_size", 24)) if cfg else 24
                expected_entry_font = cfg.get("toc_level1_font", cfg.get("toc_entry_font", "宋体")) if cfg else "宋体"
            else:
                expected_entry_size = cfg.get("toc_entry_size", 24) if cfg else 24
                expected_entry_font = cfg.get("toc_entry_font", "宋体") if cfg else "宋体"
            for run_elem in get_non_empty_runs(p_elem):
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
    """LNU_TOC03: 目录必须为 Word 自动生成域，不应手敲。"""
    toc_title_found = False
    toc_generated = False

    for p_elem in document_root.findall(".//w:p", NSMAP):
        text = get_paragraph_text(p_elem).strip()
        if is_toc_title(text):
            toc_title_found = True

        p_style = p_elem.find("w:pPr/w:pStyle", NSMAP)
        style_val = (get_w_attr(p_style, "val") or "").strip()
        if is_toc_generated_style_id(style_val):
            toc_generated = True
            break

        if has_toc_field_instr(p_elem, NSMAP):
            toc_generated = True
        if toc_generated:
            break

    if not toc_title_found and not toc_generated:
        return True, [], "文档无目录区段"
    if toc_generated:
        return True, [], "目录包含 TOC 自动生成域"
    return False, ["检测到目录标题，但未发现 TOC 域或 TOC 样式，目录应自动生成，不要手敲。"], "目录区段"


def check_body_font(document_root, contexts, style_map, cfg):
    """C01-ext: 正文中文应为宋体/SimSun"""
    issues = []
    expected_cn = cfg.get("body_font_cn", "宋体")
    checked = 0
    for ctx in contexts:
        if not is_main_body_context(ctx):
            continue
        p = ctx.get("elem")
        if p is None:
            continue
        checked += 1
        for run in p.findall(".//w:r", NSMAP):
            rpr = run.find("w:rPr", NSMAP)
            if rpr is None:
                continue
            fonts = rpr.find("w:rFonts", NSMAP)
            if fonts is None:
                continue
            east_asia = get_w_attr(fonts, "eastAsia")
            if east_asia and east_asia not in (expected_cn, "SimSun", ""):
                issues.append(f"正文中文字体应为{expected_cn}，实际={east_asia}")
                break
        if len(issues) >= 5:
            break
    return (len(issues) == 0), issues, f"抽查{checked}个正文段落"


def check_f05(document_root, contexts, style_map):
    """图表题注（caption 类段落）run 字体应为宋体+Times New Roman。"""
    captions = [
        ctx
        for ctx in contexts
        if ctx["kind"] == "caption" or ctx.get("module") in {"body_caption_note", "appendix_caption_note"}
    ]
    if not captions:
        return True, [], "文档无图表题注"
    bad_positions = []
    samples = []
    for ctx in captions:
        for run_elem in ctx["elem"].findall(".//w:r", NSMAP):
            run_text = get_run_text(run_elem)
            if not run_text.strip():
                continue
            r_fonts = run_elem.find("w:rPr/w:rFonts", NSMAP)
            east_asia = get_w_attr(r_fonts, "eastAsia")
            ascii_font = get_w_attr(r_fonts, "ascii")
            has_cjk = bool(CJK_CHAR_RE.search(run_text))
            has_latin_or_digit = bool(re.search(r"[A-Za-z0-9]", run_text))
            east_asia_ok = east_asia in ("宋体", "SimSun")
            ascii_ok = ascii_font == "Times New Roman"
            if has_cjk and not east_asia_ok:
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段题注字体 eastAsia={east_asia}，ascii={ascii_font}")
                break
            if has_latin_or_digit and not ascii_ok:
                bad_positions.append(ctx["index"])
                if len(samples) < 3:
                    samples.append(f"第{ctx['index']}段题注字体 eastAsia={east_asia}，ascii={ascii_font}")
                break
    if bad_positions:
        issues = [f"{len(bad_positions)} 个图表题注段落字体不符合宋体+Times New Roman要求。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部图表题注"


def check_f06(document_root, contexts, style_map):
    """含图片（w:drawing）的段落应居中、无首行缩进。"""
    bad_positions = []
    samples = []
    for ctx in contexts:
        has_drawing = ctx["elem"].find(".//w:drawing", NSMAP) is not None
        if not has_drawing:
            continue
        jc_val = get_paragraph_alignment(ctx["elem"]) or "left"
        first_line = get_paragraph_first_line(ctx["elem"])
        if jc_val != "center" or first_line not in (None, "0"):
            bad_positions.append(ctx["index"])
            if len(samples) < 3:
                samples.append(f"第{ctx['index']}段图片段落对齐={jc_val}，firstLine={first_line}")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个图片段落未居中或有首行缩进。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部图片段落"


def check_f07(document_root, contexts, style_map):
    """图题末尾不应以句号（。或.）结尾。"""
    captions = [ctx for ctx in contexts if ctx["kind"] == "caption" and ctx["text"].strip().startswith("图")]
    if not captions:
        return True, [], "文档无图题"
    bad_positions = []
    samples = []
    for ctx in captions:
        stripped = ctx["text"].rstrip()
        if stripped.endswith("。") or stripped.endswith("."):
            bad_positions.append(ctx["index"])
            if len(samples) < 5:
                samples.append(f"第{ctx['index']}段图题\"{excerpt(stripped)}\"末尾有句号")
    if bad_positions:
        issues = [f"{len(bad_positions)} 个图题末尾带有句号（图题不加句号）。"]
        issues.extend(samples)
        return False, issues, summarize_positions(bad_positions)
    return True, [], "全部图题"


def check_tb03_line(document_root, contexts, style_map):
    """三线表应有栏目线：第一行每个单元格底边框 sz >= 6（0.75pt）。"""
    tables = get_non_equation_layout_tables(document_root)
    if not tables:
        return True, [], "文档无表格或仅含公式布局表"
    bad_tables = []
    issues = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        rows = tbl_elem.findall("w:tr", NSMAP)
        if not rows:
            continue
        first_row = rows[0]
        cells = first_row.findall("w:tc", NSMAP)
        if not cells:
            continue
        row_has_bottom = False
        for cell in cells:
            bottom_border = cell.find("w:tcPr/w:tcBorders/w:bottom", NSMAP)
            if bottom_border is not None:
                sz = parse_int(get_w_attr(bottom_border, "sz"))
                val = get_w_attr(bottom_border, "val")
                if sz is not None and sz >= 6 and val not in ("nil", "none"):
                    row_has_bottom = True
                    break
        if not row_has_bottom:
            bad_tables.append(table_index)
            issues.append(f"第{table_index}个表格首行（表头）缺少底边框（栏目线），无法形成三线表中间分隔线")
    if bad_tables:
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], f"全部{len(tables)}个表格"


def check_tb02_no_vline(document_root, contexts, style_map, cfg):
    """TB02: 三线表不应有内部竖线（insideV 应为 none 或不存在）"""
    tables = document_root.findall(".//w:tbl", NSMAP)
    if not tables:
        return True, [], "文档无表格"
    bad_tables = []
    issues = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        tbl_pr = tbl_elem.find("w:tblPr", NSMAP)
        if tbl_pr is None:
            continue
        tbl_borders = tbl_pr.find("w:tblBorders", NSMAP)
        if tbl_borders is None:
            continue
        inside_v = tbl_borders.find("w:insideV", NSMAP)
        if inside_v is not None:
            val = get_w_attr(inside_v, "val") or "none"
            sz_str = get_w_attr(inside_v, "sz") or "0"
            try:
                sz = int(sz_str)
            except ValueError:
                sz = 0
            if val not in ("none", "nil") and sz > 0:
                bad_tables.append(table_index)
                issues.append(f"第{table_index}个表格存在内部竖线（insideV val={val}, sz={sz}），三线表不应有竖线")
    if bad_tables:
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], f"全部{len(tables)}个表格无多余竖线"


def check_tb03(document_root, contexts, style_map):
    """跨页表格应设置表头重复（w:tblHeader）。"""
    tables = document_root.findall(".//w:tbl", NSMAP)
    if not tables:
        return True, [], "文档无表格"
    bad_tables = []
    for table_index, tbl_elem in enumerate(tables, start=1):
        rows = tbl_elem.findall("w:tr", NSMAP)
        if len(rows) < 6:
            continue
        first_row = rows[0]
        tbl_header = first_row.find("w:trPr/w:tblHeader", NSMAP)
        if tbl_header is None:
            bad_tables.append(table_index)
    if bad_tables:
        issues = [f"{len(bad_tables)} 个较长表格（>=6行）首行未设置 w:tblHeader，跨页时表头不会重复。"]
        return False, issues, summarize_table_positions(bad_tables)
    return True, [], "全部较长表格"


_PU01_CJK_RE = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_PU01_HALF_PUNCT_RE = re.compile(
    rf"(?<={_PU01_CJK_RE})[,;:]|[,;:](?={_PU01_CJK_RE})|(?<={_PU01_CJK_RE})\.(?!\d)|\.(?={_PU01_CJK_RE})"
)


def _has_half_width_punct_in_cjk_context(text: str) -> bool:
    return _PU01_HALF_PUNCT_RE.search(text or "") is not None


def check_pu01(document_root, contexts, style_map, cfg):
    """PU01: 中文正文中不应使用英文半角标点（,.;:） 代替全角标点（，。；：）"""
    skip_kinds = {"reference", "caption"}
    issues = []
    for ctx in contexts:
        if ctx.get("effective_section") not in {"body", "appendix"}:
            continue
        if ctx.get("kind") in skip_kinds:
            continue
        elem = ctx.get("elem")
        if elem is not None and elem.find(".//m:oMath", MNSMAP) is not None:
            continue
        txt = ctx.get("text", "")
        if _has_half_width_punct_in_cjk_context(txt):
            snippet = txt.strip()[:50]
            issues.append(f"第{ctx['index']}段正文中存在英文半角标点夹在中文字符中：{snippet}")
        if len(issues) >= 5:
            break
    if not issues:
        return True, [], "全文"
    return False, issues, f"{len(issues)} 处"


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


def check_pu02(document_root, contexts, style_map, cfg):
    """PU02: 省略号应使用 ……（中文），不得用 ......（英文点号）"""
    paras = document_root.findall(".//w:p", NSMAP)
    issues = []
    for p in paras:
        runs = p.findall(".//w:r", NSMAP)
        txt = "".join(get_run_text(r) for r in runs)
        if re.search(r"\.{3,}", txt):
            snippet = txt.strip()[:50]
            issues.append(f"省略号应用 ……（中文），不可用点号代替：{snippet}")
        if len(issues) >= 5:
            break
    if not issues:
        return True, [], "全文"
    return False, issues, f"{len(issues)} 处"


RULE_CHECKERS = {
    "P01": lambda doc, ctxs, sm, cfg: check_p01(doc, ctxs, sm, cfg),
    "T01": lambda doc, ctxs, sm, cfg: check_t01(doc, ctxs, sm),
    "T02": lambda doc, ctxs, sm, cfg: check_t02(doc, ctxs, sm),
    "T03": lambda doc, ctxs, sm, cfg: check_t03(doc, ctxs, sm, cfg),
    "T04": lambda doc, ctxs, sm, cfg: check_t04(doc, ctxs, sm, cfg),
    "T05": lambda doc, ctxs, sm, cfg: check_t05(doc, ctxs, sm),
    "T06": lambda doc, ctxs, sm, cfg: check_t06(doc, ctxs, sm),
    "H01": lambda doc, ctxs, sm, cfg: check_heading(
        ctxs,
        "h1",
        "center",
        cfg["h1_size"],
        expected_font=cfg.get("h1_font"),
        require_bold=cfg.get("h1_bold", False),
    ),
    "H02": lambda doc, ctxs, sm, cfg: check_heading(
        ctxs,
        "h2",
        "left",
        cfg["h2_size"],
        expected_font=cfg.get("h2_font"),
        require_bold=cfg.get("h2_bold", False),
    ),
    "H03": lambda doc, ctxs, sm, cfg: check_heading(
        ctxs,
        "h3",
        "left",
        cfg["h3_size"],
        expected_font=cfg.get("h3_font"),
        require_bold=cfg.get("h3_bold", False),
    ),
    "C01": lambda doc, ctxs, sm, cfg: check_c01(doc, ctxs, sm),
    "C02": lambda doc, ctxs, sm, cfg: check_c02(doc, ctxs, sm),
    "C03": lambda doc, ctxs, sm, cfg: check_c03(doc, ctxs, sm),
    "C04": lambda doc, ctxs, sm, cfg: check_c04(doc, ctxs, sm),
    "R01": lambda doc, ctxs, sm, cfg: check_r01(doc, ctxs, sm, cfg),
    "R02": lambda doc, ctxs, sm, cfg: check_r02(doc, ctxs, sm, cfg),
    "R03": lambda doc, ctxs, sm, cfg: check_r03(doc, ctxs, sm, cfg),
    "R04": lambda doc, ctxs, sm, cfg: check_r04(doc, ctxs, sm),
    "R05": lambda doc, ctxs, sm, cfg: check_r05(doc, ctxs, sm, cfg),
    "F01": lambda doc, ctxs, sm, cfg: check_f01(doc, ctxs, sm, cfg),
    "F02": lambda doc, ctxs, sm, cfg: check_f02(doc, ctxs, sm, cfg),
    "TB01": lambda doc, ctxs, sm, cfg: check_tb01(doc, ctxs, sm),
    "H04": lambda doc, ctxs, sm, cfg: check_h04(doc, ctxs, sm, cfg),
    "S01": lambda doc, ctxs, sm, cfg: check_s01(doc, ctxs, sm, cfg),
    "S02": lambda doc, ctxs, sm, cfg: check_s02(doc, ctxs, sm),
    "S03": lambda doc, ctxs, sm, cfg: check_s03(doc, ctxs, sm),
    "FN01": lambda doc, ctxs, sm, cfg, footnotes_root: check_fn01(doc, ctxs, sm, footnotes_root),
    "PG01": lambda doc, ctxs, sm, cfg: check_pg01(doc, ctxs, sm, cfg),
    "P03": lambda doc, ctxs, sm, cfg: check_p03(doc, ctxs, sm, cfg),
    "REF01": lambda doc, ctxs, sm, cfg: check_ref01(doc, ctxs, sm),
    "KW01": lambda doc, ctxs, sm, cfg: check_kw01(doc, ctxs, sm, cfg),
    "EQ01": lambda doc, ctxs, sm, cfg: check_eq01(doc, ctxs, sm),
    "EQ02": lambda doc, ctxs, sm, cfg: check_eq02(doc, ctxs, sm, cfg),
    "EQ03": lambda doc, ctxs, sm, cfg: check_eq03(doc, ctxs, sm),
    "F03": lambda doc, ctxs, sm, cfg: check_f03(doc, ctxs, sm, cfg),
    "F04": lambda doc, ctxs, sm, cfg: check_f04(doc, ctxs, sm, cfg),
    "F05": lambda doc, ctxs, sm, cfg: check_f05(doc, ctxs, sm),
    "F06": lambda doc, ctxs, sm, cfg: check_f06(doc, ctxs, sm),
    "F07": lambda doc, ctxs, sm, cfg: check_f07(doc, ctxs, sm),
    "TB03_LINE": lambda doc, ctxs, sm, cfg: check_tb03_line(doc, ctxs, sm),
    "TB02": lambda doc, ctxs, sm, cfg: check_tb02_no_vline(doc, ctxs, sm, cfg),
    "TB03": lambda doc, ctxs, sm, cfg: check_tb03(doc, ctxs, sm),
    "SP01": lambda doc, ctxs, sm, cfg: check_sp01(doc, ctxs, sm),
    "SP02": lambda doc, ctxs, sm, cfg: check_sp02(doc, ctxs, sm),
    "SP_CJK_LATIN": lambda doc, ctxs, sm, cfg: check_sp_cjk_latin(doc, ctxs, sm, cfg),
    "SP_NUM_CJK": lambda doc, ctxs, sm, cfg: check_sp_num_cjk(doc, ctxs, sm, cfg),
    "KW02": lambda doc, ctxs, sm, cfg: check_kw02(doc, ctxs, sm, cfg),
    "LNU_ACK01": lambda doc, ctxs, sm, cfg: check_lnu_ack(doc, ctxs, sm, cfg),
    "LNU_H01": lambda doc, ctxs, sm, cfg: check_heading_num_space(ctxs),
    "PU02": lambda doc, ctxs, sm, cfg: check_pu02(doc, ctxs, sm, cfg),
    "PU01": lambda doc, ctxs, sm, cfg: check_pu01(doc, ctxs, sm, cfg),
}

LNU_RULE_CHECKERS = {
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
    "LNU_TB01": check_lnu_tb01,
    "LNU_TOC01": check_lnu_toc01,
    "LNU_TOC02": check_lnu_toc02,
    "LNU_TOC03": check_lnu_toc03,
    "LNU_F05": lambda doc, ctxs, sm, cfg: check_lnu_f05(doc, ctxs, sm, cfg),
    "LNU_TB02": lambda doc, ctxs, sm, cfg: check_lnu_tb02(doc, ctxs, sm, cfg),
    "LNU_TB04": lambda doc, ctxs, sm, cfg: check_lnu_tb04(doc, ctxs, sm, cfg),
    "LNU_ABS01": lambda doc, ctxs, sm, cfg: check_lnu_abs01(doc, ctxs, sm, cfg),
    "LNU_ABS02": lambda doc, ctxs, sm, cfg: check_lnu_abs02(doc, ctxs, sm, cfg),
    "LNU_ABS03": lambda doc, ctxs, sm, cfg: check_lnu_abs03(doc, ctxs, sm, cfg),
    "LNU_ABS04": lambda doc, ctxs, sm, cfg: check_lnu_abs04(doc, ctxs, sm, cfg),
    "LNU_H01": lambda doc, ctxs, sm, cfg: check_heading_num_space(ctxs),
    "LNU_CONC01": lambda doc, ctxs, sm, cfg: check_lnu_conc01(doc, ctxs, sm, cfg),
    "LNU_S03": lambda doc, ctxs, sm, cfg: check_lnu_s03(doc, ctxs, sm, cfg),
    "LNU_TITLE01": lambda doc, ctxs, sm, cfg: check_lnu_title01(doc, ctxs, sm, cfg),
    "LNU_TB03": lambda doc, ctxs, sm, cfg: check_lnu_tb03(doc, ctxs, sm, cfg),
    "LNU_UNIT01": lambda doc, ctxs, sm, cfg: check_lnu_unit01(doc, ctxs, sm, cfg),
}


def build_rule_definitions(profile_id, disabled_rules=()):
    rule_definitions = list(RULE_DEFINITIONS)
    if profile_id.startswith("lnu-"):
        rule_definitions.extend(LNU_RULE_DEFINITIONS)
    disabled = set(disabled_rules or ())
    if disabled:
        rule_definitions = [rule for rule in rule_definitions if rule[0] not in disabled]
    return tuple(rule_definitions)


def build_rule_checkers(profile_id, disabled_rules=()):
    rule_checkers = dict(RULE_CHECKERS)
    if profile_id.startswith("lnu-"):
        rule_checkers.update(LNU_RULE_CHECKERS)
    for rule_id in set(disabled_rules or ()):
        rule_checkers.pop(rule_id, None)
    return rule_checkers


def build_audit_runtime(profile_path=None, strict_profile=None):
    bundle = load_profile_bundle(
        profile_path,
        yaml_lib=yaml,
        warn=warn_profile,
        aliases=PROFILE_ALIASES,
        strict=strict_profile,
    )
    profile_id, profile_data, settings = bundle.profile_id, bundle.profile_data, bundle.settings
    cfg = build_profile_cfg(profile_id, profile_data, settings)
    disabled_rules = profile_data.get("disabled_rules") or []
    return AuditRuntime(
        cfg=cfg,
        rule_definitions=build_rule_definitions(profile_id, disabled_rules),
        rule_checkers=build_rule_checkers(profile_id, disabled_rules),
        profile_id=profile_id,
        requested_profile=bundle.requested_profile,
        fallback_used=bundle.fallback_used,
    )


def calculate_score(results):
    score = 100
    for result in results:
        if not result["passed"]:
            score -= SEVERITY_SCORES[result["severity"]]
    return max(score, 0)


def generate_markdown_report(file_path, results, score):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 📋 论文格式审查报告",
        "",
        f"**文件**：{os.path.basename(file_path)}",
        f"**审查时间**：{timestamp}",
        f"**总评分**：{score}/100",
        "",
        "---",
        "",
    ]

    for severity in ("critical", "important", "minor"):
        failed = [result for result in results if result["severity"] == severity and not result["passed"]]
        title = SEVERITY_LABELS[severity]
        suffix = {
            "critical": "必须修复",
            "important": "建议修复",
            "minor": "",
        }[severity]
        header = f"## ❌ {title}{len(failed)}项" if severity == "critical" else (
            f"## ⚠️ {title}{len(failed)}项" if severity == "important" else f"## ℹ️ {title}{len(failed)}项"
        )
        if suffix:
            header += f" — {suffix}"
        lines.append(header)
        lines.append("")
        if failed:
            lines.append("| 规则ID | 规则名称 | 问题描述 | 受影响位置 |")
            lines.append("|--------|---------|---------|-----------|")
            for result in failed:
                description = "；".join([markdown_escape(issue) for issue in result["issues"]]) or "未通过"
                lines.append(
                    f"| {result['id']} | {markdown_escape(result['name'])} | {description} | {markdown_escape(result['affected'])} |"
                )
        else:
            lines.append("无")
        lines.append("")

    passed_ids = [result["id"] for result in results if result["passed"]]
    lines.append(f"## ✅ 通过的规则（{len(passed_ids)}/{len(results)}）")
    lines.append(" | ".join([f"{result['id']} ✓" for result in results if result["passed"]]) or "无")
    lines.append("")
    lines.append("---")
    lines.append("*推荐使用 `scripts/thesis_workbench.py plan/apply/verify` 处理问题；底层引擎可直接调用 `fix_thesis.py`。*")
    lines.append("")
    return "\n".join(lines)


def audit_roots(file_path, document_root, styles_root, footnotes_root=None, cfg=None, runtime=None):
    if runtime is None:
        runtime = AuditRuntime(
            cfg=clone_default_cfg() if cfg is None else cfg,
            rule_definitions=tuple(RULE_DEFINITIONS),
            rule_checkers=dict(RULE_CHECKERS),
            profile_id="cn-common",
        )
    cfg = runtime.cfg if cfg is None else cfg
    style_map = build_style_map(styles_root)
    contexts = build_paragraph_contexts(document_root, style_map)
    results = []
    for rule_id, rule_name, severity in runtime.rule_definitions:
        if rule_id == "FN01":
            passed, issues, affected = runtime.rule_checkers[rule_id](document_root, contexts, style_map, cfg, footnotes_root)
        else:
            passed, issues, affected = runtime.rule_checkers[rule_id](document_root, contexts, style_map, cfg)
        results.append(make_result(rule_id, rule_name, severity, passed, issues, affected))
    score = calculate_score(results)
    report = generate_markdown_report(file_path, results, score)
    return results, score, report


def audit_docx_with_runtime(file_path, profile_path=None, strict_profile=None):
    runtime = build_audit_runtime(profile_path, strict_profile=strict_profile)
    document_xml, styles_xml, footnotes_xml = load_docx_xml(file_path)
    document_root = ET.fromstring(document_xml)
    document_root = DocumentRootProxy(document_root, file_path)
    styles_root = ET.fromstring(styles_xml)
    footnotes_root = ET.fromstring(footnotes_xml) if footnotes_xml else None
    results, score, report = audit_roots(
        file_path,
        document_root,
        styles_root,
        footnotes_root=footnotes_root,
        cfg=runtime.cfg,
        runtime=runtime,
    )
    return results, score, report, runtime


def audit_docx(file_path, profile_path=None, strict_profile=None):
    results, score, report, _runtime = audit_docx_with_runtime(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    return results, score, report


def main():
    parser = argparse.ArgumentParser(description="审查 DOCX 论文格式")
    parser.add_argument("file", help="待审查的 .docx 文件路径")
    parser.add_argument("--profile", default=None, help="学校Profile路径或简称（lnu/cn-common）")
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
        help="profile 加载失败时回退到默认 CN-Common 配置",
    )
    args = parser.parse_args()

    try:
        results, score, report, runtime = audit_docx_with_runtime(
            args.file,
            profile_path=args.profile,
            strict_profile=args.strict_profile,
        )
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")
    failed = [result for result in results if not result.get("passed")]
    print(f"文件: {os.path.basename(args.file)}")
    print(f"Profile: {format_profile_resolution(runtime.profile_id, runtime.requested_profile, runtime.fallback_used)}")
    print(f"评分: {score}/100")
    print(f"未通过规则: {len(failed)}")
    if failed:
        for result in failed:
            print(f"- {result['id']} {result['name']}")


if __name__ == "__main__":
    main()
