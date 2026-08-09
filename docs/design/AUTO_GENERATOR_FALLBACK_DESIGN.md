# Auto 生成器降级设计（auto generator fallback）

设计日期: 2026-08-06
状态: 待评审（尚未实现）
作者: GSQ 确认的方向 + 代码核实

## 1. 背景与动机

用户诉求：**"默认开 AI，用不了的话给出提醒并降级"**——任务默认优先使用
NGA（内网 AI），当 NGA 调用失败时，不要卡死任务，而是给出明确提醒并
自动改用 Stub 生成器完成任务。

现状：项目核心不变量 3 为"显式启用 NGA 后失败不得静默回退"（`ARCHITECTURE.md`、
`AGENTS.md`、README FAQ）。这条不变量保护的是**可复现性与诚实性**——降级
必须是**显式、可见**的，不能是静默的。

本设计在**不打破不变量**的前提下满足用户诉求：把"降级"从隐藏行为变成
**显式的 auto 模式**——降级发生时代理可见、产物可追溯、审计可解释。

## 2. 目标与非目标

### 目标

- 新增 `auto` 生成模式：激活 NGA 时，任务默认尝试 NGA；NGA 调用失败
  （超时 / 可重试错误重试耗尽 / 认证失败 / 非法响应等）自动回退 Stub，
  任务正常完成，结果与审计明确标注降级来源。
- 保留 `strict`（现状行为：NGA 失败即任务失败，绝不降级），二者可切换。
- 默认模式为 `auto`（用户确认）。
- 降级全程可追溯：任务快照、job_state、失败契约、审计文件均记录实际使用
  的生成器序列（如 `nga -> stub (auto)`）。
- Stub 不参与回退链：Stub 是确定性兜底，其失败就是真实失败（E 系错误）。
- **设置能力补全（2026-08-06 追加）**：浏览器前端新增设置面板（NGA 配置
  + 模式开关 + 测试连接），补齐与 WPF 的设置能力差距；WPF 常规设置新增
  生成模式下拉框；后端设置 API 增加 `mode` 字段。

### 非目标

- 不改变 IR 契约、Schema、渲染、lint 行为。
- 不做 NGA -> Codex 或任意 NGA 间的回退（只回退到确定性 Stub）。
- 不做"任务暂停等人工确认"（用户已确认要自动兜底，不留人工）。
- 不把降级信息写进 PPTX/DOCX 产物本体（污染交付物；只标 API 与审计）。
- 不引入 FastAPI / asyncio / 队列框架（维持 Flask + 线程模型）。
- 浏览器前端 Token 不落盘：只存后端内存 draft，刷新页面需重新输入
  （非敏感配置如地址/模型可存 settings.json）。

## 3. 术语

- `strict`：现状模式。激活 NGA 时 NGA 失败 = 任务失败（E010-E014）。
- `auto`：新增模式。激活 NGA 时 NGA 失败自动回退 Stub 完成任务，
  结果与审计标注 `generator: "nga -> stub (auto)"`。
- 模式仅在**激活生成器为 NGA**时有意义；激活 Stub 时两种模式行为相同
  （都用 Stub，无回退可言）。

## 4. 设计决策（已与用户确认）

| 决策点 | 结论 |
| --- | --- |
| auto 语义 | NGA 失败自动回退 Stub；Stub 不参与回退链 |
| 默认模式 | 默认 `auto`，`strict` 作为可选设置保留 |
| 降级可见性 | 降级必须显式标注（快照/状态/审计），不允许静默 |
| 产物标注 | 只标 API 与审计，不写进 DOCX/PPTX 本体 |
| 回退范围 | 仅 NGA -> Stub；不引入其它回退 |

## 5. 现状梳理（代码核实）

### 5.1 GeneratorManager（`backend/app/generators/manager.py`）

- `GeneratorName = Literal["stub", "nga"]`（L14）——需要扩展。
- `GeneratorSnapshot`（L18-22）：`name / revision / generator`，已冻结 dataclass。
- `configure()`（L63-96）：校验 `generator in {"stub","nga"}`（L71）。
- `activate()`（L131-151）：把 draft 提升为 active，`name=draft.name`。
- `test_draft()`（L98-129）：NGA 连接测试，与模式无关。
- `status()`（L157+）：返回 `settings_version / active / draft`，无模式字段。
- 任务侧 `snapshot()`（L153-155）直接返回 active snapshot——**任务拿到的
  generator 就是 active 的 generator 实例**。

### 5.2 web_api（`backend/app/web_api.py`）

- `ApiJob`（L86-）：`generator_name: str = "stub"`（L91）、`generator_revision`（L92）、
  `payload()`（L109）序列化 `generator: {name, revision}`（L114-117）。
- `/api/generate`（`_generate_request` L606-）：读取 `manager.snapshot()`（L650 附近），
  把 `generator_name / generator_revision / generator` 存入任务（L656-663）。
- `_execute_job`（L1072-）：`_generate_artifact(job, document, generator, jobs)` 使用
  传入的 generator 单实例完成解析->生成->渲染->lint 全链。
- `_fail_job`：失败契约 `code / stage / retryable / suggestion / support_id`。
- 任务状态持久化：`job_state.json`（`_persist_unlocked` L268），schema 见
  `backend/schemas/job_state.schema.json`：`generator_name`（pattern
  `^[a-z][a-z0-9_-]*$`，L60 附近）——**`nga -> stub` 含空格/箭头，不能直接写入**。

### 5.3 其它相关

- `backend/app/generators/interface.py`：`GeneratorTarget`、`IRTextGenerator` 协议、
  `generator_from_name()`（stub/nga/codex）。任务链路不使用
  `generator_from_name`（直接传实例）。
- `desktop/DocumentWorkbench/ApiModels.cs`：`GeneratorState`（name/revision 等）
  已反序列化 `generator` 字段；任务展示不感知"降级"概念，需小改展示。
- `backend/app/static/index.html`：任务结果区当前不展示 generator 名称，无需大改；
  如需展示降级标注，加一行即可。

## 6. 契约设计

### 6.1 生成模式

- 新增枚举：`GeneratorMode = Literal["auto", "strict"]`。
- 该模式是**进程级设置**（与激活生成器并列），不是任务级参数——
  任务不传 mode，统一使用激活时的 mode（保证任务快照可复现）。

### 6.2 任务快照与 job_state

- `job_state.generator_name` 只存 **Stub 兜底前的首个生成器名**（现有字段语义
  不变，保持 schema pattern 合法）：`"nga"` 或 `"stub"`。
- 新增 job_state 字段 `generator_fallback`（布尔，默认 false）：任务实际发生过
  回退。`generator_revision` 语义不变（激活时 NGA 的 revision）。
- 状态 payload 增加 `generator.mode`（"auto"|"strict"）与
  `generator.fallback`（bool）——既有前端/WPF 字段保持向后兼容。

### 6.3 降级标注（成功任务的 audit/manifest）

- `_generate_artifact` 产出的 `manifest`（`manifest.json`）与审计文件新增：
  - `generator.requested`：`{"name": "nga", "revision": N}`
  - `generator.used`：`{"name": "stub", "revision": 0}`
  - `generator.fallback`：`true`
  - `generator.fallback_reason`：稳定错误码（如 `E013` timeout / `E011` 认证 /
    重试耗尽原错误码），不加原始异常文本。
- 降级成功时任务 `status="done"`，但 manifest 明确标注，前端/WPF 可据此
  显示"AI 不可用，已自动使用确定性生成器完成"。

### 6.4 降级失败（Stub 也失败）

- 保持任务失败，错误码为 Stub 侧的 E 系错误；`suggestion` 中说明
  "AI 不可用且确定性生成也失败"。

### 6.5 错误码

- 复用现有 E010-E014（NGA 配置/凭据/请求失败），不新增错误码——
  降级不是新错误，是成功路径上的一次可见回退。
- `fallback_reason` 使用被吞掉的 NGA 错误码，保证可诊断。

## 7. 实现方案

### 7.1 `backend/app/generators/manager.py`

1. `GeneratorMode = Literal["auto", "strict"]`（新常量）。
2. `GeneratorManager.__init__` 增加 `mode: GeneratorMode = "auto"`（默认 auto，
   用户已确认）；`_active_mode` 保存。
3. `configure()/activate()` 增加可选 `mode` 参数（默认不改动现有 mode）；
   `status()` 返回 `mode`。
4. `activate()` 的 snapshot 携带 mode：`GeneratorSnapshot` 增加 `mode` 字段
   （frozen dataclass，加字段向后兼容，调用方按 kwargs 或默认值处理）。
5. 不改变 `GeneratorName` 的取值（仍是 stub/nga）；mode 是另一维度。
   `configure(generator=...)` 仍只接受 stub/nga。

### 7.2 `backend/app/generators/interface.py`

- 新增（可选）`FallbackGenerator` 包装器，或由 web_api 实现编排逻辑。
  建议：**编排放 web_api**（避免生成器包引入任务概念），manager 只提供
  `snapshot().mode`。

### 7.3 `backend/app/web_api.py`

1. `ApiJob` 增加 `generator_mode: str = "auto"`、`generator_fallback: bool = False`；
   `payload()` 输出 `generator: {name, revision, mode, fallback}`。
2. `_generate_request`：从 `manager.snapshot()` 读 mode 存入任务。
3. `_generate_artifact` 外层包装降级逻辑（**推荐**，覆盖单页与深度两条路径）：
   - 捕获 `NgaGeneratorError`（含超时/认证/非法响应等，即 `retryable` 与否
     都要捕获——只有 NGA 的"不可用"才触发回退）；
   - 若 `job.generator_mode == "auto"` 且 `job.generator_name == "nga"`：
     记录 `fallback_reason`（原错误码），改用 `StubGenerator()` 重跑
     生成阶段（解析/渲染/lint 不变，只换 generator）；
     设置 `generator_fallback=True`，manifest 写入
     `generator: {requested: nga, used: stub, fallback: true, reason}`；
     任务照常完成（`status=done`）。
   - 若 `mode == "strict"`：维持现状（失败即失败）。
4. 状态持久化：`_persist_unlocked` 写入 `generator_fallback` 字段；
   `job_state.schema.json` 增加该字段（见 7.5）。
5. `_fail_job` 与失败报告不暴露 NGA 原始异常/堆栈（现状已保证，不破坏）。

### 7.4 前端 / WPF（最小改动）

- `backend/app/static/index.html`：
  - 任务结果区在 `generator.fallback == true` 时显示一行提示
    "AI 生成器不可用（E0xx），已自动使用确定性生成器完成"。
  - **新增设置面板（补齐浏览器缺口）**：NGA 地址/接口路径/模型/Token/超时/
    重试 + 生成模式开关（auto/strict）+ 测试连接按钮 + 保存按钮；
    调用既有 `/api/settings/generator`（GET/PUT/POST test/activate）。
    Token 只存后端内存 draft，不落盘；刷新页面需重新输入 Token，
    非敏感配置（地址/模型/超时/重试/模式）可存 settings.json。
- `desktop/DocumentWorkbench/ApiModels.cs`：`GeneratorState` 增加
  `Mode`、`Fallback` 属性（反序列化自动兼容）；任务详情若展示 generator，
  同样显示降级提示。
- `desktop/DocumentWorkbench/MainWindow.xaml(.cs)`：常规设置页新增
  "生成模式"下拉框（自动降级 / 严格模式），`WorkbenchSettings` 增加
  `GeneratorMode` 属性（默认 "auto"），随 NGA 配置一起提交到后端。
- 后端设置 API 增加 `mode` 字段读写（`_update_generator_settings`）。

### 7.5 Schema 快照

- `backend/schemas/job_state.schema.json`：
  - `generator_name` 保持 pattern 不变（仍存 "nga"/"stub"）。
  - 新增 `generator_fallback`（boolean，default false）。
- 按仓库规则：改 schema 必须先更新快照 + 快照测试（`test_c0_contract.py` 等）。

## 8. 测试计划（先写红灯，再实现）

### 8.1 单元（backend/tests/test_generator_settings_api.py 扩展）

1. `test_auto_mode_is_default`：manager 默认 mode 为 auto。
2. `test_strict_mode_can_be_selected`：configure/activate 可设 strict。
3. `test_snapshot_carries_mode`：snapshot().mode 正确。
4. `test_status_reports_mode`：status() 含 mode。

### 8.2 集成（web_api，新增 test_auto_fallback.py 或扩展现有）

5. `test_auto_fallback_nga_failure_completes_with_stub`：mock NGA 必败，
   mode=auto，任务 done，manifest 标注 fallback，job_state 落盘
   `generator_fallback=true`。
6. `test_auto_fallback_records_requested_and_used`：manifest
   `generator.requested=nga`、`generator.used=stub`、`fallback_reason` 为
   稳定错误码。
7. `test_strict_mode_nga_failure_fails_job`：mode=strict，NGA 必败，
   任务 failed，无 fallback。
8. `test_auto_fallback_stub_success_has_no_fallback_marker`：激活 Stub +
   auto，无 fallback 标记（Stub 不参与回退链）。
9. `test_auto_fallback_when_stub_also_fails_job_fails`：NGA 败 + Stub 败
   （构造 Stub 失败场景，如不可写输出），任务 failed，suggestion 说明。
10. `test_auto_fallback_not_silent_in_payload`：任务 payload/status 含
    `mode` 与 `fallback` 字段。
11. `test_job_state_schema_accepts_fallback_field`：schema 快照与落盘兼容。
12. `test_settings_api_reads_and_writes_mode`：`GET/PUT /api/settings/generator`
    支持 `mode` 字段读写。
13. `test_workbench_settings_persists_mode`：WPF `WorkbenchSettings` 保存
    `GeneratorMode`（默认 "auto"）并随 NGA 配置提交。
14. `test_browser_settings_panel_renders`（可选）：浏览器设置面板存在
    NGA 字段 + 模式开关 + 测试连接按钮。

### 8.3 回归

- 全量 pytest、`scripts/verify.py`、ruff、`git diff --check`、
  `verify.ps1`（C0 门禁）全绿；job_state schema 快照更新后
  既有 `test_c0_contract` 同步更新。

## 9. 文档更新

- `README.md`：FAQ 中"显式 NGA 失败不会回退 Stub"改为
  "strict 模式不会回退；auto 模式会显式回退 Stub 并标注"。
- `ARCHITECTURE.md` 核心不变量 3：补充 auto 显式降级说明。
- `docs/使用说明.md`：设置区模式开关说明。
- `docs/FRONTEND_API.md`：浏览器设置面板的 API 用法。
- `PROGRESS.md`：追加本轮记录。

## 10. 风险与边界

- **不变量保护**：降级仅发生在 `mode=auto` 且任务快照明确记录；strict 行为
  与现状完全一致，不破坏既有契约。
- **可复现性**：job_state + manifest 记录 requested/used/reason，任何产物可
  追溯实际生成器。
- **回退范围**：仅 NGA->Stub；不引入 NGA->Codex 等新链路，避免组合爆炸。
- **产物纯净**：PPTX/DOCX 本体不写降级标注（避免污染交付物），只标
  API/审计/前端提示。
- **向后兼容**：job_state 新增字段 default=false；既有任务（无字段）按
  false 处理；WPF/前端对新增字段天然兼容。

## 11. 验证与回滚

- 验收：8.1/8.2 全部通过 + 全量回归 + verify 门禁 + 手动跑一遍
  auto 成功（mock NGA 必败 -> Stub 完成 -> 界面显示降级提示）。
- 回滚：单文件回滚（manager/web_api/schema 各独立小批次），
  job_state 新字段 default=false 无需迁移，回滚安全。

## 12. NGA CLI 传输接入（2026-08-06 追加）

### 背景

目标环境的 NGA 不是 HTTP 服务，而是**本机命令行工具**：`nga run "prompt" -m <model> --format json`，
输出 NDJSON 事件流。认证由 CLI 自管（`nga providers login`，OAuth + DPAPI，
自动刷新），项目代码完全不需要 Token。

### 实现

- `backend/app/generators/nga.py` 新增 `NgaCliConfig`（transport=cli）与 CLI 传输：
  - `NgaGenerator.transport`（http/cli）按配置类型分派；
  - `_send_cli`：subprocess 调用 `nga run --model <model> --format json <prompt>`；
  - `_extract_ndjson_text`：解析 NDJSON 事件流，拼接所有 `type=="text"` 的
    `part.text`（step_start / text / tool_use / step_finish 四类事件）；
  - cli 模式**免 Token**（认证归 CLI），http 模式保持原 Token 要求；
  - 错误映射：CLI 未找到→E010、超时→E012（可重试）、非零退出→E013（可重试）、
    空/非法输出→E014；
  - 环境变量：`NGA_TRANSPORT=cli`、`NGA_CLI_PATH`、`NGA_MODEL`。
- `web_api._nga_config_from_payload`：按 `transport` 字段分派配置模型，
  并过滤 CLI 字段（兼容 WPF/浏览器全量字段）。
- `GeneratorManager`：cli 配置无需 credential 即可 test/activate。
- WPF：NGA 面板新增"调用方式"下拉（HTTP/CLI），CLI 时隐藏 HTTP 专属字段
  并显示 CLI 路径；`NgaStoredConfig` 新增 `Transport`/`CliPath`。
- 浏览器设置面板：新增"调用方式"切换 + CLI 路径字段。

### 验证

- 单元：`test_nga_generator.py` 新增 10 个 CLI 用例（NDJSON 拼接、命令参数、
  免 Token、重试、E010/E012/E013/E014 映射、环境变量配置）；
  `test_generator_settings_api.py` 新增 CLI 配置保存/测试/激活端到端。
- 集成：fake NGA CLI（模拟 4 类 NDJSON 事件）走通
  配置→测试→启用→生成 word.docx 全链路；CLI 失败时 auto 降级回退 Stub
  并标记 `fallback: true`。
- 全量回归：633 passed, 1 skipped（6 个环境限制 deselected 与本次无关）。
