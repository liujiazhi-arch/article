from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

import audit_thesis
from _profile_utils import DEFAULT_PROFILE_ID, PROFILE_ALIASES, load_profile_bundle, resolve_template_profile_id
from thesis_fix.cover_template import normalize_cover_fields
from thesis_tool.scopes import list_scope_definitions, normalize_scope_names


DEFAULT_CFG = dict(audit_thesis.DEFAULT_CFG)
DEFAULT_CFG.update(
    {
        "toc_auto": False,
        "toc_title": "目录",
        "toc_max_level": 3,
    }
)
DEFAULT_HEADING_STYLE_IDS = {
    "h1": "Heading1",
    "h2": "Heading2",
    "h3": "Heading3",
    "h4": "Heading4",
}
KNOWN_SCOPES = frozenset(scope.id for scope in list_scope_definitions())
SAFE_NORMALIZE_SCOPE_IDS = (
    "page",
    "abstract",
    "headings",
    "body_paragraphs",
    "figures_tables",
    "references",
    "acknowledgement",
    "appendix",
)
SAFE_NORMALIZE_OPERATION_LABELS = {
    "soft_line_breaks": "清理软换行碎片",
    "object_wrapping": "归一化图表对象锚点/环绕",
    "heading_styles": "扶正高置信度标题样式",
    "abstract_keywords": "归位错放的摘要关键词",
    "frontmatter_sections": "归一化前置部分页码分节",
    "frontmatter_breaks": "清理前置部分冗余分页符",
    "duplicate_toc_title": "移除正文中重复目录标题",
    "toc_title": "规范目录标题段落",
    "toc_entries": "规范目录条目段落",
}


@dataclass(frozen=True)
class FixRuntime:
    cfg: dict
    profile_id: str
    heading_style_ids: dict
    requested_scopes: set[str] | None
    template_profile_id: str
    requested_profile: str | None = None
    fallback_used: bool = False
    renumber_headings: bool = False
    layout_rebalance: bool = False
    dry_run: bool = False
    cover_fields: dict[str, str] | None = None


@dataclass(frozen=True)
class ScopeFlags:
    cover: bool
    page: bool
    abstract: bool
    toc: bool
    headings: bool
    body: bool
    figures: bool
    references: bool
    acknowledgement: bool
    appendix: bool


@dataclass
class FixExecutionContext:
    document_root: ET.Element
    style_map: dict
    runtime: FixRuntime
    cfg: dict
    temp_dir: str | None
    document_model: object
    sections: dict
    paragraph_sections: dict
    protected_ids: set[int]
    editable_text_ids: set[int]
    scope_flags: ScopeFlags


def build_fix_runtime(
    profile_path=None,
    toc=False,
    scopes=None,
    renumber_headings=False,
    layout_rebalance=False,
    dry_run=False,
    strict_profile=None,
    cover_fields=None,
):
    profile_bundle = load_profile_bundle(
        profile_path,
        yaml_lib=getattr(audit_thesis, "yaml", None),
        warn=getattr(audit_thesis, "warn_profile", None),
        aliases=PROFILE_ALIASES,
        strict=strict_profile,
    )
    cfg = dict(DEFAULT_CFG)
    cfg.update(load_profile(profile_path, profile_bundle=profile_bundle) or {})
    if toc:
        cfg["toc_auto"] = True
    requested_scopes = normalize_scopes(scopes)
    normalized_cover_fields = normalize_cover_fields(cover_fields)
    cover_requested = requested_scopes is not None and "cover" in requested_scopes
    if cover_requested and normalized_cover_fields is None:
        raise ValueError("cover scope 需要完整 cover_fields")
    if normalized_cover_fields is not None and not cover_requested:
        raise ValueError("cover_fields 只能与显式 cover scope 一起使用")
    return FixRuntime(
        cfg=cfg,
        profile_id=profile_bundle.profile_id,
        heading_style_ids=dict(DEFAULT_HEADING_STYLE_IDS),
        requested_scopes=requested_scopes,
        template_profile_id=resolve_template_profile_id(profile_path, profile_bundle.profile_id, aliases=PROFILE_ALIASES),
        requested_profile=profile_bundle.requested_profile,
        fallback_used=profile_bundle.fallback_used,
        renumber_headings=bool(renumber_headings),
        layout_rebalance=bool(layout_rebalance),
        dry_run=bool(dry_run),
        cover_fields=normalized_cover_fields,
    )


def resolve_fix_cfg(cfg=None, runtime=None):
    if cfg is not None:
        return cfg
    if runtime is not None:
        return runtime.cfg
    return DEFAULT_CFG


def resolve_fix_profile_id(runtime=None):
    if runtime is not None:
        return runtime.profile_id
    return DEFAULT_PROFILE_ID


def resolve_fix_heading_style_ids(heading_style_ids=None, runtime=None):
    if heading_style_ids is not None:
        return heading_style_ids
    if runtime is not None:
        return runtime.heading_style_ids
    return DEFAULT_HEADING_STYLE_IDS


def _normalized_style_token(value) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


def resolve_document_heading_style_ids(style_map, runtime=None) -> dict[str, str]:
    resolved = dict(resolve_fix_heading_style_ids(runtime=runtime))
    for level in range(1, 5):
        key = f"h{level}"
        canonical = resolved[key]
        if canonical in style_map:
            continue
        expected_tokens = {f"heading{level}", f"标题{level}"}
        candidate = next(
            (
                style_id
                for style_id, props in style_map.items()
                if props.get("outlineLvl") == level - 1
                and {
                    _normalized_style_token(style_id),
                    _normalized_style_token(props.get("name")),
                }
                & expected_tokens
            ),
            None,
        )
        if candidate:
            resolved[key] = candidate
    return resolved


def normalize_scopes(scopes):
    normalized = normalize_scope_names(scopes)
    if normalized is None:
        return None
    return set(normalized)


def is_scope_enabled(scopes, *scope_ids):
    if scopes is None:
        return True
    return any(scope_id in scopes for scope_id in scope_ids)


def should_fix_heading_in_scope(scopes, section_name):
    if section_name == "body":
        return is_scope_enabled(scopes, "headings")
    if section_name == "appendix":
        return is_scope_enabled(scopes, "headings", "appendix")
    if section_name == "references":
        return is_scope_enabled(scopes, "headings", "references")
    if section_name == "acknowledgement":
        return is_scope_enabled(scopes, "headings", "acknowledgement")
    return False


def load_profile(profile_path, profile_bundle=None):
    bundle = profile_bundle or load_profile_bundle(
        profile_path,
        yaml_lib=getattr(audit_thesis, "yaml", None),
        warn=getattr(audit_thesis, "warn_profile", None),
        aliases=PROFILE_ALIASES,
    )
    return audit_thesis.build_profile_cfg(bundle.profile_id, bundle.profile_data, bundle.settings)


def is_lnu_profile(runtime=None):
    return resolve_fix_profile_id(runtime=runtime).startswith("lnu-")


def build_scope_flags(requested_scopes) -> ScopeFlags:
    return ScopeFlags(
        cover=requested_scopes is not None and "cover" in requested_scopes,
        page=is_scope_enabled(requested_scopes, "page"),
        abstract=is_scope_enabled(requested_scopes, "abstract"),
        toc=is_scope_enabled(requested_scopes, "toc"),
        headings=is_scope_enabled(requested_scopes, "headings"),
        body=is_scope_enabled(requested_scopes, "body_paragraphs"),
        figures=is_scope_enabled(requested_scopes, "figures_tables"),
        references=is_scope_enabled(requested_scopes, "references"),
        acknowledgement=is_scope_enabled(requested_scopes, "acknowledgement"),
        appendix=is_scope_enabled(requested_scopes, "appendix"),
    )
