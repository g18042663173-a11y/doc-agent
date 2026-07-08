from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_parse_docx_extracts_headings_paragraph_lists_and_table(tmp_path: Path) -> None:
    from app.parsers.docx_parser import parse_docx

    path = tmp_path / "需求说明.docx"
    doc = Document()
    doc.add_heading("需求说明", level=1)
    doc.add_paragraph("本文件描述输入解析能力。")
    doc.add_heading("功能列表", level=2)
    doc.add_paragraph("解析 DOCX 标题", style="List Bullet")
    doc.add_paragraph("提取表格预览", style="List Bullet 2")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "字段"
    table.cell(0, 1).text = "说明"
    table.cell(1, 0).text = "title"
    table.cell(1, 1).text = "文档标题"
    doc.save(path)

    ir = parse_docx(path)

    assert ir.source.format == "docx"
    assert [item.text for item in ir.content.outline] == ["需求说明", "功能列表"]
    assert [block.type for block in ir.content.blocks] == ["heading", "paragraph", "heading", "bullet_list", "table"]
    assert ir.content.blocks[-1].header == ["字段", "说明"]
    assert ir.content.blocks[-1].rows == [["title", "文档标题"]]


def test_parse_docx_truncates_table_preview_to_20_rows(tmp_path: Path) -> None:
    from app.parsers.docx_parser import parse_docx

    path = tmp_path / "large.docx"
    doc = Document()
    doc.add_heading("大表", level=1)
    table = doc.add_table(rows=26, cols=2)
    table.cell(0, 0).text = "A"
    table.cell(0, 1).text = "B"
    for row in range(1, 26):
        table.cell(row, 0).text = f"A{row}"
        table.cell(row, 1).text = f"B{row}"
    doc.save(path)

    ir = parse_docx(path)

    table_block = ir.content.blocks[-1]
    assert table_block.type == "table"
    assert len(table_block.rows) == 20
    assert any("truncated to 20 rows" in warning for warning in ir.warnings)
