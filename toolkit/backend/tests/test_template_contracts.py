from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.template.contracts import (
    TemplatePlan,
    TemplateProfile,
    TemplateReplacementAudit,
    template_schema_documents,
)


ROOT = Path(__file__).resolve().parents[2]


def _profile_payload() -> dict:
    return {
        "profile_version": "1.0",
        "source": {"filename": "template.pptx", "sha256": "a" * 64, "bytes": 1024},
        "slide_width_in": 13.333,
        "slide_height_in": 7.5,
        "theme": {
            "major_fonts": ["等线 Light"],
            "minor_fonts": ["等线"],
            "colors": {"accent1": "3494BA", "text1": "000000", "background1": "FFFFFF"},
        },
        "slides": [
            {
                "index": 1,
                "prototype_id": "slide-001",
                "role": "cover",
                "layout_name": "标题幻灯片",
                "master_name": "母版",
                "safe_to_clone": True,
                "shapes": [
                    {
                        "shape_id": 2,
                        "name": "Title 1",
                        "kind": "text",
                        "role": "title",
                        "left_ratio": 0.1,
                        "top_ratio": 0.2,
                        "width_ratio": 0.8,
                        "height_ratio": 0.2,
                        "text_preview": "模板标题",
                        "style": {"font_name": "等线", "font_size_pt": 30, "bold": True},
                        "capacity": {"char_capacity": 30, "line_capacity": 2, "list_item_capacity": 1},
                    }
                ],
            }
        ],
    }


def test_template_profile_accepts_regular_shapes_and_off_canvas_decoration() -> None:
    payload = _profile_payload()
    payload["slides"][0]["shapes"].append(
        {
            "shape_id": 3,
            "name": "Decoration",
            "kind": "shape",
            "role": "decorative",
            "left_ratio": -0.1,
            "top_ratio": 0.0,
            "width_ratio": 1.2,
            "height_ratio": 0.1,
        }
    )

    profile = TemplateProfile.model_validate(payload)

    assert profile.profile_version == "1.0"
    assert profile.slides[0].shapes[1].left_ratio == -0.1


def test_template_contracts_reject_unknown_fields() -> None:
    payload = _profile_payload()
    payload["invented"] = True

    with pytest.raises(ValidationError, match="invented"):
        TemplateProfile.model_validate(payload)


def test_template_plan_records_strategy_scores_replacements_and_warnings() -> None:
    plan = TemplatePlan.model_validate(
        {
            "plan_version": "1.0",
            "template_sha256": "a" * 64,
            "profile_sha256": "b" * 64,
            "deck_ir_version": "1.9",
            "slides": [
                {
                    "output_index": 1,
                    "deck_layout": "cover",
                    "strategy": "prototype_replace",
                    "prototype_id": "slide-001",
                    "prototype_index": 1,
                    "score": 100,
                    "score_details": {"role": 40, "slots": 25, "capacity": 25, "safety": 10, "reuse_penalty": 0},
                    "selection_reason": "cover role and title capacity match",
                    "replacements": [{"shape_id": 2, "role": "title", "source_path": "slides[0].title"}],
                    "warnings": [],
                }
            ],
            "warnings": [
                {"code": "W201", "loc": "slides[1].template", "message": "安全重绘"}
            ],
        }
    )

    assert plan.slides[0].score_details.role == 40
    assert plan.warnings[0].code == "W201"


def test_replacement_audit_is_privacy_safe_and_rejects_invalid_hashes() -> None:
    audit = TemplateReplacementAudit.model_validate(
        {
            "audit_version": "1.0",
            "template_sha256": "a" * 64,
            "plan_sha256": "b" * 64,
            "slides": [
                {
                    "output_index": 1,
                    "prototype_id": "slide-001",
                    "strategy": "prototype_replace",
                    "planned_shapes_exist": True,
                    "unused_text_cleared": True,
                    "no_placeholder_residue": True,
                    "text_fit": True,
                    "shapes": [
                        {
                            "shape_id": 2,
                            "role": "title",
                            "action": "replaced",
                            "source_path": "title",
                            "expected_text_sha256": "c" * 64,
                            "rendered_text_sha256": "c" * 64,
                            "text_fit": True,
                        }
                    ],
                }
            ],
        }
    )

    assert audit.slides[0].shapes[0].action == "replaced"
    with pytest.raises(ValidationError, match="hash"):
        TemplateReplacementAudit.model_validate({**audit.model_dump(), "plan_sha256": "not-a-hash"})


def test_checked_in_template_schemas_match_models() -> None:
    for name, expected in template_schema_documents().items():
        path = ROOT / "backend" / "schemas" / f"{name}.schema.json"
        assert json.loads(path.read_text(encoding="utf-8")) == expected
