from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_github_beta_release_documents_exist_and_state_product_boundary():
    required_paths = [
        ".env.example",
        "LICENSE",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "docs/SECURITY.md",
        "docs/USER_GUIDE.md",
        "docs/DEVELOPMENT.md",
        "docs/PRIVACY.md",
        "docs/DISCLAIMER.md",
        "docs/GITHUB_RELEASE_TEMPLATE.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/WINDOWS_SMOKE_CHECKLIST.md",
        "docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/document_compatibility.md",
    ]
    missing = [path for path in required_paths if not (PROJECT_ROOT / path).exists()]
    assert missing == []

    env_example = _read(".env.example")
    for phrase in (
        "ARTICLE_LOCAL_RELEASE_API_URL=",
        "https://api.github.com/repos/<owner>/<repo>/releases/latest",
        "不要填写真实 API key",
        "不要填写论文路径",
        "不要提交本地日志、运行缓存或修复稿路径",
    ):
        assert phrase in env_example

    readme = _read("README.md")
    for phrase in (
        "GitHub Beta",
        "辽宁大学本科毕业论文",
        "本地处理",
        "GitHub 只托管代码、文档、CI 和发布包",
        "不同步你的论文、API key、本地日志、运行缓存或修复稿",
        "手动检查 GitHub Release 新版本",
        "不会自动下载或安装更新",
        "生成修复副本",
        "部分规则自动修复",
        "部分规则提示人工复核",
        "不要上传论文到外部服务器",
    ):
        assert phrase in readme

    for forbidden in (
        "所有论文自动完美修好",
        "全自动完美修复",
    ):
        assert forbidden not in readme

    assert "python3 -m pip install '.[api]'" in _read("docs/USER_GUIDE.md")
    assert "普通学生首选 Windows 本地网页 zip" in readme
    user_guide = _read("docs/USER_GUIDE.md")
    assert "小程序/云端网页不是首处理端" in user_guide
    assert "从 GitHub Release 下载" in user_guide
    assert "GitHub 只负责分发软件版本" in user_guide
    assert "手动检查 GitHub Release 新版本" in user_guide
    assert "不会自动下载或安装更新" in user_guide
    assert "不要把论文、修复稿、API key、本地日志或未检查的反馈包上传到 GitHub issue" in user_guide
    assert "导出反馈包.bat" in user_guide
    assert "反馈包默认不包含论文原文、修复稿或 API key，并会脱敏文档文件名" in user_guide
    assert "端口 8000 被占用" in user_guide
    assert "关闭占用端口的程序" in user_guide
    development = _read("docs/DEVELOPMENT.md")
    assert "python3 -m pytest -q" in development
    assert "scripts/build_windows_local_bundle.py" in development
    assert "--runtime-dir" in development
    assert "--output-zip" in development
    assert "GitHub Actions 会在 windows-latest runner" in development
    assert "可在 GitHub Actions 页面手动运行 CI" in development
    assert "workflow_dispatch" in development
    assert "article-local-windows.zip" in development
    assert "导出反馈包.bat" in development
    assert "article-local feedback" in development
    assert "Windows clean 环境" in development
    assert "GitHub Release" in development
    assert "软件版本从 GitHub 发布，用户论文和密钥不进入 GitHub" in development
    assert "手动检查 GitHub Release 新版本" in development
    assert "不会自动下载或安装更新" in development
    assert "CI 构建正式 zip 时会传入 `--release-api-url https://api.github.com/repos/${{ github.repository }}/releases/latest`" in development
    assert "verify_release_artifact.py" in development
    assert "article-local-windows.zip.sha256" in development
    assert "扫描 zip 不含本地论文、反馈包、env、日志或状态数据库" in development
    assert "最近一次 CI 为 `completed/success`" in development
    assert "Release 资产同时包含 `article-local-windows.zip` 和 `article-local-windows.zip.sha256`" in development
    assert "GitHub Release tag 与 Windows smoke 报告的 Release tag 一致" in development
    assert "旧 Windows smoke 报告" in development
    privacy = _read("docs/PRIVACY.md")
    assert "不会主动上传论文" in privacy
    assert "GitHub 只用于分发软件版本和接收脱敏问题反馈" in privacy
    assert "版本检查只会请求 GitHub Release 元数据" in privacy
    assert "不会上传论文、修复稿、任务记录、本地路径或日志" in privacy
    assert "不要上传论文、修复稿、API key、本地日志或未检查的反馈包" in privacy
    assert "反馈包默认不包含论文原文、修复稿、PDF、页面图片或 API key，并会脱敏文档文件名" in privacy
    security = _read("docs/SECURITY.md")
    for phrase in (
        "密钥与隐私防护",
        ".env.example",
        "不要提交真实 API key",
        "不要提交论文、修复稿、本地日志、运行缓存或状态数据库",
        "secret scanning",
        "git status --short",
        "scripts/verify_release_artifact.py",
        "反馈包发送前必须人工检查文件列表",
    ):
        assert phrase in security
    release_checklist = _read("docs/RELEASE_CHECKLIST.md")
    for phrase in (
        "article-local-windows.zip",
        "article-local-windows.zip.sha256",
        "docs/WINDOWS_SMOKE_CHECKLIST.md",
        "docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md",
        "这是 Beta",
        "不保证最终提交版完全合规",
        "论文默认只在本机处理",
        "不要把论文、修复稿或 API key 上传到 GitHub issue",
        "用 WPS/Word 打开修复稿人工复核",
        "python3 -m pytest -q",
        "scripts/release_smoke.py",
        "scripts/local_browser_smoke.py",
        "scripts/github_release_status.py",
        "scripts/release_evidence_gate.py",
        "scripts/windows_bundle_smoke.py",
        "Windows clean 环境",
        "只有输出 `ready` 才能把 GitHub Beta 视为发布证据齐备",
        "GitHub Release tag 与 Windows smoke 报告的 Release tag 一致",
        "GitHub Actions 页面手动运行 CI",
        "workflow_dispatch",
        "点击“检查新版本”",
        "不会自动下载或安装更新",
    ):
        assert phrase in release_checklist

    github_release_template = _read("docs/GITHUB_RELEASE_TEMPLATE.md")
    for phrase in (
        "GitHub Release 文案模板",
        "这是 Beta",
        "不保证最终提交版完全合规",
        "article-local-windows.zip",
        "article-local-windows.zip.sha256",
        "启动论文格式检查.bat",
        "论文默认只在本机处理",
        "GitHub 只用于分发软件版本",
        "不会同步用户论文、修复稿、API key、本地日志、运行缓存或本地状态目录",
        "不要把论文、修复稿或 API key 上传到 GitHub issue",
        "反馈问题时优先提供页面提示截图、命令窗口截图、脱敏错误摘要或已检查的反馈包",
        "修复结果必须用 WPS/Word 人工复核",
        "手动检查 GitHub Release 新版本",
        "不会自动下载或安装更新",
    ):
        assert phrase in github_release_template

    windows_smoke_checklist = _read("docs/WINDOWS_SMOKE_CHECKLIST.md")
    for phrase in (
        "Windows 实机 smoke checklist",
        "这不是 CI 的替代品",
        "clean Windows 环境",
        "article-local-windows.zip",
        "启动论文格式检查.bat",
        "浏览器自动打开",
        "上传 `.docx`",
        "audit / plan / apply / download",
        "用 WPS/Word 打开修复稿",
        "不要上传论文、修复稿、API key、本地日志或未检查的反馈包",
        "截图",
        "命令窗口日志",
        "证据记录",
    ):
        assert phrase in windows_smoke_checklist

    windows_smoke_report = _read("docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md")
    for phrase in (
        "Windows 实机 smoke 证据报告模板",
        "Release tag",
        "article-local-windows.zip",
        "article-local-windows.zip.sha256",
        "sha256 校验结果",
        "Windows 版本",
        "WPS/Word 版本",
        "启动论文格式检查.bat",
        "浏览器自动打开",
        "上传 `.docx`",
        "audit / plan / apply / download",
        "用 WPS/Word 打开修复稿",
        "截图文件清单",
        "命令窗口日志",
        "隐私确认",
        "未上传论文、修复稿、API key、本地日志或未检查的反馈包",
        "release-smoke-evidence-*",
        "windows-bundle-smoke-evidence",
        "article-github-status.json",
        "article-release-smoke.json",
        "windows-bundle-smoke.json",
        "article-release-evidence.zip",
        "证据门禁",
        "release_evidence_gate.py",
        "release_evidence_bundle.py",
        "仅包含 JSON/Markdown/text/sha256 证据",
        "不包含论文、修复稿、PDF、截图、日志、env、runtime、state 或反馈包",
        "发布结论",
        "通过 / 不通过",
    ):
        assert phrase in windows_smoke_report
    bug_template = _read(".github/ISSUE_TEMPLATE/bug_report.md")
    compatibility_template = _read(".github/ISSUE_TEMPLATE/document_compatibility.md")
    assert "不要上传论文、修复稿、API key、本地日志或未检查的反馈包" in bug_template
    for phrase in (
        "Windows 本地网页包",
        "article-local-windows.zip",
        "启动论文格式检查.bat",
        "页面提示截图",
        "命令窗口截图",
        "导出反馈包.bat",
        "反馈包发送前已人工检查文件列表",
        "不要上传论文、修复稿、API key、本地日志或未检查的反馈包",
    ):
        assert phrase in bug_template
    assert "不要上传未脱敏论文、修复稿、API key 或未检查的反馈包" in compatibility_template
    for phrase in (
        "Windows 本地网页包",
        "WPS/Word 版本",
        "修复稿能否打开",
        "目录、分页、图表、公式和参考文献",
        "页面提示截图",
        "反馈包发送前已人工检查文件列表",
        "不要上传未脱敏论文、修复稿、API key 或未检查的反馈包",
    ):
        assert phrase in compatibility_template
    assert "不能替代学校或导师的最终审核" in _read("docs/DISCLAIMER.md")


def test_ci_runs_tests_wheel_build_and_release_smoke_gate():
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists()
    workflow = workflow_path.read_text(encoding="utf-8")

    for fragment in (
        "python-version: ['3.11', '3.12']",
        "workflow_dispatch:",
        "python3 -m pytest -q",
        "python3 -m pip wheel . -w dist --no-deps",
        "python3 -m build --sdist --wheel --outdir dist",
        "actions/upload-artifact",
        "python3 scripts/release_smoke.py",
        "--wheelhouse /tmp/article-wheelhouse",
        "--command-timeout-seconds",
        "--json-output dist/release-smoke-${{ matrix.python-version }}.json",
        "release-smoke-evidence-${{ matrix.python-version }}",
        "dist/release-smoke-${{ matrix.python-version }}.json",
    ):
        assert fragment in workflow


def test_ci_builds_windows_local_bundle_on_windows_runner():
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists()
    workflow = workflow_path.read_text(encoding="utf-8")

    for fragment in (
        "windows-local-bundle:",
        "runs-on: windows-latest",
        "python-version: '3.11'",
        "python -m pip wheel '.[api]' -w dist\\wheelhouse",
        "python -m venv dist\\windows-runtime",
        ".\\dist\\windows-runtime\\Scripts\\python.exe -m pip install --no-index --find-links dist\\wheelhouse 'thesis-format-tool[api]'",
        ".\\dist\\windows-runtime\\Scripts\\python.exe -m article_api.local_app doctor --state-root dist\\windows-state --runtime-root dist\\windows-data",
        "python scripts\\build_windows_local_bundle.py --runtime-dir dist\\windows-runtime --output-zip dist\\article-local-windows.zip",
        "--release-api-url https://api.github.com/repos/${{ github.repository }}/releases/latest",
        "python scripts\\verify_release_artifact.py dist\\article-local-windows.zip --sha256-output dist\\article-local-windows.zip.sha256",
        "Smoke extracted Windows local web flow",
        "python scripts\\windows_bundle_smoke.py dist\\article-local-windows.zip --work-dir dist\\windows-bundle-http-smoke --command-timeout-seconds 600 --json-output dist\\windows-bundle-smoke.json",
        "windows-bundle-smoke-evidence",
        "dist\\windows-bundle-smoke.json",
        "article-local-windows.zip",
        "article-local-windows.zip.sha256",
        "启动论文格式检查.bat",
        "导出反馈包.bat",
        "快速开始.txt",
    ):
        assert fragment in workflow


def test_ci_uploads_windows_bundle_to_github_release_when_release_is_published():
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists()
    workflow = workflow_path.read_text(encoding="utf-8")

    for fragment in (
        "release:",
        "types: [published]",
        "permissions:",
        "contents: write",
        "Upload Windows bundle to GitHub Release",
        "gh release upload",
        "${{ github.event.release.tag_name }}",
        "dist\\article-local-windows.zip",
        "dist\\article-local-windows.zip.sha256",
        "--clobber",
    ):
        assert fragment in workflow
