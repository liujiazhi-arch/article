from __future__ import annotations


_DEPS: dict[str, object] = {}


def configure(deps: dict[str, object]) -> None:
    _DEPS.update(deps)


def require(*names: str) -> tuple[object, ...]:
    missing = [name for name in names if name not in _DEPS]
    if missing:
        raise RuntimeError(f"thesis_fix dependencies are not configured: {', '.join(missing)}")
    return tuple(_DEPS[name] for name in names)
