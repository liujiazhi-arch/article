# Frontend Workbench And PDF Review Plan — 实操评估

Date: 2026-06-16

评估对象:`docs/superpowers/plans/2026-06-16-frontend-workbench-and-pdf-review-plan.md`

## 结论

这份计划在**视觉 / 文案 / 排版层面**写得很细,但它默认了一个不成立的前提——“前端是个需要升级的工作台”。

实际上当前前端不是“原型待升级”,而是**两套前端的分叉**,而计划完全没提这件事。这正是“未来还要反复校准前后端差异”的根源。

下面按严重程度排序,每条都附了代码证据。

## 证据基线(交叉核对结果)

- 漂亮但是死的:`.tmp/frontend-preview/system.html`(96KB)。四主题、资产齐全,但整个 `<script>` 只有 40 行,只做 show/hide 切屏。无 fetch、无文件上传 input、无轮询、无数据渲染。PDF 的 bbox 框是写死的 CSS 矩形,字段全是“待返回”占位。
- 能跑但是旧皮肤:已删除的 `scripts/article_api/local_console.html`(`git show HEAD:scripts/article_api/local_console.html`,4235 行)。真上传 docx/pdf、真 fetch `/jobs/apply`、`/uploads/pdf`、`/render-verify`、真轮询、真把 `rule_id/severity/page/message` 映射成中文标签。但只有 light/dark 两个主题。
- 后端 evidence_item 真实字段(`scripts/thesis_tool/render_verify.py:586`):`page / screenshot_path / rule_id / bbox / message / severity / next_action`,API 层再加 `screenshot_url`。没有 `student_title` / `student_message`。
- bbox 为归一化 0-1 `{x,y,w,h}`,但多数是粗框(整页或写死横条),只有一个 finding 用真实像素 ink bbox,所有 TOC 问题 bbox 为 null(`render_analyzer.py:361`)。
- 无任何 text-span / 字符级坐标能力。计划建议的 pdfplumber/PyMuPDF/`pdftotext -bbox-layout` 一个都没接;现用 poppler 的 `pdftoppm` + `pdftotext -layout`。
- PDF 上传端点 `/uploads/pdf` 存在(`routes_uploads.py:58`),但没有任何 job 把它接到 render-verify。
- render-verify 是同步 `POST /render-verify`(`routes_sync.py:66`),而 verify/normalize/apply 全是异步带轮询。
- `default_user` 模式强制要求传 `rendered_pdf` 或 `page_images_dir`(`response_payloads.py:258`)。
- screenshot token 存在内存字典(`render_evidence.py:10`),无持久化、无过期,服务器重启后历史截图链接全 404。
- 自渲染 docx→PDF 仅 macOS + Microsoft Word 的 AppleScript 自动化(`render_verify.py:98`,代码自标 fragile),否则需学生自带 PDF;还依赖系统装了 poppler。
- 主题 board 覆盖:rain(雨后)四块 board 全定义了;真正 fallback 到 ginkgo 默认的是 morning(清晨)。
- 前端文件与主题图都在 `.tmp/frontend-preview/`(scratch 目录),未进 git、无稳定服务路由。

## 阻断级:不先定就会无限校准

### 1. 前端有两套,计划没选基线

漂亮的那套(system.html)是死的,能用的那套(local_console.html)是旧皮肤。

计划 Step 2-5(文案、排版、PDF viewer、主题)全在 system.html 这具空壳上做表面功,做完仍不能用。

必须先拍板:**是把 system.html 的四主题 token 移植到 local_console.html 的功能骨架上,还是把功能逻辑灌进 system.html?**

倾向前者:功能骨架是真资产,主题是 CSS,移植 CSS 比重写整套前后端交互便宜得多。

这一条不定,后面每一步都会返工。

### 2. 前后端数据契约是“编”出来的,和后端对不上

计划 PDF 字段示例用了 `student_title` / `student_message` / `next_action` / `screenshot_url`。

后端实际只有 7 字段(见证据基线),根本没有 `student_title` / `student_message`。

把 `rule_id` 翻译成学生看得懂的标题这层映射必须有人做(旧 local_console 里是前端 `renderFindingName` 做的)。计划既没说后端加学生文案,也没说前端做映射,直接假设契约存在。

这正是反复校准的高发区。

建议:Step 1 产物里加一份 `docs/FRONTEND_BACKEND_CONTRACT.md`,把每个端点、每个字段、coordinate 系统、每个状态冻结下来,后续所有步骤引用它。这份契约文档才是“一次性确定”的真正抓手。

### 3. “上传 PDF -> 看预览”主流程在后端没接通

- `/uploads/pdf` 能存 PDF,但没有 job 把它接到 render-verify。
- render-verify 收文件系统路径 `rendered_pdf`,不是 `upload_id`。
- render-verify 同步,verify/normalize/apply 异步带轮询,两套范式并存,前端要统一。
- `default_user` 模式强制要求 `rendered_pdf` 或 `page_images_dir`。
- screenshot token 在内存,无持久化无过期,重启后历史截图全 404。

计划的 History / Result / PDF 复核都假设证据持久可回看,这一条不解决,学生重启一次就崩。

需要拍板:**上传的 PDF 怎么触发 render-verify(新端点?)、同步还是异步、screenshot 落到 job artifact 还是持久化 token。**

## 高优先级

### 4. PDF 精度被高估,第二阶段是“新造能力”不是“加个字段”

后端 bbox 归一化 0-1(与计划一致,好),但多数是粗框,所有 TOC 问题 bbox 为 null。

计划说“第二阶段增加 text_spans / 字符级高亮”,但后端完全没有 text-span 能力,建议的工具一个都没接。

“第二阶段”是一块独立后端工程,不是前端微调。计划应如实标注工作量,第一版明确:有框画框,无框退化整页提示(计划已写,对的),TOC 类问题默认走整页提示。

### 5. docx->PDF 渲染依赖没写清楚,平台约束被藏了

工具自渲染 PDF 只有一条路:macOS + Microsoft Word 的 AppleScript(代码自标 fragile);否则学生自带 PDF。还依赖系统装了 poppler。

计划写“上传或导入 PDF”隐含接受学生自带 PDF(对),但没声明依赖和平台限制。

要定:**PDF 复核以“学生自己导 PDF”为主线还是“工具帮你渲染”;poppler 依赖写进文档/doctor 检查。**

### 6. 前端和资产都住在 `.tmp/`,不是可交付路径

能跑的前端文件在 `.tmp/frontend-preview/`(scratch),主题图在 `.tmp/frontend-preview/generated-ui-assets/`,都没进 git、无稳定服务路由。删掉的那套是 git-tracked 由 app 提供服务。

计划必须定:**生产前端落在哪、谁来 serve、资产怎么 commit/serve。** 否则主题做得再好,发布出去就是空的。

### 7. 失败 / 空 / 加载态在设计里缺席

计划全是 happy path。真实需要:上传失败、render-verify 失败(Word 没装 / poppler 缺失 / PDF 损坏)、零问题、截图丢失、任务超时、网络错误。

CLAUDE.md 明确要求每层显式处理错误且给用户友好信息。这块不在第一版设计里,必然回炉。

## 中优先级(小,但正是“反复校准”的来源)

### 8. 主题资产目标搞错了

计划反复说“雨后主题补齐 workflow/pdf/result board”,但 rain(雨后)四块 board 全都定义了;真正 fallback 到 ginkgo 默认的是 morning(清晨)。

验收清单里“雨后不继承错误暖色资产”在追一个不存在的问题,而 morning 的真缺口没列。改对目标。

### 9. 避免词清单不全

system.html 里真正泄露给学生的渲染文本:`rule_id`、`bbox`、`page_image`、`data contract`、`profile lnu`、`mode local`、`preflight/plan/apply job`、`异步任务`。

计划的 avoid-list 漏了 profile/mode/preflight/plan/apply/data contract。

建议:**从文件实际字符串里 grep 出清单,别用通用列表。**

### 10. 4 栏 PDF viewer 没定义窄屏怎么塌

Step 6 才检查窄屏,但“左列表 / 中截图 / 右说明 / 底工具条”是纯桌面布局,窄屏必崩。移动端 reflow 应在设计阶段就定。

## 建议:怎么改这份计划才能“一次定死”

把当前 Step 1(Inventory)升级为**决策关口**,先产出并冻结这三样,再动任何像素:

1. **基线决策**:功能骨架(local_console)+ 主题移植,还是空壳(system.html)+ 灌功能。(建议前者)
2. **`docs/FRONTEND_BACKEND_CONTRACT.md`**:端点清单(含 PDF 上传如何触发 render-verify、同步/异步)、evidence_item 真实字段、rule_id->学生文案映射归属、bbox 坐标系与 null 退化规则、screenshot_url 生命周期 / 持久化。
3. **PDF 复核能力边界声明**:第一版 = 学生自带 / 工具渲染哪个为主线 + poppler 依赖 + 粗框 / 整页退化;text_spans 明确标为“第二阶段独立后端工程”。

把这三个决策落地后,现有 Step 2-6 才有稳定地基,不会做一版返一版。

## 严重级别汇总

| 级别 | 条目 |
|------|------|
| 阻断(blocker) | 1 前端基线未选 / 2 数据契约凭空假设 / 3 PDF 主流程后端未接通 |
| 高(high) | 4 PDF 精度高估 / 5 渲染依赖与平台约束未声明 / 6 前端与资产无可交付路径 / 7 失败空加载态缺席 |
| 中(medium) | 8 主题 board 目标搞错 / 9 避免词清单不全 / 10 PDF viewer 窄屏未定义 |
