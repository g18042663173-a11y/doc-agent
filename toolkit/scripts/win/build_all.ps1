# 一键完整打包：WPF 原生测试 + 便携 ZIP 发布包
# 用法：.\scripts\win\build_all.ps1 [-PythonEmbed <zip>] [-GraphvizRoot <path>]

param(
    [string]$PythonEmbed = "",
    [string]$GraphvizRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $RepoRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Dotnet = Join-Path $env:LOCALAPPDATA "Codex\dotnet-sdk-8.0.423\dotnet.exe"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "缺少 .venv。请先运行 .\bootstrap_windows.ps1 完成环境准备。"
}

Write-Step "步骤 1/3：WPF 原生测试（xUnit/FlaUI）"
if (-not (Test-Path -LiteralPath $Dotnet -PathType Leaf)) {
    throw "缺少 .NET SDK 8.0.423：$Dotnet。请先按 docs/内网接入.md 准备 .NET SDK。"
}
& $Dotnet test desktop\DocumentWorkbench.Tests\DocumentWorkbench.Tests.csproj -c Debug
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "步骤 2/3：WPF Release 构建"
& $Dotnet publish desktop\DocumentWorkbench\DocumentWorkbench.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "步骤 3/3：便携 ZIP 发布包"
$packageArgs = @(
    "scripts\package_document_workbench.py",
    "--overwrite"
)
if ($PythonEmbed -ne "") { $packageArgs += @("--python-embed", $PythonEmbed) }
if ($GraphvizRoot -ne "") { $packageArgs += @("--graphviz-root", $GraphvizRoot) }
& $Python @packageArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "打包完成"
$version = (Get-Content -Raw (Join-Path $RepoRoot "VERSION")).Trim()
Write-Host "产物：dist\document-workbench-windows-x64-$version.zip + .sha256"
Write-Host "下一步（安装程序）：.\scripts\win\package_setup.ps1"
exit 0
