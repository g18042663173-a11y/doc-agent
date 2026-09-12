# 界面设计 Token 表（Web 工作台 + WPF 桌面端）

本文档是工作台外观的单一事实源。PPTX 产物仍使用
`backend/app/rendering/themes/*.json` 和 `docs/风格规范.md`；本表只约束 WPF 与浏览器界面。

## 设计方向

工作台采用 Windows 10/11 设置应用的层级：系统标题栏、低对比导航、浅灰画布、细分隔线和紧凑设置行。
生成、任务、设置和诊断都以可扫描的状态与操作为中心，不使用大面积深色侧栏、渐变、玻璃拟态或嵌套卡片。

交互强调色是 Windows 系统强调色语义，默认回退 Fluent Blue。华为红只允许出现在小型产品标识和导出的 PPT 主题中，不能主导按钮、焦点、选中项或进度。

## 外观行为

| 场景 | 默认 | 持久化 | 解析规则 |
| --- | --- | --- | --- |
| 新安装 | `system` | WPF `settings.json: appearance`；Web `localStorage: huawei-workbench-theme-v1` | 读取系统浅/深色偏好 |
| 既有设置 | 保留 `light` / `dark` | 不改用户已有覆盖 | 手动覆盖系统偏好 |
| 高对比度 | WPF 系统高对比度 | 不改用户选择 | 始终优先系统颜色 |
| Web 强制颜色 | 浏览器 `forced-colors` | 不改用户选择 | 交给浏览器系统颜色 |

WPF 监听 Windows 用户偏好和高对比度变化。Web 在 `system` 模式监听
`prefers-color-scheme`；旧 localStorage 中的 `light` 或 `dark` 是有效的手动覆盖，其他值归一为 `system`。

## 颜色

| Token | 浅色 | 深色 | 用途 |
| --- | --- | --- | --- |
| 页面背景 | `#F3F3F3` | `#202020` | 设置页画布、导航底 |
| 面板 | `#FFFFFF` | `#2B2B2B` | 单层工具面、弹层 |
| 弱表面 | `#F6F6F6` | `#333333` | 悬停、紧凑分组、进度轨 |
| 分隔线 | `#E0E0E0` | `#3D3D3D` | 行分隔、控件边框 |
| 主文字 | `#1A1A1A` | `#F5F5F5` | 标题、正文 |
| 次要文字 | `#616161` | `#C8C8C8` | 说明、状态 |
| 默认强调色 | `#0078D4` | `#4CC2FF` | 主操作、选中、焦点、进度 |
| 强调悬停 / 按下 | `#0067C0` / `#005A9E` | `#76D0FF` / `#2EA8E6` | 可交互反馈 |
| 成功 / 警告 / 危险 | `#107C10` / `#8A5A00` / `#C42B1C` | `#6CCB5F` / `#F2C94C` / `#FF99A4` | 仅表达状态 |
| 产品标识 | `#C7000B` | `#C7000B` | 小型产品方块，非交互色 |

Web CSS 对应 `--canvas`、`--surface`、`--surface-muted`、`--line`、`--ink`、`--muted`、`--accent`、`--accent-hover`、`--accent-pressed`。WPF 对应同名语义的 `*Brush` 资源。

## 形状、密度与无障碍

- 页面区域不浮动成卡片；只对单个工具、任务结果或重复列表项使用 `4px` 圆角和细边框。
- 按钮和输入控件最低高度为 `36px`，触控优先操作达到 `44px`。
- 设置行固定为“名称和说明 + 右侧控件”，任务行固定为“状态 + 产物 + 可恢复操作”。
- 焦点使用可见的 `2px` 系统强调色描边，不以颜色作为唯一状态信号。
- Web 必须响应 `prefers-reduced-motion` 和 `forced-colors`，WPF 高对比度使用 `SystemColors`。
- 只对产生状态变化的颜色做动画；不使用装饰性动效。

## 实现位置

- WPF：`desktop/DocumentWorkbench/Themes/Palette.*.xaml`、`AppearanceResolver.cs`、`MainWindow.xaml`
- Web：`backend/app/static/index.html`
- PPT 输出主题：`backend/app/rendering/themes/*.json`（不受本表交互色约束）
