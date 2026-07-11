from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
PY_ENV = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}


def _run(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("module", "args"),
    [
        ("app.cli.parse", []),
        ("app.cli.prompt", []),
        ("app.cli.render", []),
        ("app.cli.check", []),
    ],
)
def test_each_cli_argument_failure_has_code_and_no_traceback(module: str, args: list[str]) -> None:
    result = _run(module, *args)

    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["items"][0]["code"] == "E001"
    assert payload["items"][0]["loc"] == "arguments"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("context_kind", ["missing", "bad_json", "directory"])
def test_prompt_cli_context_failures_are_structured(tmp_path: Path, context_kind: str) -> None:
    context = tmp_path / "context.json"
    if context_kind == "bad_json":
        context.write_text("{bad json", encoding="utf-8")
    elif context_kind == "directory":
        context.mkdir()

    result = _run(
        "app.cli.prompt",
        "--kind",
        "word",
        "--context",
        str(context),
        "--output",
        str(tmp_path / "prompt.txt"),
    )

    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["items"][0]["code"] == "E001"
    assert payload["items"][0]["loc"] == "context"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(("kind", "code"), [("word", "E001"), ("deck", "D001")])
def test_render_cli_missing_ir_has_target_code(tmp_path: Path, kind: str, code: str) -> None:
    result = _run(
        "app.cli.render",
        "--type",
        kind,
        str(tmp_path / "missing.json"),
        "--output",
        str(tmp_path / ("out.docx" if kind == "word" else "out.pptx")),
    )

    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["items"][0]["code"] == code
    assert "Traceback" not in result.stderr


def test_render_cli_unwritable_output_has_code_and_no_traceback(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")

    result = _run(
        "app.cli.render",
        "--type",
        "word",
        "samples/ir/word_valid_01_plain.json",
        "--output",
        str(blocked_parent / "out.docx"),
    )

    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["items"][0]["code"] == "E001"
    assert payload["items"][0]["loc"] == "output"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("suffix", ["pptx", "docx"])
def test_check_cli_corrupt_or_missing_office_file_writes_structured_report(tmp_path: Path, suffix: str) -> None:
    source = tmp_path / f"broken.{suffix}"
    if suffix == "docx":
        source.write_text("not a package", encoding="utf-8")
    output_dir = tmp_path / f"{suffix}-report"

    result = _run("app.cli.check", str(source), "--output-dir", str(output_dir))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["summary"]["pass"] is False
    assert payload["items"][0]["code"] == "E001"


def test_check_cli_wrong_extension_writes_e003_report(tmp_path: Path) -> None:
    source = tmp_path / "artifact.zip"
    source.write_bytes(b"not office")
    output_dir = tmp_path / "report"

    result = _run("app.cli.check", str(source), "--output-dir", str(output_dir))

    assert result.returncode == 1
    payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["items"][0]["code"] == "E003"
    assert "Traceback" not in result.stderr


def test_parse_cli_output_failure_has_code_and_no_traceback(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")

    result = _run(
        "app.cli.parse",
        "samples/input/quarterly_report.md",
        "--output",
        str(blocked_parent / "document.json"),
    )

    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["items"][0]["code"] == "E001"
    assert payload["items"][0]["loc"] == "output"
    assert "Traceback" not in result.stderr


def test_parse_cli_corrupt_input_and_unwritable_report_has_code_without_traceback(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.xlsx"
    source.write_bytes(b"not a workbook")
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")

    result = _run("app.cli.parse", str(source), "--output", str(blocked_parent / "document.json"))

    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["items"][0]["code"] == "E001"
    assert payload["items"][0]["loc"] == "output"
    assert "Traceback" not in result.stderr
