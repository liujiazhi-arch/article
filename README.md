# 论文格式检查工具

基于 OOXML 结构分析的毕业论文格式审查与修复工具。

当前产品边界只保留单文档处理链路，不再提供批量处理入口。

保留能力：

- `audit`
- `plan`
- `preflight`
- `normalize`
- `apply`
- `verify`
- `render-verify`
- `article-local`
- `article-api`
- `article-doctor`
- `article-backup`
- `article-restore`
- `article-maintain`

运行产物默认只留在本地 `outputs/`，仓库内不再维护输出索引或里程碑记录。

当前稳定主链：

- `scripts/thesis_workbench.py`：推荐用户入口
- `scripts/thesis_tool/workflow.py`：scope/workflow 编排层
- `scripts/audit_thesis.py`：审查引擎
- `scripts/fix_thesis.py`：修复引擎
- `scripts/_thesis_utils.py`：文档模型与共享工具

## 快速使用

在仓库根目录执行：

```bash
# 安装当前仓库
python3 -m pip install -e .

# 全量审查
python3 scripts/thesis_workbench.py audit 你的论文.docx --profile lnu

# 按 scope 生成修复计划
python3 scripts/thesis_workbench.py plan 你的论文.docx --profile lnu

# 按 scope 修复
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu --scope abstract --output 修复后_摘要.docx
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu --scope toc --toc --output 修复后_目录.docx
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu --scope body_paragraphs --output 修复后_正文段落.docx

# 先看 dry-run 预览，不落盘
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu --scope headings --dry-run

# 只有显式传入时才重编号正文标题
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu --scope headings --renumber-headings --output 修复后_标题.docx

# 复查指定 scope
python3 scripts/thesis_workbench.py verify 修复后_正文段落.docx --profile lnu --scope body_paragraphs

# 查看可用 scope
python3 scripts/thesis_workbench.py scopes
```

如果要使用 `pyproject.toml` 里声明的 console scripts（包括 `article-local`、`article-api`、`article-doctor` 等），优先直接安装当前仓库：

```bash
python3 -m pip install -e '.[api]'
```

如果还要跑开发回归或 live HTTP smoke，再补开发依赖：

```bash
python3 -m pip install -e '.[api,dev]'
```

## 第一阶段支持场景

当前 profile catalog 会显式标出 `support_scenarios`、`document_types` 和 `support_level`，第一阶段先落这三类一等支持场景：

- `课程作业/基础论文`：基于 `cn-common`，适合作业稿、课程论文、通用基础论文
- `普通论文或综述`：基于 `cn-common`，适合普通论文、文献综述等非学校专属模板场景
- `学校学位论文`：基于学校 profile，当前只维护 `lnu-checker-2026` 一套辽大规则

查看方式：

```bash
python3 scripts/thesis_workbench.py profiles
article-local profiles
```

如果要接本地网页或外部调用，`GET /profiles` 返回的 profile catalog 也会直接带这些场景字段。

## Scope

- `page`：页边距、页码、页脚等页面层设置
- `abstract`：中文摘要、英文摘要、关键词
- `toc`：目录补全/规范、目录条目与 TOC 规则
- `headings`：各级标题、编号、分页
- `body_paragraphs`：正文段落、空格、标点、正文内引用、公式正文相关规则
- `figures_tables`：图题、表题、图片段落、表格边框和表格内容
- `references`：参考文献列表、编号、缩进、标点
- `acknowledgement`：致谢正文
- `appendix`：附录正文

推荐顺序：

1. `plan`
2. `apply --scope abstract`
3. `apply --scope toc`
4. `apply --scope body_paragraphs`
5. 按需修 `headings` / `figures_tables` / `references`
6. 每修完一类立刻 `verify --scope ...`

补充说明：

- `headings` 默认只修格式，不自动改写标题编号；只有显式传入 `--renumber-headings` 才会重编号。
- `apply --dry-run` 会输出预计触达模块、待补 Heading 样式段落数和目录/重编号状态，但不会写出文件。
- 若启用了 `--toc`，输出文档打开后如目录页码未刷新，请在 Word 中 `Ctrl+A` 后按 `F9` 更新域。
- 工具当前默认保留现有封面，不再对封面文字和封面布局做自动归一化；后续修复默认只动正文、目录、图表、参考文献等正文链路。除非你明确要求，否则不再碰任何人的封面。

## WPS 版式复核

这套工具当前分两层工作：

- 结构层：由 `audit / diagnose / apply / verify` 保证 OOXML 规则正确。
- 渲染层：由 Word/WPS 实际打开或导出 PDF，确认视觉版式是否紧凑。

如果用户明确说“以 WPS 排版结果为准”，尤其是遇到下面几类现象：

- 公式下方突然出现粗横线
- 图表不跨页，但页底或页中出现大块空白
- 前面空白刚消掉，后面又冒出新的空白页或空白段

推荐不要只跑 `figures_tables`，而是按下面顺序处理：

```bash
python3 scripts/thesis_workbench.py audit 你的论文.docx --profile lnu
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu \
  --scope headings \
  --scope figures_tables \
  --layout-rebalance \
  --output 修复后_WPS复核版.docx
python3 scripts/thesis_workbench.py verify 修复后_WPS复核版.docx --profile lnu \
  --scope headings \
  --scope figures_tables
```

如果用户已经回头改过正文内容，尤其是实验结果里的图表引用句、图注/表注、公式附近描述句，推荐把正文一起联动重跑：

```bash
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu \
  --scope body_paragraphs \
  --scope headings \
  --scope figures_tables \
  --layout-rebalance \
  --output 修复后_正文联动版.docx
```

原因：

- 有些 WPS 留白不是图块 spacing 问题，而是后续标题残留了 `pageBreakBefore`。
- 有些公式横线不是公式对象自身问题，而是“公式布局表”被误当成普通三线表。
- `--layout-rebalance` 解决的是图表对象块锚点位置，不会自动清理标题分页属性，所以图表问题经常需要和 `headings` 联动看。
- 正文一旦改写，图表引用句、图注/表注细节和公式附近引用上标都可能重新变化，所以只修图表往往不够。

渲染证据优先级：

- 最终版式判断以 WPS/Word 打开或导出的 PDF/页图为准。
- 工具不再保留内置预览渲染；Word 自动导出不可用时，先在 WPS/Word 手动导出 PDF，再传给 `--rendered-pdf`。
- 页面端和 API 现在按三种模式区分版式复核：
  - 默认用户模式：用户手动用 Word/WPS 导出 PDF，工具只分析真实 PDF；这是普通用户默认入口。
  - 高级模式：后端尝试连接 Microsoft Word 自动导出 PDF，适合本机调试；遇到权限、恢复弹窗或超时就改用默认用户模式。
  - Agent 候选稿模式：只生成可回退的 DOCX 候选稿，之后仍需导出 PDF 并用默认用户模式复核。
- 推荐让用户在 WPS/Word 中导出 PDF 后再复核：

```bash
python3 scripts/thesis_workbench.py render-verify 修复后_WPS复核版.docx --profile lnu \
  --scope headings \
  --scope figures_tables \
  --rendered-pdf 用户从WPS或Word导出的.pdf
```

当前已经内化进工具的经验包括：

- 公式布局表会跳过普通三线表修复，并清理历史边框残留。
- 含公式的正文段在保护公式对象的同时，仍会继续拆正文内的 `[N]` 引用上标。
- 公式下方“其中/式中”说明段里的英文符号会统一回正文风格：英文字体用 `Times New Roman`，像 `m1/m2/V1/A10/W0` 这类变量后缀会落成下角标。
- 图表重排会优先回到同一 `h2` 小节内更早的有效引用点。
- `h3/h4` 不再阻断图表回扫。
- 图表注释段也会补 `注 1)` 这类中数字间距。
- 普通非 `h1` 标题会清理遗留的 `pageBreakBefore`，减少 WPS 里的后置空白页。

## 主链架构

```text
用户 CLI
  -> scripts/thesis_workbench.py
    -> scripts/thesis_tool/workflow.py
      -> scripts/audit_thesis.py / scripts/fix_thesis.py
        -> scripts/_thesis_utils.py
          -> DocumentModel / ParagraphNode / section-module 分类
```

核心职责：

- `thesis_workbench.py`：统一 CLI 入口，屏蔽底层细节
- `workflow.py`：scope 规划、修复、复查
- `audit_thesis.py`：rule runtime、审查报告、profile 规则启用
- `fix_thesis.py`：按 scope 修复文档
- `_thesis_utils.py`：段落分类、section 划分、document_model、共享文本/XML 工具

## 目录结构

```text
论文格式检查工具/
├── scripts/
│   ├── thesis_workbench.py
│   ├── audit_thesis.py
│   ├── fix_thesis.py
│   ├── _thesis_utils.py
│   ├── _profile_utils.py
│   ├── thesis_tool/
│   │   ├── scopes.py
│   │   ├── capabilities.py
│   │   └── workflow.py
│   ├── sections/
│   │   └── _xml_helpers.py
│   ├── article_engine/
│   └── article_api/
├── config/
│   ├── capability_matrix.md
│   ├── sources.yaml
│   ├── profiles/
│   │   ├── CN-Common.yaml
│   │   └── lnu-checker-2026.yaml
│   └── templates/
│       └── lnu/
├── references/
└── tests/
```

## Runtime 规则规模

- `cn-common` 当前 runtime：49 条规则
- `lnu-checker-2026` 当前 runtime：74 条规则

规则能力清单见 `config/capability_matrix.md`。

## Profile 约定

- `settings`：当前代码实际消费的配置字段
- `disabled_rules`：显式禁用 runtime 规则
- `additions`：当前 profile 已接入 runtime 的扩展规则
- `reference_additions` / `reference_overrides`：规范记录或待实现项，不进入当前 runtime

## 模板注入

模板组件目录是 `config/templates/<profile-id>/`，不是仓库根目录的 `templates/`。

当前 `lnu` 的注入逻辑会尝试读取以下组件：

- `styles.xml`
- `numbering.xml`
- `header1.xml` / `header2.xml`

当前仓库已提供 `styles.xml`；若后续补充 `numbering.xml` / `header*.xml`，修复时会自动注入。

## 测试

```bash
python3 -m pytest -q
```

当前全量回归基线：`523 passed, 6 skipped, 1 xfailed`

## Article 后端原型

`article` 分身当前已经有可调用的本地后端原型，主入口在：

- `scripts/article_engine/service.py`
- `scripts/article_api/app.py`
- `scripts/article_api/jobs.py`
- `scripts/article_api/storage.py`
- `scripts/article_api/uploads.py`

推荐先用项目自己的 console script，而不是手写 `PYTHONPATH` 启动。

最省事的本地安装方式：

```bash
python3 scripts/install_article_local.py
```

如果你要更靠近“可交付给本地用户”的非 editable 安装，而不是继续把运行环境绑在当前仓库源码上，优先走：

```bash
python3 scripts/install_article_local.py --install-mode wheel
```

如果你已经在 wheel 路径上迭代本地交付，安装脚本现在还支持：

```bash
python3 scripts/install_article_local.py --install-mode wheel --upgrade
python3 scripts/install_article_local.py --install-mode wheel --rollback
```

脚本默认会：

- 在 `~/.article/venv` 创建虚拟环境
- 安装当前仓库的 `.[api]`
- 初始化 `~/.article/state` 和 `~/.article/runtime`
- 写出 `~/.article/article-local.env`
- 直接返回一组可复制执行的 `quickstart` 命令（`doctor / serve / maintain / backup / restore`）

补充说明：

- `--python` 既可以传绝对路径，也可以直接传 `python3.12` 这类在 `PATH` 里的解释器名。
- `--install-mode editable` 保持当前开发态安装；`--install-mode wheel` 会先在 `--artifact-dir` 构建 wheel，再从 wheel 做本地安装，更适合交付和升级验证。
- `--upgrade` 会自动切到 wheel 安装并把本次交付显式记为升级；`--rollback` 也会自动走 wheel 历史并尝试回装上一版。
- 用同一组 roots 重跑安装脚本时，已有 env 文件会被视为同内容 no-op；如果你改了 roots 或想强制刷新 env 文件，再加 `--overwrite-env`。

如果你只想验证安装链路，不拉依赖，也不做初始化：

```bash
python3 scripts/install_article_local.py --no-deps --skip-init
```

最小本地安装：

```bash
python3 -m pip install -U pip
python3 -m pip install -e '.[api]'
```

如果还要跑 article 的 live HTTP smoke 或补开发依赖，再装：

```bash
python3 -m pip install -e '.[api,dev]'
```

如果你已经用安装脚本写出了 env 文件，后续可以直接：

```bash
source ~/.article/article-local.env
article-local doctor
article-local serve
```

如果你没有 `source` env 文件，也可以继续显式走 `~/.article/venv/bin/article-local ...`。

安装完成后会得到这些本地命令：

- `article-local`：统一入口，所有子命令都从这里走
- `article-api`：等价于 `article-local serve`
- `article-doctor`：等价于 `article-local doctor`
- `article-maintain`：等价于 `article-local maintain`
- `article-backup`：等价于 `article-local backup`
- `article-restore`：等价于 `article-local restore`

先看帮助最稳妥：

```bash
article-local --help
article-local init --help
article-local serve --help
article-local profiles --help
article-api --help
article-doctor --help
article-maintain --help
```

当前可用 profile 可以直接列出来：

```bash
article-local profiles
python3 scripts/thesis_workbench.py profiles
```

现在 `profiles` 输出除了 profile id / alias / school，也会带第一阶段支持场景、文档类型和支持级别，方便前端或调用方直接决定入口文案。

如果后面接本地网页，不想先写一层 CLI 包装，`article-api` 现在也直接暴露了：

- `GET /profiles`
- `POST /audit`
- `POST /plan`
- `POST /verify`
- `POST /apply`
- `POST /jobs/verify`
- `POST /jobs/apply`

如果要本地启动 API，优先保证当前解释器里已经安装 `.[api]`；其中会包含：

- `fastapi`
- `uvicorn`
- `python-multipart`

如果要跑 live HTTP smoke，再额外保证解释器里有：

- `httpx`

安装后，推荐这样启动：

```bash
article-api --state-root ~/.article/state --runtime-root ~/.article/runtime
```

不走安装、只想临时从源码目录启动时，再退回模块方式：

```bash
PYTHONPATH=scripts python3 -m uvicorn article_api.app:create_app --factory
```

本地应用壳层完整命令示例：

```bash
article-local serve --state-root ~/.article/state --runtime-root ~/.article/runtime
article-local doctor --state-root ~/.article/state --runtime-root ~/.article/runtime
article-local maintain --state-root ~/.article/state --runtime-root ~/.article/runtime --vacuum
article-local backup ~/Desktop/article-backup.zip --state-root ~/.article/state --runtime-root ~/.article/runtime
article-local restore ~/Desktop/article-backup.zip --state-root ~/.article/state --runtime-root ~/.article/runtime --force

article-api --state-root ~/.article/state --runtime-root ~/.article/runtime
article-doctor --state-root ~/.article/state --runtime-root ~/.article/runtime
article-maintain --state-root ~/.article/state --runtime-root ~/.article/runtime --vacuum
article-backup ~/Desktop/article-backup.zip --state-root ~/.article/state --runtime-root ~/.article/runtime
article-restore ~/Desktop/article-backup.zip --state-root ~/.article/state --runtime-root ~/.article/runtime --force
```

`article-local` 是统一入口；`article-api`、`article-doctor`、`article-maintain`、`article-backup`、`article-restore` 是安装后可直接调用的等价便捷别名。

推荐按这条本地用户流程使用：

### 1. 先初始化本地运行壳

```bash
article-local init \
  --state-root ~/.article/state \
  --runtime-root ~/.article/runtime \
  --write-env ~/.article/article-local.env
```

`init` 会做这几件事：

- 初始化 SQLite 状态库
- 预创建 `jobs / uploads / staging` 目录
- 可选写出环境变量文件
- 直接返回下一步应该执行的 `doctor` / `serve` 命令

如果写了 env 文件，后续可以在 shell 里加载：

```bash
source ~/.article/article-local.env
```

如果当前 `article-local` 是从已安装的虚拟环境里执行的，生成的 env 文件还会把对应 `venv/bin` 预加到 `PATH`，这样后续可以直接敲 `article-local`、`article-api`、`article-doctor`。

如果你不想依赖环境变量，也可以始终在每条命令里显式传 `--state-root` / `--runtime-root`。

### 2. 首次启动前先跑 doctor

```bash
article-local doctor --state-root ~/.article/state --runtime-root ~/.article/runtime
```

`doctor` 现在优先给出“本地后端运维摘要”，重点看：

- `summary.headline`：当前能不能直接启动
- `summary.issues`：阻断项或运行告警
- `summary.recommended_actions`：下一步建议动作
- `checks`：storage、runtime_root、single-worker recovery、retention 的只读状态
- `workflow`：当前根目录下可直接复制执行的 `serve / maintain / backup / restore` 命令

建议场景：

1. 首次安装后先跑一次 doctor
2. 改过根目录或恢复过备份后再跑一次 doctor
3. 异常退出、怀疑任务卡死时再跑一次 doctor

### 3. 再启动本地 API

```bash
article-local serve --state-root ~/.article/state --runtime-root ~/.article/runtime
```

### 4. 运行中优先看只读 ops 接口

- `GET /ready`：检查 state root / schema / runtime_root 是否可用
- `GET /profiles`：返回当前可见 profile catalog，包含支持场景/文档类型/支持级别，供本地网页直接渲染学校/模板选择器
- `GET /ops/summary`：运维总览，先看它
- `GET /ops/storage`：只读看 SQLite 健康、schema、索引、表行数
- `GET /ops/runtime`：只读看 single-worker、active futures、recovery、heartbeat

### 5. 日常维护

```bash
article-local maintain --state-root ~/.article/state --runtime-root ~/.article/runtime
article-local maintain --state-root ~/.article/state --runtime-root ~/.article/runtime --vacuum
```

建议：

1. 日常只跑 `maintain`
2. 做过大量 cleanup 后，再按需补一次 `--vacuum`
3. 如果 doctor 报 storage 异常，先 `maintain`，再决定是否 restore

### 5.1 已下线的历史入口

本地批量处理入口已从当前主线移除。当前产品先聚焦单篇论文的上传、审查、修复、规范化、版式复核、任务历史、备份恢复和本机运维，避免旧的目录级批量处理继续拖大 CLI/API/job/UI 维护面。

### 6. 备份与恢复

```bash
article-local backup ~/Desktop/article-backup.zip \
  --state-root ~/.article/state \
  --runtime-root ~/.article/runtime

article-local restore ~/Desktop/article-backup.zip \
  --state-root ~/.article/state \
  --runtime-root ~/.article/runtime \
  --force
```

当前 restore 约定：

- 默认要求目标目录为空
- 只有显式 `--force` 才覆盖目标目录
- 会校验 backup manifest 的 schema 兼容性
- restore 前后都建议各跑一次 `article-local doctor`

当前 API 原型包含：

- 同步接口：`/health`、`/ready`、`/version`、`/profiles`、`/audit`、`/plan`、`/verify`、`/apply`
- upload 接口：`/uploads/docx`、`/uploads`、`/uploads/{upload_id}`、`/uploads/{upload_id}/cleanup`
- job 接口：`/jobs/verify`、`/jobs/apply`、`/jobs`、`/jobs/{job_id}`、`/jobs/{job_id}/inspect`、`/jobs/{job_id}/result`、`/jobs/{job_id}/cleanup`、`/jobs/{job_id}/retry`、`/jobs/{job_id}/artifacts/{artifact_role}/download`
- ops 接口：`/ops/retention/sweep`、`/ops/retention/run-defaults`、`/ops/summary`、`/ops/storage`、`/ops/runtime`

运行和排障时，先记住这几个边界：

- SQLite 状态根默认在 `.article_runtime/`；测试或并行运行时，优先显式隔离 `ARTICLE_API_STATE_ROOT`。
- `runtime_root` 用于 upload、job workspace 和运行产物；它和 SQLite 状态根不是一回事。
- `job.status` 只表示生命周期：`queued` / `running` / `succeeded` / `failed`。
- `summary.business_status` 才表示业务结论，不要把 worker timeout 或人工复核语义塞进 `job.status`。
- runtime 当前已补最小单 worker 元数据：`worker_model` / `lease_state` / `last_heartbeat_at` / `heartbeat_count`；它们只用于运行观测，不扩张 lifecycle 枚举。
- `wait_for_job(timeout=...)` 只是调用侧等待超时，不应改持久化状态。
- `cleanup` 只清理 job workspace 和 job 产物快照，不负责删除 upload registry 下的源文件；upload 生命周期由 upload cleanup 单独管理。
- upload-backed retry 会重新从 upload registry 取源文件；公开 `request` 仍不得泄漏内部执行 `file_path`。
- `runtime.events` 当前已提供最小结构化事件流：`job_queued`、`worker_started`、`attempt_started`、`attempt_failed`、`retry_scheduled`、`attempt_succeeded`、`job_failed`、`job_succeeded`、`recovered_as_failed`。
- 如果 worker 已返回，但后续在 summary / artifact 冻结阶段抛出异常，job 会立即落成 `failed`，而不是先写出不一致状态再等 stale recovery 兜底。
- `POST /ops/retention/sweep` 当前提供最小 retention automation：按 age threshold 清理已完成 job 和 upload，并把 cleanup 审计 `policy` 标记为 `retention`；默认仍不启后台守护。
- `POST /ops/retention/run-defaults` 当前支持读取环境变量里的 retention 默认值执行 sweep。
- 当前还支持机会式 autorun retention：在本地单机 API 的写操作入口按间隔检查是否需要自动 sweep，不启独立后台线程。
- `GET /ready` 当前提供最小 readiness：检查 SQLite 状态根与 schema version 是否可读，并确认 `runtime_root` 可写。
- `GET /version` 当前固定返回服务版本与 API 版本约定。
- `GET /ops/summary` 当前优先提供本地运维总览：总体状态、checks、job/upload/cleanup 摘要、runtime 摘要、retention 摘要。
- `GET /ops/storage` 当前保留底层存储详情，同时额外给出 schema / 索引 / db 大小 / integrity 的运维摘要。
- `GET /ops/runtime` 当前保留底层 runtime snapshot，同时额外给出 single-worker / recovery / heartbeat 的运维摘要。
- `article-doctor` 会直接输出上述本地运维摘要，适合不启动 HTTP 时做本机自检。
- `article-maintain` 当前提供最小存储维护：`ANALYZE`，可选 `VACUUM`，并返回维护摘要和最新存储摘要。
- `article-backup` / `article-restore` 当前提供最小本机备份恢复：按“状态数据”和“运行产物”分层打包，不把 upload/job/runtime 语义混进 SQLite 状态层；restore 会校验备份 manifest 的 schema 兼容性，并拒绝越界写出恢复根目录。
- `ARTICLE_API_RUNTIME_ROOT` 现在可以像 `ARTICLE_API_STATE_ROOT` 一样通过环境变量显式覆盖默认运行目录。
- storage 当前已进入显式 migration chain：`0 -> 1 -> 2`；其中 `2` 会补索引治理，不再靠“直接写到最新版本号”完成升级。
- `ARTICLE_API_JOB_HEARTBEAT_STALE_SECONDS` 当前只用于运行观测，不改变 lifecycle；超过阈值的活动 job 会在 runtime 摘要里标记为 stale heartbeat。
- `ARTICLE_API_JOB_RECOVERY_GRACE_SECONDS` 当前控制“无 active future 时延迟多久再收口为 failed”；它只影响恢复判定时机，不扩 lifecycle，不改变冻结结果语义。
- 当前本地单机原型已显式不做：`cancel`、`priority`、`queue backpressure`、多 worker 调度。
- 依赖 SQLite 状态根的 article 测试不要并行跑多套共享默认状态根；要么串行，要么显式隔离 `ARTICLE_API_STATE_ROOT`。

Article 后端相关回归：

仓库瘦身与本地交付边界验证：

```bash
python3 -m pytest -q tests/test_repo_hygiene.py tests/test_article_install_script.py tests/test_packaging_metadata.py tests/test_article_local_app.py tests/test_article_http_smoke.py
```

其中 `test_repo_hygiene.py` 专门防止 `runs/`、`output/`、`.article_runtime/`、`.tmp_render_probe_out/` 等运行态重新混进源码边界。

```bash
python3 -m pytest -q tests/test_article_api.py tests/test_article_jobs.py tests/test_article_storage.py tests/test_article_uploads.py tests/test_article_engine.py tests/test_article_http_smoke.py tests/test_article_local_app.py tests/test_packaging_metadata.py
/Users/apple/Desktop/article/.venv/bin/python -m pytest -q tests/test_article_http_smoke.py
python3 -m pytest -q
```

当前基线：

- article 后端全套：`148 passed`
- live HTTP smoke：`6 passed`
- 全量回归：`523 passed, 6 skipped, 1 xfailed`

## 依赖

- Python 3
- `python-docx`
- `PyYAML`
- `pytest`（运行测试时需要）

当前不再保留 npm 包装入口；主链统一走 Python CLI 与 `pyproject.toml` 里的 console scripts。
