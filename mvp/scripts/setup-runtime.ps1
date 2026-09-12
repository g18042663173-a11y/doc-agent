param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not (Test-Path "wheelhouse")) {
  throw "Missing wheelhouse/. Build a runtime bundle on a matching internet machine first."
}

if (-not (Test-Path "ppt-agent-frontend\dist\index.html")) {
  throw "Missing ppt-agent-frontend\dist\index.html. Build a runtime bundle first."
}

powershell -ExecutionPolicy Bypass -File "scripts\setup.ps1" -Offline -SkipFrontend -Python $Python -Requirements "requirements-runtime.txt"

Write-Host "Runtime setup complete."
Write-Host "Start the app with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1"
Write-Host "Then open:"
Write-Host "  http://127.0.0.1:8000/"
