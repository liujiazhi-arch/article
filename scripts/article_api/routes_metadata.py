from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def register_metadata_routes(
    app: Any,
    *,
    file_response_cls: Any,
    http_exception_cls: Any,
    html_response_fn: Callable[[str], Any],
    local_console_html_fn: Callable[[], str],
    health_payload_fn: Callable[[], dict[str, Any]],
    readiness_payload_fn: Callable[[], dict[str, Any]],
    version_payload_fn: Callable[[], dict[str, Any]],
    latest_update_payload_fn: Callable[[], dict[str, Any]],
    render_workflow_modes_payload_fn: Callable[[], dict[str, Any]],
    profile_catalog_fn: Callable[[], dict[str, Any]],
    raise_sync_http_error: Callable[[Exception], None],
    package_file: str | Path,
) -> None:
    @app.get("/")
    def local_console():
        return html_response_fn(local_console_html_fn())

    @app.get("/assets/lnu-emblem.jpg")
    def lnu_emblem():
        emblem_path = Path(package_file).with_name("assets") / "lnu-emblem.jpg"
        if not emblem_path.exists():
            raise http_exception_cls(status_code=404, detail="Liaoning University emblem asset is unavailable.")
        return file_response_cls(str(emblem_path), media_type="image/jpeg")

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
