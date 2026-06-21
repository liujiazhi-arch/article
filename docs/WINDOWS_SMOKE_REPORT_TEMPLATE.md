# Windows 实机 smoke 证据报告模板

本模板用于记录 clean Windows 环境下的发布前验证证据。报告可以保存在私有发布记录、内部 issue 或 release owner 的验收目录中；公开反馈时必须先脱敏。

## 基本信息

- Release tag:
- GitHub Release 地址:
- `lnu-thesis-local-windows.zip` 下载地址:
- `lnu-thesis-local-windows.zip.sha256` 下载地址:
- `lnu-thesis-local-windows.zip` 文件大小:
- `lnu-thesis-local-windows.zip.sha256` 内容:
- sha256 校验结果: 通过 / 不通过
- GitHub Actions run 地址:
- `release-smoke-evidence-*` artifact:
- `windows-bundle-smoke-evidence` artifact:
- `article-github-status.json`:
- `article-release-smoke.json`:
- `windows-bundle-smoke.json`:
- `article-release-evidence.zip`:
- 验证人:
- 验证日期:

## 验证环境

- Windows 版本:
- 机器类型: 物理机 / 虚拟机
- 是否 clean Windows 环境:
- 是否未预装 Python:
- 默认浏览器:
- WPS/Word 版本:
- 网络状态:

## 操作记录

- 已完整解压 `lnu-thesis-local-windows.zip`: 通过 / 不通过
- 解压目录可见 `启动论文格式检查.bat`: 通过 / 不通过
- 解压目录可见 `导出反馈包.bat`: 通过 / 不通过
- 解压目录可见 `快速开始.txt`: 通过 / 不通过
- 双击 `启动论文格式检查.bat`: 通过 / 不通过
- 命令窗口无需用户输入命令: 通过 / 不通过
- 浏览器自动打开本地网页: 通过 / 不通过
- 上传 `.docx`: 通过 / 不通过
- audit / plan / apply / download: 通过 / 不通过
- 下载修复稿且不覆盖原文档: 通过 / 不通过
- 用 WPS/Word 打开修复稿: 通过 / 不通过
- 人工复核目录、分页、图表、公式和参考文献: 通过 / 不通过
- 检查新版本只检查 GitHub Release，不上传论文数据: 通过 / 不通过
- 导出反馈包默认不包含论文原文、修复稿、PDF、页面图片或 API key: 通过 / 不通过

## 截图文件清单

- 解压目录截图:
- 命令窗口日志截图:
- 浏览器首页截图:
- 上传 `.docx` 后页面截图:
- audit / plan 页面截图:
- apply / download 完成页面截图:
- WPS/Word 打开修复稿截图:
- 检查新版本提示截图:
- 反馈包文件列表截图:

## 命令窗口日志

```text
粘贴或概述黑色窗口日志。不要包含论文路径中的个人姓名、学号、手机号、API key 或其他隐私信息。
```

## 错误与处理

- 是否出现中文错误提示:
- 错误提示内容:
- 页面给出的下一步:
- 是否可按提示恢复:
- 仍需修复的问题:

## 隐私确认

- 未上传论文、修复稿、API key、本地日志或未检查的反馈包到 GitHub issue: 通过 / 不通过
- 公开反馈材料已脱敏: 通过 / 不通过
- 反馈包发送前已人工检查文件列表: 通过 / 不通过
- 本次验证使用的是测试样本或已脱敏样本: 通过 / 不通过
- `article-release-evidence.zip` 仅包含 JSON/Markdown/text/sha256 证据: 通过 / 不通过
- `article-release-evidence.zip` 不包含论文、修复稿、PDF、截图、日志、env、runtime、state 或反馈包: 通过 / 不通过

## 证据门禁

- `release_evidence_gate.py` 命令:
- `release_evidence_gate.py` 输出状态: ready / not_ready
- `release_evidence_gate.py` 输出 JSON 摘要:
- `release_evidence_bundle.py` 命令:
- 证据 zip 人工检查结果: 通过 / 不通过

## 发布结论

- 发布结论: 通过 / 不通过
- 阻塞发布的问题:
- 非阻塞已知问题:
- release owner 复核:
- 备注:
