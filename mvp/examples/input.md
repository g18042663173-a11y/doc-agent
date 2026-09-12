# 企业文档生成 Agent MVP

这是一个面向企业内部的文档生成 MVP。系统将输入文件解析为统一的 DocumentIR，再由模型或 MockLLM 规划 DeckIR / WordIR，最后通过本地渲染器输出可编辑 PPTX 或 DOCX。

## 核心目标

- 默认本地 mock 模式运行
- 支持 md、docx、pptx 输入
- 输出可编辑 pptx 和 docx
- 样式由 style_profile.yaml 控制
- 后续可接入公司 GLM-4.7

## 技术路线

| 模块 | 第一版选择 |
| --- | --- |
| 工作流 | LangGraph + 顺序 fallback |
| 解析 | python-docx / python-pptx / MarkdownParser |
| 规划 | MockLLM / OpenAI-compatible |
| 渲染 | python-pptx / python-docx |

## 验收重点

- 输出文件能重新打开
- 不调用外部服务
- 没有硬编码密钥
- CLI、Streamlit 和 FastAPI 都能作为入口
