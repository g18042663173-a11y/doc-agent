# QUESTIONS

> 分步执行清单见 `docs/WINDOWS_ACCEPTANCE_20260806.md`（Windows 验收与人工交付清单）。
> 内网 AI 调用适配所需信息见 `docs/内网AI适配信息清单.md`（拿清单找内网平台方填写即可）。

## 2026-08-14 AI 优先默认(用户指令)已完成

- **默认生成器 = AI**:检测到 `OPENAI_API_KEY`(用户级环境变量)时,工作台默认使用
  codex/opencode-go(`https://opencode.ai/zen/go/v1` + `deepseek-v4-flash`);无凭据
  时回退 stub;`IR_GENERATOR` 可强制指定。NGA 仍未接入(按用户决定,进内网再说)。
- **密钥**:仅存于本机用户环境变量(setx 持久化),不进代码、不进 git、不落盘。
  换机器/换密钥:重新 `setx OPENAI_API_KEY <新密钥>` 后重启工作台。
- **进内网时**:默认仍走 AI——只需把 `OPENAI_API_KEY` 换成内网网关凭据,并按
  `docs/内网AI适配信息清单.md` 提供的信息调整 `OPENAI_BASE_URL`/`OPENAI_MODEL`
  (或接入 NGA)。离线不再作为主要目的,但无凭据时仍可 stub 运行。

## 2026-08-14 代码收敛(用户指令)与内网适配准备

- **分支收敛**:主线重命名为 `codex/release-2.2.0`(与 VERSION 对齐);删除全部
  `backup-*` 与旧 `codex/*` 实验分支及旁支 worktree(ai-ppt-2.2.0/2.3.0)共 20 个,
  归档到 `dist/git-bundles/branches-archive-20260814.bundle`(9MB,可恢复);
  2.3.0 未提交改动存档为 `ai-ppt-2.3.0-uncommitted-20260814.patch`(0.3MB)。
- **dist 清理**:删除 2.1.0 与 7 月旧发布物,仅保留 2.2.0 ZIP/EXE/SHA-256/交付说明。
- **内网 AI 适配**:新增 `docs/内网AI适配信息清单.md` —— 13 项信息收集表
  (Base URL/接口路径/认证/模型 ID/JSON 约束/TLS/超时/限流/响应样例等)+ 适配
  步骤与验证基线。拿到内网信息后:OpenAI-compatible 仅配置零代码;协议不同则
  新增 adapter,IR/renderer/lint 零改动(I3 不变量)。
- 主线 `codex/release-2.2.0` 工作树干净,`verify.ps1` C0 通过。

## 2026-08-14 发布冲刺刷新

- **G-N10 已解决**:`codex.py` 默认模型改为 opencode-go 网关实测可用的
  `deepseek-v4-flash`(网关 `/models` 验证;显示名 "DeepSeek V4 Flash" 不被接受);
  网关对 `Python-urllib` UA 返回 403/1010,已加浏览器 UA;真实冒烟全链路通过
  (WordIR 1.3 + DeckIR 2.2,lint 零 Error)。Key 仅环境变量使用,不落盘、不提交。
- **NGA 按用户决定不接入**:默认 stub;真实模型链路走 codex/opencode-go 通道
  (`https://opencode.ai/zen/go/v1`,模型 `deepseek-v4-flash`)。
- **版本对齐**:`VERSION` → 2.2.0,`dist/document-workbench-windows-x64-2.2.0.zip` 与
  `HuaweiDocumentGenerator-Setup-2.2.0.exe` 已重建(含全部修复与 UI 缩放),
  SHA-256 见 `dist/*.sha256`;包内后端冒烟 version=2.2.0 / deck_ir=2.2。
- **C# 真机编译确认完成**:本机 `dotnet build DocumentWorkbench.csproj -c Release`
  0 警告 0 错误;`DocumentWorkbench.Tests` xUnit 17/17 通过(C-N6~C-N10 均已编译验证)。
- **UI 测试修复两处测试资产滞后**(非产品 bug):FailOnceGenerator 缺 `cancel_event`(#28)、
  测试环境缺 `session_token`(#2);修复后 UI 测试 desktop/mobile 全绿。
- **A5 代码签名按用户决定不做**(仅要求安装可用)。
- 剩余人工门禁:干净断网真机验收(本机演练为近似证据,不能冒充)、PowerPoint 视觉
  签字、真实脱敏语料语义抽查。

## 2026-08-14 状态刷新

- **IR-N4(表格 rows 缺 minItems)已解决**:2026-08-13 完成契约升版仪式
  (WordIR 1.2→1.3、DeckIR 2.1→2.2),rows 强制非空,Schema/迁移/样例/快照同步更新。
- **W-N2(任务严格串行)已决策**:web_api 改为 2 个并发 worker + 4 等待位。
- **C-N9(重试按钮)已实现**:重试携带当前输入重放,不再依赖后端保留原始输入。
- **业务语料已生成(用户委托)**:`samples/input/business/` 含 docx/xlsx/pptx 各 3 个
  业务形态仿真文件(由 `scripts/make_business_samples.py` 确定性生成,虚构、完全脱敏),
  已纳入 `backend/tests/test_business_corpus.py`(28 用例:解析确定性 + Word/Deck
  stub 全链路,lint 零 Error)。**注意**:business 是仿真语料,不冒充真实脱敏文件的
  验收证据;`samples/input/real/` 仍须业务侧提供真实文件做最终语义验收。

## 2026-08-13 全量排障后遗留项(需决策或真机验证)

本轮已修复两轮审计报告中绝大多数 HIGH/MEDIUM/LOW 缺陷(主题穿越、UTF-16 DTD、
md/docx/xlsx/pptx 解析边界、shell 剥壳、模板规划/审计、lint 图表数据、web_api
竞态、脚本打包、C# 桌面端多项)。以下项**未自动修复**,原因与建议:

### 需产品决策(Track C)
- **G-N10**: `generators/codex.py` 默认 `gpt-5.6-terra`/`xhigh` 是不存在的模型/推理
  强度值,真端点必 400。当前默认值仅是占位,正确默认需由内网确认后提供。
- **IR-N8**: DocumentIR 表格不要求 rows 非空、image_placeholder 不要求 ref/caption。
  判定为**有意宽松**(DocumentIR 是源数据表示,空表/无引图占位在源文档中合法),
  与 WordIR(输出契约)严格性不一致是设计使然。

### 需 Windows 真机验证(C# / PowerShell)
- ~~C-N6~C-N10 未编译验证~~ → **2026-08-14 已在本机编译确认**:
  `dotnet build DocumentWorkbench.csproj -c Release` 0 警告 0 错误,
  `DocumentWorkbench.Tests` xUnit 17/17 通过。仍建议在干净目标机跑一次
  `dotnet test` + 便携包 UI 走查作为最终证据。
- `stop_workbench.ps1` S-N4(子进程不再 throw)需在真实运行(dot/NGA 子进程)下验证。

### 判定为设计/有意保留(不修)
- #26(运行时兜底改写调用方 plan):磁盘 `template_plan.json` 在渲染后写,与实际一致,
  改写正是记录 fallback 的既定行为。
- #52(docx_lint `except Exception`):lint 对任意输入永不崩溃是有意防御,收窄反而引入
  崩溃风险。
- L-N15(产物文件句柄)/#27:python-pptx/python-docx 加载即读入内存并关闭 zip,引用计数
  回收,无长期句柄占用。
- #3(xlsx 同一 sheet 二次迭代):openpyxl 3.1.5 `ReadOnlyWorksheet.iter_rows` 每次重新
  解析,数据正确,仅冗余解析(性能)。

## 2026-08-12 发布候选测试完成(2.1.0 重建产物,待人工终审)

- 已重建发布物(含全部修复与 DeckIR 2.1 契约):`dist/document-workbench-windows-x64-2.1.0.zip`
  (sha256 `079b4a67b1c6ce47b2146a1c2a93f439f574f45f481d2647e09f2c4d02ced518`,2257 文件)
  与 `dist/HuaweiDocumentGenerator-Setup-2.1.0.exe`(sha256 `04ef3bb769f11d2a69a30ce3a660d1643cf8f81f430eed4c56f84889c8b13ef3`)
- 自动化测试全部通过:pytest 708/15、ruff、verify.py C0、dotnet xUnit 16/16;
  打包应用 UI 走查(便携包与已安装 exe 各 1 次)、包内后端 API 冒烟
  (token 流程 + word 任务 done + lint pass)、SHA256SUMS 校验、静默安装/卸载清理、
  离线 wheelhouse --require-hashes dry-run。
- 测试发现并修复 2 个发布级问题:① 便携包缺 samples/ir few-shot 样例导致包内
  生成必失败(已补打包并回归测试);② packages.lock.json 与钉定 SDK 8.0.423 的
  ILLink.Tasks 版本不同步(已用钉定 SDK 重新生成)。
- TODO(人工终审,自动化无法替代):干净断网机离线安装验收、PowerPoint 视觉审美签字、
  真实业务语料、真机 NGA 接入、代码签名、Windows 10/11 各 DPI 走查。

## 2026-08-12 Track A 修复后的新增人工待办

- TODO: 本机无 .NET SDK,`BackendProcessHost.cs` 管道排空改动(A8,commit c24eb1c)
  未编译验证;需在 Windows 真机 `dotnet build desktop/DocumentWorkbench.sln`(或
  Release 发布脚本)确认 0 错误,并跑 `DocumentWorkbench.Tests`。
- TODO: Track B 与 Track C(见 `代码审查报告_2026-08-12_第二轮.md` 第十章):
  B 批含 #18 表索引、#21 阈值取错、G-N1 CLI 进程树、#28 线程不终止、#29 无超时、
  C# 轮询三兄弟等;C 批需产品决策:NGA CLI 传输是否改 stdin 传 prompt(与第 7 项
  合并)、任务严格串行是否接受、codex 默认模型值、repair 提示是否带 marker。

## 人工待办

1. 真实业务语料:需要提供脱敏后的真实 docx / xlsx / pptx 各至少 3 个,放入 `samples/input/real/`,用于解析与模板生成回归。
   - 当前默认值:已生成业务形态仿真语料 `samples/input/business/`(docx/xlsx/pptx 各 3,
     由 `scripts/make_business_samples.py` 确定性生成,虚构脱敏),纳入
     `test_business_corpus.py` 解析确定性 + Word/Deck stub 全链路回归;另有构造样例、
     固定公开样例与 HIT 模板覆盖结构与边界。
   - TODO:导师或业务侧提供真实脱敏语料后放入 `samples/input/real/`(gitignore 排除,
     不提交)纳入 fixtures;business 仿真语料不得冒充真实文件验收证据。
2. PowerPoint 最终审美签字:需要人在目标 Windows PowerPoint 和目标字体环境中判断模板继承、字体观感、信息密度与专业度是否可交付。
   - 当前结果:自动 lint、包校验和 PowerPoint 16 导出均已执行,HIT 联系表位于 `output/hit_template_acceptance/powerpoint_visual_20260729/contact_sheet.png`；双引擎最终对照联系表位于 `output/html2pptx-final-office/`，均为 `manual_pending`。
   - TODO:业务评审人对最终样例签字;自动检查通过不等于人工审美终审完成。
3. 真实图片语料:需要提供可在交付材料中使用的 PNG/JPEG/WebP，明确版权/来源、署名、替代文本和关键焦点，用于横图、竖图、透明图、低分辨率与 2-4 图网格验收。
   - 当前默认值:使用仓库公开截图和合成图片验证解码、裁切、哈希、DPI 与审计，不把它们冒充业务图片。
   - TODO:业务侧提供脱敏且授权明确的图片后，补真实图文页、图片网格和模板图片槽的 PowerPoint 人工签字。
4. 全新 Windows 物理断网验收证据:需要在未预装项目依赖的干净 Windows 机器上，从发布包和 wheelhouse 完成离线安装并执行 `verify.ps1`。
   - 当前结果:本机 Python 3.12、29 个锁定 wheel 的 `--no-index --require-hashes --dry-run`、`verify.ps1` 和工作台浏览器回归均已通过。
   - TODO:交付人员同时验证开发快照和 WPF 便携 ZIP；在无系统 Python/.NET、无管理员权限下完成 Stub Word/PPT、模拟 NGA、真实 NGA、Graphviz 诊断和 Office 打开，保存系统/Office/字体版本、日志与截图。本机验证不得冒充该证据。
5. 真实 NGA 配置与兼容性:需要内网提供实际 base URL、endpoint path、模型名、Token、自定义 CA 和 Chat Completions 响应样例。
   - 当前默认值:按 OpenAI-compatible `/v1/chat/completions`、Bearer Token、非流式、`temperature=0` 实现；自动测试覆盖成功、鉴权、限流、5xx、超时、TLS、非法/超大响应和重试边界。
   - TODO:在受控内网使用 WPF“测试连接”完成 WordIR/DeckIR 最小真实冒烟；确认 `choices[0].message.content`、`response_format=json_object` 和 CA 策略。若协议不同，新增 adapter，不改 IR/renderer。
6. Windows 代码签名:正式推广前需要内网代码签名证书、时间戳服务和发布审批流程。
   - 当前默认值:2.1.0 ZIP 为无签名内部试点包，清单和 SHA-256 完整，不宣称已满足正式推广签名门禁。
   - TODO:对最终 `DocumentWorkbench.exe` 签名并在干净 Windows 10/11 验证签名链、SmartScreen/终端防护策略和升级后的文件哈希。
7. NGA CLI 长 prompt 传输方式:Windows CreateProcess 命令行上限 32767 字符，deck prompt（约 58 KB）以位置参数传给 `nga run` 必然触发 WinError 206（已在 Windows 实测复现）。
   - 当前默认值:`generators/nga.py::_send_cli` 在 win32 上做长度预估守卫，超限或收到 WinError 206 时抛出 E010「prompt exceeds the Windows command-line length limit; use the HTTP transport or a smaller input」，不再误报为「CLI not found」；auto 模式仍按既有逻辑记录 `generator_fallback` 并降级 stub。
   - TODO:向内网 NGA CLI 维护方确认 `nga run` 是否支持从 stdin 或文件读取 prompt（如 `nga run -` 或 `--prompt-file`）；若支持，将 `_send_cli` 改为 stdin/临时文件传参并补真实 CLI 冒烟，临时文件须写入 job 工作目录并随 24 小时清理策略删除，不落 prompts 持久化。
8. 2.1.0 发布人工门禁:当前 Windows 11 自动化候选已完成（含 150% DPI 的便携包窗口级截图），
   但尚无 Windows 10、干净断网机、真实 NGA 与 Office 最终签字证据。
   - 当前默认值:保留 `codex/audit-2.1.0`；ZIP/安装 EXE 仅作为技术候选交付，哈希见
     `dist/*.sha256`，不创建 `codex/release-2.1.0`，不宣称可正式推广。
   - TODO:按 `docs/WINDOWS_ACCEPTANCE_20260806.md` 在 Windows 10/11 各完成便携包和
     Inno Setup 安装/卸载、150%/200% DPI、系统主题/高对比度、离线 Stub Word/PPT、真实
     NGA（若授权）和设置保留验收；附环境、截图和签字后再批准发布分支。
9. 2026-08-26 实习答辩 PPT 的真实媒体与实测值：需要答辩人提供姓名/部门/导师/日期、
   `/templates` 模板墙截图、`demo.mp4`，以及端到端耗时中位数与成功率样本结果。
   - 当前默认值：封面、页 9、页 12、页 13 均保留可编辑占位；未发现已注册的
     `template_v2` / `huawei-project-report`，因此页 4、页 9 使用可核实的“8 套”版本。
   - TODO：替换真实素材与数值；若模板注册后实测为 10 套，同步更新页 4、页 9，重新运行
     `check.py`、溢出检查、PowerPoint/PDF 逐页视觉检查，并在答辩电脑完成字体、视频和投影终审。
10. rhetoric-deck-workflow 的非多模态媒体策略：模式 A 保留截图与 SmartArt 图形像素，只清可见
    文字再填用户材料。非多模态 Agent 仍无法区分装饰图、截图、带字图或含敏感数据的照片。
    - 当前默认值：seal **不删除** `ppt/media` 与 SmartArt 图形；文本泄漏门 `RD-E040` 只拦源句
      与数字。源图像素留在产物里是故意的，不是把图画成可编辑原生对象。旧默认「seal 删除图片」
      已废弃。
    - TODO：若业务方要求删除含敏感数据的照片，需另增“逐媒体确认清单 + 哈希 + 人工放行”，
      不能仅凭提示词自动分类像素。字体/气质终审仍归人。
11. rhetoric-deck-workflow 的内置 deck_pattern 页序与九类 page_pattern 不完全一致：规格页序还用了
    `cover/conclusion/risk_plan/next_plan/benefit_plan`，但严格 Schema 没有这些页级枚举。
    - 当前默认值：不擅自扩张 page_pattern；内置骨架仅含九类受控业务页。DeckIR 模式从用户材料
      补 cover，并在已有用户结论内容时补 conclusion；source-shell 不新增页面。
    - TODO：若业务方需要五类新增修辞页，先扩 DeckSkeleton Schema、提升版本并补正反样例，再改映射。
