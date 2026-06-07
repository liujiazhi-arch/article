from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _path_exists_relative(path: str) -> bool:
    return (PROJECT_ROOT / path).exists()


def test_readme_declares_single_document_product_boundary():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    for keyword in (
        "单文档",
        "audit",
        "plan",
        "preflight",
        "normalize",
        "apply",
        "verify",
        "render-verify",
        "article-local",
        "article-api",
        "article-doctor",
        "article-backup",
        "article-feedback",
        "article-restore",
        "article-maintain",
    ):
        assert keyword in readme

    for forbidden in (
        "批量任务",
        "article-local batch",
        "/jobs/batch",
    ):
        assert forbidden not in readme


def test_repo_root_does_not_track_boundary_external_output_indexes():
    tracked = _git_lines("ls-files", "outputs")
    deleted = set(_git_lines("ls-files", "--deleted", "outputs"))
    live_tracked = [path for path in tracked if path not in deleted and _path_exists_relative(path)]
    assert live_tracked == []


def test_requirements_txt_is_removed_in_favor_of_pyproject_install():
    assert not (PROJECT_ROOT / "requirements.txt").exists()


def test_packaging_scripts_match_current_product_boundary():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    for script_name in (
        'thesis-workbench = "thesis_workbench:main"',
        'article-local = "article_api.local_app:main"',
        'article-api = "article_api.local_app:serve_main"',
        'article-doctor = "article_api.local_app:doctor_main"',
        'article-backup = "article_api.local_app:backup_main"',
        'article-feedback = "article_api.local_app:feedback_main"',
        'article-restore = "article_api.local_app:restore_main"',
        'article-maintain = "article_api.local_app:maintain_main"',
    ):
        assert script_name in pyproject

    assert "batch" not in pyproject


def test_default_output_naming_uses_versioned_single_document_labels():
    from article_api.output_naming import (
        DEFAULT_INTERMEDIATE_OUTPUT_DIR,
        DEFAULT_OUTPUT_DIR,
        FORMAT_FIX_SUFFIX,
        NORMALIZE_SUFFIX,
        clean_versioned_stem,
        normalize_output_path,
        scoped_output_path,
    )

    assert clean_versioned_stem("demo_格式修复_v01.docx") == "demo"
    assert FORMAT_FIX_SUFFIX == "格式修复"
    assert NORMALIZE_SUFFIX == "结构整理"
    assert Path(
        scoped_output_path(
            source_file_path="/tmp/demo.docx",
            scopes=["headings"],
            source_display_name="demo.docx",
        )
    ).parent == DEFAULT_OUTPUT_DIR
    normalize_path = Path(
        normalize_output_path(
            source_file_path="/tmp/demo.docx",
            source_display_name="demo.docx",
        )
    )
    assert normalize_path.parent == DEFAULT_INTERMEDIATE_OUTPUT_DIR
    assert normalize_path.parent != DEFAULT_OUTPUT_DIR
