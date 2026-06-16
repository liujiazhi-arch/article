# Release Checklist

用于发布 GitHub Beta 和 Windows 本地网页包。GitHub 只分发软件版本，不同步用户论文数据。

跨项目经验沉淀见 `docs/GITHUB_LOCAL_BUNDLE_PLAYBOOK.md`。新项目如果也要做成 GitHub Release 下载、本地运行的包，先用这份 playbook 确认产品形态、隐私边界、发布资产、Release 文案和实机 smoke。

## 发布前验证

- 运行 `python3 -m pytest -q`。
- 确认 GitHub About 区已设置 description、homepage URL 和 topics。
- 确认 README 首屏包含下载入口、平台状态表、隐私边界和 `docs/assets/local-console-home.png` / `docs/assets/local-console-repaired.png`。
- 运行 `python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke --wheelhouse /tmp/article-wheelhouse --json-output /tmp/article-release-smoke.json`。
- 可选运行浏览器级本地网页 smoke：`python3 scripts/local_browser_smoke.py --work-dir /tmp/article-local-browser-smoke --json-output /tmp/article-browser-smoke.json`，确认真实浏览器里 upload / audit / plan / apply / download 跑通并保存截图。
- 构建 Windows zip 后运行 `python3 scripts/windows_bundle_smoke.py dist/article-local-windows.zip --work-dir dist/windows-bundle-http-smoke --command-timeout-seconds 600`。
- 发布 Release 前，可在 GitHub Actions 页面手动运行 CI（`workflow_dispatch`），预先确认 Windows 本地网页包能在 `windows-latest` 构建并通过 smoke。
- 在 GitHub Actions artifacts 中保存 `release-smoke-evidence-*` 和 `windows-bundle-smoke-evidence`，用于发布证据归档。
- 确认 GitHub Actions Python 3.11 / 3.12 通过。
- 发布 GitHub Release 后运行 `python3 scripts/github_release_status.py --repo <owner>/<repo> --branch main --tag <release-tag> --json-output /tmp/article-github-status.json`，确认 CI 最近一次运行成功，且 Release 资产包含 `article-local-windows.zip` 和 `article-local-windows.zip.sha256`。
- 确认发布包里的版本检查地址匹配当前发布类型：Beta/prerelease 使用 `https://api.github.com/repos/<owner>/<repo>/releases/tags/<release-tag>`，稳定版可使用 `https://api.github.com/repos/<owner>/<repo>/releases/latest`。
- 按 `docs/WINDOWS_SMOKE_CHECKLIST.md` 完成 Windows 实机 smoke，并保存截图、命令窗口日志和证据记录。
- 使用 `docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md` 填写 Windows 实机 smoke 证据报告，记录 Release tag、sha256、Windows/WPS/Word 环境、截图文件清单、隐私确认和发布结论。
- 保存 `scripts/release_smoke.py`、`scripts/windows_bundle_smoke.py`、`scripts/local_browser_smoke.py` 和 `scripts/github_release_status.py` 输出的 JSON 后，运行 `python3 scripts/release_evidence_gate.py --github-status-json /tmp/article-github-status.json --windows-report <windows-smoke-report.md> --release-smoke-json /tmp/article-release-smoke.json --windows-bundle-smoke-json <windows-bundle-smoke.json> --browser-smoke-json /tmp/article-browser-smoke.json`，确认本地安装 smoke、Windows bundle smoke、真实浏览器 smoke、GitHub Release tag 与 Windows smoke 报告的 Release tag 一致；其中 `--release-smoke-json` 和 `--windows-bundle-smoke-json` 是必填证据，只有输出 `ready` 才能把 GitHub Beta 视为发布证据齐备。
- 证据齐备后可运行 `python3 scripts/release_evidence_bundle.py --output-zip /tmp/article-release-evidence.zip --evidence /tmp/article-github-status.json --evidence /tmp/article-release-smoke.json --evidence <windows-bundle-smoke.json> --evidence <windows-smoke-report.md>`，归档 JSON/Markdown 证据；不要把论文、修复稿、PDF、截图、日志、env、runtime、state 或反馈包放入证据 zip。
- 确认 Windows clean 环境可解压 `article-local-windows.zip`。
- 双击 `启动论文格式检查.bat`，确认浏览器自动打开本地网页。
- 上传 `.docx`，生成修复方案，选择修复项，下载修复稿。
- 用 WPS/Word 打开修复稿人工复核目录、分页、图表、公式和参考文献。
- 点击“检查新版本”，确认页面说明这是手动检查 GitHub Release，只检查软件版本，不上传论文、修复稿、任务记录、本地路径或日志，且不会自动下载或安装更新。

## GitHub 展示检查

- Repository description 清楚说明这是本地 `.docx` 论文格式检查工具。
- Homepage URL 指向 Release 或 README。
- Topics 至少包含 `docx`、`ooxml`、`thesis`、`python`、`fastapi`、`local-first`、`privacy`、`windows`、`chinese-thesis`、`lnu`。
- README 截图来自脱敏 smoke，不包含真实论文、姓名、路径、日志或 API key。
- `SECURITY.md`、`docs/TROUBLESHOOTING.md`、`docs/ROADMAP.md` 和 `.github/PULL_REQUEST_TEMPLATE.md` 已存在。

## Release 资产

- `article-local-windows.zip`
- `article-local-windows.zip.sha256`

发布前必须确认 zip 已通过 `scripts/verify_release_artifact.py` 检查：zip 内只能有一个顶层目录 `论文格式检查本地版/`，且不包含本地论文、反馈包、env、日志或状态数据库。

## Release 文案模板

发布文案使用 `docs/GITHUB_RELEASE_TEMPLATE.md`。发布前必须确认模板里的 Beta 提示、人工复核提示、隐私边界、下载资产、手动更新说明和反馈隐私要求仍匹配当前版本。

发布文案必须明确：这是 Beta，不保证最终提交版完全合规；论文默认只在本机处理；不要把论文、修复稿或 API key 上传到 GitHub issue；用 WPS/Word 打开修复稿人工复核；点击“检查新版本”只做手动版本检查，且不会自动下载或安装更新。

## macOS 后续

当前不要把 macOS 说成正式支持。只有在实验包存在后，才按 `docs/MACOS_SMOKE_CHECKLIST.md` 做 clean macOS、Gatekeeper、启动/退出、upload / audit / plan / apply / download 和 WPS/Word 复核。
