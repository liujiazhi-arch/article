from __future__ import annotations

from pathlib import Path
from secrets import token_urlsafe
from threading import Lock
from typing import Any


_LOCK = Lock()
_SCREENSHOT_PATHS_BY_TOKEN: dict[str, str] = {}


def _valid_png_path(path_value: Any) -> str | None:
    if not path_value:
        return None
    path = Path(str(path_value)).expanduser().resolve()
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".png":
        return None
    return str(path)


def register_render_evidence_screenshots(payload: dict[str, Any]) -> dict[str, Any]:
    evidence_items = payload.get("evidence_items")
    if not isinstance(evidence_items, list):
        return payload

    registered_items: list[Any] = []
    with _LOCK:
        for item in evidence_items:
            if not isinstance(item, dict):
                registered_items.append(item)
                continue
            registered_item = dict(item)
            screenshot_path = _valid_png_path(registered_item.get("screenshot_path"))
            if screenshot_path:
                token = token_urlsafe(24)
                _SCREENSHOT_PATHS_BY_TOKEN[token] = screenshot_path
                registered_item["screenshot_path"] = screenshot_path
                registered_item["screenshot_url"] = f"/render-evidence/screenshot/{token}"
            else:
                registered_item.pop("screenshot_url", None)
            registered_items.append(registered_item)
    payload["evidence_items"] = registered_items
    return payload


def resolve_render_evidence_screenshot(token: str) -> str:
    with _LOCK:
        path_value = _SCREENSHOT_PATHS_BY_TOKEN.get(str(token or ""))
    screenshot_path = _valid_png_path(path_value)
    if screenshot_path is None:
        raise LookupError("Render evidence screenshot token is unavailable.")
    return screenshot_path
