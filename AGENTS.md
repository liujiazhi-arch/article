# 论文格式检查工具 - 项目上下文

## 项目概述

这是一个基于 OOXML 结构分析的论文格式审查与修复工具。

## 前端 UI 记忆与字体规范

后续只要处理本项目的前端、原型页、主题页、字体、字号、排版、玻璃态 UI、背景图或视觉资产，必须先读取并遵守：

- `docs/FRONTEND_UI_STYLE_GUIDE.md`
- 如会话可识别，使用本地 skill：`impeccable-image-theme`

这些规则是从用户已确认的前端调整中沉淀出来的项目记忆，优先级高于临时审美猜测。

### 前端 skill 路由

未来做前端时按任务选择技能，不要只凭当前模型审美直接改：

- `frontend-architecture-rules`：任何前端页面、组件、主题、路由、样式结构修改都先用它定边界、token、验证方式。
- `impeccable-image-theme`：当任务涉及参考网站图、截图、生图、主题图、视觉方向提取、配色、材质、字体气质、主题资产或让 UI 匹配图片时必须使用。
- `gpt-image-2-generator` 或系统图像生成能力：当现有图片不够、主题资产断裂、需要 hero / workflow / PDF / result / history 配套图时使用。
- `image-to-code-skill`：当需要从视觉稿或生成图落成页面结构时使用。
- `playwright` 或 Browser：前端改完必须做真实浏览器截图和控制台检查。
- `taste-skill`：只作为审美辅助，不得覆盖本文件和 `FRONTEND_UI_STYLE_GUIDE.md` 中已确认的项目偏好。

### 图像驱动前端工作流

本项目后续做主题化前端时，优先采用下面的工作流：

```text
参考图或生成图
  -> 提取视觉方向
  -> 生成或补齐配套图
  -> 定主题 token、配色、字体、材质
  -> 生成匹配 UI 组件
  -> 浏览器截图和控制台校验
```

不要只换一张大背景就开始写 UI。每个主题至少要检查 `hero`、功能地图、工作台、PDF 复核、历史、结果页是否有一致的图像和材质语言。

核心要求：

- 用户是学生，所有可见文案必须面向学生说话，不要写“不是给学生看”“普通学生”这类表达。
- 可见 UI 文案要短句化。中文同一可视行尽量不要出现逗号、句号、冒号、顿号等标点；需要停顿时改为换行、分卡片、分标签或用空格分隔。
- 不把开发态术语直接给学生看，例如 `/jobs/{id}`、`queued`、`running`、`failed`、`JSON`、`bbox`、`report artifact`、`rule_id`。改成“处理进度”“下一步提示”“需要你确认”“报告文件”“问题位置”等学生能理解的说法。
- 字体和字号以“愿意读、读得清”为第一目标。重要说明不要使用 11-12px 小字；玻璃面板里的正文通常用 15-16px，卡片标题 16-17px，步骤块 15px 起。
- 封面或主题页的大标题不能只共用一套渐变文字再换两个颜色；每个主题都要有自己的字体气质、色温、阴影或光带等材质细节。
- 学校名应整体排版，例如 `辽宁大学` 必须放在同一行；长标题优先拆成语义明确的固定行，不要交给浏览器自动断开。
- 玻璃态不是把文字也做淡。玻璃面板必须有足够深的稳定底色，正文对比度要高；只允许辅助说明使用低透明度。
- 避免大段文字堆在同一块面板里。功能说明应拆成短标题加一行说明的卡片，必要时增大卡片高度、行距和间距。
- 不要把内容挤在上半部分并留下大块空白。流程、状态、历史、结果类页面要纵向分布，空白要服务于阅读节奏。
- 白色实底卡片会破坏当前雨后/玻璃主题。除非是刻意的纸张语义，否则优先使用深色半透明玻璃底。
- 每个主题都要有一致的资产链路。新增或切换主题时，不要让雨后主题继承银杏/清晨的内部背景板；至少检查 `hero`、`asset-board`、`workflow-board`、`pdf-board`、`result-board` 是否匹配。

当前稳定主链是：

- `scripts/thesis_workbench.py`
- `scripts/thesis_tool/scope_plan.py`
- `scripts/thesis_tool/workflow.py`
- `scripts/audit_thesis.py`
- `scripts/fix_thesis.py`
- `scripts/_thesis_utils.py`

不要再把旧的 `format_thesis.py`、`fix_and_preview.py` 思路当成主流程；历史脚本目录已删除。

## 当前架构

```text
CLI
  -> thesis_workbench.py
    -> thesis_tool/scope_plan.py (plan)
    -> thesis_tool/workflow.py (apply / verify)
      -> audit_thesis.py / fix_thesis.py
        -> _thesis_utils.py
          -> DocumentModel / ParagraphNode / section-module 分类
```

### 关键文件职责

- `scripts/thesis_workbench.py`：推荐用户入口
- `scripts/thesis_tool/scopes.py`：scope 定义与别名
- `scripts/thesis_tool/capabilities.py`：读取 `config/capability_matrix.md`
- `scripts/thesis_tool/scope_plan.py`：审查结果到 scope plan 的唯一组装入口
- `scripts/thesis_tool/workflow.py`：apply/verify 编排
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

- 公开 runtime 只有 `lnu-checker-2026`：75 条规则
- `CN-Common.yaml` 保留为内部基线和 LNU 继承来源，不作为公开 profile catalog 项

能力矩阵以 `config/capability_matrix.md` 为准，并只记录公开 LNU runtime 当前启用规则。

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
