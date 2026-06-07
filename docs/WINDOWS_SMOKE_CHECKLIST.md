# Windows 实机 smoke checklist

这不是 CI 的替代品。CI 负责构建、单元测试、HTTP smoke 和 zip 内容检查；本清单用于发布前在真实 clean Windows 环境里确认学生视角的下载、解压、双击启动、浏览器使用和 WPS/Word 复核流程。

## 环境

- 使用 clean Windows 环境，优先选择没有安装 Python、没有配置开发工具的普通用户机器或虚拟机。
- 使用当前待发布的 `article-local-windows.zip` 和对应的 `article-local-windows.zip.sha256`。
- 不使用用户真实论文、修复稿、API key、本地日志或未检查的反馈包做公开演示材料。

## 操作步骤

1. 从 GitHub Release 下载 `article-local-windows.zip`。
2. 完整解压 zip，确认目录内能看到 `启动论文格式检查.bat`、`导出反馈包.bat` 和 `快速开始.txt`。
3. 双击 `启动论文格式检查.bat`。
4. 确认命令窗口没有要求用户输入命令，且浏览器自动打开本地网页。
5. 在网页中上传 `.docx`。
6. 确认可以看到 audit / plan 结果。
7. 选择至少一个 scope 修复项并执行 apply。
8. 下载修复稿，确认文件名是修复副本，不覆盖原文档。
9. 用 WPS/Word 打开修复稿，人工复核目录、分页、图表、公式和参考文献。
10. 点击“检查新版本”，确认页面说明这是手动检查 GitHub Release，只检查软件版本，不上传论文、修复稿、任务记录、本地路径或日志，且不会自动下载或安装更新。
11. 如需反馈，运行 `导出反馈包.bat`，确认反馈包默认不包含论文原文、修复稿、PDF、页面图片或 API key。

## 证据记录

发布前至少保留以下证据记录，供 release owner 复核：

- zip 文件名、版本号、sha256 校验结果。
- Windows 版本和 WPS/Word 版本。
- 解压后目录截图，能看到 `启动论文格式检查.bat`、`导出反馈包.bat` 和 `快速开始.txt`。
- 双击启动后的命令窗口日志截图，能看到本地服务启动地址。
- 浏览器自动打开后的首页截图。
- 上传 `.docx` 后的页面截图。
- audit / plan / apply / download 跑通后的页面截图。
- 用 WPS/Word 打开修复稿的截图。
- 失败时记录中文错误提示、下一步建议和命令窗口日志。

建议使用 `docs/WINDOWS_SMOKE_REPORT_TEMPLATE.md` 记录 Release tag、sha256 校验结果、Windows 版本、WPS/Word 版本、截图文件清单、命令窗口日志、隐私确认和发布结论。

## 隐私边界

- 不要上传论文、修复稿、API key、本地日志或未检查的反馈包到 GitHub issue。
- 公开 issue 只放脱敏错误摘要、页面提示、版本号和必要的环境信息。
- GitHub 只负责分发软件版本；论文处理、修复副本、任务记录和密钥都留在用户本机。
