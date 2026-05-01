# 辽大专项实现记忆

## 当前口径

- 当前唯一主 profile：`config/profiles/lnu-checker-2026.yaml`
- 可用入口：`lnu`、`lnu-checker`、`lnu-checker-2026`
- 已移除：`lnu-undergraduate` 入口和第二套辽大 profile
- 2026-05-01 用户提供的最新格式要求截图优先级最高
- 2026-04-17 checker 批注和旧样本只作历史参考

## 已稳定支持

- `diagnose --profile lnu` 可输出目录状态、序言编号状态、标题链、表格伪标题风险、样式/文本层级冲突和建议动作
- 目录链路支持识别手工目录、自动目录域、重复目录，并可清理旧目录后重建 TOC 域
- 标题链支持识别错样式标题、误挂 Heading 的正文段，并避免表格内容污染重编号
- 图块按“图片本体 + 图名 + 图注”整体处理
- 表块按“表名 + 表格 + 表注”整体处理
- 公式布局表会跳过普通三线表修复，历史残留边框会被清理
- 普通正文标题会清掉历史 `pageBreakBefore`
- 图表重排可通过 `--layout-rebalance` 显式开启
- 参考文献编号统一为 `[N]` 后保留一个半角空格，再接正文内容
- 参考文献悬挂缩进为 `420 / -420`
- 摘要、目录、正文混排空格按最新规则紧凑化，数字和单位之间保留空格

## 执行顺序建议

处理辽大论文时优先：

```bash
python3 scripts/thesis_workbench.py audit 输入.docx --profile lnu
python3 scripts/thesis_workbench.py diagnose 输入.docx --profile lnu --compact
python3 scripts/thesis_workbench.py plan 输入.docx --profile lnu
```

若涉及目录：

```bash
python3 scripts/thesis_workbench.py apply 输入.docx --profile lnu --scope toc --toc --output 输出.docx
```

若涉及图表/WPS 留白：

```bash
python3 scripts/thesis_workbench.py apply 输入.docx --profile lnu \
  --scope headings \
  --scope figures_tables \
  --layout-rebalance \
  --output 输出.docx
```

若正文已经被用户重新修改，图表建议联动正文、标题和图表：

```bash
python3 scripts/thesis_workbench.py apply 输入.docx --profile lnu \
  --scope body_paragraphs \
  --scope headings \
  --scope figures_tables \
  --layout-rebalance \
  --output 输出.docx
```

## 高频事故与判断

- 目录问题要分结构层和渲染层：工具负责 TOC 结构，Word/WPS 负责刷新域。
- 图表留白不一定是 spacing，常见根因是对象块锚点太晚、后续标题残留分页、或 `h3/h4` 曾阻断回扫。
- 公式下方粗横线通常是公式布局表被误当普通表格套了三线表边框。
- 表名离表太远、表后与正文/图块挤在一起，应优先视为工具问题。
- 图题/表题和对象主体分居两页，应优先检查对象块分页保护。
- 中文摘要正文不能整段斜体，只允许学名片段斜体。
- 参考文献标题本身也可能异常，例如 `——`、空段或占位文本；这仍是待主链化缺口。
- 封面默认不改，除非用户明确要求。

## 规则接入检查表

新增辽大 runtime 规则时必须同时更新：

- `config/profiles/lnu-checker-2026.yaml`
- `scripts/audit_thesis.py`
- `scripts/fix_thesis.py` 或明确不可自动修复
- `scripts/thesis_tool/scopes.py`
- `config/capability_matrix.md`
- 对应测试

新增 profile `settings` 参数时必须确认：

- profile 已写入字段
- `build_profile_cfg()` 已加载
- audit/fix 运行时真正消费
- 测试覆盖运行时值

## 下一阶段缺口

- 野生文档结构自动判别和修复
- 自动目录的渲染闭环和 Word/WPS 刷新流程自动化
- 图表紧凑排版从启发式向更可靠的渲染反馈推进
- 参考文献标题占位符审查/修复主链化
- 多篇真实辽大论文的回归样本库
