# Windows 迁移与继续开发指南

本指南对应由 `scripts/package_windows_dev.py` 生成的 Windows 开发快照。该快照用于把当前项目从 Mac 带入内网 Windows，并在解压后继续开发、测试和生成 DOCX/PPTX。

## 1. 包的边界

压缩包默认包含：

- 当前工作树中的源码、测试、Schema、样例、文档和脚本，包含尚未提交但位于项目目录内的源码；
- `wheelhouse/` 中面向 CPython 3.12 / Windows x64 的离线 Python 依赖；
- 经脱敏的 `.git/` 元数据，用于保留当前分支、提交历史和未提交工作树状态；
- 根目录 `MIGRATION_PACKAGE_MANIFEST.json`，记录包内文件 SHA-256、来源提交、分支和打包时的 `git status`。

压缩包刻意不包含：

- `output/`、`.venv/`、`.pytest_cache/`、`.ruff_cache/`、`__pycache__/` 和覆盖率文件；它们均可在 Windows 再生成；
- `.env*`、证书/私钥文件，以及 `.git/config`、Git hooks 和 reflog；密钥、远端 URL、Git 身份必须在内网机器重新配置；
- macOS 的 Graphviz 二进制。架构图自动布局需要另行放入 Windows Graphviz 运行时；
- 任何 NGA token、真实业务文件或模型响应记录。

`wheelhouse/` 已随包带走，但其可安装性仍必须在目标 Windows 真机断网验证。`NGA` 适配器仍是预留接口，不能因包内存在环境变量名就认定真实模型已接通。

## 2. 迁移前检查

在 Mac 端，从仓库根目录重新生成包：

```bash
python scripts/package_windows_dev.py --overwrite
```

输出位于 `dist/`，包含 ZIP 和同名 `.sha256` 文件。先记录 ZIP 的 SHA-256，再通过受控介质传到内网。不要把 ZIP 解压到同步盘、临时目录或已有项目目录上。

## 3. Windows 前置条件

目标环境需要：

1. Windows 10/11 x64。
2. CPython 3.12 x64，命令 `py -3.12 --version` 应返回 `3.12.x`。
3. Git for Windows，用于查看、提交和后续分支开发。
4. PowerShell 5.1 或 7。
5. Microsoft YaHei（`微软雅黑`）和 Arial。项目主题以这两个字体为默认目标；请在目标 Office 中实际检查替换效果。
6. 可选：Microsoft Word / PowerPoint，用于人工终审；LibreOffice 用于 PDF 预览转换。
7. 可选但推荐：经内网审计的 Graphviz Windows 运行时，用于 `architecture_diagram` 和 Mermaid 图的自动布局。

## 4. 在 Windows 解压并验证包完整性

以下 PowerShell 命令假设介质中的 ZIP 位于 `D:\transfer`，开发目录为 `C:\work`。路径可调整，但必须是可写目录。

```powershell
New-Item -ItemType Directory -Force C:\work | Out-Null
Set-Location D:\transfer

# 将输出与同目录 .sha256 文件第一列比较，必须完全相同。
(Get-FileHash .\huawei_document_generator_windows_dev_YYYYMMDD.zip -Algorithm SHA256).Hash
Get-Content .\huawei_document_generator_windows_dev_YYYYMMDD.zip.sha256

Expand-Archive -LiteralPath .\huawei_document_generator_windows_dev_YYYYMMDD.zip -DestinationPath C:\work -Force
Set-Location C:\work\huawei_document_generator_windows_dev_YYYYMMDD

# 确认包没有漏文件，且本地 Git 工作树可读。
Get-Content .\MIGRATION_PACKAGE_MANIFEST.json -Encoding UTF8
git status --short
git log -1 --oneline
```

首次解压后不要执行 `git clean`、`git reset --hard` 或覆盖式 checkout。包可能携带有意保留的未提交源码；先检查 `git status` 与 `MIGRATION_PACKAGE_MANIFEST.json` 的 `working_tree_status`，确认后做一次内网基线提交。包内生成的 `.git/info/exclude` 会忽略 `MIGRATION_PACKAGE_MANIFEST.json` 本身，因此它不会干扰这个比对。

由于 `.git/config` 没有随包转移，请在确认仓库状态后配置 Windows 本机身份和内网远端：

```powershell
git config user.name "你的姓名"
git config user.email "你的内网邮箱"
# 获得内网仓库地址后再执行：
# git remote add origin <内网 Git 地址>
```

## 5. 断网安装 Python 依赖

所有命令均在仓库根目录执行。建议不要修改系统级 Python 包。

```powershell
.\bootstrap_windows.ps1
.\verify.ps1
```

`bootstrap_windows.ps1` 固定调用 `py -3.12` 创建 `.venv`,并使用
`.venv\Scripts\python.exe` 从 Windows lock/wheelhouse 离线安装。`verify.ps1` 强制
UTF-8、`PYTHONPATH=backend` 和 Python 3.12,不会落到系统默认 Python 3.14。两者都会
写出 `output/environment_report.json`。通过条件包括 Schema 快照、四格式 stub 端到端
链路、DOCX/PPTX lint、离线依赖闭包 dry-run 和覆盖率门槛。Windows 真机的首次通过
结果应保存到内网验收记录。

若 PowerShell 阻止本地脚本，仅对当前进程使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\verify.ps1
```

## 6. Graphviz、字体与 Office 人工终审

Python 的 `graphviz` wheel 不包含 `dot.exe`。若需要架构图、Mermaid 图的 Graphviz 自动布局，把经内网安全审计的 Windows Graphviz 运行时放到：

```text
tools\graphviz\bin\dot.exe
```

然后在当前 PowerShell 会话设置路径并确认：

```powershell
$env:PATH = "$(Join-Path $PWD 'tools\graphviz\bin');$env:PATH"
dot -V
```

没有 `dot.exe` 时，PPT 的 `architecture_diagram` 会回退到确定性布局并报告 warning；其它 Word/PPT 渲染链路不应因此中断。请在 Windows Word/PowerPoint 中重新检查：中文字体替换、页眉页脚、跨页表格、图表标签、节点文字、重叠、裁切和可编辑性。Mac lint 绿灯不等于 Office 视觉终审通过。

## 7. 继续开发的常用入口

```powershell
# 运行完整自动测试
$env:PYTHONPATH = (Join-Path $PWD "backend")
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe scripts/verify.py

# 默认 stub 生成 Word / Deck 的端到端样例
.\.venv\Scripts\python.exe scripts/demo_e2e.py samples/input/quarterly_report.md --target word --generator stub --output-dir output/demo-word
.\.venv\Scripts\python.exe scripts/generate.py samples/input/quarterly_report.md --generator stub --depth 标准 --lint --output-dir output/demo-deck
.\.venv\Scripts\python.exe scripts/generate.py samples/input/quarterly_report.md --generator stub --depth 标准 --template C:\path\template.pptx --lint --output-dir output/demo-template-deck

# 本地 Web UI（默认仅监听本机）
.\start_workbench.ps1
# 停止
.\stop_workbench.ps1
```

工作台地址为 `http://127.0.0.1:5056/static/index.html`。正式服务使用 Waitress、固定监听
`127.0.0.1`，提供健康/版本探测、持久任务恢复、取消、限流和 24 小时产物保留。模板任务会
额外提供 profile、plan、structure、replacement-audit、package-report 与 lint 审计下载。

真实 NGA 接入只能在 `backend/app/generators/nga.py` 实现，并且 token 仅经环境变量传入。当前 `NgaGenerator` 会明确抛出 `NotImplementedError`，这是预期的内网待办而非安装故障。

## 8. 打包后的自检清单

在 Windows 首次完成迁移后，至少确认：

1. `git status --short` 与包内 manifest 一致，当前分支和最近提交可读。
2. `.\.venv\Scripts\python.exe -m pytest backend/tests -q` 与 `.\verify.ps1` 均为零失败。
3. `output/environment_report.json` 中的 Graphviz 版本、SHA-256 和 fallback 状态与实际部署一致。
4. Word 和 PowerPoint 能打开 stub 生成产物，中文显示、页眉页脚和可编辑形状正常。
5. 真实脱敏 `.md/.docx/.xlsx/.pptx` 解析、真实 NGA 协议、Windows 离线安装和视觉终审均单独记录，不得标为 Mac 阶段已完成。

更完整的内网接入边界、NGA 替换点和验收要求见 `DEPLOY_AND_USAGE.md` 与 `docs/内网接入.md`。
