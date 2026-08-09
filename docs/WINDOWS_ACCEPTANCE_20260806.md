# Windows 验收与人工交付清单（2026-08-06 快照）

> 本文是把本轮全部改动（auto 降级、NGA CLI、命名主题、deck-ir、前置检查、
> 界面优化）在 Windows 目标机上完成验收的可执行清单。自动测试全绿 ≠ 交付通过；
> 下列每一项都需要在 Windows 上产生真实证据。

## 0. 改动快照（本次验收范围）

> **快速执行**：本清单所有手动命令已合并为一键 PowerShell 脚本，
> 见 `scripts/win/README.md`。常用：
> `.\scripts\win\verify_all.ps1`（验证）、`.\scripts\win\build_all.ps1`（打包）、
> `.\scripts\win\package_setup.ps1`（安装程序）。

| 改动 | 位置 | 验证要点 |
| --- | --- | --- |
| auto/strict 生成模式 | `generators/manager.py`、`web_api.py` | 默认 auto；strict 可选；降级标注 fallback |
| NGA CLI 传输 | `generators/nga.py` | `nga run --model -m --format json`；免 Token；NDJSON 解析 |
| NGA HTTP 传输 | 同上 | OpenAI 兼容；Bearer Token |
| 命名主题 ×3 | `rendering/themes/` | hw-report / hw-proposal / hw-academic |
| 主题入口 | CLI/API/前端/WPF | 四入口 + Prompt 注入 |
| deck-ir 受控下载 | `web_api.py` | 产物区可见"结构化内容"下载 |
| 前置 CLI 检查 | `web_api.py` | 提交前 E010，不排队 |
| 引擎指示条 | `static/index.html` | 开始生成上方显示当前引擎 |
| 设置面板 | 前后端 | CLI/HTTP 切换 + 模式 + 主题 |

---

## 第一步：代码级验证（Python 3.12）

在项目根目录打开 PowerShell，先确认 `.venv` 是 Python 3.12：

```powershell
cd C:\Users\GSQ\Desktop\huawei_document_generator_windows_dev_20260728
.\.venv\Scripts\python.exe --version   # 必须是 3.12.x
```

### 1.1 一键门禁

```powershell
.\verify.ps1
```

通过标准：pytest 全绿、parsers/ir/lint 各 ≥80%、整体 ≥70%、四格式 stub E2E 通过、
输出 `C0 verify passed`。

### 1.2 可靠性报告（含工作台 UI）

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev-ui.txt
.\.venv\Scripts\python.exe scripts\reliability_test.py --ui
```

报告在 `output\qa\report.json`；浏览器 1280×900 与 390×844 两视口无溢出/报错。

### 1.3 主题专项（本次新增）

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_theme_presets.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_auto_fallback.py backend\tests\test_nga_generator.py -q
```

预期：三组全绿（14 + 12 + 23+）。

---

## 第二步：工作台功能验收（浏览器 5056）

```powershell
.\start_workbench.ps1
```

打开 `http://127.0.0.1:5056/static/index.html`，逐项：

| # | 操作 | 预期 |
|---|---|---|
| 2.1 | 看"开始生成"上方 | 引擎指示条显示"确定性 Stub（未接入 AI）"，灰色点 |
| 2.2 | 展开"AI 生成设置" | 状态卡、调用方式（CLI 默认）、字段提示、模式开关齐全 |
| 2.3 | 选 Word | 主题下拉框自动禁用 |
| 2.4 | 上传 md → 生成 | 任务完成；审计区含"合规报告"与"结构化内容（DeckIR）"链接 |
| 2.5 | 下载 deck-ir | 是合法 JSON，`meta.theme` 与所选主题一致 |
| 2.6 | 主题选 hw-academic → 生成 | 产物封面/标题为深蓝色系（视觉初判） |
| 2.7 | 主题选 hw-proposal → 生成 | 排版留白更大、强调色更丰富（视觉初判） |

---

## 第三步：NGA 接入（真实内网）

### 3.1 前置（本机 CLI）

```powershell
nga providers login        # 华为账号 OAuth，一次性
nga run "hi" -m w3/GLM-5.1-WX-Auto --format json   # 确认能对话
```

### 3.2 工作台配置

设置 → 调用方式选"本机 NGA 命令行" → CLI 路径 `nga` → 模型
`w3/GLM-5.1-WX-Auto` → 测试连接（应显示延迟）→ 启用生成器。

### 3.3 端到端生成

- 引擎指示条变绿："生成引擎：NGA（w3/GLM-5.1-WX-Auto · 本机命令行 · auto 模式）"
- 用真实脱敏业务文档生成 Word + PPT
- **auto 降级验证**：临时把 CLI 路径改成不存在的值 → 提交任务 → 应**立即**
  返回 E010（stage=preflight），而不是排队后失败；改回后恢复

### 3.4 HTTP 方式（如有 OpenAI 兼容服务）

设置 → 调用方式选"HTTP 服务" → 填 base_url / 接口路径 / 模型 / Token →
测试 → 启用。Token 存 Windows Credential Manager（WPF）或仅内存（浏览器）。

---

## 第四步：三套主题人工视觉签字

在目标 Windows PowerPoint + 目标字体环境下，用同一份业务文档分别生成
hw-report / hw-proposal / hw-academic 三份 PPTX，逐项检查：

- 字体替代是否正常（微软雅黑为主，无黑块/方框）
- 红色只用于标题、编号、箭头、关键数据锚点（学术版以深蓝为主）
- 无文本溢出、无重叠、密级与页码完整
- 三套主题风格差异是否明显、是否符合预期定位

结论记录到 `output\theme-visual-signoff.txt`（评审人、日期、结论），
未签字前保持 `manual_pending`。

---

## 第五步：WPF 桌面端验收

```powershell
$dotnet = "$env:LOCALAPPDATA\Codex\dotnet-sdk-8.0.423\dotnet.exe"
& $dotnet test desktop\DocumentWorkbench.Tests\DocumentWorkbench.Tests.csproj -c Debug
.\.venv\Scripts\python.exe scripts\package_document_workbench.py `
  --python-embed "$env:TEMP\python-3.12.10-embed-amd64.zip" `
  --graphviz-root "C:\Program Files\Graphviz" --overwrite
```

- WPF 测试 3/3、Release 构建 0 warning/0 error
- 便携包 `dist\document-workbench-windows-x64-2.1.0.zip` + SHA-256
- 解压双击 `DocumentWorkbench.exe`：设置 > 常规 有"默认 PPT 主题"下拉；
  NGA 设置有"调用方式"；引擎状态显示当前生成器

### 第五步附加：安装程序验收（新分发方式）

前提：已生成上述 ZIP 便携包。

```powershell
# 一次性安装 Inno Setup 6（https://jrsoftware.org/isdl.php）
.\.venv\Scripts\python.exe scripts\package_installer.py --overwrite
```

预期：`dist\HuaweiDocumentGenerator-Setup-2.1.0.exe` + `.exe.sha256`。

在**干净用户目录**（无旧安装）验收：

1. 双击 Setup.exe：中文向导 → 默认装到 `%LOCALAPPDATA%\Programs\HuaweiDocumentGenerator\2.1.0`，
   免管理员权限。
2. 桌面与开始菜单出现"文档生成工作台"图标。
3. 双击桌面图标：WPF 正常启动、能生成 Stub Word/PPT。
4. "添加或删除程序"有"文档生成工作台 2.1.0"；卸载后安装目录清空、
  `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json` 保留。
5. 干净断网机器重复 1-4，记录日志与截图作为交付证据。

设计文档：`docs/design/INSTALLER_DESIGN.md`（Inno Setup、用户目录免提权、签名待挂）。

---

## 第六步：交付前必办（QUESTIONS.md 既有待办）

| # | 事项 | 证据要求 |
|---|---|---|
| 6.1 | 真实脱敏 docx/xlsx/pptx 各 ≥3 | 放 `samples\input\real\`，记录哈希与来源 |
| 6.2 | PowerPoint 最终审美签字 | 见第四步；业务评审人签字 |
| 6.3 | 授权真实图片语料 | 来源/版权/署名/替代文本记录 |
| 6.4 | 全新 Windows 物理断网安装 | 干净机器 + 发布包 + wheelhouse 离线安装 + verify.ps1，记录日志截图 |
| 6.5 | 真实 NGA 端到端 | 见第三步；协议差异记录（若 Chat Completions 不兼容需新增 adapter） |
| 6.6 | 内网代码签名 | 签名链、SmartScreen、升级后哈希 |

---

## 常见问题

- **`verify.ps1` 报 Python 版本错误**：重跑 `.\bootstrap_windows.ps1` 重建 `.venv`。
- **Graphviz 缺失**：环境报告标记确定性降级；Word/PPT 生成仍可用，
  架构图自动退化为确定性布局（有 warning）。
- **NGA 测试连接失败**：确认 `nga providers login` 已完成；CLI 路径是否正确；
  `nga run` 手工能对话吗。
- **主题下拉不生效**：确认所选主题名在注册表内（hw_v1 / hw-report /
  hw-proposal / hw-academic），非法名 API 返回 E001。
