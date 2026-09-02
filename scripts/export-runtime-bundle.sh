#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v zip >/dev/null 2>&1; then
  echo "zip is required to create a runtime archive." >&2
  exit 1
fi

find_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then
    printf '%s\n' "$PYTHON_BIN"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi
  return 1
}

PYTHON_EXEC="$(find_python)" || {
  echo "Python >= 3.11 is required but was not found." >&2
  exit 1
}

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the frontend dist." >&2
  exit 1
fi

"$PYTHON_EXEC" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python >= 3.11 is required.")
PY

REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements-runtime.txt}"
REQUIREMENTS_PATH="$ROOT_DIR/$REQUIREMENTS_FILE"
if [ ! -f "$REQUIREMENTS_PATH" ]; then
  echo "Requirements file not found: $REQUIREMENTS_FILE" >&2
  exit 1
fi

rm -rf "$ROOT_DIR/wheelhouse"
mkdir -p "$ROOT_DIR/wheelhouse"
"$PYTHON_EXEC" -m pip wheel -r "$REQUIREMENTS_PATH" -w "$ROOT_DIR/wheelhouse"

(
  cd "$ROOT_DIR/ppt-agent-frontend"
  npm ci
  npm run build
)

RELEASE_DIR="${RELEASE_DIR:-$ROOT_DIR/release}"
ARCHIVE_NAME="${1:-doc-agent-mvp-runtime-$(date +%Y%m%d-%H%M%S).zip}"
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
  "ppt-agent-frontend/node_modules/*"
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
