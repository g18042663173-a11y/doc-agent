# 内网 AI 调用适配 — 信息收集清单

> 用途:进入内网后,把本清单交给内网 AI 平台/网关负责人填写,拿回信息即可完成适配。
> 代码已把"产 IR 的通道"与"确定性流水线"彻底解耦(任务书 I3 不变量):**适配只发生在
> generator 层,不改 IR、renderer、lint 任何代码**。

## 一、代码已支持的接入形态(内网二选一即可)

| 通道 | 协议假设 | 配置入口 | 失败行为 |
| --- | --- | --- | --- |
| **NGA HTTP**(推荐内网) | OpenAI-compatible Chat Completions | 设置 > NGA > 调用方式=HTTP | auto 回退 Stub / strict 失败 E010-E014 |
| **NGA CLI** | 本机 `nga run` 命令 | 设置 > NGA > 调用方式=本机命令行 | 同上 |
| **codex / opencode-go**(开发冒烟) | responses 或 chat_completions | 环境变量 `OPENAI_*` | 失败即失败(E001) |

三者共用同一份下游流水线;协议不兼容时只需**新增一个 adapter**,下游零改动。

## 二、需要内网提供的信息(逐项填写)

| # | 信息 | 示例 | 为什么需要 / 拿到后怎么用 |
| --- | --- | --- | --- |
| 1 | **服务 Base URL** | `https://nga.example.com/v1` | 填到 NGA 设置/环境变量 |
| 2 | **接口路径** | `/chat/completions` 或 `/responses` | 当前实现两者都支持;确认真实路径 |
| 3 | **认证方式** | `Authorization: Bearer <token>` | 当前假设 Bearer;若为 `x-api-key` 等需小改 adapter |
| 4 | **Token / 密钥获取方式** | 申请流程、有效期 | Token 只存 Windows Credential Manager,不落盘不提交 |
| 5 | **模型名(精确 ID 列表)** | `deepseek-v4-flash` | 模型名大小写敏感;代码默认 `deepseek-v4-flash`(opencode-go 实测) |
| 6 | **JSON 输出约束支持** | `response_format={"type":"json_object"}` | 当前依赖它保证 IR 合法率;不支持则走"剥壳+repair 回路"降级 |
| 7 | **推理参数支持** | `temperature`、`reasoning_effort`、`max_tokens` | 确认哪些参数被接受/忽略 |
| 8 | **流式输出** | 是否仅支持 SSE 流式 | 当前实现**非流式**;若仅流式需小幅适配(读取 SSE 事件) |
| 9 | **TLS / CA 证书** | 自签 CA 的 `.crt` 文件 | 内网网关常用自签证书;证书文件路径需配置 |
| 10 | **超时与重试建议** | 单请求超时上限、限流阈值 | 当前默认 300s 超时、10MB 响应上限 |
| 11 | **并发限制** | QPS / 并发数 | 工作台 2 worker + 4 等待位;超限需调参 |
| 12 | **请求/响应样例(脱敏)** | 一个真实 curl 请求 + 响应 JSON | 用于离线验证 adapter 解析,不依赖内网在线调试 |
| 13 | **错误码约定** | 429 限流、5xx 重试语义、鉴权失败码 | 决定 retryable 与错误文案映射 |

## 三、拿到信息后的适配步骤(工作量参考)

1. **若完全 OpenAI-compatible**:仅配置,零代码,10 分钟完成。
2. **若认证/路径有差异**:改 `backend/app/generators/nga.py` 的请求构造(约半天,
   含回归测试),不动其它模块。
3. **若协议完全不同**(如私有 RPC):新增 `backend/app/generators/<name>.py`
   实现统一 `IRTextGenerator` 接口(约 1-2 天,含测试),注册到
   `generators/interface.py`。
4. 每步都跑:连接测试按钮 → 最小 WordIR 冒烟 → 最小 DeckIR 冒烟 → 全量回归
   (`verify.ps1`)。

## 四、当前默认假设(适配时对照,逐条确认)

- [ ] OpenAI-compatible Chat Completions(`choices[0].message.content`)或
      opencode-go responses(`output_text`)
- [ ] Bearer Token 认证
- [ ] 非流式请求
- [ ] 支持 `response_format=json_object`(或可容忍剥壳修复)
- [ ] 单响应 ≤ 10MB
- [ ] HTTP 状态码语义:401/403 鉴权失败、429 限流、5xx 服务端错误
- [ ] 无需自定义 CA(或提供证书)

## 五、验证基线(适配完成后应达到)

- 连接测试通过(设置页按钮)
- 真实 WordIR 生成:lint 0 Error
- 真实 DeckIR 生成:lint 0 Error
- `verify.ps1` 全绿(离线 stub 链路不受内网影响)
- 失败场景:错误 token / 断网 / 超时 → 稳定错误码,无堆栈泄露
