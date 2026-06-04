from __future__ import annotations

import importlib
import tomllib
from pathlib import Path


def test_pyproject_declares_python_first_metadata():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    project = data["project"]
    assert project["name"] == "thesis-format-tool"
    assert project["requires-python"].startswith(">=")
    assert "python-docx>=1.1,<2" in project["dependencies"]
    assert "PyYAML>=6,<7" in project["dependencies"]
    assert "fastapi>=0.115,<1" in data["project"]["optional-dependencies"]["api"]
    assert "uvicorn>=0.30,<1" in data["project"]["optional-dependencies"]["api"]
    assert "python-multipart>=0.0.9,<1" in data["project"]["optional-dependencies"]["api"]
    assert "httpx>=0.27,<1" in data["project"]["optional-dependencies"]["dev"]


def test_pyproject_declares_expected_console_scripts():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert data["project"]["scripts"] == {
        "thesis-workbench": "thesis_workbench:main",
        "article-local": "article_api.local_app:main",
        "article-api": "article_api.local_app:serve_main",
        "article-doctor": "article_api.local_app:doctor_main",
        "article-backup": "article_api.local_app:backup_main",
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


def test_pyproject_includes_local_console_asset():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert data["tool"]["setuptools"]["package-data"]["article_api"] == [
        "local_console.html",
        "assets/lnu-emblem.jpg",
    ]


def test_local_console_includes_apple_style_motion_hooks():
    html_path = Path(__file__).resolve().parents[1] / "scripts" / "article_api" / "local_console.html"
    html = html_path.read_text(encoding="utf-8")

    required_fragments = [
        "prefers-reduced-motion: reduce",
        "IntersectionObserver",
        "initAppleMotion",
        "motion-reveal",
        "topbar compact",
        "report-updated",
        "upload-active",
        "step-pulse",
    ]
    for fragment in required_fragments:
        assert fragment in html
