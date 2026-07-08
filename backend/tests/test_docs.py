from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_yellow_zone_integration_doc_covers_required_topics() -> None:
    text = (ROOT / "docs" / "内网接入.md").read_text(encoding="utf-8")

    assert "generators/nga.py" in text
    assert "华为官方渲染 Skill" in text
    assert "NGA_BASE_URL" in text
    assert "NGA_TOKEN" in text
    assert "wheelhouse" in text
    assert "stub 全链路" in text
    assert "不动清单" in text
