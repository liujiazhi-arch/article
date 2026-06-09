from __future__ import annotations

from typing import Any, Callable

from article_api.request_payloads import (
    apply_kwargs,
    audit_kwargs,
    normalize_kwargs,
    plan_kwargs,
    preflight_kwargs,
    render_verify_kwargs,
    verify_kwargs,
)
from article_api.route_error_handlers import call_with_http_error
from article_api.schemas import (
    ApplyRequest,
    AuditRequest,
    NormalizeRequest,
    PlanRequest,
    PreflightRequest,
    RenderVerifyRequest,
    VerifyRequest,
)


def register_sync_engine_routes(
    app: Any,
    *,
    audit_document_fn: Callable[..., dict[str, Any]],
    plan_document_fn: Callable[..., dict[str, Any]],
    build_preflight_payload_fn: Callable[..., dict[str, Any]],
    build_normalize_payload_fn: Callable[..., dict[str, Any]],
    build_render_verify_payload_fn: Callable[..., dict[str, Any]],
    verify_document_fn: Callable[..., dict[str, Any]],
    apply_fix_fn: Callable[..., dict[str, Any]],
    raise_sync_http_error: Callable[[Exception], None],
) -> None:
    @app.post("/audit")
    def audit_endpoint(request: AuditRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: audit_document_fn(**audit_kwargs(request)),
            raise_sync_http_error,
        )

    @app.post("/plan")
    def plan_endpoint(request: PlanRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: plan_document_fn(**plan_kwargs(request)),
            raise_sync_http_error,
        )

    @app.post("/preflight")
    def preflight_endpoint(request: PreflightRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: build_preflight_payload_fn(**preflight_kwargs(request)),
            raise_sync_http_error,
        )

    @app.post("/normalize")
    def normalize_endpoint(request: NormalizeRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: build_normalize_payload_fn(**normalize_kwargs(request)),
            raise_sync_http_error,
        )

    @app.post("/render-verify")
    def render_verify_endpoint(request: RenderVerifyRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: build_render_verify_payload_fn(**render_verify_kwargs(request)),
            raise_sync_http_error,
        )

    @app.post("/verify")
    def verify_endpoint(request: VerifyRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: verify_document_fn(**verify_kwargs(request)),
            raise_sync_http_error,
        )

    @app.post("/apply")
    def apply_endpoint(request: ApplyRequest) -> dict[str, Any]:
        return call_with_http_error(
            lambda: apply_fix_fn(**apply_kwargs(request)),
            raise_sync_http_error,
        )
