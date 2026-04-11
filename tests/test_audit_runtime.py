import json
import re
from pathlib import Path

import audit_thesis
import fix_thesis
import yaml
from docx import Document
from _profile_utils import PROFILE_ALIASES
from thesis_tool.capabilities import load_rule_capabilities


def _write_profile(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "custom-profile.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_build_audit_runtime_keeps_profile_rules_isolated():
    default_runtime = audit_thesis.build_audit_runtime()
    lnu_runtime = audit_thesis.build_audit_runtime("lnu")
    fresh_default_runtime = audit_thesis.build_audit_runtime()

    default_rule_ids = {rule_id for rule_id, _, _ in default_runtime.rule_definitions}
    lnu_rule_ids = {rule_id for rule_id, _, _ in lnu_runtime.rule_definitions}
    fresh_default_rule_ids = {rule_id for rule_id, _, _ in fresh_default_runtime.rule_definitions}

    assert "LNU_ABS01" not in default_rule_ids
    assert "LNU_ABS01" in lnu_rule_ids
    assert "LNU_ABS01" not in fresh_default_rule_ids
    assert "LNU_ACK01" not in default_rule_ids
    assert "LNU_ACK01" in lnu_rule_ids
    assert "LNU_ACK01" not in fresh_default_rule_ids


def test_build_audit_runtime_applies_disabled_rules_without_global_mutation(tmp_path):
    profile_path = _write_profile(
        tmp_path,
        """
meta:
  id: cn-common
disabled_rules:
  - T01
  - H02
""".strip(),
    )

    custom_runtime = audit_thesis.build_audit_runtime(str(profile_path))
    fresh_default_runtime = audit_thesis.build_audit_runtime()

    custom_rule_ids = {rule_id for rule_id, _, _ in custom_runtime.rule_definitions}
    default_rule_ids = {rule_id for rule_id, _, _ in fresh_default_runtime.rule_definitions}

    assert "T01" not in custom_rule_ids
    assert "H02" not in custom_rule_ids
    assert "T01" in default_rule_ids
    assert "H02" in default_rule_ids


def test_fix_runtime_applies_per_side_margin_settings(tmp_path):
    profile_path = _write_profile(
        tmp_path,
        """
meta:
  id: cn-common
settings:
  margin_top: 1701
  margin_bottom: 1418
  margin_left: 1701
  margin_right: 1418
""".strip(),
    )
    source_path = tmp_path / "margin_source.docx"
    Document().save(source_path)
    fixed_path = tmp_path / "margin_fixed.docx"

    fix_thesis.fix_docx(str(source_path), str(fixed_path), profile_path=str(profile_path), scopes=["page"])

    fixed_doc = Document(fixed_path)
    section = fixed_doc.sections[0]
    assert section.top_margin.twips == 1701
    assert section.bottom_margin.twips == 1418
    assert section.left_margin.twips == 1701
    assert section.right_margin.twips == 1418


def test_audit_and_fix_runtime_share_profile_resolution_for_alias_and_path():
    profile_path = PROFILE_ALIASES["lnu"]

    audit_runtime = audit_thesis.build_audit_runtime(profile_path)
    alias_fix_runtime = fix_thesis.build_fix_runtime("lnu")
    path_fix_runtime = fix_thesis.build_fix_runtime(profile_path)

    assert audit_runtime.profile_id == "lnu-undergraduate"
    assert alias_fix_runtime.profile_id == audit_runtime.profile_id
    assert path_fix_runtime.profile_id == audit_runtime.profile_id
    assert alias_fix_runtime.cfg["body_font"] == path_fix_runtime.cfg["body_font"]
    assert alias_fix_runtime.template_profile_id == "lnu"
    assert path_fix_runtime.template_profile_id == "lnu"


def test_lnu_profile_cfg_matches_20250608_source_sample():
    audit_runtime = audit_thesis.build_audit_runtime("lnu")
    fix_runtime = fix_thesis.build_fix_runtime("lnu")

    for runtime in (audit_runtime, fix_runtime):
        cfg = runtime.cfg
        assert cfg["margin_fix"] == 1418
        assert cfg["margin_gutter"] == 283
        assert cfg["body_font"] == "宋体"
        assert cfg["body_ascii_font"] == "Times New Roman"
        assert cfg["body_size"] == 24
        assert cfg["body_line"] == 360
        assert cfg["body_indent"] == 480
        assert cfg["h1_size"] == 32
        assert cfg["h2_size"] == 28
        assert cfg["h3_size"] == 24
        assert cfg["h4_size"] == 24
        assert cfg["h4_font"] == "宋体"
        assert cfg["kw_min"] == 3
        assert cfg["kw_max"] == 5
        assert cfg["kw_font"] == "黑体"
        assert cfg["kw_bold"] is False
        assert cfg["kw_half_points"] == 24
        assert cfg["abstract_title_font"] == "黑体"
        assert cfg["abstract_title_size"] == 32
        assert cfg["abstract_title_line"] == 360
        assert cfg["abstract_title_after_pt"] == 0
        assert cfg["abstract_en_title_font"] == "Times New Roman"
        assert cfg["abstract_en_title_size"] == 32
        assert cfg["abstract_en_body_font"] == "Times New Roman"
        assert cfg["abstract_en_body_size"] == 24
        assert cfg["abstract_en_body_line"] == 240
        assert cfg["caption_number_sep"] == "."
        assert cfg["eq_number_sep"] == "."
        assert cfg["ref_hanging"] == 420
        assert cfg["ref_use_tab"] is False
        assert cfg["ref_font_size"] == 21
        assert cfg["ref_line_spacing"] == 360
        assert cfg["ref_terminal_punct"] == "."
        assert cfg["pg01_format"] == "em_dash"
        assert cfg["check_snap_to_grid"] is True


def test_capability_matrix_matches_current_audit_runtime_rules():
    capabilities = load_rule_capabilities()
    default_rule_ids = {rule_id for rule_id, _, _ in audit_thesis.build_audit_runtime().rule_definitions}
    lnu_rule_ids = {rule_id for rule_id, _, _ in audit_thesis.build_audit_runtime("lnu").rule_definitions}
    runtime_rule_ids = default_rule_ids | lnu_rule_ids

    missing = sorted(rule_id for rule_id in runtime_rule_ids if rule_id not in capabilities)
    extra = sorted(rule_id for rule_id in capabilities if rule_id not in runtime_rule_ids)

    assert missing == []
    assert extra == []


def test_lnu_profile_active_additions_match_runtime_extensions():
    profile_path = Path(PROFILE_ALIASES["lnu"])
    profile_data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))

    default_rule_ids = {rule_id for rule_id, _, _ in audit_thesis.build_audit_runtime().rule_definitions}
    lnu_rule_ids = {rule_id for rule_id, _, _ in audit_thesis.build_audit_runtime("lnu").rule_definitions}
    runtime_lnu_extensions = {rule_id for rule_id in lnu_rule_ids - default_rule_ids if rule_id.startswith("LNU_")}
    profile_lnu_extensions = {item["id"] for item in profile_data.get("additions") or []}

    assert profile_lnu_extensions == runtime_lnu_extensions


def test_ams_profile_marks_unimplemented_rules_as_reference_only():
    profile_path = Path(PROFILE_ALIASES["ams"])
    profile_data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    runtime = audit_thesis.build_audit_runtime("ams")
    runtime_rule_ids = {rule_id for rule_id, _, _ in runtime.rule_definitions}

    assert "reference_additions" in profile_data
    assert "additions" not in profile_data
    assert "AMS01" not in runtime_rule_ids
    assert runtime.cfg["h1_bold"] is True
    assert runtime.cfg["h2_bold"] is True
    assert runtime.cfg["h3_bold"] is True
    assert runtime.cfg["h3_font"] == "宋体"
    assert runtime.cfg["ref_font_size"] == 21


def test_package_json_only_exposes_current_python_workflow_scripts():
    package_path = Path(__file__).resolve().parents[1] / "package.json"
    package_data = json.loads(package_path.read_text(encoding="utf-8"))
    scripts = package_data["scripts"]

    assert sorted(scripts) == ["apply", "audit", "plan", "scopes", "test", "verify"]
    assert not any("preview" in value for value in scripts.values())


def test_validate_docx_path_rejects_legacy_doc_input(tmp_path):
    legacy_doc = tmp_path / "legacy.doc"
    legacy_doc.write_text("not-a-docx", encoding="utf-8")

    try:
        audit_thesis.validate_docx_path(str(legacy_doc))
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError for legacy .doc input")

    assert ".docx" in message
    assert ".doc" in message


def test_build_audit_runtime_strict_profile_raises_on_invalid_path():
    try:
        audit_thesis.build_audit_runtime("missing-profile.yaml", strict_profile=True)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected strict profile resolution to fail")

    assert "Profile 加载失败" in message
    assert "missing-profile.yaml" in message


def test_runtime_rule_counts_match_readme_and_claude_docs():
    project_root = Path(__file__).resolve().parents[1]
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    claude = (project_root / "CLAUDE.md").read_text(encoding="utf-8")

    actual_counts = {
        "cn-common": len(audit_thesis.build_audit_runtime().rule_definitions),
        "lnu-undergraduate": len(audit_thesis.build_audit_runtime("lnu").rule_definitions),
    }

    for label, text in {"README": readme, "CLAUDE": claude}.items():
        for profile_id, expected in actual_counts.items():
            match = re.search(rf"`{re.escape(profile_id)}`\s+(?:当前\s+)?runtime[:：]\s*(\d+)\s*条", text)
            assert match, f"{label} missing runtime count for {profile_id}"
            assert int(match.group(1)) == expected, f"{label} runtime count drift for {profile_id}"
