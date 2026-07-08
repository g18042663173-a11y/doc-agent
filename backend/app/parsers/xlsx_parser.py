from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.ir.document_ir import DocumentIR


MAX_PREVIEW_ROWS = 20
MAX_PREVIEW_COLS = 15


def parse_xlsx(path: Path) -> DocumentIR:
    value_workbook = load_workbook(path, read_only=True, data_only=True)
    formula_workbook = load_workbook(path, read_only=True, data_only=False)
    meta_workbook = load_workbook(path, read_only=False, data_only=False)
    warnings: list[str] = []
    sheets: list[dict] = []

    try:
        for sheet_name in value_workbook.sheetnames:
            sheet = value_workbook[sheet_name]
            formula_sheet = formula_workbook[sheet_name]
            meta_sheet = meta_workbook[sheet_name]
            nrows = sheet.max_row or 0
            ncols = sheet.max_column or 0
            truncated = nrows > MAX_PREVIEW_ROWS or ncols > MAX_PREVIEW_COLS
            if truncated:
                warnings.append(f"xlsx preview truncated for sheet {sheet_name} to 20 rows x 15 columns")

            preview_rows = _preview_rows(sheet)
            header_guess = preview_rows[0] if preview_rows else []
            sheets.append(
                {
                    "name": sheet_name,
                    "nrows": nrows,
                    "ncols": ncols,
                    "header_guess": header_guess,
                    "preview_rows": preview_rows,
                    "col_stats": _column_stats(sheet, nrows, min(ncols, MAX_PREVIEW_COLS)),
                    "formula_count": _formula_count(formula_sheet),
                    "merged_count": len(meta_sheet.merged_cells.ranges),
                    "truncated": truncated,
                }
            )
    finally:
        value_workbook.close()
        formula_workbook.close()
        meta_workbook.close()

    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.0",
            "source": {
                "filename": path.name,
                "format": "xlsx",
                "size_kb": round(path.stat().st_size / 1024, 2),
                "parsed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            "stats": {
                "headings": 0,
                "paragraphs": 0,
                "tables": len(sheets),
                "images": 0,
            },
            "warnings": warnings,
            "content": {"sheets": sheets},
        }
    )


def _preview_rows(sheet) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in sheet.iter_rows(
        min_row=1,
        max_row=min(sheet.max_row or 0, MAX_PREVIEW_ROWS),
        min_col=1,
        max_col=min(sheet.max_column or 0, MAX_PREVIEW_COLS),
        values_only=True,
    ):
        rows.append([_stringify(value) for value in row])
    return rows


def _column_stats(sheet, nrows: int, ncols: int) -> list[dict]:
    stats: list[dict] = []
    for col in range(1, ncols + 1):
        values: list[Any] = []
        samples: list[str] = []
        for row in sheet.iter_rows(min_row=1, max_row=nrows, min_col=col, max_col=col, values_only=True):
            value = row[0]
            if value is None:
                continue
            values.append(value)
            if len(samples) < 3:
                samples.append(_stringify(value))
        stats.append(
            {
                "name": _column_name(sheet, col),
                "type_guess": _type_guess(values),
                "non_empty_ratio": round(len(values) / nrows, 4) if nrows else 0,
                "samples": samples,
            }
        )
    return stats


def _column_name(sheet, col: int) -> str:
    value = sheet.cell(row=1, column=col).value
    return _stringify(value) if value is not None else f"Column {col}"


def _type_guess(values: list[Any]) -> str:
    if not values:
        return "empty"
    non_header = values[1:] if len(values) > 1 else values
    if non_header and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_header):
        return "number"
    if non_header and all(isinstance(value, (datetime, date)) for value in non_header):
        return "date"
    if all(isinstance(value, str) for value in values):
        return "string"
    return "mixed"


def _formula_count(sheet) -> int:
    count = 0
    for row in sheet.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                count += 1
    return count


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
