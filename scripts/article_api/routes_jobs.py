from __future__ import annotations

from typing import Any, Callable

from article_api.job_queries import filter_jobs
from article_api.route_error_handlers import call_with_http_error


def register_job_status_routes(
    app: Any,
    *,
    list_jobs_fn: Callable[[], list[dict[str, Any]]],
    get_job_fn: Callable[[str], dict[str, Any]],
    inspect_job_fn: Callable[[str], dict[str, Any]],
    get_job_result_fn: Callable[[str], dict[str, Any]],
    cleanup_job_fn: Callable[[str], dict[str, Any]],
    retry_job_fn: Callable[[str], dict[str, Any]],
    build_download_response_fn: Callable[[str, str], Any],
    raise_job_http_error: Callable[[Exception], None],
) -> None:
    @app.get("/jobs")
    def list_job_statuses(
        operation: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return call_with_http_error(
            lambda: filter_jobs(list_jobs_fn(), operation=operation, status=status, limit=limit),
            raise_job_http_error,
        )

    @app.get("/jobs/{job_id}")
    def get_job_status(job_id: str) -> dict[str, Any]:
        return call_with_http_error(lambda: get_job_fn(job_id), raise_job_http_error)

    @app.get("/jobs/{job_id}/inspect")
    def inspect_job_status(job_id: str) -> dict[str, Any]:
        return call_with_http_error(lambda: inspect_job_fn(job_id), raise_job_http_error)

    @app.get("/jobs/{job_id}/result")
    def get_job_output(job_id: str) -> dict[str, Any]:
        return call_with_http_error(lambda: get_job_result_fn(job_id), raise_job_http_error)

    @app.post("/jobs/{job_id}/cleanup")
    def cleanup_job_runtime(job_id: str) -> dict[str, Any]:
        return call_with_http_error(lambda: cleanup_job_fn(job_id), raise_job_http_error)

    @app.post("/jobs/{job_id}/retry", status_code=201)
    def retry_job_runtime(job_id: str) -> dict[str, Any]:
        return call_with_http_error(lambda: retry_job_fn(job_id), raise_job_http_error)

    @app.get("/jobs/{job_id}/artifacts/{artifact_role}/download")
    def download_job_artifact(job_id: str, artifact_role: str):
        return call_with_http_error(
            lambda: build_download_response_fn(job_id, artifact_role),
            raise_job_http_error,
        )
