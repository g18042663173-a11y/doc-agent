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


def test_parse_pptx_extracts_titles_bodies_tables_and_notes(tmp_path: Path) -> None:
    from app.parsers.pptx_parser import parse_pptx

    path = tmp_path / "项目汇报.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "项目汇报"
    slide.placeholders[1].text = "主链路已经打通"
    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1))
    table = table_shape.table
    table.cell(0, 0).text = "事项"
    table.cell(0, 1).text = "状态"
    table.cell(1, 0).text = "Word 输出"
    table.cell(1, 1).text = "完成"
    slide.notes_slide.notes_text_frame.text = "演讲备注"
    prs.save(path)

    ir = parse_pptx(path)

    slide_summary = ir.content.slides[0]
    assert ir.source.format == "pptx"
    assert slide_summary.index == 1
    assert slide_summary.title == "项目汇报"
    assert "主链路已经打通" in slide_summary.bodies
    assert slide_summary.tables[0]["header"] == ["事项", "状态"]
    assert slide_summary.tables[0]["rows"] == [["Word 输出", "完成"]]
    assert slide_summary.notes == "演讲备注"


def test_parse_pptx_records_transition_warning(tmp_path: Path) -> None:
    from app.parsers.pptx_parser import parse_pptx

    path = tmp_path / "transition.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "带切换"
    prs.save(path)
    _inject_transition(path)

    ir = parse_pptx(path)

    assert any("transition" in warning for warning in ir.content.slides[0].shape_warnings)


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
