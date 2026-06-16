from __future__ import annotations

from typing import Any, Callable


def register_metadata_routes(
    app: Any,
    *,
    file_response_cls: Any,
    http_exception_cls: Any,
    health_payload_fn: Callable[[], dict[str, Any]],
    readiness_payload_fn: Callable[[], dict[str, Any]],
    version_payload_fn: Callable[[], dict[str, Any]],
    latest_update_payload_fn: Callable[[], dict[str, Any]],
    render_workflow_modes_payload_fn: Callable[[], dict[str, Any]],
    render_evidence_screenshot_path_fn: Callable[[str], str],
    profile_catalog_fn: Callable[[], dict[str, Any]],
    raise_sync_http_error: Callable[[Exception], None],
) -> None:
    @app.get("/render-evidence/screenshot/{token}")
    def render_evidence_screenshot(token: str):
        try:
            screenshot_path = render_evidence_screenshot_path_fn(token)
        except LookupError as exc:
            raise http_exception_cls(status_code=404, detail="Render evidence screenshot is unavailable.") from exc
        if file_response_cls is None:  # pragma: no cover - used by fake route tests
            return {"path": str(screenshot_path), "media_type": "image/png"}
        return file_response_cls(str(screenshot_path), media_type="image/png")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return health_payload_fn()

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        try:
            return readiness_payload_fn()
        except Exception as exc:
            raise http_exception_cls(status_code=503, detail=f"Readiness check failed: {exc}") from exc

    @app.get("/version")
    def version() -> dict[str, Any]:
        return version_payload_fn()

    @app.get("/updates/latest")
    def latest_update() -> dict[str, Any]:
        return latest_update_payload_fn()

    @app.get("/profiles")
    def profiles() -> dict[str, Any]:
        try:
            return profile_catalog_fn()
        except Exception as exc:
            raise_sync_http_error(exc)
            raise

    @app.get("/render-workflow-modes")
    def render_workflow_modes() -> dict[str, Any]:
        return render_workflow_modes_payload_fn()
