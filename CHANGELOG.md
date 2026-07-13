# Changelog

## 0.1.2 - GitHub Beta

- Replace the copied Windows virtual environment with the official Python 3.11.9 embeddable runtime.
- Bundle PDFium/Pillow fallback support and verify DOCX apply/download plus PDF render-review in release smoke.
- Isolate concurrent repair and render-review workspaces, restore PDF review retries, and harden WPS DOCX output compatibility.
- Harden feedback archive redaction, diagnostic size limits, Draft Release commit binding, and Windows evidence checks.

## 0.1.1 - GitHub Beta

- 仓库与发布资产改名为 `lnu-thesis-format-tool` / `lnu-thesis-local-windows.zip`。
- 新增 `lnu-thesis-*` 命令入口，并保留旧 `article-*` 入口兼容。
- 更新 README、Release 文档、CI 发布资产和版本检查目标。

## 0.1.0 - GitHub Beta

- 公开产品边界收敛为辽宁大学本科毕业论文。
- 公开 profile 保留 `lnu-checker-2026`，当前 runtime 为 74 条规则。
- 增加本地网页入口、任务记录、上传校验、友好错误和修复副本下载链路。
- 增加非 editable wheel 安装 release smoke：构建 wheel、仓库外 clean venv 安装、运行 doctor/profiles/API 上传修复下载流程。
- 增加 GitHub Beta 文档、隐私说明、免责声明、贡献指南和 CI 发布门槛。

## Unreleased

- 完成 GitHub Beta 展示材料升级：README 增加下载入口、平台状态、截图、隐私边界、故障排查和路线图入口。
- 增加 `启动论文格式检查.bat` 生成能力，为 Windows 本地网页包提供双击启动入口。
- 增加 Windows 本地网页 zip 组装脚本，打包已准备好的 Windows runtime、快速说明和本地数据目录。
- 增加手动 GitHub Release 版本检查说明；Beta/prerelease 包应指向当前 tag API，稳定版可指向 latest API。
- 增加 `导出反馈包.bat` 和反馈包隐私说明，强调反馈包发送前必须人工检查文件列表。
- 增加 render evidence 截图 token 访问入口，避免用本地文件路径暴露页面证据截图。
- 增强 plan/audit 输出，补充 scope radar、人工确认统计和 rule matrix 所需字段。
- 改进目录修复说明：工具会写入可见自动目录结果，后续正文变动仍需 Word/WPS 更新域并复核页码。
- 细化 LNU 目录格式、数字单位/摄氏度空格和百分号空格规则。
- 下载项缺失或已清理时返回中文错误原因和下一步操作，减少学生遇到下载失败时的排障成本。
- 扩充真实脏 DOCX 样本库：WPS、Word、目录域、脚注、批注、修订、浮动图片、公式、嵌套表格、异常 section break。
- 继续拆清 `thesis_rules/` 与 `thesis_fix/` 的依赖方向。
