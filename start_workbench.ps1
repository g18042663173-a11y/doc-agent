param(
    [int]$Port = 5056,
    [string]$WorkDir = "output\web_api"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RuntimeDir = Join-Path $RepoRoot "output\workbench"
$PidFile = Join-Path $RuntimeDir "workbench.pid"
$StdoutLog = Join-Path $RuntimeDir "workbench.stdout.log"
$StderrLog = Join-Path $RuntimeDir "workbench.stderr.log"
$WorkDirPath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $WorkDir))
$HealthUrl = "http://127.0.0.1:$Port/api/health"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository virtual environment is missing. Run .\bootstrap_windows.ps1 first."
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
    $ExistingPid = 0
    if ([int]::TryParse((Get-Content -Raw -LiteralPath $PidFile).Trim(), [ref]$ExistingPid)) {
        $Existing = Get-CimInstance Win32_Process -Filter "ProcessId = $ExistingPid" -ErrorAction SilentlyContinue
        if ($null -ne $Existing) {
            if ($Existing.ExecutablePath -ne $Python -or $Existing.CommandLine -notmatch "app\.web_api") {
                throw "PID file points to a process not owned by this workbench: $ExistingPid"
            }
            Write-Output "Workbench is already running: $HealthUrl"
            exit 0
        }
    }
    Remove-Item -LiteralPath $PidFile -Force
}

$Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($null -ne $Listener) {
    throw "Port $Port is already in use. Stop the existing service or choose another port."
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = Join-Path $RepoRoot "backend"

$Arguments = @(
    "-m",
    "app.web_api",
    "--host",
    "127.0.0.1",
    "--port",
    $Port.ToString(),
    "--work-dir",
    ('"' + $WorkDirPath + '"')
)
$Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
$Process.Id.ToString() | Set-Content -LiteralPath $PidFile -Encoding ascii

$Ready = $false
for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
    Start-Sleep -Milliseconds 500
    if ($Process.HasExited) {
        break
    }
    try {
        $Health = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2
        if ($Health.ready -eq $true) {
            $Ready = $true
            break
        }
    } catch {
        continue
    }
}

if (-not $Ready) {
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    throw "Workbench did not become ready. Review $StderrLog"
}

Write-Output "Workbench started: http://127.0.0.1:$Port/static/index.html"
Write-Output "Health: $HealthUrl"
Write-Output "PID: $($Process.Id)"
