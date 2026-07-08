from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_parse_xlsx_summarizes_sheets_formulas_and_merged_cells(tmp_path: Path) -> None:
    from app.parsers.xlsx_parser import parse_xlsx

    path = tmp_path / "销售台账.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "销售"
    sheet.append(["区域", "销售额", "备注"])
    sheet.append(["华东", 100, "稳定"])
    sheet.append(["华南", 120, "增长"])
    sheet["D2"] = "=B2*2"
    sheet.merge_cells("A5:B5")
    sheet["A5"] = "合并说明"
    workbook.create_sheet("空表")
    workbook.save(path)

    ir = parse_xlsx(path)

    sales = ir.content.sheets[0]
    assert ir.source.format == "xlsx"
    assert sales.name == "销售"
    assert sales.nrows == 5
    assert sales.ncols == 4
    assert sales.header_guess == ["区域", "销售额", "备注", ""]
    assert sales.preview_rows[1][:3] == ["华东", "100", "稳定"]
    assert sales.formula_count == 1
    assert sales.merged_count == 1
    assert sales.col_stats[1].type_guess == "number"
    assert sales.col_stats[1].non_empty_ratio > 0


def test_parse_xlsx_truncates_preview_to_20_by_15(tmp_path: Path) -> None:
    from app.parsers.xlsx_parser import parse_xlsx

    path = tmp_path / "wide.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    for row in range(25):
        sheet.append([f"R{row}C{col}" for col in range(18)])
    workbook.save(path)

    ir = parse_xlsx(path)
    sheet_summary = ir.content.sheets[0]

    assert len(sheet_summary.preview_rows) == 20
    assert len(sheet_summary.preview_rows[0]) == 15
    assert sheet_summary.truncated is True
    assert any("xlsx preview truncated" in warning for warning in ir.warnings)
