from __future__ import annotations

from backmatter_title_utils import (
    is_abstract_cn_title,
    is_abstract_en_title,
    detect_backmatter_bucket,
    heading_title_contains_conclusion,
    is_acknowledgement_title,
    is_backmatter_pagebreak_title,
    is_frontmatter_title,
    is_lnu_title01_single_form,
    is_preface_heading_title,
    is_reference_title,
    is_toc_title,
    matches_allowed_titles,
    resolve_lnu_double_spaced_title,
)


def test_detect_backmatter_bucket_handles_reference_ack_appendix_variants():
    assert detect_backmatter_bucket("参考文献", "h1") == "references"
    assert detect_backmatter_bucket("致  谢", "h1") == "acknowledgement"
    assert detect_backmatter_bucket("附录A", "h1") == "appendix"
    assert detect_backmatter_bucket("致谢说明", "h2") is None


def test_pagebreak_and_ack_title_detection_normalizes_spacing():
    assert is_backmatter_pagebreak_title("附  录")
    assert is_backmatter_pagebreak_title("致　　谢")
    assert is_acknowledgement_title("致  谢")
    assert is_reference_title("参考文献")


def test_lnu_title01_helpers_resolve_single_form_titles():
    assert is_lnu_title01_single_form("摘要")
    assert resolve_lnu_double_spaced_title("目录") == "目  录"
    assert resolve_lnu_double_spaced_title("致谢") == "致  谢"
    assert resolve_lnu_double_spaced_title("参考文献") is None


def test_frontmatter_title_helpers_normalize_abstract_and_toc_variants():
    assert is_abstract_cn_title("摘  要")
    assert is_abstract_en_title("Abstract")
    assert is_toc_title("目　录")
    assert is_toc_title("Table of Contents")
    assert is_frontmatter_title("目录")
    assert not is_frontmatter_title("参考文献")


def test_preface_and_conclusion_heading_helpers_ignore_number_prefixes():
    assert is_preface_heading_title("1 序言")
    assert is_preface_heading_title("序  言")
    assert heading_title_contains_conclusion("第4章 结论与展望")
    assert heading_title_contains_conclusion("5 结论")
    assert not heading_title_contains_conclusion("4 讨论")


def test_matches_allowed_titles_uses_normalized_title_comparison():
    allowed_titles = {"致  谢", "附录"}

    assert matches_allowed_titles("致谢", allowed_titles)
    assert matches_allowed_titles("附  录", allowed_titles)
    assert not matches_allowed_titles("参考文献", allowed_titles)
