# 人工交付门禁

自动测试、lint、OOXML 包校验和 Office 导出只能证明确定性软件行为，不能替代真实业务
语义、目标环境视觉效果、内网协议兼容性和组织发布审批。未取得人工证据时，相应状态必须
保持 `manual_pending`。

## 自动化已经覆盖

- DocumentIR 1.2、WordIR 1.2 和 DeckIR 2.1 的 Schema、迁移器、正反样例及剥壳校验。
- Markdown、DOCX、XLSX、PPTX 解析到 Stub Word/PPT 的离线确定性链路。
- `AssetManifest 1.0` 图片安全导入、真实图片嵌入、焦点裁切、DPI 与使用审计。
- 原生可编辑图表、表格、信息图、模板 Profile/Plan、W201/W202 回退及包关系检查。
- NGA OpenAI-compatible adapter 的鉴权、TLS、重试、超时、响应格式和失败脱敏模拟测试。
- WPF 本地会话保护、Windows Credential Manager 凭据边界、任务恢复/取消与受控下载。
- `verify.ps1`、可靠性 QA、Ruff、xUnit/FlaUI 和可选浏览器工作台回归。

这些结果不代表下面的人工门禁已经通过。

## 1. 真实业务语料与语义抽查

业务侧需提供脱敏且授权使用的真实 DOCX、XLSX、PPTX 各至少 3 个，并记录文件哈希、来源、
预期行为和允许公开的最小复现 fixture。评审人需逐项确认生成内容没有遗漏、错误归纳、虚构
数据或改变业务口径。原始敏感文件不得提交 Git。

## 2. PowerPoint 与 Word 最终视觉签字

在目标 Windows、Office 版本和目标字体环境打开最终 DOCX/PPTX，检查字体替代、文本裁切、
重叠、表格分页、图表标签、模板保真、密级、页码和对象可编辑性。Office 导出的 PNG/PDF
联系表只能作为评审材料；没有评审人、日期和结论时保持 `manual_pending`。

## 3. 图片版权与视觉语义

真实 PNG/JPEG/WebP 必须记录来源、版权/授权、署名、替代文本和关键焦点。自动
`AssetManifest 1.0` 安全检查不判断版权，也不能证明图片与业务叙事匹配。低分辨率、裁切或
署名 warning 必须由评审人决定是否接受。

## 4. 模板安全处理

宏、ActiveX、OLE、外部关系和损坏包继续以 `E003` 阻断。人工不得通过关闭预检来放行；
应在 PowerPoint 中删除嵌入对象、转为安全图片或重建模板后另存为 `.pptx`。模板通过安全
检查后仍需人工确认母版继承、原型映射和 `master_redraw` 页面观感。

## 5. 干净 Windows 断网验收

在未预装项目 Python/.NET 依赖、无管理员权限的 Windows 10/11 x64 机器上：

1. 校验开发快照、wheelhouse 和便携 ZIP 的 SHA-256。
2. 断网运行 `bootstrap_windows.ps1` 和 `verify.ps1`。
3. 双击 `DocumentWorkbench.exe` 完成 Stub Word/PPT、模板、图片、失败与恢复流程。
4. 用 Word/PowerPoint 打开并编辑产物，记录系统、Office、字体和终端防护版本。
5. 扫描便携目录、LocalAppData、日志和失败报告，确认没有 Token、Prompt 或输入正文泄漏。

## 6. 真实 NGA 冒烟

内网提供实际 base URL、endpoint、模型、Token、自定义 CA 和响应样例后，在 WPF 设置页先
“测试连接”再启用。至少完成 WordIR 和 DeckIR 各一条最小真实链路，确认
`choices[0].message.content`、`response_format`、限流和证书策略。协议不兼容时新增 adapter，
不得绕过 IR Schema，也不得静默回退 Stub。

Token 只能保存到 Windows Credential Manager 的 `HuaweiDocumentGenerator/NGA`，不得进入
设置 JSON、任务目录、日志、失败报告或验收截图。

## 7. 签名与发布审批

正式推广前使用内网代码签名证书签署 `DocumentWorkbench.exe`，验证签名链、时间戳、
SmartScreen/终端防护策略和签名后的文件哈希。无签名 ZIP 只能作为受控内部试点。

## 证据记录

每项人工门禁至少记录：评审项、输入哈希/产物哈希、环境版本、执行人、日期、结论、失败
截图或报告路径、复测结果。当前未完成事项以 `QUESTIONS.md` 为准；不得因为自动报告为绿色
而删除或改写人工待办。
