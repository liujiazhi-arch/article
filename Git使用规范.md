# 论文格式检查工具 Git 使用规范

## 目标

这套 Git 只做三件事：

- 保存工具代码、配置、测试和规则记忆的历史
- 让每次规则接入、回归修复、经验沉淀都可追踪、可回退
- 不把每次生成的论文产物、临时输出、系统噪音带进版本库

## 仓库分工

Git 管：

- `scripts/`
- `config/`
- `tests/`
- `references/`
- `README.md`
- `CLAUDE.md`
- `项目修改日志.md`
- `当前交接状态.md`
- `记忆机制.md`
- `记忆/`

Git 默认不管：

- `outputs/` 根目录下的生成文档
- 单次运行产生的局部产物
- 缓存、临时文件、系统噪音

Git 定向纳管：

- `outputs/index/`
  - 追踪输出索引和里程碑记录
- `outputs/milestones/`
  - 只追踪少量关键成果

## 分支设计

推荐只保留一条稳定主线和少量短分支：

- `main`
  - 稳定主链
  - 只放已经验证通过的项目级变更
- `feat/<scope>`
  - 新增规则或新能力
  - 例如 `feat/references-lnu`
- `fix/<scope>`
  - 修主链 bug 或回归
  - 例如 `fix/figure-spacing`
- `docs/<topic>`
  - 只改记忆文件、项目日志、说明文档
  - 例如 `docs/memory-update`

原则：

- 分支尽量短命，改完就合回 `main`
- 不长期堆很多并行分支
- 单篇论文处理结果不要单独建分支

## 推荐提交粒度

一次提交只做一类事情，避免把几种性质不同的修改混在一起。

推荐提交类型：

- `feat:` 新能力、新规则接入
- `fix:` 主链 bug 修复
- `test:` 新增或调整回归测试
- `docs:` 记忆文件、日志、说明更新
- `refactor:` 不改行为的内部整理

示例：

```bash
git commit -m "feat: 接入辽大参考文献悬挂缩进参数"
git commit -m "fix: 修正图块前后留白结算"
git commit -m "docs: 更新项目记忆与交接状态"
```

## 日常工作流

### 1. 开始改动前

先看：

1. `项目修改日志.md`
2. `当前交接状态.md`
3. 对应专项记忆文件

然后拉一个短分支：

```bash
git checkout -b feat/你的主题
```

### 2. 修改过程中

如果是项目级修改，收尾时同步更新：

1. `项目修改日志.md`
2. `当前交接状态.md`
3. 对应专项记忆
4. `记忆/每日记录/YYYY-MM-DD.md`

### 3. 提交前

至少确认三件事：

1. 变更文件里没有无关的 `outputs/` 根目录产物
2. 相关测试或最小验证已经跑过
3. 记忆文件和代码状态一致

如果本轮需要让 Git 看见输出结果，再补一件事：

4. 运行 `python3 scripts/output_versioning.py manifest`

### 4. 合回主线

验证通过后回到 `main`，再合并：

```bash
git checkout main
git merge --no-ff feat/你的主题
```

## 这个项目最重要的 Git 原则

- Git 是“历史系统”，不是“记忆替代品”
- 记忆文件继续作为下一次 Codex 接手时的主入口
- 如果规则已经主链化，后续新论文再出同类问题，应先判定为工具问题
- 不要把用户论文原件或修复产物提交进 Git
- 不要为了保存某一次论文处理结果，污染稳定主链
- 输出结果采用“默认忽略、索引纳管、里程碑提升”的三层策略

## 输出版本控制

当前 `outputs/` 采用三层管理：

### 1. 工作产物

- 位置：`outputs/` 根目录
- 策略：默认忽略
- 用途：中间步骤和日常生成结果

### 2. 输出索引

- 位置：`outputs/index/`
- 策略：进入 Git
- 用途：让 Git 看见当前有哪些结果，但不强行追踪所有 `.docx`

刷新命令：

```bash
python3 scripts/output_versioning.py manifest
```

### 3. 里程碑产物

- 位置：`outputs/milestones/`
- 策略：只追踪少量关键成果
- 用途：保存少数值得回归对照的代表性文件

提升命令：

```bash
python3 scripts/output_versioning.py promote outputs/某个文件.docx --note "用途说明"
```

## 推荐首轮提交结构

这个项目后续建议优先形成这样的首轮历史：

1. `chore: 初始化 git 基础设施`
2. `docs: 接入项目记忆机制与专项规则拆分`
3. `feat/fix/test` 按实际功能继续推进

这样后面回看历史时，会很容易区分：

- 哪些是基础设施
- 哪些是规则能力演进
- 哪些是纯记忆沉淀
