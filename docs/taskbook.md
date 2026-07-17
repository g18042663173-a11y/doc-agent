# 实习任务书(定稿交付版 v3)

**AICoding 文档生成能力与华为风格黄区 PPTX 工具建设**

—— 依据本地环境现状对齐:CLI 直连 · AICoding 产 IR · 本地确定性渲染 ——

| 字段 | 内容 |
| --- | --- |
| 文档版本 | 定稿交付版 v3(在 v2 基础上补入开发 macOS/类 Unix 与目标 内网 Windows 的双环境约定:跨平台卫生规则、脚本 Python 化 + 平台薄封装、Windows 平台 wheelhouse 与字体保真视觉终审的警示) |
| 任务对象 | 实习生 / 初级开发同学 |
| 项目方向 | 企业文档生成 Agent、AICoding 输入输出桥接、华为风格 PPTX 生成工具 |
| 实施周期 | 5 周(排期细化到天,含 4 个检查点评审) |
| 总体目标 | 把现有本地能力整合成可演示、可验收、可迁移的命令行文档生成工具链 |
| 技术基线 | 命令行(CLI)直连 AICoding 产 IR;本地 Python 确定性渲染;不接真实 NGA、不做 Web 强约束 |
| 边界说明 | 不接真实 NGA;不复刻完整 PowerPoint 母版;不做多人在线协作;不采用手工 HTML 编写 PPT |
| 本版用途 | 开工评审依据、过程对照清单、验收对账清单 |

## 0  阅读指引

本文是任务书的工程化定稿版:统一术语、锁定技术方案、给出三份 IR 字段级规范、把三个 Step 拆成 18 张带验收标准与工时的任务卡、排期落到天、验收落到命令。架构已按实际环境完成对齐、默认项已在开工前确认(见附录 A)。与原始任务书范围冲突时,以原任务书的边界说明为准;本文只回答“怎么做、做到什么程度算完成”。

- **先读这一章:** 第 0.5 章给出架构总览与核心设计原则(CLI 直连、AICoding 产 IR、本地确定性渲染、以 IR 为唯一契约),导师与实习生都应先看它再进入正文。
- **快速开工路径:** 先读第 1 章(术语与不变量)和 2.1 节(主链路),再对照第 8 章排期领取当天任务卡;每张任务卡的“验收标准”即当日下班前的自查清单。
- **导师评审路径:** 重点看第 3 章(IR 契约)、6.3 节(合规规则)、附录 A(待确认问题),这三处一旦确认,后续实现即可少返工。
- **原文对照:** 第 4/5/6 章分别对应 v1.0 的 3.1/3.2/3.3 节;第 7 章对应“验收标准”;第 8 章对应“建议排期”;第 9 章对应“风险与处理建议”。

## 0.5  架构总览与核心设计原则

在当前环境下,AICoding 就是命令行里的 AI 模型本身,现网已具备 Python 3.12、成熟的 MD→DOCX 转换与基础 Flask 服务。整体架构据此定为“命令行(CLI)直连 + AICoding 产 IR + 本地确定性渲染”:用户在命令行提供输入,AICoding 产出结构化中间表示(IR),本地 Python 程序对 IR 做校验与渲染,产出可编辑的 DOCX / 华为风格 PPTX 并做合规检查。详细主链路见 2.1,模块划分见 2.2,不接真实 NGA、不做 Web 强约束(Web 界面为可选 P2)。

### 0.5.1  三块基石

- **三份 IR 规范与错误码(第 3 章):** 模型与渲染器之间的唯一格式契约,与运行环境无关——项目的核心设计价值主要沉淀于此。
- **华为风格 tokens 与合规规则(第 6 章):** 风格集中在 hw_theme.json 单点收敛;外网承诺“合规检查通过”,像素级还原留给内网 Skill。
- **可离线全量测试的流水线(第 7 章):** stub 通道让整条链路在“无 AI 参与”下即可跑通与回归,是项目可评分、可 CI、可迁移的基础。

> **注** 核心设计原则(建议贯穿始终):把“谁产出 IR”与“消费 IR 的确定性流水线”彻底解耦。AICoding 产 IR 是既有能力,无需从零开发;实习生真正交付的,是围绕 IR 的解析 → 组装 → 校验 → 渲染 → 合规检查 → 测试这条本地流水线。因为它不依赖任何具体模型,在 stub 通道下即可全量运行,进内网时只需把产 IR 的通道从 aicoding 换成 nga、渲染对接官方 Skill,其余零改动。

## 1  术语、关键假设与工程不变量

### 1.1  术语表(本项目内统一口径)

| 术语 | 本项目内约定含义 |
| --- | --- |
| AICoding | AI 模型助手,通过命令行(CMD)直接对话交互:能理解需求、生成内容、产出结构化 JSON,无需本地安装或 Web 服务——即当前对话中的 AI 本身。本项目把它抽象为“产出 IR 的默认 generator”,通过 Prompt 输入、JSON 输出完成桥接。 |
| NGA | 内网大模型网关 / 服务(协议外网完全未知)。本阶段不做任何实现,仅在 generator 层预留接口与 TODO,待内网部署确认协议后再补充。 |
| 黄区 | 华为内网办公安全区。本项目所有设计需满足:进黄区后只替换 generator 与渲染 Skill 两处即可运行。 |
| IR(中间表示) | 模型与渲染器之间的结构化 JSON 契约,共三份:DocumentIR(输入侧)、WordIR(Word 输出侧)、DeckIR(PPT 输出侧)。 |
| stub 模式 | 不依赖任何真实模型,由规则模板直接产出合法 IR(stub generator)。用于离线演示、CI 回归和进内网前自测,是“无 AI 也能全量验收”的支柱。 |
| 剥壳 | 从 AICoding 返回文本中提取 json 代码块、剔除前后解释文字与噪声的过程,是模型文本进入校验器前的固定一步。 |
| 五件套 | 每个功能的完成定义 = 代码 + 样例 + 失败提示 + 最小测试 + 文档,缺一不算完成。 |
| golden 测试 | 渲染产物用解析库回读,对结构性事实(标题数、表格尺寸、页脚文案等)做断言的回归测试。 |

### 1.2  关键假设(默认值;若与实际不符,以导师确认为准,见附录 A)

| 编号 | 假设与默认值 |
| --- | --- |
| A1 | 双环境:开发机为 macOS / 类 Unix(实习生与编码 agent 都在此写代码、跑测试),目标机为内网 Windows(离线运行)。核心代码为纯 Python、跨平台;Python 3.12;主交互为命令行 + 本地目录,不强制引入 Web 框架。 |
| A2 | AICoding 输出形态:基本能稳定输出一个 json 代码块,但可能夹带解释文字,必须经“剥壳 + Schema 校验”后方可进入渲染。 |
| A3 | 密级文案默认:DOCX 页脚为“内部公开”,PPTX 页脚为“HUAWEI CONFIDENTIAL”,均在配置中可改。 |
| A4 | 中文字体:外网以微软雅黑为主选,HarmonyOS Sans 作为内网目标字体;不追求与母版逐像素一致,字体集中在主题配置,内网只改一处。 |
| A5 | DeckIR v1.6 已定稿:本文 3.3 节给出的字段表为权威版;1.4/1.5 输入先做兼容读取,再按本表校验。 |
| A6 | 主界面为 CLI + 本地文件目录(input/ 放输入、output/ 取产物);Web 工作台为可选项(P2),如需可复用现有 Flask,不作为核心交付。 |
| A7 | AICoding 输入约束:单次输入按 8K–16K 字符规划(Prompt 截断上限据此设定);以“把内容贴进 Prompt”为准,不假设 AICoding 能直接读取本地文件路径。 |

### 1.3  三条工程不变量(整个实习期间不允许破坏)

- **I1 模型文本永不直连渲染器:** 任何进入渲染器的 JSON 必须先通过对应 Schema 校验;校验失败给出错误码与定位,绝不“尽力渲染”。
- **I2 IR 是唯一契约:** 解析器只产 DocumentIR,渲染器只消费 WordIR / DeckIR;两侧互不感知对方实现,产 IR 的 generator(stub / aicoding / 未来 nga)可整体替换。
- **I3 内外网差异只允许存在于两处:** generator(产 IR 的通道)与华为渲染 Skill 对接层;上游解析、IR、Prompt、合规检查零改动。

## 2  总体设计

### 2.1  唯一主链路(所有任务都服务它)

```
[可选输入文件 md / docx / xlsx / pptx]
   -> (1) parsers   解析(仅当有输入文件)  -> DocumentIR(结构化摘要 + warnings)
   -> (2) prompting 组装四段式提示           -> Prompt 文本
   -> (3) generator 产出 IR                  -> 目标 IR 原始文本
                                               stub     = 规则直接产(测试 / 断网)
                                               aicoding = 当前 CLI 中的 AI 产(默认)
   -> (4) ir        剥壳 + Schema 校验       -> WordIR / DeckIR(或错误码清单)
   -> (5) rendering 本地确定性渲染           -> 可编辑 DOCX / 华为风格 PPTX
   -> (6) lint      合规检查                 -> Error / Warning / Info 报告
   -> 落盘 output/ + 运行记录
```

- **两条入口路径:** ① 纯生成——用户口述主题,无输入文件,直接进第(2)(3)环;② 文档改写——有输入文件,先经第(1)环解析为 DocumentIR 作为提示上下文,再进第(3)环。

实习生真正开发的是第(1)(2)(4)(5)(6)环这条本地流水线;第(3)环“产 IR”在 aicoding 模式下由现成 AI 完成,在 stub 模式下由规则完成——两种模式共用同一份下游流水线。三个 Step 与主链路的对应:Step 1 = 第(4)(5)环 Word 分支;Step 2 = 第(1)(2)环;Step 3 = 第(5)(6)环 PPT 分支 + 黄区接入说明。任何新增功能,先回答“落在哪一环”,回答不了就进 P2 待办,不抢主线。

### 2.2  模块划分与目录结构(建议)

```
backend/
  app/
    cli/            # 命令行入口:parse.py / prompt.py / render.py / check.py / verify(契约见 2.5)
    ir/             # pydantic 模型 + JSON Schema 导出:document_ir.py / word_ir.py / deck_ir.py / errors.py
    parsers/        # md_parser.py  docx_parser.py  xlsx_parser.py  pptx_parser.py(统一返回 DocumentIR)
    prompting/      # templates/*.txt + builder.py(截断策略集中在此)
    generators/     # base.py  stub.py  aicoding.py  nga.py(仅接口与 TODO)
    rendering/      # docx_renderer.py  pptx_renderer.py  themes/hw_theme.json
    lint/           # pptx_lint.py  rules/*.py  report.py
    storage/        # 本地运行记录(轻量 JSON 日志即可;非必需)
  tests/            # unit/  golden/  e2e/
  samples/          # input/  ir/  expected/(清单见附录 B)
docs/               # README.md  使用说明.md  内网接入.md  验收手册.md  风格规范.md
scripts/            # demo_e2e.py  verify.py  make_wheelhouse.py(逻辑用 Python);verify.sh / verify.ps1 仅作平台薄封装
web/(可选,P2)     # 若做轻量界面再建;可复用现有 Flask,不属核心交付
```

> **注** 若现有工程目录不同,不必强行搬家;保证“职责分层一致、IR 单独成包、主题与规则可配置、CLI 可独立运行”即可,目录名以现状为准。

### 2.3  技术选型(定版;变更需在检查点评审提出)

| 环节 | 选型 | 理由 / 实现备注 |
| --- | --- | --- |
| docx 解析与渲染 | python-docx | 成熟稳定。标题层级识别用“样式名 + outlineLevel”双策略,兼容中英文样式名。 |
| xlsx 解析 | openpyxl | read_only + data_only 打开保证性能;公式计数按 cell.data_type 是否为 'f'(需一次非 data_only 加载)。 |
| pptx 解析与渲染 | python-pptx | 版式全部自绘,不依赖母版占位符;替代此前手工 HTML + html2pptx 方案,使用者无需接触 HTML / CSS。动画/转场检测读取 slide 底层 XML。 |
| Markdown 解析 | markdown-it-py(或轻量自写) | 只需标题/段落/列表/表格四类,产出与 WordIR 同构的 blocks。 |
| IR 定义与校验 | pydantic v2 | model_json_schema 一键导出 JSON Schema,CLI、Prompt 模板与(可选)界面共用同一份。 |
| 交互方式 / 服务 | 命令行(CLI)+ 本地目录;Web 可选 | 核心不依赖 Web 框架;不引入 FastAPI 强约束。若做 P2 界面可复用现有 Flask,保持轻量。 |
| 测试 | pytest + coverage | golden 断言一律用“回读产物”方式,不比对二进制;stub 通道支撑无 AI 全量测试。 |
| 部署 | pip wheelhouse(Windows 平台)+ Python 脚本(平台薄封装) | wheelhouse 必须为 Windows 目标构建(见下方约定与 §7.4);满足内网离线安装,第 5 周前完整演练一次。 |

- **跨平台卫生约定(Mac 开发、Windows 运行,务必遵守):** ① 路径一律用 pathlib、不手拼分隔符;② 所有文件读写显式 encoding="utf-8"(防内网中文 Windows 默认 GBK 把中文读乱);③ 不 shell out 到平台专属命令,平台差异只留在 verify.sh / verify.ps1 薄封装里;④ 离线 wheelhouse 必须含 Windows 平台 wheel(lxml、pydantic-core 等带编译产物、分平台),用 pip download --platform win_amd64 --python-version 3.12 --only-binary=:all: 下载,或直接在一台 Windows 机上构建(更稳)。

### 2.4  产 IR 的 generator 分层(接口即契约)

```
from typing import Literal, Protocol

class IRGenerator(Protocol):
    name: str
    def generate(self, prompt: str, *, target: Literal["word_ir", "deck_ir"]) -> str:
        """返回产出的 IR 原始文本;剥壳与校验由上游统一处理,generator 不做。"""
```

- **StubGenerator(默认测试通道,P0):** 读取 DocumentIR / 按规则直接映射成合法 IR,毫秒级、确定性。是自动化测试、CI 与断网演示的支柱,也是“无 AI 也能全量验收”的关键。
- **AICodingGenerator(默认生产通道,P0):** 由当前命令行中的 AI 产出 IR:基本能稳定输出一个 json 代码块,偶夹解释文字,交由剥壳器统一处理。落盘方式与自动化程度见下方分级。
- **NgaGenerator(仅预留接口,内网再实现):** 只写接口签名、配置项(NGA_BASE_URL / NGA_TOKEN / 超时 / 重试)与 TODO 注释;外网阶段不实现、不猜协议。

**AICodingGenerator 自动化分级(先保证可用,再逐步提升):**

- **P0(默认,当前实现):** 人工把 Prompt 交给 AICoding,再把返回的 json 代码块另存为 ir/*.json;端到端可用,零额外依赖。
- **P1(半自动,时间富余再做):** 写一小段捕获脚本读取 AICoding 输出、自动提取 json 代码块并落盘,省去手工复制。
- **P2(全自动,依赖内网):** 当 AICoding / NGA 提供可调用接口时,generator 直接程序化调用,无人工介入。

> **注** 落地顺序:先做 P0 确保功能跑通,再视余量做 P1;P2 待内网条件具备。无论哪一级,下游 parse / prompt / render / check 完全不变——这正是 generator 分层的价值。渲染器 / 校验器 / 检查器都不依赖具体 generator,因此可在 stub 通道下被全量测试,是本项目可评分、可 CI、可迁移的技术基础。

### 2.5  命令行契约(核心交付)

| 命令 | 入参 | 出参 | 说明 |
| --- | --- | --- | --- |
| parse.py <file> | md / docx / xlsx / pptx 路径 | ir/doc.json(DocumentIR) | 超限内容自动截断并记入 warnings。 |
| prompt.py --kind word\|deck [--context ir/doc.json] [--max-output-chars N] | 目标类型 + 可选上下文 + 弱模型输出预算 | prompt.txt | 输出确定性:同一输入两次逐字节一致;预算不足时要求删减低价值内容并保持 JSON 完整。 |
| render.py --type word\|deck <ir.json> | 目标 IR 文件 | output/x.docx \| x.pptx | 先 Schema 校验(不变量 I1)再渲染;失败给错误码与定位,PPTX 渲染后自动 lint。 |
| check.py <pptx\|docx> | 产物路径 | report.md / report.json | 合规检查;支持对外部文件复检。 |
| verify(脚本) | - | 验收结论 | 串联样例全链路 + pytest + 覆盖率,一键出结论(见 7.2)。 |

退出码约定:0 = 成功;非 0 = 失败并打印错误码(E / W 系,见第 3 章)。所有面向使用者的错误文案不暴露堆栈。把每个命令的入参 / 出参 / 退出码固定下来,即构成稳定接口。generator 用哪种(stub / aicoding)由 render 前的一步决定,命令签名不变。

### 2.6  日常使用方式与可选 Web 界面(P2)

核心交付是 CLI;当前不存在现成工作台,也不强制开发。日常使用即:把输入文件放进 input/,依次运行 2.5 的命令,产物落在 output/,报告在同目录。与 AI 的衔接是“把 prompt.txt 交给 AICoding、把返回的 json 存成 ir/*.json”这一步(见下)。

**AICoding 交互流程(以 deck 为例;步骤 3–5 当前需人工,未来可脚本半自动化,见 2.4 分级):**

1. 运行 prompt.py --kind deck --context ir/doc.json --max-output-chars 6000,系统生成带字段约束、内容规则、预算和 few-shot 的 prompt.txt。
2. 复制 prompt.txt 内容,交给 AICoding。
3. AICoding 应只返回一个裸 JSON 对象;剥壳器仍兼容历史 json 围栏和夹带解释文字的输出。
4. 复制其中的 json,保存为 ir/deck.json。
5. 运行 render.py --type deck ir/deck.json 生成 PPTX,再运行 check.py 产出合规报告。

> **注** 纯生成场景(无输入文件)跳过 --context,直接口述主题让 AICoding 产 IR;其余步骤一致。

**Web 界面优先级:P2(可选,建议暂缓)**

- **原因:** 当前环境无现成工作台,从零开发成本高;CLI + 本地目录已满足核心需求。
- **实现时机:** 核心功能稳定、且排期有余量时再考虑;不占用 P0/P1 任务的时间。
- **技术选择:** 复用现有 Flask,仅做“上传 + 结果展示 + 报告查看”三块;底层调用与 CLI 完全相同的 parse / prompt / render / check 函数,保证有无界面行为一致、都可测试。
- **明确不做:** FastAPI 全套服务、历史管理、多模型、在线协作等重功能——当前环境不需要,保持轻量。

### 2.7  健壮性与可自动化机制

以下五项机制把“原本靠人盯”的环节尽量翻译成“机器能自查”,既降低出错,也让本项目可以安全地交给编码 agent 迭代(因为有确定性的通过 / 失败信号可循环)。每项都落在具体小节,此处只做索引:

| 机制 | 目的 | 落点(条款) |
| --- | --- | --- |
| 契约冻结与快照测试 | 防 IR 契约被悄悄改动 / 漂移 | §3.0、§7.1、任务卡 S1-1 |
| IR 修复回路 + 结构化输出 | 把不合法模型输出救回来,提升合法率 | §5.3、任务卡 S1-2、§9 |
| 可测量版式网格与 token | 把“好不好看”尽量变成可 lint 的硬指标 | §6.1、§6.3、§6.5 |
| 边界样例分类学 + 降级契约 | 逼出对真实脏文件的防御 | §5.4、附录 B |
| Windows 离线验收 checklist | 一次性人工在真机确认打包 | §7.4、§10 |

> **注** 有三件事写不进任务书、只能靠外部资产或人来补(受能力与事实边界所限,不是文字问题):真实文件语料、真 Huawei CI、最终视觉与内容终审。它们已分别在 §5.4、§6.1、§10 列为硬性动作,把“不可约的人”至少固化成流程里的确定步骤。

## 3  IR 规范(契约层,先评审后编码)

### 3.0  通用约定

- 所有 IR 顶层必带 ir_type 与 ir_version;编码 UTF-8;未知字段忽略但记 Warning(向前兼容)。
- 长度上限(超限即截断并记 Warning):单段落 2000 字;WordIR 表格 100 行 x 12 列;DeckIR 单页表格 12 行 x 8 列;单页要点 7 条、单条 60 字。
- 剥壳规则:优先取第一个 json 代码块;无代码块则取首个左花括号到与之配对的右花括号的子串;仍失败报 E001,并附原文前 200 字帮助排查。
- Schema 冻结与快照测试:三份 JSON Schema 导出为文件入库,配 schema 快照测试;凡改动 IR 字段而未同步升 ir_version、未过评审的,CI 直接失败(见 §7.1),杜绝契约悄悄漂移。
- IR 契约是唯一可信来源:任何人(含编码 agent)不得为了让某个样例通过而擅自放宽 Schema;确需变更时,先改 Schema + 升版本 + 更新正反样例,再改代码。

### 3.1  WordIR v1.0(Word 输出契约,Step 1 核心)

顶层结构:meta(文档元信息)+ blocks(有序内容块数组)。meta 字段:title(必填)、subtitle、author、classification(密级,默认“内部公开”)、header_text、footer_text。blocks 类型枚举如下:

| block.type | 必填字段 | 渲染要点 |
| --- | --- | --- |
| heading | level(1-4), text | 映射 Word 内置标题样式,保证导航窗格与目录可用。 |
| paragraph | text;可选 style: normal / quote / note | note 渲染为浅底提示框;quote 渲染为左竖线灰字。 |
| bullet_list / numbered_list | items[{ text, level: 1\|2 }] | 支持两级嵌套;空 items 报 E006。 |
| table | header[], rows[][];可选 caption, col_widths[] | 行列必须规整;有 col_widths 按比例分配,否则均分。 |
| image_placeholder | 可选 ref, caption | v1 输出带边框占位文本框与题注,不嵌真图(真图为 P2)。 |
| page_break | - | 强制分页。 |

最小合法样例:

```
{
  "ir_type": "word", "ir_version": "1.0",
  "meta": { "title": "XX 项目周报", "subtitle": "2026 年第 27 周",
            "author": "张三", "classification": "内部公开" },
  "blocks": [
    { "type": "heading", "level": 1, "text": "本周进展" },
    { "type": "paragraph", "text": "完成 WordIR 校验器与渲染主链路联调。" },
    { "type": "bullet_list", "items": [
        { "text": "解析器:新增 xlsx 摘要", "level": 1 },
        { "text": "渲染器:表格跨页修复", "level": 2 } ] },
    { "type": "table", "caption": "风险清单",
      "header": ["风险", "等级", "应对"],
      "rows": [["模型 JSON 不稳定", "中", "剥壳 + 校验 + 重试话术"]],
      "col_widths": [3, 1, 4] }
  ]
}
```

校验规则与错误码(Step 1 的失败提示即按此表输出):

| 错误码 | 级别 | 规则与处理 |
| --- | --- | --- |
| E001 | Error | 剥壳后仍无法解析为 JSON。提示附原文前 200 字与常见原因(多个代码块、尾部逗号、被截断)。 |
| E002 | Error | 缺少 meta.title 或为空白字符串。 |
| E003 | Error | 出现未知 block.type,列出该块序号与允许的类型清单。 |
| E004 | Error | 表格行列不规整,或超过 100 行 x 12 列上限。 |
| E005 | Error | heading.level 不在 1-4 范围。 |
| E006 | Error | 列表 items 为空数组。 |
| W101 | Warning | 标题层级跳级(如 1 级直接到 3 级),按就近降一级渲染并提示。 |
| W102 | Warning | 空段落已自动跳过。 |
| W103 | Warning | 单元格 / 段落超长已按上限截断。 |
| I201 | Info | 未提供 classification,已使用默认密级文案。 |

渲染硬性要求:中文字体与字号、标题层级样式、段落间距、表格边框(0.5pt)、页眉(= title)、页脚(密级 + 页码)全部集中在渲染器 STYLES 常量,业务代码零散设置样式视为缺陷;产物必须是可编辑 DOCX,禁止图片化或只读输出。

### 3.2  DocumentIR v1.1(输入侧契约,Step 2 核心)

顶层结构:source { filename, format, size_kb, parsed_at } + stats(计数摘要)+ warnings[](降级与不支持项)+ content(按格式区分)。设计决定:docx / md 的 content 直接复用 WordIR 的 blocks 词汇(外加 outline 标题树摘要),使“解析结果”与“目标输出”同构,天然可当 few-shot 示例,降低模型出错率。

| 输入格式 | content 结构 | 关键字段与限额 |
| --- | --- | --- |
| md / docx | blocks[](同 WordIR 词汇)+ outline[] | 保留章节层级与出现顺序;表格每张预览至多 20 行并标记 truncated。 |
| xlsx | sheets[] | 每 sheet:name、nrows、ncols、header_guess、preview_rows(至多 20x15)、col_stats(类型猜测 / 非空率 / 3 个样本值)、formula_count、merged_count、truncated。 |
| pptx | slides[] | 每页:index、layout_name、title、bodies[](文本框逐段)、tables[]、notes(演讲备注)、shape_warnings[](不支持形状)。 |

明示不支持 / 降级清单(解析器遇到即记 warning,严禁假装理解):

| 特性 | v1 处理方式 |
| --- | --- |
| Word 修订、批注、文本框正文、SmartArt | 跳过内容,warnings 记录数量与位置提示。 |
| Excel 公式求值、透视表、图表、VBA | 不求值不解析;仅统计 formula_count,其余记 warning。 |
| Excel 合并单元格 | 仅计数 + 取左上格值填充预览,标注 merged。 |
| PPT 动画、切换、母版继承细节、SmartArt | 跳过;动画与切换在输入侧记 warning(输出侧则是 lint 违规)。 |
| PPT 图表 | 只取图表标题与类型,不反解数据(P2 再议)。 |
| 嵌入图片(全格式) | 记录存在与尺寸,不搬运二进制(DOCX 图片透传列为 P2)。 |

### 3.3  DeckIR v1.6(PPT 输出契约,Step 3 核心)

meta 字段:title(必填)、subtitle、author、date、classification(默认 HUAWEI CONFIDENTIAL)、theme(默认 hw_v1)。slides[].layout 枚举 13 种,覆盖 v1.0 要求并受控新增流程与时间线:

| layout | 必填字段(可选项加问号) | 渲染要点 |
| --- | --- | --- |
| cover | title;subtitle? presenter? date? | 大标题 + 红色装饰条 + 页脚密级;不放真实 logo,用占位。 |
| agenda | items[2..8] | 编号目录;超过 5 条自动两栏。 |
| section | index, title;subtitle? | 大号章节数字 + 标题,统一分隔页样式。 |
| title_bullets | title, bullets[{text, level:1\|2}](至多 7 条) | 单条不超 60 字,超限触发 HW-W03。 |
| two_column | title, left, right(列 = heading? + bullets 或 text) | 左右等宽,列内小标题加粗。 |
| table | title, table{ header, rows; column_groups?, row_groups?, cell_spans?, col_widths?, conclusion_col? }(数据区至多 12x8) | 方案对比表 / 决策矩阵;表头红底白字,支持分组表头、合并单元格、重点单元格黄 / 青强调、短列表与结论列。 |
| cards | title, cards[2..4]{ title, desc, tag? };variant:default\|kpi | 等宽卡片;KPI 模式中 title/desc/tag 分别表示指标名、核心数值、趋势或口径。 |
| chart | title, chart{ kind: bar\|line\|pie, orientation:vertical\|horizontal, categories, series; unit?, thresholds?, show_data_labels?, legend_position?, side_conclusion?, side_table? } | 指标 / 性能图表页;horizontal 仅适用于 bar 并生成原生横向数据条;阈值线方向跟随数值轴;line/pie 保持 vertical。 |
| architecture_diagram | title, nodes[{id,text,type,group?,position?,size?}], edges[{from,to,label?,style,direction}], groups[{id,label,node_ids}], manual_hints? | 架构图可编辑骨架;节点、连接符、虚线分组框均为独立 PPT 对象;默认只承诺确定性分层布局和人工可调,不承诺一键成品。 |
| process_flow | title, steps[2..7]{id,title,description?}, orientation:horizontal\|vertical | 线性流程;按数组顺序连接,步骤框与箭头均为独立可编辑对象;分支流程继续使用 architecture_diagram。 |
| timeline | title, milestones[2..8]{label,title,description?,status}, orientation:horizontal\|vertical | 时间线 / 简化路线图;status 限 completed/current/planned;不表达精确 Gantt。 |
| image | title;image_ref 或 placeholder, caption? | 外网使用 16:9 灰底占位框 + 题注,明确等比放入且禁止随意裁切;真实图片透传仍为 P2。 |
| conclusion | title, bullets(至多 5 条);cta? | 结尾页,可带行动号召一句。 |

最小合法样例(4 页演示):

```
{
  "ir_type": "deck", "ir_version": "1.6",
  "meta": { "title": "Q3 业务汇报", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1" },
  "slides": [
    { "layout": "cover", "title": "Q3 业务汇报", "subtitle": "命令行文档工具链",
      "presenter": "张三", "date": "2026-07" },
    { "layout": "agenda", "items": ["业务回顾", "关键进展", "风险与对策", "下步计划"] },
    { "layout": "title_bullets", "title": "关键进展", "bullets": [
        { "text": "主链路全通:输入解析到合规检查", "level": 1 },
        { "text": "stub 模式支持断网演示", "level": 2 } ] },
    { "layout": "cards", "title": "三大能力", "cards": [
        { "title": "解析", "desc": "docx / xlsx / pptx 转结构化摘要" },
        { "title": "生成", "desc": "WordIR / DeckIR 一键渲染" },
        { "title": "合规", "desc": "华为风格检查报告" } ] }
  ]
}
```

DeckIR 校验错误码沿用 WordIR 的分层思路,前缀 D:D001 JSON 不合法、D002 缺 meta.title、D003 未知 layout、D004 该 layout 缺必填字段、D005 表格超限 / 行列不规整 / 分组或合并越界、D006 bullets 超条数;W1xx 为可自动降级项(如 agenda 超 8 条截断)。页数合法范围 1-30,演示目标 5-12 页。

## 4  Step 1 细化:AICoding 搞定 Word 输出(对应 v1.0 第 3.1 节)

目标:给定模型返回的任意文本,要么产出结构完整、格式统一、可编辑的 DOCX,要么给出精确到字段的错误提示。任务卡如下(“验收标准”即完成判据,写不出断言的验收一律不算):

| 编号 | 任务 | 关键实现点 | 验收标准 | 预估 |
| --- | --- | --- | --- | --- |
| S1-1 | WordIR v1.0 定稿与校验器 | pydantic 模型;错误码表落码;validate_word_ir() 校验函数;Schema 快照导出 | 10 个非法样例逐一命中预期错误码;Schema 文件入库 | 1.0 天 |
| S1-2 | 剥壳器 + IR 修复回路 | 三形态剥壳(纯 JSON / 代码块 / 带解释);校验失败回喂错误码限重试 2 次;失败附原文前 200 字(见 §5.3) | 三形态用例全过;注入可修复错误经回路后通过,不可修复者稳定报 E00x | 1.0 天 |
| S1-3 | DOCX 渲染核心 | 标题 1-4 级、段落、两级列表、quote/note、分页;页眉页脚 + 密级 + 页码;样式集中 STYLES | 样例 1、2 渲染后回读断言全过;Word 中可直接编辑 | 2.0 天 |
| S1-4 | 表格渲染 | 表头加粗底纹、比例列宽、跨页续排(表头重复)、超限截断 + W103 | 样例 3 通过;100 行 x 12 列极限表可渲染不崩 | 1.0 天 |
| S1-5 | 官方样例与失败提示 | 3 个正样例:纯文本报告 / 带列表方案 / 带表格业务说明;5 个失败样例配文案 | 文案评审通过;失败样例进回归集 | 0.5 天 |
| S1-6 | 测试与使用说明 | golden 回读断言(标题数 / 表格尺寸 / 页脚文案);README 补“Word 输出”章节 | pytest 全绿;新人照文档 10 分钟内复现样例 | 1.0 天 |

### 4.1  Step 1 完成定义(DoD)

- 给定合法 WordIR,一条命令 / 一次点击产出 DOCX,含页眉页脚与密级文案。
- 3 个官方样例可复现,产物与 expected 断言一致;5 类失败输入报错准确、提示可执行。
- 模型输出的三种形态(裸 JSON、代码块、混杂解释)均能进入统一校验流程。
- 相关 pytest 全绿;使用说明使新人可独立复现。

## 5  Step 2 细化:Word / Excel / PPTX 输入 AICoding(对应 v1.0 第 3.2 节)

| 编号 | 任务 | 关键实现点 | 验收标准 | 预估 |
| --- | --- | --- | --- | --- |
| S2-1 | Markdown 解析 | 标题 / 段落 / 列表 / 表格转 blocks;outline 摘要 | md 样例往返(md 到 IR 再到 DOCX)不丢结构 | 0.5 天 |
| S2-2 | Word(docx)解析 | 标题层级双策略(样式名 + outlineLevel);列表识别;表格 20 行截断;warnings | docx 样例产出 blocks + outline;不支持项全部入 warnings | 1.0 天 |
| S2-3 | Excel(xlsx)解析 | read_only + data_only;预览 20x15;列画像(类型猜测 / 非空率 / 样本);公式与合并计数 | 台账样例摘要字段齐全;10MB 文件解析小于 5 秒 | 1.0 天 |
| S2-4 | PPT(pptx)解析 | 每页标题 / 文本框 / 表格 / 备注;组合形状递归展开;不支持项记 warning | 汇报样例 8 页逐页摘要正确;动画等入 warnings | 1.0 天 |
| S2-5 | Prompt 模板与组装 | 四段式模板(见 5.1);按优先级截断;est_chars;确定性输出 | 同一输入两次生成逐字节一致;超长输入正确截断并在 Prompt 中声明 | 1.0 天 |
| S2-6 | 复现实验与解析测试 | demo_e2e.py 打通四格式;解析单测每格式至少 5 例(正常 / 空 / 坏文件 / 超大截断 / 特性降级) | 一条命令完成“文件到 DOCX”;单测全绿 | 1.0 天 |

### 5.1  Prompt 模板(四段式骨架,存于 prompting/templates/)

```
[角色] 你是企业文档结构化助手。
[任务] 阅读下方 DocumentIR,生成一份 <目标文档说明>,输出必须符合 WordIR v1.0(或 DeckIR v1.6)Schema。
[输出纪律] 只输出一个裸 JSON 对象,不得使用代码围栏或附加文字;不得新增 Schema 之外的字段;
          表格不超过 <上限>;要点每页不超过 7 条。
[目标 Schema 摘要] <内嵌字段说明或精简 JSON Schema,由 ir 包自动生成,禁止手抄>
[输入 DocumentIR] <按优先级截断后的 JSON:标题 > 表头 > 关键段落 > 预览行>
[若无法完成] 不输出半截 IR;由调用侧记录明确错误并进入修复回路,不要编造内容。
```

截断策略集中在 builder.py:max_chars 默认 12000(可配,落在 A7 约定的 8K–16K 单次输入区间内);逐级丢弃顺序为 预览行、次要段落、表格尾行,每次丢弃都在 Prompt 末尾追加一行“已截断说明”,让模型知道信息不完整。

### 5.2  Step 2 完成定义(DoD)

- md / docx / xlsx / pptx 四格式各至少 1 个样例可解析,DocumentIR 字段齐全、warnings 如实。
- 同一输入文件生成的 Prompt 稳定可复现;把 AICoding 返回的 JSON 存为 IR 后能走通校验与渲染。
- AICoding 交互路径固化为三步:生成 Prompt → 交给 AICoding → 保存返回 JSON;命令行下可复现,产出的 IR 能走通校验与渲染。

### 5.3  IR 修复回路与结构化输出(提升合法率,降低人工返工)

- 修复回路:剥壳 + 校验失败时,把错误码与定位回喂给模型,附“只修正这些问题、仍只输出一个裸 JSON 对象”的追问,限重试 2 次;仍失败才落为 E00x / D00x 交人处理。回路默认开,次数与开关可配。剥壳器继续兼容历史代码围栏和夹带解释文字的输出。
- 结构化输出优先:若目标模型 / 通道支持约束解码或 structured outputs,直接以 IR 的 JSON Schema 约束生成,“能否吐出合法 JSON”基本不再是问题;不支持时退回“输出纪律段 + few-shot + 修复回路”。
- few-shot 用真样例:提示里的示例直接取 samples/ir 下正样例(与 DocumentIR 同构),不手写、不与 Schema 漂移。

> **注** 这些只解决“格式合法率”。版式选得对不对、摘要有无失真、有无编造属于语义质量,靠 prompt 调优 + 人工抽查,不在自动回路的保证范围内(见 §10 两道人工终审)。

### 5.4  输入边界样例分类学与降级契约(逼出对真实脏文件的防御)

解析器只对着“干净样例”写必然漏。把要处理的脏情况列成分类学,每类规定“检测 → 降级 / warning 契约”,并为每类至少备一个 fixture:

| 脏情况类别 | 降级 / warning 契约 |
| --- | --- |
| 合并单元格(xlsx) | 计数 merged_count + 取左上格值填充预览,标注 merged(见 §3.2)。 |
| 嵌套 / 组合形状(pptx) | 递归展开取文本;展开失败记 shape_warnings 并跳过该形状。 |
| 修订 / 批注 / 文本框正文(docx) | 跳过内容,warnings 记录数量与位置提示。 |
| 内嵌对象 / 图片 / OLE | 记录存在与尺寸,不搬运二进制(DOCX 图片透传为 P2)。 |
| 混合 / 异常编码、超长单元格 | UTF-8 兜底;解码失败记 warning;超长按上限截断 + W103。 |
| 超大文件 / 超大表 | read_only + 预览截断;解析超时或超内存记 warning 并给出“已处理范围”。 |

- **真实语料是硬要求:** 仅靠上表构造的样例不足以覆盖现实。开工首周需向无线部门收集至少各 3 个真实 docx / xlsx / pptx(脱敏后)纳入 fixtures,解析回归以它们为准。这是文档无法替代、必须由人提供的资产(见 §10、附录 B)。

## 6  Step 3 细化:华为风格黄区 PPTX 工具(对应 v1.0 第 3.3 节)

| 编号 | 任务 | 关键实现点 | 验收标准 | 预估 |
| --- | --- | --- | --- | --- |
| S3-1 | 风格调研与 tokens 定稿 | 产出 docs/风格规范.md 与 themes/hw_theme.json;标注来源与近似声明 | 评审通过;渲染器取值零硬编码,改 json 即改全局 | 1.0 天 |
| S3-2 | P0 版式渲染(五种) | cover / agenda / section / title_bullets / table;页脚三段式 | 五版式样例渲染后 lint 零 Error | 2.0 天 |
| S3-3 | P1 版式渲染(三种 + chart 增强 + image 降级) | two_column / cards / conclusion;chart 走原生图表,image 走占位降级并输出说明文案 | 十一版式样例全部可渲染;chart 为可编辑原生图表;image 降级页有明确说明 | 1.0 天 |
| S3-4 | 合规检查器与报告 | 6.3 规则表全部落码;对渲染产物回读检查;JSON + 可读双格式报告 | 每条规则正反例各至少 1;人工注入违规即刻命中 | 1.0 天 |
| S3-5 | stub 端到端演示 | md 摘要经 stub generator 到 DeckIR 到 PPTX 到 lint,一条命令 | 断网环境跑通;产出 5-12 页可编辑 PPTX | 0.5 天 |
| S3-6 | 黄区接入说明 | 两个替换点清单、环境变量、内网自测步骤、离线安装指引 | 评审通过;他人按文档可独立执行 | 0.5 天 |

### 6.1  华为风格 tokens v0.9(外网近似值,单点收敛于 hw_theme.json)

| token | 默认值(外网近似) |
| --- | --- |
| 主色 hw_red | #C7000B(近似值;进内网以官方 CI 定稿,仅改此文件) |
| 文字色阶 | 标题 #1F1F1F;正文 #333333;辅助 #595959;弱化 #8C8C8C |
| 背景色 | 页面 #FFFFFF;卡片 / 表头 #F5F5F5 |
| 字体链 | 外网主用 微软雅黑,回退 Noto Sans CJK;HarmonyOS Sans SC 为内网目标(内网优先),西文 Arial |
| 字号阶(pt) | 封面主标 40 / 副标 20;页标题 28;正文 16;注释 12;页脚 9;下限 10.5 |
| 版心 | 16:9(13.33 x 7.5 英寸);四边距 0.6 英寸;标题区高 1.1 英寸 |
| 版面网格 | 12 栏网格 + 8pt 基线;元素左右吸附到栏、上下吸附到基线(见 §6.3 HW-W06) |
| 关键坐标 | 标题框 left 0.6" / top 0.5" / w 12.13" / h 1.0";正文区 top 1.7";页脚 top 7.0"(均可配) |
| 元素间距 | 段间 ≥ 8pt;卡片间距 0.3";块到页边 ≥ 0.4"(过近触发 HW-W07) |
| 对比度 | 正文 / 背景对比度 ≥ 4.5:1(WCAG AA),低于则告警(HW-W09) |
| 页脚三段式 | 左:密级(取 meta.classification);中:留空或版权;右:页码 |
| 禁用项 | 动画、切换、夸张阴影 / 渐变、白名单外字体、真实 logo(外网用占位) |

> **注** 心声 / 3ms 为内网资源,外网阶段以公开发布会与白皮书风格加通用商务规范近似,并在风格规范.md 中逐条标注“待内网校准”;这正是 I3 不变量的意义——校准时只改 hw_theme.json。

### 6.2  渲染实现要点

- 全部版式自绘(文本框 + 形状),不依赖模板母版占位符,避免“母版找不到”类环境问题;主题值一律读 hw_theme.json。
- 每页固定绘制页脚三段式与顶部标题区;cover 与 section 使用红色装饰条形成家族感。
- 产物必须可编辑:文本是真文本框、表格是真表格;禁止把内容画成图片。
- chart 版式使用 python-pptx 原生图表;bar / line 支持阈值线、数据标签、图例、单位、侧边结论 / 小表;pie 保留基础图兼容。

### 6.3  合规检查规则表(lint;对渲染产物回读检查,外部 PPTX 亦可复检)

| 编号 | 级别 | 规则 | 检测方式(python-pptx 回读) |
| --- | --- | --- | --- |
| HW-E01 | Error | 任一页页脚缺少密级文案 | 遍历每页形状,查找文本包含 meta.classification 的页脚区文本框 |
| HW-E02 | Error | 出现字体白名单之外的字体 | 遍历 run.font.name,与 theme 白名单比对(None 视为继承默认,放行) |
| HW-E03 | Error | 存在动画或切换效果 | 读取 slide 底层 XML,检测 timing / transition 节点 |
| HW-W01 | Warning | 正文字号小于 10.5pt | run.font.size 换算 pt 比对(None 继承默认视为合格) |
| HW-W02 | Warning | 使用主题色板之外的颜色 | 收集 RGB 值与 theme 色板(含灰阶)白名单比对,统计越界次数 |
| HW-W03 | Warning | 单页要点超 7 条或单条超 60 字 | 按版式统计 title_bullets / two_column 的条目 |
| HW-W04 | Warning | 表格超过 12 行或 8 列 | 遍历 GraphicFrame 表格行列数 |
| HW-W05 | Warning | 总页数超过 30 | len(slides) |
| HW-W06 | Warning | 文本框未吸附到 12 栏网格(左右边界偏离栏线超阈值) | 读 shape.left / width 换算栏位比对 |
| HW-W07 | Warning | 元素间距或到页边距小于下限(拥挤 / 重叠) | 两两包围盒间距 + 到页边距计算 |
| HW-W08 | Warning | 关键框坐标偏离 theme 规定(标题 / 页脚不在位) | shape.top / left 与 theme 坐标比对 |
| HW-W09 | Warning | 正文与背景对比度低于 4.5:1 | 前景 / 背景 RGB 算相对亮度比 |
| HW-I01 | Info | agenda 条目数与 section 页数不一致 | 结构统计,提示但不拦截 |

报告结构:{ summary: { errors, warnings, infos, pass }, items: [ { code, level, slide, message, suggestion } ] };存在任一 Error 则 pass = false。报告同时输出 JSON(机器用)与可读文本(演示用),命令行直接打印,若有 P2 界面则按级别分组展示。

### 6.5  视觉自评回路(P1 可选,把审美部分部分纳入自动循环)

lint 只管硬指标。可再加一层:把渲染出的 PPTX 每页导出为图片(soffice 转图),交视觉模型按固定 rubric(留白是否均衡、层级是否清晰、有无溢出 / 压字 / 错位、整体是否专业)打分并给修改建议,分数低于阈值触发一次自动重排。

> **注** 两条边界要认清:真·华为 CI(颜色 / 字体 / 母版)是数据,本就留内网校准;“这份到底拿不拿得出手”的最终判断是人的活,视觉模型分只是代理、可被糊弄——§10 保留人工视觉终审。此回路为 P1,时间紧可不做。另注:Mac 上没有微软雅黑,预览与本回路转图时字体会被替换,故 Mac 看到的排版不代表 Windows 真实观感——视觉终审必须在 Windows 上做,或在 Mac 上装齐目标字体后再看。

### 6.4  黄区接入说明(docs/内网接入.md 必备内容)

- **只动两处:** 其一,generators/nga.py 实现 generate(鉴权、超时、重试、日志脱敏;密钥仅走环境变量 NGA_BASE_URL / NGA_TOKEN,严禁落盘)。其二,若使用华为官方渲染 Skill,则以 DeckIR 为输入契约对接,本地渲染器保留为回退开关。
- **明确不动:** parsers、prompting、ir、lint、CLI 命令与本地渲染器;这份“不动清单”写进文档,接入者照单核对。
- **内网自测顺序:** 离线 wheelhouse 安装,先跑 stub 全链路证明环境正常,再切 NgaGenerator 做单页冒烟,最后全量演示。
- **安全约定:** 历史记录默认不保存模型密钥与原始敏感提示词(可配);示例数据全部使用脱敏样例。

## 7  测试与验收

### 7.1  测试分层与覆盖率目标

- **单元测试:** 解析器每格式至少 5 例;IR 校验正例加全部错误码反例;lint 每条规则正反例各至少 1;渲染 golden 用回读断言。
- **契约测试:** 三份 JSON Schema 做快照比对;改字段而未升 ir_version 或未过评审即挂测试(见 §3.0),防止“悄悄改契约”。
- **端到端:** CLI 级 stub 全链路(四格式各一条:parse → prompt → render → check 一条命令跑通);另保留 1 条“文件到 PPTX”的完整演示链路。
- **覆盖率:** parsers + ir + lint 三包不低于 80%,后端整体不低于 70%;因不依赖 AI,覆盖率可在 stub 通道下稳定复现。

### 7.2  一键验收命令

```
pytest backend/tests -q --cov=app --cov-report=term-missing
python scripts/demo_e2e.py samples/input/quarterly_report.md --target word --generator stub
python scripts/demo_e2e.py samples/input/quarterly_report.md --target deck --generator stub --lint
python scripts/verify.py        # 开发机(Mac/类 Unix)一键出验收结论;Windows 目标机用 verify.ps1(见 §7.4),二者等价
```

### 7.3  验收矩阵(对齐 v1.0 六条验收标准,逐条落到操作与判据)

| 验收项 | 操作 | 通过判据 |
| --- | --- | --- |
| Word 输出 | 用 samples/ir 下带表格的合法 WordIR 调渲染(命令或界面) | 产出可编辑 DOCX;标题 / 列表 / 表格 / 页眉页脚齐全;golden 断言与 expected 一致 |
| 多格式输入 | 对 samples/input 下 md / docx / xlsx / pptx 各执行 parse.py + prompt.py | 均产出 DocumentIR 与 Prompt;重复执行结果逐字节一致 |
| PPTX 生成 | quarterly_report.md 走 deck 链路(stub generator) | 产出 5-12 页可编辑 PPTX,含封面 / 目录 / 要点 / 表格或卡片 |
| 华为风格约束 | 对上一步产物执行 check.py;再对人工注入违规的样例执行 check.py | 正常产物零 Error;注入样例逐条命中对应 Error / Warning |
| 可迁移性 | 断网且无任何密钥环境执行 verify.py(Mac)/ verify.ps1(Windows),stub 通道 | 全链路通过,证明不依赖真实 NGA、华为 Skill 与联网 AI |
| 测试覆盖 | 查看覆盖率报告 | 后端全绿且核心三包不低于 80% |

### 7.4  Windows 离线验收 checklist(一次性人工在真机执行)

打包与离线安装无法在 Linux 沙箱或 CI 里完全验证,须由人在一台干净 Windows 机上按下列步骤跑一遍并逐项打勾;这是流程动作,不是设计缺口。

1. 构建 Windows 平台 wheelhouse:在 Windows 机上 make_wheelhouse.py,或在 Mac 上用 pip download --platform win_amd64 --python-version 3.12 --only-binary=:all: 拉全依赖(含 lxml、pydantic-core 等平台 wheel),产出带 requirements 锁定与 hash 的 wheelhouse/。
2. 拷贝项目 + wheelhouse 到一台干净、断网的 Windows 机。
3. pip install --no-index --find-links wheelhouse -r requirements.txt:安装成功、无缺包。
4. 断网执行 verify.ps1:stub 全链路 + pytest + 覆盖率全绿。
5. 用真实样例各跑一次 word / deck,产物能在 Word / PowerPoint 正常打开编辑。
6. 记录 Python 版本、机器环境与结果截图,纳入验收手册。

## 8  排期(按天,含 4 个检查点)

检查点(Checkpoint)是与导师的半小时评审:C0 契约冻结、C1/C2/C3 分阶段演示。检查点未过,下阶段不开工,先修再走。预估已含缓冲;若仍延期,砍序为:chart 真图表、DOCX 图片透传、P2 Web 界面(全部是 P2 弹性项)。

| 时间 | 任务 | 当日产出 / 检查点 |
| --- | --- | --- |
| W1-D1 | 环境核对(Python 3.12 / 现有 MD→DOCX / Flask 基线);与导师过附录 A 开放问题 | 环境与开放问题确认纪要 |
| W1-D2 | 走读现有代码;绘制 CLI 主链路与模块对照图 | 架构一页图 |
| W1-D3 | 撰写《现状与能力边界说明》(不超过 2 页) | 文档评审通过 |
| W1-D4 | S1-1:三份 IR 用 pydantic 落码 + 校验器 | 检查点 C0:IR 契约冻结评审 |
| W1-D5 | S1-2:剥壳器 + 失败样例库雏形 | 三形态输入均可提取 |
| W2-D1 | S1-3:渲染核心(标题 / 段落 / 列表) | 样例 1 渲染通过 |
| W2-D2 | S1-3:页眉页脚 / 密级 / STYLES 收口 | 样式零硬编码 |
| W2-D3 | S1-4:表格渲染 | 样例 3 渲染通过 |
| W2-D4 | S1-5:3 正样例 + 5 失败样例与文案 | 失败提示评审通过 |
| W2-D5 | S1-6:golden 测试 + 使用说明 | 检查点 C1:Step 1 演示 |
| W3-D1 | S2-1 md 解析;S2-2 docx 解析(起) | md 样例进入主链路 |
| W3-D2 | S2-2 docx 解析(收)+ warnings 清单 | docx 样例进入主链路 |
| W3-D3 | S2-3 xlsx 解析 | 10MB 小于 5 秒;摘要字段齐 |
| W3-D4 | S2-4 pptx 解析 | 逐页摘要 + 备注可用 |
| W3-D5 | S2-5 Prompt 组装 + S2-6 复现实验 | 检查点 C2:文件-Prompt-存IR-DOCX 全程演示 |
| W4-D1 | S3-1 风格 tokens + 风格规范.md | hw_theme.json 评审通过 |
| W4-D2 | S3-2 P0 版式:cover / agenda / section | 三版式过 lint |
| W4-D3 | S3-2 P0 版式:title_bullets / table | 五版式全通 |
| W4-D4 | S3-3 P1 版式 + S3-4 lint(起) | two_column / cards / conclusion 可渲染 |
| W4-D5 | S3-4 lint(收)+ 报告 + S3-5 stub 演示 | 检查点 C3:Step 3 演示 |
| W5-D1 | 全链路回归与缺陷修复 | 验收矩阵首轮全过 |
| W5-D2 | 补测试,覆盖率达标 | 核心三包不低于 80% |
| W5-D3 | 文档四件:README / 使用说明 / 内网接入 / 验收手册 | 文档齐备可交接 |
| W5-D4 | S3-6 接入说明定稿 + 演示材料包(样例 / 截图 / 录屏脚本) | 演示包评审通过 |
| W5-D5 | 总结汇报;移交遗留与 P2 清单 | 终验 |

## 9  风险登记册(细化 v1.0 第 7 节)

| 风险 | 触发信号 | 应对措施 | 等级 |
| --- | --- | --- | --- |
| 模型 JSON 合法率低 | E001 / E002 高频出现 | 强化 Prompt 输出纪律段;提供“修复重试”追问话术模板;失败样例入库做回归 | 高 |
| AICoding 交互往返低效 | 单轮往返超过 5 分钟 | 把“生成 Prompt → 交 AICoding → 存 JSON”固化为脚本三步;探索用捕获脚本半自动化(见附录 A) | 中 |
| Excel / PPT 语义复杂 | 解析报错或耗时超标 | 坚守“结构摘要”边界;复杂特性一律入降级清单;read_only + 截断保性能 | 中 |
| 华为风格无法精确复刻 | 视觉评审意见分歧 | 以 hw_theme.json 单点收敛;外网只承诺“合规检查通过”,像素级还原留给内网 Skill | 中 |
| 字体环境差异 | 渲染验证乱码或字体替换 | 白名单 + 回退链;验收以 Windows 上 Word 打开效果为准 | 低 |
| 内网离线装不上 / 平台不符 | 内网 pip 无法联网,或 Mac 下载的包在 Windows 装不上 | wheelhouse 必须为 Windows 平台构建(--platform win_amd64 或在 Windows 机上做);第 5 周前完整演练一次离线安装 | 中 |
| 任务范围蔓延 | 新需求临时插入 | 一律登记 P2 清单,检查点评审再定优先级;主链路之外不即时响应 | 中 |

## 10  最终交付清单与完成定义

1. 可运行的命令行文档生成工具链:支持 Word 输出与华为风格 PPTX 输出两条主流程,含 stub 断网演示模式;Web 界面为可选 P2。
2. 三份 IR 规范:文档 + JSON Schema 文件 + 正 / 反样例,契约测试保护。
3. 四个输入解析器(md / docx / xlsx / pptx)与配套样例、warnings 降级清单。
4. Prompt 模板库与组装器:四段式模板、截断策略、确定性输出。
5. DOCX 渲染器:样式表集中、失败提示齐全、3 个官方样例。
6. 华为风格主题(hw_theme.json)+ PPTX 渲染器:13 版式(chart 为原生图表,image 允许占位降级,process_flow / timeline 为原生可编辑形状)。
7. 合规检查器与双格式报告,支持外部 PPTX 复检。
8. 测试套件与覆盖率报告:单元 + 契约 + 端到端,一键 verify 脚本。
9. 文档四件:README、使用说明、内网接入说明、验收手册(含全部验收命令)。
10. 演示材料包:输入样例、生成结果、命令行运行截图、失败提示截图、录屏脚本。
11. 真实文件测试语料:各 ≥ 3 个脱敏真实 docx / xlsx / pptx 纳入 fixtures,解析回归以它们为准(见 §5.4)。
12. 健壮性机制落地:契约快照测试、IR 修复回路、可测量版式 lint 规则(HW-W06~W09)、边界样例降级契约、Windows 离线验收记录,均随代码入库(见 §2.7)。

**通用完成定义(适用于每一张任务卡):**五件套齐备——代码、样例、失败提示、最小测试、文档;任何一件缺失,该任务卡视为未完成,不进入下一张。

**两道人工终审(不可省):**PPTX 交付前须由人做一次视觉终审(观感 / 专业度),内容交付前须对样例产物做一次语义抽查(有无失真 / 编造);lint 全绿不等于可交付。

### 10.1  给实习生的执行心法

- 先把一条链路跑通:输入文件、结构化 IR、AICoding 产 JSON、本地渲染、合规检查、产物落盘;任何新增功能都要服务这条主链路。
- 永远不信任模型文本:先剥壳、再校验、后渲染;报错要能指导下一步动作。stub 通道随时可离线验证下游。
- 遇到不确定:先写进附录 A 的待确认清单并@导师,同时按本文默认值继续推进,不空等。
- 每天下班前对照当日任务卡的验收标准自查;周五检查点前把演示脚本先自己跑一遍。

## 附录 A  确认清单

### A.1  已确认默认(开工前对齐,已回填正文)

| 事项 | 确认结论 |
| --- | --- |
| 密级 / 页脚 | 保持默认:DOCX “内部公开”、PPTX “HUAWEI CONFIDENTIAL”,均可配置。 |
| 字体选型 | 外网以微软雅黑为主选,HarmonyOS Sans 作为内网目标字体。 |
| AICoding 输入 | 单次输入按 8K–16K 字符规划;以贴入 Prompt 内容为准,不假设直接读取本地文件。 |
| AICoding 输出 | 基本稳定输出一个 json 代码块,偶夹解释文字,由剥壳器统一处理。 |
| JSON 落盘 | 先人工另存(P0);排期有余量再做脚本半自动(P1);全自动(P2)待内网接口。 |
| Web 界面 | 暂缓,专注 CLI 核心;如做则复用 Flask、仅“上传 + 展示 + 报告”三块(P2)。 |

### A.2  决议与剩余内网确认

已决事项:

1. DeckIR 以当前 v1.6 Schema 与本文 3.3 节为权威;1.4/1.5 在校验入口确定性迁移到 1.6,更早数据如需长期保存须显式迁移,renderer 不暗自兼容非法 IR。
2. chart 版式使用 python-pptx 原生可编辑图表;bar/line 增强和基础 pie 已落地,不再作为未决项。

仍需导师 / 内网确认:

1. 历史 / 运行记录是否需要?若需要,保存范围如何(是否含原始 Prompt 与输入内容)?当前 P2 默认不做。
2. DOCX 输出是否需要图片透传(输入文档中的图片带到输出)?当前列为 P2。
3. 内网渲染 Skill 的调用形态(同步 HTTP、文件落盘还是其他)?以便接入实现按真实协议落地。

## 附录 B  样例文件清单(samples/ 规划)

| 路径 | 用途 |
| --- | --- |
| samples/input/quarterly_report.md | 主演示输入:季度汇报叙事,覆盖标题 / 列表 / 表格 |
| samples/input/需求说明.docx | docx 解析用例:两级标题、列表、表格、少量文本框(验证降级) |
| samples/input/销售台账.xlsx | xlsx 解析用例:3 个 sheet,含公式与合并单元格 |
| samples/input/项目汇报.pptx | pptx 解析用例:8 页,含表格与演讲备注 |
| samples/input/real/(各 ≥ 3,脱敏) | 真实 docx / xlsx / pptx 语料,覆盖 §5.4 边界情况;文档无法替代,须人工收集 |
| samples/ir/word_valid_01_plain.json 等 3 个 | Step 1 官方正样例:纯文本报告 / 带列表方案 / 带表格业务说明 |
| samples/ir/word_invalid_*.json(10 个) | 覆盖 E001-E006 与 W 系全部错误码的回归集 |
| samples/ir/deck_valid_full.json | DeckIR 十三版式全覆盖演示样例 |
| samples/ir/deck_invalid_*.json(6 个) | DeckIR 校验错误码回归集 |
| samples/ir/deck_lint_violation.json | 人工注入合规违规,用于演示 lint 命中 |
| samples/expected/ | golden 基线:回读断言所需的结构性事实(JSON 描述,不比二进制) |
