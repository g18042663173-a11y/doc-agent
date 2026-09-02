from pathlib import Path

from doc_agent.parsers.md_parser import MarkdownParser


def test_markdown_parser_extracts_headings_bullets_and_tables(tmp_path: Path) -> None:
    source = tmp_path / "input.md"
    source.write_text(
        "\n".join(
            [
                "# 企业文档生成 Agent",
                "",
                "这是项目摘要。",
                "",
                "## 能力范围",
                "- 支持 Markdown",
                "- 支持 Word",
                "",
                "| 模块 | 状态 |",
                "| --- | --- |",
                "| Parser | ready |",
            ]
        ),
        encoding="utf-8",
    )

    ir = MarkdownParser().parse(source)

    assert ir.source_type == "md"
    assert ir.title == "企业文档生成 Agent"
    assert [block.type for block in ir.blocks] == [
        "heading",
        "paragraph",
        "heading",
        "bullet_list",
        "table",
    ]
    assert ir.blocks[3].items == ["支持 Markdown", "支持 Word"]
    assert ir.blocks[4].rows == [["模块", "状态"], ["Parser", "ready"]]
