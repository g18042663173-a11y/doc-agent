from __future__ import annotations
# ruff: noqa: E402

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.demo_e2e import main


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if not arguments:
        raise SystemExit("usage: generate.py <input_file> [options]")
    raise SystemExit(main([arguments[0], "--target", "deck", *arguments[1:]]))
