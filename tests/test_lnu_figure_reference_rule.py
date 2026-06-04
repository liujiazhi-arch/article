from __future__ import annotations

import audit_thesis


def test_lnu_f05_is_not_part_of_active_lnu_runtime():
    runtime_rule_ids = {rule_id for rule_id, _name, _severity in audit_thesis.build_audit_runtime("lnu").rule_definitions}

    assert "LNU_F05" not in runtime_rule_ids
