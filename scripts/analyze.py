from __future__ import annotations
# ruff: noqa: E402

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.cli.analyze import main


if __name__ == "__main__":
    raise SystemExit(main())
