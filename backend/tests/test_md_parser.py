from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_parse_markdown_extracts_blocks_outline_and_stats() -> None:
    from app.parsers.md_parser import parse_markdown

    ir = parse_markdown(ROOT / "samples" / "input" / "quarterly_report.md")

    assert ir.ir_type == "document"
    assert ir.source.format == "md"
    assert ir.stats.headings == 4
    assert ir.stats.paragraphs == 1
    assert ir.stats.tables == 1
    assert [item.text for item in ir.content.outline] == ["Q3 业务汇报", "关键进展", "风险清单", "下步计划"]
    assert [block.type for block in ir.content.blocks] == [
        "heading",
        "paragraph",
        "heading",
        "bullet_list",
        "heading",
        "table",
        "heading",
        "numbered_list",
    ]


def test_parse_markdown_round_trips_to_docx(tmp_path: Path) -> None:
    from app.ir.word_ir import WordIR
    from app.parsers.md_parser import parse_markdown
    from app.rendering.docx_renderer import render_word_ir

    document_ir = parse_markdown(ROOT / "samples" / "input" / "quarterly_report.md")
    word_ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "Q3 业务汇报"},
            "blocks": [block.model_dump() for block in document_ir.content.blocks],
        }
    )

    output = render_word_ir(word_ir, tmp_path / "roundtrip.docx")
    doc = Document(str(output))

    assert "Q3 业务汇报" in [paragraph.text for paragraph in doc.paragraphs]
    assert doc.tables[0].cell(0, 0).text == "风险"
