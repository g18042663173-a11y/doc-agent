# HTML/PptxGenJS 对照实验

## 边界

生产链路固定为 `DeckIR 2.1 -> python-pptx`。HTML/PptxGenJS 仅位于
`experiments/html2pptx/`，用于确定性对照，不是第二个生产渲染器。它不修改 DeckIR，
不进入 `requirements-win312.lock`、`verify.ps1`、Flask API 或工作台，也不处理用户
上传的 PPTX 模板。

输入必须先经过现有 DeckIR Schema 校验。实验代码只将已校验 IR 映射为固定 HTML，
再用 Playwright 测量布局并由 PptxGenJS 生成可编辑文本、表格、图表和形状；LLM 不会
直接生成 HTML。

## 执行

Node 依赖仅在实验目录安装：

```powershell
Set-Location experiments\html2pptx
npm ci
Set-Location ..\..
.\.venv\Scripts\python.exe scripts\html2pptx_benchmark.py --suite --output-dir output\html2pptx-benchmark --skip-office
```

在 Windows 安装桌面 PowerPoint 的机器上，去掉 `--skip-office` 可生成 PDF、PNG、联系表
和视觉状态。没有人工批准的 PNG 基线时，视觉状态必须是 `manual_pending`，不是通过。

```powershell
.\.venv\Scripts\python.exe scripts\html2pptx_benchmark.py --suite --template <safe-template.pptx> --output-dir output\html2pptx-template-benchmark
```

`<safe-template.pptx>` 必须通过既有安全限制：只接受 `.pptx`，拒绝宏、OLE/ActiveX、
外部关系、路径穿越、损坏包和超限资源。HTML 引擎不会尝试复制模板；模板样例中它的
`native_editability` 必须为 `false`，以防把不支持的能力误判为通过。

## 证据与决策

每个样例目录保留 Python 和 HTML 两个子目录，以及：

- 可编辑 PPTX、PPTX 包关系报告和 lint 报告。
- 每页确定性 HTML、HTML 溢出/渐变检查和 HTML SHA-256。
- PPTX SHA-256、引擎版本、文本/表格/图表原生对象统计。
- 可选 Office PDF、PNG、联系表和视觉差异报告。

根目录的 `engine_assessment.json` 先执行以下硬门禁：Schema、PPTX 包完整、无 lint
Error、无 `HW-W03`/`HW-W07`、Office 可打开、所需文字/表格/图表仍为原生对象。任一项
失败即该引擎在该样例失败。

硬门禁后才记录 5 分制的视觉层级、中文排版、模板保真和部署可靠性。只有 HTML 在所有
样例（含模板样例）通过硬门禁、获得人工批准的视觉证据、总体得分至少高出 Python 15%
时，才会给出 `candidate_for_review`。即使如此，程序也不会切换生产引擎；架构变更仍需
人工确认。

`keep_python` 表示 HTML 已有硬门禁失败或无足够优势；`expand_html_experiment` 表示可继续
研究但证据或人工审查尚不足；`candidate_for_review` 仅表示可以提交人工架构评审。
