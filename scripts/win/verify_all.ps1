# 一键完整验证：verify.ps1 + 可靠性报告（可选 UI）+ 本轮专项测试
# 用法：.\scripts\win\verify_all.ps1 [-Ui]

param(
    [switch]$Ui
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
Set-Location $RepoRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "缺少 .venv。请先运行 .\bootstrap_windows.ps1 完成环境准备。"
}

Write-Step "步骤 1/4：verify.ps1 一键门禁"
& (Join-Path $RepoRoot "verify.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "步骤 2/4：可靠性测试（pytest 全量 + JUnit/HTML 报告）"
# Step 1 has already run the offline C0 gate. Do not run it again inside the
# reliability wrapper; this keeps the four gates non-overlapping.
$reliabilityArgs = @("scripts\reliability_test.py", "--skip-verify")
if ($Ui) { $reliabilityArgs += "--ui" }
& $Python @reliabilityArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "步骤 3/4：本轮新增专项测试（命名主题 + auto 降级 + NGA CLI）"
& $Python -m pytest `
    backend\tests\test_theme_presets.py `
    backend\tests\test_auto_fallback.py `
    backend\tests\test_nga_generator.py `
    -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Step "步骤 4/4：代码质量检查（ruff）"
$ruff = Join-Path $RepoRoot ".venv\Scripts\ruff.exe"
if (Test-Path -LiteralPath $ruff -PathType Leaf) {
    & $ruff check backend scripts
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "跳过 ruff：未安装开发质量依赖（可选：python -m pip install -r requirements-dev-quality.txt）"
}

Write-Step "全部验证通过"
Write-Host "下一步（打包）：.\scripts\win\build_all.ps1"
exit 0
