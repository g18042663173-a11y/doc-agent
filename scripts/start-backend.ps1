param(
  [string]$HostName = $(if ($env:HOST) { $env:HOST } elseif ($env:API_HOST) { $env:API_HOST } else { "127.0.0.1" }),
  [int]$Port = $(if ($env:PORT) { [int]$env:PORT } elseif ($env:API_PORT) { [int]$env:API_PORT } else { 8000 }),
  [switch]$Reload
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  throw "Missing .venv. Run scripts/setup.ps1 first."
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

New-Item -ItemType Directory -Force -Path "data", "outputs" | Out-Null

$ArgsList = @("-m", "uvicorn", "app.api:app", "--host", $HostName, "--port", "$Port")
if ($Reload) {
  $ArgsList += "--reload"
}

& $VenvPython @ArgsList
