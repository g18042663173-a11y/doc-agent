# Windows 一键脚本入口

> 面向 Windows 目标机的一键操作：验证 → 打包 → 安装程序 → 启动工作台。
> 在 PowerShell 中执行（右键"使用 PowerShell 运行"即可）。

## 首次准备（一次性）

```powershell
.\bootstrap_windows.ps1        # 建 .venv + 装依赖（Python 3.12）
```

## 日常使用

| 操作 | 命令 | 说明 |
| --- | --- | --- |
| **完整验证** | `.\scripts\win\verify_all.ps1` | verify 门禁 + 可靠性报告 + 本轮专项 + ruff |
| **完整验证（含浏览器 UI）** | `.\scripts\win\verify_all.ps1 -Ui` | 需要 `requirements-dev-ui.txt` |
| **打包便携 ZIP** | `.\scripts\win\build_all.ps1` | WPF 测试 + Release 构建 + 便携 ZIP |
| **打包（自定义运行时）** | `.\scripts\win\build_all.ps1 -PythonEmbed <zip> -GraphvizRoot <path>` | 缺省时自动用默认路径 |
| **打包安装程序** | `.\scripts\win\package_setup.ps1` | 需 Inno Setup 6 + 已有 ZIP；生成 Setup.exe |
| **启动浏览器工作台** | `.\scripts\win\start_workbench_ui.ps1` | 启动 5056 浏览器版 |
| **停止浏览器工作台** | `.\stop_workbench.ps1` | 关闭服务 |

## 典型流程

```powershell
# 1. 改完代码先验证
.\scripts\win\verify_all.ps1

# 2. 打包发布（ZIP 绿色版）
.\scripts\win\build_all.ps1

# 3. 打包安装程序（正式安装版，需 Inno Setup 6）
.\scripts\win\package_setup.ps1 -Overwrite

# 4. 浏览器快速查看
.\scripts\win\start_workbench_ui.ps1
# 打开 http://127.0.0.1:5056/static/index.html
```

## 桌面端（推荐日常分发）

不想用浏览器？直接双击便携包解压后的 `DocumentWorkbench.exe`，或安装程序装完后双击桌面图标。

详细验收步骤见 `docs/WINDOWS_ACCEPTANCE_20260806.md`。
