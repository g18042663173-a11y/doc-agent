# QUESTIONS

> 分步执行清单见 `docs/WINDOWS_ACCEPTANCE_20260806.md`（Windows 验收与人工交付清单）。

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
   - 当前默认值:使用构造样例、固定公开样例和 HIT 模板覆盖结构与边界。
   - TODO:导师或业务侧提供真实语料后纳入 fixtures,不得用构造样例冒充真实验收。
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
