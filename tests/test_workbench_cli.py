from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

from docx import Document
import pytest

from .conftest import RULE_MUTATORS, SCRIPTS_DIR, audit_rule_status, make_compliant_doc


_RENDER_DOCX_SCRIPT_READY = bool(
    glob.glob(os.path.expanduser("~/.codex/plugins/cache/openai-primary-runtime/documents/*/skills/documents/render_docx.py"))
)


def _make_high_risk_lnu_doc(source_path: Path) -> Path:
    doc = Document()
    heading = doc.add_paragraph("1 绪论")
    heading.style = doc.styles["Heading 1"]
    doc.add_paragraph("这是正文示例。")
    table = doc.add_table(rows=5, cols=1)
    values = [
        "1,4-Diaminobutane",
        "2-Amino-2-Deoxy-D-Glucopyranose",
        "2.80E+08",
        "3.20E+01",
        "2.79E+08",
    ]
    for row, value in zip(table.rows, values):
        row.cells[0].text = value
    doc.save(source_path)
    return source_path


def _make_style_conflict_lnu_doc(source_path: Path) -> Path:
    doc = Document()
    heading = doc.add_paragraph("1 绪论")
    heading.style = doc.styles["Heading 1"]
    conflict = doc.add_paragraph("3.6 分子对接验证结果")
    conflict.style = doc.styles["Heading 1"]
    doc.add_paragraph("这是正文示例。")
    doc.save(source_path)
    return source_path


def _make_lnu_f05_fail_doc(source_path: Path) -> Path:
    doc = Document()
    heading = doc.add_paragraph("第一章 绪论")
    heading.style = doc.styles["Heading 1"]
    doc.add_paragraph("本节介绍实验装置。")
    doc.add_paragraph("图1.1 实验装置示意图")
    doc.save(source_path)
    return source_path


def test_workbench_apply_cli_repairs_only_selected_scope(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_source.docx")
    doc = Document(source_path)
    RULE_MUTATORS["H02"](doc)
    RULE_MUTATORS["T01"](doc)
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "workbench_cli_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "cn-common",
            "--scope",
            "headings",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"输出文件: {fixed_path}" in result.stdout
    assert "复查范围: headings" in result.stdout
    assert "Profile: cn-common" in result.stdout

    after_h02 = audit_rule_status(fixed_path, "H02")
    after_t01 = audit_rule_status(fixed_path, "T01")
    assert after_h02["rule"]["passed"], after_h02["rule"]["issues"]
    assert not after_t01["rule"]["passed"]


def test_workbench_apply_cli_rejects_doc_input(tmp_path):
    doc_path = tmp_path / "not_supported.doc"
    doc_path.write_text("placeholder", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(doc_path),
            "--scope",
            "headings",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "仅支持 .docx 文件" in result.stderr
    assert str(doc_path) in result.stderr


def test_workbench_profiles_lists_expected_profiles():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "profiles",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "cn-common" in result.stdout
    assert "lnu-checker-2026" in result.stdout
    assert "lnu-undergraduate" not in result.stdout
    assert "support=一等支持" in result.stdout
    assert "课程作业/基础论文[课程作业、基础论文]/一等支持" in result.stdout
    assert "学校学位论文[本科毕业论文]/一等支持" in result.stdout


def test_workbench_apply_cli_supports_dry_run_without_writing_output(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_dry_run_source.docx")
    fixed_path = Path(tmp_path) / "workbench_cli_dry_run_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "cn-common",
            "--scope",
            "headings",
            "--output",
            str(fixed_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "dry-run: 是" in result.stdout
    assert "修复范围: headings" in result.stdout
    assert not fixed_path.exists()


def test_workbench_apply_cli_can_opt_in_to_heading_renumber(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_renumber_source.docx")
    doc = Document(source_path)
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith("第一章"):
            paragraph.runs[0].text = "0 引言"
        elif paragraph.text.startswith("1.1 研究背景"):
            paragraph.runs[0].text = "0.1 研究背景"
        elif paragraph.text.startswith("1.1.1 研究现状"):
            paragraph.runs[0].text = "0.1.1 研究现状"
    doc.save(source_path)

    fixed_path = Path(tmp_path) / "workbench_cli_renumber_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "cn-common",
            "--scope",
            "headings",
            "--renumber-headings",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    fixed_doc = Document(fixed_path)
    texts = [paragraph.text for paragraph in fixed_doc.paragraphs]
    assert "1 引言" in texts
    assert "1.1 研究背景" in texts
    assert "1.1.1 研究现状" in texts


def test_workbench_apply_cli_prints_toc_refresh_note(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_toc_source.docx")
    fixed_path = Path(tmp_path) / "workbench_cli_toc_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "lnu",
            "--scope",
            "toc",
            "--toc",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert fixed_path.exists()
    assert "Ctrl+A" in result.stdout
    assert "F9" in result.stdout


def test_workbench_apply_cli_warns_but_does_not_block_table_risk_only_heading_renumber(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_guard_source.docx")
    _make_high_risk_lnu_doc(Path(source_path))
    fixed_path = Path(tmp_path) / "workbench_cli_guard_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "lnu",
            "--scope",
            "headings",
            "--renumber-headings",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "[警告]" in result.stdout
    assert "表格伪标题候选" in result.stdout
    assert fixed_path.exists()


def test_workbench_apply_cli_blocks_style_conflict_heading_renumber_without_force(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_guard_conflict_source.docx")
    _make_style_conflict_lnu_doc(Path(source_path))
    fixed_path = Path(tmp_path) / "workbench_cli_guard_conflict_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "lnu",
            "--scope",
            "headings",
            "--renumber-headings",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[警告]" in result.stdout
    assert "样式/文本层级冲突" in result.stdout
    assert "--force" in result.stdout
    assert not fixed_path.exists()


def test_workbench_apply_cli_allows_force_on_style_conflict_heading_renumber(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_guard_force_source.docx")
    _make_style_conflict_lnu_doc(Path(source_path))
    fixed_path = Path(tmp_path) / "workbench_cli_guard_force_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "lnu",
            "--scope",
            "headings",
            "--renumber-headings",
            "--force",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert fixed_path.exists()


def test_workbench_apply_cli_warns_but_does_not_block_unrelated_scope(tmp_docx, tmp_path):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_guard_unrelated_scope_source.docx")
    _make_high_risk_lnu_doc(Path(source_path))
    fixed_path = Path(tmp_path) / "workbench_cli_guard_unrelated_scope_fixed.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "apply",
            str(source_path),
            "--profile",
            "lnu",
            "--scope",
            "toc",
            "--toc",
            "--output",
            str(fixed_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "[警告]" in result.stdout
    assert fixed_path.exists()
    assert "Ctrl+A" in result.stdout


def test_workbench_diagnose_cli_prints_diagnostic_sections(tmp_docx):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_diagnose_source.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "diagnose",
            str(source_path),
            "--profile",
            "lnu",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "目录状态:" in result.stdout
    assert "正文标题链：" in result.stdout
    assert "表格内伪标题候选：" in result.stdout
    assert "样式/文本层级冲突：" in result.stdout
    assert "建议动作：" in result.stdout


def test_workbench_diagnose_cli_supports_compact_output(tmp_docx):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_diagnose_compact_source.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "diagnose",
            str(source_path),
            "--profile",
            "lnu",
            "--compact",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "file=workbench_cli_diagnose_compact_source.docx" in result.stdout
    assert "toc_status=" in result.stdout
    assert "preface_status=" in result.stdout
    assert "heading_renumber_guard_status=" in result.stdout
    assert "heading_renumber_guard_reason=" in result.stdout
    assert "recommended_action_count=" in result.stdout


def test_workbench_preflight_cli_reports_user_facing_status(tmp_path):
    source_path = _make_style_conflict_lnu_doc(Path(tmp_path) / "workbench_cli_preflight_blocked.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "preflight",
            str(source_path),
            "--profile",
            "lnu",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "预检状态: blocked" in result.stdout
    assert "建议动作：" in result.stdout


def test_workbench_preflight_cli_supports_compact_output(tmp_path):
    source_path = _make_high_risk_lnu_doc(Path(tmp_path) / "workbench_cli_preflight_compact.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "preflight",
            str(source_path),
            "--profile",
            "lnu",
            "--compact",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "file=workbench_cli_preflight_compact.docx" in result.stdout
    assert "preflight_status=warning" in result.stdout
    assert "heading_renumber_guard_status=warn" in result.stdout


def test_workbench_normalize_cli_reports_preflight_delta(tmp_path):
    source_path = _make_style_conflict_lnu_doc(Path(tmp_path) / "workbench_cli_normalize.docx")
    output_path = Path(tmp_path) / "workbench_cli_normalized.docx"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "normalize",
            str(source_path),
            "--profile",
            "lnu",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.exists()
    assert "输出文件:" in result.stdout
    assert "预规整改动: 有" in result.stdout
    assert "预检变化: blocked -> warning" in result.stdout


def test_workbench_normalize_cli_supports_compact_output(tmp_path):
    source_path = _make_style_conflict_lnu_doc(Path(tmp_path) / "workbench_cli_normalize_compact.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "normalize",
            str(source_path),
            "--profile",
            "lnu",
            "--compact",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "file=workbench_cli_normalize_compact.docx" in result.stdout
    assert "before_preflight_status=blocked" in result.stdout
    assert "after_preflight_status=warning" in result.stdout


@pytest.mark.skipif(not _RENDER_DOCX_SCRIPT_READY, reason="requires bundled render_docx.py")
def test_workbench_render_verify_cli_writes_page_proof(tmp_path):
    source_path = Path(tmp_path) / "workbench_cli_render_verify.docx"
    doc = Document()
    doc.add_heading("Render Verify", level=1)
    doc.add_paragraph("This is a render verification probe.")
    doc.save(source_path)
    output_dir = Path(tmp_path) / "render-proof"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "render-verify",
            str(source_path),
            "--profile",
            "lnu",
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "渲染证据目录:" in result.stdout
    assert "生成页图:" in result.stdout
    assert (output_dir / "page-1.png").exists()
    assert (output_dir / "render_verify_report.json").exists()


def test_workbench_verify_cli_highlights_manual_review_rules(tmp_path):
    source_path = _make_lnu_f05_fail_doc(Path(tmp_path) / "workbench_cli_verify_lnu_f05.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "verify",
            str(source_path),
            "--profile",
            "lnu",
            "--scope",
            "figures",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "可提交状态: manual-review-required" in result.stdout
    assert "仍需人工复核：" in result.stdout
    assert "LNU_F05" in result.stdout
    assert "[提示] 当前结果仍含人工复核项" in result.stdout


def test_workbench_audit_cli_prints_effective_profile(tmp_docx):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_audit_profile_source.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "audit",
            str(source_path),
            "--profile",
            "lnu",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Profile: lnu-checker-2026 (requested: lnu)" in result.stdout


def test_workbench_audit_cli_supports_strict_profile(tmp_docx):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_audit_strict_profile_source.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "audit",
            str(source_path),
            "--profile",
            "missing-profile.yaml",
            "--strict-profile",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Profile 加载失败" in result.stderr


def test_workbench_audit_cli_defaults_to_strict_profile_for_explicit_profile(tmp_docx):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_audit_default_strict_source.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "audit",
            str(source_path),
            "--profile",
            "missing-profile.yaml",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Profile 加载失败" in result.stderr


def test_workbench_audit_cli_can_allow_profile_fallback(tmp_docx):
    source_path = tmp_docx(make_compliant_doc, filename="workbench_cli_audit_allow_fallback_source.docx")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "thesis_workbench.py"),
            "audit",
            str(source_path),
            "--profile",
            "missing-profile.yaml",
            "--allow-profile-fallback",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Profile: cn-common (requested: missing-profile.yaml; fallback: cn-common)" in result.stdout
