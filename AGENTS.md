# 论文格式检查工具 - 项目上下文

## 项目概述

这是一个基于 OOXML 结构分析的论文格式审查与修复工具。

当前稳定主链是：

- `scripts/thesis_workbench.py`
- `scripts/thesis_tool/workflow.py`
- `scripts/audit_thesis.py`
- `scripts/fix_thesis.py`
- `scripts/_thesis_utils.py`

不要再把旧的 `format_thesis.py`、`fix_and_preview.py` 思路当成主流程；历史脚本目录已删除。

## 当前架构

```text
CLI
  -> thesis_workbench.py
    -> thesis_tool/workflow.py
      -> audit_thesis.py / fix_thesis.py
        -> _thesis_utils.py
          -> DocumentModel / ParagraphNode / section-module 分类
```

### 关键文件职责

- `scripts/thesis_workbench.py`：推荐用户入口
- `scripts/thesis_tool/scopes.py`：scope 定义与别名
- `scripts/thesis_tool/capabilities.py`：读取 `config/capability_matrix.md`
- `scripts/thesis_tool/workflow.py`：plan/apply/verify 编排
- `scripts/audit_thesis.py`：rule runtime、profile 解析、报告生成
- `scripts/fix_thesis.py`：按 scope 修复
- `scripts/_thesis_utils.py`：document_model、段落分类、section/bucket/module 工具
- `scripts/_profile_utils.py`：profile 别名和路径解析
- `scripts/sections/_xml_helpers.py`：低层 XML 操作

## Profile 约定

- `settings`：当前 runtime 实际消费
- `disabled_rules`：禁用当前 runtime 规则
- `additions`：当前已接入 runtime 的扩展规则
- `reference_additions` / `reference_overrides`：规范记录或待实现项，不进入当前 runtime

注意：

- `lnu-checker-2026.yaml` 的 active additions 已与当前 runtime 对齐

## 当前规则规模

- `cn-common` runtime：49 条
- `lnu-checker-2026` runtime：74 条

能力矩阵以 `config/capability_matrix.md` 为准，但前提是它必须与当前 runtime 同步。

## 模板注入

模板目录是 `config/templates/<profile-id>/`，不是仓库根目录的 `templates/`。

`fix_thesis.py` 当前会从 `config/templates/lnu/` 注入可用的：

- `styles.xml`
- `numbering.xml`
- `header1.xml`
- `header2.xml`

## 常用命令

```bash
# 审查
python3 scripts/thesis_workbench.py audit ~/Desktop/论文.docx --profile lnu

# 生成 scope 计划
python3 scripts/thesis_workbench.py plan ~/Desktop/论文.docx --profile lnu

# 按 scope 修复
python3 scripts/thesis_workbench.py apply ~/Desktop/论文.docx --profile lnu --scope abstract --output ~/Desktop/论文_摘要修复.docx

# 按 scope 复查
python3 scripts/thesis_workbench.py verify ~/Desktop/论文_摘要修复.docx --profile lnu --scope abstract

# 全量测试
python3 -m pytest -q
```

底层引擎仍可直接使用：

```bash
python3 scripts/audit_thesis.py ~/Desktop/论文.docx --profile lnu
python3 scripts/fix_thesis.py ~/Desktop/论文.docx --profile lnu --output ~/Desktop/论文_修复.docx
```

## 重要事实

- 封面不是当前自动修复主线的一部分
- 已失效的网页预览链路已移除，不存在可用的 `preview/` 目录
- 历史脚本目录已删除，不再保留“仅供参考”的旧脚本

## 开发约束

- 新增 runtime 规则时，同时更新测试和 `config/capability_matrix.md`
- 如果 profile 中新增 active `additions`，必须与 runtime/checker 对齐
- 不要再引入第二套“看起来已实现、实际上未接线”的规则来源
