# HTML/PptxGenJS 对照实验

此目录是非生产实验。它只接收已经通过 DeckIR 1.9 校验的 JSON，并生成 HTML 与可编辑的 PptxGenJS PPTX，用于和 `python-pptx` 产物比较。

它不支持上传模板、不被 Web API 调用、不进入 `requirements-win312.lock`，也不改变默认生产引擎。安装依赖后运行：

```powershell
npm ci
```

通过仓库根目录的 `scripts/html2pptx_benchmark.py` 运行对照与评估。Node、Chrome、Office 或人工视觉基线缺失时，实验报告必须标记待执行/待人工，不能把生产门禁标为失败或把实验误报为通过。
