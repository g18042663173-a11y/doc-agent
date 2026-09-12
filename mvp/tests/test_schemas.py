from pathlib import Path

from doc_agent.ir.schemas import (
    DeckIR,
    CardIR,
    ChartIR,
    ChartSeriesIR,
    DocumentBlock,
    DocumentIR,
    SlideIR,
    VisualIR,
    WordBlockIR,
    WordIR,
    load_json,
    save_json,
    to_pretty_json,
)


def test_document_ir_round_trips_json(tmp_path: Path) -> None:
    ir = DocumentIR(
        source_file="input.md",
        source_type="md",
        title="项目汇报",
        blocks=[
            DocumentBlock(id="b1", type="heading", text="项目汇报", level=1),
            DocumentBlock(id="b2", type="paragraph", text="这是摘要。"),
        ],
    )

    path = tmp_path / "document_ir.json"
    save_json(ir, path)
    loaded = load_json(path, DocumentIR)

    assert loaded == ir
    assert "项目汇报" in to_pretty_json(loaded)


def test_deck_and_word_ir_validate_expected_shapes() -> None:
    deck = DeckIR(
        deck_title="项目汇报",
        slides=[
            SlideIR(layout="cover", title="项目汇报", subtitle="内部汇报"),
            SlideIR(layout="title_bullets", title="重点", bullets=["目标清晰", "风险可控"]),
        ],
    )
    word = WordIR(
        title="项目汇报",
        blocks=[
            WordBlockIR(type="heading", text="摘要", level=1),
            WordBlockIR(type="paragraph", text="项目整体进展稳定。"),
            WordBlockIR(type="bullet_list", items=["目标清晰", "风险可控"]),
        ],
    )

    assert deck.slides[0].layout == "cover"
    assert word.blocks[2].items == ["目标清晰", "风险可控"]


def test_deck_ir_v11_accepts_visual_intent_and_components() -> None:
    deck = DeckIR(
        deck_title="华为风格汇报",
        source_refs=[{"block_id": "b1", "excerpt": "收入增长"}],
        slides=[
            SlideIR(
                layout="cards",
                title="关键判断",
                intent="用卡片承载三个核心观点",
                importance="high",
                cards=[
                    CardIR(title="增长", body="收入保持增长"),
                    CardIR(title="风险", bullets=["交付周期需关注"]),
                ],
            ),
            SlideIR(
                layout="chart",
                title="指标趋势",
                chart=ChartIR(labels=["Q1", "Q2"], series=[ChartSeriesIR(name="收入", values=[1, 2])]),
            ),
            SlideIR(
                layout="image",
                title="方案示意",
                visuals=[VisualIR(kind="placeholder", alt_text="方案架构图")],
            ),
        ],
    )

    loaded = DeckIR.model_validate(deck.model_dump(mode="json"))

    assert loaded.ir_version == "1.1"
    assert loaded.slides[0].cards[0].title == "增长"
    assert loaded.slides[1].chart is not None
    assert loaded.slides[2].visuals[0].alt_text == "方案架构图"
