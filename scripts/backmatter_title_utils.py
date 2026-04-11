from __future__ import annotations

import re


LNU_DOUBLE_SPACED_TITLE_MAP = {
    "摘要": "摘  要",
    "目录": "目  录",
    "序言": "序  言",
    "致谢": "致  谢",
}

_HEADING_NUMBER_PREFIX_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百\d]+[章节篇]|\d+(?:\.\d+)*)\s*"
)

REFERENCE_TITLES = frozenset(
    map(
        lambda text: re.sub(r"[\s\u3000]+", "", text).lower(),
        {
            "参考文献",
            "references",
        },
    )
)

ACKNOWLEDGEMENT_TITLES = frozenset(
    map(
        lambda text: re.sub(r"[\s\u3000]+", "", text).lower(),
        {
            "致谢",
            "致  谢",
            "致　　谢",
            "acknowledgement",
            "acknowledgements",
            "acknowledgment",
        },
    )
)

APPENDIX_TITLES = frozenset(
    map(
        lambda text: re.sub(r"[\s\u3000]+", "", text).lower(),
        {
            "附录",
            "附  录",
            "附　　录",
        },
    )
)

_BACKMATTER_PAGEBREAK_TITLES = frozenset({"参考文献", "附录", "致谢"})
ABSTRACT_CN_TITLES = frozenset(
    map(
        lambda text: re.sub(r"[\s\u3000]+", "", text).lower(),
        {
            "摘要",
            "摘  要",
            "摘　要",
            "中文摘要",
            "中  文  摘  要",
        },
    )
)
ABSTRACT_EN_TITLES = frozenset(
    map(
        lambda text: re.sub(r"[\s\u3000]+", "", text).lower(),
        {
            "abstract",
            "英文摘要",
            "英 文 摘 要",
        },
    )
)
TOC_TITLES = frozenset(
    map(
        lambda text: re.sub(r"[\s\u3000]+", "", text).lower(),
        {
            "目录",
            "目  录",
            "目　录",
            "contents",
            "table of contents",
        },
    )
)


def normalize_title_text(text: str | None) -> str:
    return re.sub(r"[\s\u3000]+", "", str(text or "")).lower()


def strip_heading_number_prefix(text: str | None) -> str:
    stripped = str(text or "").strip()
    return _HEADING_NUMBER_PREFIX_RE.sub("", stripped, count=1)


def normalize_heading_title_text(text: str | None) -> str:
    return normalize_title_text(strip_heading_number_prefix(text))


def matches_allowed_titles(text: str | None, allowed_titles) -> bool:
    if allowed_titles is None:
        return True
    normalized_allowed = {normalize_title_text(value) for value in allowed_titles}
    return normalize_title_text(text) in normalized_allowed


def is_backmatter_pagebreak_title(text: str | None) -> bool:
    return normalize_title_text(text) in _BACKMATTER_PAGEBREAK_TITLES


def is_abstract_cn_title(text: str | None) -> bool:
    return normalize_title_text(text) in ABSTRACT_CN_TITLES


def is_abstract_en_title(text: str | None) -> bool:
    return normalize_title_text(text) in ABSTRACT_EN_TITLES


def is_toc_title(text: str | None) -> bool:
    return normalize_title_text(text) in TOC_TITLES


def is_frontmatter_title(text: str | None) -> bool:
    return is_abstract_cn_title(text) or is_abstract_en_title(text) or is_toc_title(text)


def is_acknowledgement_title(text: str | None) -> bool:
    return normalize_title_text(text) in ACKNOWLEDGEMENT_TITLES


def is_reference_title(text: str | None) -> bool:
    return normalize_title_text(text) in REFERENCE_TITLES


def is_appendix_title(text: str | None) -> bool:
    normalized = normalize_title_text(text)
    return normalized in APPENDIX_TITLES or bool(re.match(r"^附录[a-z0-9]?$", normalized))


def detect_backmatter_bucket(text: str | None, paragraph_kind: str | None = None) -> str | None:
    if paragraph_kind not in (None, "h1"):
        return None
    if is_reference_title(text):
        return "references"
    if is_acknowledgement_title(text):
        return "acknowledgement"
    if is_appendix_title(text):
        return "appendix"
    return None


def is_lnu_title01_single_form(text: str | None) -> bool:
    return str(text or "").strip() in LNU_DOUBLE_SPACED_TITLE_MAP


def is_preface_heading_title(text: str | None) -> bool:
    return normalize_heading_title_text(text) == "序言"


def heading_title_contains_conclusion(text: str | None) -> bool:
    return "结论" in normalize_heading_title_text(text)


def resolve_lnu_double_spaced_title(text: str | None) -> str | None:
    stripped = str(text or "").strip()
    if stripped in LNU_DOUBLE_SPACED_TITLE_MAP:
        return LNU_DOUBLE_SPACED_TITLE_MAP[stripped]
    return None
