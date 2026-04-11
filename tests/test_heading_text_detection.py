from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _thesis_utils import HeadingCandidateFilter, match_heading_by_text
from _thesis_utils import classify_paragraph, W_NS
import xml.etree.ElementTree as ET


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def test_match_heading_by_text_accepts_arabic_number_h1():
    assert match_heading_by_text("4 讨论") == 1
    assert match_heading_by_text("5 结论") == 1


def test_match_heading_by_text_rejects_scientific_notation_and_decimal_values():
    assert match_heading_by_text("2.80E+08") is None
    assert match_heading_by_text("231.112323") is None
    assert match_heading_by_text("1,4-Diaminobutane") is None
    assert match_heading_by_text("2-Amino-2-Deoxy-D-Glucopyranose") is None


def test_heading_candidate_filter_reason_stays_consistent_with_false_heading_detection():
    cases = {
        "2.80E+08": "scientific_notation",
        "231.112323": "decimal_value",
        "1,4-Diaminobutane": "comma_compound",
        "2-Amino-2-Deoxy-D-Glucopyranose": "hyphen_compound",
    }

    for text, reason in cases.items():
        assert HeadingCandidateFilter.is_false_heading_text(text)
        assert HeadingCandidateFilter.candidate_reason(text) == reason


def test_classify_paragraph_prefers_numeric_depth_over_h1_style():
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "Heading1")
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = "3.6 分子对接验证结果"

    style_map = {
        "Heading1": {"outlineLvl": 0, "sz": 30, "bold": False, "jc": "center", "name": "heading 1", "basedOn": None},
    }

    assert classify_paragraph(p, style_map) == "h2"


def test_classify_paragraph_rejects_false_heading_text_even_with_h1_style():
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "Heading1")
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = "2.80E+08"

    style_map = {
        "Heading1": {"outlineLvl": 0, "sz": 30, "bold": False, "jc": "center", "name": "heading 1", "basedOn": None},
    }

    assert classify_paragraph(p, style_map) != "h1"


def test_classify_paragraph_rejects_long_body_sentence_even_with_h1_style():
    p = ET.Element(_w("p"))
    p_pr = ET.SubElement(p, _w("pPr"))
    p_style = ET.SubElement(p_pr, _w("pStyle"))
    p_style.set(_w("val"), "Heading1")
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = "这是一个被误套用标题样式的正文句子，包含完整语义和句号。"

    style_map = {
        "Heading1": {"outlineLvl": 0, "sz": 30, "bold": False, "jc": "center", "name": "heading 1", "basedOn": None},
    }

    assert classify_paragraph(p, style_map) == "body"
