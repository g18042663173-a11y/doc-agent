from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_check_pptx_rendered_deck_has_no_errors(tmp_path: Path) -> None:
    from app.ir.deck_ir import DeckIR
    from app.lint.pptx_lint import check_pptx
    from app.rendering.pptx_renderer import render_deck_ir

    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "合规", "classification": "HUAWEI CONFIDENTIAL"},
            "slides": [{"layout": "cover", "title": "合规"}],
        }
    )
    path = render_deck_ir(deck, tmp_path / "ok.pptx")

    report = check_pptx(path, classification="HUAWEI CONFIDENTIAL")

    assert report.summary["errors"] == 0
    assert report.summary["pass"] is True


def test_check_pptx_reports_missing_footer_and_bad_font(tmp_path: Path) -> None:
    from app.lint.pptx_lint import check_pptx

    path = tmp_path / "bad.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shape = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    run = shape.text_frame.paragraphs[0].add_run()
    run.text = "Bad font"
    run.font.name = "Comic Sans MS"
    prs.save(path)

    report = check_pptx(path, classification="HUAWEI CONFIDENTIAL")
    codes = [item.code for item in report.items]

    assert "HW-E01" in codes
    assert "HW-E02" in codes


def test_check_pptx_reports_transition_and_large_table_and_slide_count(tmp_path: Path) -> None:
    from app.lint.pptx_lint import check_pptx

    path = tmp_path / "violations.pptx"
    prs = Presentation()
    for index in range(31):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_textbox(Inches(0.6), Inches(7.0), Inches(4), Inches(0.3)).text = "HUAWEI CONFIDENTIAL"
        if index == 0:
            slide.shapes.add_table(13, 9, Inches(1), Inches(1), Inches(8), Inches(4))
    prs.save(path)
    _inject_transition(path)

    report = check_pptx(path, classification="HUAWEI CONFIDENTIAL")
    codes = [item.code for item in report.items]

    assert "HW-E03" in codes
    assert "HW-W04" in codes
    assert "HW-W05" in codes


def test_check_cli_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    import os
    import subprocess

    from app.ir.deck_ir import DeckIR
    from app.rendering.pptx_renderer import render_deck_ir

    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "报告", "classification": "HUAWEI CONFIDENTIAL"},
            "slides": [{"layout": "cover", "title": "报告"}],
        }
    )
    pptx = render_deck_ir(deck, tmp_path / "report.pptx")
    out = tmp_path / "reports"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli.check",
            str(pptx),
            "--classification",
            "HUAWEI CONFIDENTIAL",
            "--output-dir",
            str(out),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(BACKEND)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (out / "report.json").exists()
    assert (out / "report.md").exists()


def _inject_transition(path: Path) -> None:
    temp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temp, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "ppt/slides/slide1.xml":
                xml = data.decode("utf-8")
                xml = xml.replace("</p:sld>", "<p:transition/></p:sld>")
                data = xml.encode("utf-8")
            target.writestr(item, data)
    shutil.move(temp, path)
