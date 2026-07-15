from __future__ import annotations

import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS
from sections._xml_helpers import (
    get_run_text,
    get_paragraph_spacing_twips,
    is_superscript,
    is_onoff_enabled,
    paragraph_onoff_enabled,
    set_paragraph_pagination_flags,
    set_paragraph_spacing_attrs,
    set_table_row_cant_split,
    table_row_cant_split_enabled,
)


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def test_get_run_text_concatenates_nested_text_nodes():
    run = ET.Element(_w("r"))
    first = ET.SubElement(run, _w("t"))
    first.text = "第"
    wrapper = ET.SubElement(run, _w("smartTag"))
    second = ET.SubElement(wrapper, _w("t"))
    second.text = "1"
    empty = ET.SubElement(run, _w("t"))
    empty.text = None
    third = ET.SubElement(run, _w("t"))
    third.text = "章"

    assert get_run_text(run) == "第1章"


def test_is_superscript_reads_run_vertical_alignment():
    run = ET.Element(_w("r"))
    r_pr = ET.SubElement(run, _w("rPr"))
    vert_align = ET.SubElement(r_pr, _w("vertAlign"))
    vert_align.set(_w("val"), "superscript")
    subscript_run = ET.Element(_w("r"))
    subscript_r_pr = ET.SubElement(subscript_run, _w("rPr"))
    subscript_vert_align = ET.SubElement(subscript_r_pr, _w("vertAlign"))
    subscript_vert_align.set(_w("val"), "subscript")
    normal_run = ET.Element(_w("r"))

    assert is_superscript(run) is True
    assert is_superscript(subscript_run) is False
    assert is_superscript(normal_run) is False


def test_paragraph_spacing_helpers_create_and_read_twip_attributes():
    paragraph = ET.Element(_w("p"))

    assert get_paragraph_spacing_twips(paragraph, "before") == 0

    set_paragraph_spacing_attrs(paragraph, before=120, after=240, line=360)

    spacing = paragraph.find("w:pPr/w:spacing", NSMAP)
    assert spacing is not None
    assert spacing.get(_w("before")) == "120"
    assert spacing.get(_w("after")) == "240"
    assert spacing.get(_w("line")) == "360"
    assert spacing.get(_w("lineRule")) == "auto"
    assert get_paragraph_spacing_twips(paragraph, "before") == 120
    assert get_paragraph_spacing_twips(paragraph, "after") == 240


def test_pagination_and_table_row_flags_report_idempotent_changes():
    paragraph = ET.Element(_w("p"))
    p_pr = ET.SubElement(paragraph, _w("pPr"))
    ET.SubElement(p_pr, _w("pStyle"))
    ET.SubElement(p_pr, _w("spacing"))
    ET.SubElement(p_pr, _w("rPr"))
    row = ET.Element(_w("tr"))

    assert set_paragraph_pagination_flags(paragraph, keep_next=True, keep_lines=True, page_break_before=False) == 3
    assert set_paragraph_pagination_flags(paragraph, keep_next=True, keep_lines=True, page_break_before=False) == 0
    assert paragraph.find("w:pPr/w:keepNext", NSMAP).get(_w("val")) == "1"
    assert paragraph.find("w:pPr/w:keepLines", NSMAP).get(_w("val")) == "1"
    assert paragraph.find("w:pPr/w:pageBreakBefore", NSMAP).get(_w("val")) == "0"
    assert [child.tag for child in p_pr] == [
        _w("pStyle"),
        _w("keepNext"),
        _w("keepLines"),
        _w("pageBreakBefore"),
        _w("spacing"),
        _w("rPr"),
    ]

    assert set_table_row_cant_split(row) == 1
    assert set_table_row_cant_split(row) == 0
    assert row.find("w:trPr/w:cantSplit", NSMAP).get(_w("val")) == "1"


def test_pagination_flags_reorder_existing_properties_once():
    paragraph = ET.Element(_w("p"))
    p_pr = ET.SubElement(paragraph, _w("pPr"))
    ET.SubElement(p_pr, _w("pStyle"))
    ET.SubElement(p_pr, _w("spacing"))
    for tag_name, value in (("keepNext", "1"), ("keepLines", "1"), ("pageBreakBefore", "0")):
        element = ET.SubElement(p_pr, _w(tag_name))
        element.set(_w("val"), value)

    assert set_paragraph_pagination_flags(paragraph, keep_next=True, keep_lines=True) == 3
    assert set_paragraph_pagination_flags(paragraph, keep_next=True, keep_lines=True) == 0
    assert [child.tag for child in p_pr] == [
        _w("pStyle"),
        _w("keepNext"),
        _w("keepLines"),
        _w("pageBreakBefore"),
        _w("spacing"),
    ]


def test_onoff_read_helpers_match_word_boolean_semantics():
    paragraph = ET.Element(_w("p"))
    row = ET.Element(_w("tr"))

    assert is_onoff_enabled(None) is False
    assert paragraph_onoff_enabled(paragraph, "keepNext") is False
    assert table_row_cant_split_enabled(row) is False

    p_pr = ET.SubElement(paragraph, _w("pPr"))
    keep_next = ET.SubElement(p_pr, _w("keepNext"))
    tr_pr = ET.SubElement(row, _w("trPr"))
    cant_split = ET.SubElement(tr_pr, _w("cantSplit"))

    assert is_onoff_enabled(keep_next) is True
    assert paragraph_onoff_enabled(paragraph, "keepNext") is True
    assert table_row_cant_split_enabled(row) is True

    for false_value in ("0", "false", "False", "off", "none"):
        keep_next.set(_w("val"), false_value)
        cant_split.set(_w("val"), false_value)
        assert paragraph_onoff_enabled(paragraph, "keepNext") is False
        assert table_row_cant_split_enabled(row) is False

    keep_next.set(_w("val"), "1")
    cant_split.set(_w("val"), "1")

    assert paragraph_onoff_enabled(paragraph, "keepNext") is True
    assert table_row_cant_split_enabled(row) is True
