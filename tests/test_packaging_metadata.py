from __future__ import annotations

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
    assert data["project"]["scripts"]["thesis-workbench"] == "thesis_workbench:main"
