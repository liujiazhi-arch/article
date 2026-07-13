# 用户指南

这个工具用于辽宁大学本科毕业论文 `.docx` 的格式审查和分 scope 修复。它在本地运行，生成修复副本，不直接覆盖原文件。

## 安装

面向普通学生的目标形态是 Windows zip。`v0.1.2-beta` 完成 clean Windows 和 WPS/Word 实机验收并发布后，可从 GitHub Release 下载 `lnu-thesis-local-windows.zip`，解压后双击 `启动论文格式检查.bat`。小程序/云端网页不是首处理端。新包发布前请不要把公开的 `v0.1.1-beta` 当成本轮修复版本；开发验证可按下面的开发者方式安装。

GitHub 只负责分发软件版本、文档和脱敏问题反馈，不负责同步论文数据。不要把论文、修复稿、API key、本地日志或未检查的反馈包上传到 GitHub issue。

开发者方式需要 Python 3.11 或 3.12：

```bash
python3 -m pip install -U pip
python3 -m pip install '.[api]'
```

## 启动本地网页

如果使用 Windows zip 包，双击：

```text
启动论文格式检查.bat
```

如果使用开发者方式安装，运行：

```bash
lnu-thesis-local doctor
lnu-thesis-local serve
```

浏览器打开命令行输出的本地地址后：

1. 把 `.docx` 上传到本机网页。
2. 查看审查结果或修复计划。
3. 选择需要修复的 scope。
4. 等待任务完成。
5. 下载修复副本。
6. 用 Word/WPS 打开修复副本做最终人工复核。

这里的“上传”只表示交给你电脑上的本地网页服务处理，不是上传到 GitHub 或云端。

## 本地前端

启动本地 API 后，浏览器打开 `http://127.0.0.1:<port>/`。

PDF 复核需要先用 Word 或 WPS 导出 PDF，再上传到工具中查看页面问题。通过实机验收后的 `v0.1.2-beta` Windows 本地包会包含 PDF 复核运行组件，不需要另外安装 Poppler。

界面示例：

- 首页截图：[docs/assets/local-console-home.png](assets/local-console-home.png)
- 修复完成截图：[docs/assets/local-console-repaired.png](assets/local-console-repaired.png)

## 检查新版本

本地网页可以手动检查 GitHub Release 新版本。点击“检查新版本”时，只会连接 GitHub 获取软件版本信息，不会上传论文、修复稿、任务记录、本地路径或日志。

如果发现新版本，请前往 GitHub Release 手动下载新版 `lnu-thesis-local-windows.zip`，重新解压后使用。当前版本不会自动下载或安装更新。

Beta 或 prerelease 包使用当前发布 tag 检查版本；稳定版可以使用 GitHub 的 latest Release。两种方式都只请求 GitHub Release 元数据。

## 命令行入口

```bash
thesis-workbench profiles
thesis-workbench audit 你的论文.docx --profile lnu
thesis-workbench plan 你的论文.docx --profile lnu
thesis-workbench apply 你的论文.docx --profile lnu --scope abstract --output 修复后_摘要.docx
thesis-workbench verify 修复后_摘要.docx --profile lnu --scope abstract
```

## 支持范围

- 支持：辽宁大学本科毕业论文。
- 支持：单个 `.docx` 文档。
- 支持：生成修复副本。
- 支持：部分规则自动修复，部分规则提示人工复核。
- 不承诺：封面自动完美归一化。
- 不承诺：所有论文自动完美修好。
- 不承诺：替代导师、学院、学校的最终审核。

## 常见错误

**不是完整 docx 包**

请用 Word/WPS 重新另存为 `.docx`，不要直接改文件后缀。

**任务失败**

查看页面提示。用户可见错误应该说明发生了什么、下一步怎么做、是否可以重试。

如果使用 Windows zip 包，可以双击 `导出反馈包.bat`，把生成的 `反馈包.zip` 发给维护者。反馈包默认不包含论文原文、修复稿或 API key，并会脱敏文档文件名，只保留任务摘要、环境信息和诊断日志。发送前仍建议先打开 zip 查看文件列表。

**端口 8000 被占用**

关闭占用端口的程序，或重启电脑后重新双击 `启动论文格式检查.bat`。如果仍失败，请截图黑色窗口里的中文提示。

**目录或分页不一致**

启用目录修复时，工具会直接写入可见的自动目录域结果。若后续继续修改正文导致分页变化，再在 Word/WPS 中更新目录域并复核页码；最终分页以 Word/WPS 打开结果为准。
如果你手里已经有 Word/WPS 导出的 PDF，也可以把它传给 `thesis-workbench render-verify --rendered-pdf`，工具会把目录条目页码和正文实际渲染页不一致的问题合并进复核结果。

更多启动、端口、SmartScreen、`.docx` 和反馈包问题见 [故障排查](TROUBLESHOOTING.md)。
