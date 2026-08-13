# 华为风格文档生成工具链

本仓库实现确定性的离线文档流水线:

```text
md/docx/xlsx/pptx -> DocumentIR -> Prompt/generator -> WordIR/DeckIR -> DOCX/PPTX -> 合规报告
```

IR 是唯一契约。模型文本必须先剥壳和校验,非法 IR 不进入 renderer。

## 唯一正式版本与入口

- 产品版本唯一来源：根目录 `VERSION`。Python API、WPF Assembly、界面版本、User-Agent
  和便携包名称都从该文件派生，不在各模块单独维护版本号。
- 主用户入口：发布包中的 `DocumentWorkbench.exe`；源码项目为
  `desktop/DocumentWorkbench/DocumentWorkbench.csproj`。
- 浏览器/API 模块入口：`python -m app.web_api`；Windows 固定使用
  `.\.venv\Scripts\python.exe -m app.web_api`。它是 WPF 和浏览器兼容客户端共享的唯一
  HTTP 后端，不存在第二套同步 Web 服务。
- CLI 入口：`python -m app.cli.parse`、`python -m app.cli.prompt`、
  `python -m app.cli.render` 和 `python -m app.cli.check`，分别承担一个流水线阶段。
- 安装命令：`.\bootstrap_windows.ps1`。
- 浏览器兼容入口启动命令：`.\start_workbench.ps1`。
- 测试与发布门禁：`.\verify.ps1`。
- **一键脚本入口（推荐）**：`scripts/win/README.md`（verify_all / build_all /
  package_setup / start_workbench_ui，覆盖验证、打包、安装程序、启动工作台）。
- WPF 构建入口：`scripts/package_document_workbench.py`（便携 ZIP）；
  `scripts/package_installer.py`（Inno Setup 安装程序，需先装 Inno Setup 6，
  设计见 `docs/design/INSTALLER_DESIGN.md`）。
- 生产 PPT 引擎：DeckIR 2.2 到 `python-pptx`；`experiments/html2pptx/` 仅为隔离对照实验。
- 本仓库不包含训练或推理入口；NGA 是受约束的 IR generator adapter，不是模型训练代码。

## 环境

- Python 3.12
- 依赖见 `requirements.txt`
- 目标环境为内网 Windows 离线运行;开发与验收固定使用仓库 `.venv` 中的 Python 3.12

Windows 首次配置与验收:

```powershell
.\bootstrap_windows.ps1
.\verify.ps1
```

两条脚本都会固定 UTF-8、`PYTHONPATH=backend`,并生成
`output/environment_report.json`。Graphviz 按 `tools\graphviz\bin\dot.exe`、系统
`dot.exe` 的顺序选择;不可用时报告会明确标记 deterministic fallback。

```bash
python -m pip install -r requirements.txt
brew install graphviz
dot -V
```

`graphviz` Python 包只负责调用布局引擎,不包含 `dot` 二进制。Mac 开发机需安装
Graphviz;目标 Windows 内网机需将离线 Graphviz 运行时随项目部署并把其 `bin`
目录加入 `PATH`。`dot` 不可用时只有 `architecture_diagram` 自动退回旧的确定性
布局并发出 warning,其它渲染链路不受影响。

## 三步使用

1. 解析输入:

```bash
PYTHONPATH=backend python -m app.cli.parse samples/input/需求说明.docx --output output/document_ir.json
```

2. 生成 Prompt,由 stub 或内网 generator 产目标 IR:

```bash
PYTHONPATH=backend python -m app.cli.prompt --kind word --context output/document_ir.json --max-output-chars 6000 --output output/prompt.txt
```

3. 校验后渲染并复检:

```bash
PYTHONPATH=backend python -m app.cli.render --type word samples/ir/word_valid_03_table.json --output output/word.docx
PYTHONPATH=backend python -m app.cli.render --type deck samples/ir/deck_valid_full.json --output output/deck.pptx
PYTHONPATH=backend python -m app.cli.render --type deck samples/ir/deck_valid_full.json --template template.pptx --output output/deck-template.pptx
PYTHONPATH=backend python -m app.cli.check output/deck.pptx --classification "HUAWEI CONFIDENTIAL" --output-dir output/check-deck
```

## 一键验收

```bash
python scripts/verify.py
```

Windows:

```powershell
.\verify.ps1
```

通过条件:pytest 全绿,parsers/ir/lint 各不低于 80%,整体不低于 70%,四格式到 Word/Deck 的 stub 链路均通过多事实内容核对。

可靠性汇总（默认不联网、不调用真实模型）:

```powershell
.\.venv\Scripts\python.exe scripts\reliability_test.py
```

该命令输出 `output/qa/report.json`、JUnit XML 和本地 HTML 摘要。工作台浏览器测试是开发专用依赖，不进入离线生产 lock：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev-ui.txt
.\.venv\Scripts\python.exe scripts\reliability_test.py --ui
```

真实模型冒烟必须显式传入 `--real-model` 且已配置生成器；它是独立健康检查，不替代离线发布门禁。

静态检查同样是开发专用，不进入生产依赖闭包:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev-quality.txt
.\.venv\Scripts\python.exe -m ruff check backend scripts
```

## 先分析、再生成 Deck

```bash
python scripts/analyze.py samples/input/需求说明.docx --generator stub --output output/analysis.json
python scripts/generate.py samples/input/需求说明.docx --generator stub --depth 标准 --lint --output-dir output/deck-standard
python scripts/generate.py samples/input/需求说明.docx --generator stub --depth 详细 --lint --output-dir output/deck-detailed
```

`analyze` 只给基于 parser 实测数据的页数建议。`generate` 可选 `--depth 概览|标准|详细`
和 `--pages N`;均不传时保持原有生成行为。详细档采用大纲加分批 DeckIR 的方式避免弱模型
一次输出被截断,见 `docs/GENERATION.md`。

## 图片、信息图与视觉规划

DeckIR 2.2 支持真实图片、`image_text`、2-4 图 `image_grid`、漏斗/象限/循环/矩阵信息图、
scatter 和 combo。图片必须先规范化为独立 `AssetManifest 1.0`：

```powershell
$env:PYTHONPATH = Join-Path $PWD "backend"
.\.venv\Scripts\python.exe -m app.cli.assets C:\path\photo.png C:\path\evidence.webp --output-dir output\assets
.\.venv\Scripts\python.exe -m app.cli.render --type deck C:\path\deck-with-images.json `
  --asset-manifest output\assets\asset_manifest.json --output output\deck-with-images.pptx
```

合法 `image_ref` 会嵌入真实图片；缺失引用返回 `A005`，不会静默生成占位框。只有 IR 明确给出
`placeholder` 才绘制占位。渲染输出 `asset_usage_audit.json`，记录页码、适配方式、裁切和有效
DPI。生成链路同时输出 `visual_plan.json` 与 `visual_selection_audit.json`，说明系统为何推荐或
未采用某种图。1.4-2.1 DeckIR 只在内存迁移到 2.2，不覆盖用户原文件。

组合图由两张对齐的原生可编辑图表实现：主轴 bar 与次轴 line 各自保留为 PowerPoint 图表
对象。它不是单一 OOXML combo chart，但不栅格化，也不改写业务数据。

模板模式使用 DeckIR 2.2，并输出独立的 `template_profile.json`、`template_plan.json`、
`template_structure.json`、`template_replacement_audit.json` 和 `pptx_package_report.json`。
原型不安全或容量不足时记录 W201 并在模板母版/主题下重绘；字体替代记录 W202。实现为
纯 Python，不依赖 HTML、PptxGenJS、浏览器或外部 presentation skill。

## HTML 对照实验（非生产）

生产渲染固定为 `DeckIR 2.2 -> python-pptx`。`experiments/html2pptx/` 是隔离的
DeckIR -> HTML -> PptxGenJS 对照实验，不接入 CLI 默认生成、API、工作台或 Windows
离线依赖闭包，也不接收上传模板。

```powershell
Set-Location experiments\html2pptx
npm ci
Set-Location ..\..
.\.venv\Scripts\python.exe scripts\html2pptx_benchmark.py --suite --output-dir output\html2pptx-benchmark --skip-office
```

可传入已通过模板安全校验的源文件做模板基准：`--template <safe-template.pptx>`。报告
`engine_assessment.json` 会记录两套引擎的版本、PPTX/HTML SHA-256、HTML 溢出检查、
包校验、lint、原生对象统计、Office 视觉状态及不可自动切换的推荐。详见
`docs/HTML_EXPERIMENT.md`。

本地工作台:

```powershell
.\start_workbench.ps1
```

打开 `http://127.0.0.1:5056/static/index.html`；停止服务使用 `.\stop_workbench.ps1`。

失败任务会显示稳定错误码、阶段、是否可重试、支持编号和受控的失败报告下载；报告不保存输入正文、Prompt、密钥或异常堆栈。
任务状态会落盘并在刷新后恢复；服务为单 worker、4 个等待位、900 秒总超时，产物与脱敏审计保留 24 小时。

## Windows 原生工作台与 NGA

`desktop/DocumentWorkbench` 是 .NET 8 WPF 原生客户端，不使用 WebView2、Electron、PySide6
或第三方 UI 框架。它完整复用同一个 Flask API 和确定性生成链路，支持分析、Word/PPT、
模板、多图片、三档深度、任务恢复/取消、产物与审计下载。桌面进程只启动自身的隐藏
`pythonw.exe` 后端，绑定 `127.0.0.1` 随机端口，并用每次启动随机生成的
`X-Workbench-Session` 保护全部 API。

NGA 采用 OpenAI-compatible Chat Completions，默认路径 `/v1/chat/completions`、非流式、
`temperature=0`。用户必须在“设置 > NGA”完成保存、连接测试和启用；已明确启用但配置
或凭据失效时会阻断生成，不会静默切回 Stub。Token 只保存在 Windows Credential Manager
的 `HuaweiDocumentGenerator/NGA`，非敏感配置保存在
`%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json`。

真实模型开发冒烟可用 `--generator codex` 走 opencode-go 网关（默认
`https://opencode.ai/zen/go/v1`，模型 `deepseek-v4-flash`，responses 协议）：
设置 `OPENAI_API_KEY`（网关 Token，仅环境变量，不落盘）后执行
`scripts/demo_e2e.py <input> --target word|deck --generator codex`；Stub 仍是默认生成器，
显式启用失败不会静默回退。

构建原生测试和便携包：

```powershell
$dotnet = "$env:LOCALAPPDATA\Codex\dotnet-sdk-8.0.423\dotnet.exe"
& $dotnet test desktop\DocumentWorkbench.Tests\DocumentWorkbench.Tests.csproj -c Debug
.\.venv\Scripts\python.exe scripts\package_document_workbench.py `
  --python-embed "$env:TEMP\python-3.12.10-embed-amd64.zip" `
  --graphviz-root "C:\Program Files\Graphviz" --overwrite
```

输出为 `dist/document-workbench-windows-x64-<VERSION>.zip` 及同名 SHA-256 文件；实际版本取自根目录 `VERSION`。便携包自带
.NET、Python 3.12、锁定 Python 依赖与 Graphviz，解压后双击 `DocumentWorkbench.exe`，
无需管理员权限。正式推广前仍须完成内网代码签名和干净 Windows 10/11 断网验收。

## 交付资产

- 固定 Office 输入:`samples/input/需求说明.docx`、`销售台账.xlsx`、`项目汇报.pptx`
- 五类 parser matrix:`samples/input/parser_matrix/manifest.json`
- 业务形态语料:`samples/input/business/`(docx/xlsx/pptx 各 3 个,由
  `scripts/make_business_samples.py` 确定性生成,用于解析与全链路回归;
  真实脱敏业务文件仍由人放入 `samples/input/real/`,不提交)
- IR 正反例:`samples/ir/`
- 结构 golden:`samples/expected/`
- 可编辑结果样例:`samples/output/`
- 成功/失败日志与截图:`samples/demo/`
- 18 张任务卡五件套索引:`docs/任务卡交付索引.md`

复现资产与演示:

```bash
PYTHONPATH=backend python scripts/build_delivery_assets.py
PYTHONPATH=backend python scripts/make_lint_violation.py
python scripts/record_demo.py
```

详细说明见 `docs/交付资产说明.md`、`docs/使用说明.md`（含生成器配置决策表：Stub / NGA 本机命令行 / NGA HTTP）、`docs/内网接入.md`、`docs/验收手册.md`。Windows 机器上的分步验收与人工交付清单见 `docs/WINDOWS_ACCEPTANCE_20260806.md`。

## 仓库结构与开发规则

- `backend/app/`: 正式 Python 业务模块；IR、解析、生成、渲染、lint 和安全边界按领域分包。
- `backend/tests/`: Python 单元与集成测试；新增行为必须有对应回归用例。
- `backend/schemas/`: 冻结的 IR/Profile/Plan JSON Schema 快照。
- `desktop/`: .NET 8 WPF 客户端与原生 UI 测试。
- `scripts/`: 可审计的验证、QA 和发布入口，不放唯一业务实现。
- `experiments/`: 非生产实验及其独立依赖，禁止被正式后端导入。
- `samples/`: 固定 fixture、正反 IR、golden 与演示资产。
- `docs/`: 使用、架构、验收、生成策略和 Git 工作流。

架构边界见 `ARCHITECTURE.md`，当前审计见 `REPO_AUDIT.md`，分批重构与回滚方法见
`REFACTOR_PLAN.md`，分支和发布规则见 `docs/GIT_WORKFLOW.md`。

## 常见问题

- Python 版本错误：重新运行 `bootstrap_windows.ps1`，后续命令固定使用 `.venv\Scripts\python.exe`。
- Graphviz 不可用：环境报告会标记确定性降级；普通 Word/PPT 生成仍可运行。
- 模板返回 `E003`：模板含宏、OLE、ActiveX、外部关系或损坏部件，需在 PowerPoint 中清理后另存为 `.pptx`。
- 图片返回 `A00x`：检查格式、大小、Manifest 哈希和 `image_ref`，系统不会把缺失图片静默变成占位框。
- NGA 返回 `E010-E014`：在工作台重新保存、测试并启用配置；显式 NGA 失败不会回退 Stub。
- 自动测试全绿但视觉未签字：必须继续执行 Windows Office 导出和人工终审。

## 人工边界

自动全绿不等于最终交付通过。真实脱敏业务文件、Windows 断网 wheelhouse 安装、目标字体下的 PPTX/DOCX 视觉观感和内容语义仍需人工验收,见 `docs/HUMAN_REVIEW.md`。
