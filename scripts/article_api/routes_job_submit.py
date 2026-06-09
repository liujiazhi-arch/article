from __future__ import annotations

from typing import Any, Callable

from article_api.request_payloads import apply_job_kwargs, normalize_job_kwargs, verify_job_kwargs
from article_api.route_error_handlers import call_with_http_error
from article_api.schemas import ApplyRequest, NormalizeJobRequest, VerifyRequest


def register_job_submit_routes(
    app: Any,
    *,
    create_job_fn: Callable[[str, dict[str, Any]], dict[str, Any]],
    maybe_autorun_retention: Callable[[], None],
    raise_job_http_error: Callable[[Exception], None],
) -> None:
    @app.post("/jobs/verify", status_code=201)
    def create_verify_job(request: VerifyRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("verify", verify_job_kwargs(request))

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/jobs/normalize", status_code=201)
    def create_normalize_job(request: NormalizeJobRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("normalize", normalize_job_kwargs(request))

        return call_with_http_error(action, raise_job_http_error)

    @app.post("/jobs/apply", status_code=201)
    def create_apply_job(request: ApplyRequest) -> dict[str, Any]:
        def action() -> dict[str, Any]:
            maybe_autorun_retention()
            return create_job_fn("apply", apply_job_kwargs(request))

        return call_with_http_error(action, raise_job_http_error)
