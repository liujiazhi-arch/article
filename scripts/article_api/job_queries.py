from __future__ import annotations

from typing import Any, Iterable


def coerce_jobs_limit(limit: int) -> int:
    normalized = int(limit)
    if normalized < 1:
        raise ValueError("limit must be >= 1")
    return normalized


def filter_jobs(
    jobs: Iterable[dict[str, Any]],
    *,
    operation: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    filtered = list(jobs)
    if operation is not None:
        filtered = [item for item in filtered if item.get("operation") == operation]
    if status is not None:
        filtered = [item for item in filtered if item.get("status") == status]
    if limit is not None:
        filtered = filtered[:coerce_jobs_limit(limit)]
    return filtered
