# Contributing

这个项目当前优先服务辽宁大学本科毕业论文格式检查。贡献前请先确认改动是否落在当前产品边界内：本地 `.docx`、单文档、审查与生成修复副本。

## 开发环境

```bash
python3 -m pip install -U pip
python3 -m pip install '.[api,dev]'
python3 -m pytest -q
```

## 提交要求

- 新增 runtime 规则时，同时更新测试和 `config/capability_matrix.md`。
- 新增 active profile additions 时，必须确认 runtime/checker 已接线。
- 用户可见错误必须说明发生了什么、下一步怎么做、是否可以重试。
- 不要引入第二套“看起来已实现、实际上未接线”的规则来源。
- 不要提交用户论文、运行输出、缓存、虚拟环境或本地状态目录。

## 发布前检查

```bash
python3 -m pytest -q
python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke
```

如果 release smoke 因网络超时失败，先确认依赖 wheelhouse 能否下载，再重试或在 CI 中启用 pip cache。
