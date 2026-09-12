# Repository Audit

审计日期: 2026-07-31
审计分支: `codex/repository-cleanup-20260731`
权威需求: `docs/taskbook.md`

## 1. 项目用途

本项目是面向内网 Windows 的可编辑 Office 文档生成工具链。正式数据流是:

```text
MD/DOCX/XLSX/PPTX
  -> DocumentIR
  -> Prompt + Stub/NGA/Codex adapter
  -> JSON 剥壳与 Schema 校验
  -> WordIR/DeckIR
  -> python-docx/python-pptx renderer
  -> lint、包安全检查与审计文件
```

IR 是唯一业务契约。模型文本不得直接进入 renderer。HTML/PptxGenJS 仅存在于隔离实验，不是生产引擎。

## 2. 技术栈

| 范围 | 技术 |
| --- | --- |
| 核心 | Python 3.12、Pydantic v2、pathlib |
| Office | python-docx、openpyxl、python-pptx、Pillow |
| API | Flask、waitress、线程队列 |
| 桌面端 | .NET 8 WPF、HttpClient、Windows Credential Manager |
| 图布局 | Graphviz，缺失时确定性降级 |
| 测试 | pytest、pytest-cov、xUnit、FlaUI、可选 Playwright |
| 实验 | Node.js、PptxGenJS、Playwright、Sharp，仅 `experiments/html2pptx/` |
| 发布 | Windows wheelhouse、Python embeddable、WPF self-contained ZIP |

仓库没有数据库、Notebook、训练入口或科研模型检查点。

## 3. 当前目录

```text
backend/app/                 Python 正式实现
backend/tests/               Python 单元与集成测试
backend/schemas/             冻结的 JSON Schema 快照
desktop/DocumentWorkbench/   WPF 正式客户端
desktop/DocumentWorkbench.Tests/
docs/                        任务书、使用、验收和实验文档
experiments/html2pptx/       隔离对照实验
samples/                     固定输入、IR、golden 和演示资产
scripts/                     验证、发布、QA 和开发工具
wheelhouse/                  Windows 离线依赖缓存，不入 Git
output/                      运行产物，不入 Git
dist/                        发布产物与迁移 ZIP，不入 Git
```

## 4. 真实运行入口

| 类型 | 正式入口 | 说明 |
| --- | --- | --- |
| Windows 桌面 | `desktop/DocumentWorkbench` | 普通用户入口，启动受会话密钥保护的本地后端 |
| 浏览器兼容入口 | `python -m app.web_api` / `start_workbench.ps1` | `127.0.0.1:5056`，异步任务 API |
| 解析 | `python -m app.cli.parse` | 输入转换为 DocumentIR |
| Prompt | `python -m app.cli.prompt` | 只组装 Prompt，不渲染 |
| 渲染 | `python -m app.cli.render` | 先校验 IR，再生成 DOCX/PPTX |
| 检查 | `python -m app.cli.check` | 独立 lint 入口 |
| E2E | `scripts/generate.py`、`scripts/demo_e2e.py` | Stub/NGA/Codex 生成链路 |
| 发布门禁 | `verify.ps1`、`scripts/verify.py` | 离线依赖、四格式 E2E、pytest 与覆盖率 |
| 可靠性 QA | `scripts/reliability_test.py` | JSON、JUnit、HTML 报告 |
| WPF 发布 | `scripts/package_document_workbench.py` | self-contained Windows ZIP |

已删除的 `backend/app/web.py` 是 5055 端口的旧同步原型，不是正式入口。

## 5. 构建与测试

```powershell
.\bootstrap_windows.ps1
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe scripts\reliability_test.py
.\verify.ps1
```

WPF 使用仓库锁定的 .NET 8 SDK 和 `desktop/NuGet.Config`。浏览器 UI、FlaUI 和真实 NGA 测试是独立门禁，不进入 Python 生产依赖闭包。

## 6. 主要架构问题

1. `backend/app/web_api.py` 曾同时承担路由装配、任务状态、上传、生成编排和错误映射，工厂 McCabe 复杂度为 59。
2. `backend/app/rendering/pptx_renderer.py`、`backend/app/lint/pptx_lint.py` 和 WPF `MainWindow.xaml.cs` 体积较大，但具有高行为风险，不能无测试地切割。
3. 仓库根目录积累了多个过期状态、周报、临时计划和迁移说明，内容仍引用旧 IR/旧测试数字。
4. 存在旧同步 Web、C0 placeholder renderer 和 synthetic passing lint report 三套已被正式实现替代的代码。
5. Git 中存在多个 `backup-*` 长期分支、无正式标签，并有损坏的 Codex checkpoint refs 警告。
6. `.gitignore` 含部分历史文件名规则，和当前文档治理边界不完全一致。

## 7. 重复与多版本清单

| 项目 | 正式实现 | 旧实现/副本 | 结论 |
| --- | --- | --- | --- |
| Web 工作台 | `backend/app/web_api.py` | `backend/app/web.py` | `REMOVE_AFTER_VERIFICATION`，已删除 |
| PPT lint | `app.lint.pptx_lint` | `app.lint.placeholder` | `REMOVE_AFTER_VERIFICATION`，假绿报告已删除 |
| Office 占位 renderer | DOCX/PPTX 正式 renderer | `app.rendering.placeholder` | `REMOVE_AFTER_VERIFICATION`，已删除 |
| Office 包安全 | `app.security.office_package` | `app.parsers.office_preflight` | `KEEP`，后者是错误契约适配器，不是重复扫描器 |
| PPT 引擎 | Python renderer | `experiments/html2pptx` | `KEEP` + `EXPERIMENT`，禁止生产引用 |
| 用户入口 | WPF | 同源 HTML 页面 | `KEEP`，分别为正式桌面端和兼容诊断入口 |

## 8. 文件分类

| 分类 | 文件/目录 | 依据 |
| --- | --- | --- |
| `KEEP` | `backend/app/ir`、`parsers`、`rendering`、`lint`、`security` | 正式数据链与硬门禁 |
| `KEEP` | `desktop/DocumentWorkbench*` | Windows 原生正式入口及测试 |
| `KEEP` | `samples`、`backend/schemas` | 可复现 fixture 与契约快照 |
| `REFACTOR` | `backend/app/web_api.py` | 编排职责过多，已分批提取 handler/context |
| `REFACTOR` | `backend/app/cli/render.py` | Word/PPT 分支已拆分 |
| `REFACTOR` | `pptx_renderer.py`、`pptx_lint.py` | 仅在固定 golden/视觉回归后继续拆分 |
| `ARCHIVE` | 历史审计和设计报告 | 不应继续与当前运行文档混放 |
| `DEPRECATE` | `backup-*` 本地分支 | 需确认远程/人工用途后统一归档，不自动删除 |
| `REMOVE_AFTER_VERIFICATION` | 旧 Web、placeholder 模块、过期状态文档 | 无正式引用且已有替代实现 |
| `NEEDS_CONFIRMATION` | 真实脱敏文件、Office 视觉基线、代码签名 | 自动化无法代替人工验收 |

## 9. 高耦合与风险点

- IR Schema、迁移器、renderer、lint 是联动边界；任何字段变化必须先升版本并更新快照。
- 模板克隆涉及 OOXML 关系安全，不能为了接受 OLE/ActiveX 模板而放宽预检。
- API 任务目录含敏感中间文件，失败和完成后必须继续执行清理。
- WPF Token 只能进入 Credential Manager，配置、日志和失败报告不得落盘。
- Graphviz、PowerPoint COM、Playwright 和真实 NGA 都有可选环境依赖，不能伪装为离线门禁通过。
- 根目录迁移 ZIP 约 449 MiB，是明确保留的用户迁移资产，不属于待删缓存。

## 10. 需要人工确认

1. 哪些 `backup-*` 分支仍承担人工备份职责，确认后才能删除或打归档标签。
2. 正式版本号、首个 release tag 和内网签名证书。
3. 真实 NGA 地址、模型、证书链及协议差异。
4. 真实脱敏 docx/xlsx/pptx 语料和 PowerPoint 最终视觉签字。
5. Codex checkpoint 损坏 refs 是否由宿主工具清理，不在本次分支直接修改 `.git`。

## 11. 优先级

1. P0: 保持 IR/安全/失败契约，删除假绿和重复正式入口。
2. P0: API/CLI 编排拆分后执行全量 pytest、coverage、verify、WPF build/test。
3. P1: 文档与 Git 工作流归一，清理生成缓存和过期状态文档。
4. P1: 在视觉 golden 充分后继续拆分 PPT renderer/lint。
5. P2: 人工清理历史分支、建立签名 release 和真实业务视觉基线。
