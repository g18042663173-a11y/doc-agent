# 任务接力书（Claude Code / 终端会话）

> 给下一会话的接手人（AI 或工程师）：本文件是当前会话的全部遗留任务与上下文。
> 目标：在 **Windows 10/11 x64** 上完成验证、打包、安装程序编译与人工验收。
> 项目根：`C:\Users\GSQ\Desktop\huawei_document_generator_windows_dev_20260728`

## 一、当前状态（上一会话已完成）

### 1.1 已实现的功能（代码全部就位、测试全绿）

| 功能 | 核心文件 | 状态 |
|---|---|---|
| auto/strict 生成模式（NGA 失败自动回退 Stub 并标注） | `backend/app/generators/manager.py`、`backend/app/web_api.py` | 完成，12 测试 |
| NGA 双传输（CLI `nga run` + HTTP OpenAI 兼容） | `backend/app/generators/nga.py` | 完成，23+ 测试 |
| NGA CLI 免 Token（认证归 NGA CLI） | 同上 | 完成 |
| 命名主题 ×3（hw-report / hw-proposal / hw-academic） | `backend/app/rendering/themes/*.json` | 完成，14 测试 |
| 主题入口（CLI/API/前端/WPF + Prompt 注入 style_guide） | `generation/depth.py`、`prompting/builder.py` 等 | 完成 |
| deck-ir 受控下载（结构化内容可改后重渲染） | `backend/app/web_api.py` | 完成，3 测试 |
| 前置 CLI 存在性检查（提交前 E010） | `backend/app/web_api.py` | 完成，2 测试 |
| 引擎指示条 + 设置面板 + 三套主题下拉 | `backend/app/static/index.html` | 完成 |
| WPF 主题/调用方式/模式设置 | `desktop/DocumentWorkbench/` | 完成（未在 Windows 编译） |
| Inno Setup 安装程序（用户目录免提权） | `installer.iss`、`scripts/package_installer.py` | 设计+脚本完成，**未在 Windows 编译** |
| Windows 一键脚本入口 | `scripts/win/*.ps1` | 完成，**未在 Windows 执行** |

### 1.2 验证基线（沙箱已跑通，Python 3.10）

- 全量 pytest：**649 passed, 1 skipped, 0 failed**（7 个环境限制 deselected，与代码无关）
- verify.py 门禁：C0 核心全过（Schema 快照、四格式 E2E 8 条链路、lint pass、覆盖率 89%）
- ruff：全绿

### 1.3 关键设计/分析留档（接手前先读）

- `docs/design/AUTO_GENERATOR_FALLBACK_DESIGN.md`（auto 降级设计 + 决策）
- `docs/design/INSTALLER_DESIGN.md`（Inno Setup 安装程序设计）
- `docs/design/REVIEW_OPEN_KIMI_PPT.md`（open-kimi 借鉴评估，含"视觉质检为何不做"）
- `docs/WINDOWS_ACCEPTANCE_20260806.md`（Windows 分步验收清单，六步）
- `scripts/win/README.md`（一键脚本入口）
- `docs/design/INSTALLER_DESIGN.md`、`installer.iss`、`scripts/package_installer.py`（安装程序）

## 二、待办任务（按顺序执行）

### 任务 0：首次准备（一次性）

```powershell
cd C:\Users\GSQ\Desktop\huawei_document_generator_windows_dev_20260728
.\.venv\Scripts\python.exe --version   # 必须是 3.12.x；不是则先 .\bootstrap_windows.ps1
```

### 任务 1：代码级验证（必过）

```powershell
.\scripts\win\verify_all.ps1
```

通过标准：verify 门禁 `C0 verify passed`、可靠性报告 0 failed、专项测试全绿、ruff 全绿。
若失败：把报错原文记录到本文件"执行日志"，逐条定位。

可选（含浏览器 UI）：`.\scripts\win\verify_all.ps1 -Ui`（需先 `python -m pip install -r requirements-dev-ui.txt`）。

### 任务 2：WPF 编译 + 便携 ZIP

```powershell
.\scripts\win\build_all.ps1
```

预期：WPF 测试 3/3、Release 构建 0 warning/0 error、
`dist\document-workbench-windows-x64-2.1.0.zip` + `.sha256`。

注意：需 .NET SDK 8.0.423（`$env:LOCALAPPDATA\Codex\dotnet-sdk-8.0.423\dotnet.exe`）。
Graphviz 缺省用 `C:\Program Files\Graphviz`；不在标准路径用
`.\scripts\win\build_all.ps1 -GraphvizRoot "<path>"`。

### 任务 3：安装程序编译（需 Inno Setup 6）

```powershell
# 一次性安装 Inno Setup 6（https://jrsoftware.org/isdl.php）
.\scripts\win\package_setup.ps1 -Overwrite
```

预期：`dist\HuaweiDocumentGenerator-Setup-2.1.0.exe` + `.exe.sha256`。

### 任务 4：工作台功能验收（浏览器 5056）

```powershell
.\scripts\win\start_workbench_ui.ps1
# 打开 http://127.0.0.1:5056/static/index.html
```

逐项（详见 `docs/WINDOWS_ACCEPTANCE_20260806.md` 第二步）：

1. "开始生成"上方引擎指示条显示"确定性 Stub（未接入 AI）"
2. "AI 生成设置"展开后有状态卡、调用方式（CLI 默认）、字段提示
3. 选 Word 时主题下拉禁用
4. 上传 md → 生成，审计区含"结构化内容（DeckIR）"链接且可下载
5. 主题选 hw-academic / hw-proposal 生成，产物风格差异可见

### 任务 5：NGA 接入（真实内网，需人工）

```powershell
nga providers login   # 一次性
nga run "hi" -m w3/GLM-5.1-WX-Auto --format json   # 确认能对话
```

工作台设置 → 调用方式选"本机 NGA 命令行" → CLI 路径 `nga` → 模型
`w3/GLM-5.1-WX-Auto` → 测试连接 → 启用。用真实脱敏业务文档生成 Word + PPT。

auto 降级实测：临时把 CLI 路径改成不存在的值 → 提交任务 → 应**立即**返回
E010（stage=preflight），而不是排队后失败。

### 任务 6：三套主题人工视觉签字

目标 PowerPoint + 目标字体环境下，用同一份业务文档生成 hw-report / hw-proposal /
hw-academic 三份 PPTX，逐项检查：字体替代、红色锚点、无溢出/重叠、密级页码、
风格差异。结论记到 `output\theme-visual-signoff.txt`（评审人/日期/结论）。

### 任务 7：WPF 桌面端 + 安装程序验收

- 双击便携包解压后的 `DocumentWorkbench.exe`：设置 > 常规 有"默认 PPT 主题"；
  NGA 设置有"调用方式"；引擎状态正确
- 双击 `HuaweiDocumentGenerator-Setup-2.1.0.exe`：中文向导 → 用户目录
  → 桌面/开始菜单图标 → 点图标正常启动；"添加或删除程序"可卸载；
  `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json` 保留

### 任务 8：既有 QUESTIONS.md 人工待办（长期）

- 真实脱敏 docx/xlsx/pptx 各 ≥3（放 `samples\input\real\`）
- 授权真实图片语料（来源/版权/署名/替代文本）
- 全新 Windows 物理断网安装验收
- 真实 NGA 协议兼容记录
- 内网代码签名

## 三、硬约束（不得违反）

- 不放宽 IR Schema；需求变更先升 `ir_version` + 更新正反样例
- 不"尽力渲染"非法 IR；错误走 E/W/D 系并定位
- 不引入 Node/浏览器/在线依赖到生产；`experiments/html2pptx` 保持隔离
- 不放开 `DisabledImageProvider`；不联网搜图/生图
- NGA CLI 模式下项目代码不碰认证（归 `nga providers login` 管理）
- 新行为必须有回归测试；`backend/tests/` 覆盖率 parsers/ir/lint ≥80%、整体 ≥70%

## 四、执行日志（接手人填写）

> 每完成一个任务，在这里记录：日期 / 任务号 / 结果（通过/失败）/ 关键输出或报错原文。

| 日期 | 任务 | 结果 | 关键输出/报错 |
| --- | --- | --- | --- |
| 2026-08-06 | 任务 0 首次准备 | 通过 | `.venv` = Python 3.12.10，无需 bootstrap |
| 2026-08-06 | 前置修复（接力书未记录的坑） | 通过 | 全部 `.ps1` 原为 UTF-8 无 BOM，Windows PowerShell 5.1 按 GBK 解析直接 ParserError；已对 `scripts/win/*.ps1` 与根目录 4 个 `.ps1` 补 UTF-8 BOM |
| 2026-08-06 | 任务 1 代码级验证 | 通过 | `C0 verify passed`；覆盖率 app=93.5%/parsers、ir=93.9%、lint=94.3%、overall=89.3%；专项 49 passed；ruff 全绿；QA 报告 `output/qa/report.json` |
| 2026-08-06 | 附加：前端审美改版 | 通过 | `backend/app/static/index.html` 全量重设计（华为主题 token、胶囊分段控件、主题色板联动、focus-visible、移动端适配）；`test_web_api_static` 通过；截图留档 `output/ui-redesign/` |
| 2026-08-06 | 任务 3 前置检查 | 已解决 | Inno Setup 6.7.3 已静默安装（GitHub 官方包、Pyrsys B.V. 签名验签 Valid）；补装简体中文语言包 `ChineseSimplified.isl`（jrsoftware 官方翻译库）到 `Inno Setup 6\Languages\`；5056 端口残留进程（PID 9388/11232）已清理 |
| 2026-08-06 | 任务 3 安装程序编译 | 通过 | `dist\HuaweiDocumentGenerator-Setup-2.1.0.exe`（91.8 MB）+ sha256 `6671199c…b197f`，源为最新便携 ZIP |
| 2026-08-06 | 任务 2 WPF 编译 + 便携 ZIP | 通过 | xUnit 4/4 通过；Release 构建成功；`dist\document-workbench-windows-x64-2.1.0.zip`（105.7 MB，2199 文件）+ sha256 `f5ba495e…eeb107`；ZIP 已包含前端审美改版 |
| 2026-08-06 | 附加：双端设计 token 统一 | 通过 | 新建 `docs/design/FRONTEND_TOKENS.md`（界面色板单一事实源）；修正 WPF 主红 `#C7002B→#C7000B` 等 7 项色值 + 图标脚本同色修正并重建 `app-icon.ico`；UI 回归 `test_workbench_ui.py` pass（desktop/mobile）、WPF xUnit 4/4、Release 0 警告；截图留档 `output/frontend-unification/`（含 WPF 实机截屏） |
| 2026-08-06 | 附加：专业办公效率风格增强 | 通过 | Web 圆角收紧 6/4px、h1 改半粗、指标数字 tabular-nums；WPF 清除 3 个离调色板色值（`#F23D61`/`#8FB4FF`/`#FDECEF`）、新增按压态（`AccentPressedBrush #8C0008`）与深底强调色（`AccentOnDarkBrush #F85948`）；token 表同步；双端回归+实机截图复核全绿（`output/frontend-unification/*-v2.png`） |
| 2026-08-06 | 稳定性收尾：bug 修复 + 全量自测 + 重打包 | 通过 | **修复 2 个真 bug**：①设置面板 CLI 模式保存/测试被误要求 base_url（任务 5 会被卡死），改为按传输方式校验；②Stub 激活时 HTTP 字段显隐失效。`test_workbench_ui.py` 新增对应回归覆盖。全量自测：verify_all 四步全绿（C0、可靠性 657 passed/0 failed、专项 49、ruff）；UI 回归双视口 pass；WPF xUnit 4/4 + Release 0/0。**重打包**：`dist\document-workbench-windows-x64-2.1.0.zip` 新 sha256 `64a4c353…30cfb`，已抽查 ZIP 内含修复后的 index.html。**注意**：5056 端口有两个 8/6 23:09 残留的 web_api 进程（PID 9388/11232），跑任务 4 前需先结束或换端口 |
| 2026-08-07 | 附加：Web UI 视觉验收（AI 代行，用户委托） | 通过 | 12 张全状态实机截图审阅（`output/visual-review/`，工具 `scripts/visual_review_shots.py`）；**修复 2 项真实缺陷**：①文件已选行被 `place-items` 穿透导致居中（Chromium block 布局 justify-items 新特性），改为左对齐+删除按钮居右；②移动端设置面板双列截字，≤620px 收单列。回归：`test_web_api_static` 通过、`test_workbench_ui` 双视口 pass、ruff 全绿。签字结论 `output/ui-visual-signoff.txt`。**已重打包**：ZIP 新 sha256 `643a3a80…de7be`（已抽查含修复）、安装程序新 sha256 `22a83705…74fa2`（91.8 MB） |
| 2026-08-07 | 任务 6 三套主题视觉签字（AI 代行，PowerPoint 16.0 实机渲染） | 通过 | 同一源文档 Stub 生成三主题各 11 页，COM 导出 33 张 PNG 逐页审阅（`output/theme-visual-signoff/`）。**修复 3 项缺陷**：①hw-academic 学术蓝锚点不生效（渲染器锚点统一取 hw_red，主题只覆盖 accent1）→ 主题数据 hw_red 改 #1F4E79；②`check_pptx` 的 theme_name 未透传（web_api×2、cli/render、demo_e2e 共 4 处，非默认主题误报 HW-W02）→ 全部透传 + `cli/check.py --theme` + 回归用例；③hw-proposal 行距 10.08pt 破坏 8pt 基线（HW-W06×5）→ 0.111111in；卡片 tag 灰底灰字 4.23:1（HW-W09）→ 色 token 改 body。修复后三主题 lint 全 0 误 0 警，全量 643 passed。签字 `output/theme-visual-signoff.txt` |
| 2026-08-07 | 任务 7 WPF + 安装程序验收（AI 代行，真实安装/运行/卸载） | 通过 | 便携包与已安装实例各跑一遍 FlaUI 走查（新增 `PortableAcceptanceTests.cs`，默认跳过不影响常规测试）：标题/引擎状态/设置常规主题下拉/NGA 调用方式/诊断页全过，截图 `output/desktop-qa/`。安装程序：中文向导真实走完→用户目录安装→桌面+开始菜单图标→完成页自动启动→unins000 静默卸载 exit 0→目录图标清除、settings.json 哈希不变。记录 `output/desktop-qa/installer-acceptance.txt`（含证据瑕疵说明） |
| 2026-08-07 | 任务 6 修复后重打包 | 通过 | 便携 ZIP 新 sha256 `59412d85…593e`（105.7 MB / 2199 文件，已抽查含 hw-academic 蓝锚点与 lint 透传修复）；安装程序新 sha256 `387899fc…c67273`（91.8 MB）。**此为当前最新分发物** |
| 2026-08-07 | 附加：open-kimi-ppt 二次评审（聚焦图绘制）+ 架构图渲染改造 | 通过 | 评审结论落档 `docs/design/REVIEW_OPEN_KIMI_PPT.md` §6（对方无图形引擎，最有价值是"制图纪律"文本；我们确定性路线更强）。渲染改造：架构图节点白底+类型色边框、emphasis 实心红、连接 emphasis 的边红色加粗（关键路径）、组框 2pt 虚线→1pt 实线浅灰底；Graphviz 与回退双路径同步；lint HW-W02 节点校验改验边框色；相关测试断言同步。证据 `output/diagram-review/` |
| 2026-08-07 | 附加：深色主题重构（WPF + Web） | 通过 | token 表重写为深色（`docs/design/FRONTEND_TOKENS.md`）；WPF 全套控件深色模板（含 ComboBox/CheckBox/DataGrid/ProgressBar/ScrollBar 自绘模板）；Web CSS 深色化。修复：ComboBox TemplateBinding 绑定层级错误、设置页两个下拉默认值不回显。xUnit + 静态测试 + UI 回归全绿，截图 `output/desktop-qa/dark-shots/`、`output/visual-review-dark/` |
| 2026-08-07 | 附加：双主题 + AI Arena 交互吸收 | 通过 | WPF 调色板抽 `Themes/Palette.Dark/Light.xaml` + DynamicResource 全量改造，设置页"外观"即时切换并持久化 `settings.json: appearance`；Web `:root[data-theme="light"]` + 顶栏切换按钮。生成页简洁/高级渐进披露（高级选项折叠面板收模板/图片/输出主题，新增任务级主题下拉 `deck-theme`）；任务阶段 10 段可视化 + 生成器快照；结果分块主产物/合规与审计/下一步。修复：UIA Toggle 不触发 Click → 改挂 Checked/Unchecked。**已重打包**：ZIP `0a6d0411…b36a2`、安装程序 `55070608…a38f`（含图渲染+双主题+交互全部改动，**当前最新分发物**） |
| 2026-08-07 | 代码审查遗留处理：NGA CLI 发布阻断 bug + 中级项 | 通过 | **严重**：`_send_cli` 把 prompt 作命令行位置参数，Windows CreateProcess 上限 32767 字符，deck prompt（约 58 KB）必然 WinError 206 且被误报为"CLI 找不到"（本机实测复现）。修复：win32 spawn 前长度预估守卫 + winerror 206 区分，改报诚实 E010（建议 HTTP 传输/Stub）。**中级**：①cli_path 放行含空格路径（list 传参无注入风险，`C:\Program Files\…` 可配）；②preflight 提交时拦截 win32+CLI+deck（确定性不可行场景），快速失败。新增/更新测试 5 例，全量 663 passed、ruff 全绿。永久修复（stdin/文件传 prompt）待内网确认 `nga run` 能力，记 `QUESTIONS.md` 第 7 条。**已重打包**：ZIP `39e2f8dd…1fe2b`、安装程序 `170fb933…911de`（91.9 MB，均已抽查含修复，**当前最新分发物**） |

## 五、快速定位（遇到问题时）

- **任何 `.ps1` 报 ParserError / 中文乱码** → 文件必须是 UTF-8 **带 BOM**（Windows PowerShell 5.1 按 ANSI 解析无 BOM 文件）。修复：用 Python 补 `\xef\xbb\xbf` 头（2026-08-06 已对全部现存脚本处理，新写脚本时注意）

- `.\scripts\win\verify_all.ps1` 失败 → 看 `output\workbench\workbench.stderr.log` 与 pytest 输出
- `.\scripts\win\build_all.ps1` 失败 → 确认 .NET SDK 版本、Graphviz 路径
- `.\scripts\win\package_setup.ps1` 失败 → 确认 Inno Setup 6 安装、ISCC.exe 路径
- 工作台 5056 拒绝连接 → `.\scripts\win\start_workbench_ui.ps1` 启动后再访问
- NGA 测试连接失败 → 确认 `nga providers login` 已完成、CLI 路径、`nga run` 手工可用
