from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.ir.document_ir import DocumentIR


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
UNORDERED_RE = re.compile(r"^(\s*)[-*]\s+(.+?)\s*$")
ORDERED_RE = re.compile(r"^(\s*)\d+[.)]\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def parse_markdown(path: Path) -> DocumentIR:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    blocks: list[dict] = []
    outline: list[dict] = []
    warnings: list[str] = []
    paragraph_buffer: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph_buffer:
            blocks.append({"type": "paragraph", "text": " ".join(paragraph_buffer).strip()})
            paragraph_buffer.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            text_value = heading.group(2).strip()
            if level > 4:
                warnings.append(f"heading level {level} capped to 4: {text_value}")
                level = 4
            blocks.append({"type": "heading", "level": level, "text": text_value})
            outline.append({"level": level, "text": text_value})
            index += 1
            continue

        if _is_table_start(lines, index):
            flush_paragraph()
            table, consumed, truncated = _parse_table(lines[index:])
            blocks.append(table)
            if truncated:
                warnings.append("markdown table preview truncated to 20 rows")
            index += consumed
            continue

        unordered = UNORDERED_RE.match(line)
        ordered = ORDERED_RE.match(line)
        if unordered or ordered:
            flush_paragraph()
            list_block, consumed = _parse_list(lines[index:], ordered=ordered is not None)
            blocks.append(list_block)
            index += consumed
            continue

        paragraph_buffer.append(stripped)
        index += 1

    flush_paragraph()

    table_count = sum(1 for block in blocks if block["type"] == "table")
    paragraph_count = sum(1 for block in blocks if block["type"] == "paragraph")
    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.0",
            "source": {
                "filename": path.name,
                "format": "md",
                "size_kb": round(path.stat().st_size / 1024, 2),
                "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "stats": {
                "headings": len(outline),
                "paragraphs": paragraph_count,
                "tables": table_count,
                "images": 0,
            },
            "warnings": warnings,
            "content": {"blocks": blocks, "outline": outline},
        }
    )


def _is_table_start(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and "|" in lines[index] and TABLE_SEPARATOR_RE.match(lines[index + 1]) is not None


def _parse_table(lines: list[str]) -> tuple[dict, int, bool]:
    header = _split_table_row(lines[0])
    rows: list[list[str]] = []
    consumed = 2
    truncated = False
    while consumed < len(lines) and "|" in lines[consumed] and lines[consumed].strip():
        row = _split_table_row(lines[consumed])
        if len(row) == len(header):
            if len(rows) < 20:
                rows.append(row)
            else:
                truncated = True
        consumed += 1
    return {"type": "table", "header": header, "rows": rows}, consumed, truncated


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _parse_list(lines: list[str], *, ordered: bool) -> tuple[dict, int]:
    pattern = ORDERED_RE if ordered else UNORDERED_RE
    items: list[dict] = []
    consumed = 0
    while consumed < len(lines):
        match = pattern.match(lines[consumed])
        if match is None:
            break
        indent = len(match.group(1).replace("\t", "    "))
        level = 2 if indent >= 2 else 1
        items.append({"text": match.group(2).strip(), "level": level})
        consumed += 1
    block_type = "numbered_list" if ordered else "bullet_list"
    return {"type": block_type, "items": items}, consumed
