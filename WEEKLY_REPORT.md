# 基于 IR 的可编辑 Office 文档生成系统

**汇报类型：** 项目周报 / 技术架构阶段汇报  
**汇报对象：** PL 及技术评审人员  
**汇报人：** 项目开发人员  
**统计时间：** 2026-07-17

> 本文件包含两套内容。生成 PPTX 时只取“第一部分：PPT 精简稿”；生成 DOCX/PDF 时只取“第二部分：Word/PDF 详细稿”。自动验证数字是 2026-07-17 的阶段快照，不代表内网真机与真实业务文件已经完成验收。

---

# 第一部分：PPT 精简稿

## 第 1 页：封面

**推荐版式：** `cover`

**标题：** 基于 IR 的可编辑 Office 文档生成系统

**副标题：** 将多格式业务资料转化为可校验、可编辑、可复现的 Word 与 PPT

**汇报人：** 项目开发人员  
**日期：** 2026-07-17

---

## 第 2 页：系统价值

**推荐版式：** `title_bullets`

**观点标题：** 系统的核心价值，是让模型负责内容组织，让确定性流水线负责交付质量

- **输入难统一：** Markdown、Word、Excel、PPTX 的结构不同，直接生成容易丢失标题、表格和关键事实。
- **模型输出不稳定：** JSON 可能带解释文字、字段错误或被截断，不能直接交给 Office 渲染器。
- **交付难验收：** 仅生成文件不够，还需要可编辑、可复现，并能给出结构化错误与合规报告。

**项目定位：** 建立一条围绕 IR 的本地确定性流水线，而不是让大模型直接“画”Word 或 PPT。

---

## 第 3 页：总体架构

**推荐版式：** `architecture_diagram`

**观点标题：** IR 将内容生成与 Office 渲染解耦，生成器可以替换，下游质量边界保持稳定

**架构节点：**

1. 输入资料：`MD / DOCX / XLSX / PPTX`
2. 解析层：`parsers`
3. 统一输入契约：`DocumentIR 1.1`
4. 提示词层：`prompting`
5. 生成器层：`Stub / Codex / 未来 NGA`
6. 质量闸门：`JSON 剥壳 -> Schema 校验 -> repair`
7. 输出契约：`WordIR 1.0 / DeckIR 1.6`
8. 渲染层：`DOCX renderer / PPTX renderer`
9. 检查层：`check_docx / check_pptx`
10. 最终产物：`可编辑 DOCX / PPTX + 合规报告`

**主数据流：**

```text
MD/DOCX/XLSX/PPTX
        -> parsers
        -> DocumentIR
        -> prompting
        -> generator
        -> JSON 剥壳 / IR 校验与修复
        -> WordIR 或 DeckIR
        -> renderer
        -> DOCX 或 PPTX
        -> lint / check report
```

---

## 第 4 页：输入解析层

**推荐版式：** `table`

**观点标题：** 四类输入先转成统一 DocumentIR，后续生成逻辑不再绑定具体文件格式

| 输入 | 核心技术 | 主要提取内容 | 边界处理 |
| --- | --- | --- | --- |
| Markdown | Python 文本解析 | 标题、段落、列表、表格 | UTF-8 优先，常见中文编码回退，畸形结构告警 |
| DOCX | `python-docx` + OOXML 检测 | 段落、样式、表格、图片线索 | 修订、批注、复杂对象记录 warning |
| XLSX | `openpyxl` | 多 Sheet、表格预览、公式与统计 | `read_only`、采样、隐藏行列跳过、超限降级 |
| PPTX | `python-pptx` + OOXML 检测 | 页面文字、表格、备注、形状线索 | 组合形状、SmartArt 等复杂对象明确降级 |

**输出原则：** 能可靠提取的内容进入 `DocumentIR`；无法完整还原的对象必须留下 warning，不静默伪装成成功理解。

---

## 第 5 页：IR 契约与质量闸门

**推荐版式：** `cards`

**观点标题：** 三份版本化 IR 把输入事实、Word 结构和 PPT 版式冻结成可测试契约

| 契约 | 负责内容 | 当前版本 |
| --- | --- | --- |
| DocumentIR | 统一记录来源、结构摘要、内容块和解析告警 | 1.1 |
| WordIR | 描述标题、段落、列表、表格、占位区与分页 | 1.0 |
| DeckIR | 描述页面类型、页面内容、图表、表格和架构节点 | 1.6 |

**关键技术：**

- 使用 **Pydantic v2** 定义字段、枚举、数量和跨字段约束。
- 导出 **JSON Schema** 给模型与 CLI 共用，并用版本快照和历史哈希防止契约静默漂移。
- 原始模型文本必须经过 **JSON 剥壳、Schema 校验和有限修复**；失败时返回定位明确的错误码，不进入渲染器。

---

## 第 6 页：Prompt 与 Generator

**推荐版式：** `process_flow`

**观点标题：** 三阶段提示词先锁定事实再组织表达，Generator 接口让内外网模型可以替换

1. **事实提取：** 从 DocumentIR 提取方法、数据、结论、限制和来源证据。
2. **体裁骨架：** 按技术评审、Word 技术文档等体裁组织章节与页面关系。
3. **成稿表达：** 在输出预算内生成符合 WordIR 或 DeckIR 的完整 JSON。

**Generator 分层：**

- `StubGenerator`：规则化、确定性、断网可运行，用于测试和演示。
- `CodexGenerator`：用于外部模型链路验证，仍受同一 IR 质量闸门约束。
- `NgaGenerator`：已预留替换位置，尚未接入内网真实协议。

**弱模型兜底：** Prompt 明确字段结构、版式选择、每页内容密度和输出预算；脏 JSON、截断或内容矛盾由校验与错误报告暴露，而不是继续“尽力渲染”。

---

## 第 7 页：渲染与合规检查

**推荐版式：** `two_column`

**观点标题：** Office 产物由 Python 原生对象绘制，既可编辑，也能被程序回读检查

**左栏：确定性渲染**

- DOCX 使用 `python-docx`，支持标题、段落、列表、基础表格、引用/备注和图片占位。
- PPTX 使用 `python-pptx`，当前支持 13 类 DeckIR 版式。
- 决策矩阵、原生图表、流程、时间线和架构骨架均为可编辑对象，不是整页截图。
- 颜色、字体、字号、页边距和页脚从 `hw_theme.json` 主题 token 读取。

**右栏：产物级检查**

- 回读实际 DOCX/PPTX，而不是采信渲染器自报数据。
- 检查字体、字号、主题色、页边距、重叠/裁切、表格样式和页眉页脚。
- 以 `Error / Warning / Info` 分级输出 JSON 与 Markdown 报告。
- lint 全绿只代表自动规则通过，不能替代真实字体和业务语义下的人工终审。

---

## 第 8 页：阶段成果

**推荐版式：** `cards`，使用 KPI 变体

**观点标题：** 核心链路已在 Mac 构造样例和 Stub 环境闭环，具备继续接真实环境的基础

- **384 passed**：2026-07-17 阶段性 pytest 快照。
- **89.04%**：同一快照下的整体覆盖率，高于任务书 70% 门槛。
- **4 类输入**：MD、DOCX、XLSX、PPTX 均进入 Word/Deck Stub 端到端链路。
- **3 份 IR**：WordIR 1.0、DocumentIR 1.1、DeckIR 1.6。
- **13 类 PPT 版式**：覆盖基础页面、表格、图表、流程、时间线和架构骨架。
- **2 类可编辑产物**：DOCX 与 PPTX，并配套结构化检查报告。

**验证方式：** 单元测试、Schema 快照、正反样例、四格式 E2E、Office 产物回读和 `scripts/verify.py` 一键门禁。

---

## 第 9 页：当前边界与下一步

**推荐版式：** `conclusion`

**观点标题：** 本地确定性流水线已经成形，生产可用性还需在内网真实环境完成最后验证

**已经具备：**

- Mac 上的构造样例、Stub 生成、IR 校验、DOCX/PPTX 渲染与自动检查已经闭环。
- 系统架构支持替换 Generator，不需要重写解析、渲染和 lint。

**尚未完成：**

- NGA 真实协议、鉴权、超时重试与日志脱敏尚未接入。
- 真实脱敏业务文件、Windows 断网安装、目标字体/官方 CI 下的视觉终审尚未签收。
- 图片二进制透传、精确 Gantt、Word 决策矩阵完全对齐和一键成品级架构排版仍属后续能力。

**下一步优先级：**

1. 用脱敏真实文件核对解析内容和 warnings。
2. 进入内网接通 NGA，并验证弱模型下的 IR 合法率与内容质量。
3. 在 Windows、真实 Office 与目标字体环境完成离线安装和人工视觉/语义终审。

**结论：** 当前不是“模型直接生成 Office”，而是一套可校验、可替换、可复现的文档工程流水线。

---

# 第二部分：Word/PDF 详细稿

## 1. 项目概述

本项目面向技术方案、设计说明、评审材料和阶段汇报等办公场景，将 Markdown、DOCX、XLSX、PPTX 等已有资料统一解析，再生成可编辑的 Word 或华为风格 PPTX。系统重点解决三个问题：异构资料难统一、模型输出难约束、最终 Office 产物难复检。

项目不把大模型视为唯一核心，也不允许模型文本直接进入渲染器。系统真正交付的是一条围绕 IR 的确定性流水线：输入解析、Prompt 组装、Generator 产出、IR 校验与修复、本地 Office 渲染、产物级 lint 和自动验收。模型可以替换，但 IR、渲染和质量门禁保持稳定。

截至 2026-07-17，Mac 构造样例与 Stub 环境下的主链路已经闭环；真实 NGA、真实业务文件、Windows 离线环境及目标字体/CI 下的人工终审仍属于后续验收，不在本报告中写成已完成。

## 2. 为什么采用 IR 中间层

如果模型直接输出 DOCX/PPTX 绘制指令，内容、排版和模型能力会耦合在一起：模型更换后渲染逻辑容易失效，字段错误可能在生成 Office 文件时才暴露，内容丢失也难以追踪。项目因此把 IR 设为唯一契约，并明确以下不变量：

1. 输入文件先解析为 `DocumentIR`，不直接拼进渲染器。
2. Generator 只产出 WordIR 或 DeckIR 的原始 JSON 文本。
3. 原始文本必须经过 JSON 剥壳、Schema 校验和有限修复。
4. 非法 IR 返回结构化错误与定位，不做“尽力渲染”。
5. 渲染后的 DOCX/PPTX 还要再次回读检查，避免只验证输入 JSON、不验证真实产物。

这种设计把不稳定的模型输出限制在一个可替换边界内，使解析、渲染、lint 和测试能够在无模型、断网环境下独立运行。

## 3. 总体架构与数据流

系统采用分层流水线，各层只承担单一职责：

```text
输入层
MD / DOCX / XLSX / PPTX / 主题文本
                |
                v
解析层 parsers
结构提取 + 边界识别 + warnings
                |
                v
DocumentIR 1.1
统一的来源、结构摘要与内容事实
                |
                v
Prompting
Schema + 体裁规则 + few-shot + 输出预算 + 输入上下文
                |
                v
Generator
Stub / Codex / 未来 NGA
                |
                v
IR 质量闸门
JSON 剥壳 -> Schema 校验 -> 内容规则 -> 有限 repair
                |
           +----+----+
           |         |
           v         v
     WordIR 1.0   DeckIR 1.6
           |         |
           v         v
   DOCX renderer  PPTX renderer
           |         |
           v         v
    可编辑 DOCX   可编辑 PPTX
           |         |
           +----+----+
                v
       check / lint / report
```

主数据流可以概括为：

`parsers -> DocumentIR -> prompting -> generator -> IR validation/repair -> rendering -> lint`

WordIR 与 DeckIR 位于校验和渲染之间：前者描述 Word 文档块，后者描述 PPT 页面、版式和可编辑图形。最终报告位于产物之后，用实际 Office 文件中的字体、几何、样式和内容做复检。

## 4. 各层技术实现

### 4.1 输入解析层：把不同文件统一为 DocumentIR

解析层使用 Python 3.12 实现，按格式选择成熟的 Office 库，并把输出统一为 `DocumentIR 1.1`。

| 格式 | 主要技术 | 提取内容 | 健壮性策略 |
| --- | --- | --- | --- |
| Markdown | Python 文本读取与结构识别 | 标题、段落、列表、表格 | 显式 UTF-8；常见中文编码回退；畸形结构告警 |
| DOCX | `python-docx`、必要的 OOXML 检测 | 段落、标题、表格、图片线索、分节信息 | 修订、批注、嵌套对象等无法完整还原时记录 warning |
| XLSX | `openpyxl` | 多 Sheet、合并单元格、公式线索、预览与列画像 | `read_only`、预览截断、统计采样、隐藏行列跳过、超限降级 |
| PPTX | `python-pptx`、必要的 OOXML 检测 | 页面文本、表格、图表/图片线索、演讲备注 | 组合形状、SmartArt、复杂对象按可识别程度降级并告警 |

解析层的目标不是完整复制 Office 内部语义，而是提取后续内容生成所需的可靠事实。遇到无法理解或成本过高的对象，系统优先保留可追溯 warning，而不是静默丢失或把隐藏内容误带入摘要。

### 4.2 IR 契约层：把系统边界变成可执行规则

项目使用 Pydantic v2 定义三份 IR，并导出 JSON Schema：

| IR | 作用 | 版本 | 关键约束 |
| --- | --- | --- | --- |
| DocumentIR | 统一输入来源、结构、内容摘要和 warnings | 1.1 | 来源信息、统计、内容块和降级记录必须结构化 |
| WordIR | 描述 Word 文档结构 | 1.0 | block 类型、标题层级、表格列数和必填内容受约束 |
| DeckIR | 描述 PPT 页面与版式 | 1.6 | layout、页面字段、图表数据、表格跨度、架构节点/边受约束 |

Schema 同时服务于 Prompt、CLI 校验、正反样例和自动测试。版本快照与历史哈希用于发现“字段已经变化但版本号未升级”的契约漂移；旧版 DocumentIR/DeckIR 只在有明确、确定性的迁移规则时进行内存迁移，原始输入不被修改。

除了字段类型，校验层还检查内容关系，例如表格行列数是否一致、图表系列与分类数量是否一致、阈值与结论是否矛盾、架构图的边是否引用真实节点、流程步骤和时间线状态是否有效。这些规则用于兜住“JSON 格式合法但内容逻辑错误”的弱模型输出。

### 4.3 Prompting：先锁定事实，再组织结构，最后成稿

Prompt 组装不是简单拼接原文，而是包含目标 Schema、字段约束、体裁规则、版式选择、few-shot、输出预算和 DocumentIR 上下文。当前生成思路分为三个阶段：

1. **事实提取：** 优先保留方法名、参数、数据、对比、结论、限制与风险；输入没有的事实不得补写。
2. **体裁骨架：** 技术评审 PPT 强调观点标题、每页单一观点和证据支撑；Word 技术文档强调连续标题层级与完整论述。
3. **成稿表达：** 在字符预算和页数/深度要求内生成完整 IR JSON，不能因达到上限而输出半个 JSON。

系统还提供概览、标准、详细三档 Deck 深度分析。页数建议来自输入内容量和结构，而不是固定凑页；流程页、时间线页也只有在原文存在步骤或时间证据时才选用，避免为了版式丰富而编造流程。

### 4.4 Generator：模型可替换，但接口和下游不变

Generator 接口只负责接收 Prompt 并返回 IR 原始文本，当前分层如下：

| Generator | 作用 | 当前状态 |
| --- | --- | --- |
| StubGenerator | 根据 DocumentIR 规则化生成确定性 IR | 已用于断网测试、CLI 演示和四格式 E2E |
| CodexGenerator | 验证真实模型生成链路 | 已实现接口路径，输出仍进入统一校验与修复流程 |
| NgaGenerator | 面向内网 `codeagent.exe` 或既定 NGA 服务 | 仅预留接口，真实协议、鉴权和运行约束待内网确认 |

这种分层意味着接入 NGA 时只替换“获取 IR 原始文本”的位置，不需要重写 parser、renderer 或 lint。它也允许 CI 使用 Stub 保持结果确定，而真实模型测试单独评价 IR 合法率、事实一致性和内容质量。

### 4.5 IR 质量闸门：拒绝非法输入，而不是掩盖问题

模型输出可能包含 Markdown 围栏、解释文字、多段 JSON 或截断内容。系统先提取唯一 JSON 对象，再运行 Schema 与内容合理性校验；只有有限、确定且不改变语义的错误可以进入 repair。无法修复时，CLI 和界面应返回 IR、错误码和定位，允许人工修正后重试。

错误与合规信息按 `Error / Warning / Info` 分级。Error 阻止渲染；Warning 表示可继续但需要人工关注，例如解析降级、页面内容过密或架构图边数过多；Info 记录迁移和一般提示。这样可以让上层机器判断失败原因，而不是依赖 stderr 中的一段自然语言。

### 4.6 渲染层：生成可编辑 Office 对象

DOCX 渲染器基于 `python-docx`，支持标题、段落、列表、基础表格、引用/备注、分页、图片占位和页眉页脚。样式从统一主题读取，避免 Word 与 PPT 各维护一套会漂移的颜色与字体。

PPTX 渲染器基于 `python-pptx` 自绘，当前支持 13 类 DeckIR 版式：

`cover / agenda / section / title_bullets / two_column / table / cards / chart / image / conclusion / architecture_diagram / process_flow / timeline`

其中，表格支持方案对比和重点单元格；图表使用原生可编辑 chart 对象；流程、时间线和架构图由独立形状与连接线组成。架构图的定位是“自动生成可编辑骨架，再由人工精调布局”，不承诺一次生成即可达到正式汇报的视觉质量。

主题集中在 `hw_theme.json`，包括实测主红 `#C7000B`、accent 色系、中文/英文字体、字号层级、页面尺寸、页边距和页脚。普通演示页与表格/图表等高密度组件使用不同字号层级，避免把紧凑组件的 8-14pt 规格误用于封面和普通正文。

### 4.7 Lint 与验收：检查真实产物，而不只检查代码路径

DOCX/PPTX 生成后会被重新打开，检查真实字体、颜色、字号、表格样式、页眉页脚和 PPT 几何。PPT 的重叠、裁切和网格判断使用产物中的实际形状位置，不采信渲染器自报坐标。

`scripts/verify.py` 将以下门禁串成一键验收：

- 全量 pytest 与覆盖率门槛。
- 三份 JSON Schema 快照及版本历史检查。
- Word/PPT 正反样例与产物回读。
- MD、DOCX、XLSX、PPTX 到 WordIR/DeckIR，再到最终 Office 文件的 Stub E2E。
- 输入关键标题、段落、列表、表格数据、工作表、幻灯片及备注的事实贯通检查。

自动检查可以发现结构、样式和部分内容错误，但不能判断“像不像正式华为材料”或业务结论是否恰当，因此人工视觉和语义终审仍是交付条件。

## 5. 技术栈总览

| 技术 | 在系统中的职责 | 选择原因 |
| --- | --- | --- |
| Python 3.12 | CLI、解析、校验、渲染和测试的统一运行时 | 跨平台、Office 生态成熟、适合离线部署 |
| Pydantic v2 | IR 模型、字段/跨字段校验、JSON Schema 导出 | 契约可执行、错误可定位、便于版本管理 |
| python-docx | DOCX 解析与可编辑 Word 输出 | 直接操作 Word 结构，不依赖 HTML 转换 |
| openpyxl | XLSX 解析、只读预览和采样统计 | 支持多 Sheet、公式与合并单元格等结构 |
| python-pptx | PPTX 解析与原生可编辑形状/图表绘制 | 产物可编辑，符合项目的 Python 自绘路线 |
| pytest + coverage | 单元、集成、E2E 与覆盖率门禁 | 断网可复现，适合 Mac 开发和 Windows 验收复用 |
| JSON Schema + 快照哈希 | Prompt 约束、CLI 校验和契约防漂移 | 防止模型、代码和样例使用不同字段口径 |

## 6. 关键设计取舍

### 6.1 选择“IR 优先”，而不是模型直连渲染器

代价是需要维护三份契约、版本和迁移，但收益是错误可以在渲染前定位，Generator 可以替换，自动测试也不依赖真实模型。这是系统最核心的工程选择。

### 6.2 选择“可编辑原生对象”，而不是截图式输出

Word 段落、PPT 表格、图表、节点和连接线尽量使用 Office 原生对象，便于业务人员在最终交付前修改。代价是自动布局比图片生成更复杂，尤其架构图仍需要人工微调。

### 6.3 选择“明确降级并告警”，而不是假装完整解析

Office 文件中的修订、SmartArt、OLE、复杂组合对象很难由通用库完整恢复。系统在无法可靠提取时记录 warning，并说明跳过、采样或占位方式。这样会让报告中出现更多告警，但能减少内容丢失和敏感信息泄露的 false-green。

### 6.4 选择“Stub 保证确定性”，真实模型另行验收

Stub 让解析、Prompt、校验、渲染和 lint 在断网环境下稳定测试，但它不能代表真实模型的内容质量。NGA 接入后仍需单独评估 JSON 合法率、事实一致性、截断率和修复成功率。

## 7. 当前能力与阶段证据

截至 2026-07-17 的阶段性自动验收快照如下：

| 指标 | 结果 | 能说明什么 |
| --- | --- | --- |
| pytest | `384 passed` | 当前构造样例和自动回归全部通过 |
| 整体覆盖率 | `89.04%` | 高于任务书 70% 门槛 |
| 核心包覆盖率 | parsers `93.75%`、IR `93.84%`、lint `94.34%` | 核心契约与质量路径有较高测试覆盖 |
| 输入链路 | 4 种格式均通过 Word/Deck Stub E2E | 主流程在确定性输入下可运行 |
| 输出能力 | 可编辑 DOCX、PPTX 和结构化检查报告 | 具备本地演示和后续内网接入基础 |

这组数字是阶段快照，不等同于真实环境签收。本报告重构时的代码基线为提交 `ca13c48`。

## 8. 已知边界与未完成事项

以下事项必须保持诚实，不应在汇报中包装为已完成：

1. **NGA 尚未真实接入。** 还缺内网协议、鉴权、超时/重试、日志脱敏和 `codeagent.exe` 调用约束。
2. **真实业务文件尚未系统验收。** Synthetic 样例能覆盖结构边界，但不能替代脱敏真实 DOCX/XLSX/PPTX 的内容核对。
3. **Windows 离线真机尚未签收。** wheelhouse、安装脚本和 `verify.ps1` 需要在干净断网 Windows + Python 3.12 环境留存证据。
4. **目标字体与官方 CI 下的视觉终审尚未完成。** Mac 字体替代和 lint 不能证明 Windows PowerPoint/Word 的最终观感。
5. **图片二进制透传未实现。** 当前 image 能力以可编辑占位槽、引用和题注为主。
6. **架构图不是一键成品。** 当前生成可编辑骨架与基础避让，复杂图仍需人工调整。
7. **精确 Gantt 未实现。** 只有明确阶段节点时使用 timeline，涉及持续时间和依赖关系时不冒充 Gantt。
8. **Word 表格未完全对齐 PPT 决策矩阵。** 分组表头、复杂合并和强调能力留待后续契约演进。

## 9. 下一阶段计划

### 9.1 先用真实材料验证解析与内容贯通

收集脱敏的 DOCX、XLSX、PPTX 各至少 3 份，逐个核对 `DocumentIR.content` 与 `warnings`，重点检查复杂表格、修订/批注、隐藏数据、备注、组合形状和超大文件降级。

### 9.2 在内网接通 NGA，并量化弱模型表现

完成 NgaGenerator 的真实调用后，统计合法 IR 率、截断率、修复成功率和事实一致性。必要时只调整 Prompt、分段和 repair 策略，不绕过 Schema，也不让模型直接控制 renderer。

### 9.3 在 Windows 和真实字体环境完成交付签收

在干净断网 Windows 上验证 wheelhouse 安装、四条 CLI、`verify.py`、DOCX/PPTX 打开与编辑；使用目标字体和官方 CI 规范逐页检查中文显示、字号层级、重叠裁切、图表可读性和业务语义。

## 10. 汇报结论

本阶段已经建立了从多格式资料到可编辑 Office 产物的确定性技术底座：输入先统一为 DocumentIR，Generator 只负责产生结构化内容，WordIR/DeckIR 经过严格校验后再渲染，最终 Office 文件还要通过产物级 lint 和自动验收。

这套架构的价值不在于绑定某一个模型，而在于把模型的不确定性限制在可替换、可校验的边界内。当前 Mac + Stub 环境已经证明主链路可运行；下一阶段的重点不是继续堆版式，而是用真实文件、真实 NGA 和 Windows/真实字体环境完成生产条件下的验证。

---

# 附录：证据与追问索引

## A. 自动验收命令

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
python scripts/verify.py
```

## B. 核心代码位置

| PL 可能追问的问题 | 代码或文档位置 |
| --- | --- |
| IR 为什么是唯一契约？ | `AGENTS.md`、`docs/taskbook.md`、`backend/app/ir/` |
| 四格式如何解析？ | `backend/app/parsers/` |
| Prompt 如何约束弱模型？ | `backend/app/prompting/builder.py`、`backend/app/prompting/templates/` |
| Generator 如何替换？ | `backend/app/generators/interface.py`、`stub.py`、`codex.py`、`nga.py` |
| 非法 JSON/IR 如何处理？ | `backend/app/ir/shell.py`、`validation.py`、`repair.py` |
| Word/PPT 如何渲染？ | `backend/app/rendering/docx_renderer.py`、`pptx_renderer.py` |
| 主题规格在哪里？ | `backend/app/rendering/themes/hw_theme.json` |
| 合规检查在哪里？ | `backend/app/lint/docx_lint.py`、`pptx_lint.py` |
| 一键验收检查什么？ | `scripts/verify.py` |
| 哪些必须留到内网验？ | `HUMAN_REVIEW.md`、`QUESTIONS.md`、`REAL_PARSE_REPORT.md` |

## C. 事实口径说明

- 自动测试数字来自 2026-07-17 阶段快照：`384 passed`，整体覆盖率 `89.04%`。
- 当前 Git 提交口径为 `ca13c48 feat: strengthen evidence-grounded IR generation prompts`。
- 自动验收只证明 Mac 构造样例与确定性链路，不替代真实业务文件、真实 NGA、Windows 离线和目标字体/CI 下的人工终审。
