# Next GitHub Release Draft

> 发布前把 `<release-tag>`、`<version>` 和校验值替换成最终值。当前草稿用于前端最终确认后直接粘贴到 GitHub Release。

## `<release-tag>` - Windows 本地网页包 Beta

这是面向辽宁大学本科毕业论文 `.docx` 的本地格式审查与辅助修复工具。普通用户下载 Windows zip 后，完整解压，双击 `启动论文格式检查.bat`，浏览器会打开本机网页；在网页里上传论文、查看审查结果、选择修复项，并下载修复副本。

论文默认只在自己的电脑上处理，不上传到 GitHub 或云端。本版本仍是 Beta，不保证最终提交版完全合规，修复稿必须用 Word/WPS 人工复核。

## 下载

请在本页 **Assets** 中下载：

- `article-local-windows.zip`
- `article-local-windows.zip.sha256`

普通用户下载 `article-local-windows.zip` 即可。请先完整解压 zip，再双击 `启动论文格式检查.bat`；不要在压缩包预览窗口里直接运行。

## 本版本改进

- Windows 本地包发布链路完善：自带 Python 运行环境、双击启动脚本、快速开始说明、本地数据目录和反馈包导出入口。
- GitHub 展示材料升级：README 下载入口、平台状态表、界面截图、故障排查、路线图、安全策略和 Release checklist 已补齐。
- 手动检查新版本：本地网页只请求 GitHub Release 元数据，不上传论文、修复稿、任务记录、本地路径或日志，也不会自动下载或安装更新。
- Beta/prerelease 包的版本检查指向当前 tag API，避免 prerelease 在 latest API 下不可见。
- Scope 计划更适合界面展示：返回自动修复项、人工复核项、unsupported 项和人工确认总数。
- 审查结果补齐 rule matrix 所需字段，并明确区分可自动修复和人工复核项目。
- 渲染复核增加页面证据项和截图 token，便于解释 PDF 版式问题。
- 目录修复会写入可见自动目录结果；后续正文继续修改时，仍需在 Word/WPS 中更新域并人工复核页码。
- 规则细化：目录标题/条目格式、数字与单位/摄氏度空格、百分号前空格等。
- 反馈包隐私边界强化：反馈包默认不包含论文原文、修复稿、PDF、页面图片或 API key，发送前仍建议人工检查文件列表。

## 平台状态

| Platform | Current status | User entry |
| --- | --- | --- |
| Windows | Beta supported | `article-local-windows.zip` |
| macOS | Planned experimental package | Not yet released |
| Linux | Developer/source use only | `pip install '.[api]'` |

## 使用步骤

1. 下载并完整解压 `article-local-windows.zip`。
2. 进入解压后的文件夹。
3. 双击 `启动论文格式检查.bat`。
4. 浏览器自动打开本地网页。
5. 上传 Word/WPS 保存的 `.docx` 论文。
6. 查看审查结果和修复方案。
7. 选择需要修复的项目，生成修复稿。
8. 下载修复稿，并用 WPS/Word 人工复核。

## 界面预览

- 首页截图：`docs/assets/local-console-home.png`
- 修复完成截图：`docs/assets/local-console-repaired.png`

如果在 GitHub Release 页面查看，请回到仓库 README 查看最新截图。

## 隐私说明

论文默认只在本机处理。GitHub 只用于分发软件版本、文档和接收脱敏问题反馈，不会同步用户论文、修复稿、API key、本地日志、运行缓存或本地状态目录。

不要把论文、修复稿或 API key 上传到 GitHub issue。反馈问题时优先提供页面提示截图、命令窗口截图、脱敏错误摘要或已检查的反馈包。反馈包发送前请先人工检查文件列表。

## Beta 说明

这是 Beta 版本，不保证最终提交版完全合规。学校、学院、导师和当年模板要求优先。

修复结果必须用 WPS/Word 人工复核，重点检查目录、分页、图表、公式、表格和参考文献。

## 更新说明

本地网页可手动检查 GitHub Release 新版本。手动检查 GitHub Release 新版本只请求软件版本信息，不上传论文数据；发现新版后仍需手动下载新版 zip，不会自动下载或安装更新。

Beta 或 prerelease 发布包内的 `ARTICLE_LOCAL_RELEASE_API_URL` 应指向：

```text
https://api.github.com/repos/liujiazhi-arch/article/releases/tags/<release-tag>
```

稳定版可以使用：

```text
https://api.github.com/repos/liujiazhi-arch/article/releases/latest
```

## 已知边界

- 这是 Windows zip + bat 本地网页包，不是 `.exe` / `.msi` 安装器。
- 当前不是 macOS `.app` / `.dmg`。
- 没有自动更新器。
- 当前主要支持辽宁大学本科毕业论文格式流程。
- Beta 不等于最终提交版保证合规，必须人工复核。

## 发布前硬门槛

- `python3 -m pytest -q` 通过。
- `python3 -m build --sdist --wheel --outdir dist` 成功。
- `python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke --wheelhouse /tmp/article-wheelhouse --json-output /tmp/article-release-smoke.json` 成功。
- Windows `article-local-windows.zip` 由 GitHub Actions `windows-latest` 构建，并通过 `scripts/verify_release_artifact.py` 和 `scripts/windows_bundle_smoke.py`。
- Windows clean 环境双击 `启动论文格式检查.bat` 后浏览器必须打开可用前端，不允许停在 404 或空白页。
- 用 WPS/Word 打开修复稿并完成目录、分页、图表、公式、表格和参考文献人工复核。

## 反馈

如果遇到启动、上传、审查、修复或下载失败，请在 issue 中提供：

- 使用的 Release tag。
- Windows 版本。
- WPS/Word 版本。
- 页面提示截图或命令窗口截图。
- 脱敏错误摘要。
- 已检查过的反馈包。

不要上传论文、修复稿、API key、本地日志或未检查的反馈包。
