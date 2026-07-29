from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ir.deck_ir import DeckIR
from app.ir.validation import validate_deck_ir


def _deck(slide: dict) -> dict:
    return {
        "ir_type": "deck",
        "ir_version": "2.0",
        "meta": {"title": "视觉契约"},
        "slides": [slide],
    }


def test_deck_ir_19_is_migrated_in_memory_to_20() -> None:
    payload = _deck({"layout": "image", "title": "占位", "placeholder": "稍后补图"})
    payload["ir_version"] = "1.9"
    result = validate_deck_ir(payload)
    assert result.ok
    assert result.value is not None and result.value.ir_version == "2.0"
    assert result.warnings == []


def test_image_text_and_grid_contracts_validate_focus_and_capacity() -> None:
    image = {
        "image_ref": "asset-123456789abc",
        "fit": "cover",
        "focal_x": 0.25,
        "focal_y": 0.75,
        "alt": "现场设备状态",
        "credit": "内部项目组",
    }
    assert DeckIR.model_validate(
        _deck(
            {
                "layout": "image_text",
                "title": "现场证据支撑当前判断",
                "image": image,
                "image_position": "left",
                "heading": "关键发现",
                "bullets": ["设备运行稳定", "异常均已闭环"],
            }
        )
    )
    assert DeckIR.model_validate(
        _deck({"layout": "image_grid", "title": "证据覆盖两个场景", "images": [image, {**image, "image_ref": "asset-fedcba987654"}]})
    )
    with pytest.raises(ValidationError):
        DeckIR.model_validate(_deck({"layout": "image_grid", "title": "数量不足", "images": [image]}))


@pytest.mark.parametrize(
    "infographic",
    [
        {"kind": "funnel", "direction": "forward", "stages": [{"label": str(i)} for i in range(3)]},
        {
            "kind": "quadrant",
            "x_axis": "影响",
            "y_axis": "难度",
            "items": [{"label": "方案A", "x": 0.8, "y": 0.3}],
        },
        {"kind": "cycle", "stages": [{"label": str(i)} for i in range(3)]},
        {"kind": "matrix", "row_labels": ["高", "低"], "column_labels": ["急", "缓"], "cells": [["A", "B"], ["C", "D"]]},
    ],
)
def test_infographic_discriminated_contracts(infographic: dict) -> None:
    deck = DeckIR.model_validate(_deck({"layout": "infographic", "title": "信息图保持业务结构", "infographic": infographic}))
    assert deck.slides[0].layout == "infographic"


def test_matrix_shape_and_combo_semantics_are_strict() -> None:
    with pytest.raises(ValidationError, match="matrix cells"):
        DeckIR.model_validate(
            _deck(
                {
                    "layout": "infographic",
                    "title": "坏矩阵",
                    "infographic": {
                        "kind": "matrix",
                        "row_labels": ["高", "低"],
                        "column_labels": ["急", "缓"],
                        "cells": [["A"], ["B"]],
                    },
                }
            )
        )

    chart = {
        "kind": "combo",
        "categories": ["一月", "二月"],
        "series": [
            {"name": "收入", "values": [10, 12], "chart_type": "bar", "axis": "primary", "unit": "万元"},
            {"name": "利润率", "values": [20, 25], "chart_type": "line", "axis": "secondary", "unit": "%"},
        ],
        "value_axis_title": "收入",
        "secondary_value_axis_title": "利润率",
        "number_format": "0.0",
        "secondary_number_format": "0.0%",
        "source": "经营月报",
        "methodology": "利润率=利润/收入",
    }
    assert DeckIR.model_validate(_deck({"layout": "chart", "title": "收入增长且利润率改善", "chart": chart}))
    bad = {**chart, "series": [{**chart["series"][0], "axis": "secondary"}, chart["series"][1]]}
    with pytest.raises(ValidationError, match="primary and secondary"):
        DeckIR.model_validate(_deck({"layout": "chart", "title": "错误双轴", "chart": bad}))


def test_scatter_requires_explicit_x_values() -> None:
    valid = {
        "kind": "scatter",
        "categories": [],
        "series": [{"name": "样本", "x_values": [1, 2], "values": [3, 5]}],
        "category_axis_title": "投入",
        "value_axis_title": "产出",
    }
    assert DeckIR.model_validate(_deck({"layout": "chart", "title": "投入与产出正相关", "chart": valid}))
    with pytest.raises(ValidationError, match="x_values"):
        DeckIR.model_validate(
            _deck({"layout": "chart", "title": "缺少横坐标", "chart": {**valid, "series": [{"name": "样本", "values": [3, 5]}]}})
        )
