from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Callable


STATE_ROOT_ENV_VAR = "ARTICLE_API_STATE_ROOT"
DB_FILENAME = "article_api.sqlite3"
SCHEMA_VERSION = 2
_TABLE_NAMES = ("jobs", "artifacts", "uploads", "job_cleanup", "upload_cleanup")
_INDEX_DEFINITIONS = {
    "idx_jobs_status_updated_at": "CREATE INDEX IF NOT EXISTS idx_jobs_status_updated_at ON jobs(status, updated_at)",
    "idx_jobs_finished_at": "CREATE INDEX IF NOT EXISTS idx_jobs_finished_at ON jobs(finished_at)",
    "idx_artifacts_job_id_position": (
        "CREATE INDEX IF NOT EXISTS idx_artifacts_job_id_position ON artifacts(job_id, position)"
    ),
    "idx_uploads_created_at": "CREATE INDEX IF NOT EXISTS idx_uploads_created_at ON uploads(created_at)",
}
_SUPPORTED_SCHEMA_VERSIONS = (1, 2)

_DB_LOCK = Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_state_root() -> Path:
    return Path(__file__).resolve().parents[2] / ".article_runtime"


def resolve_state_root(state_root: str | Path | None = None) -> Path:
    root_value = state_root or os.environ.get(STATE_ROOT_ENV_VAR)
    root = Path(root_value).expanduser().resolve() if root_value else _default_state_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_db_path(state_root: str | Path | None = None) -> Path:
    return resolve_state_root(state_root) / DB_FILENAME


def _connect(state_root: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(resolve_db_path(state_root))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _get_user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    return int(row[0])


def _set_user_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute(f"PRAGMA user_version = {int(version)}")


def _create_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            request_json TEXT NOT NULL,
            resolved_request_json TEXT NOT NULL,
            workspace_json TEXT,
            runtime_json TEXT,
            summary_json TEXT,
            error_json TEXT,
            result_json TEXT,
            result_available INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            kind TEXT,
            role TEXT,
            path TEXT,
            payload_json TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads (
            upload_id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            workspace_dir TEXT NOT NULL,
            runtime_root TEXT,
            size_bytes INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS job_cleanup (
            job_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_cleanup (
            upload_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            FOREIGN KEY(upload_id) REFERENCES uploads(upload_id) ON DELETE CASCADE
        )
        """
    )


def _create_indexes(connection: sqlite3.Connection) -> None:
    for ddl in _INDEX_DEFINITIONS.values():
        connection.execute(ddl)


def _apply_migration_0_to_1(connection: sqlite3.Connection) -> None:
    _create_tables(connection)
    _set_user_version(connection, 1)


def _apply_migration_1_to_2(connection: sqlite3.Connection) -> None:
    _create_tables(connection)
    _create_indexes(connection)
    _set_user_version(connection, 2)


_MIGRATION_CHAIN: dict[int, Callable[[sqlite3.Connection], None]] = {
    0: _apply_migration_0_to_1,
    1: _apply_migration_1_to_2,
}


def _migrate(connection: sqlite3.Connection) -> None:
    user_version = _get_user_version(connection)
    if user_version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {user_version} is newer than supported version {SCHEMA_VERSION}"
        )
    while user_version < SCHEMA_VERSION:
        try:
            migration = _MIGRATION_CHAIN[user_version]
        except KeyError as exc:
            raise RuntimeError(f"No migration path registered for schema version {user_version}") from exc
        migration(connection)
        user_version = _get_user_version(connection)


def init_storage(state_root: str | Path | None = None) -> None:
    with _DB_LOCK:
        with _connect(state_root) as connection:
            _migrate(connection)


def get_schema_version(state_root: str | Path | None = None) -> int:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            return _get_user_version(connection)


def inspect_storage(
    state_root: str | Path | None = None,
    *,
    include_integrity_check: bool = True,
) -> dict[str, Any]:
    init_storage(state_root)
    resolved_state_root = resolve_state_root(state_root)
    db_path = resolve_db_path(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            schema_version = _get_user_version(connection)
            journal_mode_row = connection.execute("PRAGMA journal_mode").fetchone()
            journal_mode = str(journal_mode_row[0]) if journal_mode_row is not None else None
            integrity_result = None
            if include_integrity_check:
                integrity_row = connection.execute("PRAGMA quick_check").fetchone()
                integrity_result = str(integrity_row[0]) if integrity_row is not None else "unknown"
            tables = {
                table_name: {
                    "rows": int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]),
                }
                for table_name in _TABLE_NAMES
            }
            present_indexes = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
    return {
        "status": "ok" if integrity_result in (None, "ok") else "degraded",
        "state_root": str(resolved_state_root),
        "state_root_exists": resolved_state_root.exists(),
        "state_root_writable": os.access(resolved_state_root, os.W_OK),
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "schema_version": schema_version,
        "supported_schema_versions": list(_SUPPORTED_SCHEMA_VERSIONS),
        "journal_mode": journal_mode,
        "integrity_check": integrity_result,
        "tables": tables,
        "indexes": {
            index_name: {
                "present": index_name in present_indexes,
            }
            for index_name in sorted(_INDEX_DEFINITIONS)
        },
    }


def maintain_storage(
    state_root: str | Path | None = None,
    *,
    run_vacuum: bool = False,
    run_analyze: bool = True,
    include_integrity_check: bool = True,
) -> dict[str, Any]:
    init_storage(state_root)
    resolved_state_root = resolve_state_root(state_root)
    db_path = resolve_db_path(state_root)
    before_size = db_path.stat().st_size if db_path.exists() else 0
    actions: list[str] = []
    with _DB_LOCK:
        with sqlite3.connect(db_path, isolation_level=None) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            if run_analyze:
                connection.execute("ANALYZE")
                actions.append("analyze")
            if run_vacuum:
                connection.execute("VACUUM")
                actions.append("vacuum")
    after = inspect_storage(resolved_state_root, include_integrity_check=include_integrity_check)
    after_size = Path(after["db_path"]).stat().st_size if after["db_exists"] else 0
    return {
        "state_root": str(resolved_state_root),
        "db_path": str(db_path),
        "performed_at": _utcnow(),
        "actions": actions,
        "vacuum": bool(run_vacuum),
        "analyze": bool(run_analyze),
        "size_bytes_before": before_size,
        "size_bytes_after": after_size,
        "size_delta_bytes": after_size - before_size,
        "status": after["status"],
        "storage": after,
    }


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _json_loads(payload: str | None) -> Any:
    if payload is None:
        return None
    return json.loads(payload)


def upsert_job(job_payload: dict[str, Any], *, state_root: str | Path | None = None) -> None:
    init_storage(state_root)
    artifacts = list(job_payload.get("artifacts") or [])
    with _DB_LOCK:
        with _connect(state_root) as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    operation,
                    status,
                    mode,
                    created_at,
                    updated_at,
                    started_at,
                    finished_at,
                    request_json,
                    resolved_request_json,
                    workspace_json,
                    runtime_json,
                    summary_json,
                    error_json,
                    result_json,
                    result_available
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    operation = excluded.operation,
                    status = excluded.status,
                    mode = excluded.mode,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    request_json = excluded.request_json,
                    resolved_request_json = excluded.resolved_request_json,
                    workspace_json = excluded.workspace_json,
                    runtime_json = excluded.runtime_json,
                    summary_json = excluded.summary_json,
                    error_json = excluded.error_json,
                    result_json = excluded.result_json,
                    result_available = excluded.result_available
                """,
                (
                    job_payload["job_id"],
                    job_payload["operation"],
                    job_payload["status"],
                    job_payload.get("mode", "inline"),
                    job_payload["created_at"],
                    job_payload["updated_at"],
                    job_payload.get("started_at"),
                    job_payload.get("finished_at"),
                    _json_dumps(job_payload.get("request") or {}),
                    _json_dumps(job_payload.get("resolved_request") or {}),
                    _json_dumps(job_payload.get("workspace")),
                    _json_dumps(job_payload.get("runtime")),
                    _json_dumps(job_payload.get("summary")),
                    _json_dumps(job_payload.get("error")),
                    _json_dumps(job_payload.get("result")),
                    int(bool(job_payload.get("result_available"))),
                ),
            )
            connection.execute("DELETE FROM artifacts WHERE job_id = ?", (job_payload["job_id"],))
            for position, artifact in enumerate(artifacts):
                connection.execute(
                    """
                    INSERT INTO artifacts (job_id, position, kind, role, path, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_payload["job_id"],
                        position,
                        artifact.get("kind"),
                        artifact.get("role"),
                        artifact.get("path"),
                        _json_dumps(artifact),
                    ),
                )


def _load_artifacts(connection: sqlite3.Connection, job_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT payload_json FROM artifacts WHERE job_id = ? ORDER BY position ASC",
        (job_id,),
    ).fetchall()
    return [_json_loads(row["payload_json"]) for row in rows]


def _row_to_job_payload(row: sqlite3.Row, artifacts: list[dict[str, Any]], *, include_result: bool) -> dict[str, Any]:
    payload = {
        "job_id": row["job_id"],
        "operation": row["operation"],
        "status": row["status"],
        "mode": row["mode"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "request": _json_loads(row["request_json"]),
        "resolved_request": _json_loads(row["resolved_request_json"]),
        "workspace": _json_loads(row["workspace_json"]),
        "runtime": _json_loads(row["runtime_json"]),
        "result_available": bool(row["result_available"]),
        "summary": _json_loads(row["summary_json"]),
        "artifacts": artifacts,
        "error": _json_loads(row["error_json"]),
    }
    if include_result:
        payload["result"] = _json_loads(row["result_json"])
    return payload


def _row_to_upload_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "upload_id": row["upload_id"],
        "file_name": row["file_name"],
        "stored_path": row["stored_path"],
        "workspace_dir": row["workspace_dir"],
        "runtime_root": row["runtime_root"],
        "size_bytes": int(row["size_bytes"]),
        "created_at": row["created_at"],
    }


def upsert_upload(upload_payload: dict[str, Any], *, state_root: str | Path | None = None) -> None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            connection.execute(
                """
                INSERT INTO uploads (
                    upload_id,
                    file_name,
                    stored_path,
                    workspace_dir,
                    runtime_root,
                    size_bytes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(upload_id) DO UPDATE SET
                    file_name = excluded.file_name,
                    stored_path = excluded.stored_path,
                    workspace_dir = excluded.workspace_dir,
                    runtime_root = excluded.runtime_root,
                    size_bytes = excluded.size_bytes,
                    created_at = excluded.created_at
                """,
                (
                    upload_payload["upload_id"],
                    upload_payload["file_name"],
                    upload_payload["stored_path"],
                    upload_payload["workspace_dir"],
                    upload_payload.get("runtime_root"),
                    int(upload_payload["size_bytes"]),
                    upload_payload["created_at"],
                ),
            )


def get_upload(upload_id: str, *, state_root: str | Path | None = None) -> dict[str, Any] | None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            row = connection.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
    if row is None:
        return None
    return _row_to_upload_payload(row)


def list_uploads(*, state_root: str | Path | None = None) -> list[dict[str, Any]]:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            rows = connection.execute("SELECT * FROM uploads ORDER BY created_at DESC").fetchall()
    return [_row_to_upload_payload(row) for row in rows]


def upsert_job_cleanup(job_id: str, payload: dict[str, Any], *, state_root: str | Path | None = None) -> None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            connection.execute(
                """
                INSERT INTO job_cleanup (job_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (job_id, _json_dumps(payload)),
            )


def get_job_cleanup(job_id: str, *, state_root: str | Path | None = None) -> dict[str, Any] | None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            row = connection.execute("SELECT payload_json FROM job_cleanup WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return _json_loads(row["payload_json"])


def _load_job_cleanup(connection: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT payload_json FROM job_cleanup WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return _json_loads(row["payload_json"])


def upsert_upload_cleanup(upload_id: str, payload: dict[str, Any], *, state_root: str | Path | None = None) -> None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            connection.execute(
                """
                INSERT INTO upload_cleanup (upload_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(upload_id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (upload_id, _json_dumps(payload)),
            )


def get_upload_cleanup(upload_id: str, *, state_root: str | Path | None = None) -> dict[str, Any] | None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            row = connection.execute("SELECT payload_json FROM upload_cleanup WHERE upload_id = ?", (upload_id,)).fetchone()
    if row is None:
        return None
    return _json_loads(row["payload_json"])


def get_job(job_id: str, *, include_result: bool, state_root: str | Path | None = None) -> dict[str, Any] | None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            artifacts = _load_artifacts(connection, job_id)
            cleanup = _load_job_cleanup(connection, job_id)
    payload = _row_to_job_payload(row, artifacts, include_result=include_result)
    payload["cleanup"] = cleanup
    return payload


def list_jobs(*, include_result: bool, state_root: str | Path | None = None) -> list[dict[str, Any]]:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            payloads = []
            for row in rows:
                artifacts = _load_artifacts(connection, row["job_id"])
                payload = _row_to_job_payload(row, artifacts, include_result=include_result)
                payload["cleanup"] = _load_job_cleanup(connection, row["job_id"])
                payloads.append(payload)
    return payloads


def clear_jobs(state_root: str | Path | None = None) -> None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            connection.execute("DELETE FROM jobs")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'artifacts'")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'uploads'")


def clear_uploads(state_root: str | Path | None = None) -> None:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            connection.execute("DELETE FROM uploads")


def job_count(state_root: str | Path | None = None) -> int:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()
    return int(row["count"])


def upload_count(state_root: str | Path | None = None) -> int:
    init_storage(state_root)
    with _DB_LOCK:
        with _connect(state_root) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM uploads").fetchone()
    return int(row["count"])
