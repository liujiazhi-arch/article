import audit_thesis
import pytest

from thesis_tool.scope_plan import build_scope_plan


def test_scope_plan_rejects_unknown_scope_before_audit(monkeypatch):
    def fail_if_audited(*_args, **_kwargs):
        pytest.fail("audit ran before scope validation")

    monkeypatch.setattr(audit_thesis, "audit_docx_with_runtime", fail_if_audited)

    with pytest.raises(ValueError, match="未知 scope"):
        build_scope_plan("unused.docx", scopes=["missing"])
