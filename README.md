# 华为风格文档生成工具链

本仓库按 `docs/taskbook.md` 实现命令行文档生成工具链。当前已完成 Word 输出链路的契约、校验、剥壳、修复回路与 DOCX 渲染核心。

## Word 输出

### 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

### 渲染合法 WordIR

```bash
PYTHONPATH=backend python3 -m app.cli.render \
  --type word \
  samples/ir/word_valid_03_table.json \
  --output output/word_valid_03_table.docx
```

输出是可编辑 DOCX,包含标题、正文、列表、表格、页眉、密级页脚与页码域。

### 查看失败提示

```bash
PYTHONPATH=backend python3 -m app.cli.render \
  --type word \
  samples/ir/word_invalid_e004_ragged_table.json \
  --output output/bad.docx
```

非法 IR 会在渲染前停止,并打印错误码、定位和修正建议。

### 当前验证命令

```bash
python3 -m pytest backend/tests -q
python3 scripts/verify.py
```

`scripts/verify.py` 会导出三份 Schema,通过 stub 生成 WordIR / DeckIR,并生成 `output/c0_word.docx`。
