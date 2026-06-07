from __future__ import annotations

import sys
from pathlib import Path


_DISTRIBUTION_NAME = "thesis-format-tool"


def _candidate_config_dirs() -> list[Path]:
    module_dir = Path(__file__).resolve().parent
    candidates = [
        module_dir.parent / "config",
        module_dir / "share" / _DISTRIBUTION_NAME / "config",
        Path(sys.prefix) / "share" / _DISTRIBUTION_NAME / "config",
    ]
    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    if base_prefix != sys.prefix:
        candidates.append(Path(base_prefix) / "share" / _DISTRIBUTION_NAME / "config")
    return candidates


def config_dir() -> Path:
    for candidate in _candidate_config_dirs():
        if candidate.is_dir():
            return candidate
    return _candidate_config_dirs()[0]


def config_path(*parts: str) -> Path:
    return config_dir().joinpath(*parts)
