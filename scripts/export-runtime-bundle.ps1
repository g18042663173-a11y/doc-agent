param(
  [string]$Name = "doc-agent-mvp-runtime-$(Get-Date -Format yyyyMMdd-HHmmss).zip",
  [string]$Python = "python",
  [string]$Requirements = "requirements-runtime.txt",
  [switch]$IncludeData,
  [switch]$IncludeOutputs
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python >= 3.11 is required.')"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm is required to build the frontend dist."
}

if (Test-Path "wheelhouse") {
  Remove-Item "wheelhouse" -Recurse -Force
}
New-Item -ItemType Directory -Force -Path "wheelhouse" | Out-Null
if (-not (Test-Path $Requirements)) {
  throw "Requirements file not found: $Requirements"
}
& $Python -m pip wheel -r $Requirements -w "wheelhouse"

Push-Location "ppt-agent-frontend"
npm ci
npm run build
Pop-Location

$ReleaseDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$ArchivePath = Join-Path $ReleaseDir $Name
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "doc-agent-mvp-runtime-$([System.Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

$ExcludePatterns = @(
  '^\.env$',
  '(^|[\\/])\.env$',
  '^\.DS_Store$',
  '^\.venv([\\/]|$)',
  '^\.pytest_cache([\\/]|$)',
  '^\.runtime([\\/]|$)',
  '^\.e2e-data([\\/]|$)',
  '^htmlcov([\\/]|$)',
  '^release([\\/]|$)',
  '^ppt-agent-frontend[\\/]node_modules([\\/]|$)',
  '^ppt-agent-frontend[\\/]playwright-report([\\/]|$)',
  '^ppt-agent-frontend[\\/]test-results([\\/]|$)',
  '^ppt-agent-frontend[\\/]coverage([\\/]|$)',
  '\.pyc$',
  '\.pyo$',
  '\.tsbuildinfo$',
  '(^|[\\/])__pycache__([\\/]|$)',
  '^\.coverage$'
)

if (-not $IncludeData) {
  $ExcludePatterns += '^data([\\/]|$)'
} else {
  Write-Host "Including data/. Keep data/users/.encryption_key with user JSON files."
}

if (-not $IncludeOutputs) {
  $ExcludePatterns += '^outputs([\\/]|$)'
}

Get-ChildItem -Force -Recurse -File | ForEach-Object {
  $Relative = [System.IO.Path]::GetRelativePath($Root, $_.FullName)
  $Normalized = $Relative -replace '\\', '/'
  foreach ($Pattern in $ExcludePatterns) {
    if ($Normalized -match $Pattern) {
      return
    }
  }
  $Destination = Join-Path $TempDir $Relative
  New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
  Copy-Item $_.FullName $Destination
}

if (Test-Path $ArchivePath) {
  Remove-Item $ArchivePath -Force
}
Compress-Archive -Path (Join-Path $TempDir '*') -DestinationPath $ArchivePath -Force
Remove-Item $TempDir -Recurse -Force

Write-Host "Created $ArchivePath"
