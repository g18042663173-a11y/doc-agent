from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_validate_word_ir_maps_missing_title_to_e002() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir({"ir_type": "word", "ir_version": "1.0", "meta": {}, "blocks": []})

    assert result.value is None
    assert result.errors[0].code == "E002"


def test_validate_word_ir_maps_empty_blocks_to_e006() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "空文档"},
            "blocks": [],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "E006"
    assert result.errors[0].loc == "blocks"


def test_validate_word_ir_maps_table_shape_to_e004() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "表格错误"},
            "blocks": [
                {
                    "type": "table",
                    "header": ["风险", "等级"],
                    "rows": [["模型 JSON 不稳定"], ["字段漂移", "中", "冻结 Schema"]],
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "E004"


def test_validate_word_ir_ignores_unknown_fields_and_warns() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "unknown_top": "ignored",
            "meta": {"title": "未知字段", "unknown_meta": "ignored"},
            "blocks": [
                {"type": "paragraph", "text": "正文", "unknown_block": "ignored"},
            ],
        }
    )

    assert result.value is not None
    assert [warning.code for warning in result.warnings] == ["W104", "W104", "W104"]
    assert [warning.loc for warning in result.warnings] == ["unknown_top", "meta.unknown_meta", "blocks[0].unknown_block"]
    assert not hasattr(result.value, "unknown_top")


def test_validate_deck_ir_maps_unknown_layout_to_d003() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "未知版式"},
            "slides": [{"layout": "mystery", "title": "无法渲染"}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D003"
