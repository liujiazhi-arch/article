from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Callable

from article_api.local_feedback import create_feedback_archive
from article_api.route_error_handlers import call_with_http_error


def build_feedback_download_response(*, file_response_cls: Any) -> Any:
    feedback_dir = Path(tempfile.mkdtemp(prefix="article-feedback-"))
    feedback_path = feedback_dir / "feedback.zip"
    create_feedback_archive(str(feedback_path))
    filename = "反馈包.zip"
    media_type = "application/zip"
    if file_response_cls is None:  # pragma: no cover
        return {
            "path": str(feedback_path),
            "filename": filename,
            "media_type": media_type,
        }
    return file_response_cls(
        str(feedback_path),
        filename=filename,
        media_type=media_type,
    )


def register_feedback_routes(
    app: Any,
    *,
    build_feedback_download_response_fn: Callable[[], Any],
    raise_job_http_error: Callable[[Exception], None],
) -> None:
    @app.get("/feedback/download")
    def download_feedback_archive():
        return call_with_http_error(build_feedback_download_response_fn, raise_job_http_error)
