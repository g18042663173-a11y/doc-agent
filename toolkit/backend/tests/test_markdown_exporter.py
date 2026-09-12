from __future__ import annotations

from pathlib import Path

from app.cli.parse import parse_file
from app.export.markdown_exporter import export_document_markdown, export_file_markdown
from app.ir.document_ir import DocumentIR


ROOT = Path(__file__).resolve().parents[2]


def test_export_document_markdown_converts_every_document_block() -> None:
    document = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "input.docx", "format": "docx", "size_kb": 1, "parsed_at": "2026-07-22T00:00:00Z"},
            "stats": {},
            "content": {
                "blocks": [
                    {"type": "heading", "level": 2, "text": "设计说明"},
                    {"type": "paragraph", "text": "普通正文"},
                    {"type": "paragraph", "text": "引用\n第二行", "style": "quote"},
                    {"type": "bullet_list", "items": [{"text": "一级", "level": 1}, {"text": "二级", "level": 2}]},
                    {"type": "numbered_list", "items": [{"text": "步骤", "level": 1}]},
                    {
                        "type": "table",
                        "caption": "接口表",
                        "header": ["字段", "说明"],
                        "rows": [["name", "a|b\n第二行"]],
                    },
                    {"type": "code_block", "language": "python", "code": "if ready:\n    send()"},
                    {"type": "image_placeholder", "caption": "架构图", "ref": "architecture.png"},
                    {"type": "page_break"},
                ]
            },
        }
    )

    markdown = export_document_markdown(document)

    assert "## 设计说明" in markdown
    assert "普通正文" in markdown
    assert "> 引用\n> 第二行" in markdown
    assert "- 一级\n  - 二级" in markdown
    assert "1. 步骤" in markdown
    assert "**接口表**" in markdown
    assert "| name | a\\|b<br>第二行 |" in markdown
    assert "```python\nif ready:\n    send()\n```" in markdown
    assert "![架构图](architecture.png)" in markdown
    assert "\n---\n" in markdown


def test_exporter_escapes_both_brackets_in_image_caption() -> None:
    """A caption with '[' must escape it too, or CommonMark stops recognizing
    the image link and renders the whole line as plain text."""
    document = _document_with_blocks(
        [{"type": "image_placeholder", "caption": "图1 [架构] 说明", "ref": "architecture.png"}]
    )

    markdown = export_document_markdown(document)

    assert "![图1 \\[架构\\] 说明](architecture.png)" in markdown
    assert "\\[架构" in markdown


def test_exporter_uses_a_safe_fence_when_code_contains_backticks() -> None:
    document = _document_with_blocks([{"type": "code_block", "code": "```literal\n    still code"}])

    markdown = export_document_markdown(document)

    assert markdown == "````\n```literal\n    still code\n````\n"


def test_exporter_falls_back_to_outline_when_a_document_has_no_blocks() -> None:
    document = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "outline.docx", "format": "docx", "size_kb": 1, "parsed_at": "2026-07-22T00:00:00Z"},
            "stats": {"headings": 2},
            "content": {"outline": [{"level": 1, "text": "总览"}, {"level": 2, "text": "范围"}]},
        }
    )

    assert export_document_markdown(document) == "# 总览\n\n## 范围\n"


def test_export_document_markdown_preserves_office_summary_metadata_as_comments() -> None:
    workbook = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "sales.xlsx", "format": "xlsx", "size_kb": 1, "parsed_at": "2026-07-22T00:00:00Z"},
            "stats": {},
            "warnings": ["W103: preview truncated"],
            "content": {
                "sheets": [
                    {
                        "name": "销售",
                        "nrows": 3,
                        "ncols": 2,
                        "header_guess": ["月份", "金额"],
                        "preview_rows": [["月份", "金额"], ["一月", "100"]],
                        "col_stats": [{"name": "金额", "type_guess": "number", "samples": ["100"]}],
                    }
                ]
            },
        }
    )
    deck = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "report.pptx", "format": "pptx", "size_kb": 1, "parsed_at": "2026-07-22T00:00:00Z"},
            "stats": {},
            "content": {
                "slides": [
                    {
                        "index": 1,
                        "layout_name": "标题和内容",
                        "title": "项目状态",
                        "bodies": ["主链路完成"],
                        "tables": [{"header": ["事项", "状态"], "rows": [["解析", "完成"]]}],
                        "notes": "汇报时说明风险。",
                        "shape_warnings": ["image present"],
                    }
                ]
            },
        }
    )

    workbook_markdown = export_document_markdown(workbook)
    deck_markdown = export_document_markdown(deck)

    assert "# 工作表：销售" in workbook_markdown
    assert "| 月份 | 金额 |" in workbook_markdown
    assert '"type_guess": "number"' in workbook_markdown
    assert "<!-- 解析提示: W103: preview truncated -->" in workbook_markdown
    assert "# 项目状态" in deck_markdown
    assert "| 事项 | 状态 |" in deck_markdown
    assert "> 汇报时说明风险。" in deck_markdown
    assert "<!-- 幻灯片解析提示: layout=标题和内容 | image present -->" in deck_markdown


def test_export_file_markdown_reuses_existing_word_ppt_excel_parsers() -> None:
    word = export_file_markdown(ROOT / "samples" / "input" / "需求说明.docx")
    deck = export_file_markdown(ROOT / "samples" / "input" / "项目汇报.pptx")
    workbook = export_file_markdown(ROOT / "samples" / "input" / "销售台账.xlsx")

    assert "需求说明" in word
    assert "# 一、建设目标" in word
    assert "| 验收项 | 判据 | 责任角色 |" in word
    assert "# 项目汇报" in deck
    assert deck.count("# 项目汇报") == 1
    assert "# 工作表：" in workbook
    assert "**区域销售台账**" in workbook
    assert "| 区域 | 负责人 | 目标 | 实际 | 完成率 |" in workbook
    assert "|" in workbook


def test_export_file_markdown_preserves_parser_code_block_indentation() -> None:
    markdown = export_file_markdown(ROOT / "samples" / "input" / "synthetic" / "md_03_code_fence.md")

    assert "```c" in markdown
    assert "    uint16_t frame_id;" in markdown


def test_exported_office_markdown_can_be_read_by_the_existing_markdown_parser(tmp_path: Path) -> None:
    for filename in ("需求说明.docx", "项目汇报.pptx", "销售台账.xlsx"):
        markdown_path = tmp_path / f"{Path(filename).stem}.md"
        markdown_path.write_text(
            export_file_markdown(ROOT / "samples" / "input" / filename),
            encoding="utf-8",
        )
        reparsed = parse_file(markdown_path)

        assert reparsed.source.format == "md"
        assert reparsed.content.blocks


def _document_with_blocks(blocks: list[dict]) -> DocumentIR:
    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {"filename": "input.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-22T00:00:00Z"},
            "stats": {},
            "content": {"blocks": blocks},
        }
    )
