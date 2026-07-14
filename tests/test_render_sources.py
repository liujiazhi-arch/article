from pathlib import Path

import pytest

import thesis_tool.render_sources as render_sources_module
from thesis_tool.render_sources import resolve_render_source


def test_resolve_render_source_normalizes_manual_page_images(tmp_path):
    page_dir = tmp_path / "pages"
    page_dir.mkdir()
    for name in ("page-10.png", "page-2.png", "page-1.png"):
        (page_dir / name).write_bytes(b"png")

    metadata = resolve_render_source(
        "unused.docx",
        str(tmp_path / "proof"),
        "auto",
        page_images_dir=str(page_dir),
    )

    assert metadata == {
        "engine": "wps-manual-images",
        "page_dir": str(page_dir.resolve()),
        "pdf_path": None,
        "page_images": [
            str((page_dir / "page-1.png").resolve()),
            str((page_dir / "page-2.png").resolve()),
            str((page_dir / "page-10.png").resolve()),
        ],
        "fallback_used": False,
        "warnings": [],
    }


def test_resolve_render_source_normalizes_generated_word_pages(monkeypatch, tmp_path):
    def fake_export(_input_docx: str, output_pdf: str) -> None:
        Path(output_pdf).write_bytes(b"%PDF")

    def fake_convert(_input_pdf: str, output_dir: str) -> None:
        page_dir = Path(output_dir)
        page_dir.mkdir(parents=True)
        (page_dir / "page-1.png").write_bytes(b"png")

    monkeypatch.setattr(render_sources_module, "_export_docx_to_pdf_with_word", fake_export)
    monkeypatch.setattr(render_sources_module, "_convert_pdf_to_page_images", fake_convert)

    metadata = resolve_render_source("paper.docx", str(tmp_path / "proof"), "auto")

    assert metadata["engine"] == "word-pdf"
    assert metadata["pdf_path"].endswith("render_verify_word.pdf")
    assert metadata["page_images"] == [str((tmp_path / "proof" / "word_pdf_pages" / "page-1.png").resolve())]


def test_resolve_render_source_rejects_conflicting_or_invalid_manual_sources(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF")
    empty_dir = tmp_path / "empty-pages"
    empty_dir.mkdir()

    with pytest.raises(ValueError, match="只能选择一个"):
        resolve_render_source(
            "paper.docx",
            str(tmp_path / "proof"),
            "auto",
            rendered_pdf=str(pdf_path),
            page_images_dir=str(empty_dir),
        )
    with pytest.raises(RuntimeError, match="PDF 不存在"):
        resolve_render_source(
            "paper.docx",
            str(tmp_path / "proof"),
            "auto",
            rendered_pdf=str(tmp_path / "missing.pdf"),
        )
    with pytest.raises(RuntimeError, match="未发现 PNG"):
        resolve_render_source(
            "paper.docx",
            str(tmp_path / "proof"),
            "auto",
            page_images_dir=str(empty_dir),
        )
