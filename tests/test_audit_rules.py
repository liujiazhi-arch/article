import pytest

from .conftest import TARGET_RULE_IDS, audit_rule_status, make_compliant_doc, make_violating_doc


@pytest.mark.parametrize("rule_id", TARGET_RULE_IDS)
def test_rule_passes_on_compliant_doc(tmp_docx, rule_id):
    docx_path = tmp_docx(make_compliant_doc, filename=f"{rule_id.lower()}_ok.docx")
    status = audit_rule_status(docx_path, rule_id)

    assert status["rule"]["passed"], status["rule"]["issues"]


@pytest.mark.parametrize("rule_id", TARGET_RULE_IDS)
def test_rule_is_detected_on_violating_doc(tmp_docx, rule_id):
    docx_path = tmp_docx(make_violating_doc, filename=f"{rule_id.lower()}_bad.docx", rule_id=rule_id)
    status = audit_rule_status(docx_path, rule_id)

    assert not status["rule"]["passed"]
    assert status["rule"]["issues"]

