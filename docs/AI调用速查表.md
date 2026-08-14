# AI 调用接入 · 一页速查表(OpenAI 兼容网关)

> 详细原理与代码见 `docs/AI调用经验手册.md`。本节只留"必须记住"的结论。
> 场景:应用直连 OpenAI 兼容网关调用 DeepSeek v4-flash 等推理模型。

## 三大高危坑(先看这个)

| 坑 | 现象 | 结论 |
| --- | --- | --- |
| ① 模型 ID | `ModelError: ... is not supported` | 显示名 ≠ API ID,从网关 `/models` 拉精确 ID(如 `deepseek-v4-flash`),做成可配置 |
| ② UA 风控 | 手工通、代码 403 + error code 1010 | Python 默认 UA 被 Cloudflare 拦截;HTTP 客户端必须带浏览器 UA |
| ③ 推理截断 | 200 但正文为空,偶发失败,长 prompt 必现 | 推理模型的 `reasoning` 会耗尽 `max_output_tokens`;预算 ≥8192,检测截断后**翻倍预算重试 1 次** |

## 截断信号(两种协议都要检测)

| 协议 | 信号 |
| --- | --- |
| responses | `incomplete_details.reason == "max_output_tokens"` 或 `status == "incomplete"` |
| chat/completions | `choices[0].finish_reason == "length"` |

- 提取失败 + 截断 → 重试;提取成功但响应标记截断(残缺 JSON)→ **也要重试**。

## 重试策略

| 情况 | 处理 |
| --- | --- |
| HTTP 429/500/502/503/504 | 重试 ≤2 次,退避 1.5s×次数 |
| 网络超时/连接失败 | 同上 |
| **401/403/400** | **绝不重试**,立即报错 |

## 密钥与隐私红线

- 密钥只进环境变量 / 系统凭据管理器;不进代码、不进 git、不落日志。
- 状态接口只回 `credential_configured` 布尔,**永不回传密钥**。
- 失败消息脱敏:不含 prompt、密钥、正文、堆栈;给错误码 + 建议。
- 请求带 `store: false`。

## 错误处理

- 适配器异常**单独错误码**(如 E010=AI 通道调用失败)+ `retryable` + 具体原因,不要吞进通用错误。
- 配置三阶段:保存 → **测试连接**(最小请求 `{"ok":true}` + 60s 超时护栏)→ 启用。
- UI 至少展示:当前通道 / 模型 / Base URL / 密钥状态(已配置|未配置)。

## 接入新通道 6 步

1. `/models` 拿精确模型 ID → 2. 手工(浏览器 UA)验证鉴权与协议 → 3. 写适配器(构造+提取+截断重试+临时错误重试+脱敏)→ 4. 配置三阶段 → 5. 测试矩阵(成功/401/429/5xx/超时/截断/坏响应/超大响应)→ 6. 真实任务 + lint 验证。

## 配置基线(一行记住)

```
max_output_tokens=8192 · 截断重试1次(×2) · 429/5xx重试2次(1.5s退避) · 请求超时300s · store=false · 响应上限10MB
```

---

*速查不够用时:完整手册 `docs/AI调用经验手册.md`;参考实现 `backend/app/generators/codex.py`;参考测试 `backend/tests/test_codex_generator.py`。*
