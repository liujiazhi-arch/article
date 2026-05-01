from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from _profile_utils import list_profile_catalog
from article_engine import apply_fix, audit_document, plan_document, verify_document
from thesis_tool.scopes import normalize_scope_names


BATCH_OPERATIONS = ("audit", "plan", "verify", "apply")


def _infer_readiness_from_payload(payload: dict) -> str | None:
    if payload.get("readiness"):
        return str(payload["readiness"])

    verification = payload.get("verification") or {}
    if verification.get("readiness"):
        return str(verification["readiness"])

    manual_review_rule_ids = payload.get("manual_review_rule_ids") or verification.get("manual_review_rule_ids") or []
    unsupported_rule_ids = payload.get("unsupported_rule_ids") or verification.get("unsupported_rule_ids") or []
    if unsupported_rule_ids:
        return "unsupported"
    if manual_review_rule_ids:
        return "manual-review-required"

    failed_results = payload.get("failed_results") or []
    if failed_results:
        actions = {item.get("action") for item in failed_results}
        if "unsupported" in actions:
            return "unsupported"
        if "manual_review" in actions:
            return "manual-review-required"
        if "autofix" in actions:
            return "needs-fix"

    summary = payload.get("summary") or {}
    failed_rules = summary.get("failed_rules")
    if failed_rules == 0:
        return "structure-ready"
    if failed_rules:
        return "needs-fix"
    return None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json_file(output_path: str | Path, payload: dict) -> Path:
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _catalog_support_summary(profiles: list[dict]) -> list[dict]:
    scenarios: dict[str, dict] = {}
    for profile in profiles:
        for scenario in profile.get("support_scenarios") or []:
            scenario_id = str(scenario.get("id") or "").strip()
            label = str(scenario.get("label") or "").strip()
            if not scenario_id or not label:
                continue
            entry = scenarios.setdefault(
                scenario_id,
                {
                    "id": scenario_id,
                    "label": label,
                    "document_types": [],
                    "support_levels": [],
                    "profile_ids": [],
                },
            )
            for doc_type in scenario.get("document_types") or []:
                if doc_type not in entry["document_types"]:
                    entry["document_types"].append(doc_type)
            level_label = scenario.get("support_level_label")
            if level_label and level_label not in entry["support_levels"]:
                entry["support_levels"].append(level_label)
            profile_id = profile.get("id")
            if profile_id and profile_id not in entry["profile_ids"]:
                entry["profile_ids"].append(profile_id)
    return sorted(scenarios.values(), key=lambda item: item["id"])


def build_profile_catalog(
    *,
    service_name: str,
    stage: str,
    version: str,
    api_version: str,
) -> dict:
    profiles = list_profile_catalog()
    support_scenarios = _catalog_support_summary(profiles)
    return {
        "service": service_name,
        "stage": stage,
        "version": version,
        "api_version": api_version,
        "observed_at": _utcnow(),
        "summary": {
            "profile_count": len(profiles),
            "default_profile_id": "cn-common",
            "support_scenario_count": len(support_scenarios),
            "support_scenarios": support_scenarios,
        },
        "profiles": profiles,
    }


def _collect_batch_inputs(input_path: str, *, pattern: str = "*.docx", recursive: bool = False) -> tuple[Path, list[Path]]:
    root = Path(input_path).expanduser().resolve()
    if root.is_file():
        return root.parent, [root]
    if not root.exists():
        raise RuntimeError(f"Batch input path not found: {root}")
    if not root.is_dir():
        raise RuntimeError(f"Batch input path is not a file or directory: {root}")
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    files = sorted(path.resolve() for path in iterator if path.is_file())
    if not files:
        raise RuntimeError(f"No input documents matched {pattern} under {root}")
    return root, files


def _batch_output_suffix(scopes) -> str:
    normalized_scopes = normalize_scope_names(scopes)
    if not normalized_scopes:
        return "fixed"
    return "_".join(sorted(normalized_scopes))


def _batch_apply_output_path(source_path: Path, *, input_root: Path, output_dir: Path, scopes) -> Path:
    relative_path = source_path.relative_to(input_root) if source_path.is_relative_to(input_root) else Path(source_path.name)
    suffix = _batch_output_suffix(scopes)
    return output_dir / relative_path.parent / f"{source_path.stem}_{suffix}{source_path.suffix or '.docx'}"


def _batch_item_summary(operation: str, payload: dict, *, output_path: str | None = None) -> dict:
    summary = payload.get("summary") or {}
    verification = payload.get("verification") or {}
    verification_summary = verification.get("summary") or {}
    profile = payload.get("profile") or {}
    if operation == "apply" and verification:
        profile = verification.get("profile") or profile
    item = {
        "profile_id": profile.get("id"),
        "score": payload.get("score"),
        "failed_rules": summary.get("failed_rules"),
        "readiness": _infer_readiness_from_payload(payload),
    }
    if operation == "apply" and verification:
        item["failed_rules"] = verification_summary.get("failed_rules")
        item["overall_status"] = verification.get("overall_status")
    elif "overall_status" in payload:
        item["overall_status"] = payload.get("overall_status")
    elif operation in {"audit", "plan"}:
        item["overall_status"] = "needs_fix" if (summary.get("failed_rules") or 0) > 0 else "verified"
    if output_path is not None:
        item["output_path"] = output_path
    return item


def run_batch_workflow(
    operation: str,
    input_path: str,
    *,
    profile: str = "lnu",
    strict_profile: bool | None = None,
    scopes=None,
    output_dir: str | None = None,
    summary_file: str | None = None,
    pattern: str = "*.docx",
    recursive: bool = False,
    toc: bool = False,
    dry_run: bool = False,
    renumber_headings: bool = False,
    layout_rebalance: bool = False,
    force: bool = False,
    fail_fast: bool = False,
    service_name: str,
    stage: str,
    version: str,
    api_version: str,
) -> dict:
    if operation not in BATCH_OPERATIONS:
        supported = ", ".join(BATCH_OPERATIONS)
        raise RuntimeError(f"Unsupported batch operation: {operation}. Supported operations: {supported}")

    input_root, files = _collect_batch_inputs(input_path, pattern=pattern, recursive=recursive)
    selected_scopes = normalize_scope_names(scopes)
    resolved_output_dir = None
    if operation == "apply":
        resolved_output_dir = Path(output_dir or (input_root / "article-batch-output")).expanduser().resolve()
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict] = []
    counts = {"succeeded": 0, "failed": 0}
    status_counts: dict[str, int] = {}
    readiness_counts: dict[str, int] = {}

    for file_path in files:
        item = {
            "input_path": str(file_path),
            "relative_path": str(file_path.relative_to(input_root)) if file_path.is_relative_to(input_root) else file_path.name,
        }
        try:
            if operation == "audit":
                payload = audit_document(str(file_path), profile_path=profile, strict_profile=strict_profile)
                item.update(_batch_item_summary(operation, payload))
            elif operation == "plan":
                payload = plan_document(str(file_path), profile_path=profile, scopes=scopes, strict_profile=strict_profile)
                item.update(_batch_item_summary(operation, payload))
            elif operation == "verify":
                payload = verify_document(str(file_path), profile_path=profile, scopes=scopes, strict_profile=strict_profile)
                item.update(_batch_item_summary(operation, payload))
            else:
                output_path = _batch_apply_output_path(
                    file_path,
                    input_root=input_root,
                    output_dir=resolved_output_dir,
                    scopes=scopes,
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                payload = apply_fix(
                    str(file_path),
                    output_path=str(output_path),
                    profile_path=profile,
                    scopes=scopes,
                    toc=toc,
                    renumber_headings=renumber_headings,
                    layout_rebalance=layout_rebalance,
                    strict_profile=strict_profile,
                    dry_run=dry_run,
                    force=force,
                )
                item.update(_batch_item_summary(operation, payload, output_path=str(output_path)))
            item["status"] = "succeeded"
            counts["succeeded"] += 1
            overall_status = str(item.get("overall_status") or "unknown")
            status_counts[overall_status] = status_counts.get(overall_status, 0) + 1
            readiness = str(item.get("readiness") or "unknown")
            readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            counts["failed"] += 1
            if fail_fast:
                items.append(item)
                break
        items.append(item)

    payload = {
        "service": service_name,
        "stage": stage,
        "version": version,
        "api_version": api_version,
        "observed_at": _utcnow(),
        "operation": operation,
        "input_root": str(input_root),
        "profile": profile,
        "selected_scopes": sorted(selected_scopes) if selected_scopes else None,
        "output_dir": str(resolved_output_dir) if resolved_output_dir is not None else None,
        "summary": {
            "headline": f"批量 {operation} 完成。",
            "total": len(items),
            "succeeded": counts["succeeded"],
            "failed": counts["failed"],
            "status_counts": status_counts,
            "readiness_counts": readiness_counts,
        },
        "items": items,
    }
    if summary_file:
        payload["summary_file"] = str(_write_json_file(summary_file, payload))
    return payload
