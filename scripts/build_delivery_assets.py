from __future__ import annotations
# ruff: noqa: E402

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from docx import Document
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.cli.parse import parse_file
from app.ir.deck_ir import DeckIR
from app.ir.validation import validate_word_ir
from app.lint.pptx_lint import check_pptx
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


INPUT_DIR = ROOT / "samples" / "input"
MATRIX_DIR = INPUT_DIR / "parser_matrix"
IR_DIR = ROOT / "samples" / "ir"
EXPECTED_DIR = ROOT / "samples" / "expected"
SAMPLE_OUTPUT_DIR = ROOT / "samples" / "output"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic delivery fixtures and expected assets.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root; intended for test-only temp copies.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.root.resolve() != ROOT:
        raise SystemExit("--root override is reserved for future isolated builders")
    generated = generate_delivery_assets()
    print(f"generated {len(generated)} delivery assets")
    return 0


def generate_delivery_assets() -> list[Path]:
    for directory in (INPUT_DIR, MATRIX_DIR, IR_DIR, EXPECTED_DIR, SAMPLE_OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    generated = [
        _make_appendix_docx(INPUT_DIR / "需求说明.docx"),
        _make_appendix_xlsx(INPUT_DIR / "销售台账.xlsx"),
        _make_appendix_pptx(INPUT_DIR / "项目汇报.pptx"),
    ]
    generated.extend(_make_parser_matrix())
    generated.extend(_write_expected_assets())
    generated.append(_write_expected_hash_manifest())
    return generated


def _make_appendix_docx(path: Path) -> Path:
    document = Document()
    document.core_properties.title = "需求说明"
    document.add_heading("需求说明", level=0)
    document.add_paragraph("本文件是脱敏的固定交付样例,用于验证 Word 输入解析主链路。")
    document.add_heading("一、建设目标", level=1)
    document.add_paragraph("形成可离线运行的文档解析、IR 校验与可编辑产物生成能力。")
    document.add_heading("1.1 功能范围", level=2)
    document.add_paragraph("支持 Markdown、Word、Excel、PowerPoint 四类输入。", style="List Bullet")
    document.add_paragraph("所有模型输出必须先通过 IR 校验。", style="List Bullet 2")
    document.add_heading("二、验收要求", level=1)
    table = document.add_table(rows=3, cols=3)
    for index, value in enumerate(("验收项", "判据", "责任角色")):
        table.cell(0, index).text = value
    for row, values in enumerate(
        (("结构解析", "标题、列表、表格顺序正确", "开发"), ("交付复检", "错误码与报告齐全", "评审")),
        start=1,
    ):
        for column, value in enumerate(values):
            table.cell(row, column).text = value
    document.add_paragraph("文本框内容仅用于验证不支持项 warning,不应进入正文。")
    document.save(path)
    _inject_docx_textbox(path)
    return path


def _inject_docx_textbox(path: Path) -> None:
    text_box = """
<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
     xmlns:v="urn:schemas-microsoft-com:vml">
  <w:r><w:pict><v:shape id="DeliveryTextBox" style="width:180pt;height:32pt" type="#_x0000_t202">
    <v:textbox><w:txbxContent><w:p><w:r><w:t>文本框降级样例</w:t></w:r></w:p></w:txbxContent></v:textbox>
  </v:shape></w:pict></w:r>
</w:p>
""".strip().encode("utf-8")
    _rewrite_zip_member(path, "word/document.xml", lambda data: data.replace(b"</w:body>", text_box + b"</w:body>"))


def _make_appendix_xlsx(path: Path) -> Path:
    workbook = Workbook()
    ledger = workbook.active
    ledger.title = "销售台账"
    ledger.merge_cells("A1:E1")
    ledger["A1"] = "区域销售台账"
    ledger.append(["区域", "负责人", "目标", "实际", "完成率"])
    for region, owner, target, actual in (
        ("华东", "同事A", 120, 126),
        ("华南", "同事B", 100, 96),
        ("西北", "同事C", 80, 82),
    ):
        row = ledger.max_row + 1
        ledger.append([region, owner, target, actual, f"=D{row}/C{row}"])

    target_sheet = workbook.create_sheet("目标配置")
    target_sheet.append(["区域", "季度目标"])
    for region, target in (("华东", 120), ("华南", 100), ("西北", 80)):
        target_sheet.append([region, target])

    summary = workbook.create_sheet("汇总")
    summary.append(["指标", "数值"])
    summary.append(["目标合计", "=SUM(销售台账!C3:C5)"])
    summary.append(["实际合计", "=SUM(销售台账!D3:D5)"])
    summary.append(["达成差额", "=B3-B2"])
    workbook.save(path)
    return path


def _make_appendix_pptx(path: Path) -> Path:
    presentation = Presentation()
    presentation.slide_width = Inches(13.34)
    presentation.slide_height = Inches(7.5)

    slide = presentation.slides.add_slide(presentation.slide_layouts[0])
    slide.shapes.title.text = "项目汇报"
    slide.placeholders[1].text = "脱敏固定解析样例"

    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "目录"
    slide.placeholders[1].text = "项目背景\n方案概览\n实施进展\n风险与计划"

    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "项目背景"
    slide.placeholders[1].text = "当前流程需要统一结构契约。\n离线环境要求全部自动测试可复现。"

    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "方案概览"
    slide.placeholders[1].text = "输入解析 → DocumentIR → 目标 IR → 可编辑产物 → 合规报告"

    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(6.0), Inches(0.5)).text_frame.text = "实施进展"
    table = slide.shapes.add_table(4, 3, Inches(0.8), Inches(1.4), Inches(8.0), Inches(2.2)).table
    for column, value in enumerate(("事项", "状态", "说明")):
        table.cell(0, column).text = value
    for row, values in enumerate(
        (("IR 契约", "完成", "三份 Schema 已冻结"), ("渲染链路", "完成", "DOCX/PPTX 可编辑"), ("内网接入", "待办", "需真实 NGA 协议")),
        start=1,
    ):
        for column, value in enumerate(values):
            table.cell(row, column).text = value

    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(6.0), Inches(0.5)).text_frame.text = "质量趋势"
    chart_data = CategoryChartData()
    chart_data.categories = ["第一周", "第二周", "第三周"]
    chart_data.add_series("通过用例", (120, 210, 288))
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(1.0),
        Inches(1.5),
        Inches(7.2),
        Inches(3.8),
        chart_data,
    ).chart
    chart.has_title = True
    chart.chart_title.text_frame.text = "自动测试通过数"
    slide.notes_slide.notes_text_frame.text = "演讲备注:测试数量只表示回归范围,不替代人工视觉终审。"

    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "风险与计划"
    slide.placeholders[1].text = "真实业务文件仍需人工提供。\nWindows 离线安装仍需真机验收。"
    slide.notes_slide.notes_text_frame.text = "演讲备注:优先验证内网依赖与字体环境。"

    presentation.slides.add_slide(presentation.slide_layouts[6])
    presentation.save(path)
    return path


def _make_parser_matrix() -> list[Path]:
    generated: list[Path] = []

    generated.append(_write_text(MATRIX_DIR / "md_empty.md", ""))
    (MATRIX_DIR / "md_corrupt.md").write_bytes(b"\x81")
    generated.append(MATRIX_DIR / "md_corrupt.md")
    rows = "\n".join(f"| 事项{i:02d} | 完成 |" for i in range(1, 26))
    generated.append(
        _write_text(MATRIX_DIR / "md_large.md", f"# 大表周报\n\n| 事项 | 状态 |\n| --- | --- |\n{rows}\n")
    )
    generated.append(
        _write_text(
            MATRIX_DIR / "md_degraded.md",
            "# 畸形表格\n\n| 事项 | 状态 |\n| --- | --- |\n| 缺列 |\n| 完整事项 | 完成 |\n",
        )
    )

    empty_doc = Document()
    empty_doc.save(MATRIX_DIR / "docx_empty.docx")
    generated.append(MATRIX_DIR / "docx_empty.docx")
    (MATRIX_DIR / "docx_corrupt.docx").write_bytes(b"not-a-docx")
    generated.append(MATRIX_DIR / "docx_corrupt.docx")
    large_doc = Document()
    large_doc.add_heading("超长周报", level=1)
    large_doc.add_paragraph("长" * 2101)
    large_doc.save(MATRIX_DIR / "docx_large.docx")
    generated.append(MATRIX_DIR / "docx_large.docx")
    shutil.copyfile(INPUT_DIR / "需求说明.docx", MATRIX_DIR / "docx_degraded.docx")
    generated.append(MATRIX_DIR / "docx_degraded.docx")

    empty_book = Workbook()
    empty_book.save(MATRIX_DIR / "xlsx_empty.xlsx")
    generated.append(MATRIX_DIR / "xlsx_empty.xlsx")
    (MATRIX_DIR / "xlsx_corrupt.xlsx").write_bytes(b"not-an-xlsx")
    generated.append(MATRIX_DIR / "xlsx_corrupt.xlsx")
    chart_book = Workbook()
    chart_sheet = chart_book.active
    chart_sheet.title = "图表降级"
    chart_sheet.append(["月份", "完成数"])
    chart_sheet.append(["一月", 10])
    chart_sheet.append(["二月", 12])
    chart = BarChart()
    chart.title = "完成趋势"
    chart.add_data(Reference(chart_sheet, min_col=2, min_row=1, max_row=3), titles_from_data=True)
    chart.set_categories(Reference(chart_sheet, min_col=1, min_row=2, max_row=3))
    chart_sheet.add_chart(chart, "D2")
    chart_book.save(MATRIX_DIR / "xlsx_degraded.xlsx")
    generated.append(MATRIX_DIR / "xlsx_degraded.xlsx")

    Presentation().save(MATRIX_DIR / "pptx_empty.pptx")
    generated.append(MATRIX_DIR / "pptx_empty.pptx")
    (MATRIX_DIR / "pptx_corrupt.pptx").write_bytes(b"not-a-pptx")
    generated.append(MATRIX_DIR / "pptx_corrupt.pptx")
    large_presentation = Presentation()
    slide = large_presentation.slides.add_slide(large_presentation.slide_layouts[6])
    slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(5.0), Inches(0.5)).text_frame.text = "超长表格"
    table = slide.shapes.add_table(26, 2, Inches(0.8), Inches(1.2), Inches(6.0), Inches(5.0)).table
    table.cell(0, 0).text = "事项"
    table.cell(0, 1).text = "状态"
    for row in range(1, 26):
        table.cell(row, 0).text = f"事项{row:02d}"
        table.cell(row, 1).text = "完成"
    large_presentation.save(MATRIX_DIR / "pptx_large.pptx")
    generated.append(MATRIX_DIR / "pptx_large.pptx")
    shutil.copyfile(INPUT_DIR / "synthetic" / "pptx_03_smartart_equivalent.pptx", MATRIX_DIR / "pptx_degraded.pptx")
    generated.append(MATRIX_DIR / "pptx_degraded.pptx")

    manifest = {
        "schema_version": 1,
        "categories": ["normal", "empty", "corrupt", "large", "degraded"],
        "formats": {
            "md": [
                _fixture("normal", "samples/input/parser_samples/md_sample_01.md", "success"),
                _fixture("empty", "samples/input/parser_matrix/md_empty.md", "success"),
                _fixture("corrupt", "samples/input/parser_matrix/md_corrupt.md", "error", error="E001"),
                _fixture("large", "samples/input/parser_matrix/md_large.md", "success", warning="W103"),
                _fixture("degraded", "samples/input/parser_matrix/md_degraded.md", "success", warning="malformed table rows"),
            ],
            "docx": [
                _fixture("normal", "samples/input/parser_samples/docx_sample_01.docx", "success"),
                _fixture("empty", "samples/input/parser_matrix/docx_empty.docx", "success"),
                _fixture("corrupt", "samples/input/parser_matrix/docx_corrupt.docx", "error", error="E001"),
                _fixture("large", "samples/input/parser_matrix/docx_large.docx", "success", warning="W103"),
                _fixture("degraded", "samples/input/parser_matrix/docx_degraded.docx", "success", warning="unsupported text boxes"),
            ],
            "xlsx": [
                _fixture("normal", "samples/input/parser_samples/xlsx_sample_01.xlsx", "success"),
                _fixture("empty", "samples/input/parser_matrix/xlsx_empty.xlsx", "success"),
                _fixture("corrupt", "samples/input/parser_matrix/xlsx_corrupt.xlsx", "error", error="E001"),
                _fixture("large", "samples/input/synthetic/xlsx_04_large_ledger_50000.xlsx", "success", warning="W103"),
                _fixture("degraded", "samples/input/parser_matrix/xlsx_degraded.xlsx", "success", warning="chart unsupported"),
            ],
            "pptx": [
                _fixture("normal", "samples/input/项目汇报.pptx", "success"),
                _fixture("empty", "samples/input/parser_matrix/pptx_empty.pptx", "success"),
                _fixture("corrupt", "samples/input/parser_matrix/pptx_corrupt.pptx", "error", error="E001"),
                _fixture("large", "samples/input/parser_matrix/pptx_large.pptx", "success", warning="W103"),
                _fixture("degraded", "samples/input/parser_matrix/pptx_degraded.pptx", "success", warning="SmartArt"),
            ],
        },
    }
    manifest_path = MATRIX_DIR / "manifest.json"
    _write_json(manifest_path, manifest)
    generated.append(manifest_path)
    return generated


def _fixture(category: str, path: str, outcome: str, *, error: str | None = None, warning: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"category": category, "path": path, "outcome": outcome}
    if error:
        payload["expected_error"] = error
    if warning:
        payload["expected_warning_contains"] = warning
    return payload


def _write_expected_assets() -> list[Path]:
    generated: list[Path] = []
    appendix_expected = {
        path.name: _document_ir_facts(parse_file(path))
        for path in (INPUT_DIR / "需求说明.docx", INPUT_DIR / "销售台账.xlsx", INPUT_DIR / "项目汇报.pptx")
    }
    generated.append(_write_json(EXPECTED_DIR / "appendix_b_document_ir.expected.json", appendix_expected))

    presentation_facts = appendix_expected["项目汇报.pptx"]
    generated.append(_write_json(EXPECTED_DIR / "项目汇报.pptx.expected.json", presentation_facts))

    word_expected: dict[str, Any] = {}
    word_output_dir = SAMPLE_OUTPUT_DIR / "word"
    word_output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(IR_DIR.glob("word_valid_*.json")):
        result = validate_word_ir(json.loads(path.read_text(encoding="utf-8")))
        if result.value is None:
            raise RuntimeError(f"invalid official WordIR sample: {path}")
        output = render_word_ir(result.value, word_output_dir / f"{path.stem}.docx")
        word_expected[path.stem] = _docx_facts(output)
    generated.append(_write_json(EXPECTED_DIR / "word_official_outputs.expected.json", word_expected))

    deck_payload = json.loads((IR_DIR / "deck_valid_full.json").read_text(encoding="utf-8"))
    deck = DeckIR.model_validate(deck_payload)
    deck_output_dir = SAMPLE_OUTPUT_DIR / "deck"
    deck_output_dir.mkdir(parents=True, exist_ok=True)
    deck_output = render_deck_ir(deck, deck_output_dir / "deck_valid_full.pptx")
    generated.append(_write_json(EXPECTED_DIR / "deck_valid_full.expected.json", _deck_facts(deck, deck_output)))
    return generated


def _document_ir_facts(document_ir) -> dict[str, Any]:
    return {
        "format": document_ir.source.format,
        "stats": document_ir.stats.model_dump(mode="json"),
        "warning_fragments": sorted(_warning_fragment(value) for value in document_ir.warnings),
        "block_types": [block.type for block in document_ir.content.blocks],
        "outline": [{"level": item.level, "text": item.text} for item in document_ir.content.outline],
        "sheets": [
            {
                "name": sheet.name,
                "nrows": sheet.nrows,
                "ncols": sheet.ncols,
                "header_guess": sheet.header_guess,
                "formula_count": sheet.formula_count,
                "merged_count": sheet.merged_count,
            }
            for sheet in document_ir.content.sheets
        ],
        "slides": [
            {
                "index": slide.index,
                "title": slide.title,
                "body_count": len(slide.bodies),
                "table_count": len(slide.tables),
                "notes": slide.notes,
            }
            for slide in document_ir.content.slides
        ],
    }


def _warning_fragment(value: str) -> str:
    for fragment in ("W103", "unsupported text boxes", "chart unsupported", "SmartArt"):
        if fragment in value:
            return fragment
    return value


def _docx_facts(path: Path) -> dict[str, Any]:
    document = Document(path)
    xml = _read_zip_text(path, "word/styles.xml") + _read_zip_text(path, "word/document.xml")
    return {
        "paragraphs": [paragraph.text for paragraph in document.paragraphs if paragraph.text],
        "paragraph_styles": [paragraph.style.name for paragraph in document.paragraphs if paragraph.text],
        "tables": [[[cell.text for cell in row.cells] for row in table.rows] for table in document.tables],
        "header": document.sections[0].header.paragraphs[0].text,
        "footer": document.sections[0].footer.paragraphs[0].text,
        "has_theme_red": "C7000B" in xml,
        "has_legacy_word_blue": "4F81BD" in xml.upper(),
    }


def _deck_facts(deck: DeckIR, path: Path) -> dict[str, Any]:
    presentation = Presentation(path)
    report = check_pptx(path, classification=deck.meta.classification)
    return {
        "slide_count": len(presentation.slides),
        "layouts": [slide.layout for slide in deck.slides],
        "titles": [getattr(slide, "title", None) for slide in deck.slides],
        "editable_table_slides": [
            index
            for index, slide in enumerate(presentation.slides, start=1)
            if any(getattr(shape, "has_table", False) for shape in slide.shapes)
        ],
        "editable_chart_slides": [
            index
            for index, slide in enumerate(presentation.slides, start=1)
            if any(getattr(shape, "has_chart", False) for shape in slide.shapes)
        ],
        "lint": {
            "errors": report.summary["errors"],
            "warnings": report.summary["warnings"],
            "infos": report.summary["infos"],
            "pass": report.summary["pass"],
        },
    }


def _write_expected_hash_manifest() -> Path:
    assets = sorted(path for path in EXPECTED_DIR.glob("*.json") if path.name != "manifest.json")
    payload = {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "assets": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in assets
        ],
    }
    return _write_json(EXPECTED_DIR / "manifest.json", payload)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _write_json(path: Path, value: Any) -> Path:
    return _write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _read_zip_text(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as package:
        return package.read(member).decode("utf-8")


def _rewrite_zip_member(path: Path, member: str, transform) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == member:
                data = transform(data)
            target.writestr(info, data)
    temp.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
