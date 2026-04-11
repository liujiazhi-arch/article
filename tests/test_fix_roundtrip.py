from pathlib import Path

import pytest

from .conftest import FIX_ROUNDTRIP_RULE_IDS, audit_rule_status, fix_thesis, make_violating_doc


@pytest.mark.parametrize("rule_id", FIX_ROUNDTRIP_RULE_IDS)
def test_fix_roundtrip_clears_all_issues(tmp_docx, tmp_path, rule_id):
    source_path = tmp_docx(make_violating_doc, filename=f"{rule_id.lower()}_source.docx", rule_id=rule_id)
    before = audit_rule_status(source_path, rule_id)
    assert not before["rule"]["passed"]

    fixed_path = Path(tmp_path) / f"{rule_id.lower()}_fixed.docx"
    fix_thesis.fix_docx(str(source_path), str(fixed_path))

    after = audit_rule_status(fixed_path, rule_id)
    assert after["rule"]["passed"], after["rule"]["issues"]
    assert after["failed_ids"] == []

