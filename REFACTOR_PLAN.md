# Refactor Plan

本计划采用小批次修改。每批只做一种变换，失败时可单独回滚，不修改 DeckIR 2.0、公共 API 或输出格式。

| 阶段 | 状态 | 目标 | 主要文件 | 风险 | 验证 | 回滚 |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | 完成 | 建立安全分支和迁移 ZIP | Git、`dist/` | 低 | SHA-256、ZIP 清单 | 切回 `codex/windows-native-app` |
| R1 | 完成 | 删除确认无引用的旧实现 | old Web、placeholder、空 storage | 低 | rg、专项 pytest、ruff | 恢复该批删除 |
| R2 | 完成 | 禁止 synthetic passing lint | `scripts/demo_e2e.py` | 中 | CLI/reliability 测试 | 恢复旧分支，但不建议 |
| R3 | 完成 | 简化 CLI 编排 | `backend/app/cli/render.py` | 低 | render/asset/error contract 测试 | 单文件回滚 |
| R4 | 完成 | 拆分 API handler 与任务生成上下文 | `backend/app/web_api.py` | 中 | web API、NGA、资产、模板测试 | 按 handler 批次回滚 |
| R5 | 完成 | 清理过期状态文档和生成缓存 | 根目录、ignored caches | 低 | git status、README 链接、重跑测试 | Git 恢复文档；缓存可再生成 |
| R6 | 完成 | 全量交付验证 | pytest、coverage、verify、WPF | 高 | 所有门禁实际输出 | 定位到最近绿色批次 |
| R7 | 延期 | 后续 renderer/lint 拆分 | PPT renderer/lint | 高 | OOXML、golden、Office 视觉基线 | 独立后续分支 |

## 已完成

- 建立 `codex/repository-cleanup-20260731` 分支。
- 创建迁移包 `dist/huawei_document_generator_windows_dev_20260731.zip`。
- 删除旧同步 Web、占位 renderer、假绿 lint 和无调用私有函数。
- `demo_e2e.py` 改为始终执行真实 lint，保留 `--lint` 兼容参数。
- CLI Word/PPT 路径分离。
- API 路由装配、分析、设置、下载、任务异常和产物上下文分离。
- 删除已被 `PROGRESS.md` 取代的状态快照、周报和迁移说明。
- 全量 Python 回归 `595 passed, 15 skipped`；`verify.ps1` 通过，整体覆盖率 89.17%。
- 可靠性 QA 共 610 项，595 通过、15 跳过、0 失败；WPF Release 构建 0 warning/0 error，测试 3/3 通过。

## 完成标准

1. `ruff` 正确性门禁通过，无空白错误。
2. 全量 pytest 和覆盖率门槛不下降。
3. `scripts/verify.py` 与 `verify.ps1` 通过。
4. WPF build/test 通过，或准确记录缺失环境。
5. Stub Word/PPT、模板、图片、NGA 模拟和失败报告路径通过。
6. README、架构、Git 和迁移文档与代码一致。
7. ignored 缓存不进入 Git，迁移 ZIP 和 wheelhouse 不误删。

## 暂不处理

- 不修改 DeckIR/WordIR/DocumentIR 契约或迁移行为。
- 不把 HTML/PptxGenJS 接入生产。
- 不放宽 OLE、ActiveX、宏和外部关系检查。
- 不删除用途未确认的 `backup-*` 分支或 `.git` checkpoint refs。
- 不在缺少 Office 视觉基线时重写 PPT renderer 核心算法。
- 不伪造真实 NGA、真实业务语料、代码签名或人工视觉终审。
