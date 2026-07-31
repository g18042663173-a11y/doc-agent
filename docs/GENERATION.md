# 分析、深度生成与修复流程

该能力只扩展 generator 上游编排。`analysis.json` 是独立建议结构，不属于 WordIR、DocumentIR 或 DeckIR；三份 IR Schema、parser、renderer、check 和 lint 不因此改变。

## 两步命令

先分析输入文件的实测规模，不生成 IR 或 PPT:

```powershell
.\.venv\Scripts\python.exe scripts\analyze.py <输入文件> --generator stub --output output\analysis.json
```

用户选档后生成 Deck:

```powershell
.\.venv\Scripts\python.exe scripts\generate.py <输入文件> --generator stub --depth 标准 --lint --output-dir output\deck-standard
.\.venv\Scripts\python.exe scripts\generate.py <输入文件> --generator stub --depth 详细 --lint --output-dir output\deck-detailed
.\.venv\Scripts\python.exe scripts\generate.py <输入文件> --generator stub --depth 标准 --pages 12 --lint --output-dir output\deck-12
```

- 概览默认目标 8 页，保留核心结论和关键指标。
- 标准默认目标 11 页，每个要点包含结论和具体依据。
- 详细默认目标 16 页，每个要点展开方法、数据、权衡或适用条件。
- `--pages` 覆盖档位默认页数；只给 `--pages` 时按标准深度组织。
- 两个参数都不传时继续执行兼容的单次生成路径。

## 详细档与截断处理

详细档先生成并校验独立大纲，再按每批最多 4 页调用相同 generator。每批返回完整 DeckIR envelope，并分别执行 JSON 剥壳、DeckIR Schema 校验和最多两次修复。只有校验成功的 `slides` 才能合并；合并结果最后再次执行完整 DeckIR 校验。

截断、结构错误或页数错误分别记录为 `D001/D002/D006` 并进入有限修复回路。`generation_manifest.json` 保存阶段、首次错误码和脱敏修复事件；`prompts/` 只用于非敏感测试语料。API 正式任务完成或失败后会清理 Prompt 和模型原文。

## NGA 约定

NGA 实现统一的 `generate(prompt, target=...)` 接口。除 `word_ir`、`deck_ir` 外，还接受 `analysis`。该 target 不对应新 IR，也不能改变三份 IR Schema。分批、剥壳、修复、合并和最终校验都在本地编排层完成，NGA 不感知 renderer。

用户显式启用 NGA 后，配置、鉴权、TLS、限流和响应格式错误分别映射为 `E010-E014`，不允许静默回退 Stub。

## 安全边界

- 生成器输出始终是不可信文本。
- Prompt、原始模型输出和输入正文不得进入失败报告。
- 模板、图片和 Office 包必须先通过各自安全预检。
- HTML/PptxGenJS 实验不参与此生产流程。
