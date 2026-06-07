from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from thesis_tool.scopes import normalize_scope_names


DEFAULT_OUTPUT_DIR = Path("/Users/apple/Desktop/论文格式修复输出")
DEFAULT_INTERMEDIATE_OUTPUT_DIR = Path(__file__).resolve().parents[2] / ".article_runtime" / "intermediate"
FORMAT_FIX_SUFFIX = "格式修复"
NORMALIZE_SUFFIX = "结构整理"
LAYOUT_CANDIDATE_SUFFIX = "版式候选稿"
VERSION_RE = re.compile(r"^(?P<stem>.+?)_(?P<suffix>格式修复|结构整理|版式候选稿)_v(?P<version>\d{2,})$", re.IGNORECASE)


def clean_versioned_stem(file_name: str) -> str:
    name = Path(file_name or "论文.docx").name
    suffix = ".docx" if name.lower().endswith(".docx") else ""
    stem = name[: -len(suffix)] if suffix else name
    while True:
        match = VERSION_RE.match(stem)
        if not match:
            break
        stem = match.group("stem")
    return stem or "论文"


def next_versioned_output_path(
    *,
    source_file_path: str,
    source_display_name: str | None,
    suffix_label: str = FORMAT_FIX_SUFFIX,
    output_dir: str | Path | None = None,
) -> str:
    target_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = clean_versioned_stem(source_display_name or Path(source_file_path).name)
    existing_versions = _existing_versions(target_dir, stem=stem, suffix_label=suffix_label)
    next_version = (max(existing_versions) + 1) if existing_versions else 1
    return str(target_dir / f"{stem}_{suffix_label}_V{next_version:02d}.docx")


def scoped_output_path(
    *,
    source_file_path: str,
    scopes: Iterable[str] | None,
    source_display_name: str | None,
) -> str:
    normalized_scopes = normalize_scope_names(scopes)
    if normalized_scopes:
        return next_versioned_output_path(
            source_file_path=source_file_path,
            source_display_name=source_display_name,
            suffix_label=FORMAT_FIX_SUFFIX,
        )
    return next_versioned_output_path(
        source_file_path=source_file_path,
        source_display_name=source_display_name,
        suffix_label=FORMAT_FIX_SUFFIX,
    )


def normalize_output_path(
    *,
    source_file_path: str,
    source_display_name: str | None,
    output_dir: str | Path | None = None,
) -> str:
    return next_versioned_output_path(
        source_file_path=source_file_path,
        source_display_name=source_display_name,
        suffix_label=NORMALIZE_SUFFIX,
        output_dir=output_dir or DEFAULT_INTERMEDIATE_OUTPUT_DIR,
    )


def _existing_versions(output_dir: Path, *, stem: str, suffix_label: str) -> list[int]:
    pattern = re.compile(
        rf"^{re.escape(stem)}_{re.escape(suffix_label)}_v(?P<version>\d{{2,}})\.docx$",
        re.IGNORECASE,
    )
    versions: list[int] = []
    if not output_dir.exists():
        return versions
    for path in output_dir.iterdir():
        match = pattern.match(path.name)
        if match:
            versions.append(int(match.group("version")))
    return versions
