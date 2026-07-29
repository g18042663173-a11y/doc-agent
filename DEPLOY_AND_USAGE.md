# 内网部署与使用交接

## 1. 交付内容

本项目是一个以 IR 为唯一契约的离线文档流水线：

```text
md/docx/xlsx/pptx -> DocumentIR -> Prompt/generator -> WordIR/DeckIR -> DOCX/PPTX -> 合规报告
```

当前交付版本的 IR 为：DocumentIR `1.2`、WordIR `1.2`、DeckIR `2.0`。历史 WordIR `1.0/1.1`、DocumentIR `1.0/1.1`、DeckIR `1.4-1.9` 可在内存中迁移后按现行约束校验。

默认可离线运行的是 `stub` 生成器。它用于可重复的链路、回归和交付验收，不代表真实模型生成质量。

## 2. 内网 Windows 部署

### 前置条件

- Windows x64，CPython `3.12`。
- 解压完整迁移包到一个可写目录；以下命令在仓库根目录运行。
- 包内 `wheelhouse/` 是 Python 依赖离线轮子，`requirements-win312.lock` 锁定了文件哈希。
- 若要获得 Graphviz 架构图自动布局，需要另行将经内网审计的 Graphviz Windows 运行时放到 `tools/graphviz/`，使 `tools/graphviz/bin/dot.exe` 存在。Python 的 `graphviz` wheel 不包含 `dot.exe`。

```powershell
# 创建 Python 3.12 虚拟环境并从 wheelhouse 校验哈希后离线安装
.\bootstrap_windows.ps1

# Graphviz 已按上述方式放置时执行；未放置时，架构图会使用确定性 fallback 并给出 warning
$env:PATH = "$PWD\tools\graphviz\bin;$env:PATH"
dot -V

# 设置 Python 包路径并执行自动验收
.\verify.ps1
```

`verify.ps1` 会设置 `PYTHONPATH=backend` 并运行 `python scripts/verify.py`。通过后会验证 schema 快照、四种输入格式到 Word/Deck 的 stub 端到端链路、PPTX lint 和覆盖率门槛。

## 3. 目录职责

| 路径 | 职责 |
| --- | --- |
| `backend/app/parsers/` | 解析 md/docx/xlsx/pptx 为 DocumentIR。 |
| `backend/app/ir/` | 三份 IR 模型、schema、错误码、剥壳和修复校验。 |
| `backend/app/prompting/` | 确定性 prompt 组装、few-shot 与分段策略。 |
| `backend/app/generators/` | `stub`、可选 Codex，以及待内网实现的 `nga` 适配层。 |
| `backend/app/rendering/` | python-docx / python-pptx 的可编辑 DOCX/PPTX 渲染。 |
| `backend/app/lint/` | DOCX/PPTX 合规检查与报告。 |
| `backend/app/reliability/` | FailureEnvelope、持久 JobState 与服务可靠性契约。 |
| `backend/app/cli/` | `parse`、`prompt`、`render`、`check`、`analyze` 命令。 |
| `backend/schemas/` | 导出的三份 JSON Schema 快照。 |
| `backend/tests/` | 单元、契约、渲染回读、lint 和端到端测试。 |
| `samples/` | 固定输入、IR 正反例、expected、演示与回归资产。 |
| `wheelhouse/` | 随完整迁移包携带的 Windows CPython 3.12 离线依赖。 |
| `docs/` | 任务书、内网接入、验收手册、资产说明和审计记录。 |

## 4. 常用命令

以下命令均从仓库根目录执行。Windows PowerShell 中将 `PYTHONPATH=backend` 换成 `$env:PYTHONPATH = "backend"`；或先执行一次 `verify.ps1` 后再在同一会话中使用。

### 解析输入

```bash
PYTHONPATH=backend python -m app.cli.parse samples/input/需求说明.docx --output output/document_ir.json
```

支持 `.md`、`.docx`、`.xlsx`、`.pptx`。解析失败会以非零退出，并在输出文件旁写出结构化失败报告。

### 生成 Prompt

```bash
PYTHONPATH=backend python -m app.cli.prompt \
  --kind deck \
  --context output/document_ir.json \
  --max-context-chars 12000 \
  --max-output-chars 6000 \
  --output output/deck_prompt.txt
```

`--kind` 只能是 `word` 或 `deck`。Prompt 是交给模型的文本；模型输出必须先经过 IR 剥壳和校验，不能直接交给 renderer。

### 直接渲染已校验的 IR

```bash
PYTHONPATH=backend python -m app.cli.render \
  --type word samples/ir/word_valid_03_table.json --output output/example.docx

PYTHONPATH=backend python -m app.cli.render \
  --type deck samples/ir/deck_valid_full.json --output output/example.pptx
```

`--type` 只能是 `word` 或 `deck`。Deck 渲染后会自动运行 PPTX lint；存在 lint Error 时命令非零退出。

### 复检成品

```bash
PYTHONPATH=backend python -m app.cli.check \
  output/example.pptx \
  --classification "HUAWEI CONFIDENTIAL" \
  --output-dir output/check-pptx

PYTHONPATH=backend python -m app.cli.check \
  output/example.docx \
  --classification "HUAWEI CONFIDENTIAL" \
  --output-dir output/check-docx
```

复检支持 `.pptx` 和 `.docx`，在 `--output-dir` 下写 JSON 与 Markdown 报告。

### 使用默认 stub 走完整链路

```bash
# Word
python scripts/demo_e2e.py samples/input/quarterly_report.md \
  --target word --generator stub --output-dir output/demo-word

# Deck：先分析页数建议
python scripts/analyze.py samples/input/quarterly_report.md \
  --generator stub --output output/analysis.json

# Deck：生成标准档，并输出 lint 报告
python scripts/generate.py samples/input/quarterly_report.md \
  --generator stub --depth 标准 --lint --output-dir output/demo-deck
```

`scripts/demo_e2e.py` 的完整参数为：

```text
<input_file> --target word|deck [--generator stub|nga|codex]
[--output-dir PATH] [--lint] [--max-context-chars 12000]
[--max-output-chars 6000] [--pages N] [--depth 概览|标准|详细]
```

`--pages` 与 `--depth` 仅适用于 `--target deck`。`scripts/generate.py` 是强制 `--target deck` 的便捷包装。

## 5. NGA 接入边界

`backend/app/generators/nga.py` 是内网接入点，但目前只校验 `NGA_BASE_URL` 和 `NGA_TOKEN` 后抛出 `NotImplementedError`，尚未实现真实协议、鉴权和请求格式。因此不要在当前状态将 `--generator nga` 当作可用能力。

内网接入时只实现该 adapter，并保留上游 IR、parser、prompt、renderer 与 lint 契约。所需环境变量为：

```text
NGA_BASE_URL
NGA_TOKEN
NGA_TIMEOUT_SECONDS
NGA_MAX_RETRIES
```

密钥只能通过环境变量传入，不能写入仓库、样例或运行记录。接口细节见 `docs/内网接入.md`。

## 6. 交接验收与已知边界

### 已在本机 Windows 构造样例/stub 环境验证

- 四格式输入到 Word/Deck 的 stub 全链路、三份 schema 快照、DOCX/PPTX 渲染与 lint。
- 可编辑的 PPTX 基础版式、表格、流程/时间线、图表、架构图、composite 和可编辑 DOCX 标题/表格/代码块/文档头。
- Waitress 本地服务的健康/版本、持久任务、队列、超时、取消、幂等、限流和浏览器双视口流程。

### 必须在内网或目标机完成

1. 在干净断网 Windows + Python 3.12 实跑本文件的安装命令与 `verify.ps1`，并保存命令输出。
2. 提供脱敏真实 `.docx`、`.xlsx`、`.pptx` 各至少 3 份，做解析和生成回归。
3. 实现并验证 NGA 实际协议、认证、超时、重试、脱敏日志和弱模型输出质量。
4. 在 Windows Word/PowerPoint 与实际目标字体/CI 下人工检查字体替换、跨页表格、页眉页脚、元素重叠、可编辑性及视觉观感。
5. 将经审计的 Graphviz Windows 运行时加入 `tools/graphviz/`；没有它时，架构图仍可渲染但会降级为 fallback 布局。

DeckIR 2.0 已支持经 AssetManifest 安全规范化的真实图片、图文页和图片网格；AI 生图默认禁用。精确 Gantt 和地图版式未实现。自动 lint 和本机预览不能替代上述真实环境验收。
