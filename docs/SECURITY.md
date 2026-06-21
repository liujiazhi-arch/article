# 密钥与隐私防护

本项目按本地处理优先发布。GitHub 只托管代码、文档、CI 和发布包，不同步用户论文、修复稿、API key、本地日志、运行缓存或状态数据库。

## 配置模板

`.env.example` 只用于公开示例配置。它可以记录 `ARTICLE_LOCAL_RELEASE_API_URL` 这类不含密钥的公开模板值，但不要提交真实 API key、论文路径、修复稿路径、本地日志路径、运行缓存路径或反馈包路径。

真实本地配置如果存在，必须保存在被 `.gitignore` 忽略的 `.env`、`.env.*`、`*.env` 或 `article-local.env` 文件中。

## 提交前检查

提交或发布前至少执行：

```bash
git status --short
python3 -m pytest -q
python3 scripts/verify_release_artifact.py dist/lnu-thesis-local-windows.zip --sha256-output dist/lnu-thesis-local-windows.zip.sha256
```

检查重点：

- 不要提交真实 API key。
- 不要提交论文、修复稿、本地日志、运行缓存或状态数据库。
- 不要提交未检查的反馈包。
- 不要把 `.env`、`.env.*`、`article-local.env` 或其他个人配置加入 Git。
- 发布 zip 必须通过 `scripts/verify_release_artifact.py`，确认不含本地论文、反馈包、env、日志或状态数据库。

## secret scanning

推送到 GitHub 前建议启用或人工执行 secret scanning。发现疑似密钥时，先撤销该密钥，再清理提交历史或改用新的安全凭据。不要在 issue、PR、Release 文案、截图、反馈包或日志中暴露密钥。

## 反馈包

反馈包默认不包含论文原文、修复稿、PDF、页面图片或 API key，并会脱敏文档文件名。反馈包发送前必须人工检查文件列表；公开 issue 中不要上传未检查的反馈包。
