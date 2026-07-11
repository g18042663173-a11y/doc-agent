from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_build_prompt_is_deterministic_and_contains_schema() -> None:
    from app.parsers.md_parser import parse_markdown
    from app.prompting.builder import build_prompt

    context = parse_markdown(ROOT / "samples" / "input" / "quarterly_report.md")

    first = build_prompt(kind="word", context=context)
    second = build_prompt(kind="word", context=context)

    assert first == second
    assert "WordIR v1.0" in first
    assert '"ir_type"' in first
    assert "[输入 DocumentIR]" in first
    assert "Q3 业务汇报" in first


def test_build_prompt_truncates_context_and_declares_it() -> None:
    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "huge.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-08T00:00:00Z"},
            "stats": {"headings": 0, "paragraphs": 1, "tables": 0, "images": 0},
            "warnings": [],
            "content": {"blocks": [{"type": "paragraph", "text": "长文本" * 500}], "outline": []},
        }
    )

    prompt = build_prompt(kind="deck", context=context, max_context_chars=300)

    assert "DeckIR v1.4" in prompt
    assert "已截断说明" in prompt
    assert len(prompt.split("[输入 DocumentIR]", 1)[1]) < 700


def test_build_prompt_truncates_context_as_valid_json_by_priority() -> None:
    import json

    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "huge.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-08T00:00:00Z"},
            "stats": {"headings": 1, "paragraphs": 30, "tables": 1, "images": 0},
            "warnings": [],
            "content": {
                "blocks": [
                    {"type": "heading", "level": 1, "text": "关键标题"},
                    *[{"type": "paragraph", "text": f"次要段落 {index} " + "长文本" * 80} for index in range(30)],
                    {"type": "table", "header": ["A", "B"], "rows": [[f"R{row}A", f"R{row}B"] for row in range(20)]},
                ],
                "outline": [{"level": 1, "text": "关键标题"}],
            },
        }
    )

    prompt = build_prompt(kind="word", context=context, max_context_chars=900)
    context_json = prompt.split("[输入 DocumentIR]", 1)[1].split("[字符估算]", 1)[0].strip()
    payload = json.loads(context_json)

    assert payload["content"]["outline"] == [{"level": 1, "text": "关键标题"}]
    assert len(json.dumps(payload, ensure_ascii=False)) <= 900
    assert "按优先级" in prompt


def test_build_deck_prompt_contains_weak_model_rules_and_few_shot() -> None:
    import json

    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None, max_output_chars=6000)

    assert "只输出一个完整的 JSON 对象" in prompt
    assert "不要使用 Markdown 代码围栏" in prompt
    assert "必须以 { 开始、以 } 结束" in prompt
    assert "观点在标题" in prompt
    assert "每页最多 3 个内容点" in prompt
    assert "title_bullets" in prompt and "architecture_diagram" in prompt
    assert "目标 JSON 总长度不得超过 6000 个字符" in prompt
    assert "内容过长时按主题拆成多页" in prompt
    assert "优先组织为 8-10 页技术评审稿" in prompt
    assert "[正例 few-shot]" in prompt
    assert '"ir_type":"deck"' in prompt
    sample = json.loads((ROOT / "samples" / "ir" / "deck_valid_01_minimal.json").read_text(encoding="utf-8"))
    compact_sample = json.dumps(sample, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert compact_sample in prompt
    assert "est_chars=2" in prompt
    assert "```" not in prompt


def test_build_prompt_output_budget_controls_page_and_block_limits() -> None:
    from app.prompting.builder import build_prompt

    small_deck = build_prompt(kind="deck", context=None, max_output_chars=4000)
    large_deck = build_prompt(kind="deck", context=None, max_output_chars=8000)
    small_word = build_prompt(kind="word", context=None, max_output_chars=4000)

    assert "最多 5 页" in small_deck
    assert "最多 10 页" in large_deck
    assert "优先组织为 8-10 页技术评审稿" not in small_deck
    assert "优先组织为 8-10 页技术评审稿" in large_deck
    assert "最多 13 个 blocks" in small_word


def test_stub_channel_accepts_hardened_prompt_and_returns_valid_ir() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None, max_output_chars=6000)
    raw = StubGenerator().generate(prompt, target="deck_ir")

    deck = DeckIR.model_validate_json(raw)
    assert "严格字段结构" in prompt
    assert "最多 8 页" in prompt
    assert deck.ir_type == "deck"


def test_prompt_normalizes_volatile_parse_timestamp() -> None:
    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    base = {
        "ir_type": "document",
        "ir_version": "1.1",
        "source": {"filename": "same.md", "format": "md", "size_kb": 1},
        "stats": {},
        "content": {"blocks": [{"type": "paragraph", "text": "同一内容"}]},
    }
    first = DocumentIR.model_validate({**base, "source": {**base["source"], "parsed_at": "2026-07-10T01:00:00Z"}})
    second = DocumentIR.model_validate({**base, "source": {**base["source"], "parsed_at": "2026-07-10T02:00:00Z"}})

    assert build_prompt(kind="word", context=first) == build_prompt(kind="word", context=second)
    assert "<normalized-for-determinism>" in build_prompt(kind="word", context=first)


def test_stub_output_changes_with_document_content_and_preserves_primary_fact() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.word_ir import WordIR
    from app.parsers.md_parser import parse_markdown
    from app.prompting.builder import build_prompt

    generator = StubGenerator()
    first_context = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_01.md")
    second_context = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_02.md")
    first_prompt = build_prompt(kind="word", context=first_context)
    second_prompt = build_prompt(kind="word", context=second_context)

    first_word_raw = generator.generate(first_prompt, target="word_ir")
    second_word_raw = generator.generate(second_prompt, target="word_ir")
    first_deck_raw = generator.generate(build_prompt(kind="deck", context=first_context), target="deck_ir")
    second_deck_raw = generator.generate(build_prompt(kind="deck", context=second_context), target="deck_ir")

    WordIR.model_validate_json(first_word_raw)
    WordIR.model_validate_json(second_word_raw)
    DeckIR.model_validate_json(first_deck_raw)
    DeckIR.model_validate_json(second_deck_raw)
    assert first_word_raw != second_word_raw
    assert first_deck_raw != second_deck_raw
    assert "Markdown 样例 1" in first_word_raw and "Markdown 样例 1" in first_deck_raw
    assert "Markdown 样例 2" in second_word_raw and "Markdown 样例 2" in second_deck_raw


def test_stub_maps_each_document_format_in_process() -> None:
    from app.cli.parse import parse_file
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.word_ir import WordIR
    from app.prompting.builder import build_prompt

    samples = {
        "md_sample_01.md": "Markdown 样例 1",
        "docx_sample_01.docx": "DOCX 样例 1",
        "xlsx_sample_01.xlsx": "台账1",
        "pptx_sample_01.pptx": "PPTX 样例 1",
    }
    generator = StubGenerator()
    for sample_name, marker in samples.items():
        context = parse_file(ROOT / "samples" / "input" / "parser_samples" / sample_name)
        word = WordIR.model_validate_json(generator.generate(build_prompt(kind="word", context=context), target="word_ir"))
        deck = DeckIR.model_validate_json(generator.generate(build_prompt(kind="deck", context=context), target="deck_ir"))

        assert marker in word.model_dump_json()
        assert marker in deck.model_dump_json()
        assert any(block.type == "table" for block in word.blocks)
        assert any(slide.layout == "table" for slide in deck.slides)


def test_stub_handles_image_page_break_empty_sheet_and_dirty_prompt_edges() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.document_ir import DocumentIR
    from app.ir.word_ir import WordIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "图片说明.docx", "format": "docx", "size_kb": 1, "parsed_at": "now"},
            "stats": {"images": 1},
            "content": {
                "blocks": [
                    {"type": "heading", "level": 1, "text": "图片说明"},
                    {"type": "image_placeholder", "caption": "图1: 架构"},
                    {"type": "page_break"},
                ]
            },
        }
    )
    empty_sheet_context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "空台账.xlsx", "format": "xlsx", "size_kb": 1, "parsed_at": "now"},
            "stats": {"tables": 1},
            "content": {"sheets": [{"name": "空表", "nrows": 0, "ncols": 0}]},
        }
    )
    generator = StubGenerator()

    word = WordIR.model_validate_json(generator.generate(build_prompt(kind="word", context=context), target="word_ir"))
    empty_sheet_word = WordIR.model_validate_json(
        generator.generate(build_prompt(kind="word", context=empty_sheet_context), target="word_ir")
    )
    fallback = WordIR.model_validate_json(generator.generate("[输入 DocumentIR]\n{broken", target="word_ir"))

    assert [block.type for block in word.blocks] == ["heading", "image_placeholder"]
    assert [block.type for block in empty_sheet_word.blocks] == ["heading", "paragraph"]
    assert fallback.meta.title == "Stub 文档"
    with pytest.raises(ValueError, match="unsupported target"):
        generator.generate("", target="unsupported")  # type: ignore[arg-type]


def test_deck_prompt_optional_depth_rules_leave_legacy_prompt_unchanged() -> None:
    from app.parsers.md_parser import parse_markdown
    from app.prompting.builder import build_prompt

    context = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_01.md")
    legacy = build_prompt(kind="deck", context=context)
    standard = build_prompt(kind="deck", context=context, depth="标准")
    detailed = build_prompt(kind="deck", context=context, depth="详细", pages=16)

    assert hashlib.sha256(legacy.encode("utf-8")).hexdigest() == (
        "9bf4674d081d1b11b95874bdc43aee10ae10c69b6f8df28cf756cfe4bd21f6da"
    )
    from app.generators.stub import StubGenerator

    legacy_raw = StubGenerator().generate(legacy, target="deck_ir")
    assert hashlib.sha256(legacy_raw.encode("utf-8")).hexdigest() == (
        "e8cb08de16a9d38036c63ed98f3ec25e8d28c4a554ed10bd721f2d3f9e8efc55"
    )
    assert "[生成深度与目标页数]" not in legacy
    assert "结论句 + 1个关键支撑" in standard
    assert "10-12 页" in standard
    assert "必须恰好生成 16 页" in detailed
    assert "结论 + 具体方法/架构名称 + 关键数据/指标 + 必要的权衡或适用条件" in detailed
    assert "CNN-LSTM" in detailed and "1000km LEO" in detailed and "NMSE -10dB" in detailed
    assert "严禁标题党" in detailed
