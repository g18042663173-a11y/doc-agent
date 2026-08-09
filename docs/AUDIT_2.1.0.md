# 2.1.0 审计与发布候选报告

日期：2026-08-08
候选基线：`codex/audit-2.1.0`（工作树中的 2.1.0 实验改动）

## 结论

当前候选已通过本机 Windows 11 的自动化技术门禁、便携包启动和安装包内容校验，能够作为
**2.1.0 技术发布候选**生成 ZIP、安装 EXE 与 SHA-256。它还不能宣称为正式内网推广版：
Windows 10、干净断网机器、真实 NGA、Office 字体/审美签字和代码签名仍须人工完成。

外部链接所声称的来源及内容无法在本次审计中验证，未被读取、引用或作为“华为内部设计”
依据。界面决策仅依据本地 token、Windows 10/11 设置应用的公开交互语言和本地截图回归。

## 已核对的边界

- IR 仍是唯一渲染契约；Schema 快照和 C0 Stub 全链路通过，未为样例放宽 Schema。
- Office/模板 ZIP 输入保持路径穿越、反斜杠、NUL、符号链接和大小写重复目标拦截；
  安装器解压仅接受受控 POSIX 归档路径。
- 上传限制、任务目录约束与清理、受控下载白名单、桌面会话头、NGA 错误映射和凭据不落盘
  均由现有专项测试覆盖。
- Graphviz 调用改为二进制流读取，再显式解码 JSON，避免本地化 Windows `dot` 在 stderr
  输出非 UTF-8 字体诊断时使 Python 子进程读取线程异常；有回归用例保护。
- FlaUI 便携包验收改为断言进程真实退出。此前测试使用的
  `WaitWhileMainHandleIsMissing` 只能等待窗口出现，不能证明退出；修正后 WPF 和后端
  `pythonw` 均不残留。
- 截图采集改为以目标 HWND 调用 Windows `PrintWindow`，并在采集线程启用 Per-Monitor V2
  DPI 上下文。它不依赖前台窗口或虚拟桌面坐标，避免 150% DPI 时将后台 Chrome 内容误写为
  WPF 视觉证据；手工截图脚本同步采用该路径。
- 深色主题下的页面标题、小节标题和字段标签改为继承 token 化 `TextBlock` 样式；新增回归测试，
  防止 WPF 默认黑色文字重新覆盖深色主题的 `TextBrush`。

## 自动化证据

| 项目 | 结果 |
| --- | --- |
| `scripts/win/verify_all.ps1 -Ui` | 通过；C0 覆盖率 parsers 93.51%、IR 93.94%、lint 94.30%、整体 89.20% |
| 后端可靠性 + 浏览器工作台 | 671/671 通过；桌面和移动端系统/浅色/深色、设置、任务、成功/失败截图已生成 |
| `pip check`、ruff | 通过 |
| WPF xUnit/FlaUI | 16/16 通过 |
| 重建便携包的 FlaUI 验收 | 1/1 通过；设置、主题、诊断、高级选项和 1024x700/1280x820/1920x1080 截图已生成 |
| ZIP 内容校验 | 2,198 条内部 SHA-256 均匹配；未发现 `.env`、设置、测试目录、字节码或 PDB 泄漏 |
| 安装包内容与签名状态 | 5 项安装包/静态回归通过；AuthentiCode 为预期的 `NotSigned` |

截图与 QA 报告位于 `output/qa/`；本轮最终便携包验收截图位于
`output/qa/audit-2.1.0/portable-final-printwindow-20260808121728/shots/`。本机为 Windows 11
150% DPI；该目录包含浅色、深色、跟随系统与三个窗口尺寸的窗口级截图。

## 发布物

| 文件 | SHA-256 |
| --- | --- |
| `dist/document-workbench-windows-x64-2.1.0.zip` | `2ecf5b4dad419cd46ce6a1bb99ca00fe0422e757d593c2d5f7fc925787c3b537` |
| `dist/HuaweiDocumentGenerator-Setup-2.1.0.exe` | `b10330dac2fe8ccac3e8477a7cc1688797563499f3c8a43acb35b16e20ca87b3` |

对应的 `.sha256` 文件位于 `dist/`。ZIP 内 `SHA256SUMS.txt` 的 2,198 项再次逐项复核通过。

## 已知限制与人工门禁

1. 本次机器为 Windows 11，已实际覆盖 150% DPI；Windows 10、100%/200% DPI 和高对比度
   真机验收仍待完成。
2. 真实 NGA 凭据、端点、证书链和业务语料未提供；自动化仅使用 Stub 和模拟 NGA。
3. 最终 DOCX/PPTX 需在目标 Office 与字体环境中完成人工内容抽查和视觉签字。
4. 无内网代码签名证书与时间戳流程，发布物保持无签名，使用 SHA-256 校验。
5. 曾出现一次 `planning_visuals` 阶段的已脱敏 `E001` 后台失败；隔离及后续全量运行均未复现。
   因失败报告刻意不保存异常链，无法将其归因于单一产品异常。后续若重现，应在不泄露输入、
   Prompt 或堆栈的前提下记录内部异常类别并补最小回归用例。

## Git 与发布判定

- 旧 `backup-*` 分支仅保留为恢复依据，不做强制合并或删除。
- `git fsck` 报出的 `refs/codex/turn-diffs/checkpoints/...` 零值/过长 ref 属宿主工具
  checkpoint 状态，不修改其 `.git` 内容，也不视为产品代码缺陷。
- `codex/release-2.1.0` 应仅在上述人工门禁记录齐全后创建；在此之前保留
  `codex/audit-2.1.0` 作为审计候选分支。
