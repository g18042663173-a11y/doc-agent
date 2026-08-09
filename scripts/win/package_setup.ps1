# 一键安装程序：从现有便携 ZIP 编译 Inno Setup 安装包
# 用法：.\scripts\win\package_setup.ps1 [-Zip <path>] [-Iscc <path>] [-Overwrite]

param(
    [string]$Zip = "",
    [string]$Iscc = "",
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $RepoRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "缺少 .venv。请先运行 .\bootstrap_windows.ps1 完成环境准备。"
}

$version = (Get-Content -Raw (Join-Path $RepoRoot "VERSION")).Trim()
$zipPath = if ($Zip -ne "") { $Zip } else { Join-Path $RepoRoot "dist\document-workbench-windows-x64-$version.zip" }
if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
    throw "便携 ZIP 不存在：$zipPath。请先运行 .\scripts\win\build_all.ps1 生成发布包。"
}

Write-Step "编译 Inno Setup 安装程序"
$installerArgs = @(
    "scripts\package_installer.py",
    "--zip", $zipPath
)
if ($Iscc -ne "") { $installerArgs += @("--iscc", $Iscc) }
if ($Overwrite) { $installerArgs += "--overwrite" }
& $Python @installerArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "安装程序完成"
Write-Host "产物：dist\HuaweiDocumentGenerator-Setup-$version.exe + .exe.sha256"
Write-Host "验收：见 docs\WINDOWS_ACCEPTANCE_20260806.md 第五步附加"
exit 0
