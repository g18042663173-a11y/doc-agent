from __future__ import annotations
# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.cli.parse import parse_file
from app.generators.interface import generator_from_name
from app.generation.depth import GenerationOptions, generate_deck
from app.ir.deck_ir import DeckIR
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.repair import repair_ir_text
from app.ir.report import format_validation_result
from app.ir.word_ir import WordIR
from app.lint.docx_lint import check_docx, write_docx_reports
from app.lint.placeholder import write_placeholder_report
from app.lint.pptx_lint import check_pptx, write_reports
from app.prompting.builder import build_prompt
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an end-to-end document generation demo through a selected IR generator.")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--target", choices=["word", "deck"], required=True)
    parser.add_argument("--generator", choices=["stub", "nga", "codex"], default="stub")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "demo")
    parser.add_argument("--lint", action="store_true")
    parser.add_argument("--max-context-chars", type=int, default=12000)
    parser.add_argument("--max-output-chars", type=int, default=6000)
    parser.add_argument("--pages", type=int)
    parser.add_argument("--depth", choices=["概览", "标准", "详细"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    document_ir = parse_file(args.input_file)
    document_path = output_dir / "document_ir.json"
    document_path.write_text(document_ir.model_dump_json(indent=2) + "\n", encoding="utf-8")

    generator = generator_from_name(args.generator)
    generator_target = "word_ir" if args.target == "word" else "deck_ir"
    generation_options = GenerationOptions(pages=args.pages, depth=args.depth)
    if args.target == "word" and generation_options.enabled:
        build_parser().error("--pages/--depth are only supported for --target deck")
    prompt_path = output_dir / "prompt.txt"
    try:
        if args.target == "deck" and generation_options.enabled:
            attempt = generate_deck(
                document_ir,
                generator=generator,
                options=generation_options,
                max_context_chars=args.max_context_chars,
                max_output_chars=args.max_output_chars,
            )
            prompt_path.write_text(next(iter(attempt.prompts.values())), encoding="utf-8")
            prompts_dir = output_dir / "prompts"
            prompts_dir.mkdir(parents=True, exist_ok=True)
            for name, prompt_text in attempt.prompts.items():
                (prompts_dir / name).write_text(prompt_text, encoding="utf-8")
            (output_dir / "generation_manifest.json").write_text(
                json.dumps(attempt.manifest(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            raw_ir = attempt.raw_text
            validation = attempt.validation
        else:
            prompt = build_prompt(
                kind=args.target,
                context=document_ir,
                max_context_chars=args.max_context_chars,
                max_output_chars=args.max_output_chars,
            )
            prompt_path.write_text(prompt, encoding="utf-8")
            raw_ir = generator.generate(prompt, target=generator_target)
            validation = repair_ir_text(raw_ir, target=generator_target, generator=generator)
    except RuntimeError as exc:
        print(format_validation_result(_generator_failure(args.target, str(exc))), file=sys.stderr)
        return 1
    raw_path = output_dir / "raw_ir.txt"
    raw_path.write_text(raw_ir.strip() + "\n", encoding="utf-8")
    if not validation.ok or validation.value is None:
        print(format_validation_result(validation), file=sys.stderr)
        return 1

    if args.target == "word":
        word_ir = WordIR.model_validate(validation.value)
        generated_ir_path = output_dir / "word_ir.json"
        generated_ir_path.write_text(word_ir.model_dump_json(indent=2) + "\n", encoding="utf-8")
        artifact = render_word_ir(word_ir, output_dir / "word.docx")
        report_obj = check_docx(artifact, classification=word_ir.meta.classification)
        report, _ = write_docx_reports(report_obj, output_dir)
    else:
        deck_ir = DeckIR.model_validate(validation.value)
        generated_ir_path = output_dir / "deck_ir.json"
        generated_ir_path.write_text(deck_ir.model_dump_json(indent=2, by_alias=True) + "\n", encoding="utf-8")
        artifact = render_deck_ir(deck_ir, output_dir / "deck.pptx")
        if args.lint:
            report_obj = check_pptx(artifact, classification=deck_ir.meta.classification)
            report, _ = write_reports(report_obj, output_dir)
        else:
            report = write_placeholder_report([artifact], output_dir)
    print(f"document_ir: {document_path}")
    print(f"prompt: {prompt_path}")
    print(f"raw_ir: {raw_path}")
    print(f"generated_ir: {generated_ir_path}")
    print(f"artifact: {artifact}")
    print(f"report: {report}")
    return 0


def _generator_failure(target: str, message: str) -> ValidationResult[None]:
    code = "E001" if target == "word" else "D001"
    return ValidationResult(
        value=None,
        errors=[
            ValidationItem(
                code=code,
                level="Error",
                loc="generator",
                message=f"generator 调用失败: {message}",
                suggestion="确认显式选择的 generator 已配置环境变量和网络访问，然后重试。",
            )
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
