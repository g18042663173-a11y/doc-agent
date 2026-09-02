from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer

from doc_agent.config import get_settings
from doc_agent.compliance.pptx import HuaweiPptxComplianceChecker
from doc_agent.exporters.preview import export_pages_to_images
from doc_agent.ir.schemas import DeckIR, DocumentIR, WordIR, load_json, save_json
from doc_agent.parsers.router import ParserRouter
from doc_agent.planners.deck_planner import DeckPlanner
from doc_agent.planners.word_planner import WordPlanner
from doc_agent.renderers.docx_python_renderer import PythonDocxRenderer
from doc_agent.renderers.huawei_skill_renderer import HuaweiSkillRenderer
from doc_agent.renderers.pptx_python_renderer import PythonPptxRenderer
from doc_agent.validators.output_validator import OutputValidator
from doc_agent.workflow import run_generate


app = typer.Typer(no_args_is_help=True, help="Enterprise document generation MVP")


@app.command("parse")
def parse_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(..., "--out", "-o"),
) -> None:
    document_ir = ParserRouter().parse(input_path)
    save_json(document_ir, out)
    typer.echo(f"Saved DocumentIR: {out}")


@app.command("plan")
def plan_command(
    document_ir_path: Path = typer.Argument(..., exists=True, readable=True),
    target: Literal["pptx", "docx"] = typer.Option("pptx", "--target"),
    out: Path = typer.Option(..., "--out", "-o"),
    slides: int = typer.Option(8, "--slides"),
) -> None:
    document_ir = load_json(document_ir_path, DocumentIR)
    if target == "pptx":
        planned = DeckPlanner().plan(document_ir, target_slide_count=slides)
    else:
        planned = WordPlanner().plan(document_ir)
    save_json(planned, out)
    typer.echo(f"Saved {target} IR: {out}")


@app.command("render")
def render_command(
    ir_path: Path = typer.Argument(..., exists=True, readable=True),
    target: Literal["pptx", "docx"] = typer.Option("pptx", "--target"),
    out: Path = typer.Option(..., "--out", "-o"),
) -> None:
    settings = get_settings()
    if target == "pptx":
        deck = load_json(ir_path, DeckIR)
        if settings.ppt_renderer == "stub":
            renderer = PythonPptxRenderer()
        elif settings.ppt_renderer == "hw_skill":
            renderer = HuaweiSkillRenderer()
        elif settings.ppt_renderer == "presenton":
            raise typer.BadParameter("PPT_RENDERER=presenton is no longer supported. Use stub or hw_skill.")
        else:
            raise typer.BadParameter(f"Unsupported PPT_RENDERER: {settings.ppt_renderer}")
        result = renderer.render(deck.model_dump(mode="json"), out)
    else:
        word = load_json(ir_path, WordIR)
        result = PythonDocxRenderer().render(word.model_dump(mode="json"), out)

    errors = OutputValidator().validate(result, target)
    if errors:
        raise typer.BadParameter("; ".join(errors))
    typer.echo(f"Rendered {target}: {result}")


@app.command("generate")
def generate_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    target: Literal["pptx", "docx"] = typer.Option("pptx", "--target"),
    out: Path = typer.Option(..., "--out", "-o"),
    slides: int = typer.Option(8, "--slides"),
) -> None:
    result = run_generate(input_path, target, out, target_slide_count=slides)
    typer.echo(f"Generated {target}: {result}")


@app.command("review-pptx")
def review_pptx_command(
    pptx_path: Path = typer.Argument(..., exists=True, readable=True),
    json_output: bool = typer.Option(False, "--json", help="Print the structured compliance report as JSON."),
    fail_on_error: bool = typer.Option(False, "--fail-on-error", help="Exit non-zero when Error items are found."),
) -> None:
    report = HuaweiPptxComplianceChecker().check(pptx_path)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
    else:
        typer.echo(f"Score: {report.score}")
        typer.echo(report.summary)
        for item in report.items:
            location = f"slide {item.slide_index}: " if item.slide_index is not None else ""
            typer.echo(f"[{item.severity}] {location}{item.code} - {item.message}")
    if fail_on_error and report.error_count > 0:
        raise typer.Exit(code=1)


@app.command("export-images")
def export_images_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    out_dir: Path = typer.Option(..., "--out-dir", "-o"),
) -> None:
    images = export_pages_to_images(input_path, out_dir)
    typer.echo(f"Exported {len(images)} images to {out_dir}")
