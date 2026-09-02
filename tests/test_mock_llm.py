from doc_agent.ir.schemas import DeckIR, DocumentBlock, DocumentIR, WordIR
from doc_agent.llm.mock_client import MockLLMClient


def _document() -> DocumentIR:
    return DocumentIR(
        source_file="input.md",
        source_type="md",
        title="企业文档生成 Agent",
        blocks=[
            DocumentBlock(id="b1", type="heading", text="企业文档生成 Agent", level=1),
            DocumentBlock(id="b2", type="paragraph", text="通过结构化 IR 生成企业文档。"),
            DocumentBlock(id="b3", type="bullet_list", items=["解析输入", "规划内容", "渲染文件"]),
        ],
    )


def test_mock_llm_generates_deterministic_deck_ir() -> None:
    prompt = (
        "任务：生成 DeckIR JSON\n"
        "目标页数：6\n"
        f"输入文档 DocumentIR：\n{_document().model_dump_json(ensure_ascii=False)}"
    )

    result = MockLLMClient().generate_json(prompt)
    deck = DeckIR.model_validate(result)

    assert deck.deck_title == "企业文档生成 Agent"
    assert len(deck.slides) == 6
    assert [slide.layout for slide in deck.slides] == [
        "cover",
        "agenda",
        "section",
        "title_bullets",
        "two_column",
        "conclusion",
    ]


def test_mock_llm_generates_deterministic_word_ir() -> None:
    prompt = (
        "任务：生成 WordIR JSON\n"
        f"输入文档 DocumentIR：\n{_document().model_dump_json(ensure_ascii=False)}"
    )

    result = MockLLMClient().generate_json(prompt)
    word = WordIR.model_validate(result)

    assert word.title == "企业文档生成 Agent"
    assert any(block.type == "bullet_list" for block in word.blocks)


def test_mock_llm_uses_v11_layouts_for_larger_decks() -> None:
    prompt = (
        "任务：生成 DeckIR JSON\n"
        "目标页数：9\n"
        f"输入文档 DocumentIR：\n{_document().model_dump_json(ensure_ascii=False)}"
    )

    result = MockLLMClient().generate_json(prompt)
    deck = DeckIR.model_validate(result)

    assert deck.ir_version == "1.1"
    assert {"cards", "chart"}.issubset({slide.layout for slide in deck.slides})
