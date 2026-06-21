# 辽宁大学毕业论文格式检查与修复工具

[![CI](https://github.com/liujiazhi-arch/lnu-thesis-format-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/liujiazhi-arch/lnu-thesis-format-tool/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/liujiazhi-arch/lnu-thesis-format-tool?include_prereleases&label=release)](https://github.com/liujiazhi-arch/lnu-thesis-format-tool/releases)
[![License](https://img.shields.io/github/license/liujiazhi-arch/lnu-thesis-format-tool)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)

GitHub Beta 目标：给辽宁大学本科毕业论文提供本地 `.docx` 格式审查和分 scope 修复。工具基于 OOXML 结构分析运行，默认只处理单文档，生成修复副本，不覆盖原文档。

普通学生首选 Windows 本地网页 zip：下载、解压、双击 `启动论文格式检查.bat`，浏览器会自动打开本机网页。论文在本地处理，默认不要上传论文到外部服务器。

产品分发边界：GitHub 只托管代码、文档、CI 和发布包，用于让用户从 Release 下载本地网页包；GitHub 不同步你的论文、API key、本地日志、运行缓存或修复稿。

## 下载

当前公开 Beta Release：

- [v0.1.1-beta - Windows 本地网页包](https://github.com/liujiazhi-arch/lnu-thesis-format-tool/releases/tag/v0.1.1-beta)
- 普通用户下载 `lnu-thesis-local-windows.zip`
- `lnu-thesis-local-windows.zip.sha256` 是校验文件，普通用户可以不下载

不要在压缩包预览窗口里直接运行。请先完整解压 zip，再双击 `启动论文格式检查.bat`。

## 普通学生怎么用

1. 从 GitHub Release 下载 `lnu-thesis-local-windows.zip`。
2. 完整解压，双击 `启动论文格式检查.bat`。
3. 在本机网页上传 Word/WPS 保存的 `.docx`，生成修复方案，下载修复副本，并用 Word/WPS 人工复核。

这里的“上传”指上传到你电脑上的本地网页服务，不是上传到 GitHub 或云端。

## 界面预览

![本地网页首页](docs/assets/local-console-home.png)

![修复完成后需要人工确认](docs/assets/local-console-repaired.png)

## 平台状态

| Platform | Current status | User entry |
| --- | --- | --- |
| Windows | Beta supported | `lnu-thesis-local-windows.zip` |
| macOS | Planned experimental package | Not yet released |
| Linux | Developer/source use only | `pip install '.[api]'` |

第一版目标是接近常见 GitHub 工具的“下载 zip、解压、双击运行”体验，不等同于完整桌面安装包、DMG、MSI、代码签名或自动更新应用。本地网页支持手动检查 GitHub Release 新版本；发现新版后仍需要用户手动下载新版 zip，不会自动下载或安装更新。

## 当前承诺

- 只公开支持：辽宁大学本科毕业论文（`lnu-checker-2026`，常用别名 `lnu`）。
- `lnu-checker-2026` 当前 runtime: 75 条。
- 本地处理：论文文件留在你的电脑上，默认不要上传论文到外部服务器。
- GitHub 发布：软件版本可以从 GitHub Release 下载；论文、密钥、日志、缓存和反馈原始数据不进入 GitHub。
- 手动检查 GitHub Release 新版本：只请求软件版本元数据，不上传论文、修复稿、任务记录、本地路径或日志，也不会自动下载或安装更新。
- 生成修复副本：原文件不会被直接改写。
- 部分规则自动修复：如标题、正文段落、目录、图表、参考文献等 scope 内的可控格式项。
- 部分规则提示人工复核：封面、WPS/Word 最终分页、学校或导师临时要求仍需要人工确认。

不要把 Beta 版理解成一键保证最终提交版完全合规。第一版产品边界是：发现问题、生成候选修复副本、减少重复手工排版工作。

## 开发者安装

建议使用 Python 3.11 或 3.12。

```bash
python3 -m pip install -U pip
python3 -m pip install '.[api]'
```

开发者如果要跑测试：

```bash
python3 -m pip install '.[api,dev]'
```

当前 GitHub Beta 推荐使用新的开发者命令入口：

```bash
lnu-thesis-local doctor
lnu-thesis-local serve
```

启动后在浏览器打开命令行输出的本地地址，上传 `.docx`，选择需要修复的 scope，等待任务完成后下载修复副本。

安装后可用入口包括：

- `lnu-thesis-local`
- `lnu-thesis-api`
- `lnu-thesis-doctor`
- `lnu-thesis-backup`
- `lnu-thesis-feedback`
- `lnu-thesis-restore`
- `lnu-thesis-maintain`
- `article-local`
- `article-api`
- `article-doctor`
- `article-backup`
- `article-feedback`
- `article-restore`
- `article-maintain`
- `thesis-workbench`

`article-*` 命令暂时保留为兼容入口，新文档和新发布包优先使用 `lnu-thesis-*`。

## 命令行使用

```bash
# 查看公开 profile
thesis-workbench profiles
lnu-thesis-local profiles

# 预检查和结构整理
thesis-workbench preflight 你的论文.docx --profile lnu
thesis-workbench normalize 你的论文.docx --profile lnu --output 结构整理后.docx

# 全量审查
thesis-workbench audit 你的论文.docx --profile lnu
thesis-workbench audit 你的论文.docx --profile lnu --rendered-pdf 手动导出的.pdf

# 生成 scope 计划
thesis-workbench plan 你的论文.docx --profile lnu

# 按 scope 修复
thesis-workbench apply 你的论文.docx --profile lnu --scope abstract --output 修复后_摘要.docx
thesis-workbench apply 你的论文.docx --profile lnu --scope toc --toc --output 修复后_目录.docx
thesis-workbench apply 你的论文.docx --profile lnu --scope body_paragraphs --output 修复后_正文段落.docx

# 先看 dry-run 预览，不落盘
thesis-workbench apply 你的论文.docx --profile lnu --scope headings --dry-run

# 只有显式传入时才重编号正文标题
thesis-workbench apply 你的论文.docx --profile lnu --scope headings --renumber-headings --output 修复后_标题.docx

# 复查指定 scope
thesis-workbench verify 修复后_正文段落.docx --profile lnu --scope body_paragraphs

# 使用 Word/WPS 导出的 PDF 做渲染复核
thesis-workbench render-verify 修复后_正文段落.docx --profile lnu --rendered-pdf 手动导出的.pdf

# 查看 scope
thesis-workbench scopes
```

仍可从源码目录直接运行脚本：

```bash
python3 scripts/thesis_workbench.py audit 你的论文.docx --profile lnu
python3 scripts/thesis_workbench.py plan 你的论文.docx --profile lnu
python3 scripts/thesis_workbench.py apply 你的论文.docx --profile lnu --scope abstract --output 修复后_摘要.docx
python3 scripts/thesis_workbench.py verify 修复后_摘要.docx --profile lnu --scope abstract
```

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

## 支持场景

当前只支持辽宁大学本科毕业论文。公开入口只有一个 profile：`lnu-checker-2026`。`CN-Common.yaml` 保留为内部基线和 LNU 继承来源，不作为公开产品 profile。

封面不是当前自动修复主线的一部分。工具默认保留现有封面，不再对封面文字和封面布局做自动归一化。

## 常见问题

**上传后提示不是完整 docx 包**

请确认文件是 Word/WPS 保存的 `.docx`，不是改后缀的 `.doc`、PDF、压缩包或临时文件。建议用 Word/WPS 另存为 `.docx` 后重试。

**目录页码需要复核**

若启用了 `--toc`，工具会直接写入可见的自动目录域结果。之后如果继续修改正文导致分页变化，再在 Word/WPS 中更新目录域并复核页码。也可以把 Word/WPS 导出的 PDF 传给 `audit --rendered-pdf`，工具会把目录条目页码和正文实际渲染页不一致的问题合并进审查结果。

**WPS 打开后分页仍不完全一致**

结构层审查不能替代 Word/WPS 的最终渲染复核。最终提交前请用你实际提交的平台打开修复副本，再人工确认目录、分页、图表、公式和参考文献。

## 隐私

默认运行方式是本地处理，不需要把论文传到外部服务器。详见 [docs/PRIVACY.md](docs/PRIVACY.md)。

版本检查只会请求 GitHub Release 元数据，用于提示软件是否有新版本；它不上传论文、修复稿、任务记录、本地路径或日志。

## 文档

- 用户指南：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- 常见故障排查：[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- 路线图：[docs/ROADMAP.md](docs/ROADMAP.md)
- 开发指南：[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- 隐私说明：[docs/PRIVACY.md](docs/PRIVACY.md)
- 安全策略：[SECURITY.md](SECURITY.md)
- 免责声明：[docs/DISCLAIMER.md](docs/DISCLAIMER.md)
- 版本记录：[CHANGELOG.md](CHANGELOG.md)

## 开发状态

当前稳定主链：

```text
CLI
  -> thesis_workbench.py
    -> thesis_tool/workflow.py
      -> audit_thesis.py / fix_thesis.py
        -> _thesis_utils.py
          -> DocumentModel / ParagraphNode / section-module 分类
```

核心入口：

- `scripts/thesis_workbench.py`：推荐用户入口
- `scripts/thesis_tool/workflow.py`：scope/workflow 编排层
- `scripts/audit_thesis.py`：审查引擎
- `scripts/fix_thesis.py`：修复引擎
- `scripts/_thesis_utils.py`：文档模型与共享工具

测试：

```bash
python3 -m pytest -q
python3 scripts/release_smoke.py --work-dir /tmp/article-release-smoke
```
