from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from app.ir.deck_ir import (
    AgendaSlide,
    CardsSlide,
    ChartSlide,
    ColumnContent,
    ConclusionSlide,
    CoverSlide,
    DeckIR,
    ImageSlide,
    SectionSlide,
    TableSlide,
    TitleBulletsSlide,
    TwoColumnSlide,
)
from app.rendering.theme import load_theme


def render_deck_ir(deck: DeckIR, output_path: Path) -> Path:
    theme = load_theme(deck.meta.theme)
    prs = Presentation()
    prs.slide_width = Inches(theme["slide"]["width_in"])
    prs.slide_height = Inches(theme["slide"]["height_in"])

    for slide_number, slide_ir in enumerate(deck.slides, start=1):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        if isinstance(slide_ir, CoverSlide):
            _render_cover(slide, slide_ir, theme)
        elif isinstance(slide_ir, AgendaSlide):
            _render_agenda(slide, slide_ir, theme)
        elif isinstance(slide_ir, SectionSlide):
            _render_section(slide, slide_ir, theme)
        elif isinstance(slide_ir, TitleBulletsSlide):
            _render_title_bullets(slide, slide_ir, theme)
        elif isinstance(slide_ir, TableSlide):
            _render_table_slide(slide, slide_ir, theme)
        elif isinstance(slide_ir, TwoColumnSlide):
            _render_two_column(slide, slide_ir, theme)
        elif isinstance(slide_ir, CardsSlide):
            _render_cards(slide, slide_ir, theme)
        elif isinstance(slide_ir, ConclusionSlide):
            _render_conclusion(slide, slide_ir, theme)
        elif isinstance(slide_ir, ChartSlide):
            _render_chart_placeholder(slide, slide_ir, theme)
        elif isinstance(slide_ir, ImageSlide):
            _render_image_placeholder(slide, slide_ir, theme)
        else:
            _render_placeholder(slide, slide_ir.layout, theme)
        _add_footer(slide, deck.meta.classification, slide_number, theme)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    return output_path


def _render_cover(slide, slide_ir: CoverSlide, theme: dict) -> None:
    _red_bar(slide, theme, top=5.85, height=0.12)
    _add_text(slide, slide_ir.title, 0.85, 2.15, 11.6, 0.8, theme, size=theme["font_sizes_pt"]["cover_title"], bold=True)
    if slide_ir.subtitle:
        _add_text(slide, slide_ir.subtitle, 0.9, 3.05, 10.8, 0.45, theme, size=theme["font_sizes_pt"]["cover_subtitle"])
    meta = "  ".join(part for part in [slide_ir.presenter, slide_ir.date] if part)
    if meta:
        _add_text(slide, meta, 0.9, 3.65, 8.0, 0.35, theme, size=theme["font_sizes_pt"]["note"], color_key="secondary")


def _render_agenda(slide, slide_ir: AgendaSlide, theme: dict) -> None:
    _title(slide, "目录", theme)
    for index, item in enumerate(slide_ir.items, start=1):
        row = (index - 1) % 5
        col = 0 if index <= 5 else 1
        left = 1.0 + col * 5.8
        top = 1.85 + row * 0.75
        _add_text(slide, f"{index:02d}", left, top, 0.7, 0.35, theme, size=18, bold=True, color_key="hw_red")
        _add_text(slide, item, left + 0.85, top, 4.4, 0.35, theme, size=18)


def _render_section(slide, slide_ir: SectionSlide, theme: dict) -> None:
    _add_text(slide, f"{slide_ir.index:02d}", 0.9, 2.1, 1.6, 0.8, theme, size=44, bold=True, color_key="hw_red")
    _add_text(slide, slide_ir.title, 2.55, 2.25, 8.8, 0.7, theme, size=32, bold=True)
    if slide_ir.subtitle:
        _add_text(slide, slide_ir.subtitle, 2.6, 3.05, 8.0, 0.4, theme, size=16, color_key="secondary")
    _red_bar(slide, theme, top=3.75, height=0.08)


def _render_title_bullets(slide, slide_ir: TitleBulletsSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    top = 1.85
    for bullet in slide_ir.bullets:
        indent = 0.35 if bullet.level == 2 else 0
        mark = "–" if bullet.level == 2 else "•"
        _add_text(slide, f"{mark} {bullet.text}", 1.0 + indent, top, 11.2 - indent, 0.34, theme, size=theme["font_sizes_pt"]["body"])
        top += 0.55


def _render_table_slide(slide, slide_ir: TableSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    rows = len(slide_ir.table.rows) + 1
    cols = len(slide_ir.table.header)
    shape = slide.shapes.add_table(rows, cols, Inches(0.85), Inches(1.8), Inches(11.6), Inches(0.45 * rows))
    table = shape.table
    for col, value in enumerate(slide_ir.table.header):
        cell = table.cell(0, col)
        cell.text = value
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(theme["colors"]["surface"])
        _format_cell(cell, theme, bold=True)
    for row_index, row in enumerate(slide_ir.table.rows, start=1):
        for col, value in enumerate(row):
            cell = table.cell(row_index, col)
            cell.text = value
            _format_cell(cell, theme)


def _render_two_column(slide, slide_ir: TwoColumnSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    _render_column(slide, slide_ir.left, 0.85, 1.85, theme)
    _render_column(slide, slide_ir.right, 6.85, 1.85, theme)


def _render_column(slide, content: ColumnContent, left: float, top: float, theme: dict) -> None:
    if content.heading:
        _add_text(slide, content.heading, left, top, 5.0, 0.35, theme, size=18, bold=True, color_key="hw_red")
        top += 0.55
    if content.text:
        _add_text(slide, content.text, left, top, 5.0, 0.6, theme, size=theme["font_sizes_pt"]["body"], color_key="body")
        top += 0.7
    for bullet in content.bullets:
        indent = 0.25 if bullet.level == 2 else 0
        _add_text(slide, f"• {bullet.text}", left + indent, top, 5.0 - indent, 0.32, theme, size=theme["font_sizes_pt"]["body"], color_key="body")
        top += 0.48


def _render_cards(slide, slide_ir: CardsSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    count = len(slide_ir.cards)
    card_width = 11.6 / count
    for index, card in enumerate(slide_ir.cards):
        left = 0.85 + index * card_width
        _card_box(slide, left, 2.0, card_width - 0.25, 2.1, theme)
        _add_text(slide, card.title, left + 0.25, 2.25, card_width - 0.75, 0.35, theme, size=18, bold=True)
        _add_text(slide, card.desc, left + 0.25, 2.85, card_width - 0.75, 0.55, theme, size=14, color_key="body")
        if card.tag:
            _add_text(slide, card.tag, left + 0.25, 3.45, card_width - 0.75, 0.25, theme, size=11, color_key="secondary")


def _card_box(slide, left: float, top: float, width: float, height: float, theme: dict) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(theme["colors"]["surface"])
    shape.line.color.rgb = _rgb(theme["colors"]["surface"])
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(theme["colors"]["hw_red"])
    bar.line.fill.background()


def _render_conclusion(slide, slide_ir: ConclusionSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    top = 1.95
    for bullet in slide_ir.bullets:
        _add_text(slide, f"• {bullet}", 1.1, top, 10.8, 0.35, theme, size=theme["font_sizes_pt"]["body"], color_key="body")
        top += 0.58
    if slide_ir.cta:
        _add_text(slide, slide_ir.cta, 1.1, 5.2, 10.0, 0.45, theme, size=20, bold=True, color_key="hw_red")


def _render_chart_placeholder(slide, slide_ir: ChartSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    _add_text(slide, "图表待内网 Skill / 后续版本生成", 0.95, 1.65, 8.0, 0.35, theme, size=14, color_key="secondary")
    rows = len(slide_ir.chart.categories) + 1
    cols = len(slide_ir.chart.series) + 1
    shape = slide.shapes.add_table(rows, cols, Inches(0.95), Inches(2.25), Inches(8.8), Inches(max(1.2, 0.35 * rows)))
    table = shape.table
    table.cell(0, 0).text = "类别"
    for col, series in enumerate(slide_ir.chart.series, start=1):
        table.cell(0, col).text = series.name
    for row, category in enumerate(slide_ir.chart.categories, start=1):
        table.cell(row, 0).text = category
        for col, series in enumerate(slide_ir.chart.series, start=1):
            value = series.values[row - 1] if row - 1 < len(series.values) else ""
            table.cell(row, col).text = str(value)
    for row in table.rows:
        for cell in row.cells:
            _format_cell(cell, theme)


def _render_image_placeholder(slide, slide_ir: ImageSlide, theme: dict) -> None:
    _title(slide, slide_ir.title, theme)
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.8), Inches(10.8), Inches(4.2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(theme["colors"]["surface"])
    shape.line.color.rgb = _rgb(theme["colors"]["muted"])
    shape.text = f"图片占位\n{slide_ir.placeholder or slide_ir.image_ref or ''}".strip()
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            _format_run(run, theme, size=18, bold=True, color_key="secondary")
    if slide_ir.caption:
        _add_text(slide, slide_ir.caption, 1.0, 6.08, 10.0, 0.3, theme, size=12, color_key="secondary")


def _render_placeholder(slide, layout: str, theme: dict) -> None:
    _title(slide, f"{layout} 待渲染", theme)
    _add_text(slide, "该版式将在后续任务卡实现。", 1.0, 2.0, 9.0, 0.4, theme, size=16, color_key="secondary")


def _title(slide, text: str, theme: dict) -> None:
    _add_text(slide, text, 0.6, 0.5, 12.1, 0.55, theme, size=theme["font_sizes_pt"]["slide_title"], bold=True)
    _red_bar(slide, theme, top=1.24, height=0.04)


def _red_bar(slide, theme: dict, *, top: float, height: float) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(top), Inches(1.5), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(theme["colors"]["hw_red"])
    shape.line.fill.background()


def _add_footer(slide, classification: str, page_number: int, theme: dict) -> None:
    top = theme["slide"]["footer_top_in"]
    _add_text(slide, classification, 0.6, top, 4.0, 0.22, theme, size=theme["font_sizes_pt"]["footer"], color_key="muted")
    _add_text(slide, str(page_number), 12.1, top, 0.6, 0.22, theme, size=theme["font_sizes_pt"]["footer"], color_key="muted")


def _add_text(
    slide,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    theme: dict,
    *,
    size: float,
    bold: bool = False,
    color_key: str = "title",
):
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    text_frame = shape.text_frame
    text_frame.clear()
    paragraph = text_frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text
    _format_run(run, theme, size=size, bold=bold, color_key=color_key)
    return shape


def _format_cell(cell, theme: dict, *, bold: bool = False) -> None:
    for paragraph in cell.text_frame.paragraphs:
        for run in paragraph.runs:
            _format_run(run, theme, size=theme["font_sizes_pt"]["note"], bold=bold, color_key="body")


def _format_run(run, theme: dict, *, size: float, bold: bool = False, color_key: str = "title") -> None:
    run.font.name = theme["fonts"]["east_asia"][0]
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(theme["colors"][color_key])


def _rgb(hex_color: str) -> RGBColor:
    value = hex_color.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
