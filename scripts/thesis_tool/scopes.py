from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeDefinition:
    id: str
    title: str
    description: str
    rule_ids: tuple[str, ...]
    aliases: tuple[str, ...] = ()


SCOPE_DEFINITIONS = (
    ScopeDefinition(
        id="page",
        title="页面与页码",
        description="页边距、页码、页脚等页面层设置。",
        rule_ids=("P01", "P03", "PG01", "FN01"),
        aliases=("pages", "layout"),
    ),
    ScopeDefinition(
        id="abstract",
        title="摘要",
        description="中文摘要、英文摘要及关键词格式。",
        rule_ids=("KW01", "KW02", "LNU_ABS01", "LNU_ABS02", "LNU_ABS03", "LNU_ABS04", "LNU_TITLE01"),
        aliases=("summary", "abstract_cn", "abstract_en"),
    ),
    ScopeDefinition(
        id="toc",
        title="目录",
        description="目录生成、目录条目与目录样式。",
        rule_ids=("LNU_TOC01", "LNU_TOC02", "LNU_TOC03"),
        aliases=("contents",),
    ),
    ScopeDefinition(
        id="headings",
        title="正文标题",
        description="各级标题的字体、字号、编号和分页。",
        rule_ids=("H01", "H02", "H03", "H04", "S01", "S02", "LNU_H01", "LNU_CONC01", "LNU_S03"),
        aliases=("heading", "title"),
    ),
    ScopeDefinition(
        id="body_paragraphs",
        title="正文段落",
        description="正文段落字体、字号、行距、缩进、标点和正文内引用。",
        rule_ids=(
            "T01",
            "T02",
            "T03",
            "T04",
            "T05",
            "T06",
            "S03",
            "C01",
            "C02",
            "C03",
            "C04",
            "EQ01",
            "EQ02",
            "EQ03",
            "SP01",
            "SP02",
            "SP_CJK_LATIN",
            "SP_NUM_CJK",
            "PU01",
            "PU02",
            "LNU_FMT01",
            "LNU_UNIT01",
        ),
        aliases=("body", "paragraph", "paragraphs"),
    ),
    ScopeDefinition(
        id="figures_tables",
        title="图表与表格",
        description="图题、表题、图片段落和表格边框/字号。",
        rule_ids=(
            "F01",
            "F02",
            "F03",
            "F04",
            "F05",
            "F06",
            "F07",
            "TB01",
            "TB02",
            "TB03",
            "TB03_LINE",
            "LNU_F01",
            "LNU_F02",
            "LNU_F03",
            "LNU_F05",
            "LNU_F06",
            "LNU_FMT02",
            "LNU_TB01",
            "LNU_TB02",
            "LNU_TB03",
            "LNU_TB04",
        ),
        aliases=("figures", "tables", "captions"),
    ),
    ScopeDefinition(
        id="references",
        title="参考文献",
        description="参考文献列表、编号、缩进和标点。",
        rule_ids=("R01", "R02", "R03", "R04", "R05", "REF01", "LNU_REF01", "LNU_REF02", "LNU_REF03", "LNU_REF04", "LNU_REF05"),
        aliases=("reference", "bibliography"),
    ),
    ScopeDefinition(
        id="acknowledgement",
        title="致谢",
        description="致谢正文及与致谢相关的专用规则。",
        rule_ids=("LNU_ACK01",),
        aliases=("ack", "thanks"),
    ),
    ScopeDefinition(
        id="appendix",
        title="附录",
        description="附录正文按正文格式修复。",
        rule_ids=(),
        aliases=("appendices",),
    ),
)

_SCOPE_BY_ID = {scope.id: scope for scope in SCOPE_DEFINITIONS}
_RULE_TO_SCOPE = {}
_ALIASES = {"all": tuple(scope.id for scope in SCOPE_DEFINITIONS)}

for scope in SCOPE_DEFINITIONS:
    for rule_id in scope.rule_ids:
        _RULE_TO_SCOPE[rule_id] = scope.id
    for alias in scope.aliases:
        _ALIASES[alias] = (scope.id,)


def list_scope_definitions() -> tuple[ScopeDefinition, ...]:
    return SCOPE_DEFINITIONS


def list_scoped_rule_ids() -> tuple[str, ...]:
    return tuple(_RULE_TO_SCOPE)


def get_scope_definition(scope_id: str) -> ScopeDefinition:
    return _SCOPE_BY_ID[scope_id]


def scope_for_rule(rule_id: str) -> str | None:
    return _RULE_TO_SCOPE.get(rule_id)


def normalize_scope_names(scope_names) -> set[str] | None:
    if scope_names is None:
        return None

    tokens: list[str] = []
    if isinstance(scope_names, str):
        scope_names = [scope_names]

    for value in scope_names:
        if value is None:
            continue
        for token in str(value).split(","):
            normalized = token.strip().lower()
            if normalized:
                tokens.append(normalized)

    if not tokens:
        return None

    resolved: set[str] = set()
    for token in tokens:
        if token in _SCOPE_BY_ID:
            resolved.add(token)
            continue
        alias_targets = _ALIASES.get(token)
        if alias_targets is not None:
            resolved.update(alias_targets)
            continue
        available = ", ".join(scope.id for scope in SCOPE_DEFINITIONS)
        raise ValueError(f"未知 scope: {token}。可用值: {available}")
    return resolved


def scope_enabled(requested_scopes: set[str] | None, *scope_ids: str) -> bool:
    if requested_scopes is None:
        return True
    return any(scope_id in requested_scopes for scope_id in scope_ids)
