# Frontend API

本文描述 `backend/app/web_api.py` 当前提供的同源异步 JSON API。默认服务地址为
`http://127.0.0.1:5056`，默认生成器为离线确定性的 stub。

## 页面

- `GET /static/index.html`：文档生成工作台。
- `GET /api/health`：服务、单 worker、队列和磁盘就绪状态；正常返回 200，降级返回 503。
- `GET /api/version`：应用、API、DeckIR、FailureEnvelope 和 JobState 版本。

## 分析

`POST /api/analyze`，请求为 `multipart/form-data`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `input_file` | 是 | `.md/.docx/.xlsx/.pptx` 源文件。 |

成功返回 `AnalysisRecommendation 1.0`。请求不会创建后台生成任务，也不会使用 PPT 模板。

## 创建生成任务

`POST /api/generate`，请求为 `multipart/form-data`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `input_file` | 是 | `.md/.docx/.xlsx/.pptx` 源文件。 |
| `type` | 是 | `word` 或 `deck`。 |
| `depth` | 否 | Deck 可用：`概览/标准/详细`。 |
| `template_file` | 否 | 仅 Deck 可用的 `.pptx` 模板，最大 50 MB。 |
| `asset_files` | 否 | 仅 Deck 可用；可重复提交 PNG/JPEG/WebP，单图最大 20 MB，最多 20 张、合计 100 MB。 |

成功立即返回 HTTP 202 和 `job_id`。模板会先通过资源、外部关系、宏/ActiveX/OLE 和
OOXML 包完整性检查；失败返回 `E001` 或 `E003`，不会进入渲染器。

客户端应为一次逻辑提交设置 `Idempotency-Key` 请求头，格式为 8-128 位字母、数字、点、
下划线、冒号或连字符。网络重试复用同一键会返回原任务，不会重复生成。

模板在创建 job 前被同步拒绝时，`error` 还会包含 `loc`、`retryable=false` 和可执行的
`suggestion`。OLE/嵌入 Excel 或 Visio 会定位到引用它的幻灯片；处理方式是在 PowerPoint
中删除嵌入对象，或将其转成 PNG 后作为普通图片重新插入。系统不会执行、复制或静默删除
OLE，也不会把这种错误提示为“稍后重试”。

## 查询状态

`GET /api/status/<job_id>` 返回：

```json
{
  "job_id": "job-...",
  "type": "deck",
  "depth": "标准",
  "status": "running",
  "progress": {"stage": "planning_template", "percent": 66}
}
```

阶段依次为 `queued`、`parsing`；图片任务包含 `normalizing_assets`，Deck 任务包含
`planning_visuals`，随后为 `generating`。模板模式额外包含
`profiling_template`、`planning_template`，随后为 `rendering`、
`validating_package`、`linting`、`done`。终态为 `done/failed/canceled`；超时阶段为
`timed_out`，服务重启恢复到未完成任务时为 `interrupted`。错误统一符合
`FailureEnvelope 1.0`：

```json
{
  "error": {
    "failure_envelope_version": "1.0",
    "code": "E001",
    "stage": "generating",
    "retryable": true,
    "message": "内容生成服务未完成响应。",
    "suggestion": "请稍后重试；若持续失败，请下载失败报告并提供支持编号。",
    "support_id": "SUP-..."
  }
}
```

失败响应不包含异常堆栈、原始 Prompt、输入文件正文或密钥。失败任务会额外返回
`assets.failure-report`，其内容同样只包含安全诊断字段。

`POST /api/jobs/<job_id>/cancel` 可取消排队或运行中的任务；成功返回 `status=canceled` 和
`E009`。服务使用单个生成 worker，最多保留 4 个等待任务；队列满或请求限流返回 HTTP 429
和可重试 `E008`。任务总时限默认为 900 秒。

完成的模板任务还返回：

- `template`：模板模式、原型替换页数、安全重绘页数和 W201/W202 数量。
- `assets.profile`：`template_profile.json`。
- `assets.plan`：`template_plan.json`。
- `assets.structure`：`template_structure.json`，用于人工检查模板页面骨架。
- `assets.replacement-audit`：`template_replacement_audit.json`，仅保存形状 ID、替换状态、哈希和检查结果，不包含输入正文或 Prompt。
- `assets.package-report`：`pptx_package_report.json`。
- `assets.lint`：`report.json`。

Deck 任务还会返回：

- `assets.asset-manifest`：规范化图片资产清单；仅有图片时出现。
- `assets.asset-usage-audit`：最终页码、适配、裁切和有效 DPI；仅实际使用图片时出现。
- `assets.visual-plan`：根据文档、表格和图片资产形成的确定性视觉候选。
- `assets.visual-selection-audit`：DeckIR 最终采用或拒绝各候选的原因。

## 下载

- `GET /api/download/<job_id>`：兼容入口，下载主产物。
- `GET /api/download/<job_id>/output`：下载主产物。
- `GET /api/download/<job_id>/<asset>`：下载受控审计文件；`asset` 仅允许
  `output/lint/profile/plan/structure/replacement-audit/package-report/failure-report/asset-manifest/asset-usage-audit/visual-plan/visual-selection-audit`。
  其中 `failure-report` 仅在失败任务中可下载。

任务未完成返回 409（失败/取消任务的 `failure-report` 除外）；任务、产物或审计文件不存在返回 404；不在固定 asset 白名单中的名称返回 400。接口不接受任意文件名，不能越过任务工作目录。输入上传上限为 100 MB，模板上传上限为 50 MB；图片还受单图 20 MB、40MP、20 张和总计 100 MB 限制。超限返回 HTTP 413 及对应 `E004`/`A003`。输入、模板、Prompt、模型原文和中间 IR 在任务终态后删除；最终产物、脱敏审计和 `job_state.json` 保留 24 小时。

## 运行

```powershell
.\start_workbench.ps1
```

停止服务使用 `.\stop_workbench.ps1`。正式入口固定绑定 `127.0.0.1` 并由 Waitress 提供服务。

核心 CLI、IR、renderer 和 lint 不依赖 Web 层；模板只改变确定性渲染策略，不改变 DeckIR 2.0。
