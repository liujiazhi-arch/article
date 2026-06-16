from dataclasses import dataclass, replace
import re
import xml.etree.ElementTree as ET

from backmatter_title_utils import (
    ABSTRACT_CN_TITLES,
    ABSTRACT_EN_TITLES,
    TOC_TITLES,
    detect_backmatter_bucket,
    is_abstract_cn_title,
    is_abstract_en_title,
    is_toc_title,
)
from frontmatter_utils import is_keywords_text, is_toc_entry_style, is_toc_generated_style_id, is_toc_heading_style


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NSMAP = {"w": W_NS}
_NAME_TO_LEVEL = {
    "heading 1": 0,
    "heading1": 0,
    "标题 1": 0,
    "标题1": 0,
    "title": 0,
    "heading 2": 1,
    "heading2": 1,
    "标题 2": 1,
    "标题2": 1,
    "heading 3": 2,
    "heading3": 2,
    "标题 3": 2,
    "标题3": 2,
    "heading 4": 3,
    "heading4": 3,
    "标题 4": 3,
    "标题4": 3,
}

HEADING_PATTERNS: dict[int, re.Pattern[str]] = {
    1: re.compile(r"^第[一二三四五六七八九十百\d]+[章节篇]"),
    2: re.compile(r"^\d+\.\d+(?!\.\d)\s*\S"),
    3: re.compile(r"^\d+\.\d+\.\d+(?!\.\d)\s*\S"),
    4: re.compile(r"^\d+\.\d+\.\d+\.\d+"),
}
ARABIC_H1_PATTERN = re.compile(r"^\d+(?![.\d])\s+\S")
UNNUMBERED_H1_TITLES = frozenset(
    {
        "绪论",
        "引言",
        "结论",
        "总结",
        "结语",
        "致谢",
        "致  谢",
        "参考文献",
        "附录",
        "摘要",
        "中文摘要",
        "英文摘要",
        "abstract",
        "目录",
        "前言",
        "综述",
        "序言",
        "序  言",    # 两个全角空格（辽大新版样本格式）
        "序   言",   # 两个普通空格（容错）
    }
)


def _normalize_compact_text(text):
    return re.sub(r"[\s\u3000]+", "", text or "")


def _false_heading_reason(text: str) -> str | None:
    compact = _normalize_compact_text(text)
    if not compact:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?[eE][+-]?\d+", compact):
        return "scientific_notation"
    if re.fullmatch(r"\d+\.\d+", compact):
        return "decimal_value"
    if re.fullmatch(r"\d+(?:,\d+)+(?:[-A-Za-z].*)?", compact):
        return "comma_compound"
    if re.fullmatch(r"\d+(?:-[A-Za-z][A-Za-z0-9-]*)+", compact):
        return "hyphen_compound"
    return None


def _looks_like_false_heading_text(text: str) -> bool:
    return _false_heading_reason(text) is not None


def _looks_like_heading_title_shape(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    compact = _normalize_compact_text(stripped)
    if len(compact) > 40:
        return False
    if re.search(r"[。；！？!?]", stripped):
        return False
    return True


_NORMALIZED_UNNUMBERED_H1_TITLES = frozenset(
    _normalize_compact_text(title).lower() for title in UNNUMBERED_H1_TITLES
)


def _normalize_section_title(title: str) -> str:
    return re.sub(r"[\s\u3000]+", "", title or "").lower()


_ABSTRACT_CN = ABSTRACT_CN_TITLES
_ABSTRACT_EN = ABSTRACT_EN_TITLES
_TOC_TITLES = TOC_TITLES
_DOCUMENT_SECTIONS = ("cover", "abstract_cn", "abstract_en", "toc", "body", "backmatter")
_HEADING_KINDS = frozenset({"h1", "h2", "h3", "h4"})


def _looks_like_toc_entry(text: str) -> bool:
    compact = (text or "").strip()
    if not compact:
        return False
    if re.search(r"\t\s*\d+\s*$", compact):
        return True
    if re.search(r"[\.·•…]{2,}\s*\d+\s*$", compact):
        return True
    if re.search(r"…+\s*\d+\s*$", compact):
        return True
    return False


def _is_toc_related_style(p_elem, style_map) -> bool:
    style_elem = p_elem.find("w:pPr/w:pStyle", NSMAP)
    style_id = style_elem.get(f"{{{W_NS}}}val") if style_elem is not None else None
    return (
        is_toc_heading_style(style_id, style_map)
        or is_toc_entry_style(style_id, style_map)
        or is_toc_generated_style_id(style_id)
    )


@dataclass(frozen=True)
class ParagraphNode:
    index: int
    elem: ET.Element
    text: str
    compact_text: str
    kind: str
    container_section: str
    backmatter_bucket: str | None
    module: str
    protected: bool
    in_table: bool

    @property
    def section(self) -> str:
        return self.backmatter_bucket or self.container_section


@dataclass(frozen=True)
class DocumentModel:
    paragraphs: tuple[ParagraphNode, ...]
    sections: dict[str, list[ET.Element]]
    paragraph_sections: dict[int, str]
    protected_ids: set[int]
    table_para_ids: set[int]
    modules: dict[str, list[ParagraphNode]]
    effective_sections: dict[str, list[ParagraphNode]]

    def section_nodes(self, section_name: str, *, effective: bool = True) -> list[ParagraphNode]:
        if effective:
            return list(self.effective_sections.get(section_name, []))
        return [node for node in self.paragraphs if node.container_section == section_name]

    def editable_text_ids(self) -> set[int]:
        return {
            id(node.elem)
            for node in self.paragraphs
            if node.section in {"abstract_cn", "abstract_en", "body"} and node.kind != "reference"
        }


def _is_keywords_paragraph(text: str, section_name: str) -> bool:
    return is_keywords_text(text, section_name)


def _is_caption_note_text(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if re.match(r"^注(?:[\s\u3000]*[:：]|[\s\u3000]*\d+[)）])", stripped):
        return True
    if re.match(r"^[（(]?[A-Z][）)]\s*\S", stripped):
        return True
    if re.match(r"^(不同|相同)小写字母表示", stripped):
        return True
    if (
        len(stripped) <= 160
        and re.search(r"[Pp]\s*[<≤≥>]\s*0\.0?5", stripped)
        and re.search(r"(小写字母|显著|差异)", stripped)
    ):
        return True
    return False


def _is_english_caption_text(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(re.match(r"^(?:Fig\.?|Figure|Table)\s*\d+(?:[.\-]\d+)*(?:\s*[A-Z])?\b", stripped, re.IGNORECASE))


def _is_section_title(text: str, titles: frozenset[str]) -> bool:
    return _normalize_section_title(text) in titles


def _classify_paragraph_module(
    p_elem,
    text: str,
    kind: str,
    container_section: str,
    backmatter_bucket: str | None,
    in_table: bool,
) -> str:
    section_name = backmatter_bucket or container_section
    if in_table:
        return "table_paragraph"

    if container_section == "cover":
        if p_elem.find(".//w:drawing", NSMAP) is not None:
            return "cover_graphic"
        if not text.strip():
            return "cover_blank"
        return "cover_text"

    if section_name in {"abstract_cn", "abstract_en"}:
        if _is_keywords_paragraph(text, section_name):
            return f"{section_name}_keywords"
        if kind == "h1" or (
            is_abstract_cn_title(text) if section_name == "abstract_cn" else is_abstract_en_title(text)
        ):
            return f"{section_name}_title"
        return f"{section_name}_body"

    if container_section == "toc":
        if is_toc_title(text):
            return "toc_title"
        p_style = p_elem.find("w:pPr/w:pStyle", NSMAP)
        style_id = p_style.get(f"{{{W_NS}}}val") if p_style is not None else None
        if _looks_like_toc_entry(text) or str(style_id or "").strip() in {"TOC1", "TOC2", "TOC3"}:
            return "toc_entry"
        return "toc_body"

    if section_name == "body":
        if kind in _HEADING_KINDS:
            return "body_heading"
        if kind == "caption":
            return "body_caption"
        if kind == "reference":
            return "body_reference"
        if paragraph_has_math(p_elem):
            return "body_equation"
        if kind == "body":
            return "body_paragraph"
        return "body_other"

    if section_name == "references":
        if kind in _HEADING_KINDS:
            return "references_title"
        return "references_entry"

    if section_name == "acknowledgement":
        if kind in _HEADING_KINDS:
            return "acknowledgement_title"
        return "acknowledgement_paragraph"

    if section_name == "appendix":
        if kind == "h1":
            return "appendix_title"
        if kind in {"h2", "h3", "h4"}:
            return "appendix_heading"
        if kind == "caption":
            return "appendix_caption"
        if paragraph_has_math(p_elem):
            return "appendix_equation"
        if kind == "body":
            return "appendix_paragraph"
        return "appendix_other"

    if kind in _HEADING_KINDS:
        return "backmatter_heading"
    if kind == "reference":
        return "backmatter_reference"
    return "backmatter_body"


def match_heading_by_text(text: str) -> int | None:
    """
    纯文本匹配标题等级。
    返回 1-4，或 None 表示非标题。
    优先匹配精确度高的（4→3→2→1）。
    """
    if not text:
        return None
    if _looks_like_false_heading_text(text):
        return None
    stripped = (text or "").strip()
    compact = _normalize_compact_text(text)
    if compact.lower() in _NORMALIZED_UNNUMBERED_H1_TITLES:
        return 1
    for level in (4, 3, 2):
        if HEADING_PATTERNS[level].match(compact):
            return level
    if HEADING_PATTERNS[1].match(compact) or ARABIC_H1_PATTERN.match(stripped):
        return 1
    return None


def _read_on_off(elem):
    if elem is None:
        return None
    val = elem.get(f"{{{W_NS}}}val")
    if val is None:
        return True
    return val not in ("0", "false", "False", "off")


def get_paragraph_text(p_elem):
    parts = []
    if p_elem.tag == f"{{{W_NS}}}r":
        run_elements = [p_elem]
    else:
        run_elements = p_elem.findall(".//w:r", NSMAP)
    for run_elem in run_elements:
        for elem in run_elem:
            if elem.tag == f"{{{W_NS}}}t" and elem.text:
                parts.append(elem.text)
            elif elem.tag == f"{{{W_NS}}}tab":
                parts.append("\t")
    return "".join(parts)


def paragraph_has_math(p_elem):
    return (
        p_elem.find(f".//{{{M_NS}}}oMath") is not None
        or p_elem.find(f".//{{{M_NS}}}oMathPara") is not None
    )


def parse_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_parse_int = parse_int


def _has_text_content(p_elem):
    for t_elem in p_elem.findall(".//w:t", NSMAP):
        if t_elem.text is not None:
            return True
    return False


def _get_max_run_size(p_elem):
    max_sz = None
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        sz_elem = run_elem.find("w:rPr/w:sz", NSMAP)
        sz_val = _parse_int(sz_elem.get(f"{{{W_NS}}}val") if sz_elem is not None else None)
        if sz_val is None:
            continue
        if max_sz is None or sz_val > max_sz:
            max_sz = sz_val
    return max_sz


def _has_bold_run(p_elem):
    for run_elem in p_elem.findall(".//w:r", NSMAP):
        bold_elem = run_elem.find("w:rPr/w:b", NSMAP)
        if _read_on_off(bold_elem):
            return True
    return False


def _get_paragraph_alignment(p_pr, style_props):
    if p_pr is not None:
        jc_elem = p_pr.find("w:jc", NSMAP)
        if jc_elem is not None:
            jc_val = jc_elem.get(f"{{{W_NS}}}val")
            if jc_val is not None:
                return jc_val
    return style_props.get("jc")


def build_style_map(styles_root):
    raw_map = {}
    default_paragraph_style_id = None

    def _read_int_attr(elem, attr_name):
        if elem is None:
            return None
        raw = elem.get(f"{{{W_NS}}}{attr_name}")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _extract_style_props(p_pr, r_pr):
        props = {
            "jc": None,
            "spacing_before": None,
            "spacing_after": None,
            "spacing_line": None,
            "spacing_lineRule": None,
            "sz": None,
            "bold": None,
            "eastAsia": None,
            "ascii": None,
            "hAnsi": None,
        }
        if p_pr is not None:
            jc_elem = p_pr.find("w:jc", NSMAP)
            if jc_elem is not None:
                props["jc"] = jc_elem.get(f"{{{W_NS}}}val")
            spacing_elem = p_pr.find("w:spacing", NSMAP)
            if spacing_elem is not None:
                props["spacing_before"] = _read_int_attr(spacing_elem, "before")
                props["spacing_after"] = _read_int_attr(spacing_elem, "after")
                props["spacing_line"] = _read_int_attr(spacing_elem, "line")
                props["spacing_lineRule"] = spacing_elem.get(f"{{{W_NS}}}lineRule")
        if r_pr is not None:
            sz_elem = r_pr.find("w:sz", NSMAP)
            if sz_elem is not None:
                props["sz"] = _read_int_attr(sz_elem, "val")
            props["bold"] = _read_on_off(r_pr.find("w:b", NSMAP))
            fonts_elem = r_pr.find("w:rFonts", NSMAP)
            if fonts_elem is not None:
                props["eastAsia"] = fonts_elem.get(f"{{{W_NS}}}eastAsia")
                props["ascii"] = fonts_elem.get(f"{{{W_NS}}}ascii")
                props["hAnsi"] = fonts_elem.get(f"{{{W_NS}}}hAnsi")
        return props

    doc_defaults = {
        "name": None,
        "outlineLvl": None,
        "basedOn": None,
        **_extract_style_props(
            styles_root.find("w:docDefaults/w:pPrDefault/w:pPr", NSMAP),
            styles_root.find("w:docDefaults/w:rPrDefault/w:rPr", NSMAP),
        ),
    }

    for style_elem in styles_root.findall(".//w:style", NSMAP):
        style_id = style_elem.get(f"{{{W_NS}}}styleId")
        if not style_id:
            continue

        p_pr = style_elem.find("w:pPr", NSMAP)
        r_pr = style_elem.find("w:rPr", NSMAP)
        based_on = style_elem.find("w:basedOn", NSMAP)

        outline_lvl = None
        style_props = _extract_style_props(p_pr, r_pr)
        jc = style_props["jc"]
        sz = style_props["sz"]
        bold = style_props["bold"]

        # 按样式名称推断 outlineLvl（兼容 outlineLvl 缺失的文档）
        name_elem = style_elem.find("w:name", NSMAP)
        style_name = (name_elem.get(f"{{{W_NS}}}val") or "").strip().lower() if name_elem is not None else ""
        if style_name in _NAME_TO_LEVEL:
            outline_lvl = _NAME_TO_LEVEL[style_name]

        if p_pr is not None:
            outline_elem = p_pr.find("w:outlineLvl", NSMAP)
            if outline_elem is not None:
                outline_val = outline_elem.get(f"{{{W_NS}}}val")
                if outline_val is not None and outline_val.isdigit():
                    outline_lvl = int(outline_val)  # XML 值优先覆盖名称推断
        style_type = style_elem.get(f"{{{W_NS}}}type")
        if style_type == "paragraph" and style_elem.get(f"{{{W_NS}}}default") in {"1", "true", "True"}:
            default_paragraph_style_id = style_id

        raw_map[style_id] = {
            "name": style_name,
            "outlineLvl": outline_lvl,
            "sz": sz,
            "bold": bold,
            "jc": jc,
            "spacing_before": style_props["spacing_before"],
            "spacing_after": style_props["spacing_after"],
            "spacing_line": style_props["spacing_line"],
            "spacing_lineRule": style_props["spacing_lineRule"],
            "eastAsia": style_props["eastAsia"],
            "ascii": style_props["ascii"],
            "hAnsi": style_props["hAnsi"],
            "basedOn": based_on.get(f"{{{W_NS}}}val") if based_on is not None else None,
        }

    resolved_map = {}

    def resolve_style(style_id, visiting):
        if style_id in resolved_map:
            return resolved_map[style_id]
        if style_id not in raw_map:
            return {
                "outlineLvl": None,
                "sz": None,
                "bold": None,
                "jc": None,
                "name": None,
                "basedOn": None,
            }
        if style_id in visiting:
            current = dict(raw_map[style_id])
            resolved_map[style_id] = current
            return current

        current = dict(raw_map[style_id])
        base_id = current.get("basedOn")
        if base_id:
            base_style = resolve_style(base_id, visiting | {style_id})
            for key in (
                "outlineLvl",
                "sz",
                "bold",
                "jc",
                "name",
                "spacing_before",
                "spacing_after",
                "spacing_line",
                "spacing_lineRule",
                "eastAsia",
                "ascii",
                "hAnsi",
            ):
                if current.get(key) is None:
                    current[key] = base_style.get(key)

        resolved_map[style_id] = current
        return current

    for style_id in raw_map:
        resolve_style(style_id, set())

    default_paragraph = dict(doc_defaults)
    if default_paragraph_style_id is not None:
        for key, value in resolved_map.get(default_paragraph_style_id, {}).items():
            if value is not None:
                default_paragraph[key] = value
    resolved_map["__doc_defaults__"] = doc_defaults
    resolved_map["__default_paragraph__"] = default_paragraph

    return resolved_map


def classify_paragraph(p_elem, style_map):
    if not _has_text_content(p_elem):
        return "empty"

    paragraph_text = get_paragraph_text(p_elem)
    compact_text = _normalize_compact_text(paragraph_text)
    p_pr = p_elem.find("w:pPr", NSMAP)
    style_id = None

    if p_pr is not None:
        style_elem = p_pr.find("w:pStyle", NSMAP)
        if style_elem is not None:
            style_id = style_elem.get(f"{{{W_NS}}}val")

    style_props = style_map.get(style_id, {})
    outline_lvl = style_props.get("outlineLvl")
    false_heading_text = _looks_like_false_heading_text(paragraph_text)
    heading_level_text = None if false_heading_text else match_heading_by_text(paragraph_text)

    if outline_lvl == 0:
        if heading_level_text == 4:
            return "h4"
        if heading_level_text == 3:
            return "h3"
        if heading_level_text == 2:
            return "h2"
        if heading_level_text == 1:
            return "h1"
        # 数字编号章标题（如"1 材料与方法"）不匹配传统"第X章"模式，但 outlineLvl=0 时仍信任样式
        if (
            not false_heading_text
            and
            _looks_like_heading_title_shape(paragraph_text)
            and
            len(compact_text) >= 2
            and not re.match(r"^\[\d", compact_text)
            and not re.match(r"^(图|表)\d", compact_text)
        ):
            return "h1"
    if outline_lvl == 1:
        if heading_level_text == 2:
            return "h2"
    if outline_lvl == 2:
        if heading_level_text == 3:
            return "h3"
    if outline_lvl == 3:
        if heading_level_text == 4:
            return "h4"

    max_sz = _get_max_run_size(p_elem)
    has_bold = _has_bold_run(p_elem)
    style_bold = style_props.get("bold") is True
    has_heading_bold_signal = has_bold or style_bold
    ind_elem = p_pr.find("w:ind", NSMAP) if p_pr is not None else None
    first_line = ind_elem.get(f"{{{W_NS}}}firstLine") if ind_elem is not None else None
    zero_first_line = first_line in (None, "0")
    jc_val = _get_paragraph_alignment(p_pr, style_props)
    if max_sz is not None and max_sz >= 28 and has_heading_bold_signal:
        if jc_val == "center":
            return "h1"
        if jc_val == "left" or (jc_val is None and zero_first_line):
            return "h2"
    if (
        max_sz == 24
        and has_heading_bold_signal
        and heading_level_text == 3
    ):
        if jc_val == "left" or (jc_val is None and zero_first_line):
            return "h3"
    if (
        max_sz == 24
        and has_heading_bold_signal
        and heading_level_text == 4
    ):
        if jc_val == "left" or (jc_val is None and zero_first_line):
            return "h4"

    if has_heading_bold_signal:
        if heading_level_text == 1:
            return "h1"
        if heading_level_text == 4:
            return "h4"
        if heading_level_text == 3:
            return "h3"
        if heading_level_text == 2:
            return "h2"

    # 黑体无粗体标题：字号足够大且文字模式匹配时，按文字判定（fix后章标题去粗但仍是黑体大字号）
    if max_sz is not None and max_sz >= 28:
        if heading_level_text == 1:
            return "h1"
        if jc_val == "left" or (jc_val is None and zero_first_line):
            if heading_level_text == 2:
                return "h2"
    if max_sz is not None and max_sz >= 24:
        if heading_level_text == 4:
            return "h4"
        if heading_level_text == 3:
            return "h3"
        if heading_level_text == 2:
            return "h2"

    heading_level = heading_level_text
    if heading_level is not None:
        return f"h{heading_level}"

    if p_pr is not None:
        if ind_elem is not None:
            hanging = _parse_int(ind_elem.get(f"{{{W_NS}}}hanging"))
            if hanging is not None and hanging >= 300:
                return "reference"

    if re.match(r"^\[\d{1,3}\]", compact_text):
        return "reference"
    if re.match(r"^(图|表)\d", compact_text):
        return "caption"
    if paragraph_text.strip():
        return "body"
    return "other"

def _assign_document_sections(document_root, style_map):
    paragraphs = list(document_root.findall(".//w:p", NSMAP))
    sections = {name: [] for name in _DOCUMENT_SECTIONS}
    if not paragraphs:
        return sections

    ordered_sections = list(_DOCUMENT_SECTIONS)
    section_order = {name: idx for idx, name in enumerate(ordered_sections)}
    current_section = "cover"
    triggered_any = False

    def _is_backmatter_title(compact_text, para_kind):
        return detect_backmatter_bucket(compact_text, para_kind) is not None

    def detect_next_section(p_elem, paragraph_text, compact_text, lower_text, paragraph_kind, active_section):
        active_index = section_order[active_section]
        if active_index < section_order["abstract_cn"] and is_abstract_cn_title(paragraph_text):
            return "abstract_cn"
        if active_index < section_order["abstract_en"] and is_abstract_en_title(paragraph_text):
            return "abstract_en"
        if active_section in {"abstract_cn", "abstract_en"} and _is_keywords_paragraph(paragraph_text, active_section):
            return None
        if active_index < section_order["toc"] and is_toc_title(paragraph_text):
            return "toc"
        if active_section == "toc":
            if is_toc_title(paragraph_text) or _is_toc_related_style(p_elem, style_map):
                return None
            if _looks_like_toc_entry(paragraph_text):
                return None
            if paragraph_text.strip() and not is_toc_title(paragraph_text):
                return "body"
        if active_index < section_order["body"] and paragraph_kind == "h1":
            return "body"
        # 只在已进入 body 节后才允许转入 backmatter，
        # 防止正文前的占位符（如"参考文献（待填写）"）提前触发
        if active_section == "body" and _is_backmatter_title(compact_text, paragraph_kind):
            return "backmatter"
        return None

    for p_elem in paragraphs:
        paragraph_text = get_paragraph_text(p_elem)
        compact_text = _normalize_compact_text(paragraph_text)
        lower_text = compact_text.lower()
        paragraph_kind = classify_paragraph(p_elem, style_map)
        next_section = detect_next_section(p_elem, paragraph_text, compact_text, lower_text, paragraph_kind, current_section)
        if next_section is not None:
            current_section = next_section
            triggered_any = True
        sections[current_section].append(p_elem)

    if triggered_any:
        return sections

    fallback_sections = {name: [] for name in sections}
    in_cover = True
    for p_elem in paragraphs:
        paragraph_kind = classify_paragraph(p_elem, style_map)
        if in_cover and paragraph_kind == "h1":
            in_cover = False
        if in_cover:
            fallback_sections["cover"].append(p_elem)
        else:
            fallback_sections["body"].append(p_elem)
    return fallback_sections


def build_document_model(document_root, style_map):
    sections = _assign_document_sections(document_root, style_map)
    paragraph_sections = build_paragraph_section_map(sections)
    protected_ids = build_protected_paragraph_ids(document_root, sections)
    table_para_ids = {
        id(p_elem)
        for tbl in document_root.findall(".//w:tbl", NSMAP)
        for p_elem in tbl.findall(".//w:p", NSMAP)
    }

    paragraphs = []
    modules: dict[str, list[ParagraphNode]] = {}
    effective_sections: dict[str, list[ParagraphNode]] = {}
    current_backmatter_bucket = None

    for index, p_elem in enumerate(document_root.findall(".//w:p", NSMAP), start=1):
        text = get_paragraph_text(p_elem)
        kind = classify_paragraph(p_elem, style_map)
        container_section = paragraph_sections.get(id(p_elem), "body")
        backmatter_bucket = None
        if container_section == "backmatter":
            if kind == "h1":
                current_backmatter_bucket = detect_backmatter_bucket(text, kind)
            backmatter_bucket = current_backmatter_bucket
        else:
            current_backmatter_bucket = None

        node = ParagraphNode(
            index=index,
            elem=p_elem,
            text=text,
            compact_text=_normalize_compact_text(text),
            kind=kind,
            container_section=container_section,
            backmatter_bucket=backmatter_bucket,
            module=_classify_paragraph_module(
                p_elem,
                text,
                kind,
                container_section,
                backmatter_bucket,
                id(p_elem) in table_para_ids,
            ),
            protected=id(p_elem) in protected_ids,
            in_table=id(p_elem) in table_para_ids,
        )
        paragraphs.append(node)
        modules.setdefault(node.module, []).append(node)
        effective_sections.setdefault(node.section, []).append(node)

    normalized_paragraphs = _relabel_caption_note_nodes(paragraphs)

    modules = {}
    effective_sections = {}
    for node in normalized_paragraphs:
        modules.setdefault(node.module, []).append(node)
        effective_sections.setdefault(node.section, []).append(node)

    return DocumentModel(
        paragraphs=tuple(normalized_paragraphs),
        sections=sections,
        paragraph_sections=paragraph_sections,
        protected_ids=protected_ids,
        table_para_ids=table_para_ids,
        modules=modules,
        effective_sections=effective_sections,
    )


def _relabel_caption_note_nodes(paragraphs: list[ParagraphNode]) -> list[ParagraphNode]:
    if not paragraphs:
        return paragraphs

    relabeled = list(paragraphs)
    index = 0
    while index < len(relabeled):
        node = relabeled[index]
        if node.module not in {"body_caption", "appendix_caption"}:
            index += 1
            continue

        note_module = "body_caption_note" if node.module == "body_caption" else "appendix_caption_note"
        english_caption_module = "body_caption_en" if node.module == "body_caption" else "appendix_caption_en"
        section_name = node.section
        is_table_caption = (node.text or "").strip().startswith("表")
        lookahead = index + 1
        while lookahead < len(relabeled):
            candidate = relabeled[lookahead]
            if candidate.section != section_name:
                break
            if is_table_caption and candidate.module == "table_paragraph":
                lookahead += 1
                continue
            if candidate.kind in _HEADING_KINDS or candidate.kind in {"caption", "reference"}:
                break
            if candidate.module not in {"body_paragraph", "body_other", "appendix_paragraph", "appendix_other"}:
                break
            if _is_english_caption_text(candidate.text):
                relabeled[lookahead] = replace(candidate, module=english_caption_module)
                lookahead += 1
                continue
            if not _is_caption_note_text(candidate.text):
                break
            relabeled[lookahead] = replace(candidate, module=note_module)
            lookahead += 1
        index = lookahead

    return relabeled


def build_document_sections(document_root, style_map):
    return _assign_document_sections(document_root, style_map)


def build_paragraph_section_map(sections):
    paragraph_sections = {}
    for section_name, section_paragraphs in (sections or {}).items():
        for p_elem in section_paragraphs:
            paragraph_sections[id(p_elem)] = section_name
    return paragraph_sections


def build_protected_paragraph_ids(document_root, sections=None):
    protected = set()
    body_paragraphs = list(document_root.findall(".//w:p", NSMAP))
    for index, p_elem in enumerate(body_paragraphs):
        if not paragraph_has_math(p_elem):
            continue
        protected.add(id(p_elem))
        if index + 1 < len(body_paragraphs):
            next_text = get_paragraph_text(body_paragraphs[index + 1]).strip()
            if next_text.startswith("其中") or next_text.startswith("式中"):
                protected.add(id(body_paragraphs[index + 1]))
        if index > 0:
            prev_text = get_paragraph_text(body_paragraphs[index - 1]).strip()
            if prev_text.startswith("其中") or prev_text.startswith("式中"):
                protected.add(id(body_paragraphs[index - 1]))

    for p_elem in (sections or {}).get("backmatter", []):
        protected.add(id(p_elem))
    return protected


def build_figure_groups(contexts):
    """将图片段落、图题、图注组合为结构化组列表。

    Returns:
        list of dict:
          {"image": ctx, "caption": ctx | None, "notes": [ctx, ...]}
    """

    def is_figure_note(ctx):
        """判断是否为图注段落（非标题、非正文章节、非下一图）"""
        kind = ctx.get("kind", "")
        text = ctx.get("text", "").strip()
        if kind in ("h1", "h2", "h3", "h4", "caption"):
            return False
        if kind in ("figure", "drawing"):
            return False
        # 图注通常短且不以数字章节编号开头
        if text and text[0].isdigit() and len(text) > 20:
            return False
        return kind == "body" and len(text) < 120

    groups = []
    i = 0
    while i < len(contexts):
        ctx = contexts[i]
        if ctx.get("kind") in ("figure", "drawing"):
            group = {"image": ctx, "caption": None, "notes": []}
            j = i + 1
            # 下一个非空段落是图题
            if j < len(contexts) and contexts[j].get("kind") == "caption":
                group["caption"] = contexts[j]
                j += 1
                # 继续收集图注
                while j < len(contexts) and is_figure_note(contexts[j]):
                    group["notes"].append(contexts[j])
                    j += 1
            i = j
            groups.append(group)
        else:
            i += 1
    return groups


def paragraph_has_drawing(p_elem: ET.Element) -> bool:
    return p_elem.find(".//w:drawing", NSMAP) is not None


def collect_figure_blocks(document_root: ET.Element, style_map: dict | None = None) -> list[dict]:
    """按 body 直属段落收集图块：图片段落 -> 图题 -> 图注列表。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return []

    document_model = build_document_model(document_root, style_map or {})
    node_by_id = {id(node.elem): node for node in document_model.paragraphs}
    body_paragraphs = [child for child in list(body) if child.tag == f"{{{W_NS}}}p"]

    def is_blank_paragraph(p_elem: ET.Element) -> bool:
        return not paragraph_has_drawing(p_elem) and not get_paragraph_text(p_elem).strip()

    blocks: list[dict] = []
    i = 0
    while i < len(body_paragraphs):
        image_elem = body_paragraphs[i]
        if not paragraph_has_drawing(image_elem):
            i += 1
            continue

        j = i + 1
        while j < len(body_paragraphs) and is_blank_paragraph(body_paragraphs[j]):
            j += 1
        if j >= len(body_paragraphs):
            i += 1
            continue

        caption_node = node_by_id.get(id(body_paragraphs[j]))
        if caption_node is None or caption_node.module not in {"body_caption", "appendix_caption"}:
            i += 1
            continue

        english_captions: list[ParagraphNode] = []
        k = j + 1
        while k < len(body_paragraphs):
            english_node = node_by_id.get(id(body_paragraphs[k]))
            if english_node is None or english_node.module not in {"body_caption_en", "appendix_caption_en"}:
                break
            english_captions.append(english_node)
            k += 1

        notes: list[ParagraphNode] = []
        while k < len(body_paragraphs):
            note_node = node_by_id.get(id(body_paragraphs[k]))
            if note_node is None or note_node.module not in {"body_caption_note", "appendix_caption_note"}:
                break
            notes.append(note_node)
            k += 1

        last_elem = notes[-1].elem if notes else (english_captions[-1].elem if english_captions else caption_node.elem)
        blocks.append(
            {
                "body_paragraphs": body_paragraphs,
                "image": image_elem,
                "image_index": i,
                "caption": caption_node,
                "caption_index": j,
                "english_captions": english_captions,
                "notes": notes,
                "end_index": k - 1,
                "last_elem": last_elem,
                "section": caption_node.section,
            }
        )
        i = max(k, i + 1)
    return blocks


def collect_table_blocks(document_root: ET.Element, style_map: dict | None = None) -> list[dict]:
    """按 body 直属节点收集表块：表题 -> 表格 -> 表注列表。"""
    body = document_root.find("w:body", NSMAP)
    if body is None:
        return []

    document_model = build_document_model(document_root, style_map or {})
    node_by_id = {id(node.elem): node for node in document_model.paragraphs}
    body_children = list(body)
    body_paragraph_tag = f"{{{W_NS}}}p"
    body_table_tag = f"{{{W_NS}}}tbl"

    def is_blank_paragraph(elem: ET.Element) -> bool:
        return elem.tag == body_paragraph_tag and not paragraph_has_drawing(elem) and not get_paragraph_text(elem).strip()

    blocks: list[dict] = []
    i = 0
    while i < len(body_children):
        caption_elem = body_children[i]
        if caption_elem.tag != body_paragraph_tag:
            i += 1
            continue

        caption_node = node_by_id.get(id(caption_elem))
        caption_text = get_paragraph_text(caption_elem).strip()
        if (
            caption_node is None
            or caption_node.module not in {"body_caption", "appendix_caption"}
            or not caption_text.startswith("表")
        ):
            i += 1
            continue

        j = i + 1
        blank_between = 0
        while j < len(body_children) and is_blank_paragraph(body_children[j]):
            blank_between += 1
            j += 1
        english_captions: list[ParagraphNode] = []
        while j < len(body_children) and body_children[j].tag == body_paragraph_tag:
            english_node = node_by_id.get(id(body_children[j]))
            if english_node is None or english_node.module not in {"body_caption_en", "appendix_caption_en"}:
                break
            english_captions.append(english_node)
            j += 1
        if j >= len(body_children) or body_children[j].tag != body_table_tag:
            i += 1
            continue

        table_elem = body_children[j]
        notes: list[ParagraphNode] = []
        k = j + 1
        while k < len(body_children):
            candidate = body_children[k]
            if candidate.tag != body_paragraph_tag:
                break
            note_node = node_by_id.get(id(candidate))
            if note_node is None or note_node.module not in {"body_caption_note", "appendix_caption_note"}:
                break
            notes.append(note_node)
            k += 1

        blocks.append(
            {
                "body_children": body_children,
                "caption": caption_node,
                "caption_index": i,
                "english_captions": english_captions,
                "table": table_elem,
                "table_index": j,
                "notes": notes,
                "blank_between": blank_between,
                "end_index": k - 1 if notes else j,
                "last_elem": notes[-1].elem if notes else table_elem,
                "section": caption_node.section,
            }
        )
        i = max(k, i + 1)
    return blocks


class HeadingCandidateFilter:
    """统一判断段落是否应被视为标题候选，供 workflow.py 和 fix_thesis.py 共用。"""

    @staticmethod
    def is_false_heading_text(text: str) -> bool:
        """文本本身不像标题（数值串、科学计数法、逗号复合数等）。"""
        return _looks_like_false_heading_text(text)

    @staticmethod
    def candidate_reason(text: str) -> str | None:
        """返回伪标题风险原因标签，无风险返回 None。"""
        return _false_heading_reason(text)

    @staticmethod
    def is_table_heading_risk(node, style_level: int | None, text_level: int | None) -> bool:
        """综合判断：节点是否为表格内伪标题风险（供 diagnostics 使用）。"""
        candidate_reason = HeadingCandidateFilter.candidate_reason(node.text)
        return bool(
            node.in_table and node.text.strip() and (
                node.kind in _HEADING_KINDS
                or text_level is not None
                or (style_level is not None and candidate_reason is not None)
                or candidate_reason is not None
            )
        )

    @staticmethod
    def should_skip_for_renumber(node) -> bool:
        """重编号时是否应跳过此节点（表格内，或文本本身是伪标题）。"""
        if node.in_table:
            return True
        return HeadingCandidateFilter.is_false_heading_text(node.text or "")
