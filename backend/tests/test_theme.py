from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_load_hw_theme_contains_required_tokens() -> None:
    from app.rendering.theme import load_theme

    theme = load_theme("hw_v1")

    assert theme["name"] == "hw_v1"
    assert theme["colors"]["hw_red"] == "#C7000B"
    assert theme["fonts"]["east_asia"][0] == "微软雅黑"
    assert theme["slide"]["width_in"] == 13.333
    assert theme["grid"]["columns"] == 12
    assert theme["footer"]["right"] == "page_number"
    assert "HUAWEI CONFIDENTIAL" in theme["footer"]["default_classification"]
