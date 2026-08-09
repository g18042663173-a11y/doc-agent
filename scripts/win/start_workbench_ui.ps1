# 一键启动浏览器工作台
# 用法：.\scripts\win\start_workbench_ui.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $RepoRoot

& (Join-Path $RepoRoot "start_workbench.ps1")
