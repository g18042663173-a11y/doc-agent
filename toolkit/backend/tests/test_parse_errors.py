from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
PY_ENV = {**os.environ, "PYTHONPATH": str(BACKEND)}


@pytest.mark.parametrize(
    ("suffix", "parser_name"),
    [
        (".md", "parse_markdown"),
        (".docx", "parse_docx"),
        (".xlsx", "parse_xlsx"),
        (".pptx", "parse_pptx"),
    ],
)
def test_each_parser_maps_unreadable_input_to_e001(tmp_path: Path, suffix: str, parser_name: str) -> None:
    from app.parsers import docx_parser, md_parser, pptx_parser, xlsx_parser
    from app.parsers.errors import ParseFailure

    path = tmp_path / f"corrupt{suffix}"
    path.write_bytes(b"\xff")
    parser = getattr(
        {
            "parse_markdown": md_parser,
            "parse_docx": docx_parser,
            "parse_xlsx": xlsx_parser,
            "parse_pptx": pptx_parser,
        }[parser_name],
        parser_name,
    )

    with pytest.raises(ParseFailure, match="E001") as exc_info:
        parser(path)

    assert exc_info.value.code == "E001"


def test_parse_file_maps_unsupported_suffix_to_e003(tmp_path: Path) -> None:
    from app.cli.parse import parse_file
    from app.parsers.errors import ParseFailure

    path = tmp_path / "source.txt"
    path.write_text("plain text", encoding="utf-8")

    with pytest.raises(ParseFailure, match="E003") as exc_info:
        parse_file(path)

    assert exc_info.value.code == "E003"


def test_parse_cli_writes_structured_error_report(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.xlsx"
    output = tmp_path / "document.json"
    source.write_bytes(b"not a workbook")

    result = subprocess.run(
        [sys.executable, "-m", "app.cli.parse", str(source), "--output", str(output)],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    report_path = output.with_suffix(".report.json")
    assert result.returncode == 1
    assert "E001" in result.stderr
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"]["pass"] is False
    assert report["items"][0]["code"] == "E001"
