from __future__ import annotations

import json
from pathlib import Path
from typing import Any


THEMES_DIR = Path(__file__).parent / "themes"


def load_theme(name: str = "hw_v1") -> dict[str, Any]:
    filename = "hw_theme.json" if name == "hw_v1" else f"{name}.json"
    path = THEMES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"theme not found: {name}")
    return json.loads(path.read_text(encoding="utf-8"))
