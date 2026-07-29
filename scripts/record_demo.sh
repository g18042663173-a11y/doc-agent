#!/usr/bin/env bash
set -euo pipefail

python "$(dirname "$0")/record_demo.py" "$@"
