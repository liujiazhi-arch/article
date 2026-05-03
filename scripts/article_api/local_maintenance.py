from __future__ import annotations

from . import app_ops
from . import storage
from .local_env import resolved_roots, root_env_scope, utcnow


def run_storage_maintenance(
    *,
    state_root: str | None = None,
    runtime_root: str | None = None,
    run_vacuum: bool = False,
    run_analyze: bool = True,
) -> dict:
    with root_env_scope(state_root=state_root, runtime_root=runtime_root):
        resolved_state_root, resolved_runtime_root = resolved_roots(state_root=state_root, runtime_root=runtime_root)
        maintenance = storage.maintain_storage(
            resolved_state_root,
            run_vacuum=run_vacuum,
            run_analyze=run_analyze,
        )
        storage_view = app_ops.build_ops_storage_payload()
    return {
        "service": app_ops.SERVICE_NAME,
        "stage": app_ops.SERVICE_STAGE,
        "version": app_ops.SERVICE_VERSION,
        "api_version": app_ops.API_VERSION,
        "observed_at": utcnow(),
        "roots": {
            "state_root": str(resolved_state_root),
            "runtime_root": str(resolved_runtime_root),
            "shared_root": resolved_state_root == resolved_runtime_root,
        },
        "summary": {
            "headline": "本地状态库维护完成。",
            "actions": maintenance["actions"],
            "size_bytes_before": maintenance["size_bytes_before"],
            "size_bytes_after": maintenance["size_bytes_after"],
            "size_delta_bytes": maintenance["size_delta_bytes"],
        },
        "maintenance": maintenance,
        "storage": storage_view["summary"],
    }
