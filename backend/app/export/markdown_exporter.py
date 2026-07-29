"""Deterministic DocumentIR-to-Markdown export for text-only generators."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.cli.parse import parse_file
from app.ir.document_ir import DocumentIR, DocumentTableBlock, SheetSummary, SlideSummary


def export_document_markdown(document: DocumentIR) -> str:
    """Return a Markdown representation of all text-bearing DocumentIR content.

    Office parsers deliberately retain spreadsheet and slide content as summaries
    rather than ``blocks``.  This exporter converts those summaries into normal
    Markdown so an IR from any supported input format can be sent to a text-only
    generator without re-parsing the original binary.
    """

    parts: list[str] = []
    if document.content.blocks:
        parts.extend(_export_block(block) for block in document.content.blocks)
    elif document.content.outline:
        parts.extend(f"{'#' * item.level} {item.text}" for item in document.content.outline)
    if document.content.sheets:
        parts.extend(_export_sheet(sheet) for sheet in document.content.sheets)
    if document.content.slides:
        parts.extend(_export_slide(slide) for slide in document.content.slides)
    if document.warnings:
        parts.append(_html_comment("解析提示", document.warnings))
    if not parts:
        parts.append("> 未解析出可导出的正文内容。")
    return "\n\n".join(part for part in parts if part) + "\n"


def export_file_markdown(path: Path) -> str:
    """Parse a supported input file with the existing parser, then export Markdown."""

    return export_document_markdown(parse_file(path))


def _export_block(block) -> str:
    match block.type:
        case "heading":
            return f"{'#' * block.level} {block.text}"
        case "paragraph":
            return _quote(block.text) if block.style in {"quote", "note"} else block.text
        case "code_block":
            language = _language_marker(block.language)
            fence = _code_fence(block.code)
            closing_prefix = "" if block.code.endswith(("\n", "\r")) else "\n"
            return f"{fence}{language}\n{block.code}{closing_prefix}{fence}"
        case "bullet_list":
            return _list_items(block.items, marker="-")
        case "numbered_list":
            return _list_items(block.items, marker="1.")
        case "table":
            return _table(block)
        case "image_placeholder":
            return _image_placeholder(block.caption, block.ref)
        case "page_break":
            return "---"
    raise ValueError(f"unsupported DocumentIR block type: {block.type}")


def _export_sheet(sheet: SheetSummary) -> str:
    parts = [f"# 工作表：{sheet.name}"]
    parts.append(
        f"<!-- 行数 {sheet.nrows}；列数 {sheet.ncols}；公式单元格 {sheet.formula_count}；合并单元格 {sheet.merged_count} -->"
    )
    if not sheet.preview_rows:
        parts.append("> 空工作表。")
    else:
        header = sheet.header_guess or sheet.preview_rows[0]
        rows = sheet.preview_rows[1:]
        merged_title = _repeated_sheet_title(header)
        if merged_title and rows:
            parts.append(f"**{merged_title}**")
            header, rows = rows[0], rows[1:]
        parts.append(_table_from_rows(header, rows))
    if sheet.truncated:
        parts.append("> 工作表预览已按解析器上限截断；以上为可用预览。")
    if sheet.col_stats:
        parts.append(
            _html_comment(
                "列画像",
                [json.dumps(stat.model_dump(mode="json"), ensure_ascii=False) for stat in sheet.col_stats],
            )
        )
    return "\n\n".join(parts)


def _export_slide(slide: SlideSummary) -> str:
    title = slide.title or f"第 {slide.index} 页"
    parts = [f"# {title}"]
    body_items = [body for body in slide.bodies if body.strip() != title.strip()]
    if body_items:
        parts.append("\n".join(f"- {body}" for body in body_items))
    for table in slide.tables:
        header = [str(value) for value in table.get("header", [])]
        rows = [[str(value) for value in row] for row in table.get("rows", [])]
        if header:
            parts.append(_table_from_rows(header, rows))
    if slide.notes:
        parts.append(_quote(slide.notes))
    metadata = []
    if slide.layout_name:
        metadata.append(f"layout={slide.layout_name}")
    metadata.extend(slide.shape_warnings)
    if metadata:
        parts.append(_html_comment("幻灯片解析提示", metadata))
    return "\n\n".join(parts)


def _list_items(items, *, marker: str) -> str:
    return "\n".join(f"{'  ' * (item.level - 1)}{marker} {item.text}" for item in items)


def _table(table: DocumentTableBlock) -> str:
    prefix = f"**{table.caption}**\n\n" if table.caption else ""
    return prefix + _table_from_rows(table.header, table.rows)


def _table_from_rows(header: list[str], rows: list[list[str]]) -> str:
    normalized_header = [_table_cell(value) or f"列 {index}" for index, value in enumerate(header, start=1)]
    width = len(normalized_header)
    lines = [
        "| " + " | ".join(normalized_header) + " |",
        "| " + " | ".join("---" for _ in normalized_header) + " |",
    ]
    for row in rows:
        values = [_table_cell(value) for value in row[:width]]
        values.extend("" for _ in range(width - len(values)))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _table_cell(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def _repeated_sheet_title(cells: list[str]) -> str | None:
    values = [cell.strip() for cell in cells]
    if len(values) > 1 and values[0] and all(value == values[0] for value in values):
        return values[0]
    return None


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines() or [""])


def _image_placeholder(caption: str | None, ref: str | None) -> str:
    alt = (caption or ref or "图片占位").replace("]", "\\]")
    destination = ref or "#image-placeholder"
    return f"![{alt}]({destination})"


def _language_marker(language: str | None) -> str:
    if language is None:
        return ""
    return re.sub(r"\s+", "", language)


def _code_fence(code: str) -> str:
    longest_backtick_run = max((len(match.group(0)) for match in re.finditer(r"`+", code)), default=0)
    return "`" * max(3, longest_backtick_run + 1)


def _html_comment(label: str, values: list[str]) -> str:
    safe_values = [value.replace("--", "- -") for value in values]
    return "<!-- " + label + ": " + " | ".join(safe_values) + " -->"
