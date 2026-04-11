from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
INDEX_DIR = OUTPUTS_DIR / "index"
MILESTONES_DIR = OUTPUTS_DIR / "milestones"
MANIFEST_PATH = INDEX_DIR / "最新产物索引.md"
MILESTONE_LOG_PATH = INDEX_DIR / "里程碑记录.md"
SKIP_NAMES = {".DS_Store", ".gitkeep", "README.md"}
SKIP_DIRS = {"index", "milestones"}


@dataclass
class OutputEntry:
    rel_path: str
    size_bytes: int
    modified_at: datetime


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def collect_output_entries(outputs_dir: Path = OUTPUTS_DIR) -> list[OutputEntry]:
    entries: list[OutputEntry] = []
    base_dir = outputs_dir.parent
    for path in sorted(outputs_dir.iterdir()):
        if path.name in SKIP_NAMES:
            continue
        if path.is_dir() and path.name in SKIP_DIRS:
            continue
        if not path.is_file():
            continue
        stat = path.stat()
        entries.append(
            OutputEntry(
                rel_path=path.relative_to(base_dir).as_posix(),
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    return entries


def render_manifest(entries: list[OutputEntry], generated_at: datetime | None = None) -> str:
    generated = generated_at or datetime.now()
    lines = [
        "# 最新产物索引",
        "",
        f"- 生成时间：{generated.strftime('%Y-%m-%d %H:%M:%S')}",
        "- 范围：`outputs/` 根目录中的当前工作产物",
        "- 说明：这些文件默认仍留在本地，不自动进入 Git 主历史",
        "",
    ]

    if not entries:
        lines.extend(["当前没有可索引的工作产物。", ""])
        return "\n".join(lines)

    lines.extend(["## 当前产物", ""])
    for entry in entries:
        lines.append(
            f"- `{entry.rel_path}` | {format_size(entry.size_bytes)} | "
            f"{entry.modified_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    lines.extend(
        [
            "",
            "## 使用建议",
            "",
            "- 普通中间产物继续留在 `outputs/` 根目录",
            "- 需要让 Git 看见当前结果时，更新本索引文件",
            "- 需要长期追踪的关键结果，再提升到 `outputs/milestones/`",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(manifest_path: Path = MANIFEST_PATH) -> Path:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    content = render_manifest(collect_output_entries())
    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


def append_milestone_record(relative_target: str, note: str) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    if MILESTONE_LOG_PATH.exists():
        content = MILESTONE_LOG_PATH.read_text(encoding="utf-8").rstrip()
    else:
        content = "# 里程碑记录"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- {timestamp} | `{relative_target}` | {note or '未填写说明'}"
    MILESTONE_LOG_PATH.write_text(f"{content}\n\n{entry}\n", encoding="utf-8")


def promote_output(source: str, note: str = "", force: bool = False) -> Path:
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path
    source_path = source_path.resolve()

    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"未找到输出文件：{source_path}")
    if OUTPUTS_DIR not in source_path.parents:
        raise ValueError("只能提升 outputs 目录下的文件")
    if source_path.parent.name in SKIP_DIRS:
        raise ValueError("索引目录或里程碑目录下的文件不能再次提升")

    MILESTONES_DIR.mkdir(parents=True, exist_ok=True)
    target_path = MILESTONES_DIR / source_path.name
    if target_path.exists() and not force:
        raise FileExistsError(f"里程碑文件已存在：{target_path}")

    shutil.copy2(source_path, target_path)
    append_milestone_record(target_path.relative_to(PROJECT_ROOT).as_posix(), note)
    write_manifest()
    return target_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 outputs 的可追踪索引和里程碑产物")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("manifest", help="刷新 outputs/index/最新产物索引.md")

    promote_parser = subparsers.add_parser("promote", help="将某个输出产物提升为里程碑")
    promote_parser.add_argument("source", help="待提升文件，支持相对项目根目录路径")
    promote_parser.add_argument("--note", default="", help="本次提升的用途说明")
    promote_parser.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "manifest":
        path = write_manifest()
        print(path.relative_to(PROJECT_ROOT).as_posix())
        return 0
    if args.command == "promote":
        path = promote_output(args.source, note=args.note, force=args.force)
        print(path.relative_to(PROJECT_ROOT).as_posix())
        return 0
    parser.error("未知命令")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
