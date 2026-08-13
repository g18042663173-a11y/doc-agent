from __future__ import annotations

from app.assets.contracts import AssetManifest, AssetRecord
from app.generation.layout_policy import detect_sequence_evidence, timeline_parts
from app.ir.document_ir import DocumentIR
from app.visual.planner import audit_visual_selection, build_visual_plan
from app.ir.deck_ir import DeckIR


def _document(text: str, *, table: bool = False) -> DocumentIR:
    blocks = [{"type": "heading", "level": 1, "text": "项目复盘"}, {"type": "paragraph", "text": text}]
    if table:
        blocks.append(
            {
                "type": "table",
                "header": ["月份", "收入"],
                "rows": [["1月", "10"], ["2月", "12"], ["3月", "15"]],
            }
        )
    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "report.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-29T00:00:00Z"},
            "stats": {"headings": 1, "paragraphs": 1, "tables": int(table), "images": 0},
            "content": {"blocks": blocks, "outline": [{"level": 1, "text": "项目复盘"}]},
        }
    )


def test_visual_plan_uses_fixed_business_rules_and_does_not_force_images() -> None:
    plan = build_visual_plan(_document("流程分为识别、筛选、闭环三个阶段，并持续循环改进。", table=True))
    layouts = {(item.recommended_layout, item.chart_kind) for item in plan.opportunities}
    assert ("chart", "line") in layouts
    assert any(layout in {"process_flow", "funnel", "cycle"} for layout, _kind in layouts)
    assert all(not item.asset_ids for item in plan.opportunities)


def test_milestone_token_does_not_match_platform_names() -> None:
    # "M1 与 M3 平台" are chip names, not milestones; must not trigger a timeline.
    document = _document("新一代处理器采用 M1 与 M3 平台架构。")
    evidence = detect_sequence_evidence(document.model_dump())
    assert evidence is None or evidence.layout != "timeline"


def test_milestone_token_matches_explicit_milestones() -> None:
    assert timeline_parts("M1 里程碑")[0] == "M1"
    assert timeline_parts("里程碑 M2")[0] == "里程碑 M2"


def test_visual_plan_recommends_image_grid_when_multiple_assets_exist() -> None:
    zero = "0" * 64
    manifest = AssetManifest(
        manifest_version="1.0",
        assets=[
            AssetRecord(
                asset_id=f"asset-{index:012d}", source_type="upload", source_filename=f"{index}.png",
                original_media_type="image/png", original_sha256=zero, normalized_sha256=zero,
                width=100, height=100, pixel_count=10000, bytes=100, relative_path=f"normalized/{index}.png",
                has_alpha=False, exif_orientation_applied=False, metadata_removed=True,
            )
            for index in range(2)
        ],
    )
    plan = build_visual_plan(_document("现场图片用于佐证结果。"), manifest)
    image = next(item for item in plan.opportunities if item.recommended_layout == "image_grid")
    assert len(image.asset_ids) == 2


def test_visual_selection_audit_records_selected_and_rejected_recommendations() -> None:
    plan = build_visual_plan(_document("系统架构包含模块、接口和数据关系。"))
    deck = DeckIR.model_validate(
        {
            "ir_type": "deck", "ir_version": "2.1", "meta": {"title": "结果"},
            "slides": [{"layout": "title_bullets", "title": "结果", "bullets": [{"text": "保留文字说明"}]}],
        }
    )
    audit = audit_visual_selection(plan, deck)
    assert audit.selections
    assert any(not item.selected for item in audit.selections)
    assert all(item.reason for item in audit.selections)


def test_visual_plan_requires_two_time_nodes_and_preserves_numbered_process() -> None:
    document = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "plan.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-29T00:00:00Z"},
            "stats": {"headings": 1, "paragraphs": 1, "tables": 0, "images": 0},
            "content": {
                "blocks": [
                    {"type": "heading", "level": 1, "text": "下步计划"},
                    {"type": "paragraph", "text": "本季度完成基础能力建设。"},
                    {
                        "type": "numbered_list",
                        "items": [
                            {"text": "完成输入解析", "level": 1},
                            {"text": "组装 Prompt 模板", "level": 1},
                        ],
                    },
                ],
                "outline": [{"level": 1, "text": "下步计划"}],
            },
        }
    )

    plan = build_visual_plan(document)

    assert plan.opportunities[0].recommended_layout == "process_flow"
    assert plan.opportunities[0].evidence_refs == ["完成输入解析", "组装 Prompt 模板"]
    assert all(item.recommended_layout != "timeline" for item in plan.opportunities)
