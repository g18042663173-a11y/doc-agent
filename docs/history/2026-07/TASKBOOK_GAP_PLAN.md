# TASKBOOK Mac 欠账分级计划

生成日期: 2026-07-10
来源: `TASKBOOK_COMPLIANCE.md` 中全部 59 条 `[A]欠账`
范围: 本文件先完成分级与排序,现已追加 P0 实施/独立复核、P1 交付资产闭环及 P2 正式降级交代。P2 不实现旧行为，待需求方签收后回写任务书。P0 独立复核闭环见 `P0_REVIEW.md`。

## 分级口径

- **P0 真欠账:** 功能、正确性、鲁棒性、契约保护或核心验收存在真实缺口,必须补。
- **P1 交付资产:** 核心功能已存在,主要缺 fixture、expected、反例文件、hash、截图、评审记录或文档同步。要补,但可在 P0 稳定后批量完成。
- **P2 建议降级:** 任务书早期口径已被后续批准的需求/实测规格替代,或当前更严格、更稳妥的行为与旧文案有意不同。建议更新任务书和验收口径,不为追旧口径回退实现。

重复说明:原合规表会从“底层要求、任务卡、测试矩阵、最终交付”多次引用同一根因。此处仍保留全部 59 个原子条目以便对账,但汇总项标为“随根因收口”,不重复估算成第二份开发工作。

## 汇总与执行顺序

| 级别 | 数量 | 建议 |
| --- | ---: | --- |
| P0 真欠账 | 34 | **34/34 已补完并验收。** 第 30-34 项已随根因收口。 |
| P1 交付资产 | 18 | **18/18 已补完并由资产专项测试验收。** |
| P2 正式降级交代 | 7 | **7/7 已形成原要求、降级理由与未来前提。** P2-3 已确认降级；其余六条的理由已确认合理，待随下一次任务书修订回写。 |
| 合计 | 59 | 初始 `[A]` 共59条;P0 34条与 P1 18条已关闭，P2 7条已有正式交代；P2-3 已确认替代验收，其余六条保留为已确认理由的规格回写项。 |

## P0 真欠账:已补完

验收状态更新于 2026-07-10。下表 34/34 均已由实现和自动测试关闭;P1 交付资产也已按后续章节关闭。P2 七项的正式偏离说明见后文，仍待需求口径签收。

| 顺序 | 原条目 | 状态 | 实现证据 | 测试证据 |
| ---: | --- | --- | --- | --- |
| 1 | B-06 Schema 快照必须阻止改字段但不升版本 | ✅ | `backend/app/ir/schema_export.py:21-123`; `scripts/verify.py:29-35`; `backend/schemas/schema_history.json` | `backend/tests/test_c0_contract.py:108-185` |
| 2 | E-05 契约测试防止 Schema/版本漂移 | ✅ | 同 B-06;verify 只调用 `verify_schema_snapshots`,不再导出 | `backend/tests/test_c0_contract.py:120-185` 覆盖快照篡改、同版本模型变化和 verify 故障注入 |
| 3 | B-14 DocumentIR 的 format/content 一致性 | ✅ | `backend/app/ir/document_ir.py:104-204`;DocumentIR 正式升至 1.1 | `backend/tests/test_c0_contract.py:208-244`; `backend/tests/test_ir_sample_matrix.py:64-73` |
| 4 | B-15 DocumentIR preview 等限额进入 Schema | ✅ | `backend/app/ir/document_ir.py:48-101`; `backend/schemas/document_ir.schema.json` | `backend/tests/test_c0_contract.py:196-280`;正反例 `samples/ir/document_valid_02_xlsx_preview.json` 等 |
| 5 | A-12 prompt CLI 失败路径错误码 | ✅ | `backend/app/cli/prompt.py:21-41`; `backend/app/cli/errors.py:10-47` | `backend/tests/test_cli_failure_contract.py:49-71` |
| 6 | A-13 render CLI IO/renderer 异常边界 | ✅ | `backend/app/cli/render.py:22-55` | `backend/tests/test_cli_failure_contract.py:74-108`; `backend/tests/test_render_cli.py:14-147` |
| 7 | A-14 check CLI 不可读产物异常边界 | ✅ | `backend/app/cli/check.py:19-58` | `backend/tests/test_cli_failure_contract.py:111-136` |
| 8 | A-16 所有 CLI 失败均带码且不暴露堆栈 | ✅ | `backend/app/cli/errors.py:10-47`;四 CLI 使用 `CodedArgumentParser` | `backend/tests/test_cli_failure_contract.py:38-158` |
| 9 | E-10 同一输入重复 parse→prompt 不确定 | ✅ | `backend/app/parsers/source_metadata.py:7-11` 以源文件 mtime 生成稳定 `parsed_at`;四 parser 统一接入 | `backend/tests/test_repro_cli.py:85-127` 两次独立 CLI 同时断言 DocumentIR 与 Prompt 逐字节一致 |
| 10 | D-11 Prompt 的 est_chars/few-shot/确定性混合缺口 | ✅ | `backend/app/prompting/builder.py:16-20,43-61,116-128`; `backend/app/prompting/templates/ir_generation.txt:1-21` | `backend/tests/test_prompt_builder.py:12-151`; `backend/tests/test_repro_cli.py:85-126` |
| 11 | F-04 Prompt 交付物汇总 | ✅ | 同 D-11;任务书 §5.1/§5.3 已统一为裸 JSON 协议 | 同 D-11 |
| 12 | A-09 StubGenerator 不消费 DocumentIR | ✅ | `backend/app/generators/stub.py:11-381` | `backend/tests/test_prompt_builder.py:153-245` 覆盖内容差异和四格式映射 |
| 13 | D-17 S3-5 的 md 摘要进入 stub Deck | ✅ | `scripts/demo_e2e.py:40-81`; `backend/app/generators/stub.py:147-203` | `backend/tests/test_repro_cli.py:158-237` |
| 14 | E-06 四格式 E2E 具备语义断言 | ✅ | `scripts/verify.py:62-238` 提取全部标题/正文/列表/表头/数据/sheet/slide/notes,逐项核对目标 IR 和最终 Office 产物 | `backend/tests/test_repro_cli.py:130-151` 单 marker 负例;`:222-264` 四格式 x Word/Deck 全事实贯通 |
| 15 | F-01 CLI 主流程+stub 交付汇总 | ✅ | CLI 边界、semantic stub 与 shell 校验均接入 `scripts/demo_e2e.py:40-81` | `backend/tests/test_cli_failure_contract.py:38-158`; `backend/tests/test_repro_cli.py:130-237` |
| 16 | B-20 Office 超长单元格截断/W103 | ✅ | `backend/app/parsers/text_limits.py:6-24`;三 Office parser 接入 TextLimiter | `backend/tests/test_xlsx_parser.py:168-184`; `test_docx_parser.py:143-163`; `test_pptx_parser.py:102-126` |
| 17 | B-19 PPTX/OLE/嵌入对象检测 | ✅ | DOCX/PPTX 原实现加 `backend/app/parsers/xlsx_parser.py:562-676`;XLSX 关系链记录 sheet/锚点/宽高/part/bytes | `backend/tests/test_xlsx_parser.py:154-182,411-445`;DOCX/PPTX 原正例保留 |
| 18 | B-16 DOCX 不支持项 warning 含位置 | ✅ | `backend/app/parsers/docx_parser.py:194-230` | `backend/tests/test_docx_parser.py:121-140` |
| 19 | D-08 DOCX parser 任务卡汇总 | ✅ | 标题/列表/20行表格/嵌套表/图片/unsupported 定位均在 `docx_parser.py:25-238` | `backend/tests/test_docx_parser.py:18-203` |
| 20 | B-21 超大文件时间/资源预算 | ✅ | `backend/app/parsers/xlsx_parser.py:44-48,184-258`;>=10MB 进入 spawn 隔离进程,超时 terminate 并返回已处理范围 warning | `backend/tests/test_xlsx_parser.py:257-275,315-409` 覆盖硬截止、ParseFailure、EOF、未知异常、IPC 与进程清理 |
| 21 | D-09 10MB xlsx 性能测试压真实大表 | ✅ | bounded preview/stats/formula scans `xlsx_parser.py:56-138` | `backend/tests/test_xlsx_parser.py:222-273` 构造 30,000 行、>10MB worksheet 并断言 <5秒 |
| 22 | F-03 parser 交付汇总 | ✅ | 四 parser 的长文本、嵌入定位、DOCX位置、XLSX图片几何与硬资源截止均已落码 | `test_xlsx_parser.py:154,257,279,315,334,352`;最终 parsers 覆盖率 93.30% |
| 23 | C-19 HW-E02 检查表格/chart字体 | ✅ | `backend/app/lint/pptx_lint.py:123-139,271-328,759-781` | `backend/tests/test_pptx_lint.py:525-576` |
| 24 | C-21 HW-W01 检查表格/chart字号 | ✅ | 同 C-19;字号种类覆盖 table/chart `pptx_lint.py:394-421` | `backend/tests/test_pptx_lint.py:525-576`;原 chart 反例 `:506-521` |
| 25 | C-22 HW-W02 检查普通形状/表格/chart色 | ✅ | `backend/app/lint/pptx_lint.py:141-205,218-328` | `backend/tests/test_pptx_lint.py:321-396,453-503,578-612` |
| 26 | C-23 HW-W03 识别原生 bullet | ✅ | `backend/app/lint/pptx_lint.py:424-436,783-785` | `backend/tests/test_pptx_lint.py:614-636` |
| 27 | C-26 HW-W06 不再跳过 renderer 文本 | ✅ | `backend/app/lint/pptx_lint.py:439-468` 只读 shape 实际 left/top/width/height 对 12 栏/8pt;renderer 不再自报坐标 | `backend/tests/test_pptx_lint.py:638-661` 即使伪造与实际一致的旧式 name 仍命中 W06 |
| 28 | C-27 HW-W07 覆盖 chart/table/无文本形状 | ✅ | `backend/app/lint/pptx_lint.py:484-558` 统一使用 theme 四边距、实际包围盒和 min_gap,无 renderer 零边距特例 | `backend/tests/test_pptx_lint.py:664-759` 覆盖贴边、正常几何、容器包含和重叠正反例 |
| 29 | C-29 HW-W09 覆盖 table/chart并标记复杂背景 | ✅ | `backend/app/lint/pptx_lint.py:632-706,850-920` | `backend/tests/test_pptx_lint.py:700-741`;原文本正反例 `:108-135` |
| 30 | D-16 S3-4 全规则任务卡汇总 | ✅ | W06/W07 已改为真实产物几何;JSON/Markdown报告保持 `pptx_lint.py:96-119` | `test_pptx_lint.py:638-759`;lint 定向回归 47 passed,最终覆盖率 92.88% |
| 31 | F-07 lint+外部复检交付汇总 | ✅ | `backend/app/cli/check.py:18-58`; `backend/app/lint/pptx_lint.py:54-949` | CLI 失败边界加 47 个 PPTX lint 测试;独立 11 页产物探针 W06=0/W07=0/pass=true |
| 32 | F-02 IR 交付汇总中的契约保护 | ✅ | schema history + DocumentIR 1.1 正规演进;`document_ir.py:186-198` 兼容读取存量 1.0;Word 1.0/Deck 1.4 未变 | `test_c0_contract.py:96-320`; `test_ir_sample_matrix.py:52-73`;合法 1.0 迁移、非法 1.0 按 1.1 约束拒绝 |
| 33 | F-08 测试/verify交付汇总 | ✅ | `scripts/verify.py:247-301` 无条件 pytest+coverage,`:253` 清除外部 `VERIFY_RUNNING`,不再存在 coverage 后门 | `test_c0_contract.py:382-436` 覆盖 main、外部变量、pytest失败和低覆盖;最终 `288 passed`,verify parsers 93.30%、IR 93.37%、lint 92.88%、overall 89.58% |
| 34 | F-12 健壮性机制交付汇总 | ✅ | 确定性、semantic E2E、XLSX硬截止/图片几何、W06/W07真实回读、verify严格门禁均已关闭 | schema 独立核验、ruff、pytest/verify全绿;详见 `P0_REVIEW.md` |

## P1 只差交付资产:已补完

验收状态更新于 2026-07-10。18/18 的资产文件均已生成,由 `backend/tests/test_delivery_assets.py` 只读验证;测试不会自动覆盖 expected。最终全量结果为 `300 passed in 95.29s`; `python scripts/verify.py` 通过(四格式 E2E/C0,parsers 93.75%、IR 93.37%、lint 92.88%、overall 89.66%)。

| 顺序 | 原条目 | 状态 | 资产证据 | 验收证据/边界 |
| ---: | --- | --- | --- | --- |
| 1 | E-13 requirements/wheelhouse hash | ✅ | `requirements-win312.lock`; `docs/wheelhouse-win312-manifest.json`; `scripts/hash_wheelhouse.py` | 26 个真实 cp312/win_amd64 wheel 记录 SHA-256;pip `--dry-run --no-index --require-hashes` 完整解析。Windows 安装仍明确待真机。 |
| 2 | D-10 8页PPT逐页解析样例 | ✅ | `samples/input/项目汇报.pptx`; `samples/expected/项目汇报.pptx.expected.json` | 固定 8 页,含表格、原生图表、两页备注、空白页;`test_delivery_assets.py` 逐页断言。 |
| 3 | D-12 每格式五类parser fixture | ✅ | `samples/input/parser_matrix/manifest.json` + 20 个/引用 fixture | md/docx/xlsx/pptx 各 normal/empty/corrupt/large/degraded,每类有 outcome/error/warning 期望。 |
| 4 | E-01 §7 parser fixture分类矩阵 | ✅ | 同第3项 | manifest 驱动测试实际调用四 parser,corrupt 命中 E001,降级命中指定 warning。 |
| 5 | F-16 附录B三个指定Office输入样例 | ✅ | `samples/input/需求说明.docx`; `销售台账.xlsx`; `项目汇报.pptx` | expected 在 `appendix_b_document_ir.expected.json`;用途与复现见 `docs/交付资产说明.md`。 |
| 6 | F-18 Deck invalid文件不足6个 | ✅ | `samples/ir/deck_invalid_d001_*` 至 `d006_*`; `deck_invalid_manifest.json` | D001-D006 各一个稳定入库反例,逐码断言。 |
| 7 | F-19 `deck_lint_violation.json`缺失 | ✅ | `deck_lint_violation.json`; `.inject.json`; `scripts/make_lint_violation.py`;违规 PPTX/报告 | 合法 IR 渲染后再注入 PPTX 层违规,稳定命中 HW-E01/E02/W01/W02/W06/W07,未在 IR 中伪造样式字段。 |
| 8 | F-20 `samples/expected/`为空 | ✅ | `samples/expected/*.expected.json`; `manifest.json`; `README.md` | 保存可审阅结构事实而非 Office 二进制 hash;manifest 对每份 JSON 记 SHA-256。 |
| 9 | D-06 S1-6 README/new人复现/expected | ✅ | 更新 `README.md`; `docs/reviews/新人复现记录.md`; `samples/expected/` | 复现记录明确为自动侧预审,不冒充真实新员工/导师签收。 |
| 10 | F-05 DOCX交付的expected与配套 | ✅ | `samples/output/word/` 3 个可编辑 DOCX; `word_official_outputs.expected.json` | 回读段落/样式/表格/页眉页脚/主题红,并断言无旧蓝 `4F81BD`。 |
| 11 | D-05 失败文案人工评审记录 | ✅ | `docs/reviews/失败文案评审记录.md` | E/W/I/D 逐码评审。D006 建议措辞不精确已如实登记为有限通过;人工签字栏未伪造。 |
| 12 | D-13 S3-1 风格来源/评审记录 | ✅ | `docs/reviews/主题校准评审记录.md` | 记录 SOURCE_FILE_SPEC 实测优先级、`#C7000B` 决策和照片不可反推精确值边界。 |
| 13 | E-25 `docs/风格规范.md`未同步 | ✅ | `docs/风格规范.md` v1.1 | 已同步 accent 六色、字体/字号、13.34x7.50、四边距、页脚和内网剩余校准。 |
| 14 | F-09 README等文档过期 | ✅ | `README.md`; `docs/使用说明.md`; `内网接入.md`; `验收手册.md` | 当前 CLI、资产命令、hash lock、verify/人工边界均已同步并有文档测试。 |
| 15 | F-22 附录A.2仍列已解决问题 | ✅ | `docs/taskbook.md` 附录 A.2 | DeckIR v1.4 与原生 chart 标为已决;仅保留历史、DOCX 图片透传、内网 Skill 协议。 |
| 16 | A-07 `record_demo.sh`含平台逻辑 | ✅ | `scripts/record_demo.py`;薄 `record_demo.sh`/`record_demo.ps1` | subprocess 全部显式 UTF-8;sh/ps1 只转调 Python,无业务编排。 |
| 17 | F-10 成功/失败截图与录屏材料 | ✅ | `samples/demo/logs/`; `screenshots/`; `recording_steps.md`; `manifest.json` | 实跑 Word/Deck 成功与 D003 失败;两张 1600x900 PNG 已视觉检查且逐文件 SHA-256。Windows Office 录屏仍需人补。 |
| 18 | F-14 五件套完成记录 | ✅ | `docs/任务卡交付索引.md` | S1-1 至 S3-6 共18行,逐卡链接代码/样例/失败提示/最小测试/文档。 |

## P2 可降级/可接受:正式交代

**状态口径:** 以下七项均不是“已满足”的替代说法，而是对任务书早期口径的正式偏离说明。本轮不实现旧行为，也不改动代码/IR。需求方已确认 P2-3 采用替代验收；其余六项的降级理由已确认合理，待下一次任务书修订回写。它们均保留为可追溯的 P2 决策，而不计入已完成的功能项。

### P2-1 E-17 §6.1 旧文字色、字体与字号

1. **任务书原要求:** §6.1 规定标题/正文/辅助色为 `#1F1F1F`、`#333333`、`#595959` 等，字号为封面 40pt、页标题 28pt、正文 16pt 等，并以当时的字体链为准。
2. **降级/不做理由:** 后续拿到的 `SOURCE_FILE_SPEC` 是对真实源文件的实测，当前 `hw_theme.json` 已按它校准为 `#C7000B` 主红、`#1D1D1A`/`#666666` 文字色、微软雅黑/Arial 与 14/12/11/10/9/8pt 信息层级。为满足旧表而回退，会把已验证的源文件真值换回早期近似值，反而降低技术评审类 PPT 与真实模板的一致性。
3. **将来要做的前提:** 需求方确认“规范文档”还是“源文件实测”拥有最终优先级。确认后应回写 §6.1 和验收样例；若决定恢复旧值，再以版本化 theme token 统一调整并重做视觉验收，而不是在 renderer 中叠加第二套口径。

### P2-2 E-18 §6.1 旧尺寸、边距与标题坐标

1. **任务书原要求:** §6.1 写明 13.33 x 7.5 英寸、四边距 0.6 英寸、标题框 `left=0.6`/`top=0.5`/`w=12.13`/`h=1.0` 等固定坐标。
2. **降级/不做理由:** 当前主题采用源文件实测的 13.34 x 7.50 英寸、左右约 0.57 英寸、上约 0.29 英寸、下约 0.50 英寸及相应标题/页脚 token。两套值不能同时被视为精确规范；继续追旧坐标只会制造 renderer 与 lint 的双标准，也不能增加真实模板还原度。
3. **将来要做的前提:** 取得可审阅的源 PPTX/母版或正式 CI 坐标规范，并由设计评审确认测量基准。之后将“精确匹配”改为匹配已版本化 theme token；若要求逐像素还原，还须在目标 Windows/Office/字体环境完成视觉签收。

### P2-3 E-20 旧 0.3in 卡片间距与 8pt 段间口径

**状态: 已确认降级。** 验收从固定 `0.3in/8pt` 阈值调整为“无重叠、无裁切 + 内网真实字体/CI 下人工视觉终审通过”。人工终审不是可选项，已保留在 `QUESTIONS.md` 的 PPTX 视觉终审与内网字体/CI 校准待办中。

1. **任务书原要求:** §6.1 要求段间距至少 8pt、卡片间距 0.3 英寸、元素到页边至少 0.4 英寸。
2. **降级/不做理由:** 当前 theme 的 cards gap 为 0.25 英寸、通用最小间距为 0.08 英寸，配合 HW-W07 的实际产物几何检查与视觉审计，目标是避免重叠/裁切而非机械追随早期数字。这里的降级是有条件的：它不代表 0.25/0.08 天然优于旧值，只说明当前技术评审版式在既有样例中以视觉完整性为优先。
3. **将来要做的前提:** 需求方已确认以“无重叠、无裁切、人工视觉终审”替代硬阈值。进入内网后必须使用真实字体/CI 在 Windows PowerPoint 中执行该终审；若终审不通过，先校准 theme token 并复验。下一次任务书修订应把 §6.1 改写为以 theme token、HW-W07 和人工视觉终审为唯一判定来源。

### P2-4 B-03 所有超限内容自动截断并记 Warning

1. **任务书原要求:** §3.0 把单段落、表格、单页要点等长度上限统一描述为“超限即截断并记 Warning”。
2. **降级/不做理由:** 文本超长目前仍按 W103 截断；但表格维度、页内结构数组、必填布局内容等结构性超限改为 Schema/内容校验拒绝并返回 D 码。静默删除结构项会改变事实、隐瞒缺失内容，违背 IR 是唯一可信契约和“非法 IR 不进入渲染器”的原则。因此这里是刻意收紧，不是漏实现。
3. **将来要做的前提:** 若业务确实接受损失式降级，需逐字段定义保留顺序、截断后的 warning 文案、源数据可追溯方式和修复回路策略。涉及 Schema 可表达范围或新 warning 语义时，须按契约演进流程升版本、补正反样例与快照；不能恢复成无差别静默截断。

### P2-5 B-25 agenda 超 8、bullet 超限自动降级

1. **任务书原要求:** §3.3 将 agenda 条目超过 8 和单页 bullet/单条文本超限列为可自动降级项，文字中包含截断/Warning 的预期。
2. **降级/不做理由:** 当前对 agenda/结构条数采用 Schema 或内容校验拒绝，对 60 字 bullet 通过 prompt 和 lint 暴露问题并进入修复，而不由 renderer 删除要点。对弱模型输出而言，自动删目录项或关键要点会造成“PPT 看起来成功但事实缺失”的 false-green；拆页、压缩表达或修复回路更符合技术评审场景。
3. **将来要做的前提:** 产品方需明确溢出策略：自动拆页、保留前 N 项、摘要合并，还是要求用户人工决断。选定后再把策略落在 generator/repair 与 DeckIR 验证层，并为内容保真、页数上限和 overflow 的正反样例建立验收；若策略需要表达“续页/省略”，须先评估契约演进。

### P2-6 B-17 每个合并区域额外标注 `merged`

1. **任务书原要求:** §3.2/§5.4 要求解析 xlsx 合并单元格时计数、取左上格值填充预览，并“标注 merged”。
2. **降级/不做理由:** 现有 DocumentIR 已提供 `merged_count`，预览采用左上格值，能支持摘要与后续生成；但不为每个合并区域或每个填充值增加 `merged` 标记。该精细标记没有当前 renderer/generator 消费者，且新增范围/单元格元数据会改变 DocumentIR 契约、放大大型表的体积与复杂度，投入与技术评审摘要用途不匹配。
3. **将来要做的前提:** 有明确消费者需要还原合并范围或审计单元格来源，并先确定粒度是 sheet 级 range 列表还是逐单元格标记。届时应新增受限的 `merged_ranges` 类结构、升级 DocumentIR 版本、导出 schema/快照、补 xlsx 正反样例；轻量需求可先用现有 warnings 记录范围文本而不改契约。

### P2-7 B-12 Word 所有排版值进入共享 theme

1. **任务书原要求:** Word 渲染硬要求提出中文字体、字号、标题层级、段落间距、表格边框、页眉页脚等全部集中在 renderer 的 `STYLES` 常量，业务代码零散设置样式视为缺陷。
2. **降级/不做理由:** 目前品牌性 token（主红、文字色、字体、字号、边框）已从 `hw_theme.json` 读取；仅 Word 专属的段前后、缩进、可用表格宽度、quote/note 局部几何仍在 `docx_renderer` 集中定义。把 Word 的版式几何强行复用 PPT 的主题 token，会混淆两种版式系统，增加 token 表面统一但语义不清的维护成本。这里保留的是“品牌 token 单一来源”，不是允许业务路径随意硬编码。
3. **将来要做的前提:** 当出现多品牌 DOCX、可配置 Word 母版，或 Word 专属值需要由非开发人员调整时，应在 theme 中增加明确的 `word` 命名空间，而非挪用 PPT token；随后迁移 renderer 常量、补 DOCX XML/视觉正反例，并由 Windows Word 打开确认。当前若仅需治理局部常量，也可在 renderer 内建立单一 Word 样式表并增加防漂移测试，无需改 IR。

## 执行批次状态

1. **批次一:契约与CLI** — P0 1-11,已完成。
2. **批次二:内容贯通与parser** — P0 12-22,已完成。
3. **批次三:lint真实作用域** — P0 23-31,已完成。
4. **批次四:P0测试收口** — P0 32-34,已完成。
5. **批次五:P1交付资产** — P1 1-18,已完成并有只读资产专项测试。
6. **批次六:规格回写** — P2 1-7已完成正式交代；P2-3 已确认降级，其余六条理由已确认合理，待下一次任务书修订回写；不实施旧行为。
