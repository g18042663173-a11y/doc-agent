> 历史规格：2026-09-05 完整页仿版方案已取代本文的跳页、删页及运行时边界。当前权威补充见 `2026-09-05-complete-imitation.md`。

# 两个 Skill 分工设计

日期：2026-09-03  
状态：已口头确认方案，待用户审阅本文后再写实施计划  
仓库：`huawei_document_generator_windows_dev_20260728`  
相关版本：`huawei-doc-workflow` 1.0.3；`rhetoric-deck-workflow` 1.0.0

## 1. 问题

领导侧要的是「一个工作台 + 两个 Skill」，对应两条真实需求：

1. **模仿讲法**：照着别人 PPT 的论证结构，换成我们的材料。
2. **从 0 / 套模板生成**：没有范本时自绘；有公司模板时借母版与配色出 Word 或 PPT。

这两条需求的安全规则相反。模仿必须丢掉源件的句子和数字；生成必须把材料写进可编辑、可 lint 的华为文档。合成一个 Skill 会把泄漏门和渲染器缠在一起，也和现有 1.0.3 安装件冲突。

**已确认选择：** 维持两个独立 Skill，用 DeckIR 2.2 交接。模仿第一期做到「学论证结构 + 用用户材料换字」，不做像素级美工克隆。

## 2. 备选与取舍

| 做法 | 结论 |
| --- | --- |
| A. 两 Skill + DeckIR 交接 | **采用。** 安全规则分开，代码已存在，符合「两个 skill」。 |
| B. 合成一个 Skill、两个 mode | 否。包体、泄漏门、已安装的 1.0.3 都会被绑死。 |
| C. 模仿永远只出 IR、从不直接出 PPTX | 否。会丢掉「保对方版式、只换字」这条最容易被点名的路径。 |

工作台（`DocumentWorkbench.exe`）继续只做人机入口，走生成引擎。第一期不把模仿接进 WPF。

## 3. 架构

```text
用户材料 ──┐
          ├─► $rhetoric-deck-workflow
源 PPTX ──┘         │
                    ├─ source-shell → deck.pptx（保版式换字）
                    └─ deck-ir → deck_ir.json
                                      │
                                      ▼
                         $huawei-doc-workflow finalize
                                      │
                                      ▼
                         华为风格可编辑 PPTX + lint

用户材料 / md/docx/xlsx/pptx / 可选模板
          │
          ▼
$huawei-doc-workflow  （无模仿）
          │
          ├─ WordIR 1.3 → word.docx + lint
          └─ DeckIR 2.2 → deck.pptx + lint
```

三条不变量：

1. Host Agent 写中间 JSON；Skill 脚本不调用任何模型 API。
2. 模型文本不得直连渲染器。生成路径必须 `validate` 后再 `finalize`；模仿路径必须 `seal` 后再 `plan`/`finalize`。
3. 模仿 Skill 不得捆绑华为主题、Word 渲染、lint 引擎或模板资源。生成 Skill 不得抽取别人 PPT 的论证骨架，也不得保留对方原文。

## 4. 模仿 Skill：`$rhetoric-deck-workflow`

职责：把「怎么讲」从「讲了什么」里拆出来，再用用户材料填回去。

### 4.1 必须做出来的产物

命令链：`doctor` → `extract` →（Agent 写 `skeleton.json`）→ `seal` → `plan` →（Agent 写 `content.json`）→ `finalize`。无源件时走 `library` + `--pattern`，且只能 `deck-ir`。

| 产物 | 契约 | 允许含什么 | 禁止含什么 |
| --- | --- | --- | --- |
| `extract_pack/pages/*.json` | 临时逐页元素清单 | 源件结构，供写骨架 | seal 之后必须删除；不得进入交付物 |
| `skeleton.json` / DeckSkeleton 1.0 | 冻结 Schema | 页角色、槽位语义、容量、`shape_ref` | 源文句、数字、专名、主张 |
| `sealed/shell.pptx` | 消毒后的版式壳 | 形状几何、母版、结构标签 | 可见源文字、宏、ActiveX、非图表嵌入对象 |
| `sealed/source_ngrams.json` | 泄漏指纹 | SHA-256(8-gram / 数字 / 术语) | 明文 n-gram |
| `fit_report.json` | 材料能否填槽 | 每页分数与缺口 | 把低分当成可以编造的许可 |
| `content.json` / FillContent 1.0 | 填槽结果 | 只来自用户材料；缺槽 `status: missing` | 源件独有表述、臆造 KPI |
| `deck.pptx`（`source-shell`） | 换字成品 | 在已有形状里换字 + 字号拟合 | 增删挪形状、SmartArt 语义复刻、动画 |
| `deck_ir.json`（`deck-ir`） | DeckIR 2.2 | 验证通过的 IR | 直接渲染华为 PPTX |
| `leak_report.json` | 出口门 | 命中项与处置 | 泄漏未清仍放行成品 |

Agent 只在两处写文件：抽取后写骨架，规划后写内容。其余步骤是本地脚本。

### 4.2 页型与讲法库（冻结）

九种论证页型，不得在本轮改语义：

- `context_pain` — 背景 / 痛点 / 目标
- `capability_evidence` — 能力举证与对比
- `solution_selection` — 方案比选
- `method_walkthrough` — 方法步骤
- `implementation_detail` — 实现与约束
- `test_matrix` — 测试矩阵
- `issue_retro` — 问题复盘
- `phase_summary` — 阶段输入输出
- `status_progress` — 目标 / 进展 / 风险 / 下一步

五种内置整本讲法：`defense_technical`、`defense_capability`、`review_solution`、`report_progress`、`pitch_proposal`。

结构页（封面、目录、结束页）**不是**论证页。本轮策略：

- 映射不上九种页型的页面记入 skip 清单，seal 后保持空白消毒，不从源件回填。
- 允许用用户材料填封面标题/副标题、目录条目、结束页标题，但必须使用新的结构页型，不得把封面伪装成 `context_pain`。
- 结构页型本轮只加三个：`struct_cover`（`page.title`，可选 subtitle）、`struct_agenda`（`page.title` + items）、`struct_close`（`page.title`，可选 conclusion）。不扩展到 17 种生成版式。

2026-09-05 更正：模仿必须保留全部源页和页序。纯截图页保留原像素并列明图内文字；SmartArt 保留原生图形并同步节点与显示缓存。无法完成的对象须阻止正式验收，内部预览仍保留整页，不能删页消除问题。

### 4.3 两种输出怎么选

- 用户要「版式也要像那份」→ `source-shell`。脚本只替换已消毒形状中的文本并做字号拟合。
- 用户要「学它的讲法，外观改成华为风」→ `deck-ir`，然后**显式**调用 `$huawei-doc-workflow` 的 `validate`/`finalize`。模仿 Skill 自己不画华为主题。

`--allow-page-adjust` 只记录适配建议，不实施版式手术。

### 4.4 错误与停止条件

| 码 | 含义 | Agent 该做什么 |
| --- | --- | --- |
| doctor Error | 运行时不够 | 停，不读用户源件 |
| `RD-E010` / `RD-E011` | 骨架非法或 shell 未消毒干净 | 改骨架或换源件，禁止绕过 |
| `RD-E020` 低适配 | 材料撑不起这些槽 | 拒绝生成，要求补材料或换骨架 |
| `RD-E040` | 出口泄漏 | 扣住 PPTX/IR，只按用户材料改 `content.json` |
| `RD-E050` | 渲染/目录/契约失败 | 不覆盖已有产物；换空输出目录 |

低分不是提示词，用来催模型编数字。

### 4.5 本轮相对现状要补的

已有：1.0.0 源码、Schema、`dist/rhetoric-deck-workflow-1.0.0.zip`、泄漏门、两种输出。

缺口：

1. **未安装。** 仓库和 ZIP 在，本机 `.codex/skills` 没有。要能 `$rhetoric-deck-workflow` 显式调用。
2. **结构页。** 按 4.2 加入三个结构页型，并在 skip 报告里列出仍无法处理的页。
3. **交接说明。** 两个 Skill 的 `SKILL.md` 写明何时互调、`deck_ir.json` 如何交给生成 Skill，禁止暗示模仿 Skill 会输出华为成品。
4. **安装/打包说明。** 保留现有 `scripts/package_rhetoric_deck_skill.py` 检查；增加「解压到 skills 目录后跑 doctor」的最短步骤。

## 5. 生成 Skill：`$huawei-doc-workflow`

职责：从主题或材料写出合法 WordIR/DeckIR，再渲染可编辑 DOCX/PPTX 并 lint。

### 5.1 必须做出来的产物

命令链：`doctor` → `prepare` →（Agent 写 `draft_ir.json`）→ `validate`（首次 + 最多两次修补）→ `finalize`。可选 `sanitize-template`、`audit`。

| 产物 | 作用 |
| --- | --- |
| `generation_packet.json` | 给 Agent 的压缩任务包：事实、版式契约、容量、主题、资源约束 |
| `document_ir.json` | 输入 md/docx/xlsx/pptx 的解析结果 |
| `draft_ir.json` → `validated_ir.json` | Agent 写的 WordIR 1.3 或 DeckIR 2.2；只有校验通过件可渲染 |
| `word.docx` / `deck.pptx` | 可编辑成品；原生形状与图表，不是图片幻灯片 |
| `report.json` / `report.md` | lint 与运行时警告 |
| `workflow_manifest.json` | 这次运行的输入、IR、主题、模板、人工终审声明 |
| `template_profile.json` 等 | 仅当 `--template`：结构分析、换字/重绘审计 |
| `assets/asset_manifest.json` | 仅当有 `--asset`：消毒后的图片身份，不是语义理解 |

脚本不调用 Stub、NGA 或其它文档 Skill。图像只做解码、尺寸、哈希、摆放；不知道图里是什么。没有 brief/源文把文件名或 `asset_id` 映射到用途时，图片保持未使用。

### 5.2 两条生成路径（不要互相冒充）

**从 0（无 `--template`）。** 主题仅 `hw_v1`、`hw-report`、`hw-proposal`、`hw-academic`。Agent 按 17 种版式写 DeckIR：`cover`、`agenda`、`section`、`title_bullets`、`two_column`、`table`、`cards`、`chart`、`architecture_diagram`、`composite`、`process_flow`、`timeline`、`image`、`image_text`、`image_grid`、`infographic`、`conclusion`。这是生成 Skill 的主路径。

**套模板（有 `--template`）。** 先 Office 包预检；仅外链超链接可 `sanitize-template` 另存，其它外部关系/宏/OLE/ActiveX 硬失败。分析 OOXML 槽位后，能安全换字则换字，否则 `master_redraw`。1.0.2 实测：13 页商务模板约 1 页封面换字、12 页重绘。因此「套模板」= 借配色、母版、封面气质，**不是**模仿讲法。本轮不承诺把页级 `prototype_replace` 做成模仿替代品。

Word 路径保持独立：`--target word`，WordIR 1.3，与模仿 Skill 无交接。

### 5.3 错误与停止条件

- doctor 必检失败：停。缺 Graphviz 不阻断渲染，但架构图走确定性回退，必须当作视觉风险告诉用户，不得说「观感不受影响」。
- 模板预检失败：停。不得跳过宏、ActiveX、OLE、外部关系、路径、体积、形状数、损坏 XML。
- `validate` 三次仍失败：停。不得发明 Schema 字段让草稿过关。
- `finalize` 仍有 Error：扣住成品。
- lint 通过 ≠ 视觉或语义终审。交接必须保留 `human_required`。

### 5.4 本轮相对现状要补的

已有：1.0.3 引擎、工作台共用渲染、Word/PPT、模板消毒、lint。

缺口：

1. **路由说明。** `SKILL.md` 开头增加「模仿讲法请用 `$rhetoric-deck-workflow`」；本 Skill 在用户拿出范本 PPT 并要求学讲法时不得自行 extract。
2. **套模板诚实说明。** 写明 `master_redraw` 是预期行为，不是缺陷伪装成像素还原。
3. **接收模仿 IR。** 规定生成 Skill 可以把模仿 Skill 的 `deck_ir.json` 当作 `--draft`/`--ir` 输入，只要它通过同一份 DeckIR 2.2 Schema。两边冻结副本的 hash 必须继续由打包脚本核对；一边改 Schema 必须两边一起升版本。
4. **页级模板匹配增强。** 明确列为**下一轮**，不在本设计实施范围内。

## 6. 交接协议

唯一交接物：一份通过 DeckIR 2.2 校验的 JSON。

推荐命令顺序（华为风 + 学讲法）：

```text
python <rhetoric>/bin/rdw.py finalize --workdir <rw> --content <content.json> --out <rhetoric-out>
# 其中 render-mode=deck-ir，得到 deck_ir.json

python <huawei-doc>/scripts/workflow.py validate --target deck --draft <rhetoric-out>/deck_ir.json --output-dir <hw-run>
python <huawei-doc>/scripts/workflow.py finalize --target deck --ir <hw-run>/validated_ir.json --output-dir <hw-run>
```

约束：

- 模仿 `finalize` 在 `deck-ir` 模式停在 IR，不调用生成 Skill。
- 生成 `finalize` 不回头读源 PPTX、skeleton 或 extract_pack。
- 两个 Skill 的 `deck_ir.schema.json` 必须保持字节级一致（现有打包检查继续作为门禁）。
- 若用户只要保版式换字，到模仿 `source-shell` 的 `deck.pptx` 结束，不进入生成 Skill。

## 7. 工作台边界

`文档生成工作台` / `HuaweiDocumentGenerator` 使用与生成 Skill 同一套引擎，面向人类点选主题、材料、Stub/网关。

本轮：

- 不增加「模仿这份 PPT」按钮。
- 不在工作台内安装或调用 rhetoric 命令。
- 不把 Presenton 或其它 Docker PPT 产品并进本设计。

## 8. 本轮范围

做：

- 冻结并写清两个 Skill 的产物、禁区和交接（本文）。
- 安装 rhetoric 1.0.0，使显式 `$rhetoric-deck-workflow` 可用。
- 三个结构页型 + skip 报告。
- 两边 `SKILL.md` 路由与交接步骤。
- 用现有样例跑通：source-shell 换字、deck-ir → 生成 Skill 华为风、无模板从 0、带模板套版（允许大量 redraw）。

不做：

- 合并 Skill。
- 像素级 / SmartArt / 动画克隆。
- 版式手术（加形状、改几何）。
- 工作台模仿入口。
- 生成 Skill 抽取论证骨架。
- 模仿 Skill 渲染华为主题或 Word。
- 提高模板 `prototype_replace` 命中率。
- 调用任何新的模型 API。

## 9. 验收

1. 未显式写出 `$rhetoric-deck-workflow` 或 `$huawei-doc-workflow` 时，Agent 不偷偷跑对应脚本。
2. 对一份源 PPTX + 一份无关材料：seal 后 extract 明文消失；`finalize` 泄漏门能扣住含源句的 content。
3. `source-shell` 成品页数与壳一致，形状几何不变，可见文字来自用户材料或结构标签。
4. `deck-ir` 成品是合法 DeckIR 2.2；生成 Skill `validate`+`finalize` 能渲染出带 lint 报告的可编辑 PPTX。
5. 无模板从 0：生成 Skill 单独产出 Word 或 hw 主题 PPTX。
6. 有模板：产出 PPTX 且审计区分换字与 `master_redraw`，不把 redraw 宣传成「已模仿原页」。
7. 纯截图/SmartArt 页出现在 skip 清单，不出现在「已模仿」计数里。

## 10. 测试要点

- 继续跑 rhetoric 自带 samples（骨架、fill、泄漏、source-shell、deck-ir）。
- 增加一条跨 Skill 测试：将 sample `deck_ir.json` 送进 `huawei-doc-workflow` 的 `validate`，断言通过。
- 结构页型：封面页进入 `struct_cover` 后，source-shell 标题来自材料而不是源件 slogan。
- 生成 Skill：现有 doctor/prepare/validate/finalize 回归不因文档改动而失败。
