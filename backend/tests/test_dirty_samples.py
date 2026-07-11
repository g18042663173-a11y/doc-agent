from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_make_dirty_samples_generates_parseable_document_ir(tmp_path: Path) -> None:
    from app.cli.parse import parse_file
    from app.ir.document_ir import DocumentIR
    from scripts.make_dirty_samples import DEFAULT_LARGE_ROWS, generate_dirty_samples

    assert DEFAULT_LARGE_ROWS >= 50_000

    generated = generate_dirty_samples(tmp_path, large_rows=120)

    assert {path.suffix for path in generated} == {".docx", ".pptx", ".xlsx"}
    assert len(generated) == 10
    assert (tmp_path / "xlsx_04_large_ledger_50000.xlsx").exists()

    parsed = {path.name: parse_file(path) for path in generated}

    assert all(isinstance(document_ir, DocumentIR) for document_ir in parsed.values())
    assert all(document_ir.ir_type == "document" for document_ir in parsed.values())
    assert all(document_ir.source.format in {"docx", "pptx", "xlsx"} for document_ir in parsed.values())

    merged = parsed["xlsx_01_merged_ledger.xlsx"].content.sheets[0]
    assert merged.merged_count >= 2
    assert merged.preview_rows[0][0] == "部门台账"
    assert merged.preview_rows[0][1] == "部门台账"
    assert merged.preview_rows[1][0] == "部门"

    cross_sheet = parsed["xlsx_02_cross_sheet_refs.xlsx"]
    assert len(cross_sheet.content.sheets) >= 3
    assert sum(sheet.formula_count for sheet in cross_sheet.content.sheets) >= 2

    formula_report = parsed["xlsx_03_formula_report.xlsx"]
    assert sum(sheet.formula_count for sheet in formula_report.content.sheets) >= 3

    large = parsed["xlsx_04_large_ledger_50000.xlsx"].content.sheets[0]
    assert large.truncated is True
    assert len(large.preview_rows) == 20
    assert any("xlsx preview truncated" in warning for warning in parsed["xlsx_04_large_ledger_50000.xlsx"].warnings)

    revisions = parsed["docx_01_revisions_comments.docx"]
    assert any("unsupported comments" in warning for warning in revisions.warnings)
    assert any("unsupported revisions" in warning for warning in revisions.warnings)
    assert any("format revisions" in warning for warning in revisions.warnings)

    nested_docx = parsed["docx_02_nested_lists_table_sections.docx"]
    assert any(block.type.endswith("_list") for block in nested_docx.content.blocks)
    assert any(block.type == "table" for block in nested_docx.content.blocks)
    assert not any("unsupported revisions" in warning for warning in nested_docx.warnings)

    image_docx = parsed["docx_03_embedded_image.docx"]
    assert image_docx.stats.images == 1
    assert any("docx image present" in warning for warning in image_docx.warnings)
    assert not any("unsupported revisions" in warning for warning in image_docx.warnings)

    nested_groups = parsed["pptx_01_nested_groups.pptx"]
    assert any("组合内层行动项" in body for slide in nested_groups.content.slides for body in slide.bodies)

    notes = parsed["pptx_02_table_notes.pptx"].content.slides[0]
    assert notes.tables
    assert notes.notes == "演讲备注:强调风险闭环和下周资源协调。"

    complex_graphics = parsed["pptx_03_smartart_equivalent.pptx"]
    assert any("SmartArt unsupported" in warning for warning in complex_graphics.warnings)
