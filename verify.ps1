$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = Join-Path $RepoRoot "backend"
} else {
    $env:PYTHONPATH = (Join-Path $RepoRoot "backend") + [System.IO.Path]::PathSeparator + $env:PYTHONPATH
}

python scripts/verify.py
exit $LASTEXITCODE
