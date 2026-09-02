param(
  [string]$HostName = $(if ($env:HOST) { $env:HOST } elseif ($env:API_HOST) { $env:API_HOST } else { "127.0.0.1" }),
  [int]$Port = $(if ($env:PORT) { [int]$env:PORT } elseif ($env:API_PORT) { [int]$env:API_PORT } else { 8000 }),
  [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

function Resolve-DocAgentPython {
  $candidates = @(
    (Join-Path $Root "runtime\python\python.exe"),
    (Join-Path $Root ".runtime\python\python.exe"),
    (Join-Path $Root ".venv\Scripts\python.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }
  $command = Get-Command python -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }
  throw "Python was not found. Use a Windows runtime package or run scripts\setup-runtime.ps1 first."
}

$Python = Resolve-DocAgentPython

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

New-Item -ItemType Directory -Force -Path "data", "outputs" | Out-Null

if (-not (Test-Path "ppt-agent-frontend\dist\index.html")) {
  Write-Warning "ppt-agent-frontend\dist is missing. The backend API can start, but the web UI will return 404."
}

$env:PYTHONDONTWRITEBYTECODE = "1"
$url = "http://${HostName}:${Port}/"

if ($OpenBrowser) {
  Start-Job -ScriptBlock {
    param($target)
    Start-Sleep -Seconds 2
    Start-Process $target
  } -ArgumentList $url | Out-Null
}

Write-Host "Starting Doc Agent..."
Write-Host "Open: $url"
& $Python -m uvicorn app.api:app --host $HostName --port "$Port"
