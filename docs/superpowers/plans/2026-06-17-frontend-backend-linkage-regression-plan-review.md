# 前后端联动回归计划 · 审查报告

> 审查对象：`docs/superpowers/plans/2026-06-17-frontend-backend-linkage-regression-plan.md`
> 审查日期：2026-06-17
> 审查范围：只读评审 + 代码事实核对，未改动任何源码。

---

## 一、我对这份计划要解决的问题的理解

迁移后的前端（`scripts/article_api/static/`）改用了 `data-action` / `data-*` 钩子，
但配套的浏览器冒烟脚本 `scripts/local_browser_smoke.py` 还在点旧选择器，导致 E2E 链路断了。

计划要做的事可归为三层：

1. **修复冒烟选择器漂移**（Task 2 / 6）——把 `label[for='paper-file']`、`#run-all-button`、
   `#report-action-button`、`#report-output` 换成迁移后的 `data-action` / `data-download-role`。
2. **冻结前端契约**（Task 1 / 4 / 5）——加测试锁死 HTML 钩子、JS 渲染函数、render-review 任务装配。
3. **把"格式雷达"接上真实状态**（Task 3）——当前 `.radar` 是纯装饰空 div，要变成数据驱动。

目标本身（恢复真实联动 + 回归保护）方向正确。

---

## 二、我的独立解决思路（先不看计划怎么写）

如果让我从零解决"冒烟断链 + 联动回归"，我会按真实运行时的状态机来设计，而不是按文本匹配：

1. **先按真实屏幕状态机走查**。前端是单页多屏，非活动屏 `display:none`
   （`layout.css:680`）。任何点击/快照断言都必须先保证目标屏 `.active`。
2. **冒烟流程 = 真实用户路径**：进首页 → 进工作台 → 选论文（隐藏 input 由按钮触发）→
   上传后自动出方案 → 生成结果 → 跳结果屏 → 下载。
3. **断言要挑"只有联动成功才会出现"的动态信号**，而不是 HTML 里本来就在的静态文案。
   真正的联动证据是：`setStatus` 写入的动态文本、指标从占位变成数字、下载按钮从 `disabled` 变可用、
   热力图被 JS 重绘。
4. **测试最小化、不重复**。仓库已有 `test_frontend_backend_contract.py` 覆盖了大量源码级断言，
   新增只补真正缺的那一条（雷达）。
5. **雷达诚实接线**：标签用真实计数（`planSummary` 已算好 `manualConfirmation`/`failedCount`），
   仪表盘角度可以是示意性的，但要在文档里说清"标签真实、盘面示意"，不假装精确分数。

---

## 三、思路差异对照（逐条）

| 维度 | 原计划做法 | 我的做法 | 谁更好 |
|------|-----------|---------|--------|
| 冒烟点击前的屏幕导航 | Task 2 直接点 `[data-action='choose-docx']`，**没有先进工作台** | 先点 `[data-action='enter-workbench']` 再点 `choose-docx` | **我的**（见 §四 阻断缺陷 1） |
| 等待文本的选取 | 等 `修复方案已生成` / `修复结果已生成` / 静态文案 `可修复范围`/`规则色谱` | 动态信号优先，并改用真实存在的文本 | **我的**（见 §四 阻断缺陷 2） |
| 联动"证据"的强度 | 多数断言等"静态 HTML 文案出现"——只证明屏切过去了 | 断言指标从 `等待` 变数字、下载键从 `disabled` 变可用 | **我的** |
| render-review 单测 | Task 5 新增 `build_render_review_job_kwargs` 单测 | 同意保留（补了纯函数层覆盖） | **持平**，但与现有 HTTP 测试部分重叠 |
| 联动回归测试文件 | Task 4 新建 `test_frontend_backend_linkage.py` | 扩展已存在的 `test_frontend_backend_contract.py` | **我的**（避免近重复文件） |
| 雷达接线 | Task 3 数据驱动 + 仪表角度启发式 | 同方向，但文档标注"标签真实、盘面示意" | **持平**，方案基本一致 |
| 钩子冻结测试 | Task 1 新增 negative 断言（旧 ID 不存在） | 保留，确有回归价值 | **持平** |

---

## 四、原计划的两个阻断级缺陷（必须修，否则 Task 2 直接超时）

### 缺陷 1（CRITICAL）：点击 `choose-docx` 前没有进入工作台

事实依据：

- `index.html:11` 首屏是 `data-screen="cover"`（`class="screen active"`）。
- `choose-docx` 按钮在 `data-screen="workbench"` 屏内（`index.html:128`）。
- 非活动屏 `display:none`（`layout.css:680`）。

后果：Playwright 的可见性检查会让点击隐藏元素**超时失败**。原计划 Task 2 Step 3
的替换片段从 `label[for='paper-file']` 直接换成 `[data-action='choose-docx']`，
但旧脚本当年能跑，是因为旧前端首屏就有上传控件；迁移后必须**先导航**。

修复：在 upload 前插入

```python
_run_playwright(pwcli_path, "click", "[data-action='enter-workbench']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "上传论文开始修正", cwd=smoke_dir, timeout=timeout)
```

### 缺陷 2（HIGH）：等待文本与代码不一致 + 误用静态文案

事实依据（`app.js`）：

- 生成结果成功后真实写入的是 **`修正结果已生成`**（`app.js:388`），
  原计划 Task 2 Step 3 等的是 **`修复结果已生成`**（"复"≠"正"），**永远等不到**。
- `修复方案已生成` 是真实动态信号（`app.js:140`）✅ 可用。
- `可修复范围`（`index.html:136`）、`规则色谱`（`index.html:292`）、`修复包已生成`
  （`index.html:274`）都是**结果/工作台屏的静态文案**——只要那屏 `.active` 就一定出现，
  **不能证明后端数据真的回填了**。

修复：动态信号用 `修正结果已生成`；要验真实联动则断言指标变化（见 §五 Task 6）。

---

## 五、我的修订版执行计划（在原骨架上做手术式修正）

保留原计划 8 个 Task 的结构与 TDD 纪律，只改错误项、去重复项、强化"真实联动"断言。

### Task 1 · 冻结迁移后钩子契约（保留，微调）

照原计划加 `test_static_frontend_uses_migrated_action_hooks_not_legacy_console_ids`。
事实核对：所有正向钩子（`choose-docx`/`create-plan`/`create-apply-job`/`download-role=output`/
`data-history-list`/`data-result-heatmap`）当前 HTML **已存在**，旧 ID 已不存在 → 该测试现在就会 PASS，
作为回归护栏成立。

### Task 2 · 修复冒烟选择器（**改对导航与文本**）

替换 `local_browser_smoke.py:173-189`，关键修正三处：

```python
# 1) 先进工作台（缺陷 1 修复）
_run_playwright(pwcli_path, "click", "[data-action='enter-workbench']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "上传论文开始修正", cwd=smoke_dir, timeout=timeout)
# 2) 选论文（上传后前端会自动生成方案，create-plan 按钮无需单独点 —— 这点原计划判断正确）
_run_playwright(pwcli_path, "click", "[data-action='choose-docx']", cwd=smoke_dir, timeout=timeout)
_run_playwright(pwcli_path, "upload", docx_path, cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修复方案已生成", cwd=smoke_dir, timeout=timeout)  # 动态信号 ✅
# 3) 生成结果，等真实文本（缺陷 2 修复："修正"不是"修复"）
_run_playwright(pwcli_path, "click", "[data-action='create-apply-job']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修正结果已生成", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "修复包已生成", cwd=smoke_dir, timeout=timeout)  # 已跳到 result 屏
download_result = _run_playwright(pwcli_path, "click", "[data-download-role='output']", cwd=smoke_dir, timeout=timeout)
```

源码级护栏测试（原计划 `test_local_browser_smoke_does_not_reference_removed_frontend_selectors`）保留，
**并加一条**：`assert "[data-action='enter-workbench']" in smoke`，锁死导航步骤不被回退删掉。

### Task 3 · 雷达数据驱动（保留，方案基本采纳）

事实核对：`.radar` 当前是空 div（`index.html:151`）+ `::after { content:"格式雷达" }`
（`layout.css:1476`）。原计划替换为 `data-format-radar` + span + `--radar-progress` 合理。
`renderFormatRadar` 消费的 `summary.failedCount/manualConfirmation` 在 `planSummary` 里已算好
（`app.js:71-80`），接线成立。

**唯一补充**：CSS 替换要同时删掉旧的 `content: "格式雷达"` 规则（`layout.css:1477`），
否则伪元素文字会盖住新 span。文档需注明"标签文字真实、盘面角度为示意"，不假装精确分数。

### Task 4 · 联动回归测试（**改为扩展现有文件，不新建**）

事实核对：`test_frontend_backend_contract.py` 已断言 `renderWorkbenchPlan`、`data-workbench-metric`、
`data-workbench-ledger`、`renderHistory`、`renderResultPanel`、`data-download-role`、pdfReview 链路。
原计划 Task 4 新建文件里 80% 断言是重复的（违反"一次使用不抽象/不重复"原则）。

修订：**只把雷达那一条**加进现有 `test_frontend_backend_contract.py`：

```python
def test_frontend_js_wires_format_radar_from_plan_summary():
    app_js = (ROOT / "scripts/article_api/static/js/app.js").read_text(encoding="utf-8")
    html = (ROOT / "scripts/article_api/static/index.html").read_text(encoding="utf-8")
    assert "function renderFormatRadar(summary)" in app_js
    assert "renderFormatRadar(summary)" in app_js
    assert "data-format-radar" in html
```

### Task 5 · render-review 装配单测（保留，承认轻度重叠）

事实核对：`build_render_review_job_kwargs` 返回键与原计划断言一致（`file_path`/`rendered_pdf`/
`workflow_mode="default_user"`/`source_display_name`/`pdf_display_name`/`runtime_root`/`_public_request`，
见 `render_review_jobs.py:23-41`）。非 PDF 拒绝走 `ValueError("请选择...PDF...")`，
`pytest.raises(match="PDF")` 能命中。

注意：现有 `test_render_review_jobs.py` 已在 **HTTP 层**覆盖了同一逻辑（404 + 201 两条）。
新增纯函数单测有价值（更快、更精准定位），**追加而非替换**，原计划这点表述正确。
仅修正：原计划示例对 missing-pdf 用 `LookupError`，而真实代码对 `pdf_upload_id` 解析失败抛的也是
`LookupError`（`render_review_jobs.py:15`）——保持一致即可。

### Task 6 · 冒烟断言"真实联动"而非静态文案（**强化**）

这是与原计划分歧最大处。原计划等 `规则色谱`/`下载 修复副本`/`审查报告` 都是 result 屏静态文案，
切过去就有，**证明不了数据回填**。改为断言"只有联动成功才会变"的状态：

```python
# 结果屏已激活后，验证真实回填：文件名不再是占位、下载键可用
snapshot = _wait_for_snapshot_text(pwcli_path, "browser_smoke", cwd=smoke_dir, timeout=timeout)
assert "等待修复结果" not in snapshot  # data-result-file-name 已被 renderResultPanel 覆盖
# 历史屏：进入触发 refreshHistory()，真实任务出现
_run_playwright(pwcli_path, "click", "[data-screen-target='history']", cwd=smoke_dir, timeout=timeout)
_wait_for_snapshot_text(pwcli_path, "browser_smoke", cwd=smoke_dir, timeout=timeout)
# 回结果屏再下载
_run_playwright(pwcli_path, "click", "[data-screen-target='result']", cwd=smoke_dir, timeout=timeout)
```

`download_bytes` 必须 > 0 且为合法 docx（原计划这点正确，沿用）。

### Task 7 · PDF 复核冒烟（保留为可选/降级）

原计划"环境不支持渲染就降级为 API 测试、不伪造成功"的处置正确，照搬。

### Task 8 · 全量验证（保留）

```bash
python3 -m pytest tests/test_article_static_frontend.py tests/test_frontend_backend_contract.py tests/test_render_review_jobs.py -q
python3 -m pytest tests/test_article_api.py tests/test_article_jobs.py -q
python3 scripts/local_browser_smoke.py --work-dir /tmp/article-smoke-final \
  --json-output /tmp/article-smoke-final.json --command-timeout-seconds 180
```

声称完成前必须贴出上述命令的真实输出（证据优先）。

---

## 六、总评

原计划根因诊断准确（选择器漂移），TDD 纪律到位，雷达接线方向正确，
对"上传后自动出方案，无需单独点 create-plan"判断也对——**骨架约 80% 可用**。

但有两个会让 Task 2 直接超时失败的阻断缺陷：**点击前未进工作台**、**等待文本写错字（修复≠修正）**；
以及"用静态文案冒充联动证据"的方法论问题，和 Task 4/5 与现有测试的重复。

结论：**不推翻重写，按本报告 §四/§五 做手术式修正**即可。修正后才满足原计划自己定的完成标准里
"Browser smoke passes on the migrated frontend"与"renders from real apply job payload"两条。


