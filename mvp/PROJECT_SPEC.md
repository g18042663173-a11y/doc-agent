# 企业文档生成 Agent MVP 开源优先方案文件

> 状态说明：本文是早期规格草案，保留作背景参考。当前实现已收敛为外网 `stub`、内网 `NGAClient` + `HuaweiSkillRenderer` 两插座架构；执行和接入请以 `README.md`、`docs/ARCHITECTURE.md`、`docs/内网接入指南.md` 为准。

版本：v1.0  
目标读者：本地 Codex / 实习开发者 / 项目负责人  
项目代号：`doc-agent-mvp`  
核心目标：在本地开发一版可运行 MVP，后续上传到公司机器，接入公司 GLM-4.7、本地模板和内部样例。

---

## 0. 一句话结论

本项目不要做“完全自主乱跑的 Agent”，而是做一个**开源框架驱动的企业文档生成流水线**：

```text
上传 md/docx/pptx
→ 解析成统一 DocumentIR
→ GLM-4.7 生成结构化 DeckIR / WordIR
→ 使用公司模板和风格规则渲染
→ 输出可编辑 pptx/docx
→ 校验失败则自动修复或重试
```

第一版采用：

```text
LangGraph + Docling/MarkItDown + python-pptx/python-docx + Streamlit + FastAPI
```

并预留：

```text
PresentonRenderer：PPT 生成可选适配器
DifyIntegration：后续可视化工作流集成方案
```

---

## 1. 项目定位

### 1.1 这个系统是什么

这是一个企业内部文档生成 Agent，支持将输入文件转换为标准化、可编辑、公司风格统一的 PPTX 或 DOCX。

它的核心不是“AI 自动设计”，而是：

```text
模型负责内容理解和结构规划
模板负责企业视觉风格
代码负责稳定渲染和校验
```

### 1.2 第一版应该证明什么

第一版 MVP 必须证明以下能力：

```text
1. 支持 md/docx/pptx 输入。
2. 能把输入统一解析成 DocumentIR。
3. 能通过 MockLLM 或 GLM 接口生成 DeckIR / WordIR。
4. 能生成可编辑 PPTX。
5. 能生成可编辑 DOCX。
6. PPT/DOCX 风格由 style_profile.yaml 和模板控制。
7. 默认本地开发不调用外部服务。
8. 到公司机器后，只需要改 .env 和模板即可接入真实 GLM。
```

### 1.3 第一版不做什么

第一版暂不承诺：

```text
1. 看懂图片里的业务含义。
2. 自动理解复杂图表。
3. 保留原 PPT 动画。
4. 保留 SmartArt。
5. 完美复刻任意旧 PPT 排版。
6. 一键把任意 PPT 高级美化。
7. 多文件复杂合并。
8. 复杂图片生成。
9. 与 Office 插件深度集成。
```

---

## 2. 总体技术路线

### 2.1 推荐主线

```text
主线：LangGraph 工作流 + 自研轻量渲染器
```

原因：

```text
1. 足够像 Agent，方便汇报。
2. 流程可控，适合企业文档生产。
3. 代码结构清晰，便于 Codex 分阶段实现。
4. 便于后续接 Dify 或 FastAPI。
5. PPT/DOCX 风格能掌握在自己手里。
```

### 2.2 开源工具分层

| 层级 | 第一版工具 | 后续增强 |
|---|---|---|
| 工作流编排 | LangGraph | Dify / LangGraph Studio |
| Web UI | Streamlit | FastAPI + React / Dify UI |
| API 服务 | FastAPI | Dify HTTP Tool / MCP |
| 文档解析 | python-docx / python-pptx / markdown-it-py | Docling / MarkItDown |
| LLM 调用 | OpenAI-compatible SDK | 公司 GLM 网关 |
| 结构校验 | Pydantic v2 | JSON Schema / 自动修复 |
| PPT 渲染 | python-pptx | Presenton / PptxGenJS |
| DOCX 渲染 | python-docx | Pandoc + reference.docx |
| 样式控制 | style_profile.yaml | 模板库 + 样例学习 |

### 2.3 开源优先但不绑定

第一版必须实现两个 PPT 渲染器接口：

```text
PythonPptxRenderer：默认可用，完全本地。
PresentonRenderer：可选适配器，有 Presenton 服务时启用。
```

不要让系统强依赖 Presenton。这样即使 Presenton 不适合公司模板，也不会影响 MVP 交付。

---

## 3. 目标功能范围

### 3.1 输入

支持：

```text
.md
.docx
.pptx
```

MVP 规则：

```text
1. 单文件输入。
2. 文件大小第一版建议限制在 20MB 内。
3. 输入内容先提取文本和表格。
4. 图片第一版仅记录占位符，不做语义理解。
```

### 3.2 输出

支持：

```text
.pptx
.docx
```

输出要求：

```text
1. 必须是可编辑原生文件。
2. 不输出图片版 PPT。
3. 不只输出 PDF。
4. 生成文件必须可被 python-pptx / python-docx 重新打开。
```

### 3.3 交互方式

第一版提供三种入口：

```text
1. CLI：给开发调试。
2. Streamlit：给演示和测试。
3. FastAPI：给后续 Dify 或系统集成。
```

CLI 示例：

```bash
python -m doc_agent generate examples/input.md --target pptx --out outputs/demo.pptx --slides 8
python -m doc_agent generate examples/input.md --target docx --out outputs/demo.docx
```

Streamlit 示例：

```bash
streamlit run app/streamlit_app.py
```

FastAPI 示例：

```bash
uvicorn app.api:app --host 0.0.0.0 --port 9000
```

---

## 4. 系统架构

### 4.1 总流程

```text
Start
  ↓
detect_file_type
  ↓
parse_document
  ↓
normalize_to_document_ir
  ↓
plan_output
  ├─ target=pptx → generate_deck_ir
  └─ target=docx → generate_word_ir
  ↓
validate_ir
  ↓
repair_if_needed
  ↓
render_output
  ├─ pptx → PythonPptxRenderer / PresentonRenderer
  └─ docx → PythonDocxRenderer
  ↓
validate_output_file
  ↓
End
```

### 4.2 LangGraph 节点

必须实现以下节点：

```text
detect_file_type_node
parse_document_node
generate_ir_node
validate_ir_node
repair_ir_node
render_output_node
validate_output_node
```

节点原则：

```text
1. 每个节点只做一件事。
2. 节点输入输出都通过 WorkflowState。
3. 所有错误写入 state.errors。
4. 不在节点里写死公司信息。
5. 不在节点里写死模型地址。
```

### 4.3 WorkflowState

```python
from typing import TypedDict, Literal, Optional, Any

class WorkflowState(TypedDict):
    input_path: str
    target: Literal["pptx", "docx"]
    target_slide_count: int
    document_ir: Optional[dict[str, Any]]
    deck_ir: Optional[dict[str, Any]]
    word_ir: Optional[dict[str, Any]]
    output_path: Optional[str]
    llm_provider: str
    ppt_renderer: str
    errors: list[str]
    warnings: list[str]
    debug: dict[str, Any]
```

---

## 5. 项目目录结构

Codex 必须按下面结构创建项目。

```text
doc-agent-mvp/
  README.md
  PROJECT_SPEC.md
  pyproject.toml
  requirements.txt
  .env.example
  .gitignore

  doc_agent/
    __init__.py
    cli.py
    config.py
    workflow.py

    parsers/
      __init__.py
      base.py
      router.py
      md_parser.py
      docx_parser.py
      pptx_parser.py
      docling_parser.py
      markitdown_parser.py

    ir/
      __init__.py
      schemas.py
      examples.py

    llm/
      __init__.py
      base.py
      mock_client.py
      openai_client.py
      prompts/
        make_deck_ir.md
        make_word_ir.md
        repair_json.md
        summarize_document.md

    planners/
      __init__.py
      deck_planner.py
      word_planner.py

    renderers/
      __init__.py
      base.py
      pptx_python_renderer.py
      pptx_presenton_renderer.py
      docx_python_renderer.py

    validators/
      __init__.py
      ir_validator.py
      deck_validator.py
      word_validator.py
      output_validator.py

    styles/
      style_profile.yaml

    utils/
      __init__.py
      file_utils.py
      json_utils.py
      text_utils.py
      yaml_utils.py
      logging_utils.py

  app/
    streamlit_app.py
    api.py

  examples/
    input.md
    sample_deck_ir.json
    sample_word_ir.json

  templates/
    company_template.pptx
    reference.docx

  outputs/
    .gitkeep

  tests/
    test_schemas.py
    test_md_parser.py
    test_mock_llm.py
    test_pptx_renderer.py
    test_docx_renderer.py
    test_workflow_generate.py
```

---

## 6. 配置文件

### 6.1 `.env.example`

```env
# mock or openai_compatible
LLM_PROVIDER=mock

# Used only when LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://127.0.0.1:8000/v1
LLM_API_KEY=EMPTY
LLM_MODEL=glm-4.7

# PPT renderer: python_pptx or presenton
PPT_RENDERER=python_pptx
PRESENTON_BASE_URL=http://127.0.0.1:5000

# Generation defaults
DEFAULT_TARGET_SLIDES=8
MAX_INPUT_CHARS=60000
MAX_REPAIR_ATTEMPTS=2

# Paths
STYLE_PROFILE=doc_agent/styles/style_profile.yaml
TEMPLATE_PPTX=templates/company_template.pptx
REFERENCE_DOCX=templates/reference.docx
OUTPUT_DIR=outputs

# Debug
SAVE_DEBUG_ARTIFACTS=true
```

### 6.2 `style_profile.yaml`

```yaml
brand:
  name: "demo_company"
  slide_size: "16:9"
  logo_path: null

fonts:
  zh: "Microsoft YaHei"
  en: "Arial"

colors:
  background: "FFFFFF"
  title: "111827"
  body: "374151"
  muted: "6B7280"
  primary: "1F4E79"
  secondary: "5B9BD5"
  accent: "C55A11"
  white: "FFFFFF"

ppt_rules:
  max_slides: 12
  min_slides: 5
  max_title_chars: 28
  max_bullets_per_slide: 5
  max_chars_per_bullet: 32
  allowed_layouts:
    - cover
    - agenda
    - section
    - title_bullets
    - two_column
    - table
    - conclusion
  forbidden_phrases:
    - "作为AI模型"
    - "作为 AI 模型"
    - "我不能"
    - "无法提供"

docx_rules:
  heading_1_size: 18
  heading_2_size: 15
  heading_3_size: 13
  body_size: 11
  use_numbered_headings: true
  max_paragraph_chars: 500
```

---

## 7. 依赖文件

### 7.1 `requirements.txt`

第一版建议：

```txt
pydantic>=2.7
python-dotenv>=1.0
PyYAML>=6.0
typer>=0.12
rich>=13.7
openai>=1.40
langgraph>=0.2.0
python-pptx>=1.0.0
python-docx>=1.1.2
streamlit>=1.36
fastapi>=0.112
uvicorn>=0.30
markdown-it-py>=3.0
requests>=2.32
pytest>=8.0
```

可选增强依赖：

```txt
markitdown
docling
pandocfilters
```

注意：`docling` 可能较重，MVP 不要强依赖。实现时要 try/except，如果未安装则 fallback 到轻量 parser。

---

## 8. 核心数据结构

### 8.1 DocumentIR

用于表示从输入文件解析出的统一内容。

```python
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

class DocumentBlock(BaseModel):
    id: str
    type: Literal["heading", "paragraph", "bullet_list", "table", "slide", "note", "image"]
    text: Optional[str] = None
    level: Optional[int] = None
    items: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

class DocumentIR(BaseModel):
    source_file: str
    source_type: Literal["md", "docx", "pptx", "unknown"]
    title: Optional[str] = None
    blocks: list[DocumentBlock] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
```

### 8.2 DeckIR

用于表示要生成的 PPT。

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

class SlideIR(BaseModel):
    layout: Literal[
        "cover",
        "agenda",
        "section",
        "title_bullets",
        "two_column",
        "table",
        "conclusion",
    ]
    title: str
    subtitle: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)

    left_title: Optional[str] = None
    left_bullets: list[str] = Field(default_factory=list)
    right_title: Optional[str] = None
    right_bullets: list[str] = Field(default_factory=list)

    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)

    speaker_notes: Optional[str] = None

class DeckIR(BaseModel):
    deck_title: str
    audience: str = "内部汇报"
    tone: str = "专业、克制、清晰"
    slides: list[SlideIR] = Field(default_factory=list)
```

### 8.3 WordIR

用于表示要生成的 Word 报告。

```python
from typing import Literal
from pydantic import BaseModel, Field

class WordBlockIR(BaseModel):
    type: Literal["heading", "paragraph", "bullet_list", "table"]
    text: str | None = None
    level: int | None = None
    items: list[str] = Field(default_factory=list)
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)

class WordIR(BaseModel):
    title: str
    subtitle: str | None = None
    blocks: list[WordBlockIR] = Field(default_factory=list)
```

---

## 9. Parser 设计

### 9.1 Parser 接口

```python
from abc import ABC, abstractmethod
from pathlib import Path
from doc_agent.ir.schemas import DocumentIR

class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> DocumentIR:
        pass
```

### 9.2 ParserRouter

```python
class ParserRouter:
    def parse(self, path: str | Path) -> DocumentIR:
        ext = Path(path).suffix.lower()
        if ext == ".md":
            return MarkdownParser().parse(path)
        if ext == ".docx":
            return DocxParser().parse(path)
        if ext == ".pptx":
            return PptxParser().parse(path)
        raise ValueError(f"Unsupported file type: {ext}")
```

### 9.3 MarkdownParser

支持：

```text
# 一级标题
## 二级标题
### 三级标题
普通段落
- bullet
* bullet
简单 Markdown 表格
```

### 9.4 DocxParser

使用 `python-docx`，提取：

```text
1. 段落
2. 标题样式 Heading 1/2/3
3. 列表段落
4. 表格
```

### 9.5 PptxParser

使用 `python-pptx`，提取：

```text
1. 每页文本框内容
2. 每页标题候选
3. 每页 bullets
4. slide_number 写入 meta
```

### 9.6 DoclingParser / MarkItDownParser

作为增强解析器：

```text
1. 如果安装了 docling，可优先使用。
2. 如果安装了 markitdown，可作为 fallback。
3. 不允许未安装时导致整个项目崩溃。
```

伪代码：

```python
try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None
```

---

## 10. LLM 设计

### 10.1 LLM Client 接口

```python
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    @abstractmethod
    def generate_json(self, prompt: str) -> dict:
        pass
```

### 10.2 MockLLMClient

必须默认启用。

用途：

```text
1. 本地开发不需要真实模型。
2. 测试可以稳定复现。
3. 没有外网也能运行。
```

Mock 输出规则：

```text
1. 根据 DocumentIR title 生成 deck_title。
2. 生成 6 页 PPT：
   - cover
   - agenda
   - section
   - title_bullets
   - two_column
   - conclusion
3. 生成一个 Word 报告：
   - 标题
   - 摘要
   - 2~3 个章节
   - bullet 列表
```

### 10.3 OpenAICompatibleLLMClient

读取：

```text
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
```

必须做到：

```text
1. 只有 LLM_PROVIDER=openai_compatible 时才调用。
2. 不在代码中硬编码模型地址。
3. 出错时返回清晰错误。
4. 支持 JSON 修复重试。
```

---

## 11. Prompt 设计

### 11.1 `make_deck_ir.md`

```text
你是企业汇报文档规划助手。

任务：
根据输入文档内容，生成一个用于渲染 PPTX 的 JSON。

要求：
1. 只输出 JSON，不要输出 Markdown，不要解释。
2. JSON 必须符合 DeckIR schema。
3. PPT 风格应专业、克制、清晰，避免花哨表达。
4. 每页只表达一个核心观点。
5. 每页 bullet 不超过 5 条。
6. 每条 bullet 不超过 32 个中文字符。
7. 不要编造输入文档中没有的关键事实。
8. 如果输入内容很长，请提炼重点，而不是堆满页面。
9. 输出语言使用中文。
10. 不要出现“作为 AI 模型”等话术。

可用 layout：
- cover：封面
- agenda：目录
- section：章节页
- title_bullets：标题 + 要点
- two_column：左右对比
- table：表格
- conclusion：结论页

输入文档 DocumentIR：
{{document_ir_json}}

目标页数：
{{target_slide_count}}

请输出 DeckIR JSON。
```

### 11.2 `make_word_ir.md`

```text
你是企业 Word 报告撰写助手。

任务：
根据输入文档内容，生成一个用于渲染 DOCX 的 JSON。

要求：
1. 只输出 JSON，不要输出 Markdown，不要解释。
2. JSON 必须符合 WordIR schema。
3. 内容要结构清晰，适合企业内部报告。
4. 不要编造输入文档中没有的关键事实。
5. 保留重要表格信息。
6. 输出语言使用中文。
7. 不要出现“作为 AI 模型”等话术。

输入文档 DocumentIR：
{{document_ir_json}}

请输出 WordIR JSON。
```

### 11.3 `repair_json.md`

```text
下面的 JSON 不符合 schema 或质量规则。

错误信息：
{{errors}}

原始 JSON：
{{bad_json}}

请修复 JSON。

要求：
1. 只输出修复后的 JSON。
2. 不要解释。
3. 不要添加 Markdown 代码块。
4. 不要改变原始业务含义。
5. 保持中文输出。
```

---

## 12. Planner 设计

### 12.1 DeckPlanner

职责：

```text
DocumentIR → DeckIR
```

流程：

```text
1. 把 DocumentIR 转成 JSON 字符串。
2. 渲染 make_deck_ir.md prompt。
3. 调用 LLM。
4. 尝试解析 JSON。
5. 用 Pydantic 校验 DeckIR。
6. 如果失败，调用 repair_json。
7. 最多重试 MAX_REPAIR_ATTEMPTS 次。
8. 失败则保存 debug/bad_response.json。
```

### 12.2 WordPlanner

职责：

```text
DocumentIR → WordIR
```

流程同 DeckPlanner。

---

## 13. 渲染器设计

### 13.1 Renderer 接口

```python
from abc import ABC, abstractmethod
from pathlib import Path

class BaseRenderer(ABC):
    @abstractmethod
    def render(self, ir: dict, output_path: Path) -> Path:
        pass
```

### 13.2 PPT 渲染器选择

配置：

```env
PPT_RENDERER=python_pptx
```

支持：

```text
python_pptx：默认
presenton：可选
```

### 13.3 PythonPptxRenderer

使用 `python-pptx`。支持布局：

```text
cover
agenda
section
title_bullets
two_column
table
conclusion
```

硬性规则：

```text
1. 所有坐标由代码决定。
2. 所有颜色来自 style_profile.yaml。
3. 所有字体来自 style_profile.yaml。
4. 模型不能决定字体、颜色、坐标。
5. bullet 超过限制时自动截断或拆页。
6. 标题为空时使用“未命名章节”兜底。
```

页面规则：

```text
cover：
- 大标题
- 副标题
- 日期/来源

agenda：
- 最多 6 个目录项

section：
- 章节标题
- 大号编号可选

title_bullets：
- 标题
- 3~5 条 bullet

two_column：
- 左右两栏
- 每栏 2~4 条 bullet

table：
- 最多 6 行 5 列
- 太大的表格截断并提示

conclusion：
- 3 条核心结论
```

### 13.4 PresentonRenderer

这是可选适配器，不作为第一版必需成功项。

职责：

```text
DeckIR → 调用 Presenton 服务 → output.pptx
```

实现要求：

```text
1. 只有 PPT_RENDERER=presenton 时启用。
2. 读取 PRESENTON_BASE_URL。
3. 如果 Presenton 不可用，给出清晰错误。
4. 不影响 PythonPptxRenderer。
5. API endpoint 以实际安装的 Presenton 文档为准。
6. Presenton PoC 通过后，再补齐具体 endpoint。
```

Codex 应先实现类结构和错误提示，不要瞎猜 Presenton API。

### 13.5 PythonDocxRenderer

使用 `python-docx`。

支持：

```text
1. title
2. subtitle
3. heading 1/2/3
4. paragraph
5. bullet list
6. table
```

规则：

```text
1. 如果 templates/reference.docx 存在，则用它作为基础文档。
2. 否则创建空白 Document。
3. 字体和字号来自 style_profile.yaml。
4. 表格使用统一边框样式。
5. 输出后必须能重新打开。
```

---

## 14. Validator 设计

### 14.1 DeckValidator

检查：

```text
1. deck_title 不为空。
2. slides 不为空。
3. slides 数量在 min_slides 和 max_slides 之间。
4. layout 在 allowed_layouts 内。
5. 每页 title 不为空。
6. 每页 title 不超过 max_title_chars。
7. bullet 不超过 max_bullets_per_slide。
8. bullet 字符数不超过 max_chars_per_bullet。
9. table 不超过 6 行 5 列。
10. 不出现 forbidden_phrases。
```

处理策略：

```text
轻微问题：自动修正。
严重问题：返回 errors，触发 repair_ir_node。
```

### 14.2 WordValidator

检查：

```text
1. title 不为空。
2. blocks 不为空。
3. heading 层级合理。
4. paragraph 不过长。
5. table 不为空。
6. 不出现 forbidden_phrases。
```

### 14.3 OutputValidator

检查：

```text
1. 输出路径存在。
2. 文件大小大于 0。
3. pptx 能被 Presentation() 打开。
4. docx 能被 Document() 打开。
5. 后缀和 target 一致。
```

---

## 15. CLI 设计

使用 Typer。

### 15.1 命令列表

```bash
python -m doc_agent parse INPUT --out outputs/document_ir.json

python -m doc_agent plan outputs/document_ir.json --target pptx --out outputs/deck_ir.json --slides 8

python -m doc_agent render outputs/deck_ir.json --target pptx --out outputs/demo.pptx

python -m doc_agent generate INPUT --target pptx --out outputs/demo.pptx --slides 8

python -m doc_agent generate INPUT --target docx --out outputs/demo.docx
```

### 15.2 generate 流程

```text
parse
→ plan
→ validate
→ render
→ validate_output
```

---

## 16. Streamlit UI 设计

文件：`app/streamlit_app.py`

功能：

```text
1. 页面标题：企业文档生成 Agent MVP
2. 文件上传：md/docx/pptx
3. 输出类型选择：pptx/docx
4. PPT 页数选择：5~12
5. LLM_PROVIDER 显示
6. PPT_RENDERER 显示
7. 生成按钮
8. 日志展示
9. 下载按钮
```

限制：

```text
1. UI 不写业务逻辑。
2. UI 只调用 doc_agent.workflow.run_generate。
3. 临时文件写入 outputs/tmp。
```

---

## 17. FastAPI 设计

文件：`app/api.py`

### 17.1 Endpoints

```text
GET  /health
POST /parse
POST /plan
POST /render
POST /generate
GET  /download/{file_id}
```

### 17.2 用途

```text
1. 后续接 Dify HTTP Tool。
2. 后续接公司内部系统。
3. 后续替换 Streamlit 前端。
```

### 17.3 注意

第一版可以简单实现：

```text
POST /generate 上传文件，返回生成文件路径或下载链接。
```

---

## 18. Dify 集成方案

Dify 不作为第一版开发必需项，但要在 README 中说明怎么接。

### 18.1 推荐方式

```text
Dify Workflow
  ↓
File Upload
  ↓
HTTP Tool: POST /generate
  ↓
返回下载链接
```

### 18.2 更细粒度方式

```text
File Upload
  ↓
HTTP Tool: /parse
  ↓
LLM Node: generate DeckIR/WordIR
  ↓
HTTP Tool: /render
  ↓
HTTP Tool: /download
```

第一版建议使用 `/generate` 一个接口，简单稳定。

---

## 19. Presenton PoC 方案

如果公司想快速验证开源 PPT 工具效果，单独做 PoC。

### 19.1 PoC 目标

```text
1. 本地跑起 Presenton。
2. 接入 OpenAI-compatible GLM。
3. 上传一份 demo 文档。
4. 导入或配置公司 PPT 模板。
5. 输出可编辑 PPTX。
6. 判断风格是否可接受。
```

### 19.2 是否进入主系统的判断标准

```text
进入条件：
- 能本地/内网运行
- 能接 GLM
- 能输出可编辑 PPTX
- 能使用公司模板
- 效果比 PythonPptxRenderer 明显好
- 可关闭外部图片/API 服务
- API 可稳定集成

不进入条件：
- API 不稳定
- 模板控制不够细
- 依赖过重
- DOCX 无法覆盖
- 安全审计成本过高
```

### 19.3 主系统如何适配

保留接口：

```python
class PptRenderer:
    def render(self, deck_ir, style_profile, output_path):
        ...
```

以后可以替换：

```text
PythonPptxRenderer
PresentonRenderer
PptxGenJsRenderer
```

---

## 20. 本地开发流程

### 20.1 创建环境

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

macOS/Linux：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

### 20.2 默认 mock 模式运行

```bash
cp .env.example .env
```

确认：

```env
LLM_PROVIDER=mock
PPT_RENDERER=python_pptx
```

生成 PPT：

```bash
python -m doc_agent generate examples/input.md --target pptx --out outputs/demo.pptx --slides 8
```

生成 Word：

```bash
python -m doc_agent generate examples/input.md --target docx --out outputs/demo.docx
```

启动 UI：

```bash
streamlit run app/streamlit_app.py
```

启动 API：

```bash
uvicorn app.api:app --reload --port 9000
```

测试：

```bash
pytest
```

---

## 21. 公司机器部署流程

### 21.1 上传内容

上传：

```text
代码
requirements.txt
README.md
.env.example
templates/占位模板
examples/非保密样例
```

不要上传：

```text
真实 API key
真实 .env
公司机密输入文件
公司生成结果
本地开发缓存
```

### 21.2 离线依赖包

如果公司机器无法访问 PyPI，在自己机器准备 wheelhouse：

```bash
mkdir wheelhouse
pip wheel -r requirements.txt -w wheelhouse
```

公司机器安装：

```bash
pip install --no-index --find-links wheelhouse -r requirements.txt
```

### 21.3 公司机器配置

创建 `.env`：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://公司内网模型地址/v1
LLM_API_KEY=公司给的key
LLM_MODEL=glm-4.7
PPT_RENDERER=python_pptx
```

替换：

```text
templates/company_template.pptx
templates/reference.docx
doc_agent/styles/style_profile.yaml
```

---

## 22. 验收标准

### 22.1 功能验收

```text
1. md → pptx 成功。
2. md → docx 成功。
3. docx → pptx 成功。
4. docx → docx 成功。
5. pptx → pptx 成功。
6. pptx → docx 成功。
7. CLI 可用。
8. Streamlit 可用。
9. FastAPI /health 可用。
10. 默认 mock 模式不调用外部服务。
```

### 22.2 文件验收

```text
1. 输出 PPTX 可用 PowerPoint 打开。
2. 输出 DOCX 可用 Word 打开。
3. 文件可编辑。
4. 文件大小大于 0。
5. 输出路径正确。
```

### 22.3 内容验收

```text
1. 没有空标题。
2. 没有空页面。
3. 没有“作为 AI 模型”等废话。
4. PPT 每页 bullet 不超过 5 条。
5. bullet 长度受控。
6. 主题和输入文档一致。
```

### 22.4 风格验收

```text
1. PPT 使用 style_profile 指定字体。
2. PPT 使用 style_profile 指定颜色。
3. DOCX 标题、正文、列表样式统一。
4. 输出整体克制、清晰，不花哨。
```

### 22.5 工程验收

```text
1. pytest 通过。
2. README 能让别人跑起来。
3. .env 不进入 git。
4. 没有 hardcoded key。
5. 未安装 docling/markitdown 时项目不崩。
6. 出错信息可读。
```

---

## 23. Codex 开发任务总提示词

把下面这段作为 Codex 第一条总提示词。

```text
You are implementing a Python 3.11 project called doc-agent-mvp.

Read PROJECT_SPEC.md carefully and implement the project incrementally.

Core requirements:
- Build a local enterprise document generation MVP.
- Support md/docx/pptx input.
- Output editable pptx/docx.
- Use LangGraph for workflow orchestration.
- Use Pydantic v2 for IR schemas.
- Use python-pptx for default PPTX rendering.
- Use python-docx for DOCX rendering.
- Use Typer for CLI.
- Use Streamlit for UI.
- Use FastAPI for integration endpoints.
- Default LLM_PROVIDER must be mock and must not call external services.
- OpenAI-compatible LLM client must only be used when LLM_PROVIDER=openai_compatible.
- Do not hardcode secrets or company-specific information.
- Put all style decisions in style_profile.yaml.
- The model must only produce structured JSON; rendering code controls layout, fonts, colors, and coordinates.
- Implement tests for schemas, parser, mock LLM, renderers, and workflow.
- Keep code simple, readable, and robust.

Implement task by task and run pytest after each major step.
```

---

## 24. Codex 分步开发任务

### Task 01：项目骨架

```text
Create the full project structure defined in PROJECT_SPEC.md.
Add README.md, requirements.txt, .env.example, .gitignore.
Create empty modules with clear TODOs.
Add outputs/.gitkeep.
```

验收：

```bash
python -m compileall doc_agent app
```

---

### Task 02：配置加载

```text
Implement doc_agent/config.py.

Requirements:
- Load .env with python-dotenv.
- Define Settings with pydantic or dataclass.
- Load style_profile.yaml.
- Provide get_settings().
- Provide load_style_profile().
```

验收：

```bash
python -c "from doc_agent.config import get_settings; print(get_settings())"
```

---

### Task 03：IR Schemas

```text
Implement doc_agent/ir/schemas.py.

Define:
- DocumentBlock
- DocumentIR
- SlideIR
- DeckIR
- WordBlockIR
- WordIR

Use Pydantic v2.
Add helper functions:
- load_json(path, model)
- save_json(obj, path)
- to_pretty_json(obj)

Add tests in tests/test_schemas.py.
```

验收：

```bash
pytest tests/test_schemas.py
```

---

### Task 04：Parsers

```text
Implement:
- BaseParser
- MarkdownParser
- DocxParser
- PptxParser
- ParserRouter

MarkdownParser:
- Parse headings.
- Parse bullet lists.
- Parse paragraphs.
- Basic markdown table support.

DocxParser:
- Use python-docx.
- Extract headings, paragraphs, tables.

PptxParser:
- Use python-pptx.
- Extract text per slide.
- Store slide number in meta.

Add tests for MarkdownParser.
```

验收：

```bash
python -m doc_agent parse examples/input.md --out outputs/document_ir.json
pytest tests/test_md_parser.py
```

---

### Task 05：Mock LLM

```text
Implement:
- BaseLLMClient
- MockLLMClient

MockLLMClient must return deterministic DeckIR/WordIR JSON from DocumentIR.

Add tests:
- Mock deck generation.
- Mock word generation.
```

验收：

```bash
pytest tests/test_mock_llm.py
```

---

### Task 06：OpenAI-compatible LLM Client

```text
Implement OpenAICompatibleLLMClient.

Requirements:
- Use openai Python SDK.
- Read base_url/api_key/model from Settings.
- Implement generate_json(prompt).
- Extract JSON from model response.
- Raise clear errors on failure.
- Must not run unless LLM_PROVIDER=openai_compatible.
```

验收：

```bash
LLM_PROVIDER=mock pytest
```

不要在测试中真实调用外部模型。

---

### Task 07：Prompt Loader 和 Planners

```text
Implement:
- Prompt loading from llm/prompts/*.md
- DeckPlanner
- WordPlanner

DeckPlanner:
- DocumentIR -> prompt -> LLM -> DeckIR

WordPlanner:
- DocumentIR -> prompt -> LLM -> WordIR

If JSON parse or validation fails:
- Use repair_json prompt up to MAX_REPAIR_ATTEMPTS.
```

验收：

```bash
python -m doc_agent plan outputs/document_ir.json --target pptx --out outputs/deck_ir.json --slides 8
python -m doc_agent plan outputs/document_ir.json --target docx --out outputs/word_ir.json
```

---

### Task 08：Validators

```text
Implement:
- DeckValidator
- WordValidator
- OutputValidator

DeckValidator should enforce style_profile ppt_rules.
WordValidator should enforce style_profile docx_rules.
OutputValidator should reopen generated files.
```

验收：

```bash
pytest
```

---

### Task 09：PythonPptxRenderer

```text
Implement PythonPptxRenderer.

Support layouts:
- cover
- agenda
- section
- title_bullets
- two_column
- table
- conclusion

Use python-pptx.
Use style_profile fonts and colors.
Use fixed coordinates.
Do not let model choose coordinates/colors/fonts.
Add output validation.
```

验收：

```bash
python -m doc_agent render examples/sample_deck_ir.json --target pptx --out outputs/demo.pptx
pytest tests/test_pptx_renderer.py
```

---

### Task 10：PythonDocxRenderer

```text
Implement PythonDocxRenderer.

Support:
- title
- subtitle
- headings
- paragraphs
- bullet lists
- tables

If templates/reference.docx exists, use it as base document.
Otherwise create blank document.
Apply style_profile fonts and sizes.
```

验收：

```bash
python -m doc_agent render examples/sample_word_ir.json --target docx --out outputs/demo.docx
pytest tests/test_docx_renderer.py
```

---

### Task 11：LangGraph Workflow

```text
Implement doc_agent/workflow.py.

Create LangGraph workflow:
- detect_file_type_node
- parse_document_node
- generate_ir_node
- validate_ir_node
- repair_ir_node
- render_output_node
- validate_output_node

Expose function:
run_generate(input_path, target, output_path, target_slide_count=8) -> Path
```

验收：

```bash
python -m doc_agent generate examples/input.md --target pptx --out outputs/demo.pptx --slides 8
python -m doc_agent generate examples/input.md --target docx --out outputs/demo.docx
pytest tests/test_workflow_generate.py
```

---

### Task 12：CLI

```text
Implement doc_agent/cli.py using Typer.

Commands:
- parse
- plan
- render
- generate

Make package executable:
python -m doc_agent ...
```

需要 `doc_agent/__main__.py`：

```python
from doc_agent.cli import app

if __name__ == "__main__":
    app()
```

验收：

```bash
python -m doc_agent --help
```

---

### Task 13：Streamlit UI

```text
Implement app/streamlit_app.py.

Features:
- Upload md/docx/pptx.
- Select target pptx/docx.
- Select target slide count.
- Show current LLM_PROVIDER and PPT_RENDERER.
- Generate output.
- Show logs/errors.
- Download file.
```

验收：

```bash
streamlit run app/streamlit_app.py
```

---

### Task 14：FastAPI

```text
Implement app/api.py.

Endpoints:
- GET /health
- POST /generate

Optional:
- POST /parse
- POST /plan
- POST /render

POST /generate should accept:
- file
- target
- slides

It returns:
- file_id
- download_url
- warnings
```

验收：

```bash
uvicorn app.api:app --reload --port 9000
curl http://127.0.0.1:9000/health
```

---

### Task 15：PresentonRenderer Adapter Skeleton

```text
Implement PptxPresentonRenderer skeleton.

Requirements:
- Read PRESENTON_BASE_URL.
- Check health if possible.
- Raise NotImplementedError with clear message if API endpoint is not configured.
- Do not break PythonPptxRenderer.
- Add README section explaining this is optional and requires actual Presenton API mapping.
```

验收：

```bash
PPT_RENDERER=python_pptx pytest
```

---

### Task 16：README 和 Demo

```text
Write README.md.

Include:
- Project overview
- Why model generates JSON and renderer controls style
- Local setup
- Mock mode
- GLM mode
- CLI usage
- Streamlit usage
- FastAPI usage
- Company deployment checklist
- Known limitations
- Roadmap
```

验收：

```text
A new developer can follow README and run md -> pptx/docx in mock mode.
```

---

## 25. README 必须包含的部署话术

```text
默认情况下，本项目使用 MockLLMClient，不会调用任何外部模型或云服务。

在个人开发机器上，请只使用非保密样例文件和虚拟模板。

公司内网部署时，通过 .env 配置 GLM-4.7 的 OpenAI-compatible 接口。

模型只负责生成结构化 JSON，PPTX/DOCX 的样式由本地模板和 style_profile.yaml 控制。

第一版仅提取文档文本内容，不承诺理解图片、复杂图表、动画、SmartArt。
```

---

## 26. 演示脚本

演示时按这个顺序：

```text
1. 展示输入 examples/input.md。
2. 运行 md → pptx。
3. 打开 outputs/demo.pptx。
4. 说明 PPT 是可编辑的，风格来自 style_profile。
5. 运行 md → docx。
6. 打开 outputs/demo.docx。
7. 切换一个 docx 输入。
8. 生成 PPTX。
9. 展示 Streamlit 上传下载页面。
10. 说明后续接公司 GLM，只需要改 .env。
```

汇报用话术：

```text
这版 MVP 验证了多格式输入、结构化生成、模板化渲染和可编辑输出。模型不直接决定视觉样式，而是输出 JSON；公司风格由模板和规则控制。因此系统稳定、可审计、可替换模型，并且后续可以接入 Dify 或 Presenton。
```

---

## 27. 风险和应对

### 27.1 GLM 输出 JSON 不稳定

应对：

```text
Pydantic 校验
repair_json prompt
最多重试 2 次
保存 bad_response.json
```

### 27.2 PPT 文本溢出

应对：

```text
限制 bullet 数量
限制 bullet 长度
超长标题截断
后续实现拆页
```

### 27.3 公司模板复杂

应对：

```text
第一版先用 style_profile 复刻基础风格
后续接真实母版
PPT 渲染器接口可替换
```

### 27.4 Presenton 集成不稳定

应对：

```text
Presenton 可选
PythonPptxRenderer 兜底
不要让主系统依赖 Presenton
```

### 27.5 Dify 部署增加复杂度

应对：

```text
第一版用 Streamlit + FastAPI
后续用 Dify HTTP Tool 调 FastAPI
```

---

## 28. 版本路线图

### v0.1 离线渲染版

```text
sample_deck_ir.json → pptx
sample_word_ir.json → docx
```

### v0.2 md 输入版

```text
input.md → DocumentIR → MockLLM → pptx/docx
```

### v0.3 多格式输入版

```text
docx/pptx → DocumentIR → MockLLM → pptx/docx
```

### v0.4 GLM 接入版

```text
LLM_PROVIDER=openai_compatible
接入公司 GLM-4.7
```

### v0.5 UI/API 版

```text
Streamlit 上传下载
FastAPI /generate
```

### v0.6 开源增强版

```text
Docling/MarkItDown 优先解析
Presenton PPT PoC
Dify Workflow PoC
```

---

## 29. 最终交付物

第一版交付：

```text
1. Git 项目源码。
2. README.md。
3. PROJECT_SPEC.md。
4. CLI。
5. Streamlit UI。
6. FastAPI /health 和 /generate。
7. md/docx/pptx 解析。
8. MockLLM。
9. OpenAI-compatible LLM client。
10. PPTX 生成。
11. DOCX 生成。
12. 基础测试。
13. demo 输入和 demo 输出。
```

不交付：

```text
1. 公司真实模板。
2. 公司真实数据。
3. 真实 API key。
4. 云部署。
5. Office 插件。
```

---

## 30. 最重要的工程原则

```text
1. 默认 mock，避免外部依赖。
2. 结构先行，模型只输出 JSON。
3. 样式外置，style_profile 控制风格。
4. 渲染可替换，PPT/DOCX renderer 都走接口。
5. 校验兜底，不能信任模型输出。
6. 先 CLI 后 UI，先可运行后好看。
7. 不把公司信息写进代码。
8. 开源工具为我所用，不被工具绑架。
```

这就是第一版的完整方案。Codex 应按任务顺序实现，不要跳到复杂功能。
