from __future__ import annotations

from pathlib import Path
import zipfile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from app.ir.common import (
    BulletListBlock,
    CodeBlock,
    HeadingBlock,
    ImagePlaceholderBlock,
    NumberedListBlock,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)
from app.ir.word_ir import WordIR
from app.rendering.theme import load_theme


def render_word_ir(ir: WordIR, output_path: Path) -> Path:
    theme = load_theme("hw_v1")
    document = Document()
    _configure_styles(document, theme)
    _configure_header_footer(document, ir, theme)
    if ir.meta.document_control is not None:
        document.core_properties.category = "HW_DOCUMENT_CONTROL"
        _render_document_control(document, ir, theme)

    for block in ir.blocks:
        if isinstance(block, HeadingBlock):
            _render_heading(document, block)
        elif isinstance(block, ParagraphBlock):
            _render_paragraph(document, block, theme)
        elif isinstance(block, CodeBlock):
            _render_code_block(document, block, theme)
        elif isinstance(block, BulletListBlock):
            _render_list(document, block, numbered=False)
        elif isinstance(block, NumberedListBlock):
            _render_list(document, block, numbered=True)
        elif isinstance(block, TableBlock):
            _render_basic_table(document, block, theme)
        elif isinstance(block, ImagePlaceholderBlock):
            _render_image_placeholder(document, block, theme)
        elif isinstance(block, PageBreakBlock):
            document.add_page_break()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    _replace_legacy_word_blue(output_path, theme)
    return output_path


def _configure_styles(document: Document, theme: dict) -> None:
    styles = document.styles
    normal = styles["Normal"]
    _set_style_font(normal, theme, theme["font_sizes_pt"]["body"], color_key="body")
    normal.paragraph_format.line_spacing = theme["typography"]["line_spacing"]

    heading_sizes = {
        1: theme["font_sizes_pt"]["level1"],
        2: theme["font_sizes_pt"]["level2"],
        3: theme["font_sizes_pt"]["level3"],
        4: theme["font_sizes_pt"]["body"],
    }
    for level, size in heading_sizes.items():
        style = styles[f"Heading {level}"]
        _set_style_font(style, theme, size, bold=True, color_key="hw_red")
        style.paragraph_format.line_spacing = theme["typography"]["line_spacing"]
        style.paragraph_format.space_before = Pt(8 if level == 1 else 6)
        style.paragraph_format.space_after = Pt(4)

    for style_name in ("List Bullet", "List Bullet 2", "List Number", "List Number 2"):
        if style_name in styles:
            _set_style_font(styles[style_name], theme, theme["font_sizes_pt"]["body"], color_key="body")

    quote = _get_or_add_paragraph_style(document, "IR Quote")
    _set_style_font(quote, theme, theme["font_sizes_pt"]["body"], italic=True, color_key="secondary")
    quote.paragraph_format.left_indent = Inches(0.25)
    quote.paragraph_format.space_before = Pt(6)
    quote.paragraph_format.space_after = Pt(6)
    quote.paragraph_format.line_spacing = theme["typography"]["line_spacing"]

    note = _get_or_add_paragraph_style(document, "IR Note")
    _set_style_font(note, theme, theme["font_sizes_pt"]["body"], color_key="body")
    note.paragraph_format.left_indent = Inches(0.15)
    note.paragraph_format.right_indent = Inches(0.15)
    note.paragraph_format.space_before = Pt(6)
    note.paragraph_format.space_after = Pt(6)
    note.paragraph_format.line_spacing = theme["typography"]["line_spacing"]

    code = _get_or_add_paragraph_style(document, "IR Code")
    _set_code_style_font(code, theme)
    code_token = theme["word_code_block"]
    code.paragraph_format.left_indent = Inches(code_token["padding_in"])
    code.paragraph_format.right_indent = Inches(code_token["padding_in"])
    code.paragraph_format.space_before = Pt(code_token["space_before_pt"])
    code.paragraph_format.space_after = Pt(code_token["space_after_pt"])
    code.paragraph_format.line_spacing = 1


def _set_style_font(style, theme: dict, size_pt: int, *, bold: bool = False, italic: bool = False, color_key: str = "body") -> None:
    font = style.font
    font.name = theme["fonts"]["east_asia"][0]
    font.size = Pt(size_pt)
    font.bold = bold
    font.italic = italic
    font.color.rgb = _theme_rgb(theme, color_key)
    _set_rfonts(style.element.get_or_add_rPr(), theme)


def _set_code_style_font(style, theme: dict) -> None:
    code_font = theme["fonts"]["code"][0]
    font = style.font
    font.name = code_font
    font.size = Pt(theme["word_code_block"]["font_size_pt"])
    font.color.rgb = _theme_rgb(theme, "body")
    _set_code_rfonts(style.element.get_or_add_rPr(), theme)


def _get_or_add_paragraph_style(document: Document, name: str):
    styles = document.styles
    if name in styles:
        return styles[name]
    return styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def _configure_header_footer(document: Document, ir: WordIR, theme: dict) -> None:
    section = document.sections[0]
    header_text = ir.meta.header_text or ir.meta.title
    footer_text = ir.meta.footer_text or ir.meta.classification

    header = section.header.paragraphs[0]
    header.text = header_text
    _format_runs(header.runs, theme, size=theme["font_sizes_pt"]["footer"], color_key="body")

    footer = section.footer.paragraphs[0]
    footer.text = f"{footer_text} | "
    _format_runs(footer.runs, theme, size=theme["font_sizes_pt"]["footer"], color_key="secondary")
    _append_page_number_field(footer)
    _format_runs(footer.runs, theme, size=theme["font_sizes_pt"]["footer"], color_key="secondary")


def _format_runs(runs, theme: dict, *, size: int, color_key: str = "body", bold: bool = False) -> None:
    for run in runs:
        run.font.name = theme["fonts"]["east_asia"][0]
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = _theme_rgb(theme, color_key)
        _set_rfonts(run._element.get_or_add_rPr(), theme)


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


def _render_paragraph(document: Document, block: ParagraphBlock, theme: dict) -> None:
    if block.style == "quote":
        paragraph = document.add_paragraph(block.text, style="IR Quote")
        _set_paragraph_left_border(paragraph, theme["colors"]["secondary"], width_pt=1.5)
    elif block.style == "note":
        paragraph = document.add_paragraph(block.text, style="IR Note")
        _shade_paragraph(paragraph, fill=_theme_hex(theme, "table_stripe"))
    elif block.text.strip():
        document.add_paragraph(block.text)


def _render_code_block(document: Document, block: CodeBlock, theme: dict) -> None:
    token = theme["word_code_block"]
    paragraph = document.add_paragraph(style="IR Code")
    paragraph.paragraph_format.keep_together = True
    _shade_paragraph(paragraph, fill=_theme_hex(theme, token["fill_color_key"]))
    _set_paragraph_box_border(
        paragraph,
        theme["colors"][token["border_color_key"]],
        width_pt=token["border_width_pt"],
    )
    lines = block.code.split("\n")
    for index, line in enumerate(lines):
        run = paragraph.add_run(line)
        _format_code_run(run, theme)
        _preserve_run_spaces(run)
        if index < len(lines) - 1:
            run.add_break()


def _render_document_control(document: Document, ir: WordIR, theme: dict) -> None:
    control = ir.meta.document_control
    if control is None:
        return
    token = theme["word_document_control"]
    classification = control.classification or ir.meta.classification
    info_table = document.add_table(rows=2, cols=4)
    info_table.style = "Table Grid"
    info_table.autofit = False
    _set_table_caption(info_table, "HW_DOCUMENT_CONTROL_INFO")
    _set_table_widths(info_table, token["info_col_widths"])
    info_rows = [
        ("产品名称", control.product_name, "文档名称", control.document_name),
        ("密级", classification, "版本号", control.version),
    ]
    for row, values in zip(info_table.rows, info_rows, strict=True):
        for index, value in enumerate(values):
            _write_document_control_cell(row.cells[index], value, theme, label=index % 2 == 0)
        _set_row_widths(row.cells, token["info_col_widths"])

    approval_table = document.add_table(rows=4, cols=3)
    approval_table.style = "Table Grid"
    approval_table.autofit = False
    _set_table_caption(approval_table, "HW_DOCUMENT_CONTROL_APPROVAL")
    _set_table_widths(approval_table, token["approval_col_widths"])
    _write_document_control_row(approval_table.rows[0], ("角色", "姓名", "日期"), theme, label=True)
    prepared_name = control.prepared.name or ir.meta.author
    approval_rows = [
        ("拟制", prepared_name, control.prepared.date),
        ("审核", control.reviewed.name, control.reviewed.date),
        ("批准", control.approved.name, control.approved.date),
    ]
    for row, values in zip(approval_table.rows[1:], approval_rows, strict=True):
        _write_document_control_row(row, values, theme, label=False)
    document.add_paragraph().paragraph_format.space_after = Pt(token["space_after_pt"])


def _write_document_control_row(row, values: tuple[str | None, str | None, str | None], theme: dict, *, label: bool) -> None:
    token = theme["word_document_control"]
    for index, value in enumerate(values):
        _write_document_control_cell(row.cells[index], value, theme, label=label or index == 0)
    _set_row_widths(row.cells, token["approval_col_widths"])


def _write_document_control_cell(cell, value: str | None, theme: dict, *, label: bool) -> None:
    token = theme["word_document_control"]
    text = value if value is not None else token["empty_value_text"]
    cell.text = text
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _set_cell_margins(cell, token["padding_in"])
    if label:
        _shade_cell(cell, _theme_hex(theme, token["label_fill_color_key"]))
    else:
        _shade_cell(cell, _theme_hex(theme, "background"))
    _set_cell_borders(cell, theme, width_pt=token["border_width_pt"], color_key=token["border_color_key"])
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.line_spacing = theme["typography"]["line_spacing"]
        for run in paragraph.runs:
            _format_runs(
                [run],
                theme,
                size=token["label_font_size_pt"] if label else token["value_font_size_pt"],
                color_key="body",
                bold=label,
            )


def _set_table_caption(table, caption: str) -> None:
    table_properties = table._tbl.tblPr
    caption_element = table_properties.find(qn("w:tblCaption"))
    if caption_element is None:
        caption_element = OxmlElement("w:tblCaption")
        table_properties.append(caption_element)
    caption_element.set(qn("w:val"), caption)


def _set_cell_margins(cell, padding_in: float) -> None:
    tc_properties = cell._tc.get_or_add_tcPr()
    margins = tc_properties.find(qn("w:tcMar"))
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_properties.append(margins)
    value = str(int(Inches(padding_in) / 635))
    for edge in ("top", "left", "bottom", "right"):
        margin = margins.find(qn(f"w:{edge}"))
        if margin is None:
            margin = OxmlElement(f"w:{edge}")
            margins.append(margin)
        margin.set(qn("w:w"), value)
        margin.set(qn("w:type"), "dxa")


def _shade_paragraph(paragraph, *, fill: str) -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    paragraph_properties.append(shading)


def _insert_before_shading(container, element) -> None:
    """CT_PPr/CT_TcPr require pBdr/tcBorders before shd; python-pptx appends
    shading, so new border containers must be inserted in front of it."""
    shading = container.find(qn("w:shd"))
    if shading is not None:
        shading.addprevious(element)
    else:
        container.append(element)


def _render_list(document: Document, block: BulletListBlock | NumberedListBlock, *, numbered: bool) -> None:
    styles = document.styles
    primary = "List Number" if numbered else "List Bullet"
    secondary = f"{primary} 2"
    for item in block.items:
        if item.level >= 2 and secondary in styles:
            style = secondary
        elif primary in styles:
            style = primary
        else:
            style = None
        document.add_paragraph(item.text, style=style)


def _format_code_run(run, theme: dict) -> None:
    run.font.name = theme["fonts"]["code"][0]
    run.font.size = Pt(theme["word_code_block"]["font_size_pt"])
    run.font.color.rgb = _theme_rgb(theme, "body")
    _set_code_rfonts(run._element.get_or_add_rPr(), theme)


def _preserve_run_spaces(run) -> None:
    for text in run._r.findall(qn("w:t")):
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def _render_basic_table(document: Document, block: TableBlock, theme: dict) -> None:
    if block.caption:
        caption = document.add_paragraph(block.caption)
        _format_runs(caption.runs, theme, size=theme["font_sizes_pt"]["body_small"], color_key="secondary")
    table = document.add_table(rows=1, cols=len(block.header))
    table.style = "Table Grid"
    table.autofit = False
    _set_table_widths(table, block.col_widths or [1] * len(block.header))
    for index, cell in enumerate(table.rows[0].cells):
        _write_cell(cell, block.header[index], theme, bold=True, color_key="background")
        _shade_cell(cell, _theme_hex(theme, "hw_red"))
        _set_cell_borders(cell, theme)
    _repeat_table_header(table.rows[0])
    for row_index, row in enumerate(block.rows):
        cells = table.add_row().cells
        fill_key = "background" if row_index % 2 == 0 else "table_stripe"
        for index, value in enumerate(row):
            _write_cell(cells[index], value, theme, bold=False, color_key="body")
            _shade_cell(cells[index], _theme_hex(theme, fill_key))
            _set_cell_borders(cells[index], theme)
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


def _write_cell(cell, text: str, theme: dict, *, bold: bool, color_key: str) -> None:
    cell.text = text
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.line_spacing = theme["typography"]["line_spacing"]
        for run in paragraph.runs:
            _format_runs([run], theme, size=theme["font_sizes_pt"]["body"], color_key=color_key, bold=bold)


def _shade_cell(cell, fill: str) -> None:
    tc_properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_properties.append(shading)


def _set_cell_borders(cell, theme: dict, *, width_pt: float | None = None, color_key: str = "border") -> None:
    tc_properties = cell._tc.get_or_add_tcPr()
    borders = tc_properties.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        _insert_before_shading(tc_properties, borders)
    for edge in ("top", "left", "bottom", "right"):
        border = borders.find(qn(f"w:{edge}"))
        if border is None:
            border = OxmlElement(f"w:{edge}")
            borders.append(border)
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(int((width_pt or theme["strokes"]["card_border_pt"]) * 8)))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), _theme_hex(theme, color_key))


def _repeat_table_header(row) -> None:
    row_properties = row._tr.get_or_add_trPr()
    table_header = OxmlElement("w:tblHeader")
    table_header.set(qn("w:val"), "true")
    row_properties.append(table_header)


def _render_image_placeholder(document: Document, block: ImagePlaceholderBlock, theme: dict) -> None:
    table = document.add_table(rows=1, cols=1)
    table.autofit = False
    table.rows[0].height = Inches(1.35)
    table.rows[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    _set_table_widths(table, [1])
    cell = table.cell(0, 0)
    placeholder = "图片占位"
    if block.ref:
        placeholder = f"{placeholder}\n{block.ref}"
    _write_cell(cell, placeholder, theme, bold=True, color_key="body")
    _shade_cell(cell, _theme_hex(theme, "surface"))
    _set_cell_borders(cell, theme)
    if block.caption:
        caption = document.add_paragraph(block.caption)
        _format_runs(caption.runs, theme, size=theme["font_sizes_pt"]["body_small"], color_key="secondary")


def _set_rfonts(rpr, theme: dict) -> None:
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), theme["fonts"]["east_asia"][0])
    rfonts.set(qn("w:ascii"), theme["fonts"]["latin"][0])
    rfonts.set(qn("w:hAnsi"), theme["fonts"]["latin"][0])


def _set_code_rfonts(rpr, theme: dict) -> None:
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    code_font = theme["fonts"]["code"][0]
    rfonts.set(qn("w:eastAsia"), code_font)
    rfonts.set(qn("w:ascii"), code_font)
    rfonts.set(qn("w:hAnsi"), code_font)


def _set_paragraph_left_border(paragraph, color: str, *, width_pt: float) -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    borders = paragraph_properties.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        _insert_before_shading(paragraph_properties, borders)
    left = borders.find(qn("w:left"))
    if left is None:
        left = OxmlElement("w:left")
        borders.append(left)
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(int(width_pt * 8)))
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), color.lstrip("#"))


def _set_paragraph_box_border(paragraph, color: str, *, width_pt: float) -> None:
    paragraph_properties = paragraph._p.get_or_add_pPr()
    borders = paragraph_properties.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        _insert_before_shading(paragraph_properties, borders)
    for edge in ("top", "left", "bottom", "right"):
        border = borders.find(qn(f"w:{edge}"))
        if border is None:
            border = OxmlElement(f"w:{edge}")
            borders.append(border)
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(int(width_pt * 8)))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), color.lstrip("#"))


def _theme_rgb(theme: dict, color_key: str) -> RGBColor:
    return RGBColor.from_string(_theme_hex(theme, color_key))


def _theme_hex(theme: dict, color_key: str) -> str:
    return theme["colors"][color_key].lstrip("#").upper()


def _decode_xml_part(data: bytes) -> str | None:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _replace_legacy_word_blue(output_path: Path, theme: dict) -> None:
    replacement = _theme_hex(theme, "hw_red")
    temp_path = output_path.with_suffix(".tmp.docx")
    try:
        with zipfile.ZipFile(output_path, "r") as source, zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    text = _decode_xml_part(data)
                    if text is not None:
                        text = text.replace("4F81BD", replacement).replace("4f81bd", replacement)
                        data = text.encode("utf-8")
                target.writestr(info, data)
        temp_path.replace(output_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
