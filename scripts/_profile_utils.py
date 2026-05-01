import os
from pathlib import Path
from dataclasses import dataclass
import yaml


PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "profiles")
PROFILE_ALIASES = {
    "cn-common": None,
    "cn_common": None,
    "lnu": os.path.join(PROFILE_DIR, "lnu-checker-2026.yaml"),
    "lnu-checker-2026": os.path.join(PROFILE_DIR, "lnu-checker-2026.yaml"),
    "lnu-checker": os.path.join(PROFILE_DIR, "lnu-checker-2026.yaml"),
}

_DEFAULT_SUPPORT_LEVEL = {
    "id": "primary",
    "label": "一等支持",
}


@dataclass(frozen=True)
class ProfileBundle:
    profile_id: str
    profile_data: dict
    settings: dict
    normalized: str
    alias_key: str
    resolved_path: str | None
    fallback_used: bool = False
    requested_profile: str | None = None
    warning_message: str | None = None


def _make_fallback_bundle(normalized, alias_key, resolved_path, warning_message):
    return ProfileBundle(
        profile_id="cn-common",
        profile_data={},
        settings={},
        normalized=normalized,
        alias_key=alias_key,
        resolved_path=resolved_path,
        fallback_used=True,
        requested_profile=normalized or None,
        warning_message=warning_message,
    )


def _strict_message(fallback_message):
    return fallback_message.replace("，已回落到默认 CN-Common 配置。", "，strict-profile 已启用，停止执行。")


def format_profile_resolution(profile_id, requested_profile=None, fallback_used=False):
    requested = str(requested_profile).strip() if requested_profile else ""
    details = []
    if requested and requested != profile_id:
        details.append(f"requested: {requested}")
    if fallback_used:
        details.append("fallback: cn-common")
    if not details:
        return profile_id
    return f"{profile_id} ({'; '.join(details)})"


def resolve_strict_profile(profile_path, strict):
    if strict is not None:
        return bool(strict)
    return bool(str(profile_path).strip()) if profile_path is not None else False


def load_profile_bundle(profile_path, yaml_lib=None, warn=None, aliases=None, strict=None):
    aliases = PROFILE_ALIASES if aliases is None else aliases
    strict = resolve_strict_profile(profile_path, strict)
    if not profile_path:
        return ProfileBundle("cn-common", {}, {}, "", "cn-common", None, requested_profile=None)

    normalized = str(profile_path).strip()
    alias_key = normalized.lower()
    if alias_key in ("cn-common", "cn_common"):
        return ProfileBundle("cn-common", {}, {}, normalized, alias_key, aliases.get(alias_key), requested_profile=normalized)

    resolved_path = aliases.get(alias_key, os.path.expanduser(normalized))
    if yaml_lib is None:
        message = "PyYAML 不可用，已回落到默认 CN-Common 配置。"
        if strict:
            raise ValueError(_strict_message(message))
        if warn is not None:
            warn(message)
        return _make_fallback_bundle(normalized, alias_key, resolved_path, message)

    try:
        with open(resolved_path, "r", encoding="utf-8") as handle:
            profile_data = yaml_lib.safe_load(handle) or {}
    except Exception as exc:
        message = f"Profile 加载失败：{normalized}（{exc}），已回落到默认 CN-Common 配置。"
        if strict:
            raise ValueError(_strict_message(message))
        if warn is not None:
            warn(message)
        return _make_fallback_bundle(normalized, alias_key, resolved_path, message)

    profile_id = str((profile_data.get("meta") or {}).get("id") or "").strip()
    if not profile_id:
        message = f"Profile 缺少 meta.id：{normalized}，已回落到默认 CN-Common 配置。"
        if strict:
            raise ValueError(_strict_message(message))
        if warn is not None:
            warn(message)
        return _make_fallback_bundle(normalized, alias_key, resolved_path, message)

    return ProfileBundle(
        profile_id=profile_id,
        profile_data=profile_data,
        settings=profile_data.get("settings") or {},
        normalized=normalized,
        alias_key=alias_key,
        resolved_path=resolved_path,
        requested_profile=normalized,
    )


def resolve_template_profile_id(profile_path, resolved_profile_id="", aliases=None):
    aliases = PROFILE_ALIASES if aliases is None else aliases
    if not profile_path:
        return resolved_profile_id or "cn-common"

    normalized = str(profile_path).strip()
    alias_key = normalized.lower()
    if alias_key in ("cn-common", "cn_common"):
        return "cn-common"

    resolved_path = aliases.get(alias_key)
    if resolved_path in (None, ""):
        expanded = os.path.abspath(os.path.expanduser(normalized))
        for candidate_alias, candidate_path in aliases.items():
            if candidate_path and os.path.abspath(candidate_path) == expanded:
                resolved_path = candidate_path
                break
    if resolved_path:
        candidate_aliases = [
            candidate_alias
            for candidate_alias, candidate_path in aliases.items()
            if candidate_alias and candidate_path == resolved_path
        ]
        if candidate_aliases:
            return sorted(candidate_aliases, key=lambda item: (len(item), item))[0]
    return alias_key or resolved_profile_id or "cn-common"


def _load_catalog_meta(profile_path: Path, yaml_lib) -> dict:
    with profile_path.open("r", encoding="utf-8") as handle:
        profile_data = yaml_lib.safe_load(handle) or {}
    meta = profile_data.get("meta") or {}
    return {
        "profile_data": profile_data,
        "meta": meta,
        "profile_id": str(meta.get("id") or profile_path.stem).strip(),
    }


def _normalize_support_level(raw_level) -> dict:
    if isinstance(raw_level, dict):
        level_id = str(raw_level.get("id") or _DEFAULT_SUPPORT_LEVEL["id"]).strip() or _DEFAULT_SUPPORT_LEVEL["id"]
        label = str(raw_level.get("label") or _DEFAULT_SUPPORT_LEVEL["label"]).strip() or _DEFAULT_SUPPORT_LEVEL["label"]
        return {"id": level_id, "label": label}
    if raw_level:
        normalized = str(raw_level).strip()
        if normalized:
            return {"id": normalized, "label": _DEFAULT_SUPPORT_LEVEL["label"] if normalized == "primary" else normalized}
    return dict(_DEFAULT_SUPPORT_LEVEL)


def _normalize_support_scenarios(meta: dict) -> tuple[list[dict], list[str], dict]:
    catalog_meta = meta.get("catalog") or {}
    raw_scenarios = catalog_meta.get("support_scenarios") or []
    support_scenarios: list[dict] = []
    document_types: list[str] = []
    support_level = _normalize_support_level(catalog_meta.get("support_level"))

    for raw_item in raw_scenarios:
        if not isinstance(raw_item, dict):
            continue
        scenario_id = str(raw_item.get("id") or "").strip()
        label = str(raw_item.get("label") or "").strip()
        if not scenario_id or not label:
            continue
        scenario_level = _normalize_support_level(raw_item.get("support_level") or support_level)
        scenario_document_types: list[str] = []
        for raw_doc_type in raw_item.get("document_types") or []:
            doc_type = str(raw_doc_type).strip()
            if not doc_type:
                continue
            scenario_document_types.append(doc_type)
            if doc_type not in document_types:
                document_types.append(doc_type)
        support_scenarios.append(
            {
                "id": scenario_id,
                "label": label,
                "document_types": scenario_document_types,
                "support_level": scenario_level["id"],
                "support_level_label": scenario_level["label"],
            }
        )

    if support_scenarios and not document_types:
        document_types = sorted({scenario["label"] for scenario in support_scenarios})

    return support_scenarios, document_types, support_level


def _build_catalog_entry(*, profile_id: str, aliases: list[str], path: str | None, meta: dict, is_default: bool) -> dict:
    support_scenarios, document_types, support_level = _normalize_support_scenarios(meta)
    return {
        "id": profile_id,
        "aliases": aliases,
        "path": path,
        "school": meta.get("school"),
        "full_name": meta.get("full_name"),
        "is_default": is_default,
        "support_level": support_level["id"],
        "support_level_label": support_level["label"],
        "document_types": document_types,
        "support_scenarios": support_scenarios,
    }


def list_profile_catalog(aliases=None, yaml_lib=None):
    aliases = PROFILE_ALIASES if aliases is None else aliases
    yaml_lib = yaml if yaml_lib is None else yaml_lib
    profile_dir = Path(PROFILE_DIR)
    default_profile_meta = _load_catalog_meta(profile_dir / "CN-Common.yaml", yaml_lib)["meta"]
    entries: list[dict] = [
        _build_catalog_entry(
            profile_id="cn-common",
            aliases=["cn-common", "cn_common"],
            path=None,
            meta=default_profile_meta,
            is_default=True,
        )
    ]

    for profile_path in sorted(profile_dir.glob("*.yaml")):
        loaded = _load_catalog_meta(profile_path, yaml_lib)
        meta = loaded["meta"]
        profile_id = loaded["profile_id"]
        if profile_id.lower() == "cn-common":
            continue
        entry_aliases = sorted(
            {
                alias
                for alias, candidate_path in aliases.items()
                if candidate_path and os.path.abspath(candidate_path) == str(profile_path.resolve())
            }
        )
        entries.append(
            _build_catalog_entry(
                profile_id=profile_id,
                aliases=entry_aliases,
                path=str(profile_path.resolve()),
                meta=meta,
                is_default=False,
            )
        )

    entries.sort(key=lambda item: (item["is_default"] is False, item["id"]))
    return entries
