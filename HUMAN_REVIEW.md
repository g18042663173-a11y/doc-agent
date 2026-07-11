# 人工确认与验收清单

生成日期: 2026-07-09
仓库状态依据: `PROGRESS.md`, `QUESTIONS.md`, `docs/taskbook.md` 附录 A.2, 全仓库关键词扫描, 一次临时 schema 快照破坏验证, 以及 `AUDIT.md` 的逐条硬性要求审计。

## 先看结论

不要直接按“自动测试通过”收货。当前自动测试能证明:IR/schema、stub 链路、DOCX/PPTX 渲染、四格式构造样例解析、Prompt 结构化截断、PPTX lint 全部规则码、CLI 复检、FG-10 主题化版式坐标与覆盖率门禁可运行。但以下人工项仍不能跳过:

1. Windows 离线真机验收。
2. 真实脱敏 docx / xlsx / pptx 语料解析。
3. PowerPoint/Word 人工视觉与语义终审。

当前 `AUDIT.md` 的自动侧 FALSE-GREEN 为 0 条;剩余风险均属于下方人工验证或外部输入。

## 本次严格审计新增 FALSE-GREEN

详见 `AUDIT.md` 的 FALSE-GREEN 汇总。上一轮新标出的 19 条表面绿已全部关闭;当前自动侧残留 0 条。

## 证据与扫描结果

### 已读证据

- `PROGRESS.md`: 记录 S1-1 到 S3-6 的实现与测试结果。
- `QUESTIONS.md`: 记录真实语料、Windows 真机、视觉终审三项人工待办。
- `docs/taskbook.md:589-595`: 附录 A.2 五个仍需导师/内网确认的问题。

### 快照测试拦截验证

【操作】临时把 `backend/schemas/word_ir.schema.json` 中 schema title 从 `WordIR` 改为 `WordIR_MUTATED`,然后运行:

```bash
python3 -m pytest backend/tests/test_c0_contract.py::test_schema_files_match_current_models -q
```

【结果】会挂。失败信息显示 `{'title': 'WordIR_MUTATED'} != {'title': 'WordIR'}`。
【还原】已执行:

```bash
git checkout -- backend/schemas/word_ir.schema.json
```

还原后 `git status --short --branch` 不再显示 schema 改动。结论:Schema 快照测试会拦截已提交 schema 与当前模型不一致。

### TODO / FIXME 扫描结果

| 文件:行号 | 内容摘要 | 处理状态 |
| --- | --- | --- |
| `QUESTIONS.md:7` | 真实语料 TODO | 人工待办 |
| `QUESTIONS.md:10` | Windows 离线验收 TODO | 人工待办 |
| `QUESTIONS.md:13` | 内网字体/CI 校准 TODO | 人工待办 |
| `AGENTS.md:34` | 遇阻塞写 QUESTIONS.md + TODO 的流程要求 | 运行手册要求 |
| `docs/taskbook.md:46` | NGA 仅预留接口与 TODO | `backend/app/generators/nga.py` 已创建;真实协议仍待内网 |
| `docs/taskbook.md:102` | 目录建议中 `nga.py` 仅接口与 TODO | `backend/app/generators/nga.py` 已创建 |
| `docs/taskbook.md:143` | NgaGenerator 仅预留接口/配置/TODO | 接口/环境变量已落;真实 NGA 调用仍待内网 |

### 默认 / 假设 / 降级 / 占位 / 近似 标记扫描结果

以下列出有实际验收意义的标记位置。`backend/schemas/*.schema.json` 中大量 `default: null` 是 pydantic 自动导出的 schema 噪音,未逐行列入;真正有决策含义的 schema default 已列出。

| 文件:行号 | 标记 | 含义 |
| --- | --- | --- |
| `QUESTIONS.md:6` | 当前默认值 | 用构造样例替代真实语料 |
| `QUESTIONS.md:9` | 当前默认值 | 已提供 wheelhouse 脚本,但未跑 Windows 真机 |
| `QUESTIONS.md:12` | 当前默认值 | lint 通过不等于视觉可交付 |
| `docs/taskbook.md:591-595` | A.2 未确认 | DeckIR 草案、历史记录、图片透传、chart 原生图表、内网 Skill 形态 |
| `backend/app/ir/word_ir.py:24` | 默认 | WordIR classification 默认 `内部公开` |
| `backend/app/ir/word_ir.py:49` | 用户确认后的契约 | WordIR blocks 必填且至少 1 条 |
| `backend/app/ir/deck_ir.py:15-16` | 默认 | DeckIR classification 默认 `HUAWEI CONFIDENTIAL`, theme 默认 `hw_v1` |
| `backend/app/ir/validation.py:87-94` | 默认/自定 | 未知字段 warning 代码自定为 `W104` |
| `backend/app/ir/validation.py:169-170` | 默认/自定 | WordIR 空 blocks 映射为 `E006` |
| `backend/app/ir/report.py:12` | 默认/自定 | `E006` 文案扩展为 blocks 或列表 items 至少 1 条 |
| `backend/app/prompting/builder.py:29` | 默认 | Prompt context 上限 12000 字符 |
| `backend/app/prompting/builder.py:44-100` | 默认/降级 | 超长 context 按优先级丢弃预览尾行、表格尾行、次要段落和低价值明细 |
| `backend/app/parsers/md_parser.py:43-56` | 降级 | Markdown 标题 >4 级降到 4;表格只预览 20 行 |
| `backend/app/parsers/docx_parser.py:43-68` | 降级 | DOCX 标题 >4 级降到 4;表格只预览 20 行 |
| `backend/app/parsers/docx_parser.py:151-161` | 假设/降级 | 通过 XML 关键字粗略检测批注、修订、文本框、SmartArt |
| `backend/app/parsers/xlsx_parser.py:12-13` | 默认 | XLSX 预览 20 行 x 15 列 |
| `backend/app/parsers/xlsx_parser.py:117-127` | 假设 | 列类型推断使用简单规则 |
| `backend/app/parsers/pptx_parser.py:80-83` | 降级 | PPTX chart 记录标题与类型,不反解数据 |
| `backend/app/parsers/pptx_parser.py:112-121` | 假设/降级 | transition/timing/group shape 检测较粗 |
| `backend/app/rendering/docx_renderer.py:24-30` | 默认 | DOCX 字体、字号、表格边框本地常量 |
| `backend/app/rendering/docx_renderer.py:103-115` | 默认 | 页眉默认 title,页脚默认 classification + PAGE |
| `backend/app/rendering/docx_renderer.py:229-231` | 占位 | DOCX 图片仅输出 `[图片占位]` |
| `backend/app/rendering/themes/hw_theme.json:2-250` | 近似/默认 | 华为主题 tokens 与 10 类版式坐标/尺寸为外网近似值 |
| `backend/app/rendering/pptx_renderer.py:232-258` | 降级 | chart 渲染为说明 + 迷你数据表 |
| `backend/app/rendering/pptx_renderer.py:261-280` | 占位 | image 渲染为灰底占位框 + 题注 |
| `scripts/demo_e2e.py:27-28` | 默认 | demo generator 默认 stub,输出目录默认 `output/demo` |
| `scripts/demo_e2e.py:50,58` | 占位 | word demo 或 deck 无 `--lint` 时写 placeholder report |
| `scripts/make_wheelhouse.py:14-17` | 默认 | wheelhouse 平台 `win_amd64`,Python `3.12`,输出 `wheelhouse/` |
| `docs/内网接入.md:19-20` | 默认 | NGA timeout/retry 只写为实现层默认,未落代码 |
| `docs/内网接入.md:64` | 默认 | 默认不落盘原始敏感 Prompt |

## A. 需要你拍板的决策与默认

### A1. DeckIR v1.1 以任务书 3.3 为准,未做“现有草案”兼容层

- 【为什么重要】如果你们已有 DeckIR 草案,字段差异会导致模型输出或内网 Skill 对不上。
- 【我这边的状态 / 我做了什么】我直接按 `docs/taskbook.md` 3.3 建模,没有实现兼容读取旧草案。
- 【你具体要做什么】对照现有草案。如果有差异,决定是改 schema、升 `ir_version`,还是加兼容转换层。
- 【在哪】`docs/taskbook.md:591`; `backend/app/ir/deck_ir.py:10-161`; `backend/schemas/deck_ir.schema.json`。
- 【优先级】高

### A2. 历史 / 运行记录是否需要

- 【为什么重要】这影响是否保存原始 Prompt、输入摘要、生成 IR、报告和敏感内容;也影响内网合规。
- 【我这边的状态 / 我做了什么】没有实现通用历史记录。`demo_e2e.py` 只把当前运行的 `document_ir.json`、`prompt.txt`、产物和报告写到指定 output dir。
- 【你具体要做什么】决定是否需要 `storage/` 运行记录;若需要,明确保存范围和脱敏规则。
- 【在哪】`docs/taskbook.md:592`; `scripts/demo_e2e.py:38-62`; `docs/内网接入.md:64`。
- 【优先级】高

### A3. 未知字段 warning 代码自定为 `W104`

- 【为什么重要】任务书只说未知字段忽略并记 Warning,没有给具体错误码;下游若依赖错误码,需要统一。
- 【我这边的状态 / 我做了什么】我自定 `W104` 表示未知字段已忽略。
- 【你具体要做什么】确认是否接受 `W104`;不接受则指定正式 warning code 并同步测试、文档、报告。
- 【在哪】`backend/app/ir/validation.py:87-94`; `backend/app/ir/report.py:19`; `backend/tests/test_ir_validation.py:76`。
- 【优先级】中

### A4. WordIR 空 `blocks` 映射为 `E006`

- 【为什么重要】任务书原本 `E006` 是“列表 items 为空数组”,但你要求 WordIR 空 blocks 报错,任务书没有给新码。
- 【我这边的状态 / 我做了什么】我把空 `blocks` 和空列表都归到 `E006`。
- 【你具体要做什么】确认是否接受共用 `E006`;若要更精确,新增 `E007` 或修改任务书错误码表。
- 【在哪】`backend/app/ir/word_ir.py:49`; `backend/app/ir/validation.py:169-170`; `backend/app/ir/report.py:12`。
- 【优先级】中

### A5. Prompt 超长截断上限默认 12000 字符

- 【为什么重要】上限影响 Prompt 完整性、模型上下文占用和真实业务长文档摘要质量。
- 【我这边的状态 / 我做了什么】默认 12000 字符;超限时保持合法 JSON,按优先级丢弃预览尾行、表格尾行、次要段落和低价值明细,并声明“已截断说明”。
- 【你具体要做什么】若内网模型上下文窗口不同,确认是否调整默认上限。
- 【在哪】`backend/app/prompting/builder.py:30`; `backend/app/prompting/builder.py:44-100`; `docs/taskbook.md:365`。
- 【优先级】高

### A6. DOCX 图片透传是否需要

- 【为什么重要】如果输入 Word 的图片必须进入输出,当前链路会丢失图片内容。
- 【我这边的状态 / 我做了什么】没有做图片透传;WordIR `image_placeholder` 只渲染占位文字。
- 【你具体要做什么】决定图片透传是否进入 P0/P1;若需要,提供样例并定义图片存储/引用方式。
- 【在哪】`docs/taskbook.md:593`; `backend/app/rendering/docx_renderer.py:229-231`; `backend/app/ir/common.py:78-81`。
- 【优先级】中

### A7. chart 是否必须原生图表

- 【为什么重要】客户看到“图表页”时,迷你表格可能不满足演示预期。
- 【我这边的状态 / 我做了什么】chart 按 P0 降级成说明文本 + 迷你数据表。
- 【你具体要做什么】确认是否接受 P0 降级;若要原生 chart,指定优先级并补视觉/数据验收样例。
- 【在哪】`docs/taskbook.md:594`; `backend/app/rendering/pptx_renderer.py:232-258`。
- 【优先级】高

### A8. 内网渲染 Skill 调用形态未定

- 【为什么重要】同步 HTTP、文件落盘、SDK 调用会影响接口、鉴权、日志和错误处理。
- 【我这边的状态 / 我做了什么】已提供 `backend/app/generators/nga.py` 环境变量读取和显式占位错误;没有真正对接官方渲染 Skill。
- 【你具体要做什么】确认内网 Skill 的真实调用形态;补官方渲染适配层或完善 NGA 真实协议调用。
- 【在哪】`docs/taskbook.md:595`; `backend/app/generators/nga.py:7-18`; `docs/内网接入.md:7-20`; `docs/内网接入.md:56-58`。
- 【优先级】高

## B. 降级与近似

### B1. 华为风格 tokens 是外网近似

- 【为什么重要】颜色、字体、版心、页脚坐标不等于官方 CI;视觉上可能不像正式华为材料。
- 【我这边的状态 / 我做了什么】集中写入 `hw_theme.json`,方便内网只改一处。
- 【你具体要做什么】拿内网 HarmonyOS 字体、官方红色/灰阶/母版坐标校准 `hw_theme.json`,再重新跑 `python3 scripts/verify.py`。
- 【在哪】`backend/app/rendering/themes/hw_theme.json:2-250`; `docs/风格规范.md:3-18`; `docs/taskbook.md:407-424`。
- 【优先级】高

### B2. chart 页不是原生图表

- 【为什么重要】可编辑性有,但不是 PowerPoint 原生 chart,视觉和交互能力有限。
- 【我这边的状态 / 我做了什么】渲染“图表待内网 Skill / 后续版本生成”文字和迷你表格。
- 【你具体要做什么】确认 P0 是否可接受;内网若有官方图表 Skill,用同一 DeckIR 对接替换。
- 【在哪】`backend/app/rendering/pptx_renderer.py:232-258`; `PROGRESS.md:90-92`。
- 【优先级】高

### B3. image 页和 DOCX 图片都是占位

- 【为什么重要】真实架构图、截图、产品图不会进入产物;演示可能缺关键视觉证据。
- 【我这边的状态 / 我做了什么】PPTX image 画灰底占位框;DOCX image_placeholder 写 `[图片占位]` 文本。
- 【你具体要做什么】确认外网阶段是否只要占位;若要真图,定义图片输入路径、脱敏规则和复制策略。
- 【在哪】`backend/app/rendering/pptx_renderer.py:261-280`; `backend/app/rendering/docx_renderer.py:228-230`; `docs/taskbook.md:280,296`。
- 【优先级】中

### B4. 解析器是结构摘要,不是完整 Office 语义还原

- 【为什么重要】真实复杂文件会有文本框、组合形状、图表、SmartArt、修订、公式等;当前只抽取摘要。
- 【我这边的状态 / 我做了什么】DOCX 用样式和 XML 标签粗检;XLSX 不求公式值;PPTX chart 只记标题与类型。
- 【你具体要做什么】用真实脱敏文件跑解析,核对 warnings 是否诚实,再决定是否补 P2 解析能力。
- 【在哪】`backend/app/parsers/docx_parser.py:157-181`; `backend/app/parsers/xlsx_parser.py:19-75`; `backend/app/parsers/pptx_parser.py:80-110`。
- 【优先级】高

## C. 我无法自证、必须你验证的

### 我做了但没法确认对不对

我能用库回读 DOCX/PPTX 的结构事实,也能跑 pytest、coverage 和 stub 链路。但我不能确认 Windows 上字体替换后的真实观感,不能确认真实业务文件解析是否足够,不能确认离线 wheelhouse 在干净 Windows 机上安装成功,也不能判断生成内容是否符合你们内部审美和语义质量。下面这些不能标成“已通过”,只能标成“待人工验收”。

### C1. Windows 离线 wheelhouse 真机验收

- 【为什么重要】macOS 上的依赖成功不代表 Windows 离线可安装;`lxml`, `pydantic-core`, `Pillow` 等 wheel 有平台差异。
- 【我这边的状态 / 我做了什么】提供 `scripts/make_wheelhouse.py` 和 `docs/内网接入.md`;没有 Windows 真机。
- 【你具体要做什么】
  1. 在联网机器运行 `python scripts/make_wheelhouse.py --platform win_amd64 --python-version 3.12 --output wheelhouse`。
  2. 拷贝项目和 `wheelhouse/` 到干净断网 Windows。
  3. 运行 `pip install --no-index --find-links wheelhouse -r requirements.txt`。
  4. 运行 `python scripts/verify.py`。
  5. 记录 Windows 版本、Python 版本、安装输出、verify 输出和截图。
- 【在哪】`docs/taskbook.md:495-504`; `scripts/make_wheelhouse.py:12-39`; `docs/内网接入.md:33-59`; `QUESTIONS.md:8-10`。
- 【优先级】高

### C2. PPTX 视觉终审

- 【为什么重要】lint 只能检查硬规则的一部分,不能判断“像不像华为、拿不拿得出手”。
- 【我这边的状态 / 我做了什么】生成可编辑 PPTX,并有 lint 规则与报告;未打开 Windows PowerPoint 目视检查。
- 【你具体要做什么】
  1. 运行 `python3 scripts/verify.py`。
  2. 打开 `output/c0_deck.pptx`。
  3. 检查字体、版心、页脚、标题区、卡片/表格间距、是否压字、是否有越界。
  4. 如内网字体不同,先校准 `backend/app/rendering/themes/hw_theme.json` 再复查。
- 【在哪】`QUESTIONS.md:11-13`; `docs/taskbook.md:457`; `backend/app/rendering/themes/hw_theme.json:12-250`。
- 【优先级】高

### C3. DOCX 人工打开和编辑验收

- 【为什么重要】python-docx 回读证明结构存在,但不能证明 Word 桌面端分页、字体、页码域和表头重复在 Windows 上显示正确。
- 【我这边的状态 / 我做了什么】测试覆盖标题、正文、列表、页眉页脚、页码域、表格表头和 100x12 极限表;未在 Windows Word 目视验证。
- 【你具体要做什么】
  1. 运行 `PYTHONPATH=backend python3 -m app.cli.render --type word samples/ir/word_valid_03_table.json --output output/word_valid_03_table.docx`。
  2. 用 Word 打开并尝试编辑标题、正文、表格。
  3. 检查页眉、页脚密级、页码域、表头重复是否符合预期。
- 【在哪】`backend/app/rendering/docx_renderer.py:24-231`; `backend/tests/test_docx_renderer.py`。
- 【优先级】中

### C4. 真实脱敏文件解析验收

- 【为什么重要】构造样例不能代表现实脏文件;解析器对文本框、修订、组合形状、图表和大表的处理可能不足。
- 【我这边的状态 / 我做了什么】已用 `scripts/make_dirty_samples.py` 生成并解析 10 个 synthetic 脏样例,覆盖 §5.4 结构边界;没有真实业务文件,synthetic 不替代真实语料。
- 【你具体要做什么】
  1. 放入 `samples/input/real/` 下 docx / xlsx / pptx 各至少 3 个脱敏文件。
  2. 逐个运行 `PYTHONPATH=backend python3 -m app.cli.parse <file> --output output/<name>.document_ir.json`。
  3. 打开输出 JSON,核对 `content` 是否有用、`warnings` 是否诚实。
- 【在哪】`QUESTIONS.md:5-7`; `docs/taskbook.md:392-394`; `backend/app/parsers/`。
- 【优先级】高

### C5. IR 样例文件人工抽查

- 【为什么重要】样例文件不仅服务自动测试,也服务演示和失败提示复核;人工应抽查它们是否表达清楚。
- 【我这边的状态 / 我做了什么】当前总测试 114 passed;`verify.py` 已串联四格式 e2e、pytest 与 coverage。Word 诊断样例、DocumentIR/DeckIR 正反样例、`deck_valid_full.json` 和 synthetic 脏样例已补齐并进测试。
- 【你具体要做什么】正式签收前抽查 `samples/ir/` 中正反样例命名、内容和失败提示是否适合演示。
- 【在哪】`docs/taskbook.md:468-482`; `docs/taskbook.md:597-611`; `backend/tests/`; `samples/ir/`。
- 【优先级】高

## D. 待外部输入才能继续的

### D1. 真实语料

- 【为什么重要】没有真实文件,解析质量和 warnings 契约都只能算构造样例通过。
- 【我这边的状态 / 我做了什么】`QUESTIONS.md` 已登记;当前没有 `samples/input/real/` 真实文件集。已补 synthetic 结构边界样例,但不替代真实脱敏语料。
- 【你具体要做什么】提供脱敏 docx / xlsx / pptx 各至少 3 个,覆盖修订、批注、文本框、合并单元格、公式、组合形状、备注等。
- 【在哪】`QUESTIONS.md:5-7`; `docs/taskbook.md:392-394`; `docs/taskbook.md:604`。
- 【优先级】高

### D2. 内网 HarmonyOS 字体与华为 CI

- 【为什么重要】当前主题是外网近似,视觉终审和 lint 阈值都依赖真实字体/颜色/母版坐标。
- 【我这边的状态 / 我做了什么】主题集中在 `hw_theme.json`,但值没有官方来源。
- 【你具体要做什么】提供官方字体、颜色、页脚/标题坐标;更新 `hw_theme.json`;重新跑 `python3 scripts/verify.py` 并人工打开 PPTX。
- 【在哪】`backend/app/rendering/themes/hw_theme.json:2-250`; `docs/风格规范.md:14-18`; `QUESTIONS.md:13`。
- 【优先级】高

### D3. 内网 NGA / AICoding 可调用接口

- 【为什么重要】当前 generator 只有 stub;真实 AI 产 IR 仍是人工复制 Prompt/JSON 或未来接口。
- 【我这边的状态 / 我做了什么】`backend/app/generators/nga.py` 已提供环境变量读取和显式占位错误;真实协议调用仍待内网提供。
- 【你具体要做什么】提供 NGA 协议、鉴权方式、错误码、超时/重试要求和日志脱敏要求。
- 【在哪】`docs/taskbook.md:591-595`; `docs/内网接入.md:7-20`; `AGENTS.md:43-44`。
- 【优先级】高

### D4. 内网华为官方渲染 Skill

- 【为什么重要】当前 PPTX renderer 是本地自绘近似,不是官方 Skill 输出。
- 【我这边的状态 / 我做了什么】保留本地 renderer 作为回退;文档说明未来只替换渲染 Skill 对接层。
- 【你具体要做什么】确认 Skill 调用方式,提供输入/输出样例;用同一 DeckIR 对比官方输出和本地输出。
- 【在哪】`docs/内网接入.md:11-13`; `docs/内网接入.md:56-58`; `backend/app/rendering/pptx_renderer.py`。
- 【优先级】高

### D5. 是否要 Web 界面

- 【为什么重要】当前只有 CLI;若面向非工程用户,可能需要上传/展示/报告查看页面。
- 【我这边的状态 / 我做了什么】没有实现 Web;任务书把 Web 放 P2。
- 【你具体要做什么】确认是否继续保持 CLI-only;若要 Web,明确最小页面和安全边界。
- 【在哪】`docs/taskbook.md:165-184`; `docs/taskbook.md:587`。
- 【优先级】低

## 建议验收顺序

1. 先做 C 区三项不能跳过的人工验证:Windows 离线、PPTX/DOCX 视觉与语义终审、真实语料。
2. 内网拿到官方字体/CI 后,只改 `backend/app/rendering/themes/hw_theme.json` 重新校准并复跑 `python3 scripts/verify.py`。
3. 若进入正式终验,按 `docs/验收手册.md` 执行并保存截图/录屏结果。
