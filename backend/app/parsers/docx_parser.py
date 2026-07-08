from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ir.document_ir import DocumentIR


HEADING_STYLE_RE = re.compile(r"^(Heading|标题)\s*([1-6])$")


def parse_docx(path: Path) -> DocumentIR:
    document = Document(str(path))
    blocks: list[dict] = []
    outline: list[dict] = []
    warnings = _unsupported_warnings(path)
    current_list: dict | None = None

    def flush_list() -> None:
        nonlocal current_list
        if current_list is not None:
            blocks.append(current_list)
            current_list = None

    for item in _iter_block_items(document):
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            heading_level = _heading_level(item)
            if heading_level is not None:
                flush_list()
                if heading_level > 4:
                    warnings.append(f"heading level {heading_level} capped to 4: {text}")
                    heading_level = 4
                blocks.append({"type": "heading", "level": heading_level, "text": text})
                outline.append({"level": heading_level, "text": text})
                continue

            list_kind = _list_kind(item)
            if list_kind is not None:
                level = _list_level(item)
                block_type = "numbered_list" if list_kind == "numbered" else "bullet_list"
                if current_list is None or current_list["type"] != block_type:
                    flush_list()
                    current_list = {"type": block_type, "items": []}
                current_list["items"].append({"text": text, "level": level})
                continue

            flush_list()
            blocks.append({"type": "paragraph", "text": text})
        elif isinstance(item, Table):
            flush_list()
            table_block, truncated = _parse_table(item)
            if table_block is not None:
                blocks.append(table_block)
            if truncated:
                warnings.append("docx table preview truncated to 20 rows")

    flush_list()

    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.0",
            "source": {
                "filename": path.name,
                "format": "docx",
                "size_kb": round(path.stat().st_size / 1024, 2),
                "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "stats": {
                "headings": len(outline),
                "paragraphs": sum(1 for block in blocks if block["type"] == "paragraph"),
                "tables": sum(1 for block in blocks if block["type"] == "table"),
                "images": len(document.inline_shapes),
            },
            "warnings": warnings,
            "content": {"blocks": blocks, "outline": outline},
        }
    )


def _iter_block_items(document: DocxDocument) -> Iterator[Paragraph | Table]:
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _heading_level(paragraph: Paragraph) -> int | None:
    match = HEADING_STYLE_RE.match(paragraph.style.name)
    if match is None:
        return None
    return int(match.group(2))


def _list_kind(paragraph: Paragraph) -> str | None:
    style_name = paragraph.style.name
    if "List Bullet" in style_name or "项目符号" in style_name:
        return "bullet"
    if "List Number" in style_name or "编号" in style_name:
        return "numbered"
    return None


def _list_level(paragraph: Paragraph) -> int:
    style_name = paragraph.style.name
    return 2 if re.search(r"(^|\D)2($|\D)", style_name) else 1


def _parse_table(table: Table) -> tuple[dict | None, bool]:
    if not table.rows or not table.columns:
        return None, False
    header = [_cell_text(cell) or f"Column {index + 1}" for index, cell in enumerate(table.rows[0].cells)]
    rows: list[list[str]] = []
    truncated = False
    for row in table.rows[1:]:
        values = [_cell_text(cell) for cell in row.cells]
        if len(rows) < 20:
            rows.append(values)
        else:
            truncated = True
    return {"type": "table", "header": header, "rows": rows}, truncated


def _cell_text(cell) -> str:
    return "\n".join(paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip())


def _unsupported_warnings(path: Path) -> list[str]:
    warnings: list[str] = []
    with zipfile.ZipFile(path) as package:
        xml = "\n".join(
            package.read(name).decode("utf-8", errors="ignore")
            for name in package.namelist()
            if name.startswith("word/") and name.endswith(".xml")
        )
    for needle, label in [
        ("w:commentRangeStart", "comments"),
        ("w:ins", "revisions"),
        ("w:del", "revisions"),
        ("w:txbxContent", "text boxes"),
        ("wps:txbx", "text boxes"),
        ("dgm:", "SmartArt"),
    ]:
        count = xml.count(needle)
        if count:
            warnings.append(f"unsupported {label}: {count}")
    return warnings
