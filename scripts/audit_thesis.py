import argparse
import datetime
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

try:
    import yaml
except ImportError:
    yaml = None

from _profile_utils import DEFAULT_PROFILE_ID, PROFILE_ALIASES, format_profile_resolution, load_profile_bundle
from _thesis_utils import build_style_map
import thesis_rules.audit_checkers as _audit_checkers
import thesis_rules.audit_common as _audit_common
import thesis_rules.audit_lnu as _audit_lnu
from thesis_rules.audit_checkers import *  # re-export legacy checker helpers
from thesis_rules.audit_common import *  # re-export legacy common checkers
from thesis_rules.audit_lnu import *  # re-export legacy LNU checkers
from thesis_rules.lnu_runtime import effective_lnu_rule_definitions

class DocumentRootProxy:
    def __init__(self, root, zip_path=None):
        self._root = root
        self._zip_path = zip_path

    def __getattr__(self, name):
        return getattr(self._root, name)

    def __iter__(self):
        return iter(self._root)


@dataclass(frozen=True)
class AuditRuntime:
    cfg: dict
    rule_definitions: tuple[tuple[str, str, str], ...]
    rule_checkers: dict
    profile_id: str
    requested_profile: str | None = None
    fallback_used: bool = False
    warning_message: str | None = None


_PATCHABLE_AUDIT_CHECKER_DEPS = (
    "build_document_model",
    "build_document_sections",
    "build_style_map",
    "collect_figure_blocks",
    "collect_table_blocks",
)


def _sync_patchable_checker_deps() -> None:
    for name in _PATCHABLE_AUDIT_CHECKER_DEPS:
        if name in globals():
            setattr(_audit_checkers, name, globals()[name])
            setattr(_audit_common, name, globals()[name])
            setattr(_audit_lnu, name, globals()[name])


def _legacy_checker_wrapper(checker):
    def wrapped(*args, **kwargs):
        _sync_patchable_checker_deps()
        return checker(*args, **kwargs)

    wrapped.__name__ = checker.__name__
    wrapped.__doc__ = checker.__doc__
    return wrapped


for _name, _checker in list(globals().items()):
    if _name.startswith("check_") and callable(_checker):
        globals()[_name] = _legacy_checker_wrapper(_checker)
del _name, _checker

def build_rule_definitions(profile_id, disabled_rules=()):
    if profile_id.startswith("lnu-"):
        return effective_lnu_rule_definitions()
    rule_definitions = list(RULE_DEFINITIONS)
    disabled = set(disabled_rules or ())
    if disabled:
        rule_definitions = [rule for rule in rule_definitions if rule[0] not in disabled]
    return tuple(rule_definitions)


def build_rule_checkers(profile_id, disabled_rules=()):
    rule_checkers = dict(RULE_CHECKERS)
    if profile_id.startswith("lnu-"):
        rule_checkers.update(LNU_RULE_CHECKERS)
    for rule_id in set(disabled_rules or ()):
        rule_checkers.pop(rule_id, None)
    return rule_checkers


def build_audit_runtime(profile_path=None, strict_profile=None):
    bundle = load_profile_bundle(
        profile_path,
        yaml_lib=yaml,
        warn=warn_profile,
        aliases=PROFILE_ALIASES,
        strict=strict_profile,
    )
    profile_id, profile_data, settings = bundle.profile_id, bundle.profile_data, bundle.settings
    cfg = build_profile_cfg(profile_id, profile_data, settings)
    disabled_rules = profile_data.get("disabled_rules") or []
    return AuditRuntime(
        cfg=cfg,
        rule_definitions=build_rule_definitions(profile_id, disabled_rules),
        rule_checkers=build_rule_checkers(profile_id, disabled_rules),
        profile_id=profile_id,
        requested_profile=bundle.requested_profile,
        fallback_used=bundle.fallback_used,
    )


def load_profile(profile_path):
    runtime = build_audit_runtime(profile_path)
    return runtime.cfg


def calculate_score(results):
    score = 100
    for result in results:
        if not result["passed"]:
            score -= SEVERITY_SCORES[result["severity"]]
    return max(score, 0)


def generate_markdown_report(file_path, results, score):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 📋 论文格式审查报告",
        "",
        f"**文件**：{os.path.basename(file_path)}",
        f"**审查时间**：{timestamp}",
        f"**总评分**：{score}/100",
        "",
        "---",
        "",
    ]

    for severity in ("critical", "important", "minor"):
        failed = [result for result in results if result["severity"] == severity and not result["passed"]]
        title = SEVERITY_LABELS[severity]
        suffix = {
            "critical": "必须修复",
            "important": "建议修复",
            "minor": "",
        }[severity]
        header = f"## ❌ {title}{len(failed)}项" if severity == "critical" else (
            f"## ⚠️ {title}{len(failed)}项" if severity == "important" else f"## ℹ️ {title}{len(failed)}项"
        )
        if suffix:
            header += f" — {suffix}"
        lines.append(header)
        lines.append("")
        if failed:
            lines.append("| 规则ID | 规则名称 | 问题描述 | 受影响位置 |")
            lines.append("|--------|---------|---------|-----------|")
            for result in failed:
                description = "；".join([markdown_escape(issue) for issue in result["issues"]]) or "未通过"
                lines.append(
                    f"| {result['id']} | {markdown_escape(result['name'])} | {description} | {markdown_escape(result['affected'])} |"
                )
        else:
            lines.append("无")
        lines.append("")

    passed_ids = [result["id"] for result in results if result["passed"]]
    lines.append(f"## ✅ 通过的规则（{len(passed_ids)}/{len(results)}）")
    lines.append(" | ".join([f"{result['id']} ✓" for result in results if result["passed"]]) or "无")
    lines.append("")
    lines.append("---")
    lines.append("*推荐使用 `scripts/thesis_workbench.py plan/apply/verify` 处理问题；底层引擎可直接调用 `fix_thesis.py`。*")
    lines.append("")
    return "\n".join(lines)


def audit_roots(file_path, document_root, styles_root, footnotes_root=None, cfg=None, runtime=None):
    if runtime is None:
        runtime = AuditRuntime(
            cfg=clone_default_cfg() if cfg is None else cfg,
            rule_definitions=tuple(RULE_DEFINITIONS),
            rule_checkers=dict(RULE_CHECKERS),
            profile_id=DEFAULT_PROFILE_ID,
        )
    cfg = runtime.cfg if cfg is None else cfg
    style_map = build_style_map(styles_root)
    contexts = build_paragraph_contexts(document_root, style_map)
    results = []
    for rule_id, rule_name, severity in runtime.rule_definitions:
        if rule_id == "FN01":
            passed, issues, affected = runtime.rule_checkers[rule_id](document_root, contexts, style_map, cfg, footnotes_root)
        else:
            passed, issues, affected = runtime.rule_checkers[rule_id](document_root, contexts, style_map, cfg)
        results.append(make_result(rule_id, rule_name, severity, passed, issues, affected))
    score = calculate_score(results)
    report = generate_markdown_report(file_path, results, score)
    return results, score, report


def audit_docx_with_runtime(file_path, profile_path=None, strict_profile=None):
    runtime = build_audit_runtime(profile_path, strict_profile=strict_profile)
    document_xml, styles_xml, footnotes_xml = load_docx_xml(file_path)
    document_root = ET.fromstring(document_xml)
    document_root = DocumentRootProxy(document_root, file_path)
    styles_root = ET.fromstring(styles_xml)
    footnotes_root = ET.fromstring(footnotes_xml) if footnotes_xml else None
    results, score, report = audit_roots(
        file_path,
        document_root,
        styles_root,
        footnotes_root=footnotes_root,
        cfg=runtime.cfg,
        runtime=runtime,
    )
    return results, score, report, runtime


def audit_docx(file_path, profile_path=None, strict_profile=None):
    results, score, report, _runtime = audit_docx_with_runtime(
        file_path,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    return results, score, report


def main():
    parser = argparse.ArgumentParser(description="审查 DOCX 论文格式")
    parser.add_argument("file", help="待审查的 .docx 文件路径")
    parser.add_argument("--profile", default=None, help="学校Profile路径或简称（默认 lnu）")
    parser.add_argument(
        "--strict-profile",
        dest="strict_profile",
        action="store_true",
        default=None,
        help="profile 加载失败时直接报错，不回退默认配置",
    )
    parser.add_argument(
        "--allow-profile-fallback",
        dest="strict_profile",
        action="store_false",
        help="profile 加载失败时回退到默认 LNU 配置",
    )
    args = parser.parse_args()

    try:
        results, score, report, runtime = audit_docx_with_runtime(
            args.file,
            profile_path=args.profile,
            strict_profile=args.strict_profile,
        )
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")
    failed = [result for result in results if not result.get("passed")]
    print(f"文件: {os.path.basename(args.file)}")
    print(f"Profile: {format_profile_resolution(runtime.profile_id, runtime.requested_profile, runtime.fallback_used)}")
    print(f"评分: {score}/100")
    print(f"未通过规则: {len(failed)}")
    if failed:
        for result in failed:
            print(f"- {result['id']} {result['name']}")


if __name__ == "__main__":
    main()
