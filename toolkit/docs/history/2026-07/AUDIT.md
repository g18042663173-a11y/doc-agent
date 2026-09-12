# 严格自我审计

审计日期: 2026-07-09
审计原则: 先找仓库证据,再下结论。本文只依据当前仓库代码、测试、样例、文档与本次实跑结果,不沿用历史口头结论。

## 本次实跑核验

| 命令 | 结果 |
| --- | --- |
| 补完前 `PYTHONPATH=backend python3 -m pytest backend/tests -q` | 63 passed |
| 补完前 `PYTHONPATH=backend python3 -m pytest backend/tests -q --cov=app --cov-report=term-missing` | 63 passed; terminal total coverage 86% |
| 补完前 `python3 scripts/verify.py` | 通过; `app/parsers=92.37%`, `app/ir=88.15%`, `app/lint=88.76%`, `overall=85.88%` |
| 当前 `PYTHONPATH=backend python3 -m pytest backend/tests -q` | 114 passed |
| 当前 `PYTHONPATH=backend python3 -m pytest backend/tests -q --cov=app --cov-report=term-missing` | 114 passed; terminal total coverage 86% |
| 当前 `python3 scripts/verify.py` | 通过; `app/parsers=93.80%`, `app/ir=92.55%`, `app/lint=89.18%`, `overall=86.40%` |
| 补完后 `render.py --type deck` | 已由 `backend/tests/test_render_cli.py:60-140` 覆盖,成功产出 PPTX;非法 DeckIR 返回 D003 |
| synthetic 脏样例生成与逐个 `parse.py` | 10 个文件全部成功产出 DocumentIR,0 崩溃;10/10 通过 `DocumentIR.model_validate_json`;见 `REAL_PARSE_REPORT.md:25-65` |
| 真实语料盘点 `find samples/input/real -maxdepth 3 -type f 2>/dev/null \| sort` | 仍为 0 个文件;synthetic 不替代真实脱敏语料,见 `REAL_PARSE_REPORT.md:75-93` |
| schema diff | `git diff -- backend/schemas/*.schema.json` 无输出 |

## 核对表

| 要求条目 | 出处(§) | 状态 | 证据(文件:行号) | 备注 |
| --- | --- | --- | --- | --- |
| 目录职责分层: `cli/ir/parsers/prompting/generators/rendering/lint/tests/samples/docs/scripts` | `docs/taskbook.md:93-113` | 满足 | `backend/app/cli/parse.py:1`, `backend/app/ir/word_ir.py:45`, `backend/app/parsers/md_parser.py:16`, `backend/app/prompting/builder.py:29`, `backend/app/generators/stub.py:7`, `backend/app/generators/nga.py:7`, `backend/app/storage/__init__.py:1`, `docs/使用说明.md:1`, `docs/验收手册.md:1`, `verify.ps1:1` | 已补 `storage/`、`NgaGenerator`、Windows 薄封装和独立使用/验收文档。 |
| 跨平台卫生: pathlib、显式 UTF-8、平台差异薄封装、Windows wheelhouse | `docs/taskbook.md:115-128` | 满足(代码/脚本) | `backend/app/cli/parse.py:5`, `backend/app/cli/parse.py:41`, `scripts/make_wheelhouse.py:24-39`, `scripts/verify.py:53-100`, `verify.ps1:1-13` | Mac 侧脚本与 Windows 薄封装已齐;Windows 离线真机执行结果仍列入人工验证边界。 |
| `parse.py <file>` 支持 md/docx/xlsx/pptx 输出 DocumentIR | `docs/taskbook.md:157` | 满足 | `backend/app/cli/parse.py:20-30`, `backend/tests/test_parser_sample_counts.py:23-32` | 统一入口覆盖四格式;样例每格式 5 个可解析。 |
| `prompt.py --kind word\|deck` 输出确定性 Prompt | `docs/taskbook.md:158` | 满足 | `backend/app/cli/prompt.py:11-17`, `backend/app/prompting/builder.py:29-40`, `backend/tests/test_prompt_builder.py:12-25` | 同一输入逐字节一致有测试。 |
| `render.py --type word\|deck` 应支持 Word 和 Deck 渲染并先校验 | `docs/taskbook.md:159`, `docs/taskbook.md:175` | 满足 | `backend/app/cli/render.py:24-47`, `backend/tests/test_render_cli.py:60-140` | Deck CLI 已走 DeckIR 校验 -> PPTX 渲染 -> lint;非法 deck 返回 D003。 |
| `check.py <pptx\|docx>` 应支持复检 | `docs/taskbook.md:160` | 满足 | `backend/app/cli/check.py:18-32`, `backend/app/lint/docx_lint.py:45-113`, `backend/tests/test_pptx_lint.py:331-369`, `backend/tests/test_docx_lint.py:14-49` | PPTX/DOCX 均输出 `report.json` 与 `report.md`;错误退出码由 report.summary.pass 决定。 |
| `verify.py` 串联样例链路 + pytest + coverage | `docs/taskbook.md:161`, `docs/taskbook.md:475-481` | 满足 | `scripts/verify.py:27-100`, `backend/tests/test_c0_contract.py:140-155`;实跑 `python3 scripts/verify.py` 通过 | 串联 C0 产物、四格式 word/deck stub e2e、pytest 与 coverage;三包覆盖率门禁生效。 |
| Windows `verify.ps1` 与 `verify.py` 等价 | `docs/taskbook.md:481`, `docs/taskbook.md:492`, `docs/taskbook.md:502` | 满足(脚本) | `verify.ps1:1-13`, `docs/验收手册.md:20-33`, `backend/tests/test_docs.py:20-31` | 已提供 Windows 薄封装;断网真机运行记录仍需人工执行。 |
| 所有 IR 顶层 `ir_type` / `ir_version` | `docs/taskbook.md:204` | 满足 | `backend/app/ir/word_ir.py:45-49`, `backend/app/ir/document_ir.py:66-72`, `backend/app/ir/deck_ir.py:157-161`, `backend/tests/test_c0_contract.py:20-95` | 三份模型均强约束。 |
| 未知字段忽略并记 Warning | `docs/taskbook.md:204` | 满足 | `backend/app/ir/common.py:8-9`, `backend/app/ir/validation.py:87-153`, `backend/tests/test_ir_validation.py:60-78`, `backend/tests/test_ir_validation.py:265-303` | 统一 `validate_*_ir` 入口对 Word/Deck/Document 均落 W104;直接 pydantic 模型仍只负责 schema 层。 |
| 单段落 2000 字上限 | `docs/taskbook.md:205` | 满足 | `backend/app/ir/validation.py:36`, `backend/app/ir/validation.py:154-184`, `backend/tests/test_ir_validation.py:143-162` | 在统一校验入口截断并返回 W103,不改 IR schema。 |
| WordIR 表格 100 行 x 12 列,行列规整 | `docs/taskbook.md:205`, `docs/taskbook.md:219`, `docs/taskbook.md:251` | 满足 | `backend/app/ir/common.py:50-55`, `backend/app/ir/word_ir.py:51-62`, `backend/tests/test_ir_validation.py:38-58`, `backend/tests/test_docx_renderer.py:146-169` | 上限与规整均有代码/测试。 |
| DeckIR 单页表格 12 行 x 8 列,行列规整 | `docs/taskbook.md:205`, `docs/taskbook.md:293`, `docs/taskbook.md:320` | 满足 | `backend/app/ir/deck_ir.py:68-77`, `backend/app/ir/validation.py:191-198`, `backend/tests/test_ir_validation.py:221-239` | D005 对不规整表格有触发测试;模型约束覆盖尺寸上限。 |
| 单页要点 7 条、单条 60 字 | `docs/taskbook.md:205`, `docs/taskbook.md:291` | 满足 | `backend/app/ir/deck_ir.py:45-49`, `backend/app/lint/pptx_lint.py:151-162`, `backend/tests/test_ir_validation.py:242-263`, `backend/tests/test_pptx_lint.py:198-227` | DeckIR 限制条数;输出侧 HW-W03 覆盖单条过长/条数过多。 |
| 剥壳: json fence / 首个平衡对象 / 失败 E001+D001 附前 200 字 | `docs/taskbook.md:206` | 满足 | `backend/app/ir/shell.py:15-30`, `backend/app/ir/shell.py:63-98`, `backend/tests/test_ir_shell_and_repair.py:22-60` | Word E001 与 Deck D001 均有触发测试。 |
| 三份 JSON Schema 入库并快照保护 | `docs/taskbook.md:207-208`, `docs/taskbook.md:471` | 满足 | `backend/app/ir/schema_export.py:14-35`, `backend/tests/test_c0_contract.py:97-112`, `backend/schemas/word_ir.schema.json`, `backend/schemas/document_ir.schema.json`, `backend/schemas/deck_ir.schema.json` | 本次 schema diff 为空;快照测试存在。 |
| WordIR meta 字段与 `blocks` 七类 block | `docs/taskbook.md:212-221` | 满足 | `backend/app/ir/word_ir.py:20-49`, `backend/app/ir/common.py:26-84`, `backend/tests/test_c0_contract.py:20-52` | `blocks` 必填且 min 1。 |
| E001: 剥壳/JSON 解析失败 | `docs/taskbook.md:248` | 满足 | `backend/app/ir/validation.py:60-84`, `backend/app/ir/shell.py:74-80`, `backend/tests/test_ir_shell_and_repair.py:44-50` | 有触发测试。 |
| E002: 缺 `meta.title` | `docs/taskbook.md:249` | 满足 | `backend/app/ir/validation.py:161-174`, `backend/tests/test_ir_validation.py:12-18`, `samples/ir/word_invalid_e002_missing_title.json` | 有触发测试和样例。 |
| E003: 未知 `block.type` | `docs/taskbook.md:250` | 满足 | `backend/app/ir/validation.py:163-164`, `backend/tests/test_word_samples.py:19-52`, `samples/ir/word_invalid_e003_unknown_block.json` | 样例回归覆盖。 |
| E004: 表格不规整或超限 | `docs/taskbook.md:251` | 满足 | `backend/app/ir/validation.py:165-179`, `backend/tests/test_ir_validation.py:38-58`, `samples/ir/word_invalid_e004_ragged_table.json` | 规整触发覆盖;100x12 极限渲染覆盖。 |
| E005: heading.level 不在 1-4 | `docs/taskbook.md:252` | 满足 | `backend/app/ir/common.py:26-31`, `backend/app/ir/validation.py:167-168`, `backend/tests/test_word_samples.py:19-52`, `samples/ir/word_invalid_e005_heading_level.json` | 样例回归覆盖。 |
| E006: 列表 items 为空 | `docs/taskbook.md:253` | 满足 | `backend/app/ir/common.py:40-47`, `backend/app/ir/validation.py:169-170`, `backend/tests/test_ir_validation.py:21-35`, `samples/ir/word_invalid_e006_empty_list.json` | 同时被用于空 `blocks`,这是任务书未定义的新映射。 |
| W101: 标题层级跳级 warning | `docs/taskbook.md:254` | 满足 | `backend/app/ir/validation.py:120-143`, `backend/app/ir/report.py:19-22`, `backend/tests/test_ir_validation.py:81-115` | 跳级标题会降级并返回 W101;顺序标题反例不触发。 |
| W102: 空段落自动跳过 warning | `docs/taskbook.md:255` | 满足 | `backend/app/ir/validation.py:144-153`, `backend/app/ir/report.py:20`, `backend/tests/test_ir_validation.py:118-141` | 校验层跳过空段落并返回 W102。 |
| W103: 单元格/段落超长截断 warning | `docs/taskbook.md:256`, `docs/taskbook.md:331`, `docs/taskbook.md:391` | 满足 | `backend/app/ir/validation.py:154-184`, `backend/app/ir/report.py:21`, `backend/tests/test_ir_validation.py:143-162` | 段落和表格单元格均截断到 2000 字并返回 W103。 |
| W104: 未知字段忽略 warning | `docs/taskbook.md:204`(用户确认扩展) | 满足 | `backend/app/ir/validation.py:87-153`, `backend/tests/test_ir_validation.py:60-78`, `backend/tests/test_ir_validation.py:265-303` | Word/Deck/Document 统一校验入口均覆盖。 |
| I201: 未提供 classification 使用默认密级 Info | `docs/taskbook.md:257` | 满足 | `backend/app/ir/validation.py:101-115`, `backend/app/ir/report.py:24`, `backend/tests/test_ir_validation.py:165-199` | 未提供 classification 时返回 I201;显式提供时反例不触发。 |
| Word 渲染样式集中、页眉页脚、可编辑 DOCX | `docs/taskbook.md:259` | 满足(自动可验证) | `backend/app/rendering/docx_renderer.py:23-30`, `backend/app/rendering/docx_renderer.py:33-56`, `backend/app/rendering/docx_renderer.py:102-135`, `backend/tests/test_docx_renderer.py:16-169` | 自动回读覆盖结构、页眉页脚、PAGE 字段和表格;Word 桌面端视觉/编辑手感另列人工边界。 |
| DocumentIR source/stats/warnings/content 结构 | `docs/taskbook.md:261-269` | 满足 | `backend/app/ir/document_ir.py:11-72`, `backend/tests/test_c0_contract.py:55-75` | 结构模型存在。 |
| DocumentIR 降级清单: Word 修订/批注/文本框/SmartArt warning | `docs/taskbook.md:271-280` | 满足(构造样例) | `backend/app/parsers/docx_parser.py:157-181`, `backend/tests/test_docx_parser.py:102-123`, `backend/tests/test_dirty_samples.py:51-64` | 修订/批注/格式修改触发 warning;普通 DOCX 不再误报 revisions。真实复杂 Word 仍需人工语料验证。 |
| DocumentIR 降级清单: Excel 公式/透视表/图表/VBA | `docs/taskbook.md:276` | 满足 | `backend/app/parsers/xlsx_parser.py:19-75`, `backend/app/parsers/xlsx_parser.py:157-163`, `backend/app/parsers/xlsx_parser.py:208-221`, `backend/tests/test_xlsx_parser.py:14-82`, `backend/tests/test_dirty_samples.py:39-49` | 公式计数、图表、透视表、VBA warning 均有测试;synthetic 覆盖跨 sheet 引用和公式报表。 |
| DocumentIR 降级清单: Excel 合并单元格 | `docs/taskbook.md:277` | 满足 | `backend/app/parsers/xlsx_parser.py:35-49`, `backend/app/parsers/xlsx_parser.py:103-111`, `backend/app/parsers/xlsx_parser.py:166-205`, `backend/tests/test_dirty_samples.py:33-37` | 已按 §5.4 计数并把预览范围内合并格填为左上格值。 |
| DocumentIR 降级清单: PPT 动画/切换/组合形状/SmartArt | `docs/taskbook.md:278`, `docs/taskbook.md:388` | 满足 | `backend/app/parsers/pptx_parser.py:112-142`, `backend/tests/test_pptx_parser.py:46-82`, `backend/tests/test_dirty_samples.py:66-74`, `scripts/make_dirty_samples.py:274-310` | 动画/切换 warning 有测试;组合形状递归抽取有 synthetic 真文件覆盖;SmartArt XML 进入 warning。 |
| PPT 图表只取标题与类型、不反解数据 | `docs/taskbook.md:279` | 满足 | `backend/app/parsers/pptx_parser.py:80-83`, `backend/app/parsers/pptx_parser.py:103-110`, `backend/tests/test_pptx_parser.py:81-99` | chart 标题与类型均进入 bodies;不反解图表数据。 |
| 嵌入图片记录存在与尺寸 | `docs/taskbook.md:280` | 满足 | `backend/app/parsers/docx_parser.py:164-168`, `backend/app/parsers/pptx_parser.py:119-123`, `backend/tests/test_docx_parser.py:82-99`, `backend/tests/test_pptx_parser.py:61-78` | DOCX/PPTX 均记录图片存在与尺寸 warning;不搬运二进制。 |
| DeckIR 10 种 layout 字段 | `docs/taskbook.md:284-297` | 满足 | `backend/app/ir/deck_ir.py:21-154`, `backend/tests/test_c0_contract.py:78-95`, `backend/tests/test_pptx_renderer.py:73-118` | 模型覆盖 10 种 layout。 |
| DeckIR 页数范围 1-30、演示目标 5-12 页 | `docs/taskbook.md:320` | 满足(模型/演示) | `backend/app/ir/deck_ir.py:157-161`, `backend/app/generators/stub.py:26-47`, `backend/tests/test_repro_cli.py:100-126` | 模型 1-30;stub demo 5-12 测试覆盖。 |
| D001: Deck JSON 不合法 | `docs/taskbook.md:320` | 满足 | `backend/app/ir/shell.py:92-98`, `backend/tests/test_ir_shell_and_repair.py:53-59` | 有触发测试。 |
| D002: Deck 缺 meta.title | `docs/taskbook.md:320` | 满足 | `backend/app/ir/validation.py:187-188`, `backend/tests/test_ir_validation.py:201-209` | 有触发测试。 |
| D003: 未知 layout | `docs/taskbook.md:320` | 满足 | `backend/app/ir/validation.py:189-190`, `backend/tests/test_ir_validation.py:81-94` | 有触发测试。 |
| D004: layout 缺必填字段 | `docs/taskbook.md:320` | 满足 | `backend/app/ir/validation.py:195-198`, `backend/tests/test_ir_validation.py:212-219` | 有触发测试。 |
| D005: Deck 表格超限/不规整 | `docs/taskbook.md:320` | 满足 | `backend/app/ir/deck_ir.py:68-77`, `backend/app/ir/validation.py:191-192`, `backend/tests/test_ir_validation.py:221-239` | 有触发测试。 |
| D006: bullets 超条数 | `docs/taskbook.md:320` | 满足 | `backend/app/ir/deck_ir.py:45-49`, `backend/app/ir/validation.py:193-194`, `backend/tests/test_ir_validation.py:242-263` | 有触发测试。 |
| S1-1: WordIR 定稿、校验器、Schema,10 个非法样例逐一命中 | `docs/taskbook.md:328` | 满足 | `backend/app/ir/word_ir.py:45-62`, `backend/tests/test_c0_contract.py:97-112`, `backend/tests/test_word_samples.py:19-78`, `samples/ir/word_invalid_e001_bad_json.json:1` | Schema 快照与 11 个 Word 诊断样例覆盖 E/W/I。 |
| S1-2: 三形态剥壳、修复回路、不可修复稳定报错 | `docs/taskbook.md:329` | 满足 | `backend/app/ir/shell.py:18-30`, `backend/app/ir/repair.py:19-52`, `backend/tests/test_ir_shell_and_repair.py:22-115` | WordIR 路径测试充分;Deck 修复路径未单独测。 |
| S1-3: DOCX 标题/段落/两级列表/quote/note/分页/页眉页脚 | `docs/taskbook.md:330` | 满足(自动结构) | `backend/app/rendering/docx_renderer.py:34-57`, `backend/app/rendering/docx_renderer.py:139-167`, `backend/tests/test_docx_renderer.py:16-108` | 自动回读满足;人工可编辑性仍需 Word 打开确认。 |
| S1-4: 表格表头、列宽、跨页表头、超限截断+W103 | `docs/taskbook.md:331` | 满足 | `backend/app/rendering/docx_renderer.py:169-226`, `backend/app/ir/validation.py:154-184`, `backend/tests/test_docx_renderer.py:111-169`, `backend/tests/test_ir_validation.py:143-162` | 表格渲染与 100x12 通过;超长段落/单元格由校验入口截断并返回 W103。 |
| S1-5: 3 正样例 + 5 失败样例配文案 | `docs/taskbook.md:332` | 满足(自动可验证) | `backend/tests/test_word_samples.py:13-52`, `samples/ir/word_valid_01_plain.json`, `samples/ir/word_invalid_e002_missing_title.json` | 文案有格式化器;“文案评审通过”另列人工边界。 |
| S1-6: golden 回读、README Word 输出、pytest 全绿 | `docs/taskbook.md:333` | 满足(自动可验证) | `backend/tests/test_docx_renderer.py:16-169`, `README.md:1-45`, `docs/使用说明.md:1-55`, 本次实跑见上 | 新人 10 分钟复现仍属于人工抽查。 |
| S2-1: Markdown 解析并往返 DOCX 不丢结构 | `docs/taskbook.md:346` | 满足 | `backend/app/parsers/md_parser.py:16-95`, `backend/tests/test_md_parser.py:14-56` | 有往返测试。 |
| S2-2: DOCX 标题双策略、列表、表格截断、warnings | `docs/taskbook.md:347` | 满足(构造样例) | `backend/app/parsers/docx_parser.py:19-22`, `backend/app/parsers/docx_parser.py:103-121`, `backend/tests/test_docx_parser.py:14-99` | 样式名 + outlineLevel 双策略、表格截断、图片尺寸 warning 均有测试;真实复杂 Word 仍需人工样例验证。 |
| S2-3: XLSX 摘要字段齐全、10MB <5 秒 | `docs/taskbook.md:348` | 满足(构造样例) | `backend/app/parsers/xlsx_parser.py:19-75`, `backend/app/parsers/xlsx_parser.py:91-136`, `backend/tests/test_xlsx_parser.py:14-104`, `backend/tests/test_dirty_samples.py:33-49`, `REAL_PARSE_REPORT.md:35-64` | 摘要字段、降级 warning、10MB 包体性能、5 万行 synthetic 截断均有证据。 |
| S2-4: PPT 每页标题/文本/表格/备注、组合递归、8 页样例 | `docs/taskbook.md:349` | 满足(构造样例) | `backend/app/parsers/pptx_parser.py:11-51`, `backend/app/parsers/pptx_parser.py:67-142`, `backend/tests/test_pptx_parser.py:17-101`, `backend/tests/test_dirty_samples.py:66-74` | 基本字段、transition warning、图片尺寸、组合递归与 SmartArt warning 均有测试;真实 8 页业务样例仍需人工语料。 |
| S2-5: 四段式 Prompt、按优先级截断、确定性 | `docs/taskbook.md:350`, `docs/taskbook.md:353-365` | 满足 | `backend/app/prompting/templates/ir_generation.txt:1-9`, `backend/app/prompting/builder.py:29-170`, `backend/tests/test_prompt_builder.py:12-80` | 截断保持合法 JSON,按表格尾行/预览尾行/次要段落优先级丢弃。 |
| S2-6: demo_e2e 打通四格式、每格式至少 5 例、文件到 DOCX | `docs/taskbook.md:351` | 满足 | `scripts/demo_e2e.py:38-59`, `backend/tests/test_parser_sample_counts.py:23-32`, `backend/tests/test_repro_cli.py:139-164` | 四格式各 5 个可解析;四格式 word/deck stub e2e 均跑 parse->prompt->render->check。 |
| S3-1: 风格 tokens 与规范,渲染器取值零硬编码 | `docs/taskbook.md:400` | 满足 | `backend/app/rendering/themes/hw_theme.json:59-242`, `docs/风格规范.md:1-18`, `backend/app/rendering/pptx_renderer.py:64-336`, `backend/tests/test_pptx_renderer.py:101-153` | 10 类版式坐标/尺寸集中在 `layouts`;测试证明改 theme 会改变标题坐标,并禁止 renderer 出现裸数值 `Inches/Pt`。 |
| S3-2: P0 五版式,页脚三段式,五版式 lint 零 Error | `docs/taskbook.md:401` | 满足 | `backend/app/rendering/pptx_renderer.py:35-44`, `backend/app/rendering/pptx_renderer.py:226-229`, `backend/tests/test_pptx_renderer.py:14-76` | 五版式可渲染并有 lint 零 Error 专门测试。 |
| S3-3: P1 三版式 + chart/image 降级,十版式样例可渲染 | `docs/taskbook.md:402` | 满足 | `backend/app/rendering/pptx_renderer.py:45-54`, `backend/app/rendering/pptx_renderer.py:175-206`, `backend/tests/test_pptx_renderer.py:99-144`, `samples/ir/deck_valid_full.json:1` | P1 与降级有测试;十版式样例入库并渲染/lint。 |
| S3-4: 6.3 规则表全部落码,每条规则正反例各至少 1 | `docs/taskbook.md:403`, `docs/taskbook.md:437-449` | 满足 | `backend/app/lint/pptx_lint.py:53-88`, `backend/app/lint/pptx_lint.py:151-260`, `backend/app/lint/pptx_lint.py:322-406`, `backend/tests/test_pptx_lint.py:39-329` | HW-E01~03、HW-W01~09、HW-I01 均有正反测试。 |
| S3-5: md 经 stub 到 DeckIR/PPTX/lint 一条命令,5-12 页 | `docs/taskbook.md:404` | 满足 | `scripts/demo_e2e.py:38-58`, `backend/app/generators/stub.py:21-47`, `backend/tests/test_repro_cli.py:100-126` | 自动测试覆盖。 |
| S3-6: 黄区接入说明两个替换点、环境变量、自测、离线安装 | `docs/taskbook.md:405`, `docs/taskbook.md:459-464` | 满足(外网侧) | `docs/内网接入.md:1-65`, `backend/app/generators/nga.py:7-18`, `backend/tests/test_docs.py:8-17`, `backend/tests/test_c0_contract.py:130-137` | NgaGenerator 只预留接口与环境变量;真实协议和内网可执行性需人工。 |
| §6.1 主色/文字/背景/字体/字号 tokens | `docs/taskbook.md:407-422` | 满足 | `backend/app/rendering/themes/hw_theme.json:3-35`, `backend/tests/test_theme.py:12-23` | token 文件存在。 |
| §6.1 版心 16:9、四边距、标题区、页脚坐标 | `docs/taskbook.md:416-418` | 满足 | `backend/app/rendering/themes/hw_theme.json:37-78`, `backend/app/rendering/pptx_renderer.py:27-31`, `backend/app/rendering/pptx_renderer.py:289-323`, `backend/tests/test_pptx_renderer.py:80-153` | 版心、标题框、页脚坐标均来自 theme;标题框高度与 token/layout 为 1.0。 |
| §6.1 12 栏网格 + 8pt 基线 | `docs/taskbook.md:417` | 满足(检测) | `backend/app/lint/pptx_lint.py:165-192`, `backend/tests/test_pptx_lint.py:39-66` | lint 有正反例。 |
| §6.1 元素间距/页边距 | `docs/taskbook.md:419`, `docs/taskbook.md:446` | 满足 | `backend/app/lint/pptx_lint.py:195-227`, `backend/app/lint/pptx_lint.py:381-406`, `backend/tests/test_pptx_lint.py:230-260` | HW-W07 同时检查页边、越界、两两包围盒重叠/间距。 |
| §6.1 对比度 4.5:1 | `docs/taskbook.md:420`, `docs/taskbook.md:448` | 满足 | `backend/app/lint/pptx_lint.py:237-260`, `backend/app/lint/pptx_lint.py:341-355`, `backend/tests/test_pptx_lint.py:104-131` | 正反例覆盖。 |
| §6.1 页脚三段式 | `docs/taskbook.md:421` | 满足 | `backend/app/rendering/pptx_renderer.py:226-229`, `backend/tests/test_pptx_renderer.py:14-50` | 左密级、右页码;中间留空。 |
| §6.1 禁用动画/切换/白名单外字体/真实 logo 等 | `docs/taskbook.md:422` | 满足(自动可验证) | `backend/app/lint/pptx_lint.py:76-86`, `backend/app/lint/pptx_lint.py:118-138`, `backend/tests/test_pptx_lint.py:134-171`, `backend/tests/test_pptx_renderer.py:139-153` | §6.3 明确定码的动画/切换/字体已检查;renderer 防回退测试禁止真实图片、阴影、渐变。官方 logo 视觉识别仍属于人工终审边界。 |
| HW-E01: 页脚缺密级 | `docs/taskbook.md:437` | 满足 | `backend/app/lint/pptx_lint.py:70-74`, `backend/app/lint/pptx_lint.py:322-331`, `backend/tests/test_pptx_lint.py:134-165` | 只接受页脚区密级;正文写密级仍触发 HW-E01。 |
| HW-E02: 字体白名单 | `docs/taskbook.md:438` | 满足 | `backend/app/lint/pptx_lint.py:117-128`, `backend/tests/test_pptx_lint.py:134-150` | 触发测试覆盖。 |
| HW-E03: 动画/切换 | `docs/taskbook.md:439` | 满足 | `backend/app/lint/pptx_lint.py:76-78`, `backend/tests/test_pptx_lint.py:153-171` | 触发测试覆盖。 |
| HW-W01: 字号小于 10.5pt | `docs/taskbook.md:440` | 满足 | `backend/app/lint/pptx_lint.py:117-135`, `backend/tests/test_pptx_lint.py:167-195` | 正反测试覆盖;页脚 9pt 按主题豁免。 |
| HW-W02: 非主题色 | `docs/taskbook.md:441` | 满足 | `backend/app/lint/pptx_lint.py:117-135`, `backend/tests/test_pptx_lint.py:182-195` | 正反测试覆盖。 |
| HW-W03: 要点超 7 条或 60 字 | `docs/taskbook.md:442` | 满足 | `backend/app/lint/pptx_lint.py:151-162`, `backend/tests/test_pptx_lint.py:198-227` | 正反测试覆盖。 |
| HW-W04: 表格超过 12x8 | `docs/taskbook.md:443` | 满足 | `backend/app/lint/pptx_lint.py:138-148`, `backend/tests/test_pptx_lint.py:153-171` | 触发测试覆盖。 |
| HW-W05: 总页数超过 30 | `docs/taskbook.md:444` | 满足 | `backend/app/lint/pptx_lint.py:59-68`, `backend/tests/test_pptx_lint.py:153-171` | 触发测试覆盖。 |
| HW-W06: 文本框网格吸附 | `docs/taskbook.md:445` | 满足 | `backend/app/lint/pptx_lint.py:165-192`, `backend/tests/test_pptx_lint.py:39-66` | 正反例覆盖。 |
| HW-W07: 元素间距/页边距 | `docs/taskbook.md:446` | 满足 | `backend/app/lint/pptx_lint.py:195-227`, `backend/app/lint/pptx_lint.py:381-406`, `backend/tests/test_pptx_lint.py:230-260` | 正反测试覆盖两两间距/重叠。 |
| HW-W08: 关键框坐标 | `docs/taskbook.md:447` | 满足 | `backend/app/lint/pptx_lint.py:210-234`, `backend/tests/test_pptx_lint.py:69-101` | 正反例覆盖。 |
| HW-W09: 对比度 | `docs/taskbook.md:448` | 满足 | `backend/app/lint/pptx_lint.py:237-260`, `backend/tests/test_pptx_lint.py:104-131` | 正反例覆盖。 |
| HW-I01: agenda 条目数与 section 页数不一致 | `docs/taskbook.md:449` | 满足 | `backend/app/lint/pptx_lint.py:353-379`, `backend/tests/test_pptx_lint.py:283-329` | 正反测试覆盖。 |
| 报告结构 JSON + Markdown, Error 决定 pass | `docs/taskbook.md:451` | 满足 | `backend/app/lint/pptx_lint.py:26-50`, `backend/app/lint/pptx_lint.py:91-114`, `backend/tests/test_pptx_lint.py:174-211` | 双格式报告有测试。 |
| §7 单元测试: parser 每格式至少 5 例 | `docs/taskbook.md:470` | 满足 | `backend/tests/test_parser_sample_counts.py:23-32`, `samples/input/parser_samples/`, `backend/tests/test_dirty_samples.py:14-74`, `samples/input/synthetic/` | 数量满足;synthetic 额外覆盖 §5.4 合并单元格、修订/批注/图片、组合形状/SmartArt、超大表截断。 |
| §7 单元测试: IR 全部错误码反例 | `docs/taskbook.md:470` | 满足 | `backend/tests/test_ir_validation.py:12-303`, `backend/tests/test_ir_shell_and_repair.py:44-59`, `backend/tests/test_word_samples.py:19-78` | E/W/I/D 码均有触发测试;主要 warning/info 有反例。 |
| §7 单元测试: lint 每条规则正反例各至少 1 | `docs/taskbook.md:470` | 满足 | `backend/tests/test_pptx_lint.py:39-329` | HW-E01~03、HW-W01~09、HW-I01 均覆盖正反例。 |
| §7 渲染 golden 回读断言 | `docs/taskbook.md:470` | 满足(主要结构) | `backend/tests/test_docx_renderer.py:16-169`, `backend/tests/test_pptx_renderer.py:14-118` | 结构回读充分;非视觉 golden。 |
| §7 契约测试 | `docs/taskbook.md:471` | 满足 | `backend/tests/test_c0_contract.py:97-112` | 三 schema 快照比对。 |
| §7 端到端四格式 parse→prompt→render→check | `docs/taskbook.md:472` | 满足 | `scripts/demo_e2e.py:38-59`, `backend/tests/test_repro_cli.py:139-164`, `scripts/verify.py:53-100` | md/docx/xlsx/pptx 均跑 word 与 deck stub 链路并检查 report.json。 |
| §7 覆盖率: parsers/ir/lint ≥80%, overall ≥70% | `docs/taskbook.md:473` | 满足 | `scripts/verify.py:23-24`, `scripts/verify.py:79-99`; 本次实跑见上 | `pytest --cov` terminal total 86%; `verify.py` JSON overall 86.40%。 |
| §7.2 一键验收命令 | `docs/taskbook.md:475-481` | 满足 | `scripts/verify.py:27-132`, `verify.ps1:1-13`, `backend/tests/test_c0_contract.py:140-155`;实跑 `python3 scripts/verify.py` 通过 | Mac verify 与 Windows 薄封装齐备;Windows 真机结果仍需人工。 |
| §7.3 Word 输出验收 | `docs/taskbook.md:488` | 满足(自动可验证) | `backend/tests/test_render_cli.py:14-36`, `backend/tests/test_docx_renderer.py:59-169` | CLI 产出 DOCX 且结构回读满足;Word 桌面端视觉/编辑体验另列人工边界。 |
| §7.3 多格式输入验收 | `docs/taskbook.md:489` | 满足 | `backend/tests/test_parser_sample_counts.py:23-32`, `backend/tests/test_repro_cli.py:139-164`, `backend/tests/test_prompt_builder.py:12-80` | 四格式 parse/prompt/e2e 均覆盖。 |
| §7.3 PPTX 生成验收 | `docs/taskbook.md:490` | 满足 | `backend/tests/test_repro_cli.py:100-126`, `backend/app/generators/stub.py:26-47` | md deck stub 5-12 页通过。 |
| §7.3 华为风格约束验收 | `docs/taskbook.md:491` | 满足(自动规则) | `backend/tests/test_pptx_lint.py:18-329`, `backend/tests/test_pptx_renderer.py:53-76` | 正常产物零 Error 与人工注入规则均覆盖;视觉观感仍需人工终审。 |
| §7.3 可迁移性验收 | `docs/taskbook.md:492` | 满足(开发机/脚本) | `scripts/verify.py:27-132`, `verify.ps1:1-13`, `docs/内网接入.md:33-59` | Mac stub verify 通过;Windows 断网真机执行仍需人工。 |
| §7.4 Windows 离线验收 | `docs/taskbook.md:495-504` | 无法自证 | `scripts/make_wheelhouse.py:12-39`, `docs/内网接入.md:33-59`, `QUESTIONS.md:8-10` | 需要干净 Windows 真机和截图记录。 |
| §10 交付 1: CLI 工具链 Word + PPTX + stub | `docs/taskbook.md:552` | 满足 | `scripts/demo_e2e.py:23-63`, `backend/app/cli/render.py:24-47`, `backend/app/rendering/pptx_renderer.py:27-61`, `backend/tests/test_render_cli.py:60-140` | Word/PPTX CLI 与 stub demo 均可运行。 |
| §10 交付 2: 三份 IR 规范 + Schema + 正/反样例 | `docs/taskbook.md:553` | 满足 | `backend/schemas/word_ir.schema.json`, `backend/schemas/document_ir.schema.json`, `backend/schemas/deck_ir.schema.json`, `backend/tests/test_ir_sample_matrix.py:12-48`, `samples/ir/deck_valid_full.json:1`, `samples/ir/document_valid_01_md_summary.json:1` | 三份 schema 与 Word/Document/Deck 正反样例均入库。 |
| §10 交付 3: 四解析器与样例/warnings 降级清单 | `docs/taskbook.md:554` | 满足(构造样例) | `backend/app/parsers/`, `backend/tests/test_parser_sample_counts.py:23-32`, `backend/tests/test_docx_parser.py:14-99`, `backend/tests/test_xlsx_parser.py:14-104`, `backend/tests/test_pptx_parser.py:17-101`, `backend/tests/test_dirty_samples.py:14-74`, `REAL_PARSE_REPORT.md:51-73` | 四解析器、每格式 5 构造样例、synthetic 脏样例和关键降级 warning 有测试;真实语料仍需人工提供。 |
| §10 交付 4: Prompt 模板库与组装器 | `docs/taskbook.md:555` | 满足 | `backend/app/prompting/templates/ir_generation.txt:1-9`, `backend/app/prompting/builder.py:43-170`, `backend/tests/test_prompt_builder.py:12-80` | 四段式、确定性、结构化优先级截断均有测试。 |
| §10 交付 5: DOCX 渲染器 + 3 官方样例 | `docs/taskbook.md:556` | 满足(自动可验证) | `backend/app/rendering/docx_renderer.py:24-231`, `backend/tests/test_word_samples.py:13-38` | 视觉和 Word 打开另列人工边界。 |
| §10 交付 6: 主题 + 10 版式 PPTX renderer | `docs/taskbook.md:557` | 满足 | `backend/app/rendering/themes/hw_theme.json:59-242`, `backend/app/rendering/pptx_renderer.py:27-377`, `backend/tests/test_pptx_renderer.py:101-183`, `samples/ir/deck_valid_full.json:1` | 代码与样例均覆盖 10 版式;版式坐标/尺寸集中在 theme。 |
| §10 交付 7: 合规检查器双报告,外部 PPTX 复检 | `docs/taskbook.md:558` | 满足 | `backend/app/cli/check.py:18-32`, `backend/app/lint/pptx_lint.py:91-114`, `backend/app/lint/docx_lint.py:92-113`, `backend/tests/test_pptx_lint.py:331-369` | PPTX/DOCX 双报告均覆盖;PPTX 全规则见 S3-4。 |
| §10 交付 8: 测试套件与 coverage 报告,一键 verify | `docs/taskbook.md:559` | 满足 | `scripts/verify.py:27-132`, `verify.ps1:1-13`, `backend/tests/test_c0_contract.py:140-155` | 本次 verify 通过;Windows 真机运行结果仍需人工记录。 |
| §10 交付 9: README、使用说明、内网接入、验收手册 | `docs/taskbook.md:560` | 满足 | `README.md:1-45`, `docs/使用说明.md:1-55`, `docs/内网接入.md:1-65`, `docs/验收手册.md:1-43`, `backend/tests/test_docs.py:20-31` | 文档四件齐备。 |
| §10 交付 10: 演示材料包:样例/结果/截图/录屏脚本 | `docs/taskbook.md:561` | 满足(脚本/样例) | `samples/input/quarterly_report.md`, `samples/input/parser_samples/`, `scripts/demo_e2e.py:23-63`, `scripts/record_demo.sh:1-18` | 样例与录屏脚本齐备;实际截图/录屏成品需按脚本人工生成。 |
| §10 交付 11: 真实脱敏 docx/xlsx/pptx 各 ≥3 | `docs/taskbook.md:562`, `docs/taskbook.md:605` | 未做/外部输入 | `QUESTIONS.md:5-7`; `REAL_PARSE_REPORT.md:75-93`; `find samples/input/real ...` 返回 0 个文件 | synthetic 已覆盖结构边界,但不替代真实文件;仍需要用户/内网提供真实脱敏语料。 |
| §10 交付 12: 健壮性机制与 Windows 离线验收记录 | `docs/taskbook.md:563` | 满足(自动可验证) | `backend/tests/test_c0_contract.py:97-112`, `backend/app/ir/repair.py:19-52`, `backend/app/lint/pptx_lint.py:165-260`, `scripts/make_dirty_samples.py:33-45`, `backend/tests/test_dirty_samples.py:14-74`, `verify.ps1:1-13`, `QUESTIONS.md:8-10` | 快照/修复/W06-W09/synthetic 边界样例有;Windows 真机记录另列人工边界。 |
| 五件套 DoD: 代码+样例+失败提示+最小测试+文档 | `docs/taskbook.md:565` | 满足(自动可验证) | `backend/tests/`, `samples/ir/`, `samples/input/parser_samples/`, `docs/使用说明.md:1-55`, `docs/验收手册.md:1-43` | 自动侧五件套已补;人工终审仍不可省。 |
| 两道人工终审: PPTX 视觉、内容语义抽查 | `docs/taskbook.md:567` | 无法自证 | `docs/taskbook.md:567`, `HUMAN_REVIEW.md:200-249` | 必须人工执行,不能标自动通过。 |

## FALSE-GREEN 汇总

这里的 FALSE-GREEN 指:自动测试或历史进度看起来为绿,但按任务书硬性验收逐条核对后,实际缺失、只做一半或没有测试证明。

| 编号 | 当前状态 | 证据 |
| --- | --- | --- |
| FG-01 | 已关闭:`render.py --type deck` 已实现 | `backend/app/cli/render.py:35-47`, `backend/tests/test_render_cli.py:60-140` |
| FG-02 | 已关闭:`check.py <docx>` 已实现 | `backend/app/cli/check.py:23-32`, `backend/app/lint/docx_lint.py:45-113`, `backend/tests/test_docx_lint.py:14-49` |
| FG-03 | 已关闭:`HW-I01` 已实现并测试 | `backend/app/lint/pptx_lint.py:353-379`, `backend/tests/test_pptx_lint.py:283-329` |
| FG-04 | 已关闭:`W101/W102/W103/I201` 已落码 | `backend/app/ir/validation.py:101-184`, `backend/tests/test_ir_validation.py:81-199` |
| FG-05 | 已关闭:Word 诊断样例已超过 10 个 | `backend/tests/test_word_samples.py:19-78`, `samples/ir/word_invalid_e001_bad_json.json:1` |
| FG-06 | 已关闭:Deck D001/D002/D004/D005/D006 已有触发测试 | `backend/tests/test_ir_shell_and_repair.py:53-59`, `backend/tests/test_ir_validation.py:201-263` |
| FG-07 | 已关闭:DOCX outlineLevel 双策略已实现 | `backend/app/parsers/docx_parser.py:103-121`, `backend/tests/test_docx_parser.py:64-80` |
| FG-08 | 已关闭:PPTX 组合形状递归遍历已实现 | `backend/app/parsers/pptx_parser.py:137-142`, `backend/tests/test_pptx_parser.py:84-101` |
| FG-09 | 已关闭:Prompt 结构化优先级截断已实现 | `backend/app/prompting/builder.py:43-170`, `backend/tests/test_prompt_builder.py:52-80` |
| FG-10 | 已关闭:S3-1 版式坐标/尺寸已迁入 `hw_theme.json` | `backend/app/rendering/themes/hw_theme.json:59-242`, `backend/app/rendering/pptx_renderer.py:64-336`, `backend/tests/test_pptx_renderer.py:101-153` |
| FG-11 | 已关闭:`HW-W07` 两两间距/重叠已实现 | `backend/app/lint/pptx_lint.py:195-227`, `backend/tests/test_pptx_lint.py:230-260` |
| FG-12 | 已关闭:`HW-E01` 页脚区校验已实现 | `backend/app/lint/pptx_lint.py:70-74`, `backend/tests/test_pptx_lint.py:153-165` |
| FG-13 | 已关闭:lint 每条规则正反例已覆盖 | `backend/tests/test_pptx_lint.py:39-329` |
| FG-14 | 已关闭:四格式 e2e 已纳入测试和 verify | `backend/tests/test_repro_cli.py:139-164`, `scripts/verify.py:53-100` |
| FG-15 | 已关闭(脚本):`verify.ps1` 已补;真机记录仍人工 | `verify.ps1:1-13`, `docs/验收手册.md:20-33` |
| FG-16 | 已关闭:DocumentIR/DeckIR 正反样例已补 | `backend/tests/test_ir_sample_matrix.py:12-48`, `samples/ir/deck_valid_full.json:1`, `samples/ir/document_valid_01_md_summary.json:1` |
| FG-17 | 已关闭:P0 五版式 lint 零 Error 测试已补 | `backend/tests/test_pptx_renderer.py:53-76` |
| FG-18 | 已关闭:10MB 包体性能测试已补 | `backend/tests/test_xlsx_parser.py:85-104` |
| FG-19 | 已关闭(脚本/文档):文档四件与录屏脚本已补 | `docs/使用说明.md:1-55`, `docs/验收手册.md:1-43`, `scripts/record_demo.sh:1-18` |

自动侧仍残留 FALSE-GREEN: 0 条。Windows 真机、真实语料、视觉/语义终审不计入自动侧 FALSE-GREEN,保留在人工验证边界。

## 我无法自证、只能人工验证

| 项目 | 为什么无法自证 | 当前证据 | 需要人工做什么 |
| --- | --- | --- | --- |
| PPTX 视觉观感 | python-pptx 回读只能证明文本/形状存在,不能判断像不像正式华为材料、是否压字、留白是否专业 | `backend/tests/test_pptx_renderer.py:14-118`, `backend/tests/test_pptx_lint.py:18-171` | 在 Windows PowerPoint 打开 `output/c0_deck.pptx` 和 demo deck,逐页检查字体、坐标、留白、重叠、压字。 |
| DOCX 视觉与可编辑性 | python-docx 回读不能证明 Word 桌面端页码域、分页、表头重复、字体替换真实表现 | `backend/tests/test_docx_renderer.py:59-169` | 在 Windows Word 打开 `output/c0_word.docx` 和表格样例,编辑标题/正文/表格,检查页眉页脚和表头重复。 |
| 真实文件解析鲁棒性 | synthetic 已覆盖结构边界,但仍不能代表真实业务文件的脏数据组合、文件损坏方式和人工观感 | `backend/tests/test_parser_sample_counts.py:23-32`, `backend/tests/test_dirty_samples.py:14-74`, `QUESTIONS.md:5-7`, `REAL_PARSE_REPORT.md:75-93` | 本轮已生成并解析 `samples/input/synthetic/`;真实 `samples/input/real/` 仍为空。提供脱敏真实 docx/xlsx/pptx 各至少 3 个后,逐个跑 parse 并人工核对 warnings。 |
| Windows 离线真机 | macOS 上安装/测试通过不代表 Windows 离线 wheelhouse 可用 | `scripts/make_wheelhouse.py:12-39`, `docs/内网接入.md:33-59`, `QUESTIONS.md:8-10` | 在干净断网 Windows 上安装 wheelhouse,运行 verify,保存环境、输出和截图。 |
| 内容语义终审 | 自动化不能判断摘要是否失真、模型是否编造、业务表达是否可交付 | `docs/taskbook.md:567` | 由业务/导师抽查样例产物内容事实与表达质量。 |
