# PARSE_AUDIT.md

日期: 2026-07-10

本轮只做代码层面的解析输入线审计,未改解析器代码、未改 IR 契约。审计对象为 `md/docx/xlsx/pptx -> DocumentIR`,重点核对 `docs/taskbook.md` §5.4 的“检测 -> 降级 / warning 契约”。本轮没有真实业务文件参与验证;`samples/input/real/` 当前为空。

## 审计依据

| 依据 | 关键要求 | 证据 |
| --- | --- | --- |
| 跨平台读写 | 文件读写显式 `encoding="utf-8"`;Windows 中文默认 GBK 不能读乱 | `docs/taskbook.md:128` |
| parse CLI | `parse.py <file>` 应输出 DocumentIR;超限内容自动截断并记入 warnings | `docs/taskbook.md:157` |
| DocumentIR | `warnings[]` 是降级与不支持项承载位置 | `docs/taskbook.md:263-278`, `backend/app/ir/document_ir.py:66-72` |
| §5.4 | 脏文件必须分类处理:合并单元格、组合形状、修订/批注/文本框、内嵌对象/图片、异常编码、超大文件/表 | `docs/taskbook.md:381-392` |
| S2 验收 | xlsx 要 `read_only + data_only`,预览 20x15,公式与合并计数;docx 不支持项入 warnings;pptx 组合形状递归展开 | `docs/taskbook.md:347-349` |

## 总体结论

当前解析线对“干净结构摘要”和部分 synthetic 脏样例是可用的,但不是完整健壮。主要风险不是所有文件都会崩,而是有多类真实办公边界会“解析成功但内容丢失/泄漏/语义错位,且没有 warning”。这正是本轮 false-green 重点。

自动样例已覆盖一部分边界: xlsx 合并/公式/多 sheet/50k 行大表,docx 修订/批注/图片,pptx 嵌套组/表格/备注/SmartArt marker。证据见 `backend/tests/test_dirty_samples.py:33-74` 与 `REAL_PARSE_REPORT.md:54-65`。但这些样例不是脱敏真实业务文件,不能替代 §10 要求的真实语料。

## §5.4 边界逐条核对

### XLSX

| 边界 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 合并单元格 | 部分 | 读取 worksheet XML merge ranges: `backend/app/parsers/xlsx_parser.py:166-205`;预览填充左上值: `backend/app/parsers/xlsx_parser.py:103-111`;测试: `backend/tests/test_dirty_samples.py:33-38` | `merged_count` 有,预览会填充;但没有按 §5.4 “标注 merged”的逐单元格标记,DocumentIR 也没有位置字段。 |
| 多 sheet | 已处理 | 遍历 `value_workbook.sheetnames`: `backend/app/parsers/xlsx_parser.py:26-29`;synthetic 测试 3 sheet: `backend/tests/test_dirty_samples.py:39-41` | 每个 sheet 单独摘要。 |
| 公式单元格 | 部分 | 第二次以 `data_only=False` 打开并统计 `cell.data_type == "f"`: `backend/app/parsers/xlsx_parser.py:20-21`, `backend/app/parsers/xlsx_parser.py:157-163`;测试: `backend/tests/test_xlsx_parser.py:16-44` | 只统计数量,不求值是符合边界;但未记录公式所在 sheet/单元格/外部引用,也没有 warning 文案说明“不求值”。 |
| 超大表 read_only + 预览截断 | 部分 | `read_only=True`: `backend/app/parsers/xlsx_parser.py:20-21`;预览 20x15: `backend/app/parsers/xlsx_parser.py:15-16`, `backend/app/parsers/xlsx_parser.py:78-88`;截断 warning: `backend/app/parsers/xlsx_parser.py:30-34`;测试: `backend/tests/test_xlsx_parser.py:47-63` | 预览截断有做;但列画像 `_column_stats` 仍按 `max_row=nrows` 扫完整 sheet 的前 15 列: `backend/app/parsers/xlsx_parser.py:46`, `backend/app/parsers/xlsx_parser.py:114-136`。没有超时/内存降级和“已处理范围”warning。 |
| 空 sheet | 部分 | `_sheet_dimensions` 对空 A1 返回 0,0: `backend/app/parsers/xlsx_parser.py:91-100`;测试创建空表但未断言空表行为: `backend/tests/test_xlsx_parser.py:29-30` | 不崩,但空 sheet 无 warning;用户无法区分“真实空表”和“解析没读到内容”。 |
| 隐藏行列 | 未处理 | xlsx parser 只用 `sheet.iter_rows(...)`: `backend/app/parsers/xlsx_parser.py:78-87`, `backend/app/parsers/xlsx_parser.py:117-123`;没有读取 `row_dimensions` / `column_dimensions` 或 hidden 标记 | 隐藏内容会进入预览/列画像,且没有 warning。真实台账常把辅助列或敏感列隐藏,这是 false-green 与潜在泄露风险。 |
| 异常单元格类型:日期/错误值/布尔/None | 部分 | 日期类型猜测: `backend/app/parsers/xlsx_parser.py:144-154`;None -> 空串: `backend/app/parsers/xlsx_parser.py:224-229`;bool 从 number 排除: `backend/app/parsers/xlsx_parser.py:148` | 日期能猜;bool/error/None 没有单独统计或 warning。Excel 错误值如 `#DIV/0!` 会被 `_stringify` 当普通字符串。 |
| 超宽表 | 部分 | `ncols > MAX_PREVIEW_COLS` 会触发 `truncated`: `backend/app/parsers/xlsx_parser.py:30-34`;预览最多 15 列: `backend/app/parsers/xlsx_parser.py:82-85` | 有截断 warning;但未给出被截断列名范围。 |
| 图表对象 | 已处理 | `_package_warnings` 统计 `xl/charts/`: `backend/app/parsers/xlsx_parser.py:208-217`;测试: `backend/tests/test_xlsx_parser.py:66-82` | 只记录数量,不解析图表语义,符合降级边界。 |
| 内嵌图片 / OLE | 未处理 | `_package_warnings` 只看 charts/pivotTables/vba: `backend/app/parsers/xlsx_parser.py:208-221`;没有 `xl/media/`, `xl/drawings/`, `embeddings/` 检测 | 与 §5.4 “内嵌对象 / 图片 / OLE 记录存在与尺寸”不一致。 |

### DOCX

| 边界 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 修订痕迹 | 已处理 | XML 扫描 `<w:ins>`, `<w:del>`, rPr/pPr change: `backend/app/parsers/docx_parser.py:157-181`;测试: `backend/tests/test_dirty_samples.py:51-55` | 记录数量,跳过内容。 |
| 批注 | 已处理 | 扫描 `<w:commentRangeStart>`: `backend/app/parsers/docx_parser.py:166-180`;测试: `backend/tests/test_docx_parser.py:102-120` | 记录数量;不提取批注正文。 |
| 嵌套表格 | 未处理 | 顶层只遍历 body 子节点: `backend/app/parsers/docx_parser.py:96-102`;表格 cell 只拼段落文本: `backend/app/parsers/docx_parser.py:153-154` | 嵌套表格内容会丢失或混入单元格段落,无 warning。 |
| 图片 | 部分 | 只统计 `document.inline_shapes`: `backend/app/parsers/docx_parser.py:88`, `backend/app/parsers/docx_parser.py:184-188`;测试: `backend/tests/test_docx_parser.py:85-99` | inline 图片有 warning;浮动/锚定图片、OLE、DrawingML 复杂对象未显式检测。 |
| 分节 | 部分 | parser 不读 `document.sections`,主循环只按 body 顺序抽段落/表格: `backend/app/parsers/docx_parser.py:37-70` | 分节不会崩,但页眉页脚变化、分节语义、分栏等都不记录 warning。synthetic 只证明不崩: `scripts/make_dirty_samples.py:150-172`。 |
| 超长文档 | 部分 | 只有表格行预览 20 行: `backend/app/parsers/docx_parser.py:138-150`;无全局段落/字符上限 | 长段落不截断、不记 W103;极长 docx 可能产出巨大 DocumentIR。 |
| 异常样式 | 部分 | 标题只认样式名正则与 outlineLevel: `backend/app/parsers/docx_parser.py:20`, `backend/app/parsers/docx_parser.py:105-121`;列表只认样式名包含 List Bullet/Number: `backend/app/parsers/docx_parser.py:124-135` | 非标准中文模板、自定义样式、编号 XML 不一定识别,会降为普通段落且无 warning。 |
| 空文档 | 部分 | 空文档会返回合法 DocumentIR,`blocks=[]`,无 warning: `backend/app/parsers/docx_parser.py:74-92`;DocumentIR 允许空 blocks: `backend/app/ir/document_ir.py:59-63` | 不崩,但静默成功;后续 generator 可能误以为解析正常。 |

### PPTX

| 边界 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 组合形状 | 已处理 | `_iter_shapes` 递归 child shapes: `backend/app/parsers/pptx_parser.py:149-154`;测试: `backend/tests/test_pptx_parser.py:102-109` | 成功路径可展开文本。 |
| 嵌套组 | 部分 | synthetic 注入嵌套组并解析出文本: `scripts/make_dirty_samples.py:274-295`;测试: `backend/tests/test_dirty_samples.py:66-68` | 没有 try/except;如果 group traversal 或 shape 属性访问失败,不会按 §5.4 写 `shape_warnings`,而会抛异常。 |
| SmartArt | 部分 | XML 含 `dgm:` 时 warning: `backend/app/parsers/pptx_parser.py:125-137`;synthetic 测试: `backend/tests/test_dirty_samples.py:73-74` | 只检测 marker,不提取 SmartArt 文本;真实 SmartArt 的文字可能被静默丢失,取决于 python-pptx 是否暴露为普通 text shape。 |
| 表格 | 已处理 | `_slide_tables` 提取 header/rows: `backend/app/parsers/pptx_parser.py:87-100`;测试: `backend/tests/test_pptx_parser.py:20-47` | 没有行列截断,但任务书未给 PPT 输入表格预览上限。 |
| 演讲备注 | 已处理 | `_slide_notes`: `backend/app/parsers/pptx_parser.py:117-122`;测试: `backend/tests/test_pptx_parser.py:20-47` | 读取失败时返回 None,无 warning。 |
| 图表 | 部分 | chart 只写 `[chart] title type` 到 bodies: `backend/app/parsers/pptx_parser.py:80-84`, `backend/app/parsers/pptx_parser.py:103-110`;测试: `backend/tests/test_pptx_parser.py:81-99` | 不解析数据系列/轴/标签;没有 warning 说明图表数据未解析。 |
| 图片 | 已处理 | `_slide_warnings` 记录图片尺寸: `backend/app/parsers/pptx_parser.py:134-137`;stats 计数: `backend/app/parsers/pptx_parser.py:140-146`;测试: `backend/tests/test_pptx_parser.py:64-79` | 只记录存在与尺寸,符合边界。 |
| 超多页 | 未处理 | parse loop 无页数上限或 warning: `backend/app/parsers/pptx_parser.py:17-31` | 大 deck 会全量扫描,无超时/内存降级。 |
| 空白页 | 部分 | 空页会生成 slide summary,空 title/bodies/tables/notes: `backend/app/parsers/pptx_parser.py:21-30` | 不崩,但无 warning 表明该页为空。 |

### Markdown

| 边界 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 异常嵌套 | 部分 | 列表只支持两级,缩进 >=2 统一 level 2: `backend/app/parsers/md_parser.py:122-135` | 三级以上被静默压成二级,没有 warning。 |
| 超大文件 | 未处理 | 一次性 `read_text` + `splitlines`: `backend/app/parsers/md_parser.py:16-18`;无文件大小/行数/时间限制 | 不符合 §5.4 超大文件“预览截断/超时降级”。 |
| 编码问题:非 UTF-8 | 未处理 | 只 `path.read_text(encoding="utf-8")`: `backend/app/parsers/md_parser.py:16-18`;CLI catch 只打印异常: `backend/app/cli/parse.py:35-39` | GBK/UTF-16 中文 md 会直接失败,没有 DocumentIR warning。 |
| 畸形表格 | 未处理 | 表格行列不等时直接不 append,也不 warning: `backend/app/parsers/md_parser.py:102-115` | 这是明确 false-green:返回成功但丢掉畸形行。 |
| 空文件 | 部分 | 空文件返回 `blocks=[]`,warnings=[]: `backend/app/parsers/md_parser.py:72-94` | 不崩,但静默成功。 |

## 错误处理审计

| 场景 | 当前行为 | 证据 | 缺口 |
| --- | --- | --- | --- |
| 不支持后缀 | `parse_file` 直接 `ValueError("unsupported input format")` | `backend/app/cli/parse.py:20-30` | 没有错误码或机器可读报告。 |
| 文件损坏 / 读不了 | parser 内基本不捕获;CLI 捕获所有异常并 `print("parse failed: ...")`,返回 1 | `backend/app/cli/parse.py:33-39`;各 parser 打开文件处: `md_parser.py:16-18`, `docx_parser.py:23-24`, `xlsx_parser.py:19-23`, `pptx_parser.py:12-13` | 不是任务书式 E/W/D 结构化错误;无法定位到文件类型、边界类别、建议动作。 |
| 超限 | md/pptx 无全局超限处理;xlsx/docx 只有部分预览截断 | `xlsx_parser.py:30-34`, `docx_parser.py:138-150`, `md_parser.py:16-18`, `pptx_parser.py:17-31` | §5.4 要求超时/超内存 warning + 已处理范围,当前没有统一机制。 |
| 格式非法 | 依赖第三方库抛异常 | 同上 | CLI 层只返回 1,没有 JSON report;调用 `parse_file()` 的上层会直接收到异常。 |

## 降级可追溯性

已追溯的降级:

- xlsx 预览截断: warning 文案在 `backend/app/parsers/xlsx_parser.py:30-34`;测试在 `backend/tests/test_xlsx_parser.py:47-63`。
- xlsx chart/pivot/VBA: warning 文案在 `backend/app/parsers/xlsx_parser.py:208-221`;测试在 `backend/tests/test_xlsx_parser.py:66-82`。
- docx 表格截断: warning 文案在 `backend/app/parsers/docx_parser.py:66-70`;测试在 `backend/tests/test_docx_parser.py:44-63`。
- docx 修订/批注/文本框/SmartArt: warning 文案在 `backend/app/parsers/docx_parser.py:157-181`;测试在 `backend/tests/test_docx_parser.py:102-120`。
- docx inline 图片: warning 文案在 `backend/app/parsers/docx_parser.py:184-188`;测试在 `backend/tests/test_docx_parser.py:85-99`。
- pptx transition/timing/SmartArt/image: warning 文案在 `backend/app/parsers/pptx_parser.py:125-137`;测试覆盖 transition/image/SmartArt: `backend/tests/test_pptx_parser.py:49-79`, `backend/tests/test_dirty_samples.py:73-74`。

静默或弱追溯的降级:

- xlsx 合并单元格只 `merged_count`,没有每个预览格的 merged 标记: `backend/app/parsers/xlsx_parser.py:47-49`, `backend/app/ir/document_ir.py:37-47`。
- xlsx 公式只计数,不提示“不求值/可能无缓存值”: `backend/app/parsers/xlsx_parser.py:47`, `backend/app/parsers/xlsx_parser.py:157-163`。
- xlsx 隐藏行列、图片/OLE、错误值没有 warning: `backend/app/parsers/xlsx_parser.py:208-221`。
- docx 嵌套表格、分节、非标准列表样式、浮动图片没有 warning: `backend/app/parsers/docx_parser.py:96-154`。
- pptx 图表数据不解析但仍返回成功,没有 warning: `backend/app/parsers/pptx_parser.py:80-84`。
- md 畸形表格行、三级列表、空文件没有 warning: `backend/app/parsers/md_parser.py:102-135`。

## False-Green 风险

| ID | 严重程度 | 场景 | 为什么是 false-green | 证据 |
| --- | --- | --- | --- | --- |
| PA-FG-001 | 必须修 | XLSX 隐藏行/列 | 隐藏数据会进入预览和列画像,既可能泄漏,也可能让用户误以为这是可见台账内容 | 只用 `iter_rows` 读值: `backend/app/parsers/xlsx_parser.py:78-87`, `backend/app/parsers/xlsx_parser.py:117-123`;没有 hidden 检测 |
| PA-FG-002 | 必须修 | XLSX 内嵌图片/OLE | §5.4 要求记录存在与尺寸;当前返回成功但完全无感知 | `_package_warnings` 只检测 charts/pivot/VBA: `backend/app/parsers/xlsx_parser.py:208-221` |
| PA-FG-003 | 必须修 | DOCX 嵌套表格 | 嵌套表格中的关键内容可能直接丢失,但返回合法 DocumentIR | 顶层 body 遍历: `backend/app/parsers/docx_parser.py:96-102`;cell 只取段落: `backend/app/parsers/docx_parser.py:153-154` |
| PA-FG-004 | 必须修 | MD 畸形表格 | 行列不等的表格行被跳过,没有 warning | `if len(row) == len(header)` 才 append: `backend/app/parsers/md_parser.py:107-114` |
| PA-FG-005 | 建议修 | PPTX 图表 | 只输出 `[chart] type`,不提示数据系列未解析;模型可能基于缺失数据生成错误结论 | `backend/app/parsers/pptx_parser.py:80-84` |
| PA-FG-006 | 建议修 | DOCX 空文档 / MD 空文件 | 返回 pass-like DocumentIR 且 warnings 为空,后续链路可能生成无依据内容 | `backend/app/parsers/docx_parser.py:74-92`, `backend/app/parsers/md_parser.py:72-94` |

## 问题分级清单

### 必须修

| ID | 影响格式 | 问题 | 证据 | 建议方向 |
| --- | --- | --- | --- | --- |
| PA-MF-001 | 全部 | 解析失败没有结构化错误码或机器可读报告;损坏文件/编码错误/非法格式只裸异常到 CLI stderr | `backend/app/cli/parse.py:35-39`;parser 打开文件处: `backend/app/parsers/xlsx_parser.py:19-23`, `backend/app/parsers/docx_parser.py:23-24`, `backend/app/parsers/pptx_parser.py:12-13`, `backend/app/parsers/md_parser.py:16-18` | 增加 parse 层错误报告模型或统一错误码映射;CLI 输出 JSON/MD 报告并保留非零退出。 |
| PA-MF-002 | xlsx | 超大表仍全量扫描列画像前 15 列,无超时/内存降级和“已处理范围”warning | `backend/app/parsers/xlsx_parser.py:46`, `backend/app/parsers/xlsx_parser.py:114-136`;§5.4 要求: `docs/taskbook.md:391-392` | 限制列画像扫描行数或采样;增加耗时/行数上限与 warning。 |
| PA-MF-003 | xlsx | 隐藏行列未检测,内容可能静默进入预览 | `backend/app/parsers/xlsx_parser.py:78-87`, `backend/app/parsers/xlsx_parser.py:117-123` | 检查 `row_dimensions`/`column_dimensions` hidden;决定跳过或保留但必须 warning。 |
| PA-MF-004 | xlsx | 内嵌图片/OLE 未检测 | `backend/app/parsers/xlsx_parser.py:208-221`;§5.4: `docs/taskbook.md:390` | 扫描 `xl/media/`, `xl/drawings/`, `xl/embeddings/`,记录数量和可得尺寸。 |
| PA-MF-005 | xlsx | 错误值/布尔/None 等异常单元格类型被普通字符串化或静默为空 | `backend/app/parsers/xlsx_parser.py:144-154`, `backend/app/parsers/xlsx_parser.py:224-229` | 统计错误单元格、布尔列、空值比例异常;至少 warning。 |
| PA-MF-006 | docx | 嵌套表格静默丢失 | `backend/app/parsers/docx_parser.py:96-102`, `backend/app/parsers/docx_parser.py:153-154` | 递归解析 cell 内表格或记录 unsupported nested tables warning。 |
| PA-MF-007 | pptx | 组合/嵌套组递归失败时不会降级为 shape_warning,会直接异常 | `_iter_shapes` 无异常边界: `backend/app/parsers/pptx_parser.py:149-154`;§5.4 要求展开失败写 warning: `docs/taskbook.md:388` | shape 访问包 try/except,失败写入当前 slide 的 `shape_warnings`。 |
| PA-MF-008 | md | 非 UTF-8 文件直接失败,没有 UTF-8 兜底或 warning | `backend/app/parsers/md_parser.py:16-18`;CLI 行为: `backend/app/cli/parse.py:35-39`;§5.4: `docs/taskbook.md:391` | 支持 `utf-8-sig`/GBK 探测或 errors replacement,并把替换/降级写 warning。 |
| PA-MF-009 | md | 畸形表格行静默丢弃 | `backend/app/parsers/md_parser.py:102-115` | 对行列不规整记录 warning,保留可解析行或把整表降级为段落。 |

XLSX 专属必须修数量:4 个(PA-MF-002~PA-MF-005)。另有 PA-MF-001 是跨 parser 的错误码缺口,也影响 xlsx。

### 建议修

| ID | 影响格式 | 问题 | 证据 | 建议方向 |
| --- | --- | --- | --- | --- |
| PA-SF-001 | xlsx | 合并单元格没有逐格 merged 标记 | `backend/app/parsers/xlsx_parser.py:47-49`, `backend/app/ir/document_ir.py:37-47` | 不改契约前可在 warning 中列 merge ranges;契约演进时增加 merged ranges 字段。 |
| PA-SF-002 | xlsx | 公式只计数,不记录位置/外部引用/是否 data_only 无缓存 | `backend/app/parsers/xlsx_parser.py:157-163` | 增加 formula samples 或 warning。 |
| PA-SF-003 | xlsx | 空 sheet 无 warning | `backend/app/parsers/xlsx_parser.py:91-100` | 对空 sheet 加 warning 或 stats 标记。 |
| PA-SF-004 | docx | 分节、分栏、页眉页脚差异未记录 | `backend/app/parsers/docx_parser.py:37-70` | 记录 section_count 和 warning,特别是不同页眉页脚。 |
| PA-SF-005 | docx | 非标准样式降级为普通段落无 warning | `backend/app/parsers/docx_parser.py:105-135` | 对无法识别但带 numbering/outline 线索的段落记录 warning。 |
| PA-SF-006 | pptx | 图表数据不解析但无 warning | `backend/app/parsers/pptx_parser.py:80-84` | 在 `shape_warnings` 中记录 chart data unsupported。 |
| PA-SF-007 | pptx | 超多页/空白页无 warning | `backend/app/parsers/pptx_parser.py:17-31` | 页数阈值、空白页 warning。 |
| PA-SF-008 | md | 三级以上嵌套列表静默压成二级 | `backend/app/parsers/md_parser.py:130-132` | 超过两级时 warning。 |

### 可接受

| ID | 影响格式 | 判断 | 证据 | 边界 |
| --- | --- | --- | --- | --- |
| PA-OK-001 | xlsx | 多 sheet、基本公式计数、chart/pivot/VBA warning 已有 | `backend/app/parsers/xlsx_parser.py:26-49`, `backend/app/parsers/xlsx_parser.py:157-221` | 不求值公式是任务书明确降级。 |
| PA-OK-002 | docx | 修订/批注/文本框/SmartArt marker 和 inline 图片已有 warning | `backend/app/parsers/docx_parser.py:157-188` | 仅证明 XML marker 能识别,不证明真实复杂 Word 全覆盖。 |
| PA-OK-003 | pptx | 普通 title/body/table/notes/image 和组合文本成功路径可用 | `backend/app/parsers/pptx_parser.py:55-122`, `backend/app/parsers/pptx_parser.py:134-154` | 不代表 SmartArt/母版/复杂图表可用。 |
| PA-OK-004 | md | 基础标题/段落/列表/表格可用 | `backend/app/parsers/md_parser.py:30-72`;测试: `backend/tests/test_md_parser.py:14-56` | 只覆盖 UTF-8 正常 Markdown。 |

## 编码健壮性

- Markdown 是最薄弱点:只按 UTF-8 读取,GBK 中文会抛 `UnicodeDecodeError`,不会产出 DocumentIR warning。证据: `backend/app/parsers/md_parser.py:16-18`, `backend/app/cli/parse.py:35-39`。
- DOCX/XLSX/PPTX 是 zip/XML 容器,主要读取 bytes 或交给 python-docx/openpyxl/python-pptx,内部 XML 读取处 docx 使用 `decode("utf-8", errors="ignore")`: `backend/app/parsers/docx_parser.py:157-164`;xlsx 直接从 zip 读 bytes 给 ElementTree: `backend/app/parsers/xlsx_parser.py:166-205`;pptx 依赖库打开: `backend/app/parsers/pptx_parser.py:12-13`。
- CLI 输出写入 JSON 显式 UTF-8: `backend/app/cli/parse.py:40-42`。
- 当前没有“非 UTF-8 降级后继续产 DocumentIR 并写 warning”的实现,与 §5.4 “混合 / 异常编码”不一致。

## 真实文件验证清单

这些边界纯代码审计无法证明,必须等内网/真实脱敏文件:

### XLSX

- 含隐藏 sheet、隐藏行列、筛选隐藏行的真实台账,确认是否跳过或 warning。
- 含真实嵌入图片、OLE、图表、透视表、VBA、外部链接、受保护工作表的工作簿。
- 含真实公式缓存、跨 workbook 引用、共享公式、数组公式、错误值(`#DIV/0!`等)、日期系统差异的报表。
- 超大真实工作簿:>100k 行、>200 列、多 sheet,确认耗时、内存、截断范围 warning。

### DOCX

- Word 真修订、批注、文本框、SmartArt、浮动图片、页眉页脚多分节、分栏、脚注/尾注、嵌套表格。
- 大文档和损坏/半损坏 docx,确认错误码和降级报告。
- 使用企业模板自定义标题/编号样式的文件,确认 outline/list 识别率。

### PPTX

- 真实 SmartArt、嵌套组合、多级组、母版继承文本、隐藏幻灯片、动画/切换、嵌入 Excel 图表/OLE、复杂图表数据。
- 大型汇报:>100 页,含大量图片和备注,确认耗时与内存。

### Markdown

- GBK/UTF-16/带 BOM 中文 md,混合换行符,超大 md,畸形表格,三层以上嵌套列表。

## 初始审计时各解析器最薄弱点

| 解析器 | 最薄弱的一环 |
| --- | --- |
| md | 编码和畸形表格:非 UTF-8 直接失败,畸形表格行静默丢弃。 |
| docx | 嵌套表格/复杂对象:顶层解析可用,但嵌套表格、浮动对象、分节语义容易无 warning 丢失。 |
| xlsx | 真实台账边界:隐藏行列、图片/OLE、错误值与超大表全量列画像是最明显缺口。 |
| pptx | 复杂图形/图表:组合文本成功路径可用,但 SmartArt/图表数据/递归失败没有足够降级证据。 |

## 2026-07-10 修复记录

以下项已按本报告的“必须修”清单补齐,DocumentIR schema 未修改:

| 原问题 | 修复与证据 | 回归测试 |
| --- | --- | --- |
| PA-MF-001 解析失败无结构化错误 | 新增 `ParseFailure`,四个 parser 入口统一映射读取/损坏失败为 `E001`;未知后缀映射 `E003`;CLI 在 `<output>.report.json` / `.report.md` 写结构化报告并非零退出。`backend/app/parsers/errors.py:15-116`;`backend/app/cli/parse.py:20-59` | `backend/tests/test_parse_errors.py:19-85` 覆盖四格式损坏输入、未知后缀与 CLI 报告。 |
| PA-MF-002 超大 XLSX 全表列画像 | 列画像与公式统计限制到前 1000 行采样;触发后写 `W103` 并说明采样/下界。`backend/app/parsers/xlsx_parser.py:17-91`, `backend/app/parsers/xlsx_parser.py:201-273` | `backend/tests/test_xlsx_parser.py:107-124`。 |
| PA-MF-003 XLSX 隐藏内容泄露 | 从 worksheet XML 读取隐藏行列;默认从 preview/header/col_stats/公式与类型扫描跳过,并写明数量的 warning。`backend/app/parsers/xlsx_parser.py:93-211`, `backend/app/parsers/xlsx_parser.py:299-341` | `backend/tests/test_xlsx_parser.py:66-101` 覆盖隐藏正例和可见反例。 |
| PA-MF-004/005 XLSX 对象与特殊单元格无感知 | 检测 `xl/media/`、`xl/embeddings/`、错误/布尔/日期单元格并记录降级 warning。`backend/app/parsers/xlsx_parser.py:246-273`, `backend/app/parsers/xlsx_parser.py:344-366` | `backend/tests/test_xlsx_parser.py:127-163`。 |
| PA-MF-006 DOCX 嵌套表格静默丢失 | 嵌套表格无法用现有 WordBlock 契约表达时记录数量 warning,不再静默。`backend/app/parsers/docx_parser.py:64-74`, `backend/app/parsers/docx_parser.py:157-166` | `backend/tests/test_docx_parser.py:66-85`。 |
| PA-MF-007 PPTX 组合形状递归失败 | 递归遍历失败时记录 `shape_warnings` 并跳过子形状,不让整个 deck 崩溃。`backend/app/parsers/pptx_parser.py:17-35`, `backend/app/parsers/pptx_parser.py:154-172` | `backend/tests/test_pptx_parser.py:112-121`。 |
| PA-MF-008/009 Markdown 编码和畸形表格 | 优先 UTF-8-SIG,回退 GB18030 并 warning;编码都失败时 `E001`;畸形表格行计数 warning。`backend/app/parsers/md_parser.py:17-104`, `backend/app/parsers/md_parser.py:129-149` | `backend/tests/test_md_parser.py:58-81`。 |

验收: `VERIFY_RUNNING=1 PYTHONPATH=backend python -m pytest backend/tests -q` 为 `186 passed`;`python scripts/verify.py` 通过,coverage: `app/parsers=92.56%`, `app/ir=92.73%`, `app/lint=92.25%`, overall `88.78%`。

修复后仍建议后续处理的非“必须修”项: xlsx 合并区域位置标记和空 sheet warning,docx 浮动对象/分节/自定义样式,pptx SmartArt 图表数据与超多页,md 超大文件和三级列表。这些保留在前文“建议修”与“真实文件验证清单”,没有被标成已完成。
