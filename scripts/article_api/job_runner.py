from __future__ import annotations

import json
import sys
from typing import Any

from article_engine import apply_fix, normalize_document, verify_document
from article_api.profile_batch import run_batch_workflow


_BATCH_JOB_SERVICE_NAME = "article-api"
_BATCH_JOB_STAGE = "local-shell-alpha"
_BATCH_JOB_VERSION = "0.1.0"
_BATCH_JOB_API_VERSION = "v0"


def _run_batch_job(**request) -> dict[str, Any]:
    return run_batch_workflow(
        request["operation"],
        request["input_path"],
        profile=request.get("profile", "lnu"),
        strict_profile=request.get("strict_profile"),
        scopes=request.get("scopes"),
        output_dir=request.get("output_dir"),
        summary_file=request.get("summary_file"),
        pattern=request.get("pattern", "*.docx"),
        recursive=bool(request.get("recursive", False)),
        toc=bool(request.get("toc", False)),
        dry_run=bool(request.get("dry_run", False)),
        renumber_headings=bool(request.get("renumber_headings", False)),
        layout_rebalance=bool(request.get("layout_rebalance", False)),
        force=bool(request.get("force", False)),
        fail_fast=bool(request.get("fail_fast", False)),
        service_name=_BATCH_JOB_SERVICE_NAME,
        stage=_BATCH_JOB_STAGE,
        version=_BATCH_JOB_VERSION,
        api_version=_BATCH_JOB_API_VERSION,
    )


_JOB_HANDLERS = {
    "apply": apply_fix,
    "normalize": normalize_document,
    "verify": verify_document,
    "batch": _run_batch_job,
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
