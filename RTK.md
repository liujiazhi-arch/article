# RTK 协作补充

本文件补齐 `AGENTS.md` 中的 `@RTK.md` 引用，避免新会话加载项目说明时出现断链。

## 全局引用规则

- `RTK.md` 是全局 token 节省规则文件，不是只能存在于某个项目根目录的源码文件。
- 如果当前项目根目录解析不到 `@RTK.md`，不要因为“找不到文件”停止；按顺序回退到 `/Users/apple/RTK.md`、`/Users/apple/.codex/RTK.md`、`/Users/apple/.claude/RTK.md`、`/Users/apple/.codex/skills/rtk-token-optimizer/SKILL.md`。
- 用户口语里说 `RDK.md` 时，除非上下文明确指向别的文件，否则按 `RTK.md` 处理。
- 所有 AI 编码客户端在代码开发、调试、仓库探索、测试、lint 和大输出命令中默认贯彻 RTK 规则。
- 如果某个项目必须有本地 `@RTK.md` 才不报警，就把全局 `RTK.md` 同步到项目根目录，不要另起一套规则。

## 仓库瘦身边界

- 源码、配置、测试、少量长期参考资料可以进入 Git。
- 日常运行态、渲染证据、临时输出和本机 API 数据不进入 Git。
- `outputs/` 只保留索引和里程碑目录可追踪；普通输出继续默认忽略。
- `runs/`、`output/`、`.article_runtime/`、`.tmp_render_probe_out/` 都属于本地运行态。

## 验证习惯

- 声称完成前运行真实命令。
- 涉及本地交付链时，优先验证 `article-local`、安装脚本、doctor/serve/maintain 相关测试。
- 涉及仓库瘦身时，至少运行仓库卫生测试并检查 `git status --short --ignored` 的边界是否符合预期。
