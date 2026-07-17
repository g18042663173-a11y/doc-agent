# 当前项目进度快照

生成时间：2026-07-17（Mac 当前工作区实测）

本文件以本次代码、工作区和命令输出为准。本次发现的 XLSX 硬截止空结果已改为结构化 `E001` 降级，并在修复后复跑两道自动验收门禁。

## 一、客观现状（硬数字）

| 项目 | 当前值 | 证据 |
| --- | --- | --- |
| 分支 | `codex-c0-contract` | 本次 `git status --short --branch` |
| 最新提交 | `5cc2950` `fix: restore readable PPT typography hierarchy` | 本次 `git log --oneline -5` |
| pytest | `380 passed in 104.72s`，失败 0。 | 修复后 `PYTHONPATH=backend python -m pytest backend/tests -q` |
| verify | **通过，退出码 0**：Schema、四格式 stub E2E、pytest + coverage 均通过。 | 修复后 `python scripts/verify.py`；`scripts/verify.py:33-59,247-301` |
| XLSX 硬截止 | 超 10MB XLSX 在 5 秒内完整摘要，或抛带 `E001/source.resource`、建议文本的明确降级；不再返回空 `sheets`。 | `backend/tests/test_xlsx_parser.py:257-309`；`backend/app/parsers/xlsx_parser.py:184-249` |
| 当前 verify 覆盖率 | parsers `93.75%` (840/896)，IR `93.84%` (1250/1332)，lint `94.34%` (934/990)，整体 `89.03%`；均高于门槛。 | 修复后 `python scripts/verify.py`；门槛 `scripts/verify.py:29-30,280-301` |
| IR 版本 | WordIR `1.0`、DocumentIR `1.1`、DeckIR `1.6`。 | `backend/schemas/word_ir.schema.json:360-371`；`backend/schemas/document_ir.schema.json:707-728`；`backend/app/ir/deck_ir.py:706-719` |
| 归档前工作集 | XLSX 截止修复、DeckIR 1.6 文档同步、失败文案版本同步、`CLEANUP.md` 与本快照将一并归档；架构图正交路由已在 `be7b7ab` 独立提交。 | `git log --oneline 3e6d936..HEAD`；本次 `git status --short --branch` |

## 二、三个 Step 各自到哪了

### Step 1：Word 输出

| 状态与验证程度 | 能力 | 证据 |
| --- | --- | --- |
| 已实现且有测试覆盖【Mac 上已验（stub/构造样例）】 | WordIR 校验、剥壳/修复、结构化 E/W/I/D；DOCX 标题、段落、两级列表、quote/note、分页、页眉页脚、表格和图片占位渲染/lint。 | `backend/app/ir/word_ir.py:45-71`；`backend/app/rendering/docx_renderer.py:26-281`；`backend/app/lint/docx_lint.py:48-190`；`backend/tests/test_docx_renderer.py`、`test_docx_lint.py` |
| 已实现且有测试覆盖【Mac 上已验（构造样例）】 | DOCX 品牌颜色、字体、字号、边框从主题读取；测试确认主题红与无 Word 默认蓝。 | `backend/app/rendering/themes/hw_theme.json:3-55`；`backend/tests/test_docx_renderer.py:149-204` |
| 部分实现【Mac 上已验（构造样例）】 | Word 表格仍是基础可编辑表格，未对齐 PPT 决策矩阵的分组表头、合并单元格和重点单元格。这是记录在案的 P2 规格，不影响 Step 1 基础闭环。 | `TASKBOOK_GAP_PLAN.md:132-136` |
| 未做【真实文件/真机未验】 | 真实 DOCX 解析保真、Windows Word/WPS 的字体、分页、表头重复、页码域和编辑体验。 | `HUMAN_REVIEW.md:194-253`；`QUESTIONS.md:5-13` |

### Step 2：输入解析与 Prompt 组装

| 状态与验证程度 | 能力 | 证据 |
| --- | --- | --- |
| 已实现且有测试覆盖【Mac 上已验（构造/synthetic 样例）】 | MD、DOCX、XLSX、PPTX 解析为 DocumentIR，均接入 CLI、prompt 与 stub E2E。 | `backend/app/parsers/`；`backend/tests/test_repro_cli.py:154-264`；`scripts/verify.py:62-135` |
| 已实现且有测试覆盖【Mac 上已验（synthetic 样例）】 | XLSX 覆盖合并、公式、隐藏行列跳过/warning、列统计采样、图/OLE 提示及资源隔离；DOCX/PPTX 对修订、批注、嵌套对象、组合形状和 SmartArt 给出降级 warning。 | `backend/tests/test_xlsx_parser.py:21-445`；`test_docx_parser.py:18-203`；`test_pptx_parser.py:20-128`；`REAL_PARSE_REPORT.md:25-96` |
| 已实现且有测试覆盖【Mac 上已验（构造大表/coverage）】 | 超 10MB XLSX 在 5 秒硬截止内返回完整摘要；若运行环境不足以完成，则抛带 `E001/source.resource` 的明确资源降级，调用方不会拿到空结果。 | `backend/app/parsers/xlsx_parser.py:184-249`；`backend/tests/test_xlsx_parser.py:257-309`；修复后 `verify.py` 通过 |
| 已实现且有测试覆盖【Mac 上已验（stub/构造样例）】 | Prompt 四段式、优先级截断、few-shot、脏 JSON 剥壳和修复回路；相同输入的 parse/prompt 可复现。 | `backend/app/prompting/builder.py`；`backend/app/ir/shell.py`；`backend/app/ir/repair.py`；`backend/tests/test_prompt_builder.py` |
| 未做【真实文件未验】 | `samples/input/real/` 实际为 0 文件，尚无 docx/xlsx/pptx 各至少 3 个真实脱敏样例；synthetic 不能替代真实业务文件验收。 | 本次 `find samples/input/real -type f` 为 0；`REAL_PARSE_REPORT.md:78-96`；`QUESTIONS.md:5-7` |

### Step 3：华为 PPTX 工具

| 状态与验证程度 | 能力 | 证据 |
| --- | --- | --- |
| 已实现且有测试覆盖【Mac 上已验（构造样例）】 | DeckIR 1.6 的 13 个 layout：基础 10 种，加 `architecture_diagram`、`process_flow`、`timeline`；1.4/1.5 可内存迁移至 1.6。 | `backend/app/ir/deck_ir.py:452-583,706-724`；`backend/app/ir/validation.py:78-80,597-615`；`backend/tests/test_ir_validation.py` |
| 已实现且有测试覆盖【Mac 上已验（构造样例/产物回读）】 | 决策矩阵、原生 chart/横向数据条、KPI cards、流程/时间线、可编辑架构骨架和正交边、image 16:9 占位槽均可生成；PPTX lint 覆盖主题、页脚、字体、颜色、字号、W06/W07/W08/W09 等。 | `backend/app/rendering/pptx_renderer.py:42-83`；`backend/app/lint/pptx_lint.py`；`backend/tests/test_pptx_renderer.py`、`test_pptx_lint.py` |
| 已实现且有测试覆盖【Mac 上已验（构造样例）】 | 选版规则不再凑页：编号步骤才选流程，明确时间标记才选时间线，无结构证据走普通内容版式。 | `backend/app/generation/layout_policy.py:10-111`；`backend/app/generators/stub.py:200-263`；`backend/tests/test_generation_depth.py:294-363` |
| 已实现且有测试覆盖【Mac 上已验（构造样例）】 | 普通 PPT 字号已与紧凑组件 token 分离：封面 `40/20/12pt`，页标题 `28pt`，正文自适应 `16 -> 14 -> 12 -> 10.5pt`，表格/图表保持紧凑字号。 | `backend/app/rendering/themes/hw_theme.json:38-82`；`backend/app/rendering/typography.py:18-131`；`backend/tests/test_ppt_typography.py:18-56`；提交 `5cc2950` |
| 部分实现【Mac 上已验（构造样例）】 | `image` 仅提供可编辑占位/题注，不传图片二进制；架构图定位为“可编辑骨架 + 人工调布局”；精确 Gantt 不用 timeline 冒充。 | `TASKBOOK_GAP_PLAN.md:114-126`；`backend/app/rendering/pptx_renderer.py` |
| 未做【真机/真字体未验】 | Windows PowerPoint 下的微软雅黑/HarmonyOS 字体、官方 CI/Logo、投影/打印效果，以及内容语义和视觉终审。 | `HUMAN_REVIEW.md:198-249`；`QUESTIONS.md:11-17` |

## 三、这一阶段新增的能力（相对最初三个 Step）

| 能力 | 当前状态与验证程度 | 证据 |
| --- | --- | --- |
| 页数/深度分析 | 已实现 `analyze` 的量化分析和概览/标准/详细三档页数建议；生成支持大纲和分段。 【Mac 上已验（stub/单测）】 | `backend/app/generation/analysis.py:13-169`；`backend/app/generation/depth.py:22-140`；`backend/app/cli/analyze.py` |
| 产 IR 抗弱模型机制 | Prompt 含 JSON 纪律、字段/版式约束与分段，剥壳、校验和修复回路确保模型文本不直连渲染器。 【Mac 上已验（stub/单测）】 | `backend/app/prompting/builder.py`；`backend/app/ir/shell.py`；`backend/app/ir/repair.py` |
| 渲染健壮性 | 表格相对列宽、0 起索引防呆、缩字到下限后的明确 HW-W03、架构正交路由/避让/密度 warning 已实现。 【Mac 上已验（产物回读/单测）】 | `backend/app/ir/deck_ir.py`；`backend/app/ir/validation.py`；`backend/app/rendering/pptx_renderer.py`；`backend/app/lint/pptx_lint.py` |
| 版式吸收 | 已最小落地流程、时间线、横向数据条、KPI 与截图占位槽规范。精确 Gantt 和真实图片透传未做。 【Mac 上已验（构造样例）】 | 提交 `74dfe94`；`docs/华为版式参考映射.md`；`backend/tests/test_pptx_renderer.py` |
| 字段语义补全 | table、chart、architecture 的索引、单位、尺寸、手工覆盖等描述和约束已补齐。 【Mac 上已验（schema/单测）】 | `backend/app/ir/deck_ir.py:250-365,440-583`；`backend/tests/test_ir_validation.py` |

## 四、还欠什么（诚实清单）

### 【Mac 上还能做的】

1. **重渲并复核当前 13 版式的 Mac 预览。** 重点检查 process_flow、timeline、横向 chart、KPI、密集架构边和 image 槽；结论必须标为 Mac 预览，不能替代真机验收。证据：提交 `5cc2950`、`74dfe94`。
2. **若业务要求所有 10MB 文件都完整摘要，再单独优化 XLSX worker。** 当前行为已保证完整摘要或明确 E001，不再存在静默空结果；完整率优化不应与正确性降级混淆。证据：`backend/app/parsers/xlsx_parser.py:184-249`。

### 【必须内网/真机/真字体才能做的】

1. **真实 NGA 接入。** `NgaGenerator` 只校验 `NGA_BASE_URL`/`NGA_TOKEN` 后抛 `NotImplementedError`，内网协议未实现。证据：`backend/app/generators/nga.py:7-18`。
2. **真实脱敏文件解析。** 缺 docx/xlsx/pptx 各至少 3 个真实文件，不能以 synthetic 声称通过。证据：`QUESTIONS.md:5-7`；`REAL_PARSE_REPORT.md:78-96`。
3. **断网 Windows + Python 3.12 验收。** 需 wheelhouse 安装、`verify.ps1` 实跑和截图记录。证据：`scripts/make_wheelhouse.py`；`verify.ps1`；`QUESTIONS.md:8-10`。
4. **真实 HarmonyOS/微软雅黑字体、官方 CI 下的 DOCX/PPTX 视觉与语义终审。** lint/Mac 预览只能证明结构和自动规则，不能证明正式交付观感。证据：`HUMAN_REVIEW.md:198-249`；`QUESTIONS.md:11-17`。

## 五、下一步建议

1. **现在就做：重渲并复核最新版 13 版式和字号样例，明确记录为 Mac 视觉预检。**
2. **按业务优先级决定是否继续优化 10MB XLSX 的完整摘要率；当前明确 E001 降级已保证下游可判断。**
3. **等待外部条件：收集真实语料、接入 NGA，并在 Windows/目标字体/官方 CI 环境完成离线、视觉和语义签收。**

## 结论

三份 IR、四格式解析、Word 输出、DeckIR 1.6、PPTX 渲染/lint、stub E2E、深度分析和字号自适应均有 Mac 构造样例与测试证据；历史 P0 34/34、P1 18/18 已关闭，P2 7 项已有正式降级交代。本次 `380 passed` 与 `verify.py` 全绿；但真实 NGA、真实文件、Windows 离线、目标字体/CI 和人工视觉语义终审仍未完成，不能称为全环境交付完成。
