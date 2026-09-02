#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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

"$PYTHON_EXEC" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python >= 3.11 is required.")
PY

if [ ! -d "$ROOT_DIR/.venv" ]; then
  "$PYTHON_EXEC" -m venv "$ROOT_DIR/.venv"
fi

VENV_PY="$ROOT_DIR/.venv/bin/python"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements.txt}"
REQUIREMENTS_PATH="$ROOT_DIR/$REQUIREMENTS_FILE"
if [ ! -f "$REQUIREMENTS_PATH" ]; then
  echo "Requirements file not found: $REQUIREMENTS_FILE" >&2
  exit 1
fi

if [ "${OFFLINE:-0}" = "1" ]; then
  if [ ! -d "$ROOT_DIR/wheelhouse" ]; then
    echo "OFFLINE=1 was set, but wheelhouse/ was not found." >&2
    exit 1
  fi
  "$VENV_PY" -m pip install --no-index --find-links "$ROOT_DIR/wheelhouse" -r "$REQUIREMENTS_PATH"
else
  "$VENV_PY" -m pip install --upgrade pip setuptools wheel
  "$VENV_PY" -m pip install -r "$REQUIREMENTS_PATH"
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/outputs"

if [ "${SKIP_FRONTEND:-0}" != "1" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm was not found. Install Node.js/npm or rerun with SKIP_FRONTEND=1." >&2
    exit 1
  fi
  cd "$ROOT_DIR/ppt-agent-frontend"
  if [ ! -f ".env" ]; then
    cp ".env.example" ".env"
  fi
  if [ -f "package-lock.json" ]; then
    npm ci
  else
    npm install
  fi
fi

cat <<EOF
Setup complete.

Backend:
  scripts/start-backend.sh

Frontend:
  scripts/start-frontend.sh

Production preview:
  scripts/preview-production.sh
EOF
