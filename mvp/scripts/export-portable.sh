#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to create a portable archive." >&2
  exit 1
fi

RELEASE_DIR="${RELEASE_DIR:-$ROOT_DIR/release}"
ARCHIVE_NAME="${1:-doc-agent-mvp-portable-$(date +%Y%m%d-%H%M%S).zip}"
ARCHIVE_PATH="$RELEASE_DIR/$ARCHIVE_NAME"
mkdir -p "$RELEASE_DIR"

EXCLUDES=(
  ".env"
  "*/.env"
  ".DS_Store"
  "*.pyc"
  "*.pyo"
  "*.tsbuildinfo"
  "__pycache__/*"
  "*/__pycache__/*"
  ".venv/*"
  ".pytest_cache/*"
  ".runtime/*"
  ".e2e-data/*"
  "htmlcov/*"
  ".coverage"
  "release/*"
  "wheelhouse/*"
  "ppt-agent-frontend/node_modules/*"
  "ppt-agent-frontend/dist/*"
  "ppt-agent-frontend/playwright-report/*"
  "ppt-agent-frontend/test-results/*"
  "ppt-agent-frontend/coverage/*"
)

if [ "${INCLUDE_DATA:-0}" != "1" ]; then
  EXCLUDES+=("data/*")
else
  echo "Including data/. Keep data/users/.encryption_key with user JSON files."
fi

if [ "${INCLUDE_OUTPUTS:-0}" != "1" ]; then
  EXCLUDES+=("outputs/*")
fi

ZIP_ARGS=()
for pattern in "${EXCLUDES[@]}"; do
  ZIP_ARGS+=("-x" "$pattern")
done

zip -r "$ARCHIVE_PATH" . "${ZIP_ARGS[@]}"
echo "Created $ARCHIVE_PATH"
