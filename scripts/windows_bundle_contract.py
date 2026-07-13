from __future__ import annotations

from pathlib import PureWindowsPath


BUNDLE_ROOT_NAME = "论文格式检查本地版"
LAUNCHER_NAME = "启动论文格式检查.bat"
FEEDBACK_LAUNCHER_NAME = "导出反馈包.bat"
QUICKSTART_NAME = "快速开始.txt"

PYTHON_ENTRY = "app/python.exe"
PYTHON_ABI_DLL_ENTRY = "app/python3.dll"
PYTHON_DLL_ENTRY = "app/python311.dll"
PYTHON_STDLIB_ENTRY = "app/python311.zip"
PYTHON_PATH_ENTRY = "app/python311._pth"
PYTHON_VCRUNTIME_ENTRY = "app/vcruntime140.dll"
PYTHON_VCRUNTIME_1_ENTRY = "app/vcruntime140_1.dll"
PYTHON_LICENSE_ENTRY = "app/LICENSE.txt"
PORTABLE_RUNTIME_ENTRIES = (
    PYTHON_ENTRY,
    PYTHON_ABI_DLL_ENTRY,
    PYTHON_DLL_ENTRY,
    PYTHON_STDLIB_ENTRY,
    PYTHON_PATH_ENTRY,
    PYTHON_VCRUNTIME_ENTRY,
    PYTHON_VCRUNTIME_1_ENTRY,
    PYTHON_LICENSE_ENTRY,
)
PORTABLE_RUNTIME_FILES = tuple(entry.removeprefix("app/") for entry in PORTABLE_RUNTIME_ENTRIES)
PYTHON_PATH_REQUIRED_LINES = {"python311.zip", ".", "Lib\\site-packages", "import site"}
STATE_KEEP_ENTRY = "data/state/.keep"
RUNTIME_KEEP_ENTRY = "data/runtime/.keep"

REQUIRED_SUFFIXES = (
    LAUNCHER_NAME,
    FEEDBACK_LAUNCHER_NAME,
    QUICKSTART_NAME,
    *PORTABLE_RUNTIME_ENTRIES,
    STATE_KEEP_ENTRY,
    RUNTIME_KEEP_ENTRY,
)

WINDOWS_BUNDLE_ASSET_NAME = "lnu-thesis-local-windows.zip"
WINDOWS_BUNDLE_SHA256_ASSET_NAME = "lnu-thesis-local-windows.zip.sha256"


def is_portable_python_path_text(value: str) -> bool:
    lines = {line.strip() for line in value.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    path_lines = [line for line in lines if not line.startswith("import ")]
    paths_are_relative = all(
        not PureWindowsPath(line).is_absolute()
        and not PureWindowsPath(line).drive
        and not line.startswith(("\\", "/"))
        and ".." not in PureWindowsPath(line).parts
        for line in path_lines
    )
    return PYTHON_PATH_REQUIRED_LINES <= lines and paths_are_relative
