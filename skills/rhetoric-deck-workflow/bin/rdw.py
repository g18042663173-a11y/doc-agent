from __future__ import annotations

from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT))

from engine.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

