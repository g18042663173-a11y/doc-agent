# doc-agent

企业文档生成 Agent：材料 → IR → 可编辑 Word/PPT。

这是一个项目、两套交付。底层都是「解析 → IR → 可编辑 Office」，**两套流水线尚未合成一份代码**。改哪套，就进哪个目录。

```text
doc-agent/
  toolkit/    原 document-toolkit：Skill + WPF + IR 门禁
  mvp/        原 doc-agent-mvp：FastAPI + React 本地工作台
```

## toolkit/ — 工具链 / Skill / WPF

Windows 离线工具链：生成 Skill、模板模仿 Skill、WPF 工作台。IR 是唯一契约，模型原文不能直接进渲染器。

```powershell
cd toolkit
.\bootstrap_windows.ps1
.\verify.ps1
```

架构见 [`toolkit/ARCHITECTURE.md`](toolkit/ARCHITECTURE.md)。使用说明见 [`toolkit/README.md`](toolkit/README.md)。

## mvp/ — 本地 FastAPI + React 工作台

本机上传 md/docx/pptx/xlsx，配置模型档案，生成可编辑 pptx/docx。默认 `LLM_PROVIDER=stub`，不调用外部模型。

```bash
cd mvp
scripts/setup.sh
scripts/start-backend.sh
scripts/start-frontend.sh
```

使用说明见 [`mvp/README.md`](mvp/README.md)。

## 旧仓库

- [`document-toolkit`](https://github.com/g18042663173-a11y/document-toolkit) → 现 `toolkit/`
- [`doc-agent-mvp`](https://github.com/g18042663173-a11y/doc-agent-mvp) → 现 `mvp/`

日常只改本仓库。需要从旧仓补提交时用 `git subtree pull`。
