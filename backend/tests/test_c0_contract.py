from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def load_schema(name: str) -> dict:
    return json.loads((ROOT / "backend" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_word_ir_validates_minimal_report() -> None:
    from app.ir.word_ir import WordIR

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "周报", "classification": "内部公开"},
            "blocks": [
                {"type": "heading", "level": 1, "text": "本周进展"},
                {"type": "paragraph", "text": "完成 C0 契约冻结。"},
            ],
        }
    )

    assert ir.meta.title == "周报"
    assert ir.blocks[0].type == "heading"


def test_word_ir_rejects_empty_blocks() -> None:
    from pydantic import ValidationError

    from app.ir.word_ir import WordIR

    with pytest.raises(ValidationError):
        WordIR.model_validate(
            {
                "ir_type": "word",
                "ir_version": "1.0",
                "meta": {"title": "空文档", "classification": "内部公开"},
                "blocks": [],
            }
        )


def test_document_ir_validates_empty_input_summary() -> None:
    from app.ir.document_ir import DocumentIR

    ir = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.0",
            "source": {
                "filename": "empty.md",
                "format": "md",
                "size_kb": 0,
                "parsed_at": "2026-07-08T00:00:00Z",
            },
            "stats": {"headings": 0, "paragraphs": 0, "tables": 0, "images": 0},
            "warnings": [],
            "content": {"blocks": [], "outline": []},
        }
    )

    assert ir.source.format == "md"
    assert ir.content.blocks == []


def test_deck_ir_validates_minimal_deck() -> None:
    from app.ir.deck_ir import DeckIR

    ir = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "C0 契约冻结", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {"layout": "cover", "title": "C0 契约冻结", "subtitle": "IR / Schema / Stub"},
                {"layout": "agenda", "items": ["IR", "Schema", "Stub"]},
            ],
        }
    )

    assert ir.meta.title == "C0 契约冻结"
    assert [slide.layout for slide in ir.slides] == ["cover", "agenda"]


def test_schema_files_match_current_models() -> None:
    from app.ir.deck_ir import DeckIR
    from app.ir.document_ir import DocumentIR
    from app.ir.word_ir import WordIR
    from app.ir.schema_export import normalized_schema

    assert load_schema("word_ir") == normalized_schema(WordIR)
    assert load_schema("document_ir") == normalized_schema(DocumentIR)
    assert load_schema("deck_ir") == normalized_schema(DeckIR)


def test_word_schema_requires_non_empty_blocks() -> None:
    schema = load_schema("word_ir")

    assert "blocks" in schema["required"]
    assert schema["properties"]["blocks"]["minItems"] == 1


def test_stub_generator_outputs_valid_target_ir() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.word_ir import WordIR

    generator = StubGenerator()

    word = WordIR.model_validate_json(generator.generate("empty", target="word_ir"))
    deck = DeckIR.model_validate_json(generator.generate("empty", target="deck_ir"))

    assert word.ir_type == "word"
    assert deck.ir_type == "deck"


def test_verify_script_runs_empty_stub_chain() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "C0 verify passed" in result.stdout
    assert (ROOT / "output" / "c0_word.docx").exists()
    assert (ROOT / "output" / "c0_deck.pptx").exists()
    report = json.loads((ROOT / "output" / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["pass"] is True
