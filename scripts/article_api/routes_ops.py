from __future__ import annotations

from typing import Any, Callable

from article_api.route_error_handlers import call_with_http_error
from article_api.schemas import RetentionDefaultsRunRequest, RetentionSweepRequest


def register_ops_routes(
    app: Any,
    *,
    ops_summary_payload_fn: Callable[[], dict[str, Any]],
    ops_storage_payload_fn: Callable[[], dict[str, Any]],
    ops_runtime_payload_fn: Callable[[], dict[str, Any]],
    run_default_retention_sweep_fn: Callable[..., dict[str, Any]],
    sweep_retention_fn: Callable[[RetentionSweepRequest], dict[str, Any]],
    raise_job_http_error: Callable[[Exception], None],
) -> None:
    @app.get("/ops/summary")
    def ops_summary() -> dict[str, Any]:
        return call_with_http_error(ops_summary_payload_fn, raise_job_http_error)

    @app.get("/ops/storage")
    def ops_storage() -> dict[str, Any]:
        return call_with_http_error(ops_storage_payload_fn, raise_job_http_error)

    @app.get("/ops/runtime")
    def ops_runtime() -> dict[str, Any]:
        return call_with_http_error(ops_runtime_payload_fn, raise_job_http_error)

    @app.post("/ops/retention/run-defaults")
    def run_default_retention(request: RetentionDefaultsRunRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: run_default_retention_sweep_fn(dry_run=request.dry_run, trigger="manual-defaults"),
            raise_job_http_error,
        )

    @app.post("/ops/retention/sweep")
    def sweep_retention(request: RetentionSweepRequest) -> dict[str, Any]:
        return call_with_http_error(lambda: sweep_retention_fn(request), raise_job_http_error)
