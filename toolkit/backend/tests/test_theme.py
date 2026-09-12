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
    assert theme["colors"]["accent1"] == "#C7000B"
    assert theme["colors"]["accent2"] == "#F85948"
    assert theme["colors"]["accent3"] == "#ED6D00"
    assert theme["colors"]["accent4"] == "#FCC800"
    assert theme["colors"]["accent5"] == "#61B230"
    assert theme["colors"]["accent6"] == "#30B5C5"
    assert theme["colors"]["title"] == "#1D1D1A"
    assert theme["colors"]["body"] == "#1D1D1A"
    assert theme["colors"]["secondary"] == "#666666"
    assert theme["colors"]["muted"] == "#666666"
    assert theme["colors"]["border"] == "#DDDDDD"
    assert theme["colors"]["surface"] == "#DDDDDD"
    assert theme["fonts"]["east_asia"] == ["微软雅黑"]
    assert theme["fonts"]["latin"] == ["Arial"]
    assert theme["font_sizes_pt"]["slide_title"] == 14
    assert theme["font_sizes_pt"]["level2"] == 12
    assert theme["font_sizes_pt"]["level3"] == 11
    assert theme["font_sizes_pt"]["body"] == 10
    assert theme["font_sizes_pt"]["body_small"] == 9
    assert theme["font_sizes_pt"]["chart_label"] == 8
    assert theme["font_sizes_pt"]["copyright"] == 8
    assert theme["font_sizes_pt"]["minimum"] == 8
    assert theme["ppt_typography"]["cover_title_candidates_pt"] == [40, 36, 32]
    assert theme["ppt_typography"]["cover_subtitle_pt"] == 20
    assert theme["ppt_typography"]["slide_title_candidates_pt"] == [28, 24, 20]
    assert theme["ppt_typography"]["body_candidates_pt"] == [16, 14, 12, 10.5]
    assert theme["ppt_typography"]["body_minimum_pt"] == 10.5
    assert theme["ppt_typography"]["compact_minimum_pt"] == 8
    assert theme["typography"]["line_spacing"] == 1.3
    assert theme["strokes"]["card_border_pt"] == 0.5
    assert theme["slide"]["width_in"] == 13.34
    assert theme["slide"]["height_in"] == 7.5
    assert theme["slide"]["margin_left_in"] == 0.57
    assert theme["slide"]["margin_right_in"] == 0.57
    assert theme["slide"]["margin_top_in"] == 0.29
    assert theme["slide"]["margin_bottom_in"] == 0.5
    assert theme["grid"]["columns"] == 12
    assert theme["constraints"]["max_font_size_kinds_per_slide"] == 3
    assert theme["footer"]["right"] == "page_number"
    assert theme["footer"]["security_prefix"] == "Security Level: "
    assert theme["footer"]["page_number_format"] == "{current}/{total}"
    assert theme["footer"]["copyright"]
    assert theme["logo"]["position"] == "top_right"
    assert "HUAWEI CONFIDENTIAL" in theme["footer"]["default_classification"]
