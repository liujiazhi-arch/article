from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document

import fix_docx_io


def test_write_docx_atomically_keeps_docx_openable(tmp_path: Path):
    source_path = tmp_path / "source.docx"
    output_path = tmp_path / "output.docx"

    fix_docx_io.Document = Document

    doc = Document()
    doc.add_paragraph("测试输出写盘")
    doc.save(source_path)

    with zipfile.ZipFile(source_path, "r") as source_zip:
        document_xml = source_zip.read("word/document.xml")

    fix_docx_io.write_docx_atomically(
        str(source_path),
        str(output_path),
        {"word/document.xml": document_xml},
    )

    reopened = Document(output_path)
    assert output_path.exists()
    assert reopened.paragraphs[0].text == "测试输出写盘"
