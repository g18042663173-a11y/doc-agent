#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d "$ROOT_DIR/wheelhouse" ]; then
  echo "Missing wheelhouse/. Use scripts/export-runtime-bundle.sh on a matching internet machine first." >&2
  exit 1
fi

if [ ! -f "$ROOT_DIR/ppt-agent-frontend/dist/index.html" ]; then
  echo "Missing ppt-agent-frontend/dist/index.html. Use scripts/export-runtime-bundle.sh first." >&2
  exit 1
fi

OFFLINE=1 SKIP_FRONTEND=1 REQUIREMENTS_FILE=requirements-runtime.txt "$ROOT_DIR/scripts/setup.sh"

cat <<EOF
Runtime setup complete.

Start the app with:
  scripts/start-backend.sh

Then open:
  http://127.0.0.1:8000/

The backend will serve the built frontend from ppt-agent-frontend/dist.
EOF
