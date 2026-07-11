from __future__ import annotations

from pathlib import Path
import sys

from app.cli.errors import CodedArgumentParser, emit_cli_failure, io_failure
from app.cli.parse import parse_file
from app.generation.analysis import (
    build_analysis_prompt,
    format_analysis,
    measure_document,
    validate_analysis_text,
)
from app.generators.interface import generator_from_name
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.repair import repair_generated_text
from app.ir.report import format_validation_result


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Analyze a source file and recommend Deck page-count/depth options.")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--generator", choices=["stub", "nga", "codex"], default="stub")
    parser.add_argument("--output", type=Path, default=Path("analysis.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = parse_file(args.input_file)
        metrics = measure_document(document)
        prompt = build_analysis_prompt(document, metrics)
        generator = generator_from_name(args.generator)
        raw = generator.generate(prompt, target="analysis")
        result = repair_generated_text(
            raw,
            target="analysis",
            generator=generator,
            validator=lambda current: validate_analysis_text(
                current,
                expected_metrics=metrics,
                expected_filename=document.source.filename,
            ),
        )
    except RuntimeError as exc:
        print(format_validation_result(_generator_failure(str(exc))), file=sys.stderr)
        return 1
    if not result.ok or result.value is None:
        print(format_validation_result(result), file=sys.stderr)
        return 1
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.value.model_dump_json(indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        emit_cli_failure(io_failure(code="E001", loc="output", operation="写入 analysis.json", exc=exc))
        return 1
    print(format_analysis(result.value))
    print(f"analysis_json: {args.output}")
    return 0


def _generator_failure(message: str) -> ValidationResult[None]:
    return ValidationResult(
        value=None,
        errors=[
            ValidationItem(
                code="D001",
                level="Error",
                loc="generator",
                message=f"generator 调用失败: {message}",
                suggestion="确认 generator 配置和网络后重试。",
            )
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
