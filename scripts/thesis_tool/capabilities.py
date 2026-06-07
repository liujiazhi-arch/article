from __future__ import annotations

from functools import lru_cache

from thesis_resources import config_path


Capability = dict[str, str]

CAPABILITY_MATRIX_PATH = config_path("capability_matrix.md")


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


@lru_cache(maxsize=1)
def load_rule_capabilities() -> dict[str, Capability]:
    capabilities: dict[str, Capability] = {}
    if not CAPABILITY_MATRIX_PATH.is_file():
        return capabilities

    for raw_line in CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) != 6:
            continue
        if cells[0] in {"ID", "----"}:
            continue
        rule_id = cells[0]
        if not rule_id or rule_id == "—":
            continue
        capabilities[rule_id] = {
            "description": cells[1],
            "check_level": cells[2],
            "method": cells[3],
            "autofix": cells[4],
            "implemented": cells[5],
        }
    return capabilities


def classify_rule_action(rule_id: str) -> str:
    capability = load_rule_capabilities().get(rule_id)
    if capability is None:
        return "unknown"

    autofix = capability.get("autofix")
    check_level = capability.get("check_level")
    if autofix == "✓":
        return "autofix"
    if check_level in {"Semi", "Manual"}:
        return "manual_review"
    return "unsupported"
