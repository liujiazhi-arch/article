# GitHub 本地包发布经验 Playbook

这份文档沉淀“把一个本地优先工具发布到 GitHub，让普通用户下载到自己电脑运行”的经验。它适用于当前 Windows zip + bat 本地网页包，也适用于后续 macOS `.app` / `.dmg`、Windows `.exe` / `.msi`、桌面外壳和自动更新方案。

核心原则：

- GitHub 负责托管代码、文档、CI、Release 包和脱敏反馈入口。
- 用户论文、API key、本地日志、运行缓存、修复稿和状态数据库默认只留在用户电脑。
- 第一版优先做到“下载、解压、双击运行”，不要把它误说成完整安装器、代码签名应用或自动更新桌面软件。

## 一句话定位

项目发布目标不是“把用户数据同步到 GitHub”，而是：

> GitHub 托管软件版本；用户下载本地包，在自己的电脑里完成处理。

这种定位适合隐私敏感、文件处理重、云端合规成本高的工具，例如论文、合同、病历、财务表格或含密钥的开发辅助工具。

## GitHub 可以放什么

可以进入仓库或 Release 的内容：

- 源代码、测试、配置模板和文档。
- GitHub Actions workflow。
- 打包脚本、安装脚本和 release smoke 脚本。
- `.env.example` 这类不含真实密钥的示例配置。
- Release 资产，例如 `article-local-windows.zip`、`.sha256`、wheel、源码包。
- 脱敏 issue 模板、反馈说明和兼容性报告模板。

不应进入仓库、CI artifact、Release 或公开 issue 的内容：

- 用户原始文件、修复后文件、截图里的敏感正文。
- API key、`.env`、个人配置。
- 本地 runtime、state、cache、upload、artifact、log、database。
- 未检查的反馈包。
- 含真实路径、真实姓名、论文题目或学校内部信息的证据材料。

## 最小可发布形态

不要一开始就追求安装器、自动更新、跨平台桌面壳。对普通用户来说，第一阶段的有效交付是：

1. 在 GitHub Release 下载 zip。
2. 完整解压。
3. 双击一个入口脚本。
4. 自动启动本地服务。
5. 自动打开浏览器。
6. 完成核心任务。
7. 下载本地结果。
8. 关闭窗口或按说明退出。

当前项目对应为：

- `article-local-windows.zip`
- `启动论文格式检查.bat`
- `导出反馈包.bat`
- `快速开始.txt`
- `article-local serve`
- 上传 `.docx`、audit / plan / apply / download

这已经接近常见 GitHub 工具的“下载即用”体验，但仍不是 `.exe` / `.msi` / `.dmg`。

## 发布资产设计

Release 资产命名要稳定、直观、可脚本检查：

- Windows zip：`<project>-windows.zip`
- Windows checksum：`<project>-windows.zip.sha256`
- macOS app zip：`<project>-macos.zip`
- macOS dmg：`<project>-macos.dmg`
- 安装器：`<project>-setup.exe`、`<project>.msi`

每个正式资产都应有：

- 固定文件名。
- sha256 校验文件。
- 构建脚本。
- 内容扫描脚本。
- smoke 测试脚本。
- Release 文案里的下载说明。

## Windows zip + bat 模式

适用场景：

- Python 项目已有本地 CLI 或本地网页服务。
- 用户群主要是 Windows。
- 目标是先让用户不用安装 Python、不输入命令。

推荐结构：

```text
项目本地版/
  启动工具.bat
  导出反馈包.bat
  快速开始.txt
  app/
    Scripts/
      python.exe
      <cli>.exe
    Lib/
  data/
    state/
    runtime/
```

关键经验：

- bat 里使用随包 Python，不依赖系统 Python。
- 先运行 `doctor`，失败时显示中文原因。
- 再启动本地服务并打开 `http://127.0.0.1:<port>`。
- 默认使用 `127.0.0.1`，不要暴露到公网。
- `data/` 放用户本地状态，但不要把真实 `data/` 打进发布包。
- zip 里可以带空目录占位，但不能带真实用户文件。

## macOS app / DMG 后续模式

macOS 的目标体验是 `.app` 或 `.dmg`，但它比 zip + bat 多出几类工作：

- `.app` bundle 结构。
- 启动本地服务或嵌入 WebView。
- 图标、菜单、退出行为和后台进程管理。
- 代码签名。
- notarization。
- Gatekeeper 提示处理。
- Apple Silicon / Intel 架构选择。
- DMG 背景、拖拽安装说明和挂载验证。

可选路线：

- 继续本地网页：`.app` 负责启动服务和打开浏览器。
- 桌面外壳：Electron / Tauri / PyInstaller + WebView。
- 纯 CLI 包装：适合开发者，不适合普通学生。

不要在未完成签名和 notarization 前承诺“像正式 Mac 软件一样安装”。更准确的说法是“macOS 本地包实验版”。

## 自动更新边界

要把两件事分清：

- 软件版本从 GitHub 更新。
- 用户文件不上传 GitHub。

第一版推荐只做手动版本检查：

1. 用户点击“检查新版本”。
2. 本地网页请求 GitHub Release 元数据。
3. 页面显示当前版本、最新版本、下载地址和更新说明。
4. 用户手动下载新版 zip 或安装包。

不要在第一版做自动替换本地目录，除非已经解决：

- Windows 文件占用。
- 用户数据目录迁移。
- 失败回滚。
- 代理和网络失败。
- 签名校验。
- macOS quarantine 和 Gatekeeper。

## Release 文案写法

Release 不是只给开发者看的 changelog。面对普通用户时，正文顺序应该是：

1. 项目是什么。
2. 适合谁。
3. 下载哪个文件。
4. 如何启动。
5. 本版本包含什么。
6. 隐私边界。
7. Beta 限制和人工复核。
8. 已知边界。
9. 反馈方式。

不要把免责声明放第一句。免责声明要保留，但应放在用户已经理解项目用途之后。

首版 Release 至少要明确：

- 这是 Beta。
- 下载 `Assets` 里的哪个文件。
- zip 需要完整解压。
- 不需要安装 Python。
- 不需要输入命令。
- 用户文件默认只在本机处理。
- 不要把论文、修复稿或 API key 上传到 issue。
- 修复结果必须人工复核。

## 验证证据分层

不要把“CI 绿了”误当成“用户一定能用”。建议分层验证：

1. 单元和集成测试：`python3 -m pytest -q`。
2. 安装 smoke：clean venv 安装 wheel 后跑 CLI 和本地 API。
3. 浏览器 smoke：真实浏览器跑 upload / audit / plan / apply / download。
4. 包内容扫描：确认 zip 不含论文、env、log、state、cache、反馈包。
5. Bundle smoke：解压发布包，用随包 runtime 跑本地网页链路。
6. GitHub Release 状态检查：确认 tag、CI、Release assets 和 sha256。
7. Windows clean machine 实机 smoke：双击启动、浏览器打开、WPS/Word 人工复核。
8. 发布证据门禁：合并 JSON、Markdown 和人工报告，输出是否 ready。

每层验证的边界要写清楚。例如 GitHub CLI 能证明 Release 资产存在，但不能证明用户电脑双击一定成功。

## CI 和 Release 自动化

推荐 GitHub Actions 流程：

1. push / pull_request 跑测试。
2. workflow_dispatch 支持手动预构建。
3. release published 触发正式构建。
4. Windows runner 构建 Windows 本地包。
5. 运行 bundle smoke。
6. 上传 zip 和 sha256 到 Release。
7. 上传 smoke evidence artifact。

关键点：

- Release 资产上传要可重复，支持 `--clobber`。
- CI 里的包不能混入本地开发机数据。
- 构建脚本要用显式输入目录，不要默认扫整个仓库。
- 失败时让日志指向具体步骤：构建、扫描、启动、上传、下载。

## 隐私和反馈包

反馈包的默认策略应是“诊断信息优先，正文内容不进入”：

- 包含版本号、系统信息、任务摘要、doctor 输出、脱敏错误信息。
- 不包含原始文件、修复稿、PDF、截图、API key。
- 脱敏文档文件名和本地路径。
- 导出后提示用户人工检查文件列表。
- 公开 issue 不接受未检查反馈包。

如果后续需要收集真实样本，应单独设计脱敏样本提交流程，不要和普通 bug 反馈混在一起。

## 多智能体分工

后续做类似项目时，可以把任务拆成几个稳定角色：

- 发布工程：GitHub Actions、打包脚本、Release assets、sha256、版本号。
- 隐私安全：`.gitignore`、secret scanning、反馈包脱敏、包内容扫描。
- Windows 体验：bat 启动、端口占用、中文错误提示、clean machine smoke。
- macOS 体验：`.app` / `.dmg`、签名、notarization、Gatekeeper 文案。
- 学生文档：README、快速开始、Release 文案、issue 模板。
- 质量验证：pytest、browser smoke、bundle smoke、WPS/Word 人工复核清单。

这些角色可以并行审查不同文件，但最终提交前必须合并成一个清晰的发布证据链。

## 可迁移到 GitHub/Codex 插件的提示词

后续如果要把这份经验做成可复用插件或技能，可以使用下面的任务说明：

```text
你是本地包发布工程助手。目标是把一个本地优先工具发布到 GitHub，让普通用户可以从 GitHub Release 下载到自己的电脑运行，同时确保用户文件、API key、本地日志和运行缓存不进入 GitHub。

优先路线：
1. 明确产品形态：Windows zip + bat、macOS app/dmg、安装器或源码安装。
2. 定义 GitHub 可上传内容和本地隐私边界。
3. 补齐 .gitignore、.env.example、隐私文档、Release 文案模板和 issue 模板。
4. 编写或检查打包脚本，确保发布包只包含运行所需文件。
5. 编写包内容扫描和 smoke 测试。
6. 配置 GitHub Actions 构建、测试、上传 Release assets。
7. 发布后用 GitHub CLI/API 验证 Release 资产、CI 状态和文案。
8. 明确哪些验证不能被 CI 替代，例如 Windows clean machine、WPS/Word 或 macOS Gatekeeper 实机检查。

输出要求：
- 先给最小可发布路径，不要一开始设计完整自动更新系统。
- Release 文案先介绍项目和下载方式，再说明 Beta 和隐私边界。
- 不要上传或建议上传用户原始文件、API key、日志、缓存、state 或未检查反馈包。
- 每次声称完成前都运行验证命令，并报告真实结果。
```

## 完成定义

只有同时满足下面条件，才算完成一次 GitHub 本地包发布：

- 仓库里有清晰 README、用户指南、隐私说明、免责声明和 Release 模板。
- Release 页面有项目介绍、下载说明、隐私边界、Beta 限制和反馈方式。
- Release assets 包含主下载包和 sha256。
- CI 或本地脚本验证包内容不含隐私数据。
- 本地 smoke 跑通核心链路。
- 至少一次目标系统实机 smoke 通过。
- 公开 issue 模板提醒不要上传用户文件和密钥。
- 提交历史不包含本地隐私文件。

如果只完成了代码上传和 CI，不要说已经完成“普通用户可用发布”；应该说“GitHub 构建链路已准备好，还需要目标系统实机 smoke”。
