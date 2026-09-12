# 安装程序设计（Inno Setup，用户目录免提权）

设计日期: 2026-08-06
状态: 待评审
目标: 把"更多人分发"的交付从"ZIP 解压双击"升级为"双击安装包 → 桌面/开始菜单快捷方式 → 点图标即用"，保持现有可审计打包链路不变。

## 1. 背景与决策

- 现有交付是 `document-workbench-windows-x64-<VERSION>.zip`：解压后双击
  `DocumentWorkbench.exe` 即可（自带 .NET / Python 3.12 embed / Graphviz /
  锁定 wheel），已是"点开即用"，但多了一步解压。
- 目标用户：部门/更多人分发；安装到**用户目录免管理员权限**。
- 选型：**Inno Setup 6**（免费、成熟、Windows 内网通用、支持用户目录安装与
  卸载注册）。不考虑 MSI（需提权/企业策略复杂）与 NSIS（脚本晦涩）。
- 保留现有 ZIP 作为"绿色版"，安装程序作为"正式安装版"；二者同源（同一
  `package_document_workbench.py` 产物），不是两套体系。

## 2. 安装行为

- **安装位置**：`%LOCALAPPDATA%\Programs\HuaweiDocumentGenerator\<VERSION>`，
  用户可写，免管理员。
- **快捷方式**：桌面与开始菜单 → `<安装目录>\DocumentWorkbench.exe`；
  图标沿用现有 `desktop/DocumentWorkbench/Assets/app-icon.ico`。
- **卸载**：注册到"添加或删除程序"（当前用户），运行
  `<安装目录>\unins000.exe`，清理安装目录、快捷方式与（可选）任务/设置目录。
- **首次启动**：现有 WPF 逻辑不变——启动隐藏后端、绑定 127.0.0.1 随机端口、
  `X-Workbench-Session` 随机令牌；Token 仍走 Windows Credential Manager。
- **升级**：新版安装包默认替换旧安装目录（保留 `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json`、jobs、凭据）。

## 3. 打包流程（复用现有链路）

```
package_document_workbench.py  →  dist/document-workbench-windows-x64-<V>.zip
                                     ↓ 解压到临时目录
package_installer.py（新）  →  确认 Inno Setup ISCC.exe 存在
                              →  读取 VERSION / 产物路径
                              →  ISCC 编译 installer.iss
                                     ↓
              dist\HuaweiDocumentGenerator-Setup-<VERSION>.exe
              dist\HuaweiDocumentGenerator-Setup-<VERSION>.exe.sha256
```

- `package_installer.py` **不重复打包逻辑**，只负责：找到现有 ZIP、解压、
  调用 Inno 编译器、写 SHA-256。ZIP 与 Setup 可分别交付。
- Inno Setup 运行时（`ISCC.exe`）需随项目携带或从 `Program Files` 读取；
  纳入 `runtime-manifest.json` 之外的安装程序清单（安装器版本、ISCC 哈希）。
- 中文界面：`ShowLanguageDialog=yes` + 中文安装向导。

## 4. 关键 Inno Setup 配置要点

- `PrivilegesRequired=lowest`（免提权，装用户目录）。
- `DefaultDirName={localappdata}\Programs\HuaweiDocumentGenerator\{#AppVersion}`。
- `DefaultGroupName=文档生成工作台`。
- `OutputDir=dist`、`OutputBaseFilename=HuaweiDocumentGenerator-Setup-<VERSION>`。
- `[Files]` 递归包含解压后的便携目录（`app/`、`runtime/`、`DocumentWorkbench.exe`、
  `runtime-manifest.json`、`file-hashes.json`、`README.txt`、
  `THIRD_PARTY_NOTICES.md`）。
- `[Icons]`：桌面与开始菜单，工作目录设为安装目录。
- `[Run]`：可选"安装完成后立即运行"。
- `[UninstallDelete]`：清理安装目录；**不**删 `%LOCALAPPDATA%\HuaweiDocumentGenerator`
  （设置/任务/凭据跨版本保留）。

## 5. 签名（暂挂）

- `SigntoolOptions` 预留在 `installer.iss`，但**内网代码签名证书未到位前不启用**。
  Setup.exe 与 ZIP 的 SHA-256 清单照常生成，保证可追溯。
- 启用条件：内网签名证书 + 时间戳服务到位后，`package_installer.py` 加
  `--sign-pfx` / `--sign-thumbprint` 参数，ISCC 传 `/Ssigntool`。

## 6. 安全与边界

- 不改动 WPF / 后端 / API 的任何运行时逻辑；只新增"分发载体"。
- 安装程序只写用户目录，不写注册表敏感项（仅卸载信息写
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`）。
- 离线分发：Setup.exe 单文件、无网络依赖，内网 U 盘/共享盘直传。

## 7. 验收步骤（Windows 目标机）

1. 构建 ZIP 便携包（现有命令）。
2. `.\.venv\Scripts\python.exe scripts\package_installer.py` → 生成 Setup.exe + SHA-256。
3. 干净用户目录（无旧安装）双击 Setup.exe：中文向导 → 用户目录 → 桌面/开始菜单出现图标。
4. 双击桌面图标：WPF 正常启动、能生成 Stub Word/PPT。
5. "添加或删除程序"确认有"文档生成工作台 <VERSION>"；卸载后安装目录清空、
  `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json` 保留。
6. 干净断网机器重复 1-5，记录日志与截图作为交付证据。

## 8. 非目标

- 不打包成单文件 exe（PyInstaller）：会破坏"逐文件哈希可审计"的交付证据链，
  且每次启动解压 100MB+。
- 不改 `DocumentWorkbench.exe` 的启动/后端生命周期逻辑。
- 不写企业级 MSI / GPO 部署。
