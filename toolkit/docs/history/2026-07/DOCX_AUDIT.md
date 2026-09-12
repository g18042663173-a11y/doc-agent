# DOCX_AUDIT.md

本轮只做 Word 输出体检,未改业务代码或 IR 契约。审计对象是 WordIR -> DOCX 链路,重点检查近期 PPT 主题校准后 DOCX 是否同步。

## 取证范围

- 代码与规格:
  - `docs/taskbook.md:210-221`: WordIR v1.0 block 类型与渲染要点。
  - `docs/taskbook.md:244-259`: WordIR 错误码与渲染硬性要求。
  - `docs/taskbook.md:328-333`: S1-1 到 S1-6 的 Word 输出验收标准。
  - `docs/taskbook.md:488`: Word 输出验收矩阵。
  - `backend/app/rendering/themes/hw_theme.json:3-21`: 当前主题色板,主红为 `#C7000B`。
  - `backend/app/rendering/themes/hw_theme.json:23-51`: 当前字体与字号体系。
  - `backend/app/rendering/docx_renderer.py:23-30`: DOCX renderer 独立 `STYLES` 常量。
  - `backend/app/lint/docx_lint.py:45-89`: DOCX lint 实际检查范围。
- 生成样例:
  - `output/docx_audit/word_audit_sample.json`: 覆盖 `heading/paragraph/bullet_list/numbered_list/table/image_placeholder/page_break`。
  - `output/docx_audit/word_audit_sample.docx`: 用正式 `render.py --type word` 生成。
  - `output/docx_audit/render/page-1.png`, `output/docx_audit/render/page-2.png`: 用 `render_docx.py --emit_pdf` 渲染后人工目检。
  - `output/docx_audit/parse/source.md` -> `output/docx_audit/parse/document_ir.json` -> `output/docx_audit/parse/word_from_parse.docx`: 解析到 Word 输出内容准确性抽查。
- 运行结果:
  - `PYTHONPATH=backend python -m app.cli.render --type word output/docx_audit/word_audit_sample.json --output output/docx_audit/word_audit_sample.docx`: 成功产出 DOCX。
  - `render_docx.py output/docx_audit/word_audit_sample.docx --output_dir output/docx_audit/render --emit_pdf`: `Pages rendered to .../output/docx_audit/render`。
  - `PYTHONPATH=backend python -m pytest backend/tests/test_docx_renderer.py backend/tests/test_docx_lint.py backend/tests/test_ir_validation.py backend/tests/test_word_samples.py -q`: `50 passed`。
  - 对样例跑 `check_docx`: 两份样例均 `{'errors': 0, 'warnings': 0, 'infos': 0, 'pass': True}`。

## 一、主题一致性

结论: DOCX 没有同步最新 `hw_theme.json`。它仍用 renderer 内部硬编码样式,且保留 Word 默认蓝色标题体系。

证据:

- 当前主题主红是 `#C7000B`,正文色 `#1D1D1A`,字体为微软雅黑/Arial,字号体系为 14/12/11/10/9/8pt: `backend/app/rendering/themes/hw_theme.json:3-51`。
- DOCX renderer 没有加载 `hw_theme.json`,而是使用 `STYLES = {"font": "微软雅黑", "western_font": "Arial", "normal_size": 11, "heading_sizes": {1: 18, 2: 15, 3: 13, 4: 12}, ...}`: `backend/app/rendering/docx_renderer.py:23-30`。
- 渲染样例 XML 抽查结果:
  - `has C7000B: False`
  - `has 4F81BD word-blue: True`
  - `has table red fill: False`
  - `has table gray fill: True`
- 视觉结果: `output/docx_audit/render/page-1.png` 中标题为 Word 默认蓝,不是华为红;正文和标题字号明显大于 PPT 主题的 9-14pt 体系。

不一致处:

| 项 | 最新主题 | DOCX 当前 | 状态 |
| --- | --- | --- | --- |
| 主红 | `#C7000B` | 未出现;标题呈 Word 默认蓝 `4F81BD` | 必须修 |
| 正文色 | `#1D1D1A` | 主要依赖 Word 样式/默认黑 | 建议修 |
| 中文字体 | 微软雅黑 | renderer 样式设置微软雅黑 | 基本满足 |
| 英文字体 | Arial | renderer 样式设置 Arial,但 header/footer `_format_runs` 只显式设置 eastAsia | 部分 |
| 字号体系 | 14/12/11/10/9/8pt | Normal 11pt, H1 18pt, H2 15pt, H3 13pt, H4 12pt | 必须修 |
| 表格色 | 主题红/白/斑马纹/边框灰 | 表头浅灰 `F5F5F5`,无斑马纹 | 必须修 |

## 二、视觉质量

样例: `output/docx_audit/word_audit_sample.docx`。渲染图: `output/docx_audit/render/page-1.png`, `output/docx_audit/render/page-2.png`。

逐块检查:

| WordIR block | 状态 | 视觉观察 | 证据 |
| --- | --- | --- | --- |
| `heading` | 部分 | 能映射 Word 内置 Heading,导航语义应可用;但颜色/字号明显是旧 Word 蓝色体系,未对齐华为主题。 | `docx_renderer.py:138-139`, `page-1.png`, `page-2.png` |
| `paragraph normal` | 可接受 | 正文内容可读,中文显示正常;但字号偏大,不在当前 PPT 主题正文 9-10pt 口径。 | `docx_renderer.py:142-149`, `page-1.png` |
| `paragraph quote` | 部分 | 灰字、缩进、斜体存在;但任务书要求 quote 是“左竖线灰字”,当前没有左竖线。 | `docs/taskbook.md:217`, `docx_renderer.py:68-72` |
| `paragraph note` | 部分 | 浅灰底存在,对比度可读;但只是段落底纹,缺少清晰边框/内边距控制,视觉上不像稳定提示框组件。 | `docx_renderer.py:74-79`, `docx_renderer.py:145-156` |
| `bullet_list` | 可接受 | 两级列表缩进正常,无明显压字。 | `docx_renderer.py:159-165`, `page-1.png` |
| `numbered_list` | 部分 | 一级编号正常;二级编号在视觉上重新从 `1.` 开始,层级语义不够清楚,但未发现内容丢失。 | `page-1.png` |
| `table` | 部分 | 表格可编辑、列宽比例生效、表头重复 XML 存在;但表头是浅灰不是华为红,无白字,无斑马纹,整体未跟 PPT 的主题表格风格同步。 | `docx_renderer.py:168-225`, `test_docx_renderer.py:111-143`, `page-1.png` |
| `image_placeholder` | 未做/不符合 | 任务书要求“带边框占位文本框与题注”;当前只是普通 `[图片占位] ...` 段落,没有边框占位框,题注也合并进同一段。 | `docs/taskbook.md:220`, `docx_renderer.py:228-230`, `page-1.png` |
| `page_break` | 满足 | 强制分页有效,页眉页脚延续。 | `docx_renderer.py:51-52`, `test_docx_renderer.py:87-108`, `page-2.png` |

## 三、内容准确性

抽查链路: `output/docx_audit/parse/source.md` -> `parse.py` -> `DocumentIR` -> 包装为 `WordIR` -> `render.py --type word`。

结论: 这条抽查链路没有发现内容丢失或错位。

证据:

- `parse.py` 对 Markdown 产出的 block 顺序是 `['heading', 'paragraph', 'heading', 'bullet_list', 'numbered_list', 'table']`。
- `output/docx_audit/parse/word_from_parse.docx` 回读段落包含: `周报标题`, `本周完成解析链路验证。`, `风险清单`, `风险一`, `子风险一`, `风险二`, `第一步`, `第二步`。
- 回读表格为 `[['项目','状态','备注'], ['解析','通过','保留中文内容'], ['渲染','待看','检查表格位置']]`。
- 对应 parser 逻辑保留标题、段落、列表、表格: `backend/app/parsers/md_parser.py:32-84`。

边界说明: 本轮没有拿真实用户 Word 文件做内容鲁棒性验证;这里只能证明构造的 Markdown 抽查样例在当前链路下内容保持。

## 四、与 PPT 的能力落差

PPT table 已增强为决策矩阵能力: `DeckTableCell.emphasis`, `column_groups`, `row_groups`, `cell_spans`, `conclusion_col` 等字段存在于 `backend/app/ir/deck_ir.py:69-116`。WordIR table 仍是简单结构: `header`, `rows`, `caption`, `col_widths`, 没有合并单元格、分组表头、重点单元格、结论列: `backend/app/ir/common.py:50-55`。

判断:

- 不建议强行把 PPT DeckIR table 字段原样搬进 WordIR,因为这是 IR 契约变更,且 Word 文档的表格阅读场景与 PPT 决策矩阵不同。
- 建议做一轮受控 WordIR v1.1 表格增强,优先补:表头红底白字、斑马纹、重点单元格、合并单元格。分组表头和结论列可视真实 Word 样式需求再决定。
- 当前如果用户期待 Word 和 PPT 输出同一份“方案对比表/决策矩阵”风格,Word 端会明显落后。

## 五、错误码与校验覆盖

结论: WordIR 输入校验与错误码基本完整;DOCX 输出 lint 过浅。

满足项:

- E001-E006, W101-W104, I201 在样例测试中有覆盖: `backend/tests/test_word_samples.py:19-33`, `backend/tests/test_word_samples.py:50-74`。
- WordIR 字段约束:
  - heading level 1-4: `backend/app/ir/common.py:26-31`。
  - 列表 items 至少 1 条: `backend/app/ir/common.py:40-47`。
  - 表格 header 1-12 列、rows 最多 100 行、col_widths 正数: `backend/app/ir/common.py:50-74`。
  - WordIR blocks 必填且至少 1 条: `backend/app/ir/word_ir.py:45-49`。
  - 表格行列规整和 col_widths 列数校验: `backend/app/ir/word_ir.py:51-62`。
- 自动降级/诊断:
  - I201 默认密级: `backend/app/ir/validation.py:235-244`。
  - W102 空段落跳过: `backend/app/ir/validation.py:257-269`。
  - W101 标题跳级修正: `backend/app/ir/validation.py:270-284`。
  - W103 超长段落/单元格截断: `backend/app/ir/validation.py:296-323`。
  - Pydantic 错误映射到 E002-E006: `backend/app/ir/validation.py:326-344`。
  - 剥壳失败带原文前 200 字: `backend/app/ir/shell.py:49-60`。

缺口:

- `check_docx` 只检查 DOCX 可打开、非空、页脚密级: `backend/app/lint/docx_lint.py:45-89`。
- 同一个视觉上未同步主题的 DOCX 样例,`check_docx` 仍返回 `pass=True` 且无 warning。这是输出验收层的 false-green 风险。
- DOCX lint 没有检查字体白名单、主题色、字号、表格表头色/边框、图片占位框、quote 左竖线、页眉/页脚格式等。

## 问题清单

| 编号 | 严重度 | 问题 | 为什么重要 | 证据 | 建议方向 |
| --- | --- | --- | --- | --- | --- |
| DWA-001 | 必须修 | DOCX renderer 未同步 `hw_theme.json`,仍用旧 Word 蓝色标题和 18/15/13/12/11pt 体系。 | 用户已经校准华为主题; Word 输出现在和 PPT 输出视觉割裂,且不符合当前主题真值。 | `hw_theme.json:3-51`, `docx_renderer.py:23-30`, XML 抽查 `has C7000B: False`, `has 4F81BD: True`, `page-1.png` | renderer 加载 `hw_theme.json`,统一颜色/字体/字号 token;避免另设一套长期漂移的 `STYLES`。 |
| DWA-002 | 必须修 | `image_placeholder` 未按任务书渲染为带边框占位文本框与题注。 | 任务书明确要求 v1 输出带边框占位文本框;当前只是普通提示段落,视觉和语义都弱。 | `docs/taskbook.md:220`, `docx_renderer.py:228-230`, `page-1.png` | 用可编辑表格/文本框近似实现边框占位区,题注独立段落。 |
| DWA-003 | 必须修 | `quote` 样式没有左竖线。 | 任务书明确 quote 渲染为“左竖线灰字”;当前仅灰字/斜体/缩进。 | `docs/taskbook.md:217`, `docx_renderer.py:68-72`, `page-1.png` | 给 quote 段落加左边框或等价可编辑结构。 |
| DWA-004 | 必须修 | DOCX lint 过浅,主题不一致、表格样式错误、占位框缺失仍全绿。 | 会造成“DOCX 视觉不合格但 check 通过”的 false-green,与 PPT 侧合规检查成熟度差距明显。 | `docx_lint.py:45-89`; `check_docx` 对审计样例返回 `pass=True` 且无 items。 | 扩展 `check_docx`: 字体/字号/主题色、表格表头与边框、占位框、页眉页脚、quote/note 样式。 |
| DWA-005 | 建议修 | Word table 仍是简单表,未同步 PPT 决策矩阵增强能力。 | 对“方案对比表/决策矩阵”类内容,Word 输出会比 PPT 明显弱。 | WordIR table: `common.py:50-55`; DeckIR table: `deck_ir.py:69-116`。 | 单独评审 WordIR v1.1 table 增强;不要静默改 v1.0。 |
| DWA-006 | 建议修 | table 视觉未使用华为红表头/白字/斑马纹,且无单元格内边距/垂直对齐审计。 | 目前可读但不像当前 PPT 主题;复杂表格会显得旧。 | `docx_renderer.py:168-225`, `test_docx_renderer.py:111-143`, `page-1.png`。 | 与主题 token 对齐;表头红底白字、数据斑马纹、边框灰、合理 padding。 |
| DWA-007 | 可接受 | 解析 -> WordIR -> DOCX 抽查未见内容丢失。 | 说明基础内容链路可用;问题主要在视觉/合规而非内容搬运。 | `output/docx_audit/parse/document_ir.json`; 回读 `word_from_parse.docx` 段落和表格均保留。 | 后续仍需真实 DOCX 输入样本验证鲁棒性。 |
| DWA-008 | 可接受 | page_break、页眉页脚和页码字段基本可用。 | 满足 WordIR v1.0 基础交付能力。 | `docx_renderer.py:102-135`, `test_docx_renderer.py:59-108`, `page-2.png`。 | 后续可优化页脚格式与主题一致性。 |

## 结论

DOCX 没有完全“坏掉”: WordIR 校验、基础块渲染、分页、页眉页脚、表格回读、解析内容保留都能跑通。但它明显被 PPT 近期主题/版式增强甩开了: 主题未同步,视觉仍偏 Word 默认样式,`image_placeholder` 和 `quote` 未达到任务书描述,`check_docx` 不能发现这些问题。

本轮发现必须修问题 4 个: DWA-001、DWA-002、DWA-003、DWA-004。建议修 2 个: DWA-005、DWA-006。可接受 2 个: DWA-007、DWA-008。
