from __future__ import annotations

import sys
from pathlib import Path

from app.cli.errors import CodedArgumentParser, emit_cli_failure, io_failure
from app.ir.report import format_validation_result
from app.ir.shell import validate_deck_ir_text, validate_word_ir_text
from app.lint.pptx_lint import check_pptx
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Render validated IR into editable documents.")
    parser.add_argument("--type", choices=["word", "deck"], required=True)
    parser.add_argument("ir_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    failure_code = "E001" if args.type == "word" else "D001"
    try:
        raw = args.ir_path.read_text(encoding="utf-8")
    except Exception as exc:
        emit_cli_failure(io_failure(code=failure_code, loc="ir_path", operation="读取 IR", exc=exc))
        return 1

    if args.type == "word":
        result = validate_word_ir_text(raw)
        if not result.ok or result.value is None:
            print(format_validation_result(result), file=sys.stderr)
            return 1
        try:
            output = render_word_ir(result.value, args.output)
        except Exception as exc:
            emit_cli_failure(io_failure(code="E001", loc="output", operation="渲染或保存 DOCX", exc=exc))
            return 1
        print(output)
        return 0

    result = validate_deck_ir_text(raw)
    if not result.ok or result.value is None:
        print(format_validation_result(result), file=sys.stderr)
        return 1
    try:
        output = render_deck_ir(result.value, args.output)
        report = check_pptx(output, classification=result.value.meta.classification)
    except Exception as exc:
        emit_cli_failure(io_failure(code="D001", loc="output", operation="渲染、保存或复检 PPTX", exc=exc))
        return 1
    if not report.summary["pass"]:
        for item in report.items:
            if item.level == "Error":
                slide = "-" if item.slide is None else str(item.slide)
                print(f"[{item.level}] {item.code} slide {slide}: {item.message}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
