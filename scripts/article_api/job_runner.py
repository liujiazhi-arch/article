from __future__ import annotations

import json
import sys
from typing import Any

from article_engine import apply_fix, normalize_document, render_verify_document, verify_document


_JOB_HANDLERS = {
    "apply": apply_fix,
    "normalize": normalize_document,
    "render-verify": render_verify_document,
    "verify": verify_document,
}


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ValueError):
        http_status = 400
        code = "validation_error"
    elif isinstance(exc, RuntimeError):
        http_status = 409
        code = "runtime_conflict"
    else:
        http_status = 500
        code = "internal_error"
    message = str(exc)
    if isinstance(exc, RuntimeError) and "Apply blocked by structural risk" in message:
        code = "apply_guard_blocked"
    payload = {
        "code": code,
        "type": exc.__class__.__name__,
        "message": message,
        "http_status": http_status,
    }
    guard = getattr(exc, "guard", None)
    if guard is not None:
        payload["guard"] = guard
    return payload


def run_request(payload: dict[str, Any]) -> dict[str, Any]:
    operation = payload["operation"]
    request = payload["request"]
    try:
        handler = _JOB_HANDLERS[operation]
    except KeyError as exc:
        raise ValueError(f"Unsupported job operation: {operation}") from exc
    try:
        return {"ok": True, "result": handler(**request)}
    except Exception as exc:
        return {"ok": False, "error": _error_payload(exc)}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit("usage: python -m article_api.job_runner <request-json-path>")
    with open(args[0], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    result = run_request(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
