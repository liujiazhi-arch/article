# frontend-backend-linkage · 双模型方案 synthesis 账本

> 日期：2026-06-17
> 对应 Codex 计划：`docs/superpowers/plans/2026-06-17-frontend-backend-linkage-regression-plan.md`
> 详细代码级评审附录：`docs/superpowers/plans/2026-06-17-frontend-backend-linkage-regression-plan-review.md`
> 本轮：第 1 轮（Claude 独立 diff 完成，待 Codex 代码复核 §3）

---

## 0. 路由说明（按能力分工）

- **intent 差异**（产品/范围/优先级，非程序员可判）→ 用户。本案 **0 条**（见 §2）。
- **technical 差异**（测试结构、断言方法、代码落点）→ Claude 推荐，Codex 用 file:line 验证。
- **factual 争议**（某事实是否成立）→ Codex + 代码定。用户不看 §3。

---

## 1. 已锁定共识（两模型独立同意，不再讨论）

- **根因 = 选择器漂移**：smoke 仍点 `label[for='paper-file']`/`#run-all-button`/`#report-action-button`/`#report-output`，前端已迁移到 `data-action`/`data-download-role`。
- **Task 1 冻结迁移钩子**：HTML 中正向钩子（`choose-docx`/`create-plan`/`create-apply-job`/`download-role=output`/`data-history-list`/`data-result-heatmap`）**当前已全部存在**，旧 ID 已不存在 → 该护栏测试现在即 PASS。
- **上传即自动出方案**：`app.js:409` 上传回调内直接 `createWorkbenchPlanFromUpload`，冒烟**无需单独点 `create-plan`**——两模型一致。
- **格式雷达 → 数据驱动**（方向共识）：`.radar` 当前是空 div（`index.html:151`），应接 `planSummary` 的真实计数。
- **Task 7 PDF 冒烟可降级**：环境无渲染依赖时降为 API 测试，**不伪造成功**。
- **纪律**：TDD（RED→GREEN）、收尾贴真实命令输出（证据优先）。

---

## 2. 用户已决策的 intent 差异

**无。** 两份计划在「做什么 / 学生看到什么 / 取舍」上完全一致，分歧只在「怎么实现与怎么验证」（technical/factual）。
按 skill「不为凑流程制造 intent 问题」原则，这一格留空，不向产品负责人发问。

## 3. 技术/事实分歧（全部已由 Codex 代码裁定，§3 已清空）

**第 1 轮 D1-D6：✅ Codex 用 file:line 裁定并写入 plan.md `## Codex Arbitration`（43-48 行）。**
**第 2 轮 D7-D8：✅ Codex 采纳并写入 plan.md（49-50 行）+ Task6 Step2 改写（plan.md 549-552）。**

| # | 裁定 | 落地位置（Claude 已核对实际文件，非仅信回账） |
|---|------|-----------------------------------------------|
| D1 | accepted | plan.md:43 + Task2 导航步 183-184 |
| D2 | accepted | plan.md:44 + Task2 文本 189（`修正结果已生成`） |
| D3 | accepted | plan.md:45 + Task6 Step1 result 屏动态断言 |
| D4 | accepted | plan.md:46 + Task4 扩展现有测试，未新建文件 |
| D5 | confirmed | plan.md:47，异常类型对齐 |
| D6 | accepted | plan.md:48 + Task3 Step4 删旧 `::after content`（323） |
| D7 | accepted | plan.md:49 + Task6 Step2 主断言改 `browser_smoke`，静态文案降兜底（549-552） |
| D8 | accepted | plan.md:50 + `## Linked Code Maintenance` 第 3 条 cache-bust 联动（97） |

**§3 待处理项：空。**

---

## 4. 顶部边界段落落地核对（Claude 已读实际 plan.md）

Codex 按 §4【B】在 `## Files` 后、`## Task 1` 前新增两段，内容逐字对应本账本 §5：

- `## Execution Boundary`（plan.md:79-89）：前端只手术不重写、不碰被测试锁定的 `pdfReview.js`/`api.js`/`state.js`/`copy.js`；后端不改 payload 形状/引擎；**明确雷达纯前端展示故不维护 `capability_matrix.md`**（85 行，防误维护）；测试不扩面；雷达防过度工程。
- `## Linked Code Maintenance`（plan.md:91-99）：HTML 钩子↔JS↔测试↔冒烟 四点联动；状态文案↔冒烟文本（D2 实例）；`.radar`↔cache-bust↔锁串测试（D8）；禁词检查；**Task2/Task6 合并为单一冒烟顺序**（99 行）。

全部为实测确认，回账无虚报。

---

## 5. 强壮性 / 执行边界 / 相关代码维护（结合本项目栈深度分析）

> 本项目栈：前端 = vanilla HTML/CSS/JS 模块（无框架无构建）；后端 = FastAPI + 本地任务；
> 测试 = pytest + FastAPI TestClient + Playwright CLI 冒烟。**无数据库**。
> 故"执行边界"聚焦前端不重写 + 后端不改形状 + 测试不新建；"相关代码维护"聚焦
> HTML 钩子↔JS 选择器↔测试↔冒烟 的四点联动。
> 本节为账本权威记录；plan.md 的 `## Execution Boundary` / `## Linked Code Maintenance` 即由此落成。

### 5.1 失败路径 / 降级（不可遗忘）

- **冒烟工具缺失**：Playwright CLI 不存在 → `_format_error` 已降级为结构化 JSON（`local_browser_smoke.py:243`），保留，不得抛裸异常。
- **方案生成失败**：`createWorkbenchPlanFromUpload` catch 走 `renderWorkbenchPlanUnavailable`（`app.js:119`）。冒烟必须区分 `修复方案已生成`（成功）与 `修复方案暂时不可用`（降级），不得把降级误判为成功。
- **下载键不可用**：artifact 不可用时 `setDownloadButton` 保持 `disabled`（`app.js:179`）。冒烟须断言"可用 + 下回真实 docx"，而非仅"按钮存在"。
- **PDF 渲染缺依赖**：降级为 API 层测试并在 payload 标注 skip，**不伪造 `status: ok`**（Task7）。

### 5.2 执行边界（Execution Boundary —— 建议升格为 plan.md 顶部段）

**前端（只手术，不重写）**
- 只改 `index.html` / `app.js` / `layout.css` 三个产物文件。
- **不改** `pdfReview.js` / `api.js` / `state.js` / `copy.js` 的既有契约——它们被 `test_frontend_backend_contract.py` 锁定，改动会连锁破测。
- 不引入任何框架 / 打包器 / npm 依赖（项目刻意为 vanilla）。

**后端（只加测试，不改形状）**
- **不改** API payload 形状、`render_review_jobs.py` 逻辑（只追加单测）。
- **不动** 论文格式引擎（`audit_thesis.py` / `fix_thesis.py` / `_thesis_utils.py`）——除非某 API 测试证明 payload 形状确实错（Files 段已声明）。
- 不触发 `config/capability_matrix.md` 维护：本轮雷达是**纯前端展示**，未新增 runtime 规则，故 CLAUDE.md「新增 runtime 规则须同步 capability_matrix」约束**不适用**——明确写出以防误维护。

**测试（不扩面）**
- **不新建** `test_frontend_backend_linkage.py`（D4）；雷达断言并入 `test_frontend_backend_contract.py`。
- 不碰 `.tmp/frontend-preview/`、主题资产、`config/`。

**防过度工程**
- 雷达盘面角度仅为示意启发式，**标签文字用真实 `planSummary` 计数**；不引入"假精确分数"、不加后端字段、不加配置项（与既有 `test_..._without_fake_counts` 立场一致）。

### 5.3 相关代码维护（Linked Code Maintenance —— 建议升格为 plan.md 顶部段）

本项目"改一处必须同步多处"的联动点（前端无类型系统，漂移只能靠测试+冒烟兜，故必须显式列出）：

1. **改 `index.html` 的 `data-*` 钩子** → 同步：`app.js` 对应 `querySelector` + `test_article_static_frontend.py` 钩子断言 + `local_browser_smoke.py` 选择器。
2. **改 `app.js` 状态文案**（如 `修正结果已生成`）→ 同步：`local_browser_smoke.py` 的 `_wait_for_snapshot_text` 文本 + 任何断言该串的测试。**D2 错字就是此联动断裂的实例。**
3. **改 `layout.css` 的 `.radar`** → 同步：`index.html` radar 标签结构 + 删除旧 `::after { content:"格式雷达" }` + 评估是否 bump `?v=20260617-upload-circle`（`index.html:9,313`）及 `test_article_static_frontend.py:136` 锁串断言（D8）。
4. **新增任何学生可见文案** → 必过 `test_frontend_backend_contract.py` 的禁词测试（`test_..._forbidden_student_terms` / `..._out_of_backend_field_names`）：不得出现 `bbox`/`rule_id`/`queued`/`running`/`failed`/`profile` 等后端术语。
5. **冒烟流程跨 Task 叠加**：Task2 与 Task6 编辑 `local_browser_smoke.py` 同一段，须按"导航→上传→方案→生成→result 动态断言→history 真实记录→回 result→下载"单一顺序合并，不得各自插入造成步骤错位。

---

## 6. 状态：计划已锻成（FORGED）

dual-model-planning 收尾校验（verification-before-completion）：

- **§3 待处理项 = 空** ✅（D1-D8 全部 Codex 代码裁定并实测落地）
- **§5 强壮性/边界/维护清单存在** ✅
- **共识已锁**（§1）✅ ｜ **用户 intent 差异 = 空**（§2，无需产品裁决）✅
- **顶部边界两段已写入 plan.md 并经 Claude 实读核对**（§4）✅

计划三要素齐备：**独立共识 + 用户 intent（本案空）+ 代码验证技术项**，外加显式执行边界与联动维护规则。
**文档阶段定稿。** 下一步进入实现阶段，按 plan.md Task 1→8 执行，收尾必须贴出 pytest 三组 + 冒烟的真实命令输出（证据优先，回账 §5 已列命令）。

分工归位：Codex 持有并更新 plan.md，Claude 仅维护本账本，二者零重叠。



