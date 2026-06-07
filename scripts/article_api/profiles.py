from __future__ import annotations

from datetime import datetime, timezone

from _profile_utils import DEFAULT_PROFILE_ID, list_public_profile_catalog


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    profiles = list_public_profile_catalog()
    support_scenarios = _catalog_support_summary(profiles)
    return {
        "service": service_name,
        "stage": stage,
        "version": version,
        "api_version": api_version,
        "observed_at": _utcnow(),
        "summary": {
            "profile_count": len(profiles),
            "default_profile_id": DEFAULT_PROFILE_ID,
            "support_scenario_count": len(support_scenarios),
            "support_scenarios": support_scenarios,
        },
        "profiles": profiles,
    }
