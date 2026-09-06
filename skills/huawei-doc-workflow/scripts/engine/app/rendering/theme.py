from __future__ import annotations

import json
from pathlib import Path
from typing import Any


THEMES_DIR = Path(__file__).parent / "themes"

# 正式主题注册表：命名主题点名即用；hw_v1 为默认别名（历史兼容）。
THEME_REGISTRY: dict[str, str] = {
    "hw_v1": "hw_v1",
    "hw-report": "hw-report",
    "hw-proposal": "hw-proposal",
    "hw-academic": "hw-academic",
}


def resolve_theme(name: str) -> str:
    """Resolve a theme name against the registry, raising a clear error for unknown names."""
    canonical = THEME_REGISTRY.get(name)
    if canonical is None:
        available = ", ".join(sorted(THEME_REGISTRY))
        raise UnknownThemeError(f"unknown theme {name!r}; available: {available}")
    return canonical


class UnknownThemeError(ValueError):
    pass


def load_theme(name: str = "hw_v1") -> dict[str, Any]:
    canonical = resolve_theme(name)
    filename = "hw_theme.json" if canonical == "hw_v1" else f"{canonical}.json"
    path = THEMES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"theme not found: {name}")
    return json.loads(path.read_text(encoding="utf-8"))
