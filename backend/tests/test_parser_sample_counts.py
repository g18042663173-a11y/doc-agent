from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.mark.parametrize(
    ("suffix", "expected_format"),
    [
        ("md", "md"),
        ("docx", "docx"),
        ("xlsx", "xlsx"),
        ("pptx", "pptx"),
    ],
)
def test_parser_sample_matrix_has_five_parseable_files_per_format(suffix: str, expected_format: str) -> None:
    from app.cli.parse import parse_file

    files = sorted((ROOT / "samples" / "input" / "parser_samples").glob(f"*.{suffix}"))

    assert len(files) >= 5
    for path in files:
        document_ir = parse_file(path)
        assert document_ir.ir_type == "document"
        assert document_ir.source.format == expected_format
