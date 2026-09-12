param(
  [string]$Name = "doc-agent-win11-runtime-$(Get-Date -Format yyyyMMdd-HHmmss).zip",
  [string]$Python = "python",
  [string]$PythonVersion = "",
  [ValidateSet("amd64", "arm64", "win32")]
  [string]$Architecture = "amd64",
  [string]$PythonEmbedZip = "",
  [string]$Requirements = "requirements-runtime.txt",
  [switch]$NoDownloadPython,
  [switch]$IncludeData,
  [switch]$IncludeOutputs
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
  throw "This exporter must run on Windows so pip resolves Windows wheels."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm is required on the build machine to create ppt-agent-frontend\dist. The target machine will not need npm."
}

$RequirementsPath = Join-Path $Root $Requirements
if (-not (Test-Path $RequirementsPath)) {
  throw "Requirements file not found: $Requirements"
}

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 'Python >= 3.11 is required.')"
if ($LASTEXITCODE -ne 0) {
  throw "Python >= 3.11 is required on the Windows build machine."
}

if (-not $PythonVersion) {
  $PythonVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
}
$BuilderMajorMinor = & $Python -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')"

Push-Location "ppt-agent-frontend"
npm ci
npm run build
Pop-Location

$ReleaseDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$ArchivePath = Join-Path $ReleaseDir $Name
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "doc-agent-win-runtime-$([System.Guid]::NewGuid().ToString('N'))"
$PackageRoot = Join-Path $TempDir "doc-agent"
$PythonDir = Join-Path $PackageRoot "runtime\python"
New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null

try {
  if ($PythonEmbedZip) {
    if (-not (Test-Path $PythonEmbedZip)) {
      throw "Python embed zip not found: $PythonEmbedZip"
    }
    Expand-Archive -Path $PythonEmbedZip -DestinationPath $PythonDir -Force
  } else {
    if ($NoDownloadPython) {
      throw "No Python embed zip was provided. Pass -PythonEmbedZip or allow the script to download the Python embeddable package."
    }
    $EmbedName = "python-$PythonVersion-embed-$Architecture.zip"
    $EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$EmbedName"
    $EmbedZip = Join-Path $TempDir $EmbedName
    Write-Host "Downloading $EmbedUrl"
    Invoke-WebRequest -Uri $EmbedUrl -OutFile $EmbedZip
    Expand-Archive -Path $EmbedZip -DestinationPath $PythonDir -Force
  }

  $PthFile = Get-ChildItem $PythonDir -Filter "python*._pth" | Select-Object -First 1
  if (-not $PthFile) {
    throw "Python embeddable package is missing python*._pth."
  }
  if ($PthFile.Name -match "python(\d+)._pth") {
    $EmbedMajorMinor = $Matches[1]
    if ($EmbedMajorMinor -ne $BuilderMajorMinor) {
      throw "Builder Python major/minor ($BuilderMajorMinor) must match embedded Python ($EmbedMajorMinor)."
    }
  }

  $pthLines = Get-Content $PthFile.FullName
  $pthLines = $pthLines | Where-Object {
    ($_ -notmatch "^\s*#?\s*import\s+site\s*$") -and
    ($_ -ne "Lib\site-packages") -and
    ($_ -ne "..\..")
  }
  $pthLines += "Lib\site-packages"
  $pthLines += "..\.."
  $pthLines += "import site"
  Set-Content -Path $PthFile.FullName -Value $pthLines -Encoding ASCII

  $SitePackages = Join-Path $PythonDir "Lib\site-packages"
  New-Item -ItemType Directory -Force -Path $SitePackages | Out-Null
  & $Python -m pip install --upgrade pip setuptools wheel
  & $Python -m pip install --no-cache-dir --upgrade --target $SitePackages -r $RequirementsPath

  $ExcludePatterns = @(
    '(^|[\\/])\.env$',
    '(^|[\\/])\.DS_Store$',
    '(^|[\\/])\.venv([\\/]|$)',
    '(^|[\\/])\.pytest_cache([\\/]|$)',
    '(^|[\\/])\.runtime([\\/]|$)',
    '(^|[\\/])\.e2e-data([\\/]|$)',
    '(^|[\\/])htmlcov([\\/]|$)',
    '(^|[\\/])release([\\/]|$)',
    '(^|[\\/])wheelhouse([\\/]|$)',
    '(^|[\\/])node_modules([\\/]|$)',
    '(^|[\\/])coverage([\\/]|$)',
    '(^|[\\/])playwright-report([\\/]|$)',
    '(^|[\\/])test-results([\\/]|$)',
    '\.pyc$',
    '\.pyo$',
    '\.tsbuildinfo$',
    '(^|[\\/])__pycache__([\\/]|$)',
    '^\.coverage$'
  )

  function Copy-FilteredPath {
    param(
      [string]$Source,
      [string]$Destination
    )
    $SourcePath = Join-Path $Root $Source
    if (-not (Test-Path $SourcePath)) {
      return
    }
    if ((Get-Item $SourcePath).PSIsContainer) {
      Get-ChildItem -Path $SourcePath -Force -Recurse -File | ForEach-Object {
        $Relative = [System.IO.Path]::GetRelativePath($Root, $_.FullName)
        $Normalized = $Relative -replace '\\', '/'
        foreach ($Pattern in $ExcludePatterns) {
          if ($Normalized -match $Pattern) {
            return
          }
        }
        $Target = Join-Path $PackageRoot $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent) | Out-Null
        Copy-Item $_.FullName $Target
      }
    } else {
      $Target = Join-Path $PackageRoot $Destination
      New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent) | Out-Null
      Copy-Item $SourcePath $Target
    }
  }

  @(
    "app",
    "doc_agent",
    "templates",
    "examples",
    "scripts",
    "docs",
    "ppt-agent-frontend\dist"
  ) | ForEach-Object { Copy-FilteredPath $_ $_ }

  @(
    ".env.example",
    "README.md",
    "MIGRATION.md",
    "requirements.txt",
    "requirements-runtime.txt",
    "requirements-dev.txt",
    "requirements-optional.txt",
    "pyproject.toml",
    "Start-DocAgent.cmd"
  ) | ForEach-Object { Copy-FilteredPath $_ $_ }

  if ($IncludeData -and (Test-Path "data")) {
    Copy-FilteredPath "data" "data"
  } else {
    New-Item -ItemType Directory -Force -Path (Join-Path $PackageRoot "data") | Out-Null
  }

  if ($IncludeOutputs -and (Test-Path "outputs")) {
    Copy-FilteredPath "outputs" "outputs"
  } else {
    New-Item -ItemType Directory -Force -Path (Join-Path $PackageRoot "outputs") | Out-Null
  }

  Push-Location $PackageRoot
  & (Join-Path $PythonDir "python.exe") -c "import app.api, fastapi, pptx, docx, pydantic; print('portable runtime import check ok')"
  Pop-Location

  if (Test-Path $ArchivePath) {
    Remove-Item $ArchivePath -Force
  }
  Compress-Archive -Path (Join-Path $PackageRoot '*') -DestinationPath $ArchivePath -Force
  Write-Host "Created $ArchivePath"
  Write-Host "On the Windows 11 intranet machine: unzip it, run Start-DocAgent.cmd, then open http://127.0.0.1:8000/."
} finally {
  if (Test-Path $TempDir) {
    Remove-Item $TempDir -Recurse -Force
  }
}
