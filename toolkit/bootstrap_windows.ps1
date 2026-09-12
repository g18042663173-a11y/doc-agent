param(
    [string]$Wheelhouse = "wheelhouse",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$Venv = Join-Path $RepoRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Lock = Join-Path $RepoRoot "requirements-win312.lock"
$WheelhousePath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Wheelhouse))

if ($Recreate -and (Test-Path -LiteralPath $Venv)) {
    $ResolvedVenv = (Resolve-Path -LiteralPath $Venv).Path
    if ($ResolvedVenv -ne (Join-Path $RepoRoot ".venv")) {
        throw "Refusing to remove unexpected virtual environment path: $ResolvedVenv"
    }
    Remove-Item -LiteralPath $ResolvedVenv -Recurse -Force
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    & py -3.12 -m venv $Venv
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.12 virtual environment creation failed."
    }
}

$Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($null -eq $Version -or $Version.Trim() -ne "3.12") {
    throw "Expected Python 3.12 in .venv, found $Version."
}
if (-not (Test-Path -LiteralPath $Lock -PathType Leaf)) {
    throw "Missing requirements lock: $Lock"
}
if (-not (Test-Path -LiteralPath $WheelhousePath -PathType Container)) {
    throw "Missing wheelhouse: $WheelhousePath"
}

& $Python -m pip install --no-index --find-links $WheelhousePath --require-hashes -r $Lock
if ($LASTEXITCODE -ne 0) {
    throw "Offline dependency installation failed."
}

$BundledGraphviz = Join-Path $RepoRoot "tools\graphviz\bin"
$BundledDot = Join-Path $BundledGraphviz "dot.exe"
if (Test-Path -LiteralPath $BundledDot -PathType Leaf) {
    $env:PATH = $BundledGraphviz + [System.IO.Path]::PathSeparator + $env:PATH
    $Dot = $BundledDot
} elseif (Test-Path -LiteralPath "C:\Program Files\Graphviz\bin\dot.exe" -PathType Leaf) {
    $env:PATH = "C:\Program Files\Graphviz\bin" + [System.IO.Path]::PathSeparator + $env:PATH
    $Dot = "C:\Program Files\Graphviz\bin\dot.exe"
} else {
    $DotCommand = Get-Command dot.exe -ErrorAction SilentlyContinue
    $Dot = if ($null -eq $DotCommand) { $null } else { $DotCommand.Source }
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = Join-Path $RepoRoot "backend"

Write-Output "Python: $(& $Python --version)"
Write-Output "Virtual environment: $Venv"
Write-Output "Wheelhouse: $WheelhousePath"
if ($null -eq $Dot) {
    Write-Warning "Graphviz dot.exe was not found; deterministic diagram fallback remains active."
} else {
    Write-Output "Graphviz: $Dot"
    & $Dot -V
}
& $Python scripts/environment_report.py --output output/environment_report.json
if ($LASTEXITCODE -ne 0) {
    throw "Environment report generation failed."
}
Write-Output "Run .\verify.ps1 to execute the full acceptance suite."
