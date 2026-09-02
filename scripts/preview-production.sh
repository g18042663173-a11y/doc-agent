#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/ppt-agent-frontend"
cd "$ROOT_DIR"

VENV_PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "Missing .venv. Run scripts/setup.sh first." >&2
  exit 1
fi
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Missing ppt-agent-frontend/node_modules. Run scripts/setup.sh first." >&2
  exit 1
fi

BACKEND_PORT="${BACKEND_PORT:-8200}"
FRONTEND_PORT="${FRONTEND_PORT:-3200}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
API_BASE_URL="${VITE_API_BASE_URL:-http://$BACKEND_HOST:$BACKEND_PORT/api}"
RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/.runtime/production-preview}"

mkdir -p "$RUNTIME_DIR/data" "$RUNTIME_DIR/outputs" "$RUNTIME_DIR/logs"

echo "Building frontend with VITE_API_BASE_URL=$API_BASE_URL"
(cd "$FRONTEND_DIR" && VITE_API_BASE_URL="$API_BASE_URL" npm run build)

cleanup() {
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

DATA_DIR="$RUNTIME_DIR/data" \
OUTPUT_DIR="$RUNTIME_DIR/outputs" \
LOG_DIR="$RUNTIME_DIR/logs" \
LLM_PROVIDER="${LLM_PROVIDER:-stub}" \
PPT_RENDERER="${PPT_RENDERER:-stub}" \
PPT_COMPLIANCE_GATE="${PPT_COMPLIANCE_GATE:-warn}" \
CORS_ORIGINS="http://$FRONTEND_HOST:$FRONTEND_PORT" \
"$VENV_PY" -m uvicorn app.api:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

for _ in $(seq 1 60); do
  if "$VENV_PY" - "$BACKEND_HOST" "$BACKEND_PORT" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

host, port = sys.argv[1], sys.argv[2]
with urlopen(f"http://{host}:{port}/health", timeout=1) as response:
    raise SystemExit(0 if response.status == 200 else 1)
PY
  then
    break
  fi
  sleep 1
done

echo "Backend: http://$BACKEND_HOST:$BACKEND_PORT"
echo "Frontend preview: http://$FRONTEND_HOST:$FRONTEND_PORT"
(cd "$FRONTEND_DIR" && ./node_modules/.bin/vite preview --host "$FRONTEND_HOST" --port "$FRONTEND_PORT")
