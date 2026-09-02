# doc-agent-mvp

企业文档生成 Agent MVP：把 `md/docx/pptx/xlsx/xlsm` 输入解析为 `DocumentIR`，再生成结构化 `DeckIR` / `WordIR`，最后渲染为可编辑 `pptx/docx`。

当前产品形态是个人本地 PPT/文档生成工作台：配置模型档案，上传文件，选择模板/配色，查看进度，下载结果，并在本地历史中复用或删除生成记录。

默认情况下，本项目使用 `LLM_PROVIDER=stub` 和 `PPT_RENDERER=stub`，不会调用任何外部模型、NGA 或华为内部渲染 Skill。需要看“主 Agent 调模型 API”的效果时，可以切到 `LLM_PROVIDER=local_relay`，让主生成链路调用本地 HTTP 中转站。

## 核心原则

- 模型只生成结构化 JSON。
- PPT 主契约是 `DeckIR v1.1`：保留基础版式，同时支持 cards/chart/image、source_refs、intent、importance、footer/confidentiality 等扩展字段。
- PPTX/DOCX 的字体、颜色、坐标和样式由本地代码、模板和 `doc_agent/styles/style_profile.yaml` 控制。
- 本地开发只使用非保密样例文件和虚拟模板。
- 公司内网部署时，只替换两个插座：`NGAClient` 负责 GLM-4.7，`HuaweiSkillRenderer` 负责华为 PPT 渲染 Skill。
- 模板导入用于提取页面尺寸、字体和主题色做风格套用，不承诺完整复刻 PowerPoint 母版、动画或复杂占位符。
- 图表、SmartArt 和 AICoding 桥接保留为辅助/实验入口，默认主线是工作台、智能生成、模板、配色和模型档案。

## 本地运行

```bash
scripts/setup.sh
scripts/start-backend.sh
scripts/start-frontend.sh
```

确认 `.env` 中保持：

```env
LLM_PROVIDER=stub
PPT_RENDERER=stub
PPT_COMPLIANCE_GATE=warn
```

`mock` 和 `python_pptx` 仍作为兼容别名可用。

如果要让主 Agent 通过本地 API 中转站跑通模型调用链路，先启动中转站：

```bash
.venv/bin/python scripts/local_llm_relay.py
```

然后把 `.env` 中模型配置改成：

```env
LLM_PROVIDER=local_relay
LLM_BASE_URL=http://127.0.0.1:8765/v1
LLM_API_KEY=EMPTY
LLM_MODEL=glm-4.7
```

这个中转站默认仍用本地 stub 逻辑返回结构化 JSON，但调用路径已经变成“主 Agent -> HTTP relay -> JSON -> 渲染”。以后把 `scripts/local_llm_relay.py` 里的 stub 调用替换成真实模型请求即可。

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

Windows 11 内网使用优先走免安装运行包，不建议在内网机器跑 `npm install` 或在线 `pip install`：

```powershell
# 在一台同架构的外网 Windows 11 构建机执行
powershell -ExecutionPolicy Bypass -File scripts/export-windows-runtime.ps1

# 内网 Windows 11 机器解压 release/doc-agent-win11-runtime-*.zip 后
Start-DocAgent.cmd
```

打开 `http://127.0.0.1:8000/`。这个包内置嵌入式 Python、最小运行依赖和已构建前端，目标机器不需要 Node.js/npm，也不需要执行 pip 安装。

Docker:

```bash
docker compose up --build
```

打开 `http://127.0.0.1:3000/`。

## 迁移到其他电脑

有四种迁移包：

- `scripts/export-windows-runtime.ps1`：Windows 11 免安装运行包，内置 Python 和运行依赖，内网机器只解压启动。
- `scripts/export-portable.sh`：源码包，最小，但目标机器要安装 Python/npm 依赖。
- `scripts/export-runtime-bundle.sh`：通用运行包，包含最小 `wheelhouse/` 和前端 `dist/`，目标机器不需要 npm，但仍会执行离线 pip 安装。
- `scripts/export-docker-images.sh`：Docker 镜像包，目标机器 `docker load` 后直接运行，最快也最少折腾。

创建干净源码包：

```bash
scripts/export-portable.sh
```

创建内网快速运行包：

```bash
scripts/export-runtime-bundle.sh
```

Windows 11 推荐创建免安装运行包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export-windows-runtime.ps1
```

目标机器解压后：

```bash
scripts/setup-runtime.sh
scripts/start-backend.sh
```

然后打开 `http://127.0.0.1:8000/`，后端会直接托管已构建前端。

默认不会打包 `.venv/`、`node_modules/`、`.env`、`data/`、`outputs/`、测试报告或构建缓存。迁移已有模型档案/模板/配色数据时使用：

```bash
INCLUDE_DATA=1 scripts/export-portable.sh
```

复制已有模型档案数据时必须一起复制 `data/users/.encryption_key`，否则旧的 token 无法解密。完整说明见 `MIGRATION.md`。

## CLI

```bash
python -m doc_agent parse examples/input.md --out outputs/document_ir.json
python -m doc_agent plan outputs/document_ir.json --target pptx --out outputs/deck_ir.json --slides 8
python -m doc_agent render examples/sample_deck_ir.json --target pptx --out outputs/demo.pptx
python -m doc_agent generate examples/input.md --target pptx --out outputs/demo.pptx --slides 8
python -m doc_agent generate examples/input.md --target docx --out outputs/demo.docx
python -m doc_agent review-pptx outputs/demo.pptx --json
python -m doc_agent export-images outputs/demo.pptx --out-dir outputs/demo-pages
```

## Streamlit

```bash
streamlit run app/streamlit_app.py
```

页面支持上传 `md/docx/pptx/xlsx/xlsm`，选择输出类型和 PPT 页数，然后下载生成文件。

## React 前端

```bash
cd ppt-agent-frontend
npm install
npm run dev
```

默认前端地址：

```text
http://127.0.0.1:3000/
```

默认后端 API 地址：

```text
http://127.0.0.1:8000/api
```

如需修改，复制 `ppt-agent-frontend/.env.example` 并设置 `VITE_API_BASE_URL`。

## 项目文档

- `docs/API.md`：接口说明和请求示例。
- `docs/ARCHITECTURE.md`：后端、前端和数据目录结构。
- `docs/DEPLOYMENT.md`：本地、内网和生产化部署注意事项。
- `docs/USER_GUIDE.md`：前端功能使用说明。
- `docs/DEVELOPMENT.md`：开发、测试和扩展约定。
- `docs/内网接入指南.md`：进入内网后接 NGA 和华为 Skill 的操作手册。
- `MIGRATION.md`：跨电脑迁移、打包、Docker 和离线依赖说明。

## FastAPI

```bash
uvicorn app.api:app --reload --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

生成接口：

```bash
curl -F "file=@examples/input.md" -F "target=pptx" -F "slides=8" http://127.0.0.1:8000/generate
```

扩展 API：

```text
POST   /api/users/create
GET    /api/users/list
GET    /api/users/{user_id}
PUT    /api/users/{user_id}
DELETE /api/users/{user_id}
POST   /api/users/switch/{user_id}
POST   /api/profiles/create
GET    /api/profiles/list
GET    /api/profiles/{profile_id}
PUT    /api/profiles/{profile_id}
DELETE /api/profiles/{profile_id}
POST   /api/profiles/switch/{profile_id}

GET    /api/templates/list
GET    /api/templates/{template_id}
POST   /api/templates/import

GET    /api/colors/list
GET    /api/colors/recommend?scenario=商务报告
GET    /api/colors/{scheme_id}
POST   /api/colors/create

POST   /api/charts/recommend
POST   /api/charts/generate

GET    /api/smartart/types
POST   /api/smartart/generate

POST   /api/aicoding/prompt
POST   /api/aicoding/render

GET    /api/system/health
GET    /api/system/metrics
GET    /api/config/export
POST   /api/config/import
```

AICoding 手动桥接用于黑终端阶段：先上传 `md/docx/pptx/xlsx/xlsm` 生成 prompt，复制到 AICoding 后把返回 JSON 粘贴到 `/api/aicoding/render`，由本项目校验并渲染 `docx/pptx`。Excel 解析当前提取 sheet、预览行、公式数量、合并单元格数量和数值列统计，不承诺图表、透视表、VBA 或复杂公式语义理解。

异步生成接口：

```bash
curl -F "file=@examples/input.md" \
  -F "target=pptx" \
  -F "slides=8" \
  -F "template_id=business_report" \
  -F "color_scheme_id=business_blue" \
  http://127.0.0.1:8000/api/generate/start

curl http://127.0.0.1:8000/api/generate/progress/{task_id}
curl -L http://127.0.0.1:8000/api/generate/download/{task_id} -o generated.pptx
```

生成历史接口：

```text
GET    /api/generate/history
GET    /api/generate/history/{task_id}
DELETE /api/generate/history/{task_id}?delete_files=false
```

历史记录保存在 `data/tasks/`，包含原文件名、输入/输出类型、模板、配色、模型配置档案、状态、时间、结果路径、合规检查报告和结构化错误信息。

实时进度 WebSocket：

```text
ws://127.0.0.1:8000/api/generate/ws/{task_id}
```

扩展模块的数据默认保存在 `data/`，包括模型配置档案、模板元数据、颜色方案、上传文件和任务历史。模型档案的 `auth_token` 会加密写入本地文件，列表和详情 API 默认只返回掩码。后端会输出结构化 JSON 日志到 `data/logs/app.log`，并通过 `/api/system/metrics` 暴露请求计数、耗时、任务状态和存储目录快照。

## 外网/内网插座

外网默认：

```env
LLM_PROVIDER=stub
PPT_RENDERER=stub
PPT_COMPLIANCE_GATE=warn
```

外网本地中转站模式：

```env
LLM_PROVIDER=local_relay
LLM_BASE_URL=http://127.0.0.1:8765/v1
LLM_API_KEY=EMPTY
LLM_MODEL=glm-4.7
PPT_RENDERER=stub
PPT_COMPLIANCE_GATE=warn
```

内网接入 NGA 和华为 Skill 后再切换：

```env
LLM_PROVIDER=nga
LLM_BASE_URL=http://NGA服务地址
LLM_API_KEY=内网凭据
LLM_MODEL=glm-4.7
PPT_RENDERER=hw_skill
PPT_COMPLIANCE_GATE=error
DATA_DIR=data
```

外网阶段 `NGAClient` 和 `HuaweiSkillRenderer` 是明确的占位适配器；真实调用逻辑只在内网补。华为 Skill 当前应优先按官方 `html2pptx` 路线接入，`generate.py` 作为兜底。`LLM_PROVIDER=local_relay` 用于本地 HTTP 中转站验证主 Agent 调用链路；旧的 `LLM_PROVIDER=openai_compatible` 仍保留为兼容模式，方便已有外部兼容端点继续验证。

## Dify 集成

第一版建议 Dify Workflow 使用一个 HTTP Tool 调用 `POST /generate`，返回 `download_url` 后下载文件。更细粒度集成可以拆成 `/parse`、LLM 节点、`/render`，但 MVP 优先保持简单稳定。

## 部署清单

- 上传代码、`requirements-runtime.txt`、`requirements.txt`、`README.md`、`.env.example`、虚拟模板和非保密样例。
- 不上传真实 API key、真实 `.env`、公司机密输入文件或生成结果。
- 替换 `templates/company_template.pptx`、`templates/reference.docx` 和 `style_profile.yaml`。
- 离线运行机器可先生成最小 wheelhouse：`pip wheel -r requirements-runtime.txt -w wheelhouse`。
- 前端生产构建时设置后端地址：`VITE_API_BASE_URL=https://your-domain/api npm run build`。

## 测试

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=doc_agent --cov=app.api --cov-report=term-missing --cov-fail-under=80
.venv/bin/python -m compileall doc_agent app
cd ppt-agent-frontend && npm run build
cd ppt-agent-frontend && npm run test:coverage
cd ppt-agent-frontend && npm run test:e2e
```

当前覆盖率门禁：后端 85.50%（目标 80%），前端 Statements 90.32%、Branches 74.30%、Functions 83.90%、Lines 93.96%（目标 70%）。`tests/test_quality_gates.py` 覆盖 10 页 PPT 30 秒内生成和 3 个并发任务 30 秒内完成的性能门槛。

`npm run test:e2e` 使用 Playwright 启动隔离的后端 `127.0.0.1:8100` 和前端 `127.0.0.1:3100`，每次运行写入独立的 `.e2e-data/<runId>`。Chrome 覆盖 Markdown 上传、PPTX 生成、WebSocket 进度、下载，设置导入/导出、模型档案创建/切换、模板导入、配色创建、图表/SmartArt IR 生成，以及桌面/移动核心页面的加载速度和横向溢出。
