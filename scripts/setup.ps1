param(
  [switch]$SkipFrontend,
  [switch]$Offline,
  [string]$Python = "python",
  [string]$Requirements = "requirements.txt"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python >= 3.11 is required.')"

if (-not (Test-Path ".venv")) {
  & $Python -m venv .venv
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

$RequirementsPath = Join-Path $Root $Requirements
if (-not (Test-Path $RequirementsPath)) {
  throw "Requirements file not found: $Requirements"
}

if ($Offline) {
  if (-not (Test-Path "wheelhouse")) {
    throw "Offline install requested, but wheelhouse/ was not found."
  }
  & $VenvPython -m pip install --no-index --find-links "$Root\wheelhouse" -r $RequirementsPath
} else {
  & $VenvPython -m pip install --upgrade pip setuptools wheel
  & $VenvPython -m pip install -r $RequirementsPath
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

New-Item -ItemType Directory -Force -Path "data", "outputs" | Out-Null

if (-not $SkipFrontend) {
  Push-Location "ppt-agent-frontend"
  if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
  }
  if (Test-Path "package-lock.json") {
    npm ci
  } else {
    npm install
  }
  Pop-Location
}

Write-Host "Setup complete."
Write-Host "Backend:  powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1"
Write-Host "Frontend: powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1"
