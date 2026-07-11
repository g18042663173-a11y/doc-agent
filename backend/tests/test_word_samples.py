from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


VALID_SAMPLES = [
    "word_valid_01_plain.json",
    "word_valid_02_list.json",
    "word_valid_03_table.json",
]

INVALID_EXPECTATIONS = {
    "word_invalid_e001_bad_json.json": "E001",
    "word_invalid_e002_missing_title.json": "E002",
    "word_invalid_e003_unknown_block.json": "E003",
    "word_invalid_e004_ragged_table.json": "E004",
    "word_invalid_e005_heading_level.json": "E005",
    "word_invalid_e006_empty_list.json": "E006",
}

DIAGNOSTIC_EXPECTATIONS = {
    "word_invalid_w101_heading_jump.json": ("warnings", "W101"),
    "word_invalid_w102_blank_paragraph.json": ("warnings", "W102"),
    "word_invalid_w103_long_text.json": ("warnings", "W103"),
    "word_invalid_w104_unknown_field.json": ("warnings", "W104"),
    "word_invalid_i201_default_classification.json": ("infos", "I201"),
}


def test_word_valid_samples_validate_and_render(tmp_path: Path) -> None:
    from app.ir.validation import validate_word_ir
    from app.rendering.docx_renderer import render_word_ir

    for sample_name in VALID_SAMPLES:
        payload = json.loads((ROOT / "samples" / "ir" / sample_name).read_text(encoding="utf-8"))
        result = validate_word_ir(payload)
        assert result.ok, sample_name
        assert result.value is not None
        output = render_word_ir(result.value, tmp_path / f"{sample_name}.docx")
        assert output.exists()


def test_word_invalid_samples_hit_expected_error_codes() -> None:
    from app.ir.report import format_validation_result
    from app.ir.shell import validate_word_ir_text

    for sample_name, expected_code in INVALID_EXPECTATIONS.items():
        raw = (ROOT / "samples" / "ir" / sample_name).read_text(encoding="utf-8")
        result = validate_word_ir_text(raw)
        report = format_validation_result(result)
        assert result.value is None, sample_name
        assert result.errors[0].code == expected_code, report
        assert expected_code in report
        assert "建议" in report


def test_word_diagnostic_samples_hit_expected_warning_or_info_codes() -> None:
    from app.ir.validation import validate_word_ir

    for sample_name, (bucket, expected_code) in DIAGNOSTIC_EXPECTATIONS.items():
        payload = json.loads((ROOT / "samples" / "ir" / sample_name).read_text(encoding="utf-8"))
        if expected_code == "W103":
            payload["blocks"][0]["text"] = "长" * 2001
        result = validate_word_ir(payload)
        items = getattr(result, bucket)
        assert result.value is not None, sample_name
        assert expected_code in [item.code for item in items], sample_name
