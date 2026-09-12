$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PidFile = Join-Path $RepoRoot "output\workbench\workbench.pid"

if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) {
    Write-Output "Workbench is not running: PID file is absent."
    exit 0
}

$ProcessId = 0
if (-not [int]::TryParse((Get-Content -Raw -LiteralPath $PidFile).Trim(), [ref]$ProcessId)) {
    throw "Workbench PID file is invalid: $PidFile"
}

$Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
if ($null -eq $Process) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Output "Removed stale workbench PID file."
    exit 0
}
if ($Process.ExecutablePath -ne $Python -or $Process.CommandLine -notmatch "app\.web_api") {
    throw "Refusing to stop PID $ProcessId because it is not the repository workbench process."
}

$OwnedProcesses = @($Process)
$PendingParents = @($ProcessId)
while ($PendingParents.Count -gt 0) {
    $ParentId = $PendingParents[0]
    $PendingParents = @($PendingParents | Select-Object -Skip 1)
    $Children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" -ErrorAction SilentlyContinue)
    foreach ($Child in $Children) {
        if ([System.IO.Path]::GetFileName($Child.ExecutablePath) -ieq "conhost.exe") {
            continue
        }
        # Descendants of a verified workbench process are owned by it, even when
        # they are helper subprocesses (dot.exe, NGA CLI) whose command line does
        # not contain "app.web_api". Aborting here would leave the tree and PID
        # file behind, so collect them instead of throwing.
        $OwnedProcesses += $Child
        $PendingParents += $Child.ProcessId
    }
}

foreach ($Owned in @($OwnedProcesses | Sort-Object ProcessId -Descending)) {
    Stop-Process -Id $Owned.ProcessId -Force -ErrorAction SilentlyContinue
}
for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
    Start-Sleep -Milliseconds 250
    if ($null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        break
    }
}
if ($null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
    throw "Workbench process $ProcessId did not stop."
}

Remove-Item -LiteralPath $PidFile -Force
Write-Output "Workbench stopped: PID $ProcessId"
