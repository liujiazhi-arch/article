from __future__ import annotations

from typing import Callable, TypeVar


T = TypeVar("T")


def call_with_http_error(action: Callable[[], T], raise_http_error: Callable[[Exception], None]) -> T:
    try:
        return action()
    except Exception as exc:
        raise_http_error(exc)
        raise
