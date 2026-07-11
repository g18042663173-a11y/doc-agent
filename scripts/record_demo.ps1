$ErrorActionPreference = "Stop"

python (Join-Path $PSScriptRoot "record_demo.py") @args
exit $LASTEXITCODE
