from __future__ import annotations

import sys
from pathlib import Path

import pytest

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


def test_validate_word_ir_rejects_non_finite_col_widths() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "NaN 表宽"},
            "blocks": [
                {
                    "type": "table",
                    "header": ["风险", "等级"],
                    "rows": [["漂移", "中"]],
                    "col_widths": [1.0, float("nan")],
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


def test_validate_word_ir_warns_and_repairs_heading_level_jump() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "标题跳级"},
            "blocks": [
                {"type": "heading", "level": 1, "text": "一级"},
                {"type": "heading", "level": 3, "text": "三级"},
            ],
        }
    )

    assert result.value is not None
    assert [warning.code for warning in result.warnings] == ["W101"]
    assert result.value.blocks[1].level == 2


def test_validate_word_ir_does_not_warn_for_sequential_heading_levels() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "标题正常", "classification": "内部公开"},
            "blocks": [
                {"type": "heading", "level": 1, "text": "一级"},
                {"type": "heading", "level": 2, "text": "二级"},
            ],
        }
    )

    assert result.value is not None
    assert "W101" not in [warning.code for warning in result.warnings]


def test_validate_word_ir_skips_blank_paragraph_and_warns() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "空段落"},
            "blocks": [
                {"type": "paragraph", "text": "   "},
                {"type": "paragraph", "text": "保留"},
            ],
        }
    )

    assert result.value is not None
    assert [warning.code for warning in result.warnings] == ["W102"]
    assert [info.code for info in result.infos] == ["I201"]
    assert len(result.value.blocks) == 1
    assert result.value.blocks[0].text == "保留"


def test_validate_word_ir_truncates_long_paragraph_and_table_cell() -> None:
    from app.ir.validation import validate_word_ir

    long_text = "长" * 2001
    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "超长", "classification": "内部公开"},
            "blocks": [
                {"type": "paragraph", "text": long_text},
                {"type": "table", "header": ["列"], "rows": [[long_text]]},
            ],
        }
    )

    assert result.value is not None
    assert [warning.code for warning in result.warnings] == ["W103", "W103"]
    assert len(result.value.blocks[0].text) == 2000
    assert len(result.value.blocks[1].rows[0][0]) == 2000


def test_validate_word_ir_infos_when_classification_defaulted() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "默认密级"},
            "blocks": [{"type": "paragraph", "text": "正文"}],
        }
    )

    assert result.value is not None
    assert [info.code for info in result.infos] == ["I201"]
    assert result.value.meta.classification == "内部公开"


def test_validate_word_ir_does_not_info_when_classification_given() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "已有密级", "classification": "内部公开"},
            "blocks": [{"type": "paragraph", "text": "正文"}],
        }
    )

    assert result.value is not None
    assert result.infos == []


def test_validate_deck_ir_maps_unknown_layout_to_d003() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
                "ir_version": "1.9",
            "meta": {"title": "未知版式"},
            "slides": [{"layout": "mystery", "title": "无法渲染"}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D003"


@pytest.mark.parametrize("source_version", ["1.4", "1.5", "1.6", "1.7", "1.8", "2.1"])
def test_validate_deck_ir_migrates_legacy_versions_without_mutating_input(source_version: str) -> None:
    import copy

    from app.ir.deck_ir import DeckIR
    from app.ir.validation import validate_deck_ir

    payload = {
        "ir_type": "deck",
        "ir_version": source_version,
        "meta": {"title": "旧版契约"},
        "slides": [{"layout": "cover", "title": "旧版契约"}],
    }
    original = copy.deepcopy(payload)
    result = validate_deck_ir(payload)
    direct = DeckIR.model_validate(payload)

    assert result.ok and result.value is not None
    assert result.value.ir_version == "2.2"
    assert direct.ir_version == "2.2"
    assert payload == original
    assert any(
        item.code == "D004"
        and item.loc == "ir_version"
        and source_version in item.message
        and "2.2" in item.message
        for item in result.warnings
    )


def test_validate_deck_ir_accepts_composite_with_existing_component_models() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.9",
            "meta": {"title": "组合页"},
            "slides": [
                {
                    "layout": "composite",
                    "title": "方案结论与数据流可在一页联读",
                    "regions": [
                        {
                            "slot": "left",
                            "components": [{
                                "layout": "table",
                                "title": "方案对比",
                                "table": {"header": ["方案", "结论"], "rows": [["A", "推荐"]]},
                            }],
                        },
                        {
                            "slot": "right",
                            "components": [{
                                "layout": "architecture_diagram",
                                "title": "数据流",
                                "nodes": [
                                    {"id": "input", "text": "输入", "type": "primary"},
                                    {"id": "output", "text": "输出", "type": "data"},
                                ],
                                "edges": [{"from": "input", "to": "output"}],
                                "groups": [],
                            }],
                        },
                    ],
                }
            ],
        }
    )

    assert result.ok and result.value is not None
    slide = result.value.slides[0]
    assert slide.layout == "composite"
    assert [region.slot for region in slide.regions] == ["left", "right"]
    assert [region.components[0].layout for region in slide.regions] == ["table", "architecture_diagram"]


def test_validate_deck_ir_migrates_v17_single_composite_component_without_mutating_input() -> None:
    import copy

    from app.ir.validation import validate_deck_ir

    payload = {
        "ir_type": "deck",
            "ir_version": "1.7",
        "meta": {"title": "旧组合页"},
        "slides": [
            {
                "layout": "composite",
                "title": "单组件组合页",
                "regions": [
                    {
                        "slot": "left",
                        "component": {
                            "layout": "title_bullets",
                            "title": "左栏",
                            "bullets": [{"text": "旧字段", "level": 1}],
                        },
                    },
                    {
                        "slot": "right",
                        "component": {
                            "layout": "cards",
                            "title": "右栏",
                            "cards": [{"title": "A", "desc": "一"}, {"title": "B", "desc": "二"}],
                        },
                    },
                ],
            }
        ],
    }
    original = copy.deepcopy(payload)

    result = validate_deck_ir(payload)

    assert result.ok and result.value is not None
    assert result.value.ir_version == "2.2"
    assert [len(region.components) for region in result.value.slides[0].regions] == [1, 1]
    assert payload == original
    assert any(item.code == "D004" and "1.7" in item.message and "2.2" in item.message for item in result.warnings)


def test_validate_deck_ir_accepts_three_stacked_components_and_rejects_fourth() -> None:
    import copy

    from app.ir.validation import validate_deck_ir

    component = {"layout": "title_bullets", "title": "块", "bullets": [{"text": "内容", "level": 1}]}
    valid = {
        "ir_type": "deck",
        "ir_version": "1.9",
        "meta": {"title": "堆叠"},
        "slides": [
            {
                "layout": "composite",
                "title": "堆叠合法",
                "regions": [
                    {"slot": "left", "components": [component, component, component]},
                    {"slot": "right", "components": [component]},
                ],
            }
        ],
    }
    invalid = copy.deepcopy(valid)
    invalid["slides"][0]["regions"][0]["components"].append(component)

    assert validate_deck_ir(valid).ok
    invalid_result = validate_deck_ir(invalid)
    assert invalid_result.value is None
    assert invalid_result.errors[0].code == "D004"


@pytest.mark.parametrize(
    ("regions", "expected_code"),
    [
        (
            [
                {
                    "slot": "left",
                    "component": {
                        "layout": "title_bullets",
                        "title": "左侧",
                        "bullets": [{"text": "要点", "level": 1}],
                    },
                },
                {
                    "slot": "left",
                    "component": {
                        "layout": "cards",
                        "title": "重复左栏",
                        "cards": [{"title": "A", "desc": "一"}, {"title": "B", "desc": "二"}],
                    },
                },
            ],
            "D004",
        ),
        (
            [
                {
                    "slot": "left",
                    "component": {
                        "layout": "chart",
                        "title": "暂不允许",
                        "chart": {"kind": "bar", "categories": ["A"], "series": [{"name": "值", "values": [1]}]},
                    },
                },
                {
                    "slot": "right",
                    "component": {
                        "layout": "title_bullets",
                        "title": "右侧",
                        "bullets": [{"text": "要点", "level": 1}],
                    },
                },
            ],
            "D003",
        ),
        (
            [
                {
                    "slot": "left",
                    "component": {
                        "layout": "table",
                        "title": "非法表格",
                        "table": {"header": ["A", "B"], "rows": [["只有一列"]]},
                    },
                },
                {
                    "slot": "right",
                    "component": {
                        "layout": "title_bullets",
                        "title": "右侧",
                        "bullets": [{"text": "要点", "level": 1}],
                    },
                },
            ],
            "D005",
        ),
        (
            [
                {
                    "slot": "left",
                    "component": {
                        "layout": "cards",
                        "title": "左侧",
                        "cards": [{"title": "A", "desc": "一"}, {"title": "B", "desc": "二"}],
                    },
                },
                {
                    "slot": "right",
                    "component": {
                        "layout": "architecture_diagram",
                        "title": "非法架构",
                        "nodes": [{"id": "known", "text": "已知节点"}],
                        "edges": [{"from": "known", "to": "missing"}],
                        "groups": [],
                    },
                },
            ],
            "D004",
        ),
        (
            [
                {
                    "slot": "left",
                    "component": {
                        "layout": "title_bullets",
                        "title": "空要点",
                        "bullets": [],
                    },
                },
                {
                    "slot": "right",
                    "component": {
                        "layout": "cards",
                        "title": "右侧",
                        "cards": [{"title": "A", "desc": "一"}, {"title": "B", "desc": "二"}],
                    },
                },
            ],
            "D006",
        ),
        (
            [
                {
                    "slot": "left",
                    "component": {
                        "layout": "title_bullets",
                        "title": "左侧",
                        "bullets": [{"text": "要点", "level": 1}],
                    },
                },
                {
                    "slot": "right",
                    "component": {
                        "layout": "cards",
                        "title": "卡片不足",
                        "cards": [{"title": "只有一张", "desc": "非法"}],
                    },
                },
            ],
            "D004",
        ),
    ],
)
def test_validate_deck_ir_composite_recursively_enforces_component_contracts(
    regions: list[dict],
    expected_code: str,
) -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法组合页"},
            "slides": [{"layout": "composite", "title": "非法组合页", "regions": regions}],
        }
    )

    assert not result.ok
    assert result.errors[0].code == expected_code


def test_validate_deck_ir_revalidates_v14_and_rejects_older_versions() -> None:
    from app.ir.validation import validate_deck_ir

    invalid_v14 = validate_deck_ir(
        {"ir_type": "deck", "ir_version": "1.4", "meta": {"title": "旧版"}, "slides": [{"layout": "cover"}]}
    )
    unsupported_v13 = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.3",
            "meta": {"title": "过旧契约"},
            "slides": [{"layout": "cover", "title": "过旧契约"}],
        }
    )

    assert not invalid_v14.ok and invalid_v14.errors[0].code == "D004"
    assert any(item.code == "D004" and item.level == "Warning" for item in invalid_v14.warnings)
    assert not unsupported_v13.ok and unsupported_v13.errors[0].loc == "ir_version"


def test_validate_deck_ir_maps_missing_title_to_d002() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir({"ir_type": "deck", "ir_version": "1.7", "meta": {}, "slides": [{"layout": "cover", "title": "封面"}]})

    assert result.value is None
    assert result.errors[0].code == "D002"


def test_validate_deck_ir_maps_missing_layout_field_to_d004() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir({"ir_type": "deck", "ir_version": "1.7", "meta": {"title": "缺字段"}, "slides": [{"layout": "cover"}]})

    assert result.value is None
    assert result.errors[0].code == "D004"


def test_validate_deck_ir_maps_ragged_or_oversized_table_to_d005() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "表格错误"},
            "slides": [{"layout": "table", "title": "表格", "table": {"header": ["A", "B"], "rows": [["only one"]]}}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D005"


def test_validate_deck_ir_accepts_decision_matrix_table_v12() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "方案对比", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {
                    "layout": "table",
                    "title": "方案对比表",
                    "table": {
                        "header": ["方案", "可靠性", "成本", "交付", "结论"],
                        "column_groups": [{"label": "评估维度", "start_col": 1, "span": 3}],
                        "row_groups": [{"label": "主推方案", "start_row": 0, "span": 2}],
                        "cell_spans": [{"area": "body", "row": 0, "col": 2, "rowspan": 1, "colspan": 2}],
                        "conclusion_col": 4,
                        "rows": [
                            [
                                {"text": "方案A"},
                                "高",
                                {"items": ["周期短", "依赖少"]},
                                "",
                                {"text": "推荐", "emphasis": "yellow"},
                            ],
                            [
                                {"text": "方案B"},
                                "中",
                                "成本可控",
                                "交付较慢",
                                {"text": "备选", "emphasis": "cyan"},
                            ],
                        ],
                    },
                }
            ],
        }
    )

    assert result.ok, result.errors
    assert result.value is not None
    table = result.value.slides[0].table
    assert table.column_groups[0].label == "评估维度"
    assert table.row_groups[0].label == "主推方案"
    assert table.cell_spans[0].colspan == 2
    assert table.rows[0][2].items == ["周期短", "依赖少"]
    assert table.rows[1][4].emphasis == "cyan"


def test_validate_deck_ir_normalizes_clear_one_based_conclusion_column() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "索引防呆"},
            "slides": [
                {
                    "layout": "table",
                    "title": "索引防呆",
                    "table": {
                        "header": ["方案", "指标", "结论"],
                        "rows": [["方案A", "达标", "推荐"]],
                        "conclusion_col": 3,
                    },
                }
            ],
        }
    )

    assert result.ok, result.errors
    assert result.value.slides[0].table.conclusion_col == 2
    assert any(item.code == "D005" and "1 起始索引" in item.message for item in result.warnings)


def test_validate_deck_ir_normalizes_clear_one_based_span_indexes_only() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "合并索引防呆"},
            "slides": [
                {
                    "layout": "table",
                    "title": "合并索引防呆",
                    "table": {
                        "header": ["方案", "指标", "风险"],
                        "rows": [["方案A", "达标", ""]],
                        "column_groups": [{"label": "评估", "start_col": 2, "span": 2}],
                        "cell_spans": [{"area": "body", "row": 1, "col": 2, "rowspan": 1, "colspan": 2}],
                    },
                }
            ],
        }
    )

    assert result.ok, result.errors
    table = result.value.slides[0].table
    assert table.column_groups[0].start_col == 1
    assert (table.cell_spans[0].row, table.cell_spans[0].col) == (0, 1)
    assert (table.cell_spans[0].rowspan, table.cell_spans[0].colspan) == (1, 2)
    assert any(item.code == "D005" and item.level == "Warning" for item in result.warnings)


def test_validate_deck_ir_keeps_valid_zero_based_table_indexes_without_warning() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "零起始索引"},
            "slides": [
                {
                    "layout": "table",
                    "title": "零起始索引",
                    "table": {
                        "header": ["方案", "指标", "结论"],
                        "rows": [["方案A", "达标", "推荐"]],
                        "column_groups": [{"label": "评估", "start_col": 0, "span": 2}],
                        "conclusion_col": 2,
                    },
                }
            ],
        }
    )

    assert result.ok, result.errors
    assert not any(item.code == "D005" for item in result.warnings)


def test_validate_deck_ir_does_not_guess_when_table_indexes_are_mixed() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "混合索引"},
            "slides": [
                {
                    "layout": "table",
                    "title": "混合索引",
                    "table": {
                        "header": ["方案", "指标", "结论"],
                        "rows": [["方案A", "达标", "推荐"]],
                        "column_groups": [{"label": "评估", "start_col": 0, "span": 2}],
                        "conclusion_col": 3,
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert any(item.code == "D005" and item.level == "Error" for item in result.errors)
    assert any(item.code == "D005" and "混用" in item.message for item in result.warnings)


def test_validate_deck_ir_does_not_shift_zero_based_conclusion_when_one_span_is_one_based() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "零起始结论列"},
            "slides": [
                {
                    "layout": "table",
                    "title": "零起始结论列",
                    "table": {
                        "header": ["方案", "指标", "成本", "结论"],
                        "rows": [["方案A", "高", "中", "推荐"]],
                        "conclusion_col": 3,
                        "cell_spans": [{"area": "body", "row": 1, "col": 4, "rowspan": 1, "colspan": 1}],
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert any(item.code == "D005" and "混用" in item.message for item in result.warnings)


def test_validate_word_ir_returns_coded_error_for_non_string_input() -> None:
    from app.ir.validation import validate_word_ir

    for raw in (123, None, b"bytes", ["list"]):
        result = validate_word_ir(raw)  # type: ignore[arg-type]

        assert result.value is None
        assert result.errors[0].code in {"E001", "D001"}
        assert "收到" in result.errors[0].message


def test_validate_word_ir_maps_list_item_level_error_to_e006_not_heading_e005() -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "列表层级"},
            "blocks": [
                {"type": "heading", "level": 5, "text": "越级标题"},
                {"type": "bullet_list", "items": [{"text": "条目", "level": 3}]},
            ],
        }
    )

    assert result.value is None
    codes = [item.code for item in result.errors]
    assert "E005" in codes
    assert any(code == "E005" and "heading" in item.loc for code, item in zip(codes, result.errors))
    assert any(item.code == "E006" and "items[0].level" in item.loc for item in result.errors)


def test_validate_deck_ir_maps_invalid_decision_matrix_span_to_d005() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法表格"},
            "slides": [
                {
                    "layout": "table",
                    "title": "非法表格",
                    "table": {
                        "header": ["方案", "可靠性", "成本"],
                        "rows": [["方案A", "高", "中"]],
                        "cell_spans": [{"area": "body", "row": 0, "col": 2, "rowspan": 1, "colspan": 2}],
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D005"


@pytest.mark.parametrize(
    "table_patch",
    [
        {"header": ["", "可靠性", "成本"]},
        {"rows": [[{"items": [""]}, "高", "中"]]},
        {"col_widths": [1.5, -1.0, 2.0]},
        {"col_widths": [1.5, 2.0]},
        {"col_widths": [1.5, float("nan"), 2.0]},
        {"col_widths": [1.5, float("inf"), 2.0]},
        {"conclusion_col": 4},
        {"column_groups": [{"label": "越界", "start_col": 3, "span": 2}]},
        {
            "column_groups": [
                {"label": "分组一", "start_col": 0, "span": 2},
                {"label": "分组二", "start_col": 1, "span": 2},
            ]
        },
        {"row_groups": [{"label": "越界", "start_row": 2, "span": 2}]},
        {
            "row_groups": [
                {"label": "分组一", "start_row": 0, "span": 2},
                {"label": "分组二", "start_row": 1, "span": 1},
            ]
        },
        {"cell_spans": [{"area": "header", "row": 0, "col": 0, "rowspan": 2, "colspan": 1}]},
        {
            "cell_spans": [
                {"area": "body", "row": 0, "col": 0, "rowspan": 1, "colspan": 2},
                {"area": "body", "row": 0, "col": 1, "rowspan": 1, "colspan": 2},
            ]
        },
    ],
)
def test_validate_deck_ir_maps_enhanced_table_contract_errors_to_d005(table_patch: dict) -> None:
    from app.ir.validation import validate_deck_ir

    table = {
        "header": ["方案", "可靠性", "成本"],
        "rows": [["方案A", "高", "中"], ["方案B", "中", "低"]],
    }
    table.update(table_patch)

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法增强表格"},
            "slides": [{"layout": "table", "title": "非法增强表格", "table": table}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D005"


def test_validate_deck_ir_maps_too_many_bullets_to_d006() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "要点过多"},
            "slides": [
                {
                    "layout": "title_bullets",
                    "title": "要点",
                    "bullets": [{"text": f"要点 {index}", "level": 1} for index in range(8)],
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D006"


def test_validate_deck_ir_accepts_performance_chart_v13() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "性能图表", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "性能趋势",
                    "chart": {
                        "kind": "bar",
                        "unit": "ms",
                        "categories": ["1月", "2月", "3月"],
                        "series": [
                            {"name": "方案A", "values": [62, 58, 55], "emphasis": True},
                            {"name": "方案B", "values": [75, 69, 64]},
                        ],
                        "show_data_labels": True,
                        "legend_position": "right",
                        "thresholds": [{"value": 60, "label": "目标阈值"}],
                        "side_conclusion": "方案A 2月起低于60ms目标阈值。",
                        "side_table": {"header": ["指标", "结论"], "rows": [["时延", "2月起达标"], ["稳定性", "需关注"]]},
                    },
                }
            ],
        }
    )

    assert result.ok, result.errors
    assert result.value is not None
    chart = result.value.slides[0].chart
    assert chart.unit == "ms"
    assert chart.series[0].emphasis is True
    assert chart.thresholds[0].label == "目标阈值"
    assert chart.side_table is not None


def test_validate_deck_ir_rejects_contradictory_chart_side_conclusion() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "矛盾结论", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "性能趋势",
                    "chart": {
                        "kind": "bar",
                        "unit": "ms",
                        "categories": ["1月", "2月", "3月"],
                        "series": [{"name": "方案A", "values": [62, 58, 55], "emphasis": True}],
                        "thresholds": [{"value": 60, "label": "目标阈值"}],
                        "side_conclusion": "方案A连续三个月低于目标阈值。",
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"


def test_validate_deck_ir_uses_the_threshold_referenced_by_side_conclusion_text() -> None:
    from app.ir.validation import validate_deck_ir

    def build(values, conclusion):
        return validate_deck_ir(
            {
                "ir_type": "deck",
                "ir_version": "1.7",
                "meta": {"title": "多阈值", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
                "slides": [
                    {
                        "layout": "chart",
                        "title": "性能趋势",
                        "chart": {
                            "kind": "bar",
                            "unit": "ms",
                            "categories": ["1月", "2月", "3月"],
                            "series": [{"name": "方案A", "values": values, "emphasis": True}],
                            "thresholds": [
                                {"value": 60, "label": "下限"},
                                {"value": 80, "label": "上限"},
                            ],
                            "side_conclusion": conclusion,
                        },
                    }
                ],
            }
        )

    contradictory = build([70, 72, 71], "方案A连续三个月高于80。")
    assert contradictory.value is None
    assert contradictory.errors[0].code == "D004"

    valid = build([82, 85, 81], "方案A连续三个月高于80。")
    assert valid.ok, valid.errors

    low_threshold_reference = build([70, 72, 71], "方案A连续三个月高于60。")
    assert low_threshold_reference.ok, low_threshold_reference.errors


def test_validate_deck_ir_strict_mode_collects_nested_unknown_fields_in_image_and_infographic_layouts() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "2.1",
            "meta": {"title": "图文页", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {
                    "layout": "image_text",
                    "title": "图文页",
                    "image": {"image_ref": "a.png", "focul_x": 0.9},
                    "text": "说明",
                },
                {
                    "layout": "image_grid",
                    "title": "多图页",
                    "images": [{"image_ref": "a.png", "focul_y": 0.2}, {"image_ref": "b.png", "unkown_ref": "x"}],
                },
                {
                    "layout": "infographic",
                    "title": "漏斗",
                    "infographic": {
                        "kind": "funnel",
                        "stages": [
                            {"label": "认知", "discription": "拼写错误"},
                            {"label": "考虑", "description": "正常"},
                            {"label": "行动", "description": "正常"},
                        ],
                    },
                },
            ],
        },
        reject_unknown_fields=True,
    )

    assert result.value is None
    unknown_locations = {error.loc for error in result.errors if error.code == "D004"}
    assert any(loc.endswith(".image.focul_x") for loc in unknown_locations)
    assert any(".images[1].unkown_ref" in loc for loc in unknown_locations)
    assert any(".infographic.stages[0].discription" in loc for loc in unknown_locations)


def test_validate_deck_ir_rejects_combo_thresholds_referencing_secondary_axis() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "2.1",
            "meta": {"title": "次轴阈值", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "组合图",
                    "chart": {
                        "kind": "combo",
                        "categories": ["一月", "二月", "三月"],
                        "series": [
                            {"name": "收入", "values": [13, 14, 15], "chart_type": "bar", "axis": "primary", "unit": "万元"},
                            {"name": "利润率", "values": [0.2, 0.22, 0.25], "chart_type": "line", "axis": "secondary", "unit": "%", "emphasis": True},
                        ],
                        "thresholds": [{"value": 0.22, "label": "利润率目标"}],
                        "side_conclusion": "利润率连续三个月高于0.22。",
                        "show_data_labels": False,
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"
    assert "primary axis" in result.errors[0].message


def test_validate_deck_ir_maps_invalid_chart_threshold_to_d004() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法阈值线"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "非法阈值线",
                    "chart": {
                        "kind": "line",
                        "categories": ["1月"],
                        "series": [{"name": "方案A", "values": [10]}],
                        "thresholds": [{"value": 8, "label": "   "}],
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"


@pytest.mark.parametrize("kind", ["line", "pie"])
def test_validate_deck_ir_rejects_horizontal_non_bar_chart(kind: str) -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法横向图表"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "非法横向图表",
                    "chart": {
                        "kind": kind,
                        "orientation": "horizontal",
                        "categories": ["A", "B"],
                        "series": [{"name": "指标", "values": [1, 2]}],
                    },
                }
            ],
        }
    )

    assert not result.ok and result.errors[0].code == "D004"
    assert "horizontal" in result.errors[0].message


def test_validate_deck_ir_preserves_default_chart_and_cards_behavior() -> None:
    from app.ir.deck_ir import DeckIR

    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "默认兼容"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "默认柱图",
                    "chart": {"kind": "bar", "categories": ["A"], "series": [{"name": "指标", "values": [1]}]},
                },
                {
                    "layout": "cards",
                    "title": "默认卡片",
                    "cards": [{"title": "A", "desc": "一"}, {"title": "B", "desc": "二"}],
                },
            ],
        }
    )

    assert deck.slides[0].chart.orientation == "vertical"
    assert deck.slides[1].variant == "default"


@pytest.mark.parametrize(
    ("chart_patch", "expected_code"),
    [
        ({"categories": [""]}, "D004"),
        ({"series": [{"name": "方案A", "values": [10, 12]}]}, "D004"),
        ({"kind": "pie", "series": [{"name": "A", "values": [10]}, {"name": "B", "values": [12]}]}, "D004"),
        ({"kind": "pie", "thresholds": [{"value": 8, "label": "目标"}]}, "D004"),
        ({"side_table": {"header": ["", "结论"], "rows": [["时延", "达标"]]}}, "D005"),
        ({"side_table": {"header": ["指标", "结论"], "rows": [["时延"]]}}, "D005"),
    ],
)
def test_validate_deck_ir_maps_chart_contract_errors(chart_patch: dict, expected_code: str) -> None:
    from app.ir.validation import validate_deck_ir

    chart = {
        "kind": "line",
        "categories": ["1月"],
        "series": [{"name": "方案A", "values": [10]}],
    }
    chart.update(chart_patch)

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法图表"},
            "slides": [{"layout": "chart", "title": "非法图表", "chart": chart}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == expected_code


def test_validate_deck_ir_ignores_unknown_fields_and_warns() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.9",
            "unknown_top": "ignored",
            "meta": {"title": "未知字段", "unknown_meta": "ignored"},
            "slides": [{"layout": "cover", "title": "封面", "unknown_slide": "ignored"}],
        }
    )

    assert result.value is not None
    assert [warning.code for warning in result.warnings] == ["W104", "W104", "W104"]
    assert [warning.loc for warning in result.warnings] == ["unknown_top", "meta.unknown_meta", "slides[0].unknown_slide"]


def test_strict_deck_validation_rejects_unknown_optional_field_for_model_repair() -> None:
    from app.ir.validation import validate_deck_ir

    payload = {
        "ir_type": "deck",
        "ir_version": "1.9",
        "meta": {"title": "字段拼写"},
        "slides": [{"layout": "cover", "title": "字段拼写", "subtitel": "拼错的可选字段"}],
    }

    compatible = validate_deck_ir(payload)
    strict = validate_deck_ir(payload, reject_unknown_fields=True)

    assert compatible.ok
    assert [(item.code, item.loc) for item in compatible.warnings] == [("W104", "slides[0].subtitel")]
    assert strict.value is None
    assert [(item.code, item.loc) for item in strict.errors] == [("D004", "slides[0].subtitel")]
    assert "未知字段" in strict.errors[0].message


def test_strict_deck_validation_recurses_into_composite_table_unknown_fields() -> None:
    from app.ir.validation import validate_deck_ir

    payload = {
        "ir_type": "deck",
        "ir_version": "1.9",
        "meta": {"title": "组合页字段拼写"},
        "slides": [
            {
                "layout": "composite",
                "title": "嵌入组件仍需严格校验",
                "regions": [
                    {
                        "slot": "left",
                        "components": [
                            {
                                "layout": "table",
                                "title": "指标表",
                                "table": {
                                    "header": ["指标", "结果"],
                                    "rows": [["时延", "18 ms"]],
                                    "colum_widths": [1, 1],
                                },
                            }
                        ],
                    },
                    {
                        "slot": "right",
                        "components": [
                            {
                                "layout": "architecture_diagram",
                                "title": "处理链路",
                                "nodes": [{"id": "in", "text": "输入", "type": "primary"}],
                                "edges": [],
                                "groups": [],
                            }
                        ],
                    },
                ],
            }
        ],
    }

    compatible = validate_deck_ir(payload)
    strict = validate_deck_ir(payload, reject_unknown_fields=True)

    expected_loc = "slides[0].regions[0].components[0].table.colum_widths"
    assert compatible.ok
    assert [(item.code, item.loc) for item in compatible.warnings] == [("W104", expected_loc)]
    assert strict.value is None
    assert [(item.code, item.loc) for item in strict.errors] == [("D005", expected_loc)]


def test_unknown_architecture_type_warns_normally_and_is_repairable_in_strict_mode() -> None:
    from app.ir.validation import validate_deck_ir

    payload = {
        "ir_type": "deck",
        "ir_version": "1.9",
        "meta": {"title": "节点类型拼写"},
        "slides": [
            {
                "layout": "architecture_diagram",
                "title": "错误 type 不应静默回退",
                "nodes": [{"id": "module", "text": "处理模块", "type": "moduel"}],
                "edges": [],
                "groups": [],
            }
        ],
    }

    compatible = validate_deck_ir(payload)
    strict = validate_deck_ir(payload, reject_unknown_fields=True)

    assert compatible.ok and compatible.value is not None
    assert compatible.value.slides[0].nodes[0].type == "moduel"
    assert [(item.code, item.loc) for item in compatible.warnings] == [("W105", "slides[0].nodes[0].type")]
    assert "回退 theme default 配色" in compatible.warnings[0].message
    assert strict.value is None
    assert [(item.code, item.loc) for item in strict.errors] == [("D004", "slides[0].nodes[0].type")]


def test_validate_deck_ir_accepts_architecture_diagram_v14() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.9",
            "meta": {"title": "技术架构"},
            "slides": [
                {
                    "layout": "architecture_diagram",
                    "title": "系统架构骨架",
                    "nodes": [
                        {"id": "gateway", "text": "接入层", "type": "primary", "group": "access"},
                        {"id": "service", "text": "服务层", "type": "secondary", "group": "core"},
                        {"id": "data", "text": "数据层", "type": "data", "group": "core"},
                    ],
                    "edges": [
                        {"from": "gateway", "to": "service", "label": "调用", "style": "solid", "direction": "forward"},
                        {"from": "service", "to": "data", "style": "dashed", "direction": "both"},
                    ],
                    "groups": [
                        {"id": "access", "label": "接入域", "node_ids": ["gateway"]},
                        {"id": "core", "label": "核心域", "node_ids": ["service", "data"]},
                    ],
                    "manual_hints": {
                        "node_positions": {"gateway": {"x": 0.1, "y": 0.1}},
                        "node_sizes": {"gateway": {"width": 0.16, "height": 0.15}},
                    },
                }
            ],
        }
    )

    assert result.ok, result.errors
    assert result.value is not None
    slide = result.value.slides[0]
    assert slide.layout == "architecture_diagram"
    assert slide.edges[0].from_node == "gateway"
    assert result.value.model_dump(mode="json")["slides"][0]["edges"][0]["from"] == "gateway"
    assert result.warnings == []


def test_validate_deck_ir_preserves_semantic_and_unregistered_architecture_types() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.9",
            "meta": {"title": "节点语义"},
            "slides": [
                {
                    "layout": "architecture_diagram",
                    "title": "type 由内容明确提供",
                    "nodes": [
                        {"id": "job", "text": "Job", "type": "job"},
                        {"id": "module", "text": "Module", "type": "module"},
                        {"id": "custom", "text": "Custom", "type": "custom_extension"},
                    ],
                    "edges": [{"from": "job", "to": "module"}, {"from": "custom", "to": "module"}],
                    "groups": [],
                }
            ],
        }
    )

    assert result.ok and result.value is not None
    assert [node.type for node in result.value.slides[0].nodes] == ["job", "module", "custom_extension"]


def test_validate_deck_ir_rejects_architecture_edge_to_unknown_node() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法架构"},
            "slides": [
                {
                    "layout": "architecture_diagram",
                    "title": "非法架构",
                    "nodes": [{"id": "known", "text": "已知节点", "type": "primary"}],
                    "edges": [{"from": "known", "to": "missing", "direction": "forward"}],
                    "groups": [],
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"
    assert "unknown node id: missing" in result.errors[0].message


def test_validate_deck_ir_warns_for_nested_architecture_unknown_fields_only() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.9",
            "meta": {"title": "架构未知字段"},
            "slides": [
                {
                    "layout": "architecture_diagram",
                    "title": "架构未知字段",
                    "nodes": [
                        {"id": "a", "text": "节点A", "type": "primary", "unknown_node": True},
                        {"id": "b", "text": "节点B", "type": "secondary"},
                    ],
                    "edges": [{"from": "a", "to": "b", "unknown_edge": True}],
                    "groups": [],
                }
            ],
        }
    )

    assert result.value is not None
    assert [warning.loc for warning in result.warnings] == [
        "slides[0].nodes[0].unknown_node",
        "slides[0].edges[0].unknown_edge",
    ]


def test_validate_document_ir_ignores_nested_unknown_fields_and_warns() -> None:
    from app.ir.validation import validate_document_ir

    result = validate_document_ir(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "a.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-08T00:00:00Z", "extra": "ignored"},
            "stats": {"headings": 0, "paragraphs": 1, "tables": 0, "images": 0, "extra": "ignored"},
            "warnings": [],
            "content": {"blocks": [{"type": "paragraph", "text": "正文", "extra": "ignored"}], "outline": [], "extra": "ignored"},
            "extra": "ignored",
        }
    )

    assert result.value is not None
    assert [warning.code for warning in result.warnings] == ["W104", "W104", "W104", "W104", "W104"]
    assert [warning.loc for warning in result.warnings] == [
        "extra",
        "source.extra",
        "stats.extra",
        "content.extra",
        "content.blocks[0].extra",
    ]


@pytest.mark.parametrize(
    ("slide", "expected_code"),
    [
        ({"layout": "agenda", "items": ["现状", "   "]}, "D004"),
        (
            {
                "layout": "two_column",
                "title": "空栏",
                "left": {"heading": "左栏"},
                "right": {"text": "右栏正文"},
            },
            "D004",
        ),
        (
            {
                "layout": "cards",
                "title": "空卡片",
                "cards": [
                    {"title": "卡片A", "desc": "有效"},
                    {"title": "卡片B", "desc": "   "},
                ],
            },
            "D004",
        ),
        ({"layout": "image", "title": "缺少图片说明"}, "D004"),
        ({"layout": "table", "title": "空表", "table": {"header": ["项", "值"], "rows": []}}, "D005"),
        ({"layout": "conclusion", "title": "结论", "bullets": ["   "]}, "D006"),
    ],
)
def test_validate_deck_ir_rejects_semantically_empty_layout_content(slide: dict, expected_code: str) -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "内容合理性"},
            "slides": [slide],
        }
    )

    assert result.value is None
    assert result.errors[0].code == expected_code


def test_validate_deck_ir_accepts_non_empty_content_for_guarded_layouts() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "内容合理性正例"},
            "slides": [
                {"layout": "agenda", "items": ["现状", "方案"]},
                {
                    "layout": "two_column",
                    "title": "对比",
                    "left": {"heading": "左栏", "text": "现状"},
                    "right": {"heading": "右栏", "bullets": [{"text": "方案"}]},
                },
                {
                    "layout": "cards",
                    "title": "方案",
                    "cards": [{"title": "A", "desc": "主方案"}, {"title": "B", "desc": "备选方案"}],
                },
                {"layout": "image", "title": "架构截图", "placeholder": "待替换源图"},
                {"layout": "table", "title": "结论表", "table": {"header": ["项", "值"], "rows": [["状态", "通过"]]}},
                {"layout": "conclusion", "title": "结论", "bullets": ["采用主方案"]},
            ],
        }
    )

    assert result.ok, result.errors


def test_validate_deck_ir_rejects_conflicting_content_inside_merged_table_cells() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "合并冲突"},
            "slides": [
                {
                    "layout": "table",
                    "title": "合并冲突",
                    "table": {
                        "header": ["方案", "说明", "结论"],
                        "rows": [["方案A", "不应保留", "推荐"]],
                        "cell_spans": [{"area": "body", "row": 0, "col": 0, "rowspan": 1, "colspan": 2}],
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D005"
    assert "covered table cells must be empty" in result.errors[0].message


@pytest.mark.parametrize(
    "chart_patch",
    [
        {"categories": ["1月", "1月"]},
        {
            "categories": ["1月", "2月"],
            "series": [{"name": "方案A", "values": [10, 9]}, {"name": "方案A", "values": [12, 11]}],
        },
    ],
)
def test_validate_deck_ir_rejects_duplicate_chart_dimensions(chart_patch: dict) -> None:
    from app.ir.validation import validate_deck_ir

    chart = {
        "kind": "line",
        "categories": ["1月", "2月"],
        "series": [{"name": "方案A", "values": [10, 9]}],
    }
    chart.update(chart_patch)
    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "重复图表维度"},
            "slides": [{"layout": "chart", "title": "趋势", "chart": chart}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"


@pytest.mark.parametrize(
    "chart_patch",
    [
        {"series": [{"name": "方案A", "values": [10, float("nan")]}]},
        {"thresholds": [{"value": float("inf"), "label": "非法阈值"}]},
        {
            "series": [
                {"name": "方案A", "values": [10, 9], "emphasis": True},
                {"name": "方案B", "values": [12, 11], "emphasis": True},
            ]
        },
    ],
)
def test_validate_deck_ir_rejects_non_finite_or_ambiguous_chart_values(chart_patch: dict) -> None:
    from app.ir.validation import validate_deck_ir

    chart = {
        "kind": "line",
        "categories": ["1月", "2月"],
        "series": [{"name": "方案A", "values": [10, 9]}],
    }
    chart.update(chart_patch)
    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法图表语义"},
            "slides": [{"layout": "chart", "title": "趋势", "chart": chart}],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"


def test_validate_deck_ir_checks_month_start_threshold_claim() -> None:
    from app.ir.validation import validate_deck_ir

    base = {
        "ir_type": "deck",
        "ir_version": "1.7",
        "meta": {"title": "阈值结论"},
        "slides": [
            {
                "layout": "chart",
                "title": "性能趋势",
                "chart": {
                    "kind": "line",
                    "unit": "ms",
                    "categories": ["1月", "2月", "3月"],
                    "series": [{"name": "方案A", "values": [62, 61, 55], "emphasis": True}],
                    "thresholds": [{"value": 60, "label": "目标阈值"}],
                    "side_conclusion": "方案A 2月起低于60ms目标阈值。",
                },
            }
        ],
    }

    invalid = validate_deck_ir(base)
    base["slides"][0]["chart"]["series"][0]["values"] = [62, 58, 55]
    valid = validate_deck_ir(base)

    assert invalid.value is None
    assert invalid.errors[0].code == "D004"
    assert valid.ok, valid.errors


def test_validate_deck_ir_rejects_ambiguous_threshold_conclusion_target() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "歧义结论"},
            "slides": [
                {
                    "layout": "chart",
                    "title": "性能趋势",
                    "chart": {
                        "kind": "line",
                        "categories": ["1月", "2月"],
                        "series": [
                            {"name": "方案A", "values": [62, 58]},
                            {"name": "方案B", "values": [75, 69]},
                        ],
                        "thresholds": [{"value": 60, "label": "目标阈值"}],
                        "side_conclusion": "2月起低于目标阈值。",
                    },
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"
    assert "exactly one emphasized series" in result.errors[0].message


def test_validate_deck_ir_rejects_architecture_self_loop() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "自环架构"},
            "slides": [
                {
                    "layout": "architecture_diagram",
                    "title": "自环架构",
                    "nodes": [{"id": "a", "text": "节点A", "type": "primary"}],
                    "edges": [{"from": "a", "to": "a", "direction": "forward"}],
                    "groups": [],
                }
            ],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"
    assert "self-loop" in result.errors[0].message


def test_validate_deck_ir_accepts_process_flow_and_timeline_v15() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "方案推进"},
            "slides": [
                {
                    "layout": "process_flow",
                    "title": "验证闭环将输入转化为可复核结论",
                    "orientation": "horizontal",
                    "steps": [
                        {"id": "parse", "title": "解析", "description": "提取结构"},
                        {"id": "review", "title": "评审", "description": "核对证据"},
                    ],
                },
                {
                    "layout": "timeline",
                    "title": "三阶段逐步收敛交付风险",
                    "orientation": "vertical",
                    "milestones": [
                        {"label": "阶段一", "title": "基线冻结", "status": "completed"},
                        {"label": "阶段二", "title": "方案验证", "status": "current"},
                        {"label": "阶段三", "title": "内网终审", "status": "planned"},
                    ],
                },
            ],
        }
    )

    assert result.ok, result.errors
    assert result.value is not None
    assert result.value.slides[0].layout == "process_flow"
    assert result.value.slides[1].layout == "timeline"


@pytest.mark.parametrize(
    "slide",
    [
        {
            "layout": "process_flow",
            "title": "步骤不足",
            "steps": [{"id": "only", "title": "仅一步"}],
        },
        {
            "layout": "process_flow",
            "title": "标识重复",
            "steps": [{"id": "same", "title": "一步"}, {"id": "same", "title": "二步"}],
        },
        {
            "layout": "timeline",
            "title": "非法状态",
            "milestones": [
                {"label": "一", "title": "开始", "status": "done"},
                {"label": "二", "title": "结束", "status": "planned"},
            ],
        },
        {
            "layout": "timeline",
            "title": "多个当前阶段",
            "milestones": [
                {"label": "一", "title": "开始", "status": "current"},
                {"label": "二", "title": "继续", "status": "current"},
            ],
        },
        {
            "layout": "timeline",
            "title": "状态顺序逆转",
            "milestones": [
                {"label": "一", "title": "计划", "status": "planned"},
                {"label": "二", "title": "完成", "status": "completed"},
            ],
        },
    ],
)
def test_validate_deck_ir_rejects_invalid_process_flow_and_timeline(slide: dict) -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "非法新版式"},
            "slides": [slide],
        }
    )

    assert result.value is None
    assert result.errors[0].code == "D004"


def test_validate_deck_ir_warns_for_nested_process_and_timeline_unknown_fields() -> None:
    from app.ir.validation import validate_deck_ir

    result = validate_deck_ir(
        {
            "ir_type": "deck",
            "ir_version": "1.9",
            "meta": {"title": "未知字段"},
            "slides": [
                {
                    "layout": "process_flow",
                    "title": "流程",
                    "steps": [
                        {"id": "a", "title": "输入", "unknown_step": True},
                        {"id": "b", "title": "输出"},
                    ],
                },
                {
                    "layout": "timeline",
                    "title": "时间线",
                    "milestones": [
                        {"label": "一", "title": "开始", "unknown_milestone": True},
                        {"label": "二", "title": "结束"},
                    ],
                },
            ],
        }
    )

    assert result.value is not None
    assert [warning.loc for warning in result.warnings] == [
        "slides[0].steps[0].unknown_step",
        "slides[1].milestones[0].unknown_milestone",
    ]


@pytest.mark.parametrize(
    ("block", "expected_code"),
    [
        ({"type": "table", "header": ["项", "值"], "rows": []}, "E004"),
        ({"type": "image_placeholder"}, "E006"),
    ],
)
def test_validate_word_ir_rejects_semantically_empty_blocks(block: dict, expected_code: str) -> None:
    from app.ir.validation import validate_word_ir

    result = validate_word_ir(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "内容合理性"},
            "blocks": [block],
        }
    )

    assert result.value is None
    assert result.errors[0].code == expected_code
