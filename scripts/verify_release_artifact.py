from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.parse
import zipfile


REQUIRED_SUFFIXES = (
    "启动论文格式检查.bat",
    "导出反馈包.bat",
    "快速开始.txt",
    "app/Scripts/python.exe",
    "app/Scripts/article-local.exe",
    "data/state/.keep",
    "data/runtime/.keep",
)
EXPECTED_BUNDLE_ROOT = "论文格式检查本地版"
FORBIDDEN_EXACT_NAMES = {
    ".env",
    "article-local.env",
    "反馈包.zip",
}
FORBIDDEN_SUFFIXES = (
    ".doc",
    ".docx",
    ".pdf",
    ".log",
    ".sqlite3",
    ".db",
)
FORBIDDEN_PATH_PARTS = {
    "uploads",
    "artifacts",
    "cache",
    ".cache",
    "state",
    "runtime",
}
USER_DATA_PARTS = {
    "data",
    "runtime",
    "state",
    "uploads",
    "artifacts",
}
ALLOWED_LOCAL_DATA_SUFFIXES = {
    ("data", "state", ".keep"),
    ("data", "runtime", ".keep"),
}
RELEASE_API_LINE_RE = re.compile(r'^set\s+"ARTICLE_LOCAL_RELEASE_API_URL=(?P<url>[^"]+)"\s*$', re.MULTILINE)


def _read_text(archive: zipfile.ZipFile, name: str) -> str:
    return archive.read(name).decode("utf-8-sig")


def _find_entry_by_suffix(names: set[str], suffix: str) -> str | None:
    normalized_suffix = suffix.replace("\\", "/")
    for name in sorted(names):
        if name.endswith(normalized_suffix):
            return name
    return None


def _require_single_top_level_folder(names: set[str]) -> str:
    top_level_parts = sorted({PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts})
    if len(top_level_parts) != 1:
        raise RuntimeError(
            "Release artifact must contain a single top-level folder; found: "
            + ", ".join(top_level_parts)
        )
    if top_level_parts[0] != EXPECTED_BUNDLE_ROOT:
        raise RuntimeError(
            f"Release artifact top-level folder must be {EXPECTED_BUNDLE_ROOT}; "
            f"found: {top_level_parts[0]}"
        )
    return top_level_parts[0]


def _find_bundle_entry(names: set[str], bundle_root: str, suffix: str) -> str | None:
    return _find_entry_by_suffix(names, f"{bundle_root}/{suffix}")


def _is_forbidden_entry(name: str) -> bool:
    path = PurePosixPath(name)
    lowered_name = path.name.lower()
    lowered_parts = tuple(part.lower() for part in path.parts)
    part_set = set(lowered_parts)
    for suffix in ALLOWED_LOCAL_DATA_SUFFIXES:
        if len(lowered_parts) == len(suffix) + 1 and lowered_parts[-len(suffix) :] == suffix:
            return False
    if path.name in FORBIDDEN_EXACT_NAMES or lowered_name in FORBIDDEN_EXACT_NAMES:
        return True
    if ".env" in lowered_name or lowered_name.endswith(".env") or lowered_name.endswith(".env.bak"):
        return True
    if lowered_name.endswith(".zip") and ("feedback" in lowered_name or "反馈包" in lowered_name):
        return True
    if lowered_name.startswith(".env"):
        return True
    if lowered_name.endswith((".log", ".sqlite3", ".db")):
        return True
    if bool(FORBIDDEN_PATH_PARTS & part_set):
        return True
    if len(lowered_parts) >= 3 and lowered_parts[-3:-1] in {("data", "state"), ("data", "runtime")}:
        return True
    if lowered_name.endswith((".doc", ".docx", ".pdf")):
        return not _is_dependency_document_resource(lowered_parts)
    if lowered_name.endswith(FORBIDDEN_SUFFIXES) and "app" not in part_set:
        return True
    if lowered_name.endswith(FORBIDDEN_SUFFIXES) and bool(USER_DATA_PARTS & part_set):
        return True
    return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_github_latest_release_api_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "api.github.com":
        return False
    parts = [part for part in parsed.path.split("/") if part]
    return len(parts) == 5 and parts[0] == "repos" and parts[3] == "releases" and parts[4] == "latest"


def _verify_release_api_url_if_present(launcher_text: str) -> None:
    match = RELEASE_API_LINE_RE.search(launcher_text)
    if match is None:
        return
    if not _is_github_latest_release_api_url(match.group("url")):
        raise RuntimeError("Launcher ARTICLE_LOCAL_RELEASE_API_URL must be a GitHub Release API latest URL")


def _is_dependency_document_resource(lowered_parts: tuple[str, ...]) -> bool:
    if len(lowered_parts) < 5 or lowered_parts[1] != "app":
        return False
    try:
        site_packages_index = lowered_parts.index("site-packages")
    except ValueError:
        return False
    return "lib" in lowered_parts[2:site_packages_index]


def verify_windows_bundle_artifact(
    bundle_zip: str | Path,
    *,
    sha256_output: str | Path | None = None,
) -> dict:
    zip_path = Path(bundle_zip).expanduser().resolve()
    if not zip_path.exists():
        raise RuntimeError(f"Release artifact does not exist: {zip_path}")
    if zip_path.suffix.lower() != ".zip":
        raise RuntimeError(f"Release artifact must be a zip file: {zip_path}")

    with zipfile.ZipFile(zip_path) as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        bundle_root = _require_single_top_level_folder(names)
        missing = [suffix for suffix in REQUIRED_SUFFIXES if _find_bundle_entry(names, bundle_root, suffix) is None]
        if missing:
            raise RuntimeError(f"Release artifact is missing required entries: {', '.join(missing)}")

        forbidden_entries = sorted(name for name in names if _is_forbidden_entry(name))
        if forbidden_entries:
            raise RuntimeError(
                "Release artifact contains privacy-sensitive entries: "
                + ", ".join(forbidden_entries[:10])
            )

        launcher_name = _find_bundle_entry(names, bundle_root, "启动论文格式检查.bat")
        feedback_name = _find_bundle_entry(names, bundle_root, "导出反馈包.bat")
        quickstart_name = _find_bundle_entry(names, bundle_root, "快速开始.txt")
        assert launcher_name is not None
        assert feedback_name is not None
        assert quickstart_name is not None
        launcher_text = _read_text(archive, launcher_name)
        feedback_text = _read_text(archive, feedback_name)
        quickstart_text = _read_text(archive, quickstart_name)
        for fragment in (
            'set "ARTICLE_PYTHON=%~dp0app\\Scripts\\python.exe"',
            '"%ARTICLE_PYTHON%" -m article_api.local_app doctor',
            '"%ARTICLE_PYTHON%" -m article_api.local_app serve',
        ):
            if fragment not in launcher_text:
                raise RuntimeError(f"Launcher is missing expected fragment: {fragment}")
        _verify_release_api_url_if_present(launcher_text)
        if '"%ARTICLE_PYTHON%" -m article_api.local_app feedback' not in feedback_text:
            raise RuntimeError("Feedback launcher must call the bundled Python module entrypoint")
        for phrase in (
            "不需要安装 Python",
            "不需要输入命令",
            "论文默认只在本机处理",
            "GitHub 只用于下载软件版本",
            "检查新版本",
            "只检查软件版本",
            "不会自动下载或安装更新",
        ):
            if phrase not in quickstart_text:
                raise RuntimeError(f"Quickstart is missing expected privacy/usability text: {phrase}")

    digest = _sha256_file(zip_path)
    sha256_path = Path(sha256_output).expanduser().resolve() if sha256_output is not None else None
    if sha256_path is not None:
        sha256_path.parent.mkdir(parents=True, exist_ok=True)
        sha256_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")

    return {
        "status": "ok",
        "artifact": str(zip_path),
        "entry_count": len(names),
        "sha256": digest,
        "sha256_output": str(sha256_path) if sha256_path is not None else None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_release_artifact.py")
    parser.add_argument("bundle_zip")
    parser.add_argument("--sha256-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = verify_windows_bundle_artifact(
        args.bundle_zip,
        sha256_output=args.sha256_output,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
