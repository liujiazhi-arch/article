from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_thesis_rule_registries_do_not_import_audit_or_copy_globals():
    for path in sorted((PROJECT_ROOT / "scripts" / "thesis_rules").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "import audit_thesis" not in source, path
        assert "_load_audit" not in source, path
        assert "globals()[" not in source, path


def test_audit_thesis_does_not_store_rule_checker_bodies():
    source = (PROJECT_ROOT / "scripts" / "audit_thesis.py").read_text(encoding="utf-8")
    assert "\ndef check_" not in source


def test_audit_rule_checker_bodies_live_in_domain_modules():
    shared_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_checkers.py").read_text(encoding="utf-8")
    common_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_common.py").read_text(encoding="utf-8")
    lnu_source = (PROJECT_ROOT / "scripts" / "thesis_rules" / "audit_lnu.py").read_text(encoding="utf-8")

    assert "\ndef check_" not in shared_source
    assert "\ndef check_p01" in common_source
    assert "\ndef check_lnu_abs01" in lnu_source


def test_thesis_fix_modules_do_not_import_fix_or_copy_all_globals():
    for path in sorted((PROJECT_ROOT / "scripts" / "thesis_fix").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "import fix_thesis" not in source, path
        assert "_load_deps" not in source, path
        assert "dir(" not in source, path
        assert "globals()[" not in source, path
