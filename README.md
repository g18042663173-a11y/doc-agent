# 华为风格文档生成工具链

本仓库实现确定性的离线文档流水线:

```text
md/docx/xlsx/pptx -> DocumentIR -> Prompt/generator -> WordIR/DeckIR -> DOCX/PPTX -> 合规报告
```

IR 是唯一契约。模型文本必须先剥壳和校验,非法 IR 不进入 renderer。

## 环境

- Python 3.12
- 依赖见 `requirements.txt`
- 目标环境为内网 Windows 离线运行;Mac 用于开发和自动验收

```bash
python -m pip install -r requirements.txt
```

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

## 先分析、再生成 Deck

```bash
python scripts/analyze.py samples/input/需求说明.docx --generator stub --output output/analysis.json
python scripts/generate.py samples/input/需求说明.docx --generator stub --depth 标准 --lint --output-dir output/deck-standard
python scripts/generate.py samples/input/需求说明.docx --generator stub --depth 详细 --lint --output-dir output/deck-detailed
```

`analyze` 只给基于 parser 实测数据的页数建议。`generate` 可选 `--depth 概览|标准|详细`
和 `--pages N`;均不传时保持原有生成行为。详细档采用大纲加分批 DeckIR 的方式避免弱模型
一次输出被截断,见 `GENERATION_NOTES.md`。

## 交付资产

- 固定 Office 输入:`samples/input/需求说明.docx`、`销售台账.xlsx`、`项目汇报.pptx`
- 五类 parser matrix:`samples/input/parser_matrix/manifest.json`
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

详细说明见 `docs/交付资产说明.md`、`docs/使用说明.md`、`docs/内网接入.md`、`docs/验收手册.md`。

## 人工边界

自动全绿不等于最终交付通过。真实脱敏业务文件、Windows 断网 wheelhouse 安装、目标字体下的 PPTX/DOCX 视觉观感和内容语义仍需人工验收,见 `HUMAN_REVIEW.md`。
