from __future__ import annotations

import xml.etree.ElementTree as ET

from _thesis_utils import NSMAP, W_NS, get_paragraph_text
from reference_section_utils import (
    is_reference_section_stop_text,
    iter_reference_section_contexts,
    iter_reference_section_paragraphs,
)


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _make_paragraph(text: str):
    p = ET.Element(_w("p"))
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = text
    return p


def _doc_with_paragraphs(*paragraphs):
    root = ET.Element(_w("document"))
    body = ET.SubElement(root, _w("body"))
    for paragraph in paragraphs:
        body.append(paragraph)
    return root


def test_iter_reference_section_contexts_skips_empty_and_stops_at_next_h1():
    contexts = [
        {"text": "第一章 绪论", "kind": "h1"},
        {"text": "正文段落", "kind": "body"},
        {"text": "参考文献", "kind": "h1"},
        {"text": "[1] Example reference.", "kind": "reference"},
        {"text": "", "kind": "empty"},
        {"text": "致谢", "kind": "h1"},
        {"text": "感谢老师指导。", "kind": "body"},
    ]

    section_contexts = list(iter_reference_section_contexts(contexts, skip_empty=True))

    assert [ctx["text"] for ctx in section_contexts] == ["[1] Example reference."]


def test_iter_reference_section_paragraphs_stops_before_acknowledgement():
    reference_title = _make_paragraph("参考文献")
    reference_body = _make_paragraph("[1] Example reference.")
    empty = _make_paragraph("")
    acknowledgement_title = _make_paragraph("致谢")
    acknowledgement_body = _make_paragraph("感谢老师指导。")
    document_root = _doc_with_paragraphs(
        reference_title,
        reference_body,
        empty,
        acknowledgement_title,
        acknowledgement_body,
    )

    paragraphs = list(
        iter_reference_section_paragraphs(
            document_root,
            nsmap=NSMAP,
            get_paragraph_text=get_paragraph_text,
            skip_empty=True,
        )
    )

    assert [text for _paragraph, text in paragraphs] == ["[1] Example reference."]


def test_iter_reference_section_paragraphs_stops_before_appendix_variant():
    reference_title = _make_paragraph("参考文献")
    reference_body = _make_paragraph("[1] Example reference.")
    appendix_title = _make_paragraph("附录A")
    appendix_body = _make_paragraph("[2] Appendix note.")
    document_root = _doc_with_paragraphs(
        reference_title,
        reference_body,
        appendix_title,
        appendix_body,
    )

    paragraphs = list(
        iter_reference_section_paragraphs(
            document_root,
            nsmap=NSMAP,
            get_paragraph_text=get_paragraph_text,
            skip_empty=True,
        )
    )

    assert [text for _paragraph, text in paragraphs] == ["[1] Example reference."]


def test_is_reference_section_stop_text_recognizes_backmatter_and_chapter_titles():
    assert is_reference_section_stop_text("致谢")
    assert is_reference_section_stop_text("Acknowledgements")
    assert is_reference_section_stop_text("附录")
    assert is_reference_section_stop_text("附录A")
    assert is_reference_section_stop_text("第4章 结论与展望")
    assert not is_reference_section_stop_text("[1] Example reference.")
