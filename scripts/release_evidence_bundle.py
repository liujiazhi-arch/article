from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any, Sequence
import zipfile

from file_hash_utils import sha256_file as _sha256_file


ALLOWED_SUFFIXES = {".json", ".md", ".txt", ".sha256"}
FORBIDDEN_SUFFIXES = {".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".log", ".db", ".sqlite3"}
FORBIDDEN_NAMES = {".env", "article-local.env", "反馈包.zip"}
FORBIDDEN_NAME_PARTS = {"secret", "apikey", "api-key", "token", "password", "论文", "修复稿"}


def _is_privacy_sensitive(path: Path) -> bool:
    lowered_name = path.name.lower()
    lowered_parts = [part.lower() for part in path.parts]
    if path.name in FORBIDDEN_NAMES or lowered_name in FORBIDDEN_NAMES:
        return True
    if lowered_name.startswith(".env") or lowered_name.endswith(".env") or ".env" in lowered_name:
        return True
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        return True
    if any(part in {"uploads", "artifacts", "runtime", "state", ".cache", "cache"} for part in lowered_parts):
        return True
    return any(fragment in lowered_name for fragment in FORBIDDEN_NAME_PARTS)


def _validate_evidence_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise RuntimeError(f"Evidence file does not exist: {resolved}")
    if _is_privacy_sensitive(resolved):
        raise RuntimeError(f"Refusing privacy-sensitive evidence input: {resolved}")
    if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
        raise RuntimeError(f"Evidence file must be JSON, Markdown, text, or sha256: {resolved}")
    return resolved


def _archive_name(path: Path) -> str:
    safe_name = PurePosixPath(path.name).name
    return f"evidence/{safe_name}"


def _manifest(files: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": "article-local-release-evidence",
        "schema_version": 1,
        "privacy": {
            "includes_documents": False,
            "includes_repaired_documents": False,
            "includes_secrets": False,
            "includes_runtime_cache": False,
            "includes_state_database": False,
            "note": "This bundle includes only explicitly selected release evidence files.",
        },
        "files": list(files),
    }


def build_release_evidence_bundle(
    *,
    output_zip: str | Path,
    evidence_paths: Sequence[str | Path],
) -> dict[str, Any]:
    resolved_output = Path(output_zip).expanduser().resolve()
    resolved_evidence = [_validate_evidence_path(Path(path)) for path in evidence_paths]
    if not resolved_evidence:
        raise RuntimeError("At least one evidence file is required.")

    seen_archive_names: set[str] = set()
    file_entries: list[dict[str, Any]] = []
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(resolved_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(resolved_evidence, key=lambda item: item.name):
            archive_name = _archive_name(path)
            if archive_name in seen_archive_names:
                raise RuntimeError(f"Duplicate evidence archive name: {archive_name}")
            seen_archive_names.add(archive_name)
            archive.write(path, archive_name)
            file_entries.append(
                {
                    "archive_name": archive_name,
                    "source_name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
        archive.writestr(
            "manifest.json",
            json.dumps(_manifest(file_entries), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    return {
        "status": "ok",
        "output_zip": str(resolved_output),
        "entry_count": len(file_entries) + 1,
        "files": file_entries,
        "sha256": _sha256_file(resolved_output),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="release_evidence_bundle.py")
    parser.add_argument("--output-zip", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    return parser


def _format_error(exc: Exception) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
        "next_steps": [
            "Pass only release evidence JSON, Markdown reports, text notes, or sha256 files.",
            "Do not include论文、修复稿、PDF、截图、日志、env、runtime、state 或反馈包。",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = build_release_evidence_bundle(
            output_zip=args.output_zip,
            evidence_paths=args.evidence,
        )
    except Exception as exc:
        print(json.dumps(_format_error(exc), ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
