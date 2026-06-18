from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock
from typing import Any

from article_api import storage


_LOCK = RLock()
_SCREENSHOT_PATHS_BY_TOKEN: dict[str, str] = {}
_TOKEN_VERSION = "v1"
_SECRET_FILE_NAME = "render_evidence.secret"


def _valid_png_path(path_value: Any) -> str | None:
    if not path_value:
        return None
    path = Path(str(path_value)).expanduser().resolve()
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".png":
        return None
    return str(path)


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _token_secret() -> bytes:
    secret_path = storage.resolve_state_root() / _SECRET_FILE_NAME
    with _LOCK:
        if not secret_path.exists():
            secret_path.write_text(token_urlsafe(32), encoding="utf-8")
        return secret_path.read_text(encoding="utf-8").strip().encode("utf-8")


def _signed_token_for_path(screenshot_path: str) -> str:
    payload = json.dumps({"path": screenshot_path}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_part = _urlsafe_b64encode(payload)
    signature = hmac.new(_token_secret(), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{_TOKEN_VERSION}.{payload_part}.{_urlsafe_b64encode(signature)}"


def _path_from_signed_token(token: str) -> str | None:
    parts = str(token or "").split(".")
    if len(parts) != 3 or parts[0] != _TOKEN_VERSION:
        return None
    payload_part = parts[1]
    expected_signature = hmac.new(_token_secret(), payload_part.encode("ascii"), hashlib.sha256).digest()
    try:
        actual_signature = _urlsafe_b64decode(parts[2])
    except Exception:
        return None
    if not hmac.compare_digest(actual_signature, expected_signature):
        return None
    try:
        payload = json.loads(_urlsafe_b64decode(payload_part).decode("utf-8"))
    except Exception:
        return None
    path_value = payload.get("path") if isinstance(payload, dict) else None
    return str(path_value) if path_value else None


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
                token = _signed_token_for_path(screenshot_path)
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
    if path_value is None:
        path_value = _path_from_signed_token(token)
    screenshot_path = _valid_png_path(path_value)
    if screenshot_path is None:
        raise LookupError("Render evidence screenshot token is unavailable.")
    return screenshot_path
