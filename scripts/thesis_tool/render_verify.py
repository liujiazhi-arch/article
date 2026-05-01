from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import audit_thesis

from thesis_tool.workflow import build_document_diagnostics, build_scope_verify


_RENDER_DOCX_SCRIPT_GLOBS = [
    "~/.codex/plugins/cache/openai-primary-runtime/documents/*/skills/documents/render_docx.py",
]
_RENDER_PYTHON_GLOBS = [
    "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
    "~/.cache/codex-runtimes/codex-primary-runtime-*/dependencies/python/bin/python3",
]


def find_render_docx_script() -> str:
    env_path = os.environ.get("ARTICLE_RENDER_DOCX_SCRIPT")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)

    for pattern in _RENDER_DOCX_SCRIPT_GLOBS:
        for candidate in sorted(glob.glob(os.path.expanduser(pattern))):
            resolved = Path(candidate).expanduser().resolve()
            if resolved.exists():
                return str(resolved)

    raise RuntimeError(
        "未找到 render_docx.py。请确认当前 Codex 文档运行时已安装，"
        "或通过 ARTICLE_RENDER_DOCX_SCRIPT 指定渲染脚本路径。"
    )


def default_render_output_dir(input_docx: str) -> str:
    source = Path(input_docx).expanduser().resolve()
    return str(source.with_name(f"{source.stem}_render_verify"))


def find_render_python() -> str:
    env_path = os.environ.get("ARTICLE_RENDER_PYTHON")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if resolved.exists():
            return str(resolved)

    for pattern in _RENDER_PYTHON_GLOBS:
        for candidate in sorted(glob.glob(os.path.expanduser(pattern))):
            resolved = Path(candidate).expanduser().resolve()
            if resolved.exists():
                return str(resolved)

    return sys.executable


def _page_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"page-(\d+)\.png$", path.name)
    if match:
        return int(match.group(1)), path.name
    return sys.maxsize, path.name


def _collect_page_images(output_dir: str | Path) -> list[str]:
    directory = Path(output_dir).expanduser().resolve()
    return [str(path) for path in sorted(directory.glob("page-*.png"), key=_page_sort_key)]


def _run_render_docx(input_docx: str, output_dir: str) -> None:
    script_path = find_render_docx_script()
    python_path = find_render_python()
    command = [
        python_path,
        script_path,
        input_docx,
        "--output_dir",
        output_dir,
        "--renderer",
        "artifact-tool",
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        message = "DOCX 渲染失败。"
        if details:
            message = f"{message}\n{details}"
        raise RuntimeError(message) from exc


def _build_render_review_items(diagnostics: dict, verification: dict) -> list[str]:
    items = [
        "逐页检查是否出现异常大块空白、孤页或空白段。",
        "逐页检查图表是否与题注分离，是否被挤到单独页面。",
        "逐页检查公式区域是否出现粗横线、编号偏移或解释项错位。",
    ]

    toc_status = str((diagnostics.get("toc") or {}).get("status") or "")
    if toc_status in {"field_only", "generated_toc"}:
        items.append("目录可能仍需在 Word/WPS 中 Ctrl+A 后按 F9 刷新，再复核页码与缩进。")
    elif toc_status in {"manual_toc", "duplicate_toc", "no_toc"}:
        items.append("目录结构当前不稳定，重点复核目录页码、层级和是否需要自动目录。")

    guard_status = str((diagnostics.get("heading_renumber_guard") or {}).get("status") or "")
    if guard_status == "warn":
        items.append("标题链附近存在表格伪标题风险，重点查看章节编号是否误伤表内内容。")
    elif guard_status == "block":
        items.append("标题样式/文本层级冲突仍存在，重点查看标题层级与分页是否自然。")

    manual_review_rule_ids = verification.get("manual_review_rule_ids") or []
    unsupported_rule_ids = verification.get("unsupported_rule_ids") or []
    if manual_review_rule_ids:
        items.append(f"除页图外，还需人工确认规则: {', '.join(manual_review_rule_ids)}。")
    if unsupported_rule_ids:
        items.append(f"当前仍有未自动闭环规则: {', '.join(unsupported_rule_ids)}。")

    return items


def build_render_verify_report(
    input_docx: str,
    *,
    output_dir: str | None = None,
    profile_path: str | None = None,
    scopes=None,
    strict_profile: bool | None = None,
) -> dict:
    validated_input = audit_thesis.validate_docx_path(input_docx)
    resolved_output_dir = Path(output_dir or default_render_output_dir(validated_input)).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    _run_render_docx(validated_input, str(resolved_output_dir))
    page_images = _collect_page_images(resolved_output_dir)
    if not page_images:
        raise RuntimeError(f"渲染未产出页图: {resolved_output_dir}")

    diagnostics = build_document_diagnostics(
        validated_input,
        profile_path=profile_path,
        strict_profile=strict_profile,
    )
    verification = build_scope_verify(
        validated_input,
        profile_path=profile_path,
        scopes=scopes,
        strict_profile=strict_profile,
    )
    report = {
        "document": {
            "path": str(Path(validated_input)),
            "name": Path(validated_input).name,
        },
        "profile": {
            "id": verification.get("profile_id"),
            "requested": verification.get("requested_profile", profile_path),
            "fallback_used": bool(verification.get("fallback_used")),
            "display": verification.get("profile_display"),
        },
        "output_dir": str(resolved_output_dir),
        "render_engine": "artifact-tool",
        "page_count": len(page_images),
        "page_images": page_images,
        "selected_scopes": verification.get("selected_scopes"),
        "overall_status": verification.get("overall_status"),
        "readiness": verification.get("readiness"),
        "manual_review_rule_ids": list(verification.get("manual_review_rule_ids") or []),
        "unsupported_rule_ids": list(verification.get("unsupported_rule_ids") or []),
        "review_items": _build_render_review_items(diagnostics, verification),
        "report_path": str(resolved_output_dir / "render_verify_report.json"),
    }
    Path(report["report_path"]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def render_render_verify_report(report: dict) -> str:
    lines = [
        f"文件: {report['document']['name']}",
        f"Profile: {report['profile'].get('display') or report['profile'].get('id') or 'default'}",
        f"结构状态: {report.get('overall_status')}",
        f"可提交状态: {report.get('readiness')}",
        f"渲染证据目录: {report['output_dir']}",
        f"生成页图: {report['page_count']} 页",
        f"报告文件: {report['report_path']}",
    ]
    selected_scopes = report.get("selected_scopes")
    if selected_scopes:
        lines.append(f"复核范围: {', '.join(selected_scopes)}")

    lines.append("")
    lines.append("复核清单：")
    for item in report.get("review_items") or []:
        lines.append(f"- {item}")
    return "\n".join(lines)
