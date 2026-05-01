from __future__ import annotations

from pathlib import Path

import yaml

import audit_thesis
from thesis_tool.capabilities import load_rule_capabilities
from thesis_tool.scopes import list_scope_definitions, list_scoped_rule_ids, scope_for_rule


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_MATRIX = PROJECT_ROOT / "config" / "capability_matrix.md"
LNU_PROFILE = PROJECT_ROOT / "config" / "profiles" / "lnu-checker-2026.yaml"


def _parse_matrix_autofix_flags() -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for line in CAPABILITY_MATRIX.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("| LNU_"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 6:
            continue
        rule_id = cells[0]
        autofix_flag = cells[4]
        flags[rule_id] = autofix_flag == "✓"
    return flags


def test_lnu_profile_fix_metadata_matches_capability_matrix():
    profile_data = yaml.safe_load(LNU_PROFILE.read_text(encoding="utf-8"))
    additions = {
        item["id"]: item
        for item in profile_data.get("additions", [])
        if str(item.get("id", "")).startswith("LNU_")
    }
    matrix_flags = _parse_matrix_autofix_flags()

    assert matrix_flags, "No LNU_* entries found in capability matrix"

    for rule_id, autofix_enabled in matrix_flags.items():
        assert rule_id in additions, f"{rule_id} missing from lnu-checker-2026 additions"
        fix_meta = additions[rule_id].get("fix")
        if autofix_enabled:
            assert fix_meta not in (None, ""), f"{rule_id} is autofixable in matrix but fix metadata is empty"
        else:
            assert fix_meta in (None, ""), f"{rule_id} is not autofixable in matrix but fix metadata is populated"


def test_lnu_autofixable_rules_are_addressable_by_scope():
    profile_data = yaml.safe_load(LNU_PROFILE.read_text(encoding="utf-8"))
    additions = {
        item["id"]: item
        for item in profile_data.get("additions", [])
        if str(item.get("id", "")).startswith("LNU_")
    }
    capabilities = load_rule_capabilities()

    autofixable_rules = [
        rule_id
        for rule_id, item in additions.items()
        if item.get("fix") not in (None, "") and capabilities.get(rule_id, {}).get("autofix") == "✓"
    ]

    assert autofixable_rules, "No autofixable LNU rules found for scope coverage check"

    for rule_id in autofixable_rules:
        assert scope_for_rule(rule_id) is not None, f"{rule_id} is autofixable but not mapped to any scope"


def test_scope_definitions_only_reference_known_capability_rules():
    capabilities = load_rule_capabilities()

    for scope in list_scope_definitions():
        for rule_id in scope.rule_ids:
            assert rule_id in capabilities, f"{scope.id} references unknown capability rule {rule_id}"


def test_all_autofixable_runtime_rules_are_mapped_to_scopes():
    capabilities = load_rule_capabilities()
    runtime_rule_ids = set()
    for profile_path in (None, "lnu"):
        runtime = audit_thesis.build_audit_runtime(profile_path)
        runtime_rule_ids.update(rule_id for rule_id, _, _ in runtime.rule_definitions)

    autofixable_rule_ids = {
        rule_id
        for rule_id in runtime_rule_ids
        if capabilities.get(rule_id, {}).get("autofix") == "✓"
    }

    assert autofixable_rule_ids, "No autofixable runtime rules found"

    for rule_id in autofixable_rule_ids:
        assert scope_for_rule(rule_id) is not None, f"{rule_id} is autofixable but not mapped to any scope"


def test_list_scoped_rule_ids_matches_scope_definitions_without_duplicates():
    expected_rule_ids = []
    for scope in list_scope_definitions():
        expected_rule_ids.extend(scope.rule_ids)

    assert list_scoped_rule_ids() == tuple(expected_rule_ids)
    assert len(set(list_scoped_rule_ids())) == len(list_scoped_rule_ids())
