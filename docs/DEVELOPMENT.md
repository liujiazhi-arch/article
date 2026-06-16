# 开发指南

## 安装开发依赖

```bash
python3 -m pip install -U pip
python3 -m pip install '.[api,dev]'
```

## 测试

```bash
python3 -m pytest -q
```

发布前还要跑仓库外安装 smoke：

```bash
python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke
```

如果已经提前构建好依赖 wheelhouse，可以让 smoke 只验证离线安装和运行链路：

```bash
python3 -m pip wheel '.[api]' -w /tmp/article-wheelhouse
python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke --wheelhouse /tmp/article-wheelhouse --json-output /tmp/article-release-smoke.json
```

这个 smoke 会构建 wheelhouse，在 clean venv 中从 wheel 安装，然后运行：

- `article-local doctor`
- `thesis-workbench profiles`
- `article-local serve`
- 上传 `.docx`
- 创建 apply job
- 下载 output artifact

如需验证真实浏览器里的本地控制台交互，可运行：

```bash
python3 scripts/local_browser_smoke.py --work-dir /tmp/article-local-browser-smoke --json-output /tmp/article-browser-smoke.json
```

这个浏览器 smoke 会启动 `article-local serve`，用 Playwright 打开本地网页，上传临时 `.docx`，执行 upload / audit / plan / apply / download，并在 work dir 里保存首页和修复完成态截图。它不替代 Windows clean 环境和 WPS/Word 实机 smoke。

## 兼容性样本库

真实学生论文不能直接提交到仓库。当前回归样本先使用 `tests/compat_samples.py` 生成脱敏 `.docx`，覆盖：

- WPS 风格文档
- Word 目录域
- 脚注
- 批注
- 修订
- 浮动图片
- 公式
- 嵌套表格
- 异常 section break

新增真实脏文档问题时，优先把问题缩小成可公开、脱敏、可生成的最小样本，再加入 `tests/test_docx_compat_samples.py` 或更具体的审查/修复回归测试。

可以用公开 OOXML 项目的测试文档做本地真实样本压力池：

```bash
python3 scripts/fetch_public_docx_samples.py
python3 -m pytest tests/test_real_docx_sample_intake.py tests/test_docx_compat_samples.py -q
```

该命令会下载 Apache POI/docx4j 的公开 `.docx` 样本并通过 `scripts/docx_sample_intake.py` 登记到被忽略的 `tests/real_docx_samples/sanitized/`，覆盖 WPS/Word、目录域、脚注、批注、修订、浮动图片、公式、嵌套表格和异常 section break。极端深层表格样本只做 package validation，避免每次审查回归被 20000 层表格拖慢。

兼容样本的最低回归门槛：

- 必须是完整 `.docx` 包。
- 必须能通过上传入口校验。
- 必须能跑 `audit_docx_with_runtime(..., profile_path="lnu")`。
- 至少一个复杂样本必须跑通上传后 `verify` job，并确认最近任务列表不泄漏 `request`、`resolved_request` 或 `runtime`。

## 架构主链

```text
CLI
  -> thesis_workbench.py
    -> thesis_tool/workflow.py
      -> audit_thesis.py / fix_thesis.py
        -> _thesis_utils.py
          -> DocumentModel / ParagraphNode / section-module 分类
```

## 关键约束

- 公开 runtime 只有 `lnu-checker-2026`。
- `CN-Common.yaml` 是内部基线，不作为公开 profile catalog 项。
- 新增 runtime 规则时，同时更新测试和 `config/capability_matrix.md`。
- 如果 profile 中新增 active `additions`，必须与 runtime/checker 对齐。
- 不要再引入第二套规则来源。
- 封面不是当前自动修复主线。
- 用户论文、运行输出、缓存、虚拟环境和状态目录不得提交。

## 发布流程

发布边界：软件版本从 GitHub 发布，用户论文和密钥不进入 GitHub。GitHub Release 可以托管源码包、wheel、Windows 本地网页 zip、变更记录和校验信息；不要把本地论文、修复稿、API key、本地日志、运行缓存、状态数据库或未检查的反馈包上传到仓库、CI artifact 或公开 issue。

跨项目复用的本地包发布经验见 `docs/GITHUB_LOCAL_BUNDLE_PLAYBOOK.md`。这份 playbook 记录从项目整理、Windows zip + bat、GitHub Release、隐私边界、发布证据到未来 macOS `.app` / `.dmg` 的通用判断，后续做类似“下载到电脑、本地运行”的 GitHub 包发布时先读它。

1. 跑全量测试。
2. 构建 wheel 和 source distribution。
3. 构建 release wheelhouse。
4. 在 Windows clean 环境准备本地运行目录。
5. 组装 Windows 本地网页 zip 包。
6. 跑 release smoke。
7. 更新 `CHANGELOG.md`。
8. 确认 README、隐私说明、免责声明和 issue 模板仍匹配当前产品边界。

```bash
python3 -m pip install build
python3 -m build --sdist --wheel --outdir dist
python3 -m pip wheel '.[api]' -w /tmp/article-wheelhouse
python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke --wheelhouse /tmp/article-wheelhouse
python3 scripts/local_browser_smoke.py --work-dir /tmp/article-local-browser-smoke
```

Windows 本地网页包需要在 Windows clean 环境准备运行目录，例如：

```bat
py -3.11 -m venv dist\windows-runtime
dist\windows-runtime\Scripts\python.exe -m pip install --no-index --find-links C:\article-wheelhouse thesis-format-tool[api]
```

准备好 `dist\windows-runtime` 后，在仓库根目录组装 zip：

```bash
python3 scripts/build_windows_local_bundle.py --runtime-dir dist/windows-runtime --output-zip dist/article-local-windows.zip --release-api-url https://api.github.com/repos/<owner>/<repo>/releases/latest
python3 scripts/build_windows_local_bundle.py --runtime-dir dist/windows-runtime --output-zip dist/article-local-windows.zip --release-api-url https://api.github.com/repos/<owner>/<repo>/releases/tags/<release-tag>
python3 scripts/verify_release_artifact.py dist/article-local-windows.zip --sha256-output dist/article-local-windows.zip.sha256
python3 scripts/windows_bundle_smoke.py dist/article-local-windows.zip --work-dir dist/windows-bundle-http-smoke --command-timeout-seconds 600 --json-output dist/windows-bundle-smoke.json
```

`verify_release_artifact.py` 会确认 zip 只有一个顶层目录 `论文格式检查本地版/`，扫描 zip 不含本地论文、反馈包、env、日志或状态数据库，也不包含真实本地 state/runtime 数据，确认双击入口、快速开始文案和可选 GitHub Release API 地址格式存在，并生成 `article-local-windows.zip.sha256`。`windows_bundle_smoke.py` 会解压 zip，用随包 `app\Scripts\python.exe` 运行 `python.exe -m article_api.local_app doctor`，再启动本地服务并跑上传 `.docx`、创建 apply job、下载 output artifact 的网页链路，并可用 `--json-output` 保存证据 JSON。GitHub Actions 会在 windows-latest runner 上执行同类 smoke：构建 wheelhouse、准备 `dist\windows-runtime`、组装 `article-local-windows.zip`、检查 zip 内容，并对解压后的 zip 跑完整本地网页链路。CI 会上传 `release-smoke-evidence-*` 和 `windows-bundle-smoke-evidence` artifacts，作为发布前 smoke 证据。CI 在 push、pull_request 或 workflow_dispatch 中会传入 `--release-api-url https://api.github.com/repos/${{ github.repository }}/releases/latest`；当 GitHub Release 发布触发 CI 时，会传入 `--release-api-url https://api.github.com/repos/${{ github.repository }}/releases/tags/${{ github.event.release.tag_name }}`，让 Beta 或正式发布包里的“检查新版本”指向当前发布页。

可在 GitHub Actions 页面手动运行 CI（`workflow_dispatch`），用于发布 Release 前预构建 Windows 本地网页包并检查 `windows-latest` smoke。这个手动运行只证明 GitHub runner 上的构建链路可用，不能替代发布后的 Release 资产检查，也不能替代 Windows clean 环境双击启动和 WPS/Word 实机复核。

当 GitHub Release 发布为 `published` 时，CI 会把 `article-local-windows.zip` 和 `article-local-windows.zip.sha256` 上传到该 Release。Release 文案仍需要明确：这是 Beta，修复稿必须人工复核，论文默认只在本机处理，不要把论文或密钥上传到 issue。

发布后可用 GitHub CLI 做远端状态复核：

```bash
python3 scripts/github_release_status.py --repo <owner>/<repo> --branch main --tag <release-tag> --json-output /tmp/article-github-status.json
```

它会检查最近一次 `CI` workflow 是否 `completed/success`，并确认 GitHub Release 资产包含 `article-local-windows.zip` 和 `article-local-windows.zip.sha256`。如果没有传 `--repo`，脚本会尝试从 `git remote.origin.url` 推断 GitHub 仓库；没有 remote 或 GitHub CLI token 失效时，会输出 JSON 错误并提示先配置 remote 或运行 `gh auth status`。这一步只能证明远端 CI 和 Release 资产状态，不能替代 Windows clean 环境双击启动和 WPS/Word 实机复核。

远端状态 JSON 和 Windows 实机 smoke 报告可以用发布证据门禁合并检查：

```bash
python3 scripts/release_evidence_gate.py --github-status-json /tmp/article-github-status.json --windows-report /path/to/windows-smoke-report.md --release-smoke-json /tmp/article-release-smoke.json --windows-bundle-smoke-json /path/to/windows-bundle-smoke.json --browser-smoke-json /tmp/article-browser-smoke.json
```

该脚本只有在 GitHub Release 状态为 `ok`、最近一次 CI 为 `completed/success`、Release 资产同时包含 `article-local-windows.zip` 和 `article-local-windows.zip.sha256`、GitHub Release tag 与 Windows smoke 报告的 Release tag 一致，并且 Windows 报告中的 clean Windows、未预装 Python、双击启动、浏览器自动打开、upload / audit / plan / apply / download、WPS/Word 打开修复稿、人工复核和隐私确认都为“通过”时才输出 `ready`。`--release-smoke-json` 和 `--windows-bundle-smoke-json` 是必填证据，门禁会确认本地安装 smoke 的 doctor/profiles/http download 成功，以及 CI Windows bundle smoke 的 doctor/http download 成功。`--browser-smoke-json` 是可选补充证据；传入时会确认真实浏览器 smoke 的截图、下载稿和 `.docx` 包有效。它用于防止把单独的 CI 绿色状态、本地 smoke、CI bundle smoke 或旧 Windows smoke 报告误当成完整发布完成。

证据门禁输出 `ready` 后，可以把 JSON/Markdown 证据归档成一个不含论文内容的 zip：

```bash
python3 scripts/release_evidence_bundle.py --output-zip /tmp/article-release-evidence.zip --evidence /tmp/article-github-status.json --evidence /tmp/article-release-smoke.json --evidence /path/to/windows-bundle-smoke.json --evidence /path/to/windows-smoke-report.md
```

`release_evidence_bundle.py` 只接收显式传入的 JSON、Markdown、text 或 sha256 文件，不会跟随 JSON 里的本地路径收集截图、下载稿或运行目录。它会拒绝 `.docx`、`.pdf`、图片、日志、env、数据库、runtime/state/cache 路径和文件名疑似包含密钥、论文或修复稿的输入。这个 zip 只用于发布证据归档，不要上传用户论文、修复稿、未检查反馈包或 API key。

zip 包内的 `启动论文格式检查.bat` 是给学生双击的入口。它会先用随包 `python.exe -m article_api.local_app doctor` 做检查，检查通过后打开 `http://127.0.0.1:8000` 并启动本地网页服务。完整自带 Python zip 发布前仍需要在 Windows clean 环境双击启动、上传 `.docx`、apply、download，并用 WPS/Word 打开修复稿复核。

zip 包内的 `导出反馈包.bat` 会调用随包 Python 生成 `反馈包.zip`；开发者也可以直接运行 `article-local feedback`。反馈包默认不包含论文原文、修复稿、PDF、页面图片或 API key，并会脱敏文档文件名，只保留任务摘要、doctor 信息、状态库摘要和诊断日志。发送前仍建议人工打开 zip 查看文件列表。

本地网页支持手动检查 GitHub Release 新版本。发布包可以通过环境变量配置 Release API 地址：

```bat
set ARTICLE_LOCAL_RELEASE_API_URL=https://api.github.com/repos/<owner>/<repo>/releases/latest
set ARTICLE_LOCAL_RELEASE_API_URL=https://api.github.com/repos/<owner>/<repo>/releases/tags/<release-tag>
```

未配置时不会联网。配置后，点击“检查新版本”只请求 GitHub Release 元数据，不会上传论文、修复稿、任务记录、本地路径或日志；稳定版可使用 `/releases/latest`，Beta 或 prerelease 包应使用 `/releases/tags/<release-tag>`。发现新版也只提示用户手动下载 zip，不会自动下载或安装更新。当前 Windows zip 仍不等同于完整桌面安装包、DMG、代码签名或自动更新应用。
