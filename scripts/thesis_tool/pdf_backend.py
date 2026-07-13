from __future__ import annotations

from pathlib import Path


def _load_pdfium():
    try:
        import pypdfium2
    except ImportError as exc:
        raise RuntimeError("缺少内置 PDF 运行组件，请重新安装论文格式检查工具。") from exc
    return pypdfium2


def convert_pdf_with_pdfium(input_pdf: str, output_dir: Path) -> None:
    document = _load_pdfium().PdfDocument(str(Path(input_pdf).expanduser().resolve()))
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = None
            image = None
            try:
                bitmap = page.render(scale=120 / 72)
                image = bitmap.to_pil()
                image.save(output_dir / f"page-{index + 1}.png", "PNG")
            finally:
                if image is not None:
                    image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
    finally:
        document.close()


def extract_pdf_text_pages_with_pdfium(pdf_path: Path) -> list[str]:
    document = _load_pdfium().PdfDocument(str(pdf_path))
    page_texts: list[str] = []
    try:
        for index in range(len(document)):
            page = document[index]
            text_page = None
            try:
                text_page = page.get_textpage()
                page_texts.append(text_page.get_text_bounded())
            finally:
                if text_page is not None:
                    text_page.close()
                page.close()
    finally:
        document.close()
    return page_texts
