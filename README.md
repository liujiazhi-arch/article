# 论文格式检查工具

基于 OOXML 结构分析的毕业论文格式审查与修复工具。

当前稳定主链：

- `scripts/thesis_workbench.py`：推荐用户入口
- `scripts/thesis_tool/workflow.py`：scope/workflow 编排层
- `scripts/audit_thesis.py`：审查引擎
- `scripts/fix_thesis.py`：修复引擎
- `scripts/_thesis_utils.py`：文档模型与共享工具

## 快速使用

在仓库根目录执行：

```bash
# 安装依赖
python3 -m pip install -r requirements.txt

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

## Scope

- `page`：页边距、页码、页脚等页面层设置
- `abstract`：中文摘要、英文摘要、关键词
- `toc`：目录重建、目录条目与 TOC 规则
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
│   └── legacy/
│       └── README.md
├── config/
│   ├── capability_matrix.md
│   ├── sources.yaml
│   ├── profiles/
│   │   ├── CN-Common.yaml
│   │   ├── lnu-checker-2026.yaml
│   │   └── lnu-undergraduate.yaml
│   └── templates/
│       └── lnu/
├── references/
├── tests/
└── package.json
```

## Runtime 规则规模

- `cn-common` 当前 runtime：49 条规则
- `lnu-checker-2026` 当前 runtime：73 条规则

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

当前全量回归基线：`142 passed`

## 依赖

- Python 3
- `python-docx`
- `PyYAML`
- `pytest`（运行测试时需要）

可选：

- `package.json` 提供了对 `thesis_workbench.py` 的 npm script 包装，但主链本质仍是 Python CLI
