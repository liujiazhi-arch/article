from __future__ import annotations

import argparse
import os
import sys

import audit_thesis
from _profile_utils import list_profile_catalog

from thesis_tool.apply_guard import assess_apply_risk, render_post_verify_notice as _render_post_verify_notice
from thesis_tool.scopes import list_scope_definitions, normalize_scope_names
from thesis_tool.render_verify import build_render_verify_report, render_render_verify_report
from thesis_tool.workflow import (
    apply_scoped_fix,
    build_document_diagnostics,
    build_document_normalize,
    build_document_preflight,
    build_scoped_fix_preview,
    build_scope_plan,
    build_scope_verify,
    render_document_diagnostics_compact,
    render_document_diagnostics,
    render_document_normalize,
    render_document_normalize_compact,
    render_document_preflight,
    render_document_preflight_compact,
    render_scoped_fix_preview,
    render_scope_plan,
    render_scope_verify,
)


def add_profile_args(command_parser, *, default="lnu"):
    command_parser.add_argument("--profile", default=default, help="学校 Profile 路径或简称")
    command_parser.add_argument(
        "--strict-profile",
        dest="strict_profile",
        action="store_true",
        default=None,
        help="profile 加载失败时直接报错，不回退默认配置",
    )
    command_parser.add_argument(
        "--allow-profile-fallback",
        dest="strict_profile",
        action="store_false",
        help="profile 加载失败时回退到默认 LNU 配置",
    )


def build_parser():
    parser = argparse.ArgumentParser(description="论文格式工作台：按 scope 检查和修复论文格式")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="按 scope 生成修复计划")
    plan_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(plan_parser)
    plan_parser.add_argument(
        "--scope",
        action="append",
        default=None,
        help="仅查看指定 scope，可重复传入，或用逗号分隔多个值",
    )

    apply_parser = subparsers.add_parser("apply", help="按 scope 执行修复")
    apply_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(apply_parser)
    apply_parser.add_argument("--output", help="输出 .docx 文件路径")
    apply_parser.add_argument(
        "--scope",
        action="append",
        required=True,
        help="要修复的 scope，可重复传入，或用逗号分隔多个值",
    )
    apply_parser.add_argument("--toc", action="store_true", default=False, help="同时重建目录")
    apply_parser.add_argument("--dry-run", action="store_true", default=False, help="仅预览将触达的修复范围，不写入文件")
    apply_parser.add_argument("--renumber-headings", action="store_true", default=False, help="显式启用正文标题重编号")
    apply_parser.add_argument(
        "--layout-rebalance",
        action="store_true",
        default=False,
        help="显式启用图表跨页排布优化，仅在 figures_tables 范围内生效",
    )
    apply_parser.add_argument("--force", action="store_true", default=False, help="跳过结构风险守卫，强制执行修复")

    audit_parser = subparsers.add_parser("audit", help="执行完整审查")
    audit_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(audit_parser)

    preflight_parser = subparsers.add_parser("preflight", help="对野生文档做预检，先识别结构风险再决定如何修复")
    preflight_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(preflight_parser)
    preflight_parser.add_argument("--compact", action="store_true", default=False, help="输出紧凑摘要，便于批量比较")

    normalize_parser = subparsers.add_parser("normalize", help="先做安全预规整，扶正野生文档骨架再进入修复")
    normalize_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(normalize_parser)
    normalize_parser.add_argument("--output", help="输出 .docx 文件路径")
    normalize_parser.add_argument("--compact", action="store_true", default=False, help="输出紧凑摘要，便于批量比较")

    diagnose_parser = subparsers.add_parser("diagnose", help="输出文档结构诊断，便于定位辽大规则问题")
    diagnose_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(diagnose_parser)
    diagnose_parser.add_argument("--compact", action="store_true", default=False, help="输出紧凑摘要，便于批量比较")

    verify_parser = subparsers.add_parser("verify", help="按 scope 复查修复结果")
    verify_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(verify_parser)
    verify_parser.add_argument(
        "--scope",
        action="append",
        default=None,
        help="仅复查指定 scope，可重复传入，或用逗号分隔多个值",
    )

    subparsers.add_parser("scopes", help="列出可用 scope")
    subparsers.add_parser("profiles", help="列出可用 profile")

    render_verify_parser = subparsers.add_parser("render-verify", help="生成页图证据并输出渲染复核清单")
    render_verify_parser.add_argument("input_docx", help="输入 .docx 文件路径")
    add_profile_args(render_verify_parser)
    render_verify_parser.add_argument("--output-dir", help="页图与 JSON 报告输出目录")
    render_verify_parser.add_argument(
        "--renderer",
        choices=["auto", "word-pdf"],
        default="auto",
        help="渲染引擎：默认 auto，使用 Microsoft Word 导出 PDF；Word 不可用时请手动导出 PDF 后传入 --rendered-pdf",
    )
    render_verify_parser.add_argument(
        "--scope",
        action="append",
        default=None,
        help="可选：按 scope 复用结构复查结论，可重复传入，或用逗号分隔多个值",
    )
    render_verify_parser.add_argument("--rendered-pdf", help="可选：使用用户手动导出的 PDF 作为渲染证据")
    render_verify_parser.add_argument("--page-images-dir", help="可选：使用用户手动导出的 PNG 页图目录作为渲染证据")
    return parser


def default_output_path(input_docx: str, scopes) -> str:
    stem, ext = os.path.splitext(input_docx)
    normalized_scopes = normalize_scope_names(scopes)
    scope_suffix = "_".join(sorted(normalized_scopes or []))
    return f"{stem}_{scope_suffix or '修复'}{ext or '.docx'}"


def _render_apply_risk_warning(diagnostics: dict, *, renumber_headings: bool, selected_scopes: set[str] | None) -> tuple[list[str], bool]:
    assessment = assess_apply_risk(
        diagnostics,
        renumber_headings=renumber_headings,
        selected_scopes=selected_scopes,
    )
    lines: list[str] = []

    if assessment.has_table_heading_risk:
        lines.append(
            f"  - 表格伪标题候选: {assessment.table_heading_risk_count} "
            f"个（阈值 {assessment.table_heading_risk_threshold}）"
        )
        lines.append("建议: 先运行 preflight 核对表格内容，避免化合物名或数值误入标题重编号链。")

    if assessment.has_style_text_conflict:
        lines.append(f"  - 样式/文本层级冲突: {assessment.style_text_conflict_count} 个")
        if assessment.affects_heading_renumber:
            lines.append("建议: 先检查 headings 相关冲突，再执行 --renumber-headings。")
        else:
            lines.append("建议: 可先运行 preflight 查看冲突详情，必要时再处理 headings scope。")

    return lines, assessment.should_block


def main():
    parser = build_parser()
    try:
        args = parser.parse_args()

        if args.command == "scopes":
            for scope in list_scope_definitions():
                print(f"{scope.id}: {scope.title} - {scope.description}")
            return 0

        if args.command == "profiles":
            for entry in list_profile_catalog():
                alias_text = ", ".join(entry["aliases"]) if entry["aliases"] else "—"
                path_text = entry["path"] or "built-in"
                school_text = entry["school"] or "通用"
                support_level_text = entry.get("support_level_label") or "—"
                scenario_parts = []
                for scenario in entry.get("support_scenarios") or []:
                    doc_types = "、".join(scenario.get("document_types") or [])
                    if doc_types:
                        scenario_parts.append(f"{scenario['label']}[{doc_types}]/{scenario.get('support_level_label') or support_level_text}")
                    else:
                        scenario_parts.append(f"{scenario['label']}/{scenario.get('support_level_label') or support_level_text}")
                scenario_text = "；".join(scenario_parts) if scenario_parts else "—"
                print(
                    f"{entry['id']}: aliases={alias_text}; school={school_text}; "
                    f"support={support_level_text}; scenarios={scenario_text}; path={path_text}"
                )
            return 0

        if args.command == "audit":
            results, score, _report, runtime = audit_thesis.audit_docx_with_runtime(
                args.input_docx,
                profile_path=args.profile,
                strict_profile=args.strict_profile,
            )
            failed = [item for item in results if not item.get("passed")]
            print(f"文件: {os.path.basename(args.input_docx)}")
            print(
                "Profile: "
                + audit_thesis.format_profile_resolution(
                    runtime.profile_id,
                    runtime.requested_profile,
                    runtime.fallback_used,
                )
            )
            print(f"评分: {score}/100")
            print(f"未通过规则: {len(failed)}")
            for result in failed:
                print(f"- {result['id']} {result['name']}")
            return 0

        if args.command == "preflight":
            preflight = build_document_preflight(
                args.input_docx,
                profile_path=args.profile,
                strict_profile=args.strict_profile,
            )
            if args.compact:
                print(render_document_preflight_compact(preflight))
            else:
                print(render_document_preflight(preflight))
            return 0

        if args.command == "normalize":
            normalize = build_document_normalize(
                args.input_docx,
                output_path=args.output,
                profile_path=args.profile,
                strict_profile=args.strict_profile,
            )
            if args.compact:
                print(render_document_normalize_compact(normalize))
            else:
                print(render_document_normalize(normalize))
            return 0

        if args.command == "diagnose":
            diagnostics = build_document_diagnostics(
                args.input_docx,
                profile_path=args.profile,
                strict_profile=args.strict_profile,
            )
            if args.compact:
                print(render_document_diagnostics_compact(diagnostics))
            else:
                print(render_document_diagnostics(diagnostics))
            return 0

        if args.command == "plan":
            plan = build_scope_plan(
                args.input_docx,
                profile_path=args.profile,
                scopes=args.scope,
                strict_profile=args.strict_profile,
            )
            print(render_scope_plan(plan))
            return 0

        if args.command == "apply":
            selected_scopes = normalize_scope_names(args.scope)
            output_path = args.output or default_output_path(args.input_docx, args.scope)
            if args.dry_run:
                preview = build_scoped_fix_preview(
                    args.input_docx,
                    output_path=output_path,
                    profile_path=args.profile,
                    scopes=args.scope,
                    toc=args.toc,
                    renumber_headings=args.renumber_headings,
                    layout_rebalance=args.layout_rebalance,
                    strict_profile=args.strict_profile,
                )
                print(render_scoped_fix_preview(preview))
                return 0
            if not args.force:
                diagnostics = build_document_diagnostics(
                    args.input_docx,
                    profile_path=args.profile,
                    strict_profile=args.strict_profile,
                )
                warning_lines, should_block = _render_apply_risk_warning(
                    diagnostics,
                    renumber_headings=args.renumber_headings,
                    selected_scopes=selected_scopes,
                )
                if warning_lines:
                    print("[警告] 发现结构风险：")
                    for line in warning_lines:
                        print(line)
                if should_block:
                    print("如需跳过此检查，请传入 --force 参数。")
                    return 1
            fixed_path = apply_scoped_fix(
                args.input_docx,
                output_path,
                profile_path=args.profile,
                scopes=args.scope,
                toc=args.toc,
                renumber_headings=args.renumber_headings,
                layout_rebalance=args.layout_rebalance,
                strict_profile=args.strict_profile,
            )
            verification = build_scope_verify(
                fixed_path,
                profile_path=args.profile,
                scopes=args.scope,
                strict_profile=args.strict_profile,
            )
            print(f"输出文件: {fixed_path}")
            print(render_scope_verify(verification))
            for line in _render_post_verify_notice(verification):
                print(line)
            if args.toc:
                print("提示: 目录为 Word 域，若页码未刷新，请在 Word 中 Ctrl+A 后按 F9 更新。")
            return 0

        if args.command == "verify":
            verification = build_scope_verify(
                args.input_docx,
                profile_path=args.profile,
                scopes=args.scope,
                strict_profile=args.strict_profile,
            )
            print(render_scope_verify(verification))
            for line in _render_post_verify_notice(verification):
                print(line)
            return 0

        if args.command == "render-verify":
            report = build_render_verify_report(
                args.input_docx,
                output_dir=args.output_dir,
                profile_path=args.profile,
                scopes=args.scope,
                strict_profile=args.strict_profile,
                renderer=args.renderer,
                rendered_pdf=args.rendered_pdf,
                page_images_dir=args.page_images_dir,
            )
            print(render_render_verify_report(report))
            return 0

        parser.error(f"未知命令: {args.command}")
        return 2
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    sys.exit(main())
