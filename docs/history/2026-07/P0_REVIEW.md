# P0 独立复核闭环报告

复核日期: 2026-07-10
复核范围: `TASKBOOK_GAP_PLAN.md` 的 34 条 P0
权威口径: `docs/taskbook.md`
方法: 重新读实现与测试、运行正反探针、回读真实 PPTX 几何、执行全量 pytest / verify。本文不以原“已完成”标记作为证据。

## 结论

- **34/34 条 P0 现均为满足。** 上一版的 11 条“部分满足”已全部关闭,其中 7 个根因已修复,4 个汇总项随根因收口。
- 三处 false-green 已改为验证真实事实:HW-W06 读取 PPTX 实际几何,HW-W07 使用真实主题页边距和实际包围盒,E2E 核对多项来源事实在目标 IR 与最终 Office 产物中的贯通。
- DocumentIR 1.0 存量中间产物确实存在,因此已补兼容读取,不是采用“无需迁移”的假设。读取后在内存中升为 1.1 并重新执行 1.1 约束。
- `VERIFY_RUNNING=1` 不再是覆盖率绕过入口。verify 会删除外部同名变量并始终启动 pytest+coverage;测试失败或低覆盖均返回失败。
- 最终验证:`288 passed`;verify 通过;parsers 93.30%、IR 93.37%、lint 92.88%、overall 89.58%。无 skip/xfail,四项覆盖率均不低于复核前基线。

## 34 条逐项复核

| # | P0 条目 | 出处 | 状态 | 代码证据 | 测试证据与复核结论 |
| ---: | --- | --- | --- | --- | --- |
| 1 | B-06 Schema 快照阻止同版本改字段 | §3.0、§7.1 | ✅ | `backend/app/ir/schema_export.py:62`、`:90`; `backend/schemas/schema_history.json:1` | `backend/tests/test_c0_contract.py:107`、`:119`、`:134`;快照篡改和同版本变化均被拒。 |
| 2 | E-05 契约测试防 Schema/版本漂移 | §7.1 | ✅ | `backend/app/ir/schema_export.py:62`; `scripts/verify.py:35` | `backend/tests/test_c0_contract.py:96`、`:107`;verify 只读校验,不会先覆盖快照。 |
| 3 | B-14 DocumentIR format/content 一致性 | §3.2 | ✅ | `backend/app/ir/document_ir.py:200` | `backend/tests/test_c0_contract.py:217`;异格式已填充内容被拒。 |
| 4 | B-15 DocumentIR 预览与表格限额进入 Schema | §3.2 | ✅ | `backend/app/ir/document_ir.py:45`、`:53`、`:70`、`:94` | `backend/tests/test_c0_contract.py:245`; `backend/tests/test_ir_sample_matrix.py:64`;20 行、20x15 与行列规整正反例齐。 |
| 5 | A-12 prompt CLI 失败路径错误码 | §2.5 | ✅ | `backend/app/cli/prompt.py:20`; `backend/app/cli/errors.py:28` | `backend/tests/test_cli_failure_contract.py:49`;缺文件、坏 JSON、输出失败均非零且无 traceback。 |
| 6 | A-13 render CLI I/O 与 renderer 边界 | §2.5 | ✅ | `backend/app/cli/render.py:22` | `backend/tests/test_render_cli.py:14`; `backend/tests/test_cli_failure_contract.py:74`;Word/Deck 均先校验后渲染。 |
| 7 | A-14 check CLI 支持 DOCX/PPTX 异常边界 | §2.5 | ✅ | `backend/app/cli/check.py:18` | `backend/tests/test_cli_failure_contract.py:111`;损坏、缺失和错误扩展名均结构化失败。 |
| 8 | A-16 所有 CLI 失败带码且不暴露堆栈 | §2.5 | ✅ | `backend/app/cli/errors.py:28` | `backend/tests/test_cli_failure_contract.py:38`;四 CLI 失败契约有集中断言。 |
| 9 | E-10 同一输入重复 parse+prompt 逐字节一致 | §7.3 | ✅ | `backend/app/parsers/source_metadata.py:7`;四 parser 分别在 `md_parser.py:88`、`docx_parser.py:90`、`xlsx_parser.py:170`、`pptx_parser.py:54` 使用源文件 mtime | `backend/tests/test_repro_cli.py:85`、`:126`;两份 DocumentIR 与 Prompt 都逐字节相同,不再只保证 Prompt。 |
| 10 | D-11 Prompt 四段式、est_chars、few-shot、确定性 | S2-5 | ✅ | `backend/app/prompting/builder.py:36`; `backend/app/prompting/templates/ir_generation.txt:1` | `backend/tests/test_prompt_builder.py:14`、`:30`、`:85`、`:109`;约束、预算、截断和确定性均被断言。 |
| 11 | F-04 Prompt 交付汇总 | §10.4 | ✅ | 同第 10 条 | `backend/tests/test_prompt_builder.py:121`、`:135`;强化 Prompt 可经 stub 产合法 IR,波动时间字段被归一化。 |
| 12 | A-09 StubGenerator 消费 DocumentIR | §2.4 | ✅ | `backend/app/generators/stub.py:55`、`:150`、`:249` | `backend/tests/test_prompt_builder.py:153`、`:181`;四格式内容差异会改变输出。 |
| 13 | D-17 S3-5 md 摘要进入 5-12 页 Deck | S3-5 | ✅ | `scripts/demo_e2e.py:37`; `backend/app/generators/stub.py:150` | `backend/tests/test_repro_cli.py:182`;Deck 页数、PPTX 和 lint 报告均有效。 |
| 14 | E-06 四格式 E2E 有真实语义断言 | §7.1 | ✅ | `scripts/verify.py:62`、`:110`、`:144`、`:223` | `backend/tests/test_repro_cli.py:130`、`:222`;标题、段落、列表项、表头、数据格、sheet、slide body/table/notes 全量核对 source→IR→最终 DOCX/PPTX;单 marker 负例必挂。 |
| 15 | F-01 CLI 主流程与 stub 断网交付 | §10.1 | ✅ | `scripts/demo_e2e.py:37`;四 CLI 主入口见 `backend/app/cli/` | `backend/tests/test_repro_cli.py:154`、`:182`、`:222`;四输入 x 两目标链路通过。 |
| 16 | B-20 Office 超长文本截断并 W103 | §5.4 | ✅ | `backend/app/parsers/text_limits.py:10`;三 Office parser 均接入 | `backend/tests/test_docx_parser.py:143`; `test_pptx_parser.py:102`; `test_xlsx_parser.py:203`;位置与反向短文本均核对。 |
| 17 | B-19 全格式图片/OLE 记录存在与尺寸 | §3.2、§5.4 | ✅ | DOCX/PPTX 原实现加 `backend/app/parsers/xlsx_parser.py:562`、`:648`、`:665` | `backend/tests/test_xlsx_parser.py:154`、`:411`;XLSX 现在记录 sheet、锚点、宽高、part、bytes,缺失元数据明确降级为 unknown;DOCX/PPTX 既有正例保留。 |
| 18 | B-16 DOCX 不支持项 warning 含数量与位置 | §3.2、§5.4 | ✅ | `backend/app/parsers/docx_parser.py:194` | `backend/tests/test_docx_parser.py:121`;修订、批注、文本框、SmartArt 有数量与部件位置。 |
| 19 | D-08 S2-2 DOCX parser 验收汇总 | S2-2 | ✅ | `backend/app/parsers/docx_parser.py:26` | `backend/tests/test_docx_parser.py:18`、`:121`、`:143`;标题、列表、表格、嵌套表、图片和降级齐。 |
| 20 | B-21 XLSX 超大文件硬时间/资源预算 | §5.4 | ✅ | `backend/app/parsers/xlsx_parser.py:44`、`:184`、`:223`、`:240`;>=10MB 进入 spawn 隔离进程,超时 terminate 并给已处理范围 | `backend/tests/test_xlsx_parser.py:257`、`:315`、`:334`、`:352`;覆盖硬截止、结构化失败、EOF、未知异常和 worker 清理。 |
| 21 | D-09 真实 >10MB XLSX 小于 5 秒 | S2-3 | ✅ | `backend/app/parsers/xlsx_parser.py:44` | `backend/tests/test_xlsx_parser.py:279`;30,000 行真实 worksheet、包体 >=10MB,断言 <5 秒。 |
| 22 | F-03 parser 交付汇总 | §10.3 | ✅ | 四 parser + `source_metadata.py` + XLSX 隔离截止/图片关系解析 | parser 定向回归包含 `test_xlsx_parser.py:154`、`:257`、`:279`;B-19/B-21 根因已关闭。 |
| 23 | C-19 HW-E02 覆盖表格/chart 字体 | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:123` | `backend/tests/test_pptx_lint.py:525`、`:555`;主题与非主题字体正反例齐。 |
| 24 | C-21 HW-W01 覆盖表格/chart 字号 | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:395` | `backend/tests/test_pptx_lint.py:507`、`:525`;最小字号和字号种类均检查。 |
| 25 | C-22 HW-W02 覆盖形状/表格/chart 色 | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:141` | `backend/tests/test_pptx_lint.py:454`、`:490`;普通形状、表格、图表系列和阈值线均有反例。 |
| 26 | C-23 HW-W03 识别原生 bullet | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:424` | `backend/tests/test_pptx_lint.py:614`;原生 `buChar/buAutoNum/buBlip` 进入计数。 |
| 27 | C-26 HW-W06 基于 PPTX 实际几何 | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:439`、`:451`;直接读取 shape.left/top/width/height 对 12 栏/8pt token,renderer name 仅作消息标签 | `backend/tests/test_pptx_lint.py:638`;即使 name 伪造为和移动后坐标一致仍命中 W06。独立 11 页产物探针为 W06=0。 |
| 28 | C-27 HW-W07 使用真实页边距/间距/重叠 | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:484`、`:488`、`:498`;边距来自 `hw_theme.json:64`-`:67`,无 renderer 零边距特例 | `backend/tests/test_pptx_lint.py:664`、`:693`、`:710`、`:741`;页边、正常几何、容器包含和重叠正反例齐。独立产物探针为 W07=0。 |
| 29 | C-29 HW-W09 覆盖 table/chart/复杂背景 | §6.3 | ✅ | `backend/app/lint/pptx_lint.py:599`、`:884` | `backend/tests/test_pptx_lint.py:108`、`:123`、`:762`、`:784`;4.5:1 正反例和复杂背景人工 warning 齐。 |
| 30 | D-16 S3-4 全规则、正反例、双报告 | S3-4 | ✅ | `backend/app/lint/pptx_lint.py:54`、`:439`、`:484` | W06/W07 漏报已关闭;`backend/tests/test_pptx_lint.py:638`、`:664` 证明违规真实命中。 |
| 31 | F-07 lint 与外部复检交付汇总 | §10.7 | ✅ | `backend/app/cli/check.py:18`; `backend/app/lint/pptx_lint.py:54` | CLI 异常测试加 47 个 PPTX lint 定向测试通过;外部文件与 renderer 产物走同一回读规则。 |
| 32 | F-02 IR 交付与契约保护汇总 | §10.2 | ✅ | `backend/app/ir/schema_export.py:62`; `backend/app/ir/document_ir.py:186`; `backend/schemas/schema_history.json:1` | `backend/tests/test_c0_contract.py:96`、`:107`、`:282`、`:306`;快照、版本历史、1.0 兼容正例及 1.1 约束反例齐。 |
| 33 | F-08 单元/契约/E2E、coverage、verify | §7.1-§7.2、§10.8 | ✅ | `scripts/verify.py:247`-`:301`;外部 `VERIFY_RUNNING` 在 `:253` 被移除,pytest/coverage 始终执行 | `backend/tests/test_c0_contract.py:382`、`:395`、`:410`;正常主流程、外部绕过、pytest 失败和低覆盖均有门禁。最终 288 passed,verify 通过。 |
| 34 | F-12 健壮性机制交付汇总 | §10.12 | ✅ | 契约迁移、确定性时间、semantic E2E、XLSX 隔离截止、真实几何 lint 与严格 verify 均已落码 | 本表第 9/14/17/20/27/28/33 条根因测试全部通过;Schema 快照复核与最终全量命令通过。 |

## 三处 False-Green 的真实修复

### 1. HW-W06 不再采信 renderer 自报坐标

- 根因:旧实现把 renderer 写在 shape.name 中的 bbox 当基准,renderer 和 name 同时写错即可通过。
- 修复:`_grid_items` 只读 PPTX 回读得到的 `shape.left/top/width/height`,换算后分别对 12 栏网格和 8pt baseline 比对,见 `backend/app/lint/pptx_lint.py:439`-`:468`。shape.name 仅用于把消息写成“renderer 文本框”,不参与坐标判定。
- 渲染器也不再写坐标元数据,统一只写 `HW_RENDERED_TEXT`,见 `backend/app/rendering/pptx_renderer.py:106`、`:947`、`:1042`。
- 反例把 shape 真坐标移动 0.2in,再伪造与移动后完全一致的旧式 name,仍命中 HW-W06,见 `backend/tests/test_pptx_lint.py:638`-`:661`。

### 2. HW-W07 不再给 renderer 文本零页边距

- 根因:旧分支把 renderer text 的允许边界设为整页,使 0.05in 贴边文本漏报。
- 修复:所有内容形状统一使用 `hw_theme.json` 的 left/right/top/bottom margin,并基于实际包围盒检查越界、重叠和 `min_gap_in`,见 `backend/app/lint/pptx_lint.py:484`-`:512`。
- 反例即使伪造旧式 shape.name,0.05in 文本仍命中 HW-W07,见 `backend/tests/test_pptx_lint.py:664`-`:690`。全页无文本背景和明确布局容器则有正向反例保护,见 `:710`-`:738`。

### 3. E2E 不再只看单一 marker

- 根因:旧门禁只找第一标题/sheet 名,其余正文、表格和数据全部丢失仍可通过。
- 修复:`_semantic_facts` 从 DocumentIR 提取每个 heading/paragraph、每个列表项、表头与数据格、sheet 名/header/preview、slide title/body/table/notes,见 `scripts/verify.py:144`-`:195`。
- 每个事实先检查目标 IR,再从真实 DOCX/PPTX 回读文本与表格单元格检查最终产物,见 `scripts/verify.py:110`-`:132`、`:223`-`:238`。
- `backend/tests/test_repro_cli.py:130` 证明只保留标题 marker 会失败;`:222` 对 md/docx/xlsx/pptx x word/deck 的 8 条链路逐项核对全部事实。

## DocumentIR 1.0 -> 1.1 兼容性结论

仓库不是“完全无存量”。代码路径会落盘中间产物:`scripts/demo_e2e.py:42`-`:44` 与 `backend/app/web.py:90`-`:93`;本轮只读扫描 `output/` 与 `samples/` 找到 DocumentIR 1.0 共 1375 份、1.1 共 181 份。数量包含历史测试/演示产物,但足以否定“无需兼容读取”的假设。

处理方式:

1. 当前 Schema 和新输出仍只有 DocumentIR 1.1,没有改 IR 字段或再升版本。
2. Pydantic 读取入口在校验前识别 1.0,复制 payload、改为 1.1 并追加迁移 warning,见 `backend/app/ir/document_ir.py:186`-`:198`。
3. 迁移后继续执行 1.1 的格式/内容一致性和预览限额;非法旧数据不会被放行,见 `backend/tests/test_c0_contract.py:306`。
4. 不自动覆写旧文件;使用边界和重新序列化方式写入 `docs/使用说明.md:61`-`:71`,并由 `backend/tests/test_docs.py:34` 固定。

结论:对合法 1.0 中间产物向后兼容;对违反 1.1 新约束的 1.0 数据明确拒绝并要求重解析/修正。这比无条件改版本号更稳妥。

## verify 门禁复核

- `scripts/verify.py` 已无“检测到 VERIFY_RUNNING 就直接 True”的分支。`:253` 主动移除外部变量,`:254`-`:273` 无条件运行 pytest+coverage。
- pytest 非零在 `:274`-`:278` 返回失败;核心包 <80% 或整体 <70% 在 `:286`-`:297` 返回失败;main 只有 schema、产物 lint、四格式 E2E、coverage 全部成功才返回 0,见 `:33`-`:59`。
- 外部预设 `VERIFY_RUNNING=1` 且 pytest 失败的负例在 `backend/tests/test_c0_contract.py:395` 仍返回 False;低覆盖负例在 `:410` 返回 False。
- 原递归执行完整 verify 的单测改为进程内 main 门禁测试,见 `:382`;这是移除递归根因,不是跳过验收。真正的 `python scripts/verify.py` 已在本轮独立执行并通过。

## 测试完整性与新发现

本轮没有新增 skip/xfail,全仓 `backend/tests` 搜索结果为空。没有降低 80%/70% 门槛,没有排除新代码,没有改 IR Schema。既有测试有四类调整,全部是加强或消除递归:

1. 重复解析从“DocumentIR 时间不同、Prompt 相同”改为两者都逐字节相同,见 `test_repro_cli.py:126`-`:127`。
2. HW-W06 反例同步伪造旧 name,确保不依赖自报坐标,见 `test_pptx_lint.py:654`-`:661`。
3. 四格式 E2E 从单 marker 改为全部事实 source→IR→artifact,见 `test_repro_cli.py:259`-`:262`。
4. 递归 verify 测试改为 main 单测,并新增外部环境绕过与低覆盖负例,见 `test_c0_contract.py:382`-`:436`。

补覆盖时新发现 XLSX worker 在 EOF 异常路径可能跳过 join/terminate。现已把进程回收放进无条件 finally,见 `backend/app/parsers/xlsx_parser.py:205`-`:210`,并由 `backend/tests/test_xlsx_parser.py:334` 断言 E001 与 terminate。**该新问题已修复,没有留下新的 P0 false-green。**

## 最终命令证据

```text
PYTHONPATH=backend python -m pytest backend/tests -q
288 passed in 31.30s

python scripts/verify.py
e2e: four input formats passed word/deck stub chains
coverage: app/parsers=93.30%, app/ir=93.37%, app/lint=92.88%, overall=89.58%
C0 verify passed
```

Schema 快照校验返回三份文件;版本与 canonical 历史哈希为 WordIR 1.0 `88cf...e9a9`、DocumentIR 1.1 `4bda...07c6`、DeckIR 1.4 `d868...b277`,与 `backend/schemas/schema_history.json` 一致。本轮没有改 Schema。

## 人工边界

34 条 P0 的 Mac 自动侧缺口已关闭,但这不替代任务书明确保留的三类人工验收:真实脱敏业务文件、Windows 离线 wheelhouse 真机、PPTX/DOCX Windows 字体与视觉/语义终审。它们继续属于外部环境边界,不能写成已通过。
