from __future__ import annotations

import sys
from pathlib import Path

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
            "ir_version": "1.0",
            "source": {"filename": "huge.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-08T00:00:00Z"},
            "stats": {"headings": 0, "paragraphs": 1, "tables": 0, "images": 0},
            "warnings": [],
            "content": {"blocks": [{"type": "paragraph", "text": "长文本" * 500}], "outline": []},
        }
    )

    prompt = build_prompt(kind="deck", context=context, max_context_chars=300)

    assert "DeckIR v1.1" in prompt
    assert "已截断说明" in prompt
    assert len(prompt.split("[输入 DocumentIR]", 1)[1]) < 700
