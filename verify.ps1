$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository virtual environment is missing. Run .\bootstrap_windows.ps1 first."
}

$Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($Version.Trim() -ne "3.12") {
    throw "Expected Python 3.12 in .venv, found $Version. Recreate it with .\bootstrap_windows.ps1."
}

$BundledGraphviz = Join-Path $RepoRoot "tools\graphviz\bin"
if (Test-Path -LiteralPath (Join-Path $BundledGraphviz "dot.exe") -PathType Leaf) {
    $env:PATH = $BundledGraphviz + [System.IO.Path]::PathSeparator + $env:PATH
} elseif (Test-Path -LiteralPath "C:\Program Files\Graphviz\bin\dot.exe" -PathType Leaf) {
    $env:PATH = "C:\Program Files\Graphviz\bin" + [System.IO.Path]::PathSeparator + $env:PATH
}

if (-not $env:PYTHONPATH) {
    $env:PYTHONPATH = Join-Path $RepoRoot "backend"
} else {
    $env:PYTHONPATH = (Join-Path $RepoRoot "backend") + [System.IO.Path]::PathSeparator + $env:PYTHONPATH
}

# Equivalent acceptance entrypoint: python scripts/verify.py
& $Python scripts/environment_report.py --output output/environment_report.json
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& $Python scripts/verify.py
exit $LASTEXITCODE
