# Open-Kimi-PPT Skill 借鉴评估

评估日期: 2026-08-06
评估对象: <https://github.com/Binaryify/open-kimi-ppt-skill>（非官方逆向 Kimi Slides 的演示文稿 Skill）
结论: 架构方向获得第三方印证；五项启发点中两项已吸收，一项明确不采用，两项已收尾实现。

## 1. 项目定位（印证我们的核心决策）

open-kimi-ppt 走"AI 友好中间层 + 浏览器端 OOXML writer"路线：
`PPTD(YAML DSL) -> 校验 -> 可编辑 PPTX`，交付 PPTD 项目 + PPTX 双产物。
其功能特性（预设设计系统、视觉质检、元素动画、模板复用、安全边界）说明
Kimi 官方生产也采用"AI 友好 DSL + 校验 + 可编辑 PPTX"思路——**这与我们的
IR 唯一契约、确定性渲染、离线安全边界是同一架构方向，核心决策获得印证。**

与我们的关键差异（我们的优势，不得放弃）：

| 维度 | open-kimi-ppt | 本项目 |
| --- | --- | --- |
| 渲染 | 浏览器端 OOXML writer（依赖 Kimi 在线编辑器 + 网络） | python-pptx 确定性渲染（完全离线自包含） |
| 中间层 | PPTD 对用户可见可交付 | DeckIR 内部契约（刻意隐藏保确定性） |
| 依赖 | Node 18+ / 浏览器 / 网络到 kimi.com | 纯 Python + Graphviz（可选） |
| 质检 | 多模态模型看图审查 | 确定性 lint + 人工签字（manual_pending） |

open-kimi 自身承认"依赖的公开前端资源可能随 Kimi 更新而失效"——这正是
我们不引入浏览器/在线依赖的原因。

## 2. 五项启发点处理结论

| # | 启发点 | 结论 | 落地状态 |
| --- | --- | --- | --- |
| 1 | 命名设计系统预设（44 套点名即用） | **吸收** | 三套命名主题 hw-report / hw-proposal / hw-academic，四入口 + Prompt 注入，`test_theme_presets.py` 14 用例 |
| 2 | 多模态视觉质检循环 | **不采用（有原因）** | 内网 NGA 只有 GLM-5.1（纯文本，无视觉）；已有 contact_sheet + Office 导出 + HUMAN_REVIEW 人工签字替代；待 NGA 提供视觉模型后再评估 |
| 3 | 前置环境检查（缺依赖立刻停下明说） | **吸收** | 提交前检查 NGA CLI 存在性（见 3.3），缺失 E010 提前暴露 |
| 4 | 双产物交付（中间层可见可编辑） | **吸收（折中）** | deck_ir.json 作为受控下载资产（deck-ir），安全边界不变；不把 IR 变成用户必须接触的格式 |
| 5 | 生成前读全部上下文 + 需求澄清 | 已有等效 | 我们的 analyze 先分析、depth 三档、明确询问页数/深度 |

## 3. 已吸收项的落地记录

### 3.1 命名主题预设（2026-08-06 完成）

- `backend/app/rendering/themes/hw-report.json` / `hw-proposal.json` / `hw-academic.json`：
  从 hw_theme.json 派生，差异在色板/字号体系/版式密度/style_guide。
- `theme.py` 新增 `THEME_REGISTRY` + `resolve_theme()` 白名单。
- `GenerationOptions.theme` + `_apply_theme_override`（校验后统一覆盖 meta.theme）。
- 入口：CLI `--theme`、API 表单 `theme`、前端/WPF 下拉框。
- `build_prompt(theme=...)` 注入 `[主题风格 <name>]`（参考 design.md 唯一风格源机制）；
  hw_v1 不注入，原 Prompt 字节零变化。

### 3.2 IR 可见化（deck-ir 受控下载，2026-08-06 完成）

- `deck_ir.json` 加入 `ALLOWED_DOWNLOAD_ASSETS`（资产名 `deck-ir`），从敏感
  中间文件清理名单中排除，作为受控下载资产保留。
- 前端/WPF 下载区展示 `deck-ir` 链接；任务状态含 `assets.deck-ir`。
- 安全边界：仍不进 Git、按任务目录保留 24 小时后清理、不暴露 Prompt/正文。

### 3.3 前置环境检查（2026-08-06 完成）

- `_generate_request` 提交前检查：激活生成器为 NGA-CLI 时，`cli_path` 存在性
  （绝对路径用 `Path.is_file()`，命令名用 `shutil.which()`）；
  缺失返回 E010（stage=preflight），不再等任务跑到 generating 阶段才报。

## 4. 明确不采用项及原因

- **多模态视觉质检循环**：内网无视觉模型；强行做要么换模型（违反离线边界）、
  要么做残废版。已有确定性 lint（HW-W01~W16）+ Office 导出联系表 +
  HUMAN_REVIEW 人工签字，覆盖"发现明显问题"与"最终审美"两端。
  未来若 NGA 提供视觉模型（如 GLM-5V-Turbo），可重新评估为可选质检阶段。
- **浏览器导出/在线编辑器依赖**：违反内网断网离线硬要求；Kimi 前端资源变更
  会导致失效。python-pptx 自包含是我们不可放弃的优势。
- **自动联网搜图/生图**：`DisabledImageProvider` 为刻意保守设计，不放开。

## 5. 后续可选（暂不立项）

- 结构化 AI 二审：把 DeckIR 结构 + lint 报告喂给 GLM-5.1 做规则审查。
  边际收益有限（确定性 lint 已覆盖大部分），列为"以后想做再做"。

## 6. 二次评审（2026-08-07，聚焦"图的绘制"）

应要求对该仓库做第二轮专项调研，只看图形/图表知识
（`reference/pptd.md`、`reference/shapes.md`、`slides_categories/tech-engineering.md`、
`design_system/*/design.md`）。结论：**它没有图形引擎——图 = 原子元素手工组合 +
写在 markdown 里的"制图纪律"**；坐标全由模型手写。我们"Graphviz/模板坐标系 +
确定性 lint"的路线比它走得更远。可吸收并已落地的：

| 启发 | 处理 | 落地 |
| --- | --- | --- |
| 制图纪律：普通边中性细线、关键路径强调色加粗；节点不大面积高饱和；组框弱化 | **吸收** | 架构图渲染改造：普通节点白底+类型色细边框、emphasis 实心红；连接 emphasis 节点的边红色加粗（关键路径），其余中性灰；组框 2pt 虚线→1pt 实线浅灰底。Graphviz 与回退两条渲染路径同步（`pptx_renderer.py`），lint 节点色规则改验边框色 |
| 关系→图形映射表（8 类：边界/调用流/时序/拓扑/状态机/对比矩阵/因果链/覆盖矩阵） | **部分吸收** | 现有 `visual/planner.py` 关键词规则已覆盖 6 类布局；时序图/状态机未立项（IR 无此布局，需升 Schema，不做） |
| 图表"去默认化"（去纵网格线、标签只标关键点、实虚线区分实际/预测） | 记入待办 | python-pptx 原生图表默认样式调整，列入后续可选 |
| Chart 数据模型校验码（DuplicateColumn/CyclicGraph 等） | 记入待办 | 现有 chart lint 已覆盖主路径，细粒度校验码以后可补 |
| Line 的 viewBox+points+curve+arrow 模型、177 预置形状表 | 不采用 | 我们走 Graphviz 布局 + 固定组件，不需要手写贝塞尔坐标 |
| 多模态 QA 清单 | 维持不采用 | 理由同 §4；对应条目已有确定性 lint 等效 |

- 架构图改造同步更新了 lint 规则（`HW-W02` 节点校验由填充色改为边框色）
  与渲染测试断言；三主题全量复检 0 误 0 警，全量后端 643+ 通过。
- 证据：`output/diagram-review/`（Graphviz 路径与回退路径渲染 PNG 对比）。
