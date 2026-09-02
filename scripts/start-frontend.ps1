param(
  [string]$HostName = $(if ($env:HOST) { $env:HOST } else { "127.0.0.1" }),
  [int]$Port = $(if ($env:PORT) { [int]$env:PORT } else { 3000 })
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Frontend = Join-Path $Root "ppt-agent-frontend"
Set-Location $Frontend

if (-not (Test-Path "node_modules")) {
  throw "Missing node_modules. Run scripts/setup.ps1 first."
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

$Vite = Join-Path $Frontend "node_modules\.bin\vite.cmd"
if (-not (Test-Path $Vite)) {
  $Vite = Join-Path $Frontend "node_modules\.bin\vite"
}

& $Vite --host $HostName --port $Port
