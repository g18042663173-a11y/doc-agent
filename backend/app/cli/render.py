from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.ir.report import format_validation_result
from app.ir.shell import validate_word_ir_text
from app.rendering.docx_renderer import render_word_ir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render validated IR into editable documents.")
    parser.add_argument("--type", choices=["word", "deck"], required=True)
    parser.add_argument("ir_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw = args.ir_path.read_text(encoding="utf-8")

    if args.type == "word":
        result = validate_word_ir_text(raw)
        if not result.ok or result.value is None:
            print(format_validation_result(result), file=sys.stderr)
            return 1
        output = render_word_ir(result.value, args.output)
        print(output)
        return 0

    print("Deck rendering is implemented in Step 3.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
