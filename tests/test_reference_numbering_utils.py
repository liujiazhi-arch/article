from __future__ import annotations

import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS
from reference_numbering_utils import (
    has_valid_reference_tab_stop,
    paragraph_has_reference_tab,
    parse_reference_number_prefix,
    reference_number_has_compact_separator,
    reference_number_has_space_separator,
    reference_number_has_tab_separator,
)


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _paragraph(text: str = "") -> ET.Element:
    paragraph = ET.Element(_w("p"))
    run = ET.SubElement(paragraph, _w("r"))
    text_elem = ET.SubElement(run, _w("t"))
    text_elem.text = text
    return paragraph


def test_parse_reference_number_prefix_reports_leading_zero_and_remainder():
    prefix = parse_reference_number_prefix("  [01]\tGuo G C.")

    assert prefix is not None
    assert prefix.leading == "  "
    assert prefix.number_text == "01"
    assert prefix.number == 1
    assert prefix.separator == "\t"
    assert prefix.remainder == "Guo G C."
    assert prefix.has_leading_zero is True


def test_reference_number_separator_predicates_match_lnu_ref02_contract():
    assert reference_number_has_tab_separator("[1]\tGuo") is True
    assert reference_number_has_space_separator("[1] Guo") is True
    assert reference_number_has_compact_separator("[1]Guo") is True

    assert reference_number_has_tab_separator("[01]\tGuo") is False
    assert reference_number_has_space_separator("[01] Guo") is False
    assert reference_number_has_compact_separator("[01]Guo") is False
    assert reference_number_has_tab_separator("[1]\t Guo") is False
    assert reference_number_has_space_separator("[1]  Guo") is False
    assert reference_number_has_space_separator(" [1] Guo") is False


def test_reference_tab_helpers_detect_inline_text_tabs_and_valid_tab_stops():
    inline_tab = _paragraph("[1]\tGuo")
    xml_tab = ET.Element(_w("p"))
    run = ET.SubElement(xml_tab, _w("r"))
    ET.SubElement(run, _w("tab"))
    low_stop = _paragraph("[1] Guo")
    p_pr = ET.SubElement(low_stop, _w("pPr"))
    tabs = ET.SubElement(p_pr, _w("tabs"))
    tab = ET.SubElement(tabs, _w("tab"))
    tab.set(_w("val"), "left")
    tab.set(_w("pos"), "419")

    assert paragraph_has_reference_tab(inline_tab) is True
    assert paragraph_has_reference_tab(xml_tab) is True
    assert has_valid_reference_tab_stop(low_stop, 420) is False

    tab.set(_w("pos"), "420")

    assert has_valid_reference_tab_stop(low_stop, 420) is True
    assert low_stop.find("w:pPr/w:tabs", NSMAP) is tabs
