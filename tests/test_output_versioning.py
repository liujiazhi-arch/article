from datetime import datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import output_versioning  # noqa: E402


def test_render_manifest_includes_entries():
    entries = [
        output_versioning.OutputEntry(
            rel_path="outputs/example.docx",
            size_bytes=2048,
            modified_at=datetime(2026, 4, 10, 12, 0, 0),
        )
    ]

    content = output_versioning.render_manifest(
        entries,
        generated_at=datetime(2026, 4, 10, 12, 30, 0),
    )

    assert "最新产物索引" in content
    assert "outputs/example.docx" in content
    assert "2.0 KB" in content
    assert "2026-04-10 12:00:00" in content


def test_collect_output_entries_skips_control_dirs(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    (outputs_dir / "index").mkdir()
    (outputs_dir / "milestones").mkdir()
    (outputs_dir / ".DS_Store").write_text("", encoding="utf-8")
    (outputs_dir / "draft.docx").write_text("x", encoding="utf-8")
    (outputs_dir / "index" / "ignored.md").write_text("x", encoding="utf-8")

    entries = output_versioning.collect_output_entries(outputs_dir=outputs_dir)

    assert [entry.rel_path for entry in entries] == ["outputs/draft.docx"]
