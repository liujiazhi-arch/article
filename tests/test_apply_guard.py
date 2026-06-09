from thesis_tool.apply_guard import assess_apply_risk, assess_post_verify_notice, render_post_verify_notice


def _diagnostics(*, table_candidates: int = 0, style_conflicts: int = 0) -> dict:
    return {
        "table_heading_candidates": [object()] * table_candidates,
        "style_text_conflicts": [object()] * style_conflicts,
    }


def test_assess_apply_risk_warns_on_table_threshold_without_blocking():
    assessment = assess_apply_risk(
        _diagnostics(table_candidates=5),
        renumber_headings=True,
        selected_scopes={"headings"},
    )

    assert assessment.table_heading_risk_count == 5
    assert assessment.style_text_conflict_count == 0
    assert assessment.has_table_heading_risk is True
    assert assessment.has_style_text_conflict is False
    assert assessment.affects_heading_renumber is True
    assert assessment.should_block is False


def test_assess_apply_risk_blocks_style_conflict_only_when_heading_renumber_is_affected():
    assessment = assess_apply_risk(
        _diagnostics(style_conflicts=1),
        renumber_headings=True,
        selected_scopes={"headings"},
    )
    unrelated_scope_assessment = assess_apply_risk(
        _diagnostics(style_conflicts=1),
        renumber_headings=True,
        selected_scopes={"abstract"},
    )

    assert assessment.has_style_text_conflict is True
    assert assessment.affects_heading_renumber is True
    assert assessment.should_block is True
    assert unrelated_scope_assessment.affects_heading_renumber is False
    assert unrelated_scope_assessment.should_block is False


def test_assess_apply_risk_treats_missing_scope_filter_as_all_scopes_for_heading_renumber():
    assessment = assess_apply_risk(
        _diagnostics(style_conflicts=1),
        renumber_headings=True,
        selected_scopes=None,
    )

    assert assessment.affects_heading_renumber is True
    assert assessment.should_block is True


def test_assess_post_verify_notice_tracks_manual_unsupported_and_scope_filter():
    notice = assess_post_verify_notice(
        {
            "manual_review_rule_ids": ["M01"],
            "unsupported_rule_ids": ["U01", "U02"],
            "selected_scopes": ["abstract"],
        }
    )

    assert notice.has_notice is True
    assert notice.manual_review_rule_ids == ("M01",)
    assert notice.unsupported_rule_ids == ("U01", "U02")
    assert notice.has_selected_scope_filter is True


def test_render_post_verify_notice_formats_shared_manual_review_lines():
    lines = render_post_verify_notice(
        {
            "manual_review_rule_ids": ["M01"],
            "unsupported_rule_ids": ["U01", "U02"],
            "selected_scopes": ["abstract"],
        }
    )

    assert lines == [
        "[提示] 当前结果仍含人工复核项，评分较高不等于可直接提交。",
        "需人工确认规则: M01",
        "当前不支持规则: U01, U02",
        "注意: 以上结论仅覆盖当前复查范围。",
    ]
