#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "Missing .venv. Run scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/outputs"

HOST_VALUE="${HOST:-${API_HOST:-127.0.0.1}}"
PORT_VALUE="${PORT:-${API_PORT:-8000}}"

ARGS=(app.api:app --host "$HOST_VALUE" --port "$PORT_VALUE")
if [ "${RELOAD:-0}" = "1" ]; then
  ARGS+=(--reload)
fi

exec "$VENV_PY" -m uvicorn "${ARGS[@]}" "$@"
