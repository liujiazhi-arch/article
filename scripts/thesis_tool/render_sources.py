from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from thesis_tool.pdf_backend import convert_pdf_with_pdfium


RENDERER_AUTO = "auto"
RENDERER_WORD_PDF = "word-pdf"
RENDERER_MANUAL_PDF = "manual-pdf"
RENDERER_WPS_MANUAL_IMAGES = "wps-manual-images"
SUPPORTED_RENDERERS = {RENDERER_AUTO, RENDERER_WORD_PDF}


def _page_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"page-(\d+)\.png$", path.name)
    if match:
        return int(match.group(1)), path.name
    return sys.maxsize, path.name


def _collect_page_images(output_dir: str | Path) -> list[str]:
    directory = Path(output_dir).expanduser().resolve()
    return [str(path) for path in sorted(directory.glob("page-*.png"), key=_page_sort_key)]


def _collect_png_images(output_dir: str | Path) -> list[str]:
    directory = Path(output_dir).expanduser().resolve()
    page_images = _collect_page_images(directory)
    if page_images:
        return page_images
    return [str(path) for path in sorted(directory.glob("*.png"), key=_page_sort_key)]


def _find_external_tool(*, env_name: str, binary: str, missing_message: str) -> str:
    env_path = os.environ.get(env_name)
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)
    found = shutil.which(binary)
    if found:
        return found
    raise RuntimeError(missing_message)


def _find_pdftoppm() -> str:
    return _find_external_tool(
        env_name="ARTICLE_PDFTOPPM",
        binary="pdftoppm",
        missing_message="未找到 pdftoppm，无法将 Word PDF 转为页图。请安装 poppler 或设置 ARTICLE_PDFTOPPM。",
    )


def _find_pdftotext() -> str:
    return _find_external_tool(
        env_name="ARTICLE_PDFTOTEXT",
        binary="pdftotext",
        missing_message="未找到 pdftotext，无法抽取 PDF 每页文本。请安装 poppler 或设置 ARTICLE_PDFTOTEXT。",
    )


def _export_docx_to_pdf_with_word(input_docx: str, output_pdf: str) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("word-pdf 渲染目前仅支持 macOS 上的 Microsoft Word。")
    if shutil.which("osascript") is None:
        raise RuntimeError("未找到 osascript，无法调用 Microsoft Word 导出 PDF。")

    script = """
on run argv
  set inputPath to POSIX file (item 1 of argv)
  set outputPath to POSIX file (item 2 of argv)
  set expectedPath to item 1 of argv
  tell application "Microsoft Word"
    repeat with candidate in documents
      set candidatePath to ""
      try
        set candidatePath to POSIX path of (full name of candidate as alias)
      end try
      if candidatePath is expectedPath then
        error "The staged DOCX is already open in Microsoft Word; refusing to reuse it."
      end if
    end repeat
    open inputPath
    set docRef to missing value
    set observedDocuments to {}
    try
    repeat with attempt from 1 to 30
      set observedDocuments to {}
      repeat with candidate in documents
        set candidatePath to ""
        try
          set candidatePath to POSIX path of (full name of candidate as alias)
        end try
        if candidatePath is not "" then
          set end of observedDocuments to candidatePath
        end if
        if candidatePath is expectedPath then
          set docRef to candidate
          exit repeat
        end if
      end repeat
      if docRef is not missing value then exit repeat
      delay 1
    end repeat
    if docRef is missing value then
      error "Microsoft Word did not expose the opened DOCX; observed=" & observedDocuments
    end if
    save as docRef file name outputPath file format format PDF
    on error errorMessage number errorNumber
      if docRef is not missing value then
        try
          close docRef saving no
        end try
      end if
      error errorMessage number errorNumber
    end try
    close docRef saving no
  end tell
end run
"""
    try:
        input_path = Path(input_docx).expanduser().resolve()
        output_path = Path(output_pdf).expanduser().resolve()
        subprocess.run(
            ["osascript", "-e", script, str(input_path), str(output_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Microsoft Word 自动化没有完成，未能导出 PDF。通常是 Word 没有暴露已打开的 DOCX，"
            "或正在等待权限、恢复文档、允许访问文件、保存确认等弹窗。请先处理 Word 弹窗；仍失败时改用手动导出 PDF。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "Microsoft Word 导出 PDF 失败。"
        if details:
            message = f"{message}\n{details}"
        raise RuntimeError(message) from exc

    if not Path(output_pdf).exists():
        raise RuntimeError(f"Microsoft Word 未生成 PDF: {output_pdf}")


def _convert_pdf_to_page_images(input_pdf: str, output_dir: str) -> None:
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    for stale_page in resolved_output_dir.glob("page-*.png"):
        stale_page.unlink()
    try:
        pdftoppm = _find_pdftoppm()
    except RuntimeError:
        try:
            convert_pdf_with_pdfium(input_pdf, resolved_output_dir)
        except Exception as exc:
            raise RuntimeError(f"PDF 转页图失败。\n{exc}") from exc
        return
    prefix = str(resolved_output_dir / "page")
    try:
        subprocess.run(
            [pdftoppm, "-png", "-r", "120", str(Path(input_pdf).expanduser().resolve()), prefix],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "PDF 转页图失败。"
        if details:
            message = f"{message}\n{details}"
        raise RuntimeError(message) from exc


def _run_word_pdf_render(input_docx: str, output_dir: str) -> dict:
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = resolved_output_dir / "render_verify_word.pdf"
    page_dir = resolved_output_dir / "word_pdf_pages"
    _export_docx_to_pdf_with_word(input_docx, str(pdf_path))
    _convert_pdf_to_page_images(str(pdf_path), str(page_dir))
    return {
        "engine": RENDERER_WORD_PDF,
        "page_dir": str(page_dir),
        "pdf_path": str(pdf_path),
        "fallback_used": False,
        "warnings": [],
    }


def _run_render_engine(input_docx: str, output_dir: str, renderer: str) -> dict:
    if renderer not in SUPPORTED_RENDERERS:
        supported = ", ".join(sorted(SUPPORTED_RENDERERS))
        raise ValueError(f"未知渲染器: {renderer}。可选: {supported}")
    return _run_word_pdf_render(input_docx, output_dir)


def _run_external_pdf_render(rendered_pdf: str, output_dir: str) -> dict:
    resolved_pdf = Path(rendered_pdf).expanduser().resolve()
    if not resolved_pdf.exists():
        raise RuntimeError(f"用户提供的渲染 PDF 不存在: {resolved_pdf}")
    if resolved_pdf.suffix.lower() != ".pdf":
        raise RuntimeError(f"--rendered-pdf 需要 PDF 文件: {resolved_pdf}")
    page_dir = Path(output_dir).expanduser().resolve() / "manual_pdf_pages"
    _convert_pdf_to_page_images(str(resolved_pdf), str(page_dir))
    return {
        "engine": RENDERER_MANUAL_PDF,
        "page_dir": str(page_dir),
        "pdf_path": str(resolved_pdf),
        "fallback_used": False,
        "warnings": [],
    }


def _run_external_page_images(page_images_dir: str) -> dict:
    resolved_dir = Path(page_images_dir).expanduser().resolve()
    if not resolved_dir.exists() or not resolved_dir.is_dir():
        raise RuntimeError(f"用户提供的页图目录不存在: {resolved_dir}")
    if not _collect_png_images(resolved_dir):
        raise RuntimeError(f"用户提供的页图目录未发现 PNG 页图: {resolved_dir}")
    return {
        "engine": RENDERER_WPS_MANUAL_IMAGES,
        "page_dir": str(resolved_dir),
        "pdf_path": None,
        "fallback_used": False,
        "warnings": [],
    }


def resolve_render_source(
    input_docx: str,
    output_dir: str,
    renderer: str,
    *,
    rendered_pdf: str | None = None,
    page_images_dir: str | None = None,
) -> dict:
    if rendered_pdf and page_images_dir:
        raise ValueError("--rendered-pdf 和 --page-images-dir 只能选择一个。")
    if rendered_pdf:
        metadata = _run_external_pdf_render(rendered_pdf, output_dir)
    elif page_images_dir:
        metadata = _run_external_page_images(page_images_dir)
    else:
        metadata = _run_render_engine(input_docx, output_dir, renderer)

    page_images = _collect_png_images(metadata["page_dir"])
    if not page_images:
        raise RuntimeError(f"渲染未产出页图: {metadata['page_dir']}")
    return {**metadata, "page_images": page_images}
