# Version Consolidation Report

报告日期: 2026-08-01
工作分支: `codex/consolidate-latest-20260801`
保护标签: `pre-version-consolidation-20260801`

## 1. 识别结果

发现并分析了 Git 开发分支、Web API、PPT 生产/实验引擎、WPF/浏览器客户端、Office 包
安全、生成脚本、产品版本声明和人工验收文档等候选组。详细矩阵、证据评分和调用关系见
`VERSION_CONSOLIDATION_AUDIT.md`。

唯一正式基础是 `fd0317f` 及本分支后续整合提交。17 个旧分支全部是当前 HEAD 的祖先，
分支独有提交均为 0；没有 `FEATURE_DONOR` 需要迁移。旧分支名称和提交时间未作为正式
版本判断依据。

## 2. 功能合并结果

| 功能 | 原来所在版本/位置 | 合并到正式模块 | 测试 | 结果 |
| --- | --- | --- | --- | --- |
| 产品版本 | API、打包器、WPF、XAML、User-Agent 多处 `2.1.0` | 根 `VERSION`、`app.version`、WPF Assembly `AppInfo` | `test_product_version.py` | 专项 3/3 通过，便携目录子进程可读取 |
| 当前人工门禁 | 早期 `docs/HUMAN_REVIEW.md` | 同路径当前门禁清单 | `test_docs.py` | 不再描述 DeckIR 1.1、图片/图表占位或未实现 NGA |
| 正式入口声明 | README 各章节分散描述 | README“唯一正式版本与入口” | `test_docs.py` | WPF/API/CLI/验证/构建职责已明确 |

旧分支没有未合并功能，因此没有执行 cherry-pick、算法回退或 IR 契约合并。

## 3. 删除与替换结果

| 路径/内容 | 原因 | 替代实现 | 对应提交 | 恢复方式 |
| --- | --- | --- | --- | --- |
| 历史 `backend/app/web.py` | 旧 5055 同步服务，缺当前异步/安全契约 | `backend/app/web_api.py` | `fd0317f` | `git show c9e000e:backend/app/web.py` |
| placeholder renderer/lint | 已被真实 renderer 和真实 lint 完全替代 | `app.rendering.*`、`app.lint.*` | `fd0317f` | 从 `c9e000e` 按路径只读恢复 |
| 多处产品版本硬编码 | 易产生跨栈发布漂移 | 根 `VERSION` | 本次整合提交 | 从保护标签查看修改前文件 |
| 早期 `docs/HUMAN_REVIEW.md` 正文 | 与 DeckIR 2.0、AssetManifest、NGA/WPF 现状冲突 | 当前人工门禁清单 | 本次整合提交 | `git show pre-version-consolidation-20260801:docs/HUMAN_REVIEW.md` |

没有删除远程分支、重写历史或清理用途未确认的本地 `backup-*` 引用。历史版本通过 Git
恢复，不在当前工作树创建 `old`、`final`、`copy` 或日期源码副本。

## 4. 唯一正式入口

| 类型 | 唯一正式入口 | 边界 |
| --- | --- | --- |
| 主用户入口 | `DocumentWorkbench.exe` / `desktop/DocumentWorkbench` | WPF 只通过受保护本地 HTTP 使用后端 |
| API 服务 | `python -m app.web_api` | 唯一 Flask API；浏览器兼容客户端复用它 |
| 桌面后端宿主 | `python -m app.desktop_host` | WPF 专用进程生命周期适配器，不复制 API 逻辑 |
| 解析 | `python -m app.cli.parse` | 源文件到 DocumentIR |
| Prompt | `python -m app.cli.prompt` | 只组装 Prompt |
| 渲染 | `python -m app.cli.render` | 校验后的 WordIR/DeckIR 到 Office 文件 |
| 检查 | `python -m app.cli.check` | DOCX/PPTX 合规复检 |
| Deck 便捷生成 | `scripts/generate.py` | `demo_e2e.py` 的 Deck 薄包装，不是第二套 pipeline |
| 测试/发布门禁 | `verify.ps1` | Windows 离线统一入口 |
| WPF 构建/打包 | `scripts/package_document_workbench.py` | 版本取自根 `VERSION` |
| 配置 | theme JSON、NGA settings + Credential Manager | 各自单一职责，优先级见 `ARCHITECTURE.md` |
| 生产 PPT 引擎 | DeckIR 2.0 -> `python-pptx` | HTML/PptxGenJS 仅 `experiments/html2pptx/` |
| 训练/推理 | 无 | 本仓库不是模型训练项目 |

## 5. 验证命令与结果

| 命令 | 状态 | 结果摘要 |
| --- | --- | --- |
| 版本单源测试（实现前） | 预期失败 | `ModuleNotFoundError: app.version`，证明尚无单源实现 |
| 文档治理测试（替换前） | 预期失败 | README 缺唯一入口，旧人工文档仍描述早期能力 |
| `pytest test_product_version.py test_docs.py` | 通过 | 12 passed；便携目录子进程读取同一版本 |
| 受影响 API/desktop/Windows 专项 | 通过 | 50 passed |
| `pytest backend/tests -q` | 通过 | 601 passed、15 skipped、0 failed |
| `python scripts/verify.py` | 通过 | 四格式 Stub；parsers 93.51%、IR 93.82%、lint 94.30%、整体 88.95% |
| `verify.ps1` | 通过 | Graphviz 系统运行时；整体覆盖率 89.17% |
| `scripts/reliability_test.py` | 通过 | 616 项：601 通过、15 跳过、0 失败 |
| WPF Debug xUnit/FlaUI | 通过 | 3/3 |
| WPF Release build | 通过 | 0 warning、0 error；Assembly `2.1.0.0` 与根 `2.1.0` 对齐 |
| `package_document_workbench.py --help` | 通过 | 打包入口可加载单源版本 |
| Python 版本单行核对 | 修正后通过 | 首次漏设 `PYTHONPATH` 无法导入；按规定设置 `backend` 后输出 `2.1.0` |
| Ruff、diff、版本/入口残留扫描 | 通过 | 无静态错误、空白错误、含糊源码路径或旧生产入口引用 |

## 6. 残留扫描

- 当前受 Git 管理路径没有含糊命名的源码副本。
- 当前源码没有第二个产品版本字面量；文档中的发布示例使用 `<VERSION>`。
- 旧 Web、placeholder renderer/lint 和 5055 入口没有生产引用。
- 生产 Python、WPF、启动脚本和依赖 lock 不引用 HTML/PptxGenJS 实验。
- 依赖清单按生产、Windows lock、质量测试、UI 测试和 HTML 实验分域，不互相竞争。
- WPF Assembly、Python API、便携 backend 和打包器均从根 `VERSION` 得到 `2.1.0`。

## 7. 未决事项

1. `backup-*` 本地分支均已合并且无独有提交，但是否删除仍需确认其人工备份用途。
2. 损坏的 Codex checkpoint ref 需要宿主工具处理；本轮不直接编辑 `.git`。
3. 正式 `vMAJOR.MINOR.PATCH` release tag 要等代码签名、干净 Windows 断网验收和人工视觉
   签字后由项目负责人创建；保护标签不是 release tag。
4. 真实业务语料、授权图片、真实 NGA 和 Office 审美仍按 `QUESTIONS.md` 与
   `docs/HUMAN_REVIEW.md` 执行。
