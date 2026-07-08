from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from app.ir.common import (
    BulletListBlock,
    HeadingBlock,
    ImagePlaceholderBlock,
    NumberedListBlock,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)
from app.ir.word_ir import WordIR


STYLES = {
    "font": "微软雅黑",
    "western_font": "Arial",
    "normal_size": 11,
    "heading_sizes": {1: 18, 2: 15, 3: 13, 4: 12},
    "classification_size": 9,
    "table_border_pt": 0.5,
}


def render_word_ir(ir: WordIR, output_path: Path) -> Path:
    document = Document()
    _configure_styles(document)
    _configure_header_footer(document, ir)

    for block in ir.blocks:
        if isinstance(block, HeadingBlock):
            _render_heading(document, block)
        elif isinstance(block, ParagraphBlock):
            _render_paragraph(document, block)
        elif isinstance(block, BulletListBlock):
            _render_list(document, block, numbered=False)
        elif isinstance(block, NumberedListBlock):
            _render_list(document, block, numbered=True)
        elif isinstance(block, TableBlock):
            _render_basic_table(document, block)
        elif isinstance(block, ImagePlaceholderBlock):
            _render_image_placeholder(document, block)
        elif isinstance(block, PageBreakBlock):
            document.add_page_break()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path


def _configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    _set_style_font(normal, STYLES["normal_size"])

    for level, size in STYLES["heading_sizes"].items():
        style = styles[f"Heading {level}"]
        _set_style_font(style, size, bold=True)

    quote = _get_or_add_paragraph_style(document, "IR Quote")
    _set_style_font(quote, STYLES["normal_size"], italic=True, color=RGBColor(89, 89, 89))
    quote.paragraph_format.left_indent = Inches(0.25)
    quote.paragraph_format.space_before = Pt(6)
    quote.paragraph_format.space_after = Pt(6)

    note = _get_or_add_paragraph_style(document, "IR Note")
    _set_style_font(note, STYLES["normal_size"], color=RGBColor(51, 51, 51))
    note.paragraph_format.left_indent = Inches(0.15)
    note.paragraph_format.right_indent = Inches(0.15)
    note.paragraph_format.space_before = Pt(6)
    note.paragraph_format.space_after = Pt(6)


def _set_style_font(style, size_pt: int, *, bold: bool = False, italic: bool = False, color: RGBColor | None = None) -> None:
    font = style.font
    font.name = STYLES["font"]
    font.size = Pt(size_pt)
    font.bold = bold
    font.italic = italic
    if color is not None:
        font.color.rgb = color
    style.element.rPr.rFonts.set(qn("w:eastAsia"), STYLES["font"])
    style.element.rPr.rFonts.set(qn("w:ascii"), STYLES["western_font"])
    style.element.rPr.rFonts.set(qn("w:hAnsi"), STYLES["western_font"])


def _get_or_add_paragraph_style(document: Document, name: str):
    styles = document.styles
    if name in styles:
        return styles[name]
    return styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def _configure_header_footer(document: Document, ir: WordIR) -> None:
    section = document.sections[0]
    header_text = ir.meta.header_text or ir.meta.title
    footer_text = ir.meta.footer_text or ir.meta.classification

    header = section.header.paragraphs[0]
    header.text = header_text
    _format_runs(header.runs, size=STYLES["classification_size"])

    footer = section.footer.paragraphs[0]
    footer.text = f"{footer_text} | "
    _format_runs(footer.runs, size=STYLES["classification_size"])
    _append_page_number_field(footer)


def _format_runs(runs, *, size: int) -> None:
    for run in runs:
        run.font.name = STYLES["font"]
        run.font.size = Pt(size)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), STYLES["font"])


def _append_page_number_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(end)


def _render_heading(document: Document, block: HeadingBlock) -> None:
    document.add_heading(block.text, level=block.level)


def _render_paragraph(document: Document, block: ParagraphBlock) -> None:
    if block.style == "quote":
        document.add_paragraph(block.text, style="IR Quote")
    elif block.style == "note":
        paragraph = document.add_paragraph(block.text, style="IR Note")
        _shade_paragraph(paragraph, fill="F5F5F5")
    elif block.text.strip():
        document.add_paragraph(block.text)


def _shade_paragraph(paragraph, *, fill: str) -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    paragraph_properties.append(shading)


def _render_list(document: Document, block: BulletListBlock | NumberedListBlock, *, numbered: bool) -> None:
    for item in block.items:
        if numbered:
            style = "List Number" if item.level == 1 else "List Number 2"
        else:
            style = "List Bullet" if item.level == 1 else "List Bullet 2"
        document.add_paragraph(item.text, style=style)


def _render_basic_table(document: Document, block: TableBlock) -> None:
    if block.caption:
        document.add_paragraph(block.caption)
    table = document.add_table(rows=1, cols=len(block.header))
    table.style = "Table Grid"
    table.autofit = False
    _set_table_widths(table, block.col_widths or [1] * len(block.header))
    for index, cell in enumerate(table.rows[0].cells):
        cell.text = block.header[index]
        _format_cell_header(cell)
    _repeat_table_header(table.rows[0])
    for row in block.rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = value
        _set_row_widths(cells, block.col_widths or [1] * len(block.header))


def _set_table_widths(table, ratios: list[float]) -> None:
    total = sum(ratios)
    total_twips = 9360
    widths = [max(1, int(total_twips * ratio / total)) for ratio in ratios]

    table_grid = table._tbl.tblGrid
    for index, grid_col in enumerate(table_grid.gridCol_lst):
        grid_col.set(qn("w:w"), str(widths[index]))

    _set_row_widths(table.rows[0].cells, ratios)


def _set_row_widths(cells, ratios: list[float]) -> None:
    total = sum(ratios)
    total_width = Inches(6.5)
    for index, cell in enumerate(cells):
        width = int(total_width * ratios[index] / total)
        cell.width = width
        tc_width = cell._tc.get_or_add_tcPr().tcW
        tc_width.set(qn("w:w"), str(int(9360 * ratios[index] / total)))
        tc_width.set(qn("w:type"), "dxa")


def _format_cell_header(cell) -> None:
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True
            run.font.name = STYLES["font"]
            run._element.rPr.rFonts.set(qn("w:eastAsia"), STYLES["font"])
    tc_properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), "F5F5F5")
    tc_properties.append(shading)


def _repeat_table_header(row) -> None:
    row_properties = row._tr.get_or_add_trPr()
    table_header = OxmlElement("w:tblHeader")
    table_header.set(qn("w:val"), "true")
    row_properties.append(table_header)


def _render_image_placeholder(document: Document, block: ImagePlaceholderBlock) -> None:
    text = block.caption or block.ref or "图片占位"
    document.add_paragraph(f"[图片占位] {text}", style="IR Note")
