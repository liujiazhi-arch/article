# GitHub Release 文案模板

> 将 `<release-tag>`、版本号和变更摘要替换为当前发布信息后再发布。

## `<release-tag>` - Windows 本地网页包 Beta

这是 Beta，不保证最终提交版完全合规。修复结果必须人工复核，学校、学院、导师和当年模板要求优先。修复结果必须用 WPS/Word 人工复核目录、分页、图表、公式和参考文献。

## 下载

- `article-local-windows.zip`
- `article-local-windows.zip.sha256`

请下载 `article-local-windows.zip`，完整解压后双击 `启动论文格式检查.bat`。不需要安装 Python，不需要输入命令。

## 本地处理与隐私

论文默认只在本机处理。GitHub 只用于分发软件版本和接收脱敏问题反馈，不会同步用户论文、修复稿、API key、本地日志、运行缓存或本地状态目录。

不要把论文、修复稿或 API key 上传到 GitHub issue。反馈问题时优先提供页面提示截图、命令窗口截图、脱敏错误摘要或已检查的反馈包。反馈包发送前请先人工检查文件列表。

## 使用方式

1. 下载 `article-local-windows.zip`。
2. 完整解压 zip。
3. 双击 `启动论文格式检查.bat`。
4. 浏览器自动打开后上传 `.docx`。
5. 生成修复方案，选择需要修复的 scope。
6. 下载修复稿。
7. 用 WPS/Word 打开修复稿并人工复核。

## 更新说明

本地网页可手动检查 GitHub Release 新版本。手动检查 GitHub Release 新版本只请求软件版本信息，不上传论文数据；发现新版后仍需手动下载新版 zip，不会自动下载或安装更新。

## 已知边界

- 这是 Windows zip + bat 本地网页包，不是 `.exe` / `.msi` 安装器。
- 不是 macOS `.app` / `.dmg`。
- 没有自动更新器。
- 不替代学校、学院、导师或当年模板的最终审核。

## 反馈

如果遇到启动、上传、审查、修复或下载失败，请在 issue 中提供：

- 使用的 Release tag。
- Windows 版本。
- WPS/Word 版本。
- 页面提示截图或命令窗口截图。
- 脱敏错误摘要。
- 已检查过的反馈包。

不要上传论文、修复稿、API key、本地日志或未检查的反馈包。
