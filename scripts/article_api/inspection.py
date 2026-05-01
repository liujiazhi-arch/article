from __future__ import annotations

from copy import deepcopy
from typing import Any

from .jobs import get_job


def build_job_inspection(job_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job_payload["job_id"],
        "operation": job_payload["operation"],
        "status": job_payload["status"],
        "created_at": job_payload["created_at"],
        "started_at": job_payload.get("started_at"),
        "finished_at": job_payload.get("finished_at"),
        "summary": deepcopy(job_payload.get("summary")),
        "runtime": deepcopy(job_payload.get("runtime")),
        "artifacts": deepcopy(job_payload.get("artifacts")),
        "error": deepcopy(job_payload.get("error")),
        "cleanup": deepcopy(job_payload.get("cleanup")),
        "result_available": bool(job_payload.get("result_available")),
        "request_paths": {
            "input_path": (job_payload.get("runtime") or {}).get("input_path"),
            "source_file_path": (job_payload.get("runtime") or {}).get("source_file_path"),
            "staged_input_path": (job_payload.get("runtime") or {}).get("staged_input_path"),
            "output_path": (job_payload.get("runtime") or {}).get("output_path"),
            "output_dir": (job_payload.get("runtime") or {}).get("output_dir"),
            "summary_file": (job_payload.get("runtime") or {}).get("summary_file"),
            "workspace_root": (job_payload.get("runtime") or {}).get("workspace_root"),
        },
    }


def get_job_inspection(job_id: str) -> dict[str, Any]:
    return build_job_inspection(get_job(job_id))


def get_job_runtime_snapshot(job_id: str) -> dict[str, Any]:
    inspection = get_job_inspection(job_id)
    return {
        "job_id": inspection["job_id"],
        "operation": inspection["operation"],
        "status": inspection["status"],
        "summary": deepcopy(inspection["summary"]),
        "runtime": deepcopy(inspection["runtime"]),
        "artifacts": deepcopy(inspection["artifacts"]),
        "error": deepcopy(inspection["error"]),
    }
