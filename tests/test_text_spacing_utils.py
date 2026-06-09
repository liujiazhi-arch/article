from text_spacing_utils import needs_num_cjk_space, starts_with_num_cjk_exception


def test_needs_num_cjk_space_requires_space_for_plain_number_chinese_boundary():
    text = "检测12样本"

    assert needs_num_cjk_space(text, 3, "2", "样") is True


def test_needs_num_cjk_space_skips_known_unit_and_left_heading_exceptions():
    assert needs_num_cjk_space("检测12个样本", 3, "2", "个") is False
    assert needs_num_cjk_space("第3章", 0, "第", "3") is False
    assert needs_num_cjk_space("图2结果", 0, "图", "2") is False


def test_starts_with_num_cjk_exception_uses_longest_token_table():
    assert starts_with_num_cjk_exception("2026年月日", 4) is True
    assert starts_with_num_cjk_exception("2026指标", 4) is False
