from __future__ import annotations


BUNDLE_ROOT_NAME = "论文格式检查本地版"
LAUNCHER_NAME = "启动论文格式检查.bat"
FEEDBACK_LAUNCHER_NAME = "导出反馈包.bat"
QUICKSTART_NAME = "快速开始.txt"

PYTHON_ENTRY = "app/Scripts/python.exe"
ARTICLE_LOCAL_ENTRY = "app/Scripts/article-local.exe"
STATE_KEEP_ENTRY = "data/state/.keep"
RUNTIME_KEEP_ENTRY = "data/runtime/.keep"

REQUIRED_SUFFIXES = (
    LAUNCHER_NAME,
    FEEDBACK_LAUNCHER_NAME,
    QUICKSTART_NAME,
    PYTHON_ENTRY,
    ARTICLE_LOCAL_ENTRY,
    STATE_KEEP_ENTRY,
    RUNTIME_KEEP_ENTRY,
)

WINDOWS_BUNDLE_ASSET_NAME = "article-local-windows.zip"
WINDOWS_BUNDLE_SHA256_ASSET_NAME = "article-local-windows.zip.sha256"
