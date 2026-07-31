# Architecture

## 项目目标

将多格式业务资料转换为可校验、可编辑、可复现的 DOCX/PPTX，并在离线 Windows 环境提供 CLI、浏览器兼容入口和原生 WPF 工作台。

## 核心不变量

1. IR 是唯一契约，模型原文不能直接进入 renderer。
2. 所有目标 IR 必须经过剥壳、版本迁移和 Schema 校验。
3. Stub 链路必须断网可运行；显式启用 NGA 后失败不得静默回退。
4. 生产 PPT 引擎是 python-pptx；HTML 引擎只在 `experiments/`。
5. 模板、图片和 Office 包先做资源与安全预检，再进入业务层。
6. 失败结果只暴露稳定错误码、stage、retryable、suggestion 和脱敏 support_id。

## 模块职责

| 模块 | 负责 | 不负责 |
| --- | --- | --- |
| `parsers` | 源文件到 DocumentIR、格式降级 warning | 目标文档设计与渲染 |
| `ir` | 契约、迁移、剥壳、校验和错误定位 | 文件系统、HTTP、Office 绘制 |
| `prompting` | 确定性 Prompt 组装 | 信任模型输出 |
| `generators` | Stub/NGA/Codex 协议适配与配置快照 | 渲染、lint、模板处理 |
| `generation` | 内容分析、深度/页数策略、生成编排 | HTTP 与桌面 UI |
| `assets` | 图片规范化、Manifest、哈希与审计 | 业务图片搜索或联网生图 |
| `template` | Profile/Plan、关系安全、模板渲染与审计 | 放宽 OLE/ActiveX 安全边界 |
| `rendering` | Word/PPT 原生可编辑对象 | 接收非法 IR |
| `lint` | 自动合规与几何检查 | 代替人工审美签字 |
| `security` | 通用 Office 包预检 | parser 专用错误文案 |
| `reliability` | 稳定失败和任务状态契约 | 业务生成逻辑 |
| `web_api` | HTTP 装配、上传、任务队列与受控下载 | 直接实现 IR/renderer 规则 |
| `desktop` | Windows 交互、本地后端生命周期、凭据 | 重复后端业务逻辑 |

## 依赖方向

```text
CLI / Web API / WPF
        |
        v
parsers -> DocumentIR -> generation/prompting -> generators
                                      |
                                      v
                               IR validation gate
                                      |
                    +-----------------+-----------------+
                    v                                   v
             Word renderer                         Deck renderer
                    |                        assets/template/security
                    +-----------------+-----------------+
                                      v
                                  lint/audit
```

允许基础设施层依赖契约模型；禁止 `ir` 反向依赖 Flask、WPF、renderer 或网络 adapter。`desktop` 只通过 HTTP 使用后端。

## 运行流程

1. 入口保存并预检输入文件。
2. parser 生成 DocumentIR。
3. generation 构建分析/视觉计划与 Prompt。
4. generator 返回不可信文本。
5. shell/validation 剥壳、迁移、Schema 校验，必要时有限修复。
6. renderer 只接收模型化 IR。
7. lint 和 OOXML 包检查生成审计结果。
8. API 清理敏感中间文件，只保留产物和脱敏审计。

## 配置流

- 固定设计 token: `backend/app/rendering/themes/hw_theme.json`。
- NGA 非敏感配置: `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json`。
- NGA Token: Windows Credential Manager。
- 开发环境: `.venv`、`PYTHONPATH=backend`、UTF-8。
- 运行时覆盖: 明确环境变量或 WPF 设置，优先级由 generator manager 固定为任务快照。

## 目标目录

当前目录已经接近目标结构，不做破坏性 `src/` 大迁移:

```text
backend/app/{assets,cli,generation,generators,ir,lint,parsers,prompting,
             reliability,rendering,security,template,visual}
backend/tests/
backend/schemas/
desktop/DocumentWorkbench/
desktop/DocumentWorkbench.Tests/
docs/
experiments/html2pptx/
samples/
scripts/
```

新的正式 Python 模块放在 `backend/app/<domain>/`；开发/发布入口放 `scripts/`；非生产试验必须放 `experiments/` 并有独立依赖锁。

## 扩展规则

- 新 IR 字段: 先更新 Pydantic 契约、版本、正反样例、Schema 快照和迁移器，再改消费者。
- 新 generator: 实现统一接口，由 `GeneratorManager` 管理配置与任务快照。
- 新图片来源: 实现 AssetRecord 规范化，不绕过 Manifest 和安全扫描。
- 新模板能力: 扩展 Profile/Plan 和 replacement audit，不复制不安全关系。
- 新 UI: 调用既有 API，不复制生成逻辑。

## 禁止依赖

- renderer -> Flask/WPF/generator
- IR -> 文件上传、HTTP 或用户凭据
- 正式代码 -> `experiments/html2pptx`
- API/desktop -> 未校验模型文本直接渲染
- 日志/失败报告 -> Token、Prompt、模型原文或输入正文
