from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_retention_sweep_report(
    *,
    max_age_seconds: float,
    reference_time: str,
    dry_run: bool,
    inspected_count: int,
    include_blocked_count: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "policy": "retention",
        "dry_run": bool(dry_run),
        "max_age_seconds": float(max_age_seconds),
        "reference_time": reference_time,
        "inspected_count": int(inspected_count),
        "eligible_count": 0,
        "cleaned_count": 0,
        "noop_count": 0,
        "skipped_count": 0,
        "items": [],
    }
    if include_blocked_count:
        report["blocked_count"] = 0
    return report


def with_cleanup_result(report: dict[str, Any], item: dict[str, Any], cleanup: dict[str, Any] | None) -> dict[str, Any]:
    cleanup_payload = deepcopy(cleanup) or {}
    updated = deepcopy(report)
    completed_item = deepcopy(item)
    completed_item["action"] = "cleaned"
    completed_item["cleanup"] = cleanup_payload

    counter_name = "cleaned_count" if cleanup_payload.get("state") == "cleaned" else "noop_count"
    updated[counter_name] = int(updated.get(counter_name) or 0) + 1
    updated["items"] = [*deepcopy(updated.get("items") or []), completed_item]
    return updated
