# Composite v1.8 栏内堆叠设计

## 范围与兼容

DeckIR v1.8 只演进 `composite`。每个 `region` 从 v1.7 的单个 `component` 改为 `components[1..3]`，并仍固定为恰好一个 `left` 与一个 `right`。嵌入类型继续限制为 `table`、`architecture_diagram`、`title_bullets`、`cards`；`process_flow` 暂缓。

`migrate_deck_payload()` 将 v1.4-v1.7 在内存中深拷贝为 v1.8。遇到 v1.7 composite region 的 `component` 时，迁移为 `components: [component]`，不修改调用方字典或磁盘文件。故原有“一栏一个组件”输入是“一栏一个块”的兼容特例，原 renderer 视觉路径保持相同。

## 高度与堆叠

每栏先由主题的 `layouts.composite.content`、列跨度和内边距得到可用区域，再从上到下处理 `components`：

1. 每块先画自身区域小标题，标题高度和标题后间距均来自主题。
2. 表格主体高度是表头、分组表头、行分组和数据行的实际主题行高之和；不因堆叠而压缩行高。
3. 要点主体以主题正文候选最大字号测量每条换行高度，累加正文间距；不会为了塞入栏内先缩小到可读下限以下。
4. 卡片主体沿用现有 cards renderer 的按数量卡片高度和间距。
5. 架构图主体调用 Graphviz 的现有布局函数，在目标栏宽和一个大探测高度下读取节点、分组、连线标签的实际包围盒，再加主题安全边距；Graphviz 不可用时使用确定性 fallback 的最小高度估算。
6. 每块总高度为“区域小标题 + 标题后间距 + 主体首选高度”。块与块之间加入主题 `stack_gap_in`，按顺序累计，不平均分配，也不自动拆页。

若累计高度超过该栏可用高度，renderer 仍按每块首选高度连续绘制以保留全部内容，并放置一个透明的实际几何块边界。PPTX lint 读取该边界的真实 bottom 坐标与主题内容区 bottom 比较，输出既有 `HW-W03`：`组合页该栏内容过多...建议人工拆分`。这是对实际渲染几何的检查，不采信 renderer 自报坐标，也不为容器添加 lint 豁免。

## 渲染与 lint

`_render_composite()` 只负责栏宽、标题、堆叠坐标和透明块边界；每块仍调用现有 `_render_table_slide()`、`_render_architecture_diagram()`、`_render_title_bullets()`、`_render_cards()`。架构图继续走 Graphviz 和其既有 fallback，产物仍是可编辑的表格、形状、连接符和文本。

现有产物 lint 对组件形状继续运行：例如架构边数超过 12 仍由 `_architecture_items()` 产生 `HW-W03`，table 色彩、要点数和 KPI 规则也不因嵌入 composite 而被跳过。新增的 composite 规则只检查栏累计高度，不替代组件自身规则。

## 验收

- v1.7 单块 composite 自动迁移为 v1.8 一块列表，原输入对象不变。
- `components` 空列表或超过 3 块命中既有 `D004`。
- 左栏“表格 + 架构图 + 要点”、右栏单组件的 PPTX 几何不重叠且中文 PDF 可读。
- 堆叠内 13 条边架构图保留既有密度 `HW-W03`；超过栏高的三块组合保留全部块并触发“该栏内容过多” `HW-W03`。
- 全量 pytest、verify、Schema 快照通过，旧 13 个 layout 回归不跳过。
