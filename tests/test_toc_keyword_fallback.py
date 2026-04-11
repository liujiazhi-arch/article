from __future__ import annotations

from types import SimpleNamespace
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fix_thesis
from _thesis_utils import W_NS, get_paragraph_text

W = W_NS


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _make_paragraph(text: str = "") -> ET.Element:
    p = ET.Element(_w("p"))
    r = ET.SubElement(p, _w("r"))
    t = ET.SubElement(r, _w("t"))
    t.text = text
    return p


def _make_doc_root(*paragraphs: ET.Element) -> ET.Element:
    root = ET.Element(_w("document"))
    body = ET.SubElement(root, _w("body"))
    for paragraph in paragraphs:
        body.append(paragraph)
    return root


def test_repair_misplaced_keywords_falls_back_when_toc_nodes_are_stale(monkeypatch):
    abstract_body = _make_paragraph("This is the abstract.")
    placeholder = _make_paragraph("")
    toc_title = _make_paragraph("目  录")
    toc_entry = _make_paragraph("第一章 绪论..........1")
    misplaced_keywords = _make_paragraph("关键词：方法；结果；分析")
    doc = _make_doc_root(abstract_body, placeholder, toc_title, toc_entry, misplaced_keywords)

    stale_toc_para = _make_paragraph("stale toc node")
    fake_model = SimpleNamespace(
        paragraph_sections={id(placeholder): "abstract_en"},
        paragraphs=[SimpleNamespace(container_section="toc", elem=stale_toc_para)],
    )
    monkeypatch.setattr(fix_thesis, "build_document_model", lambda *_args, **_kwargs: fake_model)

    changed = fix_thesis.repair_misplaced_abstract_keywords(doc, style_map={})

    assert changed == 1
    body = doc.find(f"{{{W}}}body")
    assert body is not None
    texts = [get_paragraph_text(p).strip() for p in body.findall(_w("p"))]
    assert texts == [
        "This is the abstract.",
        "关键词：方法；结果；分析",
        "目  录",
        "第一章 绪论..........1",
    ]
