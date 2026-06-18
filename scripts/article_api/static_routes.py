from __future__ import annotations

from pathlib import Path
from typing import Any


STATIC_ROOT = Path(__file__).resolve().parent / "static"


def register_static_frontend_routes(app: Any, *, file_response_cls: Any, http_exception_cls: Any) -> None:
    @app.get("/", include_in_schema=False)
    def frontend_index():
        index_path = STATIC_ROOT / "index.html"
        if not index_path.exists():
            raise http_exception_cls(status_code=404, detail="Frontend index is unavailable.")
        return file_response_cls(str(index_path), media_type="text/html; charset=utf-8")

    @app.get("/static/{asset_path:path}", include_in_schema=False)
    def frontend_asset(asset_path: str):
        requested = (STATIC_ROOT / asset_path).resolve()
        try:
            requested.relative_to(STATIC_ROOT.resolve())
        except ValueError as exc:
            raise http_exception_cls(status_code=404, detail="Frontend asset is unavailable.") from exc
        if not requested.exists() or not requested.is_file():
            raise http_exception_cls(status_code=404, detail="Frontend asset is unavailable.")
        return file_response_cls(str(requested))
