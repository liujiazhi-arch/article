import os
from dataclasses import dataclass


PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "profiles")
PROFILE_ALIASES = {
    "cn-common": None,
    "cn_common": None,
    "ams": os.path.join(PROFILE_DIR, "ams-graduate.yaml"),
    "lnu": os.path.join(PROFILE_DIR, "lnu-undergraduate.yaml"),
    "lnu-undergraduate": os.path.join(PROFILE_DIR, "lnu-undergraduate.yaml"),
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


def load_profile_bundle(profile_path, yaml_lib=None, warn=None, aliases=None, strict=False):
    aliases = PROFILE_ALIASES if aliases is None else aliases
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
