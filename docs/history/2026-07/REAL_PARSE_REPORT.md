# 解析边界样例报告

日期: 2026-07-09

本报告分两块:本轮可自动复现的 `samples/input/synthetic/` 脏样例解析结果,以及仍需人工提供的 `samples/input/real/` 真实脱敏语料。synthetic 只覆盖结构边界,不替代任务书要求的真实文件。

## 本轮执行

生成命令:

```bash
python3 scripts/make_dirty_samples.py
```

逐个解析命令:

```bash
mkdir -p output/synthetic-parse
for f in samples/input/synthetic/*; do
  name="$(basename "$f")"
  PYTHONPATH=backend python3 -m app.cli.parse "$f" --output "output/synthetic-parse/${name}.document_ir.json"
done
```

结果:

| 指标 | 结果 |
| --- | --- |
| synthetic 文件总数 | 10 |
| 成功产出 DocumentIR | 10 |
| DocumentIR 模型复验 | 10/10 通过 `DocumentIR.model_validate_json` |
| 解析崩溃 | 0 |
| 输出目录 | `output/synthetic-parse/` |
| IR 契约 | 未修改 |

5 万行大表单独复测:

```bash
PYTHONPATH=backend python3 - <<'PY'
from pathlib import Path
from time import perf_counter
from app.cli.parse import parse_file
path = Path("samples/input/synthetic/xlsx_04_large_ledger_50000.xlsx")
started = perf_counter()
ir = parse_file(path)
print(f"{perf_counter() - started:.2f}s rows={ir.content.sheets[0].nrows} truncated={ir.content.sheets[0].truncated}")
PY
```

结果: `6.52s rows=50001 cols=8 truncated=True formulas=0`;warning 为 `xlsx preview truncated for sheet 超大巡检台账 to 20 rows x 15 columns`。

## synthetic §5.4 覆盖与判断

| 文件 | 命中的 §5.4 / 解析边界 | 输出信号 | 当前处理是否合理 |
| --- | --- | --- | --- |
| `xlsx_01_merged_ledger.xlsx` | 合并单元格(xlsx) | `merged_count=3`;预览中合并区域用左上格值填充 | 合理。满足“计数 + 左上格值填充预览”;未新增 schema 字段标注 merged。 |
| `xlsx_02_cross_sheet_refs.xlsx` | 多 sheet + 跨 sheet 引用/公式 | 3 个 sheet;公式计数合计 15 | 合理。DocumentIR 做结构摘要和公式计数,不求值公式。 |
| `xlsx_03_formula_report.xlsx` | 公式报表 | 公式计数 10 | 合理。记录公式存在;不依赖 Excel 计算缓存。 |
| `xlsx_04_large_ledger_50000.xlsx` | 超大文件 / 超大表 | `nrows=50001`;`truncated=True`;warning: `xlsx preview truncated for sheet 超大巡检台账 to 20 rows x 15 columns` | 合理。read_only 路径产出 20x15 预览和截断 warning;本样例未触发超时/内存降级。 |
| `docx_01_revisions_comments.docx` | 修订 / 批注 / 格式修改 | warnings: `unsupported comments: 1`, `unsupported revisions: 2`, `unsupported format revisions: 1` | 合理。按契约跳过修订/批注内容,记录数量。 |
| `docx_02_nested_lists_table_sections.docx` | 多级嵌套列表 + 表格 + 分节符 | blocks 含 `numbered_list`、`bullet_list`、`table`;warnings 为空 | 合理。结构可抽取,无需降级。 |
| `docx_03_embedded_image.docx` | 内嵌图片 | `stats.images=1`;warning: `docx image present #1 width=1.20in height=1.20in` | 合理。只记录存在与尺寸,不搬运二进制。 |
| `pptx_01_nested_groups.pptx` | 嵌套 / 组合形状(pptx) | bodies 含 `组合内层行动项`;shape_warnings 为空 | 合理。组合形状文本递归展开成功,无需 warning。 |
| `pptx_02_table_notes.pptx` | 表格 + 演讲备注 | tables=1;notes=`演讲备注:强调风险闭环和下周资源协调。` | 合理。结构可抽取,无需降级。 |
| `pptx_03_smartart_equivalent.pptx` | SmartArt / 等价复杂图形 | warning: `slide 1: SmartArt unsupported`;bodies 保留等价流程文本 | 合理。复杂图形记录 warning,文本形状仍提取。 |

## 本轮发现并修复的问题

| 问题 | 修复 | 回归测试 |
| --- | --- | --- |
| 普通 DOCX 被误报大量 `unsupported revisions`,原因是用 `xml.count("w:ins")` 子串计数 | 改为精确 XML 标签模式计数,并聚合同类 warning | `backend/tests/test_dirty_samples.py` |
| XLSX 合并单元格只计数,预览未按 §5.4 填充左上格值 | 从 worksheet XML 读取 merge ranges,预览范围内填充左上值 | `backend/tests/test_dirty_samples.py` |
| write_only 大表在 read_only 下 `max_row/max_column` 可能为空,导致不触发截断 | 增加 `calculate_dimension(force=True)` 尺寸兜底 | `backend/tests/test_dirty_samples.py` |
| 5 万行大表列画像重复按列扫描,解析耗时约 17.2 秒 | 改为单次扫描生成列画像,本次复测约 6.52 秒 | `backend/tests/test_xlsx_parser.py`, `backend/tests/test_dirty_samples.py` |

本次顺序复跑未发现新的解析崩溃或不合理降级。

## 真实语料仍需人工提供

执行命令:

```bash
find samples/input/real -maxdepth 3 -type f 2>/dev/null | sort
```

结果:当前仓库仍没有 `samples/input/real/` 真实脱敏文件。

后续人工续跑方式:

```bash
mkdir -p samples/input/real
# 放入脱敏真实 docx / xlsx / pptx 各至少 3 个后:
PYTHONPATH=backend python3 -m app.cli.parse samples/input/real/<file> --output output/real-parse/<file>.document_ir.json
```

续跑时需要逐个检查输出 JSON 的 `content` 与 `warnings`,并把每条 warning 映射到 §5.4 边界类别。若真实文件触发崩溃或不合理 warning,再修解析器并补对应回归测试。
