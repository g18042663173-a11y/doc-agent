from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_deck_ir_positive_samples_validate_and_render(tmp_path: Path) -> None:
    from app.ir.validation import validate_deck_ir
    from app.lint.pptx_lint import check_pptx
    from app.rendering.pptx_renderer import render_deck_ir

    for sample_name in [
        "deck_valid_01_minimal.json",
        "deck_valid_02_decision_matrix.json",
        "deck_valid_03_performance_chart.json",
        "deck_valid_04_architecture_diagram.json",
        "deck_valid_05_process_flow.json",
        "deck_valid_06_timeline.json",
        "deck_valid_07_technical_review_12_pages.json",
        "deck_valid_08_layout_selection.json",
        "deck_valid_09_data_bar_kpi.json",
        "deck_valid_10_composite.json",
        "deck_valid_11_composite_stacked.json",
        "deck_valid_12_architecture_semantic_colors.json",
        "deck_valid_full.json",
    ]:
        payload = json.loads((ROOT / "samples" / "ir" / sample_name).read_text(encoding="utf-8"))
        result = validate_deck_ir(payload)
        assert result.ok, sample_name
        assert result.value is not None
        output = render_deck_ir(result.value, tmp_path / f"{sample_name}.pptx")
        report = check_pptx(output, classification=result.value.meta.classification)
        assert output.exists()
        assert report.summary["errors"] == 0


def test_deck_ir_negative_sample_hits_expected_error_code() -> None:
    from app.ir.validation import validate_deck_ir

    expected_errors = {
        "deck_invalid_d003_unknown_layout.json": "D003",
        "deck_invalid_d003_composite_unsupported_component.json": "D003",
        "deck_invalid_d005_bad_table_span.json": "D005",
        "deck_invalid_d004_bad_chart_threshold.json": "D004",
        "deck_invalid_d004_architecture_missing_node.json": "D004",
        "deck_invalid_d004_composite_duplicate_slot.json": "D004",
        "deck_invalid_d004_composite_too_many_components.json": "D004",
        "deck_invalid_d004_process_flow_too_short.json": "D004",
        "deck_invalid_d004_timeline_bad_status.json": "D004",
        "deck_invalid_d004_horizontal_line.json": "D004",
    }
    for sample_name, expected_code in expected_errors.items():
        payload = json.loads((ROOT / "samples" / "ir" / sample_name).read_text(encoding="utf-8"))
        result = validate_deck_ir(payload)

        assert result.value is None, sample_name
        assert result.errors[0].code == expected_code


def test_document_ir_positive_and_negative_samples_validate_as_expected() -> None:
    from app.ir.validation import validate_document_ir

    valid = json.loads((ROOT / "samples" / "ir" / "document_valid_01_md_summary.json").read_text(encoding="utf-8"))
    invalid = json.loads((ROOT / "samples" / "ir" / "document_invalid_missing_source_filename.json").read_text(encoding="utf-8"))

    assert validate_document_ir(valid).ok
    invalid_result = validate_document_ir(invalid)
    assert invalid_result.value is None
    assert invalid_result.errors


def test_document_ir_v11_format_and_preview_samples() -> None:
    from app.ir.validation import validate_document_ir

    valid = json.loads((ROOT / "samples" / "ir" / "document_valid_02_xlsx_preview.json").read_text(encoding="utf-8"))
    mismatch = json.loads((ROOT / "samples" / "ir" / "document_invalid_format_content_mismatch.json").read_text(encoding="utf-8"))
    overflow = json.loads((ROOT / "samples" / "ir" / "document_invalid_preview_overflow.json").read_text(encoding="utf-8"))

    assert validate_document_ir(valid).ok
    assert validate_document_ir(mismatch).errors[0].code == "E001"
    assert validate_document_ir(overflow).errors[0].code == "E001"
