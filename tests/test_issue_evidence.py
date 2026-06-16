from thesis_tool.issue_evidence import build_issue_groups


def _ctx(index, text, kind="body", section="body", module="body_paragraph"):
    return {
        "index": index,
        "text": text,
        "kind": kind,
        "section": section,
        "module": module,
    }


def test_build_issue_groups_adds_nearest_heading_and_groups_examples():
    contexts = [
        _ctx(1, "1.3.2 溶胀率和溶失率测定", kind="h3", module="body_heading"),
        _ctx(2, "式中，W0为样品初始干质量。"),
        _ctx(3, "式中，Wt为浸泡后质量。"),
        _ctx(4, "式中，m1为样品质量。"),
        _ctx(5, "式中，V2为样品体积。"),
    ]
    result = {
        "id": "LNU_EQ05",
        "name": "公式说明变量后缀下标",
        "passed": False,
        "issues": ["4 个公式说明段存在变量下标格式问题。"],
        "affected": "第2段、第3段、第4段、第5段",
        "evidence": [
            {"paragraph_index": 2, "text": "式中，W0为样品初始干质量。", "tokens": [{"text": "W0", "bad_part": "0", "expected": "subscript"}]},
            {"paragraph_index": 3, "text": "式中，Wt为浸泡后质量。", "tokens": [{"text": "Wt", "bad_part": "t", "expected": "subscript"}]},
            {"paragraph_index": 4, "text": "式中，m1为样品质量。", "tokens": [{"text": "m1", "bad_part": "1", "expected": "subscript"}]},
            {"paragraph_index": 5, "text": "式中，V2为样品体积。", "tokens": [{"text": "V2", "bad_part": "2", "expected": "subscript"}]},
        ],
    }

    groups = build_issue_groups(
        [result],
        contexts,
        actions={"LNU_EQ05": "autofix"},
        rule_to_scope={"LNU_EQ05": "body_paragraphs"},
        source_docx="thesis.docx",
    )

    assert len(groups) == 1
    group = groups[0]
    assert group["rule_id"] == "LNU_EQ05"
    assert group["action"] == "auto_fixable"
    assert group["scope_id"] == "body_paragraphs"
    assert group["total_count"] == 4
    assert group["shown_count"] == 3
    assert group["hidden_count"] == 1
    assert group["examples"][0]["nearest_heading"] == "1.3.2 溶胀率和溶失率测定"
    assert group["examples"][0]["paragraph_index"] == 2
    assert group["examples"][0]["tokens"][0]["text"] == "W0"
    assert "apply thesis.docx --profile lnu --scope body_paragraphs" in group["suggested_command"]


def test_build_issue_groups_quotes_source_path_in_suggested_command():
    result = {
        "id": "LNU_EQ05",
        "name": "公式说明变量后缀下标",
        "passed": False,
        "issues": ["1 个公式说明段存在变量下标格式问题。"],
        "affected": "第2段",
        "evidence": [{"paragraph_index": 2, "text": "式中，W0为样品初始干质量。", "tokens": []}],
    }

    groups = build_issue_groups(
        [result],
        [_ctx(2, "式中，W0为样品初始干质量。")],
        actions={"LNU_EQ05": "autofix"},
        rule_to_scope={"LNU_EQ05": "body_paragraphs"},
        source_docx="/tmp/my thesis/source.docx",
    )

    assert "apply '/tmp/my thesis/source.docx' --profile lnu" in groups[0]["suggested_command"]


def test_build_issue_groups_handles_unknown_action_and_fallback_without_count():
    result = {
        "id": "SP_CJK_LATIN",
        "name": "中英文字符间距",
        "passed": False,
        "issues": ["正文段落存在中英文字符间距缺失。"],
        "affected": "第2段、第3段 等12段",
    }

    groups = build_issue_groups(
        [result],
        [_ctx(2, "鹿皮gelatin样品稳定。")],
        actions={"SP_CJK_LATIN": "unknown"},
        rule_to_scope={},
        source_docx="thesis.docx",
    )

    assert groups[0]["action"] == "unknown"
    assert groups[0]["scope_id"] is None
    assert groups[0]["total_count"] is None
    assert groups[0]["source"] == "checker_message_fallback"
    assert groups[0]["examples"][0]["tokens"] == []
