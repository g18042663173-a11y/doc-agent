from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
PY_ENV = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}


def test_parse_cli_writes_document_ir_json(tmp_path: Path) -> None:
    output = tmp_path / "doc.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli.parse",
            "samples/input/quarterly_report.md",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ir_type"] == "document"
    assert payload["source"]["format"] == "md"


def test_prompt_cli_writes_prompt_from_context(tmp_path: Path) -> None:
    context = tmp_path / "doc.json"
    prompt = tmp_path / "prompt.txt"
    subprocess.run(
        [sys.executable, "-m", "app.cli.parse", "samples/input/quarterly_report.md", "--output", str(context)],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        capture_output=True,
        check=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli.prompt",
            "--kind",
            "word",
            "--context",
            str(context),
            "--output",
            str(prompt),
        ],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "WordIR v1.0" in prompt.read_text(encoding="utf-8")


def test_demo_e2e_stub_word_generates_docx(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/demo_e2e.py",
            "samples/input/quarterly_report.md",
            "--target",
            "word",
            "--generator",
            "stub",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "document_ir.json").exists()
    assert (output_dir / "prompt.txt").exists()
    assert (output_dir / "word.docx").exists()


def test_demo_e2e_stub_deck_generates_linted_pptx(tmp_path: Path) -> None:
    output_dir = tmp_path / "deck-out"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/demo_e2e.py",
            "samples/input/quarterly_report.md",
            "--target",
            "deck",
            "--generator",
            "stub",
            "--lint",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    pptx = output_dir / "deck.pptx"
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert pptx.exists()
    assert 5 <= len(Presentation(str(pptx)).slides) <= 12
    assert report["summary"]["pass"] is True
