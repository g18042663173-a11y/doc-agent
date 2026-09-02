#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to export image tarballs." >&2
  exit 1
fi

RELEASE_DIR="${RELEASE_DIR:-$ROOT_DIR/release}"
ARCHIVE_NAME="${1:-doc-agent-mvp-docker-images-$(date +%Y%m%d-%H%M%S).tar}"
ARCHIVE_PATH="$RELEASE_DIR/$ARCHIVE_NAME"
mkdir -p "$RELEASE_DIR"

docker compose build
docker save doc-agent-mvp-backend:latest doc-agent-mvp-frontend:latest -o "$ARCHIVE_PATH"

cat <<EOF
Created $ARCHIVE_PATH

On the intranet machine:
  docker load -i $ARCHIVE_NAME
  docker compose up -d
EOF
