#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/ppt-agent-frontend"
cd "$FRONTEND_DIR"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Missing ppt-agent-frontend/node_modules. Run scripts/setup.sh first." >&2
  exit 1
fi

if [ ! -f "$FRONTEND_DIR/.env" ]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
fi

HOST_VALUE="${HOST:-127.0.0.1}"
PORT_VALUE="${PORT:-3000}"
VITE_BIN="$FRONTEND_DIR/node_modules/.bin/vite"

exec "$VITE_BIN" --host "$HOST_VALUE" --port "$PORT_VALUE" "$@"
