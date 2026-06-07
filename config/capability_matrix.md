# capability_matrix.md — 辽宁大学 lnu-checker-2026 runtime 规则能力矩阵
# 更新日期：2026-06-04

## 说明

| 列名 | 说明 |
|------|------|
| ID | 规则编号 |
| 描述 | 规则内容简述 |
| check_level | Auto=程序自动判断 / Semi=程序定位后人工确认 / Manual=仅人工确认 |
| method | docx-structure=基于 OOXML 结构 / rendered-layout=依赖 Word 渲染 |
| 自动修复 | ✓=fix_thesis.py 已接入 / ✗=当前不自动修复 |
| 实现状态 | ✓=audit_thesis.py 当前 runtime 已启用 |

补充约定：

- 本矩阵只记录公开 LNU runtime 当前启用的 74 条规则。
- `CN-Common.yaml` 中被 LNU profile 禁用的内部基线规则不进入此表。
- 对 `config/profiles/lnu-checker-2026.yaml` 中已接入 runtime 的 `additions` 规则，若此表“自动修复”为 `✓`，对应条目应提供非空 `fix` 元数据说明；若为 `✗`，则保持 `fix: null` 或省略。

---

## 页面与页码

| ID | 描述 | check_level | method | 自动修复 | 实现状态 |
|----|------|------------|--------|----------|----------|
| P01 | 页边距 | Auto | docx-structure | ✓ | ✓ |
| P03 | 页码底端居中 | Auto | docx-structure | ✓ | ✓ |
| PG01 | 页码存在性 | Semi | docx-structure | ✓ | ✓ |
| FN01 | 脚注字号 | Auto | docx-structure | ✗ | ✓ |

## 正文与通用格式

| ID | 描述 | check_level | method | 自动修复 | 实现状态 |
|----|------|------------|--------|----------|----------|
| T01 | 正文中文字体 | Auto | docx-structure | ✓ | ✓ |
| T02 | 正文西文字体 | Auto | docx-structure | ✓ | ✓ |
| T03 | 正文字号 | Auto | docx-structure | ✓ | ✓ |
| T04 | 正文行距 | Auto | docx-structure | ✓ | ✓ |
| T05 | 正文首行缩进 | Auto | docx-structure | ✓ | ✓ |
| T06 | 正文两端对齐 | Auto | docx-structure | ✓ | ✓ |
| S03 | 正文段前段后间距 | Auto | docx-structure | ✓ | ✓ |
| PU01 | 中文正文不含英文半角标点 | Semi | docx-structure | ✓ | ✓ |
| PU02 | 省略号规范 | Semi | docx-structure | ✓ | ✓ |
| EQ01 | 公式段落居中 | Auto | docx-structure | ✓ | ✓ |
| EQ02 | 公式编号右对齐 | Semi | docx-structure | ✗ | ✓ |
| EQ03 | 正文公式引用格式 | Manual | docx-structure | ✗ | ✓ |

## 标题

| ID | 描述 | check_level | method | 自动修复 | 实现状态 |
|----|------|------------|--------|----------|----------|
| H01 | 一级标题格式 | Auto | docx-structure | ✓ | ✓ |
| H02 | 二级标题格式 | Auto | docx-structure | ✓ | ✓ |
| H03 | 三级标题格式 | Auto | docx-structure | ✓ | ✓ |
| H04 | 四级标题格式 | Auto | docx-structure | ✓ | ✓ |
| S01 | 标题段前段后间距 | Auto | docx-structure | ✓ | ✓ |
| S02 | 章标题前分页 | Auto | docx-structure | ✓ | ✓ |

## 图表与表格

| ID | 描述 | check_level | method | 自动修复 | 实现状态 |
|----|------|------------|--------|----------|----------|
| F01 | 图题格式 | Auto | docx-structure | ✓ | ✓ |
| F02 | 表题格式 | Auto | docx-structure | ✓ | ✓ |
| F05 | 图表题注字体 | Auto | docx-structure | ✓ | ✓ |
| F06 | 图片段落居中 | Auto | docx-structure | ✓ | ✓ |
| F07 | 图题末尾无句号 | Auto | docx-structure | ✓ | ✓ |
| TB01 | 三线表边框 | Auto | docx-structure | ✓ | ✓ |
| TB02 | 三线表无多余竖线 | Auto | docx-structure | ✓ | ✓ |
| TB03_LINE | 三线表栏目线 | Auto | docx-structure | ✓ | ✓ |
| TB03 | 续表表头重复 | Auto | docx-structure | ✓ | ✓ |

## 正文引用、关键词与参考文献

| ID | 描述 | check_level | method | 自动修复 | 实现状态 |
|----|------|------------|--------|----------|----------|
| C01 | 正文引用为上标 | Auto | docx-structure | ✓ | ✓ |
| C02 | 正文引用字体 | Auto | docx-structure | ✓ | ✓ |
| C03 | 正文引用在句末标点之前 | Auto | docx-structure | ✓ | ✓ |
| C04 | 正文中未上标的[N]引用 | Auto | docx-structure | ✓ | ✓ |
| R01 | 参考文献悬挂缩进 | Auto | docx-structure | ✓ | ✓ |
| R03 | 参考文献行距 | Auto | docx-structure | ✓ | ✓ |
| R04 | 参考文献编号不使用上标 | Auto | docx-structure | ✓ | ✓ |
| R05 | 参考文献编号格式 | Auto | docx-structure | ✗ | ✓ |
| KW01 | 关键词数量与样式 | Auto | docx-structure | ✓ | ✓ |
| KW02 | 关键词末尾标点 | Auto | docx-structure | ✓ | ✓ |

## 辽宁大学扩展（LNU）

| ID | 描述 | check_level | method | 自动修复 | 实现状态 |
|----|------|------------|--------|----------|----------|
| LNU_F01 | 图题点号编号格式（图X.X 后两个半角空格） | Auto | docx-structure | ✓ | ✓ |
| LNU_F02 | 表题点号编号格式（表X.X 后两个半角空格） | Auto | docx-structure | ✓ | ✓ |
| LNU_F03 | 图前图后空行（辽大） | Auto | docx-structure | ✓ | ✓ |
| LNU_F06 | 图题、英文题名与说明性图注版式（辽大） | Auto | docx-structure | ✓ | ✓ |
| LNU_F07 | 图表块同页/跨页保护（辽大） | Auto | docx-structure | ✓ | ✓ |
| LNU_FMT01 | 软回车换行 | Auto | docx-structure | ✓ | ✓ |
| LNU_FMT02 | 图片嵌入型/表格无环绕 | Auto | docx-structure | ✓ | ✓ |
| LNU_TB01 | 表格外框1.5pt内线0.5pt | Auto | docx-structure | ✓ | ✓ |
| LNU_TB02 | 表格内容宋体五号 | Auto | docx-structure | ✓ | ✓ |
| LNU_TB03 | 表格内容1.5倍行距 | Auto | docx-structure | ✓ | ✓ |
| LNU_TB04 | 表块留白与表题贴表 | Auto | docx-structure | ✓ | ✓ |
| LNU_REF01 | 参考文献英文半角标点 | Semi | docx-structure | ✓ | ✓ |
| LNU_REF02 | 参考文献编号制表位对齐格式 | Auto | docx-structure | ✓ | ✓ |
| LNU_REF03 | 参考文献字号、行距、两端对齐与禁用断字 | Auto | docx-structure | ✓ | ✓ |
| LNU_REF04 | 参考文献文献类型标识 | Auto | docx-structure | ✓ | ✓ |
| LNU_REF05 | 参考文献序号连续性 | Auto | docx-structure | ✓ | ✓ |
| LNU_REF06 | 参考文献题名大小写与期刊名风格一致性 | Semi | docx-structure | ✗ | ✓ |
| LNU_ABS01 | 中文摘要标题格式 | Auto | docx-structure | ✓ | ✓ |
| LNU_ABS02 | Abstract 标题格式 | Auto | docx-structure | ✓ | ✓ |
| LNU_ABS03 | 英文摘要正文格式 | Auto | docx-structure | ✓ | ✓ |
| LNU_ABS04 | 中文摘要不含英文半角标点 | Semi | docx-structure | ✓ | ✓ |
| LNU_TEXT01 | 摘要混排空格紧凑化 | Auto | docx-structure | ✓ | ✓ |
| LNU_TEXT02 | 目录条目混排空格紧凑化 | Auto | docx-structure | ✓ | ✓ |
| LNU_TEXT03 | 正文混排空格紧凑化 | Auto | docx-structure | ✓ | ✓ |
| LNU_ACK01 | 致谢正文格式 | Auto | docx-structure | ✓ | ✓ |
| LNU_H01 | 标题编号与文字间距 | Auto | docx-structure | ✓ | ✓ |
| LNU_CONC01 | 末章标题含结论 | Manual | docx-structure | ✗ | ✓ |
| LNU_S03 | 参考文献/附录/致谢前分页符 | Auto | docx-structure | ✓ | ✓ |
| LNU_TITLE01 | 摘要/目录/序言/致谢双空格标题 | Auto | docx-structure | ✓ | ✓ |
| LNU_TOC01 | 目录标题与条目样式 | Auto | docx-structure | ✓ | ✓ |
| LNU_TOC02 | 目录条目段后5磅 | Auto | docx-structure | ✓ | ✓ |
| LNU_TOC03 | 目录区段存在并可核对页码 | Auto | docx-structure | ✓ | ✓ |
| LNU_UNIT01 | 数字与单位间空格 | Auto | docx-structure | ✓ | ✓ |
