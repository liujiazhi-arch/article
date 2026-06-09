from __future__ import annotations

from pathlib import Path
import shutil


def prepare_work_dir(work_dir: str | Path, *, keep_existing: bool = False) -> Path:
    resolved = Path(work_dir)
    if resolved.exists() and not keep_existing:
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
