from __future__ import annotations

import importlib
import ast
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


PACKAGING_COMMAND_TIMEOUT_SECONDS = 120


def test_pytest_config_lives_only_in_pytest_ini():
    project_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_ini = (project_root / "pytest.ini").read_text(encoding="utf-8")

    assert pyproject.get("tool", {}).get("pytest") is None
    assert "[pytest]" in pytest_ini
    assert "testpaths = tests" in pytest_ini


def test_packaging_subprocesses_have_explicit_timeouts():
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    missing_timeouts = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        if node.func.value.id != "subprocess" or node.func.attr != "run":
            continue
        if not any(keyword.arg == "timeout" for keyword in node.keywords):
            missing_timeouts.append(node.lineno)

    assert missing_timeouts == []


def test_pyproject_declares_python_first_metadata():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    project = data["project"]
    assert project["name"] == "thesis-format-tool"
    assert project["requires-python"].startswith(">=")
    assert "python-docx>=1.1,<2" in project["dependencies"]
    assert "PyYAML>=6,<7" in project["dependencies"]
    assert "pypdfium2>=5,<6" in project["dependencies"]
    assert "Pillow>=11,<13" in project["dependencies"]
    assert "fastapi>=0.115,<1" in data["project"]["optional-dependencies"]["api"]
    assert "uvicorn>=0.30,<1" in data["project"]["optional-dependencies"]["api"]
    assert "python-multipart>=0.0.9,<1" in data["project"]["optional-dependencies"]["api"]
    assert "httpx>=0.27,<1" in data["project"]["optional-dependencies"]["dev"]


def test_pyproject_declares_expected_console_scripts():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert data["project"]["scripts"] == {
        "thesis-workbench": "thesis_workbench:main",
        "lnu-thesis-local": "article_api.local_app:main",
        "lnu-thesis-api": "article_api.local_app:serve_main",
        "lnu-thesis-doctor": "article_api.local_app:doctor_main",
        "lnu-thesis-backup": "article_api.local_app:backup_main",
        "lnu-thesis-feedback": "article_api.local_app:feedback_main",
        "lnu-thesis-restore": "article_api.local_app:restore_main",
        "lnu-thesis-maintain": "article_api.local_app:maintain_main",
        "article-local": "article_api.local_app:main",
        "article-api": "article_api.local_app:serve_main",
        "article-doctor": "article_api.local_app:doctor_main",
        "article-backup": "article_api.local_app:backup_main",
        "article-feedback": "article_api.local_app:feedback_main",
        "article-restore": "article_api.local_app:restore_main",
        "article-maintain": "article_api.local_app:maintain_main",
    }


def test_console_script_targets_resolve_to_callables():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    for script_name, target in data["project"]["scripts"].items():
        module_name, attr_name = target.split(":")
        module = importlib.import_module(module_name)
        target_obj = getattr(module, attr_name)
        assert callable(target_obj), f"{script_name} target must be callable"


def test_required_api_runtime_modules_are_tracked_by_git():
    project_root = Path(__file__).resolve().parents[1]
    required_paths = [
        "scripts/article_api/render_evidence.py",
    ]

    subprocess.run(
        ["git", "ls-files", "--error-unmatch", *required_paths],
        check=True,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )


def test_pyproject_packages_finalized_static_frontend_assets():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    package_data = data["tool"]["setuptools"].get("package-data", {})
    assert "article_api" in package_data
    assert "static/**/*.html" in package_data["article_api"]
    assert "static/**/*.css" in package_data["article_api"]
    assert "static/**/*.js" in package_data["article_api"]
    assert "static/assets/**" in package_data["article_api"]


def test_built_wheel_contains_runtime_modules_and_resources(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheelhouse"
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(project_root), "-w", str(wheel_dir), "--no-deps"],
        check=True,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )
    wheel_path = next(wheel_dir.glob("thesis_format_tool-*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())

    required_entries = {
        "audit_thesis.py",
        "fix_thesis.py",
        "thesis_workbench.py",
        "thesis_resources.py",
        "docx_sample_intake.py",
        "fetch_public_docx_samples.py",
        "release_smoke.py",
        "local_browser_smoke.py",
        "ooxml_namespaces.py",
        "github_release_status.py",
        "release_evidence_gate.py",
        "release_evidence_bundle.py",
        "verify_release_artifact.py",
        "build_windows_local_bundle.py",
        "windows_bundle_smoke.py",
        "windows_bundle_contract.py",
        "smoke_workdir_utils.py",
        "install_article_local.py",
        "backmatter_title_utils.py",
        "citation_text_utils.py",
        "cli_json_output.py",
        "file_hash_utils.py",
        "frontmatter_utils.py",
        "reference_numbering_utils.py",
        "reference_section_utils.py",
        "release_url_utils.py",
        "reorder_references_by_appearance.py",
        "text_spacing_utils.py",
        "thesis_rules/audit_common.py",
        "thesis_rules/audit_lnu.py",
        "thesis_rules/lnu_runtime.py",
        "thesis_fix/dependencies.py",
        "thesis_fix/lnu_postpasses.py",
        "thesis_fix/page_footer.py",
        "thesis_fix/tables_figures.py",
        "thesis_fix/toc.py",
        "thesis_tool/apply_guard.py",
        "thesis_tool/render_image_metrics.py",
        "thesis_tool/workflow_renderers.py",
        "article_api/local_feedback.py",
        "article_api/render_evidence.py",
        "article_api/job_retention.py",
        "article_api/retention_reports.py",
        "article_api/route_error_handlers.py",
    }
    assert required_entries <= names
    assert "article_api/local_console.html" not in names
    assert "article_api/assets/lnu-emblem.jpg" not in names
    assert "article_api/static/index.html" in names
    assert "article_api/static/styles/tokens.css" in names
    assert "article_api/static/js/app.js" in names

    required_resource_suffixes = {
        "config/profiles/lnu-checker-2026.yaml",
        "config/profiles/CN-Common.yaml",
        "config/capability_matrix.md",
        "config/templates/lnu/styles.xml",
        "config/templates/lnu/cover-assets/emblem.png",
        "config/templates/lnu/cover-assets/wordmark.jpeg",
    }
    for suffix in required_resource_suffixes:
        assert any(name.endswith(suffix) for name in names), suffix


def test_built_sdist_contains_runtime_modules_and_resources(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "build"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )
    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", str(dist_dir)],
        check=True,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )
    sdist_path = next(dist_dir.glob("thesis_format_tool-*.tar.gz"))

    with tarfile.open(sdist_path, "r:gz") as sdist:
        names = {Path(name).as_posix() for name in sdist.getnames()}

    required_suffixes = {
        "scripts/audit_thesis.py",
        "scripts/fix_thesis.py",
        "scripts/thesis_workbench.py",
        "scripts/thesis_resources.py",
        "scripts/docx_sample_intake.py",
        "scripts/fetch_public_docx_samples.py",
        "scripts/release_smoke.py",
        "scripts/local_browser_smoke.py",
        "scripts/ooxml_namespaces.py",
        "scripts/github_release_status.py",
        "scripts/release_evidence_gate.py",
        "scripts/release_evidence_bundle.py",
        "scripts/verify_release_artifact.py",
        "scripts/build_windows_local_bundle.py",
        "scripts/windows_bundle_smoke.py",
        "scripts/windows_bundle_contract.py",
        "scripts/smoke_workdir_utils.py",
        "scripts/install_article_local.py",
        "scripts/citation_text_utils.py",
        "scripts/cli_json_output.py",
        "scripts/file_hash_utils.py",
        "scripts/reference_numbering_utils.py",
        "scripts/release_url_utils.py",
        "scripts/text_spacing_utils.py",
        "scripts/thesis_rules/audit_lnu.py",
        "scripts/thesis_fix/toc.py",
        "scripts/thesis_tool/apply_guard.py",
        "scripts/thesis_tool/render_image_metrics.py",
        "scripts/thesis_tool/workflow_renderers.py",
        "scripts/article_api/local_feedback.py",
        "scripts/article_api/render_evidence.py",
        "scripts/article_api/job_retention.py",
        "scripts/article_api/retention_reports.py",
        "scripts/article_api/route_error_handlers.py",
        "config/profiles/lnu-checker-2026.yaml",
        "config/capability_matrix.md",
        "config/templates/lnu/styles.xml",
        "config/templates/lnu/cover-assets/emblem.png",
        "config/templates/lnu/cover-assets/wordmark.jpeg",
    }
    for suffix in required_suffixes:
        assert any(name.endswith(suffix) for name in names), suffix
    excluded_suffixes = {
        "scripts/article_api/local_console.html",
        "scripts/article_api/assets/lnu-emblem.jpg",
    }
    for suffix in excluded_suffixes:
        assert not any(name.endswith(suffix) for name in names), suffix
    required_static_suffixes = {
        "scripts/article_api/static/index.html",
        "scripts/article_api/static/styles/tokens.css",
        "scripts/article_api/static/js/app.js",
    }
    for suffix in required_static_suffixes:
        assert any(name.endswith(suffix) for name in names), suffix


def test_wheel_install_imports_entry_modules_from_outside_repo(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheelhouse"
    install_dir = tmp_path / "install"
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(project_root), "-w", str(wheel_dir), "--no-deps"],
        check=True,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )
    wheel_path = next(wheel_dir.glob("thesis_format_tool-*.whl"))
    subprocess.run(
        [sys.executable, "-m", "pip", "install", str(wheel_path), "--target", str(install_dir), "--no-deps"],
        check=True,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )

    import_script = """
import importlib
from pathlib import Path
from _profile_utils import DEFAULT_PROFILE_ID, list_public_profile_catalog
from thesis_resources import config_path
from thesis_tool.capabilities import load_rule_capabilities

for name in (
    "audit_thesis",
    "fix_thesis",
    "thesis_workbench",
    "article_api.local_app",
    "article_api.local_feedback",
    "article_api.render_evidence",
    "article_api.job_retention",
    "article_api.retention_reports",
    "article_api.route_error_handlers",
    "citation_text_utils",
    "cli_json_output",
    "file_hash_utils",
    "reference_numbering_utils",
    "release_url_utils",
    "text_spacing_utils",
    "thesis_tool.render_analyzer",
    "thesis_tool.render_image_metrics",
    "thesis_tool.workflow_renderers",
    "docx_sample_intake",
    "fetch_public_docx_samples",
    "release_smoke",
    "local_browser_smoke",
    "ooxml_namespaces",
    "github_release_status",
    "release_evidence_gate",
    "release_evidence_bundle",
    "build_windows_local_bundle",
    "windows_bundle_smoke",
    "windows_bundle_contract",
    "smoke_workdir_utils",
    "install_article_local",
):
    importlib.import_module(name)

profiles = list_public_profile_catalog()
assert DEFAULT_PROFILE_ID == "lnu-checker-2026"
assert [profile["id"] for profile in profiles] == ["lnu-checker-2026"]
assert len(load_rule_capabilities()) == 77
assert Path(config_path("templates", "lnu", "cover-assets", "emblem.png")).is_file()
assert Path(config_path("templates", "lnu", "cover-assets", "wordmark.jpeg")).is_file()
"""
    subprocess.run(
        [sys.executable, "-c", import_script],
        check=True,
        cwd=tmp_path,
        env={"PYTHONPATH": str(install_dir)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=PACKAGING_COMMAND_TIMEOUT_SECONDS,
    )
