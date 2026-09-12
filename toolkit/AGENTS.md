> 2026-09-05 当前实现说明：本仓库已在 Windows 上具备本机 Office 和便携运行时。本文早期“你跑不了 Windows”“不支持真实语料”的环境假设不再适用。完整模仿遵循 `docs/superpowers/specs/2026-09-05-complete-imitation.md`，保持全部源页与截图，使用真实 PowerPoint 导出和 Agent 逐页复核，并区别自动检查与视觉验收。已有 WPF/本地 API 保持生成功能。

# AGENTS.md — 华为风格文档生成工具链(Codex 运行手册)

本文件是 Codex 的操作手册(runbook),放在仓库根目录、Codex 会自动读取。**权威规格是 `docs/taskbook.md`(《实习任务书 定稿交付版 v3》)**。动手前先通读它,重点 §0.5、§2、§3、§7、附录 A。

## 三条最高原则

1. **IR 是唯一契约,模型文本永不直连渲染器**(不变量 I1):进渲染器的 JSON 必先剥壳 → Schema 校验 → 再渲染;失败给错误码 + 定位,绝不"尽力渲染"。
2. **先 stub 后真模型,先测试后实现**:每张卡先用 stub generator + 测试跑通,拿到确定性绿灯再往下;整条链路要能在无 AI、断网下全量运行。
3. **你交付的是围绕 IR 的确定性流水线**(解析 → 组装 → 校验 → 渲染 → 合规检查 → 测试),不是"产 IR 的 AI"——那是既有能力。

## 环境与跨平台(务必)

- 开发在 macOS / 类 Unix(你在这);目标运行环境是**内网 Windows(离线)**。核心代码纯 Python、跨平台;Python 3.12。
- 路径一律用 `pathlib`;文件读写一律 `encoding="utf-8"`;不 shell out 平台专属命令;平台差异只留在 `verify.sh` / `verify.ps1` 薄封装。
- 技术栈锁定:python-docx、openpyxl、python-pptx、pydantic v2、pytest。不引入 FastAPI / Web(Web 是 P2);PPTX 用 python-pptx 自绘,禁手工 HTML。

## 工作循环(逐张任务卡)

按 §8 从 S1-1 顺序推进。每张卡:读"关键实现点 + 验收标准" → 先写模型 / stub + 对应测试 → 实现 → `pytest` 与 `python scripts/verify.py` 全绿 → 逐条自查验收 → 小步 commit(信息带卡号)。

- **契约优先**:最先落 §3 三份 IR 的 pydantic 模型 + 导出 JSON Schema 到文件 + 快照测试,并作为**第一个 commit** 冻结(便于随时 review diff),再写消费它们的代码。
- **覆盖率**:parsers + ir + lint 三包 ≥ 80%,整体 ≥ 70%。
- 产合法 JSON / IR 优先用 Structured Outputs / Schema 约束,不靠字符串拼装。

## 硬护栏(绝不做)

- 不为让样例通过而放宽 / 绕过 Schema;需求变更:先改 Schema + 升 `ir_version` + 更新正反样例,再改代码。
- 不"尽力渲染"非法 IR;错误走 E / W / D 系并定位。
- 不 shell out 平台命令;不假设 AICoding 读本地文件(输入贴进 Prompt);不搬运图片二进制(P2)。
- 不自造 Schema 外字段;不打乱约定的目录职责分层。

## 遇到阻塞时(关键:不要停,记下来继续)

- 需要外部事实或人工决策的(附录 A.2 五问、任何需改 IR 契约的情况):**不要卡住整个 run**。追加到 `QUESTIONS.md`(写清问题 + 你暂用的默认值 + 打 `TODO`),然后**继续做其它未阻塞的卡**。
- 只有当某阻塞导致**再无任何可推进的工作**时,才 soft-stop 并汇报。

## 你做不了、必须留给人的(不要伪造 / 假装完成)

- **真实文件语料**:你只能构造边界样例;真实 docx / xlsx / pptx 需人收集。把需要的清单写进 `QUESTIONS.md`。
- **Windows 平台 wheelhouse + §7.4 真机离线验收**:你跑不了 Windows。产出 `make_wheelhouse.py` 与锁定 `requirements`(含 hash),把真机验证标记为人工待办。
- **字体保真的 PPTX 视觉终审**:可让 lint 全绿、可选做视觉打分回路,但"像不像华为、拿不拿得出手"由人在 Windows 判定。**lint 全绿 ≠ 可交付。**

## 进度与审计

- 持续维护 `PROGRESS.md`:当前检查点、已验证什么、还剩什么、是否阻塞。这是我离开数小时后能看懂发生了什么的凭据。

## 结束报告(达成停止条件或 soft-stop 时)

分四块,诚实区分:① 已完成并通过验收;② 做了降级 / 近似(如 chart 占位、image 占位);③ 阻塞待人输入(附 `QUESTIONS.md` 摘要);④ 仍不确定。
