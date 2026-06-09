from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from thesis_tool.scopes import scope_enabled


TABLE_HEADING_RISK_THRESHOLD = 5


@dataclass(frozen=True)
class ApplyRiskAssessment:
    table_heading_risk_count: int
    style_text_conflict_count: int
    affects_heading_renumber: bool
    table_heading_risk_threshold: int = TABLE_HEADING_RISK_THRESHOLD

    @property
    def has_table_heading_risk(self) -> bool:
        return self.table_heading_risk_count >= self.table_heading_risk_threshold

    @property
    def has_style_text_conflict(self) -> bool:
        return self.style_text_conflict_count >= 1

    @property
    def should_block(self) -> bool:
        return self.has_style_text_conflict and self.affects_heading_renumber


@dataclass(frozen=True)
class PostVerifyNoticeAssessment:
    manual_review_rule_ids: tuple[str, ...]
    unsupported_rule_ids: tuple[str, ...]
    has_selected_scope_filter: bool

    @property
    def has_notice(self) -> bool:
        return bool(self.manual_review_rule_ids or self.unsupported_rule_ids)


def assess_apply_risk(
    diagnostics: Mapping[str, Any],
    *,
    renumber_headings: bool,
    selected_scopes: Iterable[str] | None,
) -> ApplyRiskAssessment:
    selected_scope_set = set(selected_scopes) if selected_scopes is not None else None
    affects_heading_renumber = bool(
        renumber_headings and scope_enabled(selected_scope_set, "headings")
    )
    return ApplyRiskAssessment(
        table_heading_risk_count=len(diagnostics["table_heading_candidates"]),
        style_text_conflict_count=len(diagnostics["style_text_conflicts"]),
        affects_heading_renumber=affects_heading_renumber,
    )


def assess_post_verify_notice(verification: Mapping[str, Any]) -> PostVerifyNoticeAssessment:
    return PostVerifyNoticeAssessment(
        manual_review_rule_ids=tuple(verification.get("manual_review_rule_ids") or ()),
        unsupported_rule_ids=tuple(verification.get("unsupported_rule_ids") or ()),
        has_selected_scope_filter=bool(verification.get("selected_scopes")),
    )


def render_post_verify_notice(verification: Mapping[str, Any]) -> list[str]:
    assessment = assess_post_verify_notice(verification)
    lines: list[str] = []

    if assessment.has_notice:
        lines.append("[提示] 当前结果仍含人工复核项，评分较高不等于可直接提交。")
        if assessment.manual_review_rule_ids:
            lines.append(f"需人工确认规则: {', '.join(assessment.manual_review_rule_ids)}")
        if assessment.unsupported_rule_ids:
            lines.append(f"当前不支持规则: {', '.join(assessment.unsupported_rule_ids)}")
        if assessment.has_selected_scope_filter:
            lines.append("注意: 以上结论仅覆盖当前复查范围。")
    return lines
