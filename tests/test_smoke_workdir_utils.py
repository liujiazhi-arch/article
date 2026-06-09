from pathlib import Path

from smoke_workdir_utils import prepare_work_dir


def test_prepare_work_dir_removes_existing_contents_by_default(tmp_path):
    work_dir = tmp_path / "smoke"
    stale_file = work_dir / "old.txt"
    stale_file.parent.mkdir()
    stale_file.write_text("old", encoding="utf-8")

    result = prepare_work_dir(work_dir)

    assert result == work_dir
    assert work_dir.exists()
    assert not stale_file.exists()


def test_prepare_work_dir_keeps_existing_contents_when_requested(tmp_path):
    work_dir = tmp_path / "smoke"
    stale_file = work_dir / "old.txt"
    stale_file.parent.mkdir()
    stale_file.write_text("old", encoding="utf-8")

    result = prepare_work_dir(work_dir, keep_existing=True)

    assert result == work_dir
    assert stale_file.read_text(encoding="utf-8") == "old"


def test_prepare_work_dir_creates_missing_directory(tmp_path):
    work_dir = tmp_path / "missing"

    result = prepare_work_dir(work_dir)

    assert result == work_dir
    assert work_dir.is_dir()
