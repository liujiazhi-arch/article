# RTK 协作补充

本文件补齐 `AGENTS.md` 中的 `@RTK.md` 引用，避免新会话加载项目说明时出现断链。

## 仓库瘦身边界

- 源码、配置、测试、少量长期参考资料可以进入 Git。
- 日常运行态、渲染证据、临时输出和本机 API 数据不进入 Git。
- `outputs/` 只保留索引和里程碑目录可追踪；普通输出继续默认忽略。
- `runs/`、`output/`、`.article_runtime/`、`.tmp_render_probe_out/` 都属于本地运行态。

## 验证习惯

- 声称完成前运行真实命令。
- 涉及本地交付链时，优先验证 `article-local`、安装脚本、doctor/serve/maintain 相关测试。
- 涉及仓库瘦身时，至少运行仓库卫生测试并检查 `git status --short --ignored` 的边界是否符合预期。
