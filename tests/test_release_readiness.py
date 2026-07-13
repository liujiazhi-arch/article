from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_github_beta_release_documents_exist_and_state_product_boundary():
    required_paths = [
        ".env.example",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "docs/SECURITY.md",
        "docs/USER_GUIDE.md",
        "docs/DEVELOPMENT.md",
        "docs/PRIVACY.md",
        "docs/DISCLAIMER.md",
        "docs/GITHUB_RELEASE_TEMPLATE.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/TROUBLESHOOTING.md",
        "docs/ROADMAP.md",
        "docs/MACOS_SMOKE_CHECKLIST.md",
        "docs/assets/README.md",
        "docs/assets/local-console-home.png",
        "docs/assets/local-console-repaired.png",
        ".github/PULL_REQUEST_TEMPLATE.md",
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
        "https://api.github.com/repos/<owner>/<repo>/releases/tags/<release-tag>",
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
        "lnu-thesis-local-windows.zip",
        "docs/assets/local-console-home.png",
        "docs/assets/local-console-repaired.png",
        "Planned experimental package",
        "docs/TROUBLESHOOTING.md",
        "docs/ROADMAP.md",
        "SECURITY.md",
    ):
        assert phrase in readme

    for forbidden in (
        "所有论文自动完美修好",
        "全自动完美修复",
    ):
        assert forbidden not in readme

    assert "python3 -m pip install '.[api]'" in _read("docs/USER_GUIDE.md")
    assert "请等待 `v0.1.2-beta` 完成 clean Windows 和 WPS/Word 实机验收" in readme
    user_guide = _read("docs/USER_GUIDE.md")
    assert "小程序/云端网页不是首处理端" in user_guide
    assert "从 GitHub Release 下载" in user_guide
    assert "GitHub 只负责分发软件版本" in user_guide
    assert "手动检查 GitHub Release 新版本" in user_guide
    assert "Beta 或 prerelease 包使用当前发布 tag 检查版本" in user_guide
    assert "故障排查" in user_guide
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
    assert "在 GitHub Actions 页面手动运行 CI" in development
    assert "workflow_dispatch" in development
    assert "lnu-thesis-local-windows.zip" in development
    assert "导出反馈包.bat" in development
    assert "lnu-thesis-local feedback" in development
    assert "Windows clean 环境" in development
    assert "GitHub Release" in development
    assert "软件版本从 GitHub 发布，用户论文和密钥不进入 GitHub" in development
    assert "手动检查 GitHub Release 新版本" in development
    assert "不会自动下载或安装更新" in development
    assert "发布前先创建 Draft Release" in development
    assert "`workflow_dispatch`" in development
    assert "`release_tag`" in development
    assert "目标 Release 仍为 draft" in development
    assert "verify_release_artifact.py" in development
    assert "lnu-thesis-local-windows.zip.sha256" in development
    assert "扫描 zip 不含本地论文、反馈包、env、日志或状态数据库" in development
    assert "最近一次 CI 为 `completed/success`" in development
    assert "Release 资产同时包含 `lnu-thesis-local-windows.zip` 和 `lnu-thesis-local-windows.zip.sha256`" in development
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
        "lnu-thesis-local-windows.zip",
        "lnu-thesis-local-windows.zip.sha256",
        "GitHub About 区",
        "description、homepage URL 和 topics",
        "docs/assets/local-console-home.png",
        "docs/assets/local-console-repaired.png",
        "releases/tags/<release-tag>",
        "docs/WINDOWS_SMOKE_CHECKLIST.md",
        "docs/MACOS_SMOKE_CHECKLIST.md",
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
        "Draft Release",
        "release_tag",
        "点击“检查新版本”",
        "不会自动下载或安装更新",
    ):
        assert phrase in release_checklist

    github_release_template = _read("docs/GITHUB_RELEASE_TEMPLATE.md")
    for phrase in (
        "GitHub Release 文案模板",
        "这是 Beta",
        "不保证最终提交版完全合规",
        "lnu-thesis-local-windows.zip",
        "lnu-thesis-local-windows.zip.sha256",
        "启动论文格式检查.bat",
        "平台状态",
        "docs/assets/local-console-home.png",
        "docs/assets/local-console-repaired.png",
        "releases/tags/<release-tag>",
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

    security_policy = _read("SECURITY.md")
    assert "Do not attach real thesis documents" in security_policy
    pr_template = _read(".github/PULL_REQUEST_TEMPLATE.md")
    assert "I ran the relevant tests" in pr_template
    troubleshooting = _read("docs/TROUBLESHOOTING.md")
    assert "Windows SmartScreen" in troubleshooting
    roadmap = _read("docs/ROADMAP.md")
    assert "Signed and notarized `.dmg`" in roadmap
    macos_smoke = _read("docs/MACOS_SMOKE_CHECKLIST.md")
    assert "Gatekeeper" in macos_smoke

    windows_smoke_checklist = _read("docs/WINDOWS_SMOKE_CHECKLIST.md")
    for phrase in (
        "Windows 实机 smoke checklist",
        "这不是 CI 的替代品",
        "clean Windows 环境",
        "lnu-thesis-local-windows.zip",
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
        "lnu-thesis-local-windows.zip",
        "lnu-thesis-local-windows.zip.sha256",
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
        "lnu-thesis-local-windows.zip",
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
        'Invoke-WebRequest "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip"',
        '009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b',
        "Expand-Archive dist\\python-embed.zip -DestinationPath dist\\windows-runtime",
        "Add-Content dist\\windows-runtime\\python311._pth",
        "--target dist\\windows-runtime\\Lib\\site-packages 'thesis-format-tool[api]'",
        ".\\dist\\windows-runtime\\python.exe -m article_api.local_app doctor --state-root dist\\windows-state --runtime-root dist\\windows-data",
        "$releaseApiUrl = \"https://api.github.com/repos/${{ github.repository }}/releases/latest\"",
        "if (\"${{ inputs.release_tag }}\")",
        "$releaseApiUrl = \"https://api.github.com/repos/${{ github.repository }}/releases/tags/${{ inputs.release_tag }}\"",
        "python scripts\\build_windows_local_bundle.py --runtime-dir dist\\windows-runtime --output-zip dist\\lnu-thesis-local-windows.zip --release-api-url $releaseApiUrl",
        "python scripts\\verify_release_artifact.py dist\\lnu-thesis-local-windows.zip --sha256-output dist\\lnu-thesis-local-windows.zip.sha256",
        "Smoke extracted Windows local web flow",
        "python scripts\\windows_bundle_smoke.py dist\\lnu-thesis-local-windows.zip --work-dir dist\\windows-bundle-http-smoke --command-timeout-seconds 600 --json-output dist\\windows-bundle-smoke.json",
        "windows-bundle-smoke-evidence",
        "dist\\windows-bundle-smoke.json",
        "lnu-thesis-local-windows.zip",
        "lnu-thesis-local-windows.zip.sha256",
        "启动论文格式检查.bat",
        "导出反馈包.bat",
        "快速开始.txt",
    ):
        assert fragment in workflow
    assert "python -m venv dist\\windows-runtime" not in workflow


def test_ci_uploads_validated_windows_bundle_to_an_existing_draft_release():
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow_path.exists()
    workflow = workflow_path.read_text(encoding="utf-8")

    for fragment in (
        "release_tag:",
        "publish-draft-release-assets:",
        "needs: [test, windows-local-bundle]",
        "permissions:",
        "contents: write",
        "actions/download-artifact@v4",
        "Verify target release is still a draft",
        "--json isDraft",
        ".target_commitish",
        'test "$target_sha" = "$GITHUB_SHA"',
        "Upload validated Windows bundle to draft GitHub Release",
        "gh release upload",
        "${{ inputs.release_tag }}",
        "dist/lnu-thesis-local-windows.zip",
        "dist/lnu-thesis-local-windows.zip.sha256",
        "--clobber",
    ):
        assert fragment in workflow
    assert "types: [published]" not in workflow
