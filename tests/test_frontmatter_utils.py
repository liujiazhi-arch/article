from __future__ import annotations

import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS
from frontmatter_utils import (
    contains_toc_field_text,
    find_contiguous_toc_block_range,
    is_cn_keywords_paragraph_text,
    is_en_keywords_paragraph_text,
    is_keyword_paragraph_text,
    is_keywords_text,
    is_toc_entry_style,
    is_toc_generated_style_id,
    is_toc_heading_style,
    is_toc_structural_style_id,
    normalize_style_semantic_name,
    paragraph_has_toc_field_instr,
)


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _make_paragraph(text: str = "") -> ET.Element:
    paragraph = ET.Element(_w("p"))
    run = ET.SubElement(paragraph, _w("r"))
    text_elem = ET.SubElement(run, _w("t"))
    text_elem.text = text
    return paragraph


def test_keywords_helpers_detect_cn_and_en_variants():
    assert is_cn_keywords_paragraph_text("关键词：测试；修复")
    assert is_en_keywords_paragraph_text("Keywords: alpha; beta")
    assert is_keyword_paragraph_text("Key words: alpha; beta")
    assert is_keywords_text("关键词：测试；修复", "abstract_cn")
    assert is_keywords_text("Keywords: alpha; beta", "abstract_en")
    assert not is_keywords_text("正文段落", "abstract_en")


def test_toc_field_helpers_detect_instruction_text_and_styles():
    paragraph = ET.Element(_w("p"))
    run = ET.SubElement(paragraph, _w("r"))
    instr = ET.SubElement(run, _w("instrText"))
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '

    assert contains_toc_field_text(instr.text)
    assert paragraph_has_toc_field_instr(paragraph, nsmap=NSMAP)
    assert is_toc_generated_style_id("TOCHeading")
    assert is_toc_generated_style_id("TOCField")
    assert is_toc_structural_style_id("TOCField")
    assert not is_toc_structural_style_id("TOC1")


def test_toc_style_helpers_normalize_style_map_names():
    style_map = {
        "x1": {"name": "TOC Heading"},
        "x2": {"name": "目录1"},
    }

    assert normalize_style_semantic_name("x1", style_map) == "tocheading"
    assert is_toc_heading_style("x1", style_map)
    assert is_toc_entry_style("x2", style_map)


def test_find_contiguous_toc_block_range_handles_leading_non_candidates_and_trailing_blank():
    bookmark = ET.Element(_w("bookmarkStart"))
    title = _make_paragraph("目  录")
    entry = _make_paragraph("摘  要\t2")
    blank = _make_paragraph("")
    body = _make_paragraph("1 序言")

    start_idx, end_idx = find_contiguous_toc_block_range(
        [bookmark, title, entry, blank, body],
        is_candidate=lambda node: node.tag == _w("p"),
        get_text=lambda node: "".join(t.text or "" for t in node.findall(".//w:t", NSMAP)),
        is_tocish=lambda _node, text: text in {"目  录", "摘  要\t2"},
    )

    assert start_idx == 1
    assert end_idx == 3
