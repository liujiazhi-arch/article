# Next Release Prep

这份清单用于前端最终确认后，把当前版本发布到 GitHub Release。它记录本地能准备的产物、GitHub Actions 负责的 Windows 包，以及当前必须先处理的发布门槛。

## 当前发布资产

- Python package version: `pyproject.toml` 中的 `0.1.2`
- Runtime service version: `scripts/article_api/response_payloads.py` 中的 `SERVICE_VERSION = "0.1.2"`
- GitHub Release 草稿: `docs/NEXT_GITHUB_RELEASE_DRAFT.md`
- Release 模板: `docs/GITHUB_RELEASE_TEMPLATE.md`
- 发布检查清单: `docs/RELEASE_CHECKLIST.md`
- Windows 包名: `lnu-thesis-local-windows.zip`
- Windows sha256: `lnu-thesis-local-windows.zip.sha256`

本轮新 tag 使用 `v0.1.2-beta`。发布前需要同步确认 README 下载链接、Release 标题、`CHANGELOG.md` 版本段落、GitHub Release tag 和 Windows 包内 `ARTICLE_LOCAL_RELEASE_API_URL`。

## 本地准备命令

```bash
python3 -m pytest -q
python3 -m build --sdist --wheel --outdir dist
python3 -m pip wheel '.[api]' -w /tmp/article-wheelhouse
python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke --wheelhouse /tmp/article-wheelhouse --json-output /tmp/article-release-smoke.json
python3 scripts/local_browser_smoke.py --work-dir /tmp/article-local-browser-smoke --json-output /tmp/article-browser-smoke.json
```

`local_browser_smoke.py` 是前端入口门槛。它必须能打开本地网页、上传 `.docx`、生成方案、执行修复并下载修复稿。

## Windows 包构建

正式 Windows zip 不应在 macOS 上伪造。当前主链由 GitHub Actions `windows-latest` 生成：

1. `python -m pip wheel '.[api]' -w dist\wheelhouse`
2. 下载并校验 Python 3.11.9 官方 embeddable zip
3. 解压到 `dist\windows-runtime` 并用 `pip --target dist\windows-runtime\Lib\site-packages` 安装 wheelhouse
4. `python scripts\build_windows_local_bundle.py --runtime-dir dist\windows-runtime --output-zip dist\lnu-thesis-local-windows.zip --release-api-url <release-api-url>`
5. `python scripts\verify_release_artifact.py dist\lnu-thesis-local-windows.zip --sha256-output dist\lnu-thesis-local-windows.zip.sha256`
6. `python scripts\windows_bundle_smoke.py dist\lnu-thesis-local-windows.zip --work-dir dist\windows-bundle-http-smoke --command-timeout-seconds 600 --json-output dist\windows-bundle-smoke.json`

先创建 Draft Release，再手动运行 CI 并把 `release_tag` 设为该草稿 tag。只有 Python 测试和 Windows bundle smoke 都通过且目标仍为 draft，CI 才上传 `lnu-thesis-local-windows.zip` 和 `lnu-thesis-local-windows.zip.sha256`。确认资产后再发布 Release。

## 发布前硬门槛

- 前端最终入口确认：双击启动后打开的 `http://127.0.0.1:8000` 必须是可用页面，不是 404、空白页或仅 API JSON。
- `docs/assets/local-console-home.png` 和 `docs/assets/local-console-repaired.png` 必须来自脱敏 smoke，不含真实论文、姓名、路径、日志或 API key。
- `python3 -m pytest -q` 通过。
- release smoke JSON 状态为 `ok`，且包含 doctor/profiles、DOCX apply/download 和 PDF render-review 成功证据。
- Windows bundle smoke JSON 状态为 `ok`，且包含 doctor、DOCX apply/download 和 PDF render-review 成功证据。
- Draft Release 已通过带 `release_tag` 的 workflow_dispatch 收到 zip 和 sha256，公开发布前已核对资产。
- Windows clean 环境实机 smoke 报告通过。
- 发布后运行 `scripts/github_release_status.py`，确认 CI 最近一次 `completed/success`，Release assets 同时包含 zip 和 sha256。
- 证据门禁 `scripts/release_evidence_gate.py` 输出 `ready` 后，才把 GitHub Beta 视为发布证据齐备。

## 当前已知风险

- FastAPI `/` 已接入静态前端并通过本地真实浏览器 smoke；Windows 发布前仍必须在 clean 环境确认双击入口打开的不是 404 或空白页。
- 公开的 `v0.1.1-beta` 仍是旧预览包，不作为本轮修复的发布证据。
- `CHANGELOG.md` 已新增 `0.1.2 - GitHub Beta` 段落；新 Draft Release tag 使用 `v0.1.2-beta`。
- Python 包版本和服务版本已同步为 `0.1.2`。
- Windows clean 环境、WPS/Word 打开修复稿、SmartScreen 来源确认不能由 macOS 本地命令替代。

## 发布后验证

```bash
python3 scripts/github_release_status.py --repo liujiazhi-arch/lnu-thesis-format-tool --branch main --tag <release-tag> --json-output /tmp/article-github-status.json
python3 scripts/release_evidence_gate.py --github-status-json /tmp/article-github-status.json --windows-report <windows-smoke-report.md> --release-smoke-json /tmp/article-release-smoke.json --windows-bundle-smoke-json <windows-bundle-smoke.json> --browser-smoke-json /tmp/article-browser-smoke.json
python3 scripts/release_evidence_bundle.py --output-zip /tmp/article-release-evidence.zip --evidence /tmp/article-github-status.json --evidence /tmp/article-release-smoke.json --evidence <windows-bundle-smoke.json> --evidence <windows-smoke-report.md>
```

证据 zip 只放 JSON、Markdown、text 或 sha256 文件。不要放论文、修复稿、PDF、截图、日志、env、runtime、state 或反馈包。
