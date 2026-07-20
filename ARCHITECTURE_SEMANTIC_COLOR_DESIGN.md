# Architecture Diagram 语义配色设计

## 现状

`ArchitectureNode.type` 当前是 `primary / secondary / emphasis / data` 四值枚举。现有 renderer 在 `_render_architecture_node()` 内维护硬编码映射：`primary -> accent6 (#30B5C5)`、`secondary -> accent4 (#FCC800)`、`emphasis -> hw_red (#C7000B)`、`data -> accent5 (#61B230)`。因此已有配色与华为 CI accent 色一致，但 type 名称不足以直接表达“job / module”这类业务语义，且颜色映射不在主题中。

## 决策

DeckIR 升至 v1.9，并将节点 `type` 从封闭 Literal 改为非空字符串：主题已注册的值获得确定配色，未注册值使用主题 `default` 配色。这满足两个边界：

1. 内容作者可明确给出 `job`、`module` 等业务语义，renderer 只按 type 查 theme，不推断文本或业务领域。
2. 未指定时仍保留既有默认 `secondary`；未知字符串不阻塞合法渲染，稳定回退到主题 default 色。

主题 `layouts.architecture_diagram.node_type_colors` 是唯一映射源：既有 primary/secondary/emphasis/data 保持原色，新增 `job -> accent4`（黄）和 `module -> accent5`（绿）。`default -> secondary` 使未知值行为可配置。节点形状、Graphviz 布局、连接符、标签与字体均不改。

## 兼容与验收

- v1.4-v1.8 DeckIR 在内存深拷贝迁移为 v1.9；v1.7 composite 仍同时完成单 `component` 到 `components: [component]` 的迁移。
- renderer 和 lint 都从同一 theme 映射读允许色；现有四种 type 的色值保持不变。
- 回归覆盖 job/module/data/default 四种 type 的实际 PPTX 填充色、未知 type 的 default 回退、嵌入 composite 的架构图、以及现有 HW-W03 边数密度检查。
