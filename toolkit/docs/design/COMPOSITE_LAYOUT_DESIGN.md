# Composite 组合页版式设计与实现记录

> 状态：这是 DeckIR v1.7 单组件首版的历史设计记录。当前实现已演进为 DeckIR v1.8，每栏支持 1-3 个 `components` 纵向堆叠；详见 `COMPOSITE_STACKING_DESIGN.md`。嵌入类型仍限 `table / architecture_diagram / title_bullets / cards`，`process_flow` 暂缓但未取消。

> 合规边界：左右位置、组件白名单和组件内部结构由 DeckIR 模型校验；没有新增 composite 专用 lint 或豁免。嵌入组件渲染为原生 PPTX 对象，继续由既有产物 lint 识别，因此 table 色彩、架构图边密度、要点数量和 KPI 卡片语义等规则在 composite 内照常触发。

## 1. 设计基线与改动边界

- 实现前 DeckIR 为 `1.6`，`DeckSlide` 是按 `layout` 判别的 13 种 slide union；本轮将新类型加入该 union，并将版本升到 `1.7`。证据：`backend/app/ir/deck_ir.py:686-754`。
- 当前渲染器按 slide model 类型分派，13 种版式各自画整页；新增 `CompositeSlide` 需要增加一个分派分支。证据：`backend/app/rendering/pptx_renderer.py:48-85`。
- `title_bullets`、`table`、`cards`、`architecture_diagram` 当前都在函数内部绘制整页标题并读取全页绝对坐标，不能直接原样调用到半页区域。证据：`backend/app/rendering/pptx_renderer.py:203-231,234-295,548-571,991-1017`。
- Graphviz 架构图已经把可用内容区作为 `layout["content"]` 输入，坐标换算也以该内容区为基准，因此只要传入右栏内容区即可复用现有 Graphviz 计算与原生形状绘制。证据：`backend/app/rendering/architecture_graphviz.py:56-60,144-180,197-220`。
- Schema 导出有版本与历史哈希门禁；`1.7` 必须导出新快照并登记历史哈希，不能直接覆盖 `1.6`。证据：`backend/app/ir/schema_export.py:84-106,112-146`。

本轮只新增第 14 种 `composite`，不改现有 13 种 layout 的公开字段、默认值或整页渲染结果。解析器、DOCX、chart、process_flow、timeline、image 等不在范围内。

## 2. DeckIR v1.7 结构

### 2.1 JSON 形态

```json
{
  "layout": "composite",
  "title": "方案已形成可比较、可追溯的双区块结论",
  "regions": [
    {
      "slot": "left",
      "component": {
        "layout": "table",
        "title": "方案对比",
        "table": {
          "header": ["方案", "结论"],
          "rows": [["方案 A", "推荐"], ["方案 B", "备选"]]
        }
      }
    },
    {
      "slot": "right",
      "component": {
        "layout": "architecture_diagram",
        "title": "数据流骨架",
        "nodes": [
          {"id": "input", "text": "输入", "type": "primary"},
          {"id": "gate", "text": "质量闸门", "type": "emphasis"},
          {"id": "output", "text": "输出", "type": "data"}
        ],
        "edges": [
          {"from": "input", "to": "gate", "direction": "forward"},
          {"from": "gate", "to": "output", "direction": "forward"}
        ],
        "groups": []
      }
    }
  ]
}
```

顶层 `title` 是整页结论式标题。嵌入组件继续使用它原有的 `title` 字段，但在组合页内渲染为区域小标题，不重复画整页标题红线。

### 2.2 Pydantic 模型

建议新增三个类型，不复制任何既有组件字段：

```python
CompositeComponent = Annotated[
    Union[TableSlide, ArchitectureDiagramSlide, TitleBulletsSlide, CardsSlide],
    Field(discriminator="layout"),
]

class CompositeRegion(ContractModel):
    slot: Literal["left", "right"]
    component: CompositeComponent

class CompositeSlide(ContractModel):
    layout: Literal["composite"]
    title: str
    regions: list[CompositeRegion] = Field(min_length=2, max_length=2)
```

这样 `table` 仍使用 `DeckTable`，架构图仍使用 `ArchitectureNode/Edge/Group`，要点和卡片也直接复用现有 slide model。组合页不会再生一套 `table_component`、`diagram_component` 等平行契约。

### 2.3 合法性规则

`CompositeSlide` 的模型校验负责：

1. `regions` 必须恰好两个。
2. `slot` 必须恰好包含一次 `left` 和一次 `right`；缺失、重复或其它位置均返回 D004。
3. `component.layout` 仅允许 `table`、`architecture_diagram`、`title_bullets`、`cards`。
4. 每个 component 继续执行原模型的全部校验，例如 table 列数/span、架构图 node/edge 引用、cards 数量和 bullets 数量。
5. 区域不会接收任意坐标；左右栏由主题确定，因此“区域不重叠”由结构保证，而不是相信模型给出的坐标。

第一版不支持嵌套 composite，也不支持 chart、image、timeline、process_flow。用户原需求中提到“流程图”，本设计将复杂关系图对应为 `architecture_diagram`；线性流程 `process_flow` 暂不放入第一版白名单，避免一次同时改五个组件的区域适配。确认后如必须把 `process_flow` 纳入第一版，可将其加入白名单，但工作量与视觉回归范围会随之增加。

## 3. v1.6 到 v1.7 的迁移

- `DeckIR.ir_version` 从 `Literal["1.6"]` 升为 `Literal["1.7"]`。
- `migrate_deck_payload()` 接受 `1.4`、`1.5`、`1.6`，只在内存浅拷贝顶层字典并改为 `1.7`；不修改输入对象或磁盘文件。
- 旧版不需要补字段，因为旧数据不含 composite；迁移后仍执行完整 `1.7` 校验。
- `1.3` 及更早版本继续拒绝。
- `validate_deck_ir()` 对迁移成功继续返回 D004 Warning，message 明确源版本和目标版本；`DeckIR.model_validate()` 与 `validate_deck_ir()` 两个入口行为一致。
- 更新 `backend/schemas/deck_ir.schema.json` 与 `backend/schemas/schema_history.json`，保留 `1.6` 历史哈希并新增 `1.7` 哈希。

## 4. 渲染设计：区域上下文复用现有组件

### 4.1 主题 token

在 `hw_theme.json` 新增 `layouts.composite`，所有布局数值只从此处读取：

- `content`：整页标题下方、页脚上方的组合页内容区。
- `column_gap_in`：左右栏间距。
- `region_padding_in`：每栏内边距。
- `region_title_height_in`、`region_title_gap_in`、`region_title_font_size_pt`：区域小标题。
- `region_border_pt`：默认 0；第一版保持平面排版，不强制画卡片边框。
- `compact_table_min_row_height_in`、`compact_body_min_font_size_pt`：半页区域可读性下限。

左右栏使用主题声明的 5 栏 / 1 栏间距 / 6 栏结构；右栏略宽以容纳关系图，所有边界直接落在现有 12 栏网格上，避免新增 lint 例外。现有主题 token 不改值。

### 4.2 内部区域对象

renderer 内新增私有、非契约的数据类，例如：

```python
@dataclass(frozen=True)
class RenderRegion:
    left_in: float
    top_in: float
    width_in: float
    height_in: float
```

`_render_composite()` 只做三件事：画一次顶层标题、按主题切出 left/right、把 region 交给现有组件绘制函数。

### 4.3 保证现有 13 版式行为不变

不复制组件绘制算法，而是给以下私有函数增加仅内部使用的可选参数：`region=None`、`include_page_title=True`。默认值保持现有整页路径，旧调用不变；composite 调用传入子区域并关闭整页标题。

- `_render_table_slide()`：复用表格创建、表头、斑马纹、强调色、分组和 span 逻辑；仅把表格可用宽高和起点替换为 region 内容区。
- `_render_architecture_diagram()`：复用 Graphviz 与 fallback；仅将派生 layout 的 `content` 替换为 region 内容区。节点、边、组仍为独立 PPT 原生对象。
- `_render_title_bullets()`：复用现有文本栈自适应函数；可用宽高改为 region 内容区。
- `_render_cards()`：复用 `_card_box()`、普通/KPI 卡片内容；将全页 12 栏网格换算为 region 内部网格，但不改卡片视觉 token。

区域小标题由组合页统一画一次，使用 component 原有 `title`。嵌入组件不再调用 `_title()`，因此不会出现每栏各自画一条整页红线。

### 4.4 半页密度边界

契约仍接收所有原本合法的组件内容，不私自缩窄既有模型上限。渲染时：

- 优先在 region 内自适应宽高和字号。
- 不截断内容，不自动拆页。
- 到主题定义的可读下限仍放不下时，沿用现有 `HW-W03` 原因文本机制，提示“组合页区域内容过多，建议拆成独立页面”。
- Graphviz 架构图继续使用现有最小字号和密度警告；右栏只改变 `content`，不改变节点/边算法。

如果实现阶段发现现有 HW-W03 只能识别整页而无法区分 region，该点会先停下来报告，不通过新增 lint 码或修改 lint 核心绕过。

## 5. 校验与 lint 边界

用户约束同时要求“parse/check/lint 一律不碰”和“校验器/lint 对 composite 做基本检查”。本设计采用以下兼容解释，待确认：

- 组件类型、region 数量、left/right 唯一性全部由 DeckIR/Pydantic 校验，非法输入返回现有 D004。
- region 坐标不开放给模型，几何区域由主题确定，因此 schema 层即可保证两个区域不重叠。
- 产物仍运行现有 `check_pptx()`；它基于真实 PPTX 几何检查页边、重叠、字体和颜色，不修改 lint 规则或错误码。
- 本轮不改 `backend/app/lint/pptx_lint.py`。若确认必须增加 composite 专用 lint 逻辑，需要明确放宽“不动 check/lint”约束后再实施。

## 6. Prompt、stub 与文档策略

- Prompt 的完整 Schema 会自动包含 composite；另补一条选择规则：只有两个需要同时比较/联读且都能在半页内表达的组件才选 composite，禁止用它把两页内容硬塞一页。
- stub 默认生成行为保持不变，不为展示新版式强行追加 composite；验收使用固定合法样例，保证离线确定性。
- `docs/taskbook.md` 的 DeckIR 表补 composite 行，并把“13 版式”更新为“14 版式”；README/使用说明补最小 JSON 示例。该文档变更只描述新能力，不改原有 13 版式定义。

## 7. 实现文件范围

预计只涉及：

- `backend/app/ir/deck_ir.py`：新增 composite model、union、1.7 迁移。
- `backend/app/ir/validation.py`：登记新 slide model、更新迁移 message。
- `backend/app/rendering/pptx_renderer.py`：新增 composite 分派和区域上下文；既有四个组件只做带默认值的区域化重构。
- `backend/app/rendering/themes/hw_theme.json`：新增 `layouts.composite` token。
- `backend/app/prompting/builder.py`、`backend/app/generation/depth.py`、`backend/app/generators/stub.py`：仅更新版本常量/提示；stub 选版行为不变。
- `backend/schemas/deck_ir.schema.json`、`backend/schemas/schema_history.json`：1.7 契约快照。
- `samples/ir/`、`samples/expected/`：合法 composite、非法 slot/非法 component 正反样例与 expected。
- `backend/tests/`：契约、迁移、renderer 回读、Graphviz 区域、CLI/样例矩阵回归。
- `docs/taskbook.md`、README/使用说明：第 14 种版式说明。

明确不动：四个 parser、WordIR/DocumentIR、DOCX renderer、现有 lint 规则、现有 13 种公开字段。

## 8. 验收结果

### 8.1 契约与迁移

- 合法 left-table/right-architecture composite 通过。
- 缺 region、重复 left、非法 slot、嵌入未允许 layout、内部 table/edge 非法分别命中 D004/D005 等既有码。
- 1.4、1.5、1.6 均迁移到 1.7；1.3 拒绝；输入对象未修改。
- Schema 快照与历史哈希一致。

### 8.2 渲染回读

- 顶层标题只出现一次，两个区域小标题各出现一次。
- 左表格仍是原生 PowerPoint table，表头/斑马纹/强调/span 行为与独立 table 相同。
- 右架构图由 Graphviz 布局，节点、组框、边和标签均是独立可编辑原生形状。
- 逐形状读取真实 `left/top/width/height`，断言全部位于对应 region 内；left/right region 不相交。
- 现有 13 版式测试和产物回读断言不修改、不跳过，全部继续通过。

### 8.3 视觉与门禁

- 生成 `output/composite_layout_review/deck_composite_table_architecture.pptx`。
- 中文可读 PDF 为 `output/deck_composite_table_architecture_wps_preview.pdf`，逐页 JPEG 为 `output/composite_layout_review/deck_composite_table_architecture_wps_preview-1.jpg`。
- 全尺寸检查：表格与架构并排、无重叠/裁切、节点文字不溢出、边标签不压节点、标题层级清楚。
- 运行全量 pytest 和 `python scripts/verify.py`，要求零失败、Schema 快照一致、覆盖率不低于当前基线。
- 最终 `git diff --stat` 与逐文件 diff 复核：现有 13 个公开 schema 字段无变化，parse/check/lint 核心无变化。

## 9. 已确认决策与实现结论

1. 第一版组件白名单按 `table / architecture_diagram / title_bullets / cards` 执行；线性 `process_flow` 暂不纳入。后续在 composite 架构验证稳定后扩充白名单。
2. composite 基础校验全部放在 DeckIR 模型，产物复用现有通用 lint；本轮没有增加 composite 专用 lint 代码，也没有给容器或嵌入组件增加 lint 豁免。
3. 回归测试使用右栏 13 条边的架构图，确认既有 `HW-W03`“架构图过密”警告仍然触发；另以 table、title_bullets 和 cards 反例确认各组件原有规则在 composite 内继续生效。
4. 左表右架构图样例已输出为可编辑 PPTX；中文可读预览使用 WPS 转换，LibreOffice 在当前 Mac 字体环境下存在中文方框，不作为视觉验收件。
