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


def test_outputs_metadata_whitelist_stays_trackable():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "outputs/**",
        "!outputs/.gitkeep",
        "!outputs/README.md",
        "!outputs/index/",
        "!outputs/index/**",
        "!outputs/milestones/",
        "!outputs/milestones/**",
    ):
        assert pattern in gitignore


def test_runtime_only_directories_have_no_tracked_files():
    tracked = _git_lines("ls-files", "runs", "output", ".article_runtime", ".tmp_render_probe_out")
    assert tracked == []


def test_agents_rtk_reference_resolves():
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "@RTK.md" not in agents or (PROJECT_ROOT / "RTK.md").exists()
