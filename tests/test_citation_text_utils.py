from citation_text_utils import (
    CITATION_NUMBER_GROUP_RE,
    citation_numbers_from_group,
    contains_citation_token,
    citation_numbers_from_token,
    format_citation_numbers,
    is_citation_token,
)


def test_citation_numbers_from_token_expands_commas_ranges_and_reverse_ranges():
    assert citation_numbers_from_token("[1, 3，5、7-9,12-10]") == [1, 3, 5, 7, 8, 9, 12, 11, 10]


def test_citation_numbers_from_token_ignores_non_citation_text_and_invalid_parts():
    assert citation_numbers_from_token("正文[1]") == []
    assert citation_numbers_from_token("[1,a,2000,3]") == [1, 3]


def test_citation_token_predicates_share_strict_run_pattern():
    assert is_citation_token("[1,2-3，4、5]") is True
    assert is_citation_token("[01]") is True
    assert is_citation_token("正文[1]") is False
    assert is_citation_token("[1,a]") is False
    assert contains_citation_token("正文[1]结尾") is True


def test_body_citation_number_group_expands_commas_and_ranges_with_legacy_reverse_range_order():
    assert citation_numbers_from_group("1, 3，5、7-9,12-10") == [1, 3, 5, 7, 8, 9, 10, 11, 12]
    assert CITATION_NUMBER_GROUP_RE.findall("正文[1,2]和[4-3]") == ["1,2", "4-3"]


def test_format_citation_numbers_sorts_deduplicates_and_compresses_runs_of_three_or_more():
    assert format_citation_numbers([3, 2, 1, 2, 5, 6, 8, 10, 9]) == "[1-3,5,6,8-10]"
