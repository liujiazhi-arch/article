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


def _live_tracked_paths(*paths: str) -> list[str]:
    tracked = _git_lines("ls-files", *paths)
    deleted = set(_git_lines("ls-files", "--deleted", *paths))
    return [path for path in tracked if path not in deleted and (PROJECT_ROOT / path).exists()]


def test_gitignore_keeps_runtime_artifacts_out_of_source_control():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        ".article_runtime/",
        ".tmp_render_probe_out/",
        ".tmp_render_artifact/",
        ".tmp_render_verify_live/",
        "runs/",
        "output/",
        "build/",
        "dist/",
        "*.egg-info/",
    ):
        assert pattern in gitignore


def test_outputs_directory_is_fully_ignored():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "outputs/" in gitignore


def test_runtime_only_directories_have_no_tracked_files():
    tracked = _live_tracked_paths("runs", "output", ".article_runtime", ".tmp_render_probe_out", "outputs")
    assert tracked == []


def test_agents_rtk_reference_resolves():
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "@RTK.md" not in agents or (PROJECT_ROOT / "RTK.md").exists()
