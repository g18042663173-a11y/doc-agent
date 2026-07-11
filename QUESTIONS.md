# QUESTIONS

## 人工待办

1. 真实文件语料:需要提供脱敏后的真实 docx / xlsx / pptx 各至少 3 个,放入 `samples/input/real/`,用于解析回归。
   - 当前默认值:使用构造样例与测试动态生成样例覆盖边界。
   - TODO:导师或业务侧提供真实语料后纳入 fixtures。
2. Windows 离线验收:需要在干净 Windows + Python 3.12 环境中执行 wheelhouse 安装与 `python scripts/verify.py`。
   - 当前默认值:已提供 `scripts/make_wheelhouse.py` 和接入说明,但未在 Windows 真机验证。
   - TODO:人工记录 Windows 版本、Python 版本、安装输出和截图。
3. PPTX 视觉终审:需要人在 Windows PowerPoint 中打开生成产物做字体、观感、专业度判断。
   - 当前默认值:lint 通过代表硬规则通过,不代表最终视觉可交付。
   - TODO:内网字体/CI 校准后复核 `backend/app/rendering/themes/hw_theme.json`。
4. 临时 CodexGenerator 上限验证:CCSwitch 已切换到 custom provider 的 `gpt-5.5`，项目 `CodexGenerator` 已通过显式 `CODEX_GENERATOR_TRANSPORT=cli` 接入其新启动的 Codex CLI 认证会话。
   - 当前结果:以 `scripts/demo_e2e.py --generator codex` 实跑公开技术报告，真实 WordIR（33 blocks）和 DeckIR（10 页）原始输出均直接通过 Schema；DOCX/PPTX 及 PDF 预览均已生成。DOCX lint 无错误/无警告；PPTX lint 为 0 Error、1 Warning（HW-W09）和 1 Info（HW-I01）。默认 HTTP transport、默认 stub 和既有 IR 契约保持不变。
   - 诚实边界:HTTP transport 仍只使用环境变量 API key；CLI transport 仅在 CCSwitch/Codex 已认证并显式启用时可用，使用 `codex exec --ephemeral --ignore-rules -s read-only`，不保存或打印凭据。此前直连 custom provider 的 HTTP 请求返回 502，不代表 CLI transport 可用性。
   - TODO:Mac LibreOffice 预览缺少微软雅黑且出现黑底/方框字，DOCX/PPTX 的最终视觉验收仍应在 Windows PowerPoint/Word 完成。聊天中提供的临时 key 应立即轮换，且不得写入仓库或日志。
