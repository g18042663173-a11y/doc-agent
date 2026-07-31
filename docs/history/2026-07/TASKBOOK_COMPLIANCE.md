# 任务书达成度核对

审计日期: 2026-07-10
审计基准: `docs/taskbook.md` 当前工作区版本
审计方式: 初次审计采用只读探针;本文件现已在 P0 实施及 P1 交付资产补齐后按最终代码、测试、固定资产与命令结果复核更新。

## 判定口径

- `✅ 已满足`: 当前仓库有实现和足够的自动证据,或明确满足任务书规定的外网阶段边界。
- `⚠️ 部分满足`: 已有实现,但验收断言仍有缺口、覆盖范围不足、文档与实现漂移,或尚缺指定人工/环境验证。
- `❌ 未满足`: 指定产物、样例或验收动作不存在。
- `[A]欠账`: 纯代码、契约、测试、样例或文档问题,Mac 阶段即可完成。
- `[B]待内网`: 必须依赖真实 NGA/内网 Skill、真实业务文件、Windows 真机、真实字体/CI 或人工终审。
- 统计按下表的“原子验收断言”计数。任务卡、章节硬要求和最终 DoD 即使互相引用,仍分别计数,因为任务书把它们定义为独立验收关口。

## 本次实跑证据

| 命令/检查 | 结果 |
| --- | --- |
| `python --version` | `Python 3.12.2` |
| `PYTHONPATH=backend python -m pytest backend/tests -q` | `300 passed in 95.29s`(P1交付资产闭环后全量回归) |
| `python scripts/verify.py` | 退出码 0;四格式 word/deck 多事实 semantic E2E 通过;`app/parsers=93.75%`, `app/ir=93.37%`, `app/lint=92.88%`, overall `89.66%`;`C0 verify passed` |
| 三份 Schema + 历史门禁 | 当前模型、快照与历史哈希一致;版本分别为 `1.0`, `1.1`, `1.4`;同版本改Schema会失败 |
| 同一文件重新解析后再组 Prompt | `parsed_at` 基于源文件 mtime 稳定;两份 DocumentIR 与 Prompt 均逐字节相同;测试 `backend/tests/test_repro_cli.py:85-127` |
| parser fixture 数量 | `samples/input/parser_matrix/manifest.json` 固定 md/docx/xlsx/pptx 各 5 类(normal/empty/corrupt/large/degraded);另有 8 页 `samples/input/项目汇报.pptx` 及逐页 expected |
| IR/expected 样例 | `word_invalid_*=11`;Deck D001-D006 由 `deck_invalid_manifest.json` 固定;`deck_lint_violation.json` 已入库;`samples/expected/manifest.json` 对全部 5 份 expected JSON 记录 SHA-256 |
| 外部资产 | `samples/input/real/` 仍为 0 个文件;本机已下载 26 个 CPython 3.12/win_amd64 wheel 并生成 hash lock/manifest,但尚未完成 Windows 真机断网安装 |
| CLI 失败探针 | parse/prompt/render/check 均非零、带码、无 `Traceback`;坏 Office 检查会落结构化报告 |

## 一、架构、分层、CLI 与跨平台

| 要求条目 | 出处(§) | 状态(✅/⚠️/❌) | 类别([A]欠账/[B]待内网) | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| A-01 模型文本必须先剥壳、Schema 校验,非法 IR 不进入渲染器(I1) | §1.3, §2.1 | ✅ 已满足 | — | `backend/app/cli/render.py:24-39`; `backend/app/ir/shell.py:108-132`; `backend/tests/test_render_cli.py:41-63,111-147` | CLI 正反例证明错误在渲染前被拦截。 |
| A-02 parsers 只产 DocumentIR,renderers 只消费 WordIR/DeckIR(I2) | §1.3 | ✅ 已满足 | — | `backend/app/cli/parse.py:21-31`; `backend/app/parsers/md_parser.py:17-99`; `backend/app/rendering/docx_renderer.py:26-51`; `backend/app/rendering/pptx_renderer.py:39-76` | 包职责与类型边界清楚。 |
| A-03 内外网差异只在 generator 与官方渲染 Skill 两处(I3) | §1.3, §6.4 | ⚠️ 部分满足 | [B]待内网 | `docs/内网接入.md:5-30`; `backend/app/generators/nga.py:7-18` | 文档设计符合,但真实 NGA/Skill 尚未接入,无法证明进内网后确实只改两处。 |
| A-04 目录职责分层一致,IR/主题/CLI 可独立运行 | §2.2 | ✅ 已满足 | — | `backend/app/{cli,ir,parsers,prompting,generators,rendering,lint,storage}`; `backend/tests/`; `scripts/`; `docs/` | 目录名与建议略有差异,但符合 §2.2 的“职责一致即可”。 |
| A-05 技术栈锁定为 Python 3.12、pydantic v2、python-docx/openpyxl/python-pptx/pytest | §2.3 | ✅ 已满足 | — | `requirements.txt:1-7`;命令 `python --version` 输出 `3.12.2` | Flask 是已批准的可选 P2 薄壳。 |
| A-06 pathlib、显式 UTF-8、subprocess 显式 UTF-8 | §2.3 跨平台卫生 | ✅ 已满足 | — | `backend/tests/test_subprocess_encoding.py:12-24`; `backend/app/cli/parse.py:5,57`; `backend/app/cli/render.py:5,24`;本轮全仓扫描未发现文本 `read_text/write_text` 漏 encoding | Office/ZIP 二进制 API 不适用文本 encoding 约束。 |
| A-07 平台差异仅留薄封装,脚本逻辑用 Python | §2.2-2.3 | ✅ 已满足 | — | `scripts/record_demo.py`; `scripts/record_demo.sh`; `scripts/record_demo.ps1`; `backend/tests/test_delivery_assets.py:214-232` | sh/ps1 仅转调同一 Python 入口,无平台业务编排;subprocess 显式 UTF-8。 |
| A-08 generator 接口签名稳定,剥壳/校验留在接口外 | §2.4 | ✅ 已满足 | — | `backend/app/generators/interface.py:8-21`; `backend/app/generators/stub.py:7-10`; `backend/app/ir/repair.py:9-16` | 接口与任务书语义一致。 |
| A-09 StubGenerator 应按 DocumentIR/规则映射,使 E2E 内容与输入相关 | §2.4, S3-5 | ✅ 已满足 | — | `backend/app/generators/stub.py:11-381`; `backend/tests/test_prompt_builder.py:153-245` | 四格式标题、段落和表格摘要确定性进入 WordIR/DeckIR;不同输入产物不同。 |
| A-10 NgaGenerator 外网阶段仅预留接口与 TODO,不猜协议 | §1.1, §2.4 | ✅ 已满足 | — | `backend/app/generators/nga.py:7-18`; `backend/app/generators/interface.py:18-21`; `docs/内网接入.md:7-20` | `NotImplementedError` 符合本阶段边界,真实接入另列 B 类。 |
| A-11 `parse.py` 入参/出参/退出码与结构化失败报告 | §2.5 | ✅ 已满足 | — | `backend/app/cli/parse.py:14-59`; `backend/tests/test_repro_cli.py:16-39`; `backend/tests/test_parse_errors.py:62-84`;本轮缺文件探针返回 `E001` 无 traceback | 支持 md/docx/xlsx/pptx。 |
| A-12 `prompt.py` 入参/出参/退出码与用户错误码 | §2.5 | ✅ 已满足 | — | `backend/app/cli/prompt.py:21-41`; `backend/tests/test_cli_failure_contract.py:49-71` | 缺失、坏JSON、目录冒充文件均返回结构化E001且无堆栈。 |
| A-13 `render.py --type word/deck` 先校验、生成 DOCX/PPTX、deck 自动 lint | §2.5 | ✅ 已满足 | — | `backend/app/cli/render.py:22-55`; `backend/tests/test_render_cli.py:14-147`; `test_cli_failure_contract.py:74-108` | 读IR、渲染、保存、deck复检异常均有目标码边界。 |
| A-14 `check.py` 支持外部 PPTX/DOCX并写 JSON/Markdown | §2.5, §6.3 | ✅ 已满足 | — | `backend/app/cli/check.py:19-58`; `backend/tests/test_cli_failure_contract.py:111-136` | 缺失/损坏/错扩展名返回E001/E003并尽量写双格式报告。 |
| A-15 `verify` 串联样例、pytest、coverage并按结果非零退出 | §2.5, §7.2 | ✅ 已满足 | — | `scripts/verify.py:29-51,54-164`;本轮 `python scripts/verify.py` 退出 0并报告覆盖率 | 契约快照防漂移缺陷另列 B-06/E-05。 |
| A-16 所有 CLI 失败均非零、带错误码且不暴露堆栈 | §2.5 | ✅ 已满足 | — | `backend/app/cli/errors.py:10-47`; `backend/tests/test_cli_failure_contract.py:38-158` | 四CLI参数错误和主要I/O错误均逐一断言退出码、错误码及无Traceback。 |

## 二、IR 契约与输入边界

| 要求条目 | 出处(§) | 状态(✅/⚠️/❌) | 类别([A]欠账/[B]待内网) | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| B-01 三份 IR 顶层都有 `ir_type`/`ir_version`,版本 Word 1.0、Document 1.0、Deck 1.4 | §3.0-3.3 | ✅ 已满足 | — | `backend/app/ir/word_ir.py:45-49`; `backend/app/ir/document_ir.py:66-72`; `backend/app/ir/deck_ir.py:599-603` | 本轮内存态 Schema 对比也确认 const 版本一致。 |
| B-02 未知字段忽略并记录 W104 | §3.0 | ✅ 已满足 | — | `backend/app/ir/common.py:8-10`; `backend/app/ir/validation.py:106-139,149-295`; `backend/tests/test_ir_validation.py:62-81,530-546,616-668` | Word/Document/Deck 与架构嵌套字段均有测试。 |
| B-03 超限内容统一“截断并 Warning” | §3.0 | ⚠️ 部分满足 | [A]欠账 | `backend/app/ir/validation.py:51,364-391`; `backend/app/ir/deck_ir.py:35,55,133-139`;本轮探针:61 字 Deck bullet `ok=True,warnings=[]`,agenda 9 条报 `D004` | Word 长文本会 W103;Deck bullet 长度不校验,agenda/数组超限是 Error 而非任务书所写自动降级。任务书 §3.0 与 D005/D006 本身也需统一口径。 |
| B-04 剥壳兼容纯 JSON、代码块、解释文字,失败附原文前 200 字 | §3.0, S1-2 | ✅ 已满足 | — | `backend/app/ir/shell.py:16-48,97-132`; `backend/tests/test_ir_shell_and_repair.py:24-108` | 额外拒绝多个 JSON与截断对象,比“取第一个”更严格且有明确 E001/D001。 |
| B-05 三份已导出 Schema 与当前模型一致 | §3.0 | ✅ 已满足 | — | `backend/app/ir/schema_export.py:14-35`; `backend/tests/test_c0_contract.py:97-105`;本轮内存态对比三份均 `match=True` | 当前工作树没有模型/Schema 内容差异。 |
| B-06 Schema 快照必须阻止改字段但不升 `ir_version` | §3.0, §7.1 | ✅ 已满足 | — | `backend/app/ir/schema_export.py:21-123`; `scripts/verify.py:29-35`; `backend/tests/test_c0_contract.py:108-185` | verify只读核验;历史哈希拒绝同版本契约变化。 |
| B-07 WordIR meta 字段、默认密级与非空 title | §3.1 | ✅ 已满足 | — | `backend/app/ir/word_ir.py:20-28`; `backend/tests/test_ir_validation.py:14-21,166-196` | classification 默认“内部公开”并产 I201。 |
| B-08 WordIR 七种 block 类型及字段约束 | §3.1 | ✅ 已满足 | — | `backend/app/ir/common.py:19-84`; `backend/app/ir/word_ir.py:31-42`; `backend/tests/test_docx_renderer.py:17-57,88-109,180-223` | heading/paragraph/两类 list/table/image/page_break 均有渲染证据。 |
| B-09 WordIR `blocks` 必填且至少 1 条 | §3.1及已确认契约 | ✅ 已满足 | — | `backend/app/ir/word_ir.py:45-49`; `backend/tests/test_c0_contract.py:39-52,108-112` | 空文档被拒绝。 |
| B-10 Word 表格规整、100x12、列宽一致性 | §3.0-3.1 | ✅ 已满足 | — | `backend/app/ir/common.py:50-74`; `backend/app/ir/word_ir.py:51-65`; `backend/tests/test_ir_validation.py:40-60`; `backend/tests/test_docx_renderer.py:225-248` | 100x12 极限回读通过。 |
| B-11 Word quote/note/image_placeholder/page_break 渲染语义 | §3.1 | ✅ 已满足 | — | `backend/app/rendering/docx_renderer.py:153-177,266-307`; `backend/tests/test_docx_renderer.py:88-109,180-223` | quote 左线、note 底色、图片框+题注、分页均有 XML 回读。 |
| B-12 Word 字体/字号/间距/边框/页眉页脚全部集中配置 | §3.1 渲染硬要求 | ⚠️ 部分满足 | [A]欠账 | `backend/app/rendering/docx_renderer.py:54-90,203-223,242-256`; `backend/app/rendering/themes/hw_theme.json:23-59` | 颜色/字体/字号/边框来自 theme,但标题段前后距、quote/note 缩进和 6.5 英寸表宽仍硬编码在 renderer,未完全单点收敛。 |
| B-13 DocumentIR source/stats/warnings/content 与三类摘要结构字段 | §3.2 | ✅ 已满足 | — | `backend/app/ir/document_ir.py:11-72`; `backend/tests/test_c0_contract.py:55-75`; `backend/tests/test_ir_sample_matrix.py:52-61` | 字段定义和基础正反例存在。 |
| B-14 DocumentIR 按 `source.format` 约束对应 content 类型 | §3.2 | ✅ 已满足 | — | `backend/app/ir/document_ir.py:104-204`; `backend/tests/test_c0_contract.py:208-244` | runtime validator与JSON Schema条件分支同时约束;契约升至1.1。 |
| B-15 DocumentIR Schema 强制 md/docx 表20行、xlsx preview 20x15等限额 | §3.2 | ✅ 已满足 | — | `backend/app/ir/document_ir.py:48-101`; `backend/tests/test_c0_contract.py:196-280` | 20行、20x15及表格规整均在模型/Schema强制。 |
| B-16 Word 修订/批注/文本框/SmartArt跳过时 warning 要含数量与位置 | §3.2, §5.4 | ✅ 已满足 | — | `backend/app/parsers/docx_parser.py:194-230`; `backend/tests/test_docx_parser.py:121-140` | 每类告警包含计数、Word XML部件位置和跳过方式。 |
| B-17 Excel 合并单元格计数、填充预览并“标注 merged” | §3.2, §5.4 | ⚠️ 部分满足 | [A]欠账 | `backend/app/parsers/xlsx_parser.py:24-28,61-68,85-96,341-364`; `backend/tests/test_dirty_samples.py:33-38` | merged_count与左上值填充已做;DocumentIR 无逐格/逐区域 merged 标记。 |
| B-18 PPTX 组合/嵌套形状递归,失败入 shape_warnings | §3.2, §5.4 | ✅ 已满足 | — | `backend/app/parsers/pptx_parser.py:150-170`; `backend/tests/test_pptx_parser.py:102-129`; `backend/tests/test_dirty_samples.py:66-67` | 正例和异常迭代器反例均覆盖。 |
| B-19 内嵌对象/图片/OLE记录存在与尺寸,不搬运二进制 | §3.2, §5.4 | ✅ 已满足 | — | `backend/app/parsers/xlsx_parser.py:562-676`;DOCX/PPTX embedding实现 | XLSX现记录sheet/锚点/宽高/part/bytes;全格式均不提取二进制,缺元数据明确标unknown。 |
| B-20 异常编码与超长单元格统一 warning/W103 | §5.4 | ✅ 已满足 | — | `backend/app/parsers/text_limits.py:6-24`;三Office parser接入 | 三格式超长正反测试:`test_xlsx_parser.py:168-184`,`test_docx_parser.py:143-163`,`test_pptx_parser.py:102-126`。 |
| B-21 超大文件 read_only、预览/画像采样、超时或超内存时报告已处理范围 | §5.4 | ✅ 已满足 | — | `backend/app/parsers/xlsx_parser.py:44-258`; `backend/tests/test_xlsx_parser.py:257-409` | >=10MB 进入可终止隔离进程;硬截止、结构化失败、EOF、未知异常和进程清理均有测试,降级写已处理范围。 |
| B-22 DeckIR meta、1-30页约束 | §3.3 | ✅ 已满足 | — | `backend/app/ir/deck_ir.py:12-20,599-603` | title/classification/theme默认及页数上限落在模型。 |
| B-23 DeckIR 11种 layout 字段完整 | §3.3 | ✅ 已满足 | — | `backend/app/ir/deck_ir.py:23-248,353-478,541-596`; `backend/tests/test_c0_contract.py:115-146` | 含增强 table/chart 与 architecture_diagram。 |
| B-24 table/chart/architecture 内容一致性与引用校验 | §3.3 | ✅ 已满足 | — | `backend/app/ir/deck_ir.py:155-218,315-350,438-478`; `backend/tests/test_ir_validation.py:299-376,440-528,591-644,748-932` | 表格合并冲突、图表维度/结论、edge/group引用均有反例。 |
| B-25 Deck 单条 bullet 60字、agenda超8自动降级等内容上限 | §3.0, §3.3 | ⚠️ 部分满足 | [A]欠账 | `backend/app/ir/deck_ir.py:33-40,52-56`;本轮探针:61字 bullet无告警,agenda 9条映射 `D004` | 数量上限多数由 Schema拒绝;60字只在后置 lint中近似检测,没有 IR warning/截断。 |
| B-26 脱敏真实 docx/xlsx/pptx各至少3个纳入 fixtures | §5.4 | ❌ 未满足 | [B]待内网 | `QUESTIONS.md:5-7`;命令 `find samples/input/real ...` 返回0 | synthetic 10个结构样例不能替代真实业务文件。 |

## 三、错误码与合规码逐码核对

| 要求条目 | 出处(§) | 状态(✅/⚠️/❌) | 类别([A]欠账/[B]待内网) | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| C-01 E001 JSON/剥壳失败 | §3.1 | ✅ 已满足 | — | `backend/app/ir/shell.py:97-114`; `backend/tests/test_ir_shell_and_repair.py:46-52,82-89`; `backend/tests/test_word_samples.py:19-26,50-61` | 触发测试含无JSON、截断、坏JSON。 |
| C-02 E002 缺/空 meta.title | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:394-414`; `backend/tests/test_ir_validation.py:14-21`; `backend/tests/test_word_samples.py:21,50-61` | 真正触发并定位。 |
| C-03 E003 未知 block.type | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:401-403`; `backend/tests/test_word_samples.py:22,50-61` | 反例文件进入统一校验。 |
| C-04 E004 Word表格不规整/超限 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:403-419`; `backend/tests/test_ir_validation.py:40-60`; `backend/tests/test_word_samples.py:23,50-61` | 行列不齐触发。 |
| C-05 E005 heading.level越界 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:405-406`; `backend/tests/test_word_samples.py:24,50-61` | 文件反例触发。 |
| C-06 E006 空列表/空blocks/语义空块 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:407-410`; `backend/tests/test_ir_validation.py:23-38,938-951`; `backend/tests/test_word_samples.py:25,50-61` | 扩展覆盖已确认的空 WordIR。 |
| C-07 W101 标题跳级并就近降级 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:338-352`; `backend/tests/test_ir_validation.py:83-119`; `backend/tests/test_word_samples.py:29,64-74` | 正反例均有。 |
| C-08 W102 空段落跳过 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:325-336`; `backend/tests/test_ir_validation.py:122-141`; `backend/tests/test_word_samples.py:30,64-74` | 触发后仍返回合法 IR。 |
| C-09 W103 超长段落/单元格截断 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:364-391`; `backend/tests/test_ir_validation.py:144-163`; `backend/tests/test_word_samples.py:31,64-74` | WordIR路径有正例;parser长单元格缺口另列B-20。 |
| C-10 W104 未知字段忽略并告警 | §3.0 | ✅ 已满足 | — | `backend/app/ir/validation.py:106-139`; `backend/tests/test_ir_validation.py:62-81,530-546,646-668`; `backend/tests/test_word_samples.py:32,64-74` | 三份IR均覆盖。 |
| C-11 I201 默认密级提示 | §3.1 | ✅ 已满足 | — | `backend/app/ir/validation.py:303-312`; `backend/tests/test_ir_validation.py:166-196`; `backend/tests/test_word_samples.py:33,64-74` | 有/无显式classification正反例。 |
| C-12 D001 Deck JSON/剥壳失败 | §3.3 | ✅ 已满足 | — | `backend/app/ir/shell.py:126-132`; `backend/tests/test_ir_shell_and_repair.py:55-61,92-100` | 无JSON与多JSON均触发。 |
| C-13 D002 Deck缺 meta.title | §3.3 | ✅ 已满足 | — | `backend/app/ir/validation.py:422-440`; `backend/tests/test_ir_validation.py:215-222` | 触发测试存在。 |
| C-14 D003 未知 layout | §3.3 | ✅ 已满足 | — | `backend/app/ir/validation.py:429-430`; `backend/tests/test_ir_validation.py:199-212`; `backend/tests/test_ir_sample_matrix.py:35-49` | 单元+文件反例。 |
| C-15 D004 layout缺字段/内容矛盾 | §3.3 | ✅ 已满足 | — | `backend/app/ir/validation.py:435-440`; `backend/tests/test_ir_validation.py:224-231,440-528,591-614,701-745` | 覆盖缺字段、阈值、架构引用、语义空内容。 |
| C-16 D005 Deck表格不规整/越界 | §3.3 | ✅ 已满足 | — | `backend/app/ir/validation.py:431-432`; `backend/tests/test_ir_validation.py:233-376,748-783`; `backend/tests/test_ir_sample_matrix.py:38-49` | 旧表/增强表均覆盖。 |
| C-17 D006 bullets超条数 | §3.3 | ✅ 已满足 | — | `backend/app/ir/validation.py:433-434`; `backend/tests/test_ir_validation.py:378-398` | 触发测试存在。 |
| C-18 HW-E01 任一页页脚缺密级 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:54-75`; `backend/tests/test_pptx_lint.py:137-167`;健康反例 `:21-39` | 还验证密级文字必须在页脚区域。 |
| C-19 HW-E02 白名单外字体 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:123-139,271-328,759-781`; `backend/tests/test_pptx_lint.py:525-576` | 文本框、表格单元格及chart字体对象均覆盖。 |
| C-20 HW-E03 动画/切换 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:76-78`; `backend/tests/test_pptx_lint.py:300-318`;健康产物 `:21-39` | XML timing/transition命中。 |
| C-21 HW-W01 小字号/字号种类 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:123-139,394-421`; `backend/tests/test_pptx_lint.py:525-576` | 按当前theme阈值检查文本框、表格、chart及单页字号种类;旧10.5pt冲突留P2规格回写。 |
| C-22 HW-W02 非主题色 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:141-205,218-328`; `backend/tests/test_pptx_lint.py:578-612`及原专项测试 | 普通形状填充/线条、表格XML颜色、chart系列/文字均收集。 |
| C-23 HW-W03 要点>7或单条>60 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:424-436,783-785`; `backend/tests/test_pptx_lint.py:614-636` | 同时识别字符前缀与PowerPoint原生buChar/buAutoNum/buBlip。 |
| C-24 HW-W04 表格>12行或>8列 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:145-157`; `backend/tests/test_pptx_lint.py:300-318`;健康表格 `backend/tests/test_pptx_renderer.py:58-81` | 触发和健康路径均有。 |
| C-25 HW-W05 总页数>30 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:60-69`; `backend/tests/test_pptx_lint.py:300-318`;健康产物 `:21-39` | 触发测试为31页。 |
| C-26 HW-W06 12栏/8pt基线吸附 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:439-468`; `test_pptx_lint.py:638-661` | 只读PPTX实际left/top/width/height对12栏/8pt;即使伪造renderer name仍命中。 |
| C-27 HW-W07 页边/间距/重叠 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:484-558`; `backend/tests/test_pptx_lint.py:664-759` | 所有内容统一使用theme四边距与实际包围盒;无renderer零边距特例;合法背景/容器有反向保护。 |
| C-28 HW-W08 标题/页脚关键框坐标 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:482-508`; `backend/tests/test_pptx_lint.py:72-104`; `backend/tests/test_pptx_renderer.py:167-202` | theme改坐标的回归也覆盖。 |
| C-29 HW-W09 正文/背景对比度<4.5 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:632-706,850-920`; `backend/tests/test_pptx_lint.py:700-741` | table/chart可测纯色按4.5:1计算;图片/复杂背景不再假通过而输出人工复核warning。 |
| C-30 HW-I01 agenda与section数量不一致 | §6.3 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:613-642`; `backend/tests/test_pptx_lint.py:545-591` | 一致/不一致正反例均有。 |

## 四、18张任务卡逐卡验收

| 要求条目 | 出处(§) | 状态(✅/⚠️/❌) | 类别([A]欠账/[B]待内网) | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| D-01 S1-1 WordIR定稿、校验器、10个非法样例、Schema入库 | §4 S1-1 | ✅ 已满足 | — | `backend/app/ir/word_ir.py:20-66`; `backend/tests/test_word_samples.py:13-74`;命令统计 `word_invalid_*=11`; `backend/schemas/word_ir.schema.json` | 6个Error+4个Warning+1个Info文件样例。 |
| D-02 S1-2 三形态剥壳、最多2次修复、稳定失败码 | §4 S1-2 | ✅ 已满足 | — | `backend/app/ir/shell.py:19-105`; `backend/app/ir/repair.py:19-54`; `backend/tests/test_ir_shell_and_repair.py:24-183` | 可修复/不可修复/截断/多JSON均有测试。 |
| D-03 S1-3 标题1-4、段落、两级列表、quote/note、分页、页眉页脚且可编辑 | §4 S1-3 | ✅ 已满足 | — | `backend/app/rendering/docx_renderer.py:26-177`; `backend/tests/test_docx_renderer.py:17-109,149-223` | 回读证明文本、样式、页码域、边框存在;真实Word视觉另列B类。 |
| D-04 S1-4 表头/列宽/重复表头/W103/100x12 | §4 S1-4 | ✅ 已满足 | — | `backend/app/rendering/docx_renderer.py:180-263`; `backend/tests/test_docx_renderer.py:112-146,225-248`; `backend/tests/test_ir_validation.py:144-163` | 极限表不崩、XML有重复表头。 |
| D-05 S1-5 三正样例、五失败样例及文案评审 | §4 S1-5 | ✅ 已满足 | — | `backend/tests/test_word_samples.py:13-74`; `samples/ir/word_valid_*.json`; `docs/reviews/失败文案评审记录.md`; `backend/tests/test_delivery_assets.py:200-211` | E/W/I/D 已逐码留评审记录;D006 建议措辞的局限如实登记,人工签字栏未伪造。 |
| D-06 S1-6 golden、README、新人10分钟复现 | §4 S1-6 | ✅ 已满足 | — | `samples/output/word/`; `samples/expected/word_official_outputs.expected.json`; `README.md`; `docs/reviews/新人复现记录.md`; `backend/tests/test_delivery_assets.py:86-108,200-232` | 三份官方 DOCX 用解析库回读结构 golden;复现记录明确是自动侧预审,不冒充真实新人签收。 |
| D-07 S2-1 Markdown往返不丢结构 | §5 S2-1 | ✅ 已满足 | — | `backend/app/parsers/md_parser.py:17-153`; `backend/tests/test_md_parser.py:14-56` | md→DocumentIR→WordIR→DOCX 回读标题和表格。 |
| D-08 S2-2 DOCX双策略、列表、20行截断、不支持项全部warnings | §5 S2-2 | ✅ 已满足 | — | `backend/app/parsers/docx_parser.py:25-238`; `backend/tests/test_docx_parser.py:18-203` | 不支持项有部件位置;图片按v1契约记录存在与尺寸,不搬运二进制。 |
| D-09 S2-3 XLSX摘要字段齐、10MB文件<5秒 | §5 S2-3 | ✅ 已满足 | — | `backend/app/parsers/xlsx_parser.py:40-138`; `backend/tests/test_xlsx_parser.py:222-273` | fixture为30,000行真实worksheet数据且包体>10MB,实测断言<5秒。 |
| D-10 S2-4 PPTX 8页逐页摘要正确、动画warning | §5 S2-4 | ✅ 已满足 | — | `samples/input/项目汇报.pptx`; `samples/expected/项目汇报.pptx.expected.json`; `backend/tests/test_delivery_assets.py:50-71`;原动画测试 `backend/tests/test_pptx_parser.py` | 固定 8 页样例含表格、原生图表、两页备注及空白页,逐页摘要和页序均有断言。 |
| D-11 S2-5 四段Prompt、优先级截断、est_chars、确定性 | §5 S2-5 | ✅ 已满足 | — | `backend/app/prompting/builder.py:16-20,43-61,116-128`; `templates/ir_generation.txt:1-21` | est_chars明确;few-shot从入库正例加载并校验;parsed_at归一化;任务书统一裸JSON。 |
| D-12 S2-6 四格式demo、每格式5类解析测试、一命令文件到DOCX | §5 S2-6 | ✅ 已满足 | — | `samples/input/parser_matrix/manifest.json`; `backend/tests/test_delivery_assets.py:22-47`; `backend/tests/test_repro_cli.py:85-186` | manifest 固定四格式各 normal/empty/corrupt/large/degraded,测试实际调用解析器并核对 E001/warning;原 E2E 保留。 |
| D-13 S3-1 风格规范+theme、来源/近似声明、零硬编码、评审通过 | §6 S3-1 | ✅ 已满足 | — | `backend/app/rendering/themes/hw_theme.json`; `docs/风格规范.md`; `docs/reviews/主题校准评审记录.md`; `backend/tests/test_delivery_assets.py:200-232` | 文档已记录 SOURCE_FILE_SPEC 实测优先级、`#C7000B` 与完整 token;人工签收仍留空,没有伪造。 |
| D-14 S3-2 五种P0版式渲染后零Error | §6 S3-2 | ✅ 已满足 | — | `backend/app/rendering/pptx_renderer.py:79-316`; `backend/tests/test_pptx_renderer.py:19-81` | cover/agenda/section/title_bullets/table可编辑且lint零Error。 |
| D-15 S3-3 十一版式、原生chart、image明确降级 | §6 S3-3 | ✅ 已满足 | — | `backend/app/rendering/pptx_renderer.py:39-71,317-924`; `backend/tests/test_pptx_renderer.py:287-511`; `backend/tests/test_ir_sample_matrix.py:13-32` | chart为python-pptx原生对象,image为明确占位,架构骨架为独立可编辑对象。 |
| D-16 S3-4 全规则落码、每条正反例、双格式报告 | §6 S3-4 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:54-920`; `backend/tests/test_pptx_lint.py:21-741` | 规则作用域盲区已关闭;指定违规演示fixture仍单列P1 F-19,不再冒充功能缺陷。 |
| D-17 S3-5 md摘要经stub到5-12页可编辑PPTX并lint | §6 S3-5 | ✅ 已满足 | — | `backend/app/generators/stub.py:147-203`; `scripts/demo_e2e.py:40-81`; `test_repro_cli.py:158-237` | md标题/事实进入6页DeckIR及可编辑PPTX,lint通过。 |
| D-18 S3-6 两替换点、环境变量、内网自测/离线指引,他人独立执行 | §6 S3-6 | ⚠️ 部分满足 | [B]待内网 | `docs/内网接入.md:1-65`; `backend/tests/test_docs.py:8-17` | 文档自动检查通过;“评审通过/他人在黄区独立执行”没有内网实测记录。 |

## 五、测试、主题、视觉与内网验收

| 要求条目 | 出处(§) | 状态(✅/⚠️/❌) | 类别([A]欠账/[B]待内网) | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| E-01 解析器每格式至少5例且覆盖正常/空/坏/超大/降级 | §7.1, S2-6 | ✅ 已满足 | — | `samples/input/parser_matrix/manifest.json`; `backend/tests/test_delivery_assets.py:22-47` | 四格式各 5 类且逐例实跑;损坏件命中 E001,超长/降级件命中声明的 warning。 |
| E-02 IR校验有正例和全部E/W/I/D码反例 | §7.1 | ✅ 已满足 | — | `backend/tests/test_word_samples.py:13-74`; `backend/tests/test_ir_validation.py:14-951`; `backend/tests/test_ir_shell_and_repair.py:46-100` | 逐码证据见C-01~C-17。 |
| E-03 lint每条规则正反例至少1个 | §7.1 | ✅ 已满足 | — | `backend/tests/test_pptx_lint.py:21-660` | W06/W08/W09等有显式正反;E03/W04/W05共享健康deck作为不触发例。实现作用域盲区已单列。 |
| E-04 渲染golden使用解析库回读结构事实 | §1.1, §7.1 | ✅ 已满足 | — | `backend/tests/test_docx_renderer.py:17-248`; `backend/tests/test_pptx_renderer.py:19-511` | 不比二进制,断言文本、样式、表格、chart、连接符等。 |
| E-05 契约测试能防止Schema和版本悄悄漂移 | §7.1 | ✅ 已满足 | — | `backend/tests/test_c0_contract.py:108-185`; `backend/app/ir/schema_export.py:62-123` | 快照文件、模型和版本历史三重核验;故障注入均非绿。 |
| E-06 四格式CLI级parse→prompt→render→check E2E | §7.1 | ✅ 已满足 | — | `scripts/verify.py:62-238`; `backend/tests/test_repro_cli.py:130-151,222-264` | 8条链路逐项核对标题/正文/列表/表头/数据/sheet/slide/notes从source进入目标IR并出现在最终Office产物;单marker负例会挂。 |
| E-07 保留一条文件到PPTX完整演示链路 | §7.1, §7.3 | ✅ 已满足 | — | `backend/tests/test_repro_cli.py:113-141`; `scripts/demo_e2e.py:35-66` | quarterly/md→PPTX为8页可编辑原生对象。 |
| E-08 覆盖率核心三包≥80%、整体≥70% | §7.1 | ✅ 已满足 | — | P1最终verify: parsers 93.75%, IR 93.37%, lint 92.88%, overall 89.66%; `scripts/verify.py:25-26,143-164` | 门槛和实测均满足。 |
| E-09 一键verify在测试失败/覆盖率不足/lint失败时非零 | §7.2 | ✅ 已满足 | — | `scripts/verify.py:41-51,137-160`; `backend/tests/test_c0_contract.py:174-190` | 本轮退出0;代码分支明确聚合失败条件。 |
| E-10 同一输入文件重复parse+prompt结果逐字节一致 | §7.3 多格式输入,S2-5 | ✅ 已满足 | — | `backend/app/parsers/source_metadata.py:7-11`; `backend/tests/test_repro_cli.py:85-127` | `parsed_at` 来自稳定源文件mtime;DocumentIR与Prompt两项均逐字节一致。 |
| E-11 开发环境Python 3.12 | §1.2, §2.3 | ✅ 已满足 | — | 本轮 `python --version`=`Python 3.12.2` | 与基线一致。 |
| E-12 requirements版本锁定 | §2.3, §7.4 | ✅ 已满足 | — | `requirements.txt:1-7` | 所有直接依赖固定精确版本。 |
| E-13 requirements与wheelhouse带hash | §7.4 | ✅ 已满足 | — | `requirements-win312.lock`; `docs/wheelhouse-win312-manifest.json`; `scripts/hash_wheelhouse.py`; `backend/tests/test_delivery_assets.py:160-181` | 26 个直接/传递依赖均精确锁版并带 SHA-256;Mac 上 `pip --dry-run --no-index --require-hashes` 完整解析通过。 |
| E-14 Windows平台wheelhouse已构建且可断网安装 | §2.3, §7.4 | ❌ 未满足 | [B]待内网 | 本机 `wheelhouse/` 有 26 个目标 wheel;`requirements-win312.lock`; `docs/wheelhouse-win312-manifest.json`; `docs/验收手册.md` | 目标 wheel 集和 hash 已备齐,但“可断网安装”仍必须在干净 Windows/Python 3.12 真机证明。 |
| E-15 Windows执行verify.ps1、真实Word/PPT可打开编辑并留截图 | §7.4 | ❌ 未满足 | [B]待内网 | `verify.ps1:1-13`; `docs/验收手册.md:19-32`; `QUESTIONS.md:8-13` | 无Windows真机、字体、Office和截图证据。 |
| E-16 主红`#C7000B` | §6.1 | ✅ 已满足 | — | `backend/app/rendering/themes/hw_theme.json:4-5`; `backend/tests/test_theme.py:17-24` | 与当前任务书主红一致。 |
| E-17 文字/背景/字体/字号精确符合§6.1 | §6.1 | ⚠️ 部分满足 | [A]欠账 | 任务书`docs/taskbook.md:413-416`;实际theme `backend/app/rendering/themes/hw_theme.json:11-52` | 实际按后续SOURCE_FILE_SPEC使用#1D1D1A/#666、微软雅黑/Arial、14/12/11/10/9/8pt;任务书仍写#1F1F1F/#333/#595/#8C、40/28/16/10.5pt等旧口径。需回写权威规格或回退实现,不能同时判满足。 |
| E-18 16:9、边距、标题区/关键坐标精确符合§6.1 | §6.1 | ⚠️ 部分满足 | [A]欠账 | 任务书`docs/taskbook.md:417,419`;实际theme `backend/app/rendering/themes/hw_theme.json:60-71,97-117` | 实际13.34x7.5、左右0.57/上0.29/下0.5、标题0.57/0.333/12.2/0.333;任务书仍是13.33、0.6、0.6/0.5/12.13/1.0。 |
| E-19 12栏网格+8pt baseline | §6.1 | ✅ 已满足 | — | `backend/app/rendering/themes/hw_theme.json:73-79`; `backend/app/lint/pptx_lint.py:439-468`; `test_pptx_lint.py:42-69,638-661` | token、基础正反例和renderer实际几何反例齐;不再存在自报坐标豁免。 |
| E-20 段间≥8pt、卡片gap 0.3in、块到页边≥0.4in | §6.1 | ⚠️ 部分满足 | [A]欠账 | `backend/app/rendering/themes/hw_theme.json:77-78,226-243`;任务书`docs/taskbook.md:420` | 页边0.4满足;cards gap实际0.25in,min_gap实际0.08in,与任务书字面值不一致。 |
| E-21 正文/背景对比度≥4.5:1 | §6.1 | ✅ 已满足 | — | `backend/app/rendering/themes/hw_theme.json:347-355`; `backend/app/lint/pptx_lint.py:511-534`; `backend/tests/test_pptx_lint.py:107-134` | 基础检测和token齐;复杂背景盲区见C-29。 |
| E-22 页脚左密级/中版权/右当前总页码 | §6.1,源文件实测口径 | ✅ 已满足 | — | `backend/app/rendering/themes/hw_theme.json:80-95,109-117`; `backend/app/rendering/pptx_renderer.py:945-970`; `backend/tests/test_pptx_renderer.py:261-267` | 每页固定绘制。 |
| E-23 禁动画/切换/阴影/渐变/真实logo/白名单外字体 | §6.1 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:76-80,122-142`; `backend/tests/test_pptx_renderer.py:270-285`; `backend/tests/test_pptx_lint.py:137-153,300-318` | renderer静态测试禁add_picture/shadow/gradient;字体与动画可拦。 |
| E-24 chart为可编辑python-pptx原生图表 | §6.2, S3-3 | ✅ 已满足 | — | `backend/app/rendering/pptx_renderer.py:408-500`; `backend/tests/test_pptx_renderer.py:287-390` | bar/line/pie、轴、标签、阈值、侧栏均为原生/独立对象。 |
| E-25 风格规范记录当前真实来源与校准状态 | S3-1, §6.1 | ✅ 已满足 | — | `docs/风格规范.md`; `docs/reviews/主题校准评审记录.md`; `backend/app/rendering/themes/hw_theme.json`; `backend/tests/test_delivery_assets.py:214-232` | 已记录 SOURCE_FILE_SPEC 实测真值优先于早期规范近似值,并同步颜色、字体、字号、尺寸、边距和页脚。 |
| E-26 黄区接入文档包含两替换点、不动清单、环境变量、自测顺序、安全约定 | §6.4 | ✅ 已满足 | — | `docs/内网接入.md:5-65`; `backend/tests/test_docs.py:8-17` | 外网可写部分齐全。 |
| E-27 PPTX Windows视觉终审 | §6.5, §10 | ❌ 未满足 | [B]待内网 | `docs/验收手册.md:25-32`; `QUESTIONS.md:11-13`; `VISUAL_AUDIT.md`为模型/Mac诊断,不是Windows人工签收 | 需真实字体+PowerPoint人工检查观感、压字、可编辑性。 |
| E-28 样例产物内容语义人工抽查 | §5.3, §10 | ❌ 未满足 | [B]待内网 | `docs/taskbook.md:380,568`;无人工签收记录 | 应结合真实模型/真实材料核对失真与编造,自动测试不能替代。 |

## 六、最终交付、五件套与附录样例

| 要求条目 | 出处(§) | 状态(✅/⚠️/❌) | 类别([A]欠账/[B]待内网) | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| F-01 交付1:CLI Word/PPTX主流程+stub断网演示 | §10.1 | ✅ 已满足 | — | `scripts/demo_e2e.py:40-81`; `backend/tests/test_repro_cli.py:130-237`; `test_cli_failure_contract.py:38-158` | 两主流程内容贯通;失败带码且无堆栈。 |
| F-02 交付2:三份IR文档+Schema+正反样例+契约保护 | §10.2 | ✅ 已满足 | — | `backend/schemas/`; `schema_history.json`; `samples/ir/document_*`; `samples/ir/deck_invalid_manifest.json`; `samples/expected/`; `test_c0_contract.py:97-280`; `test_delivery_assets.py:74-98` | P0契约保护与 P1 正反样例/expected 资产均已关闭。 |
| F-03 交付3:四解析器+样例+warnings降级清单 | §10.3 | ✅ 已满足 | — | `backend/app/parsers/`; `samples/input/parser_samples/`; `samples/input/synthetic/`;parser P0测试 | P0的定位、长文本、OLE与资源预算缺口均关闭;真实语料仍属B类。 |
| F-04 交付4:四段Prompt模板、截断、确定性 | §10.4 | ✅ 已满足 | — | `backend/app/prompting/templates/ir_generation.txt:1-21`; `builder.py:31-256`; `test_prompt_builder.py:12-245` | est_chars、样例few-shot、裸JSON和跨parse确定性齐。 |
| F-05 交付5:DOCX集中样式、失败提示、3官方样例 | §10.5 | ✅ 已满足 | — | `backend/app/rendering/docx_renderer.py`; `backend/app/ir/report.py`; `samples/output/word/`; `samples/expected/word_official_outputs.expected.json`; `backend/tests/test_delivery_assets.py:101-108` | 三份官方 DOCX、结构 expected、主题红/旧蓝反断言和失败提示齐全;Word 专属布局常量口径另见 P2 B-12。 |
| F-06 交付6:theme+PPTX renderer十/十一版式,chart原生,image可降级 | §10.6 | ✅ 已满足 | — | `backend/app/rendering/pptx_renderer.py:39-924`; `samples/ir/deck_valid_full.json`; `backend/tests/test_ir_sample_matrix.py:13-32` | 当前为11版式,是任务书10版式交付物的兼容超集。 |
| F-07 交付7:合规检查器+JSON/Markdown+外部复检 | §10.7 | ✅ 已满足 | — | `backend/app/lint/pptx_lint.py:18-920`; `backend/app/cli/check.py:19-58`;相关CLI/lint测试 | 外部坏包有结构化报告;规则作用域P0盲区全部关闭。 |
| F-08 交付8:单元/契约/E2E、coverage、一键verify | §10.8 | ✅ 已满足 | — | P1最终 `300 passed`; `scripts/verify.py:247-301`; `test_c0_contract.py:382-436` | schema只读门禁、多事实E2E和coverage门槛均进入一键验收;外部VERIFY_RUNNING和低覆盖不能绕过。fixture资产由 `test_delivery_assets.py` 只读校验。 |
| F-09 交付9:README/使用说明/内网接入/验收手册 | §10.9 | ✅ 已满足 | — | `README.md`; `docs/使用说明.md`; `docs/内网接入.md`; `docs/验收手册.md`; `backend/tests/test_delivery_assets.py:214-232` | Word/PPTX 主流程、资产生成、hash lock、verify 与人工边界已同步。 |
| F-10 交付10:样例、结果、命令成功/失败截图、录屏脚本 | §10.10 | ✅ 已满足 | — | `samples/demo/logs/`; `samples/demo/screenshots/`; `samples/demo/recording_steps.md`; `samples/demo/manifest.json`; `scripts/record_demo.py`; `backend/tests/test_delivery_assets.py:184-197` | 实跑 Word/Deck 成功及 D003 失败,两张 1600x900 截图和命令日志均有 SHA-256;Windows Office 录屏仍属于真机人工步骤。 |
| F-11 交付11:真实脱敏docx/xlsx/pptx各≥3 | §10.11 | ❌ 未满足 | [B]待内网 | `samples/input/real/`为0; `QUESTIONS.md:5-7` | 必须业务侧提供。 |
| F-12 交付12自动部分:快照/修复/lint W06-W09/边界降级契约 | §10.12 | ✅ 已满足 | — | schema门禁、`repair.py`, `pptx_lint.py:439-706`, parser资源/降级实现及测试 | 自动侧P0 false-green已关闭;真实文件/Windows/视觉终审仍按B类保留。 |
| F-13 交付12环境部分:Windows离线验收记录入库 | §10.12 | ❌ 未满足 | [B]待内网 | `requirements-win312.lock`; `docs/wheelhouse-win312-manifest.json`; `QUESTIONS.md:8-10`;尚无 Windows 安装/Office 截图 | wheel 与 hash 已备齐,仍需真机完成断网安装、`verify.ps1`、Word/PPT 可编辑性和截图。 |
| F-14 每张任务卡五件套:代码+样例+失败提示+最小测试+文档 | §1.1, §10 DoD | ✅ 已满足 | — | `docs/任务卡交付索引.md`; `backend/tests/test_delivery_assets.py:200-211` | S1-1 至 S3-6 共 18 行逐卡链接代码、样例、失败提示、最小测试和文档;外部人工终审仍按 B 类单列。 |
| F-15 附录B主演示`quarterly_report.md` | 附录B | ✅ 已满足 | — | `samples/input/quarterly_report.md`; `backend/tests/test_md_parser.py:14-56` | 覆盖标题、列表、表格并进入E2E。 |
| F-16 附录B指定`需求说明.docx`、`销售台账.xlsx`、`项目汇报.pptx(8页)` | 附录B | ✅ 已满足 | — | `samples/input/需求说明.docx`; `samples/input/销售台账.xlsx`; `samples/input/项目汇报.pptx`; `samples/expected/appendix_b_document_ir.expected.json`; `backend/tests/test_delivery_assets.py:50-71` | 三个固定路径样例均入库并匹配 DocumentIR 结构 expected;PPTX 恰为 8 页。 |
| F-17 附录B Word invalid 10个 | 附录B | ✅ 已满足 | — | 命令统计`word_invalid_*=11`; `backend/tests/test_word_samples.py:19-74` | 数量超额且覆盖全部E/W/I。 |
| F-18 附录B Deck invalid 6个 | 附录B | ✅ 已满足 | — | `samples/ir/deck_invalid_d001_*` 至 `deck_invalid_d006_*`; `samples/ir/deck_invalid_manifest.json`; `backend/tests/test_delivery_assets.py:74-83` | D001-D006 各有稳定入库反例并逐码验证。 |
| F-19 附录B `deck_lint_violation.json` | 附录B | ✅ 已满足 | — | `samples/ir/deck_lint_violation.json`; `.inject.json`; `scripts/make_lint_violation.py`; `samples/output/deck/deck_lint_violation.pptx`; `backend/tests/test_delivery_assets.py:145-157` | 合法 IR 渲染后在 PPTX 层注入真实违规,稳定命中声明的 HW 码。 |
| F-20 附录B `samples/expected/`结构基线 | 附录B, §7.3 | ✅ 已满足 | — | `samples/expected/*.expected.json`; `samples/expected/manifest.json`; `samples/expected/README.md`; `backend/tests/test_delivery_assets.py:86-142` | expected 保存可审阅结构事实而非脆弱二进制 hash;manifest 逐文件记录 SHA-256。 |
| F-21 附录B `deck_valid_full.json`十一版式 | 附录B | ✅ 已满足 | — | `samples/ir/deck_valid_full.json`; `backend/tests/test_ir_sample_matrix.py:18-32` | 可验证、可渲染、lint零Error。 |
| F-22 附录A.2与正文/实现同步 | 附录A.2 | ✅ 已满足 | — | `docs/taskbook.md` 附录 A.2; `backend/tests/test_delivery_assets.py:214-232` | DeckIR v1.4 与 python-pptx 原生 chart 已记为已决;仅保留历史、DOCX 图片透传和内网 Skill 协议等真实未决项。 |
| F-23 内网渲染Skill真实调用形态并完成接入 | 附录A.2, §6.4 | ❌ 未满足 | [B]待内网 | `docs/taskbook.md:596`; `docs/内网接入.md:11-13`; `backend/app/generators/nga.py:15-18` | 协议、鉴权、输入输出和Skill形态外网未知,不能伪造完成。 |

## 汇总

| 统计项 | 数量 |
| --- | ---: |
| 原子验收条目 | 141 |
| ✅ 已满足 | 124 |
| ⚠️ 部分满足 | 9 |
| ❌ 未满足 | 8 |
| [A] Mac阶段欠账(部分+未满足) | 7 |
| [B] 待内网/真实环境/外部人工(部分+未满足) | 10 |

## [A] Mac阶段剩余欠账

P0 34项与 P1 18项均已关闭。剩余7个[A]原子条目全部属于 `TASKBOOK_GAP_PLAN.md` 的 P2 建议降级/规格回写:后续 SOURCE_FILE_SPEC 已替代的旧视觉 token、结构超限应报错还是静默截断的口径、合并区域逐格标记,以及 Word 专属布局常量是否必须进入共享 theme。它们不是本轮“缺交付资产”遗留。

## [B] 留到内网/真实环境的事项

1. 接入真实NGA/codeagent与官方渲染Skill,验证I3“只改两处”和S3-6他人独立执行。
2. 提供并回归脱敏真实docx/xlsx/pptx各至少3个。
3. 在干净断网Windows+Python3.12安装已生成并带 hash 的 wheelhouse,跑`verify.ps1`,用Word/PowerPoint确认可编辑并留截图。
4. 使用真实微软雅黑/HarmonyOS/CI环境做PPTX视觉终审,并对真实模型/真实材料产物做人工语义抽查。
