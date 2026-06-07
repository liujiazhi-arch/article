# Changelog

## 0.1.0 - GitHub Beta

- 公开产品边界收敛为辽宁大学本科毕业论文。
- 公开 profile 保留 `lnu-checker-2026`，当前 runtime 为 74 条规则。
- 增加本地网页入口、任务记录、上传校验、友好错误和修复副本下载链路。
- 增加非 editable wheel 安装 release smoke：构建 wheel、仓库外 clean venv 安装、运行 doctor/profiles/API 上传修复下载流程。
- 增加 GitHub Beta 文档、隐私说明、免责声明、贡献指南和 CI 发布门槛。

## Unreleased

- 增加 `启动论文格式检查.bat` 生成能力，为 Windows 本地网页包提供双击启动入口。
- 增加 Windows 本地网页 zip 组装脚本，打包已准备好的 Windows runtime、快速说明和本地数据目录。
- 下载项缺失或已清理时返回中文错误原因和下一步操作，减少学生遇到下载失败时的排障成本。
- 扩充真实脏 DOCX 样本库：WPS、Word、目录域、脚注、批注、修订、浮动图片、公式、嵌套表格、异常 section break。
- 继续拆清 `thesis_rules/` 与 `thesis_fix/` 的依赖方向。
