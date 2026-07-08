from __future__ import annotations

import sys
import zipfile
import re
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_render_word_ir_creates_editable_docx_with_core_blocks(tmp_path: Path) -> None:
    from app.ir.word_ir import WordIR
    from app.rendering.docx_renderer import render_word_ir

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "项目周报", "classification": "内部公开"},
            "blocks": [
                {"type": "heading", "level": 1, "text": "本周进展"},
                {"type": "paragraph", "text": "完成 DOCX 渲染核心。"},
                {"type": "bullet_list", "items": [{"text": "标题与正文", "level": 1}, {"text": "两级列表", "level": 2}]},
                {"type": "numbered_list", "items": [{"text": "第一步", "level": 1}]},
                {"type": "paragraph", "style": "quote", "text": "引用段落"},
                {"type": "paragraph", "style": "note", "text": "提示段落"},
                {"type": "page_break"},
                {"type": "heading", "level": 2, "text": "下周计划"},
            ],
        }
    )

    output = render_word_ir(ir, tmp_path / "weekly.docx")

    assert output.exists()
    doc = Document(str(output))
    texts = [paragraph.text for paragraph in doc.paragraphs]
    styles = [paragraph.style.name for paragraph in doc.paragraphs]

    assert "本周进展" in texts
    assert "完成 DOCX 渲染核心。" in texts
    assert "标题与正文" in texts
    assert "两级列表" in texts
    assert "下周计划" in texts
    assert "Heading 1" in styles
    assert "Heading 2" in styles
    assert "List Bullet" in styles
    assert "List Bullet 2" in styles
    assert "List Number" in styles
    assert "IR Quote" in styles
    assert "IR Note" in styles


def test_render_word_ir_writes_header_footer_and_page_field(tmp_path: Path) -> None:
    from app.ir.word_ir import WordIR
    from app.rendering.docx_renderer import render_word_ir

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "带页眉页脚", "classification": "内部公开"},
            "blocks": [{"type": "paragraph", "text": "正文"}],
        }
    )

    output = render_word_ir(ir, tmp_path / "header-footer.docx")
    doc = Document(str(output))
    section = doc.sections[0]

    assert "带页眉页脚" in section.header.paragraphs[0].text
    assert "内部公开" in section.footer.paragraphs[0].text
    with zipfile.ZipFile(output) as package:
        footer_xml = "\n".join(
            package.read(name).decode("utf-8")
            for name in package.namelist()
            if name.startswith("word/footer") and name.endswith(".xml")
        )
    assert "PAGE" in footer_xml


def test_render_word_ir_includes_page_break_xml(tmp_path: Path) -> None:
    from app.ir.word_ir import WordIR
    from app.rendering.docx_renderer import render_word_ir

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "分页"},
            "blocks": [
                {"type": "paragraph", "text": "第一页"},
                {"type": "page_break"},
                {"type": "paragraph", "text": "第二页"},
            ],
        }
    )

    output = render_word_ir(ir, tmp_path / "page-break.docx")

    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")
    assert 'w:type="page"' in document_xml or "w:type='page'" in document_xml


def test_render_word_ir_formats_table_header_and_widths(tmp_path: Path) -> None:
    from app.ir.word_ir import WordIR
    from app.rendering.docx_renderer import render_word_ir

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "表格"},
            "blocks": [
                {
                    "type": "table",
                    "caption": "风险清单",
                    "header": ["风险", "等级"],
                    "rows": [["模型 JSON 不稳定", "中"]],
                    "col_widths": [3, 1],
                }
            ],
        }
    )

    output = render_word_ir(ir, tmp_path / "table.docx")
    doc = Document(str(output))

    assert doc.tables[0].cell(0, 0).text == "风险"
    assert doc.tables[0].cell(1, 0).text == "模型 JSON 不稳定"
    assert doc.tables[0].cell(0, 0).paragraphs[0].runs[0].bold is True
    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")
    assert "w:tblHeader" in document_xml
    assert 'w:fill="F5F5F5"' in document_xml
    widths = [int(value) for value in re.findall(r'<w:gridCol w:w="(\d+)"', document_xml)]
    assert widths[:2][0] > widths[:2][1]


def test_render_word_ir_handles_100_by_12_table(tmp_path: Path) -> None:
    from app.ir.word_ir import WordIR
    from app.rendering.docx_renderer import render_word_ir

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "极限表"},
            "blocks": [
                {
                    "type": "table",
                    "header": [f"H{i}" for i in range(12)],
                    "rows": [[f"R{row}C{col}" for col in range(12)] for row in range(100)],
                }
            ],
        }
    )

    output = render_word_ir(ir, tmp_path / "large-table.docx")
    doc = Document(str(output))

    assert len(doc.tables[0].rows) == 101
    assert len(doc.tables[0].columns) == 12
